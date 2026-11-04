# Paralelismo — plano de implementação

> **Para quem executa:** uma sessão do Claude por etapa (P0…P6). Comece pela seção da sua etapa. A P0 já está em passos. Nas P1–P6, o primeiro passo é detalhar a sua seção em passos (skill `writing-plans`, mesmo formato da P0) em `docs/superpowers/plans/2026-10-29-paralelismo-Px.md`, mostrar ao usuário e só então executar. Execução: skill `delegar` (camada 1 = OpenCode grátis via `delegar.sh`, `-a frontend` para telas; 2 = sub-agente Haiku; 3 = Claude; U = usuário), seguindo `test-driven-development`. Marque as caixas (`- [ ]`) conforme avança.

**Objetivo:** levar para o Hub a análise de paralelismo do plantio (cana e torta) da Usina da Pedra: o usuário escolhe a pasta do pen-drive, confere, a análise roda no navegador (Pyodide), um editor valida e o resultado por talhão aparece no painel e no relatório; os brutos ficam arquivados no GitHub Releases.

**Arquitetura:** núcleo Python novo em `paralelismo/` (leitores `.jdl`/GS3 + pipeline LSFP→QBD→CLE→limpar→PLL + agregação por talhão), copiado do `base-op` e rodado no navegador por um Web Worker com Pyodide. A identificação dos arquivos (série, fazenda, data) é feita em JS puro, antes de carregar o Pyodide. Banco no schema `hub` com rodadas pendente/publicada/recusada e RPCs transacionais; o Worker do Cloudflare ganha a rota `POST /paralelismo/parte` para subir as partes zipadas. Página própria `app/paralelismo.html`, no padrão do Corretivos.

**Tecnologias:** Python 3.14 + pytest, shapely 2, pyproj, pyshp (`shapefile`); Pyodide 0.27.7 (`numpy`, `shapely`, `pyproj`, `pyshp` via `micropip`); Postgres/Supabase (schema `hub`, PostGIS em `extensions`), supabase-js v2; Cloudflare Worker (`worker/arquivos.js`); JS ES2020 sem build, `node --test`; fflate (versão fixada, jsdelivr); MapLibre GL 4.7.1; Playwright + Edge em Python (E2E).

**Spec:** [docs/superpowers/specs/2026-10-26-paralelismo-design.md](../specs/2026-10-26-paralelismo-design.md) (aprovada em 29/10/2026).

**Maquete aprovada (29/10/2026):** [specs/assets/2026-10-29-paralelismo-visualizador.html](../specs/assets/2026-10-29-paralelismo-visualizador.html) · https://claude.ai/artifact/MstWwjDvuDW5m2Y5i5vNYT. Referência visual da P3–P5: o mapa dos talhões e amostras é o palco (janela inteira) e as abas Painel/Processar/Pendentes/Rodadas só mudam o que ele mostra e o que a coluna de 380 px à direita resume; Frotas é sub-aba de Rodadas; o processamento é animado no próprio mapa (trilha → linhas → limpeza em vermelho → varredura do PLL) com a faixa de fases no padrão de espera do Hub; prévia e Pendentes ligam a camada "Mudança". **Só tema claro**, como o resto do Hub. Não é modelo para outros módulos: as peças (cabeçalho, coluna, faixa de fases, camadas) são reaproveitadas e ajustadas conforme a necessidade.

## Restrições globais

- Parâmetros fixos no código, iguais ao validado: LSFP **10 m**, QBD **160°**, CLE **10 m**, PLL a cada **10 m**, ideal **2,90–3,10 m**, ignora fora de **2,60–3,40 m**, talhão com **menos de 25 amostras** = "amostra insuficiente".
- Pontos usados: `.jdl` = trilha do trator (item rico, 0,2 s) só com estado de trabalho ligado (`pontos_trator`); GS3 = antena do trator **`_5140`** com gravação ligada. (O `base-op` tem `MODO = "implemento"` como padrão; o Hub usa sempre o modo trator, que é o que deu 77,85% na 10233.)
- Projeção de trabalho: **EPSG:31983** (SIRGAS 2000 / UTM 23S). Banco guarda `geometry(LineString, 31983)`.
- Frota vem da série do `.jdl` (`BM\d{4}[A-Z]\d{6}`) pela tabela de frotas; nunca do nome da pasta. GS3 não tem série: chave `'GS3:<frota>'`. Prestador aparece pelo nome. Operação (`cana`|`torta`) vem da frota.
- Fazenda: 5 dígitos do nome gravado no monitor (pasta do log do `.jdl`, `Farm` do `.fdl`); revisão (`Rev1`) só informativa; talhão sai da geometria.
- Arquivo bruto identificado por **SHA-256**; arquivo já registrado em qualquer rodada pendente ou publicada = "já analisado" e é ignorado.
- Partes zipadas de até **90 MB** (limite do Worker é 100 MB). Release `paralelismo-r<id>` em `lmalerbo/hub-geotech-arquivos`.
- Níveis: leitura | solicitante | editor (+ admin), em `hub.usuario_modulos.nivel`, módulo `paralelismo` escondido do menu lateral e cadastrado em Ferramentas.
- Textos da tela em português do Brasil, vírgula decimal. Página HTML/CSS/JS puro, funções com prefixo `par`, estado em `PAR`, funciona em 390 px.
- Dado real (pen-drives, Base Fazendas, `Paralelismo8.xlsx`) **nunca** vai para o executor externo (camada 1). Tarefas com arquivos reais são camada 2 ou 3.
- Migrations: o **usuário** aplica no SQL Editor do Supabase. Testes que gravam no banco apagam só o que eles mesmos criaram.
- Cada etapa termina com testes passando, `verification-before-completion`, `requesting-code-review` e **ok do usuário antes de mesclar na main e enviar** (push em `lmalerbo/*` exige trocar a conta do `gh` só durante o push).

## Decisões de execução (completam a spec; confirmar com o usuário ao revisar este plano)

1. **Identificação em JS, processamento em Python.** A conferência (série, fazenda, data, "GS3 sem documentação") é feita em JS lendo bytes/XML, sem carregar o Pyodide. O Python recebe, por arquivo, a frota, a operação, o `cod_faz` e a data já resolvidos pela conferência. Assim a frota escolhida pelo usuário para o GS3 é a que vale, e só existe uma regra de identificação.
2. **Id da rodada antes do envio dos brutos.** A release precisa do id (`paralelismo-r<id>`), mas nada pode ser gravado se o envio falhar. `hub.paralelismo_preparar_parte(p_rodada_id bigint default null)` confere o acesso e, quando `p_rodada_id` vem nulo, devolve `nextval` da sequência das rodadas **sem inserir linha**. As partes seguintes e o `paralelismo_enviar` usam esse id. Falha no meio = só assets órfãos na release; "tentar de novo" reaproveita o mesmo id e o Worker substitui o asset de mesmo nome.
3. **"Fazenda que mudou desde a prévia"** é detectada por uma coluna a mais, `paralelismo_analises.base_analise_id` (a vigente quando a prévia foi feita; nula se a fazenda era nova). Ao publicar, se a vigente atual de `(operacao, cod_faz)` for outra, o RPC recusa com `recalculo_necessario` e a lista das fazendas; a tela refaz `limpar` + PLL e chama de novo com o `recalculo`.
4. **Excluir rodada publicada** só é permitido se nenhuma rodada publicada **depois** dela tocou as mesmas fazendas e operações (a análise mais nova já embutiria as linhas dela). Caso contrário, o RPC recusa com "exclua antes a rodada mais nova da fazenda X".
5. **Aderência da fazenda** conta só as amostras dentro de talhão; as de fora vão para `fora_talhao`. O total do PLL (dentro + fora) também é devolvido, porque é o número comparável com o resultado atual (2.506 / 77,85%).
6. **Frota sem trabalho registrado:** aviso quando a frota tem trilha de pelo menos 1 h numa fazenda e menos de 10% dela com trabalho ligado. Limites em constantes; conferir com o caso real 55805/10010 de 26/10 na P3.

## Foco da revisão (casos que os testes das tarefas não cobrem sozinhos)

1. **O mesmo pen-drive entra duas vezes** (copiado de novo, ou GS3 que acumula sessões antigas, ou uma segunda rodada enviada antes de a primeira ser validada). Esperado: arquivos já registrados aparecem como "já analisados" e não geram linha nem amostra repetida. → testes na P1 (`paralelismo_ja_analisados` com rodada pendente) e na P2 (`parSepararJaAnalisados`).
2. **Pen-drive com arquivo truncado ou pasta sem documentação** (`.fdd` cortado, GS3 só com mapa de cobertura). Esperado: o arquivo é pulado e listado; o resto da rodada processa. → testes na P0 (Tarefa P0.1, `test_jdl_truncado_nao_quebra`, `test_gs3_fdd_truncado_nao_quebra`) e na P2 (`parConferencia`, aviso "sem executado").
3. **Duas rodadas da mesma fazenda validadas fora de ordem.** Esperado: a segunda a ser publicada refaz `limpar` + PLL com as linhas vigentes, e o painel mostra a junção das duas. → teste na P1 (`publicar` sem recálculo recusa) e no E2E da P6.
4. **Usuário só leitura ou solicitante** tentando publicar, ver pendente de outro ou editar frotas. Esperado: o banco recusa e a tela nem mostra a ação. → testes RLS na P1 e conferência na P4.
5. **Página fechada ou pen-drive retirado no meio da fila.** Esperado: a cópia no OPFS permite seguir sem o pen-drive; fechar a página não grava nada; reabrir oferece descartar as cópias que sobraram no OPFS. → teste na P3 (`parOpfsSobras`).

---

## P0 — Núcleo Python `paralelismo/`

**Desvios na execução (04/11/2026):**
- **Amostras reais fora do git.** O `lmalerbo/hub-geotech` é público e os arquivos têm GPS real. `tests/dados/paralelismo/amostra.*` está no `.gitignore`, `test_leitores.py` usa o marcador `dados_reais` e `LEIAME.md` diz de onde copiar. O `pytest` normal cobre os leitores com arquivos sintéticos (`test_leitores_sinteticos.py`).
- **Pastas de origem mudaram:** agora `EXECUTADOS\2026-2027\BRUTOS\TORTA\10233Rev0` e `BRUTOS\CANA\10966Rev0`.
- **10966 agrupa por pasta de frota** (a cada subpasta da 10966Rev0, uma frota). Com isso deu 30.395 / 88,86%, igual ao `base-op`.
- **Código copiado do `base-op` no commit `935543c`.** A execução da P0 foi toda na camada 3, sem executor externo.
- **Mês conta todas as amostras da análise** (spec §4), inclusive as fora de talhão, para a fazenda sem polígono na base não ficar sem mês. Isso substitui a nota da Tarefa P0.3.
- **Para a P3:** fixar a versão do `pyshp` no `micropip` e filtrar o manifesto por módulo (hoje o Corretivos baixa os arquivos do paralelismo sem usar, e vice-versa).

**Arquivos:**
- Criar: `paralelismo/__init__.py`, `paralelismo/jdl.py`, `paralelismo/gs3.py`, `paralelismo/pipeline.py`, `paralelismo/analise.py`
- Criar: `tests/paralelismo/__init__.py`, `tests/paralelismo/test_leitores.py`, `tests/paralelismo/test_pipeline.py`, `tests/paralelismo/test_analise.py`, `tests/paralelismo/test_regressao.py`
- Criar: `tests/dados/paralelismo/` (um `.jdl` pequeno e uma sessão GS3 `.fdl`+`.fdd`, reais)
- Modificar: `pytest.ini` (marcador `dados_reais`)

**Origem do código:** `C:\Users\lmalerbo\Documents\GitHub\base-op\scripts\` — **cópia do working tree**, não do último commit (os scripts estão modificados e não commitados lá). Antes de copiar, peça ao usuário para commitar esses scripts no `base-op`, e anote o hash no commit do Hub.

**Interfaces produzidas (as próximas etapas dependem destes nomes):**
- `paralelismo.jdl.ler_jdl(caminho: str) -> tuple[list[tuple[float, float]], int]` → `(pontos (lat, lon) com trabalho ligado, total de ticks da trilha)`. Arquivo ilegível → `([], 0)`.
- `paralelismo.gs3.ler_gs3(caminho_fdl: str) -> tuple[list[tuple[float, float]], int]` → `(pontos (lat, lon) da antena 5140 com gravação ligada, total de registros)`. Sem `.fdd` ou ilegível → `([], 0)`.
- `paralelismo.pipeline`: `lsfp`, `qbd`, `cle`, `limpar`, `pll_amostras`, `Amostra` (iguais ao `base-op`).
- `paralelismo.analise`:
  - constantes `LSFP_M, QBD_GRAUS, CLE_M, PASSO_PLL, IDEAL_MIN, IDEAL_MAX, IGNORA_MIN, IGNORA_MAX, MIN_AMOSTRAS_TALHAO, SEM_TRABALHO_MIN_S, SEM_TRABALHO_FRACAO`;
  - `para_utm(pontos_latlon) -> list[tuple[float, float]]`;
  - `linhas_do_grupo(pontos_xy) -> list[LineString]` (LSFP→QBD→CLE de uma frota numa fazenda);
  - `talhoes_de_geojson(fc: dict) -> dict[int, Polygon | MultiPolygon]` (entra em 4326 com a propriedade `talhao`, sai em 31983);
  - `classe(espacamento) -> 'abaixo' | 'aderente' | 'acima'`;
  - `mes_execucao(contagem: dict[str, int]) -> str | None` (chave `'AAAA-MM-DD'`, devolve `'AAAA-MM-01'`);
  - `sem_trabalho(duracao_total_s: float, duracao_trabalho_s: float) -> bool`;
  - `analisar_fazenda(linhas: list[dict], talhoes: dict) -> dict` — cada linha `{'frota': str, 'data': 'AAAA-MM-DD', 'coords': [[x, y], ...]}` em 31983 (formato que vai e volta do banco); devolve o dicionário descrito na Tarefa P0.3, serializável em JSON;
  - `exportar_shapefiles(resultado: dict, linhas: list[dict], prefixo: str) -> bytes` (zip com `<prefixo>_Amostras.*` e `<prefixo>_Linhas.*`, `.prj` de 31983).

### Tarefa P0.1: leitores `.jdl` e GS3 (camada 2, Haiku — usa arquivos reais)

**Interfaces:** produz `ler_jdl`, `ler_gs3` (acima).

- [x] **Passo 1: preparar os arquivos de amostra.** Escolher na pasta de torta organizada (`G:\...\EXECUTADOS\2026-2027\TORTA\ORGANIZAR\unificado\10233Rev0`, ou onde o usuário indicar) o **menor `.jdl` com pontos de trabalho** (rodar `pontos_trator` do `base-op` em cada um e pegar o menor com > 500 pontos), e em `CANA\ORGANIZAR\UNIFICADO` uma sessão GS3 (`.fdl` + `.fdd` de mesmo nome) da 10966 com > 300 registros. Copiar para `tests/dados/paralelismo/` como `amostra.jdl`, `amostra.fdl`, `amostra.fdd`. Anotar em `tests/dados/paralelismo/LEIAME.md` a origem de cada um e os números que o `base-op` dá para eles:

```bash
cd /c/Users/lmalerbo/Documents/GitHub/base-op/scripts
python -c "
from jdl_documentacao import pontos_trator, ler_trilha_trator
from gs3_documentacao import ler_sessao, pontos_plantio
d='C:/Users/lmalerbo/Documents/hub-geotech/tests/dados/paralelismo/'
print('jdl', len(pontos_trator(d+'amostra.jdl')), len(ler_trilha_trator(d+'amostra.jdl')))
s=ler_sessao(d+'amostra.fdl'); print('gs3', len(pontos_plantio(s, antena='5140')), len(s['registros']), s['fazenda'], s['inicio'])"
```

Esses números (`N_JDL`, `TICKS_JDL`, `N_GS3`, `REG_GS3`) vão nos testes do Passo 2.

- [x] **Passo 2: escrever o teste que falha** — `tests/paralelismo/test_leitores.py` (substituir `N_JDL` etc. pelos números do Passo 1):

```python
from pathlib import Path

from paralelismo.gs3 import ler_gs3
from paralelismo.jdl import ler_jdl

DADOS = Path(__file__).resolve().parent.parent / 'dados' / 'paralelismo'
N_JDL, TICKS_JDL = 0, 0   # do LEIAME.md
N_GS3, REG_GS3 = 0, 0     # do LEIAME.md


def test_jdl_igual_ao_base_op():
    pontos, ticks = ler_jdl(str(DADOS / 'amostra.jdl'))
    assert (len(pontos), ticks) == (N_JDL, TICKS_JDL)
    lat, lon = pontos[0]
    assert -25 < lat < -19 and -52 < lon < -44


def test_gs3_igual_ao_base_op():
    pontos, registros = ler_gs3(str(DADOS / 'amostra.fdl'))
    assert (len(pontos), registros) == (N_GS3, REG_GS3)


def test_jdl_truncado_nao_quebra(tmp_path):
    dados = (DADOS / 'amostra.jdl').read_bytes()
    corte = tmp_path / 'cortado.jdl'
    corte.write_bytes(dados[: len(dados) // 2 + 7])
    pontos, ticks = ler_jdl(str(corte))
    assert 0 < len(pontos) <= N_JDL and ticks <= TICKS_JDL


def test_gs3_fdd_truncado_nao_quebra(tmp_path):
    (tmp_path / 's.fdl').write_bytes((DADOS / 'amostra.fdl').read_bytes())
    fdd = (DADOS / 'amostra.fdd').read_bytes()
    (tmp_path / 's.fdd').write_bytes(fdd[: len(fdd) // 2 + 3])
    pontos, registros = ler_gs3(str(tmp_path / 's.fdl'))
    assert len(pontos) <= N_GS3 and registros <= REG_GS3


def test_gs3_sem_fdd_e_jdl_inexistente(tmp_path):
    (tmp_path / 'so.fdl').write_bytes((DADOS / 'amostra.fdl').read_bytes())
    assert ler_gs3(str(tmp_path / 'so.fdl')) == ([], 0)
    assert ler_jdl(str(tmp_path / 'nao_existe.jdl')) == ([], 0)
```

- [x] **Passo 3: rodar e ver falhar.** `pytest tests/paralelismo/test_leitores.py -v` → `ModuleNotFoundError: No module named 'paralelismo'`.

- [x] **Passo 4: implementar.**
  - `paralelismo/__init__.py`: docstring de uma linha (`"""Análise de paralelismo do plantio (fonte única; publicada em app/py/paralelismo/)."""`).
  - `paralelismo/jdl.py`: no topo, as funções de `jdl_rich_fields.py` que `jdl_documentacao.py` usa (`read_varint`, `decode_flat`, `_zigzag`, `ticks_item_rico`, e o que elas chamam), depois o conteúdo de `jdl_documentacao.py` **sem alterar a lógica**, trocando o `from jdl_rich_fields import ...` pelas funções locais. Manter as docstrings do original. Acrescentar no fim:

```python
def ler_jdl(caminho: str) -> tuple[list[tuple[float, float]], int]:
    """(pontos (lat, lon) da trilha do trator com trabalho ligado, total de
    ticks da trilha). O total serve para o aviso de frota sem trabalho."""
    try:
        trilha = ler_trilha_trator(caminho)
        _, eventos = ler_documentacao(caminho)
    except OSError:
        return [], 0
    return _filtrar_por_estado(trilha, eventos), len(trilha)
```

  - `paralelismo/gs3.py`: conteúdo de `gs3_documentacao.py` sem alterar a lógica. Acrescentar no fim:

```python
def ler_gs3(caminho_fdl: str) -> tuple[list[tuple[float, float]], int]:
    """(pontos (lat, lon) da antena do trator, _5140, com gravação ligada,
    total de registros da sessão). Sem .fdd ou ilegível: ([], 0)."""
    try:
        sessao = ler_sessao(caminho_fdl)
    except (OSError, UnicodeDecodeError):
        return [], 0
    return pontos_plantio(sessao, antena="5140"), len(sessao["registros"])
```

  Se `ler_documentacao` ou `ler_sessao` levantarem outra exceção no arquivo truncado, capture **essa** exceção específica no `ler_*` (não `except Exception`).

- [x] **Passo 5: rodar e ver passar.** `pytest tests/paralelismo/test_leitores.py -v` → 5 passed.

- [x] **Passo 6: commit.**

```bash
git add paralelismo/__init__.py paralelismo/jdl.py paralelismo/gs3.py tests/paralelismo tests/dados/paralelismo
git commit -m "Paralelismo P0.1: leitores .jdl e GS3 copiados do base-op (<hash>)"
```

### Tarefa P0.2: pipeline LSFP/QBD/CLE/limpar/PLL (camada 1, `delegar.sh -a build` — só dados sintéticos)

**Interfaces:** produz `paralelismo.pipeline.{lsfp, qbd, cle, limpar, pll_amostras, Amostra}`.

- [x] **Passo 1: escrever o teste que falha** — `tests/paralelismo/test_pipeline.py`. Os números (desta tarefa, da P0.3 e da P0.4) foram conferidos em 29/10/2026 rodando o código deste plano sobre o `paralelismo_pipeline.py` atual do `base-op`: 16 testes passando.

```python
from shapely.geometry import LineString

from paralelismo.pipeline import cle, limpar, lsfp, pll_amostras, qbd


def passadas(n, espacamento, comprimento=200.0, x0=0.0, y0=0.0):
    """n passadas retas paralelas, com um ponto a cada 0,5 m."""
    return [LineString([(x0 + d / 2, y0 + k * espacamento) for d in range(int(comprimento * 2) + 1)])
            for k in range(n)]


def contagem(linhas):
    a = pll_amostras(linhas)
    aderentes = sum(1 for x in a if 2.90 <= x.espacamento <= 3.10)
    acima = sum(1 for x in a if x.espacamento > 3.10)
    return len(a), aderentes, acima, len(a) - aderentes - acima


def test_espacamento_ideal_tudo_aderente():
    # 8 passadas de 200 m: 19 amostras por lado, 14 lados com vizinha
    assert contagem(passadas(8, 3.00)) == (266, 266, 0, 0)


def test_espacamento_largo_e_estreito():
    assert contagem(passadas(8, 3.20)) == (266, 0, 266, 0)
    assert contagem(passadas(8, 2.80)) == (266, 0, 0, 266)


def test_limpar_mantem_passadas_boas():
    assert len(limpar(passadas(8, 3.00))) == 8


def test_limpar_tira_empilhada():
    linhas = passadas(8, 3.00) + [LineString([(20, 3.3), (150, 3.3)])]
    limpas = limpar(linhas)
    assert len(limpas) == 8 and all(l.length == 200.0 for l in limpas)


def test_limpar_tira_cruzamento():
    limpas = limpar(passadas(8, 3.00) + [LineString([(100, -10), (100, 40)])])
    assert len(limpas) == 8 and not any(l.length == 50 for l in limpas)


def test_limpar_tira_isolada():
    assert len(limpar(passadas(8, 3.00) + [LineString([(500, 500), (600, 500)])])) == 8


def test_lsfp_quebra_no_salto_e_qbd_corta_manobra():
    assert [round(l.length) for l in lsfp({'f': [(0, 0), (5, 0), (30, 0), (35, 0)]}, max_dist=10.0)] == [5, 5]
    ida = [(d / 2, 0.0) for d in range(401)]
    volta = [(200 - d / 2, 3.0) for d in range(401)]
    linhas = cle(qbd(lsfp({'f': ida + [(201.5, 1.5)] + volta}, max_dist=10.0), min_angle_deg=160.0),
                 min_length=10.0)
    assert [round(l.length) for l in linhas] == [200, 200]
```

- [x] **Passo 2: rodar e ver falhar.** `pytest tests/paralelismo/test_pipeline.py -v` → `ModuleNotFoundError: No module named 'paralelismo.pipeline'`.

- [x] **Passo 3: implementar.** `paralelismo/pipeline.py` = `base-op/scripts/paralelismo_pipeline.py` **sem alterar a lógica**, removendo o bloco `if __name__ == "__main__":` e as funções `pll`, `PLLResultado` e `analisar` (o Hub não as usa; a agregação fica em `analise.py`). Manter as docstrings.

- [x] **Passo 4: rodar e ver passar.** `pytest tests/paralelismo/test_pipeline.py -v` → 7 passed.

- [x] **Passo 5: commit.** `git add paralelismo/pipeline.py tests/paralelismo/test_pipeline.py && git commit -m "Paralelismo P0.2: pipeline LSFP/QBD/CLE/limpar/PLL"`

### Tarefa P0.3: análise por fazenda e talhão (camada 1, `delegar.sh -a build` — só dados sintéticos)

**Interfaces:** consome `paralelismo.pipeline`; produz as funções de `paralelismo.analise` listadas no início da P0. Resultado de `analisar_fazenda`:

```python
{
  'pll_total': int, 'pll_aderentes': int,          # todas as amostras do PLL (dentro + fora de talhão)
  'amostras': int, 'aderentes': int, 'acima': int, 'abaixo': int,   # só dentro de talhão
  'fora_talhao': int,
  'mes': 'AAAA-MM-01' | None,
  'talhoes': [{'talhao_num': int, 'amostras': int, 'aderentes': int, 'acima': int, 'abaixo': int,
               'media_m': float (3 casas), 'frotas': [str, ...] (ordenadas), 'insuficiente': bool}],  # por talhao_num
  'frotas': [{'frota': str, 'amostras': int, 'aderentes': int}],                                    # por frota
  'linhas_usadas': int,                            # linhas que sobraram do limpar
  'pontos': [[x, y, x_vizinha, y_vizinha, espacamento, classe, talhao_num | None, frota], ...],
}
```

- [x] **Passo 1: escrever o teste que falha** — `tests/paralelismo/test_analise.py`:

```python
import pytest
from shapely.geometry import box, mapping

from paralelismo.analise import (analisar_fazenda, classe, mes_execucao, para_utm, sem_trabalho,
                                 talhoes_de_geojson)


def linhas(n, espacamento, frota='64086', data='2026-10-03', y0=0.0, comprimento=200.0):
    return [{'frota': frota, 'data': data,
             'coords': [[d / 2, y0 + k * espacamento] for d in range(int(comprimento * 2) + 1)]}
            for k in range(n)]


TALHOES = {
    1: box(0, -5, 15, 30),        # só a amostra de x = 10 → 14 amostras → insuficiente
    2: box(15, -5, 250, 30),      # x = 20..190 → 18 × 14 = 252
    3: box(0, 95, 250, 130),      # passadas a 3,20 m em y0 = 100 → 266, todas acima
}


def test_classe_nos_limites():
    assert [classe(e) for e in (2.89, 2.90, 3.10, 3.11)] == ['abaixo', 'aderente', 'aderente', 'acima']


def test_para_utm_31983():
    (x, y), = para_utm([(-22.0, -48.0)])
    assert x == pytest.approx(190234.95, abs=0.01) and y == pytest.approx(7564133.21, abs=0.01)


def test_talhoes_de_geojson_converte_para_31983():
    fc = {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'talhao': 7},
         'geometry': mapping(box(-48.001, -22.001, -47.999, -21.999))}]}
    t = talhoes_de_geojson(fc)
    assert list(t) == [7] and t[7].bounds[0] > 100000 and t[7].area == pytest.approx(45809, rel=0.01)


def test_analisar_fazenda_por_talhao():
    r = analisar_fazenda(linhas(8, 3.00) + linhas(8, 3.20, frota='PLANT CANA', y0=100.0), TALHOES)
    assert (r['pll_total'], r['pll_aderentes']) == (532, 266)
    assert (r['amostras'], r['aderentes'], r['acima'], r['abaixo'], r['fora_talhao']) == (532, 266, 266, 0, 0)
    t = {x['talhao_num']: x for x in r['talhoes']}
    assert (t[1]['amostras'], t[1]['insuficiente']) == (14, True)
    assert (t[2]['amostras'], t[2]['aderentes'], t[2]['insuficiente'], t[2]['frotas']) == (252, 252, False, ['64086'])
    assert (t[3]['acima'], t[3]['media_m'], t[3]['frotas']) == (266, 3.2, ['PLANT CANA'])
    assert {f['frota']: f['aderentes'] for f in r['frotas']} == {'64086': 266, 'PLANT CANA': 0}
    assert r['linhas_usadas'] == 16 and len(r['pontos']) == 532


def test_amostra_fora_de_talhao():
    r = analisar_fazenda(linhas(8, 3.00), {2: box(15, -5, 250, 30)})
    assert (r['pll_total'], r['amostras'], r['fora_talhao']) == (266, 252, 14)


def test_mes_de_execucao_pelas_amostras():
    ls = linhas(8, 3.00)
    for l in ls[6:]:
        l['data'] = '2026-09-20'      # 57 amostras em set, 209 em out
    assert analisar_fazenda(ls, TALHOES)['mes'] == '2026-10-01'
    assert mes_execucao({'2026-09-20': 300, '2026-10-01': 100, '2026-10-02': 250}) == '2026-10-01'
    assert mes_execucao({}) is None


def test_sem_trabalho():
    assert sem_trabalho(7200, 300) is True       # 2 h de trilha, 4% trabalhando
    assert sem_trabalho(7200, 3000) is False
    assert sem_trabalho(1800, 0) is False        # trilha curta não avisa


def test_fazenda_vazia():
    r = analisar_fazenda([], TALHOES)
    assert (r['pll_total'], r['amostras'], r['mes'], r['talhoes']) == (0, 0, None, [])
```

- [x] **Passo 2: rodar e ver falhar.** `pytest tests/paralelismo/test_analise.py -v` → `ModuleNotFoundError`.

- [x] **Passo 3: implementar** `paralelismo/analise.py`:

```python
"""Agregação do paralelismo por fazenda, talhão e frota (parâmetros fixos, iguais ao validado no base-op)."""
import collections

import pyproj
from shapely.geometry import LineString, Point, shape
from shapely.strtree import STRtree

from paralelismo.pipeline import cle, limpar, lsfp, pll_amostras, qbd

LSFP_M, QBD_GRAUS, CLE_M, PASSO_PLL = 10.0, 160.0, 10.0, 10.0
IDEAL_MIN, IDEAL_MAX = 2.90, 3.10
IGNORA_MIN, IGNORA_MAX = 2.60, 3.40
MIN_AMOSTRAS_TALHAO = 25
SEM_TRABALHO_MIN_S, SEM_TRABALHO_FRACAO = 3600, 0.10

_PARA_UTM = pyproj.Transformer.from_crs(4326, 31983, always_xy=True)


def para_utm(pontos_latlon):
    if not pontos_latlon:
        return []
    xs, ys = _PARA_UTM.transform([lo for _, lo in pontos_latlon], [la for la, _ in pontos_latlon])
    return list(zip(xs, ys))


def linhas_do_grupo(pontos_xy):
    """LSFP -> QBD -> CLE dos pontos de uma frota numa fazenda, em ordem de gravação."""
    return cle(qbd(lsfp({'g': pontos_xy}, max_dist=LSFP_M), min_angle_deg=QBD_GRAUS), min_length=CLE_M)


def talhoes_de_geojson(fc):
    saida = {}
    for f in fc.get('features', []):
        g = shape(f['geometry'])
        g = _transformar(g)
        saida[int(f['properties']['talhao'])] = g if g.is_valid else g.buffer(0)
    return saida


def _transformar(g):
    from shapely.ops import transform
    return transform(lambda x, y, z=None: _PARA_UTM.transform(x, y), g)


def classe(espacamento):
    if espacamento < IDEAL_MIN:
        return 'abaixo'
    if espacamento > IDEAL_MAX:
        return 'acima'
    return 'aderente'


def mes_execucao(contagem):
    if not contagem:
        return None
    por_mes = collections.Counter()
    for data, n in contagem.items():
        por_mes[data[:7]] += n
    return por_mes.most_common(1)[0][0] + '-01'


def sem_trabalho(duracao_total_s, duracao_trabalho_s):
    return duracao_total_s >= SEM_TRABALHO_MIN_S and duracao_trabalho_s < SEM_TRABALHO_FRACAO * duracao_total_s


def analisar_fazenda(linhas, talhoes):
    geoms = [LineString(l['coords']) for l in linhas]
    limpas = {id(g) for g in limpar(geoms)}
    usadas = [(g, l) for g, l in zip(geoms, linhas) if id(g) in limpas]
    amostras = pll_amostras([g for g, _ in usadas], IGNORA_MIN, IGNORA_MAX, PASSO_PLL)

    nums = list(talhoes)
    polis = [talhoes[n] for n in nums]
    arvore = STRtree(polis) if polis else None

    def talhao_em(x, y):
        if arvore is None:
            return None
        p = Point(x, y)
        for i in arvore.query(p):
            if polis[i].contains(p):
                return nums[i]
        return None

    vazio = lambda: {'amostras': 0, 'aderentes': 0, 'acima': 0, 'abaixo': 0, 'soma': 0.0, 'frotas': set()}
    por_talhao = collections.defaultdict(vazio)
    por_frota = collections.defaultdict(lambda: {'amostras': 0, 'aderentes': 0})
    datas = collections.Counter()
    pontos, pll_aderentes, fora = [], 0, 0
    for a in amostras:
        linha = usadas[a.linha][1]
        cl = classe(a.espacamento)
        pll_aderentes += cl == 'aderente'
        num = talhao_em(a.x, a.y)
        pontos.append([a.x, a.y, a.x_vizinha, a.y_vizinha, round(a.espacamento, 3), cl, num, linha['frota']])
        if num is None:
            fora += 1
            continue
        t = por_talhao[num]
        t['amostras'] += 1
        t[cl + 's' if cl == 'aderente' else cl] += 1
        t['soma'] += a.espacamento
        t['frotas'].add(linha['frota'])
        f = por_frota[linha['frota']]
        f['amostras'] += 1
        f['aderentes'] += cl == 'aderente'
        datas[linha['data']] += 1

    talhoes_saida = [{'talhao_num': n, 'amostras': t['amostras'], 'aderentes': t['aderentes'],
                      'acima': t['acima'], 'abaixo': t['abaixo'],
                      'media_m': round(t['soma'] / t['amostras'], 3), 'frotas': sorted(t['frotas']),
                      'insuficiente': t['amostras'] < MIN_AMOSTRAS_TALHAO}
                     for n, t in sorted(por_talhao.items())]
    soma = lambda k: sum(t[k] for t in talhoes_saida)
    return {
        'pll_total': len(amostras), 'pll_aderentes': pll_aderentes,
        'amostras': soma('amostras'), 'aderentes': soma('aderentes'), 'acima': soma('acima'),
        'abaixo': soma('abaixo'), 'fora_talhao': fora, 'mes': mes_execucao(datas),
        'talhoes': talhoes_saida,
        'frotas': [{'frota': k, **v} for k, v in sorted(por_frota.items())],
        'linhas_usadas': len(usadas), 'pontos': pontos,
    }
```

  Notas para quem implementa: `mes` conta todas as amostras da análise pela data da linha; frota sem amostra em talhão não aparece em `frotas`. Se algum teste numérico não bater, **não ajuste o número do teste**: os números vêm do código validado; investigue a implementação.

- [x] **Passo 4: rodar e ver passar.** `pytest tests/paralelismo -v` → todos passam.

- [x] **Passo 5: commit.** `git add paralelismo/analise.py tests/paralelismo/test_analise.py && git commit -m "Paralelismo P0.3: análise por fazenda, talhão e frota"`

### Tarefa P0.4: shapefiles de amostras e linhas (camada 1, `delegar.sh -a build`)

**Interfaces:** consome o resultado de `analisar_fazenda`; produz `exportar_shapefiles(resultado, linhas, prefixo) -> bytes`.

- [x] **Passo 1: escrever o teste que falha** — acrescentar em `tests/paralelismo/test_analise.py`:

```python
import io
import zipfile

import shapefile

from paralelismo.analise import exportar_shapefiles


def test_exportar_shapefiles(tmp_path):
    ls = linhas(8, 3.00)
    r = analisar_fazenda(ls, TALHOES)
    z = zipfile.ZipFile(io.BytesIO(exportar_shapefiles(r, ls, '10233_torta')))
    nomes = set(z.namelist())
    for base in ('10233_torta_Amostras', '10233_torta_Linhas'):
        assert {f'{base}.{e}' for e in ('shp', 'shx', 'dbf', 'prj', 'cpg')} <= nomes
    z.extractall(tmp_path)
    am = shapefile.Reader(str(tmp_path / '10233_torta_Amostras'))
    assert len(am) == 266
    assert [f[0] for f in am.fields[1:]] == ['Talhao', 'Aderencia', 'Frota', 'Espac']
    assert am.record(0)['Aderencia'] == 'aderente'
    li = shapefile.Reader(str(tmp_path / '10233_torta_Linhas'))
    assert len(li) == 8 and [f[0] for f in li.fields[1:]] == ['Frota', 'Data']
    assert 'SIRGAS_2000_UTM_Zone_23S' in z.read('10233_torta_Amostras.prj').decode()
```

- [x] **Passo 2: rodar e ver falhar** (`ImportError: cannot import name 'exportar_shapefiles'`).

- [x] **Passo 3: implementar** em `paralelismo/analise.py` (import `io`, `zipfile` e `shapefile` no topo):

```python
PRJ_31983 = ('PROJCS["SIRGAS_2000_UTM_Zone_23S",GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",'
             'SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],'
             'UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
             'PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",10000000.0],'
             'PARAMETER["Central_Meridian",-45.0],PARAMETER["Scale_Factor",0.9996],'
             'PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]')


def exportar_shapefiles(resultado, linhas, prefixo):
    """Zip com <prefixo>_Amostras (segmento amostra -> vizinha) e <prefixo>_Linhas (linhas antes do limpar)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        def gravar(nome, campos, linhas_geo, registros):
            shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
            w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYLINE, encoding='utf-8')
            for nome_campo, tipo, tam, dec in campos:
                w.field(nome_campo, tipo, size=tam, decimal=dec)
            for coords, reg in zip(linhas_geo, registros):
                w.line([coords])
                w.record(*reg)
            w.close()
            for ext, b in (('shp', shp), ('shx', shx), ('dbf', dbf)):
                z.writestr(f'{nome}.{ext}', b.getvalue())
            z.writestr(f'{nome}.prj', PRJ_31983)
            z.writestr(f'{nome}.cpg', 'UTF-8')

        pts = resultado['pontos']
        gravar(f'{prefixo}_Amostras', [('Talhao', 'N', 4, 0), ('Aderencia', 'C', 10, 0),
                                       ('Frota', 'C', 40, 0), ('Espac', 'N', 8, 3)],
               [[(p[0], p[1]), (p[2], p[3])] for p in pts],
               [(p[6] if p[6] is not None else -1, p[5], p[7], p[4]) for p in pts])
        gravar(f'{prefixo}_Linhas', [('Frota', 'C', 40, 0), ('Data', 'C', 10, 0)],
               [l['coords'] for l in linhas], [(l['frota'], l['data']) for l in linhas])
    return buf.getvalue()
```

- [x] **Passo 4: rodar e ver passar.** `pytest tests/paralelismo -v`.

- [x] **Passo 5: commit.** `git commit -am "Paralelismo P0.4: shapefiles de amostras e linhas"` (com `git add` dos arquivos novos, se houver).

### Tarefa P0.5: regressão com dados reais e publicação para o navegador (camada 3)

**Interfaces:** consome tudo da P0; produz `mapas/publicar.py` publicando `paralelismo/*.py` em `app/py/paralelismo/`.

- [x] **Passo 1: marcador.** Em `pytest.ini`, acrescentar à lista `markers` a linha `dados_reais: lê pastas reais fora do repositório (rode com -m dados_reais)` e trocar `addopts` para `-m "not banco and not dados_reais"`.

- [x] **Passo 2: confirmar o número de referência no `base-op`.** Localizar com o usuário as pastas `10233Rev0` (torta, `.jdl`) e `10966Rev0` (cana, GS3) que deram os números da spec. Rodar o `base-op` em modo trator para cada uma e conferir que dá **2.506 amostras / 77,85%** e **30.395 / 88,86%** (o total do PLL, com as amostras fora de talhão). Se não der, parar e falar com o usuário antes de seguir.

- [x] **Passo 3: escrever o teste** — `tests/paralelismo/test_regressao.py`:

```python
"""Regressão contra o resultado do base-op (spec §8). Rode com:
PARALELISMO_10233=<pasta 10233Rev0> PARALELISMO_10966=<pasta com as sessões GS3 da 10966Rev0> pytest -m dados_reais"""
import collections
import os
import re
from pathlib import Path

import pytest

from paralelismo.analise import analisar_fazenda, linhas_do_grupo, para_utm
from paralelismo.gs3 import ler_gs3, ler_sessao
from paralelismo.jdl import ler_jdl

pytestmark = pytest.mark.dados_reais
RE_SERIE = re.compile(rb'BM\d{4}[A-Z]\d{6}')
RE_DATA = re.compile(r'^(\d{4})_(\d{2})_(\d{2})_')


def _linhas(grupos):
    saida = []
    for frota, itens in grupos.items():
        pontos = [p for _, pts in itens for p in pts]
        data = collections.Counter(d for d, pts in itens for _ in pts).most_common(1)[0][0]
        saida += [{'frota': frota, 'data': data, 'coords': [list(c) for c in g.coords]}
                  for g in linhas_do_grupo(pontos)]
    return saida


def _pasta(var):
    p = os.environ.get(var)
    if not p or not Path(p).is_dir():
        pytest.skip(f'{var} não aponta para uma pasta')
    return Path(p)


def test_regressao_10233_jdl():
    grupos = collections.defaultdict(list)
    for jdl in sorted(_pasta('PARALELISMO_10233').rglob('*.jdl')):
        pontos, _ = ler_jdl(str(jdl))
        if not pontos:
            continue
        series = RE_SERIE.findall(jdl.read_bytes())
        frota = collections.Counter(series).most_common(1)[0][0].decode() if series else jdl.parent.name
        m = RE_DATA.match(jdl.name)
        grupos[frota].append((f'{m[1]}-{m[2]}-{m[3]}' if m else '', para_utm(pontos)))
    r = analisar_fazenda(_linhas(grupos), {})
    assert r['pll_total'] == 2506
    assert round(100 * r['pll_aderentes'] / r['pll_total'], 2) == 77.85


def test_regressao_10966_gs3():
    grupos = collections.defaultdict(list)
    vistos = set()
    for fdl in sorted(_pasta('PARALELISMO_10966').rglob('*.fdl')):
        if fdl.name in vistos:
            continue
        vistos.add(fdl.name)
        pontos, _ = ler_gs3(str(fdl))
        if pontos:
            grupos['gs3'].append((ler_sessao(str(fdl))['inicio'][:10], para_utm(pontos)))
    r = analisar_fazenda(_linhas(grupos), {})
    assert r['pll_total'] == 30395
    assert round(100 * r['pll_aderentes'] / r['pll_total'], 2) == 88.86
```

  Atenção ao agrupamento: o `base-op` agrupa a cana por **frota da pasta** (`mapa_frotas`), e o LSFP só liga pontos da mesma frota. Se o 10966 não bater com tudo em `'gs3'`, agrupe pela frota do nome da pasta, como o `base-op` faz, e registre isso no `LEIAME.md` (é o que a conferência da P2 vai fazer: frota escolhida por pasta GS3).

- [x] **Passo 4: rodar.** `PARALELISMO_10233=... PARALELISMO_10966=... pytest -m dados_reais -v` → 2 passed. Sem as variáveis, `pytest` normal continua verde (os dois pulam por estarem fora do `addopts`).

- [x] **Passo 5: publicar para o navegador.** Em `mapas/publicar.py`, acrescentar a `ARQUIVOS` (mesma lista, para o workflow do Pages já existente copiar): `'paralelismo/__init__.py', 'paralelismo/jdl.py', 'paralelismo/gs3.py', 'paralelismo/pipeline.py', 'paralelismo/analise.py'`. Em `.github/workflows/pages.yml`, acrescentar `'paralelismo/**'` em `paths`. Atualizar a docstring de `publicar.py` ("fonte única: mapas/ e paralelismo/"). Conferir: `python mapas/publicar.py /tmp/py_teste && ls /tmp/py_teste/paralelismo` mostra os 5 arquivos; `pytest tests/mapas/test_publicar.py -v` passa (ajustar o teste se ele fixar a lista).

- [x] **Passo 6: prova no Pyodide** (rápida, sem tela ainda): uma página de rascunho no scratchpad que carrega Pyodide 0.27.7, `loadPackage(['numpy','shapely','pyproj','micropip'])`, `micropip.install('pyshp')`, grava os 5 arquivos e roda `analisar_fazenda` com as linhas sintéticas de `test_analise.py` → `pll_total` 532. Abrir no Edge via Playwright e ler o resultado no console. Não commitar a página.

- [ ] **Passo 7: fechamento da P0.** `pytest -v` verde; `verification-before-completion`; `requesting-code-review` do diff da P0; mostrar ao usuário; mesclar e enviar só com o ok dele. Commit: `Paralelismo P0.5: regressão 10233/10966 e publicação em app/py/paralelismo` (cite o hash do `base-op` copiado).

---

## P1 — Banco, níveis e declividade

**Camada:** 3 (SQL, RLS, segurança); U aplica a migration. Testes SQL podem ser escritos pela camada 2.

**Arquivos:**
- Criar: `supabase/migrations/20261030090000_paralelismo.sql`
- Modificar: `ingestao/base_fazendas.py` (campo `DECLIVIDAD` → `hub.talhoes.declividade`, 99 → nulo) e o teste dela em `tests/ingestao/`
- Modificar: `app/usuarios.js` (opção Solicitante também para `paralelismo`; cartão do Paralelismo) e `tests/app/usuarios_puro.test.js`
- Criar: `tests/paralelismo/test_banco.py` (marcador `banco`, com duas contas de teste: uma solicitante e uma editora)

**Conteúdo da migration:**
- `insert into hub.modulos (id, nome, ordem)` do `paralelismo`, escondido do menu lateral (mesmo jeito do `corretivos`); item no parâmetro `ferramentas` (id `paralelismo`, URL `app/paralelismo.html`).
- Trocar a regra "solicitante só no Drone" para `modulo_id in ('drone', 'paralelismo')` no `check` de `hub.usuario_modulos` e na função que salva os níveis (ver `20261023090000_niveis_por_modulo.sql`, linhas 14 e 71-72).
- `hub.talhoes.declividade numeric`.
- Tabelas da spec §5, com `paralelismo_analises.base_analise_id bigint` (decisão 3) e `fora_talhao int` + `pll_total int` + `pll_aderentes int`. Índices: `paralelismo_analises (operacao, cod_faz) where vigente`, `paralelismo_linhas (operacao, cod_faz)`, `paralelismo_arquivos (rodada_id)`.
- Funções (todas `security definer`, `set search_path = hub`):
  - `hub.paralelismo_nivel() -> text` (nível do usuário no módulo; admin = `'admin'`).
  - `hub.paralelismo_preparar_parte(p_rodada_id bigint default null) -> bigint` (decisão 2): solicitante ou editor; devolve o id.
  - `hub.paralelismo_ja_analisados(p_sha256 text[]) -> text[]`: os que já estão em rodada pendente ou publicada.
  - `hub.paralelismo_linhas_vigentes(p_operacao text, p_cod_faz int) -> jsonb` (`[{frota, data, coords}]` em 31983, só de rodadas publicadas) e `hub.paralelismo_talhoes_fazenda(p_cod_faz int) -> jsonb` (FeatureCollection 4326 com `talhao`, `area_ha`, `declividade`), leitura para quem processa.
  - `hub.paralelismo_enviar(p jsonb) -> bigint`: grava rodada pendente (id reservado), arquivos, linhas (`ST_SetSRID(ST_GeomFromGeoJSON(...), 31983)`), análises (`vigente = false`, `base_analise_id`) e talhões, numa transação. Recusa sha256 já registrado.
  - `hub.paralelismo_publicar(p_rodada_id bigint, p_recalculo jsonb default null) -> jsonb`: só editor; aplica o recálculo quando vier; se alguma fazenda mudou e não veio recálculo dela, `raise` com `recalculo_necessario:<lista>`; marca publicada e troca o `vigente`.
  - `hub.paralelismo_recusar(p_rodada_id bigint, p_motivo text)`: só editor, motivo obrigatório.
  - `hub.paralelismo_excluir(p_rodada_id bigint)`: só admin, regra da decisão 4, registra em `log_auditoria`, devolve a `release_tag` para a tela marcar "excluída".
- RLS conforme a spec §5 (análises/talhões de rodada publicada: `hub.pode_ver('paralelismo')`; pendentes: editor vê todas, solicitante só as suas; frotas: escrita só editor).

**Testes que precisam existir:** solicitante não publica nem recusa; leitura não vê pendente nem linhas; solicitante não vê pendente de outro; `ja_analisados` conta arquivo de rodada pendente; `enviar` com sha256 repetido falha sem gravar nada; `publicar` sem recálculo numa fazenda que mudou recusa; excluir rodada com outra mais nova na mesma fazenda recusa; excluir devolve a vigente anterior. Tudo apagando só as rodadas criadas pelo teste.

## P2 — Worker e funções puras da página

**Camada:** Worker = 3 (segurança); funções puras = 1 (`delegar.sh -a build`, só dados sintéticos).

**Arquivos:**
- Modificar: `worker/arquivos.js` — rota `POST /paralelismo/parte` (form: `rodada_id`, `nome`, `arquivo`). Chama `rpc/paralelismo_preparar_parte` com o token do usuário, cria/acha a release `paralelismo-r<id>` (`releaseDaTag`), sobe o asset, substitui se já existir com o mesmo nome (reenvio), devolve `{url, bytes}`. Recusa corpo > 95 MB. Rota `POST /paralelismo/excluida` (admin) que acrescenta "EXCLUÍDA em dd/mm/aaaa" à descrição da release.
- Criar: `app/paralelismo-puro.js` (sem DOM, exportado para `node --test` como o `drone-dados.js`) e `tests/app/paralelismo_puro.test.js`.

**Funções puras (interfaces para a P3–P5):**
- `parIdentificarJdl(nomeRel: string, bytes: Uint8Array) → {tipo:'jdl', serie|null, cod_faz|null, revisao|null, fazenda_monitor, data:'AAAA-MM-DD'|null}` — série mais frequente `BM\d{4}[A-Z]\d{6}`; fazenda pela pasta do log (`(\d{5})Rev(\d+)`, senão o primeiro número isolado de 5 dígitos entre 10000 e 99999); data pelo prefixo `AAAA_MM_DD_` do nome.
- `parIdentificarFdl(nomeRel, textoXml) → {tipo:'gs3', serie:null, cod_faz, revisao, fazenda_monitor, data, temFdd:boolean}` — `rcdsetup:Farm` ligado ao `FieldRef`, data de `LogTaskRegion timeStamp`.
- `parConferencia(arquivos, frotas, jaAnalisados) → [{trator (série ou pasta GS3), frota|null, operacao|null, fazendas:[cod], nArquivos, avisos:['serie_desconhecida'|'gs3_sem_documentacao'|'ja_analisados'], arquivos}]`. Pasta GS3 sem documentação = tem `.pth`/`.pvf` e nenhum `.fdl` com `.fdd`.
- `parFrotaSugeridaGs3(caminhoPasta) → string|null` (número na pasta).
- `parSepararJaAnalisados(arquivos, shaRegistrados) → {novos, repetidos}` (também repetidos dentro do próprio pen-drive).
- `parPartes(arquivos:[{caminho, bytes}], limite = 90*1024*1024) → [[...]]` — arquivo maior que o limite vai sozinho numa parte e gera aviso.
- `parMesclarComVigente(linhasVigentes, linhasNovas) → linhas` (sem duplicar a mesma linha quando a rodada já era a base).
- `parMesExecucao(contagemPorData) → 'AAAA-MM-01'|null` (mesma regra do Python).
- `parFormatarPct(n, total) → '77,85%'`, `parManifestoCsv(arquivos) → string` (`caminho;bytes;sha256;frota;fazenda`).

## P3 — Página "Processar" (fila, Pyodide, prévia, envio)

**Camada:** Web Worker e OPFS = 3; tela = 1 (`delegar.sh -a frontend`) a partir das funções da P2, com modo demonstração por `file://` como o Corretivos.

**Arquivos:** `app/paralelismo.html`, `app/paralelismo.css`, `app/paralelismo.js` (login, abas, aba Processar), `app/paralelismo-worker.js` (Pyodide), `tests/app/teste_paralelismo_tela.py`.

**Pontos que o detalhamento precisa cobrir:**
- `<input webkitdirectory>` → SHA-256 (`crypto.subtle.digest`) + cópia para o OPFS (`navigator.storage.getDirectory()`, pasta por item da fila) → aviso "pode retirar o pen-drive". Na abertura, sobras no OPFS de uma sessão anterior → oferecer descartar (`parOpfsSobras`).
- Conferência com cadastro de frota no lugar (editor) e escolha da frota de cada pasta GS3.
- Fila de um item por vez num único Worker; mensagens `{tipo:'progresso', fazenda, pct}`, `{tipo:'pronto', resultado}`, `{tipo:'erro', msg}`. O Worker carrega Pyodide 0.27.7, `numpy`, `shapely`, `pyproj`, `micropip` → `pyshp`, e os arquivos de `py/manifest.json`.
- Memória (spec §8): o JS manda um arquivo por vez; o Worker lê os pontos, junta por (frota, fazenda) e, ao terminar o grupo, chama `linhas_do_grupo` e descarta os pontos. Só as linhas ficam.
- Por (operação, fazenda): busca `paralelismo_linhas_vigentes` + `paralelismo_talhoes_fazenda`, roda `analisar_fazenda` com vigentes + novas, guarda o resultado e o `base_analise_id`.
- Prévia: aderência por fazenda, talhão e frota, comparada à vigente; avisos (arquivo pulado, fora de talhão > 5%, frota sem trabalho, `insuficiente`).
- Enviar: `parPartes` → zip com fflate (versão fixada) mantendo os caminhos → `POST /paralelismo/parte` por parte, mais `manifesto.csv` e o zip de `exportar_shapefiles` de cada fazenda → `paralelismo_enviar`. Falha em qualquer parte = nada gravado, botão "Tentar de novo" com o mesmo id. Depois do sucesso, apagar a cópia do OPFS.
- Erros da spec §10 com os textos dela.
- Conferir os tempos da spec (16 s na torta pequena, ~2,3 min na 10966) e o aviso de frota sem trabalho no caso 55805/10010.

## P4 — Pendentes, Rodadas e Frotas

**Camada:** 1 (`-a frontend`) para as telas; 3 para o recálculo na publicação.

- **Pendentes** (contador na aba): mesma prévia (lida do banco), quem processou, avisos; Publicar → se o RPC responder `recalculo_necessario`, rodar no Worker o recálculo das fazendas listadas (vigentes atuais + linhas da rodada), mostrar o resultado novo e confirmar com `p_recalculo`; Recusar → motivo obrigatório. Solicitante vê só as próprias, sem botões.
- **Rodadas:** data, quem processou e validou, situação, tratores, fazendas, link dos brutos; Excluir (admin) com confirmação → `paralelismo_excluir` + `POST /paralelismo/excluida`.
- **Frotas:** tabela editável (editor), leitura para os outros.
- Testes de tela por nível (leitura, solicitante, editor, admin) com o modo demonstração.

## P5 — Painel e Relatório

**Camada:** 1 (`-a frontend`) após `frontend-design`; dados e consultas = 3. Seguir a ordem de front-end do `CLAUDE.md` global (web-builder → frontend-design → Subframe → delegar → impeccable).

- Ler só análises vigentes de rodadas publicadas, com `hub.talhoes` (área, declividade) e `hub.talhao_geom`.
- Abas da spec §7: Resumo (KPIs, aderência por faixa de declividade, por mês, tabela de fazendas), Talhões (dispersão aderência × declividade, tabela com busca e "amostra insuficiente", mapa MapLibre pintado pela aderência), Fazenda (talhões e frotas), Frentes e frotas, Relatório (meses por caixa de seleção, padrão os 3 últimos; uma seção por operação e mês; CSS de impressão).
- Referência visual e de conteúdo: `I:\Projetos\PARALELISMO\PEDRA\BI_Paralelismo.html` e `gerar_dash.py` (abrir só os trechos necessários). Usar a skill `dataviz` nos gráficos.
- Funções de agregação do painel vão para `app/paralelismo-puro.js`, com teste `node --test`.

## P6 — Histórico, ponta a ponta e entrega

**Camada:** histórico = 3 (dado real); E2E = 3; manual = 2.

- `migracao/paralelismo_historico.py` (spec §9): `frotas_maquinas.csv` → `paralelismo_frotas`; rodada "histórico até 26/10/2026" publicada, sem brutos; análises e talhões de `Paralelismo8.xlsx` (`agrocad_fme` nas 16 fazendas antigas de cana, `trator` nas demais; mês de `meses_fazendas.csv` nas antigas); linhas dos `*_Linhas.shp` da pasta de resultado mais recente de cada fazenda `trator`; `paralelismo_arquivos` com o SHA-256 dos brutos de `ORGANIZAR-02`. Modo `--simular` que só conta, antes de gravar. Conferir com o usuário que o painel bate com o `BI_Paralelismo.html` atual.
- E2E (Playwright, spec §11): solicitante coloca duas pastas de amostra na fila e envia; painel ainda não mostra; editora publica uma e recusa a outra; painel mostra só a publicada; o teste exclui as rodadas que criou.
- Manual curto da tela (onde está, níveis, fluxo de um pen-drive) e cadastro em Ferramentas conferido.
- Fechamento: `verification-before-completion`, `requesting-code-review` do conjunto, ok do usuário, merge e deploy.
