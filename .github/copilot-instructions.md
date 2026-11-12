# Instruções do projeto hub-geotech

Responda em português.

## Fluxo de trabalho
- Specs ficam em `docs/superpowers/specs/` e planos em `docs/superpowers/plans/`. Cada plano é dividido em etapas (S0…S6, P0…P6), uma sessão por etapa.
- Ao executar uma etapa, leia só a spec e o plano dela, mais o trecho de código indicado. Se o plano ainda não estiver em passos, detalhe a seção em passos no mesmo formato dos planos existentes e mostre antes de executar.
- Siga TDD: teste que falha, implementação, teste que passa.
- Marque as caixas `- [ ]` do plano conforme avança.
- Etapas com branch própria usam worktree em `../hub-geotech-<etapa>`.
- Antes de dar uma etapa por concluída, rode os testes e confira o diff.

## Testes
- JavaScript: `node --test tests/app/*.test.js`
- Python: `pytest tests/drone -q` (configuração em `pytest.ini`)
- Testes de tela do app: `tests/app/teste_drone_tela.py`

## Ambiente
- Windows com PowerShell 5.1: não use `&&`, encadeie com `;`.
- Não mude o agente Python do Drone (`drone/`) quando o plano disser que ele não muda.

## Commits
- Termine a mensagem com `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.