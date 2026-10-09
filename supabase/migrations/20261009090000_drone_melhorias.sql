-- Drone: avisos no sininho, gravação de envios em lote (sem duplicar), travas,
-- prévias só para quem edita o Drone, obstáculos no mapa e resumo (dashboard/Consultas).
begin;

-- ── envio de origem: reprocessar o mesmo envio não duplica ─────────────
alter table hub.drone_obstaculo_versoes add column if not exists envio_id bigint references hub.drone_envios (id);
alter table hub.drone_infestacoes add column if not exists envio_id bigint references hub.drone_envios (id);

create or replace function hub.drone_gravar_obstaculos_lote(p_cod_faz int, p_origem text, p_itens jsonb,
                                                            p_usuario uuid default null, p_envio_id bigint default null)
returns int language plpgsql security definer set search_path = hub, extensions as $$
declare e jsonb; v_versao int; v_id bigint; v_classe int; n int := 0;
begin
  if p_envio_id is not null and exists (select 1 from hub.drone_obstaculo_versoes where envio_id = p_envio_id) then
    return 0;                                         -- envio já gravado (agente caiu depois de gravar)
  end if;
  for e in select * from jsonb_array_elements(p_itens) loop
    v_classe := (e->>'classe_m')::int;
    perform pg_advisory_xact_lock(hashtext('drone_obst_' || p_cod_faz || '_' || v_classe));
    select coalesce(max(versao), 0) + 1 into v_versao
      from hub.drone_obstaculo_versoes where cod_faz = p_cod_faz and classe_m = v_classe;
    update hub.drone_obstaculo_versoes set vigente = false
     where cod_faz = p_cod_faz and classe_m = v_classe and vigente;
    insert into hub.drone_obstaculo_versoes (cod_faz, classe_m, versao, origem, arquivo_origem, n_feicoes,
                                             enviado_por, envio_id)
    values (p_cod_faz, v_classe, v_versao, p_origem, e->>'arquivo', jsonb_array_length(e->'wkts'), p_usuario, p_envio_id)
    returning id into v_id;
    insert into hub.drone_obstaculo_feicoes (versao_id, geom)
    select v_id, ST_Force2D(ST_GeomFromText(w, 31983)) from jsonb_array_elements_text(e->'wkts') w;
    n := n + 1;
  end loop;
  update hub.drone_solicitacoes set status = 'solicitado'
   where cod_faz = p_cod_faz and tipo = 'normal' and status = 'aguardando_obstaculos';
  return n;
end $$;

drop function if exists hub.drone_gravar_infestacao(bigint, text, text, text[], uuid);
create or replace function hub.drone_gravar_infestacao(
  p_solicitacao_id bigint, p_empresa text, p_arquivo text, p_wkts text[], p_usuario uuid default null,
  p_envio_id bigint default null)
returns bigint language plpgsql security definer set search_path = hub, extensions as $$
declare v_sol hub.drone_solicitacoes; v_id bigint;
begin
  if p_envio_id is not null then
    select id into v_id from hub.drone_infestacoes where envio_id = p_envio_id;
    if v_id is not null then
      return v_id;                                    -- envio já gravado
    end if;
  end if;
  select * into v_sol from hub.drone_solicitacoes where id = p_solicitacao_id;
  if v_sol.id is null or v_sol.tipo <> 'catacao' then
    raise exception 'Solicitação % não é uma catação', p_solicitacao_id;
  end if;
  insert into hub.drone_infestacoes (cod_faz, solicitacao_id, empresa, arquivo_origem, n_feicoes, enviado_por, envio_id)
  values (v_sol.cod_faz, v_sol.id, p_empresa, p_arquivo, coalesce(array_length(p_wkts, 1), 0), p_usuario, p_envio_id)
  returning id into v_id;
  insert into hub.drone_infestacao_feicoes (infestacao_id, geom)
  select v_id, ST_Force2D(ST_GeomFromText(w, 31983)) from unnest(p_wkts) w;
  update hub.drone_solicitacoes set status = 'solicitado'
   where id = v_sol.id and status = 'aguardando_infestacao';
  return v_id;
end $$;

-- ── travas ────────────────────────────────────────────────────────────
create or replace function hub.drone_registrar_envio(p_cod_faz int, p_tipo text, p_classe_m int,
                                                     p_solicitacao_id bigint, p_arquivos text[])
returns bigint language plpgsql security definer set search_path = hub as $$
declare v_id bigint;
begin
  if not hub.pode_editar('drone') then
    raise exception 'Sem permissão para enviar arquivos do Drone';
  end if;
  if coalesce(array_length(p_arquivos, 1), 0) = 0 then
    raise exception 'Nenhum arquivo enviado';
  end if;
  if exists (select 1 from unnest(p_arquivos) a
              where a not like p_cod_faz || '/%' or a like '%..%' or a like '%?%' or a like '%#%') then
    raise exception 'Caminho de arquivo inválido (fora da pasta da fazenda %)', p_cod_faz;
  end if;
  if p_tipo = 'infestacao' and not exists (
       select 1 from hub.drone_solicitacoes where id = p_solicitacao_id and cod_faz = p_cod_faz and tipo = 'catacao') then
    raise exception 'A infestação precisa de uma solicitação de Catação desta fazenda';
  end if;
  insert into hub.drone_envios (cod_faz, tipo, classe_m, solicitacao_id, arquivos, enviado_por)
  values (p_cod_faz, p_tipo, p_classe_m, p_solicitacao_id, p_arquivos, auth.uid())
  returning id into v_id;
  return v_id;
end $$;

create or replace function hub.drone_descartar(p_geracao_id bigint)
returns void language plpgsql security definer set search_path = hub as $$
begin
  if not hub.pode_editar('drone') then
    raise exception 'Sem permissão';
  end if;
  update hub.drone_geracoes set status = 'descartada'
   where id = p_geracao_id and status in ('pronta', 'erro')
     and (publicar_pedido_em is null or publicacao_erro is not null);
  if not found then
    raise exception 'Só dá para descartar uma prévia pronta ou com erro (e que não esteja sendo publicada)';
  end if;
end $$;

-- prévias: só quem edita o Drone (admin ou editor com o módulo)
drop policy if exists drone_previas_le on storage.objects;
create policy drone_previas_le on storage.objects for select to authenticated
  using (bucket_id = 'drone-previas' and hub.pode_editar('drone'));

-- ── painel: "fora da Base" só de projetos individuais ─────────────────
create or replace function hub.drone_painel()
returns jsonb language sql stable security definer set search_path = hub as $$
select jsonb_build_object(
  'solicitacoes', coalesce((select jsonb_agg(x order by x->>'criado_em') from (
      select jsonb_build_object('id', s.id, 'cod_faz', s.cod_faz, 'fazenda', f.nome, 'tipo', s.tipo, 'status', s.status,
               'observacao', s.observacao, 'data_desejada', s.data_desejada, 'criado_em', s.criado_em,
               'solicitante', u.nome, 'solicitante_id', s.solicitante_id,
               'geracao', (select jsonb_build_object('id', g.id, 'status', g.status,
                                    'alertas', coalesce(jsonb_array_length(g.alertas), 0),
                                    'publicar_pedido_em', g.publicar_pedido_em, 'publicacao_erro', g.publicacao_erro,
                                    'erro', g.erro)
                             from hub.drone_geracoes g where g.solicitacao_id = s.id and g.status <> 'descartada'
                            order by g.id desc limit 1)) x
        from hub.drone_solicitacoes s
        join hub.fazendas f on f.cod_faz = s.cod_faz
        left join hub.usuarios u on u.id = s.solicitante_id
       where s.origem <> 'legado' and s.status not in ('ok', 'cancelado')) q), '[]'::jsonb),
  'incompletas', coalesce((select jsonb_agg(jsonb_build_object('cod_faz', v.cod_faz, 'fazenda', f.nome,
                                                               'pct', v.cobertura_pct) order by v.cobertura_pct)
                             from hub.drone_cobertura_v v join hub.fazendas f on f.cod_faz = v.cod_faz
                            where v.cobertura_pct < 100), '[]'::jsonb),
  'obstaculos_antigos', coalesce((select jsonb_agg(distinct v.cod_faz)
                             from hub.drone_obstaculo_versoes v
                            where v.vigente and v.enviado_em < now() - make_interval(
                                    months => (select valor::int from hub.drone_parametros
                                                where chave = 'alerta_obstaculos_meses'))), '[]'::jsonb),
  'fora_da_base', coalesce((select jsonb_agg(distinct p.cod_faz)
                             from hub.projetos p
                             join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente and r.documento = 'normal'
                             join hub.drone_revisao_talhoes t on t.revisao_id = r.id
                            where p.modulo_id = 'drone' and p.tipo = 'individual'
                              and not exists (select 1 from hub.talhao_geom g
                                               where g.cod_faz = p.cod_faz and g.talhao_num = t.talhao_num)), '[]'::jsonb));
$$;

-- ── obstáculos no mapa (objeto + buffer da classe) ────────────────────
create or replace function hub.drone_obstaculos_mapa(p_cod_faz int)
returns jsonb language sql stable security definer set search_path = hub, extensions as $$
select jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(f), '[]'::jsonb))
  from (
    select jsonb_build_object('type', 'Feature', 'geometry', ST_AsGeoJSON(ST_Transform(o.geom, 4326), 6)::jsonb,
             'properties', jsonb_build_object('camada', 'obst', 'classe', v.classe_m)) f
      from hub.drone_obstaculo_versoes v join hub.drone_obstaculo_feicoes o on o.versao_id = v.id
     where v.cod_faz = p_cod_faz and v.vigente
    union all
    select jsonb_build_object('type', 'Feature',
             'geometry', ST_AsGeoJSON(ST_Transform(ST_Union(ST_Buffer(o.geom, c.distancia_m)), 4326), 6)::jsonb,
             'properties', jsonb_build_object('camada', 'buffer', 'classe', v.classe_m))
      from hub.drone_obstaculo_versoes v
      join hub.drone_obstaculo_feicoes o on o.versao_id = v.id
      join hub.drone_classes_restricao c on c.classe_m = v.classe_m
     where v.cod_faz = p_cod_faz and v.vigente
     group by v.classe_m) q;
$$;

-- ── resumo por fazenda (dashboard e Consultas) ────────────────────────
create or replace function hub.drone_resumo()
returns table (cod_faz int, fazenda text, normal_rev int, cobertura_pct numeric, catacao_rev int, catacao_ha numeric,
               obst_15 timestamptz, obst_25 timestamptz, obst_50 timestamptz, solicitacao text)
language sql stable security definer set search_path = hub as $$
  with vig as (
    select p.cod_faz, r.id, r.documento, r.numero
      from hub.projetos p join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente
     where p.modulo_id = 'drone' and p.tipo = 'individual'),
  faz as (
    select cod_faz from vig
    union select cod_faz from hub.drone_obstaculo_versoes where vigente
    union select cod_faz from hub.drone_solicitacoes where origem <> 'legado' and status not in ('ok', 'cancelado'))
  select f.cod_faz, fz.nome,
         (select numero from vig where vig.cod_faz = f.cod_faz and documento = 'normal'),
         (select cobertura_pct from hub.drone_cobertura_v c where c.cod_faz = f.cod_faz),
         (select numero from vig where vig.cod_faz = f.cod_faz and documento = 'catacao'),
         (select round(sum(t.area_ha), 2) from vig join hub.drone_revisao_talhoes t on t.revisao_id = vig.id
           where vig.cod_faz = f.cod_faz and vig.documento = 'catacao'),
         (select max(enviado_em) from hub.drone_obstaculo_versoes o where o.cod_faz = f.cod_faz and o.vigente and o.classe_m = 15),
         (select max(enviado_em) from hub.drone_obstaculo_versoes o where o.cod_faz = f.cod_faz and o.vigente and o.classe_m = 25),
         (select max(enviado_em) from hub.drone_obstaculo_versoes o where o.cod_faz = f.cod_faz and o.vigente and o.classe_m = 50),
         (select s.tipo || ' · ' || s.status from hub.drone_solicitacoes s
           where s.cod_faz = f.cod_faz and s.origem <> 'legado' and s.status not in ('ok', 'cancelado')
           order by s.id desc limit 1)
    from faz f join hub.fazendas fz on fz.cod_faz = f.cod_faz;
$$;

-- ── avisos do Drone no sininho ────────────────────────────────────────
create or replace function hub.drone_avisar(p_tipo text, p_cod int, p_titulo text, p_texto text)
returns void language plpgsql security definer set search_path = hub as $$
declare v_id bigint; v_nome text;
begin
  select nome into v_nome from hub.fazendas where cod_faz = p_cod;
  insert into hub.avisos (modulo_id, tipo, cod_faz, titulo, texto)
  values ('drone', p_tipo, p_cod, p_cod || ' ' || coalesce(v_nome, '') || ': ' || p_titulo, p_texto)
  on conflict (tipo, cod_faz) where resolvido_em is null
    do update set titulo = excluded.titulo, texto = excluded.texto, atualizado_em = now()
  returning id into v_id;
  delete from hub.avisos_lidos where aviso_id = v_id;
end $$;

create or replace function hub.drone_resolver(p_tipos text[], p_cod int)
returns void language sql security definer set search_path = hub as $$
  update hub.avisos set resolvido_em = now()
   where modulo_id = 'drone' and tipo = any (p_tipos) and cod_faz = p_cod and resolvido_em is null;
$$;

create or replace function hub.drone_avisos_solicitacao()
returns trigger language plpgsql security definer set search_path = hub as $$
declare v_num int;
begin
  if new.origem = 'legado' then
    return new;
  end if;
  if tg_op = 'INSERT' and new.tipo = 'normal' then
    perform hub.drone_avisar('drone_solicitacao', new.cod_faz, 'nova solicitação de projeto Normal',
                             coalesce(new.observacao, 'Abra a fazenda na tela do Drone.'));
  elsif tg_op = 'UPDATE' and new.status = 'ok' and old.status <> 'ok' then
    select numero into v_num from hub.projeto_revisoes where id = new.revisao_id;
    perform hub.drone_avisar('drone_publicado', new.cod_faz,
                             'publicado ' || case new.tipo when 'normal' then 'Normal' else 'Catação' end
                             || ' Rev' || coalesce(v_num::text, '?'), 'Já está no portal de downloads.');
  elsif tg_op = 'UPDATE' and new.status = 'cancelado' then
    perform hub.drone_resolver(array['drone_solicitacao'], new.cod_faz);
  end if;
  return new;
end $$;

create or replace function hub.drone_avisos_geracao()
returns trigger language plpgsql security definer set search_path = hub as $$
declare v_cod int; v_tipo text;
begin
  select cod_faz, tipo into v_cod, v_tipo from hub.drone_solicitacoes where id = new.solicitacao_id;
  if tg_op = 'INSERT' then
    perform hub.drone_resolver(array['drone_solicitacao', 'drone_erro'], v_cod);
  elsif new.status is distinct from old.status then
    if new.status = 'pronta' then
      perform hub.drone_avisar('drone_previa', v_cod,
                               'prévia pronta para conferir (' || case v_tipo when 'normal' then 'Normal' else 'Catação' end || ')',
                               coalesce(jsonb_array_length(new.alertas), 0) || ' alerta(s).');
    elsif new.status = 'erro' then
      perform hub.drone_avisar('drone_erro', v_cod, 'erro na geração', new.erro);
    elsif new.status in ('publicada', 'descartada') then
      perform hub.drone_resolver(array['drone_previa', 'drone_erro'], v_cod);
    end if;
  elsif new.publicacao_erro is not null and new.publicacao_erro is distinct from old.publicacao_erro then
    perform hub.drone_avisar('drone_erro', v_cod, 'erro ao publicar', new.publicacao_erro);
  end if;
  return new;
end $$;

create or replace function hub.drone_avisos_envio()
returns trigger language plpgsql security definer set search_path = hub as $$
begin
  if new.status = 'erro' and old.status is distinct from 'erro' then
    perform hub.drone_avisar('drone_erro', new.cod_faz, 'erro no envio de arquivo', new.erro);
  elsif new.status = 'ok' and old.status is distinct from 'ok' then
    perform hub.drone_resolver(array['drone_erro'], new.cod_faz);
  end if;
  return new;
end $$;

drop trigger if exists drone_avisos_solicitacao on hub.drone_solicitacoes;
create trigger drone_avisos_solicitacao after insert or update of status on hub.drone_solicitacoes
  for each row execute function hub.drone_avisos_solicitacao();
drop trigger if exists drone_avisos_geracao on hub.drone_geracoes;
create trigger drone_avisos_geracao after insert or update of status, publicacao_erro on hub.drone_geracoes
  for each row execute function hub.drone_avisos_geracao();
drop trigger if exists drone_avisos_envio on hub.drone_envios;
create trigger drone_avisos_envio after update of status on hub.drone_envios
  for each row execute function hub.drone_avisos_envio();

-- "Publicado" some sozinho depois de 7 dias (o agente chama a cada ciclo)
create or replace function hub.drone_avisos_limpar()
returns int language plpgsql security definer set search_path = hub as $$
declare n int;
begin
  update hub.avisos set resolvido_em = now()
   where modulo_id = 'drone' and tipo = 'drone_publicado' and resolvido_em is null
     and atualizado_em < now() - interval '7 days';
  get diagnostics n = row_count;
  return n;
end $$;

-- ── permissões ────────────────────────────────────────────────────────
do $$
declare f text;
begin
  foreach f in array array[
    'hub.drone_gravar_obstaculos_lote(int, text, jsonb, uuid, bigint)',
    'hub.drone_gravar_infestacao(bigint, text, text, text[], uuid, bigint)',
    'hub.drone_avisar(text, int, text, text)', 'hub.drone_resolver(text[], int)', 'hub.drone_avisos_limpar()'] loop
    execute format('revoke all on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
  foreach f in array array['hub.drone_obstaculos_mapa(int)', 'hub.drone_resumo()'] loop
    execute format('revoke all on function %s from public, anon', f);
    execute format('grant execute on function %s to authenticated, service_role', f);
  end loop;
end $$;

commit;
