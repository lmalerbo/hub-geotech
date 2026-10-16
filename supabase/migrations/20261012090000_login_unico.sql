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
