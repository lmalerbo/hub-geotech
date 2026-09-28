"""Rodada diária do Hub: importa as fontes na ordem certa e aplica as regras.

Ordem: Base Fazendas primeiro (é ela que cria fazendas e talhões), depois as
fontes de demanda e de estado, e por último as regras — que dependem de todas
as fontes estarem atualizadas. Se uma importação falhar, as seguintes rodam
mesmo assim (cada uma fica registrada em hub.execucoes_ingestao), mas o
código de saída indica a falha pro agendador.

Uso:  python ingestao/rodar_diario.py
"""

import subprocess
import sys
import os

from comum import Hub

PASTA = os.path.dirname(os.path.abspath(__file__))
ETAPAS = ['base_fazendas.py', 'planagri.py', 'conservacao.py']


def main():
    # O console do Windows (e o Agendador de Tarefas) não usa UTF-8 por padrão
    # e quebra ao imprimir "→"/"⚠"/"º".
    sys.stdout.reconfigure(encoding='utf-8')
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONWARNINGS': 'ignore'}
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
