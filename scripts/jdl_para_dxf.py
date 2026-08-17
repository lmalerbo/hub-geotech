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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta_jdl")
    ap.add_argument("saida")
    ap.add_argument("--farm", default="")
    ap.add_argument("--dwg", action="store_true", help="tambem converte o DXF gerado pra DWG")
    args = ap.parse_args()

    gerar_dxf(args.pasta_jdl, args.saida, args.farm)

    if args.dwg:
        from converter_dwg import converter_dxf_para_dwg
        dwg_path = converter_dxf_para_dwg(args.saida, os.path.dirname(args.saida))
        print(f"DWG salvo em: {dwg_path}")
