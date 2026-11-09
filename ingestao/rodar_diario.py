"""Rodada diária do Hub: importa as fontes na ordem certa e aplica as regras.

Ordem: Base Fazendas primeiro (é ela que cria fazendas e talhões), depois as
fontes de demanda e de estado, e por último as regras — que dependem de todas
as fontes estarem atualizadas. Se uma importação falhar, as seguintes rodam
mesmo assim (cada uma fica registrada em hub.execucoes_ingestao), mas o
código de saída indica a falha pro agendador.

Antes de tudo, atualiza o código (git pull --ff-only) e as dependências: de 29/10 a
09/11 o servidor Geo rodou código velho e a leitura dos voos do Preparo não rodava.
Se o código mudou, roda de novo a versão nova. Pull ou pip com falha só avisam.

Uso:  python ingestao/rodar_diario.py
"""

import subprocess
import sys
import os

PASTA = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(PASTA)
ETAPAS = ['base_fazendas.py', 'talhao_geom.py', 'planagri.py', 'conservacao.py', 'icol.py', 'voos_preparo.py']


def _rodar(cmd):
    return subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True,
                          env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})


def atualizar_codigo():
    """git pull + pip install. Devolve True se o código mudou."""
    antes = _rodar(['git', 'rev-parse', 'HEAD']).stdout.strip()
    r = _rodar(['git', 'pull', '--ff-only'])
    if r.returncode != 0:
        print(f'⚠ git pull falhou, rodando com o código atual: {(r.stderr or r.stdout).strip()[:300]}')
    depois = _rodar(['git', 'rev-parse', 'HEAD']).stdout.strip()
    print(f'código: {depois[:7]}' + (f' (era {antes[:7]})' if antes != depois else ''))
    r = _rodar([sys.executable, '-m', 'pip', 'install', '-q', '-r', os.path.join(PASTA, 'requirements.txt')])
    if r.returncode != 0:
        print(f'⚠ pip install falhou: {(r.stderr or r.stdout).strip()[-300:]}')
    return antes != depois


def main():
    # O console do Windows (e o Agendador de Tarefas) não usa UTF-8 por padrão
    # e quebra ao imprimir "→"/"⚠"/"º".
    sys.stdout.reconfigure(encoding='utf-8')
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONWARNINGS': 'ignore'}
    if not os.environ.get('HUB_RODADA_ATUALIZADA'):
        print('=== atualização do código ===', flush=True)
        novo = atualizar_codigo()
        sys.stdout.flush()
        if novo:
            print('código novo: rodando a versão atualizada', flush=True)
            sys.exit(subprocess.run([sys.executable, os.path.abspath(__file__)],
                                    env={**env, 'HUB_RODADA_ATUALIZADA': '1'}).returncode)
    falhas = []
    for script in ETAPAS:
        print(f'\n=== {script} ===', flush=True)
        if subprocess.run([sys.executable, os.path.join(PASTA, script)], env=env).returncode != 0:
            falhas.append(script)

    print('\n=== regras ===')
    hub = Hub()
    restaurados = hub.rpc('restaurar_status_guardado')
    if restaurados:
        print(f'{restaurados} talhões do sistema antigo entraram na Base Fazendas e tiveram o status restaurado')
    r = hub.rpc('aplicar_regra_conservacao')[0]
    print(f"Conservação → Plantio: {r['mapeamento_liberado']} mapeamentos liberados, "
          f"{r['projeto_recalculado']} projetos recalculados")

    if falhas:
        print(f'\n⚠ Falharam: {", ".join(falhas)}')
        sys.exit(1)


if __name__ == '__main__':
    main()
