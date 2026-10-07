import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon, box

from drone.erros import ErroGeracao
from drone.montagem import (cobertura, dividir_por_talhao, fora_da_base, itens_para_json, montar_normal, uniao)


@pytest.fixture
def base():
    """3 talhões de 1 ha lado a lado."""
    return gpd.GeoDataFrame({'TALHAO': [1, 2, 3]},
                            geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100), box(200, 0, 300, 100)], crs=31983)


def _item(geom, origem='legado', rev=0):
    return {'geom': geom, 'area_ha': geom.area / 1e4, 'origem': origem, 'desde_rev': rev}


def test_dividir_por_talhao_corta_na_borda(base):
    itens = dividir_por_talhao(box(50, 0, 250, 100), base, 'legado', 0)
    assert sorted(itens) == [1, 2, 3]
    assert itens[1]['area_ha'] == pytest.approx(0.5)
    assert itens[2]['origem'] == 'legado' and itens[2]['desde_rev'] == 0


def test_incluir_pelo_sistema_desconta_obstaculos_e_copia_o_resto(base):
    vig = {1: _item(box(0, 0, 100, 100))}
    obst = Point(150, 50).buffer(10)
    itens = montar_normal(vig, {'incluir': [{'talhao': 2, 'fonte': 'sistema'}], 'remover': []}, base, obst, [], 1)
    assert sorted(itens) == [1, 2]
    assert itens[1]['desde_rev'] == 0 and itens[1]['origem'] == 'legado'      # copiado igual
    assert itens[2]['desde_rev'] == 1 and itens[2]['origem'] == 'sistema'
    assert itens[2]['area_ha'] == pytest.approx(1 - obst.area / 1e4, rel=1e-3)


def test_refazer_substitui_e_remover_tira(base):
    vig = {1: _item(box(0, 0, 100, 50)), 2: _item(box(100, 0, 200, 100))}
    itens = montar_normal(vig, {'incluir': [{'talhao': 1, 'fonte': 'sistema'}], 'remover': [2]}, base, Polygon(), [], 3)
    assert sorted(itens) == [1]
    assert itens[1]['area_ha'] == pytest.approx(1.0) and itens[1]['desde_rev'] == 3


def test_incluir_por_shape_recorta_no_talhao(base):
    ajuste = [box(150, 0, 260, 100)]
    itens = montar_normal({}, {'incluir': [{'talhao': 2, 'fonte': 'shape', 'envio_id': 7},
                                           {'talhao': 3, 'fonte': 'shape', 'envio_id': 7}]}, base, Polygon(), ajuste, 0)
    assert itens[2]['area_ha'] == pytest.approx(0.5) and itens[2]['origem'] == 'shape'
    assert itens[3]['area_ha'] == pytest.approx(0.6)


def test_shape_que_nao_cobre_o_talhao_da_erro_listando(base):
    with pytest.raises(ErroGeracao, match=r'3'):
        montar_normal({}, {'incluir': [{'talhao': 3, 'fonte': 'shape', 'envio_id': 7}]}, base, Polygon(),
                      [box(0, 0, 50, 50)], 0)


def test_talhao_que_saiu_da_base_da_erro_sem_gerar(base):
    with pytest.raises(ErroGeracao, match=r'Base de hoje: 9'):
        montar_normal({}, {'incluir': [{'talhao': 9, 'fonte': 'sistema'}]}, base, Polygon(), [], 0)


def test_primeira_normal_parte_do_vazio_e_escopo_nulo_e_fazenda_inteira(base):
    itens = montar_normal({}, None, base, Polygon(), [], 0)
    assert sorted(itens) == [1, 2, 3] and all(v['origem'] == 'sistema' for v in itens.values())


def test_remover_tudo_da_erro_de_area_vazia(base):
    vig = {1: _item(box(0, 0, 100, 100))}
    with pytest.raises(ErroGeracao, match='vazia'):
        montar_normal(vig, {'incluir': [], 'remover': [1]}, base, Polygon(), [], 1)


def test_cobertura_fora_da_base_uniao_e_json(base):
    itens = {1: _item(box(0, 0, 100, 60)), 9: _item(box(500, 0, 510, 10))}
    assert cobertura(itens, base) == pytest.approx(100 / 3)      # talhão 1 conta inteiro, mesmo com obstáculo
    assert fora_da_base(itens, base) == [9]
    assert uniao(itens).area == pytest.approx(6000 + 100)
    j = itens_para_json(itens)
    assert {x['talhao'] for x in j} == {1, 9} and j[0]['wkt'].startswith('MULTIPOLYGON')


def test_talhao_do_sistema_todo_coberto_por_obstaculo_e_pulado_com_aviso(base):
    # Parte 1 pulava esse talhão; travar a geração inteira por ele é regressão (spec §4.1 só erra no shape)
    avisos = []
    tomado = box(-60, -60, 160, 160)                      # cobre o talhão 1 inteiro
    itens = montar_normal({}, {'incluir': [{'talhao': 1, 'fonte': 'sistema'}, {'talhao': 3, 'fonte': 'sistema'}]},
                          base, tomado, [], 0, avisos=avisos)
    assert sorted(itens) == [3]
    assert avisos and '1' in avisos[0]
