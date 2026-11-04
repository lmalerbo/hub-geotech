-- Corretivo: operação de preparo Experimento (28/10/2026).
alter table hub.corretivo_mapas drop constraint if exists corretivo_mapas_operacao_check;
alter table hub.corretivo_mapas add constraint corretivo_mapas_operacao_check
  check (operacao in ('subsolagem', 'supergrade', 'arado', 'experimento', 'aerea'));
