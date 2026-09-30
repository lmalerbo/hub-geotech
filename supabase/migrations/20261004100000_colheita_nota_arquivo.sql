-- Colheita não tem controle de revisão: existe sempre um Exp1L e um Exp2L,
-- o mais atual. Arquivo com problema é corrigido e enviado de novo por cima
-- (mesmo nome, mesmo link). O que fica registrado é uma NOTA a cada envio,
-- explicando o porquê — no histórico da fazenda (log_auditoria, campo
-- 'arquivo'). O Worker chama esta função depois de subir o arquivo.

begin;

create or replace function hub.colheita_nota_arquivo(p_cod_faz int, p_nome text, p_nota text)
returns void language plpgsql security definer set search_path = hub as $$
begin
  if not hub.pode_editar('colheita') then
    raise exception 'Sem permissão para enviar arquivos da Colheita';
  end if;
  if length(trim(coalesce(p_nota, ''))) = 0 then
    raise exception 'Informe a nota da atualização';
  end if;
  insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, usuario_id, origem)
  values ('colheita', 'fazenda', p_cod_faz, 'arquivo', p_nome || ' · ' || trim(p_nota), auth.uid(), 'usuario');
end $$;

revoke all on function hub.colheita_nota_arquivo(int, text, text) from public, anon;
grant execute on function hub.colheita_nota_arquivo(int, text, text) to authenticated, service_role;

commit;
