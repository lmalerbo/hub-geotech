r"""
Gera o mapa preenchendo o DWG de verdade (template material-mapa/00000_COLHEITA_Rev0.dwt):
talhoes coloridos por parte no modelspace, viewport ajustado pra fazenda,
carimbo atualizado (secao/area/data) e legenda -- produz um .dwg de verdade,
editavel no AutoCAD, nao so uma imagem.

Uso:
    python gerar_mapa_dwg.py <shapefile_classificado.shp> <dwg_contexto1.dwg> [...] <saida.dwg> \
        --cliente "PEDRA AGROINDUSTRIAL S/A" --fazenda "10003 - PEDRA (1L)" --safra "26/27"
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import ezdxf
import ezdxf.bbox as ezbbox
import geopandas as gpd
import warnings
from ezdxf.addons.importer import Importer

sys.path.insert(0, str(Path(__file__).parent))
from converter_dwg import converter_arquivo  # noqa: E402
from gerar_mapa import (  # noqa: E402
    _coordenada_plausivel, atribuir_parte_por_talhao, extrair_talhoes, gerar_paleta,
)

warnings.filterwarnings("ignore")

TEMPLATE_DWT = Path("material-mapa/00000_COLHEITA_Rev0.dwt")
NOME_BLOCO_CARIMBO = "Layer_Automatico_Paisagem"
NOME_LAYOUT = "Paisagem"
TRANSPARENCIA_PARTES = ezdxf.colors.float2transparency(0.45)  # deixa as linhas-guia visiveis por baixo


def _chave_natural(s: str):
    """Ordena 'strings' tipo '1L-2', '1L-10' na ordem numerica esperada
    (nao alfabetica, onde '1L-10' viria antes de '1L-2')."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def _hex_para_rgb(hex_cor: str) -> tuple[int, int, int]:
    hex_cor = hex_cor.lstrip("#")
    return tuple(int(hex_cor[i:i + 2], 16) for i in (0, 2, 4))


def _carregar_template(pasta_temp: Path) -> ezdxf.document.Drawing:
    dxf_path = converter_arquivo(str(TEMPLATE_DWT), str(pasta_temp))
    return ezdxf.readfile(dxf_path)


def _ajustar_viewport(doc, minx, miny, maxx, maxy, folga: float = 1.12):
    """Recentraliza/reescala o viewport real (status=2) pra fazenda, mantendo
    a proporcao largura/altura original do quadro na folha."""
    layout = doc.layout(NOME_LAYOUT)
    vp = next(e for e in layout if e.dxftype() == "VIEWPORT" and e.dxf.status != 1)

    aspecto = vp.dxf.width / vp.dxf.height
    largura_farm = maxx - minx
    altura_farm = maxy - miny

    altura_view = max(altura_farm, largura_farm / aspecto) * folga
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2

    vp.dxf.view_center_point = (cx, cy, 0.0)
    vp.dxf.center = (cx, cy, 0.0)  # alguns leitores usam center tb como referencia de pan
    vp.dxf.view_height = altura_view
    return altura_view


def _copiar_conteudo_dwg(doc_destino, dwg_origem: str, pasta_temp: Path, prefixo: str):
    """Importa TODO o conteudo (modelspace) do dwg de contexto pra dentro do
    doc final, isolando cada arquivo de origem na sua propria familia de
    layers (prefixo$layer_original) -- assim da pra ligar/desligar cada
    fonte separadamente no AutoCAD. Descarta entidades com coordenadas
    implausiveis (lixo de paper space que vaza pro modelspace em alguns
    arquivos, ver _coordenada_plausivel)."""
    caminho = Path(dwg_origem)
    if caminho.suffix.lower() == ".dwg":
        caminho = converter_arquivo(str(caminho), str(pasta_temp))
    doc_origem = ezdxf.readfile(caminho)

    msp_destino = doc_destino.modelspace()
    antes = {e.dxf.handle for e in msp_destino}

    # alguns dwgs de contexto guardam o desenho real direto num layout de
    # papel (ex.: 'Paisagem'), nao no modelspace -- mesma situacao ja tratada
    # em extrair_talhoes/extrair_textos_contexto.
    espacos_origem = [doc_origem.modelspace()] + [
        doc_origem.layout(n) for n in doc_origem.layout_names() if n != "Model"
    ]

    importador = Importer(doc_origem, doc_destino)
    for espaco in espacos_origem:
        importador.import_entities(espaco, target_layout=msp_destino)
    importador.finalize()

    layers_criadas = set()
    n_ok, n_descartadas = 0, 0
    for e in list(msp_destino):
        if e.dxf.handle in antes:
            continue
        try:
            caixa = ezbbox.extents([e], fast=True)
        except Exception:
            caixa = None
        plausivel = (
            caixa is not None and caixa.has_data
            and _coordenada_plausivel(caixa.extmin.x, caixa.extmin.y, caixa.extmax.x, caixa.extmax.y)
        )
        if not plausivel:
            msp_destino.delete_entity(e)
            n_descartadas += 1
            continue

        layer_origem = e.dxf.layer
        layer_novo = f"{prefixo}${layer_origem}"
        if layer_novo not in layers_criadas:
            if layer_novo not in doc_destino.layers:
                cor = 7
                if layer_origem in doc_destino.layers:
                    cor = doc_destino.layers.get(layer_origem).dxf.color
                doc_destino.layers.add(layer_novo, dxfattribs={"color": cor})
            layers_criadas.add(layer_novo)
        e.dxf.layer = layer_novo
        n_ok += 1

    return n_ok, n_descartadas


def _inserir_linhas_projeto(doc, gdf_utm: gpd.GeoDataFrame, cores: dict):
    """Desenha as linhas-guia de colheita reais (o tracado do projeto), numa
    layer propria, por baixo do preenchimento colorido dos talhoes (que sai
    com transparencia pra elas ficarem visiveis por baixo)."""
    msp = doc.modelspace()
    nome_layer = "LINHAS_GUIA"
    if nome_layer not in doc.layers:
        doc.layers.add(nome_layer, dxfattribs={"color": 7})

    for geom, parte in zip(gdf_utm.geometry, gdf_utm["FIELD_NAME"]):
        if geom is None or geom.is_empty:
            continue
        cor_hex = cores.get(parte, "#808080")
        r, g, b = _hex_para_rgb(cor_hex)
        linhas = geom.geoms if geom.geom_type == "MultiLineString" else [geom]
        for linha in linhas:
            pontos = list(linha.coords)
            if len(pontos) < 2:
                continue
            msp.add_lwpolyline(
                pontos,
                dxfattribs={
                    "layer": nome_layer,
                    "true_color": ezdxf.colors.rgb2int((r, g, b)),
                    "lineweight": 0,
                },
            )


def _inserir_talhoes(doc, talhoes, contorno_geral, parte_do_talhao, cores):
    msp = doc.modelspace()

    for poly, _ in contorno_geral:
        pontos = list(poly.exterior.coords)
        hatch = msp.add_hatch(dxfattribs={
            "true_color": ezdxf.colors.rgb2int(_hex_para_rgb("#d9d5c4")),
            "transparency": TRANSPARENCIA_PARTES,
        })
        hatch.paths.add_polyline_path(pontos, is_closed=True)
        msp.add_lwpolyline(pontos, close=True, dxfattribs={"color": 5, "lineweight": 25})

    for poly, codigo in talhoes:
        parte = parte_do_talhao.get(codigo)
        cor_hex = cores[parte] if parte else "#d9d5c4"
        pontos = list(poly.exterior.coords)

        hatch = msp.add_hatch(dxfattribs={
            "true_color": ezdxf.colors.rgb2int(_hex_para_rgb(cor_hex)),
            "transparency": TRANSPARENCIA_PARTES,
        })
        hatch.paths.add_polyline_path(pontos, is_closed=True)

        msp.add_lwpolyline(pontos, close=True, dxfattribs={"color": 5, "lineweight": 18})

        cx, cy = poly.centroid.x, poly.centroid.y
        altura_texto = max(1.0, (poly.bounds[2] - poly.bounds[0]) * 0.06)
        msp.add_text(
            codigo[-3:], height=altura_texto,
            dxfattribs={"insert": (cx, cy), "halign": 1, "valign": 2, "color": 7},
        ).set_placement((cx, cy), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def _atualizar_carimbo(doc, codigo: str, nome: str, safra: str, area_ha: float):
    bloco = doc.blocks.get(NOME_BLOCO_CARIMBO)

    for e in bloco:
        if e.dxftype() == "MTEXT" and "SEÇÃO COLHEITA" in e.text:
            e.text = f"SEÇÃO {nome.upper()} - {codigo}"
        elif e.dxftype() == "TEXT" and e.dxf.text == "26/27":
            e.dxf.text = safra

    # adiciona valores de DATA e AREA (o template so tem os rotulos, sem valor)
    pos_data = next((e.dxf.insert for e in bloco if e.dxftype() == "TEXT" and e.dxf.text == "DATA"), None)
    pos_area = next((e.dxf.insert for e in bloco if e.dxftype() == "TEXT" and e.dxf.text == "AREA (Ha)"), None)

    hoje = datetime.now().strftime("%d/%m/%Y")
    if pos_data:
        bloco.add_text(hoje, height=90, dxfattribs={"insert": (pos_data[0], pos_data[1] - 120), "color": 7})
    if pos_area:
        area_fmt = f"{area_ha:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        bloco.add_text(area_fmt, height=90, dxfattribs={"insert": (pos_area[0], pos_area[1] - 120), "color": 7})


def _adicionar_legenda(doc, partes, cores):
    """Legenda em espaco de papel (Paisagem), canto superior esquerdo -- fica
    com tamanho fixo na folha independente do zoom do viewport."""
    layout = doc.layout(NOME_LAYOUT)
    x0, y0 = 200, 15200
    linha_h = 260
    lado = 180

    layout.add_text("Partes", height=200, dxfattribs={"insert": (x0, y0 + linha_h), "color": 7})
    for i, parte in enumerate(partes):
        y = y0 - i * linha_h
        r, g, b = _hex_para_rgb(cores[parte])
        hatch = layout.add_hatch(dxfattribs={"true_color": ezdxf.colors.rgb2int((r, g, b))})
        hatch.paths.add_polyline_path(
            [(x0, y), (x0 + lado, y), (x0 + lado, y + lado), (x0, y + lado)], is_closed=True,
        )
        layout.add_text(parte, height=150, dxfattribs={"insert": (x0 + lado + 80, y + 10), "color": 7})


def gerar_mapa_dwg(shp_classificado: str, dwgs_contexto: list[str], saida_dwg: str,
                    cliente: str, fazenda: str, safra: str, codigo: str, nome: str,
                    pasta_temp: str = "linhas-vant/_mapa_dwg_temp"):
    pasta_temp = Path(pasta_temp)
    pasta_temp.mkdir(parents=True, exist_ok=True)

    gdf = gpd.read_file(shp_classificado)
    utm = gdf.estimate_utm_crs()
    gdf_utm = gdf.to_crs(utm)

    talhoes_brutos = []
    for dwg in dwgs_contexto:
        talhoes_brutos.extend(extrair_talhoes(dwg, pasta_temp))

    areas = sorted(p.area for p, _ in talhoes_brutos)
    mediana = areas[len(areas) // 2] if areas else 0
    contorno_geral = [(p, c) for p, c in talhoes_brutos if mediana > 0 and p.area > mediana * 20]
    talhoes = [(p, c) for p, c in talhoes_brutos if not (mediana > 0 and p.area > mediana * 20)]
    print(f"  {len(talhoes)} talhao(oes) ({len(contorno_geral)} contorno(s) geral(is))")

    partes = sorted(gdf_utm["FIELD_NAME"].unique(), key=_chave_natural)
    paleta = gerar_paleta(len(partes))
    cores = {parte: paleta[i] for i, parte in enumerate(partes)}
    parte_do_talhao = atribuir_parte_por_talhao(talhoes, gdf_utm)

    area_ha = sum(p.area for p, _ in contorno_geral) / 10_000 if contorno_geral else 0

    print("  Carregando template...")
    doc = _carregar_template(pasta_temp)

    minx, miny, maxx, maxy = gdf_utm.total_bounds
    print("  Ajustando viewport pra fazenda...")
    _ajustar_viewport(doc, minx, miny, maxx, maxy)

    print("  Copiando conteudo dos DWGs de contexto (camada de fundo)...")
    for dwg in dwgs_contexto:
        prefixo = Path(dwg).stem.replace("_", "-")
        n_ok, n_desc = _copiar_conteudo_dwg(doc, dwg, pasta_temp, prefixo)
        print(f"    {prefixo}: {n_ok} entidades copiadas ({n_desc} descartadas por coordenada implausivel)")

    print("  Inserindo linhas-guia do projeto (por baixo das cores)...")
    _inserir_linhas_projeto(doc, gdf_utm, cores)

    print("  Inserindo talhoes coloridos...")
    _inserir_talhoes(doc, talhoes, contorno_geral, parte_do_talhao, cores)

    print("  Atualizando carimbo...")
    _atualizar_carimbo(doc, codigo, nome, safra, area_ha)

    print("  Adicionando legenda...")
    _adicionar_legenda(doc, partes, cores)

    pasta_conversao = pasta_temp / f"_saida_{Path(saida_dwg).stem}"
    pasta_conversao.mkdir(parents=True, exist_ok=True)
    dxf_saida = pasta_conversao / (Path(saida_dwg).stem + ".dxf")
    doc.saveas(dxf_saida)
    print(f"  DXF intermediario salvo: {dxf_saida}")

    print("  Convertendo pra DWG...")
    pasta_saida_dwg = Path(saida_dwg).parent
    pasta_saida_dwg.mkdir(parents=True, exist_ok=True)
    from converter_dwg import EXE_PADRAO, VERSAO_SAIDA
    import subprocess
    resultado = subprocess.run(
        [str(EXE_PADRAO), str(dxf_saida.parent), str(pasta_saida_dwg), VERSAO_SAIDA, "DWG", "0", "1"],
        capture_output=True, text=True, timeout=300,
    )
    dwg_gerado = pasta_saida_dwg / (dxf_saida.stem + ".dwg")
    if dwg_gerado.exists() and dwg_gerado != Path(saida_dwg):
        dwg_gerado.rename(saida_dwg)
    print(f"Mapa DWG gerado: {saida_dwg}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("shp_classificado")
    p.add_argument("dwgs_contexto", nargs="+")
    p.add_argument("saida_dwg")
    p.add_argument("--cliente", default="")
    p.add_argument("--fazenda", default="")
    p.add_argument("--safra", default="")
    p.add_argument("--codigo", default="")
    p.add_argument("--nome", default="")
    args = p.parse_args()
    gerar_mapa_dwg(args.shp_classificado, args.dwgs_contexto, args.saida_dwg,
                   args.cliente, args.fazenda, args.safra, args.codigo, args.nome)
