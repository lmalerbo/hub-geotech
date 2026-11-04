# Etapa Voo calculada no Preparo — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar "Voo" como etapa visível do Preparo, antes da Identificação, calculada a partir da situação do voo, sem mudar o que o banco grava.

**Architecture:** O banco e `montarPreparo` continuam com as 5 etapas (índice 0 = Identificação). A tela de projetos desloca o índice em `pjNorm`: talhão aguardando voo = 0; os demais = índice do banco + 1. `PJ_ET_P` ganha o nó Voo no índice 0 com `p:null`, e `PJ_ACOES.preparo` passa para as chaves 1 a 4. A lista (Consulta) usa as mesmas funções puras, sem deslocar `f.ok`.

**Tech Stack:** JS puro sem build (`app/dados.js`, `app/projetos.js`, `app/index.html`), testes com `node --test`, conferência de tela com Playwright em Python.

**Spec:** `docs/superpowers/specs/2026-10-29-preparo-fase-voo-design.md`, seção "Revisão 29/10/2026 (tarde)".

## Global Constraints

- Ordem na tela: Voo → Identificação → Escoamento → Observações → Projeto → Ok.
- Voo é calculado: `e===0` no banco com situação `nao_solicitado`, `solicitado` ou `processando`.
- `sem_leitura` fica em Identificação, com a etiqueta "Voo sem leitura".
- `liberado` fica em Identificação.
- Sem ação na etapa Voo. O modal "Avançar mesmo assim?" sai.
- Não há retrocesso para Voo.
- Nada muda no banco nem no Plantio. `hub.preparo_aviso_sem_voo` fica no banco, sem uso.
- Código no estilo do arquivo: compacto, sem dependências novas, comentários curtos em português.

## Review Focus

1. Fazenda mista (Voo + Identificação + Escoamento): coluna "Voo", presente nos filtros Voo e Identificação, ausente em Escoamento. Teste na Tarefa 1.
2. Fazenda só com talhões em Voo: não aparece no filtro Identificação. Teste na Tarefa 1.
3. Fazenda com tudo Ok: não entra em nenhum filtro de etapa, só em Entregue. Teste na Tarefa 1.
4. Talhão `sem_leitura`, por falha do agente: segue em Identificação e pode avançar. Teste na Tarefa 1; conferência de tela na Tarefa 2.
5. Alça, seta do teclado ou clique no nó, a partir de Identificação: nada leva a Voo. Conferência de tela na Tarefa 2.

---

### Tarefa 1: funções puras em `app/dados.js`

**Files:**
- Modify: `app/dados.js:14-23`
- Test: `tests/app/dados_puro.test.js:52-57`

**Interfaces:**
- Produz `vooAguardando(t) -> bool`, com significado novo: `sem_leitura` deixa de contar.
- Produz `etapaTelaPreparo(t) -> int`: índice do talhão na tela do Preparo (0 a 5).
- Produz `preparoNoFiltroEtapa(f, filtro) -> bool`: `filtro` é `''`, `'-1'`, `'voo'` ou um índice de `ET_P` em texto.

- [ ] **Passo 1: escrever os testes que falham**

Em `tests/app/dados_puro.test.js`, trocar a linha 56 por:

```js
  assert.deepStrictEqual(limpo(f.tals.map((t) => ctx.vooAguardando(t))), [false, false, false]);
```

e acrescentar logo depois do teste que termina na linha 57:

```js
test('Preparo: só nao_solicitado, solicitado e processando ficam em Voo', () => {
  for (const voo of ['nao_solicitado', 'solicitado', 'processando']) {
    assert.strictEqual(ctx.vooAguardando({ e: 0, voo }), true, voo);
  }
  for (const voo of ['liberado', 'sem_leitura', null, undefined]) {
    assert.strictEqual(ctx.vooAguardando({ e: 0, voo }), false, String(voo));
  }
  assert.strictEqual(ctx.vooAguardando({ e: 1, voo: 'solicitado' }), false);
});

test('Preparo: índice na tela desloca uma casa, e Voo fica no 0', () => {
  assert.strictEqual(ctx.etapaTelaPreparo({ e: 0, voo: 'processando' }), 0);
  assert.strictEqual(ctx.etapaTelaPreparo({ e: 0, voo: 'liberado' }), 1);
  assert.strictEqual(ctx.etapaTelaPreparo({ e: 0, voo: 'sem_leitura' }), 1);
  assert.strictEqual(ctx.etapaTelaPreparo({ e: 1, voo: null }), 2);
  assert.strictEqual(ctx.etapaTelaPreparo({ e: 4, voo: null }), 5);
});

test('Preparo: filtro de etapa da lista', () => {
  const faz = (si, tals) => ({ ok: [0, 1, 2, 3].map((i) => si === -1 || i < si), tals });
  const voo = { e: 0, voo: 'solicitado' }, ident = { e: 0, voo: 'liberado' }, semLeit = { e: 0, voo: 'sem_leitura' }, esc = { e: 1, voo: null }, ok = { e: 4, voo: null };
  const entra = (f) => ['', 'voo', '0', '1', '2', '3', '-1'].filter((x) => ctx.preparoNoFiltroEtapa(f, x));
  assert.deepStrictEqual(entra(faz(0, [voo, ident, esc])), ['', 'voo', '0']);   // mista: nos dois
  assert.deepStrictEqual(entra(faz(0, [voo])), ['', 'voo']);                    // só Voo: fora de Identificação
  assert.deepStrictEqual(entra(faz(0, [semLeit])), ['', '0']);                  // sem leitura: em Identificação
  assert.deepStrictEqual(entra(faz(1, [esc, ok])), ['', '1']);                  // menos avançado em Escoamento
  assert.deepStrictEqual(entra(faz(-1, [ok])), ['', '-1']);                     // tudo Ok: só Entregue
});
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `node --test tests/app/dados_puro.test.js`
Expected: FAIL (`etapaTelaPreparo` e `preparoNoFiltroEtapa` não existem; `sem_leitura` ainda conta como aguardando).

- [ ] **Passo 3: implementar**

Em `app/dados.js`, trocar as linhas 14 e 15 por:

```js
// Situação do voo (Sistematização/Expansão) de cada talhão em Identificação, da view preparo_voo_talhao.
// nao_solicitado, solicitado e processando aparecem na etapa Voo (só na tela; o banco segue em Identificação).
```

e trocar a linha 23 (`function vooAguardando...`) por:

```js
function vooAguardando(t){return t.e===0&&['nao_solicitado','solicitado','processando'].includes(t.voo)}
// Índice do talhão na tela do Preparo: Voo = 0; os demais, o índice do banco + 1.
function etapaTelaPreparo(t){return vooAguardando(t)?0:(Number(t.e)||0)+1}
// Filtro de etapa da lista do Preparo. Fazenda mista entra em Voo e em Identificação.
function preparoNoFiltroEtapa(f,filtro){
  if(filtro==='')return true;
  const done=f.ok.every(x=>x);
  if(filtro==='-1')return done;
  if(done)return false;
  if(filtro==='voo')return f.tals.some(vooAguardando);
  if(filtro==='0')return f.tals.some(t=>t.e===0&&!vooAguardando(t));
  return f.ok.indexOf(false)===Number(filtro);
}
```

- [ ] **Passo 4: rodar e ver passar**

Run: `node --test tests/app/dados_puro.test.js`
Expected: PASS em todos.

- [ ] **Passo 5: commit**

```bash
git add app/dados.js tests/app/dados_puro.test.js
git commit -m "Preparo: funções da etapa Voo calculada (situação, índice na tela, filtro)"
```

### Tarefa 2: tela da fazenda em `app/projetos.js`

**Files:**
- Modify: `app/projetos.js` (trechos abaixo)

**Interfaces:**
- Consome `vooAguardando`, `etapaTelaPreparo` e `VOO_PREPARO`, de `app/dados.js`.
- Produz `fz.talhoes[].e` no índice da tela; `fz.etapas[0]` do Preparo é Voo, com `p:null`.

Procure cada trecho pelo texto, porque as linhas mudam conforme as remoções.

- [ ] **Passo 1: etapas e ações**

Trocar o comentário e `PJ_ET_P` (linhas 12 a 20) por:

```js
const PJ_COR_VOO='#5b6ee8';
// Preparo: 6 etapas na tela (0–5). p = rótulo que o banco guarda em talhao_preparo.etapa e recebe em p_para (A1).
// Voo é só da tela (p:null): não existe no banco nem é destino de retrocesso; ver etapaTelaPreparo.
// A etapa 4 aparece como "Projeto" na tela, mas o banco a chama de "Preparo".
const PJ_ET_P=[
  {l:'Voo',c:PJ_COR_VOO,i:'flight',p:null},
  {l:'Identificação',c:PJ_COR_P,i:'pin_drop',p:'Identificação'},
  {l:'Escoamento',c:PJ_COR_P,i:'water',p:'Escoamento'},
  {l:'Observações',c:PJ_COR_P,i:'comment',p:'Observações'},
  {l:'Projeto',c:PJ_COR_P,i:'construction',p:'Preparo'},
  {l:'Ok',c:'#16a76b',i:'check_circle',p:'Ok'},
];
```

Em `PJ_ACOES.preparo`, trocar as chaves `0,1,2,3` por `1,2,3,4`, sem mudar mais nada, e acrescentar antes do bloco o comentário `// Preparo: sem ação na etapa Voo (índice 0).`

- [ ] **Passo 2: índice da tela em `pjNorm`**

No `f.tals.map` de `pjNorm`, trocar `e:Number(t.e)||0` por:

```js
e:mod==='preparo'?etapaTelaPreparo(t):Number(t.e)||0
```

- [ ] **Passo 3: remover o aviso antigo**

Apagar:
- `pjSemVoo` e `pjFundoSeg`, com seus comentários (linhas 75 a 83);
- o `if(acao==='identificacao'){...}` em `pjAcaoRpc` (linhas 223 a 226);
- `pjModalSemVoo`, `pjAbrirSemVoo` e `pjConfirmarSemVoo`, com o comentário acima (linhas 302 a 351);
- `const semVoo=pjSemVoo(fz).length;` em `painelHtml`;
- a regra CSS `.pj-leg-voo{color:var(--t3)}`.

Depois, nos pontos de uso:
- `distribuicaoHtml` e `dist`: trocar `background:${pjFundoSeg(fz,i,q)}` por `background:${fz.etapas[i].c}` e `background:${et[i].c}`, respectivamente.
- `leg`: tirar `${i===0&&semVoo?` <span class="pj-leg-voo">(${semVoo} aguardando voo)</span>`:''}`.
- `nos`: trocar `<small>${cont[i]}${i===0&&semVoo?` · ${semVoo} s/ voo`:''}</small>` por `<small>${cont[i]}</small>`.

- [ ] **Passo 4: etiqueta da situação**

Na linha do talhão, trocar a condição da etiqueta `t.e===0&&t.voo&&VOO_PREPARO[t.voo]` por:

```js
t.voo&&VOO_PREPARO[t.voo]
```

(`t.voo` só vem preenchido para talhão em Identificação no banco. Assim a etiqueta aparece em Voo e em Identificação.)

- [ ] **Passo 5: bloco Voo sem botão**

Em `painelHtml`, no laço de `blocos`, logo depois de `const a=PJ_ACOES[mod][i];`, inserir:

```js
        if(!a){
          bl.push(`<div class="pj-bloco"><div class="pj-bloco-h"><span class="ebadge" style="background:${et[i].c}1a;color:${et[i].c}">${pjH(et[i].l)}</span>`+
            `<span>· ${pjNTal(grupo.length)}</span></div><div class="pj-dica">Aguardando o material do voo. Pedido e correção são feitos no Drone MGMT.</div></div>`);
          continue;
        }
```

- [ ] **Passo 6: Voo não é destino de retrocesso**

Em `pjVolta`, trocar `if(!c)return;` por:

```js
  if(!c||!c.fz.etapas[idx].p)return;
```

Em `nos` (`painelHtml`):
- trocar `const alca=(ativo&&edit)?` por `const alca=(ativo&&edit&&s.p)?`;
- trocar `aria-valuemin="0"` por `aria-valuemin="${et[0].p?0:1}"`;
- trocar `const volta=(edit&&i<atual)?` por `const volta=(edit&&i<atual&&s.p)?`.

No arraste (`pointerdown` e `pointermove`):
- trocar `PJ.drag={al,nodes,de,alvo:de};` por `PJ.drag={al,nodes,de,alvo:de,min:c.fz.etapas[0].p?0:1};`;
- trocar `if(i>g.de)return;` por `if(i>g.de||i<g.min)return;`;
- trocar `const lo=xs[0]-xs[g.de];` por `const lo=xs[g.min]-xs[g.de];`.

- [ ] **Passo 7: Nova revisão**

Em `pjAbrirRev`, trocar `limNovo:c.mod==='plantio'?3:4` por `limNovo:c.mod==='plantio'?3:5` (índices da tela: o Ok do Preparo agora é 5).

- [ ] **Passo 8: conferir que não sobrou referência**

Run: `git grep -nE "pjSemVoo|pjFundoSeg|SemVoo|pj-leg-voo|semvoo|preparo_aviso_sem_voo" -- app/`
Expected: sem resultado.

Run: `node --test tests/app/dados_puro.test.js`
Expected: PASS.

- [ ] **Passo 9: commit**

```bash
git add app/projetos.js
git commit -m "Preparo: etapa Voo na tela da fazenda, sem ação e sem retrocesso; sai o modal de avanço sem voo"
```

### Tarefa 3: lista e filtro em `app/index.html`

**Files:**
- Modify: `app/index.html:2212`, `:2248-2252`, `:2424`

**Interfaces:**
- Consome `vooAguardando` e `preparoNoFiltroEtapa`, de `app/dados.js`.

`ET_P` não muda: a tela antiga, o painel inicial e o detalhe da linha seguem com as 4 etapas do banco.

- [ ] **Passo 1: coluna e filtro**

Na montagem das linhas da Consulta, no ramo `cMod==='preparo'`, trocar:

```js
      if(cFilters.etapa!==''&&((cFilters.etapa==='-1'&&!done)||(cFilters.etapa!=='-1'&&(done||si!==parseInt(cFilters.etapa)))))return null;
      const etapa=done?'Entregue':ET_P[si]?ET_P[si].l:'—';
      const etapaC=done?'var(--plantio)':prStepColors[si]||'var(--t3)';
```

por:

```js
      if(!preparoNoFiltroEtapa(f,cFilters.etapa))return null;
      const emVoo=f.tals.some(vooAguardando);   // etapa do talhão menos avançado
      const etapa=done?'Entregue':emVoo?'Voo':ET_P[si]?ET_P[si].l:'—';
      const etapaC=done?'var(--plantio)':emVoo?'#5b6ee8':prStepColors[si]||'var(--t3)';
```

- [ ] **Passo 2: opção no select**

Trocar:

```js
<option value="">Todas as etapas</option>${ET_P.map((e,i)=>`<option value="${i}">${e.l}</option>`).join('')}<option value="-1">Entregue</option></select>`;
```

por:

```js
<option value="">Todas as etapas</option><option value="voo">Voo</option>${ET_P.map((e,i)=>`<option value="${i}">${e.l}</option>`).join('')}<option value="-1">Entregue</option></select>`;
```

Confirmar que esta é a linha do select dentro do ramo `else` que usa `FZ_P`, e não a do Plantio.

- [ ] **Passo 3: commit**

```bash
git add app/index.html
git commit -m "Preparo: coluna Etapa e filtro da lista com Voo"
```

### Tarefa 4: conferência de tela (só leitura)

**Files:**
- Create: script temporário no scratchpad, fora do repositório.

- [ ] **Passo 1: abrir com a conta de teste e sem clicar em nada que grave**

Servir a worktree localmente e abrir com Playwright usando `HUB_CONTA_TESTE`, como em `tests/app/teste_apresentacao_tela.py`. Conferir:

- fazenda 10468 (processando): passo a passo com 6 nós, "Voo" com a quantidade, etiqueta "Voado, processando", bloco Voo sem botão;
- fazenda com talhão `liberado`: talhão em Identificação, com botão "Confirmar identificação";
- com um talhão em Identificação: o nó Voo não tem `data-pj-no`, e a seta para a esquerda na alça não abre o modal;
- lista: coluna "Voo", e os filtros Voo e Identificação conforme a spec;
- console sem erro;
- capturas de tela para o usuário conferir.

Não clicar em avançar, retroceder, enviar nem desfazer. A leitura da situação pode ter mudado desde 29/10: escolher as fazendas pela situação atual.

- [ ] **Passo 2: registrar no plano o resultado e marcar as caixas**
