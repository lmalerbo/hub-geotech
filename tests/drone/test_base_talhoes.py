import datetime

import geopandas as gpd
import pytest
from shapely.geometry import box

from drone.base_talhoes import arquivo_mais_recente, talhoes_da_fazenda
from drone.erros import ErroGeracao


def _base(tmp_path, nome):
    gdf = gpd.GeoDataFrame(
        {'SECAO': ['10156', '10156', '20001'], 'TALHAO': [2.0, 1.0, 1.0], 'AREA_PROD': [3.5, 1.2, 9.9]},
        geometry=[box(100, 0, 200, 100), box(0, 0, 100, 100), box(500, 0, 600, 100)], crs=31983)
    caminho = tmp_path / nome
    gdf.to_file(caminho)
    return caminho


def test_escolhe_o_arquivo_pela_data_do_nome(tmp_path):
    _base(tmp_path, 'Talhoes_da_Pedra_30_09_2026_fme.shp')
    _base(tmp_path, 'Talhoes_da_Pedra_01_10_2026_fme.shp')
    data, caminho = arquivo_mais_recente(str(tmp_path), 'Talhoes_da_Pedra_*_fme.shp')
    assert data == datetime.date(2026, 10, 1)
    assert caminho.name == 'Talhoes_da_Pedra_01_10_2026_fme.shp'


def test_sem_arquivo_da_erro(tmp_path):
    with pytest.raises(ErroGeracao, match='Base de Talhões'):
        arquivo_mais_recente(str(tmp_path), 'Talhoes_da_Pedra_*_fme.shp')


def test_talhoes_da_fazenda_filtra_e_tipa(tmp_path):
    t = talhoes_da_fazenda(_base(tmp_path, 'Talhoes_da_Pedra_01_10_2026_fme.shp'), 10156)
    assert sorted(t['TALHAO'].tolist()) == [1, 2]
    assert t['TALHAO'].dtype.kind == 'i'
    assert t.crs.to_epsg() == 31983


def test_fazenda_sem_talhoes_da_erro(tmp_path):
    with pytest.raises(ErroGeracao, match='99999'):
        talhoes_da_fazenda(_base(tmp_path, 'Talhoes_da_Pedra_01_10_2026_fme.shp'), 99999)
