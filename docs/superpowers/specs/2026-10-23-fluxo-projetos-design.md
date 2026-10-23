# Fluxo de projetos (Plantio e Preparo) + movimento no Hub — design

Data: 23/10/2026. Decisões tomadas com o usuário nesta data.

## Problemas de hoje

1. "Nova revisão" do Plantio pede só exportação (.zip) e projeto (.dwg); o mapa (.pdf) não pode ir junto.
2. As ações sempre valem para a fazenda inteira; fazenda grande é feita em partes e não dá pra avançar só alguns talhões.
3. Retroceder não tem volta nem justificativa. A revisão não muda a etapa: a fazenda fica "Ok" com uma Rev1 sem mapa, e o usuário retrocede para Ag. Mapa só para subir o mapa — confuso e contraditório.
4. Plantio e Preparo fazem o mesmo trabalho de formas diferentes (Plantio: etapa por talhão; Preparo: etapa por fazenda, "Reabrir", revisão documento a documento).
5. Toda ação dá sensação de travamento: o botão só fica meio apagado, `recarregar()` (app/index.html, `rpcAcao`) relê todos os módulos e redesenha tudo, e o envio de arquivos não mostra progresso.

## Decisões

### D1. Um mecanismo para Plantio e Preparo
Os dois módulos usam a mesma barra de etapa, a mesma tela de nova revisão, a mesma seleção de talhões e a mesma linha do tempo. Cada um mantém suas etapas e seus arquivos.
- **Preparo passa a guardar a etapa por talhão** (como o Plantio), porque também é avançado em partes. Migra os dados atuais: cada talhão herda a etapa da sua fazenda.

### D2. Avanço por talhão
Toda ação de avançar vale para os talhões marcados (padrão: todos os que estão na etapa certa). A seleção é feita na tabela de talhões (e no mapa, onde houver). A fazenda mostra a **distribuição** dos talhões por etapa, não só a etapa do mais atrasado.

### D3. Revisão acumulativa, numerada por fazenda
- **Um número de revisão por projeto (fazenda/módulo)**: Rev0, Rev1, Rev2… Cada revisão diz **quais arquivos mudaram**; arquivo que não mudou continua valendo da revisão anterior. (Hoje cada documento tem numeração própria — acaba.)
- O arquivo é um só da fazenda inteira e cada revisão contém tudo que já foi feito (Rev0 = talhões 1–5; Rev1 = 1–10).
- Cada revisão registra **quais talhões traz de novo ou altera**. Só esses andam de etapa:
  - talhões novos → seguem o fluxo normal (ex.: Andamento → Ag. Mapa → Ok);
  - talhões já prontos que foram alterados → voltam para Ag. Mapa até o mapa novo;
  - talhões não marcados → não mudam (continuam Ok mesmo enquanto o mapa novo não chega).
- **Revisão só de exportação**: nenhum talhão marcado → nenhuma etapa muda.
- **Mapa opcional na nova revisão**: se o mapa for anexado junto, os talhões marcados vão direto para Ok.
- Motivo obrigatório a partir da Rev1 (como hoje).

### D4. Barra de etapa: só volta, com justificativa e desfazer
- A barra desliza só para trás (avançar continua sendo pelas ações, que exigem os arquivos). Movimento animado.
- Toda volta pede justificativa, gravada no registro.
- "Desfazer" devolve cada talhão à etapa exata em que estava. Vale só para o **último retrocesso da fazenda** e só enquanto nada mais mudou nela depois (envio, avanço, outra volta). O desfazer também fica registrado.

### D5. Linha do tempo da fazenda
Um histórico único: mudanças de etapa (com justificativa), revisões (motivo, arquivos, talhões), desfazer, quem e quando.

### D6. Nenhum milissegundo de espera vazio
Sessão própria de movimento, com animações **vivas e satisfatórias** — não spinners genéricos. Toda espera do Hub ganha animação: clique em ação, carregamento de lista/mapa, envio de arquivo (progresso real em %/MB), geração de PDF, e uma **animação de conclusão** quando um projeto/fazenda chega em Ok. Referência de criação: [open-motion](https://github.com/Yuan-ManX/open-motion) (motor de animação por conversa, exporta HTML/CSS/JSON); o que entra no Hub é CSS/JS puro, sem build, respeitando `prefers-reduced-motion`.

### D7. Atualizar só o que mudou
Depois de uma ação, recarregar só a fazenda afetada (não todos os módulos) e refletir a mudança na tela na hora.

## Contrato entre as partes

As sessões trabalham em paralelo contra este contrato. Mudar o contrato = combinar na sessão de coordenação.

### Banco (schema `hub`) — RPCs novas
Todas `security definer`, checam `hub.pode_editar(p_modulo)`, gravam em `log_auditoria`. `p_modulo` ∈ `'plantio' | 'preparo'`.

| RPC | O que faz | Devolve |
|---|---|---|
| `projeto_avancar(p_modulo, p_cod_faz, p_acao text, p_talhoes int[] default null)` | ação de avanço do módulo (ex.: `mapeamento_concluido`, `iniciar`, `exportacao_enviada`, `identificacao`, `escoamento`…) só nos talhões dados (null = todos elegíveis); mantém as exigências de arquivo | qtd de talhões |
| `projeto_retroceder(p_modulo, p_cod_faz, p_para text, p_justificativa text, p_talhoes int[] default null)` | volta talhões que estão depois de `p_para`; justificativa obrigatória | `lote_id` |
| `projeto_desfazer(p_lote_id bigint)` | desfaz o lote, se ainda for o último evento da fazenda; senão erro claro | qtd de talhões |
| `projeto_nova_revisao(p_modulo, p_cod_faz, p_motivo text, p_documentos text[], p_talhoes int[])` | abre a próxima revisão da fazenda com os documentos que mudam e os talhões que traz/altera; aplica D3 nas etapas | `revisao_id, numero, sufixo` (para o envio) |
| `projeto_linha_do_tempo(p_modulo, p_cod_faz)` | eventos da D5, mais novo primeiro | tabela `(em, tipo, quem, texto, detalhe jsonb)` |

Registro: `log_auditoria` ganha `justificativa text` e `lote_id bigint` (uma ação = um lote; o desfazer usa o lote).
Revisões: `projeto_revisoes` passa a ter numeração por projeto; nova tabela `revisao_talhoes (revisao_id, layer, tipo 'novo'|'alterado')`. A view `arquivos_vigentes` continua devolvendo, por documento, o arquivo da revisão mais recente que o contém — **o portal de downloads e a Colheita não podem quebrar** (a Colheita fica fora desta mudança).
Envio pelo Worker (`registrar_arquivo`) continua igual; o mapa anexado numa revisão dispara a regra "Ag. Mapa → Ok" só nos talhões daquela revisão.

### Movimento (`app/motion.js` + `app/motion.css`)
API mínima que as telas chamam (a sessão de movimento pode ampliar, não mudar):
- `Mo.ocupado(botao)` → devolve `fim(ok:boolean)`; anima o botão enquanto espera e mostra sucesso/erro ao terminar.
- `Mo.progresso(el, {total})` → `{atualizar(bytes), fim(ok)}` para envio de arquivos.
- `Mo.carregando(container)` / `Mo.pronto(container)` → esboço animado de lista/painel.
- `Mo.etapa(barraEl, de, para)` → anima a barra de etapa.
- `Mo.concluido(el, {texto})` → animação de conclusão (fazenda/projeto em Ok).
Até a sessão de movimento entregar, as telas usam um `motion.js` provisório com essas funções vazias.

## Fora de escopo
Colheita (fluxo próprio), Drone (já tem revisão por talhão), mudanças no portal de downloads além de manter compatibilidade.

## Riscos
- **Dados reais**: migração de Preparo e da numeração de revisões mexe em dados em uso. Testes salvam e restauram, nunca apagam.
- **Numeração divergente (levantado em 23/10/2026)**: 113 projetos de Plantio/Preparo têm revisão; **19 fazendas** têm números diferentes entre documentos (6 Plantio, ex. 10095 exportação Rev2 × projeto Rev1; 13 Preparo, ex. 10819 escoamento 1 / exportação 3 / projeto 3 / sistematização 2). O número está no nome dos arquivos já publicados (`..._Rev1.zip`), então **o histórico não é renumerado**: as revisões antigas ficam como estão, e a numeração única vale daqui pra frente — a próxima revisão da fazenda é `maior número entre todos os documentos + 1` (10095 → Rev3). A linha do tempo mostra as antigas com o documento ao lado do número.
- `app/index.html` é um arquivo único grande: código novo de projetos vai para `app/projetos.js` (como `drone.js`), e o index só chama.

## Plano de sessões paralelas

Cada sessão: worktree próprio, lê **só esta spec** + o trecho de código indicado (via graphify), delega o operacional (skill `delegar`), revisa e roda os testes. Merge sempre pela sessão de coordenação.

**Onda 1 — começam juntas**

| # | Sessão | Dono de | Não toca |
|---|---|---|---|
| S1 | **Banco** | migrations novas, RPCs do contrato, migração Preparo→talhão e numeração única, testes em `tests/` | `app/` |
| S2 | **Tela de projetos** | `app/projetos.js` (barra deslizante, seleção de talhões, distribuição por etapa, modal de nova revisão com arquivos opcionais, linha do tempo), ganchos nas seções Plantio/Preparo do index | `motion.*`, `rpcAcao`, `recarregar`, `carregarDados` |
| S3 | **Movimento** | levantamento de todas as esperas do Hub, `app/motion.js`/`motion.css`, animação de conclusão, progresso real no envio (`confirmarEnvio`), `rpcAcao` usando `Mo.ocupado` | regras de etapa, banco |
| S4 | **Desempenho** | `recarregar`/`carregarDados` por fazenda, atualização imediata na tela | visual, banco |

S2 começa pela parte visual contra o contrato (RPCs simuladas) e liga no banco quando S1 for integrada.

**Onda 2 — integração (coordenação)**: merge S1 → S4 → S3 → S2, teste de ponta a ponta no banco real (Plantio e Preparo: avanço parcial, revisão complementar, revisão só de exportação, retroceder + desfazer), runbook de publicação.
