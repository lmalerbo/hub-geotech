"""Critérios das sessões do Paralelismo. Duas formas de uso:
  sem argumentos: hook Stop (lê o JSON do stdin; bloqueia o fim da sessão enquanto algum critério falhar);
  com argumentos: uma checagem avulsa, usada nos critérios de sessoes.json."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(os.environ.get('ORQ_RAIZ', Path(__file__).resolve().parent.parent))
CONFIG = Path(os.environ.get('ORQ_CONFIG', RAIZ / 'orquestra' / 'sessoes.json'))
LIMITE_BLOQUEIOS = 6
SAIDA_MAX = 3000


def config():
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def criterios(sessao_id):
    c = config()
    sessao = next(s for s in c['sessoes'] if s['id'] == sessao_id)
    return [x.replace('{id}', sessao_id) for x in c['comum'] + sessao.get('criterios', [])]


def falhas(sessao_id):
    """[(comando, fim da saída)] dos critérios que falharam."""
    saida = []
    for cmd in criterios(sessao_id):
        r = subprocess.run(cmd, shell=True, cwd=RAIZ, capture_output=True, text=True, errors='replace',
                           env={**os.environ, 'ORQ_SESSAO': ''})
        if r.returncode:
            saida.append((cmd, (r.stdout + r.stderr)[-SAIDA_MAX:]))
    return saida


def bloqueio(sessao_id):
    return (RAIZ / 'orquestra' / 'relatorios' / f'{sessao_id}-bloqueio.md').exists()


def hook_stop():
    sessao_id = os.environ.get('ORQ_SESSAO')
    if not sessao_id or bloqueio(sessao_id):
        return 0
    contador = RAIZ / 'orquestra' / 'logs' / f'{sessao_id}-bloqueios.txt'
    contador.parent.mkdir(parents=True, exist_ok=True)
    n = int(contador.read_text()) if contador.exists() else 0
    if n >= LIMITE_BLOQUEIOS:
        return 0    # o orquestrador confere de novo e decide; aqui não pode virar laço sem fim
    achadas = falhas(sessao_id)
    if not achadas:
        return 0
    contador.write_text(str(n + 1))
    motivo = '\n\n'.join(f'FALHOU: {c}\n{s}' for c, s in achadas)
    print(json.dumps({'decision': 'block', 'reason':
                      f'A sessão {sessao_id} ainda não terminou. Corrija e continue. Se depender de uma decisão do '
                      f'usuário, escreva orquestra/relatorios/{sessao_id}-bloqueio.md e pare.\n\n{motivo}'}))
    return 0


def git(*args):
    return subprocess.run(['git', *args], cwd=RAIZ, capture_output=True, text=True, errors='replace').stdout


def main(args):
    if not args:
        return hook_stop()
    op, resto = args[0], args[1:]
    if op == '--sem-dados-reais':
        ruins = [f for f in git('ls-files').splitlines() if re.search(r'\.(jdl|fdl|fdd)$', f, re.I)]
        print('\n'.join(ruins))
        return 1 if ruins else 0
    if op == '--arvore-limpa':
        pendente = git('status', '--porcelain')
        print(pendente)
        return 1 if pendente.strip() else 0
    if op == '--relatorio':
        p = RAIZ / 'orquestra' / 'relatorios' / f'{resto[0]}.md'
        if not p.exists():
            print(f'Falta {p.name}')
            return 1
        t = p.read_text(encoding='utf-8')
        if 'Revisão de código: aprovada' not in t or 'Pendências:' not in t:
            print(f'{p.name} precisa das linhas "Revisão de código: aprovada" e "Pendências:"')
            return 1
        return 0
    if op == '--existe':
        faltam = [f for f in resto if not (RAIZ / f).exists()]
        print('Faltam: ' + ', '.join(faltam) if faltam else '')
        return 1 if faltam else 0
    if op == '--contem':
        arquivo, trecho = resto[0], ' '.join(resto[1:])
        p = RAIZ / arquivo
        ok = p.exists() and trecho in p.read_text(encoding='utf-8', errors='replace')
        print('' if ok else f'{arquivo} não contém "{trecho}"')
        return 0 if ok else 1
    print(f'Opção desconhecida: {op}')
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
