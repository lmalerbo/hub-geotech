-- Paralelismo: rodadas, arquivos, linhas e análises por talhão (spec 2026-10-26-paralelismo-design.md §5).
-- Níveis: leitura | solicitante | editor (+ admin). Escrita só pelas RPCs, menos as frotas (editor, direto).
-- O cartão em Ferramentas entra na P3, junto com a página.
begin;

insert into hub.modulos (id, nome, ordem) values ('paralelismo', 'Paralelismo', 8) on conflict (id) do nothing;

alter table hub.usuario_modulos drop constraint if exists usuario_modulos_nivel_check;
alter table hub.usuario_modulos add constraint usuario_modulos_nivel_check
  check (nivel in ('leitura', 'solicitante', 'editor') and (nivel <> 'solicitante' or modulo_id in ('drone', 'paralelismo')));

-- acesso_salvar: cópia de 20261029090000_apresentacao_acesso.sql; só o nível solicitante passa a valer também no Paralelismo.
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
                 or (n.value #>> '{}' = 'solicitante' and n.key not in ('drone', 'paralelismo'))
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

alter table hub.talhoes add column if not exists declividade numeric;

create table hub.paralelismo_frotas (
  serie         text primary key,                 -- BM0000X000000; GS3: 'GS3:<frota>'
  frota         text not null,
  operacao      text check (operacao in ('cana', 'torta')),
  tipo          text check (tipo in ('propria', 'prestador')),
  nomes_antigos text,
  observacao    text
);

create table hub.paralelismo_rodadas (
  id            bigserial primary key,
  descricao     text,
  release_tag   text,
  partes        jsonb not null default '[]',
  status        text not null default 'pendente' check (status in ('pendente', 'publicada', 'recusada')),
  criado_por    uuid references hub.usuarios (id),
  criado_em     timestamptz not null default now(),
  validado_por  uuid references hub.usuarios (id),
  validado_em   timestamptz,
  motivo_recusa text
);

create table hub.paralelismo_reservas (
  id         bigint primary key,
  criado_por uuid not null references hub.usuarios (id),
  criado_em  timestamptz not null default now(),
  enviada_em timestamptz
);

create table hub.paralelismo_arquivos (
  sha256          text primary key,
  rodada_id       bigint not null references hub.paralelismo_rodadas (id) on delete cascade,
  caminho         text not null,
  bytes           bigint,
  tipo            text check (tipo in ('jdl', 'fdl', 'fdd')),
  serie           text,
  frota           text,
  cod_faz         int,
  fazenda_monitor text
);
create index paralelismo_arquivos_rodada_idx on hub.paralelismo_arquivos (rodada_id);

create table hub.paralelismo_linhas (
  id        bigserial primary key,
  rodada_id bigint not null references hub.paralelismo_rodadas (id) on delete cascade,
  operacao  text not null check (operacao in ('cana', 'torta')),
  cod_faz   int not null,
  frota     text,
  data      date,
  geom      extensions.geometry(LineString, 31983) not null
);
create index paralelismo_linhas_fazenda_idx on hub.paralelismo_linhas (operacao, cod_faz);
create index paralelismo_linhas_rodada_idx on hub.paralelismo_linhas (rodada_id);

create table hub.paralelismo_analises (
  id              bigserial primary key,
  operacao        text not null check (operacao in ('cana', 'torta')),
  cod_faz         int not null,
  rodada_id       bigint not null references hub.paralelismo_rodadas (id) on delete cascade,
  metodo          text not null default 'trator' check (metodo in ('trator', 'agrocad_fme')),
  mes             date,
  amostras        int not null default 0,
  aderentes       int not null default 0,
  acima           int not null default 0,
  abaixo          int not null default 0,
  fora_talhao     int not null default 0,
  pll_total       int not null default 0,
  pll_aderentes   int not null default 0,
  vigente         boolean not null default false,
  base_analise_id bigint references hub.paralelismo_analises (id) on delete set null,
  amostras_url    text,
  unique (rodada_id, operacao, cod_faz),
  check (aderentes + acima + abaixo = amostras),
  check (amostras + fora_talhao = pll_total)
);
create unique index paralelismo_analises_vigente_idx on hub.paralelismo_analises (operacao, cod_faz) where vigente;

create table hub.paralelismo_talhoes (
  analise_id bigint not null references hub.paralelismo_analises (id) on delete cascade,
  talhao_num int not null,
  amostras   int not null default 0,
  aderentes  int not null default 0,
  acima      int not null default 0,
  abaixo     int not null default 0,
  media_m    numeric,
  frotas     text[] not null default '{}',
  primary key (analise_id, talhao_num),
  check (aderentes + acima + abaixo = amostras)
);

-- ── Acesso ─────────────────────────────────────────────────────────────
create function hub.paralelismo_nivel()
returns text language sql stable security definer set search_path = hub as $$
  select case when u.admin then 'admin'
              else (select m.nivel from hub.usuario_modulos m
                     where m.usuario_id = u.id and m.modulo_id = 'paralelismo') end
    from hub.usuarios u where u.id = auth.uid();
$$;

create function hub.paralelismo_processa()
returns boolean language sql stable security definer set search_path = hub as $$
  select coalesce(hub.paralelismo_nivel() in ('solicitante', 'editor', 'admin'), false);
$$;

-- ── Envio ──────────────────────────────────────────────────────────────
-- O link vira href nas telas de quem valida: só https (bloqueia javascript: e afins).
create function hub.paralelismo_url_ok(p_url text)
returns boolean language sql immutable set search_path = hub as $$
  select coalesce(p_url ~ '^https://', false);
$$;

-- Sem id: reserva um para quem pediu, sem criar a rodada (a release precisa dele antes). A reserva nunca é
-- apagada: id de rodada já enviada, mesmo que excluída depois, não volta a valer e não sobrescreve a release.
create function hub.paralelismo_preparar_parte(p_rodada_id bigint default null)
returns bigint language plpgsql security definer set search_path = hub as $$
declare
  v_id      bigint := p_rodada_id;
  v_enviada timestamptz;
begin
  if not hub.paralelismo_processa() then raise exception 'Sem permissão para enviar ao Paralelismo'; end if;
  if v_id is null then
    v_id := nextval('hub.paralelismo_rodadas_id_seq');
    insert into hub.paralelismo_reservas (id, criado_por) values (v_id, auth.uid());
    return v_id;
  end if;
  select enviada_em into v_enviada from hub.paralelismo_reservas where id = v_id and criado_por = auth.uid();
  if not found then raise exception 'rodada_invalida:%', v_id; end if;
  if v_enviada is not null then raise exception 'rodada_ja_enviada:%', v_id; end if;
  return v_id;
end $$;

create function hub.paralelismo_ja_analisados(p_sha256 text[])
returns text[] language plpgsql stable security definer set search_path = hub as $$
begin
  if not hub.paralelismo_processa() then raise exception 'Sem permissão para enviar ao Paralelismo'; end if;
  return array(select a.sha256 from hub.paralelismo_arquivos a
                 join hub.paralelismo_rodadas r on r.id = a.rodada_id
                where a.sha256 = any (p_sha256) and r.status in ('pendente', 'publicada'));
end $$;

-- p_rodada_id inclui as linhas daquela rodada (o editor refaz limpar + PLL ao validar fora de ordem).
create function hub.paralelismo_linhas_vigentes(p_operacao text, p_cod_faz int, p_rodada_id bigint default null)
returns jsonb language plpgsql stable security definer set search_path = hub, extensions as $$
begin
  if not hub.paralelismo_processa() then raise exception 'Sem permissão para processar o Paralelismo'; end if;
  if p_rodada_id is not null and not hub.pode_editar('paralelismo') and not exists (
       select 1 from hub.paralelismo_rodadas where id = p_rodada_id and criado_por = auth.uid()) then
    raise exception 'Sem permissão para ver esta rodada';
  end if;
  return jsonb_build_object(
    'analise_id', (select a.id from hub.paralelismo_analises a
                    where a.operacao = p_operacao and a.cod_faz = p_cod_faz and a.vigente),
    'linhas', coalesce((
      select jsonb_agg(jsonb_build_object('frota', l.frota, 'data', l.data,
                                          'coords', st_asgeojson(l.geom)::jsonb -> 'coordinates') order by l.id)
        from hub.paralelismo_linhas l
        join hub.paralelismo_rodadas r on r.id = l.rodada_id
       where l.operacao = p_operacao and l.cod_faz = p_cod_faz
         and (r.status = 'publicada' or r.id = p_rodada_id)), '[]'::jsonb));
end $$;

create function hub.paralelismo_talhoes_fazenda(p_cod_faz int)
returns jsonb language plpgsql stable security definer set search_path = hub, extensions as $$
begin
  if not hub.paralelismo_processa() then raise exception 'Sem permissão para processar o Paralelismo'; end if;
  return jsonb_build_object('type', 'FeatureCollection', 'features', coalesce((
    select jsonb_agg(jsonb_build_object(
             'type', 'Feature', 'geometry', st_asgeojson(g.geom, 6)::jsonb,
             'properties', jsonb_build_object('talhao', g.talhao_num, 'area_ha', g.area_ha,
                                              'declividade', t.declividade)) order by g.talhao_num)
      from hub.talhao_geom g
      left join hub.talhoes t on t.cod_faz = g.cod_faz and t.talhao_num = g.talhao_num
     where g.cod_faz = p_cod_faz), '[]'::jsonb));
end $$;

create function hub.paralelismo_gravar_talhoes(p_analise_id bigint, p_talhoes jsonb)
returns void language sql security definer set search_path = hub as $$
  insert into hub.paralelismo_talhoes (analise_id, talhao_num, amostras, aderentes, acima, abaixo, media_m, frotas)
  select p_analise_id, (t ->> 'talhao_num')::int, (t ->> 'amostras')::int, (t ->> 'aderentes')::int,
         (t ->> 'acima')::int, (t ->> 'abaixo')::int, (t ->> 'media_m')::numeric,
         array(select jsonb_array_elements_text(coalesce(t -> 'frotas', '[]')))
    from jsonb_array_elements(coalesce(p_talhoes, '[]')) t;
$$;

create function hub.paralelismo_enviar(p jsonb)
returns bigint language plpgsql security definer set search_path = hub, extensions as $$
declare
  v_id      bigint := (p ->> 'rodada_id')::bigint;
  v_enviada timestamptz;
  v_shas    text[] := array(select x ->> 'sha256' from jsonb_array_elements(coalesce(p -> 'arquivos', '[]')) x);
  v_repet   text;
  a         jsonb;
  v_analise bigint;
begin
  if not hub.paralelismo_processa() then raise exception 'Sem permissão para enviar ao Paralelismo'; end if;
  perform pg_advisory_xact_lock(hashtext('hub.paralelismo'));
  select enviada_em into v_enviada from hub.paralelismo_reservas
   where id = v_id and criado_por = auth.uid() for update;
  if not found then raise exception 'rodada_invalida:%', v_id; end if;
  if v_enviada is not null then raise exception 'rodada_ja_enviada:%', v_id; end if;
  if jsonb_array_length(coalesce(p -> 'analises', '[]')) = 0 then raise exception 'rodada_sem_analise'; end if;

  select string_agg(s, ',') into v_repet
    from (select s from unnest(v_shas) s group by s having count(*) > 1) d;
  if v_repet is not null then raise exception 'arquivo_repetido_no_envio:%', v_repet; end if;

  select string_agg(distinct l.operacao || '/' || l.cod_faz, ',') into v_repet
    from jsonb_to_recordset(coalesce(p -> 'linhas', '[]')) l (operacao text, cod_faz int)
   where not exists (select 1 from jsonb_to_recordset(p -> 'analises') n (operacao text, cod_faz int)
                      where n.operacao = l.operacao and n.cod_faz = l.cod_faz);
  if v_repet is not null then raise exception 'linha_sem_analise:%', v_repet; end if;

  if exists (select 1 from jsonb_array_elements(coalesce(p -> 'partes', '[]')) x where not hub.paralelismo_url_ok(x ->> 'url'))
     or exists (select 1 from jsonb_array_elements(p -> 'analises') x
                 where x ->> 'amostras_url' is not null and not hub.paralelismo_url_ok(x ->> 'amostras_url')) then
    raise exception 'url_invalida';
  end if;

  -- arquivo de rodada recusada pode voltar; de pendente ou publicada, não
  delete from hub.paralelismo_arquivos a using hub.paralelismo_rodadas r
   where r.id = a.rodada_id and r.status = 'recusada' and a.sha256 = any (v_shas);
  select string_agg(sha256, ',') into v_repet from hub.paralelismo_arquivos where sha256 = any (v_shas);
  if v_repet is not null then raise exception 'arquivo_ja_analisado:%', v_repet; end if;

  update hub.paralelismo_reservas set enviada_em = now() where id = v_id;

  insert into hub.paralelismo_rodadas (id, descricao, release_tag, partes, criado_por)
  values (v_id, p ->> 'descricao', 'paralelismo-r' || v_id, coalesce(p -> 'partes', '[]'), auth.uid());

  insert into hub.paralelismo_arquivos (sha256, rodada_id, caminho, bytes, tipo, serie, frota, cod_faz, fazenda_monitor)
  select x ->> 'sha256', v_id, x ->> 'caminho', (x ->> 'bytes')::bigint, x ->> 'tipo', x ->> 'serie', x ->> 'frota',
         (x ->> 'cod_faz')::int, x ->> 'fazenda_monitor'
    from jsonb_array_elements(coalesce(p -> 'arquivos', '[]')) x;

  insert into hub.paralelismo_linhas (rodada_id, operacao, cod_faz, frota, data, geom)
  select v_id, l ->> 'operacao', (l ->> 'cod_faz')::int, l ->> 'frota', (l ->> 'data')::date,
         st_setsrid(st_geomfromgeojson(jsonb_build_object('type', 'LineString', 'coordinates', l -> 'coords')::text), 31983)
    from jsonb_array_elements(coalesce(p -> 'linhas', '[]')) l;

  for a in select * from jsonb_array_elements(p -> 'analises') loop
    insert into hub.paralelismo_analises (operacao, cod_faz, rodada_id, metodo, mes, amostras, aderentes, acima, abaixo,
                                          fora_talhao, pll_total, pll_aderentes, base_analise_id, amostras_url)
    values (a ->> 'operacao', (a ->> 'cod_faz')::int, v_id, coalesce(a ->> 'metodo', 'trator'), (a ->> 'mes')::date,
            (a ->> 'amostras')::int, (a ->> 'aderentes')::int, (a ->> 'acima')::int, (a ->> 'abaixo')::int,
            (a ->> 'fora_talhao')::int, (a ->> 'pll_total')::int, (a ->> 'pll_aderentes')::int,
            (a ->> 'base_analise_id')::bigint, a ->> 'amostras_url')
    returning id into v_analise;
    perform hub.paralelismo_gravar_talhoes(v_analise, a -> 'talhoes');
  end loop;
  return v_id;
end $$;

-- ── Validação ──────────────────────────────────────────────────────────
-- Recálculo: [{operacao, cod_faz, base_analise_id, mes, amostras, ..., amostras_url, talhoes}].
create function hub.paralelismo_publicar(p_rodada_id bigint, p_recalculo jsonb default null)
returns jsonb language plpgsql security definer set search_path = hub as $$
declare
  v_status  text;
  v_mudadas text;
  c         jsonb;
  v_analise bigint;
begin
  if not hub.pode_editar('paralelismo') then raise exception 'Só o editor publica rodadas do Paralelismo'; end if;
  perform pg_advisory_xact_lock(hashtext('hub.paralelismo'));
  select status into v_status from hub.paralelismo_rodadas where id = p_rodada_id for update;
  if v_status is distinct from 'pendente' then raise exception 'rodada_nao_pendente:%', p_rodada_id; end if;

  for c in select * from jsonb_array_elements(coalesce(p_recalculo, '[]')) loop
    if c ->> 'amostras_url' is not null and not hub.paralelismo_url_ok(c ->> 'amostras_url') then
      raise exception 'url_invalida';
    end if;
    update hub.paralelismo_analises
       set mes = (c ->> 'mes')::date, amostras = (c ->> 'amostras')::int, aderentes = (c ->> 'aderentes')::int,
           acima = (c ->> 'acima')::int, abaixo = (c ->> 'abaixo')::int, fora_talhao = (c ->> 'fora_talhao')::int,
           pll_total = (c ->> 'pll_total')::int, pll_aderentes = (c ->> 'pll_aderentes')::int,
           base_analise_id = (c ->> 'base_analise_id')::bigint, amostras_url = c ->> 'amostras_url'
     where rodada_id = p_rodada_id and operacao = c ->> 'operacao' and cod_faz = (c ->> 'cod_faz')::int
    returning id into v_analise;
    if v_analise is null then raise exception 'recalculo_sem_analise:%', c ->> 'cod_faz'; end if;
    delete from hub.paralelismo_talhoes where analise_id = v_analise;
    perform hub.paralelismo_gravar_talhoes(v_analise, c -> 'talhoes');
  end loop;

  select string_agg(n.operacao || '/' || n.cod_faz, ',' order by n.operacao, n.cod_faz) into v_mudadas
    from hub.paralelismo_analises n
    left join hub.paralelismo_analises v on v.operacao = n.operacao and v.cod_faz = n.cod_faz and v.vigente
   where n.rodada_id = p_rodada_id and n.base_analise_id is distinct from v.id;
  if v_mudadas is not null then raise exception 'recalculo_necessario:%', v_mudadas; end if;

  update hub.paralelismo_analises v set vigente = false
    from hub.paralelismo_analises n
   where n.rodada_id = p_rodada_id and v.operacao = n.operacao and v.cod_faz = n.cod_faz and v.vigente;
  update hub.paralelismo_analises set vigente = true where rodada_id = p_rodada_id;
  update hub.paralelismo_rodadas set status = 'publicada', validado_por = auth.uid(), validado_em = now()
   where id = p_rodada_id;
  return jsonb_build_object('rodada_id', p_rodada_id, 'fazendas',
    (select jsonb_agg(jsonb_build_object('operacao', operacao, 'cod_faz', cod_faz) order by operacao, cod_faz)
       from hub.paralelismo_analises where rodada_id = p_rodada_id));
end $$;

create function hub.paralelismo_recusar(p_rodada_id bigint, p_motivo text)
returns void language plpgsql security definer set search_path = hub as $$
begin
  if not hub.pode_editar('paralelismo') then raise exception 'Só o editor recusa rodadas do Paralelismo'; end if;
  if length(trim(coalesce(p_motivo, ''))) = 0 then raise exception 'Informe o motivo da recusa'; end if;
  update hub.paralelismo_rodadas
     set status = 'recusada', motivo_recusa = trim(p_motivo), validado_por = auth.uid(), validado_em = now()
   where id = p_rodada_id and status = 'pendente';
  if not found then raise exception 'rodada_nao_pendente:%', p_rodada_id; end if;
end $$;

-- Apaga a rodada e devolve a análise anterior de cada fazenda. A release fica no GitHub como prova:
-- devolve a tag para a tela marcá-la como excluída.
create function hub.paralelismo_excluir(p_rodada_id bigint)
returns text language plpgsql security definer set search_path = hub as $$
declare
  v_tag      text;
  v_status   text;
  v_validado timestamptz;
  v_bloqueio text;
  v_tocadas  jsonb;
  f          record;
begin
  if not hub.eh_admin() then raise exception 'Só administradores excluem rodadas do Paralelismo'; end if;
  perform pg_advisory_xact_lock(hashtext('hub.paralelismo'));
  select release_tag, status, validado_em into v_tag, v_status, v_validado
    from hub.paralelismo_rodadas where id = p_rodada_id for update;
  if v_status is distinct from 'publicada' then raise exception 'rodada_nao_publicada:%', p_rodada_id; end if;

  select string_agg(distinct n.cod_faz::text, ',') into v_bloqueio
    from hub.paralelismo_analises a
    join hub.paralelismo_analises n on n.operacao = a.operacao and n.cod_faz = a.cod_faz and n.rodada_id <> a.rodada_id
    join hub.paralelismo_rodadas r on r.id = n.rodada_id
   where a.rodada_id = p_rodada_id and r.status = 'publicada' and r.validado_em > v_validado;
  if v_bloqueio is not null then raise exception 'exclua_antes_rodada_mais_nova:%', v_bloqueio; end if;

  -- a prévia pendente já embute as linhas desta rodada: decida-a antes
  select string_agg(distinct n.rodada_id::text, ',') into v_bloqueio
    from hub.paralelismo_analises n
    join hub.paralelismo_analises a on a.id = n.base_analise_id
    join hub.paralelismo_rodadas r on r.id = n.rodada_id
   where a.rodada_id = p_rodada_id and r.status = 'pendente';
  if v_bloqueio is not null then raise exception 'rodada_pendente_depende:%', v_bloqueio; end if;

  v_tocadas := (select jsonb_agg(jsonb_build_object('operacao', operacao, 'cod_faz', cod_faz))
                  from hub.paralelismo_analises where rodada_id = p_rodada_id);
  delete from hub.paralelismo_rodadas where id = p_rodada_id;
  for f in select * from jsonb_to_recordset(v_tocadas) x (operacao text, cod_faz int) loop
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo, usuario_id, origem)
    values ('paralelismo', 'fazenda', f.cod_faz, 'rodada_paralelismo_excluida', v_tag, f.operacao, auth.uid(), 'usuario');
    update hub.paralelismo_analises set vigente = true
     where id = (select x.id from hub.paralelismo_analises x
                   join hub.paralelismo_rodadas r on r.id = x.rodada_id
                  where x.operacao = f.operacao and x.cod_faz = f.cod_faz and r.status = 'publicada'
                  order by r.validado_em desc, x.id desc limit 1);
  end loop;
  return v_tag;
end $$;

-- ── RLS ────────────────────────────────────────────────────────────────
do $$
declare t text;
begin
  foreach t in array array['paralelismo_frotas', 'paralelismo_rodadas', 'paralelismo_arquivos', 'paralelismo_linhas',
                           'paralelismo_analises', 'paralelismo_talhoes'] loop
    execute format('alter table hub.%I enable row level security', t);
    execute format('grant select on hub.%I to authenticated', t);
  end loop;
end $$;
-- reservas: só as RPCs usam
alter table hub.paralelismo_reservas enable row level security;
revoke all on hub.paralelismo_reservas from public, anon, authenticated;

create policy ver on hub.paralelismo_frotas for select to authenticated using (hub.pode_ver('paralelismo'));
create policy editar on hub.paralelismo_frotas for all to authenticated
  using (hub.pode_editar('paralelismo')) with check (hub.pode_editar('paralelismo'));
grant insert, update, delete on hub.paralelismo_frotas to authenticated;

create policy ver on hub.paralelismo_rodadas for select to authenticated using (
  (status = 'publicada' and hub.pode_ver('paralelismo'))
  or hub.pode_editar('paralelismo')
  or (criado_por = auth.uid() and hub.paralelismo_processa()));
create policy ver on hub.paralelismo_analises for select to authenticated using (
  exists (select 1 from hub.paralelismo_rodadas r where r.id = rodada_id));
create policy ver on hub.paralelismo_talhoes for select to authenticated using (
  exists (select 1 from hub.paralelismo_analises a where a.id = analise_id));
create policy ver on hub.paralelismo_arquivos for select to authenticated using (
  hub.paralelismo_processa() and exists (select 1 from hub.paralelismo_rodadas r where r.id = rodada_id));
create policy ver on hub.paralelismo_linhas for select to authenticated using (
  hub.paralelismo_processa() and exists (select 1 from hub.paralelismo_rodadas r where r.id = rodada_id));

do $$
declare f text;
begin
  foreach f in array array['paralelismo_nivel()', 'paralelismo_processa()', 'paralelismo_preparar_parte(bigint)',
                           'paralelismo_ja_analisados(text[])', 'paralelismo_linhas_vigentes(text, int, bigint)',
                           'paralelismo_talhoes_fazenda(int)', 'paralelismo_enviar(jsonb)',
                           'paralelismo_publicar(bigint, jsonb)', 'paralelismo_recusar(bigint, text)',
                           'paralelismo_excluir(bigint)'] loop
    execute format('revoke all on function hub.%s from public, anon', f);
    execute format('grant execute on function hub.%s to authenticated, service_role', f);
  end loop;
  execute 'revoke all on function hub.paralelismo_gravar_talhoes(bigint, jsonb) from public, anon, authenticated';
  execute 'revoke all on function hub.paralelismo_url_ok(text) from public, anon, authenticated';
end $$;

commit;
