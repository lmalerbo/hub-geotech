# Esperas do Hub e movimento (sessão S3)

Levantamento de 23/10/2026 para a spec `docs/superpowers/specs/2026-10-23-fluxo-projetos-design.md` (D6). Biblioteca: `app/motion.js` + `app/motion.css`. Vitrine: `app/motion-demo.html`. Teste: `python tests/app/teste_movimento.py [pasta_capturas]`.

## API entregue (contrato + ampliações)

| Função | O que faz |
|---|---|
| `Mo.ocupado(botao, {texto}?)` → `fim(ok)` | trava a largura, troca o rótulo pelo "campo" (barrinhas nas cores dos módulos) e passa uma faixa de luz pelo botão; `fim` mostra ✓ verde ou ✕ vermelho com tremida e devolve uma Promise (~0,9 s / 1,2 s) quando o botão volta ao normal. `texto` e `fim(ok,{travado:true})` (fica desabilitado depois do ✓ até quem chamou liberar; `rpcAcao` libera quando os dados novos chegam) são ampliações. Aceita `null` (não faz nada). |
| `Mo.progresso(el, {total, mb})` → `{atualizar(bytes, texto?), processando(texto?), fim(ok, texto?)}` | barra com %, "x MB de y MB" e listras andando. Chegou em 100 % e o servidor ainda grava → "respira". `mb:false` usa o total como passos. `processando` é ampliação. |
| `Mo.carregando(c)` / `Mo.pronto(c)` | esboço de linhas com brilho por cima do conteúdo (que fica apagado); `pronto` tira o esboço e faz os primeiros 10 filhos entrarem em cascata curta. |
| `Mo.etapa(barra, de, para, {cor}?)` → Promise | etapas = filhos com `[data-etapa]` (ou filhos diretos); `de`/`para` = índice ou valor de `data-etapa`. Uma moldura desliza da etapa atual à nova e as do caminho pulsam. **A tela redesenha o estado final depois da Promise.** Cor: `{cor}` ou a variável CSS `--mo-etapa-cor` da etapa de destino. |
| `Mo.concluido(el, {texto})` → Promise | véu branco, selo verde que se desenha, onda e confete curto (18 peças) por 1,9 s; some sozinho. |
| `Mo.campo(grande?)` | HTML do indicador de espera, para quem montar estados vazios/carregando. |

Tudo usa só `transform`/`opacity` (continua animando mesmo com a página ocupada, ex.: o Python do PDF). Com `prefers-reduced-motion` ficam os estados parados: cores, ✓/✕, texto e % continuam; sem confete, sem moldura, sem cascata.

## Esperas encontradas

| Onde | Espera | Situação |
|---|---|---|
| `index.html` `abrirHub` (#carregando) | carga inicial de todos os dados | **feito** — campo grande + texto respirando |
| `index.html` `rpcAcao` | toda ação de Plantio/Preparo/Colheita com botão | **feito** — `Mo.ocupado`, ✓/✕ |
| `index.html` `confirmarEnvio` | envio de arquivos ao Worker | **feito** — `XMLHttpRequest` com progresso real somando todos os arquivos, "Gravando…" depois dos bytes, "Atualizando a etapa…" no RPC final; o ✓ fica na tela enquanto os dados já recarregam |
| `index.html` `entrar`, `definirSenha` | login, troca de senha | **feito** — `Mo.ocupado` |
| `index.html` `confirmarVoo` | pedido de voo da Colheita | **feito** — `Mo.ocupado` |
| `index.html` `rCfgFontes` | lista de importações (Configurações) | **feito** — `Mo.carregando`/`Mo.pronto` |
| `aplicacao.html` preparar gerador de PDF (~20 s na 1ª vez) | Pyodide + bibliotecas | **feito** — barra por passo (5 passos com nome; `crGerador.passo/passoTxt` em `corretivos-pdf.js`) |
| `aplicacao.html` `crBaixarPdf` | geração do PDF | **feito** — `Mo.ocupado(btn,{texto:'Gerando o PDF…'})`, ✓ antes de redesenhar |
| `index.html` `recarregar`/`carregarDados` depois de ação | releitura dos dados | **S4** (desempenho) — S4 pode usar `Mo.carregando` no painel da fazenda enquanto relê |
| `index.html` barra de etapa, retroceder/desfazer, nova revisão, chegada em Ok | fluxo de projetos | **S2** — chamar `Mo.etapa` ao retroceder/desfazer e `Mo.concluido(cartão, {texto:'Fazenda em Ok'})` quando a fazenda passa a ter todos os talhões em Ok (S2 conhece a regra; S3 não decide etapa) |
| `index.html` tela de Usuários (`carregarAcessos`, `salvarUsr`, redefinir/remover) | Edge Function `contas` | **pendente** — não tocado porque o worktree `usuarios-niveis` está mexendo nessa tela; ligar depois do merge dele (`Mo.ocupado` nos botões, `Mo.carregando('#usr-list')`) |
| `index.html` `salvarCfgGeral`, `salvarFerramentas`, `cancelarVoo`, `marcarTipoC` | RPCs sem botão passado | **pendente** — passar o botão (`this`) para `rpcAcao`/`Mo.ocupado` |
| `drone.js` | `drGerarNormal`, `drPublicar`, `drCancelar`… (sem botão), envio de shapes (`storage.upload`, sem progresso), "Gerando prévia…" (polling 5 s, texto parado) | **pendente** — fora do fluxo desta spec; sugestão: `Mo.ocupado(event.currentTarget)`, `Mo.progresso` por arquivo, campo no quadro "Gerando prévia" |
| `index.html` mapas MapLibre | carga de tiles/geometria | **pendente** — `Mo.carregando` no contêiner do mapa até o evento `load` |
| `portal.html` | lista de downloads (já tem "giro" próprio) | fora de escopo (spec: portal só compatibilidade) |
