"""Regressão: o PDF do Drone tem de continuar idêntico depois da extração do layout para mapas/."""
import datetime
import os
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from drone.geometria import recortar, uniao_buffers
from drone.mapa_pdf import DadosMapa, gerar_pdf

pymupdf = pytest.importorskip('pymupdf')
REF = Path(__file__).parent / 'referencia'
DIA = datetime.date(2026, 10, 15)


def _talhoes(n, largura=800, altura=500):
    geoms = [box(i * 120, 0, i * 120 + 100, 100) for i in range(n)] if n > 2 else \
            [box(0, 0, largura / 2, altura), box(largura / 2, 0, largura, altura)]
    return gpd.GeoDataFrame({'TALHAO': list(range(1, len(geoms) + 1)),
                             'AREA_PROD': [10.0 + i for i in range(len(geoms))]}, geometry=geoms, crs=31983)


CASOS = {
    'drone_paisagem': lambda: DadosMapa(10156, 'FAZENDA TESTE', 'normal', 2, _talhoes(2),
                                        recortar(_talhoes(2), uniao_buffers({}, {})), DIA),
    'drone_retrato_catacao': lambda: DadosMapa(10372, 'FAZENDA RETRATO', 'catacao', 0, _talhoes(2, 300, 900),
                                               recortar(_talhoes(2, 300, 900), uniao_buffers({}, {})), DIA),
    'drone_muitos': lambda: DadosMapa(10008, 'FAZENDA GRANDE', 'normal', 1, _talhoes(60),
                                      recortar(_talhoes(60), uniao_buffers({}, {})), DIA),
}


@pytest.mark.parametrize('nome', CASOS)
def test_pdf_drone_igual_a_referencia(nome, tmp_path):
    destino = tmp_path / f'{nome}.pdf'
    gerar_pdf(CASOS[nome](), str(destino))
    doc = pymupdf.open(destino)
    paginas = [f'{nome}.png'] if len(doc) == 1 else [f'{nome}_p{i + 1}.png' for i in range(len(doc))]
    for pagina, arquivo in zip(doc, paginas):
        png = pagina.get_pixmap(dpi=80).tobytes('png')
        if os.environ.get('GERAR_REFERENCIA'):
            REF.mkdir(exist_ok=True)
            (REF / arquivo).write_bytes(png)
        else:
            assert (REF / arquivo).read_bytes() == png, f'{arquivo} mudou'
