import datetime
import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from drone.erros import ErroGeracao
from drone.gerador import processar


@pytest.fixture
def base(tmp_path):
    gdf = gpd.GeoDataFrame({'SECAO': [10156, 10156], 'TALHAO': [1.0, 2.0], 'AREA_PROD': [1.0, 1.0]},
                           geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)], crs=31983)
    caminho = tmp_path / 'Talhoes_da_Pedra_01_10_2026_fme.shp'
    gdf.to_file(caminho)
    return datetime.date(2026, 10, 1), caminho


class BancoFalso:
    def __init__(self, tipo='normal', obstaculos=None, infestacao=None):
        self.tipo, self.obst, self.infest, self.previas = tipo, obstaculos or {}, infestacao, []

    def parametros(self):
        return {'taxa_l_ha': '10', 'agrupar_infestacao_m': '20', 'folga_infestacao_m': '5', 'alerta_aproveitamento_min': '0.30',
                'alerta_obstaculos_meses': '24'}

    def distancias(self):
        return {15: 15.0, 25: 25.0, 50: 50.0}

    def solicitacao(self, id_):
        return {'id': id_, 'cod_faz': 10156, 'tipo': self.tipo}

    def fazenda(self, cod):
        return {'cod_faz': cod, 'nome': 'POSSES'}

    def obstaculos_vigentes(self, cod):
        versoes = [{'classe_m': c, 'versao_id': c, 'enviado_em': '2023-01-01T00:00:00+00:00'} for c in self.obst]
        return self.obst, versoes

    def infestacao(self, id_):
        return self.infest

    def proximo_numero(self, cod_faz, documento):
        return 2

    def subir_previa(self, caminho, destino):
        self.previas.append((caminho.name, destino))
        return destino


def test_normal_gera_zip_pdf_e_resumo(base, tmp_path):
    b = BancoFalso(obstaculos={15: [Point(50, 50)]})
    r = processar({'id': 3, 'solicitacao_id': 9, 'infestacao_id': None}, b, base, tmp_path / 'w',
                  datetime.date(2026, 10, 2))
    assert r['status'] == 'pronta' and r['orientacao'] == 'paisagem'
    assert r['resumo']['area_total_ha'] == pytest.approx(2.0)
    assert r['insumos']['base_talhoes'] == 'Talhoes_da_Pedra_01_10_2026_fme.shp'
    assert r['insumos']['revisao_prevista'] == 2
    assert r['previa_zip'] == 'geracao-3/10156.zip' and r['previa_pdf'] == 'geracao-3/10156.pdf'
    with zipfile.ZipFile(tmp_path / 'w' / 'geracao-3' / '10156.zip') as z:
        assert '10156.shp' in z.namelist()
    # obstáculos com mais de 24 meses e classes sem versão aparecem como alerta
    assert any('meses' in a for a in r['alertas'])
    assert any('25 m' in a for a in r['alertas'])


def test_catacao_sem_infestacao_da_erro(base, tmp_path):
    with pytest.raises(ErroGeracao, match='infestação'):
        processar({'id': 4, 'solicitacao_id': 9, 'infestacao_id': None}, BancoFalso('catacao'), base,
                  tmp_path / 'w', datetime.date(2026, 10, 2))


def test_catacao_toda_fora_dos_talhoes_da_erro(base, tmp_path):
    b = BancoFalso('catacao', infestacao=[box(5000, 5000, 5010, 5010)])
    with pytest.raises(ErroGeracao, match='vazia'):
        processar({'id': 5, 'solicitacao_id': 9, 'infestacao_id': 1}, b, base, tmp_path / 'w',
                  datetime.date(2026, 10, 2))


def test_catacao_parcialmente_fora_gera_alerta(base, tmp_path):
    b = BancoFalso('catacao', infestacao=[box(40, 40, 60, 60), box(5000, 5000, 5010, 5010)])
    r = processar({'id': 6, 'solicitacao_id': 9, 'infestacao_id': 1}, b, base, tmp_path / 'w',
                  datetime.date(2026, 10, 2))
    assert any('fora dos talhões' in a for a in r['alertas'])
