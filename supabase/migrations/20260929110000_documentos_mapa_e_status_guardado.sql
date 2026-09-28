-- Ajustes a partir do sistema atual:
-- 1) Status "Ag. Mapa" no Plantio (Andamento → Ag. Mapa → Ok).
-- 2) Revisão por TIPO DE DOCUMENTO: cada documento do projeto tem sua própria
--    numeração e sua revisão vigente (ex: planta Rev1 com escoamento Rev0).
--    O motivo é obrigatório a partir da revisão 1 em qualquer documento.
-- 3) Mapa anexado → Ok: no Plantio o mapa é o .pdf da revisão vigente do
--    documento "projeto" (mesmo nome do .dwg, só muda a extensão). Anexá-lo
--    leva os talhões da fazenda que estão em "Ag. Mapa" para "Ok".
-- 4) Status guardado de talhões do sistema antigo que ainda não estão na Base
--    Fazendas; restaurado automaticamente quando a Base cadastrar o talhão.
-- 5) Equipe do Preparo não é usada.

begin;

-- 1 ─────────────────────────────────────────────────────────────────────────
alter table hub.talhao_plantio drop constraint talhao_plantio_projeto_check;
alter table hub.talhao_plantio add constraint talhao_plantio_projeto_check
  check (projeto in ('Aguard. Map.', 'Pendente', 'Andamento', 'Ag. Mapa', 'Ok'));

-- 2 ─────────────────────────────────────────────────────────────────────────
-- marcador = prefixo da numeração no nome do arquivo; sufixo = o que vem
-- depois do número (ex: Rev1-Escoamento.pdf).
create table hub.documento_tipos (
  modulo_id  text not null references hub.modulos (id),
  codigo     text not null,
  nome       text not null,
  marcador   text not null check (marcador in ('Rev', 'Exp')),
  sufixo     text not null default '',
  ordem      int  not null,
  primary key (modulo_id, codigo)
);

insert into hub.documento_tipos (modulo_id, codigo, nome, marcador, sufixo, ordem) values
  ('plantio', 'projeto',        'Projeto (.dwg) e Mapa de Plantio (.pdf)', 'Rev', '',                 1),
  ('plantio', 'exportacao',     'Exportação',                              'Exp', '',                 2),
  ('preparo', 'projeto',        'Projeto',                                 'Rev', '',                 1),
  ('preparo', 'exportacao',     'Exportação',                              'Exp', '',                 2),
  ('preparo', 'escoamento',     'Escoamento',                              'Rev', '-Escoamento',      3),
  ('preparo', 'sistematizacao', 'Sistematização',                          'Rev', '-Sistematizacao',  4);

alter table hub.projeto_revisoes add column documento text not null default 'projeto';
alter table hub.projeto_revisoes alter column documento drop default;
alter table hub.projeto_revisoes drop constraint projeto_revisoes_projeto_id_numero_key;
drop index hub.projeto_revisoes_uma_vigente;
alter table hub.projeto_revisoes add constraint projeto_revisoes_documento_numero_key
  unique (projeto_id, documento, numero);
create unique index projeto_revisoes_uma_vigente
  on hub.projeto_revisoes (projeto_id, documento) where vigente;

drop view hub.arquivos_vigentes;
create view hub.arquivos_vigentes with (security_invoker = true) as
select p.id        as projeto_id,
       p.modulo_id,
       p.tipo,
       p.cod_faz,
       p.nome      as projeto,
       r.documento,
       r.id        as revisao_id,
       r.numero    as revisao,
       a.nome_arquivo,
       a.release_url,
       a.tamanho_bytes,
       a.publicado_em
  from hub.projetos p
  join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente
  join hub.revisao_arquivos a on a.revisao_id = r.id;
grant select on hub.arquivos_vigentes to authenticated, service_role;

drop function hub.nova_revisao(bigint, text, bigint[]);

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

  if coalesce(auth.role(), '') <> 'service_role' and not exists (
       select 1
         from hub.usuarios u
        where u.id = auth.uid()
          and (u.admin
               or (u.papel = 'editor'
                   and exists (select 1 from hub.usuario_modulos m
                                where m.usuario_id = u.id and m.modulo_id = v_modulo)))) then
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

-- 3 ─────────────────────────────────────────────────────────────────────────
create or replace function hub.mapa_anexado()
returns trigger
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_rev  hub.projeto_revisoes;
  v_proj hub.projetos;
begin
  if lower(new.nome_arquivo) not like '%.pdf' then
    return new;
  end if;
  select * into v_rev from hub.projeto_revisoes where id = new.revisao_id;
  if not v_rev.vigente or v_rev.documento <> 'projeto' then
    return new;
  end if;
  select * into v_proj from hub.projetos where id = v_rev.projeto_id;
  if v_proj.modulo_id <> 'plantio' then
    return new;
  end if;

  -- Fazendas do projeto: a própria (individual) ou as das origens (personalizado).
  with fazendas as (
    select v_proj.cod_faz as cod_faz where v_proj.tipo = 'individual'
    union
    select po.cod_faz
      from hub.revisao_origens o
      join hub.projeto_revisoes ro on ro.id = o.origem_revisao_id
      join hub.projetos po on po.id = ro.projeto_id
     where o.revisao_id = v_rev.id
  ), mudou as (
    update hub.talhao_plantio p
       set projeto = 'Ok'
      from hub.talhoes t
     where t.layer = p.layer
       and t.cod_faz in (select cod_faz from fazendas)
       and p.projeto = 'Ag. Mapa'
    returning p.layer
  )
  insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo, usuario_id, origem)
  select 'plantio', 'talhao', m.layer, 'projeto', 'Ag. Mapa', 'Ok', new.publicado_por, 'mapa_anexado'
    from mudou m;

  return new;
end $$;

create trigger revisao_arquivos_mapa_anexado
  after insert on hub.revisao_arquivos
  for each row execute function hub.mapa_anexado();

-- 4 ─────────────────────────────────────────────────────────────────────────
-- Talhões do Plantio antigo que ainda não existem na Base Fazendas (opção B:
-- não entram no Hub até a Base cadastrar). O estado deles fica guardado aqui.
create table hub.plantio_status_guardado (
  layer        bigint primary key,
  mes_plantio  date,
  seq_plantio  text,
  mapeamento   text not null,
  projeto      text not null,
  origem       text not null default 'sistema_antigo',
  guardado_em  timestamptz not null default now()
);

-- Roda na rodada diária, depois das importações: talhão guardado que já
-- existe na Base volta pro Plantio com o estado que tinha.
create or replace function hub.restaurar_status_guardado()
returns int
language plpgsql
set search_path = hub
as $$
declare
  v_qtd int;
begin
  with prontos as (
    delete from hub.plantio_status_guardado g
     using hub.talhoes t
     where t.layer = g.layer
    returning g.*
  ), gravados as (
    insert into hub.talhao_plantio (layer, mes_plantio, seq_plantio, mapeamento, projeto)
    select layer, mes_plantio, seq_plantio, mapeamento, projeto from prontos
    on conflict (layer) do update
      set mapeamento  = excluded.mapeamento,
          projeto     = excluded.projeto,
          seq_plantio = coalesce(hub.talhao_plantio.seq_plantio, excluded.seq_plantio)
    returning layer, projeto
  ), registro as (
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, origem)
    select 'plantio', 'talhao', layer, 'projeto', projeto, 'restaurado_sistema_antigo' from gravados
    returning 1
  )
  select count(*) into v_qtd from registro;
  return v_qtd;
end $$;

revoke all on function hub.restaurar_status_guardado() from public, anon, authenticated;
grant execute on function hub.restaurar_status_guardado() to service_role;

-- 5 ─────────────────────────────────────────────────────────────────────────
alter table hub.talhao_preparo drop column equipe;

-- Segurança nas tabelas novas.
alter table hub.documento_tipos         enable row level security;
alter table hub.plantio_status_guardado enable row level security;
create policy leitura_autenticado on hub.documento_tipos         for select to authenticated using (true);
create policy leitura_autenticado on hub.plantio_status_guardado for select to authenticated using (true);

commit;
