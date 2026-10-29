-- Preparo: fase de voo antes da Identificação (spec 2026-10-29-preparo-fase-voo-design.md).
-- O Hub só lê o Drone MGMT. O agente ingestao/voos_preparo.py grava aqui os registros de
-- Sistematização/Expansão das fazendas com talhões em Identificação. A etapa do talhão não muda.

-- 1 ─────────────────────────────────────────────────────────────────────────
alter table hub.voo_dronemgmt add column criado_dronemgmt timestamptz;  -- createdUtc do registro

-- Quando o agente leu cada fazenda (sem linha = nunca lida → "Voo sem leitura").
create table hub.preparo_voos_leitura (
  cod_faz  int primary key,
  lido_em  timestamptz not null default now()
);
alter table hub.preparo_voos_leitura enable row level security;
create policy leitura_autenticado on hub.preparo_voos_leitura for select to authenticated using (true);

-- 2 ─────────────────────────────────────────────────────────────────────────
-- Substitui, nas fazendas lidas, os registros de Sistematização/Expansão pelo que veio agora
-- (o que sumiu do Drone MGMT sai daqui). landPlot não numérico é ignorado.
create or replace function hub.preparo_voos_gravar(p_secoes int[], p_registros jsonb)
returns int language plpgsql security definer set search_path = hub as $$
declare
  v_n int;
begin
  delete from voo_dronemgmt v
   where v.projeto_voo in ('Sistematização', 'Expansão')
     and (v.layer / 1000)::int = any(p_secoes)
     and not exists (select 1 from jsonb_array_elements(coalesce(p_registros, '[]'::jsonb)) r
                      where r->>'id' = v.dronemgmt_id::text);

  -- case: o cast só roda depois da checagem (o where não garante ordem de avaliação).
  insert into voo_dronemgmt (dronemgmt_id, layer, projeto_voo, control_status, verify_flight_size,
                             data_agendada, inicio_voo, criado_dronemgmt, modificado_dronemgmt, sincronizado_em)
  select dronemgmt_id, layer, projeto_voo, control_status, verify_flight_size,
         data_agendada, inicio_voo, criado_dronemgmt, modificado_dronemgmt, now()
    from (select (r->>'id')::uuid                       as dronemgmt_id,
                 case when r->>'section' ~ '^\d+$' and r->>'landPlot' ~ '^\d+$'
                      then (r->>'section')::bigint * 1000 + (r->>'landPlot')::bigint end as layer,
                 r->>'projeto'                          as projeto_voo,
                 (r->>'controlStatus')::int             as control_status,
                 (r->>'verifyFlightSize')::int          as verify_flight_size,
                 (r->>'scheduledDate')::timestamptz     as data_agendada,
                 (r->>'startDateFlight')::timestamptz   as inicio_voo,
                 (r->>'createdUtc')::timestamptz        as criado_dronemgmt,
                 (r->>'modifiedUtc')::timestamptz       as modificado_dronemgmt
            from jsonb_array_elements(coalesce(p_registros, '[]'::jsonb)) r
           where r->>'projeto' in ('Sistematização', 'Expansão')) n
   where layer is not null and (layer / 1000)::int = any(p_secoes)
  on conflict (dronemgmt_id) do update
     set layer = excluded.layer, projeto_voo = excluded.projeto_voo, control_status = excluded.control_status,
         verify_flight_size = excluded.verify_flight_size, data_agendada = excluded.data_agendada,
         inicio_voo = excluded.inicio_voo, criado_dronemgmt = excluded.criado_dronemgmt,
         modificado_dronemgmt = excluded.modificado_dronemgmt, sincronizado_em = now();
  get diagnostics v_n = row_count;

  insert into preparo_voos_leitura (cod_faz, lido_em)
  select unnest(p_secoes), now()
  on conflict (cod_faz) do update set lido_em = excluded.lido_em;
  return v_n;
end $$;

-- 3 ─────────────────────────────────────────────────────────────────────────
-- Situação do voo de cada talhão em Identificação, pelo registro mais avançado da safra atual.
-- controlStatus: 1–3 solicitado, 4–8 processando, 9/10/12 liberado, 11 cancelado (ignorado).
create or replace view hub.preparo_voo_talhao with (security_invoker = true) as
select p.layer,
       case when l.cod_faz is null then 'sem_leitura'
            else (array['nao_solicitado', 'solicitado', 'processando', 'liberado'])[1 + coalesce(max(
                   case when v.control_status in (9, 10, 12)  then 3
                        when v.control_status between 4 and 8 then 2
                        when v.control_status between 1 and 3 then 1 end), 0)]
       end as situacao,
       l.lido_em
  from hub.talhao_preparo p
  left join hub.preparo_voos_leitura l on l.cod_faz = (p.layer / 1000)::int
  left join hub.voo_dronemgmt v on v.layer = p.layer
        and v.projeto_voo in ('Sistematização', 'Expansão')
        and v.control_status is distinct from 11
        and v.criado_dronemgmt >= hub.ciclo_inicio()
 where p.etapa = 'Identificação'
 group by p.layer, l.cod_faz, l.lido_em;

grant select on hub.preparo_voo_talhao to authenticated, service_role;
grant select on hub.preparo_voos_leitura to authenticated;
grant all on hub.preparo_voos_leitura to service_role;
revoke all on function hub.preparo_voos_gravar(int[], jsonb) from public, anon, authenticated;
grant execute on function hub.preparo_voos_gravar(int[], jsonb) to service_role;

-- 4 ─────────────────────────────────────────────────────────────────────────
-- O analista avançou da Identificação talhões sem material de voo (aviso aceito na tela).
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