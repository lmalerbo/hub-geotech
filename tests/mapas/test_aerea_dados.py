"""Regras do mapa de Aplicação aérea (spec 2026-10-16-mapas-aplicacao-aerea-design.md): talhão 400 com 5% da área,
total do insumo = dose × área dos talhões dele × 1,05, cores por insumo na ordem de aparição, nomes legíveis."""
from mapas.corretivo_dados import (
    PALETA_INSUMOS, area_total, br_dose, cores_do_mapa, linhas_tabela, margem, nome_insumo, rotulo, totais_por_produto,
)


def _ap(nome, unidade, dose, talhoes, ordem, os='9001'):
    return {'tipo': 'insumo', 'insumo_nome': nome, 'insumo_unidade': unidade, 'calcario': None, 'dose': dose,
            'dose_gesso': None, 'os': os, 'ordem': ordem, 'talhoes': talhoes}


DADOS = {
    'operacao': 'aerea',
    'areas': {'1': {'area_ha': 60.0}, '2': {'area_ha': 40.0, 'editada': True}},
    'aplicacoes': [_ap('INSETICIDA REVOLUX', 'L', 0.5, [1, 2], 1), _ap('ADJUVANTE LIQUIDO OCHIMA', 'L', 0.1, [1], 2),
                   _ap('REGULADOR SUMITOMO PROGIB', 'KG', 0.008, [2], 3)],
}


def test_nome_do_insumo_legivel_mantendo_siglas():
    assert nome_insumo('INSETICIDA BOUVERIZ WP PR') == 'Inseticida Bouveriz WP PR'
    assert nome_insumo('FERTILIZANTE UPPER 1L') == 'Fertilizante Upper 1L'
    assert nome_insumo('INSETICIDA CHLORANTR+LAMB') == 'Inseticida Chlorantr+Lamb'
    assert rotulo(DADOS['aplicacoes'][0]) == 'Inseticida Revolux'


def test_dose_com_ate_tres_casas():
    assert [br_dose(v) for v in (0.5, 0.15, 0.008, 0.035, 10, 1234.5)] == ['0,50', '0,15', '0,008', '0,035', '10,00', '1.234,50']


def test_margem_de_5_por_cento_e_area_total_com_ela():
    assert margem(DADOS) == 5.0
    assert area_total(DADOS) == 105.0


def test_tabela_tem_unidade_junto_do_numero_e_talhao_400_so_com_area():
    assert linhas_tabela(DADOS) == [
        ['1', '60,00', 'Inseticida Revolux', '0,50 L', '30,00 L', '9001'],
        ['', '', 'Adjuvante Liquido Ochima', '0,10 L', '6,00 L', '9001'],
        ['2', '40,00*', 'Inseticida Revolux', '0,50 L', '20,00 L', '9001'],
        ['', '', 'Regulador Sumitomo Progib', '0,008 kg', '0,32 kg', '9001'],
        ['400', '5,00', '', '', '', ''],
    ]


def test_total_do_insumo_e_dose_vezes_area_dele_com_margem():
    assert totais_por_produto(DADOS) == [
        {'titulo': 'Inseticida Revolux', 'total': 52.5, 'unidade': 'L', 'detalhe': None},        # 100 ha × 1,05 × 0,5
        {'titulo': 'Adjuvante Liquido Ochima', 'total': 6.3, 'unidade': 'L', 'detalhe': None},  # 60 ha × 1,05 × 0,1
        {'titulo': 'Regulador Sumitomo Progib', 'total': 0.34, 'unidade': 'kg', 'detalhe': None},  # 40 × 1,05 × 0,008
    ]


def test_mesmo_insumo_em_duas_aplicacoes_soma_num_quadro_so():
    d = {**DADOS, 'aplicacoes': [_ap('INSETICIDA REVOLUX', 'L', 0.5, [1], 1), _ap('INSETICIDA REVOLUX', 'L', 0.4, [2], 2, os='9002')]}
    assert totais_por_produto(d) == [{'titulo': 'Inseticida Revolux', 'total': 48.3, 'unidade': 'L', 'detalhe': None}]


def test_cores_por_insumo_na_ordem_de_aparicao():
    cores = cores_do_mapa(DADOS)
    assert list(cores.values()) == PALETA_INSUMOS[:3]
    d = {**DADOS, 'aplicacoes': [_ap(f'INSUMO {i}', 'L', 1, [1], i) for i in range(12)]}
    assert list(cores_do_mapa(d).values())[10] == PALETA_INSUMOS[0]          # acima de 10 a paleta repete


def test_corretivo_continua_sem_margem():
    d = {'operacao': 'subsolagem', 'areas': {'1': {'area_ha': 10.0}},
         'aplicacoes': [{'tipo': 'fosfato', 'calcario': None, 'dose': 1.0, 'dose_gesso': None, 'os': '1', 'ordem': 1, 'talhoes': [1]}]}
    assert area_total(d) == 10.0 and margem(d) == 0
    assert totais_por_produto(d) == [{'titulo': 'Fosfato', 'total': 10.0, 'unidade': 't', 'detalhe': None}]
    assert all(r[0] != '400' for r in linhas_tabela(d))
