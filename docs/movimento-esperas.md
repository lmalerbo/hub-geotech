# Esperas do Hub e movimento (sessão S3)

Levantamento de 23/10/2026 para a spec `docs/superpowers/specs/2026-10-23-fluxo-projetos-design.md` (D6), com a continuação do roteiro `docs/superpowers/plans/2026-10-23-drone-movimento-previa.md`. Biblioteca: `app/motion.js` + `app/motion.css`. Vitrine: `app/motion-demo.html`. Teste: `python tests/app/teste_movimento.py [pasta_capturas]`.

## API entregue (contrato + ampliações)

| Função | O que faz |
|---|---|
| `Mo.ocupado(botao, {texto}?)` → `fim(ok, {travado}?)` | trava a largura, troca o rótulo pelo "campo" (barrinhas nas cores dos módulos) e passa uma faixa de luz pelo botão; `fim` mostra ✓ verde ou ✕ vermelho com tremida e devolve uma Promise (~0,9 s / 1,2 s) quando o botão volta ao normal. `texto` e `travado` (fica desabilitado depois do ✓ até quem chamou liberar; `rpcAcao` libera quando os dados novos chegam) são ampliações. Aceita `null` (não faz nada). |
| `Mo.progresso(el, {total, mb})` → `{atualizar(bytes, texto?), processando(texto?), fim(ok, texto?)}` | barra com %, "x MB de y MB" e listras andando. Chegou em 100 % e o servidor ainda grava → "respira". `mb:false` usa o total como passos. `processando` é ampliação. |
| `Mo.carregando(c, {discreto}?)` / `Mo.pronto(c, {cascata}?)` | esboço de linhas com brilho por cima do conteúdo (que fica apagado); `pronto` tira o esboço e faz os primeiros 10 filhos entrarem em cascata curta. `discreto:true`: o conteúdo continua visível, só uma linha de luz no topo e o campo no canto (recargas curtas de painel). `cascata:false`: sem cascata (mapas, painéis redesenhados). |
| `Mo.etapa(barra, de, para, {cor}?)` → Promise | etapas = elementos com `[data-etapa]` (ou filhos diretos); `de`/`para` = índice ou valor de `data-etapa`. Uma moldura desliza da etapa atual à nova e as do caminho pulsam. Na barra de projetos o `data-etapa` fica no círculo (`.sdot`) de cada etapa. |
| `Mo.concluido(el, {texto})` → Promise | véu branco, selo verde que se desenha, onda e confete curto (18 peças) por 1,9 s; some sozinho. |
| `Mo.voo(el, {texto, desde}?)` → `{pousar(ok, texto?), parar()}` | **novo (Drone)**: um drone (visto de cima, hélices girando, sombra) faz três passadas sobre `el`, como faixas de aplicação, e volta ao início em laço de 12 s. `desde` = quando a espera começou: redesenhos (polling) continuam o voo de onde estava. `pousar(true)` leva o drone ao centro, desce e vira `Mo.concluido`; `pousar(false)` balança e mostra o erro. Serve para qualquer espera longa do Drone (ex.: S5 "montando a prévia": `Mo.voo(caixa, {texto:'Montando a prévia…', desde})`). |
| `Mo.campo(grande?)` | HTML do indicador de espera, para quem montar estados vazios/carregando. |

Tudo usa só `transform`/`opacity` (continua animando mesmo com a página ocupada, ex.: o Python do PDF). Com `prefers-reduced-motion` ficam os estados parados: cores, ✓/✕, texto e % continuam; sem confete, sem moldura, sem cascata, drone parado no centro.

## Esperas encontradas

| Onde | Espera | Situação |
|---|---|---|
| `index.html` `abrirHub` (#carregando) | carga inicial de todos os dados | **feito** — campo grande + texto respirando |
| `index.html` `rpcAcao` | toda ação com botão (Plantio/Preparo/Colheita) | **feito** — `Mo.ocupado`, ✓/✕, botão travado até os dados novos |
| `index.html` `confirmarEnvio` | envio de arquivos ao Worker | **feito** — progresso real (XMLHttpRequest) somando os arquivos, "Gravando…", "Atualizando a etapa…" |
| `index.html` `recarregar(alvo)` | recarga da fazenda depois de ação | **feito** — `Mo.carregando(painel,{discreto})` no `dpanel`/`dpanel-p`/`dpanel-c` até redesenhar (a lógica de recarga da S4 ficou em `recarregarFazenda`, sem mudança) |
| `index.html` `entrar`, `definirSenha`, `confirmarVoo` | login, troca de senha, pedido de voo | **feito** — `Mo.ocupado` |
| `index.html` `cancelarVoo`, `marcarTipoC` | Colheita | **feito** — o botão clicado vai para `rpcAcao` |
| `index.html` `salvarCfgGeral`, `salvarFerramentas` (`salvarParametro`) | Configurações | **feito** — `Mo.ocupado` no Salvar; `salvarParametro` não tem botão próprio, quem chama anima |
| `index.html` `rCfgFontes` | lista de importações | **feito** — `Mo.carregando`/`Mo.pronto` |
| `index.html` `sair` | encerrar a sessão | **feito** — o Hub apaga na hora (desbotado, leve desfoque), botão com campo, troca para o login quando a sessão fecha |
| `index.html` mapas MapLibre | — | **não se aplica** — o index não cria mapa MapLibre; o único é o do Drone (abaixo) |
| `projetos.js` retroceder / desfazer | barra de etapa | **feito** — `Mo.etapa` nos dois sentidos (o retroceder da S2 não animava porque a barra não tinha `data-etapa`; corrigido) |
| `projetos.js` chegada em Ok, envio da nova revisão, linha do tempo | — | **feito pela S2** com `Mo.concluido`, `Mo.progresso`, `Mo.carregando` |
| `drone.js` publicar (`drPublicar` + `drVooPublicacao`) | pedido + espera do agente publicar | **feito** — `Mo.ocupado` no Publicar; enquanto a publicação está pedida o drone sobrevoa o mapa da fazenda ("Publicando no portal…"); quando publica, pousa e vira ✓ "Publicado no portal"; se falhar, mostra "Falha ao publicar" |
| `drone.js` `drGerarNormal`, `drGerarCatacao`, `drAbrirCatacao`, `drDescartar`, `drCancelar`, nova solicitação | ações sem botão passado | **feito** — botão pego do evento do clique (`drBotao`) + `Mo.ocupado` |
| `drone.js` `drEnviar` | envio de shapes ao Storage | **feito** — progresso real por arquivo (XMLHttpRequest na API do Storage, sem sobrescrever, igual ao `upload`) + "Registrando o envio…" |
| `drone.js` fila, abrir fazenda, mapa | carga do painel e do MapLibre | **feito** — `Mo.carregando` na fila e na fazenda; no mapa até o `load` (só quando muda fazenda/documento, não a cada polling) |
| `drone.js` prévia (`drPrevHtml`, `drMostrarPdf`, quadro "Gerando prévia…") | — | **S5** — `Mo.voo` está disponível para o "montando a prévia" |
| `aplicacao.html` gerador de PDF (preparar ~20 s e gerar) | Pyodide + PDF | **feito** — barra por passo e botão vivo |
| `corretivos.js` aplicar aos marcados, editar/excluir aplicação, área, insumo | gravação do mapa (`crInserirTalhoesFaltantes`/`crLimparOrfaos` rodam dentro delas) | **feito** — `Mo.ocupado` nos botões ("Gravando…"), `Mo.carregando(painel,{discreto})` em `crRecarregar`, área e exclusão |
| `index.html` tela de Usuários (`carregarAcessos`, `salvarUsr`, redefinir/remover) | Edge Function `contas` | **depois da publicação da tela de Usuários** (roteiro) — `Mo.ocupado` nos botões, `Mo.carregando('#usr-list')` |
| `portal.html` | lista de downloads (tem "giro" próprio) | fora de escopo (spec: portal só compatibilidade) |
