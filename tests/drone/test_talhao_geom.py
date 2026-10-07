import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ingestao'))
from talhao_geom import linhas  # noqa: E402


def _gdf(**cols):
    geoms = cols.pop('geometry')
    return gpd.GeoDataFrame(cols, geometry=geoms, crs=31983)


def test_uma_linha_por_talhao_em_4326_com_area_em_31983():
    g = _gdf(SECAO=['10156', '10156', '10156'], TALHAO=[1, 1, 2],
             geometry=[box(200000, 7550000, 200100, 7550100), box(200100, 7550000, 200200, 7550100),
                       box(200300, 7550000, 200400, 7550050)])
    out = {(l['cod_faz'], l['talhao_num']): l for l in linhas(g)}
    assert set(out) == {(10156, 1), (10156, 2)}
    assert out[(10156, 1)]['area_ha'] == pytest.approx(2.0)           # duas partes viram um MultiPolygon
    assert out[(10156, 1)]['geom'].startswith('SRID=4326;MULTIPOLYGON')
    assert '-4' in out[(10156, 1)]['geom']                              # graus (longitude negativa)


def test_ignora_codigo_invalido_e_geometria_vazia():
    g = _gdf(SECAO=['abc', '99', '10156'], TALHAO=[1, 1, None],
             geometry=[box(0, 0, 10, 10), box(0, 0, 10, 10), box(0, 0, 10, 10)])
    assert linhas(g) == []
