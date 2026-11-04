# Título do tipo e layout do Aéreo (tela + PDF) — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** destacar o tipo do mapa no carimbo do PDF (corretivo e aéreo) e, no aéreo, usar os mesmos talhões para
todos os insumos (tela), com tabela TALHÃO | ÁREA | TOTAL, mapa de uma cor só, insumos na legenda e cards maiores (PDF).

**Architecture:** PDF em Python (`mapas/corretivo_dados.py` calcula, `mapas/corretivo_pdf.py` desenha; roda no
navegador via Pyodide, copiado por `mapas/publicar.py` no deploy). Tela em JS puro (`app/corretivos.js`, funções
`cr*`, estado em `CR_ST`). Banco sem mudança: cada insumo continua uma linha em `corretivo_aplicacoes` com sua lista
de talhões; a tela passa a manter todas as listas iguais.

**Tech Stack:** Python 3 + matplotlib/geopandas + pytest/pymupdf; JS sem build + `node --test`; Playwright (E2E).

**Spec:** `docs/superpowers/specs/2026-10-28-mapa-aereo-layout-design.md`

## Global Constraints

- Única migração: a do Experimento (Task 6); RPCs `corretivo_aplicar` / `corretivo_editar_aplicacao` usadas como estão.
- `mapas/layout.py` não muda; `pytest tests/drone/test_mapa_pdf_regressao.py` continua passando.
- Corretivo: só o título do tipo muda (tabela, mapa, cards e tela ficam iguais).
- Cor única do aéreo = `PALETA_INSUMOS[0]` (`'#2f6db5'`) no Python e `CR_PALETA_INSUMOS[0]` no JS.
- Totais por unidade: L e kg nunca se somam; texto `'29,45 L + 3,00 kg'` (ordem de aparição das unidades).
- Testes JS: `node --test tests/app/*.test.js` (sem o glob o Node 22 não acha os testes).
- E2E real salva/restaura: só apaga o que o próprio teste criou.
- Textos da tela em português do Brasil, no tom dos que já existem.

## Review Focus

- Mapa aéreo antigo com insumos em talhões diferentes: PDF soma por talhão o que está gravado; a tela mostra a união
  e "Incluir"/"Tirar" iguala todas as listas. (Teste no Task 1 e no Task 4.)
- Mapa com L e kg: célula, linha 400 e linha Total com as duas unidades, sem estourar a coluna. (Task 1 e Task 3.)
- Talhão do mapa sem insumo (todas as aplicações sem ele): linha com `—`, cor `SEM_APLICACAO`. (Task 1.)
- "Tirar do mapa" de todos os talhões: bloqueado com mensagem, nada é gravado. (Task 4.)
- Falha no meio da regravação (um insumo gravou, outro não): aviso e recarga; repetir iguala. (Task 5, manual.)

---

### Task 1: Dados do aéreo — tabela de três colunas e linha Total

**Files:**
- Modify: `mapas/corretivo_dados.py` (`linhas_tabela`, nova `linha_total`, novas auxiliares)
- Test: `tests/mapas/test_aerea_dados.py`

**Interfaces:**
- Produces: `linhas_tabela(dados)` no aéreo devolve `[[talhão, área_txt, total_txt], …, ['400', margem_txt, total_margem_txt]]`
  (corretivo continua com 6 colunas); `linha_total(dados) -> list[str]` (aéreo: `['Total', área_total_txt, total_txt]`,
  corretivo: `['Total', área_total_txt, '', '', '', '']`); `COR_AEREA = PALETA_INSUMOS[0]`.

- [x] **Step 1: Teste que falha.** Em `tests/mapas/test_aerea_dados.py`, troque
  `test_tabela_tem_unidade_junto_do_numero_e_talhao_400_so_com_area` por:

```python
def test_tabela_do_aereo_tem_talhao_area_e_total_somado_por_unidade():
    # talhão 1: Revolux 60 × 0,5 + Adjuvante 60 × 0,1 = 36 L; talhão 2: Revolux 40 × 0,5 = 20 L e Regulador 40 × 0,008 kg
    # 400: margem 5,00 ha; L = 100 × 0,05 × 0,5 + 60 × 0,05 × 0,1 = 2,8; kg = 40 × 0,05 × 0,008 = 0,016
    assert linhas_tabela(DADOS) == [
        ['1', '60,00', '36,00 L'],
        ['2', '40,00*', '20,00 L + 0,32 kg'],
        ['400', '5,00', '2,80 L + 0,02 kg'],
    ]


def test_linha_total_do_aereo_fecha_com_os_cards():
    assert linha_total(DADOS) == ['Total', '105,00', '58,80 L + 0,34 kg']        # 52,5 + 6,3 L; 0,336 kg


def test_talhao_do_mapa_sem_insumo_fica_com_traco():
    d = {**DADOS, 'areas': {**DADOS['areas'], '3': {'area_ha': 10.0}}}
    assert linhas_tabela(d)[2] == ['3', '10,00', '—']


def test_linha_total_do_corretivo_continua_com_seis_colunas():
    d = {'operacao': 'subsolagem', 'areas': {'1': {'area_ha': 10.0}},
         'aplicacoes': [{'tipo': 'fosfato', 'calcario': None, 'dose': 1.0, 'dose_gesso': None, 'os': '1', 'ordem': 1, 'talhoes': [1]}]}
    assert linha_total(d) == ['Total', '10,00', '', '', '', '']
```

  E no import do topo acrescente `linha_total`.

- [x] **Step 2:** `python -m pytest tests/mapas/test_aerea_dados.py -q` → FAIL (`ImportError: linha_total`).

- [x] **Step 3: Implementação.** Em `mapas/corretivo_dados.py`, depois de `PALETA_INSUMOS`:

```python
COR_AEREA = PALETA_INSUMOS[0]          # aéreo: todos os talhões do mapa numa cor só (spec 2026-10-28)
```

  Antes de `linhas_tabela`:

```python
def _por_unidade(soma: dict) -> str:
    """{'L': 29.45, 'kg': 3.0} -> '29,45 L + 3,00 kg' (L e kg não se somam); vazio -> '—'."""
    return ' + '.join(f'{br(v)} {un}' for un, v in soma.items()) or '—'


def _somar(soma: dict, un: str, v: float):
    soma[un] = soma.get(un, 0.0) + v


def _linhas_aerea(dados) -> list[list[str]]:
    """Aéreo: TALHÃO | ÁREA | TOTAL (soma de área × dose de todos os insumos do talhão, por unidade)."""
    linhas = []
    for chave in sorted(dados['areas'], key=int):
        t = int(chave)
        area = _area(dados, t)
        soma: dict = {}
        for a in _ordenadas(dados):
            if t in a['talhoes']:
                _somar(soma, unidade(a), area * a['dose'])
        linhas.append([str(t), br(area) + ('*' if dados['areas'][chave].get('editada') else ''), _por_unidade(soma)])
    soma = {}
    for a in _ordenadas(dados):            # margem de cada insumo = 5% da área dos talhões dele × dose
        _somar(soma, unidade(a), sum(_area(dados, t) for t in a['talhoes']) * MARGEM_AEREA * a['dose'])
    linhas.append([TALHAO_MARGEM, br(margem(dados)), _por_unidade(soma)])
    return linhas


def linha_total(dados) -> list[str]:
    if not aerea(dados):
        return ['Total', br(area_total(dados)), '', '', '', '']
    soma: dict = {}
    for q in _totais_insumos(dados):
        _somar(soma, q['unidade'], q['total'])
    return ['Total', br(area_total(dados)), _por_unidade(soma)]
```

  Em `linhas_tabela`, logo no começo: `if aerea(dados): return _linhas_aerea(dados)`; e apague o bloco final
  `if aerea(dados): linhas.append([TALHAO_MARGEM, …])`. Observação: `linha_total` soma os totais já arredondados dos
  cards, então o Total bate com os cards.

- [x] **Step 4:** `python -m pytest tests/mapas/test_aerea_dados.py tests/mapas/test_corretivo_dados.py -q` → PASS.

- [x] **Step 5: Commit** — `git add mapas/corretivo_dados.py tests/mapas/test_aerea_dados.py && git commit -m "Aereo: tabela com talhao, area e total somado por unidade"`

---

### Task 2: PDF — título do tipo (os dois) e cards maiores (aéreo)

**Files:**
- Modify: `mapas/corretivo_pdf.py` (`_carimbo`, `_quadros`, `_tamanho_titulos`, `_altura_carimbo`, `gerar_pdf`)
- Test: `tests/mapas/test_aerea_pdf.py`, `tests/mapas/test_corretivo_pdf.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: `_altura_carimbo(f, totais, grande: bool)`; `_quadros(pg, totais, x, y, w, por_linha, grande: bool)`.

- [x] **Step 1: Testes que falham.** Em `tests/mapas/test_aerea_pdf.py`, acrescente:

```python
def _spans(destino):
    doc = pymupdf.open(destino)
    return [s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans'] if s['text'].strip()]


@pytest.fixture(scope='module')
def spans_aereo(tmp_path_factory):
    destino = tmp_path_factory.mktemp('aereo_sp') / 'a.pdf'
    gerar_pdf(CASOS['aereo_em_pe_3_insumos'], destino)
    return _spans(destino)


def test_tipo_do_mapa_e_titulo_em_destaque(spans_aereo):
    tit = [s for s in spans_aereo if s['text'].strip() == 'APLICAÇÃO AÉREA']
    assert tit and tit[0]['size'] >= 10, 'tipo do mapa precisa ser título (>= 10 pt)'


def test_cards_de_totais_maiores(spans_aereo):
    from mapas.corretivo_dados import totais_por_produto
    titulos = {q['titulo'] for q in totais_por_produto(CASOS['aereo_em_pe_3_insumos'])}
    tam = [s['size'] for s in spans_aereo if s['text'].strip() in titulos and s['size'] < 11]
    assert tam and min(tam) >= 5.9, f'nome do insumo nos cards pequeno demais: {tam}'
```

  Em `tests/mapas/test_corretivo_pdf.py`, acrescente (use o caso de 1 linha do layout):

```python
def test_tipo_do_corretivo_e_titulo_em_destaque(tmp_path):
    from tests.mapas.test_corretivo_layout import CASOS
    destino = tmp_path / 'c.pdf'
    gerar_pdf(CASOS['1_linha'], destino)
    spans = [s for b in pymupdf.open(destino)[0].get_text('dict')['blocks'] for l in b.get('lines', [])
             for s in l['spans'] if s['text'].strip().startswith('CORRETIVO ·')]
    assert spans and spans[0]['size'] >= 10
```

  (Se `pymupdf` não estiver importado no arquivo, importe como no topo de `test_aerea_pdf.py`.)

- [x] **Step 2:** `python -m pytest tests/mapas/test_aerea_pdf.py tests/mapas/test_corretivo_pdf.py -q` → os três novos FAIL.

- [x] **Step 3: Título.** Em `_carimbo`, troque o bloco da etiqueta (de `tag = …` até `y = yb + 7.5`) por:

```python
    tipo = 'APLICAÇÃO AÉREA' if aerea(dados) else f"CORRETIVO · {OPERACOES[dados['operacao']].upper()}"
    tipo_txt, tt = _caber(pg, tipo, WA - 6, TIPO_TAM, 7, 'bold')
    pg.texto(x, yb + 2.3, tipo_txt, tt, MARCA, 'bold')
    y = yb + 2.3 + tt * 0.3528 * 1.35
```

  e nas constantes do topo: `TIPO_TAM = 11                     # tipo do mapa, título do carimbo (28/10: era etiqueta de 4,5 pt)`.

- [x] **Step 4: Cards.** Parametrize por `grande` (aéreo):

```python
CARD = {False: dict(h=15, passo=18, tit=(4.8, 4.0), val=(12, 9), un=5.5, y_val=5, y_un=6.8),
        True: dict(h=20, passo=23, tit=(6.5, 5.0), val=(16, 11), un=8, y_val=6.2, y_un=8.6)}


def _altura_carimbo(f: Folha, totais, grande=False) -> float:
    rows = max(1, math.ceil(len(totais) / f.por_linha))
    c = CARD[grande]
    return max(24.0, c['h'] + 4 + c['passo'] * (rows - 1))


def _tamanho_titulos(pg: Pagina, titulos, max_mm: float, inicio=4.8, minimo=4.0) -> float:
    """Um tamanho só para todos os títulos dos quadros, reduzido (até o mínimo) se algum não couber."""
    tam = inicio
    for t in titulos:
        while tam > minimo and _largura(pg, t, tam, 'semibold') > max_mm:
            tam -= 0.1
    return round(tam, 1)
```

  Em `_quadros(pg, totais, x, y, w, por_linha, grande=False)`: `c = CARD[grande]`; use `c['h']` na altura da caixa,
  `c['passo']` no lugar de `18`, `_tamanho_titulos(pg, …, cw - 5, *c['tit'])`, `_caber(pg, br(q['total']), cw - 5 - 7, *c['val'], 'bold')`
  com `cy + c['y_val']`, e a unidade com `c['un']` em `cy + c['y_un']`. Em `_carimbo`:
  `_quadros(pg, totais, xb, yb, f.wb, f.por_linha, aerea(dados))`. Em `gerar_pdf`: `hb = _altura_carimbo(f, totais, aerea(dados))`.

- [x] **Step 5:** `python -m pytest tests/mapas -q` → PASS (inclusive `test_nenhum_texto_sobre_outro` e
  `test_nenhum_texto_sai_da_margem` para todos os casos; se o título sobrepuser o nome da fazenda, aumente o
  fator `1.35`). `python -m pytest tests/drone/test_mapa_pdf_regressao.py -q` → PASS.

- [x] **Step 6: Commit** — `git commit -am "PDF dos mapas: tipo do mapa como titulo e cards maiores no aereo"`

---

### Task 3: PDF aéreo — tabela de três colunas, mapa de uma cor e legenda com os insumos

**Files:**
- Modify: `mapas/corretivo_pdf.py` (`COLUNAS_AEREA`, `NOTA_AEREA`, `_linha_tabela`, `_mapa`, `_itens_legenda`, `_legenda_mapa`, `gerar_pdf`)
- Test: `tests/mapas/test_aerea_pdf.py`, `tests/mapas/test_corretivo_layout.py`

**Interfaces:**
- Consumes: `linhas_tabela`, `linha_total`, `COR_AEREA` (Task 1).

- [x] **Step 1: Testes.** Em `tests/mapas/test_aerea_pdf.py`:
  - Troque `test_unidade_do_insumo_na_tabela_e_nos_quadros` por:

```python
def test_tabela_so_com_talhao_area_e_total(texto):
    assert 'TALHÃO' in texto and 'ÁREA (ha)' in texto and 'TOTAL' in texto
    for fora in ('INSUMO', 'DOSE/ha', 'O.S.\n'):
        assert fora not in texto, f'{fora!r} não deveria estar no PDF aéreo'
    assert '+ 0,' in texto and 'kg' in texto            # talhões 1–3 têm L e kg: total com as duas unidades


def test_legenda_tem_area_de_aplicacao_e_os_insumos(texto):
    from mapas.corretivo_dados import nome_insumo
    from tests.mapas.test_corretivo_layout import INSUMOS
    assert 'Área de aplicação' in texto
    for i in (0, 1, 3):
        assert nome_insumo(INSUMOS[i]) in texto
```

  - Em `test_total_grande_nao_encosta_na_dose_nem_na_os`, renomeie para `test_total_grande_cabe_na_coluna` e troque o
    corpo do laço para: achar o span `'104.000,00 L'`, e conferir que fica dentro da folha
    (`s['bbox'][2] <= p.rect.width - 10 * 72 / 25.4`) e a mais de 8 pt do vizinho da esquerda (a área).
  - Em `test_talhao_400_com_a_margem_e_total_com_ela`, mantenha (a área da margem continua na linha seguinte ao 400).

  Em `tests/mapas/test_corretivo_layout.py`, os casos `aereo_*` não têm mais rótulo na tabela:
  - `test_tabela_e_legenda_com_letra_grande`: para `nome.startswith('aereo')`, as células da tabela são os spans que
    casam `re.compile(r'\d,\d\d (L|kg)')`; confira o tamanho delas em vez dos rótulos.
  - `test_cada_linha_aparece_uma_vez_e_inteira`: para `aereo*`, troque a conferência de dose por: cada talhão
    `1..n` aparece como texto exato de algum span da tabela (fonte 12 pt) ao menos uma vez.
  - `test_toda_pagina_organizada`: o cabeçalho exige `'O.S.'` só quando não for aéreo; no aéreo, exija
    `'TALHÃO' in texto` nas páginas que têm células `\d,\d\d (L|kg)` a 12 pt.

- [x] **Step 2:** `python -m pytest tests/mapas -q` → os novos/ajustados FAIL.

- [x] **Step 3: Tabela.**

```python
# Aéreo (28/10): só TALHÃO | ÁREA | TOTAL (soma dos insumos, por unidade). O insumo fica na legenda e nos cards.
COLUNAS_AEREA = [('TALHÃO', 2, 'left'), ('ÁREA (ha)', 60, 'right'), ('TOTAL', 186, 'right')]
NOTA_AEREA = '* área editada · talhão 400 = margem de 5% da área · TOTAL = soma dos insumos do talhão'
```

  Em `_linha_tabela`, troque os dois casos especiais por:

```python
        if i == ultima and aerea(dados):              # TOTAL: reduz/corta para caber depois da ÁREA
            valor, tam = _caber(pg, valor, x - f.col(colunas[1][1]) - 10, LETRA_LINHA, 9)
        elif i == ultima:                             # O.S.: reduz/corta para caber na coluna
            valor, tam = _caber(pg, valor, M + f.larg - x - 1, LETRA_LINHA, 9)
```

  Em `gerar_pdf`, troque `total = ['Total', br(area_total(dados)), '', '', '', '']` por `total = linha_total(dados)`
  (importe `linha_total` e `COR_AEREA` de `mapas.corretivo_dados`).

- [x] **Step 4: Mapa de uma cor.** Em `_mapa`, no ramo `else:` (talhão com aplicação), antes do laço das faixas:

```python
        elif aerea(dados):                          # aéreo: todos os insumos em todos os talhões, uma cor só
            gpd.GeoSeries([geom], crs=gdf.crs).plot(ax=ax, facecolor=COR_AEREA, edgecolor='none', alpha=0.92)
```

  (fica entre `if not aps:` e o `else:` das faixas).

- [x] **Step 5: Legenda.** Em `_itens_legenda`, no começo:

```python
    if aerea(dados):                             # um quadrado só e, embaixo, o nome de cada insumo
        nomes = list(dict.fromkeys(rotulo(a) for a in _ordenadas(dados)))
        return [(COR_AEREA, 'Área de aplicação')] + [('', n) for n in nomes] if nomes else []
```

  Em `_legenda_mapa`, trate `cor == ''` (insumo do aéreo): texto em `GRAFITE`, alinhado com os textos que têm
  quadrado (`bx + pad + sw + 2.5`), sem quadrado. `_ordenadas` vem de `mapas.corretivo_dados` (importe se ainda não estiver).

- [x] **Step 6:** `python -m pytest tests/mapas tests/drone/test_mapa_pdf_regressao.py -q` → PASS. Gere e olhe os
  dois PDFs aéreos dos casos (`aereo_em_pe_3_insumos`, `aereo_largo_8_insumos`) em `.prints/` para conferir à vista.

- [x] **Step 7: Commit** — `git commit -am "PDF aereo: tabela talhao/area/total, mapa de uma cor e insumos na legenda"`

---

### Task 4: Tela — funções puras do aéreo

**Files:**
- Modify: `app/corretivos.js` (perto de `crCoresTalhao`, linha ~59)
- Test: `tests/app/aerea_puro.test.js`

**Interfaces:**
- Produces: `crTalhoesDoMapa(apls) -> number[]` (união ordenada); `crCoresTalhaoMapa(apls, t, operacao) -> string[]`
  (aéreo: `[CR_PALETA_INSUMOS[0]]` se algum insumo tem o talhão, senão `[]`; corretivo: `crCoresTalhao`);
  `crRegravacoes(apls, talhoes) -> [{ apl, talhoes }]` (só as aplicações cuja lista difere de `talhoes`, ordenada);
  `crIncluir(atuais, sel)` e `crTirar(atuais, sel)` -> `number[]` ordenados.

- [x] **Step 1: Teste que falha** (no fim de `tests/app/aerea_puro.test.js`):

```js
test('aéreo: talhões do mapa são a união, uma cor só e regravação só do que difere', () => {
  igual(ctx.crTalhoesDoMapa(APLS), [1, 2]);
  igual(ctx.crTalhoesDoMapa([]), []);
  igual(ctx.crCoresTalhaoMapa(APLS, 2, 'aerea'), ['#2f6db5']);
  igual(ctx.crCoresTalhaoMapa(APLS, 9, 'aerea'), []);
  igual(ctx.crIncluir([1, 2], [3, 1]), [1, 2, 3]);
  igual(ctx.crTirar([1, 2, 3], [2]), [1, 3]);
  igual(ctx.crRegravacoes(APLS, [1, 2]).map(r => [r.apl.insumo_id, r.talhoes]), [[2, [1, 2]], [3, [1, 2]]]);
  igual(ctx.crRegravacoes(APLS, [1, 2, 3]).length, 3);
});
```

- [x] **Step 2:** `node --test tests/app/*.test.js` → FAIL (`crTalhoesDoMapa is not a function`).

- [x] **Step 3: Implementação** (depois de `crCoresTalhao`):

```js
// Aéreo (spec 2026-10-28): todos os insumos valem para os mesmos talhões, os "talhões do mapa".
function crTalhoesDoMapa(apls) { return [...new Set(apls.flatMap(a => a.talhoes))].sort((a, b) => a - b); }
function crCoresTalhaoMapa(apls, talhao, operacao) {
  if (!crAerea(operacao)) return crCoresTalhao(apls, talhao);
  return apls.some(a => a.talhoes.includes(talhao)) ? [CR_PALETA_INSUMOS[0]] : [];
}
function crIncluir(atuais, sel) { return [...new Set([...atuais, ...sel])].sort((a, b) => a - b); }
function crTirar(atuais, sel) { return atuais.filter(t => !sel.includes(t)); }
function crRegravacoes(apls, talhoes) {
  const alvo = [...talhoes].sort((a, b) => a - b).join(',');
  return crOrdenadas(apls).filter(a => [...a.talhoes].sort((x, y) => x - y).join(',') !== alvo)
    .map(apl => ({ apl, talhoes: [...talhoes].sort((a, b) => a - b) }));
}
```

- [x] **Step 4:** `node --test tests/app/*.test.js` → PASS.

- [x] **Step 5: Commit** — `git commit -am "Tela aereo: funcoes de talhoes do mapa e cor unica"`

---

### Task 5: Tela — fluxo do aéreo (talhões do mapa, novo insumo, editar), demo e E2E

**Files:**
- Modify: `app/corretivos.js` (`crFeicoesMapa`, `crRenderPainel`, `crSecaoNova`, `crAplicarMarcadosAgora`,
  `crEditarAplicacao`, `crLigarTrabalho`), `app/corretivos.css` só se precisar de espaçamento dos dois botões
- Test: `tests/app/teste_aplicacao_demo.py`, `tests/app/teste_corretivos_tela.py`

**Interfaces:**
- Consumes: `crTalhoesDoMapa`, `crCoresTalhaoMapa`, `crIncluir`, `crTirar`, `crRegravacoes` (Task 4);
  `crApi().editarAplicacao(mapaId, aplId, { tipo, calcario, insumo_id, dose, dose_gesso, os, talhoes, areas })`.

- [x] **Step 1: Mapa.** Em `crFeicoesMapa`, troque `crCoresTalhao(apls, t)` por
  `crCoresTalhaoMapa(apls, t, CR_ST.trab.operacao)`.

- [x] **Step 2: Painel.** Em `crRenderPainel`, no aéreo (`aerea`), troque
  `${sel.length ? crSecaoNova(sel, aerea) : crSecaoDica()}` por `${crSecaoTalhoesAerea(sel)}${crSecaoInsumoAerea(sel)}`
  (corretivo continua igual). Novas funções:

```js
// Aéreo: os talhões marcados entram ou saem do mapa para todos os insumos de uma vez.
function crSecaoTalhoesAerea(sel) {
  if (!sel.length) return `<section class="cr-sec cr-nova-dica"><p class="cr-msg">Marque talhões no mapa para incluir ou tirar do mapa.</p></section>`;
  const doMapa = crTalhoesDoMapa(CR_ST.det.apls);
  const entra = sel.filter(t => !doMapa.includes(t));
  const sai = sel.filter(t => doMapa.includes(t));
  const n = k => (k === 1 ? '1 talhão' : `${k} talhões`);
  const abertas = CR_ST.areasAbertas;
  return `<section class="cr-sec" aria-labelledby="cr-h-tal">
      <h2 id="cr-h-tal">Talhões do mapa</h2>
      <div class="cr-md-acoes">
        ${entra.length ? `<button class="cr-btn" type="button" data-incluir>Incluir ${n(entra.length)} no mapa</button>` : ''}
        ${sai.length ? `<button class="cr-btn2" type="button" data-tirar>Tirar ${n(sai.length)} do mapa</button>` : ''}
      </div>
      <button class="cr-link" type="button" data-areas aria-expanded="${abertas}"><span class="ico" aria-hidden="true">${abertas ? 'expand_more' : 'chevron_right'}</span> Ajustar a área de algum talhão</button>
      ${abertas ? `<div class="cr-sel-lista">${sel.map(t => `<label class="cr-sel-l"><span>Talhão ${t}, área (ha)</span>
          <input class="cr-inp cr-inp-sm" type="number" step="0.01" min="0" value="${crAreaDe(t).area_ha}" data-area="${t}"></label>`).join('')}</div>` : ''}
    </section>`;
}
// Aéreo: novo insumo vale para todos os talhões do mapa (ou para os marcados, se o mapa ainda não tem talhões).
function crSecaoInsumoAerea(sel) {
  const f = CR_ST.form;
  const doMapa = crTalhoesDoMapa(CR_ST.det.apls);
  const alvo = doMapa.length ? doMapa : sel;
  return `<section class="cr-sec cr-nova" aria-labelledby="cr-h-nova">
      <h2 id="cr-h-nova">Novo insumo</h2>
      ${crCamposAerea(f)}
      <div><label class="cr-lbl" for="cr-f-os">O.S.</label>
        <input class="cr-inp" id="cr-f-os" type="text" data-f="os" value="${crEsc(f.os)}"></div>
      ${crMsgForm()}
      <button class="cr-btn cr-btn-bloco" type="button" data-aplicar${alvo.length ? '' : ' disabled'}>${alvo.length ? crEsc(crTextoAplicar(alvo).replace(/^Aplicar/, 'Adicionar')) : 'Marque os talhões do mapa'}</button>
    </section>`;
}
```

  Confira em `crLigarTrabalho` como `[data-areas]` e `[data-area]` são ligados e reaproveite (a lista usa `sel`,
  igual à `crSecaoNova`). Ligue `[data-incluir]` e `[data-tirar]` no mesmo `closest(...)` do clique do painel
  (linha ~1487) chamando `crMudarTalhoesAerea('incluir')` / `crMudarTalhoesAerea('tirar')`.

- [x] **Step 3: Gravar talhões.**

```js
async function crMudarTalhoesAerea(acao) {
  if (CR_ST.gravando) return;
  const sel = crSelecionados();
  const atuais = crTalhoesDoMapa(CR_ST.det.apls);
  const novos = acao === 'incluir' ? crIncluir(atuais, sel) : crTirar(atuais, sel);
  if (!novos.length) {
    CR_ST.formMsg = { tipo: 'erro', texto: 'O mapa precisa ter ao menos um talhão. Para começar de novo, exclua os insumos.' };
    return crRenderPainel();
  }
  const areas = {};
  for (const t of novos) areas[t] = crAreaDe(t);
  if (!CR_ST.det.apls.length) {             // sem insumo ainda: os marcados viram os talhões do primeiro insumo
    CR_ST.formMsg = { tipo: 'info', texto: 'Adicione o primeiro insumo para gravar os talhões do mapa.' };
    return crRenderPainel();
  }
  CR_ST.gravando = true;
  const fim = Mo.ocupado(document.querySelector(acao === 'incluir' ? '[data-incluir]' : '[data-tirar]'), { texto: 'Gravando…' });
  let ok = true;
  try {
    for (const { apl, talhoes } of crRegravacoes(CR_ST.det.apls, novos)) {
      await crApi().editarAplicacao(CR_ST.trab.id, apl.id, { tipo: apl.tipo, calcario: apl.calcario, insumo_id: apl.insumo_id,
        dose: apl.dose, dose_gesso: apl.dose_gesso, os: apl.os, talhoes, areas });
    }
  } catch (e) {
    ok = false;
    crToast('Não foi possível atualizar todos os insumos. Tente de novo.', true);
  } finally {
    CR_ST.gravando = false;
    fim(ok);
  }
  if (ok) crToast(acao === 'incluir' ? 'Talhões incluídos no mapa.' : 'Talhões tirados do mapa.');
  CR_ST.sel = new Set();
  CR_ST.areasAbertas = false;
  CR_ST.areaNova = {};
  await crRecarregar();
}
```

- [x] **Step 4: Novo insumo.** Em `crAplicarMarcadosAgora`, no aéreo use
  `const talhoes = aerea ? (crTalhoesDoMapa(CR_ST.det.apls).length ? crTalhoesDoMapa(CR_ST.det.apls) : crSelecionados()) : crSelecionados();`
  A mensagem de validação sem talhão (`crValidarAplicacao`) já cobre o caso vazio.

- [x] **Step 5: Editar insumo.** Em `crEditarAplicacao`, quando `a.tipo === 'insumo'`, não desenhe o `fieldset` de
  Talhões e, no `onsubmit`, use `talhoes = a.talhoes` em vez das caixas marcadas.

- [x] **Step 6: Demo.** Em `tests/app/teste_aplicacao_demo.py` (bloco aéreo, linha ~68): marque 2 talhões, adicione
  o insumo (`[data-aplicar]`), adicione um segundo insumo sem marcar nada e confira em `CR_ST.det.apls` que os dois têm
  os mesmos talhões; marque um terceiro talhão, clique `[data-incluir]` e confira os três nos dois insumos; marque
  um, clique `[data-tirar]` e confira. Rode: `python tests/app/teste_aplicacao_demo.py` → 0 falha.

- [x] **Step 7: E2E real.** Em `tests/app/teste_corretivos_tela.py`, no bloco aéreo: depois do primeiro insumo
  (`aplicar(..., [A, B])`), adicione um segundo insumo sem marcar talhões; confira no banco
  (`corretivo_aplicacao_talhoes` das duas aplicações) os talhões `{A, B}` em ambas; marque `A` e clique
  `[data-tirar]`, confira `{B}` em ambas. No PDF, troque `'0,15 L'` por `'Área de aplicação'` e acrescente
  `confere('INSUMO' not in texto, ...)`. O teste já apaga o mapa aéreo que criou. Rode com a conta de teste
  (veja a memória do projeto) → nenhuma falha.

- [x] **Step 8: Verificação geral.** `node --test tests/app/*.test.js`, `python -m pytest tests/mapas tests/drone/test_mapa_pdf_regressao.py -q`,
  demo e E2E → tudo verde. Conferir à vista um mapa aéreo e um de corretivo na tela e no PDF.

- [x] **Step 9: Commit** — `git commit -am "Tela aereo: talhoes do mapa valem para todos os insumos"`

---

### Task 6: Corretivo — operação de preparo "Experimento"

**Files:**
- Create: `supabase/migrations/20261028090000_operacao_experimento.sql`
- Modify: `mapas/corretivo_dados.py:11` (`OPERACOES`), `app/corretivos.js:5` (`CR_OPERACOES`), `:249` (`CR_OP_VAR`),
  `:561` (lista `ops` do "Novo mapa"), `app/corretivos.css:8` (variável de cor)
- Test: `tests/mapas/test_corretivo_pdf.py`, `tests/app/corretivos_puro.test.js`, `tests/aplicacao/test_mapas_aplicacao_sql.py`

**Interfaces:**
- Produces: operação `experimento` (rótulo `Experimento`), aceita pelo banco, pela tela e pelo PDF.

- [x] **Step 1: Testes que falham.**
  - `tests/mapas/test_corretivo_pdf.py`:

```python
def test_operacao_experimento_no_titulo(tmp_path):
    from tests.mapas.test_corretivo_layout import CASOS
    d = {**CASOS['1_linha'], 'operacao': 'experimento'}
    destino = tmp_path / 'exp.pdf'
    gerar_pdf(d, destino)
    assert 'CORRETIVO · EXPERIMENTO' in '\n'.join(p.get_text() for p in pymupdf.open(destino))
```

  - `tests/app/corretivos_puro.test.js`:

```js
test('operação Experimento', () => {
  assert.strictEqual(ctx.CR_OPERACOES.experimento, 'Experimento');
  assert.strictEqual(ctx.crNomeArquivo(10156, 'experimento', '2026-10-28'), 'corretivo_10156_experimento_2026-10-28.pdf');
});
```

  - `tests/aplicacao/test_mapas_aplicacao_sql.py`: num teste existente que cria mapa (`_mapa(como, uid, 'subsolagem')`),
    acrescente a criação de um mapa `'experimento'` e confira que gravou (só roda depois da migração aplicada; o teste
    apaga o que criou, como os demais desse arquivo).

- [x] **Step 2:** `python -m pytest tests/mapas/test_corretivo_pdf.py -q` e `node --test tests/app/*.test.js` → FAIL.

- [x] **Step 3: Implementação.**
  - `OPERACOES` (Python) e `CR_OPERACOES` (JS): acrescente `'experimento': 'Experimento'` / `experimento: 'Experimento'`
    antes de `aerea`.
  - `CR_OP_VAR`: `experimento: '--experimento'`; em `app/corretivos.css:8` acrescente `--experimento:#c2557a;`.
  - Lista `ops` do "Novo mapa": `[..., ['arado', 'Arado'], ['experimento', 'Experimento']]`. Confira à vista que os
    quatro botões cabem na largura do diálogo (se quebrar, ajuste a grade do fieldset no CSS).
  - Atualize a docstring de `mapas/corretivo_dados.py:3` para `subsolagem/supergrade/arado/experimento`.
  - Migração:

```sql
-- Corretivo: operação de preparo Experimento (28/10/2026).
alter table hub.corretivo_mapas drop constraint if exists corretivo_mapas_operacao_check;
alter table hub.corretivo_mapas add constraint corretivo_mapas_operacao_check
  check (operacao in ('subsolagem', 'supergrade', 'arado', 'experimento', 'aerea'));
```

- [ ] **Step 4:** testes do Step 2 → PASS (feito, inclusive SQL em Postgres local). Falta: pedir ao Leo para aplicar a migração; depois rodar
  `python -m pytest tests/aplicacao/test_mapas_aplicacao_sql.py -q` → PASS.

- [x] **Step 5: Commit** — `git add -A supabase/migrations mapas app tests && git commit -m "Corretivo: operacao de preparo Experimento"`

**Deploy:** a migração tem de estar aplicada antes de publicar a tela; sem ela, criar mapa de Experimento dá erro.

---

## Registro da execução (04/11/2026)

- Task 1: camada 2 (Haiku), aprovada.
- Task 2: camada 2 parou no card; camada 3 fechou. Desvio: nome do insumo em até 2 linhas e número até 8 pt (com 6,5–5 pt em 1 linha e mínimo de 11 pt, nomes de 25 letras e totais grandes seriam cortados em retrato).
- Task 3: camada 2, aprovada.
- Task 4: camada 2, aprovada.
- Task 5: camada 2 (código e demo); camada 3 no E2E e nos ajustes. Desvio: quadrado dos cards do aéreo também na cor única; `crAlvoAplicar` e `crRotuloAplicar` novos.
- Task 6: camada 2; camada 3 incluiu a migração no conftest. Desvio: migração em `20261104090000_operacao_experimento.sql` (já havia migrações de 29/10); `.cr-seg-4` para os 4 botões.
- Camada 1 não usada: o isolamento da sessão recusa o `HOME` exigido pelo `delegar.sh`.
