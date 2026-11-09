"""Rodada diária: atualiza o código antes de rodar (o servidor rodou código velho de 29/10 a 09/11)."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ingestao'))
import rodar_diario  # noqa: E402


def fake_run(saidas, chamadas):
    def run(cmd, **k):
        chamadas.append(cmd)
        chave = ' '.join(cmd[:3])
        codigo, saida = saidas.get(chave, (0, ''))
        return subprocess.CompletedProcess(cmd, codigo, stdout=saida, stderr='')
    return run


def test_codigo_novo_roda_de_novo(monkeypatch):
    heads = iter(['aaa\n', 'bbb\n'])
    chamadas = []
    saidas = {'git pull --ff-only': (0, 'Fast-forward')}
    run = fake_run(saidas, chamadas)
    monkeypatch.setattr(rodar_diario.subprocess, 'run',
                        lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, stdout=next(heads), stderr='')
                        if cmd[:2] == ['git', 'rev-parse'] else run(cmd, **k))
    assert rodar_diario.atualizar_codigo() is True
    assert any(c[:3] == [sys.executable, '-m', 'pip'] for c in chamadas)


def test_sem_mudanca_segue(monkeypatch):
    monkeypatch.setattr(rodar_diario.subprocess, 'run',
                        lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, stdout='aaa\n', stderr=''))
    assert rodar_diario.atualizar_codigo() is False


def test_pull_falho_avisa_e_segue(monkeypatch, capsys):
    def run(cmd, **k):
        codigo = 1 if cmd[:2] == ['git', 'pull'] else 0
        return subprocess.CompletedProcess(cmd, codigo, stdout='aaa\n', stderr='sem rede')
    monkeypatch.setattr(rodar_diario.subprocess, 'run', run)
    assert rodar_diario.atualizar_codigo() is False
    assert 'git pull falhou' in capsys.readouterr().out
