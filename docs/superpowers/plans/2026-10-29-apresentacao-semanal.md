# Apresentação semanal no Hub — plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar tarefa a tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** ferramenta "Apresentação semanal" no Hub: quem tem a ferramenta liberada ajusta metas e textos, vê a prévia dos 6 slides e baixa o PPTX, sem o notebook do Leo.

**Arquitetura:** tudo no navegador. Dados do Supabase com o login do usuário (views existentes + `hub.drone_projetos_v` nova), voos do GeoMap por uma rota nova do Worker, cálculo em funções puras portadas do `gerar.py`, slides em HTML no frame Pedra, PPTX montado no navegador (cada slide vira imagem).

**Stack:** HTML/JS sem build (padrão de `app/aplicacao.html`), supabase-js@2, PptxGenJS 3.12.0 e html-to-image 1.11.11 (CDN jsdelivr, versões fixas), Postgres/Supabase (migrations SQL), Cloudflare Worker, testes `node:test` + `vm` e pytest com Postgres local.

**Spec:** `docs/superpowers/specs/2026-10-29-apresentacao-semanal-design.md`. Protótipo das telas: https://claude.ai/artifact/DBwux9Cmjqhj7LX8KMdk5E

**Fonte das regras atuais:** `Documents/GitHub/src/scripts/gerar.py` e `extrair.py` (fora deste repo; versão de 28/10). A Tarefa 7 copia o `gerar.py` para `tests/app/apresentacao/referencia/` para gerar o esperado dos testes de paridade.

## Restrições globais

- Idioma do código, comentários, mensagens e commits: português, no estilo dos arquivos vizinhos (prefixo de função por módulo: `ap` para a apresentação, como `cr` nos Corretivos).
- Módulo/ferramenta: id `apresentacao`, rótulo "Apresentação semanal"; nível único `editor` (como `corretivos`).
- Permissão: `hub.pode_usar_apresentacao()` = admin ou linha em `hub.usuario_modulos` com `modulo_id = 'apresentacao'`.
- Metas iniciais: `meta_ervas_ha` 20863, `meta_fornecedor_ha` 3500, `meta_ha_dia` 250, `drone_pendente_ha` 2000, `safra_atual` '26/27', `inicio_safra` '2026-04-01'.
- Safra vira em 1º de abril: data em abr/2026–mar/2027 → '26/27'.
- Semana: regra da quinta-feira. A semana N do mês M é a N-ésima quinta do mês; corte = dia anterior à quinta. Nome `S{N}M{M}` (ex.: 29/10/2026 → S5M10, corte 28/10/2026).
- Rodapé de todo slide: `S5M10 · Dados até 28/10/2026`. Arquivo: `s5m10 - Apresentacao Geotecnologia - Indicadores e Entregas.pptx`.
- Números em formato BR: milhar com ponto (20.863), percentual inteiro (`pct`) ou uma casa (`p1`) como no `gerar.py`.
- `INDICADORES_TOKEN` só nos secrets da Cloudflare. Nunca em código, teste ou resposta.
- Migrations aplicadas à mão no SQL Editor do Supabase, na ordem do nome, como as anteriores. Nenhuma tarefa aplica migration no banco real sem o ok do Leo.

## Foco da revisão

1. **Semana na virada de mês:** quinta no dia 1 (ex.: 01/10/2026 → S1M10, corte 30/09/2026). O corte cai no mês anterior, mas a semana é do mês da quinta.
2. **Projeto de drone sem área ou sem safra:** não pode virar `NaN` nem sumir em silêncio. Entra em "Anteriores / sem safra" (sem safra) ou fica fora da soma (sem área), e aparece listado na tela.
3. **Texto do usuário com HTML ou aspas** (`<b>`, `"`, `&`) em subtítulo, destaque ou notas: sai escapado no slide e literal nas notas do PPTX.
4. **API do GeoMap lenta (~2 min) ou com erro:** a tela não trava, os outros slides seguem editáveis, o PPTX fica bloqueado e "Tentar de novo" funciona.
5. **Dois editores na mesma semana:** salvar só os campos do slide editado (merge no jsonb), sem apagar o que o outro escreveu em outro slide.

Cada item tem teste na tarefa dona: 1 → Tarefa 6; 2 → Tarefas 3 e 6; 3 → Tarefa 7; 4 → Tarefa 8 (modo demo `?demo=voos-falha`); 5 → Tarefa 2.

---

### Tarefa 1: ferramenta `apresentacao` e permissão

**Arquivos:**
- Criar: `supabase/migrations/20261029090000_apresentacao_acesso.sql`
- Alterar: `app/index.html` (aba Ferramentas do usuário ~linha 2011-2021; `MOD_ROTULO` linha 1835), `app/usuarios.js:47`
- Testar: `tests/contas/test_apresentacao_acesso_sql.py`; `tests/contas/conftest.py:14` (acrescentar a migration)

**Interfaces:**
- Produz: `hub.pode_usar_apresentacao() returns boolean`; módulo `apresentacao` em `hub.modulos`; `hub.acesso_salvar` aceita `{"apresentacao": "editor"}` e ignora a chave no cálculo do `papel`.

- [ ] **Passo 1: teste que falha.** `tests/contas/test_apresentacao_acesso_sql.py`, usando os fixtures de `tests/contas/conftest.py` (leia o arquivo para os nomes exatos dos fixtures de banco e de usuário; siga `tests/contas/test_niveis_sql.py`):

```python
"""Ferramenta Apresentação semanal: módulo próprio, nível único editor, não muda o papel."""


def test_modulo_existe(banco):
    assert banco.execute("select nome from hub.modulos where id = 'apresentacao'").fetchone()[0] == 'Apresentação semanal'


def test_salvar_acesso_com_apresentacao_nao_vira_editor(banco, como_admin):
    como_admin("select hub.acesso_salvar(p_email => 'ap@t.local', p_nome => 'Ap', p_admin => false, "
               "p_niveis => '{\"apresentacao\": \"editor\"}'::jsonb)")
    assert banco.execute("select papel from hub.acessos where email = 'ap@t.local'").fetchone()[0] == 'leitura'


def test_apresentacao_so_aceita_editor(banco, como_admin):
    r = como_admin("select hub.acesso_salvar(p_email => 'ap2@t.local', p_nome => 'Ap', p_admin => false, "
                   "p_niveis => '{\"apresentacao\": \"leitura\"}'::jsonb)")
    assert r[0] == 'ERRO' and 'Nível inválido' in r[1]


def test_pode_usar(banco, pessoa, como):
    com, sem = pessoa(modulos=('apresentacao',)), pessoa(modulos=('plantio',))
    assert como(com, 'select hub.pode_usar_apresentacao()') == [(True,)]
    assert como(sem, 'select hub.pode_usar_apresentacao()') == [(False,)]
```

Se `tests/contas/conftest.py` não tiver `como_admin`/`pessoa`/`como`, crie-os nele copiando `pessoa` e `como` de `tests/fluxo/conftest.py:83-110`. `como_admin(sql)` = `como(uid_de_um_admin, sql)`.

- [ ] **Passo 2:** rode `python -m pytest tests/contas/test_apresentacao_acesso_sql.py -v`. Esperado: FALHA (módulo/função não existem). Precisa de `initdb` no PATH; sem ele, os testes são pulados. Nesse caso, avise e não declare a tarefa pronta.

- [ ] **Passo 3: migration.** `supabase/migrations/20261029090000_apresentacao_acesso.sql`:

```sql
-- Ferramenta Apresentação semanal (spec 2026-10-29-apresentacao-semanal-design.md, D2).
-- Módulo próprio, nível único editor (como corretivos); não conta para o papel.
begin;

insert into hub.modulos (id, nome, ordem) values ('apresentacao', 'Apresentação semanal', 7) on conflict (id) do nothing;

create or replace function hub.pode_usar_apresentacao()
returns boolean language sql stable security definer set search_path = hub as $$
  select exists (select 1 from hub.usuarios u
                  where u.id = auth.uid()
                    and (u.admin or exists (select 1 from hub.usuario_modulos m
                                             where m.usuario_id = u.id and m.modulo_id = 'apresentacao')));
$$;
revoke all on function hub.pode_usar_apresentacao() from public, anon;
grant execute on function hub.pode_usar_apresentacao() to authenticated, service_role;

-- acesso_salvar: cópia da definição de 20261023090000_niveis_por_modulo.sql (assinatura e corpo inteiros),
-- com só duas mudanças: 'corretivos' passa a ser n.key in ('corretivos', 'apresentacao')
-- (a) na checagem "Nível inválido" e (b) no cálculo de v_papel.

commit;
```

Copie para o lugar do comentário o `create or replace function hub.acesso_salvar(...)` completo de `supabase/migrations/20261023090000_niveis_por_modulo.sql`, desde a linha do `create` até o `end $$;`, com os `grant`/`revoke` que vierem logo depois. Faça só as duas trocas:
- `or (n.key = 'corretivos' and n.value #>> '{}' <> 'editor')` → `or (n.key in ('corretivos', 'apresentacao') and n.value #>> '{}' <> 'editor')`
- `where n.value = 'editor' and n.key <> 'corretivos'` → `where n.value = 'editor' and n.key not in ('corretivos', 'apresentacao')`

Depois, rode `grep -rn "'corretivos'" supabase/functions` para ver se a Edge Function `contas` tem lista de módulos fixa. Se tiver, acrescente `'apresentacao'` do mesmo jeito.

Acrescente `'20261029090000_apresentacao_acesso.sql'` ao fim de `MIGRACOES` em `tests/contas/conftest.py:14`.

- [ ] **Passo 4:** rode `python -m pytest tests/contas -v`. Esperado: tudo PASSA, inclusive os testes antigos de níveis.

- [ ] **Passo 5: tela Usuários.** Em `app/index.html`, no card "Mapas de aplicação" da aba Ferramentas (~linha 2011), acrescente uma linha igual logo abaixo da de Corretivos:

```js
    <div class="cfg-row"><div class="cfg-row-l"><div class="cfg-row-lbl">Apresentação semanal</div>
      <div class="cfg-row-sub">Edita metas e textos e baixa o PPTX da semana.</div></div>
      ${usrSwitch('u-apres',r.niveis.apresentacao==='editor','usrApresentacao(this)')}</div>
```

Mude o título do card de "Mapas de aplicação" para "Ferramentas do Hub", e o ícone para `apps`. Ao lado de `usrCorretivos`:

```js
function usrApresentacao(el){
  if(el.checked)USR.rasc.niveis.apresentacao='editor';else delete USR.rasc.niveis.apresentacao;
}
```

Também:
- `MOD_ROTULO` (linha 1835): acrescente `apresentacao:'Apresentação semanal'`;
- `app/usuarios.js:47`: depois da linha de corretivos, acrescente `if (niveis.apresentacao) partes.push('Apresentação semanal');`;
- em `tests/app/usuarios_puro.test.js`: um teste que confirme que o resumo de `{ apresentacao: 'editor' }` contém "Apresentação semanal". Use a função que contém a linha 47; leia o arquivo para pegar o nome dela.

- [ ] **Passo 6:** rode `node --test tests/app/`. Esperado: PASSA.
- [ ] **Passo 7: commit** `feat(apresentacao): ferramenta própria e permissão`.

---

### Tarefa 2: metas e rascunho da semana

**Arquivos:**
- Criar: `supabase/migrations/20261029100000_apresentacao_tabelas.sql`
- Testar: `tests/contas/test_apresentacao_tabelas_sql.py` (mesmo conftest; acrescente a migration em `MIGRACOES`)

**Interfaces:**
- Consome: `hub.pode_usar_apresentacao()` (Tarefa 1).
- Produz:
  - tabela `hub.apresentacao_metas(chave text pk, valor text, rotulo text, atualizado_por uuid, atualizado_em timestamptz)`;
  - tabela `hub.apresentacao_semanas(semana text pk, corte date, textos jsonb, atualizado_por uuid, atualizado_em timestamptz)`;
  - RPC `hub.apresentacao_texto_salvar(p_semana text, p_corte date, p_slide text, p_campo text, p_valor text) returns timestamptz`, que grava só aquele campo (merge).

- [ ] **Passo 1: teste que falha.**

```python
"""Metas e rascunho da Apresentação semanal (spec D6)."""
import json


def test_metas_iniciais(banco):
    m = dict(banco.execute('select chave, valor from hub.apresentacao_metas').fetchall())
    assert m == {'meta_ervas_ha': '20863', 'meta_fornecedor_ha': '3500', 'meta_ha_dia': '250',
                 'drone_pendente_ha': '2000', 'safra_atual': '26/27', 'inicio_safra': '2026-04-01'}


def test_sem_ferramenta_nao_le_nem_grava(pessoa, como):
    sem = pessoa(modulos=('plantio',))
    assert como(sem, 'select count(*) from hub.apresentacao_metas') == [(0,)]
    r = como(sem, "select hub.apresentacao_texto_salvar('S5M10', '2026-10-28', 'colheita', 'destaque', 'x')")
    assert r[0] == 'ERRO'


def test_dois_editores_nao_se_apagam(banco, pessoa, como):
    a, b = pessoa(modulos=('apresentacao',)), pessoa(modulos=('apresentacao',))
    como(a, "select hub.apresentacao_texto_salvar('S5M10', '2026-10-28', 'colheita', 'destaque', 'chuva na F3')")
    como(b, "select hub.apresentacao_texto_salvar('S5M10', '2026-10-28', 'plantio', 'notas', 'falar do atraso')")
    como(a, "select hub.apresentacao_texto_salvar('S5M10', '2026-10-28', 'colheita', 'notas', 'ok')")
    t = banco.execute("select textos from hub.apresentacao_semanas where semana = 'S5M10'").fetchone()[0]
    assert t == {'colheita': {'destaque': 'chuva na F3', 'notas': 'ok'}, 'plantio': {'notas': 'falar do atraso'}}


def test_campo_e_slide_validos(pessoa, como):
    a = pessoa(modulos=('apresentacao',))
    assert como(a, "select hub.apresentacao_texto_salvar('S5M10', '2026-10-28', 'xx', 'notas', 'a')")[0] == 'ERRO'
    assert como(a, "select hub.apresentacao_texto_salvar('S5M10', '2026-10-28', 'drone', 'cor', 'a')")[0] == 'ERRO'


def test_metas_editaveis_por_quem_tem_a_ferramenta(banco, pessoa, como):
    a = pessoa(modulos=('apresentacao',))
    como(a, "update hub.apresentacao_metas set valor = '2500' where chave = 'drone_pendente_ha'")
    assert banco.execute("select valor, atualizado_por is not null from hub.apresentacao_metas "
                         "where chave = 'drone_pendente_ha'").fetchone() == ('2500', True)
```

- [ ] **Passo 2:** rode `python -m pytest tests/contas/test_apresentacao_tabelas_sql.py -v`. Esperado: FALHA.

- [ ] **Passo 3: migration.**

```sql
-- Metas e rascunho da Apresentação semanal (spec 2026-10-29, D6).
begin;

create table hub.apresentacao_metas (
  chave          text primary key,
  valor          text not null,
  rotulo         text not null,
  atualizado_por uuid references hub.usuarios (id) default auth.uid(),
  atualizado_em  timestamptz not null default now()
);
insert into hub.apresentacao_metas (chave, valor, rotulo) values
  ('meta_ervas_ha', '20863', 'Ervas daninhas (ha)'),
  ('meta_fornecedor_ha', '3500', 'Fornecedor (ha)'),
  ('meta_ha_dia', '250', 'Ritmo de voo (ha/dia)'),
  ('drone_pendente_ha', '2000', 'Drone pendente (ha)'),
  ('safra_atual', '26/27', 'Safra atual'),
  ('inicio_safra', '2026-04-01', 'Início da safra');

create table hub.apresentacao_semanas (
  semana         text primary key check (semana ~ '^S[1-5]M([1-9]|1[0-2])$'),
  corte          date not null,
  textos         jsonb not null default '{}',
  atualizado_por uuid references hub.usuarios (id) default auth.uid(),
  atualizado_em  timestamptz not null default now()
);

create or replace function hub.apresentacao_carimbo()
returns trigger language plpgsql as $$
begin new.atualizado_por := auth.uid(); new.atualizado_em := now(); return new; end $$;
create trigger apresentacao_metas_carimbo before update on hub.apresentacao_metas
  for each row execute function hub.apresentacao_carimbo();

alter table hub.apresentacao_metas enable row level security;
alter table hub.apresentacao_semanas enable row level security;
create policy ferramenta on hub.apresentacao_metas for all to authenticated
  using (hub.pode_usar_apresentacao()) with check (hub.pode_usar_apresentacao());
create policy ferramenta on hub.apresentacao_semanas for select to authenticated
  using (hub.pode_usar_apresentacao());
grant select, update on hub.apresentacao_metas to authenticated;
grant select on hub.apresentacao_semanas to authenticated;

-- Grava um campo de um slide sem apagar os outros (dois editores na mesma semana).
create or replace function hub.apresentacao_texto_salvar(p_semana text, p_corte date, p_slide text, p_campo text, p_valor text)
returns timestamptz language plpgsql security definer set search_path = hub as $$
declare v_em timestamptz := now();
begin
  if not hub.pode_usar_apresentacao() then raise exception 'Sem acesso à Apresentação semanal'; end if;
  if p_slide not in ('divisoria', 'colheita', 'sistematizacao', 'plantio', 'voos', 'drone') then raise exception 'Slide inválido'; end if;
  if p_campo not in ('subtitulo', 'destaque', 'notas') then raise exception 'Campo inválido'; end if;
  insert into hub.apresentacao_semanas (semana, corte, textos, atualizado_por, atualizado_em)
  values (p_semana, p_corte, jsonb_build_object(p_slide, jsonb_build_object(p_campo, p_valor)), auth.uid(), v_em)
  on conflict (semana) do update
    set corte = excluded.corte,
        textos = hub.apresentacao_semanas.textos
                 || jsonb_build_object(p_slide, coalesce(hub.apresentacao_semanas.textos -> p_slide, '{}') || jsonb_build_object(p_campo, p_valor)),
        atualizado_por = auth.uid(), atualizado_em = v_em;
  return v_em;
end $$;
revoke all on function hub.apresentacao_texto_salvar(text, date, text, text, text) from public, anon;
grant execute on function hub.apresentacao_texto_salvar(text, date, text, text, text) to authenticated;

commit;
```

- [ ] **Passo 4:** rode `python -m pytest tests/contas -v`. Esperado: PASSA.
- [ ] **Passo 5: commit** `feat(apresentacao): metas e rascunho por semana`.

---

### Tarefa 3: drone de aplicação vira dado do Hub (`hub.drone_projetos_v`)

**Arquivos:**
- Criar: `supabase/migrations/20261029110000_drone_projetos_v.sql`
- Criar: `tests/apresentacao/__init__.py`, `tests/apresentacao/conftest.py`, `tests/apresentacao/stub_drone.sql`, `tests/apresentacao/test_drone_projetos_v_sql.py`

**Interfaces:**
- Produz:
  - colunas `hub.projeto_revisoes.area_aplicacao_ha numeric` e `safra text`;
  - função `hub.safra_de(date) returns text` (ex.: '2026-04-01' → '26/27', '2026-03-31' → '25/26');
  - view `hub.drone_projetos_v(projeto_id, cod_faz, revisao_id, documento, area_aplicacao_ha, safra, origem)`, com `origem in ('hub', 'legado', 'sem_dado')`.

- [ ] **Passo 1: stub e conftest.** `tests/apresentacao/stub_drone.sql` cria só o que a view lê das tabelas do drone, sem PostGIS. Antes de escrever, confira os nomes das colunas em `20261002090000_modulo_drone.sql:69-125`:

```sql
-- Stub das tabelas do Drone que hub.drone_projetos_v lê (a migração real usa PostGIS).
create table hub.drone_solicitacoes (
  id bigint generated always as identity primary key,
  cod_faz int, tipo text, status text, revisao_id bigint references hub.projeto_revisoes (id), concluido_em timestamptz);
create table hub.drone_geracoes (
  id bigint generated always as identity primary key,
  solicitacao_id bigint references hub.drone_solicitacoes (id), status text, resumo jsonb, concluido_em timestamptz);
```

`tests/apresentacao/conftest.py`, no padrão de `tests/preparo/conftest.py`:

```python
"""Postgres local com o fluxo de projetos + stub do Drone + drone_projetos_v."""
import pytest

from tests.fluxo import conftest as fluxo
from tests.fluxo.conftest import pg, fazenda, pessoa, como  # noqa: F401

MIGRACOES = fluxo.MIGRACOES + ['../../tests/apresentacao/stub_drone.sql', '20261029110000_drone_projetos_v.sql']


@pytest.fixture(scope='session')
def banco(pg):
    fluxo.MIGRACOES, antigas = MIGRACOES, fluxo.MIGRACOES
    try:
        con = fluxo.montar(pg, 'apresentacao')
    finally:
        fluxo.MIGRACOES = antigas
    yield con
    con.close()
```

`montar` lê `RAIZ / 'supabase' / 'migrations' / m`, por isso o caminho relativo do stub. Se o `read_text` não aceitar `..` no Windows, troque `montar` para aceitar um `Path` absoluto quando `m` for `Path`, e passe `fluxo.RAIZ / 'tests/apresentacao/stub_drone.sql'`.

- [ ] **Passo 2: teste que falha.** Leia `tests/fluxo/test_fluxo_projetos_sql.py` para ver como ele cria projeto e revisão (função `por` e afins) e use os mesmos inserts. O helper `revisao` abaixo precisa das colunas obrigatórias reais de `hub.projetos`/`hub.projeto_revisoes`; complete com o que o fluxo usa.

```python
"""hub.drone_projetos_v: ha de aplicação e safra por projeto vigente (spec D4)."""


def revisao(banco, cod, documento='normal', criado='2026-06-10 12:00-03', area=None, safra=None, vigente=True):
    pid = banco.execute("insert into hub.projetos (modulo_id, tipo, cod_faz, nome) values ('drone','individual',%s,'P') "
                        "returning id", (cod,)).fetchone()[0]
    return banco.execute("insert into hub.projeto_revisoes (projeto_id, documento, numero, vigente, criado_em, "
                         "area_aplicacao_ha, safra) values (%s,%s,1,%s,%s,%s,%s) returning id",
                         (pid, documento, vigente, criado, area, safra)).fetchone()[0]


def publicada(banco, rev, ha):
    sol = banco.execute("insert into hub.drone_solicitacoes (status, revisao_id) values ('ok', %s) returning id", (rev,)).fetchone()[0]
    banco.execute("insert into hub.drone_geracoes (solicitacao_id, status, resumo) values (%s, 'publicada', %s)",
                  (sol, f'{{"aplicacao_ha": {ha}}}'))


def linha(banco, rev):
    return banco.execute('select area_aplicacao_ha::float, safra, origem from hub.drone_projetos_v where revisao_id = %s',
                         (rev,)).fetchone()


def test_safra_vira_em_abril(banco):
    assert banco.execute("select hub.safra_de('2026-04-01'), hub.safra_de('2026-03-31')").fetchone() == ('26/27', '25/26')


def test_projeto_do_hub_usa_resumo_da_geracao(banco, fazenda):
    rev = revisao(banco, fazenda(1), criado='2026-09-02 10:00-03')
    publicada(banco, rev, 37.4)
    assert linha(banco, rev) == (37.4, '26/27', 'hub')


def test_projeto_do_legado_usa_colunas(banco, fazenda):
    rev = revisao(banco, fazenda(1), area=120.5, safra='24/25')
    assert linha(banco, rev) == (120.5, '24/25', 'legado')


def test_sem_dado_aparece_com_nulos(banco, fazenda):
    rev = revisao(banco, fazenda(1))
    assert linha(banco, rev) == (None, None, 'sem_dado')


def test_revisao_nao_vigente_fica_fora(banco, fazenda):
    rev = revisao(banco, fazenda(1), area=10, safra='26/27', vigente=False)
    assert linha(banco, rev) is None


def test_geracao_descartada_nao_conta(banco, fazenda):
    rev = revisao(banco, fazenda(1))
    sol = banco.execute("insert into hub.drone_solicitacoes (status, revisao_id) values ('ok', %s) returning id", (rev,)).fetchone()[0]
    banco.execute("insert into hub.drone_geracoes (solicitacao_id, status, resumo) values (%s,'descartada','{\"aplicacao_ha\": 5}')", (sol,))
    assert linha(banco, rev) == (None, None, 'sem_dado')
```

- [ ] **Passo 3:** rode `python -m pytest tests/apresentacao/test_drone_projetos_v_sql.py -v`. Esperado: FALHA.

- [ ] **Passo 4: migration.**

```sql
-- Drone de aplicação como dado do Hub (spec 2026-10-29, D4): ha de aplicação e safra por projeto vigente.
-- Projeto feito no Hub: ha do resumo da geração publicada; safra pela data da revisão.
-- Projeto do legado: colunas preenchidas uma vez por drone/carga_area_safra.py.
begin;

alter table hub.projeto_revisoes add column if not exists area_aplicacao_ha numeric;
alter table hub.projeto_revisoes add column if not exists safra text check (safra is null or safra ~ '^\d\d/\d\d$');

create or replace function hub.safra_de(p date)
returns text language sql immutable as $$
  select lpad((a % 100)::text, 2, '0') || '/' || lpad(((a + 1) % 100)::text, 2, '0')
    from (select case when extract(month from p) >= 4 then extract(year from p)::int
                      else extract(year from p)::int - 1 end as a) s;
$$;

create or replace view hub.drone_projetos_v with (security_invoker = true) as
select p.id as projeto_id, p.cod_faz, r.id as revisao_id, r.documento,
       coalesce(r.area_aplicacao_ha, (g.resumo ->> 'aplicacao_ha')::numeric) as area_aplicacao_ha,
       coalesce(r.safra, case when g.id is not null
                              then hub.safra_de((r.criado_em at time zone 'America/Sao_Paulo')::date) end) as safra,
       case when r.area_aplicacao_ha is not null then 'legado'
            when g.id is not null then 'hub'
            else 'sem_dado' end as origem
  from hub.projetos p
  join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente
  left join lateral (
    select g.id, g.resumo
      from hub.drone_solicitacoes s
      join hub.drone_geracoes g on g.solicitacao_id = s.id and g.status = 'publicada'
     where s.revisao_id = r.id
     order by g.concluido_em desc nulls last, g.id desc
     limit 1) g on true
 where p.modulo_id = 'drone' and p.tipo = 'individual';

grant select on hub.drone_projetos_v to authenticated;

commit;
```

Se `hub.projeto_revisoes` tiver `documento` com outros valores no drone (ex.: PDF), confira em `arquivos_vigentes`. O slide soma todos os documentos de drone, como o `gerar.py`; não filtre.

- [ ] **Passo 5:** rode `python -m pytest tests/apresentacao tests/fluxo -v`. Esperado: PASSA.
- [ ] **Passo 6: commit** `feat(drone): view drone_projetos_v com ha de aplicação e safra`.

---

### Tarefa 4: carga única do legado (`drone/carga_area_safra.py`)

**Arquivos:**
- Criar: `drone/carga_area_safra.py`
- Testar: `tests/drone/test_carga_area_safra.py`

**Interfaces:**
- Consome: colunas da Tarefa 3; `hub.arquivos_vigentes` (`projeto_id`, `modulo_id`, `documento`, `revisao_id`, `release_url`, `nome_arquivo`); `hub.projeto_revisoes.motivo`; `drone.banco.DroneBanco` (`selecionar`, `atualizar`; leia `drone/banco.py` para as assinaturas exatas).
- Produz:
  - `area_do_zip(conteudo: bytes) -> float | None`: soma do campo de área ("Área Apli" ou o primeiro campo que começa com "área"/"area", sem distinguir maiúsculas); `None` se nenhum campo for achado;
  - `safra_do_motivo(motivo: str | None) -> str | None`;
  - CLI `python -m drone.carga_area_safra [--aplicar]`. Sem `--aplicar`, só imprime o relatório.

- [ ] **Passo 1: teste que falha.**

```python
"""Carga única de área e safra dos projetos de drone do legado (spec D4)."""
import io
import zipfile

import geopandas as gpd
from shapely.geometry import box

from drone.carga_area_safra import area_do_zip, safra_do_motivo


def zip_com(tmp_path, campo, valores):
    gdf = gpd.GeoDataFrame({campo: valores}, geometry=[box(i, 0, i + 1, 1) for i in range(len(valores))], crs=4326)
    gdf.to_file(tmp_path / 'ap.shp', encoding='utf-8')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for ext in ('shp', 'shx', 'dbf', 'prj', 'cpg'):
            if (tmp_path / f'ap.{ext}').exists():
                z.write(tmp_path / f'ap.{ext}', f'ap.{ext}')
    return buf.getvalue()


def test_soma_area_apli(tmp_path):
    assert area_do_zip(zip_com(tmp_path, 'Área Apli', [10.5, 2.25])) == 12.75


def test_campo_area_qualquer_caixa(tmp_path):
    assert area_do_zip(zip_com(tmp_path, 'AREA_HA', [3.0])) == 3.0


def test_sem_campo_de_area(tmp_path):
    assert area_do_zip(zip_com(tmp_path, 'TALHAO', [1])) is None


def test_safra_do_motivo():
    assert safra_do_motivo('Importado do legado: .../2025-2026/Rev2') == '25/26'
    assert safra_do_motivo('Importado do legado: 24/25 Rev1 e 25/26 Rev3') == '25/26'
    assert safra_do_motivo('Importado do legado') is None
    assert safra_do_motivo(None) is None
```

- [ ] **Passo 2:** rode `python -m pytest tests/drone/test_carga_area_safra.py -v`. Esperado: FALHA (módulo não existe).

- [ ] **Passo 3: implementação.**

```python
"""Carga ÚNICA de área de aplicação e safra dos projetos de drone vindos do legado (spec 2026-10-29, D4).

Projetos feitos no Hub não precisam: hub.drone_projetos_v lê o resumo da geração publicada.
Uso, da raiz do repositório:
    python -m drone.carga_area_safra            # só mostra o que faria
    python -m drone.carga_area_safra --aplicar  # grava em hub.projeto_revisoes
"""
import io
import re
import sys
import zipfile

import requests
import shapefile

from drone.banco import DroneBanco


def area_do_zip(conteudo):
    """Soma do campo de área de todos os .shp do ZIP; None se nenhum tiver campo de área."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    nomes = z.namelist()
    total, achou = 0.0, False
    for base in [n[:-4] for n in nomes if n.lower().endswith('.shp')]:
        parte = {e: io.BytesIO(z.read(next(n for n in nomes if n.lower() == (base + e).lower())))
                 for e in ('.shp', '.dbf', '.shx')}
        sf = shapefile.Reader(shp=parte['.shp'], dbf=parte['.dbf'], shx=parte['.shx'], encoding='utf-8')
        campo = next((f[0] for f in sf.fields[1:] if f[0].lower().startswith(('área', 'area'))), None)
        if campo:
            achou = True
            total += sum(float(r[campo] or 0) for r in sf.records())
    return round(total, 2) if achou else None


def safra_do_motivo(motivo):
    """Safra registrada na importação do legado: '2025-2026' na pasta de origem ou '25/26 Rev'."""
    motivo = motivo or ''
    s = re.findall(r'(?<!\d)(20\d\d)-(20\d\d)(?!\d)', motivo)
    if s:
        return f'{s[-1][0][2:]}/{s[-1][1][2:]}'
    s = re.findall(r'(\d\d/\d\d) Rev', motivo)
    return max(s) if s else None


def main(aplicar):
    b = DroneBanco()
    vig = [r for r in b.selecionar('arquivos_vigentes', '*', {'modulo_id': 'eq.drone'})
           if r['nome_arquivo'].lower().endswith('.zip')]
    view = {r['revisao_id']: r for r in b.selecionar('drone_projetos_v', 'revisao_id,origem', {})}
    ok, falhas = 0, []
    for r in vig:
        if view.get(r['revisao_id'], {}).get('origem') != 'sem_dado':
            continue   # já tem dado (Hub ou carga anterior)
        rev = b.selecionar('projeto_revisoes', 'id,motivo', {'id': f"eq.{r['revisao_id']}"})[0]
        try:
            area = area_do_zip(requests.get(r['release_url'], timeout=60).content)
        except Exception as e:  # noqa: BLE001  ZIP corrompido ou fora do ar: lista e segue
            falhas.append((r['revisao_id'], r['cod_faz'], f'zip: {str(e)[:80]}'))
            continue
        safra = safra_do_motivo(rev['motivo'])
        if area is None or safra is None:
            falhas.append((r['revisao_id'], r['cod_faz'], f'area={area} safra={safra}'))
            continue
        if aplicar:
            b.atualizar('projeto_revisoes', {'id': f"eq.{r['revisao_id']}"}, {'area_aplicacao_ha': area, 'safra': safra})
        ok += 1
    print(f"{'gravados' if aplicar else 'a gravar'}: {ok} · sem dado: {len(falhas)}")
    for f in falhas:
        print('  ', *f)


if __name__ == '__main__':
    main('--aplicar' in sys.argv)
```

Confira em `drone/banco.py` os nomes e a ordem dos parâmetros de `selecionar` e `atualizar` (`tests/app/teste_corretivos_tela.py:29` usa `selecionar(tabela, colunas, filtros)`). Se `atualizar` tiver outra ordem, ajuste a chamada. `pyshp` (`shapefile`) e `requests` já estão em `drone/requirements.txt`; se faltar algum, acrescente.

- [ ] **Passo 4:** rode `python -m pytest tests/drone/test_carga_area_safra.py -v`. Esperado: PASSA.
- [ ] **Passo 5: commit** `feat(drone): carga única de área e safra do legado`.
- [ ] **Passo 6 (manual, com o Leo):** depois de aplicar a migration da Tarefa 3, rode sem `--aplicar` e mostre o relatório. Só rode com `--aplicar` com o ok dele.

---

### Tarefa 5: rota `/voos-indicadores` no Worker

**Arquivos:**
- Alterar: `worker/arquivos.js` (roteamento, linhas 21-34; comentário do topo)
- Testar: `tests/worker/voos.test.js`

**Interfaces:**
- Consome: `hub.pode_usar_apresentacao()` (RPC `rpc/pode_usar_apresentacao` com o JWT do usuário, pelo helper `banco` já existente).
- Produz: `GET /voos-indicadores?de=YYYY-MM-DD&ate=YYYY-MM-DD` com `Authorization: Bearer <jwt>`. Respostas:
  - 200 com o JSON do GeoMap, intacto;
  - 401 sem token;
  - 403 sem a ferramenta;
  - 400 com datas inválidas;
  - 502 se o GeoMap falhar, com `{erro}`.
- Exporta, para teste: `voosIndicadores(req, env, buscar = fetch)`.

- [ ] **Passo 1: teste que falha.** O Worker é ESM (`export default`) e o repo não tem `package.json`. O teste troca os `export` por `module.exports` e roda num `vm`, como os outros testes de `tests/app`:

```js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fonte = fs.readFileSync(path.join(__dirname, '../../worker/arquivos.js'), 'utf8')
  .replace('export default {', 'module.exports.padrao = {')
  .replace('export async function voosIndicadores', 'module.exports.voosIndicadores = async function voosIndicadores');
const mod = { exports: {} };
vm.runInNewContext(fonte, { module: mod, URL, Response, fetch: () => { throw new Error('sem rede'); }, console });
const { voosIndicadores } = mod.exports;
const ENV = { SUPABASE_URL: 'https://x.supabase.co', SUPABASE_ANON_KEY: 'anon', INDICADORES_TOKEN: 'segredo-123' };
const req = (q, token = 'jwt') => new Request(`https://w/voos-indicadores?${q}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });

function buscarFalso({ pode = true, geomap = { status: 200, corpo: { resumo: { realizadoHa: 10 } } } } = {}) {
  const chamadas = [];
  const f = async (url, op = {}) => {
    chamadas.push({ url: String(url), op });
    if (String(url).includes('/rpc/pode_usar_apresentacao')) return new Response(JSON.stringify(pode), { status: 200 });
    return new Response(JSON.stringify(geomap.corpo), { status: geomap.status });
  };
  f.chamadas = chamadas;
  return f;
}

test('sem token: 401', async () => {
  const r = await voosIndicadores(req('de=2026-04-01&ate=2026-10-28', null), ENV, buscarFalso());
  assert.strictEqual(r.status, 401);
});

test('sem a ferramenta: 403 e não chama o GeoMap', async () => {
  const b = buscarFalso({ pode: false });
  const r = await voosIndicadores(req('de=2026-04-01&ate=2026-10-28'), ENV, b);
  assert.strictEqual(r.status, 403);
  assert.ok(!b.chamadas.some((c) => c.url.includes('geomap')));
});

test('datas inválidas: 400', async () => {
  const r = await voosIndicadores(req('de=ontem&ate=2026-10-28'), ENV, buscarFalso());
  assert.strictEqual(r.status, 400);
});

test('repassa ao GeoMap com o token e não o devolve', async () => {
  const b = buscarFalso();
  const r = await voosIndicadores(req('de=2026-04-01&ate=2026-10-28'), ENV, b);
  const corpo = await r.text();
  assert.strictEqual(r.status, 200);
  assert.deepStrictEqual(JSON.parse(corpo), { resumo: { realizadoHa: 10 } });
  const g = b.chamadas.find((c) => c.url.includes('geomap'));
  assert.strictEqual(g.op.headers['x-indicadores-token'], 'segredo-123');
  assert.ok(g.url.includes('de=2026-04-01') && g.url.includes('ate=2026-10-28'));
  assert.ok(!corpo.includes('segredo-123'));
});

test('GeoMap com erro: 502', async () => {
  const r = await voosIndicadores(req('de=2026-04-01&ate=2026-10-28'), ENV, buscarFalso({ geomap: { status: 500, corpo: {} } }));
  assert.strictEqual(r.status, 502);
});
```

- [ ] **Passo 2:** rode `node --test tests/worker/`. Esperado: FALHA (`voosIndicadores` não existe).

- [ ] **Passo 3: implementação.** Em `worker/arquivos.js`:
  - no comentário do topo, acrescente o parágrafo "Também serve GET /voos-indicadores (Apresentação semanal): confere a ferramenta do usuário e repassa à API do GeoMap com o segredo INDICADORES_TOKEN, que nunca sai do Worker."
  - na lista de variáveis, cite `INDICADORES_TOKEN (secret)`;
  - no `fetch`, depois da linha do `/ver`:

```js
    if (req.method === 'GET' && url.pathname === '/voos-indicadores') {
      const r = await voosIndicadores(req, env);
      for (const [k, v] of Object.entries(cors)) r.headers.set(k, v);
      return r;
    }
```

  - e a função, perto de `ver`:

```js
const GEOMAP_VOOS = 'https://geomap-docker.onrender.com/integracao/voos/indicadores';

// Apresentação semanal: voos do GeoMap. Quem pode é decidido pelo banco (hub.pode_usar_apresentacao).
export async function voosIndicadores(req, env, buscar = fetch) {
  const token = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!token) return json({ erro: 'Entre no Hub' }, 401, {});
  const url = new URL(req.url);
  const de = url.searchParams.get('de') || '', ate = url.searchParams.get('ate') || '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(de) || !/^\d{4}-\d{2}-\d{2}$/.test(ate)) return json({ erro: 'Datas inválidas' }, 400, {});
  const p = await buscar(`${env.SUPABASE_URL}/rest/v1/rpc/pode_usar_apresentacao`, {
    method: 'POST',
    headers: { apikey: env.SUPABASE_ANON_KEY, Authorization: `Bearer ${token}`, 'Content-Profile': 'hub', 'Content-Type': 'application/json' },
    body: '{}',
  });
  if (p.status === 401) return json({ erro: 'Sessão expirada' }, 401, {});
  if (!p.ok || (await p.json()) !== true) return json({ erro: 'Sem acesso à Apresentação semanal' }, 403, {});
  const g = await buscar(`${GEOMAP_VOOS}?de=${de}&ate=${ate}`, { headers: { 'x-indicadores-token': env.INDICADORES_TOKEN } });
  if (!g.ok) return json({ erro: `GeoMap respondeu ${g.status}` }, 502, {});
  return new Response(await g.text(), { status: 200, headers: { 'Content-Type': 'application/json' } });
}
```

Não use o helper `banco` aqui: ele não recebe `buscar` e o teste precisa injetar. A demora de ~2 min fica no navegador (Tarefa 8); o Worker só espera a resposta.

- [ ] **Passo 4:** rode `node --test tests/worker/ tests/app/`. Esperado: PASSA.
- [ ] **Passo 5: commit** `feat(worker): rota /voos-indicadores para a Apresentação semanal`.
- [ ] **Passo 6 (manual, Leo):** criar o secret `INDICADORES_TOKEN` na Cloudflare (Settings → Variables and Secrets). O valor está no `.env.hub.txt` do notebook. Depois, testar com `curl` usando um JWT real.

---

### Tarefa 6: cálculo puro (`app/apresentacao-calculo.js`)

**Arquivos:**
- Criar: `app/apresentacao-calculo.js`
- Testar: `tests/app/apresentacao_calculo.test.js`

**Interfaces:**
- Produz, como funções globais (sem `module.exports`; os testes carregam via `vm`, como `corretivos.js`):
  - `apSemana(hoje: Date) -> { semana: 'S5M10', corte: '2026-10-28', quinta: '2026-10-29' }`: a quinta da semana é a última quinta ≤ hoje;
  - `apN(x) -> '20.863'`, `apPct(a, b) -> int`, `apP1(x) -> '12.5'` (como `n`, `pct` e `p1` do `gerar.py`);
  - `apAgregar(D, metas) -> A`, com `D = { talhoes, colheita_talhoes, talhao_plantio, talhao_preparo, etapas, preparo_entregas, drone, voos }` (as mesmas tabelas do `extrair.py` + `drone` = linhas de `hub.drone_projetos_v`) e `metas` = `{ meta_ervas_ha: number, meta_fornecedor_ha, meta_ha_dia, drone_pendente_ha, safra_atual: '26/27', inicio_safra: '2026-04-01' }`;
  - `A` tem a mesma forma do `agregar()` do `gerar.py` (`A.colheita`, `A.plantio`, `A.preparo`, `A.drone`, `A.voos`), com chaves de dicionário iguais às do Python, mais `A.drone.sem_dado = [{ cod_faz, documento, revisao_id }]`;
  - `apVoosNumeros(A, metas) -> [realizado, previsto, fora, forn]` (como `voos_numeros`).

- [ ] **Passo 1: teste que falha.**

```js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ console });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/apresentacao-calculo.js'), 'utf8'), ctx);
const igual = (a, e) => assert.deepStrictEqual(JSON.parse(JSON.stringify(a)), e);
const METAS = { meta_ervas_ha: 20863, meta_fornecedor_ha: 3500, meta_ha_dia: 250, drone_pendente_ha: 2000,
                safra_atual: '26/27', inicio_safra: '2026-04-01' };
const VAZIO = { talhoes: [], colheita_talhoes: [], talhao_plantio: [], talhao_preparo: [], etapas: [], preparo_entregas: [],
                drone: [], voos: { resumo: { realizadoHa: 0, aVoarHa: 0 }, porTipo: [] } };

test('semana pela regra da quinta-feira', () => {
  igual(ctx.apSemana(new Date(2026, 9, 29)), { semana: 'S5M10', corte: '2026-10-28', quinta: '2026-10-29' });
  igual(ctx.apSemana(new Date(2026, 9, 27)), { semana: 'S4M10', corte: '2026-10-21', quinta: '2026-10-22' });
  igual(ctx.apSemana(new Date(2026, 9, 1)), { semana: 'S1M10', corte: '2026-09-30', quinta: '2026-10-01' });
  igual(ctx.apSemana(new Date(2026, 10, 3)), { semana: 'S5M10', corte: '2026-10-28', quinta: '2026-10-29' });
});

test('formato BR', () => {
  assert.strictEqual(ctx.apN(20863), '20.863');
  assert.strictEqual(ctx.apN(1234567.6), '1.234.568');
  assert.strictEqual(ctx.apPct(1, 3), 33);
  assert.strictEqual(ctx.apPct(1, 0), 0);
  assert.strictEqual(ctx.apP1(12.46), '12.5');
});

test('colheita: BIS soma na frente, Sem Linhas não é concluído', () => {
  const A = ctx.apAgregar({ ...VAZIO, colheita_talhoes: [
    { cod_faz: 1, status: 'CONCLUIDO', area_ha: 10, frente: '3', periodo_op: 5 },
    { cod_faz: 1, status: 'SEM LINHAS', area_ha: 4, frente: 'BIS - 3', periodo_op: 5 },
    { cod_faz: 2, status: 'CONCLUIDO', area_ha: 6, frente: 'FOCA 1', periodo_op: 6 },
  ] }, METAS);
  igual(A.colheita.frente['Frente 3'], { CONCLUIDO: 10, 'SEM LINHAS': 4 });
  igual(A.colheita.frente.FOCA, { CONCLUIDO: 6 });
  assert.strictEqual(A.colheita.faz_conc, 1);
  assert.strictEqual(A.colheita.total, 20);
});

test('plantio: status e mês', () => {
  const A = ctx.apAgregar({ ...VAZIO, talhoes: [{ layer: 1001, cod_faz: 1, area_ha: 5 }, { layer: 1002, cod_faz: 1, area_ha: 3 }],
    talhao_plantio: [{ layer: 1001, projeto: 'Ok', mes_plantio: '2026-10-01' }, { layer: 1002, projeto: 'Pendente', mes_plantio: null }] }, METAS);
  igual(A.plantio.status, { Ok: 5, Pendente: 3 });
  igual(Object.keys(A.plantio.mes), ['2026-10', 'Indef']);
});

test('preparo: entregue = Ok; ciclo 25-26 fora; mês pela data de São Paulo', () => {
  const A = ctx.apAgregar({ ...VAZIO,
    talhoes: [{ layer: 1001, cod_faz: 1, area_ha: 5 }, { layer: 1002, cod_faz: 1, area_ha: 3 }, { layer: 1003, cod_faz: 1, area_ha: 2 }],
    etapas: [{ modulo_id: 'preparo', nome: 'Preparo', ordem: 1 }],
    talhao_preparo: [{ layer: 1001, etapa: 'Ok' }, { layer: 1002, etapa: 'Preparo' }, { layer: 1003, etapa: 'Ok' }],
    preparo_entregas: [{ layer: 1001, origem: 'hub', entregue_em: '2026-10-01T02:00:00Z' },
                       { layer: 1003, origem: 'ciclo_25_26', entregue_em: '2025-08-01T12:00:00Z' }] }, METAS);
  igual(A.preparo.etapa.Entregue, [1, 5]);
  assert.strictEqual(A.preparo.fora_25_26, 2);
  igual(A.preparo.mes, { '2026-09': 5 });   // 02:00 UTC de 01/10 = 23:00 de 30/09 em SP
});

test('drone: soma por safra, sem dado listado e fora da soma', () => {
  const A = ctx.apAgregar({ ...VAZIO, drone: [
    { cod_faz: 1, documento: 'normal', revisao_id: 1, area_aplicacao_ha: 10.4, safra: '26/27' },
    { cod_faz: 2, documento: 'catacao', revisao_id: 2, area_aplicacao_ha: 5.3, safra: '26/27' },
    { cod_faz: 3, documento: 'normal', revisao_id: 3, area_aplicacao_ha: 7, safra: null },
    { cod_faz: 4, documento: 'normal', revisao_id: 4, area_aplicacao_ha: null, safra: null },
  ] }, METAS);
  assert.strictEqual(A.drone.por_safra['26/27'], 15);   // arredonda por (documento, safra), como o gerar.py
  assert.strictEqual(A.drone.por_safra['?'], 7);
  igual(A.drone.sem_dado.map((x) => x.revisao_id), [4]);
  assert.strictEqual(A.drone.n_base, 4);
  assert.ok(!Number.isNaN(A.drone.por_safra['26/27']));
});

test('voos: fornecedor fora da programação usa a meta', () => {
  const A = ctx.apAgregar({ ...VAZIO, voos: { resumo: { realizadoHa: 100, aVoarHa: 50 },
    porTipo: [{ tipo: 'Falhas Plantio Forn.', realizadoHa: 1000, aVoarHa: 500 }] } }, METAS);
  const [real, prev, fora] = ctx.apVoosNumeros(A, METAS);
  assert.deepStrictEqual([real, prev, fora], [100, 2050, 2000]);
});
```

- [ ] **Passo 2:** rode `node --test tests/app/apresentacao_calculo.test.js`. Esperado: FALHA.

- [ ] **Passo 3: implementação.** Porte `agregar()`, `n`, `pct`, `p1` e `voos_numeros` de `src/scripts/gerar.py` (linhas 44-170 e `voos_numeros`) para JS, linha a linha, com as mesmas chaves. As diferenças são:
  - **drone:** em vez de `arquivos_vigentes` + `area_drone` + `safra(rv)`, use `D.drone` (linhas da view):
    - `safra = linha.safra ?? '?'`;
    - linhas com `area_aplicacao_ha == null` vão para `sem_dado` e não somam;
    - `n_base` conta todas as linhas;
    - `faz_base` conta os `cod_faz` distintos de todas as linhas;
    - mantém o arredondamento por `(documento, safra)` antes de somar por safra;
  - **início do ciclo:** sai de `metas.inicio_safra`, não de `hoje`;
  - **voos:** `META_FORN` vira `metas.meta_fornecedor_ha`.
  - Mês em São Paulo: `new Date(iso)` deslocado em −3 h (`new Date(Date.parse(iso) - 3 * 3600e3).toISOString().slice(0, 7)`), como o Python.
  - `apSemana(hoje)`: volte de `hoje` até a quinta-feira mais recente (`getDay() === 4`); N = `Math.ceil(dia / 7)`; M = mês da quinta; corte = quinta − 1 dia; datas em `YYYY-MM-DD` pelo horário local (não use `toISOString`, que é UTC).
  - Comentário no topo: "Regras da Apresentação semanal, sem DOM (testadas em tests/app/apresentacao_calculo.test.js). Porte de agregar() do gerar.py de 28/10/2026." Liste as regras da spec ("Regras portadas").

- [ ] **Passo 4:** rode `node --test tests/app/`. Esperado: PASSA.
- [ ] **Passo 5: commit** `feat(apresentacao): cálculo dos indicadores`.

---

### Tarefa 7: slides em HTML (`app/apresentacao-slides.js`) com paridade com o `gerar.py`

**Arquivos:**
- Criar: `app/apresentacao-slides.js`, `app/apresentacao-slides.css`, `app/assets/pedra/` (`banner.png`, `logo.png`, copiados de `src/assets/`)
- Criar: `tests/app/apresentacao/referencia/gerar.py` (cópia do `src/scripts/gerar.py`), `tests/app/apresentacao/dados/*.json` (fixture pequena, sintética), `tests/app/apresentacao/gerar_esperado.py`, `tests/app/apresentacao/esperado/*.html`
- Testar: `tests/app/apresentacao_slides.test.js`

**Interfaces:**
- Consome: `apAgregar`, `apN`, `apPct`, `apP1`, `apVoosNumeros` (Tarefa 6).
- Produz:
  - `AP_SLIDES = ['divisoria', 'colheita', 'sistematizacao', 'plantio', 'voos', 'drone']`;
  - `AP_TITULOS`: objeto chave → título, iguais aos `<h1>` do `Preview.html`;
  - `apSubtituloPadrao(chave) -> string`;
  - `apCorpo(chave, A, metas, ctx) -> string`: só o miolo, idêntico ao que `gerar.py` gera para aquele slide;
  - `apSlide(chave, A, metas, textos, ctx) -> string`: frame completo; `ctx = { semana, corte, num }`, `textos = { subtitulo?, destaque? }`;
  - `apEsc(texto) -> string`.

- [ ] **Passo 1: fixture e esperado.**
  - Monte `tests/app/apresentacao/dados/` com 3 fazendas e poucos talhões, cobrindo: BIS, FOCA, Sem Linhas, ciclo 25-26, lançamento inicial, um projeto de drone sem safra e voos com fornecedor. Use os nomes de arquivo do `extrair.py`, mais `drone.json` (linhas da view) e `area_drone.json`/`arquivos_vigentes.json`/`projeto_revisoes.json` equivalentes, para o Python chegar nos mesmos números.
  - `gerar_esperado.py`:
    - recebe a pasta `dados`;
    - monta `sys.argv = ['gerar.py', 'S5M10', '2026-10-28']`;
    - aponta `DADOS` para a fixture (`import importlib.util` → carrega `referencia/gerar.py` como módulo, depois `mod.DADOS = Path(...)`) e fixa a data de hoje do Preparo em 2026-10-29;
    - roda `A = mod.agregar()` e grava `esperado/<chave>.html` com o retorno de `mod.divisoria(A)`, `mod.colheita(A)`, `mod.sistematizacao(A)`, `mod.plantio(A)`, `mod.voos(A)` e `mod.drone(A)`.
  - Rode `python tests/app/apresentacao/gerar_esperado.py` e commite os `.html`. O `gerar.py` lê `sys.argv` no import, por isso o argv vem antes.

- [ ] **Passo 2: teste que falha.**

```js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ console });
for (const f of ['apresentacao-calculo.js', 'apresentacao-slides.js'])
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app', f), 'utf8'), ctx);
const pasta = path.join(__dirname, 'apresentacao');
const ler = (n) => JSON.parse(fs.readFileSync(path.join(pasta, 'dados', `${n}.json`), 'utf8'));
const D = { talhoes: ler('talhoes'), colheita_talhoes: ler('colheita_talhoes'), talhao_plantio: ler('talhao_plantio'),
            talhao_preparo: ler('talhao_preparo'), etapas: ler('etapas'), preparo_entregas: ler('preparo_entregas'),
            drone: ler('drone'), voos: ler('voos') };
const METAS = { meta_ervas_ha: 20863, meta_fornecedor_ha: 3500, meta_ha_dia: 250, drone_pendente_ha: 2000,
                safra_atual: '26/27', inicio_safra: '2026-04-01' };
const A = ctx.apAgregar(D, METAS);
const CTX = { semana: 'S5M10', corte: '2026-10-28' };

for (const chave of ['divisoria', 'colheita', 'sistematizacao', 'plantio', 'voos', 'drone']) {
  test(`paridade com o gerar.py: ${chave}`, () => {
    const esperado = fs.readFileSync(path.join(pasta, 'esperado', `${chave}.html`), 'utf8');
    assert.strictEqual(ctx.apCorpo(chave, A, METAS, CTX), esperado);
  });
}

test('frame: título, rodapé, número e subtítulo padrão', () => {
  const h = ctx.apSlide('colheita', A, METAS, {}, { ...CTX, num: 2 });
  assert.ok(h.includes(ctx.AP_TITULOS.colheita));
  assert.ok(h.includes('S5M10 · Dados até 28/10/2026'));
  assert.ok(h.includes(ctx.apSubtituloPadrao('colheita')));
});

test('texto do usuário sai escapado', () => {
  const h = ctx.apSlide('drone', A, METAS, { subtitulo: '<b>x</b> & "y"', destaque: '<img src=x onerror=alert(1)>' }, { ...CTX, num: 6 });
  assert.ok(h.includes('&lt;b&gt;x&lt;/b&gt; &amp; &quot;y&quot;'));
  assert.ok(!h.includes('<img src=x'));
});

test('sem destaque, sem caixa de destaque', () => {
  assert.ok(!ctx.apSlide('plantio', A, METAS, { destaque: '  ' }, { ...CTX, num: 4 }).includes('ap-destaque'));
});
```

- [ ] **Passo 3:** rode `node --test tests/app/apresentacao_slides.test.js`. Esperado: FALHA.

- [ ] **Passo 4: implementação.**
  - Porte de `gerar.py` as funções `kpi`, `progresso`, `colunas`, `linhas`, `legenda`, `painel`, `fonte`, `subtitulo`, `rot_mes`, `colheita`, `sistematizacao`, `plantio`, `voos`, `drone` e `divisoria` (linhas 172-466) para template strings JS. A saída tem que ser idêntica byte a byte; é isso que o teste de paridade confere.
  - O subtítulo que cada função gera com `subtitulo(...)` vira o padrão de `apSubtituloPadrao`. Em `apSlide`, quando `textos.subtitulo` vier preenchido, ele substitui o padrão (escapado com `apEsc`).
  - O frame (banner, selo do logo, régua lateral de 8px, rodapé de 48px) sai do `<section>` do `src/Apresentacao Geotecnologia - Preview.html`. Copie a marcação e o CSS de um slide para `apSlide` e `app/apresentacao-slides.css`, com o slide em 1920×1080 e `transform: scale()` na prévia. Siga o memorial do design system: banner de 136px com `assets/pedra/banner.png`, selo branco com `assets/pedra/logo.png` de ~72px, régua `linear-gradient(180deg,#019640,#7BBB34)`, fonte Jost com fallback Century Gothic.
  - O destaque entra antes do rodapé: `<div class="ap-destaque">${apEsc(destaque)}</div>`, só quando `destaque.trim()` não for vazio.
  - `apEsc` troca `& < > " '`.

- [ ] **Passo 5:** rode `node --test tests/app/`. Esperado: PASSA.
- [ ] **Passo 6: commit** `feat(apresentacao): slides no frame Pedra com paridade do gerar.py`.

---

### Tarefa 8: tela, dados, rascunho e PPTX (`app/apresentacao.html`)

**Arquivos:**
- Criar: `app/apresentacao.html`, `app/apresentacao.css`, `app/apresentacao.js` (telas e eventos), `app/apresentacao-dados.js` (busca real e demo), `app/apresentacao-exportar.js`, `app/apresentacao-demo.js` (dados da fixture da Tarefa 7, embutidos)
- Testar: `tests/app/apresentacao_dados.test.js`, `tests/app/teste_apresentacao_tela.py` (Playwright, modo demo, sem banco)

**Interfaces:**
- Consome: Tarefas 2, 3, 5, 6 e 7.
- Produz, em `apresentacao-dados.js`:
  - `apFontes(cliente, semana, corte, workerUrl) -> { hub: Promise<D sem voos>, drone: Promise<linhas>, voos: Promise<json> }`, com uma promessa por fonte, para mostrar o status de cada uma;
  - `apLerTudo(cliente, tabela)`: lê em páginas de 1000, como o `extrair.py`, com `order=layer` em `preparo_entregas`.
- Produz, em `apresentacao-exportar.js`: `apNomeArquivo(semana) -> 's5m10 - Apresentacao Geotecnologia - Indicadores e Entregas.pptx'` e `apExportar(slidesEls, notas, semana)`.

- [ ] **Passo 1: teste que falha** (`tests/app/apresentacao_dados.test.js`, funções puras):

```js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ console });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/apresentacao-exportar.js'), 'utf8'), ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/apresentacao-dados.js'), 'utf8'), ctx);

test('nome do arquivo', () => {
  assert.strictEqual(ctx.apNomeArquivo('S5M10'), 's5m10 - Apresentacao Geotecnologia - Indicadores e Entregas.pptx');
});

test('lê em páginas de 1000 até acabar', async () => {
  const pedidos = [];
  const cliente = { from: (t) => ({ select: () => ({ order: () => ({ range: async (a, b) => {
    pedidos.push([t, a, b]); return { data: Array(a === 0 ? 1000 : 3).fill({}), error: null }; } }),
    range: async (a, b) => { pedidos.push([t, a, b]); return { data: Array(a === 0 ? 1000 : 3).fill({}), error: null }; } }) }) };
  const linhas = await ctx.apLerTudo(cliente, 'talhoes');
  assert.strictEqual(linhas.length, 1003);
  assert.deepStrictEqual(pedidos, [['talhoes', 0, 999], ['talhoes', 1000, 1999]]);
});
```

- [ ] **Passo 2:** rode `node --test tests/app/apresentacao_dados.test.js`. Esperado: FALHA.

- [ ] **Passo 3: implementação.** Siga o protótipo (link no topo) e os padrões de `app/aplicacao.html` + `app/corretivos.js`:
  - **Login e acesso:** `crSb()`/`getSession` (corretivos.js:244-290), tela de login igual. Depois do login, `rpc('pode_usar_apresentacao')`; se vier `false`, mostra "Sem acesso", como os Corretivos.
  - **Modo demo:** `?demo` ou `file:` usa `apresentacao-demo.js`, sem banco e sem Worker; `?demo=voos-falha` faz a promessa de voos falhar após 2 s. Faixa "Demonstração" no topo (`.cr-demo`).
  - **Parâmetros:** semana/corte de `apSemana(new Date())`, editáveis; metas de `hub.apresentacao_metas`; "Salvar metas" faz `update` por chave e mostra "Última alteração: <nome>, <data>".
  - **Buscar dados:** chama `apFontes`. Cada fonte tem uma linha com status (carregando/ok/falhou + tempo).
    - Voos: `fetch(WORKER + '/voos-indicadores?de=' + metas.inicio_safra + '&ate=' + corte)` com `AbortController` de 180 s e o aviso "a primeira chamada do dia leva ~2 min". Use a mesma constante de URL do Worker que o app já usa para `/enviar` (procure `workers.dev` em `app/`).
    - Ao terminar Hub e drone, já monta a prévia. Voos entra quando chegar.
  - **Edição:** lista dos 6 slides; campos Subtítulo / Destaque / Notas.
    - Cada `input` agenda `rpc('apresentacao_texto_salvar', {...})` 2 s depois da última tecla, só do campo alterado, e mostra "Rascunho salvo às HH:MM".
    - Ao abrir a semana, carrega `apresentacao_semanas.textos` e mostra "editado por <nome> às HH:MM" se `atualizado_por` for outra pessoa.
    - "Voltar ao texto padrão" grava `''` no subtítulo; vazio = padrão.
    - A prévia é `apSlide(...)` num contêiner 1920×1080 com `transform: scale(largura/1920)`.
  - **Drone sem dado:** se `A.drone.sem_dado.length`, mostra o cartão "Drone de Aplicação · N projetos" com a lista (cod_faz · documento · revisão), sem bloquear.
  - **Erro de voos:** o slide 5 mostra "Dados indisponíveis" + "Tentar de novo", que chama de novo só a fonte de voos. A divisória fica "pendente". O botão "Baixar PPTX" só fica habilitado com as 3 fontes ok.
  - **PPTX** (`apresentacao-exportar.js`):
    - para cada slide, renderiza fora da tela em 1920×1080 e chama `htmlToImage.toPng(el, { pixelRatio: 2, width: 1920, height: 1080 })`, com `await document.fonts.ready` antes;
    - `pptx.layout = 'LAYOUT_WIDE'`; `slide.addImage({ data, x: 0, y: 0, w: '100%', h: '100%' })`; `slide.addNotes(notas[i])`;
    - grava com `pptx.writeFile({ fileName: apNomeArquivo(semana) })`.
  - Scripts: `<script src="https://cdn.jsdelivr.net/npm/pptxgenjs@3.12.0/dist/pptxgen.bundle.js"></script>` e `<script src="https://cdn.jsdelivr.net/npm/html-to-image@1.11.11/dist/html-to-image.js"></script>`.

- [ ] **Passo 4:** rode `node --test tests/app/`. Esperado: PASSA.

- [ ] **Passo 5: teste de tela** (`tests/app/teste_apresentacao_tela.py`). Siga `tests/app/teste_corretivos_tela.py` (servidor estático + Playwright), mas só em modo demo:
  - abre `apresentacao.html?demo`, clica "Buscar dados" e espera os 6 slides na lista;
  - digita `<b>chuva</b>` no destaque de Colheita e confere que a prévia mostra o texto literal;
  - baixa o PPTX e confere: nome `s?m?? - Apresentacao Geotecnologia - Indicadores e Entregas.pptx`, 6 slides e notas (abrindo com `python-pptx`);
  - abre `?demo=voos-falha` e confere "Dados indisponíveis", o botão Baixar desabilitado e que "Tentar de novo" volta a chamar a fonte.

  Rode `python tests/app/teste_apresentacao_tela.py`. Esperado: termina com "ok".
- [ ] **Passo 6: commit** `feat(apresentacao): tela com prévia, rascunho e PPTX`.

---

### Tarefa 9: cartão na tela inicial e validação contra o deck atual

**Arquivos:**
- Alterar: `app/index.html` (`rGeotech`, linhas 1810-1824)
- Criar: `docs/apresentacao-manual.md`

- [ ] **Passo 1: cartão.** Em `rGeotech()`, antes das ferramentas cadastradas, quando `EU?.admin || EU?.niveis?.apresentacao === 'editor'`, insira:

```js
  const ap=(EU?.admin||EU?.niveis?.apresentacao==='editor')?`
    <div class="gt-card">
      <div class="gt-ico" style="background:#019640"><span class="ico">slideshow</span></div>
      <div class="gt-nome">Apresentação semanal</div>
      <div class="gt-desc">Indicadores e Entregas da Geotecnologia: prévia e PPTX da semana.</div>
      <div class="gt-rodape"><a class="btn-acao gt-abrir" href="apresentacao.html" style="background:#019640"><span class="ico">open_in_new</span>Abrir</a></div>
    </div>`:'';
```

e use `ap+fs.map(...)`, também no caso vazio: se não houver ferramentas cadastradas mas `ap` existir, mostre só o cartão `ap`, sem a mensagem de vazio.

- [ ] **Passo 2:** abra `app/index.html` no modo demo do Hub, se houver (procure `demo` em `index.html`), ou com a conta de teste. Confira que o cartão aparece para admin e some para quem não tem a ferramenta.

- [ ] **Passo 3: manual** `docs/apresentacao-manual.md`, no estilo de `docs/mapas-aplicacao-manual.md`: como liberar a ferramenta, o fluxo semanal (parâmetros → buscar → textos → baixar), o que fazer quando o GeoMap falha, onde mudar as metas e a carga única do drone (Tarefa 4).

- [ ] **Passo 4: validação de paridade (com o Leo, depois das migrations aplicadas e da carga do drone):**
  - na mesma semana e corte, rodar `python scripts/extrair.py` + `gerar.py --previa` no notebook e gerar pela tela;
  - comparar os 6 slides número a número;
  - no drone, só se aceita diferença vinda dos ZIPs que falhavam no `extrair.py` (listar quais);
  - anotar o resultado no PR.
  - Os scripts antigos só saem de uso depois do ok do Leo.

- [ ] **Passo 5: commit** `feat(apresentacao): cartão na tela inicial e manual`.

---

## Depois das tarefas

`verification-before-completion`: rode `node --test tests/app/ tests/worker/` e `python -m pytest tests/contas tests/apresentacao tests/drone/test_carga_area_safra.py -v`, depois `requesting-code-review` e `finishing-a-development-branch`. A ordem de aplicação no Supabase fica no corpo do PR: migrations 0900 → 1000 → 1100, depois a carga do drone e o secret da Cloudflare.
