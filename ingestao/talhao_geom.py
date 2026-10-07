"""Grava a geometria de cada talhão da Base de Talhões em hub.talhao_geom (mapa do Hub, cobertura).

Lê o .shp do dia (o mesmo da Base Fazendas), simplifica 0,5 m em SIRGAS/UTM 23S e grava em WGS84.
Talhões que saíram da Base são apagados da tabela (o projeto de drone não é tocado).
Uso:  python ingestao/talhao_geom.py [--simular]
"""
import argparse
import os
import sys

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely import wkt as shapely_wkt
from shapely.ops import unary_union
from shapely.validation import make_valid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comum import Execucao, Hub, agora_iso, carregar_config  # noqa: E402
from drone.base_talhoes import arquivo_mais_recente  # noqa: E402
from drone.geometria import so_poligonos  # noqa: E402

LOTE = 200


def linhas(gdf) -> list:
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf['cod'] = pd.to_numeric(gdf['SECAO'], errors='coerce')
    gdf['tal'] = pd.to_numeric(gdf['TALHAO'], errors='coerce')
    gdf = gdf[gdf['cod'].between(10000, 99999) & gdf['tal'].between(0, 999)]
    out = []
    for (cod, tal), g in gdf.groupby(['cod', 'tal']):
        geom = so_poligonos(make_valid(make_valid(unary_union(list(g.geometry))).simplify(0.5)))
        if geom.is_empty:
            continue
        em_graus = gpd.GeoSeries([geom], crs=31983).to_crs(4326).iloc[0]
        out.append({'cod_faz': int(cod), 'talhao_num': int(tal),
                    'geom': 'SRID=4326;' + shapely_wkt.dumps(em_graus, rounding_precision=7),
                    'area_ha': round(geom.area / 1e4, 4)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true')
    args = ap.parse_args()
    cfg = carregar_config()['drone']
    _, caminho = arquivo_mais_recente(cfg['base_talhoes_pasta'], cfg['base_talhoes_padrao'])
    gdf = pyogrio.read_dataframe(caminho, columns=['SECAO', 'TALHAO']).to_crs(31983)
    dados = linhas(gdf)
    print(f'{caminho.name}: {len(dados)} talhões com geometria')
    if args.simular:
        print('Simulação: nada foi gravado.')
        return
    hub = Hub()
    with Execucao(hub, 'talhao_geom') as execucao:
        inicio = agora_iso()
        for i in range(0, len(dados), LOTE):
            hub.upsert('talhao_geom', [{**d, 'atualizado_em': inicio} for d in dados[i:i + LOTE]],
                       'cod_faz,talhao_num')
        apagados = hub.rpc('talhao_geom_limpar', {'p_antes': inicio})
        execucao.linhas_lidas = len(gdf)
        execucao.linhas_gravadas = len(dados)
    print(f'Gravado no Hub ({apagados} talhões que saíram da Base foram retirados).')


if __name__ == '__main__':
    main()
