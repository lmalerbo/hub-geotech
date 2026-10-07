-- Drone Parte 2: trava no drone_publicar contra geração sem talhões (revisão final, item 1).
begin;
create or replace function hub.drone_publicar(
  p_cod_faz int, p_documento text, p_motivo text, p_numero int, p_arquivos jsonb,
  p_geracao_id bigint default null, p_legado boolean default false, p_talhoes jsonb default null)
returns bigint language plpgsql security definer set search_path = hub, extensions as $$
declare v_proj bigint; v_rev bigint; v_num int; v_sol bigint;
begin
  -- trava: geração sem talhões (ex.: agente antigo, antes do git pull) não pode virar revisão vazia
  if p_geracao_id is not null and not exists (select 1 from hub.drone_geracao_talhoes where geracao_id = p_geracao_id) then
    raise exception 'Geração % sem talhões gravados: atualize o agente do servidor (git pull) e gere de novo', p_geracao_id;
  end if;
  insert into hub.projetos (modulo_id, tipo, cod_faz, nome)
  select 'drone', 'individual', f.cod_faz, f.nome from hub.fazendas f where f.cod_faz = p_cod_faz
  on conflict (modulo_id, cod_faz) where tipo = 'individual' do nothing;
  select id into v_proj from hub.projetos
   where modulo_id = 'drone' and tipo = 'individual' and cod_faz = p_cod_faz;
  if v_proj is null then
    raise exception 'Fazenda % não existe em hub.fazendas', p_cod_faz;
  end if;

  v_rev := hub.nova_revisao(v_proj, p_documento, p_motivo);
  select numero into v_num from hub.projeto_revisoes where id = v_rev;
  if v_num <> p_numero then
    raise exception 'A revisão mudou: arquivos enviados como Rev%, mas a próxima é Rev%. Gere o projeto de novo.',
      p_numero, v_num;
  end if;

  insert into hub.revisao_arquivos (revisao_id, nome_arquivo, release_url, tamanho_bytes)
  select v_rev, a.nome, a.url, a.tamanho
    from jsonb_to_recordset(p_arquivos) as a (nome text, url text, tamanho bigint);

  if p_geracao_id is not null then
    insert into hub.drone_revisao_talhoes (revisao_id, talhao_num, geom, area_ha, origem, desde_rev)
    select v_rev, talhao_num, geom, area_ha, origem, desde_rev
      from hub.drone_geracao_talhoes where geracao_id = p_geracao_id;
    update hub.drone_geracoes set status = 'publicada', concluido_em = now()
     where id = p_geracao_id and status = 'pronta' returning solicitacao_id into v_sol;
    if v_sol is null then
      raise exception 'Geração % não está pronta para publicar', p_geracao_id;
    end if;
    update hub.drone_geracoes set status = 'descartada'
     where solicitacao_id = v_sol and id <> p_geracao_id and status in ('fila', 'pronta', 'erro');
    update hub.drone_solicitacoes set status = 'ok', revisao_id = v_rev, concluido_em = now()
     where id = v_sol;
  elsif p_talhoes is not null then
    insert into hub.drone_revisao_talhoes (revisao_id, talhao_num, geom, area_ha, origem, desde_rev)
    select v_rev, (e->>'talhao')::int, ST_Multi(ST_GeomFromText(e->>'wkt', 31983)),
           (e->>'area_ha')::numeric, e->>'origem', (e->>'desde_rev')::int
      from jsonb_array_elements(p_talhoes) e;
  end if;

  if p_legado then
    insert into hub.drone_solicitacoes (cod_faz, tipo, origem, status, revisao_id, concluido_em)
    values (p_cod_faz, p_documento, 'legado', 'ok', v_rev, now());
  end if;
  return v_rev;
end $$;
revoke all on function hub.drone_publicar(int, text, text, int, jsonb, bigint, boolean, jsonb) from public, anon, authenticated;
grant execute on function hub.drone_publicar(int, text, text, int, jsonb, bigint, boolean, jsonb) to service_role;
commit;
