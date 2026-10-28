# Drone S3 — Migration do painel e Início do Drone (plano em passos)

> **Para quem executa:** detalhamento da seção S3 de [2026-10-27-drone-telas-redesenho.md](2026-10-27-drone-telas-redesenho.md). Branch `drone-s3` (worktree `../hub-geotech-drone-s3`), criado a partir de `drone-s2` porque a S2 ainda não foi mesclada. Execução com a skill `delegar`, seguindo `test-driven-development`. Marque as caixas conforme avança.

**Objetivo:** trocar a fila lateral do Drone pela tela de Início da maquete (tela 1): três colunas da esteira, faixa "Atenção na base" com lista lateral e navegação Início ↔ fazenda. A área da fazenda continua a de hoje (o redesenho dela é a S4).

**Spec:** §3.1 e §6 de [2026-10-27-drone-telas-redesenho-design.md](../specs/2026-10-27-drone-telas-redesenho-design.md) · Maquete, tela 1 (`Main.dc.html`): https://claude.ai/artifact/HGJ6zku4ABshgCFSzmDJup

**Arquivos:**
- Criar: `supabase/migrations/20261028090000_drone_painel_inicio.sql`
- Reescrever: `app/drone-inicio.js` (Início inteiro; `drNovaSolicitacao`, `drCancelar` e `drIrFazenda` ficam, com ajustes)
- Modificar: `app/drone.css` (sai o grid `330px 1fr` do `#drone-root`; entram as classes `dri-*`), `app/drone-fazenda.js` (só as linhas que citam `#dr-fila`), `app/index.html` (só se o gancho de `trocar` precisar), `docs/drone-manual.md` (parágrafo do Início)
- Testes: `tests/app/drone_puro.test.js`, `tests/app/teste_drone_tela.py`

**Decisões tomadas neste detalhamento (conferir):**
1. A geração no painel traz também `concluido_em`, além de `pedido_em` e `iniciado_em` da spec. Sem ele o cartão "A analisar" não consegue dizer "gerada há 20 min", como na maquete. O agente já grava `concluido_em` quando a prévia fica pronta (`drone/banco.py:79`).
2. O "Rev3" da maquete fica de fora: o painel não sabe o número da revisão e a spec não pede.
3. O × de cancelar some do cartão (a maquete não tem). Cancelar continua no painel da fazenda (`drone-fazenda.js:278`).
4. A migration é aplicada pelo SQL Editor, como as anteriores do Drone (você cola). Não uso `supabase db push`, porque ele empurraria qualquer migration pendente junto.
5. O front lê `obstaculos_antigos`/`fora_da_base` nos dois formatos (código solto ou `{cod_faz, fazenda}`), para a tela não quebrar entre o merge e a migration.
6. O tempo decorrido ("1 min", "há 2 dias") é atualizado no lugar a cada ciclo, sem redesenhar o cartão, para o trilho animado não reiniciar.

**Interfaces produzidas (`app/drone-inicio.js`):**
- `driColuna(sol) → 'solicitacoes'|'desenvolvimento'|'analisar'`
- `driSituacao(sol) → {ico, txt, cls} | null` (linha do meio do cartão; `cls` em `''|'aviso'|'erro'|'ok'|'vivo'`)
- `driDesde(iso, agora) → string` ("agora", "5 min", "3 h", "2 dias") e `driQuando(iso, agora) → string` ("hoje", "ontem", "há 4 dias")
- `driAndamento(painel) → boolean` (há geração em fila/processando ou publicação pedida sem erro → polling de 10 s)
- `driAtencaoItens(painel, chave) → [{cod_faz, fazenda, extra}]` (aceita os dois formatos)
- `driCartaoHtml(sol, {editor, agora}) → string` (com `data-id`)
- `driPlano(atuais:[{id,ass}], novos:[{id,ass}]) → {remover, trocar, inserir}` (ids; a ordem final é a de `novos`)
- DOM: `driDesenhar(painel)`, `driAtencaoAbrir(chave)`, `driAtencaoFechar()`, `driAbrirFazenda(cod, tipo, {obstaculos})`, `driVoltar()`

---

## S3.1 Migration do painel (precisa do ok do usuário antes de aplicar)

- [ ] **Passo 1: escrever** `supabase/migrations/20261028090000_drone_painel_inicio.sql`: `create or replace function hub.drone_painel()` copiando a de `20261009090000_drone_melhorias.sql` e mudando só:

```sql
-- em 'geracao' (jsonb_build_object do cartão), acrescentar:
'pedido_em', g.pedido_em, 'iniciado_em', g.iniciado_em, 'concluido_em', g.concluido_em

-- no topo:
'publicadas_7d', (select count(*) from hub.drone_geracoes
                   where status = 'publicada' and concluido_em > now() - interval '7 days'),

-- obstaculos_antigos: de lista de códigos para [{cod_faz, fazenda}]
'obstaculos_antigos', coalesce((select jsonb_agg(jsonb_build_object('cod_faz', x.cod_faz, 'fazenda', f.nome) order by f.nome)
                          from (select distinct v.cod_faz from hub.drone_obstaculo_versoes v
                                 where v.vigente and v.enviado_em < now() - make_interval(
                                         months => (select valor::int from hub.drone_parametros
                                                     where chave = 'alerta_obstaculos_meses'))) x
                          join hub.fazendas f on f.cod_faz = x.cod_faz), '[]'::jsonb),

-- fora_da_base: mesmo formato, mesmo filtro de hoje dentro do subselect distinct
```

  Cabeçalho do arquivo com uma linha dizendo o que muda e que a função antiga está em `20261009090000_drone_melhorias.sql` (para voltar atrás, basta rodar aquela definição de novo).
- [ ] **Passo 2: conferir a sintaxe** com `pglast` (se não houver, `pip install pglast` no scratchpad): `python -c "import pglast,sys;pglast.parse_sql(open(sys.argv[1]).read());print('SQL ok')" supabase/migrations/20261028090000_drone_painel_inicio.sql`. Esperado: `SQL ok`.
- [ ] **Passo 3: commit** — `Drone S3.1: drone_painel traz tempos da geracao, publicadas_7d e nome da fazenda nas listas de atencao`
- [ ] **Passo 4: PARAR e pedir o ok do usuário.** Com o ok, o usuário cola o arquivo no SQL Editor.
- [ ] **Passo 5: conferir no banco** (SQL Editor ou RPC logado): `select jsonb_typeof(hub.drone_painel()->'publicadas_7d'), hub.drone_painel()->'obstaculos_antigos'->0, hub.drone_painel()->'solicitacoes'->0->'geracao';`. Esperado: `number`, um objeto com `cod_faz` e `fazenda`, e a geração (se houver) com `pedido_em`.

## S3.2 Regras puras do Início (TDD)

Em `tests/app/drone_puro.test.js` o contexto do `vm` ganha `esc` (o mesmo de `index.html`), porque `driCartaoHtml` usa.

- [ ] **Passo 1: testes que falham**

```js
ctx.esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

test('coluna do Início segue a esteira (spec §3.1)', () => {
  const c = g => ctx.driColuna({ status: 'em_elaboracao', geracao: g });
  assert.strictEqual(ctx.driColuna({ status: 'solicitado', geracao: null }), 'solicitacoes');
  assert.strictEqual(ctx.driColuna({ status: 'em_elaboracao', geracao: null }), 'solicitacoes');
  assert.strictEqual(ctx.driColuna({ status: 'aguardando_obstaculos' }), 'solicitacoes');
  assert.strictEqual(c({ status: 'fila' }), 'desenvolvimento');
  assert.strictEqual(c({ status: 'processando' }), 'desenvolvimento');
  assert.strictEqual(c({ status: 'erro', erro: 'x' }), 'desenvolvimento');
  assert.strictEqual(c({ status: 'pronta', publicar_pedido_em: '2026-10-28T10:00Z' }), 'desenvolvimento');
  assert.strictEqual(c({ status: 'pronta', publicar_pedido_em: '2026-10-28T10:00Z', publicacao_erro: 'x' }), 'desenvolvimento');
  assert.strictEqual(c({ status: 'pronta' }), 'analisar');
});

test('situação do cartão', () => {
  const s = (status, g) => ctx.driSituacao({ status, geracao: g || null, observacao: 'obs' });
  assert.strictEqual(s('aguardando_obstaculos').txt, 'Aguardando obstáculos');
  assert.strictEqual(s('aguardando_infestacao').ico, 'pest_control');
  assert.strictEqual(s('solicitado').txt, 'obs');                       // sem pendência: a observação
  assert.strictEqual(ctx.driSituacao({ status: 'solicitado' }), null);   // nem observação: nada
  assert.strictEqual(s('em_elaboracao', { status: 'processando' }).cls, 'vivo');
  assert.match(s('em_elaboracao', { status: 'erro', erro: 'sem feições' }).txt, /^Erro na geração: sem feições/);
  assert.strictEqual(s('em_elaboracao', { status: 'pronta', publicar_pedido_em: 'x' }).txt, 'Publicando no portal…');
  assert.match(s('em_elaboracao', { status: 'pronta', publicar_pedido_em: 'x', publicacao_erro: 'falhou' }).txt, /^Erro ao publicar: falhou/);
  assert.strictEqual(s('em_elaboracao', { status: 'pronta', alertas: 2 }).txt, 'Prévia · 2 alertas');
  assert.strictEqual(s('em_elaboracao', { status: 'pronta', alertas: 1 }).txt, 'Prévia · 1 alerta');
  assert.strictEqual(s('em_elaboracao', { status: 'pronta', alertas: 0 }).cls, 'ok');
});

test('tempos curtos do cartão', () => {
  const agora = new Date('2026-10-28T15:00:00-03:00');
  assert.strictEqual(ctx.driDesde('2026-10-28T14:59:40-03:00', agora), 'agora');
  assert.strictEqual(ctx.driDesde('2026-10-28T14:55:00-03:00', agora), '5 min');
  assert.strictEqual(ctx.driDesde('2026-10-28T12:00:00-03:00', agora), '3 h');
  assert.strictEqual(ctx.driDesde('2026-10-26T15:00:00-03:00', agora), '2 dias');
  assert.strictEqual(ctx.driDesde(null, agora), '');
  assert.strictEqual(ctx.driQuando('2026-10-28T08:00:00-03:00', agora), 'hoje');
  assert.strictEqual(ctx.driQuando('2026-10-27T23:00:00-03:00', agora), 'ontem');
  assert.strictEqual(ctx.driQuando('2026-10-24T10:00:00-03:00', agora), 'há 4 dias');
});

test('polling do Início só com item andando', () => {
  const p = (...g) => ({ solicitacoes: g.map((x, i) => ({ id: i, status: 'em_elaboracao', geracao: x })) });
  assert.strictEqual(ctx.driAndamento(p(null, { status: 'pronta' })), false);
  assert.strictEqual(ctx.driAndamento(p({ status: 'erro' })), false);
  assert.strictEqual(ctx.driAndamento(p({ status: 'fila' })), true);
  assert.strictEqual(ctx.driAndamento(p({ status: 'pronta', publicar_pedido_em: 'x' })), true);
  assert.strictEqual(ctx.driAndamento(p({ status: 'pronta', publicar_pedido_em: 'x', publicacao_erro: 'e' })), false);
  assert.strictEqual(ctx.driAndamento(null), false);
});

test('itens da Atenção aceitam código solto (painel antigo) e objeto (painel novo)', () => {
  assert.deepStrictEqual([...ctx.driAtencaoItens({ fora_da_base: [10974] }, 'fora_da_base')].map(x => ({ ...x })),
    [{ cod_faz: 10974, fazenda: '', extra: '' }]);
  assert.deepStrictEqual({ ...ctx.driAtencaoItens({ obstaculos_antigos: [{ cod_faz: 1, fazenda: 'A' }] }, 'obstaculos_antigos')[0] },
    { cod_faz: 1, fazenda: 'A', extra: '' });
  assert.strictEqual(ctx.driAtencaoItens({ incompletas: [{ cod_faz: 2, fazenda: 'B', pct: 40 }] }, 'incompletas')[0].extra, '40%');
  assert.strictEqual(ctx.driAtencaoItens({}, 'incompletas').length, 0);
});

test('cartão: data-id, nome escapado e Conferir só para quem edita', () => {
  const sol = { id: 7, cod_faz: 10, fazenda: 'Faz <b>', tipo: 'catacao', status: 'em_elaboracao',
    criado_em: '2026-10-28T10:00Z', geracao: { status: 'pronta', alertas: 0, concluido_em: '2026-10-28T11:00Z' } };
  const agora = new Date('2026-10-28T12:00Z');
  const ed = ctx.driCartaoHtml(sol, { editor: true, agora });
  const le = ctx.driCartaoHtml(sol, { editor: false, agora });
  assert.match(ed, /data-id="7"/);
  assert.match(ed, /Faz &lt;b&gt;/);
  assert.match(ed, /Catação/);
  assert.match(ed, />Conferir</);
  assert.doesNotMatch(le, />Conferir</);
});

test('plano de reconciliação dos cartões por data-id', () => {
  const pl = ctx.driPlano([{ id: '1', ass: 'a' }, { id: '2', ass: 'b' }, { id: '3', ass: 'c' }],
                          [{ id: '2', ass: 'b' }, { id: '3', ass: 'X' }, { id: '4', ass: 'd' }]);
  assert.deepStrictEqual([...pl.remover], ['1']);
  assert.deepStrictEqual([...pl.trocar], ['3']);
  assert.deepStrictEqual([...pl.inserir], ['4']);
});
```

- [ ] **Passo 2: rodar e ver falhar** — `node --test tests/app/*.test.js`. Esperado: FAIL com `ctx.driColuna is not a function` (e os demais).
- [ ] **Passo 3: implementar** as funções puras no topo de `app/drone-inicio.js`, logo depois do comentário de cabeçalho:

```js
function driColuna(sol){
  const g=sol&&sol.geracao;
  if(!g)return'solicitacoes';
  if(['fila','processando','erro'].includes(g.status))return'desenvolvimento';
  if(g.status==='pronta')return g.publicar_pedido_em||g.publicacao_erro?'desenvolvimento':'analisar';
  return'solicitacoes';
}
```

  As demais seguem os testes. `driSituacao` usa os ícones da maquete (`warning`, `pest_control`, `error`, `flight`, `report`, `check_circle`); `fila` → "Na fila", `processando` → "Gerando prévia" (`cls:'vivo'`). `driDesde` arredonda para baixo (min < 60, h < 24, depois dias). `driQuando` compara datas de calendário no fuso local. `driCartaoHtml` segue a marcação da maquete (código, nome, chip Normal/Catação, situação, rodapé "solicitante · quando" / "para dd/mm" ou "gerada há …" + Conferir); o tempo vai num `<span data-desde="ISO">` (ou `data-quando`) para ser atualizado no lugar. O cartão é `<div class="dri-card" role="button" tabindex="0" data-id=… data-cod=… data-tipo=…>`; o Conferir é `<button>` com `event.stopPropagation()`.
- [ ] **Passo 4: rodar e ver passar** — `node --test tests/app/*.test.js`. Esperado: todos PASS (os 51 de antes + 7 novos).
- [ ] **Passo 5: commit** — `Drone S3.2: regras puras do Inicio (coluna, situacao, tempos, cartao, reconciliacao)`

## S3.3 Tela do Início

- [ ] **Passo 1: estrutura.** `droneIniciar` monta uma vez dentro de `#drone-root`:
  - `<div id="dri">`: cabeçalho (título "Drone", subtítulo "Projetos de voo por talhão", busca com `<kbd>/</kbd>` e `id="dr-busca"`, resultados em `#dr-busca-res` como menu suspenso sob a busca, botão Nova solicitação só para editor/solicitante como hoje); `<section class="dri-cols">` com três `<div class="dri-col" data-col="…">` (cabeçalho com ícone `inbox` / ponto `.dri-vivo` / `fact_check`, título e contador; lista `.dri-lista`; na coluna A analisar, rodapé `#dri-pub7`); faixa `#dri-atencao`.
  - `<div id="dr-trab" hidden>`: botão `← Início` (`onclick="driVoltar()"`) + o `#dr-faz` de hoje.
- [ ] **Passo 2: `drCarregarPainel()`** busca o RPC e chama `driDesenhar(DR.painel)`. Erro: mensagem `.dr-err` no lugar das colunas, sem apagar o que já estava desenhado se for um ciclo de polling. Depois: se `!DR.cod && driAndamento(DR.painel)` → `drPollIniciar(drCarregarPainel,10000)`; se `!DR.cod` e nada andando → `drPollParar()`. Com fazenda aberta não mexe no polling (quem manda é o da fazenda, 5 s).
- [ ] **Passo 3: `driDesenhar(painel)`** separa as solicitações por `driColuna`, ordena (Solicitações por `criado_em`; Em desenvolvimento por `pedido_em`; A analisar por `concluido_em`), monta `{id, ass:JSON.stringify(sol)+editor, html}` e aplica `driPlano` em cada coluna dentro de **um** `Mo.mover(section, aplicar)` (cartão que muda de coluna sai de uma e entra na outra; o FLIP anima). Cartão igual não é tocado. Coluna vazia: `<p class="dri-vazio">` ("Nenhuma solicitação aberta." / "Nada sendo gerado agora." / "Nenhuma prévia esperando conferência."). Contadores, `Publicadas nos últimos 7 dias: N` e a faixa Atenção são texto trocado no lugar. Por fim `driTempos()` reescreve todo `[data-desde]`/`[data-quando]`.
- [ ] **Passo 4: busca e atalho.** `drBuscar` continua igual (resultado em `#dr-busca-res`, clique → `driAbrirFazenda`). Atalho `/`: um `keydown` no `document` registrado uma vez (guardado com `if(document.addEventListener)` para o teste puro), que só age com a view do Drone visível, o Início à mostra e o foco fora de `input/textarea/select`. Esc com a busca focada limpa e fecha os resultados.
- [ ] **Passo 5: CSS** em `app/drone.css`: tirar o grid do `#drone-root`; classes `dri-*` seguindo a maquete (fundo das colunas `#f6f8fb`, cartão branco com borda `var(--bd)` e raio 12, chips Normal `#f4ece7/#7d4f35` e Catação `#e8f1e8/#3d6b3c`, borda vermelha `#f1c7c7` no erro, trilho `.dri-trilho`, `.dri-voa`, `.dri-vivo`), hover com sombra e `translateY(-1px)`, foco visível. Colunas viram uma só abaixo de 900 px. `@media (prefers-reduced-motion:reduce)` desliga trilho, pairar e pulso.
- [ ] **Passo 6: commit** — `Drone S3.3: Inicio com tres colunas, reconciliacao por cartao e polling de 10 s`

## S3.4 Faixa "Atenção na base" e lista lateral

- [ ] **Passo 1:** a faixa tem três `<button>` (ícones `incomplete_circle`, `history`, `wrong_location`; textos "Normais incompletas", "com obstáculos de mais de 24 meses", "com talhões fora da Base") e o link Ajuda (`docs/drone-manual.md`, como hoje). Contador zero deixa o botão apagado mas clicável.
- [ ] **Passo 2:** `driAtencaoAbrir(chave)` abre uma lista lateral à direita (`<aside class="dri-gaveta" role="dialog" aria-modal="true" aria-labelledby>` + fundo), com título, total e as linhas de `driAtencaoItens` (código, nome, `extra`). Fecha com o X, Esc ou clique no fundo; o foco vai para o X ao abrir e volta ao botão da faixa ao fechar. Entra deslizando 200 ms (sem animação com movimento reduzido).
- [ ] **Passo 3:** clique numa linha → `driAtencaoFechar()` e `driAbrirFazenda(cod, null, {obstaculos: chave==='obstaculos_antigos'})`. A opção só grava `DR.abrirObst=true`; a S5 usa (anotar no plano da S5).
- [ ] **Passo 4: commit** — `Drone S3.4: faixa Atencao na base com lista lateral`

## S3.5 Navegação e conferência

- [ ] **Passo 1:** `driAbrirFazenda(cod,tipo,op)`: esconde `#dri`, mostra `#dr-trab`, `drPollParar()` e chama `drAbrirFazenda(cod,tipo)`. `driVoltar()`: `drPollParar()`, `drMapaDescartar()`, `DR.cod=null`, mostra `#dri`, esconde `#dr-trab` e chama `drCarregarPainel()` (o Início não é remontado). Cartão e Conferir chamam `driAbrirFazenda(cod, tipo)`. `drIrFazenda(cod)` (sininho, Consultas) passa a chamar `driAbrirFazenda`. Em `drone-fazenda.js` sai a linha que marca `#dr-fila .dr-it.on`; `drCicloFazenda` e os botões continuam chamando `drCarregarPainel()` (que não liga o polling do Início com fazenda aberta). `drNovaSolicitacao` termina em `driAbrirFazenda`.
- [ ] **Passo 2: teste de tela** `tests/app/teste_drone_tela.py`: trocar `#dr-fila .dr-grp` por `#dri .dri-col` (esperar 3); depois de abrir a 10974 pela busca, conferir `#dri` oculto e `#dr-trab` visível; no fim (depois de descartar a prévia), `← Início` volta com as 3 colunas e sem cartão da 10974 em "A analisar". A regra da 10974 livre continua.
- [ ] **Passo 3: rodar** `node --test tests/app/*.test.js` e `python tests/app/teste_movimento.py`. Esperado: tudo PASS. O `teste_drone_tela.py` (logado, `HUB_CONTA_TESTE`) roda com o usuário.
- [ ] **Passo 4: conferência visual** no navegador: servir `app/` local, desenhar o Início com um painel de exemplo (os 9 cartões e contadores da maquete, injetados por `driDesenhar`) e comparar com a tela 1 da maquete em 1440 px e em 390 px. Repetir com `editor=false` (Foco 4: sem Conferir, sem Nova solicitação para só leitura).
- [ ] **Passo 5: manual** — atualizar em `docs/drone-manual.md` o trecho do Início (três colunas, faixa Atenção, atalho `/`).
- [ ] **Passo 6: commit** — `Drone S3.5: navegacao Inicio <-> fazenda, teste de tela e manual`

## Fechamento

- [ ] `verification-before-completion`: testes puros, teste de movimento, carga sem login sem erro no console.
- [ ] `requesting-code-review` do diff `drone-s2..drone-s3`; tratar achados com `receiving-code-review`.
- [ ] Ok do usuário (migration aplicada e conferida; tela conferida logado) antes de mesclar. Ordem do merge: `drone-s2` primeiro (já aguardando ok), depois `drone-s3`. Push com a troca de conta do `gh` (memória `reference-github-contas-push`).
- [ ] Atualizar a memória `project_drone_telas_redesenho` (estado da execução).
