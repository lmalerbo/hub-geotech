-- Impressão digital (md5) das tabelas que o fluxo e a tela de Usuários tocam. Rodar antes e depois
-- de um teste no banco real: tem de dar igual.
select 'talhao_plantio' t, md5(string_agg(x::text, '|' order by layer)) from hub.talhao_plantio x
union all select 'talhao_preparo', md5(string_agg(x::text, '|' order by layer)) from hub.talhao_preparo x
union all select 'etapa_status', md5(string_agg(x::text, '|' order by etapa_id, entidade_id)) from hub.etapa_status x
union all select 'projeto_revisoes', md5(string_agg(x::text, '|' order by id)) from hub.projeto_revisoes x
union all select 'log_auditoria', md5(string_agg(x::text, '|' order by id)) from hub.log_auditoria x
union all select 'usuario_modulos', md5(string_agg(x::text, '|' order by usuario_id, modulo_id)) from hub.usuario_modulos x
union all select 'acessos', md5(string_agg(x::text, '|' order by email)) from hub.acessos x
union all select 'funcoes_hub', md5(string_agg(p.oid::regprocedure::text || pg_get_functiondef(p.oid) || coalesce(p.proacl::text,''), '|' order by p.oid::regprocedure::text)) from pg_proc p where pronamespace='hub'::regnamespace and prokind='f';
