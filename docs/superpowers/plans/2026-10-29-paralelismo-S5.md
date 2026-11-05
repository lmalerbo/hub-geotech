# Paralelismo S5 (P5a: Painel — Resumo e Talhões) Implementation Plan

> **For agentic workers:** executar com superpowers:executing-plans, tarefa a tarefa. Passos com `- [ ]`.

**Goal:** a aba Painel passa a mostrar Resumo (KPIs, aderência por declividade e por mês, tabela de fazendas) e Talhões (dispersão aderência × declividade, tabela com busca, mapa MapLibre pintado pela aderência), lendo só análises vigentes de rodadas publicadas.

**Architecture:** agregações em funções puras de `app/paralelismo-puro.js` (testadas com `node --test`); leitura em `parApi().painel()` (real: tabelas com RLS existente; demonstração: dados fictícios); telas em `app/paralelismo-painel.js` (novo), desenhadas na coluna de 380 px e no palco. Gráficos em SVG puro, uma cor sequencial (verde da marca) e as quatro cores de situação já do módulo; o mapa do Painel é MapLibre 4.7.1 (o canvas continua em Processar).

**Tech Stack:** JS puro sem build, MapLibre GL 4.7.1 (jsdelivr), supabase-js, `node --test`, Playwright + Edge.

**Spec:** `docs/superpowers/specs/2026-10-26-paralelismo-design.md` §7. Plano-mãe: `2026-10-29-paralelismo.md` (P5).

## Global Constraints

- Situação (BI atual): aderência ≥ 85% Bom, ≥ 70% Atenção, abaixo Crítico; talhão com < 25 amostras = "Amostra insuficiente" (fora de médias, dispersão e cores).
- Faixas de declividade do BI: até 6%, 6 a 9%, 9 a 12%, acima de 12%; declividade nula = fora das faixas.
- Aderência de fazenda/total conta só amostras dentro de talhão (`amostras`), nunca `fora_talhao`.
- Português do Brasil, vírgula decimal, só tema claro, funciona a 390 px, prefixo `par`, estado em `PAR`. Dado do banco sempre por `parEsc`.
- Nada de rede real nos testes; nada gravado no banco; sem migration nova (leitura usa as RLS existentes: `paralelismo_analises/talhoes` por `pode_ver`, `hub.talhoes`, `hub.fazendas`, `hub.talhao_geom` com leitura autenticada).

## Review Focus

1. Painel sem nenhuma rodada publicada → estado vazio, sem divisão por zero (teste de `parResumo` e de tela).
2. Talhão sem declividade/área no `hub.talhoes` → aparece na tabela, fica fora das faixas e da dispersão.
3. Nome de fazenda/talhão com HTML → escapado (tela).
4. Todos os talhões com amostra insuficiente → média "—", não 0%.
5. Nível leitura vê o Painel (é a aba de abertura dele).

## Tarefa 1: funções de agregação (`app/paralelismo-puro.js`, teste `tests/app/paralelismo_painel.test.js`)

**Interfaces — Produz** (entrada comum `analises`: `[{operacao, cod_faz, fazenda, mes:'2026-10-01', amostras, aderentes, acima, abaixo, fora_talhao, paralelismo_talhoes:[{talhao_num, amostras, aderentes, acima, abaixo, media_m, frotas}]}]`; `base`: `{ 'cod|num': {area_ha, declividade} }`):
- `parSituacao(pct: number|null) -> 'bom'|'atencao'|'critico'|null` (pct 0–100)
- `parFaixaDeclividade(d: number|null) -> 0..3|null`; `PAR_FAIXAS = ['até 6%','6 a 9%','9 a 12%','acima de 12%']`
- `parTalhoesPlanos(analises, base) -> [{operacao,cod_faz,fazenda,talhao,mes,area,dec,amostras,aderentes,acima,abaixo,pct,insuficiente}]` (pct = 0–100 ou null se amostras=0; `insuficiente` = amostras < 25)
- `parResumo(analises, base) -> {amostras, aderentes, pct, fazendas, talhoes, talhoesValidos, area, situacao}` (soma de `amostras`/`aderentes` das análises)
- `parPorFaixa(planos) -> [{rotulo, n, amostras, aderentes, pct}]` (só talhões não insuficientes e com declividade; faixas vazias mantidas com n=0, pct null)
- `parPorMes(analises) -> [{mes, amostras, aderentes, pct}]` ordenado por mês
- `parTabelaFazendas(analises, base) -> [{operacao,cod_faz,fazenda,mes,talhoes,area,decMedia,pct,situacao}]` (decMedia ponderada pela área; ordem por pct crescente, nulos no fim)
- `parFiltrarTalhoes(planos, busca) -> planos` (busca sem acento/caixa em fazenda, código e número do talhão)

- [ ] Escrever os testes (sintéticos) com os casos: situação nas bordas 70 e 85; faixas nas bordas 6, 9, 12 e nulo; fora_talhao não entra no pct; talhão com 24 amostras é insuficiente e fica fora de `parPorFaixa`; lista vazia → `pct null`, sem NaN; decMedia ponderada pela área; busca "são" acha "Santa São"; mês ordenado.
- [ ] Rodar `node --test tests/app/paralelismo_painel.test.js` → FALHA (funções inexistentes).
- [ ] Implementar no `paralelismo-puro.js` (usar `parFormatarPct` só na tela).
- [ ] Rodar → PASSA. Commit.

## Tarefa 2: leitura (`parApi().painel()`) real e demonstração

**Produz:** `parApi().painel() -> Promise<{analises, base}>`; `parApi().geoFazenda(cod) -> Promise<FeatureCollection>` (properties `talhao`, `area_ha`, `declividade`).

- [ ] Real: `paralelismo_analises` com `vigente=true`, `select('operacao,cod_faz,mes,amostras,aderentes,acima,abaixo,fora_talhao,paralelismo_talhoes(*)')`; `hub.fazendas` (nome) e `hub.talhoes` (`cod_faz,talhao_num,area_ha,declividade`) das fazendas encontradas; `geoFazenda` lê `hub.talhao_geom` (`geom` vem como GeoJSON).
- [ ] Demonstração: 4 fazendas (uma com nome `<b>x</b>`, uma só com talhões insuficientes) a partir de `parAnaliseDemo`/`parTalhoesDemo`; `window.PAR_DEMO_PAINEL_VAZIO` para o estado vazio.
- [ ] Commit.

## Tarefa 3: telas Resumo e Talhões (`app/paralelismo-painel.js`, `paralelismo.css`, `paralelismo.html`)

- [ ] Sub-abas Resumo | Talhões como botões `aria-pressed` na coluna (`PAR.painel = {sub, dados, busca, sel}`); `parHtmlOutraAba` delega a `parHtmlPainel()`; aba de abertura passa a Painel.
- [ ] Resumo: 4 KPIs, barras por faixa de declividade (cor sequencial única; rótulo com % e n), colunas por mês, tabela de fazendas com selo de situação (ícone + texto, nunca só cor). SVG com `<title>`/tabela acessível; tooltip nativo por mark.
- [ ] Talhões: dispersão (x declividade, y aderência, pontos ≥ 8 px com anel de 2 px), campo de busca, tabela (talhão, declividade, área, amostras, aderência, situação) com "Amostra insuficiente"; clicar numa linha escolhe fazenda e destaca no mapa.
- [ ] Mapa MapLibre (`#par-maplibre` no palco, só em Painel › Talhões; canvas escondido): fonte GeoJSON da fazenda escolhida, preenchimento pela aderência (`--r1..r4`, cinza para insuficiente), contorno branco, popup/dica ao passar; legenda reaproveitada. Se `maplibregl` não carregar, mensagem no lugar do mapa.
- [ ] Estado vazio ("Nenhuma rodada publicada ainda").
- [ ] Commit.

## Tarefa 4: teste de tela e verificação

- [ ] `tests/app/teste_paralelismo_painel_tela.py` (Edge, demonstração, 127.0.0.1): níveis leitura/editor veem Painel; KPIs e tabela; busca filtra; HTML do nome escapado; vazio; sem rolagem horizontal a 390 px; sem `pageerror`; mapa com camadas quando o MapLibre carrega (se a CDN estiver inacessível, registrar como não verificado).
- [ ] Ajustar `teste_paralelismo_tela.py` se o aviso "próxima etapa" do Painel era conferido.
- [ ] `node --test`, os testes de tela, `pytest -q`; `requesting-code-review`; relatório `orquestra/relatorios/S5.md`.
