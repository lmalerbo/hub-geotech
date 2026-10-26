"""Enquadramento do mapa dos Mapas de aplicação (pedido de 16/10 com o PDF da 10004: "dá para aproximar mais a fazenda")
e número de TODOS os talhões da fazenda no mapa, inclusive os que não estão no mapa de aplicação."""
import pymupdf
from shapely.geometry import box, mapping
from shapely.ops import transform
from pyproj import Transformer

from mapas import corretivo_pdf
from mapas.corretivo_pdf import gerar_pdf
from tests.mapas.test_corretivo_layout import _aereo, _ins

PARA_4326 = Transformer.from_crs(31983, 4326, always_xy=True).transform


def _fazenda_quadrada(n_lado=4):
    """Fazenda quase quadrada (um pouco mais larga que alta): fica deitada e é a ALTURA que limita o zoom."""
    feats = []
    for i in range(n_lado * n_lado):
        c, l = i % n_lado, i // n_lado
        x, y = 300000 + c * 260, 7600000 + l * 240
        feats.append({'type': 'Feature', 'properties': {'talhao': i + 1},
                      'geometry': mapping(transform(PARA_4326, box(x, y, x + 250, y + 230)))})
    return {'type': 'FeatureCollection', 'features': feats}


def _dados(no_mapa):
    d = _aereo(len(no_mapa), [_ins(0, 1, no_mapa, 0.15)])
    d['talhoes_geo'] = _fazenda_quadrada()
    d['areas'] = {str(t): {'area_ha': 5.0, 'editada': False} for t in no_mapa}
    return d


def _reservas_usadas(d, tmp_path):
    usadas = []
    original = corretivo_pdf._enquadrar
    corretivo_pdf._enquadrar = lambda *a: (lambda r: usadas.append(r[4]) or r)(original(*a))
    try:
        gerar_pdf(d, tmp_path / 'm.pdf')
    finally:
        corretivo_pdf._enquadrar = original
    return usadas


def test_fazenda_limitada_pela_altura_usa_enquadramento_mais_justo(tmp_path):
    assert _reservas_usadas(_dados([1, 2, 3]), tmp_path) == [corretivo_pdf.RESERVAS[0]]


def test_numero_de_todos_os_talhoes_da_fazenda():
    # Os números têm contorno branco e viram desenho no PDF: confere nos textos do mapa antes de salvar.
    from mapas.layout import nova_pagina
    d = _dados([1, 2, 3])
    pg = nova_pagina(297, 210)
    corretivo_pdf._mapa(pg, d, corretivo_pdf._gdf(d), 10, 10, 277, 150)
    numeros = {t.get_text(): t.get_fontsize() for ax in pg.fig.axes for t in ax.texts if t.get_text().isdigit()}
    assert {str(t) for t in range(1, 17)} <= set(numeros)
    assert min(numeros[str(t)] for t in range(1, 17)) >= 9          # 16/10: números maiores (eram 6,5 pt)


def test_talhao_com_auto_intersecao_vira_geometria_valida():
    """Talhão em 'gravata' (auto-interseção, como o 1 da fazenda 10650): o GEOS do Pyodide quebra no union_all
    do enquadramento (TopologyException fatal no navegador), então _gdf conserta a geometria na entrada."""
    d = _dados([1, 2])
    x, y = 300000, 7600000
    gravata = {'type': 'Polygon', 'coordinates': [[PARA_4326(*p) for p in
               [(x, y), (x + 250, y + 230), (x + 250, y), (x, y + 230), (x, y)]]]}
    d['talhoes_geo']['features'][0]['geometry'] = gravata
    gdf = corretivo_pdf._gdf(d)
    assert gdf.geometry.is_valid.all()
    assert set(gdf.geometry.geom_type) <= {'Polygon', 'MultiPolygon'}
    assert gdf.geometry.iloc[0].area > 20000          # as duas metades da gravata continuam lá
