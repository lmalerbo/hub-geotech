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
create or replace function hub.nova_revisao(
  p_projeto_id bigint,
  p_documento  text,
  p_motivo     text,
  p_origens    bigint[] default null
)
returns bigint
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_modulo text;
  v_numero int;
  v_id     bigint;
begin
  -- Trava o projeto: duas revisões simultâneas não podem ganhar o mesmo número.
  select modulo_id into v_modulo from hub.projetos where id = p_projeto_id for update;
  if v_modulo is null then
    raise exception 'Projeto % não existe', p_projeto_id;
  end if;

  if not exists (select 1 from hub.documento_tipos where modulo_id = v_modulo and codigo = p_documento) then
    raise exception 'Documento "%" não existe no módulo %', p_documento, v_modulo;
  end if;

  if coalesce(auth.role(), '') <> 'service_role' and not hub.pode_editar(v_modulo) then
    raise exception 'Sem permissão para revisar projetos de %', v_modulo;
  end if;

  select coalesce(max(numero) + 1, 0) into v_numero
    from hub.projeto_revisoes
   where projeto_id = p_projeto_id and documento = p_documento;

  if v_numero > 0 and length(trim(coalesce(p_motivo, ''))) = 0 then
    raise exception 'Informe o motivo da revisão %', v_numero;
  end if;

  update hub.projeto_revisoes set vigente = false
   where projeto_id = p_projeto_id and documento = p_documento and vigente;

  insert into hub.projeto_revisoes (projeto_id, documento, numero, motivo, criado_por)
  values (p_projeto_id, p_documento, v_numero, nullif(trim(p_motivo), ''), auth.uid())
  returning id into v_id;

  if p_origens is not null then
    insert into hub.revisao_origens (revisao_id, origem_revisao_id)
    select v_id, unnest(p_origens);
  end if;

  return v_id;
end $$;

revoke all on function hub.nova_revisao(bigint, text, text, bigint[]) from public, anon;
grant execute on function hub.nova_revisao(bigint, text, text, bigint[]) to authenticated, service_role;

-- drone_solicitar: cópia da versão de 20261008090000_drone_parte2.sql (a partir da linha 205),
-- com a checagem de solicitante lendo usuario_modulos.nivel.
create or replace function hub.drone_solicitar(p_cod_faz int, p_tipo text, p_data_desejada date default null,
                                               p_observacao text default null)
returns bigint language plpgsql security definer set search_path = hub as $$
declare v_id bigint;
begin
  if p_tipo not in ('normal', 'catacao') then
    raise exception 'Tipo inválido: %', p_tipo;
  end if;
  if not hub.pode_editar('drone') and not (p_tipo = 'normal' and exists (
       select 1 from hub.usuario_modulos m
        where m.usuario_id = auth.uid() and m.modulo_id = 'drone' and m.nivel = 'solicitante')) then
    raise exception 'Sem permissão para abrir solicitação de %', p_tipo;
  end if;
  if not exists (select 1 from hub.fazendas where cod_faz = p_cod_faz) then
    raise exception 'Fazenda % não existe', p_cod_faz;
  end if;
  select id into v_id from hub.drone_solicitacoes
   where cod_faz = p_cod_faz and tipo = p_tipo and origem <> 'legado' and status not in ('ok', 'cancelado')
   order by id desc limit 1;
  if v_id is not null then
    return v_id;                                   -- já existe uma aberta: reaproveita
  end if;
  insert into hub.drone_solicitacoes (cod_faz, tipo, origem, solicitante_id, data_desejada, observacao)
  values (p_cod_faz, p_tipo, 'formulario', auth.uid(), p_data_desejada, nullif(trim(p_observacao), ''))
  returning id into v_id;
  return v_id;
end $$;

revoke all on function hub.drone_solicitar(int, text, date, text) from public, anon;
grant execute on function hub.drone_solicitar(int, text, date, text) to authenticated, service_role;

revoke all on function hub.acesso_salvar(text, text, boolean, jsonb, boolean, boolean, int[], jsonb) from public, anon;
revoke all on function hub.acessos_situacao() from public, anon;
grant execute on function hub.acesso_salvar(text, text, boolean, jsonb, boolean, boolean, int[], jsonb) to authenticated, service_role;
grant execute on function hub.acessos_situacao() to authenticated, service_role;

commit;
