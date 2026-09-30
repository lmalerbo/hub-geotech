-- Situação atual do voo da Falha Soca por talhão (o voo mais recente de cada
-- talhão no projeto "Falhas Soca" do Drone MGMT), com quantos voos o talhão já
-- teve. Alimenta a tag de voo na tela da Colheita.

begin;

create view hub.voo_falha_soca_atual with (security_invoker = true) as
select distinct on (layer)
       layer,
       control_status,
       verify_flight_size,
       data_agendada,
       modificado_dronemgmt,
       count(*) over (partition by layer) as n_voos
  from hub.voo_dronemgmt
 where projeto_voo ilike 'falha% soca'
 order by layer, modificado_dronemgmt desc nulls last, dronemgmt_id;

grant select on hub.voo_falha_soca_atual to authenticated, service_role;

commit;
