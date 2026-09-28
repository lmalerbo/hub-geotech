-- Propriedade do talhão (ex: PARCERIA/ARREND, FORNECEDOR). A Falha Soca não
-- voa em área de fornecedor, então a regra precisa dessa informação.
alter table hub.talhoes
  add column propriedade text;   -- dono: Base Fazendas (campo PROPRIEDAD)
