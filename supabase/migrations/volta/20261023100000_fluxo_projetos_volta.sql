-- Volta da migração 20261023100000_fluxo_projetos.sql. Gerado da cadeia de migrações (versões de antes
-- do fluxo, já com 20261023090000_niveis_por_modulo) e conferido num Postgres local: depois desta volta
-- as funções, as permissões e as views ficam iguais às de antes do fluxo.
-- Rodar só para voltar atrás, junto com o revert do merge da fluxo-integracao (app antigo).
-- Ficam no banco, sem uso pelo app antigo: log_auditoria.justificativa/lote_id, talhao_preparo.etapa,
-- projeto_revisoes.unificada, hub.revisao_talhoes e hub.log_lote_seq (guardam o histórico).
-- Para reaplicar o fluxo depois, apagar antes essas estruturas (bloco comentado no fim).

begin;

-- 1) Preparo: a etapa volta a ser da fazenda (hub.etapa_status). A fazenda fica na etapa do talhão
--    mais atrasado (Ok = as quatro concluídas). Observações e datas já gravadas ficam.
create temp table _faz_preparo on commit drop as
select t.cod_faz, min(coalesce(e.ordem, 5)) as ordem
  from hub.talhao_preparo tp
  join hub.talhoes t on t.layer = tp.layer
  left join hub.etapas e on e.modulo_id = 'preparo' and e.nome = tp.etapa
 group by t.cod_faz;

insert into hub.etapa_status (etapa_id, entidade_id, ok, concluido_em)
select e.id, f.cod_faz, true, now()
  from _faz_preparo f join hub.etapas e on e.modulo_id = 'preparo' and e.ordem < f.ordem
on conflict (etapa_id, entidade_id) do update
   set ok = true, concluido_em = coalesce(hub.etapa_status.concluido_em, now())
 where not hub.etapa_status.ok;

update hub.etapa_status s set ok = false
  from _faz_preparo f, hub.etapas e
 where e.id = s.etapa_id and e.modulo_id = 'preparo' and s.entidade_id = f.cod_faz
   and e.ordem >= f.ordem and s.ok;

-- 2) Views de antes.
create or replace view hub.arquivos_vigentes with (security_invoker=true) as
 SELECT p.id AS projeto_id,
    p.modulo_id,
    p.tipo,
    p.cod_faz,
    p.nome AS projeto,
    r.documento,
    r.id AS revisao_id,
    r.numero AS revisao,
    a.nome_arquivo,
    a.release_url,
    a.tamanho_bytes,
    a.publicado_em
   FROM ((hub.projetos p
     JOIN hub.projeto_revisoes r ON (((r.projeto_id = p.id) AND r.vigente)))
     JOIN hub.revisao_arquivos a ON ((a.revisao_id = r.id)));

-- 3) Funções de antes (mesmo corpo e mesmas permissões).
CREATE OR REPLACE FUNCTION hub.mapa_anexado()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
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
end $function$;

CREATE OR REPLACE FUNCTION hub.nova_revisao(p_projeto_id bigint, p_documento text, p_motivo text, p_origens bigint[] DEFAULT NULL::bigint[])
 RETURNS bigint
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
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
end $function$;

CREATE OR REPLACE FUNCTION hub.plantio_exportacao_enviada(p_cod_faz integer)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
begin
  if not (hub.tem_arquivo('plantio', p_cod_faz, 'exportacao', 'zip')
          and hub.tem_arquivo('plantio', p_cod_faz, 'projeto', 'dwg')) then
    raise exception 'Envie a exportação (.zip) e o projeto (.dwg) antes de avançar';
  end if;
  return hub.plantio_aplicar(p_cod_faz, array['Andamento'], false, 'Ag. Mapa', null);
end $function$;

CREATE OR REPLACE FUNCTION hub.plantio_iniciar(p_cod_faz integer)
 RETURNS integer
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
  select hub.plantio_aplicar(p_cod_faz, array['Pendente'], true, 'Andamento', null);
$function$;

CREATE OR REPLACE FUNCTION hub.plantio_mapeamento_concluido(p_cod_faz integer)
 RETURNS integer
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
  select hub.plantio_aplicar(p_cod_faz, array['Aguard. Map.'], false, 'Pendente', 'Sim');
$function$;

CREATE OR REPLACE FUNCTION hub.plantio_retroceder(p_cod_faz integer, p_para text)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
declare
  v_depois text[];
begin
  if hub.plantio_ordem(p_para) is null then
    raise exception 'Etapa inválida: %', p_para;
  end if;
  select array_agg(e) into v_depois
    from unnest(array['Aguard. Map.', 'Pendente', 'Andamento', 'Ag. Mapa', 'Ok']) e
   where hub.plantio_ordem(e) > hub.plantio_ordem(p_para);
  return hub.plantio_aplicar(p_cod_faz, v_depois, false, p_para,
                             case when p_para = 'Aguard. Map.' then 'Não' end);
end $function$;

CREATE OR REPLACE FUNCTION hub.preparar_envio(p_modulo text, p_cod_faz integer, p_documento text, p_nova boolean, p_motivo text DEFAULT NULL::text)
 RETURNS TABLE(revisao_id bigint, numero integer, marcador text, sufixo text, fazenda text, extensoes text[], tag text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
declare
  v_tipo    hub.documento_tipos;
  v_fazenda text;
  v_projeto bigint;
  v_rev     hub.projeto_revisoes;
  v_nova_id bigint;
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

  select id into v_projeto from hub.projetos
   where modulo_id = p_modulo and tipo = 'individual' and cod_faz = p_cod_faz;
  if v_projeto is null then
    insert into hub.projetos (modulo_id, tipo, cod_faz, nome, criado_por)
    values (p_modulo, 'individual', p_cod_faz, v_fazenda, auth.uid())
    returning id into v_projeto;
  end if;

  select * into v_rev from hub.projeto_revisoes r
   where r.projeto_id = v_projeto and r.documento = p_documento and r.vigente;

  if p_nova or v_rev.id is null then
    -- Cria primeiro, lê depois: função que cria registro não pode ficar no
    -- filtro da consulta (seria executada uma vez por linha examinada).
    v_nova_id := hub.nova_revisao(v_projeto, p_documento, p_motivo);
    select * into v_rev from hub.projeto_revisoes r where r.id = v_nova_id;
  end if;

  return query select v_rev.id, v_rev.numero, v_tipo.marcador, v_tipo.sufixo,
                      v_fazenda, v_tipo.extensoes, p_modulo || '-' || p_cod_faz;
end $function$;

CREATE OR REPLACE FUNCTION hub.preparo_concluir_etapa(p_cod_faz integer, p_ordem integer, p_observacao text DEFAULT NULL::text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
declare
  v_etapa hub.etapas;
begin
  if not hub.pode_editar('preparo') then
    raise exception 'Sem permissão para editar o Preparo';
  end if;
  select * into v_etapa from hub.etapas where modulo_id = 'preparo' and ordem = p_ordem;
  if v_etapa.id is null then
    raise exception 'Etapa % do Preparo não existe', p_ordem;
  end if;
  if p_ordem = 2 and not hub.tem_arquivo('preparo', p_cod_faz, 'escoamento', 'pdf') then
    raise exception 'Envie o Mapa de Escoamento (.pdf) antes de concluir';
  end if;
  if p_ordem = 4 and not (hub.tem_arquivo('preparo', p_cod_faz, 'projeto', 'dwg')
                          and hub.tem_arquivo('preparo', p_cod_faz, 'exportacao', 'zip')
                          and hub.tem_arquivo('preparo', p_cod_faz, 'sistematizacao', 'pdf')) then
    raise exception 'Envie os 3 arquivos (projeto .dwg, exportação .zip e sistematização .pdf) antes de concluir';
  end if;
  if exists (
       select 1 from hub.etapas e
        where e.modulo_id = 'preparo' and e.ordem < p_ordem
          and not exists (select 1 from hub.etapa_status s
                           where s.etapa_id = e.id and s.entidade_id = p_cod_faz and s.ok)) then
    raise exception 'Conclua as etapas anteriores antes de %', v_etapa.nome;
  end if;

  insert into hub.etapa_status (etapa_id, entidade_id, ok, usuario_id, concluido_em, observacao)
  values (v_etapa.id, p_cod_faz, true, auth.uid(), now(), nullif(trim(p_observacao), ''))
  on conflict (etapa_id, entidade_id) do update
    set ok = true, usuario_id = auth.uid(), concluido_em = now(),
        observacao = coalesce(nullif(trim(p_observacao), ''), hub.etapa_status.observacao);

  insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, usuario_id)
  values ('preparo', 'fazenda', p_cod_faz, v_etapa.nome, 'concluída', auth.uid());
end $function$;

CREATE OR REPLACE FUNCTION hub.preparo_reabrir_etapa(p_cod_faz integer, p_ordem integer)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
declare
  v_qtd int;
begin
  if not hub.pode_editar('preparo') then
    raise exception 'Sem permissão para editar o Preparo';
  end if;

  with reaberta as (
    update hub.etapa_status s
       set ok = false, usuario_id = auth.uid(), concluido_em = null
      from hub.etapas e
     where e.id = s.etapa_id and e.modulo_id = 'preparo' and e.ordem >= p_ordem
       and s.entidade_id = p_cod_faz and s.ok
    returning e.nome
  ), registro as (
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, usuario_id)
    select 'preparo', 'fazenda', p_cod_faz, r.nome, 'reaberta', auth.uid() from reaberta r
    returning 1
  )
  select count(*) into v_qtd from registro;

  if v_qtd = 0 then
    raise exception 'Essa etapa não está concluída';
  end if;
  return v_qtd;
end $function$;

CREATE OR REPLACE FUNCTION hub.tem_arquivo(p_modulo text, p_cod_faz integer, p_documento text, p_ext text)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
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
       and r.vigente
       and lower(a.nome_arquivo) like '%.' || p_ext);
$function$;

CREATE OR REPLACE FUNCTION public.portal_arquivos()
 RETURNS TABLE(modulo text, cod_faz integer, fazenda text, bloco text, documento text, documento_nome text, revisao integer, marcador text, nome_arquivo text, url text, tamanho_bytes bigint, publicado_em timestamp with time zone)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'hub'
AS $function$
  select p.modulo_id,
         fz.cod_faz,
         fz.nome,
         case when p.tipo = 'personalizado' then p.nome end,
         r.documento,
         dt.nome,
         r.numero,
         dt.marcador,
         a.nome_arquivo,
         a.release_url,
         a.tamanho_bytes,
         a.publicado_em
    from projetos p
    join projeto_revisoes r  on r.projeto_id = p.id and r.vigente
    join revisao_arquivos a  on a.revisao_id = r.id
    join documento_tipos dt  on dt.modulo_id = p.modulo_id and dt.codigo = r.documento
    cross join lateral (
      select p.cod_faz as cod where p.tipo = 'individual'
      union
      select po.cod_faz
        from revisao_origens o
        join projeto_revisoes ro on ro.id = o.origem_revisao_id
        join projetos po on po.id = ro.projeto_id
       where o.revisao_id = r.id
    ) f
    join fazendas fz on fz.cod_faz = f.cod
   order by fz.nome, dt.ordem, a.nome_arquivo;
$function$;

-- 4) Funções que o fluxo criou.
drop function if exists hub.ext_arquivo(text);
drop function if exists hub.pode_ver(text);
drop function if exists hub.projeto_acoes(text,text);
drop function if exists hub.projeto_avancar(text,integer,text,integer[],text);
drop function if exists hub.projeto_conferir(text,integer);
drop function if exists hub.projeto_desfazer(bigint);
drop function if exists hub.projeto_etapas(text);
drop function if exists hub.projeto_individual(text,integer,boolean);
drop function if exists hub.projeto_linha_do_tempo(text,integer);
drop function if exists hub.projeto_mudar_etapa(text,bigint[],text,bigint,text,text,text);
drop function if exists hub.projeto_nova_revisao(text,integer,text,text[],integer[]);
drop function if exists hub.projeto_ordem(text,text);
drop function if exists hub.projeto_retroceder(text,integer,text,text,integer[]);
drop function if exists hub.projeto_talhoes(text,integer);
drop function if exists hub.revisao_documento(bigint,text,integer,text);
drop function if exists hub.revisao_principal(bigint,integer);

commit;

-- Antes de reaplicar o fluxo (não rodar junto com a volta):
-- drop table hub.revisao_talhoes; drop sequence hub.log_lote_seq; drop index hub.log_auditoria_lote_idx;
-- alter table hub.log_auditoria drop column justificativa, drop column lote_id;
-- alter table hub.talhao_preparo drop column etapa; alter table hub.projeto_revisoes drop column unificada;
