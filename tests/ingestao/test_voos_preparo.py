"""Agente dos voos do Preparo: o que vai para o banco a partir da resposta do GeoMap."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ingestao'))
import voos_preparo  # noqa: E402


def test_fazenda_com_erro_fica_de_fora():
    r1 = {'id': 'a', 'section': '10080', 'landPlot': '4', 'controlStatus': 4}
    secoes, registros = voos_preparo.separar([
        {'section': '10080', 'registros': [r1]},
        {'section': '10314', 'erro': 'DroneManagement respondeu 500'},
        {'section': '10724', 'registros': []},
    ])
    assert secoes == [10080, 10724]          # 10314 não é apagada nem marcada como lida
    assert registros == [r1]


def test_lotes_de_50():
    assert [len(l) for l in voos_preparo.lotes(list(range(120)), 50)] == [50, 50, 20]


class HubFalso:
    def __init__(self):
        self.execucoes = {}

    def selecionar(self, tabela, colunas, filtro=None):
        if tabela == 'talhao_preparo':
            return [{'layer': 10080004}, {'layer': 10314001}]
        return [{'situacao': 'liberado'}, {'situacao': 'nao_solicitado'}]

    def inserir(self, tabela, valores):
        assert tabela == 'execucoes_ingestao'
        self.execucoes[1] = dict(valores)
        return {'id': 1}

    def atualizar(self, tabela, filtro, valores):
        assert (tabela, filtro) == ('execucoes_ingestao', {'id': 'eq.1'})
        self.execucoes[1].update(valores)

    def rpc(self, nome, args):
        pass


class Resposta:
    def __init__(self, ok, corpo):
        self.ok, self.status_code, self.text, self._corpo = ok, 200 if ok else 502, 'falhou', corpo

    def json(self):
        return self._corpo


def rodar(monkeypatch, resposta):
    hub = HubFalso()
    monkeypatch.setattr(voos_preparo, 'Hub', lambda: hub)
    monkeypatch.setattr(voos_preparo, 'carregar_env', lambda: {'GEOMAP_API_URL': 'http://x', 'HUB_INTEGRACAO_TOKEN': 't'})
    monkeypatch.setattr(voos_preparo.requests, 'post', lambda *a, **k: resposta)
    monkeypatch.setattr(sys, 'argv', ['voos_preparo.py'])
    return hub


def test_rodada_ok_fica_em_execucoes_ingestao(monkeypatch):
    r1 = {'id': 'a', 'section': '10080', 'landPlot': '4', 'controlStatus': 9}
    hub = rodar(monkeypatch, Resposta(True, {'resultados': [
        {'section': '10080', 'registros': [r1]}, {'section': '10314', 'erro': 'DroneManagement respondeu 500'}]}))
    voos_preparo.main()
    e = hub.execucoes[1]
    assert (e['fonte'], e['status'], e['linhas_lidas'], e['linhas_gravadas']) == ('voos_preparo', 'ok', 1, 1)
    assert e['detalhes'] == {'fazendas': 2, 'fazendas_com_erro': ['10314'],
                             'situacao': {'liberado': 1, 'nao_solicitado': 1}}


def test_falha_do_geomap_fica_como_erro(monkeypatch):
    import pytest
    hub = rodar(monkeypatch, Resposta(False, None))
    with pytest.raises(RuntimeError):
        voos_preparo.main()
    assert hub.execucoes[1]['status'] == 'erro' and 'HTTP 502' in hub.execucoes[1]['erro']
