-- Teste de ponta a ponta do fluxo de projetos no banco REAL, depois da migração 20261023100000.
-- Roda tudo numa transação e termina em rollback: nada fica gravado. Conferir antes/depois com
-- tests/fluxo/impressao_banco.sql (as impressões têm de ser iguais).
-- supabase db query --linked -o csv -f tests/fluxo/ponta_a_ponta_banco_real.sql
begin;
create temp table _r (ord serial, passo text, valor text);
grant all on _r, _r_ord_seq to authenticated;
insert into _r (passo, valor) select 'preparo: talhoes por etapa', string_agg(etapa || '=' || n, ', ' order by etapa) from (select etapa, count(*) n from hub.talhao_preparo group by 1) x;
insert into _r (passo, valor) select 'preparo: etapa das fazendas 10329/10828', coalesce(string_agg(t.cod_faz || ':' || tp.etapa, ', '), 'sem talhao') from hub.talhao_preparo tp join hub.talhoes t on t.layer = tp.layer where t.cod_faz in (10329, 10828);
do $$
declare v_uid uuid; v_leitor uuid; v_faz int; v_faz2 int; v_tal int; v_ntal int; n int; v_lote bigint; v_map0 text; v_rev record; v_num0 int; v_faz3 int; v_tal3 int;
begin
  select m.usuario_id into v_uid from hub.usuario_modulos m join hub.usuarios u on u.id = m.usuario_id
   where m.modulo_id = 'preparo' and m.nivel = 'editor' and not u.admin
     and exists (select 1 from hub.usuario_modulos m2 where m2.usuario_id = m.usuario_id and m2.modulo_id = 'plantio' and m2.nivel = 'editor')
   order by 1 limit 1;
  select m.usuario_id into v_leitor from hub.usuario_modulos m join hub.usuarios u on u.id = m.usuario_id
   where m.modulo_id = 'preparo' and m.nivel = 'leitura' and not u.admin order by 1 limit 1;
  select t.cod_faz, count(*) into v_faz, v_ntal from hub.talhao_preparo tp join hub.talhoes t on t.layer = tp.layer
   group by t.cod_faz having bool_and(tp.etapa = 'Identificação') and count(*) >= 2 order by t.cod_faz limit 1;
  select t.cod_faz, t.talhao_num, p.mapeamento into v_faz2, v_tal, v_map0 from hub.talhao_plantio p join hub.talhoes t on t.layer = p.layer
   where p.projeto = 'Aguard. Map.' order by 1, 2 limit 1;
  select t.cod_faz, t.talhao_num into v_faz3, v_tal3 from hub.talhao_plantio p join hub.talhoes t on t.layer = p.layer
   where p.projeto = 'Ok' order by 1, 2 limit 1;
  select coalesce(max(r.numero), -1) into v_num0 from hub.projeto_revisoes r join hub.projetos pr on pr.id = r.projeto_id
   where pr.modulo_id = 'plantio' and pr.cod_faz = v_faz3;
  insert into _r (passo, valor) values ('escolhidos: editor / leitor', v_uid || ' / ' || v_leitor),
    ('escolhidos: fazenda Preparo (talhoes)', v_faz || ' (' || v_ntal || ')'),
    ('escolhidos: fazenda/talhao Plantio, mapeamento', v_faz2 || '/' || v_tal || ', ' || coalesce(v_map0, 'null'));

  perform set_config('request.jwt.claim.sub', v_uid::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', v_uid, 'role', 'authenticated')::text, true);
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  execute 'set local role authenticated';

  -- Preparo: avança a fazenda, volta com justificativa, desfaz
  n := hub.projeto_avancar('preparo', v_faz, 'identificacao', null, null);
  insert into _r (passo, valor) select 'E2E preparo avancar identificacao: qtd / etapas', n || ' / ' || string_agg(distinct tp.etapa, ',')
    from hub.talhao_preparo tp join hub.talhoes t on t.layer = tp.layer where t.cod_faz = v_faz;
  begin
    v_lote := hub.projeto_retroceder('preparo', v_faz, 'Identificação', '', null);
    insert into _r (passo, valor) values ('E2E retroceder sem justificativa', 'FALHA: aceitou');
  exception when others then insert into _r (passo, valor) values ('E2E retroceder sem justificativa', 'ok, recusou: ' || sqlerrm);
  end;
  v_lote := hub.projeto_retroceder('preparo', v_faz, 'Identificação', 'teste ponta a ponta (desfeito)', null);
  insert into _r (passo, valor) select 'E2E preparo retroceder: lote / etapas', v_lote || ' / ' || string_agg(distinct tp.etapa, ',')
    from hub.talhao_preparo tp join hub.talhoes t on t.layer = tp.layer where t.cod_faz = v_faz;
  n := hub.projeto_desfazer(v_lote);
  insert into _r (passo, valor) select 'E2E preparo desfazer: qtd / etapas', n || ' / ' || string_agg(distinct tp.etapa, ',')
    from hub.talhao_preparo tp join hub.talhoes t on t.layer = tp.layer where t.cod_faz = v_faz;

  -- Plantio: um talhão só
  n := hub.projeto_avancar('plantio', v_faz2, 'mapeamento_concluido', array[v_tal], null);
  insert into _r (passo, valor) select 'E2E plantio avancar 1 talhao: qtd / projeto,mapeamento / outros ainda Aguard.', n || ' / ' ||
    (select p.projeto || ',' || p.mapeamento from hub.talhao_plantio p join hub.talhoes t on t.layer = p.layer where t.cod_faz = v_faz2 and t.talhao_num = v_tal) || ' / ' ||
    (select count(*) from hub.talhao_plantio p join hub.talhoes t on t.layer = p.layer where t.cod_faz = v_faz2 and t.talhao_num <> v_tal and p.projeto = 'Aguard. Map.');
  v_lote := hub.projeto_retroceder('plantio', v_faz2, 'Aguard. Map.', 'teste ponta a ponta (desfeito)', array[v_tal]);
  insert into _r (passo, valor) select 'E2E plantio retroceder: projeto,mapeamento (orig ' || coalesce(v_map0, 'null') || ')',
    (select p.projeto || ',' || coalesce(p.mapeamento, 'null') from hub.talhao_plantio p join hub.talhoes t on t.layer = p.layer where t.cod_faz = v_faz2 and t.talhao_num = v_tal);
  n := hub.projeto_desfazer(v_lote);
  insert into _r (passo, valor) select 'E2E plantio desfazer: qtd / projeto', n || ' / ' ||
    (select p.projeto from hub.talhao_plantio p join hub.talhoes t on t.layer = p.layer where t.cod_faz = v_faz2 and t.talhao_num = v_tal);
  select * into v_rev from hub.projeto_nova_revisao('plantio', v_faz3, 'teste ponta a ponta (desfeito)', '{projeto}', array[v_tal3]) limit 1;
  insert into _r (passo, valor) values ('E2E nova revisao faz ' || v_faz3 || ' talhao ' || v_tal3 || ': numero (esperado ' || (v_num0 + 1) || ') / sufixo / etapa do talhao',
    v_rev.numero || ' / ' || v_rev.sufixo || ' / ' ||
    (select p.projeto from hub.talhao_plantio p join hub.talhoes t on t.layer = p.layer where t.cod_faz = v_faz3 and t.talhao_num = v_tal3));
  insert into _r (passo, valor) select 'E2E linha do tempo: eventos / tipos', count(*) || ' / ' || string_agg(distinct tipo, ',')
    from hub.projeto_linha_do_tempo('plantio', v_faz2);
  -- a tela publicada hoje usa as RPCs antigas
  begin
    perform hub.plantio_mapeamento_concluido(v_faz2);
    insert into _r (passo, valor) select 'E2E RPC antiga plantio_mapeamento_concluido: Aguard. restantes', count(*)::text
      from hub.talhao_plantio p join hub.talhoes t on t.layer = p.layer where t.cod_faz = v_faz2 and p.projeto = 'Aguard. Map.';
  exception when others then insert into _r (passo, valor) values ('E2E RPC antiga plantio_mapeamento_concluido', 'ERRO: ' || sqlerrm);
  end;

  -- Leitor não avança
  perform set_config('request.jwt.claim.sub', v_leitor::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', v_leitor, 'role', 'authenticated')::text, true);
  begin
    n := hub.projeto_avancar('preparo', v_faz, 'escoamento', null, null);
    insert into _r (passo, valor) values ('E2E leitor tenta avancar', 'FALHA: aceitou');
  exception when others then insert into _r (passo, valor) values ('E2E leitor tenta avancar', 'ok, recusou: ' || sqlerrm);
  end;
  execute 'reset role';
  perform set_config('request.jwt.claim.sub', '', true);
  perform set_config('request.jwt.claims', '', true);
  perform set_config('request.jwt.claim.role', '', true);
  insert into _r (passo, valor) values ('(interno) faz preparo', v_faz::text);
end $$;
select passo, valor from _r where passo not like '(interno)%' order by ord;
rollback;
