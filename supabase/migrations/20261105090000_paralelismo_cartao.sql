-- Paralelismo: cartão da ferramenta em Ferramentas (página app/paralelismo.html).
-- Acrescenta ao parâmetro 'ferramentas' sem apagar o que o administrador já configurou; rodar duas vezes não duplica.
-- Quem não tem o módulo cai na tela "sem acesso" da própria página.
update hub.parametros
   set valor = ((valor::jsonb) || '[{"id":"paralelismo","nome":"Paralelismo","descricao":"Analisa o espaçamento do plantio de cana e torta a partir do pen-drive do trator e valida o resultado por talhão.","url":"https://lmalerbo.github.io/hub-geotech/paralelismo.html","icone":"straighten","cor":"#16a76b"}]'::jsonb)::text,
       atualizado_em = now()
 where chave = 'ferramentas'
   and not ((valor::jsonb) @> '[{"id":"paralelismo"}]'::jsonb);
