"""Postgres local com as migrações do fluxo + Colheita (avisos, safra) + datas de campo do Preparo.
Mesmos fixtures de tests/fluxo (pg, fazenda, pessoa, como)."""
import pytest

from tests.fluxo import conftest as fluxo
from tests.fluxo.conftest import pg, fazenda, pessoa, como  # noqa: F401  (fixtures reaproveitados)

MIGRACOES = sorted(fluxo.MIGRACOES + ['20261003090000_modulo_colheita.sql',
                                      '20261028090000_preparo_datas_campo.sql'])


@pytest.fixture(scope='session')
def banco(pg):
    fluxo.MIGRACOES, antigas = MIGRACOES, fluxo.MIGRACOES
    try:
        con = fluxo.montar(pg, 'preparo_ciclo')
    finally:
        fluxo.MIGRACOES = antigas
    yield con
    con.close()
