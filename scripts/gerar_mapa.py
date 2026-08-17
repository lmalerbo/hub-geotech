"""
Gera o mapa (PDF) no estilo do projeto de colheita da usina: talhoes inteiros
preenchidos com cor solida pela parte majoritaria (votacao espacial das
linhas classificadas dentro de cada talhao), numero do talhao, carimbo
lateral com metadados, seta norte e legenda -- etapa entre a classificacao e
o relatorio de qualidade no pipeline.

Uso:
    python gerar_mapa.py <shapefile_classificado.shp> <dwg_contexto1.dwg> [<dwg_contexto2.dwg> ...] <saida.pdf> \
        --cliente "US PEDRA" --fazenda "10003 - Pedra" --safra "26/27"
"""

import argparse
import colorsys
import re
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import ezdxf
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, FancyArrow
from shapely.geometry import Polygon
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).parent))
from converter_dwg import converter_arquivo  # noqa: E402

warnings.filterwarnings("ignore")

PADRAO_LAYER_TALHAO = re.compile(r"^\d{5,}$")

# faixa plausivel de UTM pra regiao (SP/MG, zona 23S) -- descarta geometria de
# espaco de papel/detalhe (coordenadas de folha, ex: 2000-6500) que aparece
# misturada com a geometria georreferenciada real em alguns DWGs
UTM_X_MIN, UTM_X_MAX = 100_000, 999_999
UTM_Y_MIN, UTM_Y_MAX = 7_000_000, 8_000_000

COR_SEM_PARTE = "#d9d5c4"  # talhao sem linha classificada dentro (contexto)

# angulo aureo (~137.508deg): cada cor sucessiva salta esse tanto no circulo
# de matiz, o que espalha as cores de forma maximamente distinta mesmo pra
# muitas partes (ao contrario de uma paleta fixa curta, que repete e fica
# impossivel de distinguir com 50+ partes) -- alterna saturacao/brilho a
# cada volta pra aumentar ainda mais o contraste entre indices vizinhos
_ANGULO_AUREO = 137.508


def gerar_paleta(n: int) -> list[str]:
    cores = []
    for i in range(n):
        matiz = (i * _ANGULO_AUREO) % 360 / 360
        volta = i // 12  # a cada 12 cores, varia sat/brilho pra reforcar contraste
        sat = [0.78, 0.62, 0.90][volta % 3]
        val = [0.88, 0.72, 0.95][volta % 3]
        r, g, b = colorsys.hsv_to_rgb(matiz, sat, val)
        cores.append("#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255)))
    return cores


def _coordenada_plausivel(minx, miny, maxx, maxy) -> bool:
    return (UTM_X_MIN <= minx and maxx <= UTM_X_MAX
            and UTM_Y_MIN <= miny and maxy <= UTM_Y_MAX)


def extrair_talhoes(dwg_ou_dxf: str, pasta_temp: Path) -> list[tuple[Polygon, str]]:
    """Retorna lista de (poligono, codigo_talhao) de layers numericas
    (talhoes), olhando modelspace e layouts de papel (alguns arquivos
    guardam o conteudo direto no layout 'Paisagem')."""
    caminho = Path(dwg_ou_dxf)
    if caminho.suffix.lower() == ".dwg":
        caminho = converter_arquivo(str(caminho), str(pasta_temp))

    doc = ezdxf.readfile(caminho)
    espacos = [doc.modelspace()] + [doc.layout(n) for n in doc.layout_names() if n != "Model"]

    resultado = []
    for espaco in espacos:
        for e in espaco:
            if e.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            layer = e.dxf.layer
            if not PADRAO_LAYER_TALHAO.match(layer):
                continue
            if e.dxftype() == "LWPOLYLINE":
                pts = list(e.get_points("xy"))
            else:
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            if len(pts) < 3:
                continue
            try:
                poly = Polygon(pts)
            except Exception:
                continue
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty or not _coordenada_plausivel(*poly.bounds):
                continue
            resultado.append((poly, layer))
    return resultado


def extrair_textos_contexto(dwg_ou_dxf: str, pasta_temp: Path) -> list[tuple[str, tuple]]:
    """Textos de camadas NAO numericas (nome de sede, varzea, secao vizinha
    etc) -- servem de referencia visual, nao sao talhao."""
    caminho = Path(dwg_ou_dxf)
    if caminho.suffix.lower() == ".dwg":
        caminho = converter_arquivo(str(caminho), str(pasta_temp))

    doc = ezdxf.readfile(caminho)
    espacos = [doc.modelspace()] + [doc.layout(n) for n in doc.layout_names() if n != "Model"]

    textos = []
    for espaco in espacos:
        for e in espaco:
            if e.dxftype() not in ("TEXT", "MTEXT"):
                continue
            if PADRAO_LAYER_TALHAO.match(e.dxf.layer):
                continue
            txt = e.dxf.text if e.dxftype() == "TEXT" else e.plain_text()
            txt = txt.strip()
            if not txt or txt.isdigit():
                continue
            pos = e.dxf.insert
            if not _coordenada_plausivel(pos[0], pos[1], pos[0], pos[1]):
                continue
            textos.append((txt, (round(pos[0], 1), round(pos[1], 1))))
    return list(dict.fromkeys(textos))  # dedup preservando ordem (mesmo texto+posicao repetido em modelspace/paisagem)


def atribuir_parte_por_talhao(talhoes: list[tuple[Polygon, str]], gdf_utm: gpd.GeoDataFrame) -> dict:
    """Vota espacialmente: cada talhao recebe a parte com mais comprimento de
    linha classificada dentro dele (linhas sem talhao contendo caem no mais
    proximo pelo centroide)."""
    geoms = list(gdf_utm.geometry)
    partes_linha = list(gdf_utm["FIELD_NAME"])
    comprimentos = [g.length for g in geoms]

    poligonos = [p for p, _ in talhoes]
    tree = STRtree(poligonos)

    peso_por_talhao = [defaultdict(float) for _ in poligonos]

    for geom, parte, comp in zip(geoms, partes_linha, comprimentos):
        centro = geom.centroid
        candidatos = tree.query(centro)
        idx_contem = next((i for i in candidatos if poligonos[i].contains(centro)), None)
        if idx_contem is None:
            if len(candidatos) == 0:
                continue
            idx_contem = min(candidatos, key=lambda i: poligonos[i].distance(centro))
        peso_por_talhao[idx_contem][parte] += comp

    resultado = {}
    for i, (poly, codigo) in enumerate(talhoes):
        if peso_por_talhao[i]:
            resultado[codigo] = max(peso_por_talhao[i], key=peso_por_talhao[i].get)
        else:
            resultado[codigo] = None
    return resultado


def gerar_mapa(shp_classificado: str, dwgs_contexto: list[str], saida_pdf: str,
               cliente: str, fazenda: str, safra: str, pasta_temp: str = "linhas-vant/_mapa_temp"):
    pasta_temp = Path(pasta_temp)
    pasta_temp.mkdir(parents=True, exist_ok=True)

    gdf = gpd.read_file(shp_classificado)
    utm = gdf.estimate_utm_crs()
    gdf_utm = gdf.to_crs(utm)

    talhoes_brutos = []
    textos_contexto = []
    for dwg in dwgs_contexto:
        talhoes_brutos.extend(extrair_talhoes(dwg, pasta_temp))
        textos_contexto.extend(extrair_textos_contexto(dwg, pasta_temp))

    # descarta poligono(s) de contorno geral da fazenda (muito maior que a
    # mediana dos talhoes reais) -- esses nao sao talhao, sao so a fronteira
    # externa, e nao devem ser coloridos por votacao de parte
    areas = sorted(p.area for p, _ in talhoes_brutos)
    mediana_area = areas[len(areas) // 2] if areas else 0
    contorno_geral = [(p, c) for p, c in talhoes_brutos if mediana_area > 0 and p.area > mediana_area * 20]
    talhoes = [(p, c) for p, c in talhoes_brutos if not (mediana_area > 0 and p.area > mediana_area * 20)]
    talhoes.sort(key=lambda t: t[0].area, reverse=True)
    print(f"  {len(talhoes)} talhao(oes) de contexto extraido(s) ({len(contorno_geral)} contorno(s) geral(is) descartado(s) da votacao)")

    partes = sorted(gdf_utm["FIELD_NAME"].unique())
    print(f"  {len(partes)} parte(s) classificada(s)")
    paleta = gerar_paleta(len(partes))
    cores = {parte: paleta[i] for i, parte in enumerate(partes)}

    parte_do_talhao = atribuir_parte_por_talhao(talhoes, gdf_utm)

    minx, miny, maxx, maxy = gdf_utm.total_bounds
    largura, altura = maxx - minx, maxy - miny
    paisagem = largura >= altura
    figsize = (16.5, 11.7) if paisagem else (11.7, 16.5)

    fig, ax = plt.subplots(figsize=figsize, dpi=150)

    for poly, _ in contorno_geral:
        xs, ys = poly.exterior.xy
        ax.fill(xs, ys, facecolor=COR_SEM_PARTE, edgecolor="#1a3a6b", linewidth=1.0, zorder=0)

    for poly, codigo in talhoes:
        parte = parte_do_talhao.get(codigo)
        cor = cores[parte] if parte else COR_SEM_PARTE
        xs, ys = poly.exterior.xy
        ax.fill(xs, ys, facecolor=cor, edgecolor="#1a3a6b", linewidth=0.7, zorder=1)
        cx, cy = poly.centroid.x, poly.centroid.y
        if poly.area > (largura * altura) * 0.0005:  # so rotula talhao com area relevante
            ax.text(cx, cy, codigo[-3:], fontsize=7, ha="center", va="center",
                     color="#1a1a1a", zorder=3, fontweight="bold")

    for txt, (tx, ty) in textos_contexto:
        if minx - largura * 0.1 <= tx <= maxx + largura * 0.1 and miny - altura * 0.1 <= ty <= maxy + altura * 0.1:
            ax.text(tx, ty, txt, fontsize=6, color="#333", zorder=4, style="italic")

    ax.set_aspect("equal")
    ax.axis("off")

    legend_handles = [Patch(facecolor=cores[p], edgecolor="#1a3a6b", label=p) for p in partes]
    ax.legend(
        handles=legend_handles, loc="upper left", ncol=max(1, min(6, (len(partes) + 14) // 15)),
        frameon=True, framealpha=0.95, fontsize=7.5, title="Partes",
        bbox_to_anchor=(0.0, 1.0),
    )

    # seta norte simples
    nx0, ny0 = 0.05, 0.06
    ax.annotate(
        "N", xy=(nx0, ny0 + 0.05), xytext=(nx0, ny0), xycoords="axes fraction",
        textcoords="axes fraction", ha="center", fontsize=11, fontweight="bold",
        arrowprops=dict(arrowstyle="-|>", color="black", lw=1.6),
    )

    n_linhas = len(gdf_utm)
    fig.text(0.02, 0.985, "USINA DA PEDRA", fontsize=13, fontweight="bold", va="top")
    fig.text(0.02, 0.965, "Pedra Agroindustrial S/A", fontsize=9, va="top", color="#444")
    fig.text(
        0.98, 0.985, f"PROJETO DE COLHEITA — {fazenda}",
        fontsize=13, fontweight="bold", va="top", ha="right",
    )
    fig.text(
        0.98, 0.965,
        f"PROPRIETÁRIO: {cliente}    SAFRA: {safra}    LINHAS: {n_linhas}    PARTES: {len(partes)}",
        fontsize=9, va="top", ha="right", color="#444",
    )

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(saida_pdf, bbox_inches="tight")
    plt.close(fig)
    print(f"Mapa gerado: {saida_pdf}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("shp_classificado")
    p.add_argument("dwgs_contexto", nargs="+")
    p.add_argument("saida_pdf")
    p.add_argument("--cliente", default="")
    p.add_argument("--fazenda", default="")
    p.add_argument("--safra", default="")
    args = p.parse_args()
    gerar_mapa(args.shp_classificado, args.dwgs_contexto, args.saida_pdf,
               args.cliente, args.fazenda, args.safra)
