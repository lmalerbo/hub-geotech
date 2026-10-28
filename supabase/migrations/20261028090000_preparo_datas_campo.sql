-- Preparo: mês de entrega no lugar do mês de plantio + ciclo 25-26
-- (spec docs/superpowers/specs/2026-10-28-preparo-mes-ciclo-design.md).
--
-- 1) Datas de campo do PLANAGRI (dono: PLANAGRI, só informação, não avançam etapa).
-- 2) hub.ciclo_inicio(): 1º/abr do ciclo atual (parâmetro colheita_safra).
-- 3) hub.preparo_entregas: data de entrega de cada talhão Ok do Preparo.
-- 4) Lançamento único do ciclo 25-26 (com backup e volta).
-- 5) Avisos de uso em campo sem lançamento no Hub.

begin;

-- 1 ─────────────────────────────────────────────────────────────────────────
alter table hub.talhao_preparo add column conservacao_em date;        -- dono: PLANAGRI (CONSERVAÇÃO (DATA))
alter table hub.talhao_plantio add column plantio_realizado_em date;  -- dono: PLANAGRI (REALIZADO PLANTIO (DATA))

-- 2 ─────────────────────────────────────────────────────────────────────────
create or replace function hub.ciclo_inicio()
returns date language sql stable security definer set search_path = hub as $$
  select make_date(2000 + left(hub.safra_colheita(), 2)::int, 4, 1);
$$;

-- 3 ─────────────────────────────────────────────────────────────────────────
-- Entrega = talhão em Ok. Data: a última passagem para Ok no registro (fluxo por talhão, desde 23/10);
-- sem ela, a etapa Preparo da fazenda em etapa_status (histórico de antes). O lançamento do ciclo 25-26
-- usa a data de conservação. O lote do sistema antigo (17 a 19/06/2026) sai como lancamento_inicial.
create or replace view hub.preparo_entregas with (security_invoker = true) as
with ultimo_ok as (
  select distinct on (l.entidade_id) l.entidade_id as layer, l.criado_em, l.origem
    from hub.log_auditoria l
   where l.modulo_id = 'preparo' and l.entidade_tipo = 'talhao' and l.campo = 'etapa' and l.valor_novo = 'Ok'
   order by l.entidade_id, l.criado_em desc, l.id desc
), etapa_preparo as (
  select s.entidade_id as cod_faz, s.concluido_em
    from hub.etapa_status s join hub.etapas e on e.id = s.etapa_id
   where e.modulo_id = 'preparo' and e.nome = 'Preparo' and s.ok
)
select p.layer, t.cod_faz,
       case when u.origem = 'planagri_ciclo_25_26' then (p.conservacao_em::timestamp at time zone 'America/Sao_Paulo')
            else coalesce(u.criado_em, ep.concluido_em) end as entregue_em,
       case when u.origem = 'planagri_ciclo_25_26' then 'ciclo_25_26'
            when u.criado_em is null
             and (ep.concluido_em at time zone 'America/Sao_Paulo')::date between date '2026-06-17' and date '2026-06-19'
              then 'lancamento_inicial'
            else 'hub' end as origem
  from hub.talhao_preparo p
  join hub.talhoes t on t.layer = p.layer
  left join ultimo_ok u on u.layer = p.layer
  left join etapa_preparo ep on ep.cod_faz = t.cod_faz
 where p.etapa = 'Ok';

grant select on hub.preparo_entregas to authenticated, service_role;
revoke all on function hub.ciclo_inicio() from public, anon;
grant execute on function hub.ciclo_inicio() to authenticated, service_role;

commit;
