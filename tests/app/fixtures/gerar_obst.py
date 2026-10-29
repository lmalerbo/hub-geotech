"""Gera os shapes de exemplo da janela de obstáculos (teste de tela, S5.6). Coordenadas fictícias,
longe de qualquer fazenda. Rodar de novo só se mudar o conjunto: python tests/app/fixtures/gerar_obst.py"""
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Point, box

PASTA = Path(__file__).parent / 'obst'


def grava(nome, geom, pasta=PASTA, sem=()):
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f'{nome}.shp'
    gpd.GeoDataFrame({'id': [1]}, geometry=[geom], crs='EPSG:4326').to_file(caminho, encoding='utf-8')
    for ext in sem:
        caminho.with_suffix('.' + ext).unlink()
    return sorted(pasta.glob(f'{nome}.*'))


def zipa(nome_zip, arquivos, prefixo):
    with zipfile.ZipFile(PASTA / nome_zip, 'w') as z:
        for a in arquivos:
            z.write(a, prefixo + a.name)
            a.unlink()


if __name__ == '__main__':
    for velho in PASTA.glob('*'):
        velho.unlink()
    grava('restricoes15m', Point(-10.001, -10.001))
    grava('linhas_cemig', LineString([(-10.0, -10.0), (-10.002, -10.001)]))
    grava('sem_shx_50m', box(-10.003, -10.003, -10.002, -10.002), sem=('shx',))
    tmp = PASTA / '_tmp'
    zipa('obst.zip', grava('app_mata_50m', box(-10.005, -10.005, -10.004, -10.004), pasta=tmp), 'pasta/')
    zipa('outro.zip', grava('linhas_cemig', LineString([(-10.01, -10.01), (-10.012, -10.011)]), pasta=tmp), '')
    tmp.rmdir()
    print('\n'.join(sorted(p.name for p in PASTA.glob('*'))))
