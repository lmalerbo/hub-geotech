"""Dispara as sessões do Paralelismo, uma por vez, até acabar ou depender do usuário.
Cada sessão é um `claude -p` novo; o hook Stop (verifica.py) não a deixa terminar com critério falhando, e este
laço confere tudo de novo por conta própria. O estado fica em estado.json: dá para parar e rodar de novo.

Saídas: 0 = tudo pronto; 3 = portão do usuário; 4 = sessão bloqueada; 5 = sessão falhou depois das tentativas."""
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import verifica

RAIZ = verifica.RAIZ
PASTA = RAIZ / 'orquestra'
ESTADO = Path(os.environ.get('ORQ_ESTADO', PASTA / 'estado.json'))
LOGS = PASTA / 'logs'
TENTATIVAS = 3
ESPERA_LIMITE_S = 30 * 60
MAX_ESPERAS_LIMITE = 16
TEMPO_MAX_S = 6 * 60 * 60

# Reforço por padrão; a trava real do push é o hook pre-push, ver pre_push.sh.
PROIBIDOS = ['Bash(git push*)', 'Bash(git merge*)', 'Bash(git checkout main*)', 'Bash(git switch main*)',
             'Bash(gh auth*)', 'Bash(gh release*)', 'Bash(gh repo*)', 'Bash(*wrangler*)', 'Bash(supabase*)',
             'PowerShell(git push*)', 'PowerShell(gh *)', 'PowerShell(*wrangler*)']

REGRAS = """Você é uma sessão autônoma do módulo Paralelismo, sem ninguém para responder. Trabalhe em {raiz}, no branch atual.

Tarefa ({id}, {titulo}): {pedido}

Como trabalhar:
1. Leia em docs/superpowers/plans/2026-10-29-paralelismo.md as "Restrições globais", as "Decisões de execução", o "Foco da revisão" e a seção {etapa}; leia a spec e orquestra/relatorios/ só no que precisar. A nota do plano sobre mostrar o detalhamento ao usuário não vale aqui: o usuário delegou. Escolha o padrão sensato e registre no relatório.
2. Detalhe sua parte com a skill writing-plans em docs/superpowers/plans/2026-10-29-paralelismo-{id}.md e execute com test-driven-development. Commit por tarefa, com "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" no fim da mensagem.
3. Rode a revisão de código com a skill requesting-code-review, corrija o que for crítico ou importante, e rode verification-before-completion.
4. Escreva orquestra/relatorios/{id}.md em português, com o que foi feito, e as linhas exatas "Revisão de código: aprovada" (só se for verdade) e "Pendências:" (seguida do que falta ou "nenhuma"). Commite.

Limites que não têm exceção:
- Não envie nada ao GitHub, não mescle na main, não publique o Worker, não crie release. Migrations ficam só como arquivo.
- Não grave no banco real nem rode testes com o marcador banco. Teste em Postgres local (tests/paralelismo/conftest.py) e no modo demonstração.
- Dado real (pen-drives, Base Fazendas, Paralelismo8.xlsx, tests/dados/paralelismo/amostra.*) nunca vai para o executor externo nem para o git, porque o repositório é público. Não use a camada 1 da skill delegar em nada que toque neles.
- Não mexa nas configurações do Claude nem em orquestra/ além dos relatórios.
- Se depender de decisão do usuário ou de algo só ele faz, escreva orquestra/relatorios/{id}-bloqueio.md com a pergunta exata e pare. Não invente resultado.
"""


def ler_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding='utf-8'))
    return {'feitas': [], 'portoes_liberados': [], 'sessao_uuid': {}}


def gravar_estado(e):
    ESTADO.write_text(json.dumps(e, indent=2, ensure_ascii=False), encoding='utf-8')


def registro(msg):
    LOGS.mkdir(parents=True, exist_ok=True)
    linha = f'{time.strftime("%d/%m %H:%M")} {msg}'
    print(linha, flush=True)
    with open(LOGS / 'orquestra.log', 'a', encoding='utf-8') as f:
        f.write(linha + '\n')


def rodar(sessao, pedido, retomar, id_sessao):
    ajustes = PASTA / 'hook_settings.json'
    cmd = ['claude', '-p', '--model', sessao['modelo'], '--permission-mode', 'auto', '--settings', str(ajustes),
           '--disallowedTools', *PROIBIDOS]
    cmd += ['--resume', id_sessao] if retomar else ['--session-id', id_sessao]
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / f'{sessao["id"]}.log', 'a', encoding='utf-8') as log:
        log.write(f'\n=== {time.strftime("%d/%m %H:%M")} retomar={retomar}\n')
        log.flush()
        try:
            r = subprocess.run(cmd, cwd=RAIZ, input=pedido, text=True, encoding='utf-8', errors='replace',
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=TEMPO_MAX_S,
                               env={**os.environ, 'ORQ_SESSAO': sessao['id'], 'ORQ_RAIZ': str(RAIZ),
                                    'ORQ_CONFIG': str(verifica.CONFIG)})
        except subprocess.TimeoutExpired:
            log.write('TEMPO ESGOTADO\n')
            return 1, 'tempo esgotado'
        log.write(r.stdout or '')
    return r.returncode, r.stdout or ''


def executar(sessao, estado):
    sid = sessao['id']
    id_sessao = estado['sessao_uuid'].setdefault(sid, str(uuid.uuid4()))
    gravar_estado(estado)
    pedido = REGRAS.format(raiz=RAIZ, **{k: sessao[k] for k in ('id', 'titulo', 'pedido', 'etapa')})
    retomar, tentativa, esperas = (RAIZ / 'orquestra' / 'logs' / f'{sid}.log').exists(), 0, 0
    if retomar:
        pedido = f'Continue a tarefa {sid} de onde parou. Lembrete das regras:\n\n{pedido}'
    while tentativa < TENTATIVAS:
        registro(f'{sid}: {"retomando" if retomar else "iniciando"} ({sessao["titulo"]})')
        codigo, saida = rodar(sessao, pedido, retomar, id_sessao)
        if codigo and 'limit' in saida[-2000:].lower() and esperas < MAX_ESPERAS_LIMITE:
            esperas += 1
            registro(f'{sid}: limite de uso; aguardando {ESPERA_LIMITE_S // 60} min ({esperas}/{MAX_ESPERAS_LIMITE})')
            time.sleep(ESPERA_LIMITE_S)
            retomar = True
            continue
        if verifica.bloqueio(sid):
            return 'bloqueada'
        achadas = verifica.falhas(sid)
        if not achadas:
            return 'feita'
        tentativa += 1
        registro(f'{sid}: {len(achadas)} critério(s) falhando; tentativa {tentativa}/{TENTATIVAS}')
        retomar = True
        pedido = 'Estes critérios ainda falham. Corrija e termine a tarefa:\n\n' + '\n\n'.join(
            f'FALHOU: {c}\n{s}' for c, s in achadas)
    return 'falhou'


def main():
    c = verifica.config()
    estado = ler_estado()
    for sessao in c['sessoes']:
        sid = sessao['id']
        if sid in estado['feitas']:
            continue
        portao = sessao.get('portao')
        if portao and portao not in estado['portoes_liberados']:
            registro(f'PORTÃO {portao} antes de {sid}: {c["portoes"][portao]}')
            return 3
        resultado = executar(sessao, estado)
        if resultado == 'feita':
            estado['feitas'].append(sid)
            gravar_estado(estado)
            registro(f'{sid}: concluída')
        elif resultado == 'bloqueada':
            registro(f'{sid}: BLOQUEADA; ver orquestra/relatorios/{sid}-bloqueio.md')
            return 4
        else:
            registro(f'{sid}: FALHOU depois de {TENTATIVAS} tentativas; ver orquestra/logs/{sid}.log')
            return 5
    registro('TODAS AS SESSÕES CONCLUÍDAS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
