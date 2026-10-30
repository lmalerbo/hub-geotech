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

-- acesso_salvar: cópia de 20261023090000_niveis_por_modulo.sql; só 'apresentacao' entra ao lado de 'corretivos'.
create or replace function hub.acesso_salvar(
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
                 or (n.key in ('corretivos', 'apresentacao') and n.value #>> '{}' <> 'editor')) then
    raise exception 'Nível inválido';
  end if;
  if jsonb_typeof(v_mapas) <> 'array' or exists (
       select 1 from jsonb_array_elements(v_mapas) m
        where coalesce(m ->> 'mapa_id', '') !~ '^\d+$' or coalesce(jsonb_typeof(m -> 'pode_editar'), '') <> 'boolean') then
    raise exception 'Mapas do GeoMap inválidos';
  end if;
  if not v_gm then v_mapas := '[]'; end if;

  v_modulos := array(select k from jsonb_object_keys(v_niveis) k order by k);
  v_papel := case when exists (select 1 from jsonb_each_text(v_niveis) n where n.value = 'editor' and n.key not in ('corretivos', 'apresentacao')) then 'editor'
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

revoke all on function hub.acesso_salvar(text, text, boolean, jsonb, boolean, boolean, int[], jsonb) from public, anon;
grant execute on function hub.acesso_salvar(text, text, boolean, jsonb, boolean, boolean, int[], jsonb) to authenticated, service_role;

commit;
