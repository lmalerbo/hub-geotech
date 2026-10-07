-- Módulo Drone, Parte 2: geometria dos talhões, projeto por talhão, envios
-- pelo Hub e funções da tela. Spec: docs/superpowers/specs/2026-10-07-modulo-drone-parte2-design.md
begin;

-- ── execuções da ingestão: fonte nova ─────────────────────────────────
alter table hub.execucoes_ingestao drop constraint if exists execucoes_ingestao_fonte_check;
alter table hub.execucoes_ingestao add constraint execucoes_ingestao_fonte_check
  check (fonte in ('base_fazendas', 'planagri', 'icol', 'conservacao', 'dronemgmt', 'talhao_geom'));

-- ── geometria dos talhões (rodada diária) ─────────────────────────────
create table hub.talhao_geom (
  cod_faz       int not null,
  talhao_num    int not null,
  geom          extensions.geometry(MultiPolygon, 4326) not null,
  area_ha       numeric not null,
  atualizado_em timestamptz not null default now(),
  primary key (cod_faz, talhao_num)
);

create or replace function hub.talhao_geom_limpar(p_antes timestamptz)
returns int language plpgsql security definer set search_path = hub as $$
declare n int;
begin
  delete from hub.talhao_geom where atualizado_em < p_antes;
  get diagnostics n = row_count;
  return n;
end $$;

-- ── talhões das revisões e das gerações ───────────────────────────────
create table hub.drone_revisao_talhoes (
  revisao_id bigint not null references hub.projeto_revisoes (id) on delete cascade,
  talhao_num int    not null,
  geom       extensions.geometry(MultiPolygon, 31983) not null,
  area_ha    numeric not null,
  origem     text   not null check (origem in ('sistema', 'shape', 'legado')),
  desde_rev  int    not null,
  primary key (revisao_id, talhao_num)
);

create table hub.drone_geracao_talhoes (
  geracao_id bigint not null references hub.drone_geracoes (id) on delete cascade,
  talhao_num int    not null,
  geom       extensions.geometry(MultiPolygon, 31983) not null,
  area_ha    numeric not null,
  origem     text   not null check (origem in ('sistema', 'shape', 'legado')),
  desde_rev  int    not null,
  primary key (geracao_id, talhao_num)
);

alter table hub.drone_solicitacoes add column observacao text;
alter table hub.drone_geracoes add column escopo jsonb;

-- ── envios pelo Hub ───────────────────────────────────────────────────
create table hub.drone_envios (
  id             bigint generated always as identity primary key,
  cod_faz        int    not null references hub.fazendas (cod_faz),
  tipo           text   not null check (tipo in ('obstaculos', 'infestacao', 'ajuste')),
  classe_m       int    check (classe_m in (15, 25, 50)),
  solicitacao_id bigint references hub.drone_solicitacoes (id),
  arquivos       text[] not null,
  status         text   not null default 'fila' check (status in ('fila', 'processando', 'ok', 'erro')),
  erro           text,
  enviado_por    uuid references hub.usuarios (id),
  enviado_em     timestamptz not null default now(),
  iniciado_em    timestamptz,
  processado_em  timestamptz
);
create index on hub.drone_envios (status, enviado_em);

create table hub.drone_ajuste_feicoes (
  envio_id bigint not null references hub.drone_envios (id) on delete cascade,
  geom     extensions.geometry(Geometry, 31983) not null
);
create index on hub.drone_ajuste_feicoes (envio_id);

-- ── cobertura da Normal vigente ───────────────────────────────────────
create view hub.drone_cobertura_v with (security_invoker = false) as
select p.cod_faz,
       round(100 * sum(case when t.talhao_num is not null then g.area_ha else 0 end)
             / nullif(sum(g.area_ha), 0), 1) as cobertura_pct
  from hub.projetos p
  join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente and r.documento = 'normal'
  join hub.talhao_geom g on g.cod_faz = p.cod_faz
  left join hub.drone_revisao_talhoes t on t.revisao_id = r.id and t.talhao_num = g.talhao_num
 where p.modulo_id = 'drone' and p.tipo = 'individual'
 group by p.cod_faz;

-- ── funções do agente ─────────────────────────────────────────────────
create or replace function hub.drone_talhoes_vigentes(p_cod_faz int, p_documento text)
returns table (talhao_num int, wkt text, area_ha numeric, origem text, desde_rev int, revisao_em timestamptz)
language sql stable security definer set search_path = hub, extensions as $$
  select t.talhao_num, ST_AsText(t.geom), t.area_ha, t.origem, t.desde_rev, r.criado_em
    from hub.projetos p
    join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente and r.documento = p_documento
    join hub.drone_revisao_talhoes t on t.revisao_id = r.id
   where p.modulo_id = 'drone' and p.tipo = 'individual' and p.cod_faz = p_cod_faz;
$$;

create or replace function hub.drone_gravar_geracao_talhoes(p_geracao_id bigint, p_talhoes jsonb)
returns void language plpgsql security definer set search_path = hub, extensions as $$
begin
  delete from hub.drone_geracao_talhoes where geracao_id = p_geracao_id;
  insert into hub.drone_geracao_talhoes (geracao_id, talhao_num, geom, area_ha, origem, desde_rev)
  select p_geracao_id, (e->>'talhao')::int, ST_Multi(ST_GeomFromText(e->>'wkt', 31983)),
         (e->>'area_ha')::numeric, e->>'origem', (e->>'desde_rev')::int
    from jsonb_array_elements(p_talhoes) e;
end $$;

create or replace function hub.drone_gravar_revisao_talhoes(p_revisao_id bigint, p_talhoes jsonb)
returns void language plpgsql security definer set search_path = hub, extensions as $$
begin
  delete from hub.drone_revisao_talhoes where revisao_id = p_revisao_id;
  insert into hub.drone_revisao_talhoes (revisao_id, talhao_num, geom, area_ha, origem, desde_rev)
  select p_revisao_id, (e->>'talhao')::int, ST_Multi(ST_GeomFromText(e->>'wkt', 31983)),
         (e->>'area_ha')::numeric, e->>'origem', (e->>'desde_rev')::int
    from jsonb_array_elements(p_talhoes) e;
end $$;

create or replace function hub.drone_pegar_envio()
returns setof hub.drone_envios language plpgsql security definer set search_path = hub as $$
begin
  update hub.drone_envios set status = 'fila', iniciado_em = null
   where status = 'processando' and iniciado_em < now() - interval '15 minutes';
  return query
  update hub.drone_envios e set status = 'processando', iniciado_em = now()
   where e.id = (select id from hub.drone_envios where status = 'fila'
                  order by enviado_em for update skip locked limit 1)
  returning e.*;
end $$;

create or replace function hub.drone_concluir_envio(p_id bigint, p_status text, p_erro text)
returns void language sql security definer set search_path = hub as $$
  update hub.drone_envios set status = p_status, erro = left(p_erro, 1000), processado_em = now() where id = p_id;
$$;

create or replace function hub.drone_gravar_ajuste(p_envio_id bigint, p_wkts text[])
returns void language plpgsql security definer set search_path = hub, extensions as $$
begin
  delete from hub.drone_ajuste_feicoes where envio_id = p_envio_id;
  insert into hub.drone_ajuste_feicoes (envio_id, geom)
  select p_envio_id, ST_Force2D(ST_GeomFromText(w, 31983)) from unnest(p_wkts) w;
end $$;

create or replace function hub.drone_ajuste_wkt(p_envio_id bigint)
returns table (wkt text) language sql stable security definer set search_path = hub, extensions as $$
  select ST_AsText(geom) from hub.drone_ajuste_feicoes where envio_id = p_envio_id;
$$;

-- publicação: agora grava também os talhões (da geração ou do p_talhoes)
drop function hub.drone_publicar(int, text, text, int, jsonb, bigint, boolean);
create or replace function hub.drone_publicar(
  p_cod_faz int, p_documento text, p_motivo text, p_numero int, p_arquivos jsonb,
  p_geracao_id bigint default null, p_legado boolean default false, p_talhoes jsonb default null)
returns bigint language plpgsql security definer set search_path = hub, extensions as $$
declare v_proj bigint; v_rev bigint; v_num int; v_sol bigint;
begin
  insert into hub.projetos (modulo_id, tipo, cod_faz, nome)
  select 'drone', 'individual', f.cod_faz, f.nome from hub.fazendas f where f.cod_faz = p_cod_faz
  on conflict (modulo_id, cod_faz) where tipo = 'individual' do nothing;
  select id into v_proj from hub.projetos
   where modulo_id = 'drone' and tipo = 'individual' and cod_faz = p_cod_faz;
  if v_proj is null then
    raise exception 'Fazenda % não existe em hub.fazendas', p_cod_faz;
  end if;

  v_rev := hub.nova_revisao(v_proj, p_documento, p_motivo);
  select numero into v_num from hub.projeto_revisoes where id = v_rev;
  if v_num <> p_numero then
    raise exception 'A revisão mudou: arquivos enviados como Rev%, mas a próxima é Rev%. Gere o projeto de novo.',
      p_numero, v_num;
  end if;

  insert into hub.revisao_arquivos (revisao_id, nome_arquivo, release_url, tamanho_bytes)
  select v_rev, a.nome, a.url, a.tamanho
    from jsonb_to_recordset(p_arquivos) as a (nome text, url text, tamanho bigint);

  if p_geracao_id is not null then
    insert into hub.drone_revisao_talhoes (revisao_id, talhao_num, geom, area_ha, origem, desde_rev)
    select v_rev, talhao_num, geom, area_ha, origem, desde_rev
      from hub.drone_geracao_talhoes where geracao_id = p_geracao_id;
    update hub.drone_geracoes set status = 'publicada', concluido_em = now()
     where id = p_geracao_id and status = 'pronta' returning solicitacao_id into v_sol;
    if v_sol is null then
      raise exception 'Geração % não está pronta para publicar', p_geracao_id;
    end if;
    update hub.drone_geracoes set status = 'descartada'
     where solicitacao_id = v_sol and id <> p_geracao_id and status in ('fila', 'pronta', 'erro');
    update hub.drone_solicitacoes set status = 'ok', revisao_id = v_rev, concluido_em = now()
     where id = v_sol;
  elsif p_talhoes is not null then
    insert into hub.drone_revisao_talhoes (revisao_id, talhao_num, geom, area_ha, origem, desde_rev)
    select v_rev, (e->>'talhao')::int, ST_Multi(ST_GeomFromText(e->>'wkt', 31983)),
           (e->>'area_ha')::numeric, e->>'origem', (e->>'desde_rev')::int
      from jsonb_array_elements(p_talhoes) e;
  end if;

  if p_legado then
    insert into hub.drone_solicitacoes (cod_faz, tipo, origem, status, revisao_id, concluido_em)
    values (p_cod_faz, p_documento, 'legado', 'ok', v_rev, now());
  end if;
  return v_rev;
end $$;

-- ── funções do Hub (usuário logado) ───────────────────────────────────
create or replace function hub.drone_solicitar(p_cod_faz int, p_tipo text, p_data_desejada date default null,
                                               p_observacao text default null)
returns bigint language plpgsql security definer set search_path = hub as $$
declare v_id bigint;
begin
  if p_tipo not in ('normal', 'catacao') then
    raise exception 'Tipo inválido: %', p_tipo;
  end if;
  if not hub.pode_editar('drone') and not (p_tipo = 'normal' and exists (
       select 1 from hub.usuarios u join hub.usuario_modulos m on m.usuario_id = u.id and m.modulo_id = 'drone'
        where u.id = auth.uid() and u.papel = 'solicitante')) then
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

create or replace function hub.drone_registrar_envio(p_cod_faz int, p_tipo text, p_classe_m int,
                                                     p_solicitacao_id bigint, p_arquivos text[])
returns bigint language plpgsql security definer set search_path = hub as $$
declare v_id bigint;
begin
  if not hub.pode_editar('drone') then
    raise exception 'Sem permissão para enviar arquivos do Drone';
  end if;
  if coalesce(array_length(p_arquivos, 1), 0) = 0 then
    raise exception 'Nenhum arquivo enviado';
  end if;
  if exists (select 1 from unnest(p_arquivos) a where a not like p_cod_faz || '/%') then
    raise exception 'Arquivo fora da pasta da fazenda %', p_cod_faz;
  end if;
  if p_tipo = 'infestacao' and not exists (
       select 1 from hub.drone_solicitacoes where id = p_solicitacao_id and cod_faz = p_cod_faz and tipo = 'catacao') then
    raise exception 'A infestação precisa de uma solicitação de Catação desta fazenda';
  end if;
  insert into hub.drone_envios (cod_faz, tipo, classe_m, solicitacao_id, arquivos, enviado_por)
  values (p_cod_faz, p_tipo, p_classe_m, p_solicitacao_id, p_arquivos, auth.uid())
  returning id into v_id;
  return v_id;
end $$;

create or replace function hub.drone_pedir_geracao(p_solicitacao_id bigint, p_escopo jsonb default null)
returns bigint language plpgsql security definer set search_path = hub as $$
declare v_sol hub.drone_solicitacoes; v_id bigint; v_inf bigint; v_ruins int[];
begin
  if not hub.pode_editar('drone') then
    raise exception 'Sem permissão para gerar projetos de drone';
  end if;
  select * into v_sol from hub.drone_solicitacoes where id = p_solicitacao_id for update;
  if v_sol.id is null then
    raise exception 'Solicitação % não existe', p_solicitacao_id;
  end if;
  if v_sol.status in ('ok', 'cancelado') then
    raise exception 'Solicitação % já está encerrada', p_solicitacao_id;
  end if;
  perform pg_advisory_xact_lock(hashtext('drone_geracao_' || v_sol.cod_faz || '_' || v_sol.tipo));
  if exists (select 1 from hub.drone_geracoes g join hub.drone_solicitacoes s on s.id = g.solicitacao_id
              where s.cod_faz = v_sol.cod_faz and s.tipo = v_sol.tipo and g.status in ('fila', 'processando', 'pronta')) then
    raise exception 'Já existe uma prévia aberta desta fazenda. Publique ou descarte antes de gerar outra.';
  end if;

  if v_sol.tipo = 'normal' then
    if p_escopo is null or (jsonb_array_length(coalesce(p_escopo->'incluir', '[]')) = 0
                            and jsonb_array_length(coalesce(p_escopo->'remover', '[]')) = 0) then
      raise exception 'Escolha ao menos um talhão para incluir, refazer ou remover';
    end if;
    select array_agg(i order by i) into v_ruins from (
      select (e->>'talhao')::int i from jsonb_array_elements(coalesce(p_escopo->'incluir', '[]')) e
      intersect
      select r::int from jsonb_array_elements_text(coalesce(p_escopo->'remover', '[]')) r) x;
    if v_ruins is not null then
      raise exception 'Talhões marcados para incluir e remover ao mesmo tempo: %', v_ruins;
    end if;
    select array_agg(x.i order by x.i) into v_ruins
      from (select (e->>'talhao')::int i from jsonb_array_elements(coalesce(p_escopo->'incluir', '[]')) e) x
     where not exists (select 1 from hub.talhao_geom g where g.cod_faz = v_sol.cod_faz and g.talhao_num = x.i);
    if v_ruins is not null then
      raise exception 'Talhões que não existem na Base de hoje: %', v_ruins;
    end if;
    if exists (select 1 from jsonb_array_elements(coalesce(p_escopo->'incluir', '[]')) e
                where e->>'fonte' = 'shape' and not exists (
                  select 1 from hub.drone_envios v where v.id = (e->>'envio_id')::bigint
                     and v.cod_faz = v_sol.cod_faz and v.tipo = 'ajuste' and v.status = 'ok')) then
      raise exception 'O shape de ajuste ainda não foi processado (ou é de outra fazenda)';
    end if;
  else
    select id into v_inf from hub.drone_infestacoes where solicitacao_id = v_sol.id order by id desc limit 1;
    if v_inf is null then
      raise exception 'Envie a infestação antes de gerar a Catação';
    end if;
  end if;

  insert into hub.drone_geracoes (solicitacao_id, infestacao_id, escopo, pedido_por)
  values (v_sol.id, v_inf, p_escopo, auth.uid()) returning id into v_id;
  update hub.drone_solicitacoes
     set status = 'em_elaboracao', iniciado_em = coalesce(iniciado_em, now()),
         responsavel_id = coalesce(responsavel_id, auth.uid())
   where id = v_sol.id;
  return v_id;
end $$;

create or replace function hub.drone_publicar_pedido(p_geracao_id bigint, p_motivo text)
returns void language plpgsql security definer set search_path = hub as $$
declare v_g hub.drone_geracoes; v_tipo text; v_cod int; v_tem_rev boolean;
begin
  if not hub.pode_editar('drone') then
    raise exception 'Sem permissão para publicar projetos de drone';
  end if;
  select * into v_g from hub.drone_geracoes where id = p_geracao_id for update;
  if v_g.id is null or v_g.status <> 'pronta' then
    raise exception 'A prévia % não está pronta para publicar', p_geracao_id;
  end if;
  select s.tipo, s.cod_faz into v_tipo, v_cod from hub.drone_solicitacoes s where s.id = v_g.solicitacao_id;
  select exists (select 1 from hub.projetos p join hub.projeto_revisoes r on r.projeto_id = p.id
                  where p.modulo_id = 'drone' and p.tipo = 'individual' and p.cod_faz = v_cod
                    and r.documento = v_tipo) into v_tem_rev;
  if v_tipo = 'normal' and v_tem_rev and length(trim(coalesce(p_motivo, ''))) = 0 then
    raise exception 'Informe o motivo da nova revisão';
  end if;
  update hub.drone_geracoes
     set publicar_pedido_em = now(), publicar_motivo = nullif(trim(p_motivo), ''), publicar_por = auth.uid(),
         publicacao_erro = null, publicacao_iniciada_em = null
   where id = p_geracao_id;
end $$;

create or replace function hub.drone_descartar(p_geracao_id bigint)
returns void language plpgsql security definer set search_path = hub as $$
begin
  if not hub.pode_editar('drone') then
    raise exception 'Sem permissão';
  end if;
  update hub.drone_geracoes set status = 'descartada'
   where id = p_geracao_id and status in ('pronta', 'erro');
  if not found then
    raise exception 'Só dá para descartar uma prévia pronta ou com erro';
  end if;
end $$;

create or replace function hub.drone_mapa_fazenda(p_cod_faz int)
returns jsonb language sql stable security definer set search_path = hub, extensions as $$
with vig as (
  select r.id, r.documento, r.numero, r.criado_em
    from hub.projeto_revisoes r join hub.projetos p on p.id = r.projeto_id
   where p.modulo_id = 'drone' and p.tipo = 'individual' and p.cod_faz = p_cod_faz and r.vigente),
n as (select t.* from hub.drone_revisao_talhoes t join vig on vig.id = t.revisao_id and vig.documento = 'normal'),
c as (select t.* from hub.drone_revisao_talhoes t join vig on vig.id = t.revisao_id and vig.documento = 'catacao'),
feats as (
  select jsonb_build_object('type', 'Feature', 'id', g.talhao_num, 'geometry', ST_AsGeoJSON(g.geom, 6)::jsonb,
           'properties', jsonb_build_object('camada', 'talhao', 'talhao', g.talhao_num, 'area_ha', round(g.area_ha, 2),
             'status', case when n.talhao_num is null then 'sem_projeto' else 'com_projeto' end,
             'desde_rev', n.desde_rev, 'origem', n.origem, 'catacao', c.talhao_num is not null)) f
    from hub.talhao_geom g
    left join n on n.talhao_num = g.talhao_num
    left join c on c.talhao_num = g.talhao_num
   where g.cod_faz = p_cod_faz
  union all
  select jsonb_build_object('type', 'Feature', 'id', 100000 + n.talhao_num,
           'geometry', ST_AsGeoJSON(ST_Transform(n.geom, 4326), 6)::jsonb,
           'properties', jsonb_build_object('camada', 'talhao', 'talhao', n.talhao_num, 'status', 'fora_da_base',
             'desde_rev', n.desde_rev, 'origem', n.origem))
    from n where not exists (select 1 from hub.talhao_geom g where g.cod_faz = p_cod_faz and g.talhao_num = n.talhao_num)
  union all
  select jsonb_build_object('type', 'Feature', 'geometry', ST_AsGeoJSON(ST_Transform(ST_Union(geom), 4326), 6)::jsonb,
           'properties', jsonb_build_object('camada', 'normal'))
    from n having count(*) > 0
  union all
  select jsonb_build_object('type', 'Feature', 'geometry', ST_AsGeoJSON(ST_Transform(ST_Union(geom), 4326), 6)::jsonb,
           'properties', jsonb_build_object('camada', 'catacao'))
    from c having count(*) > 0)
select jsonb_build_object(
  'type', 'FeatureCollection',
  'features', coalesce((select jsonb_agg(f) from feats), '[]'::jsonb),
  'normal', (select jsonb_build_object('revisao', numero, 'em', criado_em,
                                       'area_ha', (select round(sum(area_ha), 2) from n)) from vig where documento = 'normal'),
  'catacao', (select jsonb_build_object('revisao', numero, 'em', criado_em,
                                        'area_ha', (select round(sum(area_ha), 2) from c)) from vig where documento = 'catacao'),
  'cobertura_pct', (select cobertura_pct from hub.drone_cobertura_v where cod_faz = p_cod_faz));
$$;

create or replace function hub.drone_painel()
returns jsonb language sql stable security definer set search_path = hub as $$
select jsonb_build_object(
  'solicitacoes', coalesce((select jsonb_agg(x order by x->>'criado_em') from (
      select jsonb_build_object('id', s.id, 'cod_faz', s.cod_faz, 'fazenda', f.nome, 'tipo', s.tipo, 'status', s.status,
               'observacao', s.observacao, 'data_desejada', s.data_desejada, 'criado_em', s.criado_em,
               'solicitante', u.nome,
               'geracao', (select jsonb_build_object('id', g.id, 'status', g.status,
                                    'alertas', coalesce(jsonb_array_length(g.alertas), 0),
                                    'publicar_pedido_em', g.publicar_pedido_em, 'publicacao_erro', g.publicacao_erro,
                                    'erro', g.erro)
                             from hub.drone_geracoes g where g.solicitacao_id = s.id and g.status <> 'descartada'
                            order by g.id desc limit 1)) x
        from hub.drone_solicitacoes s
        join hub.fazendas f on f.cod_faz = s.cod_faz
        left join hub.usuarios u on u.id = s.solicitante_id
       where s.origem <> 'legado' and s.status not in ('ok', 'cancelado')) q), '[]'::jsonb),
  'incompletas', coalesce((select jsonb_agg(jsonb_build_object('cod_faz', v.cod_faz, 'fazenda', f.nome,
                                                               'pct', v.cobertura_pct) order by v.cobertura_pct)
                             from hub.drone_cobertura_v v join hub.fazendas f on f.cod_faz = v.cod_faz
                            where v.cobertura_pct < 100), '[]'::jsonb),
  'obstaculos_antigos', coalesce((select jsonb_agg(distinct v.cod_faz)
                             from hub.drone_obstaculo_versoes v
                            where v.vigente and v.enviado_em < now() - make_interval(
                                    months => (select valor::int from hub.drone_parametros
                                                where chave = 'alerta_obstaculos_meses'))), '[]'::jsonb),
  'fora_da_base', coalesce((select jsonb_agg(distinct p.cod_faz)
                             from hub.projetos p
                             join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente and r.documento = 'normal'
                             join hub.drone_revisao_talhoes t on t.revisao_id = r.id
                            where p.modulo_id = 'drone'
                              and not exists (select 1 from hub.talhao_geom g
                                               where g.cod_faz = p.cod_faz and g.talhao_num = t.talhao_num)), '[]'::jsonb));
$$;

create or replace function public.portal_drone_cobertura()
returns table (cod_faz int, cobertura_pct numeric)
language sql stable security definer set search_path = hub as $$
  select cod_faz, cobertura_pct from hub.drone_cobertura_v;
$$;

-- ── segurança ─────────────────────────────────────────────────────────
do $$
declare t text;
begin
  foreach t in array array['talhao_geom', 'drone_revisao_talhoes', 'drone_geracao_talhoes',
                           'drone_envios', 'drone_ajuste_feicoes'] loop
    execute format('alter table hub.%I enable row level security', t);
    execute format('create policy leitura on hub.%I for select to authenticated using (true)', t);
    execute format('grant select on hub.%I to authenticated', t);
    execute format('grant all on hub.%I to service_role', t);
  end loop;
end $$;
grant select on hub.drone_cobertura_v to authenticated, service_role;

do $$
declare f text;
begin
  foreach f in array array[
    'hub.talhao_geom_limpar(timestamptz)', 'hub.drone_talhoes_vigentes(int, text)',
    'hub.drone_gravar_geracao_talhoes(bigint, jsonb)', 'hub.drone_gravar_revisao_talhoes(bigint, jsonb)',
    'hub.drone_pegar_envio()', 'hub.drone_concluir_envio(bigint, text, text)',
    'hub.drone_gravar_ajuste(bigint, text[])', 'hub.drone_ajuste_wkt(bigint)',
    'hub.drone_publicar(int, text, text, int, jsonb, bigint, boolean, jsonb)'] loop
    execute format('revoke all on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
  foreach f in array array[
    'hub.drone_solicitar(int, text, date, text)', 'hub.drone_registrar_envio(int, text, int, bigint, text[])',
    'hub.drone_pedir_geracao(bigint, jsonb)', 'hub.drone_publicar_pedido(bigint, text)',
    'hub.drone_descartar(bigint)', 'hub.drone_mapa_fazenda(int)', 'hub.drone_painel()'] loop
    execute format('revoke all on function %s from public, anon', f);
    execute format('grant execute on function %s to authenticated, service_role', f);
  end loop;
end $$;
revoke all on function public.portal_drone_cobertura() from public;
grant execute on function public.portal_drone_cobertura() to anon, authenticated, service_role;

-- ── storage: envios (editor sobe) e prévias (logado lê) ───────────────
insert into storage.buckets (id, name, public) values ('drone-envios', 'drone-envios', false)
on conflict (id) do nothing;
create policy drone_envios_sobe on storage.objects for insert to authenticated
  with check (bucket_id = 'drone-envios' and hub.pode_editar('drone'));
create policy drone_previas_le on storage.objects for select to authenticated
  using (bucket_id = 'drone-previas');

commit;
