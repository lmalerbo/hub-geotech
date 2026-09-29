"""Regras de recorte do projeto de aplicação (spec, seção 3). Tudo em EPSG:31983."""
import math
from dataclasses import dataclass, field

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import make_valid

from drone.erros import ErroGeracao

AREA_MINIMA_M2 = 1.0   # restos de recorte menores que 1 m² são descartados


def so_poligonos(geom: BaseGeometry) -> MultiPolygon:
    if geom is None or geom.is_empty:
        return MultiPolygon()
    if isinstance(geom, Polygon):
        partes = [geom]
    elif isinstance(geom, MultiPolygon):
        partes = list(geom.geoms)
    else:
        partes = [p for g in getattr(geom, 'geoms', []) for p in so_poligonos(g).geoms]
    return MultiPolygon([p for p in partes if p.area >= AREA_MINIMA_M2])


def uniao_buffers(obstaculos: dict, distancias: dict) -> BaseGeometry:
    partes = [make_valid(g).buffer(distancias[classe])
              for classe, geoms in obstaculos.items() for g in geoms if not g.is_empty]
    return unary_union(partes) if partes else Polygon()


@dataclass
class Recorte:
    area: MultiPolygon
    por_talhao: list = field(default_factory=list)
    area_total_ha: float = 0.0
    aplicacao_ha: float = 0.0
    talhoes_sem_area_prod: list = field(default_factory=list)


def recortar(talhoes: gpd.GeoDataFrame, buffers: BaseGeometry,
             infestacao: list | None = None, margem: float = 0.0) -> Recorte:
    geoms = [make_valid(g) for g in talhoes.geometry]
    uniao = unary_union(geoms)
    if infestacao is None:
        base = uniao
    else:
        mancha = unary_union([make_valid(g) for g in infestacao if not g.is_empty])
        base = mancha.buffer(margem).intersection(uniao)
    area = so_poligonos(make_valid(base.difference(buffers)))
    if area.is_empty:
        raise ErroGeracao('A área de aplicação ficou vazia: confira a infestação e os obstáculos desta fazenda.')

    por_talhao, sem_area = [], []
    for (_, t), g in sorted(zip(talhoes.iterrows(), geoms), key=lambda x: int(x[0][1]['TALHAO'])):
        area_prod = t['AREA_PROD']
        if area_prod is None or (isinstance(area_prod, float) and math.isnan(area_prod)):
            sem_area.append(int(t['TALHAO']))
            area_prod = 0.0
        por_talhao.append({'talhao': int(t['TALHAO']), 'area_prod': float(area_prod),
                           'aplicavel_ha': g.intersection(area).area / 1e4})
    return Recorte(area=area, por_talhao=por_talhao,
                   area_total_ha=sum(t['area_prod'] for t in por_talhao),
                   aplicacao_ha=area.area / 1e4, talhoes_sem_area_prod=sem_area)
