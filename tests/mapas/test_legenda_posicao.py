"""Posição da legenda no mapa dos Mapas de aplicação (pendência de 04/11: "a legenda pode cobrir talhões").
Como o QGIS faz com rótulos: muitas posições candidatas encostadas na moldura, logo e escala proibidos,
e a mais barata vence (livre > perto de um canto > cantos direitos, como sempre foi)."""
from shapely.geometry import Point, Polygon, box, mapping
from shapely.ops import transform
from pyproj import Transformer

from mapas import corretivo_pdf
from mapas.corretivo_pdf import _posicao_legenda, gerar_pdf
from tests.mapas.test_corretivo_layout import _aereo, _ins

X, Y, W, H = 10, 20, 270, 125                 # moldura do mapa (mm da página)
BW, BH = 66, 60                               # legenda do aéreo com 8 insumos
LOGO = box(X, Y, X + 40, Y + 19)
ESCALA = box(X, Y + H - 12, X + 50, Y + H)
PROIBIDOS = [LOGO, ESCALA]
VAZIO = Polygon()


def _pos(fazenda, rotulos=()):
    return _posicao_legenda(fazenda, list(rotulos), PROIBIDOS, X, Y, W, H, BW, BH)


def _caixa(r):
    bx, by = r[0], r[1]
    return box(bx, by, bx + BW, by + BH)


def test_sem_fazenda_no_caminho_fica_no_canto_inferior_direito():
    bx, by, cobre, rot = _pos(VAZIO)
    assert (bx, by) == (X + W - BW - 2.5, Y + H - BH - 2.5) and cobre == 0 and rot == 0


def test_canto_inferior_ocupado_sobe_para_o_superior_direito():
    bx, by, cobre, _ = _pos(box(X + W - 80, Y + H - 50, X + W, Y + H))
    assert (bx, by) == (X + W - BW - 2.5, Y + 2.5) and cobre == 0


def test_lado_direito_inteiro_ocupado_acha_espaco_livre_em_outra_borda():
    fazenda = box(X + W - 90, Y, X + W, Y + H)
    r = _pos(fazenda)
    assert r[2] == 0 and not _caixa(r).intersects(fazenda.buffer(1.0))


def test_nunca_em_cima_do_logo_nem_da_escala():
    # só sobra livre a faixa da esquerda, onde ficam o logo e a escala: a legenda não pode ir para lá
    fazenda = box(X + 52, Y, X + W, Y + H)
    r = _pos(fazenda)
    assert not _caixa(r).intersects(LOGO) and not _caixa(r).intersects(ESCALA)


def test_sem_espaco_livre_cobre_o_minimo_sem_tampar_numero_de_talhao():
    fazenda = box(X, Y, X + W, Y + H)                           # a fazenda ocupa a moldura toda
    rotulos = [Point(X + W - 30, Y + H - 30), Point(X + W - 30, Y + 30), Point(X + 120, Y + 30),
               Point(X + 120, Y + H - 30)]
    r = _pos(fazenda, rotulos)
    assert r[3] == 0 and not any(_caixa(r).intersects(p.buffer(3)) for p in rotulos)


# ---------- ponta a ponta, no PDF ----------

PARA_4326 = Transformer.from_crs(31983, 4326, always_xy=True).transform


def _fazenda_em_u():
    """Coluna de talhões na direita (ocupa os dois cantos direitos) + fileira embaixo; o meio de cima fica vazio."""
    caixas = [box(302000, 7600000 + i * 300, 302200, 7600000 + i * 300 + 290) for i in range(3)]
    caixas += [box(300000 + i * 450, 7600000, 300000 + i * 450 + 430, 7600250) for i in range(4)]
    return {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'talhao': i + 1}, 'geometry': mapping(transform(PARA_4326, c))}
        for i, c in enumerate(caixas)]}


def _posicoes(d, tmp_path):
    usadas = []
    original = corretivo_pdf._posicao_legenda
    corretivo_pdf._posicao_legenda = lambda *a: (lambda r: usadas.append(r) or r)(original(*a))
    try:
        gerar_pdf(d, tmp_path / 'l.pdf')
    finally:
        corretivo_pdf._posicao_legenda = original
    return usadas


def test_pdf_fazenda_nos_dois_cantos_direitos_legenda_nao_cobre_talhao(tmp_path):
    d = _aereo(7, [_ins(i, i + 1, list(range(1, 8)), 0.1) for i in range(8)])
    d['talhoes_geo'] = _fazenda_em_u()
    usadas = _posicoes(d, tmp_path)
    assert usadas and usadas[-1][2] == 0 and usadas[-1][3] == 0


def test_pdf_fazenda_deitada_com_legenda_alta_nao_cobre_talhao(tmp_path):
    d = _aereo(20, [_ins(i, i + 1, list(range(1, 21)), 0.1) for i in range(8)])
    usadas = _posicoes(d, tmp_path)
    assert usadas and usadas[-1][2] == 0 and usadas[-1][3] == 0
