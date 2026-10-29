"""Leitura das datas de campo do PLANAGRI (pelos nomes das colunas, nunca pela posição)."""
import datetime
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ingestao'))
import planagri  # noqa: E402


def test_le_conservacao_e_plantio_realizado(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Planagri'
    ws.append(['CÓDIGO', 'TALHÃO', 'PLAN.', 'PLAN.', 'MÊS PLANTIO (PLAN)', 'CONSERVAÇÃO (DATA)', 'REALIZADO PLANTIO (DATA)'])
    ws.append([10001, 1, 'REFORMA', 'LIB', datetime.datetime(2026, 11, 1), datetime.datetime(2025, 9, 15), None])
    ws.append([10001, 2, 'REFORMA', 'LIB', None, 'texto', datetime.datetime(2026, 10, 3)])
    caminho = tmp_path / 'p.xlsx'
    wb.save(caminho)
    talhoes, _ = planagri.ler(str(caminho), 'Planagri')
    assert talhoes[10001001]['conservacao_em'] == '2025-09-15'
    assert talhoes[10001001]['plantio_realizado_em'] is None
    assert talhoes[10001002]['conservacao_em'] is None            # texto não vira data
    assert talhoes[10001002]['plantio_realizado_em'] == '2026-10-03'
