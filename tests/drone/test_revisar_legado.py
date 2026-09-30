import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import box

from drone.revisar_legado import (classificar, mesma_geometria, precisa_refazer, projetos_em_zips)


def _zip(pasta, nome_zip, nome_shp, geoms, campos):
    tmp = pasta / 'tmp'
    tmp.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame({k: [v] * len(geoms) for k, v in campos.items()}, geometry=geoms, crs=31983).to_file(tmp / nome_shp)
    destino = pasta / nome_zip
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, 'w') as z:
        for f in tmp.glob(nome_shp.replace('.shp', '.*')):
            z.write(f, f'Pasta interna/{f.name}')
    for f in tmp.iterdir():
        f.unlink()
    return destino


def test_acha_projeto_de_drone_dentro_de_zip(tmp_path):
    faz = tmp_path / '10008 SANTA EUGENIA'
    _zip(faz / '2024-2025' / '02 PROJETO' / '99 GERAL' / 'Rev6', 'proj.zip', '10008.shp',
         [box(0, 0, 100, 100)], {'taxa l/ha': 10, 'aplicavel': 1.0})
    _zip(faz / '2024-2025' / '02 PROJETO' / '99 GERAL' / 'Rev6', 'outro.zip', 'restricoes15m.shp',
         [box(0, 0, 10, 10)], {'id': 1})                                 # sem campos de aplicação
    _zip(faz / '2024-2025' / '02 PROJETO' / '99 GERAL' / 'Rev5', 'x (EXPERIMENTO).zip', '10008.shp',
         [box(0, 0, 10, 10)], {'taxa l/ha': 10, 'aplicavel': 1.0})      # experimento fica fora
    achados = projetos_em_zips(faz)
    assert len(achados) == 1
    p = achados[0]
    assert p['safra'] == '2024-2025' and p['revisao'] == 'Rev6'
    assert p['caminho'].startswith('zip://') and p['caminho'].endswith('!Pasta interna/10008.shp')
    assert gpd.read_file(p['caminho']).area.sum() == pytest.approx(10000)


def test_mesma_geometria_reconhece_copia():
    assert mesma_geometria(box(0, 0, 100, 100), box(0, 0, 100, 100.5))
    assert not mesma_geometria(box(0, 0, 100, 100), box(0, 0, 100, 120))


def test_classificar_normal_e_catacao():
    import geopandas as gpd
    talhoes = gpd.GeoDataFrame({'TALHAO': [1]}, geometry=[box(0, 0, 1000, 1000)], crs=31983)
    assert classificar(box(0, 0, 1000, 900), talhoes) == 'normal'
    manchas = box(10, 10, 30, 30).union(box(500, 500, 520, 520)).union(box(800, 100, 815, 115))
    assert classificar(manchas, talhoes) == 'catacao'


def test_precisa_refazer():
    # publicado = projeto mais novo sozinho; consolidação usou só ele → nada muda
    assert not precisa_refazer(usados={2}, publicado=2, publicado_existe=True)
    # consolidação juntou outros projetos → refaz
    assert precisa_refazer(usados={0, 2}, publicado=2, publicado_existe=True)
    # nada publicado ainda (fazenda nova ou carga que caiu) → publica
    assert precisa_refazer(usados={0}, publicado=0, publicado_existe=False)
