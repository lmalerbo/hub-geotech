-- Corretivos: mapas de aplicação de corretivos (ferramenta app/corretivos.html).
-- Acesso: admin ou módulo 'corretivos' (qualquer papel). Escrita direta nas tabelas, protegida por RLS.
begin;

insert into hub.modulos (id, nome, ordem) values ('corretivos', 'Corretivos', 6) on conflict (id) do nothing;

create or replace function hub.pode_usar_corretivos()
returns boolean language sql stable security definer set search_path = hub as $$
  select exists (select 1 from hub.usuarios u
                  where u.id = auth.uid()
                    and (u.admin or exists (select 1 from hub.usuario_modulos m
                                             where m.usuario_id = u.id and m.modulo_id = 'corretivos')));
$$;

create table hub.corretivo_mapas (
  id            bigint generated always as identity primary key,
  cod_faz       int not null references hub.fazendas (cod_faz),
  operacao      text not null check (operacao in ('subsolagem', 'supergrade', 'arado')),
  data          date not null default current_date,
  criado_por    uuid references hub.usuarios (id) default auth.uid(),
  criado_em     timestamptz not null default now(),
  alterado_por  uuid references hub.usuarios (id) default auth.uid(),
  alterado_em   timestamptz not null default now()
);
create index on hub.corretivo_mapas (cod_faz);

create table hub.corretivo_talhoes (
  mapa_id       bigint not null references hub.corretivo_mapas (id) on delete cascade,
  talhao_num    int not null check (talhao_num between 0 and 999),
  area_ha       numeric not null check (area_ha > 0),
  area_editada  boolean not null default false,
  primary key (mapa_id, talhao_num)
);

create table hub.corretivo_aplicacoes (
  id          bigint generated always as identity primary key,
  mapa_id     bigint not null references hub.corretivo_mapas (id) on delete cascade,
  tipo        text not null check (tipo in ('calcario', 'fosfato', 'blend')),
  calcario    text check (calcario in ('dolomitico', 'ph7')),
  dose        numeric not null check (dose > 0),
  dose_gesso  numeric check (dose_gesso > 0),
  os          text not null check (length(trim(os)) > 0),
  ordem       int not null default 1,
  check ((tipo = 'fosfato'  and calcario is null     and dose_gesso is null)
      or (tipo = 'calcario' and calcario is not null and dose_gesso is null)
      or (tipo = 'blend'    and calcario is not null and dose_gesso is not null))
);
create index on hub.corretivo_aplicacoes (mapa_id);

create table hub.corretivo_aplicacao_talhoes (
  aplicacao_id  bigint not null references hub.corretivo_aplicacoes (id) on delete cascade,
  mapa_id       bigint not null,
  talhao_num    int not null,
  primary key (aplicacao_id, talhao_num),
  foreign key (mapa_id, talhao_num) references hub.corretivo_talhoes (mapa_id, talhao_num) on delete cascade
);

-- Quem mexeu por último no mapa (qualquer tabela filha "toca" o mapa).
create or replace function hub.corretivo_tocar()
returns trigger language plpgsql security definer set search_path = hub as $$
declare v_mapa bigint;
begin
  if tg_table_name = 'corretivo_mapas' then
    new.alterado_por := auth.uid(); new.alterado_em := now(); return new;
  end if;
  v_mapa := case when tg_op = 'DELETE' then old.mapa_id else new.mapa_id end;
  update hub.corretivo_mapas set alterado_em = now() where id = v_mapa;
  return null;
end $$;
create trigger corretivo_mapas_tocar before update on hub.corretivo_mapas
  for each row execute function hub.corretivo_tocar();
create trigger corretivo_talhoes_tocar after insert or update or delete on hub.corretivo_talhoes
  for each row execute function hub.corretivo_tocar();
create trigger corretivo_aplicacoes_tocar after insert or update or delete on hub.corretivo_aplicacoes
  for each row execute function hub.corretivo_tocar();

-- Talhão da aplicação precisa ser do mesmo mapa; aplicação idêntica no mesmo talhão é recusada.
create or replace function hub.corretivo_checar_aplicacao_talhao()
returns trigger language plpgsql security definer set search_path = hub as $$
declare a hub.corretivo_aplicacoes;
begin
  select * into a from hub.corretivo_aplicacoes where id = new.aplicacao_id;
  if a.mapa_id is distinct from new.mapa_id then
    raise exception 'Aplicação % não é do mapa %', new.aplicacao_id, new.mapa_id;
  end if;
  if exists (select 1 from hub.corretivo_aplicacao_talhoes x
               join hub.corretivo_aplicacoes b on b.id = x.aplicacao_id
              where x.mapa_id = new.mapa_id and x.talhao_num = new.talhao_num and b.id <> a.id
                and b.tipo = a.tipo and b.calcario is not distinct from a.calcario and b.dose = a.dose
                and b.dose_gesso is not distinct from a.dose_gesso and b.os = a.os) then
    raise exception 'O talhão % já tem esta aplicação', new.talhao_num;
  end if;
  return new;
end $$;
create trigger corretivo_aplicacao_talhoes_checar before insert or update on hub.corretivo_aplicacao_talhoes
  for each row execute function hub.corretivo_checar_aplicacao_talhao();

-- Exclusão de mapa vai para o log.
create or replace function hub.corretivo_log_exclusao()
returns trigger language plpgsql security definer set search_path = hub as $$
begin
  insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo, usuario_id, origem)
  values ('corretivos', 'fazenda', old.cod_faz, 'mapa_corretivo',
          format('mapa %s · %s · %s', old.id, old.operacao, to_char(old.data, 'DD/MM/YYYY')), null, auth.uid(), 'usuario');
  return old;
end $$;
create trigger corretivo_mapas_log after delete on hub.corretivo_mapas
  for each row execute function hub.corretivo_log_exclusao();

-- RLS: tudo liberado para quem pode usar os Corretivos.
do $$
declare t text;
begin
  foreach t in array array['corretivo_mapas', 'corretivo_talhoes', 'corretivo_aplicacoes', 'corretivo_aplicacao_talhoes'] loop
    execute format('alter table hub.%I enable row level security', t);
    execute format('create policy corretivos on hub.%I for all to authenticated '
                   'using (hub.pode_usar_corretivos()) with check (hub.pode_usar_corretivos())', t);
    execute format('grant select, insert, update, delete on hub.%I to authenticated', t);
    execute format('grant all on hub.%I to service_role', t);
  end loop;
end $$;

-- Talhões da fazenda para o mapa (geometria + área produtiva da Base).
create or replace function hub.corretivo_talhoes_fazenda(p_cod_faz int)
returns jsonb language plpgsql stable security definer set search_path = hub, extensions as $$
begin
  if not hub.pode_usar_corretivos() then
    raise exception 'Sem acesso aos Corretivos';
  end if;
  return (
    select jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(
             jsonb_build_object('type', 'Feature', 'geometry', ST_AsGeoJSON(g.geom, 6)::jsonb,
                                'properties', jsonb_build_object('talhao', g.talhao_num,
                                                                 'area_prod', coalesce(t.area_ha, g.area_ha)))
             order by g.talhao_num), '[]'::jsonb))
      from hub.talhao_geom g
      left join hub.talhoes t on t.cod_faz = g.cod_faz and t.talhao_num = g.talhao_num
     where g.cod_faz = p_cod_faz);
end $$;

revoke all on function hub.pode_usar_corretivos() from public, anon;
revoke all on function hub.corretivo_talhoes_fazenda(int) from public, anon;
grant execute on function hub.pode_usar_corretivos() to authenticated, service_role;
grant execute on function hub.corretivo_talhoes_fazenda(int) to authenticated, service_role;

commit;
