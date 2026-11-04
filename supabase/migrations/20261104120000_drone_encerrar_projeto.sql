-- Drone: encerrar o projeto de uma fazenda que saiu inteira da Base de Talhões.
-- As revisões deixam de ser vigentes (saem do portal e da faixa Atenção) e continuam guardadas.
-- Se a fazenda voltar à Base, uma nova revisão publicada torna o projeto vigente de novo.
begin;

alter table hub.projetos add column if not exists encerrado_em timestamptz;
alter table hub.projetos add column if not exists encerrado_por uuid references hub.usuarios (id);
alter table hub.projetos add column if not exists encerrado_motivo text;

create or replace function hub.drone_encerrar_projeto(p_cod_faz int, p_motivo text)
returns void language plpgsql security definer set search_path = hub as $$
declare v_proj bigint;
begin
  if not hub.pode_editar('drone') then
    raise exception 'Sem permissão para encerrar projetos de drone';
  end if;
  if length(trim(coalesce(p_motivo, ''))) = 0 then
    raise exception 'Informe o motivo do encerramento';
  end if;
  select id into v_proj from hub.projetos
   where modulo_id = 'drone' and tipo = 'individual' and cod_faz = p_cod_faz for update;
  if v_proj is null or not exists (select 1 from hub.projeto_revisoes where projeto_id = v_proj and vigente) then
    raise exception 'A fazenda % não tem projeto vigente', p_cod_faz;
  end if;
  if exists (select 1 from hub.talhao_geom where cod_faz = p_cod_faz) then
    raise exception 'A fazenda % ainda tem talhões na Base; para tirar talhões, use Remover numa revisão', p_cod_faz;
  end if;
  if exists (select 1 from hub.drone_geracoes g join hub.drone_solicitacoes s on s.id = g.solicitacao_id
              where s.cod_faz = p_cod_faz
                and (g.status = 'processando' or (g.status = 'pronta' and g.publicar_pedido_em is not null
                                                  and g.publicacao_erro is null))) then
    raise exception 'O agente está gerando ou publicando esta fazenda; espere terminar';
  end if;
  update hub.drone_geracoes g set status = 'descartada'
    from hub.drone_solicitacoes s
   where s.id = g.solicitacao_id and s.cod_faz = p_cod_faz and s.status not in ('ok', 'cancelado')
     and g.status in ('fila', 'pronta', 'erro');
  update hub.drone_solicitacoes
     set status = 'cancelado', cancelado_motivo = trim(p_motivo), cancelado_por = auth.uid(), concluido_em = now()
   where cod_faz = p_cod_faz and origem <> 'legado' and status not in ('ok', 'cancelado');
  update hub.projeto_revisoes set vigente = false where projeto_id = v_proj and vigente;
  update hub.projetos set encerrado_em = now(), encerrado_por = auth.uid(), encerrado_motivo = trim(p_motivo)
   where id = v_proj;
end $$;

revoke all on function hub.drone_encerrar_projeto(int, text) from public, anon;
grant execute on function hub.drone_encerrar_projeto(int, text) to authenticated, service_role;

commit;
