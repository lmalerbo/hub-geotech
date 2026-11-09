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


def test_tabela_so_com_talhao_area_e_total(texto):
    assert 'TALHÃO' in texto and 'ÁREA (ha)' in texto and 'TOTAL' in texto
    for fora in ('INSUMO', 'DOSE/ha', 'O.S.\n'):
        assert fora not in texto, f'{fora!r} não deveria estar no PDF aéreo'
    assert '+ 0,' in texto and 'kg' in texto            # talhões 1–3 têm L e kg: total com as duas unidades


def test_legenda_tem_area_de_aplicacao_e_os_insumos(texto):
    from mapas.corretivo_dados import nome_insumo
    from tests.mapas.test_corretivo_layout import INSUMOS
    assert 'Área de aplicação' in texto
    for i in (0, 1, 3):
        assert nome_insumo(INSUMOS[i]) in texto


def test_total_grande_cabe_na_coluna(tmp_path):
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
                assert s['bbox'][2] <= p.rect.width - 10 * 72 / 25.4, 'total sai da folha'
                assert vizinhos[i - 1]['bbox'][2] + 8 <= s['bbox'][0], 'total encosta na área'
                return
    raise AssertionError('total 104.000,00 L não encontrado')


# A posição da legenda (antes só os dois cantos direitos) é testada em test_legenda_posicao.py.

def _spans(destino):
    doc = pymupdf.open(destino)
    return [s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans'] if s['text'].strip()]


@pytest.fixture(scope='module')
def spans_aereo(tmp_path_factory):
    destino = tmp_path_factory.mktemp('aereo_sp') / 'a.pdf'
    gerar_pdf(CASOS['aereo_em_pe_3_insumos'], destino)
    return _spans(destino)


def test_tipo_do_mapa_e_titulo_em_destaque(spans_aereo):
    tit = [s for s in spans_aereo if s['text'].strip() == 'APLICAÇÃO AÉREA']
    assert tit and tit[0]['size'] >= 10, 'tipo do mapa precisa ser título (>= 10 pt)'


def test_cards_de_totais_maiores(spans_aereo):
    from mapas.corretivo_dados import totais_por_produto
    titulos = [q['titulo'] for q in totais_por_produto(CASOS['aereo_em_pe_3_insumos'])]
    palavras = {p for t in titulos for p in t.split()}
    pedacos = [s for s in spans_aereo if s['size'] < 11 and set(s['text'].split()) <= palavras]   # o nome pode ter 2 linhas
    assert pedacos and min(s['size'] for s in pedacos) >= 5.9, f'nome do insumo nos cards pequeno demais: {pedacos}'
    texto = ' '.join(s['text'].strip() for s in pedacos)
    for t in titulos:
        assert t in texto, f'nome do insumo cortado no card: {t!r} em {texto!r}'


def test_total_grande_nao_e_cortado_no_card_em_retrato(tmp_path):
    from tests.mapas.test_corretivo_layout import _aereo, _ins, _talhoes
    d = _aereo(2, [_ins(0, 1, [1, 2], 20.0)], deitada=False)
    d['areas'] = {'1': {'area_ha': 480.0, 'editada': False}, '2': {'area_ha': 5200.0, 'editada': False}}
    d['talhoes_geo'] = _talhoes(9, deitada=False)
    destino = tmp_path / 'grande.pdf'
    gerar_pdf(d, destino)
    assert any(s['text'].strip() == '119.280,00' for s in _spans(destino)), 'total do card cortado'   # 5.680 × 20 × 1,05
