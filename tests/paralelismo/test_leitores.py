from pathlib import Path

import pytest

from paralelismo.gs3 import ler_gs3
from paralelismo.jdl import ler_jdl

# As amostras têm GPS real e o repositório é público: ficam fora do git (ver LEIAME.md).
pytestmark = pytest.mark.dados_reais
DADOS = Path(__file__).resolve().parent.parent / 'dados' / 'paralelismo'
N_JDL, TICKS_JDL = 10682, 23663   # do LEIAME.md
N_GS3, REG_GS3 = 366, 366         # do LEIAME.md


def test_jdl_igual_ao_base_op():
    pontos, ticks = ler_jdl(str(DADOS / 'amostra.jdl'))
    assert (len(pontos), ticks) == (N_JDL, TICKS_JDL)
    lat, lon = pontos[0]
    assert -25 < lat < -19 and -52 < lon < -44


def test_gs3_igual_ao_base_op():
    pontos, registros = ler_gs3(str(DADOS / 'amostra.fdl'))
    assert (len(pontos), registros) == (N_GS3, REG_GS3)


def test_jdl_truncado_nao_quebra(tmp_path):
    dados = (DADOS / 'amostra.jdl').read_bytes()
    corte = tmp_path / 'cortado.jdl'
    corte.write_bytes(dados[: len(dados) // 2 + 7])
    pontos, ticks = ler_jdl(str(corte))
    assert 0 < len(pontos) <= N_JDL and ticks <= TICKS_JDL


def test_gs3_fdd_truncado_nao_quebra(tmp_path):
    (tmp_path / 's.fdl').write_bytes((DADOS / 'amostra.fdl').read_bytes())
    fdd = (DADOS / 'amostra.fdd').read_bytes()
    (tmp_path / 's.fdd').write_bytes(fdd[: len(fdd) // 2 + 3])
    pontos, registros = ler_gs3(str(tmp_path / 's.fdl'))
    assert len(pontos) <= N_GS3 and registros <= REG_GS3


def test_gs3_sem_fdd_e_jdl_inexistente(tmp_path):
    (tmp_path / 'so.fdl').write_bytes((DADOS / 'amostra.fdl').read_bytes())
    assert ler_gs3(str(tmp_path / 'so.fdl')) == ([], 0)
    assert ler_jdl(str(tmp_path / 'nao_existe.jdl')) == ([], 0)
