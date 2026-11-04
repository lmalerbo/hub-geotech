"""Campos lidos da Base Fazendas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ingestao'))

from base_fazendas import para_declividade


def test_declividade():
    assert para_declividade(7.5) == 7.5
    assert para_declividade('12,5') == 12.5
    assert para_declividade(0) == 0
    assert para_declividade(99) is None
    assert para_declividade('99') is None
    assert para_declividade(None) is None
    assert para_declividade('') is None
