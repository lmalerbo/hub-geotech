# Preparo: mês de entrega + ciclo 25-26 — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** no Preparo, trocar o mês de plantio pelo mês de entrega no Hub e na apresentação semanal. Lançar de uma vez os talhões preparados antes de 01/04/2026. Avisar quando o PLANAGRI mostrar uso em campo de um talhão que não foi lançado no Hub.

**Architecture:** uma migração cria duas colunas de data, a função `hub.ciclo_inicio()`, a view `hub.preparo_entregas` (a regra da data de entrega), as funções do lançamento único (com tabela de backup e volta) e `hub.avisos_campo_planagri()`. A ingestão do PLANAGRI grava as datas e chama a função dos avisos. O app e a apresentação leem a view.

**Tech Stack:** Postgres/Supabase (schema `hub`), Python 3 (ingestão, openpyxl, pytest + Postgres local do Scoop), JS puro (app, `node --test`).

**Spec:** `docs/superpowers/specs/2026-10-28-preparo-mes-ciclo-design.md`

## Global Constraints

- Ciclo atual = `hub.safra_colheita()` (hoje `'26-27'`), de 1º/abr do primeiro ano a 31/mar do seguinte.
- Corte do lançamento único: `conservacao_em < date '2026-04-01'`.
- Origem no `log_auditoria` do lançamento único: `'planagri_ciclo_25_26'`. Justificativa e selo: `'ciclo 25-26 · pelo PLANAGRI'`.
- Lote inicial do sistema antigo: data de `concluido_em` (em America/Sao_Paulo) entre 2026-06-17 e 2026-06-19.
- Tipos de aviso: `'preparo_campo_sem_lancamento'` e `'plantio_campo_sem_lancamento'`.
- Dado real: nunca "limpar" apagando. Toda gravação no banco de produção passa pelo usuário antes (memória `feedback_testes_dados_reais`).
- `Documents/GitHub/src` não é repositório git. Copie os arquivos antes de editar.
- O Plantio não muda na tela.
- Textos para o usuário em português do Brasil.

## Review Focus

1. Talhão que voltou de Ok (retroceder) não pode aparecer como entregue. A view filtra `etapa = 'Ok'`. Teste na Tarefa 1.
2. Talhão entregue duas vezes (Ok → volta → Ok): vale a última passagem. Teste na Tarefa 1.
3. Rodar o lançamento duas vezes não lança nada de novo nem duplica log. Teste na Tarefa 2.
4. A observação existente da fazenda não pode ser trocada pelo selo. Teste na Tarefa 2.
5. Aviso cuja contagem não mudou não volta a ficar não lido a cada importação diária. Teste na Tarefa 3.

---

### Task 1: Datas de campo, ciclo e view de entregas

**Files:**
- Create: `supabase/migrations/20261028090000_preparo_datas_campo.sql`
- Create: `tests/preparo/conftest.py`
- Create: `tests/preparo/test_preparo_datas_sql.py`

**Interfaces:**
- Produces: `hub.talhao_preparo.conservacao_em date`, `hub.talhao_plantio.plantio_realizado_em date`, `hub.ciclo_inicio() returns date`, view `hub.preparo_entregas(layer bigint, cod_faz int, entregue_em timestamptz, origem text)`, com `origem` em (`'hub'`, `'lancamento_inicial'`, `'ciclo_25_26'`).

- [ ] **Step 1: Conftest dos testes**

`tests/preparo/conftest.py` reaproveita o Postgres local de `tests/fluxo` e acrescenta a migração da Colheita (que tem `hub.avisos` e `hub.safra_colheita()`) e a nova:

```python
"""Postgres local com as migrações do fluxo + Colheita (avisos, safra) + datas de campo do Preparo.
Mesmos fixtures de tests/fluxo (pg, fazenda, pessoa, como)."""
import pytest

from tests.fluxo import conftest as fluxo
from tests.fluxo.conftest import pg, fazenda, pessoa, como  # noqa: F401  (fixtures reaproveitados)

MIGRACOES = sorted(fluxo.MIGRACOES + ['20261003090000_modulo_colheita.sql',
                                      '20261028090000_preparo_datas_campo.sql'])


@pytest.fixture(scope='session')
def banco(pg):
    fluxo.MIGRACOES, antigas = MIGRACOES, fluxo.MIGRACOES
    try:
        con = fluxo.montar(pg, 'preparo_ciclo')
    finally:
        fluxo.MIGRACOES = antigas
    yield con
    con.close()
```

Se `tests` não for importável como pacote, crie `tests/__init__.py` e `tests/fluxo/__init__.py` vazios. Se a migração da Colheita falhar por depender de outra, acrescente à lista a migração que faltar (a mensagem do Postgres diz qual objeto não existe) e anote no commit.

- [ ] **Step 2: Testes da view (falham)**

`tests/preparo/test_preparo_datas_sql.py`:

```python
"""Datas de campo do PLANAGRI, ciclo e data de entrega do Preparo (spec 2026-10-28-preparo-mes-ciclo-design.md)."""
from tests.fluxo.test_fluxo_projetos_sql import por


def log_ok(banco, layer, quando, origem='usuario', de='Preparo', para='Ok'):
    banco.execute("insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, "
                  "valor_novo, origem, criado_em) values ('preparo','talhao',%s,'etapa',%s,%s,%s,%s)",
                  (layer, de, para, origem, quando))


def etapa_preparo_ok(banco, cod, quando):
    banco.execute("insert into hub.etapa_status (etapa_id, entidade_id, ok, concluido_em) "
                  "select id, %s, true, %s from hub.etapas where modulo_id='preparo' and nome='Preparo'", (cod, quando))


def entregas(banco, cod):
    return {r[0] % 1000: (r[1], r[2]) for r in banco.execute(
        "select layer, (entregue_em at time zone 'America/Sao_Paulo')::date::text, origem "
        "from hub.preparo_entregas where cod_faz = %s", (cod,))}


def test_ciclo_inicio_vem_da_safra(banco):
    assert banco.execute('select hub.ciclo_inicio()::text').fetchone()[0] == '2026-04-01'


def test_entrega_pelo_log_vale_a_ultima_passagem(banco, fazenda):
    cod = fazenda(2)
    por(banco, 'preparo', cod, 'Ok', [1])
    log_ok(banco, cod * 1000 + 1, '2026-08-10 12:00-03')
    log_ok(banco, cod * 1000 + 1, '2026-09-05 12:00-03', de='Ok', para='Preparo')
    log_ok(banco, cod * 1000 + 1, '2026-10-02 12:00-03')
    assert entregas(banco, cod) == {1: ('2026-10-02', 'hub')}   # talhão 2 não está Ok


def test_talhao_que_voltou_de_ok_nao_e_entregue(banco, fazenda):
    cod = fazenda(1)
    log_ok(banco, cod * 1000 + 1, '2026-08-10 12:00-03')        # foi Ok, mas hoje está em Identificação
    assert entregas(banco, cod) == {}


def test_sem_log_usa_etapa_preparo_e_marca_lote_de_junho(banco, fazenda):
    a, b = fazenda(1), fazenda(1)
    por(banco, 'preparo', a, 'Ok'); por(banco, 'preparo', b, 'Ok')
    etapa_preparo_ok(banco, a, '2026-06-18 15:00-03')
    etapa_preparo_ok(banco, b, '2026-07-20 15:00-03')
    assert entregas(banco, a) == {1: ('2026-06-18', 'lancamento_inicial')}
    assert entregas(banco, b) == {1: ('2026-07-20', 'hub')}


def test_lancamento_25_26_usa_data_de_conservacao(banco, fazenda):
    cod = fazenda(1)
    por(banco, 'preparo', cod, 'Ok')
    banco.execute("update hub.talhao_preparo set conservacao_em = '2025-09-15' where layer = %s", (cod * 1000 + 1,))
    log_ok(banco, cod * 1000 + 1, '2026-10-28 12:00-03', origem='planagri_ciclo_25_26')
    assert entregas(banco, cod) == {1: ('2025-09-15', 'ciclo_25_26')}
```

Run: `python -m pytest tests/preparo -q`
Expected: FAIL (a migração ainda não existe).

- [ ] **Step 3: Migração (parte 1)**

`supabase/migrations/20261028090000_preparo_datas_campo.sql`:

```sql
-- Preparo: mês de entrega no lugar do mês de plantio + ciclo 25-26
-- (spec docs/superpowers/specs/2026-10-28-preparo-mes-ciclo-design.md).
--
-- 1) Datas de campo do PLANAGRI (dono: PLANAGRI, só informação, não avançam etapa).
-- 2) hub.ciclo_inicio(): 1º/abr do ciclo atual (parâmetro colheita_safra).
-- 3) hub.preparo_entregas: data de entrega de cada talhão Ok do Preparo.
-- 4) Lançamento único do ciclo 25-26 (com backup e volta).
-- 5) Avisos de uso em campo sem lançamento no Hub.

begin;

-- 1 ─────────────────────────────────────────────────────────────────────────
alter table hub.talhao_preparo add column conservacao_em date;        -- dono: PLANAGRI (CONSERVAÇÃO (DATA))
alter table hub.talhao_plantio add column plantio_realizado_em date;  -- dono: PLANAGRI (REALIZADO PLANTIO (DATA))

-- 2 ─────────────────────────────────────────────────────────────────────────
create or replace function hub.ciclo_inicio()
returns date language sql stable security definer set search_path = hub as $$
  select make_date(2000 + left(hub.safra_colheita(), 2)::int, 4, 1);
$$;

-- 3 ─────────────────────────────────────────────────────────────────────────
-- Entrega = talhão em Ok. Data: a última passagem para Ok no registro (fluxo por talhão, desde 23/10);
-- sem ela, a etapa Preparo da fazenda em etapa_status (histórico de antes). O lançamento do ciclo 25-26
-- usa a data de conservação. O lote do sistema antigo (17 a 19/06/2026) sai como lancamento_inicial.
create or replace view hub.preparo_entregas with (security_invoker = true) as
with ultimo_ok as (
  select distinct on (l.entidade_id) l.entidade_id as layer, l.criado_em, l.origem
    from hub.log_auditoria l
   where l.modulo_id = 'preparo' and l.entidade_tipo = 'talhao' and l.campo = 'etapa' and l.valor_novo = 'Ok'
   order by l.entidade_id, l.criado_em desc, l.id desc
), etapa_preparo as (
  select s.entidade_id as cod_faz, s.concluido_em
    from hub.etapa_status s join hub.etapas e on e.id = s.etapa_id
   where e.modulo_id = 'preparo' and e.nome = 'Preparo' and s.ok
)
select p.layer, t.cod_faz,
       case when u.origem = 'planagri_ciclo_25_26' then p.conservacao_em::timestamptz
            else coalesce(u.criado_em, ep.concluido_em) end as entregue_em,
       case when u.origem = 'planagri_ciclo_25_26' then 'ciclo_25_26'
            when u.criado_em is null
             and (ep.concluido_em at time zone 'America/Sao_Paulo')::date between date '2026-06-17' and date '2026-06-19'
              then 'lancamento_inicial'
            else 'hub' end as origem
  from hub.talhao_preparo p
  join hub.talhoes t on t.layer = p.layer
  left join ultimo_ok u on u.layer = p.layer
  left join etapa_preparo ep on ep.cod_faz = t.cod_faz
 where p.etapa = 'Ok';

grant select on hub.preparo_entregas to authenticated, service_role;
revoke all on function hub.ciclo_inicio() from public, anon;
grant execute on function hub.ciclo_inicio() to authenticated, service_role;

commit;
```

(As partes 4 e 5 entram nas Tarefas 2 e 3, **antes** do `commit;`.)

- [ ] **Step 4: Rodar**

Run: `python -m pytest tests/preparo -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20261028090000_preparo_datas_campo.sql tests/preparo tests/__init__.py tests/fluxo/__init__.py
git commit -m "Preparo: datas de campo do PLANAGRI e view de entregas"
```

---

### Task 2: Lançamento único do ciclo 25-26 (com backup e volta)

**Files:**
- Modify: `supabase/migrations/20261028090000_preparo_datas_campo.sql` (parte 4)
- Create: `tests/preparo/test_ciclo_25_26_sql.py`
- Create: `migracao/lancar_ciclo_25_26.py`

**Interfaces:**
- Consumes: `hub.projeto_mudar_etapa(p_modulo, p_layers, p_para, p_lote, p_origem, p_justificativa)`, `hub.log_lote_seq`.
- Produces: `hub.preparo_ciclo_25_26_candidatos() returns table(cod_faz int, fazenda text, talhao_num int, layer bigint, area_ha numeric, conservacao_em date, etapa text)`; `hub.preparo_lancar_ciclo_25_26() returns bigint` (o lote; null se não havia candidato); `hub.preparo_voltar_ciclo_25_26(p_lote bigint) returns int` (talhões restaurados); tabela `hub.etapa_status_backup(lote_id bigint, linha jsonb, existia boolean)`.

- [ ] **Step 1: Testes (falham)**

`tests/preparo/test_ciclo_25_26_sql.py`:

```python
"""Lançamento único do ciclo 25-26: talhão a talhão, conservação antes de 01/04/2026."""
from tests.fluxo.test_fluxo_projetos_sql import etapas, por

SELO = 'ciclo 25-26 · pelo PLANAGRI'


def conservacao(banco, cod, datas):
    for n, d in datas.items():
        banco.execute('update hub.talhao_preparo set conservacao_em = %s where layer = %s', (d, cod * 1000 + n))


def status(banco, cod):
    return banco.execute("select e.nome, s.ok, s.observacao, (s.concluido_em at time zone 'America/Sao_Paulo')::date::text "
                         "from hub.etapa_status s join hub.etapas e on e.id = s.etapa_id "
                         "where e.modulo_id='preparo' and s.entidade_id = %s order by e.ordem", (cod,)).fetchall()


def test_lanca_so_talhoes_com_conservacao_antes_do_corte(banco, fazenda):
    cod = fazenda(3)
    conservacao(banco, cod, {1: '2025-08-01', 2: '2026-04-01', 3: None})
    cand = banco.execute('select talhao_num from hub.preparo_ciclo_25_26_candidatos() where cod_faz = %s', (cod,)).fetchall()
    assert cand == [(1,)]
    lote = banco.execute('select hub.preparo_lancar_ciclo_25_26()').fetchone()[0]
    assert etapas(banco, 'preparo', cod) == {1: 'Ok', 2: 'Identificação', 3: 'Identificação'}
    assert banco.execute("select count(*) from hub.log_auditoria where lote_id = %s and entidade_id = %s "
                         "and origem = 'planagri_ciclo_25_26' and justificativa = %s", (lote, cod * 1000 + 1, SELO)).fetchone()[0] == 1
    assert status(banco, cod) == []          # fazenda não ficou inteira Ok: etapa_status não muda


def test_fazenda_inteira_ganha_etapas_sem_trocar_observacao(banco, fazenda):
    cod = fazenda(2)
    conservacao(banco, cod, {1: '2025-06-10', 2: '2025-11-20'})
    banco.execute("insert into hub.etapa_status (etapa_id, entidade_id, ok, observacao) select id, %s, false, 'obs antiga' "
                  "from hub.etapas where modulo_id='preparo' and nome='Observações'", (cod,))
    banco.execute('select hub.preparo_lancar_ciclo_25_26()')
    assert status(banco, cod) == [('Identificação', True, SELO, '2025-11-20'), ('Escoamento', True, SELO, '2025-11-20'),
                                  ('Observações', True, 'obs antiga', '2025-11-20'), ('Preparo', True, SELO, '2025-11-20')]


def test_rodar_de_novo_nao_lanca_nada(banco, fazenda):
    cod = fazenda(1)
    conservacao(banco, cod, {1: '2025-07-01'})
    banco.execute('select hub.preparo_lancar_ciclo_25_26()')
    assert banco.execute('select hub.preparo_lancar_ciclo_25_26()').fetchone()[0] is None


def test_talhao_ja_ok_nao_entra(banco, fazenda):
    cod = fazenda(1)
    conservacao(banco, cod, {1: '2025-07-01'})
    por(banco, 'preparo', cod, 'Ok')
    assert banco.execute('select count(*) from hub.preparo_ciclo_25_26_candidatos() where cod_faz = %s', (cod,)).fetchone()[0] == 0


def test_volta_restaura_etapa_status_e_log(banco, fazenda):
    cod = fazenda(1)
    conservacao(banco, cod, {1: '2025-07-01'})
    por(banco, 'preparo', cod, 'Observações')
    banco.execute("insert into hub.etapa_status (etapa_id, entidade_id, ok, observacao) select id, %s, true, 'x' "
                  "from hub.etapas where modulo_id='preparo' and nome='Identificação'", (cod,))
    antes = status(banco, cod)
    lote = banco.execute('select hub.preparo_lancar_ciclo_25_26()').fetchone()[0]
    assert banco.execute('select hub.preparo_voltar_ciclo_25_26(%s)', (lote,)).fetchone()[0] == 1
    assert etapas(banco, 'preparo', cod) == {1: 'Observações'}
    assert status(banco, cod) == antes
    assert banco.execute('select count(*) from hub.log_auditoria where lote_id = %s', (lote,)).fetchone()[0] == 0
```

Run: `python -m pytest tests/preparo/test_ciclo_25_26_sql.py -q` → FAIL (função não existe).

- [ ] **Step 2: Migração, parte 4** (antes do `commit;`)

```sql
-- 4 ─────────────────────────────────────────────────────────────────────────
-- Lançamento único: talhão do Preparo ainda não Ok com conservação antes de 01/04/2026 passa para Ok
-- (registro com origem planagri_ciclo_25_26). Fazenda que fica inteira Ok ganha as 4 etapas em
-- etapa_status com a maior data de conservação, sem usuário e com o selo (observação existente fica).
create table hub.etapa_status_backup (
  lote_id  bigint  not null,
  linha    jsonb   not null,     -- a linha de etapa_status antes do lançamento
  existia  boolean not null      -- false = a linha foi criada pelo lançamento (a volta apaga)
);
alter table hub.etapa_status_backup enable row level security;

create or replace function hub.preparo_ciclo_25_26_candidatos()
returns table (cod_faz int, fazenda text, talhao_num int, layer bigint, area_ha numeric, conservacao_em date, etapa text)
language sql stable security definer set search_path = hub as $$
  select t.cod_faz, f.nome, t.talhao_num, p.layer, t.area_ha::numeric, p.conservacao_em, p.etapa
    from hub.talhao_preparo p
    join hub.talhoes t on t.layer = p.layer
    left join hub.fazendas f on f.cod_faz = t.cod_faz
   where p.etapa <> 'Ok' and p.conservacao_em < date '2026-04-01'
   order by t.cod_faz, t.talhao_num;
$$;

create or replace function hub.preparo_lancar_ciclo_25_26()
returns bigint language plpgsql security definer set search_path = hub as $$
declare
  v_selo   constant text := 'ciclo 25-26 · pelo PLANAGRI';
  v_lote   bigint;
  v_layers bigint[];
begin
  select array_agg(c.layer) into v_layers from hub.preparo_ciclo_25_26_candidatos() c;
  if v_layers is null then return null; end if;
  v_lote := nextval('hub.log_lote_seq');
  perform hub.projeto_mudar_etapa('preparo', v_layers, 'Ok', v_lote, 'planagri_ciclo_25_26', v_selo);

  -- fazendas que ficaram inteiras Ok com este lote
  create temp table _faz on commit drop as
  select t.cod_faz, max(p.conservacao_em) as data
    from hub.talhoes t join hub.talhao_preparo p on p.layer = t.layer
   where t.cod_faz in (select t2.cod_faz from hub.talhoes t2 where t2.layer = any(v_layers))
   group by t.cod_faz
  having bool_and(p.etapa = 'Ok');

  insert into hub.etapa_status_backup (lote_id, linha, existia)
  select v_lote, coalesce(to_jsonb(s), jsonb_build_object('etapa_id', e.id, 'entidade_id', f.cod_faz)), s.etapa_id is not null
    from _faz f cross join hub.etapas e
    left join hub.etapa_status s on s.etapa_id = e.id and s.entidade_id = f.cod_faz
   where e.modulo_id = 'preparo';

  insert into hub.etapa_status (etapa_id, entidade_id, ok, usuario_id, concluido_em, observacao)
  select e.id, f.cod_faz, true, null, f.data::timestamptz + interval '12 hours', v_selo
    from _faz f cross join hub.etapas e
   where e.modulo_id = 'preparo'
  on conflict (etapa_id, entidade_id) do update
     set ok = true, usuario_id = null, concluido_em = excluded.concluido_em,
         observacao = coalesce(nullif(hub.etapa_status.observacao, ''), excluded.observacao);
  return v_lote;
end $$;

create or replace function hub.preparo_voltar_ciclo_25_26(p_lote bigint)
returns int language plpgsql security definer set search_path = hub as $$
declare v_qtd int;
begin
  update hub.talhao_preparo p set etapa = l.valor_anterior
    from hub.log_auditoria l
   where l.lote_id = p_lote and l.origem = 'planagri_ciclo_25_26' and l.entidade_id = p.layer;
  get diagnostics v_qtd = row_count;

  delete from hub.etapa_status s using hub.etapa_status_backup b
   where b.lote_id = p_lote and not b.existia
     and s.etapa_id = (b.linha->>'etapa_id')::bigint and s.entidade_id = (b.linha->>'entidade_id')::bigint;
  update hub.etapa_status s
     set ok = (b.linha->>'ok')::boolean, usuario_id = (b.linha->>'usuario_id')::uuid,
         concluido_em = (b.linha->>'concluido_em')::timestamptz, observacao = b.linha->>'observacao'
    from hub.etapa_status_backup b
   where b.lote_id = p_lote and b.existia
     and s.etapa_id = (b.linha->>'etapa_id')::bigint and s.entidade_id = (b.linha->>'entidade_id')::bigint;

  delete from hub.log_auditoria where lote_id = p_lote and origem = 'planagri_ciclo_25_26';
  delete from hub.etapa_status_backup where lote_id = p_lote;
  return v_qtd;
end $$;

revoke all on function hub.preparo_ciclo_25_26_candidatos() from public, anon, authenticated;
revoke all on function hub.preparo_lancar_ciclo_25_26()     from public, anon, authenticated;
revoke all on function hub.preparo_voltar_ciclo_25_26(bigint) from public, anon, authenticated;
grant execute on function hub.preparo_ciclo_25_26_candidatos() to service_role;
grant execute on function hub.preparo_lancar_ciclo_25_26()     to service_role;
grant execute on function hub.preparo_voltar_ciclo_25_26(bigint) to service_role;
```

Observação: `projeto_mudar_etapa` grava `usuario_id = auth.uid()`, que é null quando a chamada vem do `service_role`. É isso que a spec pede. Se o trigger de `talhao_preparo` ou o próprio `projeto_mudar_etapa` exigir usuário, o teste do Step 1 mostra.

- [ ] **Step 3: Rodar**

Run: `python -m pytest tests/preparo -q` → todos passam.

- [ ] **Step 4: Script de operação**

`migracao/lancar_ciclo_25_26.py`:

```python
"""Lançamento único do ciclo 25-26 no Preparo (spec 2026-10-28-preparo-mes-ciclo-design.md, D3).

Uso:
  python migracao/lancar_ciclo_25_26.py                 # lista os candidatos e grava um CSV (não grava no banco)
  python migracao/lancar_ciclo_25_26.py --gravar        # lança (depois do ok do usuário na lista)
  python migracao/lancar_ciclo_25_26.py --voltar LOTE   # desfaz o lançamento
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ingestao'))
from comum import Hub  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--gravar', action='store_true')
    ap.add_argument('--voltar', type=int, metavar='LOTE')
    args = ap.parse_args()
    hub = Hub()

    if args.voltar:
        n = hub.rpc('preparo_voltar_ciclo_25_26', {'p_lote': args.voltar})
        print(f'Volta do lote {args.voltar}: {n} talhões restaurados.')
        return

    cand = hub.rpc('preparo_ciclo_25_26_candidatos')
    saida = os.path.join(os.path.dirname(__file__), 'ciclo_25_26_candidatos.csv')
    with open(saida, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(cand[0]) if cand else ['cod_faz'], delimiter=';')
        w.writeheader()
        w.writerows(cand)
    fazendas = {c['cod_faz'] for c in cand}
    print(f'{len(cand)} talhões em {len(fazendas)} fazendas, {sum(c["area_ha"] or 0 for c in cand):.1f} ha → {saida}')

    if args.gravar:
        lote = hub.rpc('preparo_lancar_ciclo_25_26')
        print(f'Lançado. Lote {lote} (para desfazer: --voltar {lote}).')
    else:
        print('Só a lista: nada foi gravado. Confira o CSV antes de rodar com --gravar.')


if __name__ == '__main__':
    main()
```

Acrescente `migracao/ciclo_25_26_candidatos.csv` ao `.gitignore`.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20261028090000_preparo_datas_campo.sql tests/preparo/test_ciclo_25_26_sql.py migracao/lancar_ciclo_25_26.py .gitignore
git commit -m "Preparo: lançamento único do ciclo 25-26 com backup e volta"
```

---

### Task 3: Avisos de uso em campo sem lançamento

**Files:**
- Modify: `supabase/migrations/20261028090000_preparo_datas_campo.sql` (parte 5)
- Create: `tests/preparo/test_avisos_campo_sql.py`

**Interfaces:**
- Consumes: `hub.ciclo_inicio()`, `hub.avisos`, `hub.avisos_lidos`.
- Produces: `hub.avisos_campo_planagri() returns void` (executável pelo `service_role`).

- [ ] **Step 1: Testes (falham)**

```python
"""Aviso por fazenda: data de campo do PLANAGRI no ciclo atual e talhão sem lançamento no Hub."""
from tests.fluxo.test_fluxo_projetos_sql import por


def avisos(banco, cod):
    return banco.execute('select tipo, texto from hub.avisos where cod_faz = %s and resolvido_em is null order by tipo',
                         (cod,)).fetchall()


def rodar(banco):
    banco.execute('select hub.avisos_campo_planagri()')


def test_preparo_e_plantio_abrem_aviso_so_no_ciclo_atual(banco, fazenda):
    cod = fazenda(3)
    banco.execute("update hub.talhao_preparo set conservacao_em = '2026-09-10' where layer in (%s, %s)", (cod*1000+1, cod*1000+2))
    banco.execute("update hub.talhao_preparo set conservacao_em = '2025-09-10' where layer = %s", (cod*1000+3,))
    banco.execute("update hub.talhao_plantio set plantio_realizado_em = '2026-10-01' where layer = %s", (cod*1000+1,))
    rodar(banco)
    assert avisos(banco, cod) == [
        ('plantio_campo_sem_lancamento', '1 talhão(ões) com plantio realizado no PLANAGRI, falta lançar no Hub.'),
        ('preparo_campo_sem_lancamento', '2 talhão(ões) usados em campo (conservação no PLANAGRI), falta lançar no Hub.')]


def test_aviso_resolve_quando_lanca(banco, fazenda):
    cod = fazenda(1)
    banco.execute("update hub.talhao_preparo set conservacao_em = '2026-09-10' where layer = %s", (cod*1000+1,))
    rodar(banco)
    por(banco, 'preparo', cod, 'Ok')
    rodar(banco)
    assert avisos(banco, cod) == []


def test_aviso_igual_nao_volta_a_ficar_nao_lido(banco, fazenda, pessoa):
    cod, uid = fazenda(2), pessoa()
    banco.execute("update hub.talhao_preparo set conservacao_em = '2026-09-10' where layer = %s", (cod*1000+1,))
    rodar(banco)
    aid = banco.execute('select id from hub.avisos where cod_faz = %s and resolvido_em is null', (cod,)).fetchone()[0]
    banco.execute('insert into hub.avisos_lidos (aviso_id, usuario_id) values (%s, %s)', (aid, uid))
    rodar(banco)
    assert banco.execute('select count(*) from hub.avisos_lidos where aviso_id = %s', (aid,)).fetchone()[0] == 1
    banco.execute("update hub.talhao_preparo set conservacao_em = '2026-09-11' where layer = %s", (cod*1000+2,))
    rodar(banco)                                            # mudou a contagem → não lido de novo
    assert banco.execute('select count(*) from hub.avisos_lidos where aviso_id = %s', (aid,)).fetchone()[0] == 0
```

Run: `python -m pytest tests/preparo/test_avisos_campo_sql.py -q` → FAIL.

- [ ] **Step 2: Migração, parte 5** (antes do `commit;`)

```sql
-- 5 ─────────────────────────────────────────────────────────────────────────
-- Roda depois de cada importação do PLANAGRI. Um aviso aberto por tipo e fazenda; texto que muda volta a
-- ficar não lido; some sozinho quando não sobra talhão na condição. Só datas do ciclo atual.
create or replace function hub.avisos_campo_planagri()
returns void language plpgsql security definer set search_path = hub as $$
declare
  v_ini date := hub.ciclo_inicio();
  v_fim date := hub.ciclo_inicio() + interval '1 year';
  r     record;
  v_id  bigint;
begin
  create temp table _pend on commit drop as
  select 'preparo'::text as modulo, 'preparo_campo_sem_lancamento'::text as tipo, t.cod_faz, count(*) as n,
         ' talhão(ões) usados em campo (conservação no PLANAGRI), falta lançar no Hub.' as frase
    from hub.talhao_preparo p join hub.talhoes t on t.layer = p.layer
   where p.conservacao_em >= v_ini and p.conservacao_em < v_fim and p.etapa <> 'Ok'
   group by t.cod_faz
  union all
  select 'plantio', 'plantio_campo_sem_lancamento', t.cod_faz, count(*),
         ' talhão(ões) com plantio realizado no PLANAGRI, falta lançar no Hub.'
    from hub.talhao_plantio p join hub.talhoes t on t.layer = p.layer
   where p.plantio_realizado_em >= v_ini and p.plantio_realizado_em < v_fim and p.projeto <> 'Ok'
   group by t.cod_faz;

  update hub.avisos a set resolvido_em = now()
   where a.tipo in ('preparo_campo_sem_lancamento', 'plantio_campo_sem_lancamento') and a.resolvido_em is null
     and not exists (select 1 from _pend p where p.tipo = a.tipo and p.cod_faz = a.cod_faz);

  for r in select p.*, f.nome from _pend p left join hub.fazendas f on f.cod_faz = p.cod_faz loop
    v_id := null;
    insert into hub.avisos (modulo_id, tipo, cod_faz, titulo, texto)
    values (r.modulo, r.tipo, r.cod_faz,
            r.cod_faz || ' ' || coalesce(r.nome, '') || ': usado em campo, falta lançar',
            r.n || r.frase)
    on conflict (tipo, cod_faz) where resolvido_em is null
      do update set texto = excluded.texto, atualizado_em = now()
       where hub.avisos.texto is distinct from excluded.texto
    returning id into v_id;
    if v_id is not null then
      delete from hub.avisos_lidos where aviso_id = v_id;
    end if;
  end loop;
end $$;

revoke all on function hub.avisos_campo_planagri() from public, anon, authenticated;
grant execute on function hub.avisos_campo_planagri() to service_role;
```

- [ ] **Step 3: Rodar** `python -m pytest tests/preparo -q` → todos passam.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/20261028090000_preparo_datas_campo.sql tests/preparo/test_avisos_campo_sql.py
git commit -m "Preparo/Plantio: aviso de uso em campo sem lançamento no Hub"
```

---

### Task 4: Ingestão do PLANAGRI grava as datas e chama os avisos

**Files:**
- Modify: `ingestao/planagri.py` (`ler` e `main`)
- Create: `tests/ingestao/test_planagri_datas.py`

**Interfaces:**
- Consumes: `hub.avisos_campo_planagri()` (Tarefa 3).
- Produces: `ler(caminho, aba)` devolve em cada talhão também `conservacao_em` e `plantio_realizado_em` (ISO `YYYY-MM-DD` ou None).

- [ ] **Step 1: Teste (falha)**

```python
"""Leitura das datas de campo do PLANAGRI (pelos nomes das colunas, nunca pela posição)."""
import datetime
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ingestao'))
import planagri  # noqa: E402


def test_le_conservacao_e_plantio_realizado(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Planagri'
    ws.append(['CÓDIGO', 'TALHÃO', 'PLAN.', 'PLAN.', 'MÊS PLANTIO (PLAN)', 'CONSERVAÇÃO (DATA)', 'REALIZADO PLANTIO (DATA)'])
    ws.append([10001, 1, 'REFORMA', 'LIB', datetime.datetime(2026, 11, 1), datetime.datetime(2025, 9, 15), None])
    ws.append([10001, 2, 'REFORMA', 'LIB', None, 'texto', datetime.datetime(2026, 10, 3)])
    caminho = tmp_path / 'p.xlsx'
    wb.save(caminho)
    talhoes, _ = planagri.ler(str(caminho), 'Planagri')
    assert talhoes[10001001]['conservacao_em'] == '2025-09-15'
    assert talhoes[10001001]['plantio_realizado_em'] is None
    assert talhoes[10001002]['conservacao_em'] is None            # texto não vira data
    assert talhoes[10001002]['plantio_realizado_em'] == '2026-10-03'
```

Run: `python -m pytest tests/ingestao/test_planagri_datas.py -q` → FAIL (KeyError).

- [ ] **Step 2: Implementação**

Em `ler`, as colunas novas entram como obrigatórias e são lidas:

```python
    colunas, linhas = ler_tabela(achar_aba(wb, aba), ['CÓDIGO', 'TALHÃO', 'PLAN.', 'MÊS PLANTIO (PLAN)',
                                                      'CONSERVAÇÃO (DATA)', 'REALIZADO PLANTIO (DATA)'])
    j_cod, j_tal = colunas['CODIGO'][0], colunas['TALHAO'][0]
    j_mes, j_status = colunas['MES PLANTIO (PLAN)'][0], coluna_status(colunas, linhas)
    j_cons, j_real = colunas['CONSERVACAO (DATA)'][0], colunas['REALIZADO PLANTIO (DATA)'][0]
```

e o dicionário do talhão:

```python
        talhoes[calc_layer(cod, tal)] = {'layer': calc_layer(cod, tal), 'mes_plantio': para_data(l[j_mes]),
                                         'conservacao_em': para_data(l[j_cons]),
                                         'plantio_realizado_em': para_data(l[j_real])}
```

Em `main`, separe o que vai para cada tabela e chame os avisos:

```python
        hub.upsert('talhao_plantio', [{'layer': t['layer'], 'mes_plantio': t['mes_plantio'],
                                       'plantio_realizado_em': t['plantio_realizado_em']} for t in validos], 'layer')
        # No Preparo o andamento é por talhão (etapas); daqui vem só a demanda e a data de conservação.
        hub.upsert('talhao_preparo', [{'layer': t['layer'], 'conservacao_em': t['conservacao_em']} for t in validos], 'layer')
        hub.rpc('avisos_campo_planagri')
```

Atualize a docstring do módulo: "Grava só o que o PLANAGRI é dono: o talhão estar na demanda, o mês de plantio e as datas de campo (conservação e plantio realizado), que só geram aviso e não avançam etapa."

- [ ] **Step 3: Rodar** `python -m pytest tests/ingestao -q` → passa. Se o arquivo real estiver acessível: `python ingestao/planagri.py --simular`, que deve ler sem erro de cabeçalho.

- [ ] **Step 4: Commit**

```bash
git add ingestao/planagri.py tests/ingestao/test_planagri_datas.py
git commit -m "Ingestão PLANAGRI: datas de conservação e plantio realizado + avisos"
```

---

### Task 5: Hub — "Entregue em" na Consulta do Preparo

**Files:**
- Modify: `app/dados.js` (`SEL_PREPARO`, `montarPreparo`, recarga por fazenda ~linha 192)
- Modify: `app/index.html` (carga ~2565-2626; Consulta do Preparo ~2236-2250, filtro ~2414, cabeçalho da tabela)
- Test: `tests/app/dados_puro.test.js`

**Interfaces:**
- Consumes: view `preparo_entregas` (Tarefa 1).
- Produces: `montarPreparo(linhas, etapas, status, nomeUsr, entregas)`, em que `entregas` é uma lista de `{layer, entregue_em, origem}`. Cada fazenda devolvida tem `mes` (rótulo `mesLabel` do maior `entregue_em` quando **todos** os talhões estão Ok, senão `''`), `ciclo25` (boolean: algum talhão com origem `ciclo_25_26`), e cada talhão tem `cons` (`conservacao_em`, ISO ou null).

- [ ] **Step 1: Teste (falha)** — acrescente a `tests/app/dados_puro.test.js`:

```js
const talPr = (cod, num, etapa, cons = null) => ({
  layer: cod * 1000 + num, etapa, conservacao_em: cons,
  talhoes: { cod_faz: cod, talhao_num: num, area_ha: 5, fazendas: { nome: 'F' + cod } },
});

test('Preparo: "Entregue em" é o mês do último talhão, só com a fazenda toda Ok', () => {
  const linhas = [talPr(1, 1, 'Ok'), talPr(1, 2, 'Ok', '2025-09-01'), talPr(2, 1, 'Ok'), talPr(2, 2, 'Preparo')];
  const ent = [
    { layer: 1001, entregue_em: '2026-08-10T15:00:00+00:00', origem: 'hub' },
    { layer: 1002, entregue_em: '2025-09-01T00:00:00+00:00', origem: 'ciclo_25_26' },
    { layer: 2001, entregue_em: '2026-09-01T15:00:00+00:00', origem: 'hub' },
  ];
  const [f1, f2] = ctx.montarPreparo(linhas, [], [], {}, ent);
  assert.strictEqual(f1.mes, '2026-08');
  assert.strictEqual(f1.ciclo25, true);
  assert.strictEqual(f1.tals[1].cons, '2025-09-01');
  assert.strictEqual(f2.mes, '');
  assert.strictEqual(f2.ciclo25, false);
});
```

(`mesLabel` no contexto do teste devolve `iso.slice(0, 7)`.)

Run: `node --test tests/app/dados_puro.test.js` → FAIL.

- [ ] **Step 2: `app/dados.js`**

```js
const SEL_PREPARO='layer,etapa,conservacao_em,talhoes(cod_faz,talhao_num,area_ha,fazendas(nome))';
```

Em `montarPreparo`, troque o parâmetro `mesFaz` por `entregas` e ajuste o cálculo:

```js
// Preparo: fazendas da demanda, talhões com a etapa do banco (tals, como o Plantio) e etapas
// concluídas (etapa_status: ok, quem, quando e a observação). A etapa da fazenda é a do talhão menos avançado.
// mes = "Entregue em": mês do último talhão entregue (view preparo_entregas), só com a fazenda toda Ok.
function montarPreparo(linhas,etapas,status,nomeUsr,entregas){
  const idsEtapa=new Set(etapas.map(e=>e.id));
  const st=new Map(status.filter(s=>idsEtapa.has(s.etapa_id)).map(s=>[s.etapa_id+'|'+s.entidade_id,s]));
  const ent=new Map((entregas||[]).map(x=>[x.layer,x]));
  const idxEtapa=Object.fromEntries(ETAPAS_PREPARO.map((n,i)=>[n,i]));
  const porFaz=new Map();
  for(const r of linhas){
    const t=r.talhoes;
    if(!t)continue;
    let f=porFaz.get(t.cod_faz);
    if(!f){
      f={n:t.fazendas?.nome||String(t.cod_faz),cod:String(t.cod_faz),ha:0,mes:'',ciclo25:false,_ult:'',_todosOk:true,
         voo:'?',ok:[],usr:[],dt:[],obs:'',tals:[],e:ETAPAS_PREPARO.length-1};
      porFaz.set(t.cod_faz,f);
    }
    const e=idxEtapa[r.etapa]??0;
    f.tals.push({layer:r.layer,num:t.talhao_num,ha:t.area_ha||0,e,cons:r.conservacao_em||null});
    f.e=Math.min(f.e,e);
    f.ha+=t.area_ha||0;
    const x=ent.get(r.layer);
    if(r.etapa!=='Ok'||!x)f._todosOk=false;
    if(x){if(x.origem==='ciclo_25_26')f.ciclo25=true;if(x.entregue_em>f._ult)f._ult=x.entregue_em;}
  }
  return [...porFaz.entries()].sort((a,b)=>a[1].n.localeCompare(b[1].n,'pt-BR')).map(([cod,f])=>{
    f.ha=Math.round(f.ha*10)/10;
    f.tals.sort((a,b)=>a.num-b.num);
    f.mes=f._todosOk&&f._ult?mesLabel(f._ult.slice(0,10)):'';
    delete f._ult;delete f._todosOk;
    for(const e of etapas){
      const s=st.get(e.id+'|'+cod);
      f.ok.push(!!s?.ok);
      f.usr.push(s?.ok?(nomeUsr[s.usuario_id]||'—'):'');
      f.dt.push(s?.ok?fmtDataHora(s.concluido_em):'');
      if(s?.observacao)f.obs=s.observacao;
    }
    return f;
  });
}
```

Na recarga por fazenda (`app/dados.js` ~192), leia `preparo_entregas` da fazenda (`.eq('cod_faz',cod)`) junto com as outras leituras e passe no lugar de `mesFaz`. Abra o trecho com `Read` (offset 170, limit 30) para encaixar no `Promise.all` que já existe ali.

- [ ] **Step 3: `app/index.html`**

1. Na carga (~2565), acrescente ao `Promise.all` e à desestruturação uma leitura `entregasP`:
   `lerTudo(()=>sb.from('preparo_entregas').select('layer,entregue_em,origem').order('layer'))`
2. ~2625: apague `const mesFaz=...` e use `montarPreparo(preparo,etapas,status,nomeUsr,entregasP)`.
3. Consulta do Preparo (~2246): no objeto da linha, use `mes:f.mes||'—'` e `ciclo:f.ciclo25?'25-26':getCiclo()`.
4. Na mesma linha (~2317), quando `f.ciclo25`, acrescente depois do nome um selo `<span class="cons-badge" style="background:var(--s2);color:var(--t2)">ciclo 25-26 · PLANAGRI</span>`.
5. Filtro (~2418): o texto da opção vazia passa a ser `Entregue em: todos`. A lista é `meses.filter(m=>m&&m!=='—')`.
6. Cabeçalho: ache com `Grep` o `<th>` "Mês" da tabela da Consulta quando `cMod==='preparo'` e troque por "Entregue em" **só no Preparo** (o Plantio continua "Mês").
7. Tabela de talhões da fazenda no Preparo: ache com `Grep` onde `tals` do `FZ_P` é desenhado e acrescente uma coluna "Conservação" com `t.cons?t.cons.split('-').reverse().join('/'):'—'`.

- [ ] **Step 4: Rodar** `node --test tests/app/*.test.js` → todos passam.

- [ ] **Step 5: Teste de tela.** Fica com o usuário, depois da Tarefa 6: na Consulta do Preparo, conferir a coluna "Entregue em", o filtro, o texto copiado e o selo.

- [ ] **Step 6: Commit**

```bash
git add app/dados.js app/index.html tests/app/dados_puro.test.js
git commit -m "Hub Preparo: Entregue em no lugar do mês de plantio + selo ciclo 25-26"
```

---

### Task 6: Produção (com o usuário em cada gravação)

**Files:** nenhum arquivo novo.

- [x] **Step 1:** `supabase db push` da migração `20261028090000_preparo_datas_campo.sql`. Antes, mostre ao usuário o que será aplicado. Depois, confira: `select count(*) from hub.preparo_entregas;`.
- [x] **Step 2:** `python ingestao/planagri.py --simular`, depois `python ingestao/planagri.py`. Confira quantos talhões ficaram com `conservacao_em` e `plantio_realizado_em`, e os avisos abertos (`select tipo, count(*) from hub.avisos where resolvido_em is null group by 1`). Pela spec, devem aparecer cerca de 90 ha em set/2026 como aviso do Preparo.
- [x] **Step 3:** `python migracao/lancar_ciclo_25_26.py` (só a lista). Mande o CSV e o resumo ao usuário (a expectativa é algo perto de 428 ha). **Pare e espere o ok.**
- [x] **Step 4:** Com o ok: `python migracao/lancar_ciclo_25_26.py --gravar` e anote o lote na memória do projeto. Confira `select origem, count(*) from hub.preparo_entregas group by 1`.
- [x] **Step 5:** Merge na main e push (Pages). Use `reference_github_contas_push` para a conta certa. O usuário testa a tela.

---

### Task 7: Apresentação semanal (`Documents/GitHub/src/scripts`)

**Files:**
- Modify: `C:/Users/lmalerbo/Documents/GitHub/src/scripts/extrair.py:31` (`TABELAS`)
- Modify: `C:/Users/lmalerbo/Documents/GitHub/src/scripts/gerar.py:97-118` (agregação do Preparo) e `:261-281` (`sistematizacao`)

- [ ] **Step 1: Backup** (a pasta não é repositório git):

```bash
cd /c/Users/lmalerbo/Documents/GitHub/src/scripts && cp gerar.py gerar.py.bak-20261028 && cp extrair.py extrair.py.bak-20261028
```

- [ ] **Step 2: `extrair.py`** — acrescente `"preparo_entregas"` ao fim de `TABELAS`. Confira se `baixar_hub` usa só o nome da tabela na URL do PostgREST. Se usar, a view funciona sem mudança.

- [ ] **Step 3: `gerar.py`, agregação** — substitua as linhas 97-118 por:

```python
    etapas = sorted([e for e in L("etapas") if e["modulo_id"] == "preparo"], key=lambda e: e["ordem"])
    ordem = {e["nome"]: i for i, e in enumerate(etapas)}
    entregas = {r["layer"]: r for r in L("preparo_entregas")}
    # O ciclo 25-26 (lançamento único pelo PLANAGRI) não entra no slide: estamos no ciclo 26-27.
    prep = [r for r in L("talhao_preparo") if (entregas.get(r["layer"]) or {}).get("origem") != "ciclo_25_26"]
    fora_25_26 = sum((talhoes.get(l) or {}).get("area_ha") or 0 for l, r in entregas.items() if r["origem"] == "ciclo_25_26")
    por_etapa = {e["nome"]: [set(), 0.0] for e in etapas}
    por_etapa["Entregue"] = [set(), 0.0]
    prmes = collections.defaultdict(float)
    total = 0.0
    for r in prep:
        t = talhoes.get(r["layer"])
        if not t:
            continue
        ha = t["area_ha"] or 0
        total += ha
        nome = "Entregue" if r["etapa"] == "Ok" else r["etapa"]
        por_etapa[nome][0].add(t["cod_faz"])
        por_etapa[nome][1] += ha
        en = entregas.get(r["layer"])
        if en:
            prmes["Lançamento inicial (jun/26)" if en["origem"] == "lancamento_inicial" else en["entregue_em"][:7]] += ha
    por_etapa = {k: [len(v[0]), v[1]] for k, v in por_etapa.items()}
    A["preparo"] = dict(total=total, n_faz=len({talhoes[r["layer"]]["cod_faz"] for r in prep if r["layer"] in talhoes}),
                        n_tal=len(prep), etapa=por_etapa, fora_25_26=fora_25_26,
                        mes=dict(sorted(prmes.items(), key=lambda x: (not x[0].startswith("Lan"), x[0]))))
```

Observação: o painel por etapa passa a contar talhões pela etapa **deles** (o Preparo é por talhão desde 23/10). O número de fazendas por etapa conta cada fazenda em toda etapa em que ela tem talhão. Remova `ordem` se ficar sem uso.

- [ ] **Step 4: `gerar.py`, slide** — em `sistematizacao`:

```python
    barras = [(k if k.startswith("Lan") else rot_mes(k), [(VERDE, v)]) for k, v in pr["mes"].items()]
```

troque o título do painel e a legenda:

```python
            + painel("Projetos Entregues pela Geotecnologia por Mês", colunas(barras, mt="12px") + legenda([(VERDE, "Entregue")], "12px", "12px"), "1", "20px 24px")
```

e a frase final da fonte:

```python
                             "Cada talhão aparece na etapa em que está; “Entregue” = Ok. Mês = data da entrega no Hub; "
                             f"ciclo 25-26 fora do slide ({n(pr['fora_25_26'])} ha lançados pelo PLANAGRI)."),
```

- [ ] **Step 5: Gerar e conferir.** Rode `extrair.py` e `gerar.py` do jeito de sempre (o cabeçalho de cada script mostra o uso) e abra o HTML gerado. Confira:
  - o gráfico mostra a barra "Lançamento inicial (jun/26)" seguida dos meses do ciclo, sem mês de plantio;
  - os KPIs fecham: concluído + a fazer = total;
  - a nota de fonte traz os ha do ciclo 25-26.

  Mostre ao usuário.

- [ ] **Step 6:** Apague os `.bak-20261028` só depois do ok do usuário.

---

## Self-review

- **Cobertura da spec:**

  | Item da spec | Tarefa |
  |---|---|
  | D1 | Tarefas 1 e 4 |
  | D2 | Tarefa 1 |
  | D3 | Tarefas 2 e 6 |
  | D4 | Tarefas 3 e 4 |
  | D5 | Tarefa 5 |
  | D6 | Tarefa 7 |
  | Fora do escopo (Plantio sem mudança na tela) | Tarefa 5, item 6 |

- **Review Focus:**

  | Item | Onde é testado |
  |---|---|
  | 1 e 2 | Tarefa 1, testes 2 e 3 |
  | 3 e 4 | Tarefa 2, testes 3 e 2 |
  | 5 | Tarefa 3, teste 3 |

- **Atenção na execução:** a Consulta do Preparo decide "Entregue" por `f.ok` (`etapa_status`). Depois de 23/10, o fluxo por talhão não grava mais `etapa_status`, então uma fazenda entregue pela tela nova pode aparecer como não entregue na Consulta. Isso é anterior a este plano. Se aparecer no teste de tela, anote como achado separado e não corrija aqui sem falar com o usuário.
