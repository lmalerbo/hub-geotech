-- Fase 2B: envio de arquivos com revisão.
--
-- Fluxo (quem chama é o Worker de envio, com o login do próprio usuário —
-- ele não tem chave de serviço; toda permissão é conferida aqui):
--   1. preparar_envio  → acha/cria o projeto individual da fazenda e a
--      revisão certa do documento (nova, ou a vigente pra completar), e
--      devolve o que o Worker precisa pra montar o nome do arquivo.
--   2. o Worker sobe o arquivo no GitHub Releases.
--   3. registrar_arquivo → grava o arquivo na revisão (anexar o .pdf do
--      projeto do Plantio dispara o "mapa → Ok").
-- Transições que dependem de arquivo:
--   Plantio: plantio_exportacao_enviada (Andamento → Ag. Mapa, exige a
--            exportação .zip e o projeto .dwg vigentes).
--   Preparo: Escoamento e Projeto de Preparo passam a concluir quando os
--            arquivos exigidos estão na revisão vigente (antes eram recusados).

begin;

-- Extensões aceitas por documento (a partir do que existe nos sistemas atuais).
alter table hub.documento_tipos add column extensoes text[] not null default '{}';
update hub.documento_tipos set extensoes = case
  when modulo_id = 'plantio' and codigo = 'projeto'        then array['dwg', 'pdf']   -- .pdf = mapa de plantio
  when modulo_id = 'plantio' and codigo = 'exportacao'     then array['zip']
  when modulo_id = 'preparo' and codigo = 'projeto'        then array['dwg']
  when modulo_id = 'preparo' and codigo = 'exportacao'     then array['zip', 'dwg']
  when modulo_id = 'preparo' and codigo = 'escoamento'     then array['pdf', 'dwg']
  when modulo_id = 'preparo' and codigo = 'sistematizacao' then array['pdf']
end;

-- A revisão vigente de um documento tem arquivo com essa extensão, no projeto
-- individual da fazenda ou num personalizado que inclua a fazenda.
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
       and r.vigente
       and lower(a.nome_arquivo) like '%.' || p_ext);
$$;

-- Passo 1 do envio. p_nova = true abre a próxima revisão (motivo obrigatório
-- a partir da 1); false completa a vigente (ou abre a 0 se ainda não houver).
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
end $$;

-- Passo 3 do envio. Repetir com o mesmo nome (reenvio após falha) só
-- atualiza o endereço — nada é duplicado.
create or replace function hub.registrar_arquivo(
  p_revisao_id bigint,
  p_nome       text,
  p_url        text,
  p_tamanho    bigint
)
returns void
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_modulo text;
begin
  select p.modulo_id into v_modulo
    from hub.projeto_revisoes r join hub.projetos p on p.id = r.projeto_id
   where r.id = p_revisao_id;
  if v_modulo is null then
    raise exception 'Revisão % não existe', p_revisao_id;
  end if;
  if not hub.pode_editar(v_modulo) then
    raise exception 'Sem permissão para enviar arquivos do módulo %', v_modulo;
  end if;
  insert into hub.revisao_arquivos (revisao_id, nome_arquivo, release_url, tamanho_bytes, publicado_por)
  values (p_revisao_id, p_nome, p_url, p_tamanho, auth.uid())
  on conflict (revisao_id, nome_arquivo) do update
    set release_url = excluded.release_url, tamanho_bytes = excluded.tamanho_bytes;
end $$;

-- Plantio: com a exportação e o projeto enviados, Andamento → Ag. Mapa.
create or replace function hub.plantio_exportacao_enviada(p_cod_faz int)
returns int
language plpgsql
security definer
set search_path = hub
as $$
begin
  if not (hub.tem_arquivo('plantio', p_cod_faz, 'exportacao', 'zip')
          and hub.tem_arquivo('plantio', p_cod_faz, 'projeto', 'dwg')) then
    raise exception 'Envie a exportação (.zip) e o projeto (.dwg) antes de avançar';
  end if;
  return hub.plantio_aplicar(p_cod_faz, array['Andamento'], false, 'Ag. Mapa', null);
end $$;

-- Preparo: mesma função de antes, agora aceitando Escoamento e Projeto de
-- Preparo quando os arquivos exigidos estão enviados.
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
end $$;

revoke all on function hub.tem_arquivo(text, int, text, text) from public, anon;
revoke all on function hub.preparar_envio(text, int, text, boolean, text) from public, anon;
revoke all on function hub.registrar_arquivo(bigint, text, text, bigint) from public, anon;
revoke all on function hub.plantio_exportacao_enviada(int) from public, anon;
grant execute on function hub.tem_arquivo(text, int, text, text) to authenticated;
grant execute on function hub.preparar_envio(text, int, text, boolean, text) to authenticated;
grant execute on function hub.registrar_arquivo(bigint, text, text, bigint) to authenticated;
grant execute on function hub.plantio_exportacao_enviada(int) to authenticated;

commit;
