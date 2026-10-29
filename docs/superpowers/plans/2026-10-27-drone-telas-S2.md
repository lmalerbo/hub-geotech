# Drone S2: motor de atualização e animações novas — plano em passos

> **Para quem executa:** detalhamento da seção S2 de [2026-10-27-drone-telas-redesenho.md](2026-10-27-drone-telas-redesenho.md). Execução pela skill `delegar`: o operacional sai para o executor barato; revisão e merge ficam com o Claude principal. Marque as caixas (`- [ ]`) conforme avança. Branch `drone-s2` (worktree `../hub-geotech-drone-s2`), saído da main 59636d8 (S1 já mesclada).

**Objetivo:** a área da fazenda deixa de redesenhar tudo a cada 5 s. O mapa é criado uma vez ao abrir a fazenda, a troca Normal/Catação só atualiza as fontes, cada parte da tela é redesenhada só quando os dados dela mudam, o polling tem um timer só e pausa fora da tela. Entram as animações de espera da geração (varredura do mapa, pulso dos talhões, trilho no painel) e o fade da camada de obstáculos. O layout continua o atual.

**Arquitetura:** `drCarregarFazenda()` busca, descarta a resposta se a fazenda mudou no meio (`drRespostaValida`), calcula `drAssinaturas` e chama `drDesenhar(partes)` só com as partes que mudaram (`drPartesMudadas`). O mapa é criado por `drMapaCriar()` e daí em diante só recebe `drMapaAtualizar()` (`setData` + cor do documento). O polling sai de `drPainelLateral` e vira `drPollIniciar/Parar/Visivel` (um timer, pausa com a aba oculta ou fora da view `drone`). As animações novas entram em `motion.js`/`motion.css` como extensão do contrato.

**Tecnologias:** JS puro (scripts clássicos), MapLibre GL (feature-state, `setPaintProperty`, `*-transition`), Web Animations API (FLIP), `node --test`, Playwright + Edge.

**Spec:** §4 e §5 de [2026-10-27-drone-telas-redesenho-design.md](../specs/2026-10-27-drone-telas-redesenho-design.md)

## Restrições globais

- O agente Python e o banco não mudam. A única mudança de consulta é acrescentar `escopo` ao `select` de `drone_geracoes` (a coluna já existe desde `20261008090000_drone_parte2.sql`).
- Textos em português do Brasil; prefixo `dr` nas funções.
- Toda animação nova respeita `prefers-reduced-motion` (estado final, sem laço).
- Testes: `node --test tests/app/*.test.js` (sem o glob, falha; hoje 46) e `python tests/app/teste_movimento.py` (sem conta). `tests/app/teste_drone_tela.py` precisa de `HUB_CONTA_TESTE`, que o Claude não lê: **quem roda é o usuário**, com a fazenda 10974 livre.
- Antes de mesclar: verificação, revisão do diff e **ok do usuário**. Push com troca de conta do `gh` (memória `reference-github-contas-push`).

## Decisões de movimento (skill `design-motion-principles`, contexto ferramenta de trabalho → Emil primeiro, Jakub depois)

| Animação | Propósito | Valores | Menos movimento |
|---|---|---|---|
| `Mo.varredura` | o mapa está sendo gerado (espera de minutos) | véu `rgba(91,110,232,.06)` entra em 200 ms (`--mo-sai`); faixa de 30% cruza em 2,4 s, `cubic-bezier(.45,0,.55,1)`; sai em 200 ms | só o véu, parado |
| Pulso dos talhões | quais talhões estão em geração | `line-opacity` 1 ↔ .35, período 1,6 s, ~20 quadros/s (não a 60, poupa o mapa) | contorno azul fixo, sem pulso |
| `Mo.trilho` | o painel "Gerando" está vivo | trilho de 3 px; faixa de 35% em 1,6 s, mesma curva | trilho parado, sem faixa |
| `Mo.mover` (FLIP) | continuidade quando um cartão muda de lugar (usado na S3) | 240 ms, `--mo-sai` (`cubic-bezier(.16,1,.3,1)`), só `transform` | troca seca |
| Fade de obstáculos | camada nova chegou | **300 ms** (o plano geral dizia 600; ferramenta de trabalho pede < 300–400) | 0 ms |

Os três laços (varredura, pulso, trilho) só existem enquanto há geração em fila/processando; somem ao terminar. Não há laço "chamando atenção" fora de uma espera real.

## Foco da revisão

1. **Foco 1 do plano geral — o polling apaga o que o usuário fez.** Com assinaturas, o painel não é redesenhado se os dados não mudaram. Conferir que seleção (`DR.sel/rem`), modo remover e o motivo (`DRP.motivo`, na janela da prévia) sobrevivem a um ciclo. Teste de tela S2.2.
2. **Foco 2 — resposta atrasada de outra fazenda.** `drCarregarFazenda` guarda `cod` no início e sai calada se `DR.cod` mudou, inclusive no `catch` (erro da fazenda velha não pode pintar a nova).
3. **Foco 5 — timers duplicados.** `drPollIniciar` sempre limpa o anterior; `drAbrirFazenda` chama `drPollParar`; `trocar()` chama `drPollVisivel`. Teste puro S2.3.
4. **Mapa ainda carregando** quando chega dado novo ou troca de documento: `drMapaAtualizar` sai se a fonte não existe, e o `load` lê `DR.geo`/`DR.doc` na hora (não o que havia na criação).
5. **rAF do pulso preso** depois de trocar de fazenda: o laço confere `DR.mapa===m` a cada quadro e para.
6. **`Mo.carregando` em `#dr-faz`** só acrescenta o esboço (não apaga o mapa); mesmo assim, abrir uma fazenda (ação rara) sempre descarta e recria o mapa — é a regra "uma vez por fazenda aberta".

---

### Tarefa S2.1: regras puras (assinaturas, resposta válida, ocupado, talhões em geração)

- [x] **Passo 1: testes que falham** (fim de `tests/app/drone_puro.test.js`)

```js
test('assinaturas: painel ignora enviado_em e muda com o status da geração', () => {
  const geo = { normal: { revisao: 2 }, catacao: null, cobertura_pct: 100,
    features: [{ properties: { camada: 'talhao', talhao: 1, status: 'ok', area_ha: 10 }, geometry: null }] };
  const info = { faz: { cod_faz: 1, nome: 'X' }, sols: [], obst: [{ classe_m: 15, versao: 1 }], revs: [],
    ger: [{ id: 5, status: 'fila' }], envios: [{ id: 1, tipo: 'obstaculos', status: 'ok', enviado_em: '2026-10-01' }] };
  const a = ctx.drAssinaturas(info, geo, 'normal');
  const b = ctx.drAssinaturas({ ...info, envios: [{ ...info.envios[0], enviado_em: '2026-10-02' }] }, geo, 'normal');
  assert.strictEqual(a.painel, b.painel);
  const c = ctx.drAssinaturas({ ...info, ger: [{ id: 5, status: 'processando' }] }, geo, 'normal');
  assert.notStrictEqual(a.painel, c.painel);
  assert.strictEqual(a.mapa, c.mapa);
  assert.notStrictEqual(a.mapa, ctx.drAssinaturas(info, geo, 'catacao').mapa);
  assert.deepStrictEqual(Object.keys(a).sort(), ['cab', 'mapa', 'obst', 'painel']);
});

test('partes mudadas: tudo na primeira vez, só o que mudou depois', () => {
  const x = { cab: '1', painel: '2', obst: '3', mapa: '4' };
  assert.deepStrictEqual(ctx.drPartesMudadas(null, x), ['cab', 'painel', 'obst', 'mapa']);
  assert.deepStrictEqual(ctx.drPartesMudadas(x, { ...x, painel: '9' }), ['painel']);
  assert.deepStrictEqual(ctx.drPartesMudadas(x, { ...x }), []);
});

test('resposta de outra fazenda é descartada', () => {
  assert.strictEqual(ctx.drRespostaValida(10372, 10156), false);
  assert.strictEqual(ctx.drRespostaValida(10372, 10372), true);
});

test('ocupado: geração em andamento, publicação pedida ou envio na fila', () => {
  const info = { envios: [] };
  assert.strictEqual(ctx.drOcupado(info, null), false);
  assert.strictEqual(ctx.drOcupado(info, { status: 'fila' }), true);
  assert.strictEqual(ctx.drOcupado(info, { status: 'processando' }), true);
  assert.strictEqual(ctx.drOcupado(info, { status: 'pronta' }), false);
  assert.strictEqual(ctx.drOcupado(info, { status: 'pronta', publicar_pedido_em: 'x' }), true);
  assert.strictEqual(ctx.drOcupado(info, { status: 'pronta', publicar_pedido_em: 'x', publicacao_erro: 'e' }), false);
  assert.strictEqual(ctx.drOcupado({ envios: [{ status: 'processando' }] }, null), true);
});

test('talhões em geração saem do escopo, só com a geração em andamento', () => {
  const esc = { incluir: [{ talhao: 3, fonte: 'sistema' }, { talhao: 7, fonte: 'shape' }], remover: [9] };
  assert.deepStrictEqual(ctx.drTalhoesGerando({ status: 'processando', escopo: esc }), [3, 7]);
  assert.deepStrictEqual(ctx.drTalhoesGerando({ status: 'pronta', escopo: esc }), []);
  assert.deepStrictEqual(ctx.drTalhoesGerando({ status: 'fila', escopo: null }), []);   // Catação
  assert.deepStrictEqual(ctx.drTalhoesGerando(null), []);
});
```

- [x] **Passo 2: rodar e ver falhar.** `node --test tests/app/*.test.js` → FAIL (`drAssinaturas is not a function` etc.).
- [x] **Passo 3: implementar** (fim de `app/drone-dados.js`)

```js
// ── motor de atualização (spec §4) ───────────────────────────────────────
// JSON das partes que alimentam cada pedaço da tela. Parte com a mesma
// assinatura do ciclo anterior não é redesenhada (fim do pisca-pisca).
function drAssinaturas(info,geo,doc){
  const tal=(geo.features||[]).filter(f=>f.properties.camada==='talhao');
  const envios=(info.envios||[]).map(({enviado_em,...e})=>e);
  return{
    cab:JSON.stringify([info.faz,doc,geo.normal,geo.catacao,geo.cobertura_pct,
      tal.map(f=>[f.properties.talhao,f.properties.status,f.properties.area_ha])]),
    painel:JSON.stringify([doc,geo.normal&&geo.normal.revisao,info.sols,info.ger,envios,info.obst,info.revs]),
    obst:drAssinaturaObst(info.obst),
    mapa:JSON.stringify([doc,geo.features])};
}
function drPartesMudadas(antes,agora){return Object.keys(agora).filter(k=>!antes||antes[k]!==agora[k]);}
function drRespostaValida(codPedido,codAtual){return codPedido===codAtual;}
function drOcupado(info,ger){
  return !!((ger&&(['fila','processando'].includes(ger.status)||(ger.publicar_pedido_em&&!ger.publicacao_erro)))
    ||(info.envios||[]).some(e=>e.status==='fila'||e.status==='processando'));
}
// Talhões que pulsam no mapa enquanto a prévia é gerada (Catação não tem escopo: só a varredura).
function drTalhoesGerando(ger){
  if(!ger||!['fila','processando'].includes(ger.status))return[];
  return((ger.escopo&&ger.escopo.incluir)||[]).map(i=>i.talhao);
}
```

- [x] **Passo 4: rodar e ver passar** (51 testes).
- [x] **Passo 5: commit** — `Drone S2.1: assinaturas, resposta valida, ocupado e talhoes em geracao (puros)`

### Tarefa S2.2: desenho por partes e mapa criado uma vez

Arquivos: `app/drone-fazenda.js`, `app/drone-previa.js` (classe `drp-gerando`), `tests/app/teste_drone_tela.py`.

- [x] **Passo 1: teste de tela** (em `teste_drone_tela.py`, logo depois de abrir a fazenda 10974 e antes de gerar; e o do motivo logo depois que a prévia fica pronta, antes de descartar)

```python
        # S2.2: o mapa não é recriado pelo polling nem pela troca Normal/Catação
        pg.evaluate("window.__mapa=DR.mapa")
        pg.evaluate("async()=>{await drCarregarFazenda();await drCarregarFazenda();}")
        pg.click('.dr-doc >> nth=1'); pg.click('.dr-doc >> nth=0')
        confere(pg.evaluate("DR.mapa===window.__mapa"), 'mapa reaproveitado no polling e na troca de documento')
```
```python
        # Foco 1: o motivo digitado na prévia sobrevive a um ciclo de atualização
        pg.click('text=Abrir prévia'); pg.fill('#dr-mot', 'teste S2')
        pg.evaluate("drCarregarFazenda()"); pg.wait_for_timeout(1500)
        confere(pg.input_value('#dr-mot') == 'teste S2', 'motivo continua depois do polling')
        pg.evaluate("drPrevFechar()")
```
As chamadas existentes a `drRecarregarFazenda()` no teste passam a `drCarregarFazenda()`.

- [x] **Passo 2: reescrever o ciclo em `drone-fazenda.js`**
  - `drRecarregarFazenda` → **`drCarregarFazenda`** (renomear também todas as chamadas em `drone-fazenda.js`). No `select` de `drone_geracoes`, acrescentar `escopo`. Depois de cada `await` de dados, antes de gravar em `DR`: `if(!drRespostaValida(cod,DR.cod))return;`. No `catch`, só escrever o erro se `drRespostaValida(cod,DR.cod)`. No fim, no lugar de `drRender()`:
    ```js
      drRedesenhar();
      if(drOcupado(DR.info,drAtual().ger))drPollIniciar(async()=>{await drCarregarFazenda();drCarregarPainel();},5000);
      else drPollParar();
    ```
  - Novas:
    ```js
    function drRedesenhar(){
      const ass=drAssinaturas(DR.info,DR.geo,DR.doc),partes=drPartesMudadas(DR.ass,ass);
      DR.ass=ass;drDesenhar(partes);
    }
    // Troca Normal/Catação: o mapa fica, só as fontes e a cor mudam.
    function drTrocarDoc(doc){DR.doc=doc;DR.sel=new Map();DR.rem=new Set();drRedesenhar();}
    function drDesenhar(partes){
      const tem=p=>partes.includes(p);
      if(!DR.mapa||!document.getElementById('dr-map')){drEsqueleto();drMapaCriar();drPainelLateral();}
      else{
        if(tem('cab'))document.getElementById('dr-ph').outerHTML=drCabecalhoHtml();
        if(tem('mapa'))drMapaAtualizar();
        if(tem('obst')&&DR.mostrarObst)drObstaculos(true);
        if(tem('painel'))drPainelLateral();
      }
      drVooPublicacao();drAnimGeracao();
    }
    ```
  - `drEsqueleto()`: o `innerHTML` de `#dr-faz` que hoje está em `drRender` (cabeçalho + `#dr-map` + legenda + `#dr-side`), com `id="dr-leg-apl"` no `<i>` da cor da área de aplicação.
  - `drMapaCriar()`: o atual `drPintarMapa` sem o `DR.mapa.remove()` e sem `DR.mapaChave`; sempre `Mo.carregando(box)`. Dentro do `load`, montar as fontes a partir de `DR.geo`/`DR.doc` **na hora** (não do que existia na criação). Em `tal-l`, o `case` de cor e largura ganha o estado `ger` (mesma cor/largura de `sel`) e a pintura ganha `'line-opacity':1`. No fim do `load`: `drAtualizarSelecaoMapa(); if(DR.mostrarObst)drObstaculos(true); drAnimGeracao();`.
  - `drMapaAtualizar()` (substitui `drAtualizarFontesMapa`):
    ```js
    function drMapaAtualizar(){
      const m=DR.mapa;if(!m||!m.getSource('tal'))return;   // ainda carregando: o 'load' lê DR.geo
      m.getSource('tal').setData({type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada==='talhao')});
      m.getSource('apl').setData({type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada===DR.doc)});
      m.setPaintProperty('apl-f','fill-color',DR_COR[DR.doc]);
      const leg=document.getElementById('dr-leg-apl');if(leg)leg.style.background=DR_COR[DR.doc];
      drAtualizarSelecaoMapa();
    }
    ```
  - `drMapaDescartar()`: `drPulsarGeracao(false)`; `DR.varr&&DR.varr.parar()`; `DR.varr=null`; `DR.mapa&&DR.mapa.remove()`; `DR.mapa=null`; `DR.ass=null`.
  - `drAbrirFazenda`: no lugar de `clearTimeout(DR.poll)`, chamar `drPollParar(); drMapaDescartar();` e então `drCarregarFazenda()`.
  - `drAtualizarSelecaoMapa`: `setFeatureState` com `{sel, rem, ger: gerando.has(n)}`, sendo `gerando=new Set(drTalhoesGerando(drAtual().ger))`.
  - Cartões Normal/Catação (`drCabecalhoHtml`): `onclick="drTrocarDoc('${doc}')"`.
  - `drPainelLateral`: tirar o bloco final de `clearTimeout(DR.poll)`/`ocupado`/`setTimeout` (foi para `drCarregarFazenda`).
  - Apagar `drRender`, `drPintarMapa`, `drAtualizarFontesMapa`. Em `drone-dados.js`, apagar `drMapaReaproveitavel` e o teste dela; tirar `poll` do objeto `DR`.
  - `drone-previa.js`, `drPrevHtml`: a caixa de "Gerando prévia…" ganha a classe `drp-gerando` (`<div class="dr-box drp-gerando">`).
  - Até a S2.5, `drAnimGeracao` e `drPulsarGeracao` existem como `function drAnimGeracao(){}` e `function drPulsarGeracao(){}`.
- [x] **Passo 3:** `node --test tests/app/*.test.js` passa; `grep -n "drRender\|drRecarregarFazenda\|drPintarMapa\|DR.poll\|drMapaReaproveitavel" app/ tests/` não acha nada.
- [x] **Passo 4: commit** — `Drone S2.2: desenho por partes, mapa criado uma vez por fazenda, resposta velha descartada`

### Tarefa S2.3: polling único

- [x] **Passo 1: teste que falha** (fim de `drone_puro.test.js`, num contexto `vm` próprio com timers falsos)

```js
test('polling: um timer só, para e pausa com a aba oculta ou fora da tela', () => {
  const timers = new Map(); let seq = 0;
  const c = { console, sb: {}, document: { visibilityState: 'visible' },
    setTimeout: (f, ms) => { timers.set(++seq, f); return seq; }, clearTimeout: id => timers.delete(id) };
  vm.createContext(c);
  vm.runInContext(fs.readFileSync(__dirname + '/../../app/drone-dados.js', 'utf8'), c);
  let n = 0; const fn = () => n++;
  c.drPollIniciar(fn, 5000); c.drPollIniciar(fn, 5000);
  assert.strictEqual(timers.size, 1);
  c.drPollParar(); assert.strictEqual(timers.size, 0);
  c.document.visibilityState = 'hidden'; c.drPollIniciar(fn, 5000);
  assert.strictEqual(timers.size, 0);                       // aba oculta: não agenda
  c.document.visibilityState = 'visible'; c.drPollAgendar();
  assert.strictEqual(timers.size, 1);                       // voltou: retoma
  c.drPollVisivel(false); assert.strictEqual(timers.size, 0); // saiu da view drone
  c.drPollVisivel(true); assert.strictEqual(timers.size, 1);
  const [id, f] = [...timers][0]; timers.delete(id); f();   // dispara como o navegador: o timer some
  assert.strictEqual(n, 1);
  assert.strictEqual(timers.size, 0);                       // roda uma vez; só reagenda se fn chamar drPollIniciar
});
```

- [x] **Passo 2: rodar e ver falhar.**
- [x] **Passo 3: implementar** (fim de `drone-dados.js`)

```js
// Polling único (spec §4): um timer só. Pausa com a aba oculta ou fora da view
// do Drone e retoma ao voltar. O callback roda uma vez; quem quer continuar chama drPollIniciar de novo.
const DR_POLL={t:null,fn:null,ms:0,fora:false};
function drPollAgendar(){
  clearTimeout(DR_POLL.t);DR_POLL.t=null;
  if(!DR_POLL.fn||DR_POLL.fora||document.visibilityState==='hidden')return;
  DR_POLL.t=setTimeout(()=>{DR_POLL.t=null;const f=DR_POLL.fn;DR_POLL.fn=null;f();},DR_POLL.ms);
}
function drPollIniciar(fn,ms){DR_POLL.fn=fn;DR_POLL.ms=ms;drPollAgendar();}
function drPollParar(){clearTimeout(DR_POLL.t);DR_POLL.t=null;DR_POLL.fn=null;}
function drPollVisivel(naTela){DR_POLL.fora=!naTela;drPollAgendar();}
if(document.addEventListener)document.addEventListener('visibilitychange',drPollAgendar);
```
Em `app/index.html`, `trocar()`, logo antes de `if(v==='drone')droneIniciar();`: `if(typeof drPollVisivel==='function')drPollVisivel(v==='drone');`

- [x] **Passo 4: rodar e ver passar.**
- [x] **Passo 5: commit** — `Drone S2.3: polling unico que pausa com a aba oculta ou fora da tela`

### Tarefa S2.4: animações novas em `motion.js` / `motion.css`

- [x] **Passo 1: vitrine e testes que falham.** Em `app/motion-demo.html`, nova seção (antes de `Mo.voo`):
```html
<section class="card"><h2>Mo.trilho / Mo.varredura / Mo.mover</h2>
  <div id="gerando" style="padding:8px;border:1px solid #e3e6ea;border-radius:8px">Gerando prévia…</div>
  <div id="mapa-varr" style="position:relative;height:120px;background:#f7f8fa;border-radius:8px;margin:8px 0"></div>
  <div id="colunas" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
    <div id="col-a"><div data-id="c1">Cartão 1</div><div data-id="c2">Cartão 2</div></div><div id="col-b"></div></div>
  <button class="btn esc" id="b-trilho" onclick="demoTrilho()">Liga/desliga espera</button>
  <button class="btn esc" id="b-mover" onclick="demoMover()">Mover cartão 1</button></section>
```
com `demoTrilho()` alternando `Mo.trilho(#gerando)` + `Mo.varredura(#mapa-varr)` e `parar()` nos dois, e `demoMover()` = `window.__mov=Mo.mover(colunas,()=>colB.appendChild(c1))`.

Em `tests/app/teste_movimento.py`, dentro de `rodar` (antes de `sem erro de JS`):
```python
    pg.click('#b-trilho')
    confere('trilho e varredura aparecem' + sufixo,
            pg.locator('#gerando .mo-trilho').count() == 1 and pg.locator('#mapa-varr .mo-varr').count() == 1)
    confere('varredura não pega clique' + sufixo,
            pg.locator('#mapa-varr .mo-varr').evaluate("v=>getComputedStyle(v).pointerEvents") == 'none')
    anim = pg.locator('#mapa-varr .mo-varr i').evaluate("i=>getComputedStyle(i).animationName")
    confere(f'varredura anda só com movimento ({anim})' + sufixo, (anim != 'none') != calmo)
    pg.click('#b-trilho'); pg.wait_for_timeout(400)
    confere('trilho e varredura somem' + sufixo,
            pg.locator('#gerando .mo-trilho').count() == 0 and pg.locator('#mapa-varr .mo-varr').count() == 0)
    pg.click('#b-mover')
    if not calmo:
        confere('mover: anima transform no meio' + sufixo,
                pg.locator('[data-id=c1]').evaluate("e=>e.getAnimations().length") > 0)
    pg.evaluate("window.__mov")
    confere('mover: termina no lugar novo e sem animação' + sufixo,
            pg.locator('#col-b [data-id=c1]').count() == 1
            and pg.locator('[data-id=c1]').evaluate("e=>e.getAnimations().length") == 0)
```
(`pg.evaluate("window.__mov")` espera a Promise.)

- [x] **Passo 2: rodar e ver falhar.** `python tests/app/teste_movimento.py`
- [x] **Passo 3: implementar.** No contrato do topo de `motion.js`, acrescentar:
```
//   Mo.trilho(el)                → {parar()}  faixa de luz num trilho fino (espera de geração)
//   Mo.varredura(el)             → {parar()}  véu e faixa varrendo el (mapa), sem tocar no canvas
//   Mo.mover(container,aplicar)  → Promise    FLIP por data-id: mede, aplica, anima o deslocamento
```
Funções (dentro do IIFE, exportadas no objeto `Mo` como as outras):
```js
  function trilho(el){
    if(!el)return{parar(){}};
    const t=document.createElement('span');t.className='mo-trilho';t.setAttribute('aria-hidden','true');
    el.appendChild(t);return{parar(){t.remove();}};
  }
  function varredura(el){
    if(!el)return{parar(){}};
    if(getComputedStyle(el).position==='static')el.style.position='relative';
    const v=document.createElement('div');v.className='mo-varr';v.setAttribute('aria-hidden','true');v.innerHTML='<i></i>';
    el.appendChild(v);
    return{parar(){if(calmo())return v.remove();v.classList.add('mo-sai');setTimeout(()=>v.remove(),200);}};
  }
  async function mover(container,aplicar){
    if(!container){aplicar();return;}
    const antes=new Map();
    container.querySelectorAll('[data-id]').forEach(e=>antes.set(e.dataset.id,e.getBoundingClientRect()));
    aplicar();
    if(calmo())return;
    const anims=[];
    container.querySelectorAll('[data-id]').forEach(e=>{
      const a=antes.get(e.dataset.id);if(!a)return;            // cartão novo: entra sem FLIP
      const b=e.getBoundingClientRect(),dx=a.left-b.left,dy=a.top-b.top;
      if(!dx&&!dy)return;
      anims.push(e.animate([{transform:`translate(${dx}px,${dy}px)`},{transform:'none'}],
        {duration:240,easing:'cubic-bezier(.16,1,.3,1)'}).finished.catch(()=>{}));
    });
    await Promise.all(anims);
  }
```
CSS em `motion.css` (antes do bloco `@media (prefers-reduced-motion:reduce)`):
```css
/* ── Trilho e varredura: esperas da geração do Drone ─────── */
.mo-trilho{display:block;position:relative;height:3px;margin-top:8px;border-radius:2px;overflow:hidden;background:rgba(91,110,232,.15)}
.mo-trilho::after{content:'';position:absolute;inset:0;width:35%;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,var(--mo-c4),transparent);animation:mo-trilho 1.6s cubic-bezier(.45,0,.55,1) infinite}
@keyframes mo-trilho{to{transform:translateX(300%)}}
.mo-varr{position:absolute;inset:0;z-index:2;pointer-events:none;overflow:hidden;background:rgba(91,110,232,.06);
  animation:mo-varr-entra .2s var(--mo-sai);transition:opacity .2s}
.mo-varr.mo-sai{opacity:0}
.mo-varr i{position:absolute;top:0;bottom:0;left:0;width:30%;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,rgba(91,110,232,.18),transparent);animation:mo-varr 2.4s cubic-bezier(.45,0,.55,1) infinite}
@keyframes mo-varr{to{transform:translateX(340%)}}
@keyframes mo-varr-entra{from{opacity:0}}
```
e, dentro do bloco `prefers-reduced-motion` já existente: `.mo-trilho::after,.mo-varr i{animation:none;display:none}.mo-varr{animation:none;transition:none}`.

- [x] **Passo 4: rodar e ver passar** (com e sem menos movimento). `node --test` continua verde.
- [x] **Passo 5: commit** — `Movimento: Mo.trilho, Mo.varredura e Mo.mover (FLIP), com menos movimento`

### Tarefa S2.5: ligar na tela da fazenda

- [x] **Passo 1: implementar em `drone-fazenda.js`** (no lugar dos stubs da S2.2)
```js
// Espera da geração: varredura no mapa, pulso nos talhões do escopo e trilho no painel.
function drAnimGeracao(){
  const {ger}=drAtual(),on=!!ger&&['fila','processando'].includes(ger.status);
  const box=document.getElementById('dr-map');
  if(on&&!DR.varr&&box)DR.varr=Mo.varredura(box);
  if(!on&&DR.varr){DR.varr.parar();DR.varr=null;}
  drPulsarGeracao(on);
  const g=document.querySelector('#dr-side .drp-gerando');   // painel só é redesenhado quando muda
  if(g&&!g.querySelector(':scope>.mo-trilho'))Mo.trilho(g);
}
// Pulso do contorno dos talhões em geração: line-opacity da camada tal-l só no estado 'ger', ~20 quadros/s.
function drPulsarGeracao(on){
  const m=DR.mapa,calmo=matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(!on||calmo||!m||!m.getLayer('tal-l')){
    cancelAnimationFrame(DR.pulso);DR.pulso=null;
    if(m&&m.getLayer('tal-l'))m.setPaintProperty('tal-l','line-opacity',1);
    return;
  }
  if(DR.pulso)return;
  const t0=performance.now();let ult=0;
  const passo=t=>{
    if(DR.mapa!==m||!m.getLayer('tal-l')){DR.pulso=null;return;}
    if(t-ult>=50){ult=t;
      const op=.35+.65*(.5+.5*Math.cos((t-t0)/1600*2*Math.PI));
      m.setPaintProperty('tal-l','line-opacity',['case',['boolean',['feature-state','ger'],false],op,1]);}
    DR.pulso=requestAnimationFrame(passo);
  };
  DR.pulso=requestAnimationFrame(passo);
}
// Camada nova chega em 300 ms (0 com menos movimento).
function drFadeCamada(id,prop,final){
  const m=DR.mapa;if(!m||!m.getLayer(id))return;
  const ms=matchMedia('(prefers-reduced-motion: reduce)').matches?0:300;
  m.setPaintProperty(id,prop+'-transition',{duration:ms,delay:0});
  requestAnimationFrame(()=>{if(m.getLayer(id))m.setPaintProperty(id,prop,final);});
}
```
Em `drObstaculos`, as camadas entram com opacidade 0 (`fill-opacity:0` em `obs-buf`, `line-opacity:0` em `obs-buf-l`/`obs-lin`, `circle-opacity:0` em `obs-pt`) e, depois dos `addLayer`: `drFadeCamada('obs-buf','fill-opacity',.15); drFadeCamada('obs-buf-l','line-opacity',1); drFadeCamada('obs-lin','line-opacity',1); drFadeCamada('obs-pt','circle-opacity',1);`. Como `drObstaculos` é assíncrona, conferir `DR.mapa===m` depois do `await` antes de adicionar.
- [x] **Passo 2: verificação.** `node --test tests/app/*.test.js`; `python tests/app/teste_movimento.py`; carregar `app/index.html` sem login (servidor local + Playwright) e conferir zero erro de JS.
- [x] **Passo 3: commit** — `Drone S2.5: varredura, pulso e trilho durante a geracao; fade da camada de obstaculos`

### Fechamento

- [x] `verification-before-completion` (saídas dos testes na mensagem ao usuário).
- [x] `requesting-code-review` sobre `main...drone-s2`, com o Foco da revisão acima.
- [ ] Usuário roda `tests/app/teste_drone_tela.py` (com `HUB_CONTA_TESTE`, 10974 livre) e confere logado: abrir fazenda, trocar Normal/Catação sem piscar, gerar prévia (varredura + pulso + trilho), descartar, ligar obstáculos (fade).
- [ ] **Ok do usuário** → merge na main, push (troca de conta do `gh`), remover worktree/branch, atualizar a memória `project_drone_telas_redesenho`.

## Registro da execução (28/10)

- S2.1+S2.3: camada 1 — nemotron-3-ultra (OpenRouter grátis) — aprovada com ajuste (comparação de arrays entre contextos `vm` no teste; o executor estourou o tempo antes de commitar).
- S2.4: camada 2 — Haiku — aprovada de primeira.
- S2.2+S2.5: camada 2 — Haiku — aprovada; corrigido na revisão: estado `ger` dos talhões só era aplicado com mudança do mapa; mapa antigo não era removido após erro.
- Revisão (Sonnet), corrigidos: ciclo antigo da mesma fazenda sobrescrevia o novo (falso "Publicado"); erro de rede no polling apagava o mapa e matava o polling; clicar no documento ativo deixava seleção fantasma; `drObstaculos` concorrente/antes do `load`; pulso pintando com a view escondida.
- Anotados para depois: assinatura do mapa serializa todas as geometrias a cada 5 s (trocar por algo mais barato se pesar em fazenda grande); painel antigo clicável durante a carga de outra fazenda (já existia antes da S2).
