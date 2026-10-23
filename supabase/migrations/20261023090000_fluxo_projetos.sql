-- Fluxo de projetos do Plantio e do Preparo (spec docs/superpowers/specs/2026-10-23-fluxo-projetos-design.md).
--
-- 1) Registro: log_auditoria ganha justificativa e lote_id (uma ação = um lote; o desfazer usa o lote).
-- 2) Preparo por talhão: talhao_preparo.etapa, como talhao_plantio.projeto. Cada talhão herda a etapa
--    da sua fazenda (a primeira etapa não concluída; todas concluídas = Ok). hub.etapa_status do Preparo
--    fica como histórico — só a observação da etapa Observações continua sendo gravada lá.
-- 3) Revisão numerada por fazenda: a próxima revisão do projeto é o maior número entre todos os
--    documentos + 1. Cada documento que muda ganha uma linha (projeto, documento, número); o documento
--    que não muda continua valendo da revisão anterior. As revisões antigas não são renumeradas
--    (o número está no nome dos arquivos publicados): unificada = false.
--    Revisão aberta: enviar um arquivo sem pedir revisão nova completa a última revisão da fazenda
--    (se o documento ainda não está nela, entra nela).
--    revisao_talhoes: talhões que a revisão traz (novo) ou altera (alterado). Ficam presos à primeira
--    linha da revisão (a de menor id entre as linhas com o mesmo projeto e número).
-- 4) Arquivo vigente, no Plantio e no Preparo, é por documento e extensão: o da revisão mais recente
--    que contém um arquivo daquela extensão (ex.: projeto .dwg da Rev1 com o mapa .pdf da Rev2).
--    arquivos_vigentes e o portal mantêm as mesmas colunas. Colheita e Drone seguem como estavam.
-- 5) RPCs do contrato: projeto_avancar, projeto_retroceder, projeto_desfazer, projeto_nova_revisao,
--    projeto_linha_do_tempo. p_talhoes são os números dos talhões da fazenda (talhao_num).
-- 6) As RPCs antigas (plantio_*, preparo_*) passam a chamar as novas, para a tela atual continuar
--    funcionando até a tela nova entrar.

begin;

-- 1 ─────────────────────────────────────────────────────────────────────────
alter table hub.log_auditoria add column justificativa text, add column lote_id bigint;
create index log_auditoria_lote_idx on hub.log_auditoria (lote_id) where lote_id is not null;
create sequence hub.log_lote_seq;

-- 2 ─────────────────────────────────────────────────────────────────────────
alter table hub.talhao_preparo add column etapa text not null default 'Identificação'
  constraint talhao_preparo_etapa_check
  check (etapa in ('Identificação', 'Escoamento', 'Observações', 'Preparo', 'Ok'));

update hub.talhao_preparo tp
   set etapa = coalesce((select e.nome from hub.etapas e
                          where e.modulo_id = 'preparo'
                            and not exists (select 1 from hub.etapa_status s
                                             where s.etapa_id = e.id and s.entidade_id = t.cod_faz and s.ok)
                          order by e.ordem
                          limit 1), 'Ok')
  from hub.talhoes t
 where t.layer = tp.layer;

-- Etapas de cada módulo, na ordem (o valor guardado é a etapa em que o talhão está).
create or replace function hub.projeto_etapas(p_modulo text)
returns text[] language sql immutable as $$
  select case p_modulo
           when 'plantio' then array['Aguard. Map.', 'Pendente', 'Andamento', 'Ag. Mapa', 'Ok']
           when 'preparo' then array['Identificação', 'Escoamento', 'Observações', 'Preparo', 'Ok']
         end;
$$;

create or replace function hub.projeto_ordem(p_modulo text, p_etapa text)
returns int language sql immutable as $$
  select array_position(hub.projeto_etapas(p_modulo), p_etapa) - 1;
$$;

-- Ações de avanço. exige = 'documento.extensão' que precisam estar enviados.
create or replace function hub.projeto_acoes(p_modulo text, p_acao text default null)
returns table (acao text, de text, para text, so_mapeados boolean, mapeamento text, exige text[], falta text)
language sql immutable as $$
  select a.acao, a.de, a.para, a.so_mapeados, a.mapeamento, a.exige, a.falta
    from (values
      ('plantio', 'mapeamento_concluido', 'Aguard. Map.',  'Pendente',    false, 'Sim', '{}'::text[], null::text),
      ('plantio', 'iniciar',              'Pendente',      'Andamento',   true,  null,  '{}', null),
      ('plantio', 'exportacao_enviada',   'Andamento',     'Ag. Mapa',    false, null,  '{exportacao.zip,projeto.dwg}',
       'Envie a exportação (.zip) e o projeto (.dwg) antes de avançar'),
      ('preparo', 'identificacao',        'Identificação', 'Escoamento',  false, null,  '{}', null),
      ('preparo', 'escoamento',           'Escoamento',    'Observações', false, null,  '{escoamento.pdf}',
       'Envie o Mapa de Escoamento (.pdf) antes de concluir'),
      ('preparo', 'observacoes',          'Observações',   'Preparo',     false, null,  '{}', null),
      ('preparo', 'preparo',              'Preparo',       'Ok',          false, null,
       '{projeto.dwg,exportacao.zip,sistematizacao.pdf}',
       'Envie os 3 arquivos (projeto .dwg, exportação .zip e sistematização .pdf) antes de concluir')
    ) a (modulo, acao, de, para, so_mapeados, mapeamento, exige, falta)
   where a.modulo = p_modulo and (p_acao is null or a.acao = p_acao);
$$;

-- Talhões da fazenda no módulo, com a etapa atual.
create or replace function hub.projeto_talhoes(p_modulo text, p_cod_faz int)
returns table (layer bigint, talhao_num int, etapa text, mapeamento text)
language sql stable security definer set search_path = hub as $$
  select t.layer, t.talhao_num, p.projeto, p.mapeamento
    from hub.talhao_plantio p join hub.talhoes t on t.layer = p.layer
   where p_modulo = 'plantio' and t.cod_faz = p_cod_faz
  union all
  select t.layer, t.talhao_num, p.etapa, null
    from hub.talhao_preparo p join hub.talhoes t on t.layer = p.layer
   where p_modulo = 'preparo' and t.cod_faz = p_cod_faz;
$$;

-- Muda a etapa dos talhões dados e registra cada mudança no lote. Voltar o Plantio para
-- Aguard. Map. zera o mapeamento (p_mapeamento = 'Não'); o mapeamento também entra no registro,
-- para o desfazer devolver exatamente o que era.
create or replace function hub.projeto_mudar_etapa(
  p_modulo        text,
  p_layers        bigint[],
  p_para          text,
  p_lote          bigint,
  p_origem        text,
  p_justificativa text default null,
  p_mapeamento    text default null
)
returns int
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_qtd int;
begin
  if p_modulo = 'plantio' then
    with antes as (
      select p.layer, p.projeto, p.mapeamento from hub.talhao_plantio p
       where p.layer = any(p_layers)
         and (p.projeto <> p_para or p.mapeamento <> coalesce(p_mapeamento, p.mapeamento))
         for update
    ), mudou as (
      update hub.talhao_plantio p
         set projeto = p_para, mapeamento = coalesce(p_mapeamento, p.mapeamento)
        from antes a
       where a.layer = p.layer
      returning p.layer, a.projeto as de, a.mapeamento as map_de, p.mapeamento as map_para
    ), registro as (
      insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo,
                                     usuario_id, origem, justificativa, lote_id)
      select 'plantio', 'talhao', m.layer, c.campo, c.de, c.para, auth.uid(), p_origem, p_justificativa, p_lote
        from mudou m
        cross join lateral (values ('projeto', m.de, p_para), ('mapeamento', m.map_de, m.map_para)) c (campo, de, para)
       where c.de <> c.para
      returning campo
    )
    select count(*) filter (where campo = 'projeto') into v_qtd from registro;
  else
    with antes as (
      select p.layer, p.etapa from hub.talhao_preparo p
       where p.layer = any(p_layers) and p.etapa <> p_para
         for update
    ), mudou as (
      update hub.talhao_preparo p set etapa = p_para
        from antes a
       where a.layer = p.layer
      returning p.layer, a.etapa as de
    ), registro as (
      insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo,
                                     usuario_id, origem, justificativa, lote_id)
      select 'preparo', 'talhao', m.layer, 'etapa', m.de, p_para, auth.uid(), p_origem, p_justificativa, p_lote
        from mudou m
      returning 1
    )
    select count(*) into v_qtd from registro;
  end if;
  return v_qtd;
end $$;

-- Módulo válido + quem chamou pode editar + trava a fazenda/módulo até o fim da transação
-- (duas ações ao mesmo tempo na mesma fazenda viram fila).
create or replace function hub.projeto_conferir(p_modulo text, p_cod_faz int)
returns void
language plpgsql
security definer
set search_path = hub
as $$
begin
  if p_modulo is null or p_modulo not in ('plantio', 'preparo') then
    raise exception 'Módulo inválido: % (use plantio ou preparo)', p_modulo;
  end if;
  if not hub.pode_editar(p_modulo) then
    raise exception 'Sem permissão para editar o %', initcap(p_modulo);
  end if;
  perform pg_advisory_xact_lock(hashtext('projeto:' || p_modulo || ':' || p_cod_faz));
end $$;

-- 3 ─────────────────────────────────────────────────────────────────────────
alter table hub.projeto_revisoes add column unificada boolean not null default false;
comment on column hub.projeto_revisoes.unificada is
  'Revisão com a numeração única da fazenda (Plantio/Preparo, desde 23/10/2026). As antigas ficam false.';

create table hub.revisao_talhoes (
  revisao_id  bigint not null references hub.projeto_revisoes (id) on delete cascade,
  layer       bigint not null references hub.talhoes (layer) on delete cascade,
  tipo        text   not null check (tipo in ('novo', 'alterado')),
  primary key (revisao_id, layer)
);
alter table hub.revisao_talhoes enable row level security;
create policy leitura_autenticado on hub.revisao_talhoes for select to authenticated using (true);
grant select on hub.revisao_talhoes to authenticated;
grant all on hub.revisao_talhoes to service_role;

create or replace function hub.ext_arquivo(p_nome text)
returns text language sql immutable as $$
  select lower(substring(p_nome from '\.([^./]+)$'));
$$;

-- Projeto individual da fazenda no módulo (cria se p_criar e ainda não existir).
create or replace function hub.projeto_individual(p_modulo text, p_cod_faz int, p_criar boolean)
returns bigint
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_id      bigint;
  v_fazenda text;
begin
  select id into v_id from hub.projetos
   where modulo_id = p_modulo and tipo = 'individual' and cod_faz = p_cod_faz;
  if v_id is null and p_criar then
    select nome into v_fazenda from hub.fazendas where cod_faz = p_cod_faz;
    if v_fazenda is null then
      raise exception 'Fazenda % não existe na Base Fazendas', p_cod_faz;
    end if;
    insert into hub.projetos (modulo_id, tipo, cod_faz, nome, criado_por)
    values (p_modulo, 'individual', p_cod_faz, v_fazenda, auth.uid())
    returning id into v_id;
  end if;
  return v_id;
end $$;

-- Primeira linha de uma revisão (é nela que ficam os talhões da revisão).
create or replace function hub.revisao_principal(p_projeto bigint, p_numero int)
returns bigint language sql stable security definer set search_path = hub as $$
  select min(id) from hub.projeto_revisoes where projeto_id = p_projeto and numero = p_numero;
$$;

-- Linha do documento na revisão p_numero do projeto (cria se ainda não existir: o documento passa
-- a valer desta revisão). A linha nova herda motivo e "unificada" da revisão; sem revisão, unificada.
create or replace function hub.revisao_documento(p_projeto bigint, p_documento text, p_numero int, p_motivo text)
returns bigint
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_id   bigint;
  v_prin hub.projeto_revisoes;
begin
  select id into v_id from hub.projeto_revisoes
   where projeto_id = p_projeto and documento = p_documento and numero = p_numero;
  if v_id is not null then
    return v_id;
  end if;
  select * into v_prin from hub.projeto_revisoes where id = hub.revisao_principal(p_projeto, p_numero);
  update hub.projeto_revisoes set vigente = false
   where projeto_id = p_projeto and documento = p_documento and vigente;
  insert into hub.projeto_revisoes (projeto_id, documento, numero, motivo, criado_por, unificada)
  values (p_projeto, p_documento, p_numero,
          coalesce(nullif(trim(p_motivo), ''), v_prin.motivo), auth.uid(), coalesce(v_prin.unificada, true))
  returning id into v_id;
  return v_id;
end $$;

-- nova_revisao: no Plantio e no Preparo o número é o da fazenda (maior entre todos os documentos + 1).
-- Colheita e Drone continuam com número por documento.
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
  v_modulo    text;
  v_numero    int;
  v_id        bigint;
  v_unificada boolean;
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

  v_unificada := v_modulo in ('plantio', 'preparo');
  select coalesce(max(numero) + 1, 0) into v_numero
    from hub.projeto_revisoes
   where projeto_id = p_projeto_id and (v_unificada or documento = p_documento);

  if v_numero > 0 and length(trim(coalesce(p_motivo, ''))) = 0 then
    raise exception 'Informe o motivo da revisão %', v_numero;
  end if;

  update hub.projeto_revisoes set vigente = false
   where projeto_id = p_projeto_id and documento = p_documento and vigente;

  insert into hub.projeto_revisoes (projeto_id, documento, numero, motivo, criado_por, unificada)
  values (p_projeto_id, p_documento, v_numero, nullif(trim(p_motivo), ''), auth.uid(), v_unificada)
  returning id into v_id;

  if p_origens is not null then
    insert into hub.revisao_origens (revisao_id, origem_revisao_id)
    select v_id, unnest(p_origens);
  end if;

  return v_id;
end $$;

-- preparar_envio: no Plantio e no Preparo, sem pedir revisão nova, o arquivo entra na última revisão
-- da fazenda (revisão aberta). Colheita e Drone: igual a antes (completa a vigente do documento).
create or replace function hub.preparar_envio(
  p_modulo    text,
  p_cod_faz   int,
  p_documento text,
  p_nova      boolean,
  p_motivo    text default null
)
returns table (revisao_id bigint, numero int, marcador text, sufixo text,
               fazenda text, extensoes text[], tag text)
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_tipo    hub.documento_tipos;
  v_fazenda text;
  v_projeto bigint;
  v_rev     hub.projeto_revisoes;
  v_nova_id bigint;
  v_ultima  int;
begin
  if not hub.pode_editar(p_modulo) then
    raise exception 'Sem permissão para enviar arquivos do módulo %', p_modulo;
  end if;
  select * into v_tipo from hub.documento_tipos where modulo_id = p_modulo and codigo = p_documento;
  if v_tipo.codigo is null then
    raise exception 'Documento "%" não existe no módulo %', p_documento, p_modulo;
  end if;
  select nome into v_fazenda from hub.fazendas where cod_faz = p_cod_faz;
  if v_fazenda is null then
    raise exception 'Fazenda % não existe na Base Fazendas', p_cod_faz;
  end if;

  v_projeto := hub.projeto_individual(p_modulo, p_cod_faz, true);

  if p_modulo in ('plantio', 'preparo') and not p_nova then
    perform 1 from hub.projetos where id = v_projeto for update;
    select max(r.numero) into v_ultima from hub.projeto_revisoes r where r.projeto_id = v_projeto;
    if v_ultima is null then
      v_nova_id := hub.nova_revisao(v_projeto, p_documento, p_motivo);
    else
      v_nova_id := hub.revisao_documento(v_projeto, p_documento, v_ultima, null);
    end if;
    select * into v_rev from hub.projeto_revisoes r where r.id = v_nova_id;
  else
    select * into v_rev from hub.projeto_revisoes r
     where r.projeto_id = v_projeto and r.documento = p_documento and r.vigente;

    if p_nova or v_rev.id is null then
      -- Cria primeiro, lê depois: função que cria registro não pode ficar no
      -- filtro da consulta (seria executada uma vez por linha examinada).
      v_nova_id := hub.nova_revisao(v_projeto, p_documento, p_motivo);
      select * into v_rev from hub.projeto_revisoes r where r.id = v_nova_id;
    end if;
  end if;

  return query select v_rev.id, v_rev.numero, v_tipo.marcador, v_tipo.sufixo,
                      v_fazenda, v_tipo.extensoes, p_modulo || '-' || p_cod_faz;
end $$;

-- 4 ─────────────────────────────────────────────────────────────────────────
create or replace view hub.arquivos_vigentes with (security_invoker = true) as
select projeto_id, modulo_id, tipo, cod_faz, projeto, documento, revisao_id, revisao,
       nome_arquivo, release_url, tamanho_bytes, publicado_em
  from (select p.id     as projeto_id,
               p.modulo_id,
               p.tipo,
               p.cod_faz,
               p.nome   as projeto,
               r.documento,
               r.id     as revisao_id,
               r.numero as revisao,
               a.nome_arquivo,
               a.release_url,
               a.tamanho_bytes,
               a.publicado_em,
               r.vigente,
               r.numero = max(r.numero) over (partition by p.id, r.documento, hub.ext_arquivo(a.nome_arquivo))
                        as mais_recente
          from hub.projetos p
          join hub.projeto_revisoes r on r.projeto_id = p.id
          join hub.revisao_arquivos a on a.revisao_id = r.id) x
 where case when modulo_id in ('plantio', 'preparo') then mais_recente else vigente end;

create or replace function public.portal_arquivos()
returns table (
  modulo         text,
  cod_faz        int,
  fazenda        text,
  bloco          text,
  documento      text,
  documento_nome text,
  revisao        int,
  marcador       text,
  nome_arquivo   text,
  url            text,
  tamanho_bytes  bigint,
  publicado_em   timestamptz
)
language sql
stable
security definer
set search_path = hub
as $$
  select v.modulo_id,
         fz.cod_faz,
         fz.nome,
         case when v.tipo = 'personalizado' then v.projeto end,
         v.documento,
         dt.nome,
         v.revisao,
         dt.marcador,
         v.nome_arquivo,
         v.release_url,
         v.tamanho_bytes,
         v.publicado_em
    from arquivos_vigentes v
    join documento_tipos dt on dt.modulo_id = v.modulo_id and dt.codigo = v.documento
    cross join lateral (
      select v.cod_faz as cod where v.tipo = 'individual'
      union
      select po.cod_faz
        from revisao_origens o
        join projeto_revisoes ro on ro.id = o.origem_revisao_id
        join projetos po on po.id = ro.projeto_id
       where o.revisao_id = v.revisao_id
    ) f
    join fazendas fz on fz.cod_faz = f.cod
   order by fz.nome, dt.ordem, v.nome_arquivo;
$$;

-- tem_arquivo: no Plantio e no Preparo vale o arquivo vigente por extensão (qualquer revisão do
-- documento que tenha um arquivo dessa extensão, já que nada é apagado).
create or replace function hub.tem_arquivo(p_modulo text, p_cod_faz int, p_documento text, p_ext text)
returns boolean
language sql
stable
security definer
set search_path = hub
as $$
  with projetos_da_fazenda as (
    select id from hub.projetos
     where modulo_id = p_modulo and tipo = 'individual' and cod_faz = p_cod_faz
    union
    select r.projeto_id
      from hub.projeto_revisoes r
      join hub.revisao_origens o on o.revisao_id = r.id
      join hub.projeto_revisoes ro on ro.id = o.origem_revisao_id
      join hub.projetos po on po.id = ro.projeto_id
     where po.modulo_id = p_modulo and po.cod_faz = p_cod_faz
  )
  select exists (
    select 1
      from hub.projeto_revisoes r
      join hub.revisao_arquivos a on a.revisao_id = r.id
     where r.projeto_id in (select id from projetos_da_fazenda)
       and r.documento = p_documento
       and (r.vigente or p_modulo in ('plantio', 'preparo'))
       and hub.ext_arquivo(a.nome_arquivo) = lower(p_ext));
$$;

-- Mapa anexado (.pdf do documento projeto do Plantio, na linha vigente): Ag. Mapa → Ok só nos
-- talhões daquela revisão. Revisão antiga (unificada = false): como antes, a fazenda inteira.
create or replace function hub.mapa_anexado()
returns trigger
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_rev  hub.projeto_revisoes;
  v_proj hub.projetos;
  v_lote bigint;
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
  v_lote := nextval('hub.log_lote_seq');

  with fazendas as (
    select v_proj.cod_faz as cod_faz where v_proj.tipo = 'individual'
    union
    select po.cod_faz
      from hub.revisao_origens o
      join hub.projeto_revisoes ro on ro.id = o.origem_revisao_id
      join hub.projetos po on po.id = ro.projeto_id
     where o.revisao_id = v_rev.id
  ), alvo as (
    select rt.layer
      from hub.revisao_talhoes rt
      join hub.projeto_revisoes r on r.id = rt.revisao_id
     where v_rev.unificada and r.projeto_id = v_rev.projeto_id and r.numero = v_rev.numero
    union
    select t.layer from hub.talhoes t
     where not v_rev.unificada and t.cod_faz in (select cod_faz from fazendas)
  ), mudou as (
    update hub.talhao_plantio p
       set projeto = 'Ok'
     where p.layer in (select layer from alvo)
       and p.projeto = 'Ag. Mapa'
    returning p.layer
  )
  insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo,
                                 usuario_id, origem, lote_id)
  select 'plantio', 'talhao', m.layer, 'projeto', 'Ag. Mapa', 'Ok', new.publicado_por, 'mapa_anexado', v_lote
    from mudou m;

  return new;
end $$;

-- 5 ─────────────────────────────────────────────────────────────────────────
-- Avança os talhões dados (null = todos os que estão na etapa certa). Talhão dado que não está na
-- etapa certa é erro (nada muda). Ação que exige arquivo registra os talhões na última revisão da
-- fazenda como "novo" (revisão aberta), para o mapa anexado depois saber quais são.
create or replace function hub.projeto_avancar(
  p_modulo  text,
  p_cod_faz int,
  p_acao    text,
  p_talhoes int[] default null
)
returns int
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_def     record;
  v_exige   text;
  v_alvo    bigint[];
  v_fora    text;
  v_qtd     int;
  v_projeto bigint;
  v_ultima  int;
begin
  perform hub.projeto_conferir(p_modulo, p_cod_faz);
  select * into v_def from hub.projeto_acoes(p_modulo, p_acao);
  if v_def.acao is null then
    raise exception 'Ação "%" não existe no %', p_acao, initcap(p_modulo);
  end if;

  foreach v_exige in array v_def.exige loop
    if not hub.tem_arquivo(p_modulo, p_cod_faz, split_part(v_exige, '.', 1), split_part(v_exige, '.', 2)) then
      raise exception '%', v_def.falta;
    end if;
  end loop;

  if p_talhoes is not null then
    select string_agg(n::text, ', ' order by n) into v_fora
      from (select distinct unnest(p_talhoes) n) d
     where not exists (select 1 from hub.projeto_talhoes(p_modulo, p_cod_faz) t
                        where t.talhao_num = d.n and t.etapa = v_def.de
                          and (not v_def.so_mapeados or t.mapeamento = 'Sim'));
    if v_fora is not null then
      raise exception 'Talhão(ões) % não está(ão) em % (nada foi alterado)', v_fora, v_def.de;
    end if;
  end if;

  select array_agg(t.layer) into v_alvo
    from hub.projeto_talhoes(p_modulo, p_cod_faz) t
   where t.etapa = v_def.de
     and (not v_def.so_mapeados or t.mapeamento = 'Sim')
     and (p_talhoes is null or t.talhao_num = any(p_talhoes));
  if v_alvo is null then
    raise exception 'Nenhum talhão desta fazenda está na etapa certa para esta ação';
  end if;

  v_qtd := hub.projeto_mudar_etapa(p_modulo, v_alvo, v_def.para, nextval('hub.log_lote_seq'), 'avancar',
                                   null, v_def.mapeamento);

  if cardinality(v_def.exige) > 0 then
    v_projeto := hub.projeto_individual(p_modulo, p_cod_faz, false);
    select max(numero) into v_ultima from hub.projeto_revisoes where projeto_id = v_projeto;
    if v_ultima is not null then
      insert into hub.revisao_talhoes (revisao_id, layer, tipo)
      select hub.revisao_principal(v_projeto, v_ultima), unnest(v_alvo), 'novo'
      on conflict do nothing;
    end if;
  end if;
  return v_qtd;
end $$;

-- Volta para p_para os talhões (dados, ou todos) que estão depois dela. Devolve o lote, que é o que
-- o desfazer recebe.
create or replace function hub.projeto_retroceder(
  p_modulo        text,
  p_cod_faz       int,
  p_para          text,
  p_justificativa text,
  p_talhoes       int[] default null
)
returns bigint
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_alvo bigint[];
  v_lote bigint;
begin
  perform hub.projeto_conferir(p_modulo, p_cod_faz);
  if length(trim(coalesce(p_justificativa, ''))) = 0 then
    raise exception 'Informe a justificativa para voltar a etapa';
  end if;
  if p_para is null or hub.projeto_ordem(p_modulo, p_para) is null or p_para = 'Ok' then
    raise exception 'Etapa inválida para voltar: %', p_para;
  end if;

  select array_agg(t.layer) into v_alvo
    from hub.projeto_talhoes(p_modulo, p_cod_faz) t
   where hub.projeto_ordem(p_modulo, t.etapa) > hub.projeto_ordem(p_modulo, p_para)
     and (p_talhoes is null or t.talhao_num = any(p_talhoes));
  if v_alvo is null then
    raise exception 'Nenhum talhão selecionado está depois de %', p_para;
  end if;

  v_lote := nextval('hub.log_lote_seq');
  perform hub.projeto_mudar_etapa(p_modulo, v_alvo, p_para, v_lote, 'retroceder', trim(p_justificativa),
                                  case when p_modulo = 'plantio' and p_para = 'Aguard. Map.' then 'Não' end);
  return v_lote;
end $$;

-- Desfaz um retrocesso: cada talhão volta à etapa (e ao mapeamento) exatos de antes. Só se o lote
-- ainda for o último evento da fazenda no módulo (nenhuma mudança de etapa, revisão ou envio depois).
create or replace function hub.projeto_desfazer(p_lote_id bigint)
returns int
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_modulo  text;
  v_cod_faz int;
  v_ultimo  bigint;
  v_em      timestamptz;
  v_retro   boolean;
  v_projeto bigint;
  v_lote    bigint;
  v_r       hub.log_auditoria;
  v_qtd     int;
begin
  select min(modulo_id), min(entidade_id / 1000)::int, max(id), min(criado_em), bool_and(origem = 'retroceder')
    into v_modulo, v_cod_faz, v_ultimo, v_em, v_retro
    from hub.log_auditoria
   where lote_id = p_lote_id and entidade_tipo = 'talhao';
  if v_ultimo is null then
    raise exception 'Não há registro do lote %', p_lote_id;
  end if;
  if not v_retro then
    raise exception 'Só uma volta de etapa pode ser desfeita';
  end if;
  perform hub.projeto_conferir(v_modulo, v_cod_faz);

  v_projeto := hub.projeto_individual(v_modulo, v_cod_faz, false);
  if exists (select 1 from hub.log_auditoria l
              where l.modulo_id = v_modulo and l.id > v_ultimo
                and ((l.entidade_tipo = 'talhao' and l.entidade_id between v_cod_faz * 1000::bigint
                                                                       and v_cod_faz * 1000::bigint + 999)
                     or (l.entidade_tipo = 'fazenda' and l.entidade_id = v_cod_faz)))
     or exists (select 1 from hub.projeto_revisoes r
                 where r.projeto_id = v_projeto and r.criado_em > v_em)
     or exists (select 1 from hub.projeto_revisoes r join hub.revisao_arquivos a on a.revisao_id = r.id
                 where r.projeto_id = v_projeto and a.publicado_em > v_em) then
    raise exception 'Não dá mais para desfazer: a fazenda mudou depois dessa volta (avanço, envio, revisão ou outra volta)';
  end if;

  v_lote := nextval('hub.log_lote_seq');
  for v_r in select * from hub.log_auditoria where lote_id = p_lote_id order by id desc loop
    if v_modulo = 'plantio' and v_r.campo = 'projeto' then
      update hub.talhao_plantio set projeto = v_r.valor_anterior
       where layer = v_r.entidade_id and projeto = v_r.valor_novo;
    elsif v_modulo = 'plantio' and v_r.campo = 'mapeamento' then
      update hub.talhao_plantio set mapeamento = v_r.valor_anterior
       where layer = v_r.entidade_id and mapeamento = v_r.valor_novo;
    elsif v_modulo = 'preparo' and v_r.campo = 'etapa' then
      update hub.talhao_preparo set etapa = v_r.valor_anterior
       where layer = v_r.entidade_id and etapa = v_r.valor_novo;
    else
      continue;
    end if;
    if found then
      insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo,
                                     usuario_id, origem, justificativa, lote_id)
      values (v_modulo, 'talhao', v_r.entidade_id, v_r.campo, v_r.valor_novo, v_r.valor_anterior,
              auth.uid(), 'desfazer', format('Desfaz a volta (lote %s)', p_lote_id), v_lote);
    end if;
  end loop;

  select count(distinct entidade_id) into v_qtd from hub.log_auditoria where lote_id = v_lote;
  return v_qtd;
end $$;

-- Abre a próxima revisão da fazenda com os documentos que mudam e os talhões que ela traz ou altera.
-- Regras (D3):
--   Plantio: talhão em Andamento = novo → Ag. Mapa (a revisão precisa trazer projeto e exportação);
--            em Ag. Mapa ou Ok = alterado → Ag. Mapa (precisa trazer o projeto). O mapa anexado
--            depois leva os talhões da revisão para Ok.
--   Preparo: o projeto muda → exportação e sistematização vêm junto. Talhão novo avança pelas ações
--            cujos arquivos a revisão traz (escoamento: Escoamento → Observações; projeto:
--            Preparo → Ok). Alterado (já passou dessas etapas) não muda de etapa.
-- Devolve uma linha por documento, na ordem de p_documentos.
create or replace function hub.projeto_nova_revisao(
  p_modulo     text,
  p_cod_faz    int,
  p_motivo     text,
  p_documentos text[],
  p_talhoes    int[]
)
returns table (revisao_id bigint, numero int, sufixo text)
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_projeto bigint;
  v_numero  int;
  v_doc     text;
  v_prin    bigint;
  v_lote    bigint;
  v_t       record;
  v_etapa   text;
  v_tipo    text;
  v_fora    text;
  v_esc     boolean := 'escoamento' = any(p_documentos);
  v_proj    boolean := 'projeto' = any(p_documentos);
  v_exp     boolean := 'exportacao' = any(p_documentos);
begin
  perform hub.projeto_conferir(p_modulo, p_cod_faz);

  if coalesce(cardinality(p_documentos), 0) = 0 then
    raise exception 'Escolha ao menos um documento que muda nesta revisão';
  end if;
  select string_agg(d, ', ') into v_fora
    from unnest(p_documentos) d
   where not exists (select 1 from hub.documento_tipos dt where dt.modulo_id = p_modulo and dt.codigo = d);
  if v_fora is not null then
    raise exception 'Documento(s) % não existe(m) no %', v_fora, initcap(p_modulo);
  end if;
  if cardinality(p_documentos) <> (select count(distinct d) from unnest(p_documentos) d) then
    raise exception 'Documento repetido na revisão';
  end if;
  if p_modulo = 'preparo' and v_proj
     and not ('exportacao' = any(p_documentos) and 'sistematizacao' = any(p_documentos)) then
    raise exception 'Quando o projeto muda, a exportação e a sistematização vêm junto na mesma revisão';
  end if;

  if p_talhoes is not null then
    select string_agg(n::text, ', ' order by n) into v_fora
      from (select distinct unnest(p_talhoes) n) d
     where not exists (select 1 from hub.projeto_talhoes(p_modulo, p_cod_faz) t where t.talhao_num = d.n);
    if v_fora is not null then
      raise exception 'Talhão(ões) % não existe(m) no % desta fazenda', v_fora, initcap(p_modulo);
    end if;
  end if;

  v_projeto := hub.projeto_individual(p_modulo, p_cod_faz, true);
  perform 1 from hub.projetos where id = v_projeto for update;
  select coalesce(max(r.numero) + 1, 0) into v_numero from hub.projeto_revisoes r where r.projeto_id = v_projeto;
  if v_numero > 0 and length(trim(coalesce(p_motivo, ''))) = 0 then
    raise exception 'Informe o motivo da Rev%', v_numero;
  end if;

  -- Classifica cada talhão antes de gravar qualquer coisa.
  create temp table if not exists _rev_talhoes (layer bigint, talhao_num int, tipo text, para text) on commit drop;
  truncate _rev_talhoes;
  for v_t in select t.* from hub.projeto_talhoes(p_modulo, p_cod_faz) t
              where t.talhao_num = any(coalesce(p_talhoes, '{}')) order by t.talhao_num loop
    v_etapa := v_t.etapa;
    v_tipo := null;
    if p_modulo = 'plantio' then
      if v_t.etapa = 'Andamento' then
        if not (v_proj and v_exp) then
          raise exception 'Talhão % está em Andamento: para entrar como novo, a revisão precisa trazer o projeto e a exportação', v_t.talhao_num;
        end if;
        v_tipo := 'novo';
        v_etapa := 'Ag. Mapa';
      elsif v_t.etapa in ('Ag. Mapa', 'Ok') then
        if not v_proj then
          raise exception 'Talhão % já tem projeto: para alterá-lo, a revisão precisa trazer o projeto', v_t.talhao_num;
        end if;
        v_tipo := 'alterado';
        v_etapa := 'Ag. Mapa';
      else
        raise exception 'Talhão % está em %: ainda não tem projeto para entrar numa revisão', v_t.talhao_num, v_t.etapa;
      end if;
    else
      if v_esc and v_etapa = 'Escoamento' then
        v_etapa := 'Observações';
        v_tipo := 'novo';
      end if;
      if v_proj and v_etapa = 'Preparo' then
        v_etapa := 'Ok';
        v_tipo := 'novo';
      end if;
      if v_tipo is null then
        if v_t.etapa = 'Ok'
           or (v_esc and hub.projeto_ordem('preparo', v_t.etapa) > hub.projeto_ordem('preparo', 'Escoamento'))
           or (v_proj and hub.projeto_ordem('preparo', v_t.etapa) > hub.projeto_ordem('preparo', 'Preparo')) then
          v_tipo := 'alterado';
        else
          raise exception 'Talhão % está em %: conclua as etapas anteriores antes de colocá-lo nesta revisão',
                          v_t.talhao_num, v_t.etapa;
        end if;
      end if;
    end if;
    insert into _rev_talhoes values (v_t.layer, v_t.talhao_num, v_tipo, v_etapa);
  end loop;

  foreach v_doc in array p_documentos loop
    perform hub.revisao_documento(v_projeto, v_doc, v_numero, p_motivo);
  end loop;
  v_prin := hub.revisao_principal(v_projeto, v_numero);

  insert into hub.revisao_talhoes (revisao_id, layer, tipo)
  select v_prin, layer, tipo from _rev_talhoes;

  v_lote := nextval('hub.log_lote_seq');
  for v_etapa in select distinct para from _rev_talhoes loop
    perform hub.projeto_mudar_etapa(p_modulo, (select array_agg(layer) from _rev_talhoes where para = v_etapa),
                                    v_etapa, v_lote, 'nova_revisao', null);
  end loop;

  return query
  select r.id, r.numero, dt.sufixo
    from unnest(p_documentos) with ordinality d (doc, ord)
    join hub.projeto_revisoes r on r.projeto_id = v_projeto and r.numero = v_numero and r.documento = d.doc
    join hub.documento_tipos dt on dt.modulo_id = p_modulo and dt.codigo = d.doc
   order by d.ord;
end $$;

-- Linha do tempo da fazenda no módulo, mais novo primeiro: mudanças de etapa agrupadas por ação
-- (lote), revisões (motivo, documentos, arquivos, talhões) e desfazer. Revisões antigas aparecem
-- uma por documento ("Rev1 · Exportação").
create or replace function hub.projeto_linha_do_tempo(p_modulo text, p_cod_faz int)
returns table (em timestamptz, tipo text, quem text, texto text, detalhe jsonb)
language plpgsql
stable
security definer
set search_path = hub
as $$
declare
  v_projeto bigint;
begin
  if p_modulo is null or p_modulo not in ('plantio', 'preparo') then
    raise exception 'Módulo inválido: % (use plantio ou preparo)', p_modulo;
  end if;
  if not hub.pode_editar(p_modulo) then
    raise exception 'Sem permissão para ver o % desta fazenda', initcap(p_modulo);
  end if;
  v_projeto := hub.projeto_individual(p_modulo, p_cod_faz, false);

  return query
  with registro as (
    select l.*,
           case when l.entidade_tipo = 'talhao' then (l.entidade_id - p_cod_faz * 1000::bigint)::int end as talhao,
           coalesce('L' || l.lote_id,
                    concat_ws('|', l.criado_em, l.usuario_id, l.origem, l.entidade_tipo, l.campo, l.valor_novo)) as chave
      from hub.log_auditoria l
     where l.modulo_id = p_modulo
       and l.origem <> 'nova_revisao'
       and ((l.entidade_tipo = 'talhao' and l.entidade_id between p_cod_faz * 1000::bigint
                                                              and p_cod_faz * 1000::bigint + 999)
            or (l.entidade_tipo = 'fazenda' and l.entidade_id = p_cod_faz))
  ), acoes as (
    select g.chave,
           min(g.criado_em) as em,
           min(g.origem) as origem,
           min(g.usuario_id::text)::uuid as usuario_id,
           min(g.lote_id) as lote_id,
           min(g.justificativa) as justificativa,
           min(g.campo) filter (where g.entidade_tipo = 'fazenda') as etapa_fazenda,
           count(distinct g.talhao) filter (where g.campo in ('projeto', 'etapa')) as qtd,
           case when count(distinct g.valor_novo) filter (where g.campo in ('projeto', 'etapa')) = 1
                then min(g.valor_novo) filter (where g.campo in ('projeto', 'etapa')) end as para,
           min(g.valor_novo) filter (where g.entidade_tipo = 'fazenda') as valor_fazenda,
           jsonb_agg(jsonb_build_object('talhao', g.talhao, 'campo', g.campo,
                                        'de', g.valor_anterior, 'para', g.valor_novo) order by g.talhao, g.campo)
             as mudancas
      from registro g
     group by g.chave
  ), revisoes as (
    select coalesce(case when r.unificada then 'U' || r.numero end, 'D' || r.id) as chave,
           bool_or(r.unificada) as unificada,
           min(r.numero) as numero,
           min(r.criado_em) as em,
           (array_agg(r.criado_por order by r.id))[1] as usuario_id,
           (array_agg(r.motivo order by r.id))[1] as motivo,
           array_agg(r.id order by r.id) as ids,
           jsonb_agg(jsonb_build_object('codigo', r.documento, 'nome', dt.nome) order by dt.ordem) as documentos,
           string_agg(dt.nome, ', ' order by dt.ordem) as nomes
      from hub.projeto_revisoes r
      join hub.documento_tipos dt on dt.modulo_id = p_modulo and dt.codigo = r.documento
     where r.projeto_id = v_projeto
     group by 1
  )
  select a.em,
         case a.origem when 'retroceder' then 'retrocesso' when 'desfazer' then 'desfazer'
                       when 'mapa_anexado' then 'mapa' when 'avancar' then 'avanco' else 'etapa' end,
         u.nome,
         case
           when a.etapa_fazenda is not null then a.etapa_fazenda || ' ' || coalesce(a.valor_fazenda, '')
           when a.origem = 'retroceder' then format('%s talhão(ões) voltaram para %s: %s', a.qtd, a.para, a.justificativa)
           when a.origem = 'desfazer' then format('Volta desfeita: %s talhão(ões) retornaram à etapa em que estavam', a.qtd)
           when a.origem = 'mapa_anexado' then format('Mapa anexado: %s talhão(ões) em Ok', a.qtd)
           else format('%s talhão(ões) em %s', a.qtd, coalesce(a.para, 'etapas diferentes'))
         end,
         jsonb_build_object('lote_id', a.lote_id, 'justificativa', a.justificativa, 'para', a.para,
                            'mudancas', a.mudancas)
    from acoes a
    left join hub.usuarios u on u.id = a.usuario_id
  union all
  select v.em,
         'revisao',
         u.nome,
         case when v.unificada then format('Rev%s · %s', v.numero, coalesce(v.motivo, 'primeira revisão'))
              else format('Rev%s · %s', v.numero, v.nomes) end,
         jsonb_build_object(
           'numero', v.numero,
           'unificada', v.unificada,
           'motivo', v.motivo,
           'documentos', v.documentos,
           'talhoes', (select coalesce(jsonb_agg(jsonb_build_object('talhao', t.talhao_num, 'tipo', rt.tipo)
                                                 order by t.talhao_num), '[]')
                         from hub.revisao_talhoes rt join hub.talhoes t on t.layer = rt.layer
                        where rt.revisao_id = any(v.ids)),
           'arquivos', (select coalesce(jsonb_agg(jsonb_build_object('documento', r.documento, 'nome', a.nome_arquivo,
                                                                     'url', a.release_url, 'em', a.publicado_em)
                                                  order by a.publicado_em), '[]')
                          from hub.revisao_arquivos a join hub.projeto_revisoes r on r.id = a.revisao_id
                         where a.revisao_id = any(v.ids)))
    from revisoes v
    left join hub.usuarios u on u.id = v.usuario_id
   order by 1 desc;
end $$;

-- 6 ─────────────────────────────────────────────────────────────────────────
-- RPCs da tela atual, agora em cima das novas (sempre a fazenda inteira).
create or replace function hub.plantio_mapeamento_concluido(p_cod_faz int)
returns int language sql security definer set search_path = hub as $$
  select hub.projeto_avancar('plantio', p_cod_faz, 'mapeamento_concluido');
$$;

create or replace function hub.plantio_iniciar(p_cod_faz int)
returns int language sql security definer set search_path = hub as $$
  select hub.projeto_avancar('plantio', p_cod_faz, 'iniciar');
$$;

create or replace function hub.plantio_exportacao_enviada(p_cod_faz int)
returns int language sql security definer set search_path = hub as $$
  select hub.projeto_avancar('plantio', p_cod_faz, 'exportacao_enviada');
$$;

create or replace function hub.plantio_retroceder(p_cod_faz int, p_para text)
returns int
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_lote bigint := hub.projeto_retroceder('plantio', p_cod_faz, p_para, 'Volta pela tela antiga (sem justificativa)');
begin
  return (select count(*) from hub.log_auditoria where lote_id = v_lote and campo = 'projeto');
end $$;

create or replace function hub.preparo_concluir_etapa(
  p_cod_faz    int,
  p_ordem      int,
  p_observacao text default null
)
returns void
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_acao text := (array['identificacao', 'escoamento', 'observacoes', 'preparo'])[p_ordem];
begin
  if v_acao is null then
    raise exception 'Etapa % do Preparo não existe', p_ordem;
  end if;
  perform hub.projeto_avancar('preparo', p_cod_faz, v_acao);
  -- A observação da fazenda continua guardada na etapa Observações de etapa_status.
  if p_ordem = 3 and length(trim(coalesce(p_observacao, ''))) > 0 then
    insert into hub.etapa_status (etapa_id, entidade_id, ok, usuario_id, concluido_em, observacao)
    select e.id, p_cod_faz, true, auth.uid(), now(), trim(p_observacao)
      from hub.etapas e where e.modulo_id = 'preparo' and e.ordem = 3
    on conflict (etapa_id, entidade_id) do update
      set usuario_id = auth.uid(), concluido_em = now(), observacao = excluded.observacao;
  end if;
end $$;

create or replace function hub.preparo_reabrir_etapa(p_cod_faz int, p_ordem int)
returns int
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_para text := (hub.projeto_etapas('preparo'))[p_ordem];
  v_lote bigint;
begin
  if v_para is null or p_ordem > 4 then
    raise exception 'Etapa % do Preparo não existe', p_ordem;
  end if;
  v_lote := hub.projeto_retroceder('preparo', p_cod_faz, v_para, 'Reaberta pela tela antiga (sem justificativa)');
  return (select count(*) from hub.log_auditoria where lote_id = v_lote);
end $$;

-- ── Permissões ─────────────────────────────────────────────────────────────
-- Funções internas: só chamadas de dentro das RPCs (security definer).
revoke all on function hub.projeto_talhoes(text, int) from public, anon, authenticated;
revoke all on function hub.projeto_mudar_etapa(text, bigint[], text, bigint, text, text, text) from public, anon, authenticated;
revoke all on function hub.projeto_conferir(text, int) from public, anon, authenticated;
revoke all on function hub.projeto_individual(text, int, boolean) from public, anon, authenticated;
revoke all on function hub.revisao_principal(bigint, int) from public, anon, authenticated;
revoke all on function hub.revisao_documento(bigint, text, int, text) from public, anon, authenticated;

-- RPCs do contrato: a checagem de editor fica dentro de cada uma.
revoke all on function hub.projeto_avancar(text, int, text, int[]) from public, anon;
revoke all on function hub.projeto_retroceder(text, int, text, text, int[]) from public, anon;
revoke all on function hub.projeto_desfazer(bigint) from public, anon;
revoke all on function hub.projeto_nova_revisao(text, int, text, text[], int[]) from public, anon;
revoke all on function hub.projeto_linha_do_tempo(text, int) from public, anon;
grant execute on function hub.projeto_avancar(text, int, text, int[]) to authenticated;
grant execute on function hub.projeto_retroceder(text, int, text, text, int[]) to authenticated;
grant execute on function hub.projeto_desfazer(bigint) to authenticated;
grant execute on function hub.projeto_nova_revisao(text, int, text, text[], int[]) to authenticated;
grant execute on function hub.projeto_linha_do_tempo(text, int) to authenticated;

commit;
