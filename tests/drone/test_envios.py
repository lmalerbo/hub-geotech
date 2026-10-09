import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from drone.envios import processar_envio, shapefiles
from drone.erros import ErroGeracao


def _shp(pasta, nome, geoms, crs=31983):
    pasta.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame({'id': range(len(geoms))}, geometry=geoms, crs=crs).to_file(pasta / nome)
    return pasta / nome


def test_acha_shp_dentro_de_zip_com_pastas(tmp_path):
    src = _shp(tmp_path / 'src', 'restricoes15m.shp', [Point(200000, 7550000)])
    z = tmp_path / 'envio.zip'
    with zipfile.ZipFile(z, 'w') as f:
        for p in src.parent.iterdir():
            f.write(p, f'pasta/sub/{p.name}')
    achados = shapefiles([z], tmp_path / 'x')
    assert [p.name for p in achados] == ['restricoes15m.shp']


class _Banco:
    def __init__(self, pasta_origem):
        self.origem, self.gravados = pasta_origem, []

    def baixar_envio(self, caminho, local):
        import shutil
        local.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.origem / caminho.split('/')[-1], local)
        return local

    def gravar_obstaculos(self, cod, classe, origem, arquivo, geoms, usuario=None):
        self.gravados.append(('obst', cod, classe, len(geoms)))

    def gravar_obstaculos_lote(self, cod, origem, itens, usuario=None, envio_id=None):
        for i in itens:
            self.gravados.append(('obst', cod, i['classe_m'], len(i['wkts'])))

    def gravar_infestacao(self, sol, empresa, arquivo, geoms, usuario=None, envio_id=None):
        self.gravados.append(('inf', sol, len(geoms)))

    def gravar_ajuste(self, envio_id, geoms):
        self.gravados.append(('aj', envio_id, len(geoms)))


def _envio(tmp_path, tipo, nomes, classe=None, sol=None):
    return {'id': 5, 'cod_faz': 10156, 'tipo': tipo, 'classe_m': classe, 'solicitacao_id': sol,
            'arquivos': [f'10156/1/{n}' for n in nomes], 'enviado_por': None}


def _partes(p):
    return [p.with_suffix(e).name for e in ('.shp', '.shx', '.dbf', '.prj', '.cpg') if p.with_suffix(e).exists()]


def test_obstaculos_classe_pelo_nome_e_junta_arquivos_da_mesma_classe(tmp_path):
    o = tmp_path / 'o'
    a = _shp(o, 'arvores15m.shp', [Point(200000, 7550000)])
    b = _shp(o, 'restricoes15m.shp', [Point(200010, 7550000), Point(200020, 7550000)])
    banco = _Banco(o)
    processar_envio(_envio(tmp_path, 'obstaculos', _partes(a) + _partes(b)), banco, tmp_path / 'w')
    assert banco.gravados == [('obst', 10156, 15, 3)]


def test_obstaculo_sem_classe_no_nome_pede_para_escolher(tmp_path):
    o = tmp_path / 'o'
    a = _shp(o, 'arvores.shp', [Point(200000, 7550000)])
    with pytest.raises(ErroGeracao, match='escolha a classe'):
        processar_envio(_envio(tmp_path, 'obstaculos', _partes(a)), _Banco(o), tmp_path / 'w')


def test_infestacao_e_ajuste(tmp_path):
    o = tmp_path / 'o'
    a = _shp(o, 'mamona.shp', [box(200000, 7550000, 200010, 7550010)])
    b = _shp(o, 'ajuste.shp', [box(200000, 7550000, 200100, 7550100)])
    banco = _Banco(o)
    processar_envio(_envio(tmp_path, 'infestacao', _partes(a), sol=3), banco, tmp_path / 'w1')
    processar_envio(_envio(tmp_path, 'ajuste', _partes(b)), banco, tmp_path / 'w2')
    assert banco.gravados == [('inf', 3, 1), ('aj', 5, 1)]


def test_envio_sem_shp_da_erro(tmp_path):
    o = tmp_path / 'o'
    o.mkdir()
    (o / 'leia.txt').write_text('x')
    with pytest.raises(ErroGeracao, match=r'\.shp'):
        processar_envio(_envio(tmp_path, 'ajuste', ['leia.txt']), _Banco(o), tmp_path / 'w')


def test_ignora_lixo_de_zip_feito_no_mac(tmp_path):
    src = _shp(tmp_path / 'src', 'restricoes25m.shp', [Point(200000, 7550000)])
    z = tmp_path / 'envio.zip'
    with zipfile.ZipFile(z, 'w') as f:
        for p in src.parent.iterdir():
            f.write(p, f'pasta/{p.name}')
            f.writestr(f'__MACOSX/pasta/._{p.name}', b'lixo')
    assert [p.name for p in shapefiles([z], tmp_path / 'x')] == ['restricoes25m.shp']


class _BancoLote(_Banco):
    def gravar_obstaculos_lote(self, cod, origem, itens, usuario=None, envio_id=None):
        self.gravados.append(('lote', cod, envio_id, sorted((i['classe_m'], len(i['wkts'])) for i in itens)))


def test_obstaculos_de_varias_classes_gravam_numa_chamada_so(tmp_path):
    o = tmp_path / 'o'
    a = _shp(o, 'restricoes15m.shp', [Point(200000, 7550000)])
    b = _shp(o, 'restricoes50m.shp', [Point(200010, 7550000), Point(200020, 7550000)])
    banco = _BancoLote(o)
    processar_envio(_envio(tmp_path, 'obstaculos', _partes(a) + _partes(b)), banco, tmp_path / 'w')
    assert banco.gravados == [('lote', 10156, 5, [(15, 1), (50, 2)])]
