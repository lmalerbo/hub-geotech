# Mapas de aplicação: novo layout — Plano de implementação

> **Para quem executa:** este plano é executado pela skill `delegar` (executor externo ou sub-agente), uma tarefa por
> vez, com revisão do diff e da verificação antes da próxima. Os passos usam caixas (`- [ ]`) para acompanhar.

**Objetivo:** levar `app/aplicacao.html` ao layout escolhido no canvas (variação A da tela do mapa, lista em linhas,
novo mapa em dois passos).

**Arquitetura:** tudo continua em JS puro, sem build, nos arquivos atuais (`app/aplicacao.html`, `app/corretivos.js`,
`app/corretivos.css`). As regras novas que não mexem na tela (textos, totais previstos, lista de recentes) entram como
funções puras no topo de `corretivos.js`, testadas com `node --test`. A tela é conferida por um teste novo em modo
demonstração (Playwright + Edge, sem banco) e, no fim, pelo E2E real que já existe.

**Tecnologia:** JS puro + MapLibre GL 4.7.1 (já usado), Node `node:test`, Python + Playwright (Edge).

**Spec:** `docs/superpowers/specs/2026-10-27-mapas-aplicacao-layout-design.md`
(canvas de referência: https://claude.ai/artifact/QGhJ6aeLkAin16s7doJNsi, artboards "A", "Lista" e "Novo mapa").

## Restrições gerais

- Sem build e sem dependência nova. O código segue o estilo de `app/corretivos.js`: prefixo `cr`, nomes em português,
  HTML montado em template string com `crEsc` em todo texto vindo de dado.
- Textos em português do Brasil, com frase normal (nada de caixa alta) e números no formato `crBr` (vírgula decimal).
- **Não mudar** o PDF, o banco, as RPCs nem `app/corretivos-pdf.js`. O teste `tests/drone/test_mapa_pdf_regressao.py`
  tem que continuar passando.
- O modo demonstração (`aplicacao.html?demo`) tem que continuar funcionando.
- As funções puras ficam na seção do topo de `corretivos.js`. Elas não tocam `document`, `window` nem
  `localStorage`, porque rodam no contexto `vm` dos testes.
- O alvo é o computador, com 1280 px ou mais. Abaixo de 900 px a tela só não pode quebrar: a coluna desce para baixo
  do mapa.
- O E2E `tests/app/teste_corretivos_tela.py` usa o banco real e só apaga o que ele mesmo criou. Não mude isso.

## Pontos para a revisão

1. **Muitos talhões marcados** (Selecionar todos numa fazenda de 80): o título e a barra de seleção não podem
   estourar. `crListaTalhoes` corta em 6 ("… e mais N"), e a barra usa reticências. Coberto na Tarefa 1 (unitário) e
   na Tarefa 3 (demo).
2. **Dose vazia, zero, ou blend sem gesso:** o botão não pode mostrar "(NaN t)". `crPrevisto` devolve `null` nesses
   casos. Coberto na Tarefa 1.
3. **`localStorage` bloqueado ou com lixo:** "Abertos por último" fica vazio, sem erro. Coberto por `crLerRecentes`
   (Tarefa 1) e pelo `try/catch` (Tarefa 5).
4. **Mapa recente que foi excluído:** aparece o aviso "Esse mapa não existe mais." e o atalho some. Uma falha de rede
   **não** apaga o atalho. Coberto na Tarefa 5 (demo, com um id inexistente).
5. **Menu "⋯" aberto quando a coluna redesenha, quando se clica fora ou com Esc:** o menu fecha e não sobra menu
   solto. Coberto na Tarefa 3 (demo).

---

## Sessões de execução

Cada sessão é uma conversa nova do Claude Code, para não arrastar contexto. Uma sessão não lê esta conversa nem o
canvas inteiro: ela lê só o **cabeçalho deste plano** (até "Mapa dos arquivos"), as **tarefas dela** e a spec.

| Sessão | Tarefas | Entrega | Peso |
|---|---|---|---|
| 1 | 1 e 2 | funções puras com testes, tela do mapa em tela cheia, teste de demonstração criado | médio |
| 2 | 3 | coluna da direita, barra de seleção, menu "⋯" | o maior |
| 3 | 4 e 5 | dica do talhão, lista em linhas, "Abertos por último" | médio |
| 4 | 6 e 7 | novo mapa em dois passos, E2E real, manual, verificação final e revisão do branch | médio |

**Em toda sessão:**
1. **Começo.** Abrir com: *"Executar a Sessão N do plano `docs/superpowers/plans/2026-10-27-mapas-aplicacao-layout.md`."*
   Trabalhar na worktree `../hub-geotech-layout`, no branch `mapas-layout`. A Sessão 1 cria os dois com a skill
   `using-git-worktrees`, e as outras entram nela. Antes de começar, conferir que a sessão anterior fechou: o commit da
   última tarefa dela está no `git log` e `node --test tests/app/*.test.js` passa.
2. **Execução.** Skill `delegar`: o executor barato (OpenCode grátis ou sub-agente Haiku) implementa uma tarefa por vez,
   a partir do código que o plano já traz. O Claude principal não escreve o código. Ele confere.
3. **Portão de qualidade, por tarefa, antes do commit:**
   - o Claude principal lê o diff da tarefa e confere que bate com o plano, sem código a mais;
   - roda `node --test tests/app/*.test.js` e `python tests/app/teste_aplicacao_demo.py` e cola a saída;
   - abre os prints da tarefa em `.prints/` e compara com o artboard correspondente do canvas;
   - se algo falhar, devolve ao executor com o erro. Na **segunda** falha da mesma tarefa, o Claude principal assume a
     correção.
4. **Fechamento.** Marcar as caixas das tarefas feitas neste arquivo e dar commit. Atualizar a memória
   `project_corretivos.md` com uma linha: "Layout: Sessão N feita (commit abc123); próxima: Sessão N+1". Encerrar a
   conversa. A próxima sessão começa do zero.

**Notas da Sessão 1 (27/10):** no Node 22 desta máquina `node --test tests/app/` não acha os testes; use
`node --test tests/app/*.test.js`. A Tarefa 2 também esconde o `<main>` vazio na tela do mapa
(`.cr-modo-trab .cr-main{display:none}`), senão sobrava uma faixa de 32 px acima do cabeçalho. A coluna da direita
ficou sem padding e sem rolagem (a regra antiga de `.cr-painel` saiu): a Tarefa 3 precisa cuidar disso.

**Notas da Sessão 2 (27/10):** os executores grátis estavam sem cota, então a Tarefa 3 foi feita pelo Haiku (camada 2),
de primeira. Os arquivos estão com CRLF: o Edit não casa blocos de várias linhas, e o executor usou um script Python que
preserva o CRLF. No console cp1252, o caractere "⋯" num rótulo de `confere` derruba o print; use texto sem ele. No
"Total do mapa", nome de produto longo empurra o valor para a linha de baixo (CSS do plano). Vale olhar no polimento
da Sessão 4.

**Só a Sessão 4:** o passo 4 da Tarefa 7 (E2E real) usa a conta de teste e o banco real, então quem roda é o Claude
principal. Depois vem `requesting-code-review` no branch inteiro e `finishing-a-development-branch`. O merge e a
publicação só acontecem com o OK do Leo.

---

## Mapa dos arquivos

| Arquivo | O que muda |
|---|---|
| `app/corretivos.js` | funções puras novas (topo); tela do mapa, coluna, barra de seleção, dica, lista em linhas, recentes, novo mapa |
| `app/corretivos.css` | regras da tela cheia, da coluna, da barra, da dica, do menu, da lista e do novo mapa |
| `app/aplicacao.html` | `#cr-trabalho` sai de dentro do `<main>` e ganha um cabeçalho próprio; `#cr-recentes` na lista |
| `tests/app/layout_puro.test.js` | **novo**: testes das funções puras |
| `tests/app/teste_aplicacao_demo.py` | **novo**: confere a tela em modo demonstração e salva prints em `.prints/` |
| `tests/app/teste_corretivos_tela.py` | troca dos seletores da criação e da exclusão de mapa |
| `docs/mapas-aplicacao-manual.md` | descreve as telas novas |

Os testes rodam da raiz do repositório:
- unitários: `node --test tests/app/*.test.js`
- demo: `python tests/app/teste_aplicacao_demo.py` (sai com código 1 se alguma conferência falhar)

---

### Tarefa 1: Funções puras do layout

**Arquivos:**
- Modificar: `app/corretivos.js` (inserir logo depois de `crNomeArquivo`, antes do comentário
  `// ===== Corretivos: meio a meio por geometria`)
- Criar: `tests/app/layout_puro.test.js`

**Interfaces produzidas** (usadas nas Tarefas 3, 4 e 5):
- `crListaTalhoes(ts: number[], max = 6): string` → `'11, 12 e 14'`; acima de `max`, `'1, 2, 3, 4, 5, 6 e mais 4'`
- `crSemAplicacao(talhoes: number[], apls): number[]`, em ordem crescente
- `crTextoDose(a): string` → `'2,00 t/ha'`, `'1,50 t/ha + gesso 1,00 t/ha'`, `'0,15 L/ha'`
- `crPrevisto(f, aerea: boolean, talhoes: number[], areas: {[t]: {area_ha}}): number | null`
- `crDicaTalhao(t, areaHa, apls, marcado: boolean): { titulo, linhas: string[], acao }`
- `crLerRecentes(texto: string | null): Array<{id, cod_faz, operacao, data}>`
- `crRecentesCom(lista, item, max = 3)` e `crRecentesSem(lista, id)`

- [x] **Passo 1: Escrever o teste que falha**

Criar `tests/app/layout_puro.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ document: {}, window: {}, console, location: { protocol: 'https:', search: '' } });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/corretivos.js'), 'utf8'), ctx);
const igual = (atual, esperado) => assert.deepStrictEqual(JSON.parse(JSON.stringify(atual)), esperado);

const DOL = { tipo: 'calcario', calcario: 'dolomitico', dose: 2, dose_gesso: null, os: '4520', ordem: 1, talhoes: [1, 3] };
const FOS = { tipo: 'fosfato', calcario: null, dose: 0.5, dose_gesso: null, os: '4521', ordem: 2, talhoes: [2, 3] };
const BLEND = { tipo: 'blend', calcario: 'dolomitico', dose: 1.5, dose_gesso: 1, os: '4530', ordem: 3, talhoes: [4, 5] };
const INS = { tipo: 'insumo', insumo_nome: 'INSETICIDA REVOLUX', insumo_unidade: 'L', dose: 0.15, os: '9', ordem: 4, talhoes: [1] };
const AREAS = { 1: { area_ha: 23 }, 2: { area_ha: 23 }, 3: { area_ha: 21.4 }, 4: { area_ha: 5.24 }, 5: { area_ha: 4.7 } };

test('lista de talhões para textos', () => {
  assert.strictEqual(ctx.crListaTalhoes([]), '');
  assert.strictEqual(ctx.crListaTalhoes([5]), '5');
  assert.strictEqual(ctx.crListaTalhoes([12, 11]), '11 e 12');
  assert.strictEqual(ctx.crListaTalhoes([14, 11, 12]), '11, 12 e 14');
  const dez = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1];
  assert.strictEqual(ctx.crListaTalhoes(dez), '1, 2, 3, 4, 5, 6 e mais 4');
  assert.strictEqual(ctx.crListaTalhoes(dez, Infinity), '1, 2, 3, 4, 5, 6, 7, 8, 9 e 10');
});

test('talhões sem aplicação', () => {
  igual(ctx.crSemAplicacao([9, 1, 2, 3, 4, 5], [DOL, FOS, BLEND]), [9]);
  igual(ctx.crSemAplicacao([2, 1], []), [1, 2]);
});

test('texto da dose', () => {
  assert.strictEqual(ctx.crTextoDose(DOL), '2,00 t/ha');
  assert.strictEqual(ctx.crTextoDose(BLEND), '1,50 t/ha + gesso 1,00 t/ha');
  assert.strictEqual(ctx.crTextoDose(INS), '0,15 L/ha');
});

test('total previsto da nova aplicação', () => {
  assert.strictEqual(ctx.crPrevisto({ tipo: 'calcario', dose: '2', gesso: '' }, false, [1, 3], AREAS), 88.8);
  assert.strictEqual(ctx.crPrevisto({ tipo: 'blend', dose: '1.5', gesso: '1' }, false, [4, 5], AREAS), 24.85);
  assert.strictEqual(ctx.crPrevisto({ insumo_id: '1', dose: '2' }, true, [1, 2], AREAS), 96.6);   // com 5% de margem
  assert.strictEqual(ctx.crPrevisto({ tipo: 'calcario', dose: '', gesso: '' }, false, [1], AREAS), null);
  assert.strictEqual(ctx.crPrevisto({ tipo: 'calcario', dose: '0', gesso: '' }, false, [1], AREAS), null);
  assert.strictEqual(ctx.crPrevisto({ tipo: 'blend', dose: '1.5', gesso: '' }, false, [4], AREAS), null);
  assert.strictEqual(ctx.crPrevisto({ tipo: 'calcario', dose: '2', gesso: '' }, false, [], AREAS), null);
});

test('dica do talhão', () => {
  igual(ctx.crDicaTalhao(3, 21.4, [FOS, DOL], false), {
    titulo: 'Talhão 3, 21,40 ha',
    linhas: ['Calc. Dolomítico 2,00 t/ha, O.S. 4520', 'Fosfato 0,50 t/ha, O.S. 4521'],
    acao: 'Clique para marcar',
  });
  igual(ctx.crDicaTalhao(9, 10, [DOL], true), { titulo: 'Talhão 9, 10,00 ha', linhas: ['Sem aplicação'], acao: 'Clique para desmarcar' });
});

test('abertos por último', () => {
  igual(ctx.crLerRecentes(null), []);
  igual(ctx.crLerRecentes('lixo'), []);
  igual(ctx.crLerRecentes('{"a":1}'), []);
  igual(ctx.crLerRecentes('[{"id":5,"cod_faz":10974},{"x":1},null]'), [{ id: 5, cod_faz: 10974 }]);
  igual(ctx.crRecentesCom([{ id: 1 }, { id: 2 }, { id: 3 }], { id: 2 }), [{ id: 2 }, { id: 1 }, { id: 3 }]);
  igual(ctx.crRecentesCom([{ id: 1 }, { id: 2 }, { id: 3 }], { id: 4 }), [{ id: 4 }, { id: 1 }, { id: 2 }]);
  igual(ctx.crRecentesSem([{ id: 1 }, { id: 2 }], '2'), [{ id: 1 }]);
});
```

- [x] **Passo 2: Rodar e ver falhar**

Rodar: `node --test tests/app/layout_puro.test.js`
Esperado: FALHA com `ctx.crListaTalhoes is not a function` (e as outras).

- [x] **Passo 3: Implementar**

Em `app/corretivos.js`, logo depois da função `crNomeArquivo`:

```js
// ── Layout (27/10): textos e contas das telas, sem DOM ──
// Lista de talhões para textos: '11', '11 e 12', '11, 12 e 14'; acima de max, '1, 2, 3, 4, 5, 6 e mais 4'.
function crListaTalhoes(ts, max = 6) {
  const o = [...ts].sort((a, b) => a - b);
  if (o.length <= 1) return o.join('');
  if (o.length > max) return `${o.slice(0, max).join(', ')} e mais ${o.length - max}`;
  return `${o.slice(0, -1).join(', ')} e ${o[o.length - 1]}`;
}
function crSemAplicacao(talhoes, apls) {
  const com = new Set(apls.flatMap(a => a.talhoes));
  return talhoes.filter(t => !com.has(t)).sort((a, b) => a - b);
}
function crTextoDose(a) {
  if (a.tipo === 'insumo') return `${crBrDose(a.dose)} ${crUnidade(a)}/ha`;
  return `${crBr(a.dose)} t/ha` + (a.tipo === 'blend' ? ` + gesso ${crBr(a.dose_gesso)} t/ha` : '');
}
// Total previsto da nova aplicação, com a mesma conta do cartão (crTotalApl). null enquanto a dose não vale.
// Os campos vêm de <input type="number"> (ponto decimal), por isso Number e não crNum.
function crPrevisto(f, aerea, talhoes, areas) {
  const dose = Number(f.dose);
  if (!(dose > 0) || !talhoes.length) return null;
  const tipo = aerea ? 'insumo' : f.tipo;
  const gesso = tipo === 'blend' ? Number(f.gesso) : 0;
  if (tipo === 'blend' && !(gesso > 0)) return null;
  return crTotalApl({ tipo, dose, dose_gesso: gesso, talhoes }, areas);
}
function crDicaTalhao(t, areaHa, apls, marcado) {
  const doTalhao = crOrdenadas(apls).filter(a => a.talhoes.includes(t));
  return {
    titulo: `Talhão ${t}, ${crBr(areaHa)} ha`,
    linhas: doTalhao.length ? doTalhao.map(a => `${crRotulo(a)} ${crTextoDose(a)}, O.S. ${a.os}`) : ['Sem aplicação'],
    acao: marcado ? 'Clique para desmarcar' : 'Clique para marcar',
  };
}
// "Abertos por último": o texto guardado no navegador pode estar vazio ou estragado.
function crLerRecentes(texto) {
  try {
    const v = JSON.parse(texto || '[]');
    return Array.isArray(v) ? v.filter(r => r && r.id != null && r.cod_faz != null) : [];
  } catch (e) {
    return [];
  }
}
function crRecentesCom(lista, item, max = 3) {
  return [item, ...lista.filter(r => String(r.id) !== String(item.id))].slice(0, max);
}
function crRecentesSem(lista, id) { return lista.filter(r => String(r.id) !== String(id)); }
```

(`crTotalApl` fica mais abaixo no arquivo. Como só é chamada quando `crPrevisto` roda, a ordem não importa.)

- [x] **Passo 4: Rodar e ver passar**

Rodar: `node --test tests/app/*.test.js`
Esperado: tudo PASSA (os testes antigos também).

- [x] **Passo 5: Commit**

```bash
git add app/corretivos.js tests/app/layout_puro.test.js
git commit -m "Mapas de aplicacao: funcoes puras do novo layout (listas, dose, previsto, dica, recentes)"
```

---

### Tarefa 2: Tela do mapa em tela cheia, com cabeçalho próprio e PDF no cabeçalho

**Arquivos:**
- Modificar: `app/aplicacao.html` (bloco `#cr-trabalho`)
- Modificar: `app/corretivos.js` (`crTela`, `crAbrirMapa`, `crRenderBotaoPdf`, `crLigarTrabalho`)
- Modificar: `app/corretivos.css` (seção "Conteúdo" e `@media (max-width:899px)`)
- Criar: `tests/app/teste_aplicacao_demo.py`

**Interfaces:**
- Produz: no DOM, `#cr-trab-tit`, `#cr-trab-sub` e `#cr-pdf` (no cabeçalho); `#cr-dica` e `#cr-selbar` dentro de
  `.cr-mapa-box`; a classe `cr-modo-trab` em `#cr-app` enquanto o mapa está aberto.
- Produz: o arquivo `tests/app/teste_aplicacao_demo.py`, que as Tarefas 3 a 6 completam (cada uma acrescenta um bloco
  antes da linha `# fim das conferências`).

- [x] **Passo 1: Escrever o teste de demonstração (falha)**

Criar `tests/app/teste_aplicacao_demo.py`:

```python
"""Confere as telas dos Mapas de aplicação em modo demonstração (sem banco). Roda à mão, da raiz do repositório:
    python tests/app/teste_aplicacao_demo.py
Sobe um servidor local para app/, abre aplicacao.html?demo no Edge e salva prints em .prints/."""
import functools
import http.server
import re
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
PRINTS = RAIZ / '.prints'
falhas = []


def confere(cond, msg):
    print(('ok    ' if cond else 'FALHA ') + msg)
    if not cond:
        falhas.append(msg)


class Quieto(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


srv = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Quieto, directory=str(RAIZ / 'app')))
porta = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
PRINTS.mkdir(exist_ok=True)

try:
    with sync_playwright() as p:
        nav = p.chromium.launch(channel='msedge')
        pg = nav.new_page(viewport={'width': 1440, 'height': 900})
        erros = []
        pg.on('pageerror', lambda e: erros.append(str(e)))
        pg.goto(f'http://127.0.0.1:{porta}/aplicacao.html?demo')
        # a demonstração abre sozinha o primeiro mapa da primeira fazenda
        pg.wait_for_function("typeof CR_ST !== 'undefined' && CR_ST.geo && CR_ST.det", timeout=30000)
        pg.wait_for_selector('#cr-mapa canvas', timeout=30000)

        # ── Tarefa 2: tela cheia e cabeçalho do mapa ──
        caixa = pg.locator('#cr-mapa').bounding_box()
        confere(caixa and caixa['width'] > 900, f"mapa ocupa a largura ({caixa and round(caixa['width'])} px)")
        confere(not pg.locator('.cr-top').is_visible(), 'cabeçalho do app some na tela do mapa')
        confere(pg.locator('.cr-trab-top #cr-pdf button').first.is_visible(), 'Baixar PDF no cabeçalho do mapa')
        tit = pg.locator('#cr-trab-tit').inner_text()
        confere(bool(re.match(r'^\S.*, \d\d/\d\d/\d{4}$', tit)), f'título "Operação, data" ({tit})')
        pg.screenshot(path=str(PRINTS / 'aplicacao_mapa.png'))
        pg.click('#cr-voltar')
        confere(pg.locator('.cr-top').is_visible(), 'cabeçalho do app volta na lista')
        pg.click('[data-abrir]')
        pg.wait_for_function('CR_ST.geo && CR_ST.det', timeout=30000)
        pg.wait_for_selector('#cr-mapa canvas', timeout=30000)

        # fim das conferências
        confere(not erros, f'sem erros de JavaScript ({erros[:2]})')
        nav.close()
finally:
    srv.shutdown()

print(f'\n{len(falhas)} falha(s)')
sys.exit(1 if falhas else 0)
```

- [x] **Passo 2: Rodar e ver falhar**

Rodar: `python tests/app/teste_aplicacao_demo.py`
Esperado: FALHA em "mapa ocupa a largura" (hoje uns 500 px) e em "cabeçalho do app some".

- [x] **Passo 3: Mudar o HTML**

Em `app/aplicacao.html`, apagar o bloco `<section id="cr-trabalho" …>…</section>` de dentro do `<main>` e colocar
este bloco logo **depois** do `</main>`, ainda dentro de `#cr-app`:

```html
  <section id="cr-trabalho" class="cr-trab off" aria-label="Mapa em edição">
    <header class="cr-trab-top">
      <button class="cr-btn2" type="button" id="cr-voltar"><span class="ico">arrow_back</span> Mapas da fazenda</button>
      <div class="cr-trab-id">
        <h1 class="cr-trab-tit" id="cr-trab-tit"></h1>
        <span class="cr-trab-sub" id="cr-trab-sub"></span>
      </div>
      <div class="cr-trab-pdf" id="cr-pdf"></div>
    </header>
    <div class="cr-trab-corpo" id="cr-trab-corpo"></div>
  </section>
```

- [x] **Passo 4: Mudar o JS**

Em `crTela`, acrescentar no fim:

```js
  document.getElementById('cr-app').classList.toggle('cr-modo-trab', nome === 'trabalho');
```

Em `crAbrirMapa`, trocar a linha que preenche `cr-trab-tit` por:

```js
  document.getElementById('cr-trab-tit').textContent = `${CR_OPERACOES[mapa.operacao]}, ${crDataIso(mapa.data)}`;
  const resumo = CR_ST.mapas.find(m => String(m.id) === String(mapa.id));
  document.getElementById('cr-trab-sub').textContent = `${CR_ST.faz.cod_faz} ${CR_ST.faz.nome}`
    + (resumo ? `. Alterado por ${resumo.alterado_por_nome} em ${crDiaMes(resumo.alterado_em)}` : '');
```

Em `crRenderBotaoPdf`, trocar os três `alvo.innerHTML` de botão e erro, e a frase do preparo, por estas versões
compactas (o resto da função continua igual):

```js
  if (CR_DEMO || !window.crGerador) {
    alvo.innerHTML = '<button class="cr-btn" type="button" disabled title="Indisponível na demonstração"><span class="ico">download</span> Baixar PDF</button>';
    return;
  }
  const est = crGerador.estado;
  if (est === 'erro') {
    alvo.innerHTML = '<span class="cr-erro-bloco" role="alert">O gerador de PDF não carregou.</span>'
      + '<button class="cr-btn2" type="button" data-pdf-tentar>Tentar de novo</button>';
  } else if (est === 'pronto' || est === 'parado') {
    alvo.innerHTML = `<button class="cr-btn" type="button" data-pdf${vazio ? ' disabled title="Lance uma aplicação para baixar o PDF"' : ''}><span class="ico">download</span> Baixar PDF</button>`;
  } else {
    if (!crProgPdf || !alvo.contains(crProgPdf.el)) {
      alvo.innerHTML = '<span class="cr-trab-sub">Preparando o PDF (só na primeira vez)</span>';
```

Em `crLigarTrabalho`, trocar o `innerHTML` de `cr-trab-corpo` por:

```js
  document.getElementById('cr-trab-corpo').innerHTML = `<div class="cr-trab-grid">
    <div class="cr-mapa-box">
      <div id="cr-mapa"></div>
      <div class="cr-dica off" id="cr-dica" aria-hidden="true"></div>
      <div class="cr-selbar" id="cr-selbar"></div>
    </div>
    <aside class="cr-painel" id="cr-painel" aria-label="Aplicações do mapa"></aside>
  </div>`;
  document.getElementById('cr-pdf').onclick = e => {
    const b = e.target.closest('[data-pdf],[data-pdf-tentar]');
    if (!b || b.disabled) return;
    if ('pdfTentar' in b.dataset) { crGerador.preparar().catch(() => {}); crRenderBotaoPdf(); }
    else crBaixarPdf();
  };
```

No `painel.onclick` de `crLigarTrabalho`, tirar `[data-pdf],[data-pdf-tentar]` do seletor e apagar os dois ramos
`pdfTentar` e `pdf` (o PDF agora é tratado pelo `onclick` de `#cr-pdf`).

Em `crRenderPainel`, apagar a linha `<div id="cr-pdf"></div>` (o lugar do PDF agora é o cabeçalho). A chamada
`crRenderBotaoPdf()` no fim continua.

- [x] **Passo 5: Mudar o CSS**

Em `app/corretivos.css`, na seção "Conteúdo", trocar `max-width:880px` de `.cr-main` por `max-width:1040px`. Apagar
as regras antigas `.cr-trab-grid`, `#cr-trabalho .cr-pnl`, `.cr-mapa-box` e `.cr-painel`, e pôr no lugar delas:

```css
#cr-app.cr-modo-trab{height:100vh;display:flex;flex-direction:column;overflow:hidden}
.cr-modo-trab .cr-top{display:none}
.cr-trab{flex:1;min-height:0;display:flex;flex-direction:column}
.cr-trab-top{display:flex;align-items:center;gap:16px;padding:12px 20px;background:var(--sf);border-bottom:1px solid var(--bd);flex-wrap:wrap}
.cr-trab-id{display:flex;flex-direction:column;min-width:0}
.cr-trab-tit{font-size:18px;font-weight:600;letter-spacing:-.2px}
.cr-trab-sub{font-size:12px;color:var(--t2)}
.cr-trab-pdf{margin-left:auto;display:flex;align-items:center;gap:8px;min-width:0}
.cr-trab-pdf .mo-prog{width:220px}
.cr-trab-corpo{flex:1;min-height:0}
.cr-trab-grid{display:grid;grid-template-columns:minmax(0,1fr) 380px;height:100%;min-height:0}
.cr-mapa-box{position:relative;min-width:0;min-height:0}
.cr-painel{display:flex;flex-direction:column;min-height:0;background:var(--sf);border-left:1px solid var(--bd)}
```

Trocar o bloco `@media (max-width:899px){…}` da seção "Conteúdo" por:

```css
@media (max-width:899px){
  #cr-app.cr-modo-trab{height:auto;overflow:visible}
  .cr-trab-grid{grid-template-columns:1fr;height:auto}
  .cr-mapa-box{height:55vh;min-height:320px}
  .cr-painel{border-left:0;border-top:1px solid var(--bd)}
}
```

- [x] **Passo 6: Rodar e ver passar**

Rodar: `node --test tests/app/*.test.js` e depois `python tests/app/teste_aplicacao_demo.py`
Esperado: tudo PASSA. Abrir `.prints/aplicacao_mapa.png` e conferir que o mapa ocupa a tela e o PDF está no
cabeçalho. (Nesta tarefa a coluna ainda tem o conteúdo antigo; ela muda na Tarefa 3.)

- [x] **Passo 7: Commit**

```bash
git add app/aplicacao.html app/corretivos.js app/corretivos.css tests/app/teste_aplicacao_demo.py
git commit -m "Mapas de aplicacao: tela do mapa em tela cheia, cabecalho proprio e PDF no cabecalho"
```

---

### Tarefa 3: Coluna da direita e barra de seleção

**Arquivos:**
- Modificar: `app/corretivos.js` (`crAbrirMapa`, `crAplicarMarcadosAgora`, `crVoltarLista`, `crCardAplicacao`,
  `crRenderPainel`, `crLigarTrabalho`; funções novas `crSecaoNova`, `crSecaoDica`, `crTextoAplicar`,
  `crRenderSelBar`, `crMenu`, `crFecharMenu`)
- Modificar: `app/corretivos.css`
- Modificar: `tests/app/teste_aplicacao_demo.py`

**Interfaces:**
- Consome (Tarefa 1): `crListaTalhoes`, `crSemAplicacao`, `crTextoDose`, `crPrevisto`
- Consome (Tarefa 2): `#cr-selbar`, `#cr-painel`
- Produz: `crMenu(botao: HTMLElement, itens: Array<{rotulo, ico, perigo?, acao: () => void}>)` e `crFecharMenu()`,
  usadas também na Tarefa 5; o estado novo `CR_ST.areasAbertas: boolean`

- [x] **Passo 1: Acrescentar as conferências (falham)**

Em `tests/app/teste_aplicacao_demo.py`, antes de `# fim das conferências`:

```python
        # ── Tarefa 3: coluna da direita e barra de seleção ──
        confere(pg.locator('.cr-nova').count() == 0, 'sem talhão marcado, a Nova aplicação fica fechada')
        confere('Clique nos talhões' in pg.locator('#cr-selbar').inner_text(), 'barra diz como marcar')
        ts = pg.evaluate("() => { const ts = CR_ST.geo.features.map(f => f.properties.talhao).sort((a, b) => a - b).slice(0, 2);"
                         " ts.forEach(t => crToggleSel(t)); return ts; }")
        confere(pg.locator('.cr-nova h2').inner_text() == 'Nova aplicação nos 2 talhões', 'título da Nova aplicação')
        confere('2 talhões marcados' in pg.locator('#cr-selbar').inner_text(), 'barra conta os marcados')
        if pg.evaluate("CR_ST.trab.operacao === 'aerea'"):
            pg.select_option('#cr-f-insumo', index=1)
        pg.fill('#cr-f-dose', '2')
        if pg.locator('#cr-f-gesso').count():
            pg.fill('#cr-f-gesso', '1')
        rot = pg.locator('[data-aplicar]').inner_text()
        confere(bool(re.match(r'^Aplicar nos 2 talhões \([\d.,]+\s\S+\)$', rot)), f'botão com total previsto ({rot})')
        pg.fill('#cr-f-dose', '')
        confere('NaN' not in pg.locator('[data-aplicar]').inner_text(), 'dose vazia não mostra NaN')
        confere(pg.locator('[data-area]').count() == 0, 'áreas por talhão começam recolhidas')
        pg.click('[data-areas]')
        confere(pg.locator('[data-area]').count() == 2, 'Ajustar a área abre um campo por talhão')
        confere(pg.locator('.cr-painel-tot').is_visible(), 'total do mapa no pé da coluna')
        n_apl = pg.locator('[data-menu-apl]').count()
        confere(n_apl > 0, 'demonstração tem aplicações para conferir o menu')
        if n_apl:
            pg.locator('[data-menu-apl]').first.click()
            confere(pg.locator('.cr-menu button:has-text("Editar")').is_visible(), 'menu ⋯ com Editar')
            pg.keyboard.press('Escape')
            confere(pg.locator('.cr-menu').count() == 0, 'Esc fecha o menu')
            pg.locator('[data-menu-apl]').first.click()
            pg.click('#cr-trab-tit')
            confere(pg.locator('.cr-menu').count() == 0, 'clicar fora fecha o menu')
        pg.screenshot(path=str(PRINTS / 'aplicacao_selecao.png'))
        pg.evaluate('crSelecionarTodos()')
        largura = pg.locator('#cr-selbar').bounding_box()['width']
        confere(largura < pg.locator('#cr-mapa').bounding_box()['width'], 'barra com todos marcados não estoura o mapa')
        pg.click('#cr-selbar [data-limpar]')
        confere(pg.locator('.cr-nova').count() == 0, 'Limpar fecha a Nova aplicação')
```

Rodar: `python tests/app/teste_aplicacao_demo.py`. Esperado: FALHA a partir de "barra diz como marcar".

- [x] **Passo 2: Estado e limpeza**

Em `crAbrirMapa`, no `Object.assign(CR_ST, {…})`, acrescentar `areasAbertas: false`.
Em `crAplicarMarcadosAgora`, logo depois de `CR_ST.sel = new Set();`, acrescentar `CR_ST.areasAbertas = false;`.
Em `crVoltarLista`, acrescentar `crFecharMenu();` como primeira linha.

- [x] **Passo 3: Menu "⋯"**

Acrescentar logo antes de `// ── Painel ──`:

```js
// Menu "⋯": abre embaixo do botão, alinhado à direita; fecha ao escolher, ao clicar fora ou com Esc.
function crMenu(botao, itens) {
  crFecharMenu();
  const el = document.createElement('div');
  el.className = 'cr-menu';
  el.setAttribute('role', 'menu');
  el.innerHTML = itens.map((it, i) => `<button type="button" role="menuitem" data-i="${i}"${it.perigo ? ' class="perigo"' : ''}><span class="ico" aria-hidden="true">${it.ico}</span> ${crEsc(it.rotulo)}</button>`).join('');
  document.body.appendChild(el);
  const r = botao.getBoundingClientRect();
  el.style.top = `${Math.min(r.bottom + 4, window.innerHeight - el.offsetHeight - 8)}px`;
  el.style.left = `${Math.max(8, r.right - el.offsetWidth)}px`;
  el.onclick = e => {
    const b = e.target.closest('[data-i]');
    if (!b) return;
    crFecharMenu();
    itens[Number(b.dataset.i)].acao();
  };
  crMenu.aberto = el;
  setTimeout(() => document.addEventListener('click', crFecharMenuFora), 0);
  document.addEventListener('keydown', crMenuEsc);
  el.querySelector('button').focus();
}
function crFecharMenuFora(e) { if (crMenu.aberto && !crMenu.aberto.contains(e.target)) crFecharMenu(); }
function crMenuEsc(e) { if (e.key === 'Escape') crFecharMenu(); }
function crFecharMenu() {
  if (crMenu.aberto) { crMenu.aberto.remove(); crMenu.aberto = null; }
  document.removeEventListener('click', crFecharMenuFora);
  document.removeEventListener('keydown', crMenuEsc);
}
```

- [x] **Passo 4: Cartão de aplicação, seções e coluna**

Trocar `crCardAplicacao` inteira por:

```js
function crCardAplicacao(a, areas, cores) {
  const cor = cores[crChaveCor(a)];
  const on = CR_ST.destApl === a.id;
  const total = crTotalApl(a, areas);
  const quanto = a.tipo === 'insumo' ? `${crBr(total)} ${crUnidade(a)}` : crTon(total);
  const ts = a.talhoes;
  return `<div class="cr-ap${on ? ' on' : ''}">
    <span class="cr-ap-sw" style="background:${cor}" aria-hidden="true"></span>
    <button class="cr-ap-main" type="button" data-dest="${a.id}" aria-pressed="${on}">
      <b>${crEsc(crRotulo(a))}, ${crEsc(crTextoDose(a))}</b>
      <small>O.S. ${crEsc(a.os)}. ${ts.length === 1 ? 'Talhão' : 'Talhões'} ${crListaTalhoes(ts, Infinity)}. ${quanto}</small>
    </button>
    <button class="cr-x" type="button" data-menu-apl="${a.id}" aria-haspopup="menu" aria-label="Ações de ${crEsc(crRotulo(a))}, O.S. ${crEsc(a.os)}"><span class="ico">more_vert</span></button>
  </div>`;
}
```

Acrescentar, logo depois de `crLinhaArea`:

```js
// Texto do botão Aplicar: alvo e, quando a dose já vale, o total previsto.
function crTextoAplicar(sel) {
  const aerea = crAerea(CR_ST.trab.operacao);
  const f = CR_ST.form;
  const areas = {};
  for (const t of sel) areas[t] = crAreaDe(t);
  const prev = crPrevisto(f, aerea, sel, areas);
  const ins = aerea ? CR_ST.insumos.find(i => String(i.id) === String(f.insumo_id)) : null;
  const un = aerea ? (ins ? CR_UNIDADE[ins.unidade] : '') : 't';
  const alvo = sel.length === 1 ? `no talhão ${sel[0]}` : `nos ${sel.length} talhões`;
  return `Aplicar ${alvo}` + (prev != null && un ? ` (${crBr(prev)} ${un})` : '');
}
function crMsgForm() {
  const m = CR_ST.formMsg;
  return m ? `<p class="${m.tipo === 'erro' ? 'cr-erro' : 'cr-info'}" role="${m.tipo === 'erro' ? 'alert' : 'status'}">${crEsc(m.texto)}</p>` : '';
}
// Sem talhão marcado: só a orientação (e o recado da última gravação, se houver).
function crSecaoDica() {
  return `<section class="cr-sec cr-nova-dica"><p class="cr-msg">Marque talhões no mapa para lançar uma nova aplicação.</p>${crMsgForm()}</section>`;
}
function crSecaoNova(sel, aerea) {
  const f = CR_ST.form;
  const abertas = CR_ST.areasAbertas;
  const alvo = sel.length === 1 ? `no talhão ${sel[0]}` : `nos ${sel.length} talhões`;
  return `<section class="cr-sec cr-nova" aria-labelledby="cr-h-nova">
      <h2 id="cr-h-nova">Nova aplicação ${alvo}</h2>
      ${aerea ? crCamposAerea(f) : crCamposCorretivo(f)}
      <div><label class="cr-lbl" for="cr-f-os">O.S.</label>
        <input class="cr-inp" id="cr-f-os" type="text" data-f="os" value="${crEsc(f.os)}"></div>
      <button class="cr-link" type="button" data-areas aria-expanded="${abertas}"><span class="ico" aria-hidden="true">${abertas ? 'expand_more' : 'chevron_right'}</span> Ajustar a área de algum talhão</button>
      ${abertas ? `<div class="cr-sel-lista">${sel.map(t => `<label class="cr-sel-l"><span>Talhão ${t}, área (ha)</span>
          <input class="cr-inp cr-inp-sm" type="number" step="0.01" min="0" value="${crAreaDe(t).area_ha}" data-area="${t}"></label>`).join('')}</div>` : ''}
      ${crMsgForm()}
      <button class="cr-btn cr-btn-bloco" type="button" data-aplicar>${crEsc(crTextoAplicar(sel))}</button>
    </section>`;
}
// Barra sobre o mapa: quantos talhões estão marcados, quais e quantos hectares.
function crRenderSelBar() {
  const alvo = document.getElementById('cr-selbar');
  if (!alvo || !CR_ST.geo) return;
  const sel = crSelecionados();
  if (!sel.length) {
    alvo.innerHTML = '<span class="cr-selbar-tit">Clique nos talhões para marcar</span>'
      + '<button class="cr-selbar-b2" type="button" data-todos>Selecionar todos</button>';
    return;
  }
  const ha = sel.reduce((s, t) => s + Number(crAreaDe(t).area_ha), 0);
  const todos = sel.length === CR_ST.geo.features.length;
  alvo.innerHTML = `<span class="cr-selbar-tit">${sel.length === 1 ? '1 talhão marcado' : `${sel.length} talhões marcados`}</span>
    <span class="cr-selbar-sub">${crListaTalhoes(sel)}, somando ${crBr(ha)} ha</span>
    <button class="cr-selbar-b" type="button" data-limpar>Limpar</button>
    ${todos ? '' : '<button class="cr-selbar-b2" type="button" data-todos>Selecionar todos</button>'}`;
}
```

Trocar `crRenderPainel` inteira por:

```js
function crRenderPainel() {
  const alvo = document.getElementById('cr-painel');
  if (!CR_ST.det || !CR_ST.geo) return;
  crFecharMenu();
  const { areas, apls } = CR_ST.det;
  const fora = crTalhoesForaDaBase(areas, CR_ST.geo);
  const sel = crSelecionados();
  const aerea = crAerea(CR_ST.trab.operacao);
  const cores = crCoresDoMapa(apls);
  const tot = crTotaisPorProduto(apls, areas, CR_ST.trab.operacao);
  const sem = crSemAplicacao(CR_ST.geo.features.map(f => f.properties.talhao), apls);
  alvo.innerHTML = `
    <div class="cr-painel-rol">
      ${fora.length ? `<div class="cr-aviso" role="status"><span class="ico" aria-hidden="true">warning</span><span>Talhões que saíram da Base: ${fora.join(', ')}. Eles continuam no PDF, sem desenho.</span></div>` : ''}
      ${sel.length ? crSecaoNova(sel, aerea) : crSecaoDica()}
      <section class="cr-sec" aria-labelledby="cr-h-lista">
        <h2 id="cr-h-lista">Aplicações do mapa</h2>
        ${apls.length ? crOrdenadas(apls).map(a => crCardAplicacao(a, areas, cores)).join('') : '<p class="cr-msg">Nenhuma aplicação neste mapa ainda.</p>'}
        ${sem.length ? `<div class="cr-ap-sem"><span class="cr-ap-sw" style="background:#ffffff" aria-hidden="true"></span><span>Sem aplicação: ${sem.length === 1 ? 'talhão' : 'talhões'} ${crListaTalhoes(sem, 12)}</span></div>` : ''}
      </section>
    </div>
    <footer class="cr-painel-tot" aria-labelledby="cr-h-res">
      <h2 id="cr-h-res">Total do mapa</h2>
      ${tot.length
        ? `<div class="cr-tot-lista">${tot.map(t => `<div class="cr-tot-l"><span>${crEsc(t.titulo)}</span><b>${crBr(t.total)} ${t.unidade}</b>${t.detalhe ? `<small>${crEsc(t.detalhe.replace(/ t\b/g, ' t'))}</small>` : ''}</div>`).join('')}</div>`
        : '<p class="cr-msg">Sem aplicações ainda.</p>'}
      ${aerea ? crLinhaArea(areas, CR_ST.trab.operacao) : ''}
    </footer>`;
  crRenderSelBar();
  crRenderBotaoPdf();
}
```

- [x] **Passo 5: Eventos**

Em `crLigarTrabalho`, trocar o `painel.onclick` e o `painel.oninput` por estes, e acrescentar o `onclick` da barra:

```js
  painel.onclick = e => {
    const b = e.target.closest('[data-dest],[data-menu-apl],[data-areas],[data-aplicar],[data-insumos],[data-tentar-trab]');
    if (!b || b.disabled) return;
    const d = b.dataset;
    if (d.dest) crDestacar(Number(d.dest));
    else if (d.menuApl) {
      const id = Number(d.menuApl);
      crMenu(b, [
        { rotulo: 'Editar', ico: 'edit', acao: () => crEditarAplicacao(id) },
        { rotulo: 'Excluir', ico: 'delete', perigo: true, acao: () => crExcluirAplicacao(id) },
      ]);
    }
    else if ('areas' in d) { CR_ST.areasAbertas = !CR_ST.areasAbertas; crRenderPainel(); }
    else if ('insumos' in d) crAbrirInsumos();
    else if ('aplicar' in d) crAplicarMarcados();
    else if ('tentarTrab' in d) crAbrirMapa(CR_ST.trab);
  };
  painel.oninput = e => {
    if (!e.target.dataset.f) return;
    CR_ST.form[e.target.dataset.f] = e.target.value;
    const b = painel.querySelector('[data-aplicar]');
    if (b && !CR_ST.gravando) b.textContent = crTextoAplicar(crSelecionados());
  };
  document.getElementById('cr-selbar').onclick = e => {
    const b = e.target.closest('[data-todos],[data-limpar]');
    if (!b) return;
    if ('todos' in b.dataset) crSelecionarTodos(); else crLimparSel();
  };
```

(O `painel.onchange` continua igual.)

- [x] **Passo 6: CSS**

Acrescentar na seção "Conteúdo" de `app/corretivos.css`:

```css
.cr-painel-rol{flex:1;overflow:auto;padding:18px;display:flex;flex-direction:column;gap:22px;min-height:0}
.cr-painel-tot{border-top:1px solid var(--bd);background:#fbfcfd;padding:14px 18px;display:flex;flex-direction:column;gap:8px}
.cr-painel-tot h2{font-size:13px;font-weight:600}
.cr-tot-lista{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 16px}
.cr-tot-l{display:flex;flex-wrap:wrap;justify-content:space-between;gap:0 8px;font-size:12px;min-width:0}
.cr-tot-l span{color:var(--t2)}
.cr-tot-l b{font-weight:600}
.cr-tot-l small{flex-basis:100%;color:var(--t2);font-size:11px}
.cr-nova{border:2px solid var(--plantio);border-radius:14px;padding:14px}
.cr-nova h2{font-size:15px}
.cr-link{display:inline-flex;align-items:center;gap:4px;background:none;border:0;padding:0;color:var(--t2);font-size:12px;cursor:pointer;align-self:flex-start}
.cr-link .ico{font-size:18px}
.cr-ap-sem{display:flex;align-items:center;gap:10px;padding:4px 10px;color:var(--t2);font-size:12px}
.cr-selbar{position:absolute;left:50%;bottom:24px;transform:translateX(-50%);display:flex;align-items:center;gap:14px;background:var(--t1);color:#fff;border-radius:14px;padding:8px 8px 8px 18px;box-shadow:var(--sh-md);max-width:calc(100% - 32px);z-index:2}
.cr-selbar-tit{font-weight:600;white-space:nowrap}
.cr-selbar-sub{color:#c9ced6;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cr-selbar-b{background:transparent;color:#fff;border:1px solid #4d5560;border-radius:10px;padding:8px 12px;cursor:pointer;white-space:nowrap}
.cr-selbar-b2{background:var(--plantio);color:#fff;border:0;border-radius:10px;padding:8px 14px;font-weight:600;cursor:pointer;white-space:nowrap}
.cr-menu{position:fixed;z-index:70;background:var(--sf);border-radius:12px;box-shadow:var(--sh-md);padding:6px;display:flex;flex-direction:column;min-width:170px}
.cr-menu button{display:flex;align-items:center;gap:8px;border:0;background:none;padding:9px 10px;border-radius:8px;cursor:pointer;text-align:left;color:var(--t1);font-size:13px}
.cr-menu button:hover,.cr-menu button:focus-visible{background:var(--s2)}
.cr-menu button.perigo{color:#b03030}
```

E apagar as regras que ficaram sem uso: `.cr-sec-top`, `.cr-acoes-sel`, `.cr-ap-acoes`, `.cr-tot-grid` e `.cr-tot`.

- [x] **Passo 7: Rodar e ver passar**

Rodar: `node --test tests/app/*.test.js` e depois `python tests/app/teste_aplicacao_demo.py`
Esperado: tudo PASSA. Comparar `.prints/aplicacao_selecao.png` com o artboard "A" do canvas.

- [x] **Passo 8: Commit**

```bash
git add app/corretivos.js app/corretivos.css tests/app/teste_aplicacao_demo.py
git commit -m "Mapas de aplicacao: coluna com nova aplicacao contextual, aplicacoes como legenda, total fixo e barra de selecao"
```

---

### Tarefa 4: Dica ao passar o mouse no talhão

**Arquivos:**
- Modificar: `app/corretivos.js` (`crMapaCriar`, `crVoltarLista`; funções novas `crMostrarDica`, `crEsconderDica`)
- Modificar: `app/corretivos.css`
- Modificar: `tests/app/teste_aplicacao_demo.py`

**Interfaces:**
- Consome (Tarefa 1): `crDicaTalhao`. Consome (Tarefa 2): `#cr-dica`.

- [x] **Passo 1: Acrescentar a conferência (falha)**

Antes de `# fim das conferências`:

```python
        # ── Tarefa 4: dica ao passar o mouse ──
        ponto = pg.evaluate("""() => {
            const f = CR_ST.geo.features[0];
            const anel = (f.geometry.type === 'Polygon' ? f.geometry.coordinates : f.geometry.coordinates[0])[0];
            const lng = anel.reduce((s, c) => s + c[0], 0) / anel.length, lat = anel.reduce((s, c) => s + c[1], 0) / anel.length;
            const p = CR_ST.map.project([lng, lat]);
            return { x: p.x, y: p.y, t: f.properties.talhao };
        }""")
        caixa = pg.locator('#cr-mapa').bounding_box()
        pg.mouse.move(caixa['x'] + ponto['x'], caixa['y'] + ponto['y'])
        pg.wait_for_selector('#cr-dica:not(.off)', timeout=5000)
        confere(f"Talhão {ponto['t']}," in pg.locator('#cr-dica').inner_text(), 'dica mostra o talhão sob o mouse')
        pg.screenshot(path=str(PRINTS / 'aplicacao_dica.png'))
        pg.mouse.move(caixa['x'] + 5, caixa['y'] + caixa['height'] - 5)
        pg.mouse.move(0, 0)
        confere(pg.locator('#cr-dica.off').count() == 1, 'dica some ao sair do mapa')
```

Rodar e ver FALHAR em "dica mostra o talhão" (tempo esgotado).

- [x] **Passo 2: Implementar**

Acrescentar logo depois de `crAtualizarEstados`:

```js
// Dica ao passar o mouse: segue o ponteiro e vira para dentro perto das bordas do mapa.
function crMostrarDica(t, ponto) {
  const el = document.getElementById('cr-dica');
  if (!el || !CR_ST.det) return;
  const d = crDicaTalhao(t, crAreaDe(t).area_ha, CR_ST.det.apls, CR_ST.sel.has(t));
  el.innerHTML = `<b>${crEsc(d.titulo)}</b>${d.linhas.map(l => `<span>${crEsc(l)}</span>`).join('')}<span class="cr-dica-acao">${d.acao}</span>`;
  el.classList.remove('off');
  const box = el.parentElement.getBoundingClientRect();
  const x = Math.min(ponto.x + 14, box.width - el.offsetWidth - 8);
  const y = ponto.y + 14 + el.offsetHeight > box.height ? ponto.y - el.offsetHeight - 10 : ponto.y + 14;
  el.style.transform = `translate(${Math.max(8, x)}px, ${Math.max(8, y)}px)`;
}
function crEsconderDica() {
  const el = document.getElementById('cr-dica');
  if (el) el.classList.add('off');
}
```

Em `crMapaCriar`, dentro de `m.on('load', …)`:
- no `m.on('click', …)`, depois de `if (f) crToggleSel(f.properties.talhao);`, acrescentar
  `if (f) crMostrarDica(f.properties.talhao, e.point);` (para o "Clique para marcar/desmarcar" virar na hora);
- acrescentar `m.on('mousemove', 'cr-fill', e => crMostrarDica(e.features[0].properties.talhao, e.point));`
- trocar o `mouseleave` por `m.on('mouseleave', 'cr-fill', () => { m.getCanvas().style.cursor = ''; crEsconderDica(); });`

Em `crVoltarLista`, acrescentar `crEsconderDica();` depois de `crFecharMenu();`.

CSS, na seção "Conteúdo":

```css
.cr-dica{position:absolute;left:0;top:0;z-index:3;pointer-events:none;background:var(--sf);border-radius:10px;box-shadow:0 8px 24px rgb(0 0 0/.14);padding:10px 12px;display:flex;flex-direction:column;gap:2px;font-size:12px;max-width:280px}
.cr-dica b{font-size:13px;font-weight:600}
.cr-dica span{color:var(--t2)}
.cr-dica-acao{margin-top:2px}
```

- [x] **Passo 3: Rodar e ver passar**

Rodar: `python tests/app/teste_aplicacao_demo.py`. Esperado: PASSA. Olhar `.prints/aplicacao_dica.png`.

- [x] **Passo 4: Commit**

```bash
git add app/corretivos.js app/corretivos.css tests/app/teste_aplicacao_demo.py
git commit -m "Mapas de aplicacao: dica do talhao ao passar o mouse"
```

---

### Tarefa 5: Lista de mapas em linhas e "Abertos por último"

**Arquivos:**
- Modificar: `app/aplicacao.html` (dentro de `#cr-lista`, logo depois de `<div class="cr-busca">…</div>`)
- Modificar: `app/corretivos.js` (`crCarregarFazendas`, `crEscolherFazenda`, `crCarregarMapas`, `crRenderMapas`,
  `crAbrirMapa`, `crIniciar`; troca `crCardMapa` por `crLinhaMapa`; funções novas de recentes)
- Modificar: `app/corretivos.css`
- Modificar: `tests/app/teste_aplicacao_demo.py`

**Interfaces:**
- Consome (Tarefa 1): `crLerRecentes`, `crRecentesCom`, `crRecentesSem`. Consome (Tarefa 3): `crMenu`.
- Produz: `crEscolherFazenda(f, abrirPrimeiro)` e `crCarregarMapas()` passam a devolver `true` quando a lista de
  mapas carregou e `false` quando falhou.
- Seletores que o E2E da Tarefa 7 usa: `[data-abrir="<id>"]` (linha) e `[data-menu-mapa="<id>"]` (menu "⋯").

- [x] **Passo 1: Acrescentar as conferências (falham)**

Antes de `# fim das conferências`:

```python
        # ── Tarefa 5: lista em linhas e abertos por último ──
        pg.click('#cr-voltar')
        pg.wait_for_selector('.cr-lin-abrir', timeout=10000)
        n_mapas = pg.evaluate('CR_ST.mapas.length')
        confere(pg.locator('.cr-lin-abrir').count() == n_mapas and n_mapas > 0, 'uma linha por mapa')
        confere(pg.locator('.cr-mapa').count() == 0, 'sem os cartões antigos')
        confere(pg.locator('#cr-recentes [data-recente]').count() >= 1, 'mapa aberto aparece em Abertos por último')
        pg.locator('[data-menu-mapa]').first.click()
        confere(pg.locator('.cr-menu button:has-text("Excluir mapa")').is_visible(), 'menu ⋯ da linha com Excluir mapa')
        pg.keyboard.press('Escape')
        pg.screenshot(path=str(PRINTS / 'aplicacao_lista.png'))
        pg.evaluate("localStorage.setItem('cr-recentes-demo', JSON.stringify([{ id: 999999, cod_faz: CR_ST.faz.cod_faz,"
                    " operacao: 'arado', data: '2026-01-01' }])); crRenderRecentes();")
        pg.click('[data-recente="999999"]')
        pg.wait_for_selector('#cr-toast.show', timeout=5000)
        confere('não existe mais' in pg.locator('#cr-toast').inner_text(), 'recente de mapa excluído avisa')
        confere(pg.locator('#cr-recentes.off').count() == 1, 'recente de mapa excluído sai da lista')
        pg.locator('.cr-lin-abrir').first.click()
        pg.wait_for_function('CR_ST.geo && CR_ST.det', timeout=30000)
        confere(pg.locator('#cr-trabalho').is_visible(), 'clicar na linha abre o mapa')
        pg.click('#cr-voltar')
```

Rodar e ver FALHAR em "uma linha por mapa".

- [x] **Passo 2: HTML**

Em `app/aplicacao.html`, logo depois do `</div>` que fecha `<div class="cr-busca">`:

```html
      <div class="cr-recentes off" id="cr-recentes"></div>
```

- [x] **Passo 3: Recentes (JS)**

Acrescentar antes de `// ── Lista de mapas ──`:

```js
// ── Abertos por último (só neste navegador; a demonstração usa outra chave) ──
const CR_RECENTES_CHAVE = CR_DEMO ? 'cr-recentes-demo' : 'cr-recentes';
function crRecentes() {
  try { return crLerRecentes(localStorage.getItem(CR_RECENTES_CHAVE)); } catch (e) { return []; }
}
function crGuardarRecentes(lista) {
  try { localStorage.setItem(CR_RECENTES_CHAVE, JSON.stringify(lista)); } catch (e) { /* sem armazenamento: só não lembra */ }
  crRenderRecentes();
}
function crRenderRecentes() {
  const alvo = document.getElementById('cr-recentes');
  const lista = crRecentes();
  alvo.classList.toggle('off', !lista.length);
  alvo.innerHTML = '<span class="cr-recentes-tit">Abertos por último:</span>'
    + lista.map(r => `<button class="cr-chip" type="button" data-recente="${crEsc(r.id)}">${crEsc(`${r.cod_faz}, ${CR_OPERACOES[r.operacao] || r.operacao} ${crDataIso(r.data).slice(0, 5)}`)}</button>`).join('');
}
async function crAbrirRecente(id) {
  const esquecer = msg => { crGuardarRecentes(crRecentesSem(crRecentes(), id)); crToast(msg, true); };
  const r = crRecentes().find(x => String(x.id) === String(id));
  const f = r && CR_ST.fazendas.find(x => String(x.cod_faz) === String(r.cod_faz));
  if (!f) return esquecer('Esse mapa não está mais disponível.');
  if (!(await crEscolherFazenda(f))) return;          // falha de rede: mantém o atalho
  const m = CR_ST.mapas.find(x => String(x.id) === String(id));
  if (!m) return esquecer('Esse mapa não existe mais.');
  await crAbrirMapa(m);
}
```

Em `crCarregarFazendas`, depois do `try/catch` (só no caminho de sucesso), acrescentar `crRenderRecentes();` antes da
linha `if (CR_DEMO && …)`. Os atalhos só aparecem depois que as fazendas carregaram, para o clique achar a fazenda.

Em `crAbrirMapa`, logo depois de `CR_ST.insumos = insumos;` (dentro do `try`, depois do carregamento), acrescentar:

```js
    crGuardarRecentes(crRecentesCom(crRecentes(), { id: mapa.id, cod_faz: CR_ST.faz.cod_faz, operacao: mapa.operacao,
                                                    data: String(mapa.data).slice(0, 10) }));
```

Em `crIniciar`, acrescentar:

```js
  document.getElementById('cr-recentes').onclick = e => {
    const b = e.target.closest('[data-recente]');
    if (b) crAbrirRecente(b.dataset.recente);
  };
```

- [x] **Passo 4: Lista em linhas (JS)**

`crEscolherFazenda`: trocar `await crCarregarMapas();` e a linha seguinte por:

```js
  const ok = await crCarregarMapas();
  if (ok && abrirPrimeiro && CR_DEMO && CR_ST.mapas.length) crAbrirMapa(CR_ST.mapas[0]);
  return ok;
```

`crCarregarMapas`: depois de `crRenderMapas();`, acrescentar `return true;`. No `catch`, trocar o `if (CR_ST.faz !== faz) return;`
por `if (CR_ST.faz !== faz) return false;` e acrescentar `return false;` no fim do `catch`. No `try`, trocar o
`if (CR_ST.faz !== faz) return;` por `if (CR_ST.faz !== faz) return false;`.

Trocar `crRenderMapas` e `crCardMapa` por:

```js
function crRenderMapas() {
  crFecharMenu();
  const alvo = document.getElementById('cr-mapas');
  const n = CR_ST.mapas.length;
  document.getElementById('cr-faz-sub').textContent = `Código ${CR_ST.faz.cod_faz}. ${n === 1 ? '1 mapa' : `${n} mapas`}`;
  if (!n) {
    alvo.innerHTML = '<div class="cr-vazio"><span class="ico">compost</span><span>Nenhum mapa nesta fazenda.</span>'
      + '<button class="cr-btn" type="button" data-novo><span class="ico">add</span> Novo mapa</button></div>';
    return;
  }
  alvo.innerHTML = `<div class="cr-tab">
    <div class="cr-lin cr-tab-cab" aria-hidden="true"><div class="cr-lin-abrir">
      <span>Tipo</span><span>Data</span><span>O.S.</span><span class="num">Talhões</span><span class="num">Total</span><span>Alterado</span>
    </div><span class="cr-x-esp"></span></div>
    ${CR_ST.mapas.map(crLinhaMapa).join('')}
  </div>`;
}
function crLinhaMapa(m) {
  const op = CR_OPERACOES[m.operacao] || m.operacao;
  const total = crAerea(m.operacao) ? (m.insumos === 1 ? '1 insumo' : `${m.insumos} insumos`) : crTon(m.toneladas);
  return `<div class="cr-lin">
    <button class="cr-lin-abrir" type="button" data-abrir="${m.id}" aria-label="Abrir mapa ${crEsc(op)} de ${crDataIso(m.data)}">
      <span><span class="cr-op" style="--c:var(${CR_OP_VAR[m.operacao]})">${crEsc(op)}</span></span>
      <span class="cr-lin-data">${crDataIso(m.data)}</span>
      <span class="cr-lin-os">${m.os.length ? crEsc(m.os.join(', ')) : '—'}</span>
      <span class="num">${m.talhoes}</span>
      <span class="num">${total}</span>
      <span class="cr-lin-alt">${crEsc(m.alterado_por_nome)}, ${crDiaMes(m.alterado_em)}</span>
    </button>
    <button class="cr-x" type="button" data-menu-mapa="${m.id}" aria-haspopup="menu" aria-label="Ações do mapa ${crEsc(op)} de ${crDataIso(m.data)}"><span class="ico">more_horiz</span></button>
  </div>`;
}
```

Em `crIniciar`, no `onclick` de `cr-mapas`, trocar o ramo de `[data-excluir]` por:

```js
    const mm = e.target.closest('[data-menu-mapa]');
    if (mm) crMenu(mm, [{ rotulo: 'Excluir mapa', ico: 'delete', perigo: true, acao: () => crExcluir(mm.dataset.menuMapa) }]);
```

(A chamada `crAbrirMapa(CR_ST.mapas.find(…))` do ramo `[data-abrir]` continua igual. O subtítulo `cr-faz-sub` que
`crEscolherFazenda` preenche é sobrescrito por `crRenderMapas` com o número de mapas.)

- [x] **Passo 5: CSS**

Apagar as regras `.cr-grid`, `.cr-mapa`, `.cr-mapa-top`, `.cr-data`, `.cr-os`, `.cr-stats`, `.cr-stat small`,
`.cr-stat b` e `.cr-rod` (`.cr-esq` dentro de `.cr-grid` é o carregando da lista: em `crCarregarMapas`, trocar
`<div class="cr-grid" …>` por `<div class="cr-tab" aria-label="Carregando mapas" style="padding:16px;gap:8px">`).
Acrescentar:

```css
.cr-recentes{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.cr-recentes-tit{color:var(--t2);font-size:12px}
.cr-chip{background:var(--sf);border:1px solid var(--bd);border-radius:20px;padding:5px 12px;font-size:12px;color:var(--t1);cursor:pointer}
.cr-chip:hover{background:var(--s2)}
.cr-tab{display:flex;flex-direction:column}
.cr-lin{display:flex;align-items:center;gap:8px;border-top:1px solid var(--bd);padding-right:12px}
.cr-lin:hover{background:#f6f8fb}
.cr-lin-abrir{flex:1;min-width:0;display:grid;grid-template-columns:150px 100px minmax(0,1fr) 70px 110px 150px;gap:12px;align-items:center;background:none;border:0;padding:12px 0 12px 16px;text-align:left;cursor:pointer;color:var(--t1);font-size:13px}
.cr-lin-data{font-weight:600}
.cr-lin-os,.cr-lin-alt{color:var(--t2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cr-tab .num{text-align:right;font-variant-numeric:tabular-nums}
.cr-tab-cab,.cr-tab-cab:hover{background:var(--s2);border-top:0}
.cr-tab-cab .cr-lin-abrir{cursor:default;padding-block:10px;color:var(--t2);font-size:12px;font-weight:600}
.cr-x-esp{width:28px;flex-shrink:0}
@media (max-width:899px){
  .cr-tab-cab{display:none}
  .cr-lin-abrir{grid-template-columns:1fr 1fr}
}
```

- [x] **Passo 6: Rodar e ver passar**

Rodar: `node --test tests/app/*.test.js` e `python tests/app/teste_aplicacao_demo.py`. Esperado: tudo PASSA. Comparar
`.prints/aplicacao_lista.png` com o artboard "Lista" do canvas.

- [x] **Passo 7: Commit**

```bash
git add app/aplicacao.html app/corretivos.js app/corretivos.css tests/app/teste_aplicacao_demo.py
git commit -m "Mapas de aplicacao: lista de mapas em linhas, menu de acoes e abertos por ultimo"
```

---

### Tarefa 6: Novo mapa em dois passos

**Arquivos:**
- Modificar: `app/corretivos.js` (`crNovoMapa`; função nova `crEscolherNovoMapa`)
- Modificar: `app/corretivos.css` (seção "Diálogo")
- Modificar: `tests/app/teste_aplicacao_demo.py`

**Interfaces:**
- Produz: `crEscolherNovoMapa(): Promise<'subsolagem'|'supergrade'|'arado'|'aerea'|null>`
- Seletores que o E2E da Tarefa 7 usa: `[data-grupo="corretivo"|"aerea"]`, `.cr-seg-o:has([data-op="<op>"])`,
  `[data-criar]`.

- [x] **Passo 1: Acrescentar as conferências (falham)**

Antes de `# fim das conferências`:

```python
        # ── Tarefa 6: novo mapa em dois passos ──
        pg.click('#cr-novo')
        confere(pg.locator('.cr-nm-g').count() == 2, 'novo mapa: Corretivo e Aplicação aérea')
        confere(pg.locator('[data-criar]').inner_text() == 'Criar mapa de SubSolagem', 'começa em Corretivo, SubSolagem')
        pg.click('.cr-seg-o:has([data-op="arado"])')
        confere(pg.locator('[data-criar]').inner_text() == 'Criar mapa de Arado', 'botão acompanha a operação')
        pg.click('[data-grupo="aerea"]')
        confere(pg.locator('[data-op]').count() == 0, 'aérea não pede operação')
        confere(pg.locator('[data-criar]').inner_text() == 'Criar mapa de aplicação aérea', 'botão da aérea')
        pg.screenshot(path=str(PRINTS / 'aplicacao_novo.png'))
        pg.click('[data-cancel]')
        confere(pg.locator('#cr-modal-fundo.off').count() == 1, 'Cancelar fecha a janela')
        pg.click('#cr-novo')
        pg.click('[data-criar]')
        pg.wait_for_function("CR_ST.trab && CR_ST.trab.operacao === 'subsolagem' && CR_ST.det", timeout=30000)
        confere(pg.locator('#cr-trabalho').is_visible(), 'Criar abre o mapa novo')
```

Rodar e ver FALHAR em "novo mapa: Corretivo e Aplicação aérea".

- [x] **Passo 2: Implementar**

Acrescentar logo antes de `crNovoMapa`:

```js
// Janela "Novo mapa": primeiro Corretivo ou Aplicação aérea; para corretivo, a operação. Devolve a operação ou null.
function crEscolherNovoMapa() {
  return new Promise(resolver => {
    const fundo = document.getElementById('cr-modal-fundo');
    const est = { grupo: 'corretivo', op: 'subsolagem' };
    const ops = [['subsolagem', 'SubSolagem'], ['supergrade', 'SuperGrade'], ['arado', 'Arado']];
    const fechar = valor => { fundo.classList.add('off'); fundo.innerHTML = ''; resolver(valor); };
    const desenhar = () => {
      const aerea = est.grupo === 'aerea';
      fundo.innerHTML = `<form class="cr-modal cr-modal-novo" role="dialog" aria-modal="true" aria-labelledby="cr-nm-tit">
        <div><h3 id="cr-nm-tit">Novo mapa em ${crEsc(CR_ST.faz.nome)}</h3><p>Escolha o que o mapa vai mostrar.</p></div>
        <div class="cr-nm-grupos">
          <button class="cr-nm-g${aerea ? '' : ' on'}" type="button" data-grupo="corretivo" aria-pressed="${!aerea}">
            <span class="ico" aria-hidden="true">agriculture</span><b>Corretivo</b>
            <span>Calcário, fosfato ou blend, aplicado junto com uma operação de preparo do solo.</span></button>
          <button class="cr-nm-g${aerea ? ' on' : ''}" type="button" data-grupo="aerea" aria-pressed="${aerea}">
            <span class="ico" aria-hidden="true">flight</span><b>Aplicação aérea</b>
            <span>Insumos aplicados por avião, com dose na unidade de cada insumo e 5% de margem na área.</span></button>
        </div>
        ${aerea ? '' : `<fieldset class="cr-fs"><legend class="cr-lbl">Operação de preparo</legend>
          <div class="cr-seg">${ops.map(([v, r]) => `<label class="cr-seg-o"><input type="radio" name="cr-nm-op" value="${v}" data-op="${v}"${est.op === v ? ' checked' : ''}><span>${r}</span></label>`).join('')}</div>
        </fieldset>`}
        <div class="cr-md-acoes">
          <button class="cr-btn2" type="button" data-cancel>Cancelar</button>
          <button class="cr-btn" type="submit" data-criar>${aerea ? 'Criar mapa de aplicação aérea' : `Criar mapa de ${CR_OPERACOES[est.op]}`}</button>
        </div>
      </form>`;
      const form = fundo.querySelector('form');
      form.querySelector('[data-cancel]').onclick = () => fechar(null);
      form.onclick = e => {
        const g = e.target.closest('[data-grupo]');
        if (!g || g.dataset.grupo === est.grupo) return;
        est.grupo = g.dataset.grupo;
        desenhar();
        fundo.querySelector(`[data-grupo="${est.grupo}"]`).focus();
      };
      form.onchange = e => {
        if (!e.target.dataset.op) return;
        est.op = e.target.value;
        form.querySelector('[data-criar]').textContent = `Criar mapa de ${CR_OPERACOES[est.op]}`;
      };
      form.onsubmit = e => { e.preventDefault(); fechar(est.grupo === 'aerea' ? 'aerea' : est.op); };
    };
    fundo.onclick = e => { if (e.target === fundo) fechar(null); };
    desenhar();
    fundo.classList.remove('off');
    fundo.querySelector('[data-grupo]').focus();
  });
}
```

Em `crNovoMapa`, trocar o `const op = await crDialogo('Novo mapa', …, [ … ]);` inteiro por:

```js
  const op = await crEscolherNovoMapa();
```

CSS, na seção "Diálogo":

```css
.cr-modal-novo{width:min(600px,calc(100vw - 32px));display:flex;flex-direction:column;gap:16px}
.cr-nm-grupos{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.cr-nm-g{display:flex;flex-direction:column;align-items:flex-start;gap:6px;text-align:left;background:var(--sf);border:2px solid var(--bd);border-radius:14px;padding:16px;cursor:pointer;color:var(--t1)}
.cr-nm-g .ico{font-size:28px;color:var(--t2)}
.cr-nm-g b{font-size:15px;font-weight:600}
.cr-nm-g span:last-child{color:var(--t2);font-size:12px;line-height:1.45}
.cr-nm-g.on{border-color:var(--plantio);background:#f3fbf7}
.cr-nm-g.on .ico{color:var(--plantio)}
@media (max-width:639px){.cr-nm-grupos{grid-template-columns:1fr}}
```

- [x] **Passo 3: Rodar e ver passar**

Rodar: `python tests/app/teste_aplicacao_demo.py`. Esperado: PASSA. Comparar `.prints/aplicacao_novo.png` com o
artboard "Novo mapa".

- [x] **Passo 4: Commit**

```bash
git add app/corretivos.js app/corretivos.css tests/app/teste_aplicacao_demo.py
git commit -m "Mapas de aplicacao: novo mapa em dois passos (corretivo ou aerea, depois a operacao)"
```

---

### Tarefa 7: E2E real, manual e verificação final

**Arquivos:**
- Modificar: `tests/app/teste_corretivos_tela.py`
- Modificar: `docs/mapas-aplicacao-manual.md`

**Interfaces:**
- Consome os seletores das Tarefas 5 e 6.

- [x] **Passo 1: Trocar os seletores do E2E**

Em `tests/app/teste_corretivos_tela.py`:

- criação do mapa Arado: trocar
  `pg.click('[data-novo]'); pg.click('#cr-modal-fundo button:has-text("Arado")')` por
  `pg.click('[data-novo]'); pg.click('.cr-seg-o:has([data-op="arado"])'); pg.click('[data-criar]')`
- criação do mapa aéreo: trocar
  `pg.click('#cr-novo'); pg.click('#cr-modal-fundo button:has-text("Aplicação aérea")')` por
  `pg.click('#cr-novo'); pg.click('[data-grupo="aerea"]'); pg.click('[data-criar]')`
- exclusão (as duas vezes, com `mapa_id` e com `mapa_aereo`): trocar
  ``pg.wait_for_selector(f'[data-excluir="{X}"]', …)`` por ``pg.wait_for_selector(f'[data-menu-mapa="{X}"]', timeout=20000)``
  e ``pg.click(f'[data-excluir="{X}"]')`` por
  ``pg.click(f'[data-menu-mapa="{X}"]'); pg.click('.cr-menu button:has-text("Excluir mapa")')``.
  O clique seguinte, `pg.click('#cr-modal-fundo button:has-text("Excluir")')`, continua igual.

Nada mais muda: o `aplicar()` do teste marca talhões por `CR_ST.sel` e chama `crRenderPainel()`, e `[data-aplicar]`
e `[data-pdf]` continuam existindo.

- [x] **Passo 2: Manual**

Em `docs/mapas-aplicacao-manual.md`, reescrever os trechos que descrevem a lista, a criação e a tela do mapa para
dizer:
- **Lista:** os mapas aparecem em linhas e é só clicar na linha para abrir. Excluir fica no botão "⋯" da linha. Embaixo
  da busca, "Abertos por último" leva direto aos 3 últimos mapas abertos neste computador.
- **Novo mapa:** escolha Corretivo ou Aplicação aérea. No corretivo, escolha a operação. O botão diz o mapa que vai ser
  criado.
- **Tela do mapa:** o mapa ocupa a tela, e o Baixar PDF fica no alto, à direita. Passe o mouse num talhão para ver a
  área e o que já foi aplicado nele. Clique nos talhões para marcar: a barra embaixo do mapa mostra quantos estão
  marcados e a soma em hectares. Com talhões marcados, a coluna da direita abre "Nova aplicação". A área de um talhão
  só muda em "Ajustar a área de algum talhão". A lista "Aplicações do mapa" é a legenda das cores: clique num cartão
  para destacar os talhões, e use o "⋯" para editar ou excluir. O total do mapa fica sempre no pé da coluna.

- [x] **Passo 3: Verificação completa**

Rodar, nesta ordem, e anotar a saída:
1. `node --test tests/app/*.test.js`, esperado: tudo PASSA.
2. `python tests/app/teste_aplicacao_demo.py`, esperado: `0 falha(s)`.
3. `python -m pytest tests/drone/test_mapa_pdf_regressao.py -q`, esperado: PASSA (o PDF não mudou).
4. E2E real (precisa da conta de teste; mexe no banco, mas só apaga o que cria):
   `set HUB_CONTA_TESTE=<caminho do conta-teste.json>` e `python tests/app/teste_corretivos_tela.py`. Esperado: todas
   as linhas `ok` e nenhuma `FALHA`. Se a variável não estiver disponível para quem executa, **parar e avisar**:
   esse passo fica com o Claude principal.

- [x] **Passo 4: Commit**

```bash
git add tests/app/teste_corretivos_tela.py docs/mapas-aplicacao-manual.md
git commit -m "Mapas de aplicacao: E2E com os seletores novos e manual das telas novas"
```
