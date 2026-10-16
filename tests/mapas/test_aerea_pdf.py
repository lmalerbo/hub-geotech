"""PDF do mapa de Aplicação aérea: selo, unidade nos quadros, talhão 400 com a margem e total com ela."""
import pymupdf
import pytest

from mapas.corretivo_pdf import gerar_pdf
from tests.mapas.test_corretivo_layout import CASOS


@pytest.fixture(scope='module')
def texto(tmp_path_factory):
    destino = tmp_path_factory.mktemp('aereo') / 'aereo.pdf'
    gerar_pdf(CASOS['aereo_em_pe_3_insumos'], destino)
    return '\n'.join(p.get_text() for p in pymupdf.open(destino))


def test_selo_e_subtitulo_do_aereo(texto):
    assert 'APLICAÇÃO AÉREA' in texto and 'MAPA DE APLICAÇÃO · AÉREA · O.S. 9001' in texto
    assert 'CORRETIVO' not in texto


def test_talhao_400_com_a_margem_e_total_com_ela(texto):
    areas = [5.0 + i * 0.37 for i in range(9)]
    margem = round(sum(areas) * 0.05, 2)
    assert f'{margem:.2f}'.replace('.', ',') in texto.split('400', 1)[1].split('\n', 2)[1]
    assert f'{sum(areas) + margem:.2f}'.replace('.', ',') in texto          # linha Total e área do carimbo
    assert 'TALHÕES + 5%' in texto


def test_unidade_do_insumo_na_tabela_e_nos_quadros(texto):
    assert '0,15 L' in texto and '0,11 kg' in texto
    assert 'DOSE/ha' in texto and 'INSUMO' in texto


def test_total_grande_nao_encosta_na_dose_nem_na_os(tmp_path):
    from tests.mapas.test_corretivo_layout import _aereo, _ins
    d = _aereo(2, [_ins(0, 1, [1, 2], 20.0, os='OS-2026-123')], deitada=False)          # retrato: o mais estreito
    d['areas'] = {'1': {'area_ha': 480.0, 'editada': False}, '2': {'area_ha': 5200.0, 'editada': False}}
    from tests.mapas.test_corretivo_layout import _talhoes
    d['talhoes_geo'] = _talhoes(9, deitada=False)                            # fazenda em pé -> A4 retrato
    destino = tmp_path / 'grande.pdf'
    gerar_pdf(d, destino)
    for p in pymupdf.open(destino):
        spans = [s for b in p.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans'] if s['text'].strip()]
        for s in spans:
            if s['text'].strip() == '104.000,00 L':                      # total do talhão 2: 5.200 × 20
                y = (s['bbox'][1] + s['bbox'][3]) / 2
                vizinhos = sorted((t for t in spans if t['bbox'][1] <= y <= t['bbox'][3]), key=lambda t: t['bbox'][0])
                i = vizinhos.index(s)
                assert vizinhos[i - 1]['bbox'][2] + 8 <= s['bbox'][0], 'total encosta na dose'
                assert s['bbox'][2] + 8 <= vizinhos[i + 1]['bbox'][0], 'total encosta na O.S.'
                return
    raise AssertionError('total 104.000,00 L não encontrado')


def test_legenda_vai_para_o_canto_direito_que_cobre_menos_a_fazenda(tmp_path):
    from tests.mapas.test_corretivo_layout import _aereo, _ins
    from mapas import corretivo_pdf
    d = _aereo(20, [_ins(i, i + 1, list(range(1, 21)), 0.1) for i in range(8)])
    usados = []
    original = corretivo_pdf._canto_legenda
    corretivo_pdf._canto_legenda = lambda *a: usados.append(original(*a)) or usados[-1]
    try:
        gerar_pdf(d, tmp_path / 'l.pdf')
    finally:
        corretivo_pdf._canto_legenda = original
    assert usados == ['cima']                 # fazenda deitada no meio: embaixo a legenda alta cobriria talhões
