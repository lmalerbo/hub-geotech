"""
Gera um .dxf (e opcionalmente converte pra .dwg via ODA File Converter) com
os pontos de execucao extraidos dos .jdl de uma fazenda, incluindo os
atributos extras como XDATA (aparecem em "Extended Data" nas propriedades
do ponto no AutoCAD/Civil3D).

Uso:
    python jdl_para_dxf.py <pasta_com_jdl> <saida.dxf> [--farm CODIGO] [--dwg]
"""
import argparse
import glob
import os

import ezdxf
import pyproj

from jdl_gps_extract import extrair_de_arquivo

UTM_23S_SIRGAS2000 = "EPSG:31983"
APPID = "AGK_JDL"

CAMPOS_EXTRA = ["DATA_HORA", "TEMPO_MS", "ELEVATION_APROX", "CAMPO_3", "CAMPO_5", "CAMPO_8", "CAMPO_9",
                "CAMPO_23", "CAMPO_24", "CAMPO_25", "CAMPO_27", "CAMPO_28"]


def gerar_dxf(pasta_jdl: str, caminho_saida: str, farm_code: str = ""):
    arquivos = sorted(glob.glob(os.path.join(pasta_jdl, "**", "*.jdl"), recursive=True))
    print(f"arquivos .jdl encontrados: {len(arquivos)}")

    transformer = pyproj.Transformer.from_crs("EPSG:4326", UTM_23S_SIRGAS2000, always_xy=True)

    doc = ezdxf.new("R2018")
    doc.appids.new(APPID)
    doc.layers.add("FIELD_POINTS")
    msp = doc.modelspace()

    total = 0
    for caminho in arquivos:
        pontos = extrair_de_arquivo(caminho)
        nome = os.path.basename(caminho)
        for _, reg in pontos:
            lat, lon = reg["latitude"], reg["longitude"]
            x, y = transformer.transform(lon, lat)
            z = reg.get("ELEVATION_APROX") or 0.0

            xdata = [(1000, f"FARM={farm_code}"), (1000, f"ARQUIVO={nome}"),
                     (1000, f"LAT={lat}"), (1000, f"LON={lon}")]
            for campo in CAMPOS_EXTRA:
                v = reg.get(campo)
                if v is not None:
                    xdata.append((1000, f"{campo}={v}"))

            pt = msp.add_point((x, y, z), dxfattribs={"layer": "FIELD_POINTS"})
            pt.set_xdata(APPID, xdata)
            total += 1

    doc.saveas(caminho_saida)
    print(f"total de pontos gravados: {total}")
    print(f"DXF salvo em: {caminho_saida}")


def gerar_dxf_ticks(pasta_jdl: str, caminho_saida: str) -> int:
    """Modo --ticks: grava a trajetoria tick a tick (1 ponto a cada 0,2s, a
    mesma trilha que o GOIMP do AgroCAD importa), em vez do registro de 30s
    do campo 6. Tudo em FIELD_POINTS, sem XDATA (fazendas com ~2M pontos).
    Retorna o numero de pontos gravados."""
    from jdl_gps_extract import extrair_ticks_de_arquivo

    arquivos = sorted(glob.glob(os.path.join(pasta_jdl, "**", "*.jdl"), recursive=True))
    print(f"arquivos .jdl encontrados: {len(arquivos)}")

    transformer = pyproj.Transformer.from_crs("EPSG:4326", UTM_23S_SIRGAS2000, always_xy=True)

    doc = ezdxf.new("R2018")
    doc.layers.add("FIELD_POINTS")
    msp = doc.modelspace()
    attribs = {"layer": "FIELD_POINTS"}

    total = 0
    for caminho in arquivos:
        try:
            ticks = extrair_ticks_de_arquivo(caminho)
        except Exception as e:  # arquivo corrompido nao derruba o lote
            print(f"  [aviso] falha lendo {os.path.basename(caminho)}: {e!r}")
            continue
        if not ticks:
            continue
        lats = [t[0] for t in ticks]
        lons = [t[1] for t in ticks]
        xs, ys = transformer.transform(lons, lats)
        for x, y in zip(xs, ys):
            msp.add_point((x, y, 0.0), dxfattribs=attribs)
        total += len(ticks)

    doc.saveas(caminho_saida)
    print(f"total de pontos gravados: {total}")
    print(f"DXF salvo em: {caminho_saida}")
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta_jdl")
    ap.add_argument("saida")
    ap.add_argument("--farm", default="")
    ap.add_argument("--dwg", action="store_true", help="tambem converte o DXF gerado pra DWG")
    ap.add_argument("--ticks", action="store_true",
                    help="grava a trajetoria tick a tick (0,2s, igual ao GOIMP) sem XDATA, "
                         "em vez do registro de 30s com XDATA")
    args = ap.parse_args()

    if args.ticks:
        gerar_dxf_ticks(args.pasta_jdl, args.saida)
    else:
        gerar_dxf(args.pasta_jdl, args.saida, args.farm)

    if args.dwg:
        from converter_dwg import converter_dxf_para_dwg
        dwg_path = converter_dxf_para_dwg(args.saida, os.path.dirname(args.saida) or ".")
        print(f"DWG salvo em: {dwg_path}")
