-- Drone: cancelar solicitação pela tela.
-- Editor do Drone cancela qualquer uma; o solicitante só as que ele abriu e ainda sem prévia.
-- Não cancela com o agente gerando ou publicando. A troca de status vai para o log_auditoria
-- (trigger drone_solicitacao_log) e o aviso de "nova solicitação" some sozinho.
begin;

alter table hub.drone_solicitacoes add column if not exists cancelado_motivo text;
alter table hub.drone_solicitacoes add column if not exists cancelado_por uuid references hub.usuarios (id);

create or replace function hub.drone_cancelar(p_solicitacao_id bigint, p_motivo text)
returns void language plpgsql security definer set search_path = hub as $$
declare v_sol hub.drone_solicitacoes; v_editor boolean := hub.pode_editar('drone');
begin
  select * into v_sol from hub.drone_solicitacoes where id = p_solicitacao_id for update;
  if v_sol.id is null or v_sol.origem = 'legado' then
    raise exception 'Solicitação % não existe', p_solicitacao_id;
  end if;
  if v_sol.status in ('ok', 'cancelado') then
    raise exception 'Solicitação % já está encerrada', p_solicitacao_id;
  end if;
  if length(trim(coalesce(p_motivo, ''))) = 0 then
    raise exception 'Informe o motivo do cancelamento';
  end if;
  if not v_editor then
    if v_sol.solicitante_id is distinct from auth.uid() then
      raise exception 'Só quem abriu a solicitação (ou a Geo) pode cancelar';
    end if;
    if exists (select 1 from hub.drone_geracoes where solicitacao_id = v_sol.id and status <> 'descartada') then
      raise exception 'A Geo já gerou uma prévia desta solicitação; peça o cancelamento à Geo';
    end if;
  end if;
  if exists (select 1 from hub.drone_geracoes
              where solicitacao_id = v_sol.id
                and (status = 'processando' or (status = 'pronta' and publicar_pedido_em is not null
                                                and publicacao_erro is null))) then
    raise exception 'O agente está gerando ou publicando esta solicitação; espere terminar';
  end if;
  update hub.drone_geracoes set status = 'descartada'
   where solicitacao_id = v_sol.id and status in ('fila', 'pronta', 'erro');
  update hub.drone_solicitacoes
     set status = 'cancelado', cancelado_motivo = trim(p_motivo), cancelado_por = auth.uid(), concluido_em = now()
   where id = v_sol.id;
end $$;

revoke all on function hub.drone_cancelar(bigint, text) from public, anon;
grant execute on function hub.drone_cancelar(bigint, text) to authenticated, service_role;

commit;
