-- Stub das tabelas do Drone que hub.drone_projetos_v lê (a migração real usa PostGIS).
insert into hub.modulos (id, nome, ordem) values ('drone', 'Drone', 5) on conflict (id) do nothing;
create table hub.drone_solicitacoes (
  id bigint generated always as identity primary key,
  cod_faz int, tipo text, status text, revisao_id bigint references hub.projeto_revisoes (id), concluido_em timestamptz);
create table hub.drone_geracoes (
  id bigint generated always as identity primary key,
  solicitacao_id bigint references hub.drone_solicitacoes (id), status text, resumo jsonb, concluido_em timestamptz);
-- Stub do que hub.drone_encerrar_projeto usa.
alter table hub.drone_solicitacoes add column origem text default 'formulario', add column cancelado_motivo text,
  add column cancelado_por uuid;
alter table hub.drone_geracoes add column publicar_pedido_em timestamptz, add column publicacao_erro text;
create table hub.talhao_geom (cod_faz int, talhao_num int, primary key (cod_faz, talhao_num));
