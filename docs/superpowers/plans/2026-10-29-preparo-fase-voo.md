# Preparo: fase de voo antes da Identificação (plano de implementação)

> **Para agentes:** use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans
> para executar tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** cada talhão do Preparo em Identificação mostra a situação do voo de Sistematização/Expansão
lida do Drone MGMT. A tela separa os que já têm material dos que aguardam voo e avisa quando o analista
avança um talhão sem material.

**Arquitetura:** a etapa gravada no banco não muda. O GeoMap ganha uma rota de leitura que devolve os
registros de Sistematização/Expansão por fazenda. Um agente diário do Hub grava esses registros em
`hub.voo_dronemgmt`, e uma view calcula a situação por talhão. O app lê a view e mostra a situação.

**Tecnologia:** Postgres/Supabase (SQL + pytest com Postgres local), Node/Express (GeoMap, `node --test`),
Python (agente de ingestão), JS puro no app (`node --test` com `vm`).

**Spec:** `docs/superpowers/specs/2026-10-29-preparo-fase-voo-design.md`

## Restrições globais

- O Hub **só lê** o Drone MGMT. Nada de POST/PUT/DELETE em `formdata`.
- Projetos que contam: `flightProjectDetails.description` igual a `Sistematização` ou `Expansão`. Levantamento Topográfico **não** conta.
- Safra atual: registro com `createdUtc >= hub.ciclo_inicio()` (hoje 2026-04-01). Não usar o campo `harvest`.
- `controlStatus`: 1–3 = solicitado; 4–8 = processando; **9, 10 e 12 = liberado**; 11 = cancelado (ignorado).
- Sem voo liberado, o Hub **avisa e deixa avançar**. Nunca bloqueia.
- O aviso aparece num modal da própria tela. Nunca usar `confirm()`/`alert()`.
- Rótulos na tela: "Voo não solicitado", "Voo solicitado", "Voado, processando", "Material disponível", "Voo sem leitura".
- Migração em produção: `supabase db query --linked -f <arquivo>`. **Nunca `supabase db push`.**
- Push nos repositórios `lmalerbo/*`: trocar para a conta `lmalerbo` no `gh` só durante o push.

## Pontos de atenção na revisão

1. **O agente parou de rodar** e nenhuma fazenda tem leitura: a tela deve dizer "Voo sem leitura", e não "Voo não solicitado". Teste na Tarefa 1 (`sem_leitura`).
2. **Registro apagado ou trocado de projeto no Drone MGMT:** a próxima leitura da fazenda tem de removê-lo do espelho. Teste na Tarefa 1 (`test_gravar_remove_o_que_sumiu`).
3. **O Drone MGMT falhou numa fazenda:** essa fazenda não pode ser apagada nem marcada como lida. Teste na Tarefa 3 (`test_fazenda_com_erro_fica_de_fora`).
4. **`landPlot` não numérico** (ex.: "1A"): o registro é ignorado sem derrubar o lote. Teste na Tarefa 1 (`test_gravar_ignora_talhao_nao_numerico`).
5. **Voo de safra passada ou cancelado:** não libera. Teste na Tarefa 1 (`test_voo_antigo_ou_cancelado_nao_conta`).

---

### Tarefa 1: banco (espelho, leitura por fazenda, view da situação)

**Arquivos:**
- Criar: `supabase/migrations/20261029090000_preparo_voo.sql`
- Alterar: `tests/preparo/conftest.py` (incluir a migração)
- Criar: `tests/preparo/test_preparo_voo_sql.py`

**Interfaces:**
- Produz: `hub.preparo_voos_gravar(p_secoes int[], p_registros jsonb) returns int` (só `service_role`).
  Cada item de `p_registros` tem as chaves da rota da Tarefa 2:
  `{id, section, landPlot, projeto, controlStatus, verifyFlightSize, createdUtc, scheduledDate, startDateFlight, modifiedUtc}`.
- Produz: view `hub.preparo_voo_talhao(layer bigint, situacao text, lido_em timestamptz)`, só com os talhões em Identificação.
  `situacao` ∈ `sem_leitura | nao_solicitado | solicitado | processando | liberado`.

- [ ] **Passo 1: incluir a migração no conftest**

Em `tests/preparo/conftest.py`, troque a lista por:

```python
MIGRACOES = sorted(fluxo.MIGRACOES + ['20261003090000_modulo_colheita.sql',
                                      '20261028090000_preparo_datas_campo.sql',
                                      '20261029090000_preparo_voo.sql'])
```

- [ ] **Passo 2: escrever os testes que falham**

`tests/preparo/test_preparo_voo_sql.py`:

```python
"""Fase de voo do Preparo (spec 2026-10-29-preparo-fase-voo-design.md)."""
import json
import uuid

from tests.fluxo.test_fluxo_projetos_sql import por


def reg(cod, num, status, projeto='Sistematização', criado='2026-10-27T12:00:00Z', id_=None, land=None):
    return {'id': str(id_ or uuid.uuid4()), 'section': str(cod), 'landPlot': land or str(num), 'projeto': projeto,
            'controlStatus': status, 'verifyFlightSize': 5, 'createdUtc': criado,
            'scheduledDate': criado, 'startDateFlight': None, 'modifiedUtc': criado}


def gravar(banco, secoes, registros):
    return banco.execute('select hub.preparo_voos_gravar(%s, %s::jsonb)',
                         (secoes, json.dumps(registros))).fetchone()[0]


def situacoes(banco, cod):
    return {r[0] % 1000: r[1] for r in banco.execute(
        'select layer, situacao from hub.preparo_voo_talhao where layer / 1000 = %s order by layer', (cod,))}


def test_sem_leitura_ate_o_agente_ler_a_fazenda(banco, fazenda):
    cod = fazenda(2)
    assert situacoes(banco, cod) == {1: 'sem_leitura', 2: 'sem_leitura'}


def test_situacao_pelo_status_mais_avancado(banco, fazenda):
    cod = fazenda(5)
    gravar(banco, [cod], [reg(cod, 1, 2), reg(cod, 2, 4), reg(cod, 3, 9), reg(cod, 3, 2), reg(cod, 4, 10)])
    assert situacoes(banco, cod) == {1: 'solicitado', 2: 'processando', 3: 'liberado', 4: 'liberado',
                                     5: 'nao_solicitado'}


def test_expansao_conta_levantamento_nao(banco, fazenda):
    cod = fazenda(2)
    gravar(banco, [cod], [reg(cod, 1, 9, projeto='Expansão'), reg(cod, 2, 9, projeto='Levantamento Topográfico')])
    assert situacoes(banco, cod) == {1: 'liberado', 2: 'nao_solicitado'}


def test_voo_antigo_ou_cancelado_nao_conta(banco, fazenda):
    cod = fazenda(2)
    gravar(banco, [cod], [reg(cod, 1, 9, criado='2026-03-31T12:00:00Z'), reg(cod, 2, 11)])
    assert situacoes(banco, cod) == {1: 'nao_solicitado', 2: 'nao_solicitado'}


def test_so_talhoes_em_identificacao(banco, fazenda):
    cod = fazenda(2)
    por(banco, 'preparo', cod, 'Escoamento', [2])
    assert set(situacoes(banco, cod)) == {1}


def test_gravar_atualiza_o_mesmo_registro(banco, fazenda):
    cod, id_ = fazenda(1), uuid.uuid4()
    gravar(banco, [cod], [reg(cod, 1, 2, id_=id_)])
    gravar(banco, [cod], [reg(cod, 1, 9, id_=id_)])
    assert situacoes(banco, cod) == {1: 'liberado'}
    assert banco.execute('select count(*) from hub.voo_dronemgmt where dronemgmt_id = %s', (id_,)).fetchone()[0] == 1


def test_gravar_remove_o_que_sumiu(banco, fazenda):
    cod = fazenda(1)
    gravar(banco, [cod], [reg(cod, 1, 9)])
    gravar(banco, [cod], [])
    assert situacoes(banco, cod) == {1: 'nao_solicitado'}


def test_gravar_nao_mexe_em_outra_fazenda_nem_em_outro_projeto(banco, fazenda):
    a, b = fazenda(1), fazenda(1)
    gravar(banco, [b], [reg(b, 1, 9)])
    banco.execute("insert into hub.voo_dronemgmt (dronemgmt_id, layer, projeto_voo, control_status) "
                  "values (%s, %s, 'Falhas Soca', 4)", (uuid.uuid4(), a * 1000 + 1))
    gravar(banco, [a], [])
    assert situacoes(banco, b) == {1: 'liberado'}
    assert banco.execute("select count(*) from hub.voo_dronemgmt where layer = %s and projeto_voo = 'Falhas Soca'",
                         (a * 1000 + 1,)).fetchone()[0] == 1


def test_gravar_ignora_talhao_nao_numerico(banco, fazenda):
    cod = fazenda(1)
    assert gravar(banco, [cod], [reg(cod, 1, 9), reg(cod, 0, 9, land='1A')]) == 1
    assert situacoes(banco, cod) == {1: 'liberado'}


def test_gravar_so_service_role(banco, pessoa, como, fazenda):
    cod = fazenda(1)
    r = como(pessoa(), 'select hub.preparo_voos_gravar(%s, %s::jsonb)', ([cod], '[]'))
    assert r[0] == 'ERRO'
```

- [ ] **Passo 3: rodar e ver falhar**

Rodar: `python -m pytest tests/preparo/test_preparo_voo_sql.py -q`
Esperado: erro ao montar o banco (arquivo de migração não existe).

- [ ] **Passo 4: escrever a migração**

`supabase/migrations/20261029090000_preparo_voo.sql`:

```sql
-- Preparo: fase de voo antes da Identificação (spec 2026-10-29-preparo-fase-voo-design.md).
-- O Hub só lê o Drone MGMT. O agente ingestao/voos_preparo.py grava aqui os registros de
-- Sistematização/Expansão das fazendas com talhões em Identificação. A etapa do talhão não muda.

-- 1 ─────────────────────────────────────────────────────────────────────────
alter table hub.voo_dronemgmt add column criado_dronemgmt timestamptz;  -- createdUtc do registro

-- Quando o agente leu cada fazenda (sem linha = nunca lida → "Voo sem leitura").
create table hub.preparo_voos_leitura (
  cod_faz  int primary key,
  lido_em  timestamptz not null default now()
);
alter table hub.preparo_voos_leitura enable row level security;
create policy leitura_autenticado on hub.preparo_voos_leitura for select to authenticated using (true);

-- 2 ─────────────────────────────────────────────────────────────────────────
-- Substitui, nas fazendas lidas, os registros de Sistematização/Expansão pelo que veio agora
-- (o que sumiu do Drone MGMT sai daqui). landPlot não numérico é ignorado.
create or replace function hub.preparo_voos_gravar(p_secoes int[], p_registros jsonb)
returns int language plpgsql security definer set search_path = hub as $$
declare
  v_n int;
begin
  delete from voo_dronemgmt v
   where v.projeto_voo in ('Sistematização', 'Expansão')
     and (v.layer / 1000)::int = any(p_secoes)
     and not exists (select 1 from jsonb_array_elements(coalesce(p_registros, '[]'::jsonb)) r
                      where r->>'id' = v.dronemgmt_id::text);

  -- case: o cast só roda depois da checagem (o where não garante ordem de avaliação).
  insert into voo_dronemgmt (dronemgmt_id, layer, projeto_voo, control_status, verify_flight_size,
                             data_agendada, inicio_voo, criado_dronemgmt, modificado_dronemgmt, sincronizado_em)
  select dronemgmt_id, layer, projeto_voo, control_status, verify_flight_size,
         data_agendada, inicio_voo, criado_dronemgmt, modificado_dronemgmt, now()
    from (select (r->>'id')::uuid                       as dronemgmt_id,
                 case when r->>'section' ~ '^\d+$' and r->>'landPlot' ~ '^\d+$'
                      then (r->>'section')::bigint * 1000 + (r->>'landPlot')::bigint end as layer,
                 r->>'projeto'                          as projeto_voo,
                 (r->>'controlStatus')::int             as control_status,
                 (r->>'verifyFlightSize')::int          as verify_flight_size,
                 (r->>'scheduledDate')::timestamptz     as data_agendada,
                 (r->>'startDateFlight')::timestamptz   as inicio_voo,
                 (r->>'createdUtc')::timestamptz        as criado_dronemgmt,
                 (r->>'modifiedUtc')::timestamptz       as modificado_dronemgmt
            from jsonb_array_elements(coalesce(p_registros, '[]'::jsonb)) r
           where r->>'projeto' in ('Sistematização', 'Expansão')) n
   where layer is not null and (layer / 1000)::int = any(p_secoes)
  on conflict (dronemgmt_id) do update
     set layer = excluded.layer, projeto_voo = excluded.projeto_voo, control_status = excluded.control_status,
         verify_flight_size = excluded.verify_flight_size, data_agendada = excluded.data_agendada,
         inicio_voo = excluded.inicio_voo, criado_dronemgmt = excluded.criado_dronemgmt,
         modificado_dronemgmt = excluded.modificado_dronemgmt, sincronizado_em = now();
  get diagnostics v_n = row_count;

  insert into preparo_voos_leitura (cod_faz, lido_em)
  select unnest(p_secoes), now()
  on conflict (cod_faz) do update set lido_em = excluded.lido_em;
  return v_n;
end $$;

-- 3 ─────────────────────────────────────────────────────────────────────────
-- Situação do voo de cada talhão em Identificação, pelo registro mais avançado da safra atual.
-- controlStatus: 1–3 solicitado, 4–8 processando, 9/10/12 liberado, 11 cancelado (ignorado).
create or replace view hub.preparo_voo_talhao with (security_invoker = true) as
select p.layer,
       case when l.cod_faz is null then 'sem_leitura'
            else (array['nao_solicitado', 'solicitado', 'processando', 'liberado'])[1 + coalesce(max(
                   case when v.control_status in (9, 10, 12)  then 3
                        when v.control_status between 4 and 8 then 2
                        when v.control_status between 1 and 3 then 1 end), 0)]
       end as situacao,
       l.lido_em
  from hub.talhao_preparo p
  left join hub.preparo_voos_leitura l on l.cod_faz = (p.layer / 1000)::int
  left join hub.voo_dronemgmt v on v.layer = p.layer
        and v.projeto_voo in ('Sistematização', 'Expansão')
        and v.control_status is distinct from 11
        and v.criado_dronemgmt >= hub.ciclo_inicio()
 where p.etapa = 'Identificação'
 group by p.layer, l.cod_faz, l.lido_em;

grant select on hub.preparo_voo_talhao to authenticated, service_role;
grant select on hub.preparo_voos_leitura to authenticated;
grant all on hub.preparo_voos_leitura to service_role;
revoke all on function hub.preparo_voos_gravar(int[], jsonb) from public, anon, authenticated;
grant execute on function hub.preparo_voos_gravar(int[], jsonb) to service_role;
```

- [ ] **Passo 5: rodar e ver passar**

Rodar: `python -m pytest tests/preparo -q`
Esperado: todos passam, incluindo os testes antigos de `tests/preparo`.

- [ ] **Passo 6: commit**

```bash
git add supabase/migrations/20261029090000_preparo_voo.sql tests/preparo/conftest.py tests/preparo/test_preparo_voo_sql.py
git commit -m "Preparo: espelho dos voos de Sistematização/Expansão e situação do voo por talhão"
```

---

### Tarefa 2: banco, registro do aviso "avançou sem voo"

**Arquivos:**
- Alterar: `supabase/migrations/20261029090000_preparo_voo.sql` (acrescentar no fim)
- Alterar: `tests/preparo/test_preparo_voo_sql.py`

**Interfaces:**
- Produz: `hub.preparo_aviso_sem_voo(p_cod_faz int, p_talhoes int[]) returns int` (`authenticated`, exige poder editar o Preparo).
  Grava uma linha por talhão em `hub.log_auditoria` (`campo='voo_aviso'`, `valor_novo='avancou_sem_voo'`).
  Devolve o número de linhas gravadas.

- [ ] **Passo 1: testes que falham** (acrescentar ao arquivo de teste)

```python
def test_aviso_sem_voo_fica_no_log(banco, pessoa, como, fazenda):
    uid, cod = pessoa(), fazenda(3)
    assert como(uid, 'select hub.preparo_aviso_sem_voo(%s, %s)', (cod, [1, 3])) == [(2,)]
    linhas = banco.execute("select entidade_id % 1000, usuario_id, valor_novo from hub.log_auditoria "
                           "where campo = 'voo_aviso' and entidade_id / 1000 = %s order by 1", (cod,)).fetchall()
    assert linhas == [(1, uid, 'avancou_sem_voo'), (3, uid, 'avancou_sem_voo')]


def test_aviso_sem_voo_exige_editar_preparo(banco, pessoa, como, fazenda):
    cod = fazenda(1)
    for uid in (pessoa(papel='leitura'), pessoa(modulos=('plantio',))):
        r = como(uid, 'select hub.preparo_aviso_sem_voo(%s, %s)', (cod, [1]))
        assert r[0] == 'ERRO'
```

- [ ] **Passo 2: rodar e ver falhar**

Rodar: `python -m pytest tests/preparo/test_preparo_voo_sql.py -q -k aviso`
Esperado: FAIL ("function hub.preparo_aviso_sem_voo ... does not exist").

- [ ] **Passo 3: acrescentar ao fim da migração**

```sql
-- 4 ─────────────────────────────────────────────────────────────────────────
-- O analista avançou da Identificação talhões sem material de voo (aviso aceito na tela).
create or replace function hub.preparo_aviso_sem_voo(p_cod_faz int, p_talhoes int[])
returns int language plpgsql security definer set search_path = hub as $$
declare
  v_n int;
begin
  perform hub.projeto_conferir('preparo', p_cod_faz);
  insert into log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, usuario_id, origem)
  select 'preparo', 'talhao', p_cod_faz::bigint * 1000 + t, 'voo_aviso', 'avancou_sem_voo', auth.uid(), 'usuario'
    from unnest(p_talhoes) t;
  get diagnostics v_n = row_count;
  return v_n;
end $$;

revoke all on function hub.preparo_aviso_sem_voo(int, int[]) from public, anon;
grant execute on function hub.preparo_aviso_sem_voo(int, int[]) to authenticated;
```

- [ ] **Passo 4: rodar e ver passar**

Rodar: `python -m pytest tests/preparo -q`
Esperado: todos passam.

- [ ] **Passo 5: commit**

```bash
git add supabase/migrations/20261029090000_preparo_voo.sql tests/preparo/test_preparo_voo_sql.py
git commit -m "Preparo: registra no log quando o analista avança sem material de voo"
```

---

### Tarefa 3: GeoMap, rota de leitura dos voos do Preparo

Repositório: `C:\Users\lmalerbo\Documents\GitHub\geomap` (worktree própria, branch `preparo-voos`).

**Arquivos:**
- Criar: `backend/src/lib/voosPreparo.js`
- Alterar: `backend/src/routes/integracao.js` (rota nova depois da `/integracao/dronemgmt/situacao`)
- Criar: `backend/test/voos-preparo.test.js`

**Interfaces:**
- Produz: `POST /integracao/dronemgmt/preparo/voos`, cabeçalho `x-hub-token`, corpo `{ secoes: ["10724", ...] }` (1 a 50, só dígitos).
  Resposta: `{ resultados: [{ section, registros: [{id, section, landPlot, projeto, controlStatus, verifyFlightSize, createdUtc, scheduledDate, startDateFlight, modifiedUtc}] } | { section, erro }] }`.
  Os registros **incluem** os cancelados (11), porque quem filtra é a view do Hub.

- [ ] **Passo 1: teste que falha**

`backend/test/voos-preparo.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { filtroVoosPreparo, mapearVoosPreparo, secaoValida } from "../src/lib/voosPreparo.js";

const reg = (projeto, extra = {}) => ({
  id: "3592d102-3d8e-4a5a-830a-c09186c1099f", section: "10724", landPlot: 2, controlStatus: 4,
  verifyFlightSize: 5, createdUtc: "2026-10-27T12:00:00Z", scheduledDate: "2026-10-27T12:00:00Z",
  startDateFlight: "2026-10-28T10:00:00Z", modifiedUtc: "2026-10-28T11:00:00Z", harvest: 2026,
  flightProjectDetails: projeto ? { description: projeto } : undefined, ...extra,
});

test("filtro pela unidade e pela fazenda", () => {
  assert.deepEqual(JSON.parse(filtroVoosPreparo("u-1", "10724")),
    { $and: [{ unitId: "UUID('u-1')" }, { section: "10724" }] });
});

test("só Sistematização e Expansão, com os campos que o Hub grava", () => {
  const out = mapearVoosPreparo([reg("Sistematização"), reg("Expansão", { controlStatus: 11 }),
                                 reg("Levantamento Topográfico"), reg("Falhas Soca"), reg(null)]);
  assert.equal(out.length, 2);
  assert.deepEqual(out[0], {
    id: "3592d102-3d8e-4a5a-830a-c09186c1099f", section: "10724", landPlot: "2", projeto: "Sistematização",
    controlStatus: 4, verifyFlightSize: 5, createdUtc: "2026-10-27T12:00:00Z",
    scheduledDate: "2026-10-27T12:00:00Z", startDateFlight: "2026-10-28T10:00:00Z", modifiedUtc: "2026-10-28T11:00:00Z",
  });
  assert.equal(out[1].controlStatus, 11);   // cancelado vai junto; o Hub filtra
});

test("seção só com dígitos", () => {
  assert.ok(secaoValida("10724"));
  for (const s of ["", "10724')", "abc", 10724, null]) assert.ok(!secaoValida(s), String(s));
});
```

- [ ] **Passo 2: rodar e ver falhar**

Rodar (em `backend/`): `node --test test/voos-preparo.test.js`
Esperado: FAIL (módulo `voosPreparo.js` não existe).

- [ ] **Passo 3: implementar a lib**

`backend/src/lib/voosPreparo.js`:

```js
// Voos do Preparo (Hub, spec 2026-10-29-preparo-fase-voo-design.md): só leitura.
// O analista agenda Sistematização/Expansão direto no DroneManagement; o Hub só
// acompanha a situação. Cancelados (controlStatus 11) vão junto: quem filtra é o Hub.

export const PROJETOS_VOO_PREPARO = ["Sistematização", "Expansão"];

export function secaoValida(s) {
  return typeof s === "string" && /^\d{1,6}$/.test(s);
}

export function filtroVoosPreparo(unitId, section) {
  return JSON.stringify({ $and: [{ unitId: `UUID('${unitId}')` }, { section }] });
}

export function mapearVoosPreparo(registros) {
  return registros
    .filter((r) => PROJETOS_VOO_PREPARO.includes(r.flightProjectDetails?.description))
    .map((r) => ({
      id: r.id, section: r.section, landPlot: String(r.landPlot), projeto: r.flightProjectDetails.description,
      controlStatus: r.controlStatus, verifyFlightSize: r.verifyFlightSize ?? null,
      createdUtc: r.createdUtc, scheduledDate: r.scheduledDate ?? null,
      startDateFlight: r.startDateFlight ?? null, modifiedUtc: r.modifiedUtc ?? null,
    }));
}
```

- [ ] **Passo 4: rodar e ver passar**

Rodar: `node --test test/voos-preparo.test.js`
Esperado: PASS.

- [ ] **Passo 5: rota**

Em `backend/src/routes/integracao.js`, acrescente aos imports:

```js
import { buscarTodosRegistros } from "../lib/consultaDroneMgmt.js";
import { filtroVoosPreparo, mapearVoosPreparo, secaoValida } from "../lib/voosPreparo.js";
```

Logo depois da rota `/integracao/dronemgmt/situacao`, acrescente a rota abaixo (o middleware da chave do Hub já vale para todo o prefixo `/integracao/dronemgmt`):

```js
// Voos de Sistematização/Expansão por fazenda, pra fase de voo do Preparo no Hub.
// Só leitura. body: { secoes: ["10724", ...] } (até 50).
integracaoRouter.post("/integracao/dronemgmt/preparo/voos", async (req, res) => {
  const { secoes } = req.body || {};
  if (!Array.isArray(secoes) || !secoes.length || secoes.length > 50 || !secoes.every(secaoValida)) {
    return res.status(400).json({ erro: "informe secoes (1 a 50, só dígitos)" });
  }
  const resultados = [];
  for (const section of secoes) {
    try {
      const { registros } = await buscarTodosRegistros(filtroVoosPreparo(UNIT_ID, section));
      resultados.push({ section, registros: mapearVoosPreparo(registros) });
    } catch (err) {
      resultados.push({ section, erro: err.message });
    }
  }
  res.json({ resultados });
});
```

Confira que o `exigirChave('x-hub-token', 'HUB_INTEGRACAO_TOKEN')` é aplicado com `integracaoRouter.use("/integracao/dronemgmt", ...)`, e não rota por rota. Se for rota por rota, aplique-o também na rota nova, do mesmo jeito.

- [ ] **Passo 6: suíte inteira**

Rodar: `npm test` (em `backend/`)
Esperado: tudo passa.

- [ ] **Passo 7: commit**

```bash
git add backend/src/lib/voosPreparo.js backend/src/routes/integracao.js backend/test/voos-preparo.test.js
git commit -m "Integração Hub: leitura dos voos de Sistematização/Expansão por fazenda (Preparo)"
```

---

### Tarefa 4: agente diário `voos_preparo.py`

**Arquivos:**
- Criar: `ingestao/voos_preparo.py`
- Alterar: `ingestao/rodar_diario.py` (incluir no fim de `ETAPAS`)
- Criar: `tests/ingestao/test_voos_preparo.py`

**Interfaces:**
- Consome: a rota da Tarefa 3 e `hub.preparo_voos_gravar` da Tarefa 1.
- Produz: `separar(resultados) -> (secoes: list[int], registros: list[dict])`, que deixa de fora as fazendas com erro.

- [ ] **Passo 1: teste que falha**

`tests/ingestao/test_voos_preparo.py`:

```python
"""Agente dos voos do Preparo: o que vai para o banco a partir da resposta do GeoMap."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ingestao'))
import voos_preparo  # noqa: E402


def test_fazenda_com_erro_fica_de_fora():
    r1 = {'id': 'a', 'section': '10080', 'landPlot': '4', 'controlStatus': 4}
    secoes, registros = voos_preparo.separar([
        {'section': '10080', 'registros': [r1]},
        {'section': '10314', 'erro': 'DroneManagement respondeu 500'},
        {'section': '10724', 'registros': []},
    ])
    assert secoes == [10080, 10724]          # 10314 não é apagada nem marcada como lida
    assert registros == [r1]


def test_lotes_de_50():
    assert [len(l) for l in voos_preparo.lotes(list(range(120)), 50)] == [50, 50, 20]
```

- [ ] **Passo 2: rodar e ver falhar**

Rodar: `python -m pytest tests/ingestao/test_voos_preparo.py -q`
Esperado: FAIL (`ModuleNotFoundError: voos_preparo`).

- [ ] **Passo 3: implementar**

`ingestao/voos_preparo.py`:

```python
"""Agente da fase de voo do Preparo: lê no Drone MGMT (via GeoMap, rota /integracao)
os voos de Sistematização/Expansão das fazendas com talhões em Identificação e grava
o espelho em hub.voo_dronemgmt. A situação por talhão sai da view hub.preparo_voo_talhao.

Só leitura no Drone MGMT. Precisa, no hub-geotech-supabase.env: GEOMAP_API_URL e
HUB_INTEGRACAO_TOKEN (os mesmos do voos_linhas_colheita.py).

Uso:  python ingestao/voos_preparo.py [--simular]
"""

import argparse
import collections
import sys

import requests
import truststore

from comum import Hub, carregar_env

truststore.inject_into_ssl()   # o firewall da empresa inspeciona TLS (certificado só no Windows)


def lotes(itens, tamanho):
    return [itens[i:i + tamanho] for i in range(0, len(itens), tamanho)]


def separar(resultados):
    """Fazendas lidas sem erro e os registros delas. Fazenda com erro fica de fora: nada é apagado nela."""
    secoes, registros = [], []
    for r in resultados:
        if r.get('erro'):
            print(f"  {r['section']}: {r['erro']}")
            continue
        secoes.append(int(r['section']))
        registros += r['registros']
    return secoes, registros


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true', help='mostra o que leu, sem gravar')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    env, hub = carregar_env(), Hub()

    em_ident = hub.selecionar('talhao_preparo', 'layer', {'etapa': 'eq.Identificação'})
    fazendas = sorted({str(r['layer'] // 1000) for r in em_ident})
    print(f'{len(em_ident)} talhões em Identificação, {len(fazendas)} fazendas')

    for lote in lotes(fazendas, 50):
        r = requests.post(env['GEOMAP_API_URL'].rstrip('/') + '/integracao/dronemgmt/preparo/voos',
                          json={'secoes': lote}, timeout=300, headers={'x-hub-token': env['HUB_INTEGRACAO_TOKEN']})
        if not r.ok:
            raise RuntimeError(f'GeoMap: HTTP {r.status_code} {r.text[:200]}')
        secoes, registros = separar(r.json()['resultados'])
        print(f'  lote: {len(secoes)} fazendas lidas, {len(registros)} registros')
        if args.simular:
            print('   ', collections.Counter((x['projeto'], x['controlStatus']) for x in registros))
            continue
        hub.rpc('preparo_voos_gravar', {'p_secoes': secoes, 'p_registros': registros})

    if not args.simular:
        sit = collections.Counter(x['situacao'] for x in hub.selecionar('preparo_voo_talhao', 'situacao'))
        print('Situação dos talhões em Identificação:', dict(sit))


if __name__ == '__main__':
    main()
```

Em `ingestao/rodar_diario.py`:

```python
ETAPAS = ['base_fazendas.py', 'talhao_geom.py', 'planagri.py', 'conservacao.py', 'icol.py', 'voos_preparo.py']
```

- [ ] **Passo 4: rodar e ver passar**

Rodar: `python -m pytest tests/ingestao -q`
Esperado: PASS.

- [ ] **Passo 5: commit**

```bash
git add ingestao/voos_preparo.py ingestao/rodar_diario.py tests/ingestao/test_voos_preparo.py
git commit -m "Agente diário dos voos do Preparo (Sistematização/Expansão, só leitura)"
```

---

### Tarefa 5: app, dados (situação do voo em cada talhão)

**Arquivos:**
- Alterar: `app/dados.js` (constante, `montarPreparo`, recarga por fazenda)
- Alterar: `app/index.html:2566-2627` (carga inicial lê a view)
- Alterar: `tests/app/dados_puro.test.js`

**Interfaces:**
- Produz (globais de `dados.js`, usados em `projetos.js`):
  - `VOO_PREPARO` = `{sem_leitura, nao_solicitado, solicitado, processando, liberado}` → `{l, c}`.
  - `vooAguardando(t) -> boolean`: `t.e === 0 && t.voo !== 'liberado'`.
  - `montarPreparo(linhas, etapas, status, nomeUsr, entregas, voos)`: cada `tals[i]` ganha `voo`
    (situação para `e === 0`, sem dado = `'sem_leitura'`; `null` nas outras etapas).

- [ ] **Passo 1: testes que falham**

Em `tests/app/dados_puro.test.js`, no teste "cada talhão leva a etapa do banco como índice", troque a expectativa dos `tals` por:

```js
  assert.deepStrictEqual(limpo(juntas[1].tals), [
    { layer: 10455001, num: 1, ha: 10.04, e: 1, cons: null, voo: null },
    { layer: 10455002, num: 2, ha: 10.04, e: 4, cons: null, voo: null },
  ]);
```

E acrescente:

```js
test('Preparo: talhão em Identificação leva a situação do voo; sem dado = sem leitura', () => {
  const linhas = [talPrep(10724, 1, 'Identificação'), talPrep(10724, 2, 'Identificação'), talPrep(10724, 3, 'Escoamento')];
  const [f] = ctx.montarPreparo(linhas, [], [], {}, [], [{ layer: 10724001, situacao: 'liberado' }]);
  assert.deepStrictEqual(limpo(f.tals.map((t) => t.voo)), ['liberado', 'sem_leitura', null]);
  assert.deepStrictEqual(limpo(f.tals.map((t) => ctx.vooAguardando(t))), [false, true, false]);
});

test('Preparo: todas as situações têm rótulo e cor', () => {
  for (const s of ['sem_leitura', 'nao_solicitado', 'solicitado', 'processando', 'liberado']) {
    assert.ok(ctx.VOO_PREPARO[s].l && ctx.VOO_PREPARO[s].c, s);
  }
});
```

- [ ] **Passo 2: rodar e ver falhar**

Rodar: `node --test tests/app/dados_puro.test.js`
Esperado: FAIL (`voo` ausente; `vooAguardando` não definido).

- [ ] **Passo 3: implementar em `app/dados.js`**

Depois de `const ETAPAS_PREPARO=...` (linha 13):

```js
// Situação do voo (Sistematização/Expansão) de cada talhão em Identificação, da view preparo_voo_talhao.
// Só "liberado" tem material para identificar; o resto aguarda voo.
const VOO_PREPARO={
  sem_leitura:{l:'Voo sem leitura',c:'#9895a2'},
  nao_solicitado:{l:'Voo não solicitado',c:'#9895a2'},
  solicitado:{l:'Voo solicitado',c:'#2566e8'},
  processando:{l:'Voado, processando',c:'#d4890a'},
  liberado:{l:'Material disponível',c:'#16a76b'},
};
function vooAguardando(t){return t.e===0&&t.voo!=='liberado'}
```

Em `montarPreparo`: assinatura `function montarPreparo(linhas,etapas,status,nomeUsr,entregas,voos){`. Depois de `const ent=...`:

```js
  const vooSit=new Map((voos||[]).map(v=>[v.layer,v.situacao]));
```

E troque o `f.tals.push(...)` por:

```js
    f.tals.push({layer:r.layer,num:t.talhao_num,ha:t.area_ha||0,e,cons:r.conservacao_em||null,
                 voo:e===0?vooSit.get(r.layer)||'sem_leitura':null});
```

Na recarga por fazenda (`modulo==='preparo'`, linha ~195), acrescente a leitura da view ao `Promise.all` e passe-a adiante:

```js
    const [linhas,etapas,status,entregas,voos,revs]=await Promise.all([
      lerTudo(()=>sb.from('talhao_preparo').select(SEL_PREPARO).gte('layer',ini).lte('layer',fim).order('layer')),
      lerTudo(()=>sb.from('etapas').select('id,ordem').eq('modulo_id','preparo').order('ordem')),
      lerTudo(()=>sb.from('etapa_status').select(SEL_ETAPA_STATUS).eq('entidade_id',cod).order('etapa_id')),
      lerTudo(()=>sb.from('preparo_entregas').select('layer,entregue_em,origem').eq('cod_faz',cod).order('layer')),
      lerTudo(()=>sb.from('preparo_voo_talhao').select('layer,situacao').gte('layer',ini).lte('layer',fim).order('layer')),
      revisoes]);
    const nomeUsr=Object.fromEntries(USUARIOS.map(u=>[u.id,u.nome]));
    return ()=>{trocarFazenda(FZ_P,cod,montarPreparo(linhas,etapas,status,nomeUsr,entregas,voos)[0]);trocarArquivos(modulo,cod,revs);};
```

- [ ] **Passo 4: carga inicial em `app/index.html`**

No `Promise.all` da linha 2566, acrescente `vooP` logo depois de `entregasP` (na desestruturação e na lista, na mesma posição):

```js
    lerTudo(()=>sb.from('preparo_voo_talhao').select('layer,situacao').order('layer')),
```

E na linha 2627:

```js
  FZ_P.length=0;FZ_P.push(...montarPreparo(preparo,etapas,status,nomeUsr,entregasP,vooP));
```

- [ ] **Passo 5: rodar e ver passar**

Rodar: `node --test tests/app/`
Esperado: PASS.

- [ ] **Passo 6: commit**

```bash
git add app/dados.js app/index.html tests/app/dados_puro.test.js
git commit -m "Preparo: app lê a situação do voo de cada talhão em Identificação"
```

---

### Tarefa 6: app, tela (barra, etiqueta e aviso ao avançar)

**Arquivos:**
- Alterar: `app/projetos.js` (`pjNorm`, `distribuicaoHtml`, `painelHtml`, `pjAcaoRpc`, modal novo, CSS)

**Interfaces:**
- Consome: `VOO_PREPARO`, `vooAguardando` (Tarefa 5) e `hub.preparo_aviso_sem_voo` (Tarefa 2).

- [ ] **Passo 1: levar `voo` adiante em `pjNorm`** (linha 68)

```js
    talhoes:f.tals.map(t=>({num:t.num,ha:t.ha,e:Number(t.e)||0,sist_conser:t.sist_conser,mes:t.mes,cons:t.cons,mapeamento:t.mapeamento,voo:t.voo})),etapas:pjEtapas(mod)};
```

Logo abaixo de `pjContagens`:

```js
// Preparo: talhões em Identificação ainda sem material de voo (só aparece no Preparo).
function pjSemVoo(fz,lista){return fz.modulo==='preparo'?(lista||fz.talhoes).filter(vooAguardando):[]}
// Fundo do segmento de Identificação: a parte que aguarda voo em cinza, à esquerda.
function pjFundoSeg(fz,i,q){
  const a=i===0?pjSemVoo(fz).length:0,cor=fz.etapas[i].c;
  if(!a)return cor;
  const p=Math.round(a/q*100);
  return `linear-gradient(90deg,${VOO_PREPARO.nao_solicitado.c} 0 ${p}%,${cor} ${p}% 100%)`;
}
```

- [ ] **Passo 2: barra e legenda**

Em `distribuicaoHtml` (linha 731), troque `background:${fz.etapas[i].c}` por `background:${pjFundoSeg(fz,i,q)}`.

Em `painelHtml`, depois de `const cont=pjContagens(fz)...` (linha 739):

```js
    const semVoo=pjSemVoo(fz).length;
```

Na linha 745, troque `background:${et[i].c}` por `background:${pjFundoSeg(fz,i,q)}`. Na legenda (linha 746):

```js
    const leg=cont.map((q,i)=>q?`<span class="pj-leg-i"><i style="background:${et[i].c}"></i>${pjH(et[i].l)} ${q}${i===0&&semVoo?` <span class="pj-leg-voo">(${semVoo} aguardando voo)</span>`:''}</span>`:'').join('');
```

No número do passo (linha 754), troque `<small>${cont[i]}</small>` por:

```js
<small>${cont[i]}${i===0&&semVoo?` · ${semVoo} s/ voo`:''}</small>
```

- [ ] **Passo 3: etiqueta no talhão** (linha 762)

```js
        `<td><span class="ebadge" style="background:${e.c}1a;color:${e.c}">${pjH(e.l)}</span>`+
        (t.e===0&&t.voo&&VOO_PREPARO[t.voo]?`<span class="pj-voo" style="background:${VOO_PREPARO[t.voo].c}1a;color:${VOO_PREPARO[t.voo].c}">${pjH(VOO_PREPARO[t.voo].l)}</span>`:'')+
        `</td></tr>`;
```

No CSS do arquivo, perto de `.pj-tal-sel` (linha ~857):

```css
.pj-voo{display:inline-block;margin-left:6px;font-size:10px;font-weight:700;border-radius:6px;padding:1px 6px}
.pj-leg-voo{color:var(--t3)}
```

- [ ] **Passo 4: aviso ao confirmar a identificação**

Em `pjAcaoRpc` (linha 210), logo depois de `if(acao==='observacoes')...`:

```js
  if(acao==='identificacao'){
    const sem=pjSemVoo(c.fz,c.fz.talhoes.filter(t=>nums.includes(t.num)));
    if(sem.length){pjAbrirSemVoo(c,nums,sem.map(t=>t.num));return}
  }
```

Depois de `pjConfirmarObs`, acrescente o modal (mesmo molde do de observações):

```js
// Aviso: talhões sem material de voo. Avançar continua permitido; a decisão fica no log.
function pjModalSemVoo(){
  let m=document.getElementById('pj-modal-semvoo');
  if(m)return m;
  m=document.createElement('div');
  m.id='pj-modal-semvoo';
  m.className='modal-fundo off pj-modal';
  m.innerHTML=`<div class="modal-caixa pj-caixa" role="dialog" aria-modal="true" aria-labelledby="pj-semvoo-t">`+
    `<div class="modal-t" id="pj-semvoo-t">Talhões sem material de voo</div>`+
    `<div class="pj-volta-txt" data-pj-semvoo-txt></div>`+
    `<div class="pj-erro" data-pj-semvoo-erro role="alert"></div>`+
    `<div class="modal-botoes"><button type="button" class="btn-retro" data-pj-fechar>Cancelar</button>`+
    `<button type="button" class="btn-acao" data-pj-semvoo-ok>Avançar mesmo assim</button></div></div>`;
  document.body.appendChild(m);
  m.addEventListener('click',e=>{
    if(e.target===m||e.target.closest('[data-pj-fechar]'))return pjFecharModal(m);
    const ok=e.target.closest('[data-pj-semvoo-ok]');
    if(ok)pjConfirmarSemVoo(ok,m);
  });
  m.addEventListener('keydown',e=>{if(e.key==='Escape')pjFecharModal(m)});
  return m;
}
function pjAbrirSemVoo(c,nums,sem){
  const m=pjModalSemVoo();
  m._V={c,nums,sem};
  m._busy=false;
  const lista=sem.map(n=>{const t=c.fz.talhoes.find(x=>x.num===n);return `${pjH(n)} (${pjH(VOO_PREPARO[t.voo]?.l||'sem dado')})`}).join(', ');
  m.querySelector('[data-pj-semvoo-txt]').innerHTML=`<strong>${pjNTal(sem.length)}</strong> de ${nums.length} ainda não ${sem.length===1?'tem':'têm'} material de voo liberado: ${lista}. Avançar mesmo assim?`;
  m.querySelector('[data-pj-semvoo-erro]').textContent='';
  m.classList.remove('off');
  setTimeout(()=>m.querySelector('[data-pj-semvoo-ok]').focus(),50);
}
async function pjConfirmarSemVoo(btn,m){
  const V=m._V,c=V.c;
  const err=m.querySelector('[data-pj-semvoo-erro]');
  err.textContent='';
  m._busy=true;
  try{
    const d=await pjChamar(btn,'projeto_avancar',{p_modulo:c.mod,p_cod_faz:c.cod,p_acao:'identificacao',p_talhoes:V.nums},{silencioso:true});
    await pjChamar(null,'preparo_aviso_sem_voo',{p_cod_faz:c.cod,p_talhoes:V.sem},{silencioso:true}).catch(()=>{});
    m._busy=false;
    m.classList.add('off');
    delete PJ.tl[c.key];
    showToast(`${pjNTal(Number(pjVal(d))||V.nums.length)} avançaram`);
    await recarregar(pjAlvo(c));
  }catch(e){
    m._busy=false;
    err.textContent=e.message||'Não foi possível avançar.';
  }
}
```

(O log do aviso é complementar: se falhar, o avanço já gravado não volta, por isso o `.catch`.)

- [ ] **Passo 5: conferir na tela, local**

Suba o app como nas tarefas anteriores do Hub (skill `run`). Com o banco local ou de produção já migrado (Tarefa 7), abra Preparo → SAO JOAO 14 (10724) e confira:
- a barra cinza com a legenda "Identificação 2 (2 aguardando voo)";
- os dois talhões com a etiqueta "Voo não solicitado";
- selecionar e clicar em "Confirmar identificação" abre o modal. **Cancele**: é produção.

Numa fazenda com material (ex.: 10080 depois que o processamento terminar), confira que o botão avança sem modal.

- [ ] **Passo 6: rodar a suíte do app**

Rodar: `node --test tests/app/`
Esperado: PASS.

- [ ] **Passo 7: commit**

```bash
git add app/projetos.js
git commit -m "Preparo: barra, etiqueta e aviso de talhão sem material de voo"
```

---

### Tarefa 7: produção (com o usuário, passo a passo)

Ordem obrigatória: banco → GeoMap → agente → app.

- [ ] **Passo 1: migração.** Mostre o arquivo ao usuário e aplique com `supabase db query --linked -f supabase/migrations/20261029090000_preparo_voo.sql`. Confira: `select situacao, count(*) from hub.preparo_voo_talhao group by 1;`. Esperado: tudo em `sem_leitura`.
- [ ] **Passo 2: GeoMap.** Faça o merge de `preparo-voos` na main do geomap e o push (trocar o `gh` para `lmalerbo` só durante o push). Espere o Render publicar e confira que `POST /integracao/dronemgmt/preparo/voos` com `{"secoes":["10724"]}` responde 200.
- [ ] **Passo 3: agente.** `python ingestao/voos_preparo.py --simular`, depois sem `--simular`. Compare com o levantamento de 29/10 da spec (6 processando, 17 solicitado, 6 não solicitado). Os números podem ter andado desde então.
- [ ] **Passo 4: app.** Faça o merge no main do hub-geotech e o push (o Pages publica). Confira a tela com o usuário (10724 e ITACOLOMY 10468).
- [ ] **Passo 5:** atualizar a memória do projeto com o que foi ao ar e como desfazer (`drop view hub.preparo_voo_talhao; drop function hub.preparo_voos_gravar(int[], jsonb), hub.preparo_aviso_sem_voo(int, int[]); drop table hub.preparo_voos_leitura; alter table hub.voo_dronemgmt drop column criado_dronemgmt;`).
