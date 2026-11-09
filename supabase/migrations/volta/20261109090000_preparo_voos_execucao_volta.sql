-- Desfaz 20261109090000_preparo_voos_execucao.sql. Apaga as execuções da fonte voos_preparo
-- (a restrição antiga não as aceita). Reverta antes o app (FONTES_DIARIAS) e o ingestao/voos_preparo.py.
begin;

delete from hub.execucoes_ingestao where fonte = 'voos_preparo';
alter table hub.execucoes_ingestao drop constraint if exists execucoes_ingestao_fonte_check;
alter table hub.execucoes_ingestao add constraint execucoes_ingestao_fonte_check
  check (fonte in ('base_fazendas', 'planagri', 'icol', 'conservacao', 'dronemgmt', 'talhao_geom'));

create or replace function hub.preparo_aviso_sem_voo(p_cod_faz int, p_talhoes int[])
returns int language plpgsql security definer set search_path = hub as $$
declare
  v_n int;
begin
  perform hub.projeto_conferir('preparo', p_cod_faz);
  insert into log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, usuario_id, origem)
  select 'preparo', 'talhao', p_cod_faz::bigint * 1000 + t, 'voo_aviso', 'avancou_sem_voo', auth.uid(), 'usuario'
    from unnest(p_talhoes) t;
  get diagnostics v_n = row_count;
  return v_n;
end $$;

revoke all on function hub.preparo_aviso_sem_voo(int, int[]) from public, anon;
grant execute on function hub.preparo_aviso_sem_voo(int, int[]) to authenticated;

commit;
