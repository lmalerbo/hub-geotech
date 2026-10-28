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

-- 4 ─────────────────────────────────────────────────────────────────────────
-- Lançamento único: talhão do Preparo ainda não Ok com conservação antes de 01/04/2026 passa para Ok
-- (registro com origem planagri_ciclo_25_26). Fazenda que fica inteira Ok ganha as 4 etapas em
-- etapa_status com a maior data de conservação, sem usuário e com o selo (observação existente fica).
create table hub.etapa_status_backup (
  lote_id      bigint      not null,
  linha        jsonb       not null,   -- a linha de etapa_status antes do lançamento
  existia      boolean     not null,   -- false = a linha foi criada pelo lançamento (a volta apaga)
  escrito_em   timestamptz not null    -- concluido_em que o lançamento gravou (a volta só mexe se ainda for esse)
);
alter table hub.etapa_status_backup enable row level security;

create or replace function hub.preparo_ciclo_25_26_candidatos()
returns table (cod_faz int, fazenda text, talhao_num int, layer bigint, area_ha numeric, conservacao_em date, etapa text)
language sql stable security definer set search_path = hub, pg_temp as $$
  select t.cod_faz, f.nome, t.talhao_num, p.layer, t.area_ha::numeric, p.conservacao_em, p.etapa
    from hub.talhao_preparo p
    join hub.talhoes t on t.layer = p.layer
    left join hub.fazendas f on f.cod_faz = t.cod_faz
   where p.etapa <> 'Ok' and p.conservacao_em < date '2026-04-01'
   order by t.cod_faz, t.talhao_num;
$$;

create or replace function hub.preparo_lancar_ciclo_25_26()
returns bigint language plpgsql security definer set search_path = hub, pg_temp as $$
declare
  v_selo   constant text := 'ciclo 25-26 · pelo PLANAGRI';
  v_lote   bigint;
  v_layers bigint[];
begin
  select array_agg(c.layer) into v_layers from hub.preparo_ciclo_25_26_candidatos() c;
  if v_layers is null then return null; end if;
  v_lote := nextval('hub.log_lote_seq');
  perform hub.projeto_mudar_etapa('preparo', v_layers, 'Ok', v_lote, 'planagri_ciclo_25_26', v_selo);

  -- Fazendas que ficaram inteiras Ok com este lote ganham as 4 etapas em etapa_status, mas só as que
  -- ainda não estão ok: linha já ok (com usuário e data reais) fica intacta. O backup guarda só o que muda.
  with faz as (
    select t.cod_faz, (max(p.conservacao_em) + time '12:00') at time zone 'America/Sao_Paulo' as data
      from hub.talhoes t join hub.talhao_preparo p on p.layer = t.layer
     where t.cod_faz in (select t2.cod_faz from hub.talhoes t2 where t2.layer = any(v_layers))
     group by t.cod_faz
    having bool_and(p.etapa = 'Ok')
  ), alvo as (
    select e.id as etapa_id, f.cod_faz, f.data, s
      from faz f cross join hub.etapas e
      left join hub.etapa_status s on s.etapa_id = e.id and s.entidade_id = f.cod_faz
     where e.modulo_id = 'preparo' and (s.etapa_id is null or not s.ok)
  ), bkp as (
    insert into hub.etapa_status_backup (lote_id, linha, existia, escrito_em)
    select v_lote, coalesce(to_jsonb(a.s), jsonb_build_object('etapa_id', a.etapa_id, 'entidade_id', a.cod_faz)),
           (a.s).etapa_id is not null, a.data
      from alvo a
    returning 1
  )
  insert into hub.etapa_status (etapa_id, entidade_id, ok, usuario_id, concluido_em, observacao)
  select a.etapa_id, a.cod_faz, true, null, a.data, v_selo from alvo a
  on conflict (etapa_id, entidade_id) do update
     set ok = true, usuario_id = null, concluido_em = excluded.concluido_em,
         observacao = coalesce(nullif(hub.etapa_status.observacao, ''), excluded.observacao)
   where not hub.etapa_status.ok;
  return v_lote;
end $$;

-- Desfaz o lote só onde nada mudou depois dele. O que foi mexido por outra pessoa fica como está e a
-- linha do log correspondente fica, como rastro. Devolve os talhões restaurados (avisa os pulados).
create or replace function hub.preparo_voltar_ciclo_25_26(p_lote bigint)
returns int language plpgsql security definer set search_path = hub, pg_temp as $$
declare
  v_selo  constant text := 'ciclo 25-26 · pelo PLANAGRI';
  v_qtd   int;
  v_total int;
  v_pul_t int;
  v_pul_e int;
begin
  select count(*) into v_total from hub.log_auditoria
   where lote_id = p_lote and origem = 'planagri_ciclo_25_26' and modulo_id = 'preparo' and campo = 'etapa';

  with r as (
    update hub.talhao_preparo p set etapa = l.valor_anterior
      from hub.log_auditoria l
     where l.lote_id = p_lote and l.origem = 'planagri_ciclo_25_26' and l.modulo_id = 'preparo' and l.campo = 'etapa'
       and l.entidade_id = p.layer and p.etapa = l.valor_novo
    returning p.layer
  ), d as (
    delete from hub.log_auditoria l
     where l.lote_id = p_lote and l.origem = 'planagri_ciclo_25_26' and l.modulo_id = 'preparo' and l.campo = 'etapa'
       and l.entidade_id in (select layer from r)
    returning 1
  )
  select count(*) into v_qtd from r;
  v_pul_t := v_total - v_qtd;

  -- etapa_status: só onde a linha ainda é a que o lote gravou (ok, sem usuário, mesma data, mesma observação)
  with igual as (
    select b.*, s.etapa_id, s.entidade_id
      from hub.etapa_status_backup b
      join hub.etapa_status s on s.etapa_id = (b.linha->>'etapa_id')::bigint and s.entidade_id = (b.linha->>'entidade_id')::bigint
     where b.lote_id = p_lote and s.ok and s.usuario_id is null and s.concluido_em = b.escrito_em
       and s.observacao is not distinct from coalesce(nullif(b.linha->>'observacao', ''), v_selo)
  ), apaga as (
    delete from hub.etapa_status s using igual i
     where not i.existia and s.etapa_id = i.etapa_id and s.entidade_id = i.entidade_id
    returning s.etapa_id, s.entidade_id
  ), volta as (
    update hub.etapa_status s
       set ok = (i.linha->>'ok')::boolean, usuario_id = (i.linha->>'usuario_id')::uuid,
           concluido_em = (i.linha->>'concluido_em')::timestamptz, observacao = i.linha->>'observacao'
      from igual i
     where i.existia and s.etapa_id = i.etapa_id and s.entidade_id = i.entidade_id
    returning s.etapa_id, s.entidade_id
  ), limpa as (
    delete from hub.etapa_status_backup b
     where b.lote_id = p_lote
       and ((b.linha->>'etapa_id')::bigint, (b.linha->>'entidade_id')::bigint) in
           (select etapa_id, entidade_id from apaga union select etapa_id, entidade_id from volta)
    returning 1
  )
  select (select count(*) from hub.etapa_status_backup where lote_id = p_lote) - (select count(*) from limpa)
    into v_pul_e;

  if v_pul_t > 0 or v_pul_e > 0 then
    raise notice 'volta do lote %: % talhão(ões) e % etapa(s) de fazenda mudaram depois do lançamento e foram mantidos (o log deles ficou)',
      p_lote, v_pul_t, v_pul_e;
  end if;
  return v_qtd;
end $$;

revoke all on function hub.preparo_ciclo_25_26_candidatos() from public, anon, authenticated;
revoke all on function hub.preparo_lancar_ciclo_25_26()     from public, anon, authenticated;
revoke all on function hub.preparo_voltar_ciclo_25_26(bigint) from public, anon, authenticated;
grant execute on function hub.preparo_ciclo_25_26_candidatos() to service_role;
grant execute on function hub.preparo_lancar_ciclo_25_26()     to service_role;
grant execute on function hub.preparo_voltar_ciclo_25_26(bigint) to service_role;

commit;
