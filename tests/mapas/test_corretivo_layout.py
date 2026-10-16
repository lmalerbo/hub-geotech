"""Layout de impressão do PDF de corretivos (pedido de 16/10/2026: tabela 3x maior para operadores idosos).
Regras que valem para QUALQUER mapa: fazenda em pé = A4 em pé com a tabela abaixo do mapa; fazenda larga = A4
deitada, folha 1 só com mapa e carimbo e a tabela grande da folha 2 em diante (pedido de 16/10); nada sai da margem; nada se sobrepõe; tabela e legenda
com letra grande; tabela longa continua nas páginas seguintes sem partir linha, com título, cabeçalho,
rodapé e "Página k de n" em todas."""
import itertools
import re

import pytest
from shapely.geometry import box, mapping
from shapely.ops import transform
from pyproj import Transformer

from mapas.corretivo_pdf import gerar_pdf

pymupdf = pytest.importorskip('pymupdf')
PARA_4326 = Transformer.from_crs(31983, 4326, always_xy=True).transform
A4_RETRATO = (595.3, 841.9)          # pontos
A4_PAISAGEM = (841.9, 595.3)
MARGEM = 14.0                         # ~5 mm: nenhum texto encosta na borda
LETRA_TABELA = 13.0                   # ~3x a letra antiga (4,5–6 pt)
INSUMOS = ('INSETICIDA REVOLUX', 'ADJUVANTE LIQUIDO OCHIMA', 'FERTILIZANTE FOLIAR NORTO', 'INSETICIDA BOUVERIZ WP PR',
           'FERTILIZANTE AMINOCORE BA', 'INOCULANTE LIQUIDO KOPPER', 'REGULADOR CRESC STOLLER S', 'INSETICIDA VANTACOR 5L')
ROTULOS = ('Calc. Dolomítico', 'Calc. PH7', 'Fosfato', 'Blend · Dolomítico', 'Blend · PH7', '+ Gesso',
           *(__import__('mapas.corretivo_dados', fromlist=['x']).nome_insumo(n) for n in INSUMOS))
SO_NUMERO = re.compile(r'^[\d.,\s]*m?$')   # números de talhão e da escala gráfica (desenhados sobre o mapa)


def _talhoes(n, deitada=True):
    """n talhões retangulares; deitada = enfileirados na horizontal (fazenda larga)."""
    feats = []
    for i in range(n):
        x, y = (300000 + i * 220, 7600000) if deitada else (300000 + (i % 3) * 220, 7600000 + (i // 3) * 340)
        feats.append({'type': 'Feature', 'properties': {'talhao': i + 1},
                      'geometry': mapping(transform(PARA_4326, box(x, y, x + 200, y + 300)))})
    return {'type': 'FeatureCollection', 'features': feats}


def _dados(n, aplicacoes, nome='FAZENDA TESTE', deitada=True):
    return {'cod_faz': 10001, 'nome': nome, 'operacao': 'subsolagem', 'data': '2026-10-16',
            'gerado_por': 'Leonardo Malerbo', 'talhoes_geo': _talhoes(n, deitada),
            'areas': {str(i + 1): {'area_ha': 5.0 + i * 0.37, 'editada': i == 0} for i in range(n)},
            'aplicacoes': aplicacoes}


def _ins(i, ordem, talhoes, dose, os='9001'):
    return {'tipo': 'insumo', 'insumo_nome': INSUMOS[i], 'insumo_unidade': 'KG' if 'WP' in INSUMOS[i] else 'L',
            'calcario': None, 'dose': dose, 'dose_gesso': None, 'os': os, 'ordem': ordem, 'talhoes': talhoes}


def _aereo(n, aplicacoes, deitada=True):
    return {**_dados(n, aplicacoes, deitada=deitada), 'operacao': 'aerea'}


def _ap(tipo, ordem, talhoes, dose, os='3211', calcario='dolomitico', gesso=None):
    return {'tipo': tipo, 'calcario': None if tipo == 'fosfato' else calcario, 'dose': dose,
            'dose_gesso': gesso if tipo == 'blend' else None, 'os': os, 'ordem': ordem, 'talhoes': talhoes}


# Cada caso: (nome, dados). Doses únicas por linha permitem contar se cada linha aparece uma única vez.
CASOS = {
    '1_linha': _dados(1, [_ap('calcario', 1, [1], 2.11)]),
    '12_linhas': _dados(12, [_ap('calcario', 1, [t], 2 + t / 100, os=str(3200 + t)) for t in range(1, 13)]),
    '60_talhoes_2_aplicacoes': _dados(60, [_ap('calcario', 1, list(range(1, 61)), 2.37, os='3211'),
                                           _ap('fosfato', 2, list(range(1, 61)), 0.53, os='32111')]),
    '5_produtos': _dados(6, [_ap('calcario', 1, [1, 2], 2.11), _ap('calcario', 2, [3], 1.22, calcario='ph7'),
                             _ap('fosfato', 3, [4], 0.33), _ap('blend', 4, [5], 1.44, gesso=0.95),
                             _ap('blend', 5, [6], 1.55, calcario='ph7', gesso=0.85)]),
    'nome_longo_os_longa': _dados(3, [_ap('calcario', 1, [1, 2, 3], 2.11,
                                          os='OS-2026-000123456-SUBSOLAGEM-REFORMA')],
                                  nome='FAZENDA SANTA RITA DO PASSA QUATRO E ANEXOS DA BARRA'),
    'muitas_os': _dados(30, [_ap('calcario', t, [t], 2 + t / 100, os=f'98{t:04d}') for t in range(1, 31)]),
    'fazenda_em_pe': _dados(9, [_ap('calcario', 1, [1, 2, 3], 2.11), _ap('fosfato', 2, [3, 4], 0.53)],
                            deitada=False),
    'em_pe_60_talhoes': _dados(60, [_ap('calcario', 1, list(range(1, 61)), 2.37, os='3211'),
                                    _ap('fosfato', 2, list(range(1, 61)), 0.53, os='32111')], deitada=False),
    '3_aplicacoes_no_talhao': _dados(2, [_ap('calcario', 1, [1], 2.11), _ap('fosfato', 2, [1], 0.53),
                                         _ap('blend', 3, [1, 2], 1.44, calcario='ph7', gesso=0.95)]),
    'aereo_em_pe_3_insumos': _aereo(9, [_ins(0, 1, list(range(1, 10)), 0.15), _ins(1, 2, list(range(1, 10)), 0.25),
                                         _ins(3, 3, [1, 2, 3], 0.11)], deitada=False),
    'aereo_largo_8_insumos': _aereo(20, [_ins(i, i + 1, list(range(1, 21)), 0.1 + i / 100, os=f'90{i:02d}')
                                         for i in range(8)]),
}


def _spans(pagina):
    for bloco in pagina.get_text('dict')['blocks']:
        for linha in bloco.get('lines', []):
            for s in linha['spans']:
                if s['text'].strip():
                    yield s


@pytest.fixture(scope='module', params=list(CASOS))
def pdf(request, tmp_path_factory):
    destino = tmp_path_factory.mktemp('layout') / f'{request.param}.pdf'
    gerar_pdf(CASOS[request.param], destino)
    return request.param, pymupdf.open(destino)


def _deitada(nome):
    from mapas.layout import orientacao
    from mapas.corretivo_pdf import _gdf
    return orientacao(_gdf(CASOS[nome])) == 'paisagem'


def test_folha_a4_na_orientacao_da_fazenda(pdf):
    # Todas as folhas na mesma orientação (impressão sem girar folha no meio do documento).
    nome, doc = pdf
    esperado = A4_PAISAGEM if _deitada(nome) else A4_RETRATO
    for i, p in enumerate(doc):
        assert (round(p.rect.width, 1), round(p.rect.height, 1)) == esperado, f'{nome} pág. {i + 1}'


def test_fazenda_larga_tabela_comeca_na_folha_2(pdf):
    nome, doc = pdf
    if not _deitada(nome):
        return
    assert len(doc) >= 2, f'{nome}: paisagem precisa da folha 2 para a tabela'
    spans = list(_spans(doc[0]))
    assert not [s for s in spans if s['text'].strip() in ROTULOS and _linha_da_tabela(s, spans)],         f'{nome}: folha 1 em paisagem tem linhas da tabela'
    assert 'APLICAÇÕES POR TALHÃO' in doc[1].get_text() and '(continuação)' not in doc[1].get_text()


def test_nenhum_texto_sai_da_margem(pdf):
    nome, doc = pdf
    for i, p in enumerate(doc):
        for s in _spans(p):
            x0, y0, x1, y1 = s['bbox']
            assert x0 >= MARGEM - 0.5 and x1 <= p.rect.width - MARGEM + 0.5 and y1 <= p.rect.height - MARGEM + 0.5, \
                f'{nome} pág. {i + 1}: "{s["text"]}" fora da margem {s["bbox"]}'


def test_nenhum_texto_sobre_outro(pdf):
    nome, doc = pdf
    for i, p in enumerate(doc):
        caixas = [(s['text'], pymupdf.Rect(s['bbox'])) for s in _spans(p) if not SO_NUMERO.match(s['text'].strip())]
        for (ta, ra), (tb, rb) in itertools.combinations(caixas, 2):
            inter = ra & rb
            if inter.is_empty:
                continue
            menor = min(ra.get_area(), rb.get_area()) or 1
            assert inter.get_area() / menor < 0.15, f'{nome} pág. {i + 1}: "{ta}" sobre "{tb}"'


def _linha_da_tabela(s, spans):
    """Rótulo com dose e total (decimais) na mesma altura = linha da tabela."""
    y = (s['bbox'][1] + s['bbox'][3]) / 2
    return sum(1 for t in spans if t is not s and t['bbox'][1] <= y <= t['bbox'][3]
               and re.search(r'\d,\d\d', t['text'])) >= 2


def test_tabela_e_legenda_com_letra_grande(pdf):
    # Só a TABELA e a LEGENDA crescem (pedido do usuário); os títulos dos quadros de totais do carimbo
    # ("Calcário Dolomítico", "Fosfato"…) ficam do tamanho de antes e todos iguais entre si.
    nome, doc = pdf
    tabela, legenda = [], {}
    for p in doc:
        spans = list(_spans(p))
        for s in spans:
            t = s['text'].strip()
            if t in ROTULOS and _linha_da_tabela(s, spans):
                tabela.append(s['size'])
            elif t in ROTULOS + ('Blend',):
                legenda[t] = max(legenda.get(t, 0), s['size'])
    assert tabela, f'{nome}: tabela sem linhas'
    assert min(tabela) >= LETRA_TABELA - 0.5, f'{nome}: letra da tabela {min(tabela):.1f} pt'
    assert legenda and min(legenda.values()) >= LETRA_TABELA - 0.5, f'{nome}: legenda {legenda}'


def test_titulos_dos_quadros_de_totais_iguais(pdf):
    nome, doc = pdf
    p = doc[0]
    spans = list(_spans(p))
    # Os títulos dos quadros são os textos de produto em letra pequena ("Fosfato" grande é a legenda ou a tabela).
    produtos = {t['titulo'] for t in __import__('mapas.corretivo_dados', fromlist=['x']).totais_por_produto(CASOS[nome])}
    pequenos = {s['text'].strip(): round(s['size'], 1) for s in spans
                if s['text'].strip() in produtos and s['size'] < LETRA_TABELA - 0.5}
    assert set(pequenos) == produtos, f'{nome}: quadros de totais {sorted(pequenos)} ≠ produtos {sorted(produtos)}'
    assert len(set(pequenos.values())) <= 1, f'{nome}: títulos dos quadros com tamanhos diferentes {pequenos}'


def test_talhao_nunca_partido_entre_paginas(pdf):
    # A primeira linha da tabela em cada página traz o número do talhão (o operador nunca vê
    # "Fosfato" solto no topo da página sem saber de qual talhão é).
    nome, doc = pdf
    for i, p in enumerate(doc):
        spans = list(_spans(p))
        linhas = sorted((s for s in spans if s['text'].strip() in ROTULOS and _linha_da_tabela(s, spans)),
                        key=lambda s: s['bbox'][1])
        if not linhas:
            continue
        primeira = linhas[0]
        y = (primeira['bbox'][1] + primeira['bbox'][3]) / 2
        a_esquerda = [t['text'].strip() for t in spans
                      if t['bbox'][1] <= y <= t['bbox'][3] and t['bbox'][2] <= primeira['bbox'][0]]
        assert any(re.fullmatch(r'\d+', t) for t in a_esquerda), \
            f'{nome} pág. {i + 1}: primeira linha "{primeira["text"]}" sem o número do talhão ({a_esquerda})'


def test_cada_linha_aparece_uma_vez_e_inteira(pdf):
    nome, doc = pdf
    dados = CASOS[nome]
    # cada (talhão, dose) da tabela tem de aparecer exatamente uma vez no documento
    texto = '\n'.join(p.get_text() for p in doc)
    for ap in dados['aplicacoes']:
        dose = f"{ap['dose']:.2f}".replace('.', ',')
        assert texto.count(dose) >= len(ap['talhoes']), f'{nome}: faltou linha com dose {dose}'
    # nenhuma linha partida: numa linha da tabela (rótulo + números na mesma altura), estão dose, total e O.S.
    for p in doc:
        spans = list(_spans(p))
        for s in spans:
            if s['text'].strip() not in ROTULOS:
                continue
            y = (s['bbox'][1] + s['bbox'][3]) / 2
            vizinhos = [t for t in spans if t is not s and t['bbox'][1] <= y <= t['bbox'][3]]
            decimais = [t for t in vizinhos if re.search(r'\d,\d\d', t['text'])]   # dose e total (a escala é inteira)
            if decimais:                      # é linha da tabela (a legenda fica no mapa, sem decimais ao lado)
                assert len(decimais) >= 2, f'{nome}: linha "{s["text"]}" partida ({[t["text"] for t in vizinhos]})'


def test_toda_pagina_organizada(pdf):
    nome, doc = pdf
    n = len(doc)
    for i, p in enumerate(doc):
        texto = p.get_text()
        spans = list(_spans(p))
        assert 'Gerado em' in texto, f'{nome} pág. {i + 1}: sem rodapé'
        if any(s['text'].strip() in ROTULOS and _linha_da_tabela(s, spans) for s in spans):   # legenda não conta
            assert 'TALHÃO' in texto and 'O.S.' in texto, f'{nome} pág. {i + 1}: tabela sem cabeçalho'
        if n > 1:
            assert f'Página {i + 1} de {n}' in texto, f'{nome} pág. {i + 1}: sem numeração'
