-- O mínimo do Supabase + tabelas do Hub para rodar as migrações dos Mapas de aplicação num Postgres local:
-- papéis, auth.users, auth.uid() (lido de request.jwt.claim.sub, como no Supabase) e as tabelas que as
-- migrações dos corretivos referenciam. Sem PostGIS: corretivo_talhoes_fazenda só é criada, não executada.
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin; end if;
end $$;
create schema auth;
create table auth.users (id uuid primary key default gen_random_uuid(), email text);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
create schema hub;
grant usage on schema hub, auth to anon, authenticated, service_role;
create table hub.modulos (id text primary key, nome text not null, ordem int not null, ativo boolean not null default true);
create table hub.usuarios (id uuid primary key references auth.users (id) on delete cascade, nome text not null,
  admin boolean not null default false);
create table hub.usuario_modulos (usuario_id uuid not null references hub.usuarios (id) on delete cascade,
  modulo_id text not null references hub.modulos (id), primary key (usuario_id, modulo_id));
create table hub.log_auditoria (id bigint generated always as identity primary key, modulo_id text,
  entidade_tipo text not null, entidade_id bigint not null, campo text not null, valor_anterior text, valor_novo text,
  usuario_id uuid references hub.usuarios (id), origem text not null default 'usuario', criado_em timestamptz not null default now());
create table hub.fazendas (cod_faz int primary key, nome text not null);
insert into hub.fazendas values (10001, 'FAZENDA TESTE');
