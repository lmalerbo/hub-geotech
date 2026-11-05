-- Desfaz 20261105090000_paralelismo_cartao.sql: tira o cartão do Paralelismo de Ferramentas e deixa os outros como estão.
update hub.parametros
   set valor = (select coalesce(jsonb_agg(x), '[]'::jsonb) from jsonb_array_elements(valor::jsonb) x where x ->> 'id' is distinct from 'paralelismo')::text,
       atualizado_em = now()
 where chave = 'ferramentas' and (valor::jsonb) @> '[{"id":"paralelismo"}]'::jsonb;
