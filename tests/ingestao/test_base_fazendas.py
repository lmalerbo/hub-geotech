"""Campos lidos da Base Fazendas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ingestao'))

import base_fazendas
from base_fazendas import para_declividade


def test_declividade():
    assert para_declividade(7.5) == 7.5
    assert para_declividade('12,5') == 12.5
    assert para_declividade(0) == 0
    assert para_declividade(99) is None
    assert para_declividade('99') is None
    assert para_declividade(None) is None
    assert para_declividade('') is None


def test_ler_grava_a_declividade(monkeypatch):
    linhas = [{'SECAO': '10233', 'TALHAO': 1, 'DESC_SECAO': 'TESTE', 'AREA_PROD': 10.0, 'DECLIVIDAD': 7},
              {'SECAO': '10233', 'TALHAO': 2, 'DESC_SECAO': 'TESTE', 'AREA_PROD': 10.0, 'DECLIVIDAD': 99}]
    monkeypatch.setattr(base_fazendas, 'DBF', lambda *a, **k: linhas)
    _, talhoes, *_ = base_fazendas.ler('x.dbf')
    assert [t['declividade'] for t in talhoes] == [7.0, None]
