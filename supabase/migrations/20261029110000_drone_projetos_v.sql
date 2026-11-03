-- Drone de aplicação como dado do Hub (spec 2026-10-29, D4): ha de aplicação e safra por projeto vigente.
-- Projeto feito no Hub: ha do resumo da geração publicada; safra pela data da revisão.
-- Projeto do legado: colunas preenchidas uma vez por drone/carga_area_safra.py.
begin;

alter table hub.projeto_revisoes add column if not exists area_aplicacao_ha numeric;
alter table hub.projeto_revisoes add column if not exists safra text check (safra is null or safra ~ '^\d\d/\d\d$');

create or replace function hub.safra_de(p date)
returns text language sql immutable as $$
  select lpad((a % 100)::text, 2, '0') || '/' || lpad(((a + 1) % 100)::text, 2, '0')
    from (select case when extract(month from p) >= 4 then extract(year from p)::int
                      else extract(year from p)::int - 1 end as a) s;
$$;

create or replace view hub.drone_projetos_v with (security_invoker = true) as
select p.id as projeto_id, p.cod_faz, r.id as revisao_id, r.documento,
       coalesce(r.area_aplicacao_ha, (g.resumo ->> 'aplicacao_ha')::numeric) as area_aplicacao_ha,
       coalesce(r.safra, case when g.id is not null
                              then hub.safra_de((r.criado_em at time zone 'America/Sao_Paulo')::date) end) as safra,
       case when r.area_aplicacao_ha is not null then 'legado'
            when g.id is not null then 'hub'
            else 'sem_dado' end as origem
  from hub.projetos p
  join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente
  left join lateral (
    select g.id, g.resumo
      from hub.drone_solicitacoes s
      join hub.drone_geracoes g on g.solicitacao_id = s.id and g.status = 'publicada'
     where s.revisao_id = r.id
     order by g.concluido_em desc nulls last, g.id desc
     limit 1) g on true
 where p.modulo_id = 'drone' and p.tipo = 'individual';

grant select on hub.drone_projetos_v to authenticated;

commit;
