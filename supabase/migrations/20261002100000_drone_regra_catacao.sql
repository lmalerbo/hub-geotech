-- Catação: a infestação deixa de ser "buffer de 10 m em cada mancha".
-- Regra aprovada em 29/09: manchas a até 20 m viram um grupo; cada grupo vira
-- o contorno das manchas + 5 m de folga, com poucos vértices (voável pelo drone).
begin;
delete from hub.drone_parametros where chave = 'margem_infestacao_m';
insert into hub.drone_parametros (chave, valor, descricao) values
  ('agrupar_infestacao_m', '20', 'Manchas a até esta distância (m) viram um bloco só na catação'),
  ('folga_infestacao_m',   '5',  'Folga (m) em volta do contorno de cada bloco da catação')
on conflict (chave) do nothing;
commit;
