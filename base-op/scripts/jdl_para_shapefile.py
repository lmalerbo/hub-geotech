"""
Gera um shapefile de pontos GPS a partir dos .jdl de uma fazenda, usando o
extrator descoberto em jdl_gps_extract.py (par latitude/longitude do field 6
+ atributos extra do "item rico" do field 9 -- ver jdl_rich_fields.py).

Uso:
    python jdl_para_shapefile.py <pasta_com_jdl> <shapefile_saida.shp> [--farm CODIGO]
"""
import argparse
import glob
import os

import pyproj
import shapefile

from jdl_gps_extract import extrair_de_arquivo

UTM_23S_SIRGAS2000 = "EPSG:31983"

# nomes de campo DBF tem limite de 10 caracteres -- por isso abreviado
CAMPOS_EXTRA_NUMERICOS = {
    "TEMPO_MS": "TEMPO_MS",
    "ELEVATION_APROX": "ELEV_APRX",
    "CAMPO_3": "CAMPO_3",
    "CAMPO_5": "CAMPO_5",
    "CAMPO_8": "CAMPO_8",
    "CAMPO_9": "CAMPO_9",
    "CAMPO_23": "CAMPO_23",
    "CAMPO_24": "CAMPO_24",
    "CAMPO_25": "CAMPO_25",
    "CAMPO_27": "CAMPO_27",
    "CAMPO_28": "CAMPO_28",
}
CAMPO_DATA_HORA = "DATA_HORA"  # data/hora real do ponto (calculada, ver jdl_gps_extract.py)


def gerar_shapefile(pasta_jdl: str, caminho_saida: str, farm_code: str = ""):
    arquivos = sorted(glob.glob(os.path.join(pasta_jdl, "**", "*.jdl"), recursive=True))
    print(f"arquivos .jdl encontrados: {len(arquivos)}")

    transformer = pyproj.Transformer.from_crs("EPSG:4326", UTM_23S_SIRGAS2000, always_xy=True)

    w = shapefile.Writer(caminho_saida, shapeType=shapefile.POINT)
    w.field("FARM", "C", size=20)
    w.field("ARQUIVO", "C", size=80)
    w.field("LAT", "F", decimal=8)
    w.field("LON", "F", decimal=8)
    w.field(CAMPO_DATA_HORA, "C", size=26)
    for nome_dbf in CAMPOS_EXTRA_NUMERICOS.values():
        w.field(nome_dbf, "F", decimal=6)

    total = 0
    for caminho in arquivos:
        pontos = extrair_de_arquivo(caminho)
        nome = os.path.basename(caminho)
        for _, reg in pontos:
            lat, lon = reg["latitude"], reg["longitude"]
            x, y = transformer.transform(lon, lat)
            w.point(x, y)
            valores = {"FARM": farm_code, "ARQUIVO": nome, "LAT": lat, "LON": lon,
                       CAMPO_DATA_HORA: reg.get("DATA_HORA", "")}
            for nome_interno, nome_dbf in CAMPOS_EXTRA_NUMERICOS.items():
                v = reg.get(nome_interno)
                valores[nome_dbf] = v if v is not None else 0.0
            w.record(**valores)
            total += 1

    w.close()

    prj_path = os.path.splitext(caminho_saida)[0] + ".prj"
    crs = pyproj.CRS.from_epsg(31983)
    with open(prj_path, "w", encoding="utf-8") as f:
        f.write(crs.to_wkt(version="WKT1_ESRI"))

    print(f"total de pontos gravados: {total}")
    print(f"shapefile salvo em: {caminho_saida}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta_jdl")
    ap.add_argument("saida")
    ap.add_argument("--farm", default="")
    args = ap.parse_args()
    gerar_shapefile(args.pasta_jdl, args.saida, args.farm)
