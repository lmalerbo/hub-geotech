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
