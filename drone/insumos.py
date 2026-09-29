"""Leitura de shapefiles enviados (obstáculos, infestação) e classe pelo nome do arquivo."""
import re
import unicodedata
from pathlib import Path

import geopandas as gpd
from shapely import force_2d
from shapely.validation import make_valid

from drone.config import CRS_TRABALHO
from drone.erros import ErroGeracao

CLASSES = (15, 25, 50)


def ler_shapefile(caminho: Path) -> list:
    caminho = Path(caminho)
    if not caminho.with_suffix('.prj').exists():
        raise ErroGeracao(f'O arquivo {caminho.name} veio sem o .prj (sistema de coordenadas).')
    gdf = gpd.read_file(caminho)
    if gdf.crs is None:
        raise ErroGeracao(f'O arquivo {caminho.name} tem um sistema de coordenadas desconhecido.')
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].to_crs(CRS_TRABALHO)
    return [make_valid(force_2d(g)) for g in gdf.geometry]   # PolygonZ (QGIS/GPS/DJI) → 2D, como o banco


def classe_pelo_nome(nome: str) -> int | None:
    s = unicodedata.normalize('NFD', Path(nome).stem).encode('ascii', 'ignore').decode().lower()
    m = re.search(r'(\d+)\s*m(?![a-z])', s) or re.search(r'(\d+)$', s)
    if not m:
        return None
    valor = int(m.group(1))
    return valor if valor in CLASSES else None
