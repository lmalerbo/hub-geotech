"""
Gera a estrutura AgGPS (formato Trimble, usado por equipamentos CASE PTx) a
partir de paths de linhas (lon, lat em graus).

Formato observado num export real do AgroCAD:
    AgGPS/Data/<cliente>/<fazenda tipo>/<nome_parte>/
        <lon>E<lat>N<altura>H.pos      -- arquivo vazio (0 bytes), marcador;
                                           nome codifica o ponto de referencia
                                           (lon/lat com 5 casas decimais) e uma
                                           altura fixa (600, unico valor visto)
        Executado/                      -- pasta vazia, marcador de status
        LineFeature.shp/.dbf/.prj/.shx  -- shapefile WGS84 padrao (ESRI), colunas:
            Id     = 1517 (constante em todo o export, provavel ID de sessao)
            Name   = "Line" (constante)
            Length = comprimento da linha em metros (projetado)
            Dist1  = 0.0 (constante nos exemplos vistos)
            Dist2  = 0.0 (constante nos exemplos vistos)
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

ID_CONSTANTE = 1517
ALTURA_PADRAO = 600


def nome_pos(ref_lon: float, ref_lat: float, altura: int = ALTURA_PADRAO) -> str:
    return f"{ref_lon:.5f}E{ref_lat:.5f}N{altura}H.pos"


def build_aggps(pasta_destino: Path, paths: list[list[tuple[float, float]]]):
    """Escreve LineFeature.shp/.dbf/.prj/.shx + .pos + Executado/ em pasta_destino."""
    pasta_destino.mkdir(parents=True, exist_ok=True)

    linhas = [LineString(p) for p in paths]
    gdf = gpd.GeoDataFrame(
        {
            "Id": [ID_CONSTANTE] * len(linhas),
            "Name": ["Line"] * len(linhas),
            "Dist1": [0.0] * len(linhas),
            "Dist2": [0.0] * len(linhas),
        },
        geometry=linhas,
        crs="EPSG:4326",
    )

    utm = gdf.estimate_utm_crs()
    comprimento_m = gdf.to_crs(utm).length
    gdf["Length"] = comprimento_m
    gdf = gdf[["Id", "Name", "Length", "Dist1", "Dist2", "geometry"]]

    gdf.to_file(pasta_destino / "LineFeature.shp", driver="ESRI Shapefile")

    ref_lon, ref_lat = paths[0][0]
    (pasta_destino / nome_pos(ref_lon, ref_lat)).touch()
    (pasta_destino / "Executado").mkdir(exist_ok=True)


if __name__ == "__main__":
    import sys
    import warnings

    warnings.filterwarnings("ignore")
    sys.path.insert(0, ".")
    from agdata_build import _para_ecef  # so pra reusar o transformer se precisar

    import geopandas as gpd_ref
    gdf_ref = gpd_ref.read_file(
        "referencia_jd_samples/agrocad_real/AgGPS/Data/US PEDRA/10738 1L/Parte1/LineFeature.shp"
    )
    paths = [list(g.coords) for g in gdf_ref.geometry]

    destino = Path("linhas-vant/teste_aggps")
    build_aggps(destino, paths)
    print(f"Gerado em {destino}")

    gdf_novo = gpd_ref = None
    import geopandas as gpd2
    gdf_novo = gpd2.read_file(destino / "LineFeature.shp")
    print(f"linhas geradas: {len(gdf_novo)}  (original: {len(gdf_ref)})")
    print(gdf_novo[["Id", "Name", "Length", "Dist1", "Dist2"]].head(5))

    # confere erro de comprimento
    diffs = (gdf_novo["Length"].values - gdf_ref["Length"].values)
    print("erro maximo de Length (m):", abs(diffs).max())
