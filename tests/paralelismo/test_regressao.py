"""Regressão contra o resultado do base-op (spec §8). Rode com:
PARALELISMO_10233=<pasta 10233Rev0> PARALELISMO_10966=<pasta com as sessões GS3 da 10966Rev0> pytest -m dados_reais"""
import collections
import os
import re
from pathlib import Path

import pytest

from paralelismo.analise import analisar_fazenda, linhas_do_grupo, para_utm
from paralelismo.gs3 import ler_gs3, ler_sessao
from paralelismo.jdl import ler_jdl

pytestmark = pytest.mark.dados_reais
RE_SERIE = re.compile(rb'BM\d{4}[A-Z]\d{6}')
RE_DATA = re.compile(r'^(\d{4})_(\d{2})_(\d{2})_')


def _linhas(grupos):
    saida = []
    for frota, itens in grupos.items():
        pontos = [p for _, pts in itens for p in pts]
        data = collections.Counter(d for d, pts in itens for _ in pts).most_common(1)[0][0]
        saida += [{'frota': frota, 'data': data, 'coords': [list(c) for c in g.coords]}
                  for g in linhas_do_grupo(pontos)]
    return saida


def _pasta(var):
    p = os.environ.get(var)
    if not p or not Path(p).is_dir():
        pytest.skip(f'{var} não aponta para uma pasta')
    return Path(p)


def test_regressao_10233_jdl():
    grupos = collections.defaultdict(list)
    for jdl in sorted(_pasta('PARALELISMO_10233').rglob('*.jdl')):
        pontos, _ = ler_jdl(str(jdl))
        if not pontos:
            continue
        series = RE_SERIE.findall(jdl.read_bytes())
        frota = collections.Counter(series).most_common(1)[0][0].decode() if series else jdl.parent.name
        m = RE_DATA.match(jdl.name)
        grupos[frota].append((f'{m[1]}-{m[2]}-{m[3]}' if m else '', para_utm(pontos)))
    r = analisar_fazenda(_linhas(grupos), {})
    assert r['pll_total'] == 2506
    assert round(100 * r['pll_aderentes'] / r['pll_total'], 2) == 77.85


def test_regressao_10966_gs3():
    grupos = collections.defaultdict(list)
    vistos = set()
    pasta = _pasta('PARALELISMO_10966')
    for fdl in sorted(pasta.rglob('*.fdl')):
        if fdl.name in vistos:
            continue
        vistos.add(fdl.name)
        pontos, _ = ler_gs3(str(fdl))
        if pontos:
            grupos[fdl.relative_to(pasta).parts[0]].append((ler_sessao(str(fdl))['inicio'][:10], para_utm(pontos)))
    r = analisar_fazenda(_linhas(grupos), {})
    assert r['pll_total'] == 30395
    assert round(100 * r['pll_aderentes'] / r['pll_total'], 2) == 88.86
