import datetime
import re

import geopandas as gpd
from shapely.geometry import box

from drone.geometria import recortar, uniao_buffers
from drone.mapa_pdf import DadosMapa, gerar_pdf, orientacao, safra_de


def _talhoes(largura, altura):
    return gpd.GeoDataFrame({'TALHAO': [1, 2], 'AREA_PROD': [10.0, 12.5]},
                            geometry=[box(0, 0, largura / 2, altura), box(largura / 2, 0, largura, altura)],
                            crs=31983)


def _pdf(tmp_path, t, tipo='normal'):
    d = DadosMapa(cod_faz=10156, nome='POSSES', tipo=tipo, revisao=0, talhoes=t,
                  recorte=recortar(t, uniao_buffers({}, {})), gerado_em=datetime.date(2026, 9, 29))
    destino = tmp_path / 'mapa.pdf'
    return gerar_pdf(d, destino), destino.read_bytes()


def _medidas(pdf_bytes):
    m = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)', pdf_bytes)
    return float(m.group(1)), float(m.group(2))


def test_orientacao_pelo_formato():
    assert orientacao(_talhoes(3000, 1000)) == 'paisagem'
    assert orientacao(_talhoes(1000, 3000)) == 'retrato'


def test_safra():
    assert safra_de(datetime.date(2026, 9, 29)) == '26/27'
    assert safra_de(datetime.date(2027, 3, 31)) == '26/27'
    assert safra_de(datetime.date(2027, 4, 1)) == '27/28'


def test_pdf_paisagem_a4(tmp_path):
    orient, b = _pdf(tmp_path, _talhoes(3000, 1000))
    assert orient == 'paisagem' and b.startswith(b'%PDF')
    w, h = _medidas(b)
    assert round(w) == 842 and round(h) == 595


def test_pdf_retrato_a4_catacao(tmp_path):
    orient, b = _pdf(tmp_path, _talhoes(1000, 3000), tipo='catacao')
    assert orient == 'retrato'
    w, h = _medidas(b)
    assert round(w) == 595 and round(h) == 842


def test_pdf_com_muitos_talhoes_nao_quebra(tmp_path):
    t = gpd.GeoDataFrame({'TALHAO': list(range(1, 61)), 'AREA_PROD': [5.0] * 60},
                         geometry=[box(i * 100, 0, i * 100 + 100, 100) for i in range(60)], crs=31983)
    orient, b = _pdf(tmp_path, t)
    assert b.startswith(b'%PDF')
