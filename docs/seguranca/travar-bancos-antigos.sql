-- ══════════════════════════════════════════════════════════════════
-- Trava de escrita nos bancos dos sistemas antigos (já substituídos pelo Hub):
--   · Plantio/Preparo  (msdkrkakuwmskoidxmxl)
--   · Colheita / Expo_safra (wewicqysphguehqnyjdh)
-- Rodar uma vez em CADA um dos dois projetos (SQL Editor → nova query).
--
-- Os formulários antigos continuam no ar e gravavam com a chave pública
-- (anon) — qualquer pessoa na internet podia alterar ou apagar dados. Depois
-- daqui a chave pública só LÊ:
--   · tira insert/update/delete/truncate de anon e authenticated em todas as
--     tabelas dos schemas da aplicação;
--   · tira a execução, para anon/authenticated, das funções que gravam
--     (registrar_bloco, upsert_usuario, ...), exceto as usadas pelas regras
--     de leitura (RLS), para a leitura continuar funcionando.
-- A chave de serviço (rotinas do servidor) não é afetada.
-- Ao final mostra o que ainda ficou gravável pela chave pública (deve vir vazio).
-- ══════════════════════════════════════════════════════════════════

begin;

create temporary table _schemas_app on commit drop as
select nspname from pg_namespace
 where nspname not in ('pg_catalog', 'information_schema', 'pg_toast', 'auth', 'storage', 'realtime', '_realtime',
                       'supabase_functions', 'supabase_migrations', 'extensions', 'graphql', 'graphql_public',
                       'pgsodium', 'pgsodium_masks', 'vault', 'net', 'cron', 'pgbouncer', '_analytics', 'pgmq')
   and nspname not like 'pg_temp%' and nspname not like 'pg_toast_temp%';

do $$
declare
  r record;
  usadas_em_regras text;
begin
  -- Tabelas e views: só leitura para a chave pública.
  for r in
    select n.nspname, c.relname
      from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where c.relkind in ('r', 'p', 'v', 'm', 'f')
       and n.nspname in (select nspname from _schemas_app)
  loop
    execute format('revoke insert, update, delete, truncate on %I.%I from anon, authenticated', r.nspname, r.relname);
  end loop;

  -- Funções que gravam: sem execução para a chave pública. As citadas em
  -- regras de RLS ficam (são de leitura e a leitura depende delas).
  select string_agg(coalesce(qual, '') || ' ' || coalesce(with_check, ''), ' ') into usadas_em_regras from pg_policies;
  for r in
    select p.oid::regprocedure as assinatura, p.proname
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname in (select nspname from _schemas_app)
       and p.prokind = 'f'
       and p.prorettype <> 'trigger'::regtype
       and p.prosrc ~* '\m(insert|update|delete|truncate)\M'
  loop
    if coalesce(usadas_em_regras, '') ~* ('\m' || r.proname || '\M') then
      raise notice 'mantida (usada em regra de leitura): %', r.assinatura;
      continue;
    end if;
    execute format('revoke execute on function %s from public, anon, authenticated', r.assinatura);
    raise notice 'sem execução pela chave pública: %', r.assinatura;
  end loop;
end $$;

-- Conferência: o que a chave pública ainda consegue gravar (deve vir vazio).
select 'tabela' as tipo, table_schema || '.' || table_name as objeto, string_agg(privilege_type, ', ') as permissao
  from information_schema.role_table_grants
 where grantee in ('anon', 'authenticated')
   and privilege_type in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
   and table_schema in (select nspname from _schemas_app)
 group by 1, 2
union all
select 'função', p.oid::regprocedure::text, 'EXECUTE'
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
 where n.nspname in (select nspname from _schemas_app)
   and p.prokind = 'f' and p.prorettype <> 'trigger'::regtype
   and p.prosrc ~* '\m(insert|update|delete|truncate)\M'
   and has_function_privilege('anon', p.oid, 'execute');

commit;

-- Para desfazer numa tabela específica (se algo legítimo precisar gravar):
--   grant insert, update, delete on <schema>.<tabela> to anon;
