-- Desfaz 20261104090000_paralelismo.sql. Apaga rodadas e análises do Paralelismo.
-- Depois, rode de novo o acesso_salvar de 20261029090000_apresentacao_acesso.sql.
begin;
drop table if exists hub.paralelismo_talhoes, hub.paralelismo_analises, hub.paralelismo_linhas, hub.paralelismo_arquivos,
  hub.paralelismo_rodadas, hub.paralelismo_reservas, hub.paralelismo_frotas;
drop function if exists hub.paralelismo_excluir(bigint), hub.paralelismo_recusar(bigint, text),
  hub.paralelismo_publicar(bigint, jsonb), hub.paralelismo_enviar(jsonb), hub.paralelismo_gravar_talhoes(bigint, jsonb),
  hub.paralelismo_url_ok(text), hub.paralelismo_talhoes_fazenda(int), hub.paralelismo_linhas_vigentes(text, int, bigint),
  hub.paralelismo_ja_analisados(text[]), hub.paralelismo_preparar_parte(bigint), hub.paralelismo_processa(),
  hub.paralelismo_nivel();
alter table hub.talhoes drop column if exists declividade;
delete from hub.usuario_modulos where modulo_id = 'paralelismo';
update hub.acessos set niveis = niveis - 'paralelismo', modulos = array_remove(modulos, 'paralelismo')
 where niveis ? 'paralelismo' or 'paralelismo' = any (modulos);
update hub.log_auditoria set modulo_id = null where modulo_id = 'paralelismo';
delete from hub.modulos where id = 'paralelismo';
alter table hub.usuario_modulos drop constraint if exists usuario_modulos_nivel_check;
alter table hub.usuario_modulos add constraint usuario_modulos_nivel_check
  check (nivel in ('leitura', 'solicitante', 'editor') and (nivel <> 'solicitante' or modulo_id = 'drone'));
commit;
