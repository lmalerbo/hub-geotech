-- Hub Geotech — schema unificado "hub" (migration inicial)
--
-- Substitui os schemas separados de project-plantio, project-preparo e
-- Expo_safra (Colheita). Irrigação está fora do escopo.
--
-- Regra de dono de campo: cada coluna alimentada por fonte externa tem UMA
-- única fonte (anotada ao lado). Nenhuma importação escreve em coluna de outra.
--
-- Acesso: RLS ligada em tudo. Usuário logado (authenticated) só lê; escrita
-- das importações usa a service_role (ignora RLS); escrita pela tela virá
-- depois, via funções RPC. O role anon não tem acesso nenhum.
--
-- Depois de rodar: expor o schema "hub" em Project Settings → Data API →
-- Exposed schemas, senão a API não enxerga as tabelas.

begin;

create schema if not exists hub;

create or replace function hub.tocar_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end $$;

-- ── Módulos ────────────────────────────────────────────────────────────────
create table hub.modulos (
  id     text primary key,
  nome   text not null,
  ordem  int  not null,
  ativo  boolean not null default true
);

insert into hub.modulos (id, nome, ordem) values
  ('colheita', 'Colheita',       1),
  ('preparo',  'Preparo',        2),
  ('plantio',  'Plantio',        3),
  ('voo',      'Mapeamento/Voo', 4);

-- ── Fazendas e talhões (núcleo compartilhado) ──────────────────────────────
create table hub.fazendas (
  cod_faz     int  primary key check (cod_faz between 10000 and 99999),
  nome        text not null default '',
  updated_at  timestamptz not null default now()
);

-- layer = cod_faz (5 díg) + talhão (3 díg), ex: 10728 + 11 → 10728011.
-- Calculado pelo próprio banco: nenhuma importação consegue gravar um layer
-- em outro formato (a coluna LAYER das planilhas nunca é usada).
create table hub.talhoes (
  cod_faz            int    not null references hub.fazendas (cod_faz),
  talhao_num         int    not null check (talhao_num between 0 and 999),
  layer              bigint generated always as (cod_faz::bigint * 1000 + talhao_num) stored,
  area_ha            numeric,      -- dono: Base Fazendas (área produtiva real)
  estagio            text,         -- dono: Base Fazendas (estágio vegetativo)
  data_ultimo_corte  date,         -- dono: Base Fazendas
  ciclo              text,
  sist_conser        text,         -- dono: Controle de Conservação (aba CONSERVAÇÃO do PREPARO xlsx)
  sist_conser_em     timestamptz,
  updated_at         timestamptz not null default now(),
  primary key (layer),
  unique (cod_faz, talhao_num)
);

-- ── Usuários e acesso por módulo ───────────────────────────────────────────
create table hub.usuarios (
  id         uuid primary key references auth.users (id) on delete cascade,
  nome       text not null,
  papel      text not null default 'leitura' check (papel in ('editor', 'leitura')),
  admin      boolean not null default false,
  criado_em  timestamptz not null default now()
);

-- Ter a linha = ter acesso ao módulo.
create table hub.usuario_modulos (
  usuario_id  uuid not null references hub.usuarios (id) on delete cascade,
  modulo_id   text not null references hub.modulos (id),
  primary key (usuario_id, modulo_id)
);

-- ── Estado por talhão, específico de cada módulo ───────────────────────────
create table hub.talhao_plantio (
  layer        bigint primary key references hub.talhoes (layer) on delete cascade,
  mes_plantio  date,     -- dono: PLANAGRI
  seq_plantio  text,     -- dono: PLANAGRI (ex: EXPERIMENTO)
  ambiente     text,
  mapeamento   text not null default 'Não' check (mapeamento in ('Sim', 'Não')),
  projeto      text not null default 'Aguard. Map.'
               check (projeto in ('Aguard. Map.', 'Pendente', 'Andamento', 'Ok')),
  updated_at   timestamptz not null default now()
);

create table hub.talhao_preparo (
  layer       bigint primary key references hub.talhoes (layer) on delete cascade,
  status      text,
  tipo_linha  text,
  equipe      text,
  updated_at  timestamptz not null default now()
);

create table hub.talhao_colheita (
  layer                  bigint primary key references hub.talhoes (layer) on delete cascade,
  frente                 text,     -- dono: iCol
  status                 text not null default 'A FAZER'
                         check (status in ('CONCLUIDO', 'A FAZER', 'SEM LINHAS', 'REAVALIAR')),
  tipo_linha             text,
  projeto_desatualizado  boolean not null default false,   -- Regra A (talhão reformado → refazer linhas)
  updated_at             timestamptz not null default now()
);

-- ── Motor genérico de etapas (reaproveitável por módulo novo) ──────────────
create table hub.etapas (
  id         bigint generated always as identity primary key,
  modulo_id  text not null references hub.modulos (id),
  ordem      int  not null,
  nome       text not null,
  escopo     text not null check (escopo in ('fazenda', 'talhao')),
  unique (modulo_id, ordem)
);

-- entidade_id = cod_faz (etapa de escopo fazenda) ou layer (escopo talhão).
create table hub.etapa_status (
  etapa_id      bigint not null references hub.etapas (id),
  entidade_id   bigint not null,
  ok            boolean not null default false,
  usuario_id    uuid references hub.usuarios (id),
  concluido_em  timestamptz,
  observacao    text,
  primary key (etapa_id, entidade_id)
);

insert into hub.etapas (modulo_id, ordem, nome, escopo) values
  ('preparo', 1, 'Identificação', 'fazenda'),
  ('preparo', 2, 'Escoamento',    'fazenda'),
  ('preparo', 3, 'Observações',   'fazenda'),
  ('preparo', 4, 'Preparo',       'fazenda');

-- ── Voos (Drone MGMT) ──────────────────────────────────────────────────────
-- Tradução dos códigos numéricos do Drone MGMT (fonte: geomap/docs/INTEGRACAO_DRONEMANAGEMENT.md).
-- status_hub fica vazio até confirmarmos a correspondência com os 3 estados da spec.
create table hub.voo_codigos (
  campo       text not null check (campo in ('control_status', 'verify_flight_size')),
  codigo      int  not null,
  descricao   text not null,
  status_hub  text,
  primary key (campo, codigo)
);

insert into hub.voo_codigos (campo, codigo, descricao) values
  ('control_status',      1, 'Aguardar plantio'),
  ('control_status',      2, 'A voar'),
  ('control_status',      3, 'Voar novamente'),
  ('control_status',      4, 'Voado / processar imagens'),
  ('control_status',      5, 'Pipeline de processamento'),
  ('control_status',      6, 'Pipeline de processamento'),
  ('control_status',      7, 'Pipeline de processamento'),
  ('control_status',      8, 'Pipeline de processamento'),
  ('control_status',      9, 'Pipeline de processamento'),
  ('control_status',     10, 'Pipeline de processamento'),
  ('control_status',     11, 'Cancelado'),
  ('control_status',     12, 'Importar falhas'),
  ('verify_flight_size',  1, 'Aguardando plantio'),
  ('verify_flight_size',  2, 'Aguardar porte'),
  ('verify_flight_size',  3, 'Verificar porte'),
  ('verify_flight_size',  4, 'Voar'),
  ('verify_flight_size',  5, 'Voo liberado'),
  ('verify_flight_size',  6, 'Voar urgente'),
  ('verify_flight_size',  7, 'Perdeu porte'),
  ('verify_flight_size',  8, 'Aguardar novo voo'),
  ('verify_flight_size',  9, 'Voado'),
  ('verify_flight_size', 10, 'Cancelado');

-- Espelho do que está no Drone MGMT (dono: sync do Drone MGMT, via GeoMap).
-- Sem FK em layer: o Drone MGMT tem registros de talhões fora da nossa base.
create table hub.voo_dronemgmt (
  dronemgmt_id          uuid primary key,
  layer                 bigint,
  projeto_voo           text,       -- ex: 'Falhas Soca'
  control_status        int,
  verify_flight_size    int,
  data_agendada         timestamptz,
  inicio_voo            timestamptz,
  fim_voo               timestamptz,
  modificado_dronemgmt  timestamptz,
  sincronizado_em       timestamptz not null default now()
);
create index voo_dronemgmt_layer_idx on hub.voo_dronemgmt (layer);

-- Fila de voos pedidos pelo Hub (ex: Regra B — Falha Soca após corte + 100 dias).
create table hub.voo_solicitacoes (
  id              bigint generated always as identity primary key,
  layer           bigint not null references hub.talhoes (layer),
  motivo          text not null check (motivo in ('falha_soca', 'preparo')),
  status          text not null default 'aguardando'
                  check (status in ('aguardando', 'liberado', 'agendado', 'voado', 'cancelado')),
  bypass_estagio  boolean not null default false,
  observacao      text,
  apontado_por    uuid references hub.usuarios (id),
  apontado_em     timestamptz not null default now(),
  liberado_em     timestamptz,
  dronemgmt_id    uuid,
  updated_at      timestamptz not null default now()
);
-- No máximo 1 pedido em aberto por talhão e motivo (evita agendar duas vezes).
create unique index voo_solicitacoes_uma_aberta
  on hub.voo_solicitacoes (layer, motivo)
  where status in ('aguardando', 'liberado', 'agendado');

-- ── Auditoria, arquivos e importações ──────────────────────────────────────
create table hub.log_auditoria (
  id              bigint generated always as identity primary key,
  modulo_id       text references hub.modulos (id),
  entidade_tipo   text not null check (entidade_tipo in ('fazenda', 'talhao')),
  entidade_id     bigint not null,
  campo           text not null,
  valor_anterior  text,
  valor_novo      text,
  usuario_id      uuid references hub.usuarios (id),
  origem          text not null default 'usuario',   -- 'usuario' ou o nome da importação automática
  criado_em       timestamptz not null default now()
);
create index log_auditoria_entidade_idx on hub.log_auditoria (entidade_tipo, entidade_id);

-- Metadado do arquivo; o arquivo em si continua no GitHub Releases.
create table hub.arquivos (
  id             bigint generated always as identity primary key,
  cod_faz        int  not null references hub.fazendas (cod_faz),
  modulo_id      text not null references hub.modulos (id),
  nome_arquivo   text not null,
  release_url    text not null,
  publicado_por  uuid references hub.usuarios (id),
  publicado_em   timestamptz not null default now()
);

-- Uma linha por execução de cada importação ("atualizado às X horas" no Hub).
create table hub.execucoes_ingestao (
  id               bigint generated always as identity primary key,
  fonte            text not null
                   check (fonte in ('base_fazendas', 'planagri', 'icol', 'conservacao', 'dronemgmt')),
  iniciado_em      timestamptz not null default now(),
  finalizado_em    timestamptz,
  status           text not null default 'rodando' check (status in ('rodando', 'ok', 'erro')),
  linhas_lidas     int,
  linhas_gravadas  int,
  erro             text
);
create index execucoes_ingestao_fonte_idx on hub.execucoes_ingestao (fonte, iniciado_em desc);

-- ── updated_at automático ──────────────────────────────────────────────────
create trigger fazendas_updated_at         before update on hub.fazendas         for each row execute function hub.tocar_updated_at();
create trigger talhoes_updated_at          before update on hub.talhoes          for each row execute function hub.tocar_updated_at();
create trigger talhao_plantio_updated_at   before update on hub.talhao_plantio   for each row execute function hub.tocar_updated_at();
create trigger talhao_preparo_updated_at   before update on hub.talhao_preparo   for each row execute function hub.tocar_updated_at();
create trigger talhao_colheita_updated_at  before update on hub.talhao_colheita  for each row execute function hub.tocar_updated_at();
create trigger voo_solicitacoes_updated_at before update on hub.voo_solicitacoes for each row execute function hub.tocar_updated_at();

-- ── Segurança: RLS em tudo, leitura só para usuário logado ─────────────────
do $$
declare t text;
begin
  for t in select tablename from pg_tables where schemaname = 'hub' loop
    execute format('alter table hub.%I enable row level security', t);
    execute format('create policy leitura_autenticado on hub.%I for select to authenticated using (true)', t);
  end loop;
end $$;

grant usage on schema hub to authenticated, service_role;
grant select on all tables in schema hub to authenticated;
grant all on all tables in schema hub to service_role;
grant usage, select on all sequences in schema hub to service_role;
alter default privileges in schema hub grant select on tables to authenticated;
alter default privileges in schema hub grant all on tables to service_role;
alter default privileges in schema hub grant usage, select on sequences to service_role;

commit;
