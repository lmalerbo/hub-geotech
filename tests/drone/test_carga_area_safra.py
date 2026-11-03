"""Carga única de área e safra dos projetos de drone do legado (spec D4)."""
import io
import zipfile

import geopandas as gpd
from shapely.geometry import box

from drone.carga_area_safra import area_do_zip, safra_do_motivo


def zip_com(tmp_path, campo, valores):
    gdf = gpd.GeoDataFrame({campo: valores}, geometry=[box(i, 0, i + 1, 1) for i in range(len(valores))], crs=4326)
    gdf.to_file(tmp_path / 'ap.shp', encoding='utf-8')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for ext in ('shp', 'shx', 'dbf', 'prj', 'cpg'):
            if (tmp_path / f'ap.{ext}').exists():
                z.write(tmp_path / f'ap.{ext}', f'ap.{ext}')
    return buf.getvalue()


def test_soma_area_apli(tmp_path):
    assert area_do_zip(zip_com(tmp_path, 'Área Apli', [10.5, 2.25])) == 12.75


def test_campo_area_qualquer_caixa(tmp_path):
    assert area_do_zip(zip_com(tmp_path, 'AREA_HA', [3.0])) == 3.0


def test_sem_campo_de_area(tmp_path):
    assert area_do_zip(zip_com(tmp_path, 'TALHAO', [1])) is None


def test_safra_do_motivo():
    assert safra_do_motivo('Importado do legado: .../2025-2026/Rev2') == '25/26'
    assert safra_do_motivo('Importado do legado: 24/25 Rev1 e 25/26 Rev3') == '25/26'
    assert safra_do_motivo('Importado do legado') is None
    assert safra_do_motivo(None) is None
