r"""
Extrai linhas de um DXF (layers combinadas por tipo), roda o pipeline completo
(simplify 0.01m + preenchimento de espacamento maximo 12m + classificacao em
partes por tamanho + mapa com legenda + relatorio de qualidade) e gera os 4
formatos (Gen4/GS3_2630/AgData/AgGPS) prontos pra upload/entrega, consolidados
num Field/talhao por fazenda (nao um por parte -- ver build_gs3_2630_bundle.py
pro motivo: um Field por parte faz o OC criar talhao vazio arquivado).

Uso:
    python dxf_para_gen4.py <codigo_fazenda> <nome_fazenda_exibicao>

Convencoes assumidas (mesmas do resto do pipeline):
    - DWG de linhas em G:\...\FAZENDAS\<codigo> <NOME>\2026-2027\03 EXPORTACOES\
      02 COLHEITA\<tipo>\<codigo>_<NOME>_Exp<tipo>.dwg  (tipo = 1L, 2L)
    - Camadas 1L: 01_Linhas_Vant + 02_Linhas_Cana | Camadas 2L: 03_Desdobra_Vant + 04_Desdobra_Cana
    - DWG(s) de contexto (talhoes) em material-mapa/dwg/S<codigo>_*.dwg
"""

import math
import sys
import warnings
from pathlib import Path

import ezdxf
import geopandas as gpd
from shapely.geometry import LineString

import build_bundle_completo as bundle
import classificar_partes as classif
import workflow_status as ws
from converter_dwg import converter_arquivo
from gerar_mapa import gerar_mapa

warnings.filterwarnings("ignore")

RAIZ_FAZENDAS = Path(
    r"G:\GeoProc\GEOTECNOLOGIA\08 PROJETOS PILOTO AUTOMATICO\15 PROPRIO\FAZENDAS"
)
PASTA_MATERIAL_MAPA = Path("material-mapa/dwg")

CONFIG_PADRAO = {
    "crs_origem": "EPSG:32723",
    "client_name": "US PEDRA",
    "ciclo": "2026-2027",
    "safra": "26/27",
    "grupos": {
        "1L": ["01_Linhas_Vant", "02_Linhas_Cana"],
        "2L": ["03_Desdobra_Vant", "04_Desdobra_Cana"],
    },
    "tolerancia_simplify_m": 0.01,
    "espacamento_max_m": 12.0,
    "alvo_mb_por_parte": classif.ALVO_MB_DEFAULT,
    "max_mb_por_parte": classif.MAX_MB_DEFAULT,
    "min_mb_por_parte": classif.MIN_MB_DEFAULT,
    "max_dist_conexao_m": classif.MAX_DIST_DEFAULT,
    "saida_dir": "linhas-vant/dxf_pipeline_saida",
}


def extrair_linhas(dxf_path: str, layers: list, crs_origem: str) -> gpd.GeoDataFrame:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    linhas = []
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer not in layers:
            continue
        pts = [(p[0], p[1]) for p in e.get_points()]
        if len(pts) >= 2:
            linhas.append(LineString(pts))
    return gpd.GeoDataFrame(geometry=linhas, crs=crs_origem)


def preencher_max(line: LineString, max_sp: float) -> LineString:
    coords = [(x, y) for x, y, *_ in line.coords]
    novos = [coords[0]]
    for i in range(1, len(coords)):
        p0, p1 = coords[i - 1], coords[i]
        d = ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5
        if d > max_sp:
            n = math.ceil(d / max_sp)
            for k in range(1, n):
                t = k / n
                novos.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
        novos.append(p1)
    return LineString(novos)


def localizar_dwg_linhas(codigo: str, nome: str, tipo: str, ciclo: str) -> Path:
    return (
        RAIZ_FAZENDAS / f"{codigo} {nome}" / ciclo / "03 EXPORTACOES" / "02 COLHEITA"
        / tipo / f"{codigo}_{nome}_Exp{tipo}.dwg"
    )


def localizar_dwgs_contexto(codigo: str) -> list[str]:
    achados = sorted(PASTA_MATERIAL_MAPA.glob(f"S{codigo}_*.dwg"))
    return [str(p) for p in achados]


def processar_tipo(tipo: str, layers: list, codigo: str, nome: str, cfg: dict) -> Path:
    print(f"\n=== Tipo {tipo} (layers: {layers}) ===")

    dwg_path = localizar_dwg_linhas(codigo, nome, tipo, cfg["ciclo"])
    if not dwg_path.exists():
        print(f"  Pulando {tipo}: DWG nao encontrado em {dwg_path}")
        ws.registrar(codigo, nome, tipo, "dxf", "erro", {"erro": f"DWG nao encontrado: {dwg_path}"})
        return None

    with ws.rastrear_etapa(codigo, nome, tipo, "dxf") as r:
        pasta_dxf = Path(cfg["saida_dir"]) / "_dxf"
        dxf_path = converter_arquivo(str(dwg_path), str(pasta_dxf))
        r.detalhes = {"dxf_path": str(dxf_path)}

    with ws.rastrear_etapa(codigo, nome, tipo, "classificacao") as r:
        gdf = extrair_linhas(str(dxf_path), layers, cfg["crs_origem"])
        print(f"Linhas extraidas do DXF: {len(gdf)}")
        if len(gdf) == 0:
            print(f"  Pulando {tipo}: nenhuma linha nas layers {layers}")
            ws.registrar(codigo, nome, tipo, "classificacao", "erro", {"erro": "nenhuma linha nas layers esperadas"})
            return None

        tol = cfg["tolerancia_simplify_m"]
        max_sp = cfg["espacamento_max_m"]
        processadas = [preencher_max(l.simplify(tol, preserve_topology=False), max_sp) for l in gdf.geometry]
        total_pts = sum(len(l.coords) for l in processadas)
        print(f"Pontos apos simplify({tol}m) + preenchimento max {max_sp}m: {total_pts}")

        gdf_proc = gpd.GeoDataFrame(geometry=processadas, crs=cfg["crs_origem"]).to_crs(4326)
        gdf_proc["CLIENT_NAM"] = cfg["client_name"]
        gdf_proc["FARM_NAME"] = codigo

        field_names, tamanhos, relatorio = classif.classificar_partes(
            gdf_proc, tipo=tipo,
            alvo_mb=cfg["alvo_mb_por_parte"], max_mb=cfg["max_mb_por_parte"],
            min_mb=cfg["min_mb_por_parte"], max_dist_m=cfg["max_dist_conexao_m"],
        )
        gdf_proc["FIELD_NAME"] = field_names
        print(f"Partes geradas ({len(tamanhos)}):")
        for nome_parte, n_linhas, tamanho in tamanhos:
            print(f"  {nome_parte}: {n_linhas} linha(s), {tamanho/1_000_000:.3f}MB")

        saida_dir = Path(cfg["saida_dir"])
        saida_dir.mkdir(parents=True, exist_ok=True)
        shp_path = saida_dir / f"{codigo}_{tipo}.shp"
        gdf_proc.to_file(shp_path)
        r.detalhes = {"n_linhas": len(gdf_proc), "n_partes": len(tamanhos), "shp_path": str(shp_path)}

    entrega_dir = Path("linhas-vant") / f"entrega_{codigo}" / tipo
    entrega_dir.mkdir(parents=True, exist_ok=True)

    dwgs_contexto = localizar_dwgs_contexto(codigo)
    if dwgs_contexto:
        with ws.rastrear_etapa(codigo, nome, tipo, "mapa") as r:
            print(f"  Gerando mapa ({len(dwgs_contexto)} dwg(s) de contexto)...")
            mapa_pdf = entrega_dir / f"{codigo}_{tipo}_mapa.pdf"
            gerar_mapa(
                str(shp_path), dwgs_contexto, str(mapa_pdf),
                cliente=cfg["client_name"], fazenda=f"{codigo} - {nome} ({tipo})",
                safra=cfg["safra"],
            )
            r.detalhes = {"mapa_path": str(mapa_pdf)}
    else:
        print(f"  Sem DWG de contexto em {PASTA_MATERIAL_MAPA} pra S{codigo}_* -- pulando mapa")
        ws.registrar(codigo, nome, tipo, "mapa", "erro", {"erro": "sem DWG de contexto em material-mapa"})

    with ws.rastrear_etapa(codigo, nome, tipo, "qualidade") as r:
        import json
        relatorio_path = entrega_dir / f"{codigo}_{tipo}_qualidade.json"
        relatorio_path.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Relatorio de qualidade: {relatorio_path}")
        if relatorio["precisa_revisao"]:
            print("  ATENCAO: fora dos limiares -- recomenda revisao manual na ferramenta interativa.")
        r.detalhes = {
            "precisa_revisao": relatorio["precisa_revisao"],
            "compacidade_media": relatorio["compacidade_media"],
            "desequilibrio_cv_pct": relatorio["desequilibrio_cv_pct"],
            "custo_corte_km": relatorio["custo_corte_km"],
        }

    # os 4 formatos, consolidados (1 Field/talhao por fazenda, nao por parte --
    # build_bundle_completo.py ja rastreia cada formato via workflow_status)
    bundle.main(str(shp_path), str(entrega_dir))

    return shp_path


def main(codigo: str, nome: str, cfg: dict = None):
    cfg = {**CONFIG_PADRAO, **(cfg or {})}
    shapefiles = {}
    for tipo, layers in cfg["grupos"].items():
        shp = processar_tipo(tipo, layers, codigo, nome, cfg)
        if shp:
            shapefiles[tipo] = shp
    return shapefiles


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python dxf_para_gen4.py <codigo_fazenda> <nome_fazenda>")
        print('  ex: python dxf_para_gen4.py 10003 "PEDRA"')
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
