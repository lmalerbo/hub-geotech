"""Postgres local com o fluxo de projetos + stub do Drone + drone_projetos_v."""
import pytest

from tests.fluxo import conftest as fluxo
from tests.fluxo.conftest import pg, fazenda, pessoa, como  # noqa: F401

MIGRACOES = fluxo.MIGRACOES + ['../../tests/apresentacao/stub_drone.sql', '20261029110000_drone_projetos_v.sql']


@pytest.fixture(scope='session')
def banco(pg):
    fluxo.MIGRACOES, antigas = MIGRACOES, fluxo.MIGRACOES
    try:
        con = fluxo.montar(pg, 'apresentacao')
    finally:
        fluxo.MIGRACOES = antigas
    yield con
    con.close()
