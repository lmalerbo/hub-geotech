import geopandas as gpd
import pytest
from shapely.geometry import box

CRS = 31983


@pytest.fixture
def talhoes():
    """Dois talhões de 100 x 100 m (1 ha cada), lado a lado."""
    return gpd.GeoDataFrame(
        {'TALHAO': [1, 2], 'AREA_PROD': [1.0, 1.0]},
        geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)], crs=CRS)


@pytest.fixture
def grava_shp(tmp_path):
    """grava_shp(nome, geoms, crs) -> caminho do .shp."""
    def _grava(nome, geoms, crs=CRS):
        caminho = tmp_path / f'{nome}.shp'
        gpd.GeoDataFrame({'id': list(range(len(geoms)))}, geometry=geoms, crs=crs).to_file(caminho)
        return caminho
    return _grava
