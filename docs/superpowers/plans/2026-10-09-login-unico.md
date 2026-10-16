# Login único (Hub dono das contas + GeoMap) — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O Hub passa a criar contas, gerar senhas provisórias, bloquear e dar acesso ao GeoMap (grupos/admin) pela tela Usuários; o GeoMap passa a aceitar só o login do Hub.

**Architecture:** O banco do Hub guarda quem acessa o quê (`hub.acessos`, agora com os campos do GeoMap). Uma Supabase Edge Function (`contas`) é a única peça com a chave de serviço: cria/redefine/bloqueia contas e empurra o acesso ao GeoMap por rotas `/integracao/contas/*` (chave `x-hub-token`, já existente). O GeoMap troca o token do Supabase do Hub pelo JWT dele (`POST /auth/hub`) e o resto do GeoMap não muda.

**Tech Stack:** Supabase (Postgres, Auth, Edge Functions/Deno), HTML+JS do Hub (`app/index.html`), Node/Express + Postgres (backend GeoMap), React/Vite + `@supabase/supabase-js` (frontend GeoMap), Python (migração), pytest + Postgres local, `node --test`, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-09-login-unico-design.md`

## Global Constraints

- Dois repositórios: `lmalerbo/hub-geotech` (worktree `C:\Users\lmalerbo\Documents\hub-geotech-colheita`, branch local `colheita`; publicar com `git push origin colheita:main`) e `lmalerbo/geomap` (branch padrão `master`; **outras sessões trabalham em worktrees do GeoMap** — criar worktree própria `C:\Users\lmalerbo\Documents\GitHub\geomap-login-hub` na branch `feat/login-hub` a partir de `origin/master`; nunca mexer nas pastas `geomap`, `geomap-indicadores`, `geomap-ponte`).
- Supabase do Hub: `https://dpvsivypabmvmrrpgmhc.supabase.co`, schema `hub`, chave pública `sb_publishable_3xv0R1kmhSXkoUh3i4vN0A_Q5oLBbVL`.
- A chave de serviço do Supabase e a senha do banco **nunca** vão para o app, o repositório, o Worker de arquivos ou o chat. `HUB_INTEGRACAO_TOKEN` nunca é impresso.
- Nunca imprimir hash de senha nem senha provisória em log de script (a senha provisória só aparece na tela do admin, uma vez).
- Senha provisória: 10 caracteres do alfabeto `abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789`. Senha nova escolhida pela pessoa: mínimo 8 caracteres.
- Bloqueio de conta = `ban_duration: "876000h"`; desbloqueio = `"none"`.
- Contas `@hub.local` são de teste.
- Testes que gravam no banco real salvam e restauram o original; nunca apagam dado real. Testar antes de publicar.
- Textos para o usuário em pt-BR.
- Commits terminam com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- GeoMap: testes do backend só contra Postgres local (`DATABASE_URL="postgresql://geoportal@localhost:5432/geoportal_dev" PGSSL=""`, Postgres do Scoop: `pg_ctl -D C:/Users/lmalerbo/scoop/persist/postgresql/data start`).

## Review Focus

1. **Admin tirando o próprio admin / último admin** — o banco recusa com mensagem clara (testado na Task 1).
2. **GeoMap fora do ar ao salvar um acesso** — o Hub salva, e a tela avisa "salvo no Hub; o GeoMap não respondeu, salve de novo" em vez de erro genérico (Task 3 devolve `avisoGeomap`; Task 7 mostra).
3. **Pessoa com senha provisória tentando entrar no GeoMap** — `POST /auth/hub` responde 403 com `precisaTrocarSenha`, e o frontend leva à tela de definir senha (Tasks 4 e 6).
4. **Pessoa desativada com token do GeoMap ainda válido (30 dias)** — o próximo pedido dá 401 em até 60 s (Task 4).
5. **E-mail com maiúsculas/espaços** — tudo é comparado em minúsculas e sem espaços, no Hub, na função e no GeoMap (Tasks 1, 3, 5).

---

## Mapa de arquivos

**hub-geotech**
- Create `supabase/migrations/20261012090000_login_unico.sql` — colunas novas, `acesso_salvar` v2, `acessos_situacao` v2, `senha_definida`.
- Create `tests/contas/conftest.py`, `tests/contas/stub_supabase.sql`, `tests/contas/test_login_unico_sql.py` — Postgres local temporário com um "Supabase de mentira" (schema `auth`, papéis).
- Create `supabase/functions/contas/index.ts` — a função de contas.
- Create `tests/contas/test_funcao_contas.py` — integração com a função publicada (`-m banco`).
- Create `migracao/trazer_usuarios_geomap.py`, `tests/contas/test_trazer_usuarios_geomap.py`.
- Modify `app/index.html` — tela "Defina sua senha", botão "Trocar senha", tela Usuários com GeoMap, senha provisória, abrir em Ferramentas.
- Create `tests/app/teste_usuarios_tela.py` — Playwright.
- Delete `ingestao/sincronizar_usuarios.py`, `agendamento/sincronizar_usuarios.cmd`; Modify `agendamento/instalar_tarefas.cmd`, `agendamento/README.md`.
- Create `docs/runbook-login-unico.md`.

**geomap** (worktree `geomap-login-hub`)
- Create `backend/src/lib/contaHub.js` — valida o token do Hub.
- Modify `backend/src/routes/auth.js` — `POST /auth/hub`; `/login` e `PUT /senha` só com `LOGIN_LOCAL=1`.
- Modify `backend/src/middleware/auth.js` — confere status ativo (cache 60 s).
- Modify `backend/src/routes/integracao.js` — `/integracao/contas/*`.
- Modify `backend/src/routes/admin.js` — trava criar/editar/senha/excluir usuário.
- Modify `backend/.env.example`.
- Create `backend/test/login-hub.test.js`, `backend/test/integracao-contas.test.js`.
- Create `frontend/src/lib/hub.js`; Modify `frontend/src/lib/api.js`, `frontend/src/hooks/useFormularioLogin.js`, `frontend/src/pages/DefinirSenha.jsx`, `frontend/src/context/AuthContext.jsx`, `frontend/src/App.jsx`, `frontend/src/pages/AdminUsuarios.jsx`, `frontend/package.json`, `frontend/.env.example`, `.github/workflows/deploy-frontend.yml`.

---

### Task 1: Banco do Hub — acessos com GeoMap, senha provisória e travas de admin

**Files:**
- Create: `supabase/migrations/20261012090000_login_unico.sql`
- Create: `tests/contas/stub_supabase.sql`, `tests/contas/conftest.py`, `tests/contas/test_login_unico_sql.py`

**Interfaces:**
- Produces:
  - `hub.acesso_salvar(p_email text, p_nome text, p_papel text, p_admin boolean, p_modulos text[], p_geomap_ativo boolean, p_geomap_admin boolean, p_geomap_grupos int[]) returns void`
  - `hub.acessos_situacao() returns table (email, nome, papel, admin, modulos, geomap_ativo, geomap_admin, geomap_grupos, atualizado_em, usuario_id, conta_criada, bloqueado, ultimo_login, precisa_trocar_senha)`
  - `hub.senha_definida() returns void`
  - coluna `hub.usuarios.precisa_trocar_senha boolean`

- [ ] **Step 1: Stub do Supabase para testes locais**

`tests/contas/stub_supabase.sql`:
```sql
-- O mínimo do Supabase para rodar as migrações de acesso num Postgres local:
-- papéis, auth.users e auth.uid() (lido de request.jwt.claim.sub, como no Supabase).
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin; end if;
end $$;
create schema auth;
create table auth.users (
  id uuid primary key default gen_random_uuid(),
  email text, encrypted_password text, banned_until timestamptz, last_sign_in_at timestamptz,
  updated_at timestamptz
);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
create schema hub;
grant usage on schema hub, auth to anon, authenticated, service_role;
create table hub.modulos (id text primary key, nome text not null, ordem int not null, ativo boolean not null default true);
insert into hub.modulos values ('plantio','Plantio',1,true),('preparo','Preparo',2,true),('colheita','Colheita',3,true),('drone','Drone',4,true);
create table hub.usuarios (
  id uuid primary key references auth.users (id) on delete cascade, nome text not null,
  papel text not null default 'leitura' check (papel in ('editor','leitura','solicitante')),
  admin boolean not null default false, criado_em timestamptz not null default now());
create table hub.usuario_modulos (usuario_id uuid not null references hub.usuarios (id) on delete cascade,
  modulo_id text not null references hub.modulos (id), primary key (usuario_id, modulo_id));
create table hub.log_auditoria (id bigint generated always as identity primary key, modulo_id text,
  entidade_tipo text not null constraint log_auditoria_entidade_tipo_check check (entidade_tipo in ('fazenda','talhao')),
  entidade_id bigint not null, campo text not null, valor_anterior text, valor_novo text,
  usuario_id uuid references hub.usuarios (id), origem text not null default 'usuario', criado_em timestamptz not null default now());
create table hub.parametros (chave text primary key, valor text not null, descricao text, atualizado_em timestamptz not null default now());
```

- [ ] **Step 2: Fixture que sobe um Postgres temporário e aplica stub + migrações**

`tests/contas/conftest.py`:
```python
"""Postgres local temporário (initdb em pasta temporária) com o stub do Supabase
e as migrações de acesso. Precisa de initdb/pg_ctl no PATH (Postgres do Scoop)."""
import os
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest

RAIZ = Path(__file__).resolve().parents[2]
MIGRACOES = ['20261005090000_admin_acessos_ferramentas.sql', '20261012090000_login_unico.sql']


def _porta_livre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope='session')
def banco(tmp_path_factory):
    if not shutil.which('initdb'):
        pytest.skip('Postgres local (initdb) não encontrado no PATH')
    pasta, porta = tmp_path_factory.mktemp('pg'), _porta_livre()
    subprocess.run(['initdb', '-D', str(pasta), '-U', 'postgres', '-A', 'trust', '-E', 'UTF8'], check=True, capture_output=True)
    subprocess.run(['pg_ctl', '-D', str(pasta), '-o', f'-p {porta}', '-l', str(pasta / 'log.txt'), '-w', 'start'], check=True, capture_output=True)
    try:
        con = psycopg.connect(f'host=127.0.0.1 port={porta} user=postgres dbname=postgres', autocommit=True)
        con.execute((Path(__file__).parent / 'stub_supabase.sql').read_text(encoding='utf-8'))
        for m in MIGRACOES:
            con.execute((RAIZ / 'supabase' / 'migrations' / m).read_text(encoding='utf-8'))
        yield con
        con.close()
    finally:
        subprocess.run(['pg_ctl', '-D', str(pasta), '-m', 'fast', 'stop'], capture_output=True)


@pytest.fixture
def pessoa(banco):
    """pessoa(email, admin=False) -> uuid de uma conta auth + hub.usuarios + hub.acessos."""
    def _cria(email, admin=False, com_acesso=True):
        uid = uuid.uuid4()
        banco.execute('insert into auth.users (id, email) values (%s, %s)', (uid, email))
        banco.execute('insert into hub.usuarios (id, nome, admin) values (%s, %s, %s)', (uid, email.split('@')[0], admin))
        if com_acesso:
            banco.execute('insert into hub.acessos (email, nome, admin) values (%s, %s, %s)', (email, email.split('@')[0], admin))
        return uid
    return _cria


@pytest.fixture
def como(banco):
    """como(uid, sql, params) -> executa como 'authenticated' com auth.uid() = uid; devolve linhas ou a mensagem de erro."""
    def _exec(uid, sql, params=()):
        with banco.transaction():
            banco.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(uid),))
            banco.execute('set local role authenticated')
            try:
                with banco.transaction():
                    cur = banco.execute(sql, params)
                    return cur.fetchall() if cur.description else None
            except psycopg.Error as e:
                return ('ERRO', e.diag.message_primary)
    return _exec
```

- [ ] **Step 3: Testes do banco (falham sem a migração)**

`tests/contas/test_login_unico_sql.py`:
```python
SALVAR = 'select hub.acesso_salvar(%s, %s, %s, %s, %s, %s, %s, %s)'


def salvar(como, uid, email, nome='Fulano', papel='leitura', admin=False, modulos=(), gm_ativo=False, gm_admin=False, gm_grupos=()):
    return como(uid, SALVAR, (email, nome, papel, admin, list(modulos), gm_ativo, gm_admin, list(gm_grupos)))


def test_salvar_grava_campos_do_geomap(banco, pessoa, como):
    adm = pessoa('adm1@x.com', admin=True)
    assert salvar(como, adm, '  Nova@X.com ', gm_ativo=True, gm_admin=True, gm_grupos=[3, 5]) == [(None,)]
    linha = banco.execute("select email, geomap_ativo, geomap_admin, geomap_grupos from hub.acessos where email='nova@x.com'").fetchone()
    assert linha == ('nova@x.com', True, True, [3, 5])


def test_salvar_cria_hub_usuarios_quando_a_conta_existe(banco, pessoa, como):
    adm = pessoa('adm2@x.com', admin=True)
    uid = banco.execute("insert into auth.users (email) values ('soconta@x.com') returning id").fetchone()[0]
    salvar(como, adm, 'soconta@x.com', nome='Só Conta', papel='editor', modulos=['plantio'])
    assert banco.execute('select nome, papel from hub.usuarios where id=%s', (uid,)).fetchone() == ('Só Conta', 'editor')
    assert banco.execute('select modulo_id from hub.usuario_modulos where usuario_id=%s', (uid,)).fetchall() == [('plantio',)]


def test_nao_admin_nao_salva(pessoa, como):
    comum = pessoa('comum@x.com')
    assert salvar(como, comum, 'outro@x.com')[0] == 'ERRO'


def test_nao_tira_o_proprio_admin(pessoa, como):
    adm = pessoa('adm3@x.com', admin=True)
    pessoa('adm3b@x.com', admin=True)
    r = salvar(como, adm, 'adm3@x.com', admin=False)
    assert r[0] == 'ERRO' and 'próprio admin' in r[1]


def test_nao_remove_o_ultimo_admin(banco, pessoa, como):
    banco.execute('update hub.acessos set admin = false')
    banco.execute('update hub.usuarios set admin = false')
    unico = pessoa('unico@x.com', admin=True)
    outro = pessoa('outro-adm@x.com', admin=True)
    banco.execute("update hub.acessos set admin = false where email = 'outro-adm@x.com'")  # só o 'unico' é admin na lista
    r = salvar(como, outro, 'unico@x.com', admin=False)
    assert r[0] == 'ERRO' and 'pelo menos um administrador' in r[1]
    assert unico


def test_situacao_traz_geomap_e_senha_provisoria(banco, pessoa, como):
    adm = pessoa('adm4@x.com', admin=True)
    uid = pessoa('prov@x.com')
    banco.execute('update hub.usuarios set precisa_trocar_senha = true where id=%s', (uid,))
    salvar(como, adm, 'prov@x.com', gm_ativo=True, gm_grupos=[2])
    linhas = {r[0]: r for r in como(adm, 'select email, geomap_ativo, geomap_grupos, precisa_trocar_senha from hub.acessos_situacao()')}
    assert linhas['prov@x.com'][1:] == (True, [2], True)


def test_senha_definida_so_desliga_a_propria(banco, pessoa, como):
    a, b = pessoa('a@x.com'), pessoa('b@x.com')
    banco.execute('update hub.usuarios set precisa_trocar_senha = true where id in (%s, %s)', (a, b))
    como(a, 'select hub.senha_definida()')
    assert banco.execute('select precisa_trocar_senha from hub.usuarios where id=%s', (a,)).fetchone() == (False,)
    assert banco.execute('select precisa_trocar_senha from hub.usuarios where id=%s', (b,)).fetchone() == (True,)
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `cd C:/Users/lmalerbo/Documents/hub-geotech-colheita && pip install "psycopg[binary]" && python -m pytest tests/contas/test_login_unico_sql.py -q`
Expected: erro ao aplicar migração (`20261012090000_login_unico.sql` não existe).

- [ ] **Step 5: Escrever a migração**

`supabase/migrations/20261012090000_login_unico.sql`:
```sql
-- Login único: o Hub passa a ser o dono das contas e senhas, e a tela Usuários
-- controla também o acesso ao GeoMap (grupos e admin). Ver
-- docs/superpowers/specs/2026-10-09-login-unico-design.md.
--
--   hub.usuarios.precisa_trocar_senha  liga com senha provisória (criada ou
--                                      redefinida pela função "contas").
--   hub.acessos.geomap_*               acesso ao GeoMap; a função "contas"
--                                      empurra para o GeoMap ao salvar.

begin;

alter table hub.usuarios add column if not exists precisa_trocar_senha boolean not null default false;

alter table hub.acessos
  add column if not exists geomap_ativo  boolean not null default false,
  add column if not exists geomap_admin  boolean not null default false,
  add column if not exists geomap_grupos int[]   not null default '{}';

drop function if exists hub.acesso_salvar(text, text, text, boolean, text[]);
create function hub.acesso_salvar(
  p_email text, p_nome text, p_papel text, p_admin boolean, p_modulos text[],
  p_geomap_ativo boolean, p_geomap_admin boolean, p_geomap_grupos int[])
returns void language plpgsql security definer set search_path = hub, auth as $$
declare
  v_email    text := lower(trim(p_email));
  v_admin    boolean := coalesce(p_admin, false);
  v_uid      uuid;
  v_era_admin boolean;
begin
  if not hub.eh_admin() then raise exception 'Só administradores alteram acessos'; end if;
  if v_email !~ '^[^@\s]+@[^@\s]+$' then raise exception 'E-mail inválido: %', p_email; end if;
  if length(trim(coalesce(p_nome, ''))) = 0 then raise exception 'Informe o nome'; end if;
  if exists (select 1 from unnest(coalesce(p_modulos, '{}')) m where m not in (select id from hub.modulos)) then
    raise exception 'Módulo inválido';
  end if;
  select id into v_uid from auth.users where lower(email) = v_email;
  select admin into v_era_admin from hub.acessos where email = v_email;
  if coalesce(v_era_admin, false) and not v_admin then
    if v_uid = auth.uid() then raise exception 'Você não pode tirar o seu próprio admin'; end if;
    if not exists (select 1 from hub.acessos where admin and email <> v_email) then
      raise exception 'É preciso ter pelo menos um administrador';
    end if;
  end if;

  insert into hub.acessos (email, nome, papel, admin, modulos, geomap_ativo, geomap_admin, geomap_grupos, atualizado_por, atualizado_em)
  values (v_email, trim(p_nome), p_papel, v_admin, coalesce(p_modulos, '{}'),
          coalesce(p_geomap_ativo, false), coalesce(p_geomap_admin, false), coalesce(p_geomap_grupos, '{}'), auth.uid(), now())
  on conflict (email) do update
    set nome = excluded.nome, papel = excluded.papel, admin = excluded.admin, modulos = excluded.modulos,
        geomap_ativo = excluded.geomap_ativo, geomap_admin = excluded.geomap_admin, geomap_grupos = excluded.geomap_grupos,
        atualizado_por = excluded.atualizado_por, atualizado_em = now();

  if v_uid is not null then
    insert into hub.usuarios (id, nome, papel, admin) values (v_uid, trim(p_nome), p_papel, v_admin)
    on conflict (id) do update set nome = excluded.nome, papel = excluded.papel, admin = excluded.admin;
    delete from hub.usuario_modulos where usuario_id = v_uid;
    insert into hub.usuario_modulos (usuario_id, modulo_id) select v_uid, unnest(coalesce(p_modulos, '{}'));
  end if;

  insert into hub.log_auditoria (entidade_tipo, entidade_id, campo, valor_novo, usuario_id, origem)
  values ('sistema', 0, 'acesso', v_email || ' · ' || p_papel || case when v_admin then ' + admin' else '' end
          || ' · ' || array_to_string(coalesce(p_modulos, '{}'), ', ')
          || case when coalesce(p_geomap_ativo, false) then ' · GeoMap' || case when p_geomap_admin then ' admin' else '' end
                  || ' grupos ' || array_to_string(coalesce(p_geomap_grupos, '{}'), ',') else '' end,
          auth.uid(), 'usuario');
end $$;

drop function if exists hub.acessos_situacao();
create function hub.acessos_situacao()
returns table (email text, nome text, papel text, admin boolean, modulos text[],
               geomap_ativo boolean, geomap_admin boolean, geomap_grupos int[], atualizado_em timestamptz,
               usuario_id uuid, conta_criada boolean, bloqueado boolean, ultimo_login timestamptz,
               precisa_trocar_senha boolean)
language sql stable security definer set search_path = hub, auth as $$
  select a.email, a.nome, a.papel, a.admin, a.modulos, a.geomap_ativo, a.geomap_admin, a.geomap_grupos, a.atualizado_em,
         u.id, u.id is not null, coalesce(u.banned_until > now(), false), u.last_sign_in_at,
         coalesce(hu.precisa_trocar_senha, false)
    from hub.acessos a
    left join auth.users u on lower(u.email) = a.email
    left join hub.usuarios hu on hu.id = u.id
   where hub.eh_admin()
   order by a.nome;
$$;

-- A própria pessoa, depois de trocar a senha (supabase.auth.updateUser).
create or replace function hub.senha_definida()
returns void language sql security definer set search_path = hub as $$
  update hub.usuarios set precisa_trocar_senha = false where id = auth.uid();
$$;

revoke all on function hub.acesso_salvar(text, text, text, boolean, text[], boolean, boolean, int[]) from public, anon;
revoke all on function hub.acessos_situacao() from public, anon;
revoke all on function hub.senha_definida() from public, anon;
grant execute on function hub.acesso_salvar(text, text, text, boolean, text[], boolean, boolean, int[]) to authenticated, service_role;
grant execute on function hub.acessos_situacao() to authenticated, service_role;
grant execute on function hub.senha_definida() to authenticated, service_role;

commit;
```

- [ ] **Step 6: Rodar e ver passar**

Run: `python -m pytest tests/contas/test_login_unico_sql.py -q`
Expected: `7 passed`.

- [ ] **Step 7: Commit**

```bash
git add supabase/migrations/20261012090000_login_unico.sql tests/contas/
git commit -m "Login unico: acessos com GeoMap, senha provisoria e travas de admin no banco"
```

---

### Task 2: GeoMap — rotas do Hub para contas e trava das telas de usuário

**Files (worktree `geomap-login-hub`):**
- Modify: `backend/src/routes/integracao.js` (rotas novas no fim do arquivo + `import { pool }`)
- Modify: `backend/src/routes/admin.js` (`contasNoHub` nas 4 rotas de usuário)
- Create: `backend/test/integracao-contas.test.js`

**Interfaces:**
- Produces (todas com cabeçalho `x-hub-token`):
  - `GET /integracao/contas/grupos` → `[{id:number, nome:string}]`
  - `GET /integracao/contas/usuarios` → `[{email, nome, status, papel, grupoIds:number[], precisaTrocarSenha:boolean}]`
  - `PUT /integracao/contas/usuario` body `{email, nome, ativo:boolean, admin:boolean, grupoIds:number[]}` → `{ok:true, criado:boolean, id?:number}`; 400 `{erro}` se tirar o último admin ativo.
  - Com `LOGIN_LOCAL` diferente de `"1"`: `POST/PUT/DELETE /admin/usuarios...` (exceto `/piloto`) → 410 `{erro}`.

- [ ] **Step 1: Criar a worktree**

```bash
cd C:/Users/lmalerbo/Documents/GitHub/geomap && git fetch origin
git worktree add ../geomap-login-hub -b feat/login-hub origin/master
cd ../geomap-login-hub/backend && npm ci
pg_ctl -D C:/Users/lmalerbo/scoop/persist/postgresql/data start
```

- [ ] **Step 2: Testes (falham)**

`backend/test/integracao-contas.test.js`:
```js
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { pool, iniciarServidor, req, tokenPara } from "./helpers.js";

process.env.HUB_INTEGRACAO_TOKEN = "chave-teste-hub";
const H = { "x-hub-token": "chave-teste-hub", "Content-Type": "application/json" };
let srv;
const sufixo = `t${Date.now()}`;

before(async () => { srv = await iniciarServidor(); });
after(async () => {
  await pool.query("DELETE FROM usuarios WHERE email LIKE $1", [`%${sufixo}%`]);
  await pool.query("DELETE FROM grupos WHERE nome LIKE $1", [`%${sufixo}%`]);
  await srv.fechar();
});

async function put(corpo, headers = H) {
  const r = await fetch(`${srv.url}/integracao/contas/usuario`, { method: "PUT", headers, body: JSON.stringify(corpo) });
  return { status: r.status, corpo: await r.json() };
}

test("sem a chave do Hub: 401", async () => {
  const r = await put({ email: `x-${sufixo}@t.local`, nome: "X", ativo: true }, { "Content-Type": "application/json" });
  assert.equal(r.status, 401);
});

test("cria pessoa ativa com grupos, sem senha utilizável", async () => {
  const g = (await pool.query("INSERT INTO grupos (nome) VALUES ($1) RETURNING id", [`g-${sufixo}`])).rows[0];
  const r = await put({ email: ` Nova-${sufixo}@T.local `, nome: "Nova", ativo: true, admin: false, grupoIds: [g.id, 999999] });
  assert.equal(r.status, 200);
  assert.equal(r.corpo.criado, true);
  const u = (await pool.query("SELECT status, papel, senha_hash FROM usuarios WHERE email = $1", [`nova-${sufixo}@t.local`])).rows[0];
  assert.deepEqual([u.status, u.papel, u.senha_hash], ["ativo", "usuario", "!hub"]);
  const gs = (await pool.query("SELECT grupo_id FROM usuarios_grupos WHERE usuario_id = $1", [r.corpo.id])).rows.map((x) => x.grupo_id);
  assert.deepEqual(gs, [g.id]); // grupo inexistente é ignorado
});

test("pessoa inexistente e inativa: não cria nada", async () => {
  const r = await put({ email: `nada-${sufixo}@t.local`, nome: "Nada", ativo: false });
  assert.deepEqual(r.corpo, { ok: true, criado: false });
  assert.equal((await pool.query("SELECT 1 FROM usuarios WHERE email = $1", [`nada-${sufixo}@t.local`])).rowCount, 0);
});

test("desativar existente mantém a pessoa e tira os grupos", async () => {
  await put({ email: `sai-${sufixo}@t.local`, nome: "Sai", ativo: true, grupoIds: [] });
  const r = await put({ email: `sai-${sufixo}@t.local`, nome: "Sai", ativo: false, grupoIds: [] });
  assert.equal(r.status, 200);
  assert.equal((await pool.query("SELECT status FROM usuarios WHERE email = $1", [`sai-${sufixo}@t.local`])).rows[0].status, "inativo");
});

test("não tira o último admin ativo", async () => {
  const { rows } = await pool.query("SELECT email FROM usuarios WHERE papel = 'admin' AND status = 'ativo'");
  await pool.query("UPDATE usuarios SET papel = 'usuario' WHERE papel = 'admin' AND status = 'ativo'");
  try {
    await put({ email: `adm-${sufixo}@t.local`, nome: "Adm", ativo: true, admin: true });
    const r = await put({ email: `adm-${sufixo}@t.local`, nome: "Adm", ativo: true, admin: false });
    assert.equal(r.status, 400);
    assert.match(r.corpo.erro, /último admin/);
  } finally {
    if (rows.length) await pool.query("UPDATE usuarios SET papel = 'admin' WHERE email = ANY($1)", [rows.map((x) => x.email)]);
  }
});

test("lista grupos e usuários", async () => {
  const g = await (await fetch(`${srv.url}/integracao/contas/grupos`, { headers: H })).json();
  assert.ok(g.some((x) => x.nome === `g-${sufixo}`));
  const u = await (await fetch(`${srv.url}/integracao/contas/usuarios`, { headers: H })).json();
  const nova = u.find((x) => x.email === `nova-${sufixo}@t.local`);
  assert.equal(nova.grupoIds.length, 1);
});

test("telas de usuário do admin travadas sem LOGIN_LOCAL", async () => {
  delete process.env.LOGIN_LOCAL;
  const adm = (await pool.query(
    "INSERT INTO usuarios (nome, email, senha_hash, papel) VALUES ('Adm T', $1, 'x', 'admin') RETURNING id, nome, papel",
    [`admt-${sufixo}@t.local`])).rows[0];
  const r = await req(`${srv.url}/admin/usuarios`, tokenPara(adm), { method: "POST", body: { nome: "Z", email: `z-${sufixo}@t.local` } });
  assert.equal(r.status, 410);
});
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd backend && DATABASE_URL="postgresql://geoportal@localhost:5432/geoportal_dev" PGSSL="" node --test test/integracao-contas.test.js`
Expected: FAIL (404 nas rotas novas; 201 em vez de 410).

- [ ] **Step 4: Rotas novas** — no topo de `backend/src/routes/integracao.js` acrescentar `import { pool } from "../db/pool.js";` e, no fim do arquivo:

```js
// ── Contas (login único, 2026-10) ─────────────────────────────────────────
// O Hub Geotech é o dono das contas e senhas: o GeoMap só guarda quem está
// ativo, se é admin e em quais grupos está. Quem chama é a função "contas"
// do Hub, com a mesma chave do Hub. Grupos e mapas continuam definidos aqui.
integracaoRouter.use("/integracao/contas", exigirChave("x-hub-token", "HUB_INTEGRACAO_TOKEN"));

integracaoRouter.get("/integracao/contas/grupos", async (req, res) => {
  const { rows } = await pool.query("SELECT id, nome FROM grupos ORDER BY nome");
  res.json(rows);
});

integracaoRouter.get("/integracao/contas/usuarios", async (req, res) => {
  const { rows } = await pool.query(
    `SELECT lower(u.email) AS email, u.nome, u.status, u.papel, u.precisa_trocar_senha AS "precisaTrocarSenha",
            coalesce(array_agg(ug.grupo_id) FILTER (WHERE ug.grupo_id IS NOT NULL), '{}') AS "grupoIds"
       FROM usuarios u LEFT JOIN usuarios_grupos ug ON ug.usuario_id = u.id
      GROUP BY u.id ORDER BY u.nome`
  );
  res.json(rows);
});

integracaoRouter.put("/integracao/contas/usuario", async (req, res) => {
  const email = String(req.body?.email || "").trim().toLowerCase();
  const nome = String(req.body?.nome || "").trim();
  const ativo = req.body?.ativo === true;
  const papel = req.body?.admin === true ? "admin" : "usuario";
  const status = ativo ? "ativo" : "inativo";
  const pedidos = Array.isArray(req.body?.grupoIds) ? req.body.grupoIds.map(Number).filter(Number.isInteger) : [];
  if (!email.includes("@") || !nome) return res.status(400).json({ erro: "email e nome são obrigatórios" });

  const atual = (await pool.query("SELECT id, papel, status FROM usuarios WHERE lower(email) = $1", [email])).rows[0];
  if (!atual && !ativo) return res.json({ ok: true, criado: false });

  if (atual && atual.papel === "admin" && atual.status === "ativo" && (papel !== "admin" || status !== "ativo")) {
    const { rows } = await pool.query(
      "SELECT count(*)::int AS n FROM usuarios WHERE papel = 'admin' AND status = 'ativo' AND id <> $1", [atual.id]);
    if (rows[0].n === 0) return res.status(400).json({ erro: "não é possível remover o último admin ativo do GeoMap" });
  }

  const grupoIds = ativo && pedidos.length
    ? (await pool.query("SELECT id FROM grupos WHERE id = ANY($1::int[])", [pedidos])).rows.map((g) => g.id)
    : [];

  let id = atual?.id;
  if (atual) {
    await pool.query("UPDATE usuarios SET nome = $1, papel = $2, status = $3 WHERE id = $4", [nome, papel, status, id]);
  } else {
    // "!hub" não é um hash bcrypt: ninguém entra pelo login antigo com essa conta.
    id = (await pool.query(
      `INSERT INTO usuarios (nome, email, senha_hash, papel, status, precisa_trocar_senha)
       VALUES ($1, $2, '!hub', $3, $4, false) RETURNING id`, [nome, email, papel, status])).rows[0].id;
  }
  await pool.query("DELETE FROM usuarios_grupos WHERE usuario_id = $1", [id]);
  if (grupoIds.length) {
    await pool.query(
      "INSERT INTO usuarios_grupos (usuario_id, grupo_id) SELECT $1, unnest($2::int[]) ON CONFLICT DO NOTHING", [id, grupoIds]);
  }
  res.json({ ok: true, criado: !atual, id });
});
```

- [ ] **Step 5: Trava no admin** — em `backend/src/routes/admin.js`, logo depois dos imports:

```js
// Login único (2026-10): contas, senhas e grupos de cada pessoa são geridos
// no Hub Geotech. LOGIN_LOCAL=1 religa as telas antigas (caminho de volta).
function contasNoHub(req, res, next) {
  if (process.env.LOGIN_LOCAL === "1") return next();
  return res.status(410).json({ erro: "contas, senhas e grupos de usuário são gerenciados no Hub Geotech" });
}
```
e inserir `contasNoHub,` como segundo argumento em: `adminRouter.post("/admin/usuarios", ...)`, `adminRouter.put("/admin/usuarios/:id", ...)`, `adminRouter.put("/admin/usuarios/:id/senha", ...)`, `adminRouter.delete("/admin/usuarios/:id", ...)`. **Não** em `/admin/usuarios/:id/piloto` nem nas rotas de grupos.

- [ ] **Step 6: Rodar e ver passar** — mesmo comando do Step 3. Expected: `7 pass`. Rodar também a suíte inteira (`npm test` com as mesmas variáveis) e conferir que nada mais quebrou.

- [ ] **Step 7: Commit**

```bash
git add backend/src/routes/integracao.js backend/src/routes/admin.js backend/test/integracao-contas.test.js
git commit -m "Login unico: rotas do Hub para contas e telas de usuario travadas (LOGIN_LOCAL religa)"
```

---

### Task 3: Função `contas` (Supabase Edge Function)

**Files:**
- Create: `supabase/functions/contas/index.ts`
- Create: `tests/contas/test_funcao_contas.py` (marcado `banco`)

**Interfaces:**
- Consumes: `hub.eh_admin()`, `hub.acesso_salvar(...8 parâmetros)`, `hub.acesso_remover(p_email)` (Task 1 e migração 20261005); rotas `/integracao/contas/*` (Task 2).
- Produces: `POST {SUPABASE_URL}/functions/v1/contas` com `Authorization: Bearer <login do admin>` e corpo:
  - `{acao:"grupos_geomap"}` → `[{id, nome}]`
  - `{acao:"salvar", email, nome, papel, admin, modulos, geomap_ativo, geomap_admin, geomap_grupos}` → `{ok:true, senhaProvisoria:string|null, avisoGeomap:string|null}`
  - `{acao:"redefinir_senha", email}` → `{ok:true, senhaProvisoria:string}`
  - `{acao:"remover", email}` → `{ok:true, avisoGeomap:string|null}`
  - Erros → `{erro}` com status 400/403.

- [ ] **Step 1: Escrever a função**

`supabase/functions/contas/index.ts`:
```ts
// Função "contas" do Hub Geotech (login único). Única peça com a chave de
// serviço — injetada pelo próprio Supabase em SUPABASE_SERVICE_ROLE_KEY, nunca
// guardada em arquivo. Quem chama manda o próprio login; só admin passa.
// Segredos: HUB_INTEGRACAO_TOKEN (o mesmo que o GeoMap aceita) e GEOMAP_URL.
import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICO = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const GEOMAP = (Deno.env.get("GEOMAP_URL") || "").replace(/\/$/, "");
const TOKEN_HUB = Deno.env.get("HUB_INTEGRACAO_TOKEN") || "";
const ORIGENS = ["https://lmalerbo.github.io", "http://127.0.0.1:8767"];
const BLOQUEIO = "876000h";
const ALFABETO = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789";

type Acesso = {
  email: string; nome: string; papel: string; admin: boolean; modulos: string[];
  geomap_ativo: boolean; geomap_admin: boolean; geomap_grupos: number[];
};

export function senhaProvisoria(n = 10): string {
  const b = crypto.getRandomValues(new Uint8Array(n));
  return Array.from(b, (x) => ALFABETO[x % ALFABETO.length]).join("");
}

function cors(req: Request) {
  const o = req.headers.get("Origin") || "";
  return {
    "Access-Control-Allow-Origin": ORIGENS.includes(o) ? o : ORIGENS[0],
    "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
}

async function geomap(caminho: string, opcoes: RequestInit = {}) {
  if (!GEOMAP || !TOKEN_HUB) throw new Error("GeoMap não configurado na função (GEOMAP_URL/HUB_INTEGRACAO_TOKEN)");
  const r = await fetch(`${GEOMAP}${caminho}`, {
    ...opcoes,
    headers: { "x-hub-token": TOKEN_HUB, "Content-Type": "application/json" },
  });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`GeoMap: ${corpo.erro || `HTTP ${r.status}`}`);
  return corpo;
}

async function contaPorEmail(servico: SupabaseClient, email: string) {
  for (let pagina = 1; ; pagina++) {
    const { data, error } = await servico.auth.admin.listUsers({ page: pagina, perPage: 200 });
    if (error) throw new Error(`Auth: ${error.message}`);
    const achou = data.users.find((u) => (u.email || "").toLowerCase() === email);
    if (achou) return achou;
    if (data.users.length < 200) return null;
  }
}

async function salvar(comoUsuario: SupabaseClient, servico: SupabaseClient, a: Acesso) {
  const email = String(a.email || "").trim().toLowerCase();
  const modulos = a.modulos || [];
  let conta = await contaPorEmail(servico, email);
  let senha: string | null = null;
  if (!conta) {
    senha = senhaProvisoria();
    const { data, error } = await servico.auth.admin.createUser({
      email, password: senha, email_confirm: true, user_metadata: { nome: a.nome },
    });
    if (error) throw new Error(`Não foi possível criar a conta: ${error.message}`);
    conta = data.user;
  }
  const { error } = await comoUsuario.rpc("acesso_salvar", {
    p_email: email, p_nome: a.nome, p_papel: a.papel || "leitura", p_admin: !!a.admin, p_modulos: modulos,
    p_geomap_ativo: !!a.geomap_ativo, p_geomap_admin: !!a.geomap_admin, p_geomap_grupos: a.geomap_grupos || [],
  });
  if (error) {
    if (senha) await servico.auth.admin.deleteUser(conta!.id);   // conta recém-criada sem acesso: desfaz
    throw new Error(error.message);
  }
  if (senha) await servico.from("usuarios").update({ precisa_trocar_senha: true }).eq("id", conta!.id);
  const temAcesso = modulos.length > 0 || !!a.geomap_ativo;
  await servico.auth.admin.updateUserById(conta!.id, { ban_duration: temAcesso ? "none" : BLOQUEIO });
  let avisoGeomap: string | null = null;
  try {
    await geomap("/integracao/contas/usuario", {
      method: "PUT",
      body: JSON.stringify({ email, nome: a.nome, ativo: !!a.geomap_ativo, admin: !!a.geomap_admin, grupoIds: a.geomap_grupos || [] }),
    });
  } catch (e) { avisoGeomap = (e as Error).message; }
  return { ok: true, senhaProvisoria: senha, avisoGeomap };
}

async function redefinir(servico: SupabaseClient, emailBruto: string) {
  const conta = await contaPorEmail(servico, String(emailBruto || "").trim().toLowerCase());
  if (!conta) throw new Error("Essa pessoa ainda não tem conta.");
  const senha = senhaProvisoria();
  const { error } = await servico.auth.admin.updateUserById(conta.id, { password: senha });
  if (error) throw new Error(`Não foi possível redefinir: ${error.message}`);
  await servico.from("usuarios").update({ precisa_trocar_senha: true }).eq("id", conta.id);
  return { ok: true, senhaProvisoria: senha };
}

async function remover(comoUsuario: SupabaseClient, servico: SupabaseClient, emailBruto: string) {
  const email = String(emailBruto || "").trim().toLowerCase();
  const { data: linhas } = await comoUsuario.rpc("acessos_situacao");
  const nome = (linhas || []).find((x: { email: string }) => x.email === email)?.nome || email;
  const { error } = await comoUsuario.rpc("acesso_remover", { p_email: email });
  if (error) throw new Error(error.message);
  const conta = await contaPorEmail(servico, email);
  if (conta) await servico.auth.admin.updateUserById(conta.id, { ban_duration: BLOQUEIO });
  let avisoGeomap: string | null = null;
  try {
    await geomap("/integracao/contas/usuario", { method: "PUT", body: JSON.stringify({ email, nome, ativo: false, admin: false, grupoIds: [] }) });
  } catch (e) { avisoGeomap = (e as Error).message; }
  return { ok: true, avisoGeomap };
}

Deno.serve(async (req) => {
  const h = cors(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: h });
  const resp = (obj: unknown, status = 200) =>
    new Response(JSON.stringify(obj), { status, headers: { ...h, "Content-Type": "application/json" } });
  try {
    const comoUsuario = createClient(SUPABASE_URL, ANON, {
      global: { headers: { Authorization: req.headers.get("Authorization") || "" } },
      db: { schema: "hub" }, auth: { persistSession: false },
    });
    const { data: ehAdmin, error } = await comoUsuario.rpc("eh_admin");
    if (error || !ehAdmin) return resp({ erro: "Só administradores gerenciam acessos." }, 403);
    const servico = createClient(SUPABASE_URL, SERVICO, { db: { schema: "hub" }, auth: { persistSession: false } });
    const corpo = await req.json();
    switch (corpo.acao) {
      case "grupos_geomap": return resp(await geomap("/integracao/contas/grupos"));
      case "salvar": return resp(await salvar(comoUsuario, servico, corpo));
      case "redefinir_senha": return resp(await redefinir(servico, corpo.email));
      case "remover": return resp(await remover(comoUsuario, servico, corpo.email));
      default: return resp({ erro: "Ação desconhecida" }, 400);
    }
  } catch (e) {
    return resp({ erro: (e as Error).message || String(e) }, 400);
  }
});
```

- [ ] **Step 2: Teste de integração (marcado `banco`, roda contra a função publicada)**

`tests/contas/test_funcao_contas.py`:
```python
"""Função "contas" publicada, com a conta de teste promovida a admin só durante
o teste. Cria um acesso @hub.local SEM GeoMap (não toca no GeoMap de produção),
redefine a senha, remove — e apaga a conta de teste criada no fim."""
import json
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'ingestao'))
from comum import Hub, carregar_env  # noqa: E402

pytestmark = pytest.mark.banco
CONTA = json.load(open(os.environ['HUB_CONTA_TESTE'], encoding='utf-8'))
EMAIL = 'funcao-contas@hub.local'
URL = 'https://dpvsivypabmvmrrpgmhc.supabase.co'
CHAVE = 'sb_publishable_3xv0R1kmhSXkoUh3i4vN0A_Q5oLBbVL'


def entrar(email, senha):
    r = requests.post(f'{URL}/auth/v1/token?grant_type=password', headers={'apikey': CHAVE},
                      json={'email': email, 'password': senha}, timeout=30)
    return r.json().get('access_token') if r.ok else None


def contas(token, **corpo):
    r = requests.post(f'{URL}/functions/v1/contas', headers={'apikey': CHAVE, 'Authorization': f'Bearer {token}'},
                      json=corpo, timeout=60)
    return r.status_code, r.json()


@pytest.fixture
def admin_token():
    hub = Hub()
    hub.atualizar('usuarios', {'id': f"eq.{CONTA['id']}"}, {'admin': True})
    hub.upsert('acessos', [{'email': CONTA['email'], 'nome': 'Teste Automatizado', 'admin': True}], 'email')
    try:
        yield entrar(CONTA['email'], CONTA['senha'])
    finally:
        hub.atualizar('usuarios', {'id': f"eq.{CONTA['id']}"}, {'admin': False})
        requests.delete(f'{hub.url}/acessos', params={'email': f"eq.{CONTA['email']}"}, headers=hub.headers, timeout=30)
        requests.delete(f'{hub.url}/acessos', params={'email': f'eq.{EMAIL}'}, headers=hub.headers, timeout=30)
        env = carregar_env()
        adm = {'apikey': env['SUPABASE_SERVICE_ROLE_KEY'], 'Authorization': f"Bearer {env['SUPABASE_SERVICE_ROLE_KEY']}"}
        lista = requests.get(f'{URL}/auth/v1/admin/users', headers=adm, params={'per_page': 200}, timeout=30).json()['users']
        for u in lista:
            if u['email'] == EMAIL:
                requests.delete(f"{URL}/auth/v1/admin/users/{u['id']}", headers=adm, timeout=30)


def test_nao_admin_recebe_403():
    token = entrar(CONTA['email'], CONTA['senha'])
    status, corpo = contas(token, acao='grupos_geomap')
    assert status == 403


def test_fluxo_completo(admin_token):
    status, grupos = contas(admin_token, acao='grupos_geomap')
    assert status == 200 and isinstance(grupos, list) and grupos

    status, r = contas(admin_token, acao='salvar', email=EMAIL, nome='Funcao Contas', papel='leitura',
                       admin=False, modulos=['plantio'], geomap_ativo=False, geomap_admin=False, geomap_grupos=[])
    assert status == 200 and r['senhaProvisoria'] and len(r['senhaProvisoria']) == 10 and r['avisoGeomap'] is None
    token_novo = entrar(EMAIL, r['senhaProvisoria'])
    assert token_novo, 'a senha provisória entra'
    hub = Hub()
    linha = hub.selecionar('usuarios', 'precisa_trocar_senha', {'nome': 'eq.Funcao Contas'})
    assert linha == [{'precisa_trocar_senha': True}]

    status, r2 = contas(admin_token, acao='redefinir_senha', email=EMAIL)
    assert status == 200 and r2['senhaProvisoria'] != r['senhaProvisoria']
    assert entrar(EMAIL, r['senhaProvisoria']) is None and entrar(EMAIL, r2['senhaProvisoria'])

    status, r3 = contas(admin_token, acao='remover', email=EMAIL)
    assert status == 200
    assert entrar(EMAIL, r2['senhaProvisoria']) is None, 'conta removida fica bloqueada'
```

- [ ] **Step 3: Publicar a migração da Task 1 e a função** (o Leo roda a migração no SQL Editor; a função):

```bash
cd C:/Users/lmalerbo/Documents/hub-geotech-colheita
supabase login                       # só na primeira vez (abre o navegador)
supabase functions deploy contas --project-ref dpvsivypabmvmrrpgmhc
supabase secrets set --project-ref dpvsivypabmvmrrpgmhc GEOMAP_URL=https://geomap-docker.onrender.com
supabase secrets set --project-ref dpvsivypabmvmrrpgmhc HUB_INTEGRACAO_TOKEN=<valor do hub-geotech-supabase.env, colado pelo Leo no terminal dele>
```
(O valor do token é digitado pelo Leo no terminal, nunca passado pelo chat.) Até a Task 2 estar publicada no Render, `grupos_geomap` responde erro — por isso este teste roda depois da Task 2 publicada (ver Task 8).

- [ ] **Step 4: Rodar o teste**

Run: `HUB_CONTA_TESTE=<scratchpad>/conta-teste.json python -m pytest tests/contas/test_funcao_contas.py -m banco -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add supabase/functions/contas/index.ts tests/contas/test_funcao_contas.py
git commit -m "Login unico: funcao contas (criar, redefinir senha, remover, grupos do GeoMap)"
```

---

### Task 4: GeoMap backend — entrar com o login do Hub e status a cada pedido

**Files (worktree `geomap-login-hub`):**
- Create: `backend/src/lib/contaHub.js`
- Modify: `backend/src/routes/auth.js`
- Modify: `backend/src/middleware/auth.js`
- Modify: `backend/.env.example`
- Create: `backend/test/login-hub.test.js`

**Interfaces:**
- Consumes: Supabase do Hub `GET /auth/v1/user`, `GET /rest/v1/usuarios?id=eq.<uid>&select=precisa_trocar_senha` (`Accept-Profile: hub`); coluna da Task 1.
- Produces:
  - `POST /auth/hub {accessToken}` → 200 `{token, usuario:{id,nome,email,papel}}` | 401 `{erro}` | 403 `{erro, precisaTrocarSenha:true}` | 403 `{erro}` (sem acesso ao GeoMap).
  - `POST /login`, `PUT /senha` → 410 sem `LOGIN_LOCAL=1`.
  - `exigirAutenticacao` responde 401 `{erro:"acesso desativado"}` para quem está inativo (cache 60 s); `limparCacheAtivos()` exportado para testes.
  - env `HUB_SUPABASE_URL`, `HUB_SUPABASE_ANON_KEY`.

- [ ] **Step 1: Testes (falham)** — `backend/test/login-hub.test.js`:

```js
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { pool, iniciarServidor, req, tokenPara } from "./helpers.js";
import { limparCacheAtivos } from "../src/middleware/auth.js";

// Supabase do Hub de mentira: token "ok-<email>" vale; "prov-<email>" é senha provisória.
let hubFalso, srv;
const sufixo = `t${Date.now()}`;
before(async () => {
  hubFalso = http.createServer((rq, rs) => {
    const token = (rq.headers.authorization || "").replace("Bearer ", "");
    const [tipo, email] = token.split(/-(.+)/);
    rs.setHeader("Content-Type", "application/json");
    if (rq.url.startsWith("/auth/v1/user")) {
      if (tipo !== "ok" && tipo !== "prov") { rs.statusCode = 401; return rs.end("{}"); }
      return rs.end(JSON.stringify({ id: "00000000-0000-0000-0000-000000000001", email }));
    }
    if (rq.url.startsWith("/rest/v1/usuarios")) return rs.end(JSON.stringify([{ precisa_trocar_senha: tipo === "prov" }]));
    rs.statusCode = 404; rs.end("{}");
  });
  await new Promise((r) => hubFalso.listen(0, r));
  process.env.HUB_SUPABASE_URL = `http://127.0.0.1:${hubFalso.address().port}`;
  process.env.HUB_SUPABASE_ANON_KEY = "chave-publica";
  delete process.env.LOGIN_LOCAL;
  srv = await iniciarServidor();
});
after(async () => {
  await pool.query("DELETE FROM usuarios WHERE email LIKE $1", [`%${sufixo}%`]);
  await srv.fechar();
  hubFalso.close();
});

async function criar(nome, status = "ativo") {
  const { rows } = await pool.query(
    "INSERT INTO usuarios (nome, email, senha_hash, papel, status) VALUES ($1, $2, '!hub', 'usuario', $3) RETURNING id, nome, papel",
    [nome, `${nome}-${sufixo}@t.local`, status]);
  return rows[0];
}

test("token válido do Hub vira token do GeoMap", async () => {
  await criar("ana");
  const r = await req(`${srv.url}/auth/hub`, null, { method: "POST", body: { accessToken: `ok-ANA-${sufixo}@t.local` } });
  assert.equal(r.status, 200);
  assert.ok(r.corpo.token);
  assert.equal(r.corpo.usuario.email, `ana-${sufixo}@t.local`);
  const mapas = await req(`${srv.url}/mapas`, r.corpo.token);
  assert.equal(mapas.status, 200);
});

test("token inválido: 401", async () => {
  const r = await req(`${srv.url}/auth/hub`, null, { method: "POST", body: { accessToken: "lixo" } });
  assert.equal(r.status, 401);
});

test("senha provisória: 403 com precisaTrocarSenha", async () => {
  await criar("beto");
  const r = await req(`${srv.url}/auth/hub`, null, { method: "POST", body: { accessToken: `prov-beto-${sufixo}@t.local` } });
  assert.equal(r.status, 403);
  assert.equal(r.corpo.precisaTrocarSenha, true);
});

test("sem cadastro ativo no GeoMap: 403", async () => {
  await criar("caio", "inativo");
  const r = await req(`${srv.url}/auth/hub`, null, { method: "POST", body: { accessToken: `ok-caio-${sufixo}@t.local` } });
  assert.equal(r.status, 403);
  const r2 = await req(`${srv.url}/auth/hub`, null, { method: "POST", body: { accessToken: `ok-ninguem-${sufixo}@t.local` } });
  assert.equal(r2.status, 403);
});

test("login antigo desligado sem LOGIN_LOCAL", async () => {
  const r = await req(`${srv.url}/login`, null, { method: "POST", body: { email: "a@b", senha: "x" } });
  assert.equal(r.status, 410);
});

test("desativado perde o acesso mesmo com token válido", async () => {
  const u = await criar("duda");
  const token = tokenPara(u);
  limparCacheAtivos();
  assert.equal((await req(`${srv.url}/mapas`, token)).status, 200);
  await pool.query("UPDATE usuarios SET status = 'inativo' WHERE id = $1", [u.id]);
  limparCacheAtivos();
  const r = await req(`${srv.url}/mapas`, token);
  assert.equal(r.status, 401);
  assert.equal(r.corpo.erro, "acesso desativado");
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `DATABASE_URL="postgresql://geoportal@localhost:5432/geoportal_dev" PGSSL="" node --test test/login-hub.test.js`
Expected: FAIL (`limparCacheAtivos` não existe / 404 em `/auth/hub`).

- [ ] **Step 3: `backend/src/lib/contaHub.js`**

```js
// Login único (2026-10): o Supabase do Hub Geotech é o dono das contas. Aqui
// só se confere um token de login do Hub — o GeoMap não vê senha nenhuma.
const url = () => (process.env.HUB_SUPABASE_URL || "").replace(/\/$/, "");
const chave = () => process.env.HUB_SUPABASE_ANON_KEY || "";

// { id, email, precisaTrocarSenha } ou null se o token não vale.
export async function lerContaHub(accessToken) {
  if (!url() || !chave() || typeof accessToken !== "string" || !accessToken) return null;
  const h = { apikey: chave(), Authorization: `Bearer ${accessToken}` };
  const r = await fetch(`${url()}/auth/v1/user`, { headers: h });
  if (!r.ok) return null;
  const u = await r.json();
  if (!u?.id || !u?.email) return null;
  const p = await fetch(`${url()}/rest/v1/usuarios?id=eq.${encodeURIComponent(u.id)}&select=precisa_trocar_senha`, {
    headers: { ...h, "Accept-Profile": "hub" },
  });
  const linhas = p.ok ? await p.json() : [];
  return { id: u.id, email: String(u.email).trim().toLowerCase(), precisaTrocarSenha: !!linhas[0]?.precisa_trocar_senha };
}
```

- [ ] **Step 4: Rota e login antigo** — em `backend/src/routes/auth.js`: importar `import { lerContaHub } from "../lib/contaHub.js";`; no começo do handler de `POST /login` e de `PUT /senha` acrescentar:

```js
  if (process.env.LOGIN_LOCAL !== "1") {
    return res.status(410).json({ erro: "o login agora é feito com a conta do Hub Geotech" });
  }
```
e acrescentar a rota:

```js
// Login único: o frontend entra no Supabase do Hub e troca o token dele pelo
// JWT do GeoMap (o resto do GeoMap continua igual). Acesso = cadastro ativo
// aqui, que o Hub mantém por /integracao/contas/usuario.
authRouter.post("/auth/hub", async (req, res) => {
  const conta = await lerContaHub(req.body?.accessToken);
  if (!conta) return res.status(401).json({ erro: "login do Hub inválido ou expirado" });
  if (conta.precisaTrocarSenha) {
    return res.status(403).json({ erro: "defina sua senha antes de continuar", precisaTrocarSenha: true });
  }
  const { rows } = await pool.query("SELECT id, nome, email, status, papel FROM usuarios WHERE lower(email) = $1", [conta.email]);
  const usuario = rows[0];
  if (!usuario || usuario.status !== "ativo") {
    return res.status(403).json({ erro: "sem acesso ao GeoMap — peça ao administrador do Hub" });
  }
  const token = jwt.sign({ sub: usuario.id, email: usuario.email, papel: usuario.papel }, process.env.JWT_SECRET, { expiresIn: "30d" });
  await pool.query("INSERT INTO logs (usuario_id, acao, ip) VALUES ($1, 'login', $2)", [usuario.id, req.ip]);
  res.json({ token, usuario: { id: usuario.id, nome: usuario.nome, email: usuario.email, papel: usuario.papel } });
});
```

- [ ] **Step 5: Status a cada pedido** — substituir `exigirAutenticacao` em `backend/src/middleware/auth.js`:

```js
import jwt from "jsonwebtoken";
import { pool } from "../db/pool.js";

// Quem foi desativado (pelo Hub) perde o acesso em até 60 s, mesmo com o
// token de 30 dias ainda válido.
const CACHE_MS = 60_000;
const ativos = new Map(); // usuarioId -> { ativo, ate }
export function limparCacheAtivos() { ativos.clear(); }
async function usuarioAtivo(id) {
  const c = ativos.get(id);
  if (c && c.ate > Date.now()) return c.ativo;
  const { rows } = await pool.query("SELECT status FROM usuarios WHERE id = $1", [id]);
  const ativo = rows[0]?.status === "ativo";
  ativos.set(id, { ativo, ate: Date.now() + CACHE_MS });
  return ativo;
}

export async function exigirAutenticacao(req, res, next) {
  const cabecalho = req.headers.authorization || "";
  const [tipo, token] = cabecalho.split(" ");
  if (tipo !== "Bearer" || !token) {
    return res.status(401).json({ erro: "token ausente" });
  }
  let payload;
  try {
    payload = jwt.verify(token, process.env.JWT_SECRET);
  } catch {
    return res.status(401).json({ erro: "token inválido ou expirado" });
  }
  if (!(await usuarioAtivo(payload.sub))) {
    return res.status(401).json({ erro: "acesso desativado" });
  }
  req.usuarioId = payload.sub;
  req.usuarioPapel = payload.papel;
  next();
}
```
(`exigirAdmin` continua igual.)

- [ ] **Step 6: `.env.example`** — acrescentar:
```
# Login único (Hub Geotech): o GeoMap aceita o login do Supabase do Hub.
HUB_SUPABASE_URL=https://dpvsivypabmvmrrpgmhc.supabase.co
HUB_SUPABASE_ANON_KEY=sb_publishable_3xv0R1kmhSXkoUh3i4vN0A_Q5oLBbVL
# "1" religa o login antigo (senha do próprio GeoMap) e as telas de usuário — só para voltar atrás.
LOGIN_LOCAL=
```

- [ ] **Step 7: Rodar e ver passar** — comando do Step 2 (Expected: `6 pass`) e depois a suíte inteira `npm test` (com as mesmas variáveis): os testes antigos de `/login` que esperavam 200 devem receber `LOGIN_LOCAL=1` no próprio teste (`process.env.LOGIN_LOCAL = "1"` no `before` do arquivo) — ajustar só esses arquivos.

- [ ] **Step 8: Commit**

```bash
git add backend/src/lib/contaHub.js backend/src/routes/auth.js backend/src/middleware/auth.js backend/.env.example backend/test/
git commit -m "Login unico: GeoMap aceita o login do Hub e confere status a cada pedido"
```

---

### Task 5: Migração — trazer as pessoas do GeoMap para o Hub (e aposentar a sincronização)

**Files:**
- Create: `migracao/trazer_usuarios_geomap.py`
- Create: `tests/contas/test_trazer_usuarios_geomap.py`
- Delete: `ingestao/sincronizar_usuarios.py`, `agendamento/sincronizar_usuarios.cmd`
- Modify: `agendamento/instalar_tarefas.cmd` (remove a linha `schtasks ... "Hub Geotech - Sincronizar usuarios"`), `agendamento/README.md` (seção da sincronização vira "Login único: contas no Hub")

**Interfaces:**
- Consumes: banco do GeoMap (somente leitura, `GEOMAP_DATABASE_URL`/`geomap_env` como hoje), `hub.definir_senha_hash` (service_role), API admin do Auth.
- Produces: `planejar(geomap: dict[email -> {...}], acessos: dict[email -> {...}]) -> list[dict]` (pura, testada) e o script com `--simular`.

- [ ] **Step 1: Teste da função pura (falha)** — `tests/contas/test_trazer_usuarios_geomap.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'migracao'))
from trazer_usuarios_geomap import planejar  # noqa: E402

G = {
    'ana@x.com': {'nome': 'Ana', 'hash': '$2b$10$' + 'a' * 53, 'ativo': True, 'admin': True, 'grupos': [1, 2], 'senha_provisoria': False},
    'beto@x.com': {'nome': 'Beto', 'hash': '$2b$10$' + 'b' * 53, 'ativo': True, 'admin': False, 'grupos': [], 'senha_provisoria': True},
    'caio@x.com': {'nome': 'Caio', 'hash': '$2b$10$' + 'c' * 53, 'ativo': False, 'admin': False, 'grupos': [3], 'senha_provisoria': False},
}
A = {'ana@x.com': {'nome': 'Ana Paula', 'papel': 'editor', 'admin': True, 'modulos': ['plantio']}}


def test_mantem_campos_do_hub_e_traz_os_do_geomap():
    p = {x['email']: x for x in planejar(G, A)}
    assert p['ana@x.com']['acesso'] == {'email': 'ana@x.com', 'nome': 'Ana Paula', 'papel': 'editor', 'admin': True,
                                        'modulos': ['plantio'], 'geomap_ativo': True, 'geomap_admin': True, 'geomap_grupos': [1, 2]}
    assert p['ana@x.com']['copiar_hash'] is True and p['ana@x.com']['precisa_trocar_senha'] is False


def test_senha_provisoria_do_geomap_nao_e_copiada():
    beto = next(x for x in planejar(G, A) if x['email'] == 'beto@x.com')
    assert beto['copiar_hash'] is False and beto['precisa_trocar_senha'] is True
    assert beto['acesso']['papel'] == 'leitura' and beto['acesso']['modulos'] == []


def test_inativo_no_geomap_fica_sem_geomap_e_bloqueado():
    caio = next(x for x in planejar(G, A) if x['email'] == 'caio@x.com')
    assert caio['acesso']['geomap_ativo'] is False and caio['acesso']['geomap_grupos'] == []
    assert caio['bloquear'] is True


def test_acesso_do_hub_sem_geomap_continua():
    p = planejar(G, {**A, 'so-hub@x.com': {'nome': 'Só Hub', 'papel': 'leitura', 'admin': False, 'modulos': ['preparo']}})
    so = next(x for x in p if x['email'] == 'so-hub@x.com')
    assert so['acesso']['geomap_ativo'] is False and so['copiar_hash'] is False and so['bloquear'] is False
```

- [ ] **Step 2: Rodar e ver falhar** — `python -m pytest tests/contas/test_trazer_usuarios_geomap.py -q` → `ModuleNotFoundError`.

- [ ] **Step 3: Script** — `migracao/trazer_usuarios_geomap.py`:

```python
"""Virada do login único (uma vez só): leva as pessoas do GeoMap para o Hub.

Para cada pessoa do GeoMap: conta no Hub com o MESMO hash de senha (ninguém
troca de senha), hub.usuarios e hub.acessos com os campos do GeoMap (ativo,
admin, grupos), mantendo os campos do Hub de quem já tinha acesso. Quem ainda
está com a senha provisória fixa do GeoMap não recebe esse hash: fica com
"precisa trocar senha" e o admin entrega uma provisória do Hub ("Redefinir
senha" na tela Usuários) — o script lista essas pessoas.

Lê o banco do GeoMap só em modo leitura. Nunca imprime hash.
Uso:  python migracao/trazer_usuarios_geomap.py [--simular]
"""
import argparse
import os
import ssl
import sys
import urllib.parse

import pg8000.native
import requests
import truststore

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ingestao'))
from comum import Hub, carregar_config, carregar_env  # noqa: E402

BLOQUEIO = '876000h'


def url_banco_geomap():
    url = carregar_env().get('GEOMAP_DATABASE_URL')
    if url:
        return url
    return next(linha.split('=', 1)[1].strip().strip('"').strip("'")
                for linha in open(carregar_config()['geomap_env'], encoding='utf-8')
                if linha.startswith('DATABASE_URL='))


def ler_geomap():
    u = urllib.parse.urlparse(url_banco_geomap())
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    con = pg8000.native.Connection(
        user=urllib.parse.unquote(u.username), password=urllib.parse.unquote(u.password or ''),
        host=u.hostname, port=u.port or 5432, database=u.path.lstrip('/'), ssl_context=ctx, timeout=30)
    try:
        con.run('set transaction read only')
        linhas = con.run("""select lower(u.email), u.nome, u.senha_hash, u.status, u.papel, u.precisa_trocar_senha,
                                   coalesce(array_agg(ug.grupo_id) filter (where ug.grupo_id is not null), '{}')
                              from usuarios u left join usuarios_grupos ug on ug.usuario_id = u.id
                             group by u.id""")
    finally:
        con.close()
    return {e: {'nome': n, 'hash': h, 'ativo': s == 'ativo', 'admin': p == 'admin',
                'senha_provisoria': bool(prov), 'grupos': sorted(g)}
            for e, n, h, s, p, prov, g in linhas}


def planejar(geomap, acessos):
    """Lista de ações por e-mail (pura, sem rede)."""
    plano = []
    for email in sorted(set(geomap) | set(acessos)):
        g, a = geomap.get(email), acessos.get(email)
        gm_ativo = bool(g and g['ativo'])
        acesso = {
            'email': email,
            'nome': (a or {}).get('nome') or g['nome'],
            'papel': (a or {}).get('papel', 'leitura'),
            'admin': bool((a or {}).get('admin')),
            'modulos': list((a or {}).get('modulos') or []),
            'geomap_ativo': gm_ativo,
            'geomap_admin': bool(g and g['ativo'] and g['admin']),
            'geomap_grupos': list(g['grupos']) if gm_ativo else [],
        }
        tem_acesso = bool(acesso['modulos']) or gm_ativo or acesso['admin']
        plano.append({
            'email': email, 'acesso': acesso,
            'copiar_hash': bool(g and not g['senha_provisoria']),
            'hash': g['hash'] if g else None,
            'precisa_trocar_senha': bool(g and g['senha_provisoria']),
            'bloquear': not tem_acesso,
        })
    return plano


class AuthAdmin:
    def __init__(self):
        env = carregar_env()
        self.url = env['SUPABASE_URL'].rstrip('/') + '/auth/v1/admin/users'
        k = env['SUPABASE_SERVICE_ROLE_KEY']
        self.headers = {'apikey': k, 'Authorization': f'Bearer {k}', 'Content-Type': 'application/json'}

    def _ok(self, r):
        if not r.ok:
            raise RuntimeError(f'Auth: HTTP {r.status_code} {r.text[:300]}')
        return r.json()

    def por_email(self):
        contas, pagina = {}, 1
        while True:
            lote = self._ok(requests.get(self.url, params={'page': pagina, 'per_page': 200}, headers=self.headers, timeout=60))['users']
            contas.update({c['email'].lower(): c for c in lote})
            if len(lote) < 200:
                return contas
            pagina += 1

    def criar(self, email, nome):
        return self._ok(requests.post(self.url, headers=self.headers, timeout=60,
                                      json={'email': email, 'email_confirm': True, 'user_metadata': {'nome': nome}}))['id']

    def bloquear(self, id_, sim):
        self._ok(requests.put(f'{self.url}/{id_}', headers=self.headers, timeout=60,
                              json={'ban_duration': BLOQUEIO if sim else 'none'}))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true')
    args = ap.parse_args()
    hub, auth = Hub(), AuthAdmin()
    acessos = {a['email']: a for a in hub.selecionar('acessos', 'email,nome,papel,admin,modulos', {'order': 'email'})}
    plano, contas = planejar(ler_geomap(), acessos), auth.por_email()
    pendentes = []
    for p in plano:
        a = p['acesso']
        print(f"  {p['email']}: {'atualizar' if p['email'] in contas else 'criar'} | Hub {a['papel']}"
              f"{' + admin' if a['admin'] else ''} {','.join(a['modulos']) or '-'} | GeoMap "
              f"{('admin ' if a['geomap_admin'] else '') + 'grupos ' + str(a['geomap_grupos']) if a['geomap_ativo'] else 'não'}"
              f"{' | BLOQUEADA' if p['bloquear'] else ''}{' | precisa senha provisória do Hub' if p['precisa_trocar_senha'] else ''}")
        if p['precisa_trocar_senha']:
            pendentes.append(p['email'])
        if args.simular:
            continue
        conta = contas.get(p['email'])
        id_ = conta['id'] if conta else auth.criar(p['email'], a['nome'])
        if p['copiar_hash']:
            hub.rpc('definir_senha_hash', {'p_usuario': id_, 'p_hash': p['hash']})
        hub.upsert('acessos', [a], 'email')
        hub.upsert('usuarios', [{'id': id_, 'nome': a['nome'], 'papel': a['papel'], 'admin': a['admin'],
                                 'precisa_trocar_senha': p['precisa_trocar_senha']}], 'id')
        requests.delete(f'{hub.url}/usuario_modulos', params={'usuario_id': f'eq.{id_}'}, headers=hub.headers, timeout=60).raise_for_status()
        if a['modulos']:
            hub.upsert('usuario_modulos', [{'usuario_id': id_, 'modulo_id': m} for m in a['modulos']], 'usuario_id,modulo_id')
        if bool(conta and conta.get('banned_until')) != p['bloquear'] or not conta:
            auth.bloquear(id_, p['bloquear'])
    if pendentes:
        print('\nAinda com a senha provisória do GeoMap — use "Redefinir senha" no Hub para cada um:')
        for e in pendentes:
            print('  ', e)
    print('Simulação: nada foi gravado.' if args.simular else f'{len(plano)} pessoa(s) no Hub.')


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Rodar e ver passar** — `python -m pytest tests/contas/test_trazer_usuarios_geomap.py -q` → `4 passed`. Depois `python migracao/trazer_usuarios_geomap.py --simular` (só leitura): conferir que lista as 13 pessoas do GeoMap e os 8 acessos atuais, com os mesmos módulos de hoje.

- [ ] **Step 5: Aposentar a sincronização** — `git rm ingestao/sincronizar_usuarios.py agendamento/sincronizar_usuarios.cmd`; apagar a linha 7 de `agendamento/instalar_tarefas.cmd` (`schtasks /create ... "Hub Geotech - Sincronizar usuarios" ...`); no `agendamento/README.md`, trocar a seção da sincronização por:
```markdown
### Contas (login único, desde 10/2026)
As contas e senhas são do Hub (tela Usuários). Não há mais sincronização com o GeoMap.
Na virada, remover a tarefa antiga do servidor:
`schtasks /delete /tn "Hub Geotech - Sincronizar usuarios" /f`
```

- [ ] **Step 6: Commit**

```bash
git add migracao/trazer_usuarios_geomap.py tests/contas/test_trazer_usuarios_geomap.py agendamento/
git commit -m "Login unico: migracao das pessoas do GeoMap para o Hub; sincronizacao aposentada"
```

---

### Task 6: GeoMap frontend — entrar com o Hub

**Files (worktree `geomap-login-hub`):**
- Create: `frontend/src/lib/hub.js`
- Modify: `frontend/src/lib/api.js`, `frontend/src/hooks/useFormularioLogin.js`, `frontend/src/pages/DefinirSenha.jsx`, `frontend/src/context/AuthContext.jsx`, `frontend/src/App.jsx`, `frontend/src/pages/AdminUsuarios.jsx`, `frontend/package.json`, `frontend/.env.example`, `.github/workflows/deploy-frontend.yml`

**Interfaces:**
- Consumes: `POST /auth/hub` (Task 4), `hub.senha_definida()` (Task 1).
- Produces: `hub` (cliente supabase-js do Hub) e `entrarComHub(accessToken)` em `lib/api.js`.

- [ ] **Step 1: Dependência e cliente** — `cd frontend && npm install @supabase/supabase-js@2`. `frontend/src/lib/hub.js`:

```js
import { createClient } from "@supabase/supabase-js";

// Login único (2026-10): as contas são do Supabase do Hub Geotech. Hub e
// GeoMap ficam no mesmo endereço (lmalerbo.github.io), então a sessão salva
// é a mesma: quem já entrou no Hub entra direto aqui. Chave pública.
const URL_HUB = import.meta.env.VITE_HUB_SUPABASE_URL || "https://dpvsivypabmvmrrpgmhc.supabase.co";
const CHAVE_HUB = import.meta.env.VITE_HUB_SUPABASE_ANON_KEY || "sb_publishable_3xv0R1kmhSXkoUh3i4vN0A_Q5oLBbVL";
export const hub = createClient(URL_HUB, CHAVE_HUB);
```

- [ ] **Step 2: API** — em `frontend/src/lib/api.js`, dentro de `tratarResposta`, depois de `erro.status = resp.status;` acrescentar `erro.precisaTrocarSenha = corpo.precisaTrocarSenha === true;`; trocar `login`/`definirSenha` por:

```js
// Login único: troca o token do Hub pelo token do GeoMap.
export async function entrarComHub(accessToken) {
  const resp = await fetch(`${API_URL}/auth/hub`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accessToken }),
  });
  await tratarResposta(resp);
  return resp.json();
}
```

- [ ] **Step 3: Login** — `frontend/src/hooks/useFormularioLogin.js` inteiro:

```js
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { entrarComHub } from "../lib/api.js";
import { hub } from "../lib/hub.js";
import { useAuth } from "../context/AuthContext.jsx";

// Login único: entra no Supabase do Hub e troca o token pelo do GeoMap.
// Compartilhado entre Login e PrimeiroAcesso (só muda a moldura).
export function useFormularioLogin() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const { entrar } = useAuth();
  const navigate = useNavigate();

  async function concluir(accessToken) {
    try {
      const { token, usuario } = await entrarComHub(accessToken);
      entrar(token, usuario, false);
      navigate("/inicio");
    } catch (err) {
      if (err.precisaTrocarSenha) return navigate("/definir-senha");
      throw err;
    }
  }

  // Já entrou no Hub neste navegador: entra direto.
  useEffect(() => {
    hub.auth.getSession().then(({ data }) => {
      if (data.session) concluir(data.session.access_token).catch(() => {});
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      const { data, error } = await hub.auth.signInWithPassword({ email: email.trim(), password: senha });
      if (error) {
        throw new Error(/banned/i.test(error.message)
          ? "Acesso bloqueado. Fale com o administrador do Hub."
          : "E-mail ou senha incorretos.");
      }
      await concluir(data.session.access_token);
    } catch (err) {
      setErro(err instanceof TypeError
        ? "Sem conexão com o servidor. Verifique sua internet e tente de novo."
        : err.message);
    } finally {
      setCarregando(false);
    }
  }

  return { email, setEmail, senha, setSenha, erro, carregando, handleSubmit };
}
```

- [ ] **Step 4: Definir senha** — em `frontend/src/pages/DefinirSenha.jsx`: trocar os imports de `definirSenha`/`useAuth` por `import { entrarComHub } from "../lib/api.js"; import { hub } from "../lib/hub.js"; import { useAuth } from "../context/AuthContext.jsx";`, usar `const { entrar } = useAuth();`, `minLength={8}` nos dois inputs, e o `handleSubmit`:

```js
  async function handleSubmit(e) {
    e.preventDefault();
    setErro(null);
    if (novaSenha !== confirmacao) { setErro("As senhas não coincidem."); return; }
    setEnviando(true);
    try {
      const { data } = await hub.auth.getSession();
      if (!data.session) { navigate("/login", { replace: true }); return; }
      const { error } = await hub.auth.updateUser({ password: novaSenha });
      if (error) throw new Error(error.message);
      const r = await hub.schema("hub").rpc("senha_definida");
      if (r.error) throw new Error(r.error.message);
      const { data: nova } = await hub.auth.getSession();
      const { token, usuario } = await entrarComHub(nova.session.access_token);
      entrar(token, usuario, false);
      navigate("/inicio", { replace: true });
    } catch (err) {
      setErro(err.message);
    } finally {
      setEnviando(false);
    }
  }
```
Texto do parágrafo: "Sua senha ainda é a provisória. Escolha uma senha própria (mínimo 8 caracteres) — ela vale para o Hub e o GeoMap."

- [ ] **Step 5: Rotas e sair** — em `frontend/src/App.jsx`, `RotaDefinirSenha` passa a liberar sempre (a própria página manda para /login sem sessão do Hub):

```jsx
function RotaDefinirSenha({ children }) {
  return children;
}
```
Em `frontend/src/context/AuthContext.jsx`: `import { hub } from "../lib/hub.js";` e no `sair`: `hub.auth.signOut().catch(() => {});` antes de `localStorage.removeItem(...)`.

- [ ] **Step 6: Admin de usuários só leitura** — em `frontend/src/pages/AdminUsuarios.jsx`:
  - constante no topo: `const CONTAS_NO_HUB = true; // login único: contas e grupos de cada pessoa são geridos no Hub`
  - envolver o botão "+ Novo usuário" (linhas 306–310 em origin/master) em `{!CONTAS_NO_HUB && aba === "usuarios" && (...)}`;
  - logo abaixo do `</header>`: `{CONTAS_NO_HUB && <p className="adm-aviso-linha">Contas, senhas, papéis e grupos de cada pessoa são gerenciados no Hub Geotech (tela Usuários). Aqui ficam os grupos, os mapas e o vínculo de piloto.</p>}`;
  - no painel da pessoa, envolver em `{!CONTAS_NO_HUB && (...)}`: o campo Departamento, o bloco Papel, o bloco Grupos e a barra "Alterações não salvas" (linhas 472–515), o bloco "Senha" (570–579) e o bloco Desativar/Excluir (581–597); no lugar dos três primeiros, mostrar `{CONTAS_NO_HUB && <p className="adm-suave">{usuario.papel === "admin" ? "Administrador" : "Usuário"} · grupos: {(usuario.grupoIds || []).length}</p>}`. O bloco "Piloto no DroneManagement" continua.

- [ ] **Step 7: Variáveis** — `frontend/.env.example` acrescentar `VITE_HUB_SUPABASE_URL=https://dpvsivypabmvmrrpgmhc.supabase.co` e `VITE_HUB_SUPABASE_ANON_KEY=sb_publishable_3xv0R1kmhSXkoUh3i4vN0A_Q5oLBbVL`; em `.github/workflows/deploy-frontend.yml`, no `env:` do build, acrescentar as mesmas duas linhas (valores literais: são públicos).

- [ ] **Step 8: Verificar** — `npm run lint && npm run build && npm run test:unit` sem erro. Teste manual com Playwright contra backend local (Task 4) + frontend `npm run dev`, usando `HUB_SUPABASE_URL` real e a conta de teste do Hub cadastrada no Postgres local do GeoMap (`INSERT INTO usuarios (nome,email,senha_hash,papel) VALUES ('Teste','<email da conta de teste>','!hub','usuario')`): login entra e mostra os mapas; sair volta ao login; com `precisa_trocar_senha` ligado na conta de teste (e desligado no fim), o login leva a "Defina sua senha" — **sem** trocar a senha real da conta de teste: só conferir que a tela aparece.

- [ ] **Step 9: Commit**

```bash
git add frontend/ .github/workflows/deploy-frontend.yml
git commit -m "Login unico: GeoMap entra com a conta do Hub; usuarios do admin so leitura"
```

---

### Task 7: App do Hub — senha provisória, trocar senha e acesso ao GeoMap na tela Usuários

**Files:**
- Modify: `app/index.html`
- Create: `tests/app/teste_usuarios_tela.py`

**Interfaces:**
- Consumes: função `contas` (Task 3), `hub.acessos_situacao()`/`hub.senha_definida()` (Task 1).
- Produces: telas; funções JS `chamarContas(corpo)`, `mostrarSenhaProvisoria(email, senha)`, `abrirTrocaSenha(obrigatoria)`, `definirSenha()`.

- [ ] **Step 1: Tela "Defina sua senha"** — logo depois do `<div id="login" ...>...</div>` (fim do bloco do login, antes de `<div class="modal-fundo off" id="modal-envio">`):

```html
<div id="tela-senha" class="scr off">
  <div class="deco"><div class="dc a"></div><div class="dc b"></div></div>
  <div class="lcard">
    <div class="brand"><div class="bmark">HG</div><span class="bname">hub geotech</span></div>
    <h1 class="ltitle" id="senha-titulo">Defina sua senha</h1>
    <p class="lsub" id="senha-sub">Sua senha é provisória. Escolha uma senha própria — ela vale para o Hub e o GeoMap.</p>
    <div class="lform">
      <div class="tbx"><input type="password" id="s-nova" placeholder=" " autocomplete="new-password"><label for="s-nova">Nova senha (mínimo 8 caracteres)</label></div>
      <div class="tbx"><input type="password" id="s-conf" placeholder=" " autocomplete="new-password" onkeydown="if(event.key==='Enter')definirSenha()"><label for="s-conf">Repita a nova senha</label></div>
      <div class="login-erro" id="senha-erro"></div>
      <button class="btn-in" id="btn-senha" onclick="definirSenha()">Salvar senha</button>
      <button class="btn-retro" id="btn-senha-cancelar" style="display:none" onclick="fecharTrocaSenha()">Cancelar</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Fluxo** — em `carregarDados`, trocar o select de usuários para `'id,nome,papel,admin,precisa_trocar_senha,usuario_modulos(modulo_id)'` e, onde `USUARIOS` é montado a partir dele, levar `precisa_trocar_senha` para cada objeto (`precisaTrocarSenha: u.precisa_trocar_senha`). Em `abrirHub`, depois de `if(!EU)return falhar(...)`:

```js
  if(EU.precisaTrocarSenha){car.classList.add('off');document.getElementById('login').classList.add('off');abrirTrocaSenha(true);return;}
```
e no fim de `abrirHub` (depois de mostrar o hub), abrir em Ferramentas quem não tem módulo do Hub:
```js
  if(!['plantio','preparo','colheita','drone'].some(m=>EU.perms[m]))trocar('geotech',document.querySelector(`.ni[onclick*="'geotech'"]`));
```
Funções novas (perto de `sair()`):
```js
// Senha: obrigatória depois de senha provisória (criada/redefinida pelo admin)
// ou pedida pela própria pessoa no botão "Trocar senha" da barra lateral.
let trocaObrigatoria=false;
function abrirTrocaSenha(obrigatoria){
  trocaObrigatoria=obrigatoria;
  document.getElementById('senha-titulo').textContent=obrigatoria?'Defina sua senha':'Trocar senha';
  document.getElementById('senha-sub').textContent=obrigatoria
    ?'Sua senha é provisória. Escolha uma senha própria — ela vale para o Hub e o GeoMap.'
    :'A senha nova vale para o Hub e o GeoMap.';
  document.getElementById('btn-senha-cancelar').style.display=obrigatoria?'none':'';
  ['s-nova','s-conf'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('senha-erro').textContent='';
  document.getElementById('tela-senha').classList.remove('off');
  document.getElementById('s-nova').focus();
}
function fecharTrocaSenha(){document.getElementById('tela-senha').classList.add('off');}
async function definirSenha(){
  const nova=document.getElementById('s-nova').value,conf=document.getElementById('s-conf').value;
  const erro=document.getElementById('senha-erro'),btn=document.getElementById('btn-senha');
  erro.textContent='';
  if(nova.length<8){erro.textContent='A senha precisa ter pelo menos 8 caracteres.';return;}
  if(nova!==conf){erro.textContent='As duas senhas não são iguais.';return;}
  btn.disabled=true;btn.textContent='Salvando…';
  try{
    const {error}=await sb.auth.updateUser({password:nova});
    if(error)throw error;
    const r=await sb.rpc('senha_definida');if(r.error)throw r.error;
  }catch(e){erro.textContent='Não foi possível salvar: '+(e.message||e);return;}
  finally{btn.disabled=false;btn.textContent='Salvar senha';}
  fecharTrocaSenha();
  if(trocaObrigatoria){EU.precisaTrocarSenha=false;await abrirHub();}
  else showToast('Senha trocada');
}
```
Na barra lateral, ao lado do botão de sair (`<button class="btn-out" onclick="sair()">`), acrescentar `<button class="btn-out" title="Trocar senha" onclick="abrirTrocaSenha(false)"><span class="ico">key</span></button>`. Na tela de login, trocar "Use o mesmo e-mail e senha do GeoMap." por "A mesma conta vale para o Hub e o GeoMap." e a mensagem de `banned` em `entrar()` por `'Acesso bloqueado. Fale com o administrador do Hub.'`.

- [ ] **Step 3: Chamada à função `contas`** (perto de `carregarAcessos`):

```js
// Ações de conta (criar, senha provisória, bloquear, GeoMap) passam pela função
// "contas" do Supabase — a única com a chave de serviço; aqui vai o login do admin.
async function chamarContas(corpo){
  const {data,error}=await sb.functions.invoke('contas',{body:corpo});
  if(error){let msg=error.message;try{msg=(await error.context.json()).erro||msg;}catch(_){}throw new Error(msg);}
  return data;
}
let GRUPOS_GM=null;
async function gruposGeomap(){
  if(!GRUPOS_GM){try{GRUPOS_GM=await chamarContas({acao:'grupos_geomap'});}catch(e){GRUPOS_GM=[];showToast('Grupos do GeoMap indisponíveis: '+e.message);}}
  return GRUPOS_GM;
}
function mostrarSenhaProvisoria(email,senha){
  confirmar(`Senha provisória de ${email}:<br><code class="senha-prov">${esc(senha)}</code><br>Passe para a pessoa: ela troca no primeiro acesso. Esta senha não aparece de novo.`,
    {titulo:'Senha provisória',ok:'Copiar e fechar',html:true}).then(ok=>{if(ok)navigator.clipboard?.writeText(senha);});
}
```
(Se `confirmar()` não aceitar `html:true`, acrescentar essa opção a ele: quando `html` for verdadeiro, usar `innerHTML` com o texto já escapado como acima.)

- [ ] **Step 4: Formulário com GeoMap** — em `formUsr`, depois do `<label class="usr-admin">...`:

```js
      <div class="usr-sec">GeoMap</div>
      <label class="usr-admin"><input type="checkbox" id="u-gm" ${a.geomap_ativo?'checked':''} onchange="document.getElementById('u-gm-det').style.display=this.checked?'':'none'"> Acessa o GeoMap</label>
      <div id="u-gm-det" style="${a.geomap_ativo?'':'display:none'}">
        <label class="usr-admin"><input type="checkbox" id="u-gm-admin" ${a.geomap_admin?'checked':''}> Administrador do GeoMap <span>gerencia mapas e camadas</span></label>
        <label>Grupos<div class="usr-mods" id="u-gm-grupos"><span class="usr-sit espera">Carregando grupos…</span></div>
          <span>Os grupos e os mapas de cada grupo são definidos no GeoMap.</span></label>
      </div>
```
botões (no `modal-botoes` do form, antes do "Remover acesso"): `${novo?'':`<button class="btn-retro" onclick="redefinirSenhaUsr('${esc(a.email)}')">Redefinir senha</button>`}`; nota final trocada por `<div class="usr-nota"><span class="ico">info</span>O acesso vale na hora, para o Hub e o GeoMap. Conta nova recebe uma senha provisória, que a pessoa troca no primeiro acesso.</div>`; no e-mail, o `<span>o mesmo do GeoMap</span>` vira `<span>usado para entrar</span>`.

Depois de `mostrarPainelUsr(...)` em `selUsr` e `novoUsr`, chamar `preencherGruposGm(a.geomap_grupos||[])`:
```js
async function preencherGruposGm(marcados){
  const gs=await gruposGeomap();
  const el=document.getElementById('u-gm-grupos');if(!el)return;
  el.innerHTML=gs.length?gs.map(g=>`<label class="usr-mod"><input type="checkbox" value="${g.id}" ${marcados.includes(g.id)?'checked':''}>${esc(g.nome)}</label>`).join('')
    :'<span class="usr-sit erro">Não foi possível ler os grupos do GeoMap.</span>';
}
```
`situacaoAcesso` ganha, antes do `return['ok',...]`: `if(a.precisa_trocar_senha)return['espera','Com senha provisória (ainda não trocou)'];` e o primeiro `if` passa a `if(!a.conta_criada)return['espera','Sem conta'];`.

- [ ] **Step 5: Salvar, redefinir e remover pela função** — `salvarUsr`, `removerUsr` e o novo `redefinirSenhaUsr`:

```js
async function salvarUsr(novo){
  const erro=document.getElementById('u-erro');erro.textContent='';
  const email=document.getElementById('u-email').value.trim().toLowerCase();
  const nome=document.getElementById('u-nome').value.trim();
  const papel=document.querySelector('#u-papel .on')?.dataset.v||'leitura';
  const modulos=[...document.querySelectorAll('#u-mods input:checked')].map(i=>i.value);
  const admin=document.getElementById('u-admin').checked;
  const geomap_ativo=document.getElementById('u-gm').checked;
  const geomap_admin=geomap_ativo&&document.getElementById('u-gm-admin').checked;
  const geomap_grupos=geomap_ativo?[...document.querySelectorAll('#u-gm-grupos input:checked')].map(i=>Number(i.value)):[];
  if(!/^[^@\s]+@[^@\s]+$/.test(email)){erro.textContent='Informe um e-mail válido.';return;}
  if(!nome){erro.textContent='Informe o nome.';return;}
  if(novo&&ACESSOS.some(a=>a.email===email)){erro.textContent='Esse e-mail já tem acesso.';return;}
  let r;
  try{r=await chamarContas({acao:'salvar',email,nome,papel,admin,modulos,geomap_ativo,geomap_admin,geomap_grupos});}
  catch(e){erro.textContent=e.message;return;}
  selEmail=email;await carregarAcessos();
  if(r.avisoGeomap)showToast('Salvo no Hub, mas o GeoMap não respondeu ('+r.avisoGeomap+'). Salve de novo em instantes.');
  else showToast(novo?'Acesso adicionado':'Acesso salvo');
  if(r.senhaProvisoria)mostrarSenhaProvisoria(email,r.senhaProvisoria);
}
async function redefinirSenhaUsr(email){
  if(!await confirmar(`${email} recebe uma senha provisória nova e precisa trocá-la no próximo acesso. A senha atual deixa de valer.`,{titulo:'Redefinir senha',ok:'Redefinir'}))return;
  try{const r=await chamarContas({acao:'redefinir_senha',email});await carregarAcessos();mostrarSenhaProvisoria(email,r.senhaProvisoria);}
  catch(e){showToast('Não foi possível: '+e.message);}
}
async function removerUsr(email){
  if(!await confirmar(`${email} deixa de entrar no Hub e no GeoMap na hora (a conta é bloqueada; o histórico continua).`,{titulo:'Remover acesso',ok:'Remover',perigo:true}))return;
  let r;
  try{r=await chamarContas({acao:'remover',email});}catch(e){showToast('Não foi possível: '+e.message);return;}
  showToast(r.avisoGeomap?'Removido do Hub; o GeoMap não respondeu — remova de novo em instantes.':'Acesso removido');
  selEmail=null;
  document.getElementById('dpanel-u').style.display='none';document.getElementById('dempty-u').style.display='';
  await carregarAcessos();
}
```

- [ ] **Step 6: Ferramentas** — em `rGeotech`, filtrar: `const fs=ferramentas().filter(f=>f.id!=='geomap'||EU?.admin||EU?.geomap);` e, em `carregarDados`, depois de montar `EU`, ler o próprio acesso ao GeoMap: `EU.geomap=!!(await sb.rpc('meu_acesso_geomap')).data;` — **e** acrescentar à migração da Task 1 (antes do `commit;`):
```sql
create or replace function hub.meu_acesso_geomap()
returns boolean language sql stable security definer set search_path = hub, auth as $$
  select coalesce((select a.geomap_ativo from hub.acessos a join auth.users u on lower(u.email) = a.email where u.id = auth.uid()), false);
$$;
revoke all on function hub.meu_acesso_geomap() from public, anon;
grant execute on function hub.meu_acesso_geomap() to authenticated;
```
com o teste correspondente em `tests/contas/test_login_unico_sql.py`:
```python
def test_meu_acesso_geomap(banco, pessoa, como):
    adm = pessoa('adm5@x.com', admin=True)
    uid = pessoa('gm@x.com')
    assert como(uid, 'select hub.meu_acesso_geomap()') == [(False,)]
    salvar(como, adm, 'gm@x.com', gm_ativo=True)
    assert como(uid, 'select hub.meu_acesso_geomap()') == [(True,)]
```

- [ ] **Step 7: Teste da tela** — `tests/app/teste_usuarios_tela.py` (mesmo padrão de `tests/app/teste_drone_tela.py`: servidor local da pasta `app/`, conta de teste via `HUB_CONTA_TESTE`, promovida a admin só durante o teste e restaurada no `finally`, acesso `tela-usuarios@hub.local` apagado no fim junto com a conta Auth criada):
  1. Usuários → "Novo acesso", preenche `tela-usuarios@hub.local`, marca Plantio, **não** marca GeoMap, Adicionar → aparece a janela "Senha provisória" com 10 caracteres; o card mostra "Com senha provisória".
  2. Abre o mesmo acesso: a seção GeoMap lista os grupos reais (mais de 0 checkboxes em `#u-gm-grupos`).
  3. "Redefinir senha" → nova janela com outra senha.
  4. Entrar (outra aba) com `tela-usuarios@hub.local` + senha provisória → aparece "Defina sua senha"; senha curta → erro "pelo menos 8"; senhas diferentes → erro; **não** salvar (fechar a aba).
  5. Remover acesso → toast "Acesso removido"; o login com a senha provisória passa a dar "Acesso bloqueado".
  6. Sem erros de JavaScript.
  Run: `HUB_CONTA_TESTE=<scratchpad>/conta-teste.json python tests/app/teste_usuarios_tela.py` → `FALHAS: nenhuma`.
  Rodar também `teste_app.py`, `teste_admin.py`, `teste_colheita.py` (scratchpad) e `tests/app/teste_drone_tela.py` — tudo passando.

- [ ] **Step 8: Commit**

```bash
git add app/index.html tests/app/teste_usuarios_tela.py supabase/migrations/20261012090000_login_unico.sql tests/contas/test_login_unico_sql.py
git commit -m "Login unico: senha provisoria, trocar senha e acesso ao GeoMap na tela Usuarios"
```

---

### Task 8: Runbook e virada

**Files:**
- Create: `docs/runbook-login-unico.md`

- [ ] **Step 1: Escrever o runbook** — `docs/runbook-login-unico.md`:

```markdown
# Virada do login único (Hub + GeoMap)

Duração: ~1 h, fora do horário de pico. Ninguém troca de senha.

## Antes (pode ser na véspera)
1. SQL Editor do Hub (nova query): `supabase/migrations/20261012090000_login_unico.sql`.
2. Função: `supabase functions deploy contas --project-ref dpvsivypabmvmrrpgmhc` e os dois `supabase secrets set` (GEOMAP_URL, HUB_INTEGRACAO_TOKEN — digitado pelo Leo).
3. Render do GeoMap: variáveis `HUB_SUPABASE_URL` e `HUB_SUPABASE_ANON_KEY` (valores do backend/.env.example). **Não** publicar o código ainda.
4. `python migracao/trazer_usuarios_geomap.py --simular` e conferir a lista com o Leo.

## Virada
5. Publicar o backend do GeoMap (merge de `feat/login-hub` em `master` → deploy no Render). A partir daqui o login antigo do GeoMap responde 410 — seguir direto para os passos 6–8.
6. `python migracao/trazer_usuarios_geomap.py` (de verdade).
7. Publicar o frontend do GeoMap (workflow deploy-frontend) e o app do Hub (`git push origin colheita:main`).
8. Servidor Geo: `cd $HOME\hub-geotech; git pull; schtasks /delete /tn "Hub Geotech - Sincronizar usuarios" /f`.

## Conferência
- `python -m pytest tests/contas -m banco -q` (função) e `tests/app/teste_usuarios_tela.py` contra o site publicado.
- Leo entra no GeoMap com a senha de sempre e vê os mesmos mapas; entra no Hub direto.
- Tela Usuários: as 13 pessoas do GeoMap aparecem com o GeoMap marcado e os grupos certos.
- Para cada pessoa listada como "precisa senha provisória do Hub": Redefinir senha e entregar.

## Voltar atrás
- GeoMap: `LOGIN_LOCAL=1` no Render (religa login e telas antigas; os hashes antigos continuam lá) e reverter o commit do frontend.
- Hub: `agendamento/instalar_tarefas.cmd` de uma versão anterior recria a sincronização; as colunas novas não atrapalham.
```

- [ ] **Step 2: Commit e PR do GeoMap**

```bash
git add docs/runbook-login-unico.md && git commit -m "Login unico: runbook da virada"
cd C:/Users/lmalerbo/Documents/GitHub/geomap-login-hub && git push -u origin feat/login-hub
```
A virada em si (passos 1–8 do runbook) só acontece com o Leo acompanhando.
