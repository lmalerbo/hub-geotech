# Drone: movimento e janela de prévia — roteiro das sessões

Data: 23/10/2026. Base: branch `fluxo-integracao` (já tem `app/motion.js`/`motion.css` e o fluxo de projetos integrado).
Contexto do movimento: `docs/movimento-esperas.md` (API `Mo.*` e levantamento) e a spec `docs/superpowers/specs/2026-10-23-fluxo-projetos-design.md` (D6).
Regra do usuário: **nenhuma espera vazia**, animações vivas e satisfatórias, não spinners genéricos; respeitar `prefers-reduced-motion`.

## S3 (continuação) — Movimento: fechamento + Drone

Worktree: `hub-geotech-movimento`. Antes de começar: `git merge fluxo-integracao` na branch `fluxo-movimento` (pega o fluxo integrado).

### Drone (`app/drone.js`) — prioridade
O módulo com mais esperas. Ligar `Mo.*` e criar animações próprias do Drone na biblioteca:
1. **Publicar o mapa** (`drPublicar`): animação de **drone voando** — o drone cruza a fazenda/painel enquanto publica; ao concluir, pousa e vira ✓ (e `Mo.concluido` se fizer sentido). Deve funcionar enquanto a publicação aguarda o agente (estado "publicação pedida" até a resposta).
2. **Gerar projeto Normal** (`drGerarNormal`) e **cancelar** (`drCancelar`) e demais ações via `drRpc` sem botão: passar o botão e usar `Mo.ocupado`.
3. **Envio de shapes** (`drEnviar`, `storage.upload`): `Mo.progresso` por arquivo, com % real se o cliente permitir; senão, progresso por etapa.
4. **Recarga da fazenda** (`drRecarregarFazenda`) e **carga do mapa MapLibre**: `Mo.carregando` no contêiner até o `load`/dados chegarem.
5. **Não toque** em `drPrevHtml` nem `drMostrarPdf`, nem no quadro "Gerando prévia…": são da S5. A S5 vai usar `Mo.*`; se ela precisar de uma animação nova (ex.: "montando a prévia"), a S3 entrega a função na biblioteca e avisa.

### Fora do Drone (pendências do levantamento)
6. Desfazer retrocesso na tela de projetos (`app/projetos.js`, `pjDesfazer`): animar a barra com `Mo.etapa` como no retroceder.
7. Recarga da fazenda depois de ação (`recarregar` em `index.html`): `Mo.carregando`/`Mo.pronto` no painel da fazenda.
8. Botões que não passam o botão: `salvarCfgGeral`, `salvarFerramentas`, `cancelarVoo`, `marcarTipoC`, `salvarParametro` → passar `this` e usar `Mo.ocupado`.
9. Mapas MapLibre do index: `Mo.carregando` até o `load`.
10. Mapas de aplicação (`app/corretivos.js`): `crInserirTalhoesFaltantes`, `crLimparOrfaos` e o salvar do mapa.
11. `sair()`: estado de saída animado.
12. Atualizar a tabela de `docs/movimento-esperas.md` (tudo "feito" ou com motivo).

**Fica para depois da tela de Usuários publicada:** `carregarAcessos`, `salvarUsr`, redefinir/remover (`Mo.ocupado` + `Mo.carregando('#usr-list')`).

Verificação: `python tests/app/teste_movimento.py`, `node --test tests/app/*.test.js`, `motion-demo.html` com as animações novas (inclusive o drone voando).

## S5 (nova) — Drone: prévia de aprovação em janela

Worktree novo a partir de `fluxo-integracao` (branch `drone-previa-janela`).

Problema: a prévia hoje é um PDF num `<iframe>` dentro do painel lateral (`drMostrarPdf`, link assinado do bucket `drone-previas`); na prática o navegador baixa o arquivo e o usuário precisa abri-lo por fora.
Objetivo: a prévia abre **numa janela do próprio Hub** (modal grande), sem baixar nada:
- Renderizar o PDF dentro do Hub (ex.: pdf.js de cdnjs com versão fixa), independente de como o Storage serve o arquivo (content-type/download).
- Na janela: páginas com zoom, e as ações da prévia (aprovar/publicar, pedir ajuste, fechar) — as mesmas de hoje, só que dentro da janela.
- Botão secundário "Baixar PDF" para quem quiser o arquivo.
- Esperas da janela (baixar e renderizar o PDF, "Gerando prévia…" com polling) usam `Mo.*`; animação nova → pedir à S3.
- Dono de: `drPrevHtml`, `drMostrarPdf`, o quadro "Gerando prévia…", o modal novo. Não toca no resto de `drone.js` (é da S3).

Verificação: testes existentes do drone (`node --test tests/app/drone_puro.test.js`), e conferência visual com uma prévia real (o usuário roda `tests/app/teste_drone_tela.py` se gravar no banco).

## Junção
As duas branches voltam para `fluxo-integracao` pela coordenação (S3 primeiro, depois S5). Conflitos esperados só em `drone.js`, em funções separadas.
