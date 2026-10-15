# Corretivos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Neste ambiente a execução segue a skill `delegar`:** cada tarefa diz a camada (1 = OpenCode grátis via `delegar.sh`, `-a frontend` para telas; 2 = sub-agente Haiku; 3 = Claude; U = usuário).

**Goal:** Ferramenta `app/corretivos.html` no site do Hub: o usuário escolhe a fazenda e a operação, marca talhões no mapa, lança aplicações de corretivo (Calcário Dolomítico/PH7, Fosfato, Blend) com dose e O.S., e baixa um PDF no layout do Drone gerado no navegador (Pyodide).

**Architecture:** Dados em quatro tabelas `hub.corretivo_*` com RLS por módulo `corretivos`; geometria vem de `hub.talhao_geom` por uma RPC. O layout comum de PDF sai de `drone/mapa_pdf.py` para o pacote `mapas/` (`layout.py`), usado pelo Drone (servidor) e pelo novo `mapas/corretivo_pdf.py` (navegador, via Pyodide). A página tem um modo demonstração (abre por `file://` com dados fictícios) para o executor de front-end conferir por print.

**Tech Stack:** Postgres/Supabase (schema `hub`, PostGIS em `extensions`), supabase-js v2, MapLibre GL 4.7.1, Pyodide 0.27.7 (matplotlib, shapely, pandas, pyproj, geopandas), Python 3.14 + pytest, PyMuPDF (só testes), Node 22 (`node --test`), Playwright + Edge, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-10-09-corretivos-design.md` (aprovada em 11/10/2026, com as 7 decisões).

## Global Constraints

- Operações: `subsolagem` | `supergrade` | `arado` (rótulos: SubSolagem, SuperGrade, Arado).
- Tipos: `calcario` (com `calcario` = `dolomitico` | `ph7`, 1 dose), `fosfato` (1 dose), `blend` (calcário `dolomitico`|`ph7` + gesso, 2 doses). Doses em t/ha, > 0. O.S. texto obrigatório por aplicação.
- Total (t) = área (ha) × dose, calculado sempre, nunca gravado. Arredondamento de exibição: 2 casas, vírgula decimal (`1.234,56`).
- Área: copiada da área produtiva da Base (`hub.talhoes.area_ha`; na falta, `hub.talhao_geom.area_ha`); editável; editada aparece com `*` no PDF.
- Aplicação idêntica (tipo, calcário, dose, dose do gesso, O.S.) no mesmo talhão do mesmo mapa é **recusada**.
- Paleta: Calcário Dolomítico `#2f6db5`, Calcário PH7 `#22a39f`, Fosfato `#e07b1a`, Blend `#7b4fb3`, sem aplicação `#e4e7e8`. Duas ou mais aplicações no talhão: **faixas diagonais iguais** (meio a meio com duas), na ordem de lançamento.
- PDF: esqueleto do Drone (faixa verde, mapa com logo e escala, tabela, carimbo, orientação automática, tabela longa nas páginas seguintes). Carimbo com tag `CORRETIVO · <OPERAÇÃO>`, um quadro por produto (Blend à parte; Blend Dolomítico e Blend PH7 separados; dentro do Blend "calc. X t + gesso Y t"), rodapé "Gerado em dd/mm/aaaa por <nome>", sem "Revisão". Arquivo `corretivo_<cod_faz>_<operacao>_<aaaa-mm-dd>.pdf`.
- **O PDF do Drone não pode mudar** (teste de regressão por imagem, Task 2).
- Fonte: cadeia `['Segoe UI', 'Selawik', 'DejaVu Sans']` (servidor continua Segoe UI; navegador usa Selawik, licença OFL).
- Acesso: admin ou quem tem o módulo `corretivos` em `hub.usuario_modulos` (qualquer papel). O módulo **não** entra no menu lateral do Hub; a página é cadastrada em Ferramentas.
- Salvamento automático a cada ação (sem botão Salvar). Excluir mapa pede confirmação e vai para `hub.log_auditoria`.
- Página: HTML/CSS/JS puro no padrão de `app/drone.js` (funções `crXxx` declaradas com `function`, estado em `CR`), textos em pt-BR, funciona em 390 px.
- Migrations: o **usuário** aplica no SQL Editor do Supabase. Testes com dados reais salvam e restauram o original; o E2E apaga só o que ele mesmo criou.
- Merge na `main` e push só com ok do usuário.

## Review Focus

1. **Talhão do mapa que saiu da Base** (existe em `corretivo_talhoes`, não existe mais em `talhao_geom`) → tela mostra aviso e o PDF lista o talhão na tabela sem desenhá-lo; nada quebra. Testes: Task 4 (`test_linhas_talhao_sem_geometria`), Task 5 (`test_pdf_talhao_sem_geometria`), Task 7 (`crTalhoesForaDaBase`).
2. **Três ou mais aplicações no mesmo talhão e polígonos com buraco/multipartes** → faixas cobrem o talhão inteiro sem sobrar nem sobrepor. Teste: Task 4 (`test_faixas_cobrem_talhao_multiparte`).
3. **Muitas linhas na tabela** (fazenda com 60 talhões e 2 aplicações cada) → tabela continua nas páginas seguintes, carimbo intacto. Teste: Task 5 (`test_pdf_muitas_linhas_pagina_extra`).
4. **Mesma aplicação lançada duas vezes no mesmo talhão** (duplo clique, duas abas) → recusada pela tela e pelo banco. Testes: Task 1 (trigger, verificado no E2E da Task 11) e Task 7 (`crDuplicadas`).
5. **Gerador do PDF não carrega** (CDN fora, primeira abertura lenta) → botão mostra "preparando…", depois erro com "Tentar de novo"; os dados já estão salvos. Teste: Task 10 (Step "falha do Pyodide").

---

### Task 1: Migração do banco (camada 3; U aplica)

**Files:**
- Create: `supabase/migrations/20261015090000_corretivos.sql`

**Interfaces:**
- Produces: tabelas `hub.corretivo_mapas(id, cod_faz, operacao, data, criado_por, criado_em, alterado_por, alterado_em)`, `hub.corretivo_talhoes(mapa_id, talhao_num, area_ha, area_editada)`, `hub.corretivo_aplicacoes(id, mapa_id, tipo, calcario, dose, dose_gesso, os, ordem)`, `hub.corretivo_aplicacao_talhoes(aplicacao_id, mapa_id, talhao_num)`; funções `hub.pode_usar_corretivos() -> boolean`, `hub.corretivo_talhoes_fazenda(p_cod_faz int) -> jsonb` (FeatureCollection 4326, props `talhao`, `area_prod`).

- [ ] **Step 1: Escrever a migração**

```sql
-- Corretivos: mapas de aplicação de corretivos (ferramenta app/corretivos.html).
-- Acesso: admin ou módulo 'corretivos' (qualquer papel). Escrita direta nas tabelas, protegida por RLS.
begin;

insert into hub.modulos (id, nome, ordem) values ('corretivos', 'Corretivos', 6) on conflict (id) do nothing;

create or replace function hub.pode_usar_corretivos()
returns boolean language sql stable security definer set search_path = hub as $$
  select exists (select 1 from hub.usuarios u
                  where u.id = auth.uid()
                    and (u.admin or exists (select 1 from hub.usuario_modulos m
                                             where m.usuario_id = u.id and m.modulo_id = 'corretivos')));
$$;

create table hub.corretivo_mapas (
  id            bigint generated always as identity primary key,
  cod_faz       int not null references hub.fazendas (cod_faz),
  operacao      text not null check (operacao in ('subsolagem', 'supergrade', 'arado')),
  data          date not null default current_date,
  criado_por    uuid references hub.usuarios (id) default auth.uid(),
  criado_em     timestamptz not null default now(),
  alterado_por  uuid references hub.usuarios (id) default auth.uid(),
  alterado_em   timestamptz not null default now()
);
create index on hub.corretivo_mapas (cod_faz);

create table hub.corretivo_talhoes (
  mapa_id       bigint not null references hub.corretivo_mapas (id) on delete cascade,
  talhao_num    int not null check (talhao_num between 0 and 999),
  area_ha       numeric not null check (area_ha > 0),
  area_editada  boolean not null default false,
  primary key (mapa_id, talhao_num)
);

create table hub.corretivo_aplicacoes (
  id          bigint generated always as identity primary key,
  mapa_id     bigint not null references hub.corretivo_mapas (id) on delete cascade,
  tipo        text not null check (tipo in ('calcario', 'fosfato', 'blend')),
  calcario    text check (calcario in ('dolomitico', 'ph7')),
  dose        numeric not null check (dose > 0),
  dose_gesso  numeric check (dose_gesso > 0),
  os          text not null check (length(trim(os)) > 0),
  ordem       int not null default 1,
  check ((tipo = 'fosfato'  and calcario is null     and dose_gesso is null)
      or (tipo = 'calcario' and calcario is not null and dose_gesso is null)
      or (tipo = 'blend'    and calcario is not null and dose_gesso is not null))
);
create index on hub.corretivo_aplicacoes (mapa_id);

create table hub.corretivo_aplicacao_talhoes (
  aplicacao_id  bigint not null references hub.corretivo_aplicacoes (id) on delete cascade,
  mapa_id       bigint not null,
  talhao_num    int not null,
  primary key (aplicacao_id, talhao_num),
  foreign key (mapa_id, talhao_num) references hub.corretivo_talhoes (mapa_id, talhao_num) on delete cascade
);

-- Quem mexeu por último no mapa (qualquer tabela filha "toca" o mapa).
create or replace function hub.corretivo_tocar()
returns trigger language plpgsql security definer set search_path = hub as $$
declare v_mapa bigint;
begin
  if tg_table_name = 'corretivo_mapas' then
    new.alterado_por := auth.uid(); new.alterado_em := now(); return new;
  end if;
  v_mapa := case when tg_op = 'DELETE' then old.mapa_id else new.mapa_id end;
  update hub.corretivo_mapas set alterado_em = now() where id = v_mapa;
  return null;
end $$;
create trigger corretivo_mapas_tocar before update on hub.corretivo_mapas
  for each row execute function hub.corretivo_tocar();
create trigger corretivo_talhoes_tocar after insert or update or delete on hub.corretivo_talhoes
  for each row execute function hub.corretivo_tocar();
create trigger corretivo_aplicacoes_tocar after insert or update or delete on hub.corretivo_aplicacoes
  for each row execute function hub.corretivo_tocar();

-- Talhão da aplicação precisa ser do mesmo mapa; aplicação idêntica no mesmo talhão é recusada.
create or replace function hub.corretivo_checar_aplicacao_talhao()
returns trigger language plpgsql security definer set search_path = hub as $$
declare a hub.corretivo_aplicacoes;
begin
  select * into a from hub.corretivo_aplicacoes where id = new.aplicacao_id;
  if a.mapa_id is distinct from new.mapa_id then
    raise exception 'Aplicação % não é do mapa %', new.aplicacao_id, new.mapa_id;
  end if;
  if exists (select 1 from hub.corretivo_aplicacao_talhoes x
               join hub.corretivo_aplicacoes b on b.id = x.aplicacao_id
              where x.mapa_id = new.mapa_id and x.talhao_num = new.talhao_num and b.id <> a.id
                and b.tipo = a.tipo and b.calcario is not distinct from a.calcario and b.dose = a.dose
                and b.dose_gesso is not distinct from a.dose_gesso and b.os = a.os) then
    raise exception 'O talhão % já tem esta aplicação', new.talhao_num;
  end if;
  return new;
end $$;
create trigger corretivo_aplicacao_talhoes_checar before insert or update on hub.corretivo_aplicacao_talhoes
  for each row execute function hub.corretivo_checar_aplicacao_talhao();

-- Exclusão de mapa vai para o log.
create or replace function hub.corretivo_log_exclusao()
returns trigger language plpgsql security definer set search_path = hub as $$
begin
  insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo, usuario_id, origem)
  values ('corretivos', 'fazenda', old.cod_faz, 'mapa_corretivo',
          format('mapa %s · %s · %s', old.id, old.operacao, to_char(old.data, 'DD/MM/YYYY')), null, auth.uid(), 'usuario');
  return old;
end $$;
create trigger corretivo_mapas_log after delete on hub.corretivo_mapas
  for each row execute function hub.corretivo_log_exclusao();

-- RLS: tudo liberado para quem pode usar os Corretivos.
do $$
declare t text;
begin
  foreach t in array array['corretivo_mapas', 'corretivo_talhoes', 'corretivo_aplicacoes', 'corretivo_aplicacao_talhoes'] loop
    execute format('alter table hub.%I enable row level security', t);
    execute format('create policy corretivos on hub.%I for all to authenticated '
                   'using (hub.pode_usar_corretivos()) with check (hub.pode_usar_corretivos())', t);
    execute format('grant select, insert, update, delete on hub.%I to authenticated', t);
    execute format('grant all on hub.%I to service_role', t);
  end loop;
end $$;

-- Talhões da fazenda para o mapa (geometria + área produtiva da Base).
create or replace function hub.corretivo_talhoes_fazenda(p_cod_faz int)
returns jsonb language plpgsql stable security definer set search_path = hub, extensions as $$
begin
  if not hub.pode_usar_corretivos() then
    raise exception 'Sem acesso aos Corretivos';
  end if;
  return (
    select jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(
             jsonb_build_object('type', 'Feature', 'geometry', ST_AsGeoJSON(g.geom, 6)::jsonb,
                                'properties', jsonb_build_object('talhao', g.talhao_num,
                                                                 'area_prod', coalesce(t.area_ha, g.area_ha)))
             order by g.talhao_num), '[]'::jsonb))
      from hub.talhao_geom g
      left join hub.talhoes t on t.cod_faz = g.cod_faz and t.talhao_num = g.talhao_num
     where g.cod_faz = p_cod_faz);
end $$;

revoke all on function hub.pode_usar_corretivos() from public, anon;
revoke all on function hub.corretivo_talhoes_fazenda(int) from public, anon;
grant execute on function hub.pode_usar_corretivos() to authenticated, service_role;
grant execute on function hub.corretivo_talhoes_fazenda(int) to authenticated, service_role;

commit;
```

- [ ] **Step 2: Commit** (`"Corretivos: migração (tabelas, RLS por módulo, log de exclusão, talhões da fazenda)"`).
- [ ] **Step 3 (U):** aplicar no SQL Editor. **Verificação (U, no SQL Editor):** `select hub.corretivo_talhoes_fazenda(10156)` como admin devolve um FeatureCollection com `area_prod`; `select count(*) from hub.modulos where id='corretivos'` = 1. A recusa de aplicação duplicada e o log de exclusão são verificados pelo E2E (Task 11).

---

### Task 2: Referência visual do PDF do Drone (camada 3, antes de qualquer refatoração)

**Files:**
- Create: `tests/drone/test_mapa_pdf_regressao.py`
- Create: `tests/drone/referencia/drone_paisagem.png`, `drone_retrato_catacao.png`, `drone_muitos_p1.png`, `drone_muitos_p2.png`

**Interfaces:**
- Produces: teste `test_pdf_drone_igual_a_referencia` que a Task 3 precisa manter verde.

- [ ] **Step 1: Escrever o teste** (gera os PNGs de referência na primeira execução com `GERAR_REFERENCIA=1`)

```python
"""Regressão: o PDF do Drone tem de continuar idêntico depois da extração do layout para mapas/."""
import datetime
import os
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from drone.geometria import recortar, uniao_buffers
from drone.mapa_pdf import DadosMapa, gerar_pdf

pymupdf = pytest.importorskip('pymupdf')
REF = Path(__file__).parent / 'referencia'
DIA = datetime.date(2026, 10, 15)


def _talhoes(n, largura=800, altura=500):
    geoms = [box(i * 120, 0, i * 120 + 100, 100) for i in range(n)] if n > 2 else \
            [box(0, 0, largura / 2, altura), box(largura / 2, 0, largura, altura)]
    return gpd.GeoDataFrame({'TALHAO': list(range(1, len(geoms) + 1)),
                             'AREA_PROD': [10.0 + i for i in range(len(geoms))]}, geometry=geoms, crs=31983)


CASOS = {
    'drone_paisagem': lambda: DadosMapa(10156, 'FAZENDA TESTE', 'normal', 2, _talhoes(2),
                                        recortar(_talhoes(2), uniao_buffers({}, {})), DIA),
    'drone_retrato_catacao': lambda: DadosMapa(10372, 'FAZENDA RETRATO', 'catacao', 0, _talhoes(2, 300, 900),
                                               recortar(_talhoes(2, 300, 900), uniao_buffers({}, {})), DIA),
    'drone_muitos': lambda: DadosMapa(10008, 'FAZENDA GRANDE', 'normal', 1, _talhoes(60),
                                      recortar(_talhoes(60), uniao_buffers({}, {})), DIA),
}


@pytest.mark.parametrize('nome', CASOS)
def test_pdf_drone_igual_a_referencia(nome, tmp_path):
    destino = tmp_path / f'{nome}.pdf'
    gerar_pdf(CASOS[nome](), str(destino))
    doc = pymupdf.open(destino)
    paginas = [f'{nome}.png'] if len(doc) == 1 else [f'{nome}_p{i + 1}.png' for i in range(len(doc))]
    for pagina, arquivo in zip(doc, paginas):
        png = pagina.get_pixmap(dpi=80).tobytes('png')
        if os.environ.get('GERAR_REFERENCIA'):
            REF.mkdir(exist_ok=True)
            (REF / arquivo).write_bytes(png)
        else:
            assert (REF / arquivo).read_bytes() == png, f'{arquivo} mudou'
```

- [ ] **Step 2: Gerar a referência com o código atual e conferir**

Run: `$env:GERAR_REFERENCIA='1'; python -m pytest tests/drone/test_mapa_pdf_regressao.py -q; Remove-Item env:GERAR_REFERENCIA; python -m pytest tests/drone/test_mapa_pdf_regressao.py -q`
Expected: `3 passed` nas duas rodadas; `tests/drone/referencia/` com 4 PNGs (o caso de 60 talhões tem 2 páginas — se tiver outro número, ajuste a lista no commit, não o código). Abrir um PNG e conferir que é o layout do Drone.

- [ ] **Step 3: Commit** (`"Drone: referência visual do PDF para proteger a extração do layout"`).

---

### Task 3: Extrair o layout comum para `mapas/layout.py` (camada 2, Haiku)

**Files:**
- Create: `mapas/__init__.py` (vazio), `mapas/layout.py`
- Modify: `drone/mapa_pdf.py` (passa a importar de `mapas.layout`)
- Test: `tests/drone/test_mapa_pdf.py` (inalterado), `tests/drone/test_mapa_pdf_regressao.py` (Task 2)

**Interfaces:**
- Produces (usado pela Task 5):
  - Constantes `MARCA, GRAFITE, CINZA, LINHA, MM, ALT_MIN`; `FONTES = ['Segoe UI', 'Selawik', 'DejaVu Sans']` aplicada em `plt.rcParams['font.family']`; `pdf.fonttype = 42`.
  - `br(v) -> str`, `orientacao(gdf) -> str`, `safra_de(data) -> str`, `class Pagina(fig, W, H)` (com `eixo, caixa, texto, ret`), `cabe(n, h) -> bool`
  - `eixo_mapa(pg, gdf, x, y, w, h) -> tuple[ax, s, x0, y0]` (eixo com enquadramento e fundo do Drone), `escala_grafica(ax, s, x0, y0)`, `moldura_logo(pg, x, y, w, h, logo)`, `escala_numerica(s) -> int`
  - `grade(pg, colunas, linhas, x, y, w, alt, total=None) -> float` — `colunas = [(titulo, fx, ha)]`, `linhas = list[list[str]]`, `total = list[str] | None`
  - `paginas_tabela(pdf, W, H, colunas, linhas, total, cabecalho)` — `cabecalho(pg)` desenha o título de cada página extra
  - `caixa_norte(pg, nx, ny)`, `rodape(pg, x, y, w, esquerda, direita)`, `nova_pagina(W, H) -> Pagina` (com a faixa da marca)

- [ ] **Step 1: Brief para o Haiku** (camada 2; primeiro plano):

```text
Repositório C:\Users\lmalerbo\Documents\hub-geotech. Tarefa: extrair de drone/mapa_pdf.py o que é genérico para um pacote novo mapas/ (mapas/__init__.py vazio + mapas/layout.py), SEM mudar nenhum pixel do PDF do Drone.
Mova para mapas/layout.py, com estes nomes públicos: MARCA, GRAFITE, CINZA, LINHA, MM, ALT_MIN, FONTES, br, orientacao, safra_de, Pagina, cabe (ex-_cabe), eixo_mapa, escala_grafica, moldura_logo, escala_numerica, grade, paginas_tabela, caixa_norte, rodape, nova_pagina.
- eixo_mapa(pg, gdf, x, y, w, h) -> (ax, s, x0, y0): o trecho de _mapa que cria o eixo, calcula s/x0/y0 (reservas topo 22, base 14, lado 8), limites, fundo #fbfcfb, sem ticks/spines.
- escala_grafica(ax, s, x0, y0): a barra de escala (3 retângulos + rótulos).
- moldura_logo(pg, x, y, w, h, logo): a moldura arredondada + o logo 34x15 mm.
- escala_numerica(s) -> int: round(1000 / s / 500) * 500 or 500.
- grade(pg, colunas, linhas, x, y, w, alt, total=None): generalize _grade — colunas=[(titulo, fx, ha)], linhas=list[list[str]], total=list[str]|None; mesmas medidas, fontes e cores.
- paginas_tabela(pdf, W, H, colunas, linhas, total, cabecalho): generalize _paginas_tabela; cabecalho(pg) desenha título/subtítulo de cada página extra.
- caixa_norte(pg, nx, ny): a seta de norte + "N". rodape(pg, x, y, w, esquerda, direita): a linha + os dois textos do rodapé.
- nova_pagina(W, H) -> Pagina: figura + faixa da marca no topo.
- FONTES = ['Segoe UI', 'Selawik', 'DejaVu Sans'] em plt.rcParams['font.family'] (mantenha pdf.fonttype = 42 e matplotlib.use('Agg')).
drone/mapa_pdf.py continua com a mesma interface pública (DadosMapa, orientacao, safra_de, safra_do_mapa, linha_incompleta, br, gerar_pdf, COLS, CORES, ALTURA_CARIMBO) — reexporte o que os testes importam — e passa a montar o PDF chamando as funções de mapas.layout.
Verificação obrigatória: `python -m pytest tests/drone -q` (todos passam, inclusive tests/drone/test_mapa_pdf_regressao.py, que compara imagem pixel a pixel com a referência). Se a regressão falhar, o refactor mudou algo: corrija o refactor, nunca a referência.
Não mexa em outros arquivos. Faça commit: "Mapas: layout comum de PDF extraído do Drone (sem mudança visual)".
Responda só com: arquivos alterados, resultado do pytest (contagem) e qualquer desvio da lista de nomes acima.
```

- [ ] **Step 2 (camada 3): revisar** o diff (nomes da interface batem com a lista acima) e rodar você mesmo `python -m pytest tests/drone -q`.
Expected: todos passam (os 10 de `test_mapa_pdf.py` + 3 de regressão + o resto da suíte do Drone).

---

### Task 4: Lógica do mapa de corretivos (camada 1, `delegar.sh -a build`)

**Files:**
- Create: `mapas/corretivo_dados.py`
- Test: `tests/mapas/__init__.py` (vazio), `tests/mapas/test_corretivo_dados.py`

**Interfaces:**
- Consumes: nada de outras tarefas (só shapely).
- Produces (usado pela Task 5): `CORES: dict[str, str]`, `SEM_APLICACAO = '#e4e7e8'`, `OPERACOES: dict[str, str]`, `chave_cor(ap) -> str`, `rotulo(ap) -> str`, `linhas_tabela(dados) -> list[list[str]]`, `totais_por_produto(dados) -> list[dict]` (`{'titulo', 'toneladas', 'detalhe'}`), `area_total(dados) -> float`, `faixas(geom, n) -> list[BaseGeometry]`, `lista_os(dados) -> list[str]`.
- Formato `dados` (o mesmo JSON que a página manda ao Pyodide, Task 7 `crMontarDados`):

```json
{"cod_faz": 10156, "nome": "FAZENDA TESTE", "operacao": "subsolagem", "data": "2026-10-15", "gerado_por": "Ana",
 "talhoes_geo": {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {}, "properties": {"talhao": 1}}]},
 "areas": {"1": {"area_ha": 23.0, "editada": false}},
 "aplicacoes": [{"tipo": "calcario", "calcario": "dolomitico", "dose": 2.0, "dose_gesso": null, "os": "4520",
                 "ordem": 1, "talhoes": [1, 3]}]}
```

- [ ] **Step 1: Escrever os testes (falhando)**

```python
import pytest
from shapely.geometry import MultiPolygon, Polygon, box

from mapas.corretivo_dados import (area_total, chave_cor, faixas, linhas_tabela, lista_os, rotulo,
                                   totais_por_produto)

DOL = {'tipo': 'calcario', 'calcario': 'dolomitico', 'dose': 2.0, 'dose_gesso': None, 'os': '4520', 'ordem': 1,
       'talhoes': [1, 3]}
FOS = {'tipo': 'fosfato', 'calcario': None, 'dose': 0.5, 'dose_gesso': None, 'os': '4521', 'ordem': 2,
       'talhoes': [2, 3]}
BLEND = {'tipo': 'blend', 'calcario': 'dolomitico', 'dose': 1.5, 'dose_gesso': 1.0, 'os': '4530', 'ordem': 3,
         'talhoes': [4, 5]}
AREAS = {'1': {'area_ha': 23.0, 'editada': False}, '2': {'area_ha': 23.0, 'editada': False},
         '3': {'area_ha': 21.4, 'editada': False}, '4': {'area_ha': 5.24, 'editada': True},
         '5': {'area_ha': 4.70, 'editada': False}}
DADOS = {'areas': AREAS, 'aplicacoes': [DOL, FOS, BLEND]}


def test_chave_cor_e_rotulo():
    assert chave_cor(DOL) == 'calcario:dolomitico' and rotulo(DOL) == 'Calc. Dolomítico'
    assert chave_cor({**DOL, 'calcario': 'ph7'}) == 'calcario:ph7' and rotulo({**DOL, 'calcario': 'ph7'}) == 'Calc. PH7'
    assert chave_cor(FOS) == 'fosfato' and rotulo(FOS) == 'Fosfato'
    assert chave_cor(BLEND) == 'blend' and rotulo(BLEND) == 'Blend · Dolomítico'


def test_linhas_tabela():
    assert linhas_tabela(DADOS) == [
        ['1', '23,00', 'Calc. Dolomítico', '2,00', '46,00', '4520'],
        ['2', '23,00', 'Fosfato', '0,50', '11,50', '4521'],
        ['3', '21,40', 'Calc. Dolomítico', '2,00', '42,80', '4520'],
        ['', '', 'Fosfato', '0,50', '10,70', '4521'],
        ['4', '5,24*', 'Blend · Dolomítico', '1,50', '7,86', '4530'],
        ['', '', '+ Gesso', '1,00', '5,24', '4530'],
        ['5', '4,70', 'Blend · Dolomítico', '1,50', '7,05', '4530'],
        ['', '', '+ Gesso', '1,00', '4,70', '4530'],
    ]


def test_linhas_talhao_sem_aplicacao_e_sem_geometria():
    dados = {'areas': {**AREAS, '9': {'area_ha': 3.0, 'editada': False}}, 'aplicacoes': [DOL]}
    assert ['9', '3,00', '—', '', '', ''] in linhas_tabela(dados)


def test_linhas_talhao_sem_geometria():
    # A tabela vem só de areas/aplicacoes: talhão fora de talhoes_geo continua listado.
    dados = {'areas': {'7': {'area_ha': 2.0, 'editada': False}}, 'aplicacoes': [{**FOS, 'talhoes': [7]}],
             'talhoes_geo': {'type': 'FeatureCollection', 'features': []}}
    assert linhas_tabela(dados) == [['7', '2,00', 'Fosfato', '0,50', '1,00', '4521']]


def test_totais_por_produto_blend_separado():
    blend_ph7 = {**BLEND, 'calcario': 'ph7', 'talhoes': [1], 'ordem': 4}
    t = totais_por_produto({'areas': AREAS, 'aplicacoes': [DOL, FOS, BLEND, blend_ph7]})
    assert t == [
        {'titulo': 'Calcário Dolomítico', 'toneladas': 88.8, 'detalhe': None},
        {'titulo': 'Fosfato', 'toneladas': 22.2, 'detalhe': None},
        {'titulo': 'Blend Dolomítico', 'toneladas': 24.85, 'detalhe': 'calc. 14,91 t + gesso 9,94 t'},
        {'titulo': 'Blend PH7', 'toneladas': 57.5, 'detalhe': 'calc. 34,50 t + gesso 23,00 t'},
    ]


def test_area_total_e_lista_os():
    assert area_total(DADOS) == pytest.approx(77.34)
    assert lista_os(DADOS) == ['4520', '4521', '4530']


@pytest.mark.parametrize('n', [1, 2, 3, 4])
def test_faixas_cobrem_talhao(n):
    t = Polygon([(0, 0), (100, 0), (120, 60), (10, 80)])
    partes = faixas(t, n)
    assert len(partes) == n
    assert sum(p.area for p in partes) == pytest.approx(t.area, rel=1e-9)
    assert all(not p.is_empty for p in partes)


def test_faixas_cobrem_talhao_multiparte():
    t = MultiPolygon([box(0, 0, 50, 50).difference(box(20, 20, 30, 30)), box(80, 0, 120, 40)])
    partes = faixas(t, 3)
    assert sum(p.area for p in partes) == pytest.approx(t.area, rel=1e-9)
    for i in range(3):
        for j in range(i + 1, 3):
            assert partes[i].intersection(partes[j]).area == pytest.approx(0, abs=1e-6)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/mapas -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'mapas.corretivo_dados'`.

- [ ] **Step 3: Implementar `mapas/corretivo_dados.py`**

```python
"""Regras do mapa de corretivos que não dependem de desenho: cores, rótulos, linhas da tabela,
totais por produto e divisão do talhão em faixas (duas ou mais aplicações)."""
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

CORES = {'calcario:dolomitico': '#2f6db5', 'calcario:ph7': '#22a39f', 'fosfato': '#e07b1a', 'blend': '#7b4fb3'}
SEM_APLICACAO = '#e4e7e8'
OPERACOES = {'subsolagem': 'SubSolagem', 'supergrade': 'SuperGrade', 'arado': 'Arado'}
_CALCARIO = {'dolomitico': 'Dolomítico', 'ph7': 'PH7'}


def br(v: float) -> str:
    return f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def chave_cor(ap: dict) -> str:
    return f"calcario:{ap['calcario']}" if ap['tipo'] == 'calcario' else ap['tipo']


def rotulo(ap: dict) -> str:
    if ap['tipo'] == 'calcario':
        return f"Calc. {_CALCARIO[ap['calcario']]}"
    if ap['tipo'] == 'blend':
        return f"Blend · {_CALCARIO[ap['calcario']]}"
    return 'Fosfato'


def _ordenadas(dados) -> list[dict]:
    return sorted(dados['aplicacoes'], key=lambda a: a['ordem'])


def _area(dados, talhao) -> float:
    return float(dados['areas'][str(talhao)]['area_ha'])


def linhas_tabela(dados) -> list[list[str]]:
    linhas = []
    for chave in sorted(dados['areas'], key=int):
        t = int(chave)
        area = _area(dados, t)
        area_txt = br(area) + ('*' if dados['areas'][chave].get('editada') else '')
        aps = [a for a in _ordenadas(dados) if t in a['talhoes']]
        if not aps:
            linhas.append([str(t), area_txt, '—', '', '', ''])
            continue
        primeira = True
        for a in aps:
            cab = [str(t), area_txt] if primeira else ['', '']
            linhas.append(cab + [rotulo(a), br(a['dose']), br(area * a['dose']), a['os']])
            if a['tipo'] == 'blend':
                linhas.append(['', '', '+ Gesso', br(a['dose_gesso']), br(area * a['dose_gesso']), a['os']])
            primeira = False
    return linhas


def totais_por_produto(dados) -> list[dict]:
    soma: dict[str, list[float]] = {}
    for a in _ordenadas(dados):
        area = sum(_area(dados, t) for t in a['talhoes'])
        if a['tipo'] == 'blend':
            titulo = f"Blend {_CALCARIO[a['calcario']]}"
            calc, gesso = soma.setdefault(titulo, [0.0, 0.0])
            soma[titulo] = [calc + area * a['dose'], gesso + area * a['dose_gesso']]
        else:
            titulo = 'Fosfato' if a['tipo'] == 'fosfato' else f"Calcário {_CALCARIO[a['calcario']]}"
            soma.setdefault(titulo, [0.0])
            soma[titulo][0] += area * a['dose']
    ordem = ['Calcário Dolomítico', 'Calcário PH7', 'Fosfato', 'Blend Dolomítico', 'Blend PH7']
    saida = []
    for titulo in ordem:
        if titulo not in soma:
            continue
        v = soma[titulo]
        if titulo.startswith('Blend'):
            saida.append({'titulo': titulo, 'toneladas': round(v[0] + v[1], 2),
                          'detalhe': f'calc. {br(v[0])} t + gesso {br(v[1])} t'})
        else:
            saida.append({'titulo': titulo, 'toneladas': round(v[0], 2), 'detalhe': None})
    return saida


def area_total(dados) -> float:
    return sum(_area(dados, t) for t in dados['areas'])


def lista_os(dados) -> list[str]:
    return sorted({a['os'] for a in dados['aplicacoes']})


def faixas(geom: BaseGeometry, n: int) -> list[BaseGeometry]:
    """Divide o talhão em n faixas diagonais (perpendiculares à direção x+y) de mesma largura."""
    if n <= 1:
        return [geom]
    minx, miny, maxx, maxy = geom.bounds
    umin, umax = minx + miny, maxx + maxy
    passo = (umax - umin) / n
    folga = (maxx - minx) + (maxy - miny) + 1
    partes = []
    for i in range(n):
        u0 = umin + i * passo if i else umin - folga
        u1 = umin + (i + 1) * passo if i < n - 1 else umax + folga
        # faixa entre as retas x+y=u0 e x+y=u1, larga o bastante para cobrir o talhão
        faixa = Polygon([(u0 - miny + folga, miny - folga), (u1 - miny + folga, miny - folga),
                         (u1 - maxy - folga, maxy + folga), (u0 - maxy - folga, maxy + folga)])
        partes.append(geom.intersection(faixa))
    return partes
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/mapas -q`
Expected: `11 passed`. Se `test_faixas_*` falhar por área, o erro está na faixa (os vértices devem estar sobre as retas `x+y=u0` e `x+y=u1`); conferir com `faixa.area` e corrigir a construção, não o teste.

- [ ] **Step 5: Commit** (`"Corretivos: regras do mapa (cores, tabela, totais por produto, faixas)"`).

---

### Task 5: PDF do mapa de corretivos (camada 2, Haiku)

**Files:**
- Create: `mapas/corretivo_pdf.py`
- Test: `tests/mapas/test_corretivo_pdf.py`

**Interfaces:**
- Consumes: `mapas.layout` (Task 3), `mapas.corretivo_dados` (Task 4).
- Produces (usado pela Task 10 no navegador): `gerar_pdf(dados: dict, destino) -> str` (orientação) e `gerar_bytes(json_texto: str) -> bytes`.

- [ ] **Step 1: Escrever os testes (falhando)**

```python
import json

import pytest
from shapely.geometry import box, mapping
from shapely.ops import transform
from pyproj import Transformer

from mapas.corretivo_pdf import gerar_bytes, gerar_pdf

pymupdf = pytest.importorskip('pymupdf')
PARA_4326 = Transformer.from_crs(31983, 4326, always_xy=True).transform


def _geo(n, largura=100):
    feats = [{'type': 'Feature', 'properties': {'talhao': i + 1},
              'geometry': mapping(transform(PARA_4326, box(300000 + i * (largura + 20), 7600000,
                                                           300000 + i * (largura + 20) + largura, 7600000 + 300)))}
             for i in range(n)]
    return {'type': 'FeatureCollection', 'features': feats}


def _dados(n=5, aplicacoes=None, sem_geo=()):
    geo = _geo(n)
    geo['features'] = [f for f in geo['features'] if f['properties']['talhao'] not in sem_geo]
    return {'cod_faz': 10156, 'nome': 'FAZENDA TESTE', 'operacao': 'subsolagem', 'data': '2026-10-15',
            'gerado_por': 'Ana', 'talhoes_geo': geo,
            'areas': {str(i + 1): {'area_ha': 10.0 + i, 'editada': i == 3} for i in range(n)},
            'aplicacoes': aplicacoes or [
                {'tipo': 'calcario', 'calcario': 'dolomitico', 'dose': 2.0, 'dose_gesso': None, 'os': '4520',
                 'ordem': 1, 'talhoes': [1, 3]},
                {'tipo': 'fosfato', 'calcario': None, 'dose': 0.5, 'dose_gesso': None, 'os': '4521', 'ordem': 2,
                 'talhoes': [2, 3]},
                {'tipo': 'blend', 'calcario': 'dolomitico', 'dose': 1.5, 'dose_gesso': 1.0, 'os': '4530',
                 'ordem': 3, 'talhoes': [4, 5]}]}


def _texto(caminho):
    doc = pymupdf.open(caminho)
    return len(doc), '\n'.join(p.get_text() for p in doc)


def test_pdf_basico(tmp_path):
    destino = tmp_path / 'c.pdf'
    gerar_pdf(_dados(), destino)
    paginas, texto = _texto(destino)
    assert paginas == 1
    for esperado in ['CORRETIVO · SUBSOLAGEM', '10156 · FAZENDA TESTE', 'O.S. 4520, 4521, 4530',
                     'Calcário Dolomítico', 'Fosfato', 'Blend Dolomítico', 'calc. 40,50 t + gesso 27,00 t',
                     'Blend · Dolomítico', '+ Gesso', '13,00*', 'Gerado em 15/10/2026 por Ana']:
        assert esperado in texto, esperado
    assert 'Rev' not in texto


def test_gerar_bytes_igual_ao_arquivo(tmp_path):
    b = gerar_bytes(json.dumps(_dados()))
    assert b.startswith(b'%PDF')


def test_pdf_talhao_sem_geometria(tmp_path):
    destino = tmp_path / 'c.pdf'
    gerar_pdf(_dados(sem_geo=(2,)), destino)
    _, texto = _texto(destino)
    assert '11,00' in texto            # área do talhão 2 continua na tabela


def test_pdf_muitas_linhas_pagina_extra(tmp_path):
    n = 60
    aps = [{'tipo': 'calcario', 'calcario': 'ph7', 'dose': 1.0, 'dose_gesso': None, 'os': '1', 'ordem': 1,
            'talhoes': list(range(1, n + 1))},
           {'tipo': 'blend', 'calcario': 'ph7', 'dose': 1.0, 'dose_gesso': 0.5, 'os': '2', 'ordem': 2,
            'talhoes': list(range(1, n + 1))}]
    destino = tmp_path / 'c.pdf'
    gerar_pdf(_dados(n, aps), destino)
    paginas, texto = _texto(destino)
    assert paginas >= 2
    assert 'CORRETIVO · SUBSOLAGEM' in texto and 'Blend PH7' in texto


def test_tres_aplicacoes_no_mesmo_talhao(tmp_path):
    aps = [{'tipo': t, 'calcario': c, 'dose': 1.0, 'dose_gesso': g, 'os': str(i), 'ordem': i, 'talhoes': [1]}
           for i, (t, c, g) in enumerate([('calcario', 'dolomitico', None), ('fosfato', None, None),
                                          ('blend', 'ph7', 1.0)], 1)]
    destino = tmp_path / 'c.pdf'
    gerar_pdf(_dados(1, aps), destino)
    assert _texto(destino)[0] == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/mapas/test_corretivo_pdf.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'mapas.corretivo_pdf'`.

- [ ] **Step 3: Brief para o Haiku** (camada 2; primeiro plano):

```text
Repositório C:\Users\lmalerbo\Documents\hub-geotech. Implemente mapas/corretivo_pdf.py para os testes de tests/mapas/test_corretivo_pdf.py passarem (já escritos; NÃO os altere).
Use mapas.layout (Pagina, nova_pagina, eixo_mapa, escala_grafica, moldura_logo, escala_numerica, grade, paginas_tabela, cabe, caixa_norte, rodape, orientacao, safra_de, MARCA, GRAFITE, CINZA, LINHA, ALT_MIN) e mapas.corretivo_dados (CORES, SEM_APLICACAO, OPERACOES, chave_cor, linhas_tabela, totais_por_produto, area_total, lista_os, faixas, br). Logo: drone/assets/logo-pedra.png (caminho relativo ao pacote: Path(__file__).resolve().parent.parent / 'drone' / 'assets' / 'logo-pedra.png').
Funções públicas:
- gerar_pdf(dados: dict, destino) -> str (orientação), gerar_bytes(json_texto: str) -> bytes (gera num BytesIO).
Desenho (siga o gerar_pdf do Drone em drone/mapa_pdf.py como modelo de posições, A4, orientação automática por orientacao(gdf)):
- Talhões: GeoDataFrame de dados['talhoes_geo'] (EPSG:4326) convertido para 31983. Talhão do mapa sem aplicação: SEM_APLICACAO; talhão da fazenda fora do mapa: branco com contorno; talhão com k aplicações: faixas(geom, k) pintadas com CORES[chave_cor(ap)] na ordem de 'ordem'; contorno GRAFITE 0,5; número do talhão no representative_point como no Drone. Talhão do mapa sem geometria só aparece na tabela.
- Tabela (área à direita no paisagem, abaixo à esquerda no retrato): título "APLICAÇÕES POR TALHÃO"; colunas [('TALHÃO',0.02,'left'),('ÁREA',0.20,'right'),('APLICAÇÃO',0.24,'left'),('DOSE',0.70,'right'),('TOTAL',0.85,'right'),('O.S.',0.98,'right')]; linhas = linhas_tabela(dados); total = ['Total', br(area_total(dados)), '', '', '', '']; nota "* área editada · ÁREA ha · DOSE t/ha · TOTAL t"; legenda só com os tipos usados (quadradinho de cor + rótulo) e "◩ duas aplicações" se algum talhão tiver 2+. Se não couber (cabe), vai para paginas_tabela com cabeçalho "<cod> · <nome>" / "APLICAÇÕES POR TALHÃO".
- Carimbo (mesmas medidas do _carimbo do Drone): tag MARCA com "CORRETIVO · <OPERACOES[operacao] em maiúsculas>"; "<cod_faz> · <nome>"; subtítulo "MAPA DE APLICAÇÃO · CORRETIVOS · O.S. " + ', '.join(lista_os); quadros por produto de totais_por_produto (até 3 por linha, altura 15; título, toneladas em destaque + " t", detalhe embaixo quando houver; o primeiro quadro com o fundo de destaque do Drone); linha ESCALA (1:escala_numerica) / ÁREA (br(area_total) ha · N talhões) / SAFRA (safra_de(data)); caixa_norte; rodape com "Pedra Agroindustrial S/A · Geotecnologia" e "Gerado em dd/mm/aaaa por <gerado_por>". Sem "Revisão".
Fontes: só as do mapas.layout (não registre fontes aqui).
Verificação: `python -m pytest tests/mapas tests/drone -q` (tudo passa). Gere também um PDF de amostra em C:\Users\lmalerbo\AppData\Local\Temp\corretivo_amostra.pdf com os dados de _dados() do teste e diga o caminho.
Commit: "Corretivos: PDF do mapa (layout do Drone, faixas, quadros por produto)". Responda só com: arquivos alterados, resultado do pytest e o caminho da amostra.
```

- [ ] **Step 4 (camada 3): revisar** o diff, rodar `python -m pytest tests/mapas tests/drone -q`, abrir a amostra (render PNG com PyMuPDF) e conferir contra o esboço aprovado (meio a meio, quadros por produto, Blend à parte, rodapé). Reprovado → rodada de correção com itens numerados.
Expected: `tests/mapas`: 16 passed; `tests/drone`: todos passam (regressão intacta).

---

### Task 6: Fonte Selawik, publicação dos arquivos Python e deploy (camada 3)

**Files:**
- Create: `mapas/fontes/selawk.ttf`, `mapas/fontes/selawksb.ttf`, `mapas/fontes/selawkb.ttf`, `mapas/fontes/LICENSE.txt` (OFL, do repositório oficial microsoft/Selawik)
- Create: `mapas/publicar.py`
- Modify: `.github/workflows/pages.yml`, `.gitignore`
- Test: `tests/mapas/test_publicar.py`

**Interfaces:**
- Produces: pasta `app/py/` gerada (não versionada) com `mapas/__init__.py`, `mapas/layout.py`, `mapas/corretivo_dados.py`, `mapas/corretivo_pdf.py`, `drone/assets/logo-pedra.png`, `mapas/fontes/*.ttf` e `manifest.json` (`{"arquivos": ["mapas/layout.py", ...]}`), consumida pela Task 10.

- [ ] **Step 1: Baixar a Selawik** das releases de `github.com/microsoft/Selawik` (arquivos `selawk.ttf`, `selawksb.ttf`, `selawkb.ttf` e a licença) para `mapas/fontes/`. Conferir que a licença é a SIL Open Font License.

- [ ] **Step 2: Teste (falhando)**

```python
import json

from mapas.publicar import ARQUIVOS, publicar


def test_publicar_copia_e_gera_manifesto(tmp_path):
    publicar(tmp_path)
    manifesto = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    assert manifesto['arquivos'] == ARQUIVOS
    for rel in ARQUIVOS:
        assert (tmp_path / rel).is_file(), rel
    assert 'drone/mapa_pdf.py' not in ARQUIVOS          # o navegador não precisa do código do Drone
```

- [ ] **Step 3: Implementar `mapas/publicar.py`**

```python
"""Copia para app/py/ os arquivos que o navegador carrega no Pyodide (fonte única: mapas/).
Uso: python mapas/publicar.py [destino]   (padrão: app/py)"""
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVOS = ['mapas/__init__.py', 'mapas/layout.py', 'mapas/corretivo_dados.py', 'mapas/corretivo_pdf.py',
            'drone/assets/logo-pedra.png',
            'mapas/fontes/selawk.ttf', 'mapas/fontes/selawksb.ttf', 'mapas/fontes/selawkb.ttf']


def publicar(destino) -> None:
    destino = Path(destino)
    for rel in ARQUIVOS:
        alvo = destino / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / rel, alvo)
    (destino / 'manifest.json').write_text(json.dumps({'arquivos': ARQUIVOS}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    publicar(sys.argv[1] if len(sys.argv) > 1 else RAIZ / 'app' / 'py')
```

- [ ] **Step 4: Rodar** `python -m pytest tests/mapas/test_publicar.py -q` → `1 passed`.

- [ ] **Step 5: `.gitignore`** ganha `app/py/`. **`pages.yml`**: `paths: ['app/**', 'mapas/**', 'drone/assets/**', '.github/workflows/pages.yml']` e, antes do `upload-pages-artifact`:

```yaml
        - name: Arquivos Python do gerador de PDF (Pyodide)
          run: python3 mapas/publicar.py app/py
```

- [ ] **Step 6: Commit** (`"Corretivos: fonte Selawik e publicação dos arquivos do Pyodide no deploy"`).

---

### Task 7: Funções puras da página (camada 1, `delegar.sh -a build`)

**Files:**
- Create: `app/corretivos.js` (só a seção "funções puras" nesta tarefa; as outras seções vêm nas Tasks 8–10)
- Test: `tests/app/corretivos_puro.test.js`

**Interfaces:**
- Produces (usado pelas Tasks 8–10): `crBr(v)`, `crTotal(area, dose)`, `crRotulo(ap)`, `crChaveCor(ap)`, `CR_CORES`, `crTotaisPorProduto(apls, areas)` (mesmo resultado de `totais_por_produto` do Python), `crValidarAplicacao(f) -> string|null` (mensagem de erro), `crDuplicadas(apls, nova, talhoes) -> number[]` (talhões onde a `nova` já existe), `crTalhoesForaDaBase(areas, geo) -> number[]`, `crMontarDados(ctx) -> object` (JSON da Task 4), `crNomeArquivo(codFaz, operacao, data) -> string`, `crCoresTalhao(apls, talhao) -> string[]`.

- [ ] **Step 1: Teste (falhando)**

```js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ document: {}, window: {}, console, location: { protocol: 'https:', search: '' } });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/corretivos.js'), 'utf8'), ctx);

const DOL = { tipo: 'calcario', calcario: 'dolomitico', dose: 2, dose_gesso: null, os: '4520', ordem: 1, talhoes: [1, 3] };
const FOS = { tipo: 'fosfato', calcario: null, dose: 0.5, dose_gesso: null, os: '4521', ordem: 2, talhoes: [2, 3] };
const BLEND = { tipo: 'blend', calcario: 'dolomitico', dose: 1.5, dose_gesso: 1, os: '4530', ordem: 3, talhoes: [4, 5] };
const AREAS = { 1: { area_ha: 23, editada: false }, 2: { area_ha: 23, editada: false }, 3: { area_ha: 21.4, editada: false },
                4: { area_ha: 5.24, editada: true }, 5: { area_ha: 4.7, editada: false } };

test('formato e total', () => {
  assert.strictEqual(ctx.crBr(1234.5), '1.234,50');
  assert.strictEqual(ctx.crTotal(5.24, 1.5), 7.86);
});

test('rótulos e cores', () => {
  assert.strictEqual(ctx.crRotulo(BLEND), 'Blend · Dolomítico');
  assert.strictEqual(ctx.CR_CORES[ctx.crChaveCor({ ...DOL, calcario: 'ph7' })], '#22a39f');
  assert.deepStrictEqual(ctx.crCoresTalhao([FOS, DOL], 3), ['#2f6db5', '#e07b1a']);
  assert.deepStrictEqual(ctx.crCoresTalhao([DOL], 9), []);
});

test('totais por produto iguais ao Python', () => {
  assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.crTotaisPorProduto([DOL, FOS, BLEND], AREAS))), [
    { titulo: 'Calcário Dolomítico', toneladas: 88.8, detalhe: null },
    { titulo: 'Fosfato', toneladas: 22.2, detalhe: null },
    { titulo: 'Blend Dolomítico', toneladas: 24.85, detalhe: 'calc. 14,91 t + gesso 9,94 t' },
  ]);
});

test('validação do formulário', () => {
  const ok = { tipo: 'blend', calcario: 'ph7', dose: '1,5', dose_gesso: '1', os: '4530', talhoes: [1] };
  assert.strictEqual(ctx.crValidarAplicacao(ok), null);
  assert.match(ctx.crValidarAplicacao({ ...ok, talhoes: [] }), /Marque ao menos um talhão/);
  assert.match(ctx.crValidarAplicacao({ ...ok, dose: '0' }), /Dose/);
  assert.match(ctx.crValidarAplicacao({ ...ok, dose_gesso: '' }), /gesso/);
  assert.match(ctx.crValidarAplicacao({ ...ok, os: '  ' }), /O\.S\./);
  assert.match(ctx.crValidarAplicacao({ ...ok, tipo: 'calcario', calcario: null }), /calcário/);
});

test('duplicadas', () => {
  assert.deepStrictEqual(ctx.crDuplicadas([DOL], { ...DOL, ordem: 9 }, [1, 2, 3]), [1, 3]);
  assert.deepStrictEqual(ctx.crDuplicadas([DOL], { ...DOL, os: '9999' }, [1]), []);
});

test('talhões fora da base', () => {
  const geo = { type: 'FeatureCollection', features: [{ properties: { talhao: 1 } }, { properties: { talhao: 2 } }] };
  assert.deepStrictEqual(ctx.crTalhoesForaDaBase({ 1: {}, 7: {} }, geo), [7]);
});

test('JSON para o gerador e nome do arquivo', () => {
  const d = ctx.crMontarDados({ codFaz: 10156, nome: 'F', operacao: 'arado', data: '2026-10-15', geradoPor: 'Ana',
                                geo: { type: 'FeatureCollection', features: [] }, areas: AREAS, apls: [DOL] });
  assert.deepStrictEqual(Object.keys(d).sort(), ['aplicacoes', 'areas', 'cod_faz', 'data', 'gerado_por', 'nome', 'operacao', 'talhoes_geo']);
  assert.strictEqual(d.areas['4'].editada, true);
  assert.strictEqual(ctx.crNomeArquivo(10156, 'arado', '2026-10-15'), 'corretivo_10156_arado_2026-10-15.pdf');
});
```

- [ ] **Step 2: Rodar e ver falhar** — `node --test tests/app/corretivos_puro.test.js` → FAIL (`ENOENT ... corretivos.js`).

- [ ] **Step 3: Implementar a seção pura de `app/corretivos.js`**

```js
// ===== Corretivos: funções puras (testadas em tests/app/corretivos_puro.test.js) =====
// `var` (não const) para as constantes ficarem visíveis no contexto vm dos testes.
var CR_CORES = { 'calcario:dolomitico': '#2f6db5', 'calcario:ph7': '#22a39f', fosfato: '#e07b1a', blend: '#7b4fb3' };
var CR_SEM = '#e4e7e8';
var CR_OPERACOES = { subsolagem: 'SubSolagem', supergrade: 'SuperGrade', arado: 'Arado' };
var CR_CALC = { dolomitico: 'Dolomítico', ph7: 'PH7' };

function crBr(v) {
  return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function crNum(s) { return typeof s === 'number' ? s : Number(String(s ?? '').trim().replace(/\./g, '').replace(',', '.')); }
function crTotal(area, dose) { return Math.round(area * dose * 100) / 100; }
function crChaveCor(ap) { return ap.tipo === 'calcario' ? 'calcario:' + ap.calcario : ap.tipo; }
function crRotulo(ap) {
  if (ap.tipo === 'calcario') return 'Calc. ' + CR_CALC[ap.calcario];
  if (ap.tipo === 'blend') return 'Blend · ' + CR_CALC[ap.calcario];
  return 'Fosfato';
}
function crOrdenadas(apls) { return [...apls].sort((a, b) => a.ordem - b.ordem); }
function crCoresTalhao(apls, talhao) {
  return crOrdenadas(apls).filter(a => a.talhoes.includes(talhao)).map(a => CR_CORES[crChaveCor(a)]);
}
function crTotaisPorProduto(apls, areas) {
  const soma = {};
  const area = a => a.talhoes.reduce((s, t) => s + Number(areas[t].area_ha), 0);
  for (const a of crOrdenadas(apls)) {
    if (a.tipo === 'blend') {
      const k = 'Blend ' + CR_CALC[a.calcario];
      const v = soma[k] || [0, 0];
      soma[k] = [v[0] + area(a) * a.dose, v[1] + area(a) * a.dose_gesso];
    } else {
      const k = a.tipo === 'fosfato' ? 'Fosfato' : 'Calcário ' + CR_CALC[a.calcario];
      soma[k] = [(soma[k] ? soma[k][0] : 0) + area(a) * a.dose];
    }
  }
  const r2 = v => Math.round(v * 100) / 100;
  return ['Calcário Dolomítico', 'Calcário PH7', 'Fosfato', 'Blend Dolomítico', 'Blend PH7'].filter(k => soma[k])
    .map(k => k.startsWith('Blend')
      ? { titulo: k, toneladas: r2(soma[k][0] + soma[k][1]), detalhe: `calc. ${crBr(soma[k][0])} t + gesso ${crBr(soma[k][1])} t` }
      : { titulo: k, toneladas: r2(soma[k][0]), detalhe: null });
}
function crValidarAplicacao(f) {
  if (!f.talhoes || !f.talhoes.length) return 'Marque ao menos um talhão no mapa.';
  if ((f.tipo === 'calcario' || f.tipo === 'blend') && !f.calcario) return 'Escolha o calcário (Dolomítico ou PH7).';
  if (!(crNum(f.dose) > 0)) return 'Dose deve ser maior que zero (t/ha).';
  if (f.tipo === 'blend' && !(crNum(f.dose_gesso) > 0)) return 'Informe a dose do gesso (t/ha).';
  if (!String(f.os ?? '').trim()) return 'Informe a O.S.';
  return null;
}
function crMesma(a, b) {
  return a.tipo === b.tipo && (a.calcario || null) === (b.calcario || null) && crNum(a.dose) === crNum(b.dose)
    && (a.dose_gesso == null ? null : crNum(a.dose_gesso)) === (b.dose_gesso == null ? null : crNum(b.dose_gesso))
    && String(a.os).trim() === String(b.os).trim();
}
function crDuplicadas(apls, nova, talhoes) {
  return talhoes.filter(t => apls.some(a => a.talhoes.includes(t) && crMesma(a, nova)));
}
function crTalhoesForaDaBase(areas, geo) {
  const naBase = new Set(geo.features.map(f => f.properties.talhao));
  return Object.keys(areas).map(Number).filter(t => !naBase.has(t)).sort((a, b) => a - b);
}
function crMontarDados(c) {
  const areas = {};
  for (const [t, v] of Object.entries(c.areas)) areas[String(t)] = { area_ha: Number(v.area_ha), editada: !!v.editada };
  return { cod_faz: c.codFaz, nome: c.nome, operacao: c.operacao, data: c.data, gerado_por: c.geradoPor,
           talhoes_geo: c.geo, areas,
           aplicacoes: crOrdenadas(c.apls).map(a => ({ tipo: a.tipo, calcario: a.calcario || null, dose: crNum(a.dose),
             dose_gesso: a.dose_gesso == null ? null : crNum(a.dose_gesso), os: String(a.os).trim(), ordem: a.ordem,
             talhoes: [...a.talhoes] })) };
}
function crNomeArquivo(codFaz, operacao, data) { return `corretivo_${codFaz}_${operacao}_${data}.pdf`; }
```

- [ ] **Step 4: Rodar** `node --test tests/app/corretivos_puro.test.js` → 7 testes passando.

- [ ] **Step 5: Commit** (`"Corretivos: funções puras da página (totais, validação, duplicadas, JSON do PDF)"`).

---

### Task 8: Página, login e lista de mapas (camada 1, `delegar.sh -a frontend`)

**Files:**
- Create: `app/corretivos.html`, `app/corretivos.css`, `app/corretivos-demo.js`
- Modify: `app/corretivos.js` (seções: estado, API, demo, lista)

**Interfaces:**
- Consumes: funções puras (Task 7); tokens visuais de `app/index.html` (variáveis CSS do `:root`: copiar as que forem usadas para `corretivos.css`, sem mudar `index.html`).
- Produces: `CR` (estado), `crApi` com `{ sessao(), entrar(email, senha), sair(), eu(), fazendas(), mapas(codFaz), criarMapa(codFaz, operacao), excluirMapa(id), carregarMapa(id), talhoesFazenda(codFaz), salvarArea(mapaId, talhao, area), aplicar(mapaId, ap, talhoes, areas), editarAplicacao(id, campos), excluirAplicacao(id) }` — implementação real (supabase-js, schema `hub`) e implementação demo (memória, dados de `corretivos-demo.js`); `crIniciar()`.
- Modo demo: ligado quando `location.protocol === 'file:'` ou `?demo=1`. Usa 2 fazendas fictícias, 6 talhões retangulares em coordenadas WGS84 perto de (-47.0, -21.5), 2 mapas na primeira fazenda, nenhum na segunda.

- [ ] **Step 1: Brief para o agente de front-end** (`delegar.sh -a frontend`):

```text
# Tela: Corretivos — página, login e lista de mapas
Objetivo: criar a página app/corretivos.html (ferramenta à parte do Hub) com login, busca de fazenda e lista de mapas de corretivo, no estilo do Hub.
Arquivos: criar app/corretivos.html, app/corretivos.css, app/corretivos-demo.js; acrescentar seções em app/corretivos.js (NÃO altere a seção "funções puras" que já existe no topo; NÃO altere app/index.html).
Contexto:
- Estilo: copie para corretivos.css as variáveis CSS do :root de app/index.html que usar (cores, raios, fonte); imite os cartões e botões de app/drone.js (classes dr-*), trocando o prefixo por cr-.
- Scripts no HTML, nesta ordem: supabase-js@2 (https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2), maplibre-gl 4.7.1 (css+js, igual a index.html), corretivos-demo.js, corretivos.js. Ícones: Material Symbols como em index.html.
- Supabase: const SB_URL e SB_KEY iguais às de app/index.html (copie de lá); client: window.supabase.createClient(SB_URL, SB_KEY, {db:{schema:'hub'}}). A sessão do Hub é compartilhada (mesmo site): se já houver sessão, entra direto.
- Modo demo: CR_DEMO = location.protocol === 'file:' || new URLSearchParams(location.search).has('demo'). Em demo, crApi usa dados de corretivos-demo.js em memória (sem rede) e mostra uma faixa discreta "Demonstração — dados fictícios".
Faça:
1. crApi real e demo com a interface: sessao(), entrar(email, senha), sair(), eu() -> {id, nome, admin, pode} (pode = admin ou tem 'corretivos' em usuario_modulos; leia hub.usuarios + usuario_modulos(modulo_id) como app/index.html faz), fazendas() -> [{cod_faz, nome}], mapas(codFaz) -> [{id, operacao, data, os:[...], talhoes:n, toneladas, alterado_por_nome, alterado_em}], criarMapa(codFaz, operacao) -> id, excluirMapa(id). (carregarMapa e as demais ficam para a próxima tarefa: deixe-as declaradas lançando Error('a fazer').)
2. Tela de login (e-mail + senha, botão Entrar, mensagem de erro em pt-BR). Sem acesso (pode=false): "Sua conta não tem acesso aos Corretivos. Peça ao administrador." + botão Sair.
3. Cabeçalho: "Corretivos" + nome do usuário + link "Voltar ao Hub" (index.html) + Sair.
4. Busca de fazenda (código ou nome, lista filtrada ao digitar). Ao escolher: lista de mapas da fazenda, mais recente primeiro. Cartão: operação como tag (SubSolagem/SuperGrade/Arado, cores suaves sem usar vermelho), data dd/mm/aaaa, O.S. (todas), nº de talhões, total em t (crBr), "alterado por <nome> em dd/mm".
5. Botão "Novo mapa" → escolher operação (3 botões) → crApi.criarMapa → abre a tela de trabalho (por enquanto, um contêiner #cr-trabalho vazio com o título "Mapa <operação> · <data>" e botão Voltar).
6. Excluir mapa no cartão (ícone lixeira): confirmação "Excluir o mapa <operação> de <data>? Isso não pode ser desfeito." → crApi.excluirMapa.
7. Estados: carregando (esqueleto), vazio ("Nenhum mapa de corretivo nesta fazenda." + Novo mapa), erro (mensagem + Tentar de novo).
8. Funciona em 390 px (sem rolagem horizontal, margem 16 px).
Verificação: `python ~/.claude/skills/delegar/foto.py app/corretivos.html .prints/lista` (abre em file:// = modo demo; deve mostrar a lista da fazenda demo escolhida automaticamente na primeira carga demo) e `node --test tests/app/corretivos_puro.test.js` (continua passando).
Não faça: nada de biblioteca nova; não mexa em index.html; nada de dados reais.
```

- [ ] **Step 2 (camada 3): revisar** diff, detector impeccable nos arquivos novos, prints (desktop, celular, escuro) e `node --test`. Correção com `-w` se preciso.

- [ ] **Step 3: Commit** (o executor commita; se ficar `SEM COMMIT DO EXECUTOR`, aceitar após revisão).

---

### Task 9: Tela de trabalho — mapa e painel de aplicações (camada 1, `delegar.sh -a frontend`)

**Files:**
- Modify: `app/corretivos.js`, `app/corretivos.css`, `app/corretivos-demo.js`

**Interfaces:**
- Consumes: Tasks 7–8 (`crApi`, funções puras).
- Produces: `crAbrirMapa(id)`, `crPintarMapa()`, `crClicarTalhao(n)`, `crAplicar()`, a implementação de `carregarMapa(id) -> {mapa, areas:{talhao:{area_ha, editada}}, apls:[...com id e talhoes]}`, `talhoesFazenda(codFaz) -> FeatureCollection` (real: `sb.rpc('corretivo_talhoes_fazenda', {p_cod_faz})`), `salvarArea`, `aplicar`, `editarAplicacao`, `excluirAplicacao` (real e demo).

- [ ] **Step 1: Brief para o agente de front-end** (`delegar.sh -a frontend`):

```text
# Tela: Corretivos — tela de trabalho (mapa + painel)
Objetivo: completar #cr-trabalho em app/corretivos.js: mapa grande à esquerda e painel à direita (layout "A" aprovado: igual à tela de fazenda do Drone em app/drone.js).
Arquivos: alterar app/corretivos.js, app/corretivos.css, app/corretivos-demo.js (só estes). NÃO altere a seção "funções puras".
Contexto:
- Mapa: MapLibre igual a drPintarMapa em app/drone.js (style inline com fundo #f7f8fa, glyphs demotiles, source geojson com promoteId 'talhao', camadas de preenchimento, contorno e número do talhão). Fonte dos talhões: crApi.talhoesFazenda(codFaz).
- Pintura: talhão com 1 aplicação = CR_CORES da aplicação; com 2+ = meio a meio na diagonal (use 'fill-pattern' gerado em canvas com as cores de crCoresTalhao em faixas diagonais iguais, registrado via map.addImage por combinação de cores); talhão do mapa sem aplicação = CR_SEM; talhão fora do mapa = branco com contorno. Selecionado = contorno verde (var da marca) mais grosso via feature-state 'sel'.
- Persistência: cada ação chama crApi e recarrega o mapa (salvamento automático, sem botão Salvar).
Faça:
1. crApi.carregarMapa, talhoesFazenda, salvarArea, aplicar, editarAplicacao, excluirAplicacao (real: tabelas hub.corretivo_mapas/_talhoes/_aplicacoes/_aplicacao_talhoes via supabase-js; aplicar = inserir os talhões que faltam em corretivo_talhoes com area_ha da área produtiva, inserir a aplicação com ordem = maior+1, inserir os vínculos; ao excluir uma aplicação, remover de corretivo_talhoes os talhões que ficaram sem nenhuma aplicação; demo: o mesmo em memória).
2. Clique no talhão marca/desmarca. Botões "Selecionar todos" e "Limpar seleção".
3. Painel "Nova aplicação": lista dos talhões marcados com a área de cada um (input numérico editável; editar chama salvarArea e marca editada); Tipo (Calcário | Fosfato | Blend) → Calcário (Dolomítico | PH7) quando calcário/blend → Dose (t/ha) → Dose do gesso (t/ha) só no Blend → O.S. → botão "Aplicar aos marcados". Valide com crValidarAplicacao; antes de gravar, crDuplicadas: se houver, mostre "Os talhões X, Y já têm esta aplicação" e não grave nesses (grava nos demais).
4. Lista das aplicações do mapa (ordem de lançamento): quadradinho da cor, crRotulo, dose(s), O.S., talhões, total em t (soma de crTotal por talhão; no Blend, calcário + gesso). Clicar destaca os talhões no mapa. Ações: editar (dose, O.S., talhões) e excluir (com confirmação).
5. Aviso no topo do painel quando crTalhoesForaDaBase não for vazio: "Talhões que saíram da Base: X. Eles continuam no PDF, sem desenho."
6. Resumo no fim do painel: crTotaisPorProduto em pequenos quadros + botão "Baixar PDF" (por enquanto desabilitado com o texto "Baixar PDF (em breve)").
7. Celular (390 px): mapa em cima (altura 50vh), painel embaixo; sem rolagem horizontal.
8. corretivos-demo.js: o mapa demo já vem com 3 aplicações (Calcário Dolomítico em 1 e 3; Fosfato em 2 e 3; Blend Dolomítico em 4 e 5) para os prints mostrarem o meio a meio.
Verificação: `python ~/.claude/skills/delegar/foto.py app/corretivos.html .prints/trabalho --esperar #cr-mapa` depois de fazer a página demo abrir direto no primeiro mapa quando a URL tiver #mapa=1 — em file:// use o hash: rode foto.py com o caminho "app/corretivos.html" e ajuste o demo para, na ausência de escolha, abrir o mapa 1 (documente isso no commit). `node --test tests/app/corretivos_puro.test.js` continua passando.
Não faça: biblioteca nova; dados reais; mudanças fora dos 3 arquivos.
```

- [ ] **Step 2 (camada 3): revisar** diff, detector, prints: conferir meio a meio no talhão 3, cores da paleta, seleção, aviso de fora da Base (forçar no demo), celular. Correção com `-w` se preciso.

---

### Task 10: Botão "Baixar PDF" com Pyodide (camada 3)

**Files:**
- Create: `app/corretivos-pdf.js`
- Modify: `app/corretivos.html` (script), `app/corretivos.js` (habilitar o botão)

**Interfaces:**
- Consumes: `app/py/manifest.json` (Task 6), `mapas.corretivo_pdf.gerar_bytes` (Task 5), `crMontarDados`, `crNomeArquivo` (Task 7).
- Produces: `crGerador.preparar() -> Promise` (idempotente, começa em segundo plano ao abrir a página), `crGerador.gerar(dados) -> Promise<Blob>`, estado `crGerador.estado` = `'parado' | 'preparando' | 'pronto' | 'erro'`.

- [ ] **Step 1: Implementar `app/corretivos-pdf.js`**

```js
// Gerador do PDF no navegador: Pyodide + mapas/corretivo_pdf.py (mesmo layout do Drone).
const crGerador = (() => {
  const VERSAO = '0.27.7';
  let py = null, promessa = null;
  const g = { estado: 'parado', erro: null, aoMudar: () => {} };
  const mudar = (estado, erro = null) => { g.estado = estado; g.erro = erro; g.aoMudar(estado); };
  function script(src) {
    return new Promise((ok, falha) => {
      const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => falha(new Error('não carregou ' + src));
      document.head.appendChild(s);
    });
  }
  async function preparar() {
    if (promessa) return promessa;
    mudar('preparando');
    promessa = (async () => {
      await script(`https://cdn.jsdelivr.net/pyodide/v${VERSAO}/full/pyodide.js`);
      py = await loadPyodide();
      await py.loadPackage(['matplotlib', 'shapely', 'pandas', 'pyproj', 'geopandas']);
      const { arquivos } = await (await fetch('py/manifest.json')).json();
      for (const rel of arquivos) {
        const dados = new Uint8Array(await (await fetch('py/' + rel)).arrayBuffer());
        py.FS.mkdirTree('/home/pyodide/' + rel.split('/').slice(0, -1).join('/'));
        py.FS.writeFile('/home/pyodide/' + rel, dados);
      }
      py.runPython(`
import sys; sys.path.insert(0, '/home/pyodide')
from matplotlib import font_manager
import glob
for f in glob.glob('/home/pyodide/mapas/fontes/*.ttf'):
    font_manager.fontManager.addfont(f)
from mapas.corretivo_pdf import gerar_bytes`);
      mudar('pronto');
    })().catch(e => { promessa = null; mudar('erro', e); throw e; });
    return promessa;
  }
  async function gerar(dados) {
    await preparar();
    py.globals.set('ENTRADA', JSON.stringify(dados));
    const bytes = py.runPython('gerar_bytes(ENTRADA)').toJs();
    return new Blob([bytes], { type: 'application/pdf' });
  }
  return Object.assign(g, { preparar, gerar });
})();
```

- [ ] **Step 2: Ligar na página** — `corretivos.html` carrega `corretivos-pdf.js` antes de `corretivos.js`. Ao entrar (login ok, fora do modo demo), `crGerador.preparar()` em segundo plano. O botão "Baixar PDF":
  - `preparando` → texto "Preparando o gerador… (só na primeira vez)" e desabilitado;
  - `pronto` → "Baixar PDF", ao clicar: `crGerador.gerar(crMontarDados(...))`, baixa com `crNomeArquivo` (link `a[download]` + `URL.createObjectURL`);
  - `erro` → "Não foi possível preparar o gerador de PDF. Os dados do mapa estão salvos." + botão "Tentar de novo" (`crGerador.preparar()`).
  - Modo demo: botão mostra "Baixar PDF (indisponível na demonstração)".

- [ ] **Step 3: Testar no navegador (camada 3)** — `python mapas/publicar.py`, servir `app/` com `python -m http.server` e abrir `http://localhost:<porta>/corretivos.html` logado com a conta de teste (Task 11 prepara o acesso). Gerar o PDF de um mapa da fazenda de teste e comparar com a amostra da Task 5 (mesmo layout). **Falha do Pyodide:** bloquear `cdn.jsdelivr.net` no DevTools (Network request blocking), recarregar e conferir a mensagem de erro e o "Tentar de novo".

- [ ] **Step 4: Commit** (`"Corretivos: PDF gerado no navegador (Pyodide) com carga em segundo plano"`).

---

### Task 11: Teste de ponta a ponta, acesso e manual (camada 3 + U)

**Files:**
- Create: `tests/app/teste_corretivos_tela.py`, `docs/corretivos-manual.md`

- [ ] **Step 1: E2E** no padrão de `tests/app/teste_drone_tela.py` (script, Edge, `HUB_CONTA_TESTE`):
  1. Salvar o estado de acesso da conta de teste (linhas em `usuario_modulos`); garantir `corretivos` durante o teste; restaurar no fim (`finally`).
  2. `python mapas/publicar.py`; servir `app/` com `http.server` em porta livre; abrir `corretivos.html`; login.
  3. Fazenda de teste 10974: criar mapa "Arado"; marcar 2 talhões que se sobrepõem a outra aplicação; lançar Calcário Dolomítico 2,0 / O.S. `E2E-1` nos talhões A e B; lançar Blend PH7 1,5 + gesso 1,0 / O.S. `E2E-2` em B; editar a área de A.
  4. Tentar lançar de novo Calcário Dolomítico 2,0 / `E2E-1` em A → a tela recusa; inserir direto pelo supabase-js a mesma aplicação em A → o banco recusa ("já tem esta aplicação").
  5. "Baixar PDF" (esperar `page.expect_download`, até 180 s na primeira carga) → abrir com PyMuPDF e conferir `CORRETIVO · ARADO`, `E2E-1`, `Blend PH7`, `*`.
  6. Excluir o mapa pela tela → conferir a linha nova em `hub.log_auditoria` (`campo='mapa_corretivo'`) e que o mapa sumiu. O teste só apaga o mapa que ele criou.
  Run: `python tests/app/teste_corretivos_tela.py` → `FALHAS: nenhuma`.
- [ ] **Step 2 (camada 1): manual** `docs/corretivos-manual.md` no estilo de `docs/drone-manual.md` (o que é, criar mapa, marcar talhões, lançar aplicação, Blend, editar área, PDF, excluir, mensagens de erro). Brief curto com a spec e esta lista.
- [ ] **Step 3 (U):** em Configurações → Ferramentas, cadastrar `{nome: "Corretivos", url: "corretivos.html", descricao: "Mapa de aplicação de corretivos para o operador de campo.", icone: "agriculture", cor: "#7b4fb3"}`; em Usuários, marcar o módulo **Corretivos** para quem vai usar.

---

### Task 12: Revisão final, merge e deploy (camada 3 + U)

- [ ] **Step 1:** Suítes: `python -m pytest -q` (inclui `tests/mapas` e a regressão do Drone), `node --test tests/app/`, E2E da Task 11.
- [ ] **Step 2:** Revisor independente (modelo mais capaz) sobre o diff inteiro da branch, com a spec e a seção Review Focus; corrigir Critical/Important com teste que falhe antes.
- [ ] **Step 3 (U):** ok para mesclar → merge na `main`, push, acompanhar o deploy do Pages (`gh run watch`), abrir `https://lmalerbo.github.io/hub-geotech/corretivos.html` e gerar um PDF real.
- [ ] **Step 4:** Atualizar a memória/ficha do projeto com o que entrou no ar e o que ficou pendente.
