# Drone S4 — Área de trabalho da fazenda (plano em passos)

> **Para quem executa:** detalhamento da seção S4 de [2026-10-27-drone-telas-redesenho.md](2026-10-27-drone-telas-redesenho.md). Branch `drone-s4` (worktree `../hub-geotech-drone-s4`), criado a partir da `main` (f2cde52). Execução com a skill `delegar`, seguindo `test-driven-development`. Marque as caixas conforme avança.

**Objetivo:** trocar a área da fazenda de hoje (cartões Normal/Catação + painel com tudo empilhado) pela da maquete: cabeçalho fixo com abas e chip de Obstáculos, barra de etapas, mapa com ferramentas flutuantes e um painel direito que mostra **um estado por vez**, com a ação principal fixa no rodapé.

**Spec:** §3.2 e §3.3 de [2026-10-27-drone-telas-redesenho-design.md](../specs/2026-10-27-drone-telas-redesenho-design.md) · Maquete, telas 2 (`Fazenda`), 4 (`Gerando`), 5 (`Previa`) e 6 (`Catacao`): https://claude.ai/artifact/HGJ6zku4ABshgCFSzmDJup

**Arquivos:**
- Modificar: `app/drone-dados.js` (funções puras novas), `app/drone-fazenda.js` (cabeçalho, etapas, mapa, painel por estado), `app/drone-previa.js` (só `drPrevHtml` sai do painel; a janela `drPrevAbrir` fica igual), `app/drone.css` (classes `dr-*` novas; saem `.dr-docs`, `.dr-doc`, `.dr-box` do painel da fazenda se ninguém mais usar)
- Criar: `app/drone-fazenda-demo.html` (dados fictícios, um estado por `?estado=`, para a conferência visual)
- Testes: `tests/app/drone_puro.test.js`, `tests/app/teste_drone_tela.py`

**Decisões tomadas neste detalhamento (conferir):**
1. **Só leitura e solicitante veem sempre o estado `consulta`**, mesmo com geração andando ou prévia pronta. O painel de consulta mostra uma linha com a situação ("Gerando prévia…", "Prévia pronta, aguardando conferência", "Publicando…"), o mapa, o chip de Obstáculos e o histórico, sem nenhum botão. O voo da publicação continua no mapa para todos.
2. **Estado extra `erro`** (geração que deu erro), que a spec não lista: mensagem do agente e **Descartar e montar de novo** no rodapé, como hoje. Sem ele, o editor ficaria preso.
3. **Botão Obstáculos na S4 abre o envio de hoje** (`drEnviar('obstaculos')`, com o `prompt` da classe). A janela nova é a S5. Para quem só lê, o botão vira só o chip, sem ação.
4. **Barra de etapas só na Normal e nos estados gerando/prévia/publicando da Catação.** Na Catação montando, a maquete (tela 6) troca a barra pelos passos numerados no painel; sigo a maquete.
5. **"Novo nesta prévia" no mapa = contorno verde nos talhões do escopo.** O banco não guarda a geometria da prévia (só o PDF e o .zip), então não há área nova para entrar com fade. O que entra com fade é a camada de obstáculos, que liga sozinha ao chegar na prévia.
6. **Catação, passo 2:** a lista de camadas enviadas sai dos nomes-base de `drone_envios.arquivos` do último envio de infestação. O número de feições da maquete fica de fora (o banco não guarda).
7. **Linha de contexto da solicitação** (quem pediu, observação, data) vem do cartão da solicitação em `DR.painel` (que já traz o nome do solicitante). Sem mudança de banco. Se o painel ainda não carregou, a linha fica vazia.
8. **Motivo da publicação no painel** (spec §3.3, item 4) e na janela de prévia usam o mesmo `DRP.motivo[ger.id]`; `drPublicar` lê de lá, e não mais de `#dr-mot`. Assim o campo não se perde no polling e os dois lugares ficam iguais.
9. **"Revisões" do menu ⋯** abre uma gaveta lateral com a mesma aparência da gaveta da Atenção (`.dri-gaveta`). O histórico sai do painel.
10. **Zoom:** os botões +/− da maquete são os do `NavigationControl` do MapLibre, que já está no canto superior direito. Só restilizo com CSS e coloco o botão **Camadas** embaixo dele.

**Interfaces produzidas (puras em `app/drone-dados.js`):**
- `drEtapaAtiva(sol, ger) → 0|1|2|3` (Montar, Gerar, Conferir, Publicado)
- `drEstadoPainel({doc, sol, ger, edita}) → 'montando'|'catacao'|'gerando'|'previa'|'publicando'|'erro'|'consulta'`
- `drChipObstaculos(obst, envios, hoje, meses=24) → {texto, tom: 'ok'|'velho'|'erro'|'proc'}`
- `drEscopo(sel: Map<talhao,'sistema'|'shape'>, rem: Set, ajusteId) → {incluir, remover}` (lança erro com Shape sem `ajusteId`)
- `drIndicadoresPrevia(resumo, vigente, doc) → {area, deltaArea, cob, cobAntes}` (`vigente = {area_ha, cobertura_pct}`; na Catação, `cob` e `cobAntes` são `null`)
- `drSituacaoTalhao(props) → 'sem projeto' | 'refazer RevN'`
- `drDecorrido(desdeIso, agoraMs) → '45 s' | '1 min 12 s' | '1 h 05 min'`
- `drContextoSol(card) → string` ("Solicitação de Ana · “Completar…” · para 05/11")
- `drCamadasEnvio(envio) → ['manchas_buva', …]` (nomes-base únicos, sem pasta e sem extensão)

**Interfaces produzidas (DOM em `app/drone-fazenda.js`):** `drCabecalhoHtml()` (reescrita), `drEtapasHtml()`, `drFerramentasHtml()`, `drPainelLateral()` (reescrita, um `drPainel_<estado>()` por estado, cada um devolvendo `{corpo, rodape}`), `drFerramenta(qual)`, `drFonteTalhao(n, fonte)`, `drMenuAbrir()`, `drRevisoesAbrir()`, `drCamadasAlternar()`.

---

## S4.0 Branch

- [x] **Passo 1:** `git worktree add ../hub-geotech-drone-s4 -b drone-s4 main` e rodar `node --test tests/app/*.test.js` lá. Esperado: tudo passando (59 testes puros da S3).

## S4.1 Funções puras (TDD)

**Arquivos:** `app/drone-dados.js`, `tests/app/drone_puro.test.js`

- [x] **Passo 1: escrever os testes** (falham com "não é função"):

```js
test('etapa ativa segue a geração', () => {
  assert.strictEqual(ctx.drEtapaAtiva(null, null), 0);
  assert.strictEqual(ctx.drEtapaAtiva({ status: 'solicitado' }, null), 0);
  assert.strictEqual(ctx.drEtapaAtiva({}, { status: 'fila' }), 1);
  assert.strictEqual(ctx.drEtapaAtiva({}, { status: 'processando' }), 1);
  assert.strictEqual(ctx.drEtapaAtiva({}, { status: 'erro' }), 1);
  assert.strictEqual(ctx.drEtapaAtiva({}, { status: 'pronta' }), 2);
  assert.strictEqual(ctx.drEtapaAtiva({}, { status: 'pronta', publicar_pedido_em: 'x' }), 3);
  assert.strictEqual(ctx.drEtapaAtiva({}, { status: 'pronta', publicar_pedido_em: 'x', publicacao_erro: 'falhou' }), 2);
});

test('estado do painel: um por vez; quem não edita só consulta (Foco 4)', () => {
  const E = (doc, ger, edita = true, sol = { status: 'solicitado' }) => ctx.drEstadoPainel({ doc, sol, ger, edita });
  assert.strictEqual(E('normal', null), 'montando');
  assert.strictEqual(E('catacao', null), 'catacao');
  assert.strictEqual(E('catacao', null, true, null), 'catacao');
  assert.strictEqual(E('normal', { status: 'fila' }), 'gerando');
  assert.strictEqual(E('catacao', { status: 'processando' }), 'gerando');
  assert.strictEqual(E('normal', { status: 'pronta' }), 'previa');
  assert.strictEqual(E('normal', { status: 'pronta', publicar_pedido_em: 'x' }), 'publicando');
  assert.strictEqual(E('normal', { status: 'pronta', publicar_pedido_em: 'x', publicacao_erro: 'e' }), 'previa');
  assert.strictEqual(E('normal', { status: 'erro' }), 'erro');
  for (const ger of [null, { status: 'fila' }, { status: 'pronta' }, { status: 'pronta', publicar_pedido_em: 'x' }, { status: 'erro' }])
    for (const doc of ['normal', 'catacao']) assert.strictEqual(E(doc, ger, false), 'consulta');
});

test('chip de Obstáculos: processando e erro vêm do último envio; âmbar com classe de mais de 24 meses', () => {
  const hoje = new Date('2026-10-29T12:00:00');
  const obst = [{ classe_m: 15, enviado_em: '2026-09-30T12:00:00' }, { classe_m: 25, enviado_em: '2026-01-10T12:00:00' },
    { classe_m: 50, enviado_em: '2025-03-01T12:00:00' }];
  assert.deepStrictEqual({ ...ctx.drChipObstaculos(obst, [], hoje) }, { texto: '3 classes · 30/09/26', tom: 'ok' });
  const velho = [...obst.slice(0, 2), { classe_m: 50, enviado_em: '2024-09-01T12:00:00' }];
  assert.strictEqual(ctx.drChipObstaculos(velho, [], hoje).tom, 'velho');
  assert.deepStrictEqual({ ...ctx.drChipObstaculos(obst, [{ tipo: 'obstaculos', status: 'processando' }], hoje) },
    { texto: 'processando envio…', tom: 'proc' });
  assert.deepStrictEqual({ ...ctx.drChipObstaculos(obst, [{ tipo: 'obstaculos', status: 'fila' }], hoje) },
    { texto: 'processando envio…', tom: 'proc' });
  assert.deepStrictEqual({ ...ctx.drChipObstaculos(obst, [{ tipo: 'obstaculos', status: 'erro' }], hoje) },
    { texto: 'erro no último envio', tom: 'erro' });
  // envio de outro tipo não conta; erro antigo seguido de ok não conta (o primeiro é o mais novo)
  assert.strictEqual(ctx.drChipObstaculos(obst, [{ tipo: 'ajuste', status: 'erro' }], hoje).tom, 'ok');
  assert.strictEqual(ctx.drChipObstaculos(obst, [{ tipo: 'obstaculos', status: 'ok' }, { tipo: 'obstaculos', status: 'erro' }], hoje).tom, 'ok');
  assert.deepStrictEqual({ ...ctx.drChipObstaculos([obst[0]], [], hoje) }, { texto: '1 classe · 30/09/26', tom: 'ok' });
  assert.deepStrictEqual({ ...ctx.drChipObstaculos([], [], hoje) }, { texto: 'sem cadastro', tom: 'velho' });
});

test('escopo por talhão: cada um com a sua fonte; Shape sem envio é erro', () => {
  const sel = new Map([[10, 'shape'], [3, 'sistema'], [6, 'sistema']]);
  const e = ctx.drEscopo(sel, new Set([12, 4]), 77);
  assert.strictEqual(JSON.stringify(e), JSON.stringify({
    incluir: [{ talhao: 3, fonte: 'sistema' }, { talhao: 6, fonte: 'sistema' }, { talhao: 10, fonte: 'shape', envio_id: 77 }],
    remover: [4, 12] }));
  assert.throws(() => ctx.drEscopo(sel, new Set(), null), /shape de ajuste/);
  assert.strictEqual(JSON.stringify(ctx.drEscopo(new Map([[3, 'sistema']]), new Set(), null)),
    JSON.stringify({ incluir: [{ talhao: 3, fonte: 'sistema' }], remover: [] }));
});

test('indicadores da prévia: diferença para a vigente; Catação sem cobertura', () => {
  const r = { aplicacao_ha: 412.8, cobertura_pct: 94 };
  assert.deepStrictEqual({ ...ctx.drIndicadoresPrevia(r, { area_ha: 341.4, cobertura_pct: 82 }, 'normal') },
    { area: 412.8, deltaArea: 412.8 - 341.4, cob: 94, cobAntes: 82 });
  assert.deepStrictEqual({ ...ctx.drIndicadoresPrevia(r, { area_ha: 20 }, 'catacao') },
    { area: 412.8, deltaArea: 412.8 - 20, cob: null, cobAntes: null });
  assert.deepStrictEqual({ ...ctx.drIndicadoresPrevia(r, null, 'normal') },        // primeira revisão
    { area: 412.8, deltaArea: null, cob: 94, cobAntes: null });
  assert.deepStrictEqual({ ...ctx.drIndicadoresPrevia(null, null, 'normal') },
    { area: null, deltaArea: null, cob: null, cobAntes: null });
});

test('situação do talhão na lista da revisão', () => {
  assert.strictEqual(ctx.drSituacaoTalhao({ status: 'sem_projeto' }), 'sem projeto');
  assert.strictEqual(ctx.drSituacaoTalhao({ status: 'com_projeto', desde_rev: 1 }), 'refazer Rev1');
  assert.strictEqual(ctx.drSituacaoTalhao({ status: 'com_projeto', desde_rev: 0 }), 'refazer Rev0');
});

test('tempo decorrido da geração', () => {
  const t0 = Date.parse('2026-10-29T14:00:00Z');
  assert.strictEqual(ctx.drDecorrido('2026-10-29T14:00:00Z', t0 + 45e3), '45 s');
  assert.strictEqual(ctx.drDecorrido('2026-10-29T14:00:00Z', t0 + 72e3), '1 min 12 s');
  assert.strictEqual(ctx.drDecorrido('2026-10-29T14:00:00Z', t0 + 3900e3), '1 h 05 min');
  assert.strictEqual(ctx.drDecorrido('2026-10-29T14:00:00Z', t0 - 5e3), '0 s');    // relógio adiantado
  assert.strictEqual(ctx.drDecorrido(null, t0), '');
});

test('linha de contexto da solicitação', () => {
  assert.strictEqual(ctx.drContextoSol({ solicitante: 'Ana', observacao: 'Completar talhões do bloco norte', data_desejada: '2026-11-05' }),
    'Solicitação de Ana · “Completar talhões do bloco norte” · para 05/11');
  assert.strictEqual(ctx.drContextoSol({ solicitante: 'Ana' }), 'Solicitação de Ana');
  assert.strictEqual(ctx.drContextoSol({ observacao: 'x' }), 'Solicitação · “x”');
  assert.strictEqual(ctx.drContextoSol(null), '');
});

test('camadas de um envio: nomes-base únicos, sem pasta nem extensão', () => {
  assert.deepStrictEqual([...ctx.drCamadasEnvio({ arquivos: ['10372/1/manchas_buva.shp', '10372/1/manchas_buva.dbf',
    '10372/1/manchas_buva.SHX', '10372/1/manchas_capim.shp', '10372/1/pacote.zip'] })], ['manchas_buva', 'manchas_capim', 'pacote']);
  assert.deepStrictEqual([...ctx.drCamadasEnvio(null)], []);
});
```

- [x] **Passo 2: rodar e ver falhar:** `node --test tests/app/*.test.js`. Esperado: os 9 testes novos falham com "is not a function".
- [x] **Passo 3: implementar** em `app/drone-dados.js`, numa seção `// ── área da fazenda (S4) ──`, depois de `drTalhoesGerando`:

```js
const drPublicando=ger=>!!(ger&&ger.publicar_pedido_em&&!ger.publicacao_erro);
function drEtapaAtiva(sol,ger){
  if(!ger)return 0;
  if(ger.status==='pronta')return drPublicando(ger)?3:2;
  return 1;                                            // fila, processando ou erro
}
function drEstadoPainel({doc,sol,ger,edita}){
  if(!edita)return'consulta';
  if(ger){
    if(drPublicando(ger))return'publicando';
    if(ger.status==='fila'||ger.status==='processando')return'gerando';
    if(ger.status==='erro')return'erro';
    if(ger.status==='pronta')return'previa';
  }
  return doc==='catacao'?'catacao':'montando';
}
function drDataCurta(iso){return new Date(iso).toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit',year:'2-digit'});}
function drChipObstaculos(obst,envios,hoje,meses=24){
  const ult=drUltimoEnvio(envios,'obstaculos');
  if(ult&&['fila','processando'].includes(ult.status))return{texto:'processando envio…',tom:'proc'};
  if(ult&&ult.status==='erro')return{texto:'erro no último envio',tom:'erro'};
  const o=obst||[];if(!o.length)return{texto:'sem cadastro',tom:'velho'};
  const limite=new Date(hoje);limite.setMonth(limite.getMonth()-meses);
  const datas=o.map(v=>new Date(v.enviado_em)),recente=new Date(Math.max(...datas));
  return{texto:`${o.length} classe${o.length>1?'s':''} · ${drDataCurta(recente)}`,tom:datas.some(d=>d<limite)?'velho':'ok'};
}
function drEscopo(sel,rem,ajusteId){
  const inc=[...sel].sort((a,b)=>a[0]-b[0]);
  if(inc.some(([,f])=>f==='shape')&&!ajusteId)throw new Error('Envie o shape de ajuste antes de gerar.');
  return{incluir:inc.map(([t,f])=>f==='shape'?{talhao:t,fonte:'shape',envio_id:ajusteId}:{talhao:t,fonte:'sistema'}),
    remover:[...rem].sort((a,b)=>a-b)};
}
function drIndicadoresPrevia(resumo,vigente,doc){
  const n=x=>typeof x==='number'?x:null,r=resumo||{},v=vigente||{},normal=doc==='normal';
  const area=n(r.aplicacao_ha),antes=n(v.area_ha);
  return{area,deltaArea:area!=null&&antes!=null?area-antes:null,cob:normal?n(r.cobertura_pct):null,cobAntes:normal?n(v.cobertura_pct):null};
}
function drSituacaoTalhao(p){return p.status==='sem_projeto'?'sem projeto':'refazer Rev'+p.desde_rev;}
function drDecorrido(desde,agora){
  if(!desde)return'';
  const s=Math.max(0,Math.floor((agora-Date.parse(desde))/1000));
  if(s<60)return s+' s';
  if(s<3600)return`${Math.floor(s/60)} min ${s%60} s`;
  return`${Math.floor(s/3600)} h ${String(Math.floor(s%3600/60)).padStart(2,'0')} min`;
}
function drContextoSol(c){
  if(!c)return'';
  const p=['Solicitação'+(c.solicitante?' de '+c.solicitante:'')];
  if(c.observacao)p.push(`“${c.observacao}”`);
  if(c.data_desejada)p.push('para '+new Date(c.data_desejada+'T12:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'}));
  return p.join(' · ');
}
function drCamadasEnvio(env){
  return[...new Set(((env&&env.arquivos)||[]).map(a=>a.split('/').pop().replace(/\.[^.]+$/,'')))];
}
```

  `drPodeCancelar` e `drOcupado` passam a usar `drPublicando` (mesma regra, sem repetir a expressão).
- [x] **Passo 4: rodar:** `node --test tests/app/*.test.js`. Esperado: tudo passando.
- [x] **Passo 5: commit** — `Drone S4.1: regras puras da area da fazenda (etapa, estado do painel, chip de obstaculos, escopo por talhao, indicadores da previa)`

## S4.2 Dados que a tela nova precisa

**Arquivo:** `app/drone-fazenda.js` (`drCarregarFazenda`)

- [ ] **Passo 1:** acrescentar aos selects (sem mudar a ordem das chamadas nem as checagens de `drRespostaValida`):
  - `drone_solicitacoes`: `data_desejada,criado_em`
  - `drone_geracoes`: `pedido_em,iniciado_em` (`alertas` e `resumo` já vêm)
  - `drone_envios`: `arquivos,classe_m`
- [ ] **Passo 2:** `drAssinaturas.painel` passa a incluir `DR.ajusteId` e o estado das ferramentas (`DR.modoRemover`), para o painel redesenhar quando eles mudam pelo polling. `enviado_em` continua fora. Ajustar o teste `assinaturas: painel ignora enviado_em…` se ele comparar a lista exata.
- [ ] **Passo 3:** `node --test tests/app/*.test.js` passando. Commit — `Drone S4.2: fazenda busca datas da solicitacao, tempos da geracao e arquivos dos envios`

## S4.3 Cabeçalho, barra de etapas e menu ⋯

**Arquivos:** `app/drone-fazenda.js`, `app/drone.css`. Referência visual: tela 2, faixa de cima.

- [ ] **Passo 1: `drCabecalhoHtml()`** (`#dr-ph`), da esquerda para a direita: `← Início` (`driVoltar()`), separador, código (`.dr-cod`), nome + "N talhões · X ha", abas **Normal** `RevN · NN%` e **Catação** `RevN` (ou "sem projeto"), em `<nav aria-label="Documento">` com `<button>` e `aria-pressed`. À direita: botão **Obstáculos** com o chip de `drChipObstaculos(DR.info.obst, DR.info.envios, new Date())` (classe `tom-ok|tom-velho|tom-erro|tom-proc`; em `proc` o ícone vira o indicador girando em CSS) e botão **⋯** (`aria-label="Mais ações"`, `aria-haspopup="menu"`). Para quem não edita, Obstáculos é um `<span>` com o chip, sem ação.
- [ ] **Passo 2: menu ⋯** (`drMenuAbrir()`): lista pequena ancorada no botão com **Revisões** (abre `drRevisoesAbrir()`) e **Cancelar solicitação** (só quando `drPodeCancelar(sol, ger, EU)`; chama `drCancelar(sol.id)`). Fecha com Esc, clique fora ou escolha. Revisões aparece para todos.
- [ ] **Passo 3: `drRevisoesAbrir()`**: gaveta lateral com a aparência de `.dri-gaveta`, título "Revisões · Normal" (do documento aberto) e uma linha por revisão: `RevN · data · motivo`. Vazia: "Nenhuma revisão publicada ainda.". Fecha com Esc, × e clique no fundo, e devolve o foco ao botão ⋯.
- [ ] **Passo 4: `drEtapasHtml()`** (`#dr-etapas`): quatro passos (Montar revisão, Gerar prévia, Conferir, Publicado); os anteriores à ativa com ✓ verde e trilho azul; a ativa com número em azul (ou indicador girando, com o texto "Gerando prévia", quando o estado é `gerando`; "Publicando" no `publicando`). À direita, `drContextoSol` do cartão de `DR.painel` com o mesmo `id` da solicitação aberta. Escondida no estado `catacao` (decisão 4). Cada passo com `data-etapa="0..3"`. Ao mudar de etapa entre ciclos, chamar `Mo.etapa(#dr-etapas, de, para)` (contrato atual de `app/motion.js`, sem mudar) depois de trocar as classes; na primeira montagem, sem animação.
- [ ] **Passo 5: assinaturas.** O cabeçalho passa a depender também de `info.envios` (chip) e de `info.obst`; a barra de etapas, de `drEstadoPainel` + `drEtapaAtiva` + contexto. Acrescentar em `drAssinaturas` uma parte `etapas` e redesenhá-la em `drDesenhar` só quando muda.
- [ ] **Passo 6: commit** — `Drone S4.3: cabecalho com abas e chip de obstaculos, menu de acoes, revisoes em gaveta e barra de etapas`

## S4.4 Mapa: ferramentas, camadas e legenda

**Arquivos:** `app/drone-fazenda.js` (`drEsqueleto`, `drClicarTalhao`, `drSelecionarSemProjeto`), `app/drone.css`. Referência: tela 2, mapa.

- [ ] **Passo 1: `drEsqueleto()`** monta: `#dr-ph`, `#dr-etapas`, e `.dr-trab` com `.dr-mapa-box` (contém `#dr-map`, `#dr-ferr`, `#dr-dica`, `#dr-camadas`, `#dr-leg`) e `<aside id="dr-side" aria-label="Painel">` com `#dr-side-corpo` (rola) e `#dr-side-rodape` (fixo). Painel com 360 px (340–380 da spec), mapa ocupando o resto; abaixo de 900 px o painel desce para baixo do mapa.
- [ ] **Passo 2: barra de ferramentas flutuante** (`drFerramentasHtml()`, `role="toolbar"`), só nos estados `montando`: **Incluir** e **Remover** (alternam `DR.modoRemover`, com `aria-pressed`), separador, **Sem projeto** (`drSelecionarSemProjeto`) e **Limpar** (zera `DR.sel` e `DR.rem`). Função única `drFerramenta(qual)`. Fora do `montando` a barra some.
- [ ] **Passo 3: dica do topo** (`#dr-dica`): `montando` → "Clique nos talhões para incluir ou refazer" (ou "…para remover" com Remover ativo); `gerando` → ícone de cadeado + "Mapa travado enquanto a prévia é gerada. Pode navegar e dar zoom."; nos outros estados, escondida.
- [ ] **Passo 4: Camadas** (`#dr-camadas`): botão "Camadas" abaixo do zoom do MapLibre; abre uma caixinha com o checkbox **Obstáculos** ligado a `drObstaculos(ligar)`. No estado `previa` o botão mostra "Camadas · obstáculos ligados" e os obstáculos ligam sozinhos uma vez por prévia (guardar `DR.obstPrevia=ger.id`; se o usuário desligar, não religa no polling). Sai o checkbox da legenda.
- [ ] **Passo 5: legenda compacta** (`#dr-leg`), embaixo à esquerda, muda com o estado: `montando` → aplicação vigente, sem projeto, na revisão, fora da Base; `previa` → novo nesta prévia (contorno verde), já publicado, ● 15 m ● 25 m ● 50 m; Catação → Catação vigente (RevN). As cores saem de `DR_COR`/`DR_OBS_COR`.
- [ ] **Passo 6: "novo nesta prévia"** (decisão 5): na camada `tal-l`, feature-state `novo` (talhões de `ger.escopo.incluir` com a geração `pronta`) com contorno `#2f7a3e` e largura 2,5. Preencher em `drAtualizarSelecaoMapa`.
- [ ] **Passo 7: restilizar** o `NavigationControl` (cantos 10 px, sombra da maquete) só com CSS em `.dr-mapa-box .maplibregl-ctrl-group`.
- [ ] **Passo 8: commit** — `Drone S4.4: ferramentas flutuantes no mapa, dica, menu Camadas, legenda por estado e destaque do que e novo na previa`

## S4.5 Painel por estado

**Arquivos:** `app/drone-fazenda.js`, `app/drone-previa.js`, `app/drone.css`. Referências: telas 2 (montando), 4 (gerando), 5 (prévia), 6 (catação).

`drPainelLateral()` calcula `est=drEstadoPainel({doc:DR.doc,sol,ger,edita:podeEditar('drone')})`, chama `drPainel_<est>()` que devolve `{titulo, sobre, corpo, rodape}` e grava em `#dr-side` (cabeçalho com o "sobre" em caixa alta e o título), `#dr-side-corpo` e `#dr-side-rodape`. Rodapé vazio → escondido. A linha de erro `#dr-err` fica dentro do rodapé, logo acima do botão, e `drErro` continua escrevendo nela; ela é limpa no começo de cada ação (`drLimparErro()` no início de `drGerarNormal`, `drGerarCatacao`, `drPublicar`, `drDescartar`, `drEnviar`, `drAbrirCatacao`).

- [ ] **Passo 1: `montando`** — sobre "Nova revisão", título "Normal · Rev{N+1}". "Incluir ou refazer · K talhões" com a soma das áreas à direita; uma linha por talhão (`.dr-linha`): chip com o número, `drSituacaoTalhao · X ha`, e o seletor **Sistema | Shape** daquele talhão (`drFonteTalhao(n,'sistema'|'shape')`, dois `<button aria-pressed>`). Lista vazia: "Nenhum talhão. Clique no mapa.". Se algum está em Shape: área de arrastar (`.dr-solta`, aceita soltar arquivos e clique) "Arraste o shape de ajuste dos talhões 10, 12" + ".shp + .shx + .dbf + .prj, ou .zip" + a situação de `drRotuloShape` do envio `DR.ajusteId`; soltar ou escolher chama o mesmo fluxo de `drEnviar('ajuste')` com os arquivos já escolhidos (separar `drEnviarArquivos(tipo, arqs, lugar)` de `drEnviar`). "Remover · nenhum" ou os chips vermelhos, com a nota "Use a ferramenta Remover no mapa.". Nota com ícone info: "A prévia mostra a fazenda inteira: os talhões de antes e os novos. Você confere antes de publicar." Rodapé: **Gerar prévia**, habilitado com algo a incluir ou remover. Sai `DR.fonte` e `drFonte`: um talhão novo entra como Sistema.
- [ ] **Passo 2: `drGerarNormal`** usa `drEscopo(DR.sel, DR.rem, DR.ajusteId)` (o erro de Shape sem envio aparece na linha de erro).
- [ ] **Passo 3: `catacao`** — sobre "Nova Catação", título "Catação · Rev{N+1}", subtítulo "Um levantamento novo substitui a Catação inteira." Passos numerados (`<ol>`): (1) **Solicitação aberta** + "Solicitante · quando" (do cartão do painel), ou o botão **Abrir Catação desta fazenda** com o passo em azul; (2) **Enviar infestação**: área de arrastar (`drEnviarArquivos('infestacao', …)`) ou, depois de enviado, "Infestação enviada · N camadas · quando" + uma linha por `drCamadasEnvio` do último envio de infestação + **Trocar arquivos**; com o envio em processamento, a situação "processando…"; com erro, a mensagem; (3) **Gerar prévia** + "Agrupa as manchas, recorta pelos talhões e tira os obstáculos." Passo feito = ✓ verde, passo atual = número azul. Rodapé: **Gerar prévia** (`drPodeGerarCatacao(sol)`).
- [ ] **Passo 4: `gerando`** — sobre "Normal · Rev{N+1}" (ou Catação), título "Gerando a prévia". Cartão `.drp-gerando` com "O agente está processando" (ou "Esperando o agente pegar o pedido" na fila) e o tempo `drDecorrido(ger.pedido_em, Date.now())` à direita, trilho (`Mo.trilho`, já chamado por `drAnimGeracao`) e os três passos *Pedido recebido → Processando → Prévia pronta para conferir* (fila: o 1º girando; processando: 1º ✓ e 2º girando). Resumo: Incluir ou refazer (números ou "Catação inteira"), Remover, "Pedido em" (hora de `pedido_em`). Nota com sininho: "Pode sair desta tela. Quando a prévia ficar pronta, ela aparece em **A analisar** e no sininho." Sem rodapé. O tempo decorrido atualiza no lugar a cada 1 s com um `setInterval` próprio, criado só neste estado e parado ao sair dele e em `drMapaDescartar` (sem redesenhar o cartão, para o trilho não reiniciar).
- [ ] **Passo 5: `previa`** — sobre "Prévia · Normal Rev{N+1}", título "Confira antes de publicar". Capa do PDF (`<button class="drp-capa" id="dr-pdf">`, mesma chamada `drMostrarPdf(ger)` de hoje) com o selo **Abrir prévia** (`drPrevAbrir()`). Dois indicadores (`drIndicadoresPrevia(ger.resumo, {area_ha: DR.geo[DR.doc]?.area_ha, cobertura_pct: DR.geo.cobertura_pct}, DR.doc)`): "Área de aplicação" `X ha` com `+ Y ha`/`− Y ha` (verde/vermelho) ou "primeira revisão"; "Cobertura da fazenda" `NN%` com "antes NN%" (só Normal). Lista "N alertas" com o texto de cada um de `ger.alertas` (ícone `history` para os que falam de meses, `wrong_location` para "fora", `warning` nos outros); sem alertas: "Sem alertas.". Falha de publicação anterior (`publicacao_erro`): linha de erro "Falha ao publicar: …". Campo **Motivo da revisão** (`<label>` + `<input class="dr-mot-painel">`, valor e `oninput` em `DRP.motivo[ger.id]`). Rodapé: **Descartar** (borda vermelha) e **Publicar no portal** (principal).
- [ ] **Passo 6: `drPublicar`** lê `DRP.motivo[id]` (decisão 8). Na janela de prévia (`drone-previa.js`), o `#dr-mot` continua, lendo e gravando o mesmo `DRP.motivo`.
- [ ] **Passo 7: `publicando`** — título "Publicando no portal", texto "O agente está subindo os arquivos para o portal. Pode sair desta tela." Sem rodapé. O voo (`drVooPublicacao`) segue igual.
- [ ] **Passo 8: `erro`** — título "Erro na geração", a mensagem do agente (`ger.erro`) numa caixa de erro e, no rodapé, **Descartar e montar de novo** (`drDescartar`).
- [ ] **Passo 9: `consulta`** — título "Normal · RevN vigente" (ou "sem projeto"); uma linha com a situação (`drEstadoPainel` com `edita:true` diz qual: montando/catacao → "Sem pedido em andamento" ou "Solicitação aberta"; gerando → "Gerando prévia…"; previa → "Prévia pronta, aguardando conferência"; publicando → "Publicando…"; erro → "A última geração deu erro"); a linha de contexto da solicitação, se houver; a nota "Somente consulta. Peça acesso de editor ao administrador para alterar." Sem rodapé, sem ferramentas, clique no talhão não faz nada (já é assim em `drClicarTalhao`).
- [ ] **Passo 10: o polling não apaga nada (Foco 1).** O painel só é redesenhado quando a assinatura `painel` muda; ao redesenhar, os valores vêm do estado (`DR.sel`, `DR.rem`, `DRP.motivo`), nunca do DOM antigo. Guardar o foco: se o elemento focado tem `data-foco`, refocá-lo depois do redesenho, com a mesma posição do cursor.
- [ ] **Passo 11: sai o que ficou velho:** `drObstaculosHtml` (substituída pelo chip), o histórico no painel (foi para a gaveta), o "Cancelar" no painel (foi para o ⋯), `drPrevHtml` (os estados de geração agora são do painel; conferir com grep que ninguém mais chama). Classes CSS sem uso saem de `drone.css`.
- [ ] **Passo 12:** `node --test tests/app/*.test.js` passando e `python tests/app/teste_movimento.py` passando. Commit — `Drone S4.5: painel com um estado por vez (montando, catacao, gerando, previa, publicando, erro, consulta) e fonte por talhao`

## S4.6 Demo para a conferência visual

**Arquivo:** `app/drone-fazenda-demo.html` (mesmo padrão de `app/drone-inicio-demo.html`)

- [ ] **Passo 1:** página que carrega `motion.css`, `drone.css`, MapLibre (a mesma versão do `index.html`), `motion.js`, `drone-dados.js`, `drone-previa.js`, `drone-inicio.js` e `drone-fazenda.js`, com globais falsas (`EU`, `esc`, `fmtNum`, `podeEditar` lendo `?editar=0`, `confirmar`, `sb` e `drRpc` falsos que devolvem fixtures) e uma fazenda fictícia de 12 talhões quadrados (fora da Base: 7; sem projeto: 3, 6, 11; Rev1 no 10). `?estado=montando|catacao|catacao-enviada|gerando|previa|publicando|erro` escolhe a fixture; o chip de Obstáculos varia com `?obst=ok|velho|erro|proc`. Nada é gravado: as ações só mostram um aviso no console. A capa do PDF fica no placeholder (sem PDF real).
- [ ] **Passo 2:** abrir servindo `app/` por http (`python -m http.server` na pasta `app/`) e conferir que todos os estados abrem sem erro no console.
- [ ] **Passo 3: commit** — `Drone S4.6: demo da area da fazenda com um estado por parametro`

## S4.7 Teste de tela

**Arquivo:** `tests/app/teste_drone_tela.py` (ampliar; continua só com a 10974 livre)

- [ ] **Passo 1:** depois de abrir a fazenda 10974 como editor: confere `#dr-etapas` com a etapa 1 ativa, a barra `#dr-ferr` visível e o chip de Obstáculos com texto. Clica em dois talhões, troca um para Shape: aparece `.dr-solta`; Gerar prévia fica habilitado. Força um ciclo (`await drCicloFazenda()` via `page.evaluate`) e confere que os dois talhões continuam na lista e o Shape continua marcado (Foco 1).
- [ ] **Passo 2:** volta o talhão para Sistema, gera a prévia (o teste já faz isso) e confere: estado `gerando` (título "Gerando a prévia", `#dr-ferr` escondida, `#dr-dica` com "travado", tempo decorrido mudando entre duas leituras com 2 s de diferença). Na prévia pronta: indicadores com "ha", o campo Motivo; digita "teste S4", força um ciclo e confere que o valor continua (Foco 1). Depois **Descartar** (como hoje).
- [ ] **Passo 3: só leitura (Foco 4):** muda o `papel` da conta para `leitura` (e tira o `usuario_modulos` do drone, se o teste o criou), recarrega o app, abre a 10974 e confere: painel com "Somente consulta", nenhum `button` dentro de `#dr-side`, `#dr-ferr` ausente, Obstáculos sem `onclick`, ⋯ só com Revisões; clicar num talhão não muda nada. O `finally` que já existe devolve o papel original (conferir que cobre este caminho também).
- [ ] **Passo 4:** rodar com a conta de teste (ver a memória `reference-conta-teste-hub`). Esperado: todos os ✓, nenhuma falha.
- [ ] **Passo 5: commit** — `Drone S4.7: teste de tela cobre etapas, fonte por talhao, polling sem perder motivo e selecao, e usuario so leitura`

## S4.8 Conferência visual, verificação e revisão

- [ ] **Passo 1: demo × maquete:** abrir `drone-fazenda-demo.html` em cada `?estado=` (e `?editar=0`) no navegador, a 1440×900, e comparar lado a lado com as telas 2, 4, 5 e 6. Anotar e corrigir diferenças de layout, cor, texto e ordem. Conferir também a 390 px de largura (painel desce, nada vaza na horizontal) e com `prefers-reduced-motion`.
- [ ] **Passo 2: app real logado:** abrir a 10974 como editor (montando; Catação; gerar → gerando → prévia → descartar) e como só leitura (papel `leitura`, restaurado no fim), comparando com a maquete. Console sem erro novo.
- [ ] **Passo 3:** `verification-before-completion` (testes puros, teste de tela, teste de movimento, carga sem login sem erro).
- [ ] **Passo 4:** `requesting-code-review` do diff `main...drone-s4`, com atenção aos itens 1 e 4 do "Foco da revisão" do plano geral, e `receiving-code-review` para os achados.
- [ ] **Passo 5:** registro no fim deste arquivo (o que cada camada da delegação fez) e **ok do usuário antes de mesclar na `main` e enviar** (push com a troca de conta do `gh`, memória `reference-github-contas-push`).
- [ ] **Passo 6:** atualizar a memória `project-drone-telas-redesenho` (estado da execução; próxima S5).

---

## Registro da execução

(preencher ao fim)
