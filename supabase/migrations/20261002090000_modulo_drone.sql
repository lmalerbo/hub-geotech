-- Módulo Drone, Parte 1: parâmetros, insumos (obstáculos/infestação),
-- solicitações e fila de gerações. O agente do servidor Geo usa a
-- service_role; as telas (Parte 2) terão RPCs próprias com permissão.
-- Spec: docs/superpowers/specs/2026-09-29-modulo-drone-parte1-design.md

begin;

create extension if not exists postgis with schema extensions;

insert into hub.modulos (id, nome, ordem) values ('drone', 'Drone', 5)
on conflict (id) do nothing;

-- papel novo: solicitante (abre e acompanha pedidos; não edita projeto)
alter table hub.usuarios drop constraint if exists usuarios_papel_check;
alter table hub.usuarios add constraint usuarios_papel_check
  check (papel in ('editor', 'leitura', 'solicitante'));

insert into hub.documento_tipos (modulo_id, codigo, nome, marcador, sufixo, ordem, extensoes) values
  ('drone', 'normal',  'Aplicação Normal',  'Rev', '-Normal',  1, array['zip', 'pdf']),
  ('drone', 'catacao', 'Aplicação Catação', 'Rev', '-Catacao', 2, array['zip', 'pdf'])
on conflict do nothing;

create table hub.drone_parametros (
  chave         text primary key,
  valor         text not null,
  descricao     text,
  atualizado_em timestamptz not null default now()
);
insert into hub.drone_parametros (chave, valor, descricao) values
  ('taxa_l_ha',                 '10',   'Taxa gravada no shape de aplicação (l/ha)'),
  ('margem_infestacao_m',       '10',   'Expansão do shape de infestação antes do recorte (m)'),
  ('alerta_aproveitamento_min', '0.30', 'Aplicável/AREA_PROD abaixo disso gera alerta'),
  ('alerta_obstaculos_meses',   '24',   'Obstáculos mais antigos que isso geram alerta'),
  ('agente_ultimo_ciclo',       '',     'Sinal de vida do agente (ISO 8601)');

create table hub.drone_classes_restricao (
  classe_m      int primary key check (classe_m in (15, 25, 50)),
  distancia_m   numeric not null check (distancia_m > 0),
  categorias    text not null,
  atualizado_em timestamptz not null default now()
);
insert into hub.drone_classes_restricao (classe_m, distancia_m, categorias) values
  (15, 15, 'Árvore isolada'),
  (25, 25, 'Rede de energia padrão'),
  (50, 50, 'Rede de alta tensão, sede/casa, APP/mata/vegetação nativa, zona urbana, cultura vizinha, pasto, rodovia, represa');

create table hub.drone_obstaculo_versoes (
  id             bigint generated always as identity primary key,
  cod_faz        int  not null references hub.fazendas (cod_faz),
  classe_m       int  not null references hub.drone_classes_restricao (classe_m),
  versao         int  not null,
  vigente        boolean not null default true,
  origem         text not null check (origem in ('upload', 'legado')),
  arquivo_origem text,
  n_feicoes      int  not null default 0,
  enviado_por    uuid references hub.usuarios (id),
  enviado_em     timestamptz not null default now(),
  unique (cod_faz, classe_m, versao)
);
create unique index drone_obstaculo_uma_vigente
  on hub.drone_obstaculo_versoes (cod_faz, classe_m) where vigente;

create table hub.drone_obstaculo_feicoes (
  versao_id bigint not null references hub.drone_obstaculo_versoes (id) on delete cascade,
  geom      extensions.geometry(Geometry, 31983) not null
);
create index on hub.drone_obstaculo_feicoes (versao_id);

create table hub.drone_solicitacoes (
  id               bigint generated always as identity primary key,
  cod_faz          int  not null references hub.fazendas (cod_faz),
  tipo             text not null check (tipo in ('normal', 'catacao')),
  origem           text not null check (origem in ('formulario', 'dronemgmt', 'legado')),
  solicitante_id   uuid references hub.usuarios (id),
  data_desejada    date,
  status           text not null default 'solicitado' check (status in (
                     'solicitado', 'aguardando_obstaculos', 'aguardando_infestacao',
                     'em_elaboracao', 'ok', 'devolvido', 'cancelado')),
  responsavel_id   uuid references hub.usuarios (id),
  motivo_devolucao text,
  revisao_id       bigint references hub.projeto_revisoes (id),
  criado_em        timestamptz not null default now(),
  iniciado_em      timestamptz,
  concluido_em     timestamptz
);

create table hub.drone_infestacoes (
  id             bigint generated always as identity primary key,
  cod_faz        int not null references hub.fazendas (cod_faz),
  solicitacao_id bigint references hub.drone_solicitacoes (id),
  empresa        text,
  arquivo_origem text,
  n_feicoes      int not null default 0,
  enviado_por    uuid references hub.usuarios (id),
  enviado_em     timestamptz not null default now()
);
create table hub.drone_infestacao_feicoes (
  infestacao_id bigint not null references hub.drone_infestacoes (id) on delete cascade,
  geom          extensions.geometry(Geometry, 31983) not null
);
create index on hub.drone_infestacao_feicoes (infestacao_id);

create table hub.drone_geracoes (
  id                     bigint generated always as identity primary key,
  solicitacao_id         bigint not null references hub.drone_solicitacoes (id),
  status                 text not null default 'fila' check (status in (
                           'fila', 'processando', 'pronta', 'erro', 'publicada', 'descartada')),
  infestacao_id          bigint references hub.drone_infestacoes (id),
  pedido_por             uuid references hub.usuarios (id),
  pedido_em              timestamptz not null default now(),
  iniciado_em            timestamptz,
  concluido_em           timestamptz,
  orientacao             text check (orientacao in ('retrato', 'paisagem')),
  insumos                jsonb,
  resumo                 jsonb,
  alertas                jsonb,
  erro                   text,
  previa_pdf             text,
  previa_zip             text,
  publicar_pedido_em     timestamptz,
  publicar_motivo        text,
  publicar_por           uuid references hub.usuarios (id),
  publicacao_iniciada_em timestamptz,
  publicacao_erro        text
);
create index on hub.drone_geracoes (status, pedido_em);

-- ── log das mudanças de status (entidade = fazenda) ────────────────────
create or replace function hub.drone_log_solicitacao()
returns trigger language plpgsql security definer set search_path = hub as $$
begin
  if tg_op = 'INSERT' or new.status is distinct from old.status then
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo,
                                   valor_anterior, valor_novo, usuario_id, origem)
    values ('drone', 'fazenda', new.cod_faz, 'solicitacao ' || new.id || ' (' || new.tipo || ')',
            case when tg_op = 'UPDATE' then old.status end, new.status, auth.uid(),
            case when auth.role() = 'service_role' then 'agente_drone' else 'usuario' end);
  end if;
  return new;
end $$;

-- ── status inicial: sem obstáculos / sem infestação ────────────────────
create or replace function hub.drone_status_inicial()
returns trigger language plpgsql security definer set search_path = hub as $$
begin
  if new.origem <> 'legado' and new.status = 'solicitado' then
    if new.tipo = 'normal' and not exists (
         select 1 from hub.drone_obstaculo_versoes v where v.cod_faz = new.cod_faz and v.vigente) then
      new.status := 'aguardando_obstaculos';
    elsif new.tipo = 'catacao' then
      new.status := 'aguardando_infestacao';
    end if;
  end if;
  return new;
end $$;

create trigger drone_solicitacao_status_inicial before insert on hub.drone_solicitacoes
  for each row execute function hub.drone_status_inicial();
create trigger drone_solicitacao_log after insert or update of status on hub.drone_solicitacoes
  for each row execute function hub.drone_log_solicitacao();

create or replace function hub.drone_log_geracao()
returns trigger language plpgsql security definer set search_path = hub as $$
begin
  if tg_op = 'INSERT' or new.status is distinct from old.status then
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo,
                                   valor_anterior, valor_novo, usuario_id, origem)
    select 'drone', 'fazenda', s.cod_faz, 'geracao ' || new.id || ' (solicitacao ' || s.id || ')',
           case when tg_op = 'UPDATE' then old.status end, new.status, auth.uid(),
           case when auth.role() = 'service_role' then 'agente_drone' else 'usuario' end
      from hub.drone_solicitacoes s where s.id = new.solicitacao_id;
  end if;
  return new;
end $$;

create trigger drone_geracao_log after insert or update of status on hub.drone_geracoes
  for each row execute function hub.drone_log_geracao();

-- ── insumos ────────────────────────────────────────────────────────────
create or replace function hub.drone_gravar_obstaculos(
  p_cod_faz int, p_classe_m int, p_origem text, p_arquivo text, p_wkts text[], p_usuario uuid default null)
returns bigint language plpgsql security definer set search_path = hub, extensions as $$
declare v_versao int; v_id bigint;
begin
  perform pg_advisory_xact_lock(hashtext('drone_obst_' || p_cod_faz || '_' || p_classe_m));
  select coalesce(max(versao), 0) + 1 into v_versao
    from hub.drone_obstaculo_versoes where cod_faz = p_cod_faz and classe_m = p_classe_m;
  update hub.drone_obstaculo_versoes set vigente = false
   where cod_faz = p_cod_faz and classe_m = p_classe_m and vigente;
  insert into hub.drone_obstaculo_versoes (cod_faz, classe_m, versao, origem, arquivo_origem, n_feicoes, enviado_por)
  values (p_cod_faz, p_classe_m, v_versao, p_origem, p_arquivo, coalesce(array_length(p_wkts, 1), 0), p_usuario)
  returning id into v_id;
  insert into hub.drone_obstaculo_feicoes (versao_id, geom)
  select v_id, ST_Force2D(ST_GeomFromText(w, 31983)) from unnest(p_wkts) w;
  update hub.drone_solicitacoes set status = 'solicitado'
   where cod_faz = p_cod_faz and tipo = 'normal' and status = 'aguardando_obstaculos';
  return v_id;
end $$;

create or replace function hub.drone_gravar_infestacao(
  p_solicitacao_id bigint, p_empresa text, p_arquivo text, p_wkts text[], p_usuario uuid default null)
returns bigint language plpgsql security definer set search_path = hub, extensions as $$
declare v_sol hub.drone_solicitacoes; v_id bigint;
begin
  select * into v_sol from hub.drone_solicitacoes where id = p_solicitacao_id;
  if v_sol.id is null or v_sol.tipo <> 'catacao' then
    raise exception 'Solicitação % não é uma catação', p_solicitacao_id;
  end if;
  insert into hub.drone_infestacoes (cod_faz, solicitacao_id, empresa, arquivo_origem, n_feicoes, enviado_por)
  values (v_sol.cod_faz, v_sol.id, p_empresa, p_arquivo, coalesce(array_length(p_wkts, 1), 0), p_usuario)
  returning id into v_id;
  insert into hub.drone_infestacao_feicoes (infestacao_id, geom)
  select v_id, ST_Force2D(ST_GeomFromText(w, 31983)) from unnest(p_wkts) w;
  update hub.drone_solicitacoes set status = 'solicitado'
   where id = v_sol.id and status = 'aguardando_infestacao';
  return v_id;
end $$;

create or replace function hub.drone_obstaculos_vigentes(p_cod_faz int)
returns table (classe_m int, versao_id bigint, enviado_em timestamptz, wkt text)
language sql stable security definer set search_path = hub, extensions as $$
  select v.classe_m, v.id, v.enviado_em, ST_AsText(f.geom)
    from hub.drone_obstaculo_versoes v join hub.drone_obstaculo_feicoes f on f.versao_id = v.id
   where v.cod_faz = p_cod_faz and v.vigente;
$$;

create or replace function hub.drone_infestacao_wkt(p_infestacao_id bigint)
returns table (wkt text)
language sql stable security definer set search_path = hub, extensions as $$
  select ST_AsText(geom) from hub.drone_infestacao_feicoes where infestacao_id = p_infestacao_id;
$$;

-- ── fila ───────────────────────────────────────────────────────────────
create or replace function hub.drone_pegar_geracao()
returns setof hub.drone_geracoes language plpgsql security definer set search_path = hub as $$
begin
  update hub.drone_geracoes set status = 'fila', iniciado_em = null
   where status = 'processando' and iniciado_em < now() - interval '15 minutes';
  return query
  update hub.drone_geracoes g set status = 'processando', iniciado_em = now()
   where g.id = (select id from hub.drone_geracoes where status = 'fila'
                  order by pedido_em for update skip locked limit 1)
  returning g.*;
end $$;

create or replace function hub.drone_pegar_publicacao()
returns setof hub.drone_geracoes language plpgsql security definer set search_path = hub as $$
begin
  update hub.drone_geracoes set publicacao_iniciada_em = null
   where status = 'pronta' and publicacao_iniciada_em < now() - interval '15 minutes';
  return query
  update hub.drone_geracoes g set publicacao_iniciada_em = now(), publicacao_erro = null
   where g.id = (select id from hub.drone_geracoes
                  where status = 'pronta' and publicar_pedido_em is not null
                    and publicacao_iniciada_em is null and publicacao_erro is null
                  order by publicar_pedido_em for update skip locked limit 1)
  returning g.*;
end $$;

-- ── publicação (uma transação: revisão + arquivos + geração + solicitação) ──
-- O agente sobe os arquivos no GitHub ANTES de chamar esta função, já com o
-- nome da revisão p_numero. Se o número mudou nesse meio tempo, nada é gravado.
create or replace function hub.drone_publicar(
  p_cod_faz int, p_documento text, p_motivo text, p_numero int, p_arquivos jsonb,
  p_geracao_id bigint default null, p_legado boolean default false)
returns bigint language plpgsql security definer set search_path = hub as $$
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
    update hub.drone_geracoes set status = 'publicada', concluido_em = now()
     where id = p_geracao_id and status = 'pronta' returning solicitacao_id into v_sol;
    if v_sol is null then
      raise exception 'Geração % não está pronta para publicar', p_geracao_id;
    end if;
    update hub.drone_geracoes set status = 'descartada'
     where solicitacao_id = v_sol and id <> p_geracao_id and status in ('fila', 'pronta', 'erro');
    update hub.drone_solicitacoes set status = 'ok', revisao_id = v_rev, concluido_em = now()
     where id = v_sol;
  end if;

  if p_legado then
    insert into hub.drone_solicitacoes (cod_faz, tipo, origem, status, revisao_id, concluido_em)
    values (p_cod_faz, p_documento, 'legado', 'ok', v_rev, now());
  end if;
  return v_rev;
end $$;

-- ── segurança ──────────────────────────────────────────────────────────
do $$
declare t text;
begin
  foreach t in array array['drone_parametros', 'drone_classes_restricao', 'drone_obstaculo_versoes',
                           'drone_obstaculo_feicoes', 'drone_infestacoes', 'drone_infestacao_feicoes',
                           'drone_solicitacoes', 'drone_geracoes'] loop
    execute format('alter table hub.%I enable row level security', t);
    execute format('create policy leitura on hub.%I for select to authenticated using (true)', t);
    execute format('grant select on hub.%I to authenticated', t);
    execute format('grant all on hub.%I to service_role', t);
  end loop;
end $$;

do $$
declare f text;
begin
  foreach f in array array[
    'hub.drone_gravar_obstaculos(int, int, text, text, text[], uuid)',
    'hub.drone_gravar_infestacao(bigint, text, text, text[], uuid)',
    'hub.drone_obstaculos_vigentes(int)', 'hub.drone_infestacao_wkt(bigint)',
    'hub.drone_pegar_geracao()', 'hub.drone_pegar_publicacao()',
    'hub.drone_publicar(int, text, text, int, jsonb, bigint, boolean)'] loop
    execute format('revoke all on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
end $$;

-- prévias temporárias (privado; só service_role grava)
insert into storage.buckets (id, name, public) values ('drone-previas', 'drone-previas', false)
on conflict (id) do nothing;

commit;
