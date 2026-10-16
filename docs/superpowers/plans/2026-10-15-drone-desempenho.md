# Drone: geração sem depender da rede + conferência do envio — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A prévia do Drone deixa de depender da pasta de rede, o Hub avisa quando o servidor Geo para, e o envio de infestação mostra um resumo (e a prévia um alerta de bom senso) antes de alguém publicar errado.

**Architecture:** A rotina diária já grava `hub.talhao_geom`; passa a gravar também a geometria exata (31983) e a AREA_PROD, e o agente lê dali (pasta de rede só como reserva). O agente grava um resumo e uma assinatura de cada envio em `hub.drone_envios`. O app lê a saúde do servidor por uma função e mostra faixa + aviso no sininho calculado na hora.

**Tech Stack:** Python (geopandas/shapely, pytest), Supabase/PostGIS (schema `hub`), JS do app (`app/drone.js`, `app/index.html`, MapLibre), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-15-drone-desempenho-design.md`

## Global Constraints

- Repositório `C:\Users\lmalerbo\Documents\hub-geotech-colheita` (branch local `colheita`); publicar com `git fetch && git rebase origin/main && git push origin colheita:main`. A sessão do Drone também publica em `app/drone.js` — sempre rebase antes de começar cada tarefa de app.
- Tudo de geometria em EPSG:31983 dentro do agente; GeoJSON do mapa em 4326.
- Testes: `python -m pytest tests/drone -q` (todos passando antes de cada commit). Testes que gravam no banco real salvam e restauram; nunca apagam dado real.
- Textos para o usuário em pt-BR. Nunca imprimir chave/hash de senha.
- Depois de publicar código do agente, o servidor precisa de `git pull` **e** reiniciar o processo do agente (ele mantém o código antigo na memória).
- Commits terminam com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Fazenda que entrou na Base hoje e ainda não está em `talhao_geom`** (rotina das 07:00 não rodou) — o agente cai para a pasta de rede e a prévia avisa; se a pasta também falhar, o erro é o de hoje (claro, em pt-BR). Teste na Task 3.
2. **Talhão com AREA_PROD vazia na Base** — continua contando como 0 e gerando o alerta "sem AREA_PROD" igual ao caminho pelo arquivo. Teste na Task 3.
3. **Envio de infestação só com pontos ou linhas** (sem área) — o resumo conta as manchas e mostra 0 ha, sem erro. Teste na Task 4.
4. **Primeiro envio da fazenda** (sem anterior para comparar) — sem aviso de repetido. Teste na Task 4.
5. **Relógio do navegador diferente do servidor** — a faixa usa a diferença calculada pelo banco (`agora - ultimo_ciclo` em segundos), não o relógio do navegador. Task 1 e 6.

---

### Task 1: Banco — geometria exata, saúde, resumo do envio e manchas no mapa

**Files:**
- Create: `supabase/migrations/20261016090000_drone_desempenho.sql`

**Interfaces (Produces):**
- `hub.talhao_geom.geom_proj geometry(MultiPolygon, 31983)`, `hub.talhao_geom.area_prod numeric`
- `hub.drone_talhoes_fazenda(p_cod_faz int) returns table (talhao int, area_prod numeric, wkt text)` — só service_role
- `hub.drone_saude() returns jsonb` → `{"agente_seg": int|null, "rotina_horas": numeric|null}` — authenticated
- `hub.drone_infestacao_mapa(p_infestacao_id bigint) returns jsonb` (FeatureCollection 4326) — authenticated
- `hub.drone_envios.resumo jsonb`, `hub.drone_envios.conteudo_hash text`
- `hub.drone_concluir_envio(p_id bigint, p_status text, p_erro text, p_resumo jsonb default null, p_hash text default null)`
- `hub.drone_parametros`: `alerta_razao_catacao = '5'`, `base_talhoes_arquivo = ''`

- [ ] **Step 1: Escrever a migração**

```sql
-- Drone: geração sem depender da pasta de rede, saúde do servidor Geo,
-- resumo/assinatura dos envios e manchas no mapa. Ver
-- docs/superpowers/specs/2026-10-15-drone-desempenho-design.md.
begin;

-- Geometria exata do talhão (a do mapa, em 4326, é simplificada 0,5 m) e AREA_PROD,
-- gravadas pela rotina diária (ingestao/talhao_geom.py).
alter table hub.talhao_geom add column if not exists geom_proj extensions.geometry(MultiPolygon, 31983);
alter table hub.talhao_geom add column if not exists area_prod numeric;

create or replace function hub.drone_talhoes_fazenda(p_cod_faz int)
returns table (talhao int, area_prod numeric, wkt text)
language sql stable security definer set search_path = hub, extensions as $$
  select talhao_num, area_prod, ST_AsText(geom_proj)
    from hub.talhao_geom where cod_faz = p_cod_faz and geom_proj is not null order by talhao_num;
$$;
revoke all on function hub.drone_talhoes_fazenda(int) from public, anon, authenticated;
grant execute on function hub.drone_talhoes_fazenda(int) to service_role;

-- Saúde do servidor Geo: segundos desde o último ciclo do agente e horas desde a
-- última rotina diária com sucesso (calculado no banco: o relógio do navegador não entra).
create or replace function hub.drone_saude()
returns jsonb language sql stable security definer set search_path = hub as $$
  select jsonb_build_object(
    'agente_seg', (select extract(epoch from now() - nullif(valor, '')::timestamptz)::int
                     from hub.drone_parametros where chave = 'agente_ultimo_ciclo'),
    'rotina_horas', (select round(extract(epoch from now() - max(finalizado_em)) / 3600, 1)
                       from hub.execucoes_ingestao where fonte = 'base_fazendas' and status = 'ok'));
$$;
revoke all on function hub.drone_saude() from public, anon;
grant execute on function hub.drone_saude() to authenticated, service_role;

-- Manchas de um levantamento, para o mapa.
create or replace function hub.drone_infestacao_mapa(p_infestacao_id bigint)
returns jsonb language sql stable security definer set search_path = hub, extensions as $$
  select jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(
           jsonb_build_object('type', 'Feature', 'geometry', ST_AsGeoJSON(ST_Transform(geom, 4326), 6)::jsonb,
                              'properties', jsonb_build_object('camada', 'mancha'))), '[]'::jsonb))
    from hub.drone_infestacao_feicoes where infestacao_id = p_infestacao_id;
$$;
revoke all on function hub.drone_infestacao_mapa(bigint) from public, anon;
grant execute on function hub.drone_infestacao_mapa(bigint) to authenticated, service_role;

-- Resumo e assinatura do conteúdo de cada envio (gravados pelo agente).
alter table hub.drone_envios add column if not exists resumo jsonb;
alter table hub.drone_envios add column if not exists conteudo_hash text;

drop function if exists hub.drone_concluir_envio(bigint, text, text);
create function hub.drone_concluir_envio(p_id bigint, p_status text, p_erro text,
                                         p_resumo jsonb default null, p_hash text default null)
returns void language sql security definer set search_path = hub as $$
  update hub.drone_envios
     set status = p_status, erro = left(p_erro, 1000), processado_em = now(),
         resumo = p_resumo, conteudo_hash = p_hash
   where id = p_id;
$$;
revoke all on function hub.drone_concluir_envio(bigint, text, text, jsonb, text) from public, anon, authenticated;
grant execute on function hub.drone_concluir_envio(bigint, text, text, jsonb, text) to service_role;

insert into hub.drone_parametros (chave, valor, descricao) values
  ('alerta_razao_catacao', '5', 'Catação: alerta quando a aplicação passa de N vezes a área infestada'),
  ('base_talhoes_arquivo', '', 'Arquivo da Base de Talhões gravado em hub.talhao_geom (rotina diária)')
on conflict (chave) do nothing;

commit;
```

- [ ] **Step 2: Validar a sintaxe** — `python <scratchpad>/validar_sql.py supabase/migrations/20261016090000_drone_desempenho.sql` (pglast; o regex de plpgsql não se aplica, só SQL). Expected: `SQL ok`.

- [ ] **Step 3: Commit**
```bash
git add supabase/migrations/20261016090000_drone_desempenho.sql
git commit -m "Drone: banco com geometria exata dos talhoes, saude do servidor e resumo dos envios"
```

---

### Task 2: Rotina diária grava geometria exata, AREA_PROD e o nome da Base

**Files:**
- Modify: `ingestao/talhao_geom.py`
- Modify: `tests/drone/test_talhao_geom.py`

**Interfaces:**
- Consumes: colunas da Task 1.
- Produces: cada linha de `linhas(gdf)` ganha `geom_proj` (`'SRID=31983;MULTIPOLYGON(...)'`, 2 casas, sem simplificar) e `area_prod` (float ou `None`); `main()` grava `drone_parametros.base_talhoes_arquivo = <nome do .shp>`.

- [ ] **Step 1: Testes (falham)** — acrescentar em `tests/drone/test_talhao_geom.py`:

```python
def test_grava_geometria_exata_em_31983_e_area_prod():
    g = _gdf(SECAO=['10156'], TALHAO=[1], AREA_PROD=[9.5],
             geometry=[box(200000.123, 7550000, 200100, 7550100)])
    l = linhas(g)[0]
    assert l['geom_proj'].startswith('SRID=31983;MULTIPOLYGON')
    assert '200000.12' in l['geom_proj']          # sem simplificar, 2 casas
    assert l['area_prod'] == pytest.approx(9.5)


def test_area_prod_vazia_vira_none():
    g = _gdf(SECAO=['10156'], TALHAO=[1], AREA_PROD=[None], geometry=[box(200000, 7550000, 200100, 7550100)])
    assert linhas(g)[0]['area_prod'] is None
```
(Os testes antigos continuam sem a coluna AREA_PROD: `linhas` precisa aceitar gdf sem ela.)

- [ ] **Step 2: Rodar e ver falhar** — `python -m pytest tests/drone/test_talhao_geom.py -q` → KeyError `geom_proj`.

- [ ] **Step 3: Implementar** — em `ingestao/talhao_geom.py`:
  - docstring: acrescentar "Grava também a geometria exata em SIRGAS/UTM 23S (geom_proj) e a AREA_PROD, que o agente do Drone usa para gerar sem ler a pasta de rede."
  - em `linhas`, dentro do laço, trocar o corpo por:
```python
        exata = so_poligonos(make_valid(unary_union(list(g.geometry))))
        geom = so_poligonos(make_valid(exata.simplify(0.5)))
        if geom.is_empty:
            continue
        em_graus = gpd.GeoSeries([geom], crs=31983).to_crs(4326).iloc[0]
        area_prod = None
        if 'AREA_PROD' in g.columns:
            valores = pd.to_numeric(g['AREA_PROD'], errors='coerce').dropna()
            area_prod = float(valores.iloc[0]) if len(valores) else None
        out.append({'cod_faz': int(cod), 'talhao_num': int(tal),
                    'geom': 'SRID=4326;' + shapely_wkt.dumps(em_graus, rounding_precision=7),
                    'area_ha': round(geom.area / 1e4, 4),
                    'geom_proj': 'SRID=31983;' + shapely_wkt.dumps(exata, rounding_precision=2),
                    'area_prod': area_prod})
```
  - em `main`, ler a coluna: `pyogrio.read_dataframe(caminho, columns=['SECAO', 'TALHAO', 'AREA_PROD'])`; trocar `LOTE = 200` por `LOTE = 100` (geometria exata pesa mais por linha); depois do `talhao_geom_limpar`, gravar o nome:
```python
        hub.atualizar('drone_parametros', {'chave': 'eq.base_talhoes_arquivo'},
                      {'valor': caminho.name, 'atualizado_em': agora_iso()})
```

- [ ] **Step 4: Rodar e ver passar** — `python -m pytest tests/drone -q` → tudo passando.

- [ ] **Step 5: Commit**
```bash
git add ingestao/talhao_geom.py tests/drone/test_talhao_geom.py
git commit -m "Drone: rotina diaria grava a geometria exata e a AREA_PROD dos talhoes no banco"
```

---

### Task 3: Agente gera com os talhões do banco (pasta de rede só como reserva)

**Files:**
- Modify: `drone/banco.py` (métodos novos), `drone/gerador.py`, `drone/agente.py`
- Modify: `tests/drone/test_gerador.py`

**Interfaces:**
- Consumes: `hub.drone_talhoes_fazenda`, `drone_parametros.base_talhoes_arquivo` (Tasks 1–2).
- Produces:
  - `DroneBanco.talhoes_fazenda(cod_faz) -> GeoDataFrame` com colunas `TALHAO:int`, `AREA_PROD:float (NaN se vazia)`, `geometry` em 31983; vazio se a fazenda não está no banco.
  - `DroneBanco.base_talhoes() -> tuple[date, Path] | None` (data tirada do nome `Talhoes_da_Pedra_DD_MM_AAAA_fme.shp`).
  - `gerador.processar(...)`: usa `banco.talhoes_fazenda(cod)`; se vazio, lê o arquivo (o `base` recebido, ou `arquivo_mais_recente` da config se o caminho não existir) e acrescenta o alerta `'Talhões lidos da pasta de rede: a fazenda ainda não estava na cópia do banco.'`.

- [ ] **Step 1: Testes (falham)** — em `tests/drone/test_gerador.py`, no `BancoFalso.__init__` acrescentar o parâmetro `talhoes_banco=None` e `self.talhoes_banco = talhoes_banco`, e o método:
```python
    def talhoes_fazenda(self, cod):
        if self.talhoes_banco is not None:
            return self.talhoes_banco
        return gpd.GeoDataFrame({'TALHAO': [], 'AREA_PROD': []}, geometry=[], crs=31983)
```
e os testes:
```python
def test_usa_talhoes_do_banco_sem_ler_a_pasta(tmp_path):
    do_banco = gpd.GeoDataFrame({'TALHAO': [1, 2], 'AREA_PROD': [1.0, float('nan')]},
                                geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)], crs=31983)
    sem_arquivo = (datetime.date(2026, 10, 1), tmp_path / 'nao_existe' / 'Talhoes_da_Pedra_01_10_2026_fme.shp')
    r = processar({'id': 20, 'solicitacao_id': 9, 'infestacao_id': None}, BancoFalso(talhoes_banco=do_banco),
                  sem_arquivo, tmp_path / 'w', datetime.date(2026, 10, 2))
    assert r['status'] == 'pronta'
    assert not any('pasta de rede' in a for a in r['alertas'])
    assert any('sem AREA_PROD' in a for a in r['alertas'])          # AREA_PROD vazia continua avisada


def test_fazenda_fora_do_banco_le_o_arquivo_e_avisa(base, tmp_path):
    r = processar({'id': 21, 'solicitacao_id': 9, 'infestacao_id': None}, BancoFalso(), base, tmp_path / 'w',
                  datetime.date(2026, 10, 2))
    assert r['status'] == 'pronta'
    assert any('pasta de rede' in a for a in r['alertas'])
```

- [ ] **Step 2: Rodar e ver falhar** — `python -m pytest tests/drone/test_gerador.py -q`.

- [ ] **Step 3: Implementar**

`drone/banco.py` — imports `import geopandas as gpd`, `from shapely.validation import make_valid`, `from drone.config import CRS_TRABALHO, RAIZ` e `from drone.base_talhoes import DATA_NO_NOME`; métodos na seção de leitura:
```python
    def talhoes_fazenda(self, cod_faz):
        """Talhões da fazenda pela cópia diária da Base no banco (vazio se a fazenda não está lá)."""
        linhas = self.rpc('drone_talhoes_fazenda', {'p_cod_faz': cod_faz}) or []
        return gpd.GeoDataFrame(
            {'TALHAO': [int(l['talhao']) for l in linhas],
             'AREA_PROD': [float(l['area_prod']) if l['area_prod'] is not None else float('nan') for l in linhas]},
            geometry=[make_valid(shapely_wkt.loads(l['wkt'])) for l in linhas], crs=CRS_TRABALHO)

    def base_talhoes(self):
        """(data, Path(nome)) da Base gravada no banco pela rotina diária, ou None."""
        nome = self.parametros().get('base_talhoes_arquivo') or ''
        m = DATA_NO_NOME.search(nome)
        if not m:
            return None
        dia, mes, ano = map(int, m.groups())
        return datetime.date(ano, mes, dia), Path(nome)
```

`drone/gerador.py` — trocar `talhoes = talhoes_da_fazenda(Path(arquivo_base), cod)` por:
```python
    talhoes = banco.talhoes_fazenda(cod)
    da_rede = talhoes.empty
    if da_rede:   # fazenda ainda não está na cópia do banco (rotina diária não rodou): lê a pasta
        caminho = Path(arquivo_base)
        if not caminho.exists():
            c = cfg()
            caminho = arquivo_mais_recente(c['base_talhoes_pasta'], c['base_talhoes_padrao'])[1]
        talhoes = talhoes_da_fazenda(caminho, cod)
```
com imports `from drone.base_talhoes import arquivo_mais_recente, talhoes_da_fazenda` e `from drone.config import cfg`; e, logo depois de `extras, cob, fora = [], None, False`:
```python
    if da_rede:
        extras.append('Talhões lidos da pasta de rede: a fazenda ainda não estava na cópia do banco.')
```

`drone/agente.py` — em `gerar_uma`, trocar a linha do `base = ...` por:
```python
        base = banco.base_talhoes() or arquivo_mais_recente(c['base_talhoes_pasta'], c['base_talhoes_padrao'])
```

- [ ] **Step 4: Rodar e ver passar** — `python -m pytest tests/drone -q`.

- [ ] **Step 5: Commit**
```bash
git add drone/banco.py drone/gerador.py drone/agente.py tests/drone/test_gerador.py
git commit -m "Drone: agente gera com os talhoes do banco; pasta de rede so como reserva"
```

---

### Task 4: Resumo e assinatura do envio de infestação

**Files:**
- Modify: `drone/geometria.py` (função `resumo_infestacao`)
- Modify: `drone/envios.py` (`processar_envio` devolve `(mensagem, resumo, assinatura)`)
- Modify: `drone/banco.py` (`concluir_envio` com resumo/hash; `hash_anterior`)
- Modify: `drone/agente.py` (`processar_um_envio`)
- Modify: `tests/drone/test_geometria.py`, `tests/drone/test_envios.py`

**Interfaces:**
- Produces:
  - `resumo_infestacao(geoms: list, talhoes: GeoDataFrame) -> dict` = `{'manchas': int, 'area_ha': float, 'por_talhao': [{'talhao': int, 'manchas': int, 'ha': float}], 'fora_ha': float}`
  - `processar_envio(envio, banco, pasta) -> tuple[str, dict | None, str]`; para infestação o resumo ganha `'repetido_de': <id do envio anterior> | None`.
  - `DroneBanco.concluir_envio(id_, status, erro=None, resumo=None, assinatura=None)`; `DroneBanco.hash_anterior(cod_faz, tipo, antes_de_id) -> tuple[int, str] | None`.

- [ ] **Step 1: Testes (falham)**

`tests/drone/test_geometria.py` (import `from drone.geometria import recortar, resumo_infestacao, uniao_buffers` e `from shapely.geometry import LineString, MultiPolygon, Point, box`):
```python
def test_resumo_infestacao_conta_manchas_por_talhao_e_fora(talhoes):
    manchas = MultiPolygon([box(10, 10, 20, 20), box(150, 10, 160, 20)])   # uma em cada talhão
    fora = box(300, 0, 310, 10)
    r = resumo_infestacao([manchas, fora], talhoes)
    assert r['manchas'] == 3
    assert r['area_ha'] == pytest.approx(0.03)
    assert r['por_talhao'] == [{'talhao': 1, 'manchas': 1, 'ha': 0.01}, {'talhao': 2, 'manchas': 1, 'ha': 0.01}]
    assert r['fora_ha'] == pytest.approx(0.01)


def test_resumo_infestacao_so_pontos_nao_quebra(talhoes):
    r = resumo_infestacao([Point(10, 10), Point(150, 10)], talhoes)
    assert r['manchas'] == 2 and r['area_ha'] == 0 and r['por_talhao'] == []
```

`tests/drone/test_envios.py` — no `_Banco`, acrescentar:
```python
    def __init__(self, pasta_origem, anterior=None):
        self.origem, self.gravados, self.anterior = pasta_origem, [], anterior

    def talhoes_fazenda(self, cod):
        return gpd.GeoDataFrame({'TALHAO': [1], 'AREA_PROD': [1.0]}, geometry=[box(0, 0, 1000, 1000)], crs=31983)

    def hash_anterior(self, cod, tipo, antes_de):
        return self.anterior
```
(substituindo o `__init__` atual) e os testes:
```python
def test_infestacao_devolve_resumo_e_assinatura(tmp_path):
    o = tmp_path / 'o'
    a = _shp(o, 'Daninhas.shp', [MultiPolygon([box(10, 10, 20, 20), box(100, 100, 110, 110)])])
    msg, resumo, assinatura = processar_envio(_envio(tmp_path, 'infestacao', _partes(a), sol=3), _Banco(o), tmp_path / 'w')
    assert resumo['manchas'] == 2 and resumo['por_talhao'][0]['talhao'] == 1
    assert resumo['repetido_de'] is None and len(assinatura) == 64


def test_mesmo_arquivo_do_envio_anterior_e_marcado(tmp_path):
    o = tmp_path / 'o'
    a = _shp(o, 'Daninhas.shp', [box(10, 10, 20, 20)])
    _, _, assinatura = processar_envio(_envio(tmp_path, 'infestacao', _partes(a), sol=3), _Banco(o), tmp_path / 'w1')
    _, resumo, _ = processar_envio(_envio(tmp_path, 'infestacao', _partes(a), sol=3),
                                   _Banco(o, anterior=(4, assinatura)), tmp_path / 'w2')
    assert resumo['repetido_de'] == 4
```
e trocar `MultiPolygon` no import de `shapely.geometry` do arquivo.

- [ ] **Step 2: Rodar e ver falhar** — `python -m pytest tests/drone -q`.

- [ ] **Step 3: Implementar**

`drone/geometria.py` (depois de `blocos_catacao`):
```python
def resumo_infestacao(geoms: list, talhoes) -> dict:
    """Manchas (partes separadas, não registros), área infestada, por talhão e fora dos talhões."""
    manchas = [p for g in geoms if not g.is_empty for p in _partes(make_valid(g))]
    total = unary_union([m for m in manchas if m.area > 0]) if manchas else Polygon()
    por_talhao = []
    for _, t in talhoes.iterrows():
        dentro = total.intersection(t.geometry).area
        if dentro >= AREA_MINIMA_M2:
            por_talhao.append({'talhao': int(t['TALHAO']), 'manchas': sum(1 for m in manchas if m.intersects(t.geometry)),
                               'ha': round(dentro / 1e4, 2)})
    uniao_t = unary_union(list(talhoes.geometry)) if len(talhoes) else Polygon()
    return {'manchas': len(manchas), 'area_ha': round(total.area / 1e4, 2), 'por_talhao': por_talhao,
            'fora_ha': round(total.difference(uniao_t).area / 1e4, 2)}
```

`drone/envios.py` — imports `import hashlib` e `from drone.geometria import resumo_infestacao`; função nova:
```python
def assinatura(locais: list) -> str:
    """sha256 do conteúdo dos arquivos do envio (mesmo shape reenviado = mesma assinatura)."""
    h = hashlib.sha256()
    for p in sorted(locais, key=lambda p: Path(p).name):
        h.update(Path(p).name.encode())
        h.update(Path(p).read_bytes())
    return h.hexdigest()
```
em `processar_envio`, logo depois de `locais = [...]`: `sig = assinatura(locais)`; os `return` passam a ser:
  - obstáculos: `return ('obstáculos: ' + ..., None, sig)`
  - infestação:
```python
    if tipo == 'infestacao':
        banco.gravar_infestacao(envio['solicitacao_id'], None, nomes, geoms, usuario=usuario, envio_id=envio['id'])
        resumo = resumo_infestacao(geoms, banco.talhoes_fazenda(cod))
        anterior = banco.hash_anterior(cod, tipo, envio['id'])
        resumo['repetido_de'] = anterior[0] if anterior and anterior[1] == sig else None
        return f'infestação: {resumo["manchas"]} manchas, {resumo["area_ha"]} ha', resumo, sig
```
  - ajuste: `return (f'shape de ajuste: {len(geoms)} feições', None, sig)`

`drone/banco.py`:
```python
    def concluir_envio(self, id_, status, erro=None, resumo=None, assinatura=None):
        self.rpc('drone_concluir_envio', {'p_id': id_, 'p_status': status, 'p_erro': erro,
                                          'p_resumo': resumo, 'p_hash': assinatura})

    def hash_anterior(self, cod_faz, tipo, antes_de_id):
        r = self.selecionar('drone_envios', 'id,conteudo_hash',
                            {'cod_faz': f'eq.{cod_faz}', 'tipo': f'eq.{tipo}', 'status': 'eq.ok',
                             'id': f'lt.{antes_de_id}', 'order': 'id.desc', 'limit': '1'})
        return (r[0]['id'], r[0]['conteudo_hash']) if r else None
```
(substituindo o `concluir_envio` atual.)

`drone/agente.py` — em `processar_um_envio`:
```python
        msg, resumo, sig = processar_envio(e, banco, PASTA_TRABALHO)
        _log('  ' + msg)
        banco.concluir_envio(e['id'], 'ok', resumo=resumo, assinatura=sig)
```

- [ ] **Step 4: Rodar e ver passar** — `python -m pytest tests/drone -q`.

- [ ] **Step 5: Commit**
```bash
git add drone/ tests/drone/
git commit -m "Drone: envio de infestacao grava resumo (manchas, ha, por talhao) e marca arquivo repetido"
```

---

### Task 5: Alerta de bom senso na prévia da Catação

**Files:**
- Modify: `drone/gerador.py`
- Modify: `tests/drone/test_gerador.py`

- [ ] **Step 1: Teste (falha)** — em `BancoFalso.parametros` acrescentar `'alerta_razao_catacao': '5'`; e:
```python
def test_catacao_muito_maior_que_a_infestacao_gera_alerta(base, tmp_path):
    # 3 manchas de 1 m² espalhadas a 15 m: o bloco (contorno + 5 m) passa de 5x a área infestada
    manchas = [box(10, 10, 11, 11), box(25, 10, 26, 11), box(40, 10, 41, 11)]
    r = processar({'id': 30, 'solicitacao_id': 9, 'infestacao_id': 1}, BancoFalso('catacao', infestacao=manchas),
                  base, tmp_path / 'w', datetime.date(2026, 10, 2))
    assert any('vezes a área infestada' in a for a in r['alertas'])


def test_catacao_proporcional_nao_gera_alerta(base, tmp_path):
    r = processar({'id': 31, 'solicitacao_id': 9, 'infestacao_id': 1},
                  BancoFalso('catacao', infestacao=[box(10, 10, 60, 60)]), base, tmp_path / 'w', datetime.date(2026, 10, 2))
    assert not any('vezes a área infestada' in a for a in r['alertas'])
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar** — no ramo da Catação de `processar`, depois de `recorte = recortar(...)`:
```python
        infestado_ha = unary_union([p for g in infest for p in getattr(g, 'geoms', [g]) if p.area > 0]).area / 1e4
        razao = float(params.get('alerta_razao_catacao', 5))
        if infestado_ha > 0 and recorte.aplicacao_ha > razao * infestado_ha:
            extras.append(f'Aplicação {recorte.aplicacao_ha / infestado_ha:.0f} vezes a área infestada '
                          f'({recorte.aplicacao_ha:.2f} ha para {infestado_ha:.2f} ha) — confira as manchas no mapa '
                          'antes de publicar.')
```

- [ ] **Step 4: Rodar e ver passar** — `python -m pytest tests/drone -q`.

- [ ] **Step 5: Commit**
```bash
git add drone/gerador.py tests/drone/test_gerador.py
git commit -m "Drone: alerta quando a Catacao passa de 5x a area infestada"
```

---

### Task 6: App — servidor parado, resumo do envio e manchas no mapa

**Files:**
- Modify: `app/drone.js`, `app/index.html`
- Modify: `tests/app/teste_drone_tela.py` (verificações novas)

**Interfaces:**
- Consumes: `drone_saude`, `drone_infestacao_mapa`, `drone_envios.resumo` (Task 1/4).

- [ ] **Step 1: Saúde no app** — em `app/index.html`, em `carregarDados`, acrescentar à lista do `Promise.all` (e à desestruturação) `sb.rpc('drone_saude').then(({data})=>data||{},()=>({}))` como `saude`, e guardar `SAUDE=saude;` (declarar `let SAUDE={};` junto de `let AVISOS=[];`). Em `avisosVisiveis()`, devolver também os avisos calculados:
```js
function avisosSaude(){
  const v=[];
  if(SAUDE.agente_seg>300&&(EU?.admin||EU?.perms?.drone))
    v.push({id:-1,modulo_id:'drone',titulo:'Servidor Geo sem resposta',lido:false,atualizado_em:new Date().toISOString(),
      texto:`O agente do Drone não roda há ${Math.round(SAUDE.agente_seg/60)} min: envios e prévias ficam parados até ele voltar.`});
  if(SAUDE.rotina_horas>26&&EU?.admin)
    v.push({id:-2,modulo_id:'drone',titulo:'Rotina diária atrasada',lido:false,atualizado_em:new Date().toISOString(),
      texto:`A última rotina diária com sucesso foi há ${Math.round(SAUDE.rotina_horas)} h (Base Fazendas, PLANAGRI, Conservação, ICOL).`});
  return v;
}
function avisosVisiveis(){return avisosSaude().concat(AVISOS.filter(a=>!EU||EU.admin||EU.perms[a.modulo_id]));}
```
e em `marcarLidos(ids)` filtrar `ids=ids.filter(i=>i>0);` na primeira linha; em `abrirAviso`, se `id<0`, só abrir a tela Drone (`trocar('drone',document.querySelector(\`.ni[onclick*="'drone'"]\`))`) e sair.

- [ ] **Step 2: Faixa na tela Drone** — em `app/drone.js`, na função que monta a tela (onde `DR.painel=await drRpc('drone_painel')`), buscar a saúde e mostrar a faixa no topo da tela Drone (elemento novo `<div id="dr-saude"></div>` como primeiro filho do container da tela):
```js
async function drSaude(){
  let s={};try{s=(await sb.rpc('drone_saude')).data||{};}catch(_){}
  const el=document.getElementById('dr-saude');if(!el)return;
  el.innerHTML=s.agente_seg>300
    ?`<div class="dr-err" style="margin-bottom:10px"><span class="ico">warning</span> O servidor Geo não responde há ${Math.round(s.agente_seg/60)} min — envios e prévias ficam parados até ele voltar. Avise o responsável pelo servidor.</div>`:'';
}
```
chamada junto do carregamento do painel e a cada 60 s enquanto a tela Drone estiver aberta (`setInterval(drSaude,60000)` guardado em `DR.timerSaude`, limpo ao sair da tela).

- [ ] **Step 3: Resumo do envio no cartão da Catação** — no select de `drRecarregarFazenda`, trocar `'id,tipo,status,erro,enviado_em'` por `'id,tipo,status,erro,enviado_em,resumo'`; e no cartão da Catação (perto do botão "Enviar infestação"), mostrar o último envio ok de infestação:
```js
function drResumoInfest(){
  const e=DR.info.envios.find(x=>x.tipo==='infestacao'&&x.status==='ok'&&x.resumo);
  if(!e)return'';
  const r=e.resumo, fmt=n=>Number(n).toLocaleString('pt-BR',{maximumFractionDigits:2});
  const tals=r.por_talhao.length?r.por_talhao.map(t=>`talhão ${t.talhao} (${t.manchas} · ${fmt(t.ha)} ha)`).join(', '):'nenhum talhão';
  return`<div class="dr-msg"><b>Último levantamento:</b> ${r.manchas} manchas · ${fmt(r.area_ha)} ha · ${tals}`
    +`${r.fora_ha>0?` · <span class="dr-err">${fmt(r.fora_ha)} ha fora dos talhões</span>`:' · nada fora'}`
    +`${r.repetido_de?`<br><span class="dr-err">Mesmo arquivo do envio #${r.repetido_de} — não precisava enviar de novo.</span>`:''}</div>`;
}
```

- [ ] **Step 4: Manchas no mapa** — chave "mostrar manchas" ao lado de "mostrar obstáculos", seguindo o mesmo padrão da função dos obstáculos (linhas ~485–495 de `drone.js`): busca `DR.manchasGeo=await drRpc('drone_infestacao_mapa',{p_infestacao_id:id})` para o `id` do último `drone_infestacoes` da fazenda (`sb.from('drone_infestacoes').select('id').eq('cod_faz',DR.cod).order('id',{ascending:false}).limit(1)`), fonte `manchas`, camada `fill` vermelho `#c23b3b` opacidade 0,6 com contorno; limpar `DR.manchasGeo` ao trocar de fazenda.

- [ ] **Step 5: Teste da tela** — em `tests/app/teste_drone_tela.py`, acrescentar: (a) com `drone_parametros.agente_ultimo_ciclo` salvo e trocado para 1 hora atrás, a tela Drone mostra a faixa "não responde" e o sininho tem "Servidor Geo sem resposta"; restaurar o valor original no `finally`; (b) abrir a fazenda 10678 e conferir que o cartão da Catação mostra "Último levantamento" e que a chave "mostrar manchas" adiciona a fonte `manchas` ao mapa (`map.getSource('manchas')`). Rodar: `HUB_CONTA_TESTE=<scratchpad>/conta-teste.json python tests/app/teste_drone_tela.py` → `FALHAS: nenhuma`; rodar também `teste_app.py` e `teste_admin.py`.

- [ ] **Step 6: Commit**
```bash
git add app/drone.js app/index.html tests/app/teste_drone_tela.py
git commit -m "Drone: aviso de servidor parado, resumo do levantamento e manchas no mapa"
```

---

### Task 7: Publicar e conferir no servidor

- [ ] **Step 1:** Leo roda `supabase/migrations/20261016090000_drone_desempenho.sql` no SQL Editor (nova query).
- [ ] **Step 2:** `git fetch && git rebase origin/main && git push origin colheita:main`.
- [ ] **Step 3:** No servidor Geo:
```powershell
cd $HOME\hub-geotech
git pull
python ingestao\talhao_geom.py
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -match 'drone.agente' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
schtasks /run /tn "Hub Geotech - Agente Drone"
```
- [ ] **Step 4: Conferir** — `select count(*) from hub.talhao_geom where geom_proj is not null` ≈ 7511; uma prévia de teste (fazenda 10974, Normal, como no `teste_drone_tela.py`) sai sem o alerta "pasta de rede" e com a mesma área de antes (comparar `resumo.aplicacao_ha` com a geração 12 da 10974: 14,6 ha no talhão 1); o último envio de infestação novo mostra o resumo no cartão.
