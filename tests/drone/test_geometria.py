import math

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, box

from drone.erros import ErroGeracao
from drone.geometria import recortar, uniao_buffers


def test_normal_sem_obstaculos_e_a_fazenda_inteira(talhoes):
    r = recortar(talhoes, uniao_buffers({}, {}))
    assert r.aplicacao_ha == pytest.approx(2.0)
    assert r.area_total_ha == pytest.approx(2.0)
    assert [t['aplicavel_ha'] for t in r.por_talhao] == pytest.approx([1.0, 1.0])


def test_arvore_de_15m_tira_um_circulo(talhoes):
    b = uniao_buffers({15: [Point(50, 50)]}, {15: 15})
    r = recortar(talhoes, b)
    assert r.por_talhao[0]['aplicavel_ha'] == pytest.approx(1.0 - math.pi * 15**2 / 1e4, rel=1e-2)
    assert r.por_talhao[1]['aplicavel_ha'] == pytest.approx(1.0)


def test_rede_em_linha_de_25m_vira_faixa(talhoes):
    b = uniao_buffers({25: [LineString([(0, 50), (200, 50)])]}, {25: 25})
    r = recortar(talhoes, b)
    assert r.aplicacao_ha == pytest.approx(2.0 - 200 * 50 / 1e4, rel=1e-3)


def test_catacao_mancha_isolada_vira_bloco_com_folga_de_5m(talhoes):
    # mancha de 10 x 10 m no meio do talhão 1: bloco = contorno + 5 m de folga (cantos retos)
    r = recortar(talhoes, uniao_buffers({}, {}), infestacao=[box(40, 40, 50, 50)], agrupar=20, folga=5)
    assert r.aplicacao_ha == pytest.approx(20 * 20 / 1e4, rel=0.02)
    assert r.por_talhao[1]['aplicavel_ha'] == pytest.approx(0.0)


def test_catacao_manchas_a_menos_de_20m_viram_um_bloco_so(talhoes):
    perto = [box(10, 40, 12, 42), box(25, 40, 27, 42)]          # 13 m entre elas
    r = recortar(talhoes, uniao_buffers({}, {}), infestacao=perto, agrupar=20, folga=5)
    assert len(r.area.geoms) == 1
    assert r.aplicacao_ha == pytest.approx(27 * 12 / 1e4, rel=0.02)   # (17+10) x (2+10)


def test_catacao_manchas_a_mais_de_20m_ficam_separadas(talhoes):
    longe = [box(10, 40, 12, 42), box(40, 40, 42, 42)]          # 28 m entre elas
    r = recortar(talhoes, uniao_buffers({}, {}), infestacao=longe, agrupar=20, folga=5)
    assert len(r.area.geoms) == 2


def test_catacao_bloco_tem_poucos_vertices(talhoes):
    # nuvem de 40 manchinhas espalhadas num trecho de 60 x 60 m
    manchas = [box(20 + (i * 7) % 60, 20 + (i * 13) % 60, 21 + (i * 7) % 60, 21 + (i * 13) % 60) for i in range(40)]
    r = recortar(talhoes, uniao_buffers({}, {}), infestacao=manchas, agrupar=20, folga=5)
    assert all(len(p.exterior.coords) - 1 <= 12 for p in r.area.geoms)


def test_resultado_vazio_da_erro_em_portugues(talhoes):
    b = uniao_buffers({50: [box(0, 0, 200, 100)]}, {50: 50})
    with pytest.raises(ErroGeracao, match='vazia'):
        recortar(talhoes, b)


def test_infestacao_fora_dos_talhoes_da_erro(talhoes):
    with pytest.raises(ErroGeracao, match='vazia'):
        recortar(talhoes, uniao_buffers({}, {}), infestacao=[box(1000, 1000, 1010, 1010)], agrupar=20, folga=5)


def test_geometria_invalida_e_corrigida(talhoes):
    gravata = gpd.GeoSeries.from_wkt(['POLYGON((0 0, 100 100, 100 0, 0 100, 0 0))']).iloc[0]
    r = recortar(talhoes, uniao_buffers({50: [gravata]}, {50: 1}))
    assert r.aplicacao_ha < 2.0


def test_area_prod_vazia_conta_zero_e_e_informada(talhoes):
    talhoes.loc[1, 'AREA_PROD'] = float('nan')
    r = recortar(talhoes, uniao_buffers({}, {}))
    assert r.area_total_ha == pytest.approx(1.0)
    assert r.talhoes_sem_area_prod == [2]
