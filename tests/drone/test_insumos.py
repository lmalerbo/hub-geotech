import pytest
from shapely.geometry import LineString, Point, box

from drone.erros import ErroGeracao
from drone.insumos import classe_pelo_nome, ler_shapefile


def test_le_e_mantem_31983(grava_shp):
    geoms = ler_shapefile(grava_shp('r15', [Point(200000, 7550000)]))
    assert geoms[0].x == pytest.approx(200000)


def test_reprojeta_wgs84_para_31983_antes_do_buffer(grava_shp):
    # um ponto em graus tem de virar coordenada UTM (centenas de milhares de metros)
    geoms = ler_shapefile(grava_shp('arvores', [Point(-47.6, -21.2)], crs=4326))
    assert 150_000 < geoms[0].x < 900_000
    assert 7_000_000 < geoms[0].y < 8_000_000


def test_sem_prj_da_erro(grava_shp):
    caminho = grava_shp('rede', [LineString([(0, 0), (10, 0)])])
    caminho.with_suffix('.prj').unlink()
    with pytest.raises(ErroGeracao, match='.prj'):
        ler_shapefile(caminho)


def test_descarta_vazias(grava_shp):
    geoms = ler_shapefile(grava_shp('x', [box(0, 0, 10, 10), Point()]))
    assert len(geoms) == 1


@pytest.mark.parametrize('nome,classe', [
    ('restricoes15m', 15), ('Restrições 15m', 15), ('15M', 15), ('retricoes25m', 25),
    ('resrtricoes50m', 50), ('restricoes50m_rede', 50), ('REDE50', 50), ('restricoes10m', None), ('Arvores', None),
])
def test_classe_pelo_nome(nome, classe):
    assert classe_pelo_nome(nome) == classe
