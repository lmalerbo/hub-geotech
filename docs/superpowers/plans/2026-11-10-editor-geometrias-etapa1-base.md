# Editor de geometrias — Etapa 1 (Base) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Laboratório local `editor/lab.html` em que se importa KML/SHP/GeoJSON, desenha ponto, linha e polígono, edita camadas e atributos, desfaz/refaz e exporta, sobre um núcleo de documento + comandos + registro de ferramentas testado no Node.

**Architecture:** O núcleo (`editor/nucleo/`, sem DOM) guarda o documento em UTM 23S e só muda por comandos registrados, que devolvem o próprio inverso. As ferramentas (`editor/ferramentas/`) são plug-ins que recebem um `ctx` e só alteram o documento por `ctx.executar`. O Terra Draw (`editor/interacao/`) só captura o gesto. O mapa é redesenhado a partir do documento a cada mudança.

**Tech Stack:** JS (módulos ES) sem build no dia a dia; bibliotecas empacotadas uma vez com esbuild em `editor/vendor/`; MapLibre GL 4.7.1, Terra Draw 1.37.0 + adaptador MapLibre 1.5.0, proj4 2.22.0, shpjs 6.2.0, @mapbox/shp-write 0.4.3, @tmcw/togeojson 7.1.3, tokml 0.4.0, @xmldom/xmldom (só testes); testes com `node --test` (Node 22).

**Spec:** `docs/superpowers/specs/2026-11-09-editor-geometrias-nucleo-design.md` (esta é a Etapa 1 da seção 11).

## Global Constraints

- Sistema de trabalho: **EPSG:31983** (SIRGAS 2000 / UTM 23S), proj4 `+proj=utm +zone=23 +south +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs`. Exibição e GeoJSON em EPSG:4326.
- O documento guarda geometria em UTM. Coordenadas arredondadas a **0,001 m** ao entrar no documento.
- Ângulos (quando aparecerem) em **azimute**: 0° = Norte, sentido horário.
- O documento só muda por `historico.executar(comando)`. Todo comando é serializável em JSON e determinístico (os ids vêm de contadores do documento, nunca de `Math.random`/`Date`).
- Ferramenta só usa o `ctx`. Nenhum arquivo em `editor/ferramentas/` importa de `editor/interacao/` nem acessa o DOM.
- Texto vindo de arquivo importado (nomes, atributos) entra na página **só por `textContent`/`value`**, nunca por `innerHTML`.
- `editor/` fica fora de `app/` e não é publicado. Nenhum dado real entra no repositório (fixtures de teste são sintéticas).
- `editor/package.json` e `tests/editor/package.json` têm `{"type":"module"}`; os testes ficam em `tests/editor/*.test.js` (o CI já roda `node --test $(find tests -name "*.test.js")`).
- Exportação: SHP em 4326 ou 31983 com `.prj`; KML com **9** casas decimais (8 casas dão até 1,1 mm e quebram a garantia de 1 mm da ida e volta; ajuste em relação à spec, que fala em 8); GeoJSON em 4326.
- Interface e mensagens em português do Brasil.

## Review Focus

- **Arquivo com nomes e atributos maliciosos** (KML com `<img src=x onerror=alert(1)>` no nome): deve aparecer como texto literal no painel, sem executar. Coberto na Tarefa 10 (passo de aceite) e na Tarefa 6 (o importador preserva o texto bruto).
- **Shapefile sem `.prj` com coordenadas métricas:** deve entrar como 31983 com aviso, e não ser lido como graus nem recusado. Coberto na Tarefa 7.
- **Desfazer depois de importar ou de criar**, e depois refazer: o documento volta idêntico, inclusive os contadores, e o refazer recria com os **mesmos ids**. Coberto nas Tarefas 2 e 3.
- **Desenhar ou importar numa camada travada:** recusa com mensagem e o documento não muda. Coberto nas Tarefas 3 e 8.
- **Salvamento automático corrompido ou bloqueado** (JSON inválido, `localStorage` lançando erro): o laboratório abre vazio, sem quebrar. Coberto na Tarefa 9.

---

## Estrutura de arquivos

```text
editor/
  package.json                 {"type":"module","private":true}
  vendor-src/                  montagem das bibliotecas (node_modules ignorado no git)
    package.json               versões fixas
    entradas/{proj4,arquivos,mapa,xmldom}.js
    montar.mjs                 esbuild → ../vendor/
  vendor/                      saída versionada: proj4.js, arquivos.js, mapa.js, mapa.css, xmldom.js
  nucleo/
    registro.js                registro de ferramentas, comandos, snaps e formatos
    historico.js               executar / desfazer / refazer + comando 'composto'
    documento.js               criar documento, leituras, conferência de geometria, arredondamento
    comandos-base.js           comandos de camada e feição
    projecao.js                31983 <-> 4326
    arquivos.js                importar/exportar via formatos registrados + CRS + avisos
    formatos/{geojson,kml,shp}.js
  interacao/
    contexto.js                monta o ctx entregue às ferramentas
    ponte-terradraw.js         Terra Draw → aoGesto da ferramenta ativa
    mapa-documento.js          documento → fonte GeoJSON do mapa
  ferramentas/
    index.js                   registrarFerramentasBase(registro)
    desenhar.js                ponto, linha, polígono
    historico.js               desfazer, refazer
    arquivos.js                importar, exportar
  lab/
    salvamento.js              salvar/restaurar no armazenamento do navegador
    fundos.js                  lista de fundos do mapa
    paineis.js                 camadas, atributos, avisos (DOM)
  lab.html, lab.js, lab.css
  ACEITE.md
tests/editor/
  package.json                 {"type":"module"}
  fixtures/                    arquivos sintéticos gerados pelos próprios testes quando possível
  *.test.js
```

---

### Task 1: Andaime e bibliotecas fixadas

**Files:**
- Create: `editor/package.json`, `tests/editor/package.json`
- Create: `editor/vendor-src/package.json`, `editor/vendor-src/entradas/proj4.js`, `editor/vendor-src/entradas/arquivos.js`, `editor/vendor-src/entradas/mapa.js`, `editor/vendor-src/entradas/xmldom.js`, `editor/vendor-src/montar.mjs`
- Create (gerados): `editor/vendor/proj4.js`, `editor/vendor/arquivos.js`, `editor/vendor/mapa.js`, `editor/vendor/mapa.css`, `editor/vendor/xmldom.js`
- Modify: `.gitignore` (acrescentar `editor/vendor-src/node_modules/`)
- Test: `tests/editor/vendor.test.js`

**Interfaces:**
- Produces:
  - `editor/vendor/proj4.js`: `export default proj4`
  - `editor/vendor/arquivos.js`: `export { lerShp /* shpjs default: (ArrayBuffer) => Promise<FeatureCollection | FeatureCollection[]> */, shpwrite /* @mapbox/shp-write */, kmlParaGeojson /* @tmcw/togeojson kml(Document) */, geojsonParaKml /* tokml */ }`
  - `editor/vendor/mapa.js` (só navegador): `export { maplibregl, TerraDraw, TerraDrawPointMode, TerraDrawLineStringMode, TerraDrawPolygonMode, TerraDrawSelectMode, TerraDrawMapLibreGLAdapter }`; `mapa.css` = CSS do maplibre-gl 4.7.1
  - `editor/vendor/xmldom.js` (só testes): `export { DOMParser }`

- [ ] **Step 1: Escrever `editor/vendor-src/package.json` com versões exatas** (sem `^`): `maplibre-gl 4.7.1`, `terra-draw 1.37.0`, `terra-draw-maplibre-gl-adapter 1.5.0`, `proj4 2.22.0`, `shpjs 6.2.0`, `@mapbox/shp-write 0.4.3`, `@tmcw/togeojson 7.1.3`, `tokml 0.4.0`, `@xmldom/xmldom 0.9.8`, `esbuild 0.28.2` (devDependency). Antes, conferir com `npm view <pacote>@<versão> version` que cada versão existe; se a do xmldom não existir, usar a mais nova com mais de 2 semanas e anotar no commit.

- [ ] **Step 2: Escrever as entradas e `montar.mjs`.** Cada arquivo em `entradas/` só reexporta com os nomes do bloco Interfaces. `montar.mjs` chama `esbuild.build({ entryPoints, bundle: true, format: 'esm', platform: 'browser', outdir: '../vendor', minify: false, legalComments: 'inline' })` e copia `node_modules/maplibre-gl/dist/maplibre-gl.css` para `../vendor/mapa.css`. Documentar no topo de `montar.mjs`: `cd editor/vendor-src && npm ci && node montar.mjs`.

- [ ] **Step 3: Escrever o teste que falha** em `tests/editor/vendor.test.js`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
test('proj4 do vendor converte o meridiano central do fuso 23S', async () => {
  const { default: proj4 } = await import('../../editor/vendor/proj4.js');
  const [x] = proj4('EPSG:4326', '+proj=utm +zone=23 +south +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs', [-45, -15]);
  assert.ok(Math.abs(x - 500000) < 1e-6);
});
test('bibliotecas de arquivo carregam no Node', async () => {
  const m = await import('../../editor/vendor/arquivos.js');
  for (const nome of ['lerShp', 'shpwrite', 'kmlParaGeojson', 'geojsonParaKml']) assert.ok(m[nome], nome);
  const { DOMParser } = await import('../../editor/vendor/xmldom.js');
  assert.equal(typeof DOMParser, 'function');
});
```

- [ ] **Step 4: Rodar e ver falhar.** Run: `node --test tests/editor/vendor.test.js`. Expected: FAIL (módulo não encontrado).

- [ ] **Step 5: Montar.** Run: `cd editor/vendor-src && npm ci && node montar.mjs` (na primeira vez, `npm install` para gerar o `package-lock.json`, que é versionado). Se `arquivos.js` não carregar no Node por depender de `Blob`/`window`, manter `platform: 'browser'` e acrescentar só o polyfill que faltar dentro da entrada (anotar o motivo num comentário).

- [ ] **Step 6: Rodar e ver passar.** Run: `node --test tests/editor/vendor.test.js`. Expected: 2 testes PASS.

- [ ] **Step 7: Commit**

```bash
git add .gitignore editor/package.json tests/editor/package.json editor/vendor-src/package.json editor/vendor-src/package-lock.json editor/vendor-src/entradas editor/vendor-src/montar.mjs editor/vendor tests/editor/vendor.test.js
git commit -m "feat(editor): andaime do laboratório e bibliotecas fixadas em vendor"
```

---

### Task 2: Registro e histórico de comandos (com prova do contrato)

**Files:**
- Create: `editor/nucleo/registro.js`, `editor/nucleo/historico.js`
- Test: `tests/editor/registro.test.js`, `tests/editor/historico.test.js`

**Interfaces:**
- Produces:
  - `criarRegistro() -> Registro` com `registrarFerramenta(def)`, `registrarComando(def)`, `registrarSnap(def)`, `registrarFormato(def)`, `ferramenta(id)`, `ferramentas() -> def[]` (ordem de registro), `comando(tipo)`, `formato(id)`, `formatoPorExtensao(ext)` (sem ponto, minúsculas), `snaps() -> def[]` ordenados por `prioridade` crescente.
  - Def de ferramenta: `{ id, nome, grupo, tipo: 'modo'|'acao', icone?, atalho?, exige?, opcoes?, ativar(ctx), desativar?(ctx), aoPonteiro?(ctx, ev), aoTeclado?(ctx, tecla), aoEntrada?(ctx, texto), aoGesto?(ctx, gesto) }`. `tipo: 'acao'` = roda `ativar` e não fica ativa (desfazer, importar). `grupo ∈ {criar, transformar, forma, precisao, trabalho, arquivo, cad}`.
  - Def de comando: `{ tipo, aplicar(doc, dados) -> { inverso: {tipo, dados}, alteradas?: string[] } }`. `aplicar` confere tudo **antes** de mudar `doc`; se lançar, `doc` não mudou.
  - Def de formato: `{ id, nome, extensoes: string[], importar?, exportar? }`. Def de snap: `{ id, prioridade: number, simbolo, candidatos }`.
  - `criarHistorico(doc, registro) -> Historico` com `executar(comando) -> resultado` (resultado = `{ alteradas }`), `desfazer() -> boolean`, `refazer() -> boolean`, `podeDesfazer()`, `podeRefazer()`, `aoMudar(fn) -> () => void`, getter `doc`. Comando composto embutido: `{ tipo: 'composto', dados: { comandos: [...] } }`.

- [ ] **Step 1: Testes do registro que falham** (`registro.test.js`):
  - `registrar ferramenta duplicada lança 'ferramenta já registrada: <id>'`; o mesmo para comando (`'comando já registrado: <tipo>'`) e formato.
  - `ferramenta sem id, nome, grupo válido ou ativar lança erro que cita o campo` (ex.: `/grupo/`).
  - `formatoPorExtensao('KML')` e `('kml')` acham o formato com `extensoes: ['kml']`.
  - `snaps()` volta ordenado por prioridade: registrados `{prioridade: 5}`, `{prioridade: 1}` → ids na ordem `[p1, p5]`.

- [ ] **Step 2: Testes do histórico que falham** (`historico.test.js`). Usam um comando de teste `'contador.somar'` registrado no próprio teste (`doc.valor += dados.n`, inverso `{ tipo: 'contador.somar', dados: { n: -dados.n } }`) e um documento `{ valor: 0, contadores: { id: 1 } }`:
  - executar `n:5` → `doc.valor === 5`; desfazer → `0`; refazer → `5`; `podeRefazer()` falso depois de um executar novo.
  - **contadores:** um comando `'id.novo'` incrementa `doc.contadores.id`; executar, desfazer → `doc.contadores` igual ao de antes (`deepEqual`); refazer → igual ao de depois.
  - `executar` clona `dados` (`structuredClone`): mudar o objeto passado depois não altera o que o refazer aplica.
  - comando que lança → erro repassado, pilha intacta, `aoMudar` não chamado.
  - composto `[somar 2, somar 3]` → 5; desfazer → 0 numa única entrada da pilha; composto `[somar 2, falha]` → lança e `doc.valor` volta a 0.
  - `aoMudar` é chamado uma vez por executar, desfazer e refazer, e o retorno desinscreve.
  - **Prova do contrato:** um teste registra uma ferramenta `'teste-somar'` (tipo `acao`, `ativar(ctx) { ctx.executar({ tipo: 'contador.somar', dados: { n: 7 } }) }`) e chama `registro.ferramenta('teste-somar').ativar({ executar: c => h.executar(c) })` → `doc.valor === 7`; `h.desfazer()` → `0`. Nenhum arquivo do núcleo é alterado para isso.

- [ ] **Step 3: Rodar e ver falhar.** Run: `node --test tests/editor/registro.test.js tests/editor/historico.test.js`. Expected: FAIL (módulos ausentes).

- [ ] **Step 4: Implementar `registro.js` e `historico.js`.** Pilha de desfazer guarda `{ inverso, contadoresAntes, contadoresDepois }`. `desfazer` aplica `inverso`, repõe `doc.contadores = contadoresAntes` e empilha no refazer o inverso que `aplicar` devolveu, com os contadores trocados. Composto: aplica em ordem e guarda os inversos; se um falhar, aplica os inversos já obtidos em ordem reversa e relança; o inverso do composto é um composto dos inversos em ordem reversa. Os contadores são `structuredClone` de `doc.contadores` quando existir.

- [ ] **Step 5: Rodar e ver passar.** Mesmo comando. Expected: todos PASS.

- [ ] **Step 6: Commit**

```bash
git add editor/nucleo/registro.js editor/nucleo/historico.js tests/editor/registro.test.js tests/editor/historico.test.js
git commit -m "feat(editor): registro de extensões e histórico de comandos reversíveis"
```

---

### Task 3: Documento e comandos de camada e feição

**Files:**
- Create: `editor/nucleo/documento.js`, `editor/nucleo/comandos-base.js`
- Test: `tests/editor/documento.test.js`

**Interfaces:**
- Consumes: `criarRegistro`, `criarHistorico` (Task 2).
- Produces:
  - `criarDocumento() -> Documento` = `{ versao: 1, crs: 'EPSG:31983', camadas: [], feicoes: {}, contadores: { camada: 1, feicao: 1, ordem: 1, numero: 1 } }`. `feicoes` é objeto `id -> feicao` (serializável em JSON).
  - Camada: `{ id: 'c<n>', nome, visivel: true, travada: false, participaEspacamento: false, estilo: { cor } }`. A cor padrão vem de uma paleta fixa de 8 cores, por `(n-1) % 8`.
  - Feição: `{ id: 'f<n>', camadaId, geometria /* GeoJSON Geometry em UTM */, atributos: { nome: string|null, categoria: string|null, numero: number, ...livres }, ordem: number }`.
  - Leituras: `camada(doc, id)`, `feicao(doc, id)`, `feicoesDaCamada(doc, camadaId) -> feicao[]` (por `ordem`), `camadaPorNome(doc, nome)`.
  - `conferirGeometria(g)` lança `Error('geometria inválida: <motivo>')` para tipo fora de `Point|LineString|Polygon|MultiPoint|MultiLineString|MultiPolygon`, coordenada não finita, linha com menos de 2 pontos, anel com menos de 4 pontos ou não fechado.
  - `arredondarGeometria(g, passo = 0.001) -> g` (cópia).
  - `registrarComandosBase(registro)` registra: `camada.criar {nome, estilo?}`, `camada.alterar {id, mudancas}`, `camada.remover {id}`, `camada.restaurar {camada, indice, feicoes}`, `camada.importar {nome, feicoes: [{geometria, atributos}]}`, `feicao.criar {camadaId, geometria, atributos?}`, `feicao.remover {ids}`, `feicao.restaurar {feicoes}`, `feicao.atributos {id, mudancas}`. Todos devolvem `alteradas` com os ids de feição afetados.

- [ ] **Step 1: Testes que falham** (`documento.test.js`), sempre via `criarHistorico(criarDocumento(), registro)`:
  - `camada.criar` → `doc.camadas[0]` com `id 'c1'`, `visivel true`, `travada false`; desfazer → `camadas` vazio e `contadores.camada === 1`.
  - `feicao.criar` com polígono `[[500000,8000000],[500010.00049,8000000],[500010,8000005],[500000,8000005],[500000,8000000]]` → id `'f1'`, `atributos.numero === 1`, `ordem === 1`, coordenada `500010.00049` guardada como `500010` (arredondada a 1 mm); com `atributos.numero: 40` mantém 40 e não consome o contador.
  - **Ida e volta idêntica:** para cada comando base, `const antes = structuredClone(doc)`, executar, desfazer → `assert.deepEqual(doc, antes)`; refazer → igual ao estado depois do primeiro executar (mesmos ids).
  - `camada.importar` com 3 feições → 1 camada + 3 feições numeradas 1, 2, 3 numa única entrada de desfazer.
  - Camada travada: `feicao.criar`, `feicao.remover`, `feicao.atributos` e `camada.importar` não se aplicam; `feicao.criar` numa camada travada lança `/camada travada/` e `doc` fica igual (`deepEqual`). `camada.alterar {travada: false}` continua permitido.
  - `feicao.atributos {mudancas: {nome: 'P1', obs: null}}` → `nome 'P1'` e o campo `obs` removido; desfazer restaura o valor e a presença anteriores do campo.
  - `feicao.atributos` com `numero` que não é inteiro positivo lança `/número/`.
  - `camada.remover` de camada com feições → feições somem; desfazer devolve a camada **na mesma posição** e as feições iguais.
  - `conferirGeometria` recusa: anel aberto, `NaN`, `{type: 'GeometryCollection'}`.

- [ ] **Step 2: Rodar e ver falhar.** Run: `node --test tests/editor/documento.test.js`. Expected: FAIL.

- [ ] **Step 3: Implementar `documento.js` e `comandos-base.js`.** `feicao.criar` confere a geometria, arredonda, lê os contadores e os incrementa. O inverso de criar é `feicao.remover {ids}`; o inverso de remover é `feicao.restaurar {feicoes}` com as feições completas. Os contadores são repostos pelo histórico, não pelos comandos.

- [ ] **Step 4: Rodar e ver passar.** Run: `node --test tests/editor/`. Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add editor/nucleo/documento.js editor/nucleo/comandos-base.js tests/editor/documento.test.js
git commit -m "feat(editor): documento em UTM e comandos de camada e feição"
```

---

### Task 4: Projeção 31983 ⇄ 4326

**Files:**
- Create: `editor/nucleo/projecao.js`
- Test: `tests/editor/projecao.test.js`

**Interfaces:**
- Consumes: `editor/vendor/proj4.js`.
- Produces: `UTM23S = 'EPSG:31983'`, `WGS84 = 'EPSG:4326'`, `converterPonto([x, y], de, para) -> [x, y]` (descarta Z/M), `converterGeometria(g, de, para) -> g` (cópia), `paraUTM(g)`, `paraWGS(g)`, `feicaoParaExibir(feicao) -> Feature` (geometria em 4326, `properties = { id, camadaId, ...atributos }`), `WKT_PRJ = { 'EPSG:4326': string, 'EPSG:31983': string }` (WKT ESRI para o `.prj`).

- [ ] **Step 1: Testes que falham.** Valores de referência calculados com pyproj, independente do proj4, com tolerância de 0,001 m:
  - `[-45, -15]` → `[500000.0000, 8341674.0065]`
  - `[-47.5, -15.8]` → `[232183.7458, 8251595.6827]`
  - `[-46.123456, -20.5]` → `[382850.4409, 7732784.8576]`
  - ida e volta `paraWGS(paraUTM(p))` difere menos de `1e-9` grau nos três pontos;
  - `converterGeometria` de um Polygon com furo mantém a estrutura (2 anéis, mesmas contagens);
  - `converterPonto([-45, -15, 812, 3], ...)` devolve 2 números;
  - `WKT_PRJ['EPSG:31983']` contém `'SIRGAS_2000_UTM_Zone_23S'`.

- [ ] **Step 2: Rodar e ver falhar.** Run: `node --test tests/editor/projecao.test.js`. Expected: FAIL.

- [ ] **Step 3: Implementar.** `proj4.defs('EPSG:31983', '<string das Global Constraints>')`.

- [ ] **Step 4: Rodar e ver passar.** Mesmo comando. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editor/nucleo/projecao.js tests/editor/projecao.test.js
git commit -m "feat(editor): projeção SIRGAS 2000 UTM 23S <-> WGS84"
```

---

### Task 5: Importar e exportar (núcleo) + formato GeoJSON

**Files:**
- Create: `editor/nucleo/arquivos.js`, `editor/nucleo/formatos/geojson.js`
- Test: `tests/editor/arquivos-geojson.test.js`

**Interfaces:**
- Consumes: `projecao.js` (Task 4), `conferirGeometria`, `feicoesDaCamada` (Task 3), `Registro.formato*` (Task 2).
- Produces:
  - Contrato de formato: `importar(conteudo: ArrayBuffer|string, nomeArquivo) -> Promise<{ colecoes: [{ nome, featureCollection, crs: 'EPSG:4326'|'EPSG:31983'|null }], avisos: string[] }>` e `exportar(colecoes: [{ nome, featureCollection }], { crs }) -> Promise<{ conteudo, mime, extensao, avisos: string[] }>`. O formato recebe e devolve coordenadas no `crs` pedido; quem projeta é `arquivos.js`.
  - `formatoGeojson` (id `'geojson'`, extensões `['geojson', 'json']`).
  - `detectarCrs(featureCollection) -> 'EPSG:4326'|'EPSG:31983'|null`: todas as coordenadas com |x| ≤ 180 e |y| ≤ 90 → 4326; x em [100000, 900000] e y em [6000000, 10000000] → 31983; senão `null`.
  - `importarArquivo(registro, { nome, conteudo }) -> Promise<{ camadas: [{ nome, feicoes: [{ geometria /* UTM */, atributos }] }], avisos }>`. Escolhe o formato pela extensão (sem formato → `Error('formato não suportado: .<ext>')`). Usa o `crs` da coleção; se for `null`, chama `detectarCrs` e avisa `'<arquivo>: sem sistema de coordenadas; assumido <crs>'`; se continuar `null` → `Error('<arquivo>: sistema de coordenadas não reconhecido')`. Remove Z/M (aviso único `'coordenadas Z/M descartadas'`), separa `GeometryCollection` em feições, pula geometria nula ou inválida (aviso com a quantidade). Atributos: copia `properties`; se `nome` faltar e houver `name`/`Name`, usa como `nome`; `numero` só é aproveitado se for inteiro positivo.
  - `exportarCamadas(registro, formatoId, doc, { camadaIds = todas, crs = 'EPSG:4326' }) -> Promise<{ nome, conteudo, mime, avisos }>`. O nome do arquivo é `<nome da camada ou 'editor'>.<extensao>`. Propriedades exportadas = `atributos`, mais `id_editor` com o id da feição.
- O formato GeoJSON importa com `crs` vindo do membro legado `crs.properties.name`, se houver (`EPSG:31983` ou `urn:ogc:def:crs:EPSG::31983`); senão `null`. Ignora a menção a 4326 do RFC: sem membro `crs`, deixa para a detecção, e graus não geram aviso (graus = RFC). Exporta sempre em 4326, com aviso se pedirem 31983.

- [ ] **Step 1: Testes que falham:**
  - FeatureCollection em graus (polígono com furo, linha, ponto com Z) → 1 camada, 3 feições, geometrias em UTM (o primeiro vértice confere com o valor de pyproj da Task 4), aviso de Z/M e nenhum aviso de CRS.
  - FeatureCollection em metros sem `crs` → aviso `/assumido EPSG:31983/`.
  - Coordenadas `[5000, 5000]` → lança `/não reconhecido/`.
  - Feature com `properties: { name: 'Talhão 1' }` → `atributos.nome === 'Talhão 1'`; `properties: { nome: '<img src=x onerror=alert(1)>' }` → `nome` exatamente essa string.
  - Extensão `.dwg` → lança `/formato não suportado/`.
  - **Ida e volta:** documento com as 3 feições → `exportarCamadas(..., 'geojson')` → `importarArquivo` → toda coordenada a menos de 0,001 m da original, atributos iguais (exceto `id_editor`).

- [ ] **Step 2: Rodar e ver falhar.** Run: `node --test tests/editor/arquivos-geojson.test.js`. Expected: FAIL.

- [ ] **Step 3: Implementar `arquivos.js` e `formatos/geojson.js`.**

- [ ] **Step 4: Rodar e ver passar.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editor/nucleo/arquivos.js editor/nucleo/formatos/geojson.js tests/editor/arquivos-geojson.test.js
git commit -m "feat(editor): importação/exportação por formatos registrados e GeoJSON"
```

---

### Task 6: Formato KML

**Files:**
- Create: `editor/nucleo/formatos/kml.js`
- Test: `tests/editor/arquivos-kml.test.js`

**Interfaces:**
- Consumes: contrato de formato (Task 5), `kmlParaGeojson`, `geojsonParaKml` (Task 1).
- Produces: `criarFormatoKml({ DOMParser }) -> formato` (id `'kml'`, extensões `['kml']`). No navegador recebe `window.DOMParser`; nos testes, o `DOMParser` de `editor/vendor/xmldom.js`. Importa com `crs: 'EPSG:4326'`. Exporta em 4326 (aviso se pedirem 31983), com coordenadas arredondadas a **9 casas** antes do `tokml`, `name` = `atributos.nome`.

- [ ] **Step 1: Testes que falham:**
  - KML sintético com um Placemark `<name>&lt;img src=x onerror=alert(1)&gt;</name>` e um Polygon → `atributos.nome === '<img src=x onerror=alert(1)>'` (texto bruto).
  - **Ida e volta** com o mesmo documento de 3 feições da Task 5 → toda coordenada a menos de 0,001 m, polígono com furo preservado (2 anéis).
  - O texto exportado tem, na primeira coordenada, exatamente 9 casas decimais.

- [ ] **Step 2: Rodar e ver falhar.** Run: `node --test tests/editor/arquivos-kml.test.js`. Expected: FAIL.

- [ ] **Step 3: Implementar.**

- [ ] **Step 4: Rodar e ver passar.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editor/nucleo/formatos/kml.js tests/editor/arquivos-kml.test.js
git commit -m "feat(editor): formato KML"
```

---

### Task 7: Formato SHP

**Files:**
- Create: `editor/nucleo/formatos/shp.js`
- Test: `tests/editor/arquivos-shp.test.js`

**Interfaces:**
- Consumes: contrato de formato (Task 5), `lerShp`, `shpwrite` (Task 1), `WKT_PRJ` (Task 4).
- Produces: `formatoShp` (id `'shp'`, extensões `['zip']`).
  - Importar: `lerShp(arrayBuffer)`; um item por shapefile de dentro do zip, com `nome` do arquivo. `crs`: se o zip tem `.prj` (procurar `/\.prj$/i` nos nomes do diretório central do zip, lidos dos bytes), o shpjs já reprojetou → `'EPSG:4326'`; sem `.prj` → `null` (a detecção e o aviso ficam com a Task 5).
  - Exportar: separa as feições por tipo (Point/MultiPoint, LineString/MultiLineString, Polygon/MultiPolygon) em `<nome>_pontos`, `<nome>_linhas` e `<nome>_poligonos` (só os não vazios), `.prj` = `WKT_PRJ[crs]`, coordenadas 31983 arredondadas a 3 casas, saída `ArrayBuffer`. Aviso `'campos com mais de 10 caracteres serão cortados: <lista>'` quando houver.

- [ ] **Step 1: Testes que falham:**
  - **Ida e volta em 4326 e em 31983**, com o documento de 3 feições → coordenadas a menos de 0,001 m, furo preservado.
  - Zip exportado em 31983 e depois **com o `.prj` removido** (regravar o zip sem ele, usando o JSZip que o próprio shp-write traz, ou montar um zip mínimo no teste) → importa como 31983 com aviso `/assumido EPSG:31983/`. Se o shp-write não expuser JSZip, gerar esse fixture uma vez e guardar em `tests/editor/fixtures/sem-prj.zip` (sintético).
  - Atributo `observacao_longa` → aviso `/mais de 10 caracteres/`.
  - Documento com só polígonos → o zip não contém `_pontos` nem `_linhas`.

- [ ] **Step 2: Rodar e ver falhar.** Run: `node --test tests/editor/arquivos-shp.test.js`. Expected: FAIL.

- [ ] **Step 3: Implementar.** Se a ida e volta mostrar que o shp-write 0.4.3 perde MultiPolygon ou furo, converter Multi* em várias feições na exportação, com aviso, e registrar o fato no ACEITE.md. Não trocar de biblioteca sem perguntar ao usuário.

- [ ] **Step 4: Rodar e ver passar.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editor/nucleo/formatos/shp.js tests/editor/arquivos-shp.test.js tests/editor/fixtures
git commit -m "feat(editor): formato SHP com .prj e detecção de sistema"
```

---

### Task 8: Contexto e ferramentas base

**Files:**
- Create: `editor/interacao/contexto.js`, `editor/ferramentas/index.js`, `editor/ferramentas/desenhar.js`, `editor/ferramentas/historico.js`, `editor/ferramentas/arquivos.js`
- Test: `tests/editor/ferramentas.test.js`

**Interfaces:**
- Consumes: Tasks 2–7.
- Produces:
  - `criarContexto({ historico, registro, estado, servicos }) -> ctx`, congelado com `Object.freeze`:
    - `ctx.doc` (getter) e `ctx.executar(c)`, `ctx.desfazer()`, `ctx.refazer()`;
    - `ctx.camadaAtiva()` → id ou `null` (de `estado.camadaAtiva`);
    - `ctx.projecao` (módulo da Task 4);
    - `ctx.arquivos = { importar(arq), exportar(formatoId, opcoes), escolher(): Promise<{nome, conteudo}|null>, baixar({nome, conteudo, mime}) }` (`escolher` e `baixar` vêm de `servicos`);
    - `ctx.terradraw(modo)` (de `servicos.terradraw`), `ctx.provisorio` (de `servicos.provisorio`, pode ser um objeto vazio nesta etapa);
    - `ctx.avisar(texto, nivel = 'info')`, `ctx.opcoes(id)`.
    Os erros lançados por `ctx.executar` são repassados; quem chama a ferramenta (a ponte ou a barra) mostra a mensagem com `avisar(..., 'erro')`.
  - `registrarFerramentasBase(registro)` registra:
    - `desenhar-ponto` (atalho `P`), `desenhar-linha` (`L`), `desenhar-poligono` (`G`): `tipo: 'modo'`, `grupo: 'criar'`. `ativar` chama `ctx.terradraw('point'|'linestring'|'polygon')`. `aoGesto(ctx, { tipo: 'desenho-concluido', geometria /* 4326 */ })`: sem camada ativa → `ctx.avisar('Escolha uma camada antes de desenhar', 'erro')`; senão executa `feicao.criar` com `ctx.projecao.paraUTM(geometria)`.
    - `desfazer` (`Ctrl+Z`) e `refazer` (`Ctrl+Y`): `tipo: 'acao'`, `grupo: 'trabalho'`.
    - `importar` (`grupo: 'arquivo'`, `acao`): `escolher` → `arquivos.importar` → um `camada.importar` por camada importada, juntos num `composto` → avisos repassados a `avisar`. Cancelar (`null`) não faz nada.
    - `exportar-geojson`, `exportar-kml`, `exportar-shp-4326`, `exportar-shp-31983` (`acao`): exportam todas as camadas visíveis e chamam `baixar`.

- [ ] **Step 1: Testes que falham**, com um `ctx` real criado por `criarContexto` e `servicos` falsos (`terradraw: m => modos.push(m)`, `escolher: async () => ({ nome: 'a.geojson', conteudo: '<FeatureCollection de teste>' })`, `baixar: a => baixados.push(a)`, `avisar` capturado):
  - ativar `desenhar-poligono` → `modos` igual a `['polygon']`; `aoGesto` com um polígono em graus → 1 feição com coordenadas em UTM.
  - `aoGesto` sem camada ativa → nenhuma feição, aviso de erro `/Escolha uma camada/`.
  - `aoGesto` com a camada ativa travada → `executar` lança `/camada travada/`, o documento não muda.
  - `importar` → 1 camada nova; `desfazer` → nenhuma camada; `refazer` → a camada volta com o mesmo id.
  - `importar` com `escolher` devolvendo `null` → documento igual.
  - `exportar-shp-31983` → `baixados[0].nome` termina em `.zip`.
  - Nenhum arquivo em `editor/ferramentas/` contém `document.`, `window.` nem import de `../interacao/` (o teste lê os fontes e confere com regex).

- [ ] **Step 2: Rodar e ver falhar.** Run: `node --test tests/editor/ferramentas.test.js`. Expected: FAIL.

- [ ] **Step 3: Implementar.**

- [ ] **Step 4: Rodar e ver passar.** Run: `node --test tests/editor/`. Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add editor/interacao/contexto.js editor/ferramentas tests/editor/ferramentas.test.js
git commit -m "feat(editor): contexto das ferramentas e ferramentas de desenho, histórico e arquivos"
```

---

### Task 9: Salvamento automático

**Files:**
- Create: `editor/lab/salvamento.js`
- Test: `tests/editor/salvamento.test.js`

**Interfaces:**
- Produces: `CHAVE = 'editor-lab:documento:v1'`, `salvar(armazenamento, doc) -> boolean`, `restaurar(armazenamento) -> Documento|null`. Nunca lançam: erro do armazenamento, JSON inválido ou `versao !== 1` → `false`/`null`. `restaurar` confere a forma mínima (`camadas` é array, `feicoes` é objeto, `contadores` existe) e roda `conferirGeometria` em cada feição; se alguma falhar → `null`.

- [ ] **Step 1: Testes que falham**, com armazenamento falso `{ getItem, setItem }`:
  - salvar e restaurar devolve um documento `deepEqual` ao original.
  - `getItem` devolvendo `'{quebrado'` → `null`; `getItem` lançando → `null`; `setItem` lançando → `salvar` devolve `false` sem lançar.
  - documento salvo com uma feição de anel aberto → `restaurar` devolve `null`.

- [ ] **Step 2: Rodar e ver falhar.** Run: `node --test tests/editor/salvamento.test.js`. Expected: FAIL.

- [ ] **Step 3: Implementar.**

- [ ] **Step 4: Rodar e ver passar.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editor/lab/salvamento.js tests/editor/salvamento.test.js
git commit -m "feat(editor): salvamento automático tolerante a falhas"
```

---

### Task 10: Página do laboratório

**Files:**
- Create: `editor/lab.html`, `editor/lab.js`, `editor/lab.css`, `editor/lab/fundos.js`, `editor/lab/paineis.js`, `editor/interacao/ponte-terradraw.js`, `editor/interacao/mapa-documento.js`
- Test: `tests/editor/mapa-documento.test.js` (a parte pura); o resto é verificado no navegador (passo 6)

**Interfaces:**
- Consumes: tudo das Tasks 1–9.
- Produces:
  - `fundos.js`: `FUNDOS = [{ id: 'satelite', nome: 'Satélite (Esri World Imagery)', tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'], maxzoom: 19, atribuicao: 'Esri, Maxar, Earthstar Geographics' }, { id: 'nenhum', nome: 'Sem fundo' }]`, `aplicarFundo(mapa, id)`. Um fundo novo (ex.: o ortomosaico do Geovoo) = uma entrada nova na lista. O Hub não tem satélite hoje (o Drone usa fundo liso), então o laboratório usa este.
  - `mapa-documento.js`: `documentoParaExibir(doc) -> FeatureCollection` (só camadas visíveis, 4326, `properties.cor` = cor da camada, `properties.tipoGeom`), e `sincronizarMapa(mapa, doc)`, que atualiza a fonte `'documento'` e as camadas `documento-preenchimento`, `documento-linha` e `documento-ponto`.
  - `ponte-terradraw.js`: `criarPonte({ mapa, aoGesto }) -> { modo(nome) }`. Cria o `TerraDraw` com o adaptador MapLibre e os modos point, linestring e polygon (mais `static` para "nenhum"). No evento `finish`, lê a feição do Terra Draw, **remove-a do Terra Draw** e chama `aoGesto({ tipo: 'desenho-concluido', geometria })`. O Terra Draw nunca guarda o dado.
  - `lab.js`: monta registro, comandos base, formatos (geojson, `criarFormatoKml({ DOMParser: window.DOMParser })`, shp), ferramentas base, histórico (a partir de `restaurar(localStorage)` ou de `criarDocumento()`), contexto e ponte. A barra de ferramentas é **gerada a partir de `registro.ferramentas()` agrupada por `grupo`**, e os atalhos vêm das defs. Em cada `aoMudar`: `sincronizarMapa`, renderização dos painéis e `salvar(localStorage, doc)`.
  - `paineis.js`: `renderizarCamadas(el, doc, estado, executar)` (lista com nome editável, mostrar/ocultar, travar, escolher a ativa, botão "Nova camada"; tudo por comandos), `renderizarAtributos(el, feicaoOuNull, executar)` (nome, categoria, número e campos livres, com adicionar e remover campo), `mostrarAviso(el, texto, nivel)`. **Todo texto vindo do documento entra por `textContent` ou `value`.**
  - Seleção nesta etapa: clicar numa feição no mapa (`queryRenderedFeatures` nas camadas `documento-*`) a seleciona para o painel de atributos. A seleção de verdade (item 4) é da Etapa 2.
  - Aparência: painel lateral à esquerda (camadas em cima, atributos embaixo), barra de ferramentas no topo, avisos num canto. Fonte e cores neutras, sem framework. Funciona a partir de 1280 px de largura (ferramenta de mesa).

- [ ] **Step 1: Teste da parte pura que falha** (`mapa-documento.test.js`): um documento com 2 camadas, uma oculta → `documentoParaExibir` traz só as feições da visível, em graus (primeiro vértice confere com pyproj) e com `properties.cor` da camada.

- [ ] **Step 2: Rodar e ver falhar, implementar `mapa-documento.js`, rodar e ver passar.** Run: `node --test tests/editor/mapa-documento.test.js`.

- [ ] **Step 3: Implementar `fundos.js`, `ponte-terradraw.js`, `paineis.js`, `lab.html`, `lab.css` e `lab.js`.** No `lab.html`: `<link rel="stylesheet" href="vendor/mapa.css">` e `<script type="module" src="lab.js">`. Nada de CDN.

- [ ] **Step 4: Subir localmente.** Run (na raiz do repo): `python -m http.server 8765`, depois abrir `http://localhost:8765/editor/lab.html`. Expected: mapa com satélite e nenhum erro no console.

- [ ] **Step 5: Escrever `editor/ACEITE.md` (seção Etapa 1).** Um roteiro por item, com passos e resultado esperado:
  - **1 (desenhar):** criar uma camada, desenhar ponto, linha e polígono; aparecem com a cor da camada e numerados 1, 2, 3.
  - **15 (desfazer/refazer):** desfazer 3 vezes some tudo; refazer 3 vezes volta com os mesmos números; o mesmo pelos atalhos.
  - **16 (camadas):** ocultar some do mapa; travar e tentar desenhar → mensagem e nada criado; renomear.
  - **17 (atributos):** clicar numa feição, mudar o número para 40, criar o campo `obs`; desfazer reverte.
  - **19 (importar/exportar):** importar um GeoJSON, um KML e um SHP (com e sem `.prj`); exportar nos 4 formatos e reimportar; conferir no QGIS que um polígono exportado em 31983 cai no mesmo lugar e com a mesma área.
  - **Segurança:** importar um KML cujo nome é `<img src=x onerror=alert(1)>` → aparece como texto, sem alerta.
  - **Salvamento:** recarregar a página → o documento volta; apagar a chave `editor-lab:documento:v1` com valor quebrado → abre vazio sem erro.
  Os arquivos de teste para o aceite são gerados pelos testes (Tasks 5–7) ou desenhados no próprio laboratório; nunca dados reais.

- [ ] **Step 6: Rodar o roteiro pelo navegador automatizado** (Playwright ou Claude in Chrome) em cada item do ACEITE.md da Etapa 1. Registrar no fim de cada item: `Claude: ok <data>` ou o que falhou. Os itens que dependem de arquivo do sistema ou do QGIS ficam marcados `Usuário`.

- [ ] **Step 7: Rodar a suíte inteira.** Run: `node --test $(find tests/editor -name "*.test.js")`. Expected: todos PASS.

- [ ] **Step 8: Commit**

```bash
git add editor/lab.html editor/lab.js editor/lab.css editor/lab editor/interacao editor/ACEITE.md tests/editor/mapa-documento.test.js
git commit -m "feat(editor): página do laboratório com mapa, painéis e roteiro de aceite da Etapa 1"
```

---

## Fim da Etapa 1

- O usuário faz o aceite dos itens 1, 15, 16, 17 e 19 no `ACEITE.md`.
- Só depois disso: plano da Etapa 2 (transformar e medir), escrito a partir do que esta etapa ensinou.
