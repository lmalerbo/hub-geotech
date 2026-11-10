# Inventário de pontos de HTML dinâmico (SEG4)

Plano `2026-11-10-seg4-innerhtml`, tarefa 1. Levantamento de 10/11/2026, sem alterar código. Fonte: `grep -n -E "innerHTML|outerHTML|insertAdjacentHTML" app/*.js app/*.html`, no branch `pipeline/2026-11-10-seg4-innerhtml`.

## Função de escape do projeto

- `esc(s)` em `app/index.html:2553` escapa `& < > " '`. É global: `drone-*.js`, `projetos.js` e `usuarios.js` (carregados por `index.html`) a usam direto. `pjH` (`projetos.js:9`) converte para string e chama `esc`.
- `crEsc` em `app/corretivos.js:268` e `apEsc` em `app/apresentacao-slides.js:25` fazem o mesmo em cada ferramenta. `esc` e `escJs` em `app/portal.html:355-356` valem só no portal (`escJs` escapa JS e depois HTML, para uso dentro de `onclick`).
- Os demos (`drone-*-demo.html`, `projetos-demo.html`) têm cópias próprias de `esc`.
- `esc` é escape de texto/atributo HTML. Dentro de `onclick="…"` ela não protege o contexto JavaScript; por isso os pontos com dado interpolado em `onclick`/`oninput` ficam como `handler inline`.

## Critério das situações

- `ok`: só código fixo, números calculados, valores com escape, leitura ou comentário. Em vários pontos `ok`, números e ids do banco (`cod_faz`, `a.id`, números de talhão) entram sem `esc`; isso só é seguro enquanto a coluna for numérica. Veja "Ressalvas".
- `falta esc`: texto do banco, de arquivo enviado ou do usuário interpolado sem `esc`.
- `handler inline`: o HTML tem `on*=` com dado interpolado (mesmo numérico). Quando também falta escape, aparecem as duas situações.
- `atribui vazio`: `innerHTML = ''`.

Nenhuma das ocorrências é leitura (`x = el.innerHTML`) nem comentário: todas são escritas.

## Tabela

| arquivo:linha | o que monta | de onde vêm os dados interpolados | situação |
|---|---|---|---|
| `app/apresentacao.js:438` | Lista de fontes de dados do slide (nome, detalhe, tempo) | código fixo; detalhe/erro passam por `apEsc` | ok |
| `app/apresentacao.js:471` | Lista lateral de slides | nomes fixos, `apEsc` | ok |
| `app/apresentacao.js:496` | Esvazia a prévia | — | atribui vazio |
| `app/apresentacao.js:497` | Mensagem "Carregando" via `apVazio` | código fixo; `apVazio` aplica `apEsc` | ok |
| `app/apresentacao.js:499` | Mensagem "Aguardando a API" via `apVazio` | código fixo | ok |
| `app/apresentacao.js:503` | Mensagem de falha + botão via `apVazio` | código fixo (botão é HTML fixo) | ok |
| `app/apresentacao.js:509` | Mensagem "Pendente" via `apVazio` | código fixo | ok |
| `app/apresentacao.js:514` | Slide inteiro (`apSlide`) dentro de `.apt-escala` | números calculados e rótulos fixos; subtítulo/destaque/rodapé do usuário passam por `apEsc` (apresentacao-slides.js:388,412-413); nomes de etapa vêm de agregação com chaves fixas | ok |
| `app/apresentacao.js:517` | Mensagem de erro via `apVazio(…, e.message)` | `e.message` passa por `apEsc` | ok |
| `app/apresentacao.js:542` | Lista de projetos de drone sem dado (`<li>`) | banco (cod_faz, documento, revisao_id), todos com `apEsc` | ok |
| `app/apresentacao.js:652` | Slide renderizado fora da tela para exportar PPTX (`apSlide`) | mesmo caso da linha 514 | ok |
| `app/corretivos.js:372` | Modal de confirmação (título, texto, botões) | parâmetros do código, todos com `crEsc` | ok |
| `app/corretivos.js:376` | Fecha o modal (esvazia) | — | atribui vazio |
| `app/corretivos.js:442` | Esqueleto de carregamento | código fixo | ok |
| `app/corretivos.js:446` | Mensagem de erro + botão | código fixo | ok |
| `app/corretivos.js:458` | Mensagem "Digite o código…" | código fixo | ok |
| `app/corretivos.js:460` | Lista de fazendas encontradas | banco: `cod_faz` (número, sem esc) e `nome` com `crEsc` | ok |
| `app/corretivos.js:467` | Esvazia resultados | — | atribui vazio |
| `app/corretivos.js:489` | Chips de mapas abertos recentemente | localStorage/banco; tudo com `crEsc` | ok |
| `app/corretivos.js:507` | Esqueleto de carregamento | código fixo | ok |
| `app/corretivos.js:516` | Mensagem de erro | código fixo | ok |
| `app/corretivos.js:527` | Estado vazio + botão | código fixo | ok |
| `app/corretivos.js:531` | Tabela de mapas (`crLinhaMapa`) | banco: `crEsc` em operação, O.S., alterado_por_nome; `m.id`/`m.talhoes` são números sem esc; datas formatadas | ok |
| `app/corretivos.js:579` | Fecha o modal (esvazia) | — | atribui vazio |
| `app/corretivos.js:582` | Modal "Novo mapa" | nome da fazenda (banco) com `crEsc`; resto fixo | ok |
| `app/corretivos.js:883` | Dica do talhão ao passar o mouse | `crEsc` em título e linhas; `d.acao` é texto fixo (corretivos.js:181) | ok |
| `app/corretivos.js:907` | Esqueleto do mapa | código fixo | ok |
| `app/corretivos.js:908` | Esqueleto do painel | código fixo | ok |
| `app/corretivos.js:918` | Esvazia o mapa | — | atribui vazio |
| `app/corretivos.js:919` | Mensagem de erro | código fixo | ok |
| `app/corretivos.js:923` | Esvazia o mapa | — | atribui vazio |
| `app/corretivos.js:1101` | Fecha o modal (esvazia) | — | atribui vazio |
| `app/corretivos.js:1102` | Modal "Editar aplicação" | banco: `crEsc` em rótulo e O.S.; `a.dose`, `a.dose_gesso` e números de talhão entram sem esc (valores numéricos) | ok |
| `app/corretivos.js:1186` | Itens do menu de ações | rótulos do código com `crEsc`; ícone fixo | ok |
| `app/corretivos.js:1354` | Barra de seleção vazia | código fixo | ok |
| `app/corretivos.js:1360` | Barra de seleção com talhões marcados | números de talhão e área (calculados), sem esc | ok |
| `app/corretivos.js:1376` | Painel do mapa (seções, cards de aplicação, totais) | banco: `crEsc` em rótulos, O.S., títulos de totais; talhões, `a.id` e áreas são números sem esc | ok |
| `app/corretivos.js:1403` | Botão PDF desabilitado (demo) | código fixo | ok |
| `app/corretivos.js:1408` | Mensagem de erro do gerador + botão | código fixo | ok |
| `app/corretivos.js:1411` | Botão "Baixar PDF" | código fixo | ok |
| `app/corretivos.js:1415` | Texto de preparo do PDF | código fixo | ok |
| `app/corretivos.js:1454` | Fecha o modal (esvazia) | — | atribui vazio |
| `app/corretivos.js:1478` | Modal de insumos (tabela + formulário) | banco: nome, unidade, código e valores do formulário com `crEsc`; ids com `Number()` | ok |
| `app/corretivos.js:1579` | Esqueleto da tela de trabalho (mapa, painel) | código fixo | ok |
| `app/drone-fazenda.js:47` | Mensagem de erro da fazenda | `e.message` com `esc` (global de index.html) | ok |
| `app/drone-fazenda.js:75` | Cabeçalho da fazenda (`drCabecalhoHtml`), troca via outerHTML | nome da fazenda com `esc`; `DR.cod` (código), contagens e área calculados; `onclick` só com constantes de código | ok |
| `app/drone-fazenda.js:89` | Cabeçalho + esqueleto do painel de fazenda | mesmo cabeçalho da linha 75; resto fixo | ok |
| `app/drone-fazenda.js:308` | Trilho de etapas (`drEtapasHtml`) ou vazio | nomes de etapa fixos; contexto com `esc` | ok |
| `app/drone-fazenda.js:318` | Menu ⋯ (Revisões, Cancelar, Encerrar) | `onclick="drCancelar(${sol.id})"` com id numérico do banco; resto fixo | handler inline |
| `app/drone-fazenda.js:343` | Gaveta de revisões | banco: número da revisão; data e motivo com `esc`; nome do documento fixo | ok |
| `app/drone-fazenda.js:394` | Barra de ferramentas (`drFerramentasHtml`) ou vazio | código fixo; estados booleanos | ok |
| `app/drone-fazenda.js:398` | Dica do mapa (`drDicaHtml`) | código fixo | ok |
| `app/drone-fazenda.js:404` | Botão Camadas + caixa de checkbox | rótulo fixo; booleanos | ok |
| `app/drone-fazenda.js:408` | Legenda do mapa (`drLegendaHtml`) | cores e textos fixos; número da revisão (banco, numérico) | ok |
| `app/drone-fazenda.js:550` | Cabeçalho do painel lateral | `p.sobre`/`p.titulo` com `esc` | ok |
| `app/drone-fazenda.js:552` | Corpo do painel lateral (`drPainel_*().corpo`) | `esc` em situação, erros e camadas; talhões (números do geo/shape) entram sem esc em `drLinhaResumo` e na lista de talhões do shape; `onclick="drFonteTalhao(${n},…)"` e `drManterTalhao(${t})` com número de talhão | handler inline |
| `app/drone-fazenda.js:554` | Rodapé do painel (`p.rodape`) | `onclick="drDescartar(${ger.id})"` e `drPublicar(${ger.id})` com id numérico do banco | handler inline |
| `app/drone-fazenda.js:555` | Esvazia o rodapé; insere `<div id="dr-err">` fixo no painel | código fixo | atribui vazio |
| `app/drone-inicio.js:102` | Cartão do Kanban (`driCartaoHtml`) montado em div temporária | `esc` em fazenda, solicitante, datas, situação; `cod_faz` passa por `esc` mas é usado dentro de `onclick="driAbrirFazenda(${cod},'${tipo}')"` (esc de HTML não protege contexto JS; hoje o valor é numérico) | handler inline |
| `app/drone-inicio.js:136` | Mensagem de coluna vazia (`DRI_VAZIO`) | código fixo | ok |
| `app/drone-inicio.js:181` | Esvazia resultados da busca | — | atribui vazio |
| `app/drone-inicio.js:188` | Estrutura da tela Início do Drone | código fixo; `onclick="driAtencaoAbrir('${k}')"` com chaves fixas de `DRI_ATENCAO` | ok |
| `app/drone-inicio.js:247` | Esvazia resultados da busca | — | atribui vazio |
| `app/drone-inicio.js:270` | Gaveta "Atenção na base" | banco: cod_faz, fazenda, extra com `esc` | ok |
| `app/drone-inicio.js:299` | Esvazia resultados da busca | — | atribui vazio |
| `app/drone-inicio.js:303` | Resultados da busca de fazenda | `onclick="driAbrirFazenda(${f.cod_faz})"` com `cod_faz` do banco sem esc; nome com `esc` | handler inline |
| `app/drone-inicio.js:323` | Modal "Nova solicitação" | código fixo | ok |
| `app/drone-inicio.js:341` | Esvazia resultados da busca no modal | — | atribui vazio |
| `app/drone-inicio.js:345` | Resultados da busca no modal | `data-cod` e texto com `cod_faz` (numérico, sem esc); nome com `esc` | ok |
| `app/drone-inicio.js:349` | Esvazia resultados após escolher | — | atribui vazio |
| `app/drone-obstaculos.js:144` | Janela de obstáculos | `esc` em código e nome da fazenda; corpo vem de `droCorpoHtml` | ok |
| `app/drone-obstaculos.js:209` | Esvazia o rodapé (sem permissão) | — | atribui vazio |
| `app/drone-obstaculos.js:211` | Lista de camadas encontradas (`droLinha`) + erro | nomes de arquivos/zips enviados com `esc`; extensões e classes (15/25/50) fixas; `DRO.erro` com `esc` | ok |
| `app/drone-obstaculos.js:219` | Rodapé "espere o envio" | código fixo | ok |
| `app/drone-obstaculos.js:226` | Rodapé com resumo e botões | texto do resumo com `esc`; rótulo do botão fixo | ok |
| `app/drone-obstaculos.js:236` | Corpo da janela (`droCorpoHtml`) | banco/código: cartões com `esc` em descrição/texto; erro do envio com `esc`; cores e classes fixas | ok |
| `app/drone-previa.js:74` | Esvazia o alvo antes de inserir o canvas | — | atribui vazio |
| `app/drone-previa.js:75` | Selo "Abrir prévia" | código fixo | ok |
| `app/drone-previa.js:78` | Mensagem de erro | `e.message` com `esc` | ok |
| `app/drone-previa.js:94` | Janela de prévia do PDF | nome da fazenda/documento com `esc`; botões com `onclick` sem dados | ok |
| `app/drone-previa.js:150` | Páginas do PDF (um div + canvas por página) | número da página calculado | ok |
| `app/drone-previa.js:154` | Mensagem de erro | `e.message` com `esc` | ok |
| `app/motion.js:39` | Campo de partículas (`campo`) | código fixo | ok |
| `app/motion.js:51` | Ícone de resultado (check/close) | código fixo | ok |
| `app/motion.js:54` | Esvazia o overlay | — | atribui vazio |
| `app/motion.js:68` | Barra de progresso | código fixo (textos entram por `textContent`) | ok |
| `app/motion.js:100` | Partículas (`<i>` repetido) | número calculado | ok |
| `app/motion.js:135` | Animação de voo (SVG do drone) | código fixo; texto entra por `textContent` | ok |
| `app/motion.js:214` | Confete + selo de conclusão | números aleatórios/cores fixas; texto entra por `textContent` | ok |
| `app/motion.js:231` | Varredura (`<i>`) | código fixo | ok |
| `app/projetos.js:161` | Linha do tempo (`pjTLHtml`) do cache | `pjH` (= `esc`) em texto, justificativa, quem, tipo, talhões e documentos; `lote_id` com `Number()` | ok |
| `app/projetos.js:162` | Mensagem "Carregando histórico" | código fixo | ok |
| `app/projetos.js:167` | Linha do tempo (`pjTLHtml`) | mesmo caso da linha 161 | ok |
| `app/projetos.js:171` | Mensagem de erro + botão | código fixo | ok |
| `app/projetos.js:202` | Painel de projetos (`Proj.painelHtml`) | `pjH` em etapa, talhão, conservação, mês, mapeamento; cores vêm de constantes; `data-pj-rpc` usa ação fixa do código | ok |
| `app/projetos.js:246` | Modal "Confirmar observações" | código fixo | ok |
| `app/projetos.js:267` | Texto do modal de avanço | contagem calculada; nome da etapa com `pjH` | ok |
| `app/projetos.js:312` | Modal "Retroceder etapa" | código fixo | ok |
| `app/projetos.js:333` | Texto do modal de retrocesso | contagem calculada; nome da etapa com `pjH` | ok |
| `app/projetos.js:387` | Modal de revisão (esqueleto) | código fixo | ok |
| `app/projetos.js:520` | Corpo do modal de revisão | `pjH` em rótulos, nome de arquivo, número de talhão, motivo; `data-pj-campo` com chaves fixas | ok |
| `app/drone-fazenda-demo.html:135` | Esqueleto da tela demo | código fixo | ok |
| `app/drone-inicio-demo.html:36` | Mensagem demo "Fazenda N" | constante numérica da demo | ok |
| `app/index.html:1098` | Saudação do painel inicial | nome do usuário (`EU.nome`, banco) sem `esc`: `${me.nome.split(' ')[0]}` | falta esc |
| `app/index.html:1119` | Cards de métricas do painel | números calculados, rótulos fixos, `ATUALIZADO` (texto calculado) | ok |
| `app/index.html:1187` | Cards de módulo do painel | nomes/cores/ícones fixos (array `mods`); números calculados | ok |
| `app/index.html:1228` | Mensagem "Nenhuma fazenda" | código fixo | ok |
| `app/index.html:1230` | Lista de fazendas do Plantio | `f.n` (nome da fazenda, banco) e `f.cod` sem esc; `onclick="selF(${gi})"` com índice numérico calculado | falta esc + handler inline |
| `app/index.html:1255` | Painel de projetos (`Proj.painelHtml`) + arquivos | mesmo caso de projetos.js:202; `arquivosHtml` usa `esc` | ok |
| `app/index.html:1278` | Detalhe da fazenda (Plantio) | `f.n`, `t.sist_conser`, `t.mes`, `t.mapeamento` e `f.cod` (banco) sem esc; `acaoPlantio` tem `onclick` com `cod` (`Number()`) e nomes fixos de etapa; `arquivosHtml` com `esc` | falta esc + handler inline |
| `app/index.html:1350` | Mensagem "Nenhuma fazenda" | código fixo | ok |
| `app/index.html:1352` | Lista de fazendas do Preparo | `f.n` e `f.cod` (banco) sem esc; `onclick="selFP(${i})"` com índice calculado | falta esc + handler inline |
| `app/index.html:1379` | Painel de projetos (`Proj.painelHtml`) + arquivos | mesmo caso da linha 1255 | ok |
| `app/index.html:1398` | Detalhe da fazenda (Preparo) | `f.n`, `f.cod` e o nome de quem concluiu a etapa (`f.usr[i]`, de `USUARIOS`) sem esc; `f.obs` com `esc`; `acaoPreparo` tem `onclick` com `cod` (`Number()`), índices e nomes fixos de etapa, e `abrirEnvio(JSON)` em atributo com aspas simples | falta esc + handler inline |
| `app/index.html:1477` | Mensagem "Nenhuma fazenda" | código fixo | ok |
| `app/index.html:1479` | Lista de fazendas da Colheita | `f.n` e `f.cod` (banco) sem esc (`f.fr` tem `esc`); `onclick="selFC(${gi})"` com índice calculado | falta esc + handler inline |
| `app/index.html:1547` | Detalhe da fazenda (Colheita) | `esc` em nome, frente, período, estado, tipo e histórico; `f.cod` sem esc (código numérico); `onclick` com `togTal(${i})`, `marcarTipoC('${k}')` (chaves fixas) e `abrirEnvio(JSON)` | handler inline |
| `app/index.html:1632` | Tabela da fila de voos | banco: nomes e erros com `esc`; `v.layer%1000` é número; situação e rótulos fixos | ok |
| `app/index.html:1669` | Tela do celular (mock do portal) | dados de exemplo fixos em `PORTAL_MODS` (index.html:1047); `onclick="selPMod(${i})"` com índice | ok |
| `app/index.html:1812` | Cards de ferramentas | banco (`ferramentas`): nome, descrição, ícone, cor e URL com `esc`; a URL é escapada mas o esquema não é validado (`javascript:` passaria) | ok |
| `app/index.html:1823` | Botão "Configurar ferramentas" | código fixo | ok |
| `app/index.html:1841` | Mensagem de erro | `error.message` com `esc` | ok |
| `app/index.html:1873` | Chips de filtro de usuários | nomes fixos com `esc` | ok |
| `app/index.html:1875` | Lista de acessos (usuários) | banco: nome, e-mail, resumo com `esc`; o `onclick` lê `this.dataset.email`, sem interpolar | ok |
| `app/index.html:1929` | Esvazia o painel de usuário | — | atribui vazio |
| `app/index.html:1934` | Painel do usuário (cabeçalho e abas) | banco: nome e e-mail com `esc`; abas fixas | ok |
| `app/index.html:1959` | Aba Conta do usuário (`usrHtmlConta`) | nome e e-mail com `esc`; `onclick` usa `this.dataset.email` | ok |
| `app/index.html:1960` | Aba Módulos do usuário (`usrHtmlModulos`) | nomes fixos com `esc`; `data-mod`/`data-n` fixos | ok |
| `app/index.html:1961` | Aba Ferramentas do usuário (`usrHtmlFerramentas`) | código fixo; listas são preenchidas depois (linhas 2038 e 2051) | ok |
| `app/index.html:2038` | Grupos do GeoMap (checkboxes) | `g.nome` com `esc`; `g.id` (banco) entra sem esc em `value` | ok |
| `app/index.html:2047` | Mensagem "Carregando mapas" | código fixo | ok |
| `app/index.html:2048` | Mensagem de erro | código fixo | ok |
| `app/index.html:2049` | Mensagem "sem mapas" | código fixo | ok |
| `app/index.html:2051` | Tabela de mapas do GeoMap por usuário | `m.nome` com `esc`; `m.id` (banco) sem esc em `data-mapa`; rótulos fixos | ok |
| `app/index.html:2112` | Aba Geral das configurações | nome, e-mail, módulos, parâmetros com `esc` | ok |
| `app/index.html:2147` | Esqueleto de carregamento | código fixo | ok |
| `app/index.html:2149` | Mensagem de erro | `error.message` com `esc` | ok |
| `app/index.html:2151` | Card da importação diária (fontes) | nomes/descrições fixos; contagens do banco (números); erro com `esc` | ok |
| `app/index.html:2170` | Cards de edição de ferramentas | `esc` em nome, URL, descrição, ícone, cor; `onclick`/`oninput` com índice `${i}` calculado | handler inline |
| `app/index.html:2195` | Aba Portal das configurações | URL do portal com `esc` | ok |
| `app/index.html:2298` | Cabeçalho da tabela de consulta | código fixo | ok |
| `app/index.html:2338` | Linhas da tabela de consulta (`tbHtml`, `consDetail`) | banco sem esc: `r.n`, `r.cod`, `r.ciclo`, `r.mes`, `t.est`, `s.usr` (nome de usuário), `t.mes`; drone usa `esc`; `onclick="consExpand('${r._key}')"`/`consSel` com chave calculada e `drIrFazenda(${r.cod})` | falta esc + handler inline |
| `app/index.html:2341` | Contador de resultados | números calculados | ok |
| `app/index.html:2353` | Paginação | `onclick="rCons(${cPage±1})"` com número calculado | handler inline |
| `app/index.html:2432` | Filtros da consulta (selects) | `<option>${f.n}</option>` (nome da fazenda) e `<option>${m}</option>` (mês, banco) sem esc; etapas fixas | falta esc |
| `app/index.html:2708` | Esvazia o log de arrastar | — | atribui vazio |
| `app/index.html:2717` | Slots de envio da Colheita (`slotHtml`) | extensão e rótulo do código (`esc`); `onclick="limparSlot(${i})"` com índice calculado | handler inline |
| `app/index.html:2739` | Slots de envio (`slotHtml`) | mesmo caso da linha 2717 | handler inline |
| `app/index.html:2791` | Log de arrastar: erro de extensão | `arq.name` (arquivo enviado) com `esc` | ok |
| `app/index.html:2801` | Texto do modal de confirmação com `html:true` | o chamador escapa (único uso: `mostrarSenhaProvisoria`, e-mail e senha com `esc`) | ok |
| `app/index.html:2824` | Log de arrastar: arquivos aceitos/recusados | `arq.name` e rótulo com `esc`; código da fazenda extraído do nome com `\d{5}` (só dígitos) | ok |
| `app/index.html:2849` | Esvazia o progresso do envio | — | atribui vazio |
| `app/index.html:2912` | Contador do sino | número calculado | ok |
| `app/index.html:2914` | Lista de avisos (`listaSinoHtml`) | banco: título e texto com `esc`; `onclick="abrirAviso(${a.id})"` com id do banco sem esc | handler inline |
| `app/index.html:2929` | Painel do sino (`listaSinoHtml`) | mesmo caso da linha 2914 | handler inline |
| `app/motion-demo.html:66` | Campo de partículas (demo) | código fixo (`Mo.campo`) | ok |
| `app/motion-demo.html:79` | Lista de 6 talhões (demo) | números fixos | ok |
| `app/portal.html:202` | Mensagem "Carregando projetos" | código fixo | ok |
| `app/portal.html:223` | Mensagem de erro | `e.message` com `esc` | ok |
| `app/portal.html:258` | Mensagem "nenhum projeto" | nome do módulo é constante do código | ok |
| `app/portal.html:280` | Lista de fazendas e arquivos (`cartao`/`arquivo`) | banco: nome, rótulo, marcador, extensão, URL e nome do arquivo com `esc`; porém `onclick="buscar('${f.cod}')"` e `onclick="alternar(${f.cod})"` levam `cod` sem esc, e `abrirVisor('${escJs(url)}',…)` usa `escJs` (escape de JS + HTML, adequado). `href` de `url` com `esc`, sem validar o esquema | handler inline |
| `app/projetos-demo.html:253` | Lista de fazendas (demo) | dados de exemplo do próprio arquivo, com `esc`; distribuição por `Proj.distribuicaoHtml` | ok |
| `app/projetos-demo.html:268` | Esvazia o painel | — | atribui vazio |
| `app/projetos-demo.html:271` | Painel (`Proj.painelHtml`) | mesmo caso de projetos.js:202 | ok |

## Resumo

A tabela tem **164** linhas e o `grep` devolveu **164** ocorrências: não há diferença (uma ocorrência por linha, nenhuma linha com duas).

| situação | pontos |
|---|---|
| `ok` | 122 |
| `falta esc` | 8 |
| `handler inline` | 19 |
| `atribui vazio` | 21 |

6 pontos têm as duas situações `falta esc` + `handler inline` e entram nas duas linhas acima. Pontos distintos: 164.

### Por arquivo

| arquivo | pontos |
|---|---|
| `app/apresentacao.js` | 11 |
| `app/corretivos.js` | 33 |
| `app/drone-fazenda-demo.html` | 1 |
| `app/drone-fazenda.js` | 14 |
| `app/drone-inicio-demo.html` | 1 |
| `app/drone-inicio.js` | 12 |
| `app/drone-obstaculos.js` | 6 |
| `app/drone-previa.js` | 6 |
| `app/index.html` | 52 |
| `app/motion-demo.html` | 2 |
| `app/motion.js` | 8 |
| `app/portal.html` | 4 |
| `app/projetos-demo.html` | 3 |
| `app/projetos.js` | 11 |

## Ressalvas (para a próxima tarefa)

- **`falta esc` concentrado em `index.html`**: nome da fazenda (`f.n`), `f.cod`, `t.sist_conser`, `t.mes`, `t.mapeamento`, nome do usuário (`EU.nome`, `f.usr[i]`, `s.usr`) e meses nos selects. A fonte é o banco (`fazendas.nome` vem do servidor Geo), então não é entrada livre do usuário, mas um nome com `<` quebraria a tela.
- **Números/ids do banco sem `esc`** em pontos `ok` ou `handler inline`: `cod_faz`, `sol.id`, `ger.id`, `a.id` (avisos), `g.id`/`m.id` (GeoMap), números de talhão. Seguros se a coluna for numérica; `m.id` dos mapas do GeoMap não foi confirmado.
- **`onclick` com dado interpolado**: o padrão seguro já usado no projeto é `this.dataset.x` (usuários, `index.html:1875`). `abrirEnvio(JSON)` entre aspas simples quebraria com `'` no JSON.
- **URLs do banco** (`ferramentas.url`, `release_url`, `a.url` no portal) passam por `esc`, mas nenhum ponto valida o esquema: `javascript:` seria aceito.
- Atribuições `innerHTML = ''` são seguras; podem virar `replaceChildren()` se quiserem uniformidade.
