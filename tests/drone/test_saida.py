import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import MultiPolygon, box

from drone.saida import CAMPO_AREA, CAMPO_TAXA, gravar_aplicacao, montar_zip


def _area():
    return MultiPolygon([box(200000, 7550000, 200100, 7550100), box(200300, 7550000, 200400, 7550050)])


def test_shape_de_aplicacao_no_padrao(tmp_path):
    shp = gravar_aplicacao(_area(), 10, tmp_path, 10156)
    assert shp.name == '10156.shp'
    g = gpd.read_file(shp)
    assert len(g) == 1
    assert g.crs.to_epsg() == 4326
    assert list(g.columns) == [CAMPO_TAXA, CAMPO_AREA, 'geometry']
    assert g.loc[0, CAMPO_TAXA] == 10
    assert g.loc[0, CAMPO_AREA] == pytest.approx(1.5)
    assert shp.with_suffix('.cpg').read_text().strip().upper() in ('UTF-8', 'UTF8')


def test_zip_so_com_as_partes_do_shape_na_raiz(tmp_path):
    shp = gravar_aplicacao(_area(), 10, tmp_path / 'x', 10156)
    (shp.parent / '10156.qmd').write_text('lixo')
    z = montar_zip(shp, tmp_path / 'saida.zip')
    with zipfile.ZipFile(z) as f:
        assert sorted(f.namelist()) == ['10156.cpg', '10156.dbf', '10156.prj', '10156.shp', '10156.shx']
