# Drone: redesenho das telas — plano de implementação

> **Para quem executa:** uma sessão do Claude por etapa (S0…S6). Comece pela seção da sua sessão. A S0 já está em passos. Nas S1–S6, o primeiro passo é detalhar a sua seção em passos (skill `writing-plans`, mesmo formato da S0) dentro de `docs/superpowers/plans/2026-10-27-drone-telas-Sx.md`, mostrar ao usuário e só então executar. Execução: skill `delegar` (o operacional sai para o executor barato; desenho, revisão e merge ficam com o Claude principal), seguindo `test-driven-development`. Marque as caixas (`- [ ]`) conforme avança.

**Objetivo:** refazer a tela do Drone em Início + área de trabalho da fazenda + janela de obstáculos, sem pisca-pisca e sem mudar o agente Python.

**Arquitetura:** front-end em JS puro carregado por `app/index.html` (scripts clássicos, funções globais chamadas por `onclick`), Supabase (RPCs `hub.drone_*`) e MapLibre. O mapa passa a ser criado uma vez por fazenda e atualizado com `setData`; a tela se redesenha por partes, comparando assinaturas; as animações ficam em `app/motion.js` / `motion.css`.

**Tecnologias:** JS (ES2020, sem build), MapLibre GL, pdf.js 3.11.174 (cdnjs), JSZip 3.10.1 (cdnjs, só na S5), Supabase JS, testes `node --test` (puros) e Playwright + Edge em Python (tela).

**Spec:** [docs/superpowers/specs/2026-10-27-drone-telas-redesenho-design.md](../specs/2026-10-27-drone-telas-redesenho-design.md) · Maquete: https://claude.ai/artifact/HGJ6zku4ABshgCFSzmDJup

## Restrições globais

- O agente Python (`drone/`) não muda. Exceção: um teste novo em `tests/drone/test_insumos.py` (S5).
- Banco: só a migration da S3, que estende `hub.drone_painel`. Nenhuma tabela nova.
- Textos da tela em português do Brasil. Nomes de função com prefixo `dr` (fazenda/dados), `dri` (Início), `dro` (obstáculos) e `drPrev` (prévia), seguindo o estilo do arquivo atual.
- Toda animação nova respeita `prefers-reduced-motion` (cai no estado final).
- Testes que gravam no banco salvam e restauram o valor original. Nunca "limpar" apagando.
- O teste de tela só roda com a fazenda 10974 livre (regra já existente em `tests/app/teste_drone_tela.py`).
- Cada sessão termina com: os testes passando, `verification-before-completion`, revisão do diff (`requesting-code-review`) e **ok do usuário antes de mesclar na main e enviar**. O push nos repositórios `lmalerbo/*` exige trocar a conta do `gh` só durante o push (ver memória `reference-github-contas-push`).

## Foco da revisão (casos que os testes das tarefas não cobrem sozinhos)

1. **O polling apaga o que o usuário digitou ou selecionou** (motivo da publicação, talhões marcados, aba aberta). O esperado é nada se perder num ciclo de atualização. → teste na S2 (Tarefa S2.2) e na S4 (S4.4).
2. **Resposta atrasada de outra fazenda:** o usuário troca de fazenda enquanto a busca anterior ainda responde. O esperado é ignorar a resposta antiga. → teste na S2 (S2.1, `drRespostaValida`).
3. **Arquivos estranhos na janela de obstáculos:** nome com acento ou espaço, `.zip` com pastas internas, o mesmo nome-base em dois `.zip`, `.SHP` maiúsculo, falta do `.prj`. O esperado é agrupar certo, sinalizar o conflito e não enviar uma camada incompleta. → testes na S5 (S5.1).
4. **Usuário só leitura ou solicitante** abrindo a fazenda e o Início. O esperado é ver tudo, sem nenhuma ação de editor. → teste na S4 (S4.3, `drEstadoPainel`) e conferência visual na S3.
5. **Sair da tela do Drone ou esconder a aba** com polling ativo. O esperado é o polling parar e voltar ao retornar, sem timers duplicados. → teste na S2 (S2.3).

---

## S0 — Correções dos 3 bugs na tela atual

**Arquivos:**
- Modificar: `app/drone.js` (funções `drObstaculosHtml`, `drRecarregarFazenda`, `drAbrirFazenda`, `drRender`, `drVooPublicacao`; novas funções puras logo após `drRotuloShape`)
- Testes: `tests/app/drone_puro.test.js`

**Interfaces produzidas:**
- `drUltimoEnvio(envios: Array<{tipo,status,...}>, tipo: string) → objeto | null`. Os envios chegam do mais novo para o mais antigo.
- `drAssinaturaObst(obst: Array<{classe_m, versao}>) → string`, por exemplo `"15:1|25:2"`.
- `drMapaReaproveitavel(chaveAntes: string|undefined, chaveAgora: string, temMapa: boolean) → boolean`.

### Tarefa S0.1: o erro de obstáculos considera só o último envio de obstáculos

- [ ] **Passo 1: escrever o teste que falha** (acrescentar ao fim de `tests/app/drone_puro.test.js`)

```js
test('último envio de um tipo: erro antigo não vale depois de um envio novo ok', () => {
  const envios = [   // do mais novo para o mais antigo, como vem do banco
    { id: 9, tipo: 'ajuste', status: 'erro' },
    { id: 8, tipo: 'obstaculos', status: 'ok' },
    { id: 7, tipo: 'obstaculos', status: 'erro' },
  ];
  assert.strictEqual(ctx.drUltimoEnvio(envios, 'obstaculos').id, 8);
  assert.strictEqual(ctx.drUltimoEnvio(envios, 'ajuste').id, 9);
  assert.strictEqual(ctx.drUltimoEnvio(envios, 'infestacao'), null);
  assert.strictEqual(ctx.drUltimoEnvio(null, 'obstaculos'), null);
});
```

- [ ] **Passo 2: rodar e ver falhar**

Rodar: `node --test tests/app/drone_puro.test.js`
Esperado: FAIL com `ctx.drUltimoEnvio is not a function`.

- [ ] **Passo 3: implementar** (em `app/drone.js`, logo depois de `drRotuloShape`)

```js
// Envios vêm do mais novo para o mais antigo: o primeiro do tipo é o que vale.
function drUltimoEnvio(envios,tipo){return (envios||[]).find(e=>e.tipo===tipo)||null;}
```

Em `drObstaculosHtml`, trocar as duas linhas `const env=...` e `const err=...` por:

```js
  const ult=drUltimoEnvio(DR.info.envios,'obstaculos');
  const env=ult&&['fila','processando'].includes(ult.status)?ult:null;
  const err=ult&&ult.status==='erro'?ult:null;
```

- [ ] **Passo 4: rodar e ver passar.** Rodar: `node --test tests/app/drone_puro.test.js`. Esperado: todos PASS.
- [ ] **Passo 5: commit** — `git add app/drone.js tests/app/drone_puro.test.js && git commit -m "Drone: erro de obstaculos considera so o ultimo envio de obstaculos"`

### Tarefa S0.2: obstáculo novo aparece no mapa sem atualizar a página

- [ ] **Passo 1: teste que falha**

```js
test('assinatura dos obstáculos muda quando chega versão nova (descarta o desenho guardado)', () => {
  const a = ctx.drAssinaturaObst([{ classe_m: 25, versao: 1 }, { classe_m: 15, versao: 1 }]);
  const b = ctx.drAssinaturaObst([{ classe_m: 15, versao: 1 }, { classe_m: 25, versao: 1 }]);
  const c = ctx.drAssinaturaObst([{ classe_m: 15, versao: 2 }, { classe_m: 25, versao: 1 }]);
  assert.strictEqual(a, '15:1|25:1');
  assert.strictEqual(a, b);            // a ordem não importa
  assert.notStrictEqual(a, c);         // versão nova muda a assinatura
  assert.strictEqual(ctx.drAssinaturaObst([]), '');
  assert.strictEqual(ctx.drAssinaturaObst(null), '');
});
```

- [ ] **Passo 2: rodar e ver falhar** (`drAssinaturaObst is not a function`).
- [ ] **Passo 3: implementar**

```js
// Muda quando alguma classe ganha versão nova: aí o desenho guardado (DR.obstGeo) não vale mais.
function drAssinaturaObst(obst){return (obst||[]).map(o=>o.classe_m+':'+o.versao).sort().join('|');}
```

Em `drRecarregarFazenda`, logo depois da linha `DR.geo=geo;DR.info={...};`:

```js
    const ass=drAssinaturaObst(DR.info.obst);
    if(ass!==DR.obstAss){DR.obstAss=ass;DR.obstGeo=null;}
```

Em `drAbrirFazenda`, no começo, junto de `DR.obstGeo=null;`, acrescentar `DR.obstAss=null;`.

- [ ] **Passo 4: rodar e ver passar.**
- [ ] **Passo 5: commit** — `"Drone: obstaculo novo aparece no mapa sem recarregar a pagina"`

### Tarefa S0.3: o polling não recria o mapa (fim do pisca-pisca)

- [ ] **Passo 1: teste que falha**

```js
test('mapa é reaproveitado só se a fazenda/documento é o mesmo e o mapa existe', () => {
  assert.strictEqual(ctx.drMapaReaproveitavel('10372|normal', '10372|normal', true), true);
  assert.strictEqual(ctx.drMapaReaproveitavel('10372|normal', '10372|catacao', true), false);
  assert.strictEqual(ctx.drMapaReaproveitavel('10372|normal', '10156|normal', true), false);
  assert.strictEqual(ctx.drMapaReaproveitavel('10372|normal', '10372|normal', false), false);
  assert.strictEqual(ctx.drMapaReaproveitavel(undefined, '10372|normal', true), false);
});
```

- [ ] **Passo 2: rodar e ver falhar.**
- [ ] **Passo 3: implementar**

Função pura:

```js
function drMapaReaproveitavel(antes,agora,temMapa){return !!temMapa&&antes===agora;}
```

Em `drRender`, separar o cabeçalho numa função e criar o caminho curto. Substituir o início de `drRender` até `document.getElementById('dr-faz').innerHTML=` por:

```js
function drCabecalhoHtml(){
  const g=DR.geo,i=DR.info,tal=g.features.filter(f=>f.properties.camada==='talhao');
  const area=tal.filter(f=>f.properties.status!=='fora_da_base').reduce((s,f)=>s+(f.properties.area_ha||0),0);
  const pct=g.cobertura_pct;
  const card=(doc,tit,x,extra)=>`<div class="dr-doc${DR.doc===doc?' on':''}" onclick="DR.doc='${doc}';DR.sel=new Map();DR.rem=new Set();drRender()">
    <b>${tit} · ${x?'Rev'+x.revisao:'sem projeto'}</b>${extra}<small>${x?fmtNum(x.area_ha)+' ha · '+new Date(x.em).toLocaleDateString('pt-BR'):'—'}</small></div>`;
  return`<div class="dr-ph" id="dr-ph"><span class="dr-cod" style="font-size:13px">${DR.cod}</span>
      <div><div class="nm">${esc(i.faz.nome)}</div><div class="sub">${tal.length} talhões · ${fmtNum(area)} ha</div></div>
      <div class="dr-docs">${card('normal','Normal',g.normal,pct!=null&&pct<100?`<span class="dr-tag">${Math.floor(pct)}% DA FAZENDA</span>`:'')}
        ${card('catacao','Catação',g.catacao,'')}</div></div>`;
}

// Atualiza os dados do mapa que já existe, sem recriá-lo (o polling passa por aqui).
function drAtualizarFontesMapa(){
  const m=DR.mapa;
  m.getSource('tal').setData({type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada==='talhao')});
  m.getSource('apl').setData({type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada===DR.doc)});
  drAtualizarSelecaoMapa();
  if(DR.mostrarObst&&!DR.obstGeo)drObstaculos(true);
}

function drRender(){
  const temMapa=!!(DR.mapa&&document.getElementById('dr-map')&&DR.mapa.getSource('tal'));
  if(drMapaReaproveitavel(DR.mapaChave,DR.cod+'|'+DR.doc,temMapa)){
    document.getElementById('dr-ph').outerHTML=drCabecalhoHtml();
    drAtualizarFontesMapa();drPainelLateral();drVooPublicacao();
    return;
  }
  document.getElementById('dr-faz').innerHTML=drCabecalhoHtml()+`
```

Isto é, o template que segue `innerHTML=` perde o bloco `<div class="dr-ph">…</div>` (que agora vem de `drCabecalhoHtml()`) e começa em `<div class="dr-body">`. O resto de `drRender` não muda.

Em `drVooPublicacao`, não reiniciar o voo que já está na tela. Logo depois de `if(!DR.voo||DR.voo.id!==ger.id)DR.voo={id:ger.id,desde:Date.now()};`, trocar a linha `Mo.voo(...)` por:

```js
    if(!mapa.querySelector(':scope>.mo-voo'))Mo.voo(mapa,{texto:'Publicando no portal…',desde:DR.voo.desde});
```

- [ ] **Passo 4: rodar e ver passar.** Rodar `node --test tests/app/drone_puro.test.js` e depois `node --test tests/app/` (nada mais quebra).
- [ ] **Passo 5: conferir no navegador.** Abrir o Hub local (`python -m http.server` em `app/`), entrar numa fazenda com geração em fila (ou simular: no console, `DR.poll=setTimeout(()=>drRecarregarFazenda(),100)`) e ver que o mapa não pisca nem perde o zoom. O teste real com envio de obstáculos fica com o usuário: subir um arquivo com erro, depois um certo, e ver o erro sumir e o desenho novo aparecer sem F5.
- [ ] **Passo 6: commit** — `"Drone: polling atualiza o mapa sem recria-lo (fim do pisca-pisca)"`

---

## S1 — Dividir `drone.js` sem mudar o comportamento

**Arquivos:**
- Criar: `app/drone-dados.js`, `app/drone-previa.js`, `app/drone-inicio.js`, `app/drone-fazenda.js`, `app/drone.css`
- Remover: `app/drone.js`
- Modificar: `app/index.html` (no lugar de `<script src="drone.js">`, os 4 scripts nesta ordem: dados, prévia, início, fazenda; `<link rel="stylesheet" href="drone.css">` no `<head>`), `tests/app/drone_puro.test.js` (carrega os 4 arquivos no mesmo contexto `vm`)

**O que vai em cada um:**
- `drone-dados.js`: `DR`, `DR_ST`, `DR_COR`, `DR_OBS_COR`, `drBotao`, `drRpc` e as funções puras (`drPodeGerarCatacao`, `drNomeSeguro`, `drClasseEscolhida`, `drPodeCancelar`, `drValidarSolicitacao`, `drRotuloShape`, `drUltimoEnvio`, `drAssinaturaObst`, `drMapaReaproveitavel`, `drAtual`).
- `drone-previa.js`: `DRP`, `DRP_PDFJS` e todas as `drPrev*`, `drPdfjs`, `drDesenharPagina`, `drMostrarPdf`.
- `drone-inicio.js`: `droneIniciar`, `drCarregarPainel`, `drListarAtencao`, `drBuscar`, `drNovaSolicitacao`, `drIrFazenda`, `drCancelar`.
- `drone-fazenda.js`: o resto (abrir/recarregar/desenhar fazenda, mapa, painel, envios, gerar, publicar, descartar, obstáculos no mapa).
- `drone.css`: o texto de `drEstilo()` e de `drPrevEstilo()`. As duas funções viram no-op e somem nas chamadas.

**Tarefas:**
- S1.1 Mover o código (cópia literal, sem reescrever) e ajustar `index.html` e o teste puro. Critério: `node --test tests/app/` passa sem mudar nenhuma asserção.
- S1.2 Rodar `tests/app/teste_drone_tela.py` (regras do arquivo) e conferir no navegador: fila, abrir fazenda, prévia, nova solicitação, sininho → `drIrFazenda`. Um commit por tarefa.

---

## S2 — Motor de atualização e animações novas (ainda no layout atual)

**Interfaces produzidas** (em `drone-dados.js`, salvo indicação):
- `drAssinaturas(info, geo, doc) → {cab, painel, obst, mapa}` (strings): JSON das partes que alimentam cada pedaço da tela.
- `drRespostaValida(codPedido, codAtual) → boolean`.
- `drOcupado(info, ger) → boolean`: a regra atual de `ocupado` em `drPainelLateral`, extraída.
- `drone-fazenda.js`: `drCarregarFazenda()` (busca e guarda; descarta resposta de fazenda trocada), `drDesenhar(partesMudadas)`, `drMapaCriar()` (uma vez por fazenda), `drMapaAtualizar()` (`setData` + `setPaintProperty('apl-f','fill-color',DR_COR[DR.doc])`). A troca de aba não recria o mapa.
- `drone-dados.js`: `drPoll` com um único timer, `drPollIniciar(fn, ms)`, `drPollParar()`; para quando `document.visibilityState==='hidden'` ou a view `drone` sai de cena (gancho em `trocar()` no `index.html`) e volta ao retornar.
- `motion.js` (acrescentar ao contrato no topo do arquivo): `Mo.trilho(el) → {parar()}`, `Mo.varredura(el) → {parar()}` (overlay CSS sobre o mapa, `pointer-events:none`), `Mo.mover(container, aplicar: () => void) → Promise` (FLIP por `data-id`). CSS em `motion.css`, com o bloco `prefers-reduced-motion`.
- `drone-fazenda.js`: `drPulsarSelecao(on: boolean)`: anima `line-opacity` da camada `tal-l` só nos talhões com estado `sel`, por `requestAnimationFrame`, e para ao desligar. `drFadeCamada(id)`: usa `fill-opacity-transition` de 600 ms.

**Tarefas:**
- S2.1 Assinaturas, `drRespostaValida` e `drOcupado` puros, com testes:
  - assinatura do painel não muda quando só `envios[].enviado_em` muda;
  - muda quando o status da geração muda;
  - `drRespostaValida(10372, 10156) === false`.
- S2.2 Desenho por partes e mapa criado uma vez. Teste de tela (Playwright): guardar `window.__mapa = DR.mapa`, forçar dois ciclos de `drCarregarFazenda()` e trocar de aba; conferir `DR.mapa === window.__mapa`. Digitar no campo de motivo, rodar um ciclo e conferir que o texto continua (Foco 1).
- S2.3 Polling único. Teste puro com timers falsos (`setTimeout` injetado no contexto `vm`): `drPollIniciar` duas vezes deixa um só timer; `drPollParar` limpa; sem chamadas com a aba oculta (Foco 5).
- S2.4 Animações novas em `motion.js`/`motion.css`, com casos novos em `tests/app/teste_movimento.py`: `Mo.trilho` e `Mo.varredura` criam e removem o overlay; `Mo.mover` termina com os elementos no lugar novo; com `reduced-motion` emulado não há animação ativa.
- S2.5 Ligar na tela atual: varredura + pulso durante a geração; fade da camada de obstáculos quando ela é recarregada.

---

## S3 — Migration do painel e Início do Drone

**Arquivos:** `supabase/migrations/20261028090000_drone_painel_inicio.sql` (novo), `app/drone-inicio.js`, `app/drone.css`, `app/index.html` (só se precisar de contêiner), testes.

**Migration:** `create or replace function hub.drone_painel()` mantendo tudo o que existe hoje em `20261009090000_drone_melhorias.sql` e acrescentando:
- em `geracao`: `'pedido_em', g.pedido_em, 'iniciado_em', g.iniciado_em`;
- no topo: `'publicadas_7d'` (contagem de `drone_geracoes` com `status='publicada'` e `concluido_em > now() - interval '7 days'`; confirmar a coluna de data da publicação no esquema antes);
- `obstaculos_antigos` e `fora_da_base` passam de lista de códigos para `[{cod_faz, fazenda}]`. Ajustar quem lê hoje: `drListarAtencao` e o card do dashboard/Consultas em `index.html` (procurar `obstaculos_antigos` e `fora_da_base`).

Aplicar do mesmo jeito que as migrations anteriores do Drone (ver o runbook ou o histórico em `docs/`). Se for pelo SQL Editor, pedir ao usuário.

**Interfaces:** `driColuna(sol) → 'solicitacoes'|'desenvolvimento'|'analisar'`; `driCartaoHtml(sol) → string` (com `data-id`); `driDesenhar(painel)` reconcilia por `data-id` usando `Mo.mover`; `driAtencaoAbrir(chave)` abre a lista lateral; `driAbrirFazenda(cod, tipo)` troca para a área de trabalho; `driVoltar()` volta ao Início sem recarregar tudo.

**Tarefas:**
- S3.1 Migration + leitores ajustados. Conferir com uma consulta direta que o JSON novo tem os campos.
- S3.2 `driColuna` com testes para cada caso da spec §3.1:
  - `solicitado` sem geração → solicitacoes;
  - `em_elaboracao` sem geração → solicitacoes;
  - geração `fila`/`processando` → desenvolvimento;
  - geração `erro` → desenvolvimento;
  - `pronta` + `publicar_pedido_em` sem erro → desenvolvimento;
  - `pronta` + `publicacao_erro` → desenvolvimento;
  - `pronta` sem pedido → analisar.
- S3.3 Tela do Início (colunas, cartões, coluna vazia, rodapé "Publicadas nos últimos 7 dias", busca com atalho `/`, Nova solicitação), com polling de 10 s só com item em andamento, usando `drPoll*`.
- S3.4 Faixa "Atenção na base" e lista lateral. A lista de obstáculos antigos abre a fazenda com a janela de obstáculos marcada para abrir (na S5 a janela passa a existir; até lá abre só a fazenda).
- S3.5 Navegação Início ↔ fazenda; `drIrFazenda(cod)` (sininho, Consultas) continua funcionando. Conferência visual contra a maquete (tela 1) e com um usuário só leitura (Foco 4).

---

## S4 — Área de trabalho da fazenda

**Interfaces** (puras em `drone-dados.js`, com testes):
- `drEtapaAtiva(sol, ger) → 0|1|2|3` (Montar, Gerar, Conferir, Publicado).
- `drEstadoPainel({doc, sol, ger, edita}) → 'montando'|'catacao'|'gerando'|'previa'|'publicando'|'consulta'`.
- `drChipObstaculos(obst, envioObst, hoje) → {texto, tom: 'ok'|'velho'|'erro'|'proc'}`. "velho" = alguma classe com mais de 24 meses; "erro" e "proc" vêm de `drUltimoEnvio`.
- `drEscopo(sel: Map<talhao, 'sistema'|'shape'>, rem: Set, ajusteId) → {incluir, remover}`: lança erro se houver Shape sem `ajusteId`.
- `drIndicadoresPrevia(resumo, vigente, doc) → {area, deltaArea, cob, cobAntes}`. Na Catação, sem cobertura.

**Tarefas:**
- S4.1 Cabeçalho (voltar, abas com revisão e cobertura, botão Obstáculos com chip, menu ⋯ com Revisões em lista lateral e Cancelar) e barra de etapas com `Mo.etapa`. Testes de `drChipObstaculos` e `drEtapaAtiva`.
- S4.2 Mapa: barra de ferramentas flutuante (Incluir, Remover, Sem projeto, Limpar), zoom, menu Camadas (obstáculos liga/desliga) e legenda compacta.
- S4.3 Painel por estado (spec §3.3, itens 1–6), com a ação principal fixa no rodapé. Teste de `drEstadoPainel`, incluindo solicitante e só leitura → `consulta` sem ações (Foco 4).
- S4.4 Fonte Sistema/Shape por talhão e área de arrastar o shape de ajuste. Teste de `drEscopo`. O motivo digitado e a seleção sobrevivem ao polling (Foco 1, teste de tela).
- S4.5 Prévia: capa, indicadores, alertas com o texto, Motivo, Descartar e Publicar. A janela de prévia atual (`drPrevAbrir`) continua igual. Teste de `drIndicadoresPrevia`. Conferência visual contra as telas 2, 4, 5 e 6 da maquete.

---

## S5 — Janela de obstáculos

**Interfaces** (puras em `drone-dados.js`, com testes):
- `drClassePeloNome(nome) → 15|25|50|null`: mesma regra de `drone/insumos.py::classe_pelo_nome` (tira o acento, minúsculas, `/(\d+)\s*m(?![a-z])/` ou número no fim; só 15/25/50).
- `drAgruparArquivos(arquivos: Array<{nome, tamanho}>) → Array<{base, partes: {shp?, shx?, dbf?, prj?, cpg?}, falta: string[], classe: number|null, conflito: boolean}>`: agrupa pelo nome-base sem extensão (extensão em minúsculas, pasta do zip ignorada); `falta` lista as obrigatórias ausentes (`shp`, `shx`, `dbf`); `prj` ausente vira aviso, não bloqueio; nome-base repetido vindo de origens diferentes → `conflito: true`.
- `drNomeComClasse(classe, nome) → string`: `${classe}m_${drNomeSeguro(nome)}`.
- `drone-obstaculos.js`: `droAbrir()`, `droAdicionar(FileList)` (expande `.zip` com JSZip carregado sob demanda de `https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js`), `droEnviar()` (sobe com `drSubirComProgresso` usando `drNomeComClasse` e chama `drone_registrar_envio` uma vez com `p_tipo:'obstaculos', p_classe_m:null`).

**Tarefas:**
- S5.1 Funções puras e testes (Foco 3):
  - `drClassePeloNome`: `restricoes15m.shp`→15, `Restrições 25 m.shp`→25, `rede_50m_cemig.shp`→50, `linhas_cemig.shp`→null, `obst_30m.shp`→null;
  - agrupamento com `.SHP` maiúsculo, falta de `.shx`, falta só do `.prj`, mesmo nome-base em dois zips e nome com espaço/acento.
- S5.2 Prova de que o agente lê o nome renomeado: em `tests/drone/test_insumos.py`, `classe_pelo_nome('25m_linhas_cemig.shp') == 25` e `classe_pelo_nome('15m_rede_50m.shp') == 15` (a classe da frente ganha). Rodar `pytest tests/drone/test_insumos.py -q`.
- S5.3 Janela (spec §3.4): cartões das classes, área de arrastar, lista com as partes e os botões 15/25/50, dicas, resumo e envio bloqueado até tudo estar classificado. Progresso com `Mo.progresso`.
- S5.4 Depois do envio: a janela fecha, o chip fica "processando", o polling acompanha e, no fim, a camada é recarregada com fade (usa S0.2 e S2). Se der erro, o chip fica vermelho e o erro aparece na janela.
- S5.5 Teste de tela até antes do envio: `set_input_files` com shapes de exemplo (criar em `tests/app/fixtures/obst/`, gerados por um script com geopandas), conferir o bloqueio sem classe e a lista de nomes renomeados que seriam enviados (expor `droPreparar()` que devolve os caminhos sem subir). O envio real é conferido pelo usuário numa fazenda de verdade.

---

## S6 — Polimento, revisão final e manual

- S6.1 `impeccable` (auditoria da tela: hierarquia, contraste, foco por teclado, telas estreitas ~1280 px) e `design-motion-principles` (auditar as animações novas) e aplicar o que for material.
- S6.2 Revisão do conjunto (`requesting-code-review`, nível high) e tratar os achados (`receiving-code-review`).
- S6.3 Atualizar `docs/drone-manual.md` para as telas novas (Início, área de trabalho, janela de obstáculos), com as capturas da maquete trocadas por capturas reais.
- S6.4 `finishing-a-development-branch`, atualizar a memória do projeto (`project_modulo_drone_decisoes.md`) e registrar a passagem.
