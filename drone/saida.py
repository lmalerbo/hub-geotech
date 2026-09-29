"""Entrega para o piloto: shapefile de aplicação (WGS84, 1 feição) e .zip só com ele."""
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon

from drone.config import CRS_SAIDA, CRS_TRABALHO

CAMPO_TAXA = 'Taxa l/ha'
CAMPO_AREA = 'Área Apli'   # 10 bytes em UTF-8: cabe no limite do .dbf
PARTES = ('.shp', '.shx', '.dbf', '.prj', '.cpg')


def gravar_aplicacao(area: MultiPolygon, taxa: int, pasta: Path, cod_faz: int) -> Path:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame({CAMPO_TAXA: [int(taxa)], CAMPO_AREA: [round(area.area / 1e4, 2)]},
                           geometry=[area], crs=CRS_TRABALHO).to_crs(CRS_SAIDA)
    caminho = pasta / f'{cod_faz}.shp'
    gdf.to_file(caminho, driver='ESRI Shapefile', encoding='UTF-8', engine='pyogrio')
    if not caminho.with_suffix('.cpg').exists():
        caminho.with_suffix('.cpg').write_text('UTF-8')
    return caminho


def montar_zip(shp: Path, destino: Path) -> Path:
    shp, destino = Path(shp), Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as z:
        for ext in PARTES:
            z.write(shp.with_suffix(ext), shp.stem + ext)
    return destino
