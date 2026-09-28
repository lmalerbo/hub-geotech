-- 1) Pendências de cadastro: o que cada importação ignorou por não existir na
--    Base Fazendas (ex: talhões de fazenda em reforma redividida), pro Hub
--    mostrar numa lista. A Base Fazendas continua sendo a única porta de
--    entrada de talhão.
alter table hub.execucoes_ingestao
  add column detalhes jsonb;

-- 2) Regra de conservação → Plantio (mesmo comportamento do sistema atual):
--    - Base Larga / Sem Conservação liberam o mapeamento (Não → Sim; nunca volta).
--    - Projeto em Pendente/Aguard. Map. é recalculado: Pendente se o
--      mapeamento é Sim ou o tipo libera, senão Aguard. Map. Andamento e Ok
--      nunca são tocados.
--    Cada mudança vai pro log_auditoria com origem 'regra_conservacao'.
create or replace function hub.aplicar_regra_conservacao()
returns table (mapeamento_liberado int, projeto_recalculado int)
language plpgsql
set search_path = hub
as $$
declare
  v_map  int;
  v_proj int;
begin
  with mudou as (
    update hub.talhao_plantio p
       set mapeamento = 'Sim'
      from hub.talhoes t
     where t.layer = p.layer
       and t.sist_conser in ('Base Larga', 'Sem Conservação')
       and p.mapeamento <> 'Sim'
    returning p.layer
  ), registro as (
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo, origem)
    select 'plantio', 'talhao', m.layer, 'mapeamento', 'Não', 'Sim', 'regra_conservacao'
      from mudou m
    returning 1
  )
  select count(*) into v_map from registro;

  with alvo as (
    select p.layer,
           p.projeto as antes,
           case when p.mapeamento = 'Sim' or t.sist_conser in ('Base Larga', 'Sem Conservação')
                then 'Pendente' else 'Aguard. Map.' end as depois
      from hub.talhao_plantio p
      join hub.talhoes t on t.layer = p.layer
     where p.projeto in ('Pendente', 'Aguard. Map.')
  ), mudou as (
    update hub.talhao_plantio p
       set projeto = a.depois
      from alvo a
     where a.layer = p.layer
       and a.antes <> a.depois
    returning p.layer, a.antes, a.depois
  ), registro as (
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo, origem)
    select 'plantio', 'talhao', m.layer, 'projeto', m.antes, m.depois, 'regra_conservacao'
      from mudou m
    returning 1
  )
  select count(*) into v_proj from registro;

  return query select v_map, v_proj;
end $$;

revoke all on function hub.aplicar_regra_conservacao() from public, anon, authenticated;
grant execute on function hub.aplicar_regra_conservacao() to service_role;
