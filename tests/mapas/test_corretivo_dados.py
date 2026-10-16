import pytest
from shapely.geometry import MultiPolygon, Polygon, box

from mapas.corretivo_dados import (area_total, chave_cor, faixas, linhas_tabela, lista_os, rotulo,
                                   totais_por_produto)

DOL = {'tipo': 'calcario', 'calcario': 'dolomitico', 'dose': 2.0, 'dose_gesso': None, 'os': '4520', 'ordem': 1,
       'talhoes': [1, 3]}
FOS = {'tipo': 'fosfato', 'calcario': None, 'dose': 0.5, 'dose_gesso': None, 'os': '4521', 'ordem': 2,
       'talhoes': [2, 3]}
BLEND = {'tipo': 'blend', 'calcario': 'dolomitico', 'dose': 1.5, 'dose_gesso': 1.0, 'os': '4530', 'ordem': 3,
         'talhoes': [4, 5]}
AREAS = {'1': {'area_ha': 23.0, 'editada': False}, '2': {'area_ha': 23.0, 'editada': False},
         '3': {'area_ha': 21.4, 'editada': False}, '4': {'area_ha': 5.24, 'editada': True},
         '5': {'area_ha': 4.70, 'editada': False}}
DADOS = {'areas': AREAS, 'aplicacoes': [DOL, FOS, BLEND]}


def test_chave_cor_e_rotulo():
    assert chave_cor(DOL) == 'calcario:dolomitico' and rotulo(DOL) == 'Calc. Dolomítico'
    assert chave_cor({**DOL, 'calcario': 'ph7'}) == 'calcario:ph7' and rotulo({**DOL, 'calcario': 'ph7'}) == 'Calc. PH7'
    assert chave_cor(FOS) == 'fosfato' and rotulo(FOS) == 'Fosfato'
    assert chave_cor(BLEND) == 'blend' and rotulo(BLEND) == 'Blend · Dolomítico'


def test_linhas_tabela():
    assert linhas_tabela(DADOS) == [
        ['1', '23,00', 'Calc. Dolomítico', '2,00', '46,00', '4520'],
        ['2', '23,00', 'Fosfato', '0,50', '11,50', '4521'],
        ['3', '21,40', 'Calc. Dolomítico', '2,00', '42,80', '4520'],
        ['', '', 'Fosfato', '0,50', '10,70', '4521'],
        ['4', '5,24*', 'Blend · Dolomítico', '1,50', '7,86', '4530'],
        ['', '', '+ Gesso', '1,00', '5,24', '4530'],
        ['5', '4,70', 'Blend · Dolomítico', '1,50', '7,05', '4530'],
        ['', '', '+ Gesso', '1,00', '4,70', '4530'],
    ]


def test_linhas_talhao_sem_aplicacao_e_sem_geometria():
    dados = {'areas': {**AREAS, '9': {'area_ha': 3.0, 'editada': False}}, 'aplicacoes': [DOL]}
    assert ['9', '3,00', '—', '', '', ''] in linhas_tabela(dados)


def test_linhas_talhao_sem_geometria():
    # A tabela vem só de areas/aplicacoes: talhão fora de talhoes_geo continua listado.
    dados = {'areas': {'7': {'area_ha': 2.0, 'editada': False}}, 'aplicacoes': [{**FOS, 'talhoes': [7]}],
             'talhoes_geo': {'type': 'FeatureCollection', 'features': []}}
    assert linhas_tabela(dados) == [['7', '2,00', 'Fosfato', '0,50', '1,00', '4521']]


def test_totais_por_produto_blend_separado():
    blend_ph7 = {**BLEND, 'calcario': 'ph7', 'talhoes': [1], 'ordem': 4}
    t = totais_por_produto({'areas': AREAS, 'aplicacoes': [DOL, FOS, BLEND, blend_ph7]})
    assert t == [
        {'titulo': 'Calcário Dolomítico', 'toneladas': 88.8, 'detalhe': None},
        {'titulo': 'Fosfato', 'toneladas': 22.2, 'detalhe': None},
        {'titulo': 'Blend Dolomítico', 'toneladas': 24.85, 'detalhe': 'calc. 14,91 t + gesso 9,94 t'},
        {'titulo': 'Blend PH7', 'toneladas': 57.5, 'detalhe': 'calc. 34,50 t + gesso 23,00 t'},
    ]


def test_area_total_e_lista_os():
    assert area_total(DADOS) == pytest.approx(77.34)
    assert lista_os(DADOS) == ['4520', '4521', '4530']


@pytest.mark.parametrize('n', [1, 2, 3, 4])
def test_faixas_cobrem_talhao(n):
    t = Polygon([(0, 0), (100, 0), (120, 60), (10, 80)])
    partes = faixas(t, n)
    assert len(partes) == n
    assert sum(p.area for p in partes) == pytest.approx(t.area, rel=1e-9)
    assert all(not p.is_empty for p in partes)


@pytest.mark.parametrize('n', [2, 3])
@pytest.mark.parametrize('talhao', [Polygon([(0, 0), (1, 0), (0, 1)]),            # triângulo
                                    Polygon([(1, 0), (2, 1), (1, 2), (0, 1)])])   # losango
def test_faixas_nunca_saem_vazias(talhao, n):
    # Revisão de 16/10: com o intervalo pelo retângulo envolvente, a 2ª faixa do triângulo saía vazia
    # e a cor da 2ª aplicação sumia do PDF. O intervalo tem de vir dos vértices, como na tela (crFaixas).
    partes = faixas(talhao, n)
    assert all(p.area > 1e-9 for p in partes), [p.area for p in partes]
    assert sum(p.area for p in partes) == pytest.approx(talhao.area, rel=1e-9)


def test_faixas_cobrem_talhao_multiparte():
    t = MultiPolygon([box(0, 0, 50, 50).difference(box(20, 20, 30, 30)), box(80, 0, 120, 40)])
    partes = faixas(t, 3)
    assert sum(p.area for p in partes) == pytest.approx(t.area, rel=1e-9)
    for i in range(3):
        for j in range(i + 1, 3):
            assert partes[i].intersection(partes[j]).area == pytest.approx(0, abs=1e-6)
