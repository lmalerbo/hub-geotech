# Tela de Usuários: nível por módulo e acesso por mapa no GeoMap — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar o papel único por um nível em cada módulo (Sem acesso / Leitura / Solicitante só no Drone / Editor), deixar os Mapas de aplicação só ligar e desligar, somar ao GeoMap um acesso individual por mapa (que só acrescenta ao dos grupos) e reorganizar a tela Usuários como na maquete.

**Architecture:**
- **Níveis:** o nível passa a morar em `hub.usuario_modulos.nivel`. `hub.pode_editar`, `nova_revisao` e `drone_solicitar` leem dali, e `hub.usuarios.papel` fica congelado, só para voltar atrás.
- **O que cada pessoa acessa:** `hub.acessos` guarda `niveis jsonb` e `geomap_mapas jsonb`. A função `contas` grava e empurra os mapas ao GeoMap.
- **GeoMap:** ganha `permissoes_usuario` e a view `permissoes_efetivas` (grupo ∪ individual, com `bool_or`), que passa a ser a única fonte das checagens de mapa.
- **App:** a lógica da tela vai para `app/usuarios.js` (sem DOM, testável). A tela fica em `app/index.html`.

**Tech Stack:**
- Supabase (Postgres, Edge Function/Deno);
- HTML+JS do Hub;
- Node/Express + Postgres (GeoMap);
- testes com pytest + Postgres local, `node --test` e Playwright.

**Spec:** `docs/superpowers/specs/2026-10-22-usuarios-niveis-design.md`
**Maquete:** https://claude.ai/artifact/LDm98phg3ttmT82hL4DJmd

## Global Constraints

- **Dois repositórios:**
  - **Hub:** `lmalerbo/hub-geotech`, worktree `C:\Users\lmalerbo\Documents\hub-geotech-usuarios`, branch `usuarios-niveis`, criada a partir de `main`.
  - **GeoMap:** `lmalerbo/geomap`, worktree `C:\Users\lmalerbo\Documents\GitHub\geomap-acesso-mapa`, branch `feat/acesso-por-mapa`, criada a partir de `origin/master`.
    - Outras sessões trabalham na pasta `geomap`, hoje em `feat/indicadores-voo`, e nas demais worktrees do GeoMap: nunca mexer nelas.
- **Supabase do Hub:** `https://dpvsivypabmvmrrpgmhc.supabase.co`, schema `hub`. Migrações rodam no SQL Editor, pelo Leo. A função sobe com `supabase functions deploy contas --project-ref dpvsivypabmvmrrpgmhc`.
- **Segredos:** chave de serviço, senha do banco e `HUB_INTEGRACAO_TOKEN` nunca vão para o app, o repositório, o chat ou um executor externo.
- **Testes:**
  - **Hub:** `python -m pytest tests/contas` (Postgres local temporário), `node --test tests/contas/*.mjs tests/app/*.test.js`.
  - **GeoMap:** `npm test` em `backend/`, só contra o Postgres local:
    - `DATABASE_URL="postgresql://geoportal@localhost:5432/geoportal_dev" PGSSL=""`;
    - Postgres do Scoop: `pg_ctl -D C:/Users/lmalerbo/scoop/persist/postgresql/data start`.
- **GeoMap:** `migrate.js` roda todos os `.sql` sempre, então toda migração precisa ser idempotente.
- **Textos:**
  - textos para o usuário em pt-BR;
  - nada de rótulo que suponha gênero ("Individual", "Acesso ativo").
- Commits terminam com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Ninguém ganha nem perde acesso na virada.**
   - A migração converte papel + módulos em níveis pela tabela da spec (Task 1, teste de conversão).
   - Antes da virada, conferir a contagem com o banco real (Task 6).
2. **Individual nunca rebaixa.**
   - No GeoMap, `bool_or` sobre a união de grupo e individual: um "Ver" individual num mapa em que o grupo dá "Ver e editar" continua editando (Task 2).
   - Na tela, o Resultado é o maior dos dois (Task 4).
3. **Nenhuma checagem continua lendo `papel`.**
   - Depois da migração, só `acesso_salvar` pode citar `papel` entre as funções do schema `hub`, e só para gravar (Task 1, teste; Task 6, consulta no banco real).
4. **Publicação fora de ordem não quebra.**
   - O GeoMap sem `mapas` no corpo não mexe nos mapas individuais (Task 2).
   - O app antigo continua funcionando com o banco novo, porque `papel` segue preenchido.

## Mapa de arquivos

**Hub (`hub-geotech-usuarios`):**
- Criar `supabase/migrations/20261023090000_niveis_por_modulo.sql`: colunas, conversão e funções.
- Criar `supabase/migrations/volta/20261023090000_niveis_por_modulo_volta.sql`: recria as funções antigas.
- Modificar `tests/contas/stub_supabase.sql` (módulo `corretivos`) e `tests/contas/conftest.py` (nova migração, `check_function_bodies = off`).
- Criar `tests/contas/test_niveis_sql.py`.
- Modificar `tests/contas/test_login_unico_sql.py`, que usa a assinatura nova.
- Modificar `supabase/functions/contas/regras.js` e `index.ts`.
- Modificar `tests/contas/regras_contas.test.mjs` e `tests/contas/test_funcao_contas.py`.
- Criar `app/usuarios.js` e `tests/app/usuarios_puro.test.js`.
- Modificar `app/index.html` (tela Usuários, `EU.niveis`, `podeEditar`, barra lateral, Configurações → Geral) e `app/drone.js` (solicitante).
- Criar `tests/app/teste_usuarios_tela.py` (Playwright).

**GeoMap (`geomap-acesso-mapa`):**
- Criar `backend/src/db/migrations/020_permissoes_usuario.sql`.
- Modificar `backend/src/lib/permissoes.js`, `backend/src/routes/mapas.js` e `backend/src/routes/integracao.js`.
- Criar `backend/test/permissoes-usuario.test.js`.
- Modificar `backend/test/integracao-contas.test.js`.

---

### Task 1: Banco do Hub — níveis por módulo, mapas do GeoMap e funções sem `papel`

**Files:**
- Create: `supabase/migrations/20261023090000_niveis_por_modulo.sql`, `supabase/migrations/volta/20261023090000_niveis_por_modulo_volta.sql`, `tests/contas/test_niveis_sql.py`
- Modify: `tests/contas/stub_supabase.sql`, `tests/contas/conftest.py`, `tests/contas/test_login_unico_sql.py`

- [ ] **Step 1: Preparar o banco de teste.**
  - Em `stub_supabase.sql`, acrescentar `('corretivos','Mapas de aplicação',6,true)` ao insert de `hub.modulos`.
  - Em `conftest.py`:
    - `MIGRACOES` ganha `'20261023090000_niveis_por_modulo.sql'`;
    - antes do laço das migrações, executar `con.execute('set check_function_bodies = off')`, porque `nova_revisao` e `drone_solicitar` citam tabelas que o stub não tem.

- [ ] **Step 2: Escrever os testes que falham**, em `tests/contas/test_niveis_sql.py`:

```python
"""Nível por módulo (hub.usuario_modulos.nivel) e mapas individuais do GeoMap em hub.acessos."""
import json
from pathlib import Path

SALVAR = 'select hub.acesso_salvar(%s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb)'
MIGRACAO = Path(__file__).resolve().parents[2] / 'supabase' / 'migrations' / '20261023090000_niveis_por_modulo.sql'


def salvar(como, uid, email, nome='Fulano', admin=False, niveis=None, gm_ativo=False, gm_admin=False, gm_grupos=(), gm_mapas=()):
    return como(uid, SALVAR, (email, nome, admin, json.dumps(niveis or {}), gm_ativo, gm_admin, list(gm_grupos), json.dumps(list(gm_mapas))))


def niveis_de(banco, uid):
    return dict(banco.execute('select modulo_id, nivel from hub.usuario_modulos where usuario_id=%s', (uid,)).fetchall())


def test_grava_nivel_por_modulo_e_mantem_papel_para_voltar_atras(banco, pessoa, como):
    adm = pessoa('n-adm1@x.com', admin=True)
    uid = banco.execute("insert into auth.users (email) values ('n1@x.com') returning id").fetchone()[0]
    r = salvar(como, adm, 'n1@x.com', niveis={'plantio': 'editor', 'colheita': 'leitura', 'drone': 'solicitante', 'corretivos': 'editor'})
    assert r and r[0] != 'ERRO', r
    assert niveis_de(banco, uid) == {'plantio': 'editor', 'colheita': 'leitura', 'drone': 'solicitante', 'corretivos': 'editor'}
    assert banco.execute('select papel from hub.usuarios where id=%s', (uid,)).fetchone() == ('editor',)
    a = banco.execute("select niveis, modulos, papel from hub.acessos where email='n1@x.com'").fetchone()
    assert a[0]['drone'] == 'solicitante' and sorted(a[1]) == ['colheita', 'corretivos', 'drone', 'plantio'] and a[2] == 'editor'


def test_papel_resumo_ignora_corretivos(banco, pessoa, como):
    adm = pessoa('n-adm2@x.com', admin=True)
    salvar(como, adm, 'n2@x.com', niveis={'plantio': 'leitura', 'corretivos': 'editor'})
    assert banco.execute("select papel from hub.acessos where email='n2@x.com'").fetchone() == ('leitura',)


def test_recusa_niveis_invalidos(pessoa, como):
    adm = pessoa('n-adm3@x.com', admin=True)
    assert salvar(como, adm, 'n3@x.com', niveis={'plantio': 'solicitante'})[0] == 'ERRO'
    assert salvar(como, adm, 'n3@x.com', niveis={'plantio': 'dono'})[0] == 'ERRO'
    assert salvar(como, adm, 'n3@x.com', niveis={'corretivos': 'leitura'})[0] == 'ERRO'
    assert salvar(como, adm, 'n3@x.com', niveis={'naoexiste': 'leitura'})[0] == 'ERRO'


def test_grava_mapas_do_geomap_e_zera_sem_geomap(banco, pessoa, como):
    adm = pessoa('n-adm4@x.com', admin=True)
    salvar(como, adm, 'n4@x.com', gm_ativo=True, gm_grupos=[2], gm_mapas=[{'mapa_id': 12, 'pode_editar': True}])
    assert banco.execute("select geomap_mapas from hub.acessos where email='n4@x.com'").fetchone()[0] == [{'mapa_id': 12, 'pode_editar': True}]
    salvar(como, adm, 'n4@x.com', gm_ativo=False, gm_mapas=[{'mapa_id': 12, 'pode_editar': True}])
    assert banco.execute("select geomap_mapas from hub.acessos where email='n4@x.com'").fetchone()[0] == []


def test_recusa_mapa_malformado(pessoa, como):
    adm = pessoa('n-adm5@x.com', admin=True)
    assert salvar(como, adm, 'n5@x.com', gm_ativo=True, gm_mapas=[{'mapa_id': 'x', 'pode_editar': True}])[0] == 'ERRO'
    assert salvar(como, adm, 'n5@x.com', gm_ativo=True, gm_mapas=[{'mapa_id': 3}])[0] == 'ERRO'


def test_pode_editar_por_nivel(banco, pessoa, como):
    adm = pessoa('n-adm6@x.com', admin=True)
    uid = banco.execute("insert into auth.users (email) values ('n6@x.com') returning id").fetchone()[0]
    salvar(como, adm, 'n6@x.com', niveis={'plantio': 'editor', 'colheita': 'leitura'})
    assert como(uid, "select hub.pode_editar('plantio')") == [(True,)]
    assert como(uid, "select hub.pode_editar('colheita')") == [(False,)]
    assert como(uid, "select hub.pode_editar('preparo')") == [(False,)]
    assert como(adm, "select hub.pode_editar('preparo')") == [(True,)]


def test_situacao_traz_niveis_e_mapas(banco, pessoa, como):
    adm = pessoa('n-adm7@x.com', admin=True)
    salvar(como, adm, 'n7@x.com', niveis={'drone': 'solicitante'}, gm_ativo=True, gm_mapas=[{'mapa_id': 5, 'pode_editar': False}])
    linha = [l for l in como(adm, 'select email, niveis, geomap_mapas from hub.acessos_situacao()') if l[0] == 'n7@x.com'][0]
    assert linha[1] == {'drone': 'solicitante'} and linha[2] == [{'mapa_id': 5, 'pode_editar': False}]


def test_conversao_do_papel_para_niveis(banco):
    # Reaplica só o bloco de conversão sobre dados no formato antigo. Roda numa transação
    # desfeita no fim: o bloco recalcula todas as linhas e mexeria nos dados dos outros testes.
    uid = '00000000-0000-0000-0000-0000000000c1'
    sql = MIGRACAO.read_text(encoding='utf-8')
    bloco = sql[sql.index('-- >> conversão'):sql.index('-- << conversão')]
    with banco.transaction(force_rollback=True):
        banco.execute("insert into auth.users (id, email) values (%s, 'conv@x.com')", (uid,))
        banco.execute("insert into hub.usuarios (id, nome, papel) values (%s, 'Conv', 'solicitante')", (uid,))
        banco.execute("insert into hub.usuario_modulos (usuario_id, modulo_id) values (%s, 'drone'), (%s, 'plantio'), (%s, 'corretivos')",
                      (uid, uid, uid))
        banco.execute("insert into hub.acessos (email, nome, papel, modulos) values ('conv@x.com', 'Conv', 'solicitante', '{drone,plantio,corretivos}')")
        banco.execute(bloco)
        assert niveis_de(banco, uid) == {'drone': 'solicitante', 'plantio': 'leitura', 'corretivos': 'editor'}
        assert banco.execute("select niveis from hub.acessos where email='conv@x.com'").fetchone()[0] == \
            {'drone': 'solicitante', 'plantio': 'leitura', 'corretivos': 'editor'}


def test_nenhuma_checagem_le_papel(banco):
    nomes = [r[0] for r in banco.execute(
        "select proname from pg_proc where pronamespace = 'hub'::regnamespace and prosrc ~* '\\mpapel\\M'").fetchall()]
    assert set(nomes) <= {'acesso_salvar', 'acesso_remover'}, nomes
```

  - Em `test_login_unico_sql.py`, trocar `SALVAR` e `salvar()` pela assinatura nova:
    - `papel`/`modulos` viram `niveis`;
    - os casos de `modulos=['plantio']` + `papel='editor'` passam a `niveis={'plantio': 'editor'}`;
    - o assert de `hub.usuario_modulos` passa a comparar `[('plantio',)]`, sem mudar.
  - **Os testes de admin continuam iguais.**

- [ ] **Step 3: Rodar e ver falhar.** `python -m pytest tests/contas -q` deve falhar na migração ausente ou na assinatura.

- [ ] **Step 4: Escrever a migração** `supabase/migrations/20261023090000_niveis_por_modulo.sql`:

```sql
-- Nível por módulo e acesso individual por mapa do GeoMap. Ver
-- docs/superpowers/specs/2026-10-22-usuarios-niveis-design.md.
--
--   hub.usuario_modulos.nivel  leitura | solicitante (só Drone) | editor; sem linha = sem acesso.
--                              Substitui hub.usuarios.papel, que fica congelado (só para voltar atrás).
--   hub.acessos.niveis         {"plantio":"editor",...}; papel/modulos seguem gravados, ninguém lê.
--   hub.acessos.geomap_mapas   [{"mapa_id":12,"pode_editar":false}]; a função "contas" empurra ao GeoMap.

begin;

alter table hub.usuario_modulos add column if not exists nivel text not null default 'leitura';
alter table hub.usuario_modulos drop constraint if exists usuario_modulos_nivel_check;
alter table hub.usuario_modulos add constraint usuario_modulos_nivel_check
  check (nivel in ('leitura', 'solicitante', 'editor') and (nivel <> 'solicitante' or modulo_id = 'drone'));

alter table hub.acessos
  add column if not exists niveis       jsonb not null default '{}',
  add column if not exists geomap_mapas jsonb not null default '[]';

-- >> conversão (o teste reaplica este bloco)
update hub.usuario_modulos m
   set nivel = case when m.modulo_id = 'corretivos' or u.papel = 'editor' then 'editor'
                    when u.papel = 'solicitante' and m.modulo_id = 'drone' then 'solicitante'
                    else 'leitura' end
  from hub.usuarios u
 where u.id = m.usuario_id;

update hub.acessos a
   set niveis = coalesce((select jsonb_object_agg(m, case when m = 'corretivos' or a.papel = 'editor' then 'editor'
                                                          when a.papel = 'solicitante' and m = 'drone' then 'solicitante'
                                                          else 'leitura' end)
                            from unnest(a.modulos) m), '{}')
 where a.niveis = '{}';
-- << conversão

create or replace function hub.pode_editar(p_modulo text)
returns boolean language sql stable security definer set search_path = hub as $$
  select exists (
    select 1 from hub.usuarios u
     where u.id = auth.uid()
       and (u.admin
            or exists (select 1 from hub.usuario_modulos m
                        where m.usuario_id = u.id and m.modulo_id = p_modulo and m.nivel = 'editor')));
$$;

drop function if exists hub.acesso_salvar(text, text, text, boolean, text[], boolean, boolean, int[]);
create function hub.acesso_salvar(
  p_email text, p_nome text, p_admin boolean, p_niveis jsonb,
  p_geomap_ativo boolean, p_geomap_admin boolean, p_geomap_grupos int[], p_geomap_mapas jsonb)
returns void language plpgsql security definer set search_path = hub, auth as $$
declare
  v_email     text := lower(trim(p_email));
  v_admin     boolean := coalesce(p_admin, false);
  v_gm        boolean := coalesce(p_geomap_ativo, false);
  v_niveis    jsonb := coalesce(p_niveis, '{}');
  v_mapas     jsonb := coalesce(p_geomap_mapas, '[]');
  v_modulos   text[];
  v_papel     text;
  v_uid       uuid;
  v_era_admin boolean;
begin
  if not hub.eh_admin() then raise exception 'Só administradores alteram acessos'; end if;
  if v_email !~ '^[^@\s]+@[^@\s]+$' then raise exception 'E-mail inválido: %', p_email; end if;
  if length(trim(coalesce(p_nome, ''))) = 0 then raise exception 'Informe o nome'; end if;
  if jsonb_typeof(v_niveis) <> 'object' then raise exception 'Níveis inválidos'; end if;
  if exists (select 1 from jsonb_each(v_niveis) n where n.key not in (select id from hub.modulos)) then
    raise exception 'Módulo inválido';
  end if;
  if exists (select 1 from jsonb_each(v_niveis) n
              where jsonb_typeof(n.value) <> 'string'
                 or n.value #>> '{}' not in ('leitura', 'solicitante', 'editor')
                 or (n.value #>> '{}' = 'solicitante' and n.key <> 'drone')
                 or (n.key = 'corretivos' and n.value #>> '{}' <> 'editor')) then
    raise exception 'Nível inválido';
  end if;
  if jsonb_typeof(v_mapas) <> 'array' or exists (
       select 1 from jsonb_array_elements(v_mapas) m
        where coalesce(m ->> 'mapa_id', '') !~ '^\d+$' or coalesce(jsonb_typeof(m -> 'pode_editar'), '') <> 'boolean') then
    raise exception 'Mapas do GeoMap inválidos';
  end if;
  if not v_gm then v_mapas := '[]'; end if;

  v_modulos := array(select k from jsonb_object_keys(v_niveis) k order by k);
  v_papel := case when exists (select 1 from jsonb_each_text(v_niveis) n where n.value = 'editor' and n.key <> 'corretivos') then 'editor'
                  when v_niveis ->> 'drone' = 'solicitante' then 'solicitante'
                  else 'leitura' end;

  select id into v_uid from auth.users where lower(email) = v_email;
  select admin into v_era_admin from hub.acessos where email = v_email;
  if coalesce(v_era_admin, false) and not v_admin then
    if v_uid = auth.uid() then raise exception 'Você não pode tirar o seu próprio admin'; end if;
    if not exists (select 1 from hub.acessos where admin and email <> v_email) then
      raise exception 'É preciso ter pelo menos um administrador';
    end if;
  end if;

  insert into hub.acessos (email, nome, papel, admin, modulos, niveis, geomap_ativo, geomap_admin, geomap_grupos, geomap_mapas,
                           atualizado_por, atualizado_em)
  values (v_email, trim(p_nome), v_papel, v_admin, v_modulos, v_niveis, v_gm, v_gm and coalesce(p_geomap_admin, false),
          case when v_gm then coalesce(p_geomap_grupos, '{}') else '{}' end, v_mapas, auth.uid(), now())
  on conflict (email) do update
    set nome = excluded.nome, papel = excluded.papel, admin = excluded.admin, modulos = excluded.modulos, niveis = excluded.niveis,
        geomap_ativo = excluded.geomap_ativo, geomap_admin = excluded.geomap_admin, geomap_grupos = excluded.geomap_grupos,
        geomap_mapas = excluded.geomap_mapas, atualizado_por = excluded.atualizado_por, atualizado_em = now();

  if v_uid is not null then
    insert into hub.usuarios (id, nome, papel, admin) values (v_uid, trim(p_nome), v_papel, v_admin)
    on conflict (id) do update set nome = excluded.nome, papel = excluded.papel, admin = excluded.admin;
    delete from hub.usuario_modulos where usuario_id = v_uid;
    insert into hub.usuario_modulos (usuario_id, modulo_id, nivel)
    select v_uid, n.key, n.value from jsonb_each_text(v_niveis) n;
  end if;

  insert into hub.log_auditoria (entidade_tipo, entidade_id, campo, valor_novo, usuario_id, origem)
  values ('sistema', 0, 'acesso', v_email || case when v_admin then ' · admin' else '' end || ' · ' || v_niveis::text
          || case when v_gm then ' · GeoMap' || case when p_geomap_admin then ' admin' else '' end
                  || ' grupos ' || array_to_string(coalesce(p_geomap_grupos, '{}'), ',') || ' mapas ' || v_mapas::text
             else '' end,
          auth.uid(), 'usuario');
end $$;

drop function if exists hub.acessos_situacao();
create function hub.acessos_situacao()
returns table (email text, nome text, admin boolean, niveis jsonb,
               geomap_ativo boolean, geomap_admin boolean, geomap_grupos int[], geomap_mapas jsonb, atualizado_em timestamptz,
               usuario_id uuid, conta_criada boolean, bloqueado boolean, ultimo_login timestamptz,
               precisa_trocar_senha boolean)
language sql stable security definer set search_path = hub, auth as $$
  select a.email, a.nome, a.admin, a.niveis, a.geomap_ativo, a.geomap_admin, a.geomap_grupos, a.geomap_mapas, a.atualizado_em,
         u.id, u.id is not null, coalesce(u.banned_until > now(), false), u.last_sign_in_at,
         coalesce(hu.precisa_trocar_senha, false)
    from hub.acessos a
    left join auth.users u on lower(u.email) = a.email
    left join hub.usuarios hu on hu.id = u.id
   where hub.eh_admin()
   order by a.nome;
$$;

-- nova_revisao: cópia da versão de 20260929110000_documentos_mapa_e_status_guardado.sql
-- (linhas 71–130), com a checagem inline trocada por hub.pode_editar(v_modulo).
-- [colar aqui a função inteira — ver Step 5]

-- drone_solicitar: cópia da versão de 20261008090000_drone_parte2.sql (a partir da linha 205),
-- com a checagem de solicitante lendo usuario_modulos.nivel.
-- [colar aqui a função inteira — ver Step 5]

revoke all on function hub.acesso_salvar(text, text, boolean, jsonb, boolean, boolean, int[], jsonb) from public, anon;
revoke all on function hub.acessos_situacao() from public, anon;
grant execute on function hub.acesso_salvar(text, text, boolean, jsonb, boolean, boolean, int[], jsonb) to authenticated, service_role;
grant execute on function hub.acessos_situacao() to authenticated, service_role;

commit;
```

- [ ] **Step 5: Copiar as duas funções**, mudando só a checagem de permissão.
  - **`nova_revisao`:**
    - copiar `create or replace function hub.nova_revisao(...)` de `20260929110000_documentos_mapa_e_status_guardado.sql`, da linha 71 até o fim da função;
    - trocar o bloco `if coalesce(auth.role(), '') <> 'service_role' and not exists (select 1 from hub.usuarios u ... u.papel = 'editor' ...)) then` por:
      ```sql
      if coalesce(auth.role(), '') <> 'service_role' and not hub.pode_editar(v_modulo) then
      ```
    - a mensagem e o resto ficam iguais.
  - **`drone_solicitar`:**
    - copiar de `20261008090000_drone_parte2.sql`, da linha 205 até o fim da função;
    - trocar `u.papel = 'solicitante'` por `m.nivel = 'solicitante'`:
      ```sql
      if not hub.pode_editar('drone') and not (p_tipo = 'normal' and exists (
           select 1 from hub.usuario_modulos m
            where m.usuario_id = auth.uid() and m.modulo_id = 'drone' and m.nivel = 'solicitante')) then
      ```
  - **Grants:** repetir os `revoke`/`grant` que essas migrações já têm para as duas funções. Mesmas assinaturas, logo `create or replace` mantém os grants, mas repetir não custa.

- [ ] **Step 6: Script de volta** `supabase/migrations/volta/20261023090000_niveis_por_modulo_volta.sql`. Ele é só para emergência e não roda na sequência normal.
  - Recria, nas versões de antes:
    - `hub.pode_editar`, de `20260930090000_acoes_plantio_preparo.sql`;
    - `nova_revisao`, de `20260929110000`;
    - `drone_solicitar`, de `20261008090000`;
    - `acesso_salvar` com 8 parâmetros e `acessos_situacao`, de `20261012090000_login_unico.sql`.
  - Antes de recriar, derruba a nova `acesso_salvar(text, text, boolean, jsonb, boolean, boolean, int[], jsonb)` e a nova `acessos_situacao()`.
  - As colunas novas ficam.
  - **Comentário no topo:** "rodar só para voltar atrás; o app antigo funciona porque papel/modulos continuaram gravados".

- [ ] **Step 7: Rodar e ver passar.**
  - `python -m pytest tests/contas -q` deve passar inteiro.
  - Se `test_nenhuma_checagem_le_papel` acusar outra função, ela também lê `papel`: tratar como `nova_revisao`.

- [ ] **Step 8: Commit.**

```bash
git add supabase/migrations/20261023090000_niveis_por_modulo.sql supabase/migrations/volta tests/contas
git commit -m "Usuarios: nivel por modulo (usuario_modulos.nivel) e mapas individuais do GeoMap em hub.acessos

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: GeoMap — acesso individual por mapa

**Files:**
- Create: `backend/src/db/migrations/020_permissoes_usuario.sql`, `backend/test/permissoes-usuario.test.js`
- Modify: `backend/src/lib/permissoes.js`, `backend/src/routes/mapas.js`, `backend/src/routes/integracao.js`, `backend/test/integracao-contas.test.js`

- [ ] **Step 1: Criar a worktree.**

```bash
git -C C:/Users/lmalerbo/Documents/GitHub/geomap fetch origin
git -C C:/Users/lmalerbo/Documents/GitHub/geomap worktree add C:/Users/lmalerbo/Documents/GitHub/geomap-acesso-mapa -b feat/acesso-por-mapa origin/master
cd C:/Users/lmalerbo/Documents/GitHub/geomap-acesso-mapa/backend && npm ci
```

- [ ] **Step 2: Escrever os testes que falham**, em `backend/test/permissoes-usuario.test.js`:
  - montar o cenário com `criarCenario()` de `helpers.js`, que já tem `leitor`, `editor`, `grupoLeitor`, `grupoEditor` e `mapa`;
  - acrescentar um segundo mapa, sem grupo, criado no teste e apagado no `after`.
  - **Casos:**
    1. **Individual dá acesso a um mapa que nenhum grupo dá:**
       - `INSERT INTO permissoes_usuario (usuario_id, mapa_id, pode_editar) VALUES (leitor, mapa2, false)`;
       - `GET /mapas` do leitor inclui `mapa2` com `podeEditar: false`;
       - o download de uma camada do `mapa2` devolve 200.
    2. **Individual libera edição:** com `pode_editar = true` no `mapa2`, `usuarioPodeEditarMapa(leitor, mapa2)` é `true`.
    3. **Individual não rebaixa:**
       - o `editor` edita `mapa` pelo grupo, e se insere para ele `(editor, mapa, false)`;
       - `GET /mapas` continua com `podeEditar: true` e sem duplicar o mapa.
    4. **Sem individual, nada muda:** o `leitor` continua sem o `mapa2` depois de apagar a linha.
  - Em `backend/test/integracao-contas.test.js`, acrescentar:
    - `PUT /integracao/contas/usuario` com `mapas: [{mapaId: mapa2, podeEditar: true}]` grava; um segundo PUT **sem** `mapas` mantém; um PUT com `ativo: false` apaga;
    - `GET /integracao/contas/usuarios` devolve `mapas: [{mapaId, podeEditar}]`;
    - `GET /integracao/contas/mapas` devolve `[{id, nome, grupos: [{grupoId, podeEditar}]}]` com o `grupoEditor` no `mapa`;
    - sem `x-hub-token`, as rotas dão 401, como as outras.

- [ ] **Step 3: Rodar e ver falhar.** `npm test` deve falhar porque a tabela não existe.

- [ ] **Step 4: Migração** `backend/src/db/migrations/020_permissoes_usuario.sql`:

```sql
-- Acesso individual por mapa, gerenciado pelo Hub (tela Usuários). Soma ao dos
-- grupos e só acrescenta: quem consulta faz bool_or sobre permissoes_efetivas.
-- Idempotente (migrate.js roda todos os .sql sempre).
CREATE TABLE IF NOT EXISTS permissoes_usuario (
    usuario_id INTEGER NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    mapa_id INTEGER NOT NULL REFERENCES mapas (id) ON DELETE CASCADE,
    pode_editar BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (usuario_id, mapa_id)
);

CREATE OR REPLACE VIEW permissoes_efetivas AS
    SELECT ug.usuario_id, p.mapa_id, p.pode_editar
      FROM permissoes p
      JOIN usuarios_grupos ug ON ug.grupo_id = p.grupo_id
    UNION ALL
    SELECT usuario_id, mapa_id, pode_editar
      FROM permissoes_usuario;
```

- [ ] **Step 5: Trocar as junções pela view.**
  - **`lib/permissoes.js`:**
    - `usuarioTemPermissaoMapa` passa a `SELECT 1 FROM permissoes_efetivas WHERE usuario_id = $1 AND mapa_id = $2 LIMIT 1`;
    - `usuarioPodeEditarMapa` faz o mesmo, com `AND pode_editar`;
    - o comentário de cada uma passa a dizer "via grupo ou individual".
  - **`routes/mapas.js`:**
    - **`GET /mapas`:** `FROM mapas m JOIN permissoes_efetivas pe ON pe.mapa_id = m.id WHERE pe.usuario_id = $1 GROUP BY m.id`, com `bool_or(pe.pode_editar) AS pode_editar`;
    - **download:** `JOIN permissoes_efetivas pe ON pe.mapa_id = m.id WHERE pe.usuario_id = $1 AND c.id = $2`;
    - o comentário do catálogo passa a dizer "que o usuário pode ver (por grupo ou individual)".
  - **Conferência:** `git grep -n "JOIN usuarios_grupos" backend/src` só pode sobrar em `integracao.js` (lista de grupos do usuário) e `admin.js`.

- [ ] **Step 6: Integração**, em `routes/integracao.js`:

```js
integracaoRouter.get("/integracao/contas/mapas", async (req, res) => {
  const { rows } = await pool.query(
    `SELECT m.id, m.nome,
            coalesce(json_agg(json_build_object('grupoId', p.grupo_id, 'podeEditar', p.pode_editar)
                              ORDER BY p.grupo_id) FILTER (WHERE p.grupo_id IS NOT NULL), '[]') AS grupos
       FROM mapas m LEFT JOIN permissoes p ON p.mapa_id = m.id
      GROUP BY m.id ORDER BY m.nome`
  );
  res.json(rows);
});
```

  - **`GET /integracao/contas/usuarios`:** acrescentar a coluna `mapas` com um subselect:
    ```sql
    (SELECT coalesce(json_agg(json_build_object('mapaId', pu.mapa_id, 'podeEditar', pu.pode_editar) ORDER BY pu.mapa_id), '[]')
       FROM permissoes_usuario pu WHERE pu.usuario_id = u.id) AS mapas
    ```
    Como fica dentro do `GROUP BY u.id`, funciona.
  - **`PUT /integracao/contas/usuario`**, depois de gravar os grupos:

```js
  // "mapas" é opcional: um Hub antigo não manda e os mapas individuais ficam como estão.
  if (!ativo || Array.isArray(req.body?.mapas)) {
    const pedidosMapa = ativo ? req.body.mapas
      .map((m) => ({ mapaId: Number(m?.mapaId), podeEditar: m?.podeEditar === true }))
      .filter((m) => Number.isInteger(m.mapaId)) : [];
    await pool.query("DELETE FROM permissoes_usuario WHERE usuario_id = $1", [id]);
    if (pedidosMapa.length) {
      await pool.query(
        `INSERT INTO permissoes_usuario (usuario_id, mapa_id, pode_editar)
         SELECT $1, x.mapa_id, x.pode_editar
           FROM unnest($2::int[], $3::bool[]) AS x(mapa_id, pode_editar)
           JOIN mapas m ON m.id = x.mapa_id
         ON CONFLICT (usuario_id, mapa_id) DO UPDATE SET pode_editar = excluded.pode_editar`,
        [id, pedidosMapa.map((m) => m.mapaId), pedidosMapa.map((m) => m.podeEditar)]);
    }
  }
```

  - O `JOIN mapas` descarta em silêncio um mapa que foi apagado no GeoMap, como já acontece com os grupos.
  - Atualizar o comentário do topo da seção: "o GeoMap só guarda quem está ativo, se é admin, em quais grupos está e os mapas individuais".

- [ ] **Step 7: Rodar e ver passar.** `npm test` deve passar inteiro.

- [ ] **Step 8: Commit** na branch `feat/acesso-por-mapa`:

```bash
git add backend/src/db/migrations/020_permissoes_usuario.sql backend/src/lib/permissoes.js backend/src/routes/mapas.js backend/src/routes/integracao.js backend/test
git commit -m "Acesso individual por mapa (permissoes_usuario) somado aos grupos; rotas do Hub para mapas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Função `contas` — níveis e mapas

**Files:**
- Modify: `supabase/functions/contas/regras.js`, `supabase/functions/contas/index.ts`, `tests/contas/regras_contas.test.mjs`, `tests/contas/test_funcao_contas.py`

- [ ] **Step 1: Teste que falha**, em `regras_contas.test.mjs`:
  - **Trocar `modulos` por `niveis`** nos testes que já existem:
    - `{ niveis: { plantio: "leitura" } }` tem acesso;
    - `{ niveis: {} , geomap_ativo: true }` tem acesso;
    - admin sem nada tem acesso;
    - `{}` não tem acesso.
  - **Acrescentar:**

```js
test("Mapas de aplicação sozinho dá acesso (conta não fica bloqueada)", () => {
  assert.equal(temAcesso({ niveis: { corretivos: "editor" } }), true);
});

test("mapasParaGeomap converte o formato do Hub para o do GeoMap", () => {
  assert.deepEqual(mapasParaGeomap([{ mapa_id: 12, pode_editar: true }, { mapa_id: 3, pode_editar: false }]),
    [{ mapaId: 12, podeEditar: true }, { mapaId: 3, podeEditar: false }]);
  assert.deepEqual(mapasParaGeomap(null), []);
});
```

- [ ] **Step 2: `regras.js`:**

```js
/** A conta fica liberada? (algum nível em módulo do Hub, GeoMap ativo ou admin). Sem acesso = conta bloqueada. */
export function temAcesso(a) {
  return Object.keys(a?.niveis || {}).length > 0 || !!a?.geomap_ativo || !!a?.admin;
}

/** hub.acessos.geomap_mapas ([{mapa_id, pode_editar}]) → corpo do GeoMap ([{mapaId, podeEditar}]). */
export function mapasParaGeomap(mapas) {
  return (mapas || []).map((m) => ({ mapaId: Number(m.mapa_id), podeEditar: m.pode_editar === true }));
}
```

- [ ] **Step 3: `index.ts`:**
  - **Tipo `Acesso`:** troca `papel` e `modulos` por `niveis: Record<string, string>` e acrescenta `geomap_mapas: { mapa_id: number; pode_editar: boolean }[]`.
  - **`salvar`:**
    - **rpc:** chama `p_email, p_nome, p_admin, p_niveis: a.niveis || {}, p_geomap_ativo, p_geomap_admin, p_geomap_grupos, p_geomap_mapas: a.geomap_mapas || []`;
    - **bloqueio:** `temAcesso({ niveis: a.niveis, geomap_ativo: a.geomap_ativo, admin: a.admin })`;
    - **PUT ao GeoMap:** ganha `mapas: a.geomap_ativo ? mapasParaGeomap(a.geomap_mapas) : []`.
  - **`redefinir`:** o select de `acessos` passa a `"niveis,geomap_ativo,admin"`.
  - **`remover`:** o PUT ganha `mapas: []`.
  - **Ação nova:** no `switch`, `case "mapas_geomap": return resp(await geomap("/integracao/contas/mapas"));`, ao lado de `grupos_geomap`, com a mesma checagem de admin.
  - **Import:** `import { temAcesso, mapasParaGeomap } from "./regras.js";`.

- [ ] **Step 4: Teste de ponta a ponta (`test_funcao_contas.py`, marcado `banco`):**
  - o `salvar` passa a mandar `niveis={'plantio': 'leitura'}` e `geomap_mapas=[]`, em vez de `papel`/`modulos`;
  - acrescentar `status, mapas = contas(admin_token, acao='mapas_geomap')`, com `assert status == 200 and isinstance(mapas, list)`. É só leitura no GeoMap.

- [ ] **Step 5: Rodar.**
  - `node --test tests/contas/*.mjs` deve passar.
  - O `test_funcao_contas.py` só roda na publicação (Task 6), porque precisa da função publicada.

- [ ] **Step 6: Commit.**

```bash
git add supabase/functions/contas tests/contas
git commit -m "Funcao contas: niveis por modulo, mapas individuais do GeoMap e acao mapas_geomap

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `app/usuarios.js` — regras da tela, sem DOM

**Files:**
- Create: `app/usuarios.js`, `tests/app/usuarios_puro.test.js`

- [ ] **Step 1: Teste que falha** (`tests/app/usuarios_puro.test.js`, mesmo estilo de `drone_puro.test.js`: carrega o arquivo num `vm`):

```js
// Regras puras da tela Usuários. Roda com: node --test tests/app/usuarios_puro.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');

const ctx = { console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(__dirname + '/../../app/usuarios.js', 'utf8'), ctx);

const mapa = { id: 7, nome: 'Voos', grupos: [{ grupoId: 1, podeEditar: false }, { grupoId: 2, podeEditar: true }] };

test('o que os grupos marcados dão num mapa', () => {
  assert.strictEqual(ctx.usrPelosGrupos(mapa, []), 'nada');
  assert.strictEqual(ctx.usrPelosGrupos(mapa, [1]), 'ver');
  assert.strictEqual(ctx.usrPelosGrupos(mapa, [1, 2]), 'editar');
});

test('individual só acrescenta: vale o maior', () => {
  assert.strictEqual(ctx.usrNivelFinal('editar', 'ver'), 'editar');
  assert.strictEqual(ctx.usrNivelFinal('ver', 'editar'), 'editar');
  assert.strictEqual(ctx.usrNivelFinal('nada', 'ver'), 'ver');
  assert.strictEqual(ctx.usrNivelFinal('ver', 'nada'), 'ver');
});

test('ciclo da coluna Individual: — → Ver → Ver e editar → —', () => {
  assert.strictEqual(ctx.usrProximoIndividual('nada'), 'ver');
  assert.strictEqual(ctx.usrProximoIndividual('ver'), 'editar');
  assert.strictEqual(ctx.usrProximoIndividual('editar'), 'nada');
});

test('mapas individuais: ida e volta entre a tela e hub.acessos', () => {
  const tela = ctx.usrMapasDoBanco([{ mapa_id: 7, pode_editar: true }, { mapa_id: 9, pode_editar: false }]);
  assert.deepStrictEqual({ ...tela }, { 7: 'editar', 9: 'ver' });
  assert.deepStrictEqual(ctx.usrMapasParaBanco({ 7: 'editar', 9: 'ver', 4: 'nada' }),
    [{ mapa_id: 7, pode_editar: true }, { mapa_id: 9, pode_editar: false }]);
});

test('resumo da linha da lista', () => {
  const a = { niveis: { plantio: 'editor', preparo: 'leitura', drone: 'solicitante', corretivos: 'editor' },
              geomap_ativo: true, geomap_grupos: [1, 2], geomap_mapas: [{ mapa_id: 7, pode_editar: false }] };
  assert.strictEqual(ctx.usrResumo(a), 'Plantio (editor) · Preparo · Drone (solicitante) · GeoMap: 2 grupos + 1 mapa · Mapas de aplicação');
  assert.strictEqual(ctx.usrResumo({ admin: true, niveis: {} }), 'Admin do Hub');
  assert.strictEqual(ctx.usrResumo({ niveis: {}, geomap_ativo: true, geomap_admin: true, geomap_grupos: [] }), 'GeoMap (admin)');
  assert.strictEqual(ctx.usrResumo({ niveis: { plantio: 'editor' }, bloqueado: true }), 'Sem acesso — bloqueado');
  assert.strictEqual(ctx.usrResumo({ niveis: {} }), 'Sem acesso');
});

test('situação, sem supor gênero', () => {
  assert.deepStrictEqual([...ctx.usrSituacao({ conta_criada: false })], ['espera', 'Sem conta']);
  assert.deepStrictEqual([...ctx.usrSituacao({ conta_criada: true, bloqueado: true })], ['erro', 'Bloqueado']);
  assert.deepStrictEqual([...ctx.usrSituacao({ conta_criada: true, precisa_trocar_senha: true })], ['espera', 'Senha provisória']);
  assert.deepStrictEqual([...ctx.usrSituacao({ conta_criada: true })], ['espera', 'Ainda não entrou']);
  assert.deepStrictEqual([...ctx.usrSituacao({ conta_criada: true, ultimo_login: '2026-10-20T10:00:00Z' })], ['ok', 'Acesso ativo']);
});

test('filtro e busca', () => {
  const lista = [
    { nome: 'Ana Souza', email: 'ana@x.com', niveis: { plantio: 'editor' } },
    { nome: 'Bruno Lima', email: 'bruno@x.com', niveis: {}, geomap_ativo: true },
    { nome: 'Carla', email: 'carla@x.com', niveis: { drone: 'leitura' }, precisa_trocar_senha: true },
  ];
  const nomes = (l) => l.map((a) => a.nome);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'todos', '')), ['Ana Souza', 'Bruno Lima', 'Carla']);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'plantio', '')), ['Ana Souza']);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'geomap', '')), ['Bruno Lima']);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'provisoria', '')), ['Carla']);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'todos', 'BRUNO')), ['Bruno Lima']);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'todos', 'carla@')), ['Carla']);
});
```

- [ ] **Step 2: Implementar `app/usuarios.js`:**

```js
// Regras da tela Usuários, sem DOM (testadas em tests/app/usuarios_puro.test.js).
// Nível por módulo: leitura | solicitante (só Drone) | editor; sem chave = sem acesso.
// GeoMap: o acesso individual por mapa soma ao dos grupos e só acrescenta.
const USR_MODULOS_HUB = [['plantio', 'Plantio'], ['preparo', 'Preparo'], ['colheita', 'Colheita'], ['drone', 'Drone']];
const USR_NIVEIS = { leitura: 'Leitura', solicitante: 'Solicitante', editor: 'Editor' };
const USR_FILTROS = [['todos', 'Todos'], ['plantio', 'Plantio'], ['preparo', 'Preparo'], ['colheita', 'Colheita'],
  ['drone', 'Drone'], ['geomap', 'GeoMap'], ['provisoria', 'Senha provisória']];
const USR_MAPA_ORDEM = { nada: 0, ver: 1, editar: 2 };
const USR_MAPA_ROTULO = { nada: '—', ver: 'Ver', editar: 'Ver e editar' };

function usrPelosGrupos(mapa, grupoIds) {
  let n = 'nada';
  for (const g of mapa.grupos || []) {
    if (!grupoIds.includes(g.grupoId)) continue;
    const v = g.podeEditar ? 'editar' : 'ver';
    if (USR_MAPA_ORDEM[v] > USR_MAPA_ORDEM[n]) n = v;
  }
  return n;
}
function usrNivelFinal(pelosGrupos, individual) {
  return USR_MAPA_ORDEM[individual] > USR_MAPA_ORDEM[pelosGrupos] ? individual : pelosGrupos;
}
function usrProximoIndividual(n) { return { nada: 'ver', ver: 'editar', editar: 'nada' }[n] || 'ver'; }
function usrMapasDoBanco(mapas) {
  const r = {};
  for (const m of mapas || []) r[m.mapa_id] = m.pode_editar ? 'editar' : 'ver';
  return r;
}
function usrMapasParaBanco(tela) {
  return Object.entries(tela || {}).filter(([, n]) => n !== 'nada')
    .map(([id, n]) => ({ mapa_id: Number(id), pode_editar: n === 'editar' }));
}
function usrPlural(n, um, varios) { return n + ' ' + (n === 1 ? um : varios); }
function usrResumo(a) {
  if (a.bloqueado) return 'Sem acesso — bloqueado';
  const niveis = a.niveis || {}, partes = [];
  if (a.admin) partes.push('Admin do Hub');
  for (const [id, nome] of USR_MODULOS_HUB) {
    const n = niveis[id];
    if (n) partes.push(n === 'leitura' ? nome : `${nome} (${USR_NIVEIS[n].toLowerCase()})`);
  }
  if (a.geomap_ativo) {
    const g = (a.geomap_grupos || []).length, m = (a.geomap_mapas || []).length;
    const det = [g ? usrPlural(g, 'grupo', 'grupos') : '', m ? usrPlural(m, 'mapa', 'mapas') : ''].filter(Boolean).join(' + ');
    partes.push('GeoMap' + (a.geomap_admin ? ' (admin)' : '') + (det ? ': ' + det : ''));
  }
  if (niveis.corretivos) partes.push('Mapas de aplicação');
  return partes.join(' · ') || 'Sem acesso';
}
function usrSituacao(a) {
  if (!a.conta_criada) return ['espera', 'Sem conta'];
  if (a.bloqueado) return ['erro', 'Bloqueado'];
  if (a.precisa_trocar_senha) return ['espera', 'Senha provisória'];
  if (!a.ultimo_login) return ['espera', 'Ainda não entrou'];
  return ['ok', 'Acesso ativo'];
}
function usrFiltrar(lista, filtro, busca) {
  const q = String(busca || '').trim().toLowerCase();
  return lista.filter((a) => {
    if (q && !(String(a.nome || '').toLowerCase().includes(q) || String(a.email || '').toLowerCase().includes(q))) return false;
    if (filtro === 'geomap') return !!a.geomap_ativo;
    if (filtro === 'provisoria') return !!a.precisa_trocar_senha;
    if (filtro && filtro !== 'todos') return !!(a.niveis || {})[filtro];
    return true;
  });
}
```

- [ ] **Step 3: Rodar.** `node --test tests/app/usuarios_puro.test.js` deve passar.

- [ ] **Step 4: Commit.**

```bash
git add app/usuarios.js tests/app/usuarios_puro.test.js
git commit -m "Usuarios: regras da tela (resumo, filtro, situacao, nivel final por mapa) sem DOM

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: App do Hub — níveis de quem entrou e tela Usuários nova

**Files:**
- Modify: `app/index.html`, `app/drone.js`
- Create: `tests/app/teste_usuarios_tela.py`

**Referência visual:** a maquete (abra o link). As cores e componentes são os do Hub (`cfg-card`, `seg`, `btn-acao`, `btn-retro`, `usr-*`); a maquete é a referência de estrutura, não de CSS.

- [ ] **Step 1: Níveis de quem entrou** (`app/index.html`):
  - **`carregarDados`:**
    - o select de `usuarios` passa a `'id,nome,admin,precisa_trocar_senha,usuario_modulos(modulo_id,nivel)'`;
    - ao montar `USUARIOS`, troca `role:u.papel` por `niveis:Object.fromEntries((u.usuario_modulos||[]).map(m=>[m.modulo_id,m.nivel]))`;
    - `perms` passa a vir de `niveis`, com `plantio:!!niveis.plantio` etc. e `drone:!!niveis.drone||u.admin`.
  - **`podeEditar`:**
    ```js
    // Mesma regra do banco (hub.pode_editar): admin ou nível editor no módulo.
    function podeEditar(mod){return !!EU&&(EU.admin||EU.niveis[mod]==='editor');}
    ```
  - **Barra lateral:** `sb-urole` mostra `EU.admin?'Admin':''`.
  - **Configurações → Geral**, linha ~1919: o `role-chip` do papel vira um chip por módulo com nível, `${MOD_ROTULO[id]} · ${USR_NIVEIS[n]}`, mais o de Admin.
  - **Limpeza:** apagar `ROLE_LABELS` quando não sobrar uso. Conferir com `grep -n "ROLE_LABELS\|EU.role\|\.papel" app/`.
  - **Script:** incluir `<script src="usuarios.js"></script>` antes de `drone.js`.
- [ ] **Step 2: `app/drone.js`, linha ~95:** `(EU&&EU.role==='solicitante'&&EU.perms.drone)` vira `(EU&&EU.niveis.drone==='solicitante')`.
- [ ] **Step 3: Tela Usuários**, substituindo `rUsrList`/`formUsr`/`salvarUsr` e o HTML da página `usuarios`:
  - **Estado:**
    ```js
    let USR={filtro:'todos',busca:'',aba:'conta',rasc:null};
    ```
    O rascunho `rasc` é uma cópia do acesso selecionado, com `{email,nome,admin,niveis,geomap_ativo,geomap_admin,geomap_grupos,mapas:{id:'ver'|'editar'}}`. Ele guarda as mudanças entre abas até o Salvar.
  - **Lista (coluna esquerda):**
    - cabeçalho "Quem acessa o quê", botão "Novo acesso" e campo Buscar (`oninput` → `USR.busca`);
    - chips de filtro de `USR_FILTROS`;
    - cada pessoa: `usr-card` com iniciais, nome, ponto (`usrSituacao`) e `usrResumo(a)` numa linha cortada com reticências;
    - a lista vem de `usrFiltrar(ACESSOS,USR.filtro,USR.busca)`;
    - mantém `data-email` + `this.dataset.email`, como cobre `tests/app/usuarios_onclick.test.js`.
  - **Cabeçalho do painel:** iniciais, nome, `email · último acesso …` e o selo de situação.
  - **Abas** (`role="tablist"`, botões com `aria-selected`): Conta, Módulos do Hub e Ferramentas. Trocar de aba re-renderiza só o corpo, a partir de `rasc`.
  - **Aba Conta:**
    - Nome; E-mail ("usado para entrar"; `readonly` se não for novo);
    - linha "Senha": "Gera uma senha provisória; a pessoa troca no próximo acesso.", com "Redefinir senha" (sem mudança);
    - linha "Remover acesso": "Bloqueia a conta no Hub e em todas as ferramentas na hora. O histórico continua.", com "Remover", escondida para a própria pessoa e para acesso novo.
  - **Aba Módulos do Hub:**
    - nota: "Nível em cada módulo. Leitura consulta; Solicitante pede projetos (Drone); Editor faz ações e envia arquivos.";
    - uma linha por `USR_MODULOS_HUB`, com nome e `div.seg` (Sem acesso / Leitura / [Solicitante só no Drone] / Editor). Clicar atualiza `rasc.niveis` e apaga a chave em "Sem acesso";
    - abaixo, um cartão "Administrador do Hub — Gerencia usuários e configurações. Só um admin concede admin.", com uma chave (checkbox estilizado) em `rasc.admin`.
  - **Aba Ferramentas:**
    - **Cartão GeoMap** ("Mapas, polígonos e ortomosaicos"):
      - **chave de acesso:** `rasc.geomap_ativo`. Desligada, esconde o resto e não apaga o rascunho; o banco zera ao salvar;
      - **checkbox de admin:** "Administrador do GeoMap (gerencia mapas e camadas)";
      - **Grupos:** chips de `gruposGeomap()` que ligam e desligam em `rasc.geomap_grupos`;
      - **Mapas:** nota "O grupo dá a base; aqui você pode dar acesso a mais um mapa ou liberar edição (anotar pins) só para esta pessoa.";
      - **tabela de mapas:**
        - colunas Mapa · Pelos grupos · Individual · Resultado, com linhas de `mapasGeomap()` (novo, igual a `gruposGeomap`, com cache, chamando `chamarContas({acao:'mapas_geomap'})`);
        - "Pelos grupos": `USR_MAPA_ROTULO[usrPelosGrupos(m,rasc.geomap_grupos)]`, ou "—";
        - "Individual": botão que mostra "+ dar acesso" quando `nada` e, se não, o rótulo; o clique usa `usrProximoIndividual`;
        - "Resultado": `usrNivelFinal`, com "Sem acesso" quando `nada`, em cor por nível;
        - em telas estreitas, a tabela rola dentro de uma caixa;
        - se os mapas não carregarem, mostrar "Não foi possível ler os mapas do GeoMap." sem travar o resto.
    - **Cartão Mapas de aplicação** ("Corretivos e Aplicação aérea — gera o PDF do mapa"): a chave liga `rasc.niveis.corretivos='editor'` e desliga apagando a chave.
    - **Aviso:** "Kronos e Portal de downloads entram aqui quando passarem a usar o login do Hub."
  - **Rodapé fixo do painel:** "Vale na hora, para o Hub e as ferramentas.", com `#u-erro` e o botão Salvar ("Adicionar" quando é novo).
  - **`salvarUsr`:**
    - valida e-mail e nome como hoje; com erro, troca para a aba Conta;
    - chama:
      ```js
      chamarContas({acao:'salvar',email,nome,admin:rasc.admin,niveis:rasc.niveis,geomap_ativo,geomap_admin,geomap_grupos,geomap_mapas:usrMapasParaBanco(rasc.mapas)})
      ```
    - mantém o aviso `avisoGeomap` e a senha provisória.
  - **Novo acesso:** abre com `rasc={niveis:{},geomap_grupos:[],mapas:{}}` na aba Conta.
  - **Trocar de pessoa com o rascunho alterado:** perguntar com `confirmar('Há mudanças não salvas. Descartar?')`.
- [ ] **Step 4: Teste de tela** (`tests/app/teste_usuarios_tela.py`, mesmo padrão de `teste_drone_tela.py`):
  - abre `app/index.html` com o Supabase simulado da mesma forma que o teste do Drone;
  - `acessos_situacao` devolve três pessoas fictícias;
  - `contas` `grupos_geomap`/`mapas_geomap` devolvem dados fixos.
  - **Confere:**
    1. **Filtros:** o filtro Drone deixa só quem tem Drone, e a busca por e-mail acha a pessoa.
    2. **Níveis:** selecionar a pessoa → aba Módulos → Editor no Plantio e Solicitante no Drone; o Plantio não oferece Solicitante.
    3. **Mapas:** aba Ferramentas → marcar um grupo muda "Pelos grupos"; clicar em "Individual" num mapa sem grupo leva o Resultado a "Ver"; num mapa em que o grupo dá "Ver e editar", um "Ver" individual mantém o Resultado "Ver e editar".
    4. **Salvar:** a chamada interceptada a `contas` recebe `niveis`, `geomap_mapas` e `admin` certos, sem `papel` nem `modulos`.
    5. **Largura de celular (390 px):** sem rolagem horizontal da página.
- [ ] **Step 5: Rodar.**
  - `node --test tests/app/*.test.js` e `python -m pytest tests/app/teste_usuarios_tela.py tests/app/teste_drone_tela.py -q` devem passar.
  - O Drone continua passando com o solicitante novo.
- [ ] **Step 6: Commit.**

```bash
git add app/index.html app/drone.js tests/app/teste_usuarios_tela.py
git commit -m "Tela Usuarios reorganizada: lista com resumo e filtros, abas Conta / Modulos do Hub / Ferramentas, nivel por modulo e mapas do GeoMap

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Publicação e conferência

- [ ] **Step 1: Revisão.**
  - Rodar `/code-review` nas duas branches, com foco na seção Review Focus.
  - Corrigir antes de seguir.
- [ ] **Step 2: Conferência antes da virada**, só leitura, no SQL Editor do Hub, pelo Leo:

```sql
select u.papel, m.modulo_id, count(*) from hub.usuario_modulos m join hub.usuarios u on u.id = m.usuario_id group by 1, 2 order by 1, 2;
```

  - Guardar o resultado.
  - Depois da migração, repetir agrupando por `m.nivel` e conferir com a tabela da spec. Os totais por módulo têm de bater.
- [ ] **Step 3: GeoMap.**
  - Merge de `feat/acesso-por-mapa` em `master` e push. O Render publica sozinho.
  - Conferir `GET /integracao/contas/mapas` pela função, depois do passo 5.
  - Enquanto o Hub não muda, nada muda para ninguém, porque ainda não existe mapa individual.
- [ ] **Step 4: Migração do Hub.**
  - O Leo roda `supabase/migrations/20261023090000_niveis_por_modulo.sql` no SQL Editor.
  - **Conferir:**
    - o agrupamento do Step 2, agora por `nivel`;
    - `select proname from pg_proc where pronamespace='hub'::regnamespace and prosrc ~* '\mpapel\M';` deve listar só `acesso_salvar` e `acesso_remover`.
- [ ] **Step 5: Função e app.**
  - Publicar a função:
    ```bash
    supabase functions deploy contas --project-ref dpvsivypabmvmrrpgmhc
    ```
  - Fazer o merge de `usuarios-niveis` em `main` e o push. O GitHub Pages publica.
  - Rodar `python -m pytest -m banco tests/contas/test_funcao_contas.py`, com `HUB_CONTA_TESTE`.
- [ ] **Step 6: Conferência na tela**, com o Leo:
  - abrir Usuários e conferir três pessoas reais com o resumo esperado;
  - dar a uma conta `@hub.local` um mapa individual "Ver" fora dos grupos, entrar com ela no GeoMap e ver o mapa;
  - tirar o mapa individual e conferir que ele some;
  - um editor de um módulo continua editando, e um solicitante do Drone continua abrindo pedido.
- [ ] **Step 7: Encerrar.**
  - Atualizar a memória `project_passagem_2026_10_22`: o item 1 fica feito, e o próximo passo é a limpeza de `papel`/`modulos` depois de algumas semanas.
  - Remover as worktrees.

**Voltar atrás:**
- **Hub:**
  - reverter o merge da `usuarios-niveis`;
  - republicar a função `contas` da versão anterior;
  - rodar `supabase/migrations/volta/20261023090000_niveis_por_modulo_volta.sql`.
- **GeoMap:** reverter o merge. A tabela `permissoes_usuario` e a view ficam sem uso.
