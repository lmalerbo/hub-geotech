-- Corretivos: gravação de aplicações em transação única (revisão de 16/10/2026).
-- Antes, a tela gravava talhões, aplicação e vínculos em chamadas separadas: um duplo clique ou uma falha
-- no meio deixava aplicação sem talhão; duas abas ao mesmo tempo passavam pela checagem de duplicada.
-- Agora: três funções (aplicar, editar, excluir) que rodam inteiras ou nada, com trava por mapa.
-- Também: O.S. sem espaços nas pontas, autoria não forjável, RLS avaliando o acesso uma vez por consulta.
begin;

-- Uma trava por mapa: gravações no mesmo mapa entram em fila (resolve a corrida da checagem de duplicada).
create or replace function hub.corretivo_travar_mapa(p_mapa_id bigint)
returns void language sql volatile set search_path = hub as $$
  select pg_advisory_xact_lock(hashtext('corretivo_mapa'), p_mapa_id::int);
$$;

-- O.S. gravada sempre sem espaços nas pontas (a checagem de duplicada compara o texto).
alter table hub.corretivo_aplicacoes add constraint corretivo_aplicacoes_os_aparada check (os = trim(os));

-- A checagem de duplicada também trava o mapa (vale para escrita direta pela API, fora das funções).
create or replace function hub.corretivo_checar_aplicacao_talhao()
returns trigger language plpgsql security definer set search_path = hub as $$
declare a hub.corretivo_aplicacoes;
begin
  perform hub.corretivo_travar_mapa(new.mapa_id);
  select * into a from hub.corretivo_aplicacoes where id = new.aplicacao_id;
  if a.mapa_id is distinct from new.mapa_id then
    raise exception 'Aplicação % não é do mapa %', new.aplicacao_id, new.mapa_id;
  end if;
  if exists (select 1 from hub.corretivo_aplicacao_talhoes x
               join hub.corretivo_aplicacoes b on b.id = x.aplicacao_id
              where x.mapa_id = new.mapa_id and x.talhao_num = new.talhao_num and b.id <> a.id
                and b.tipo = a.tipo and b.calcario is not distinct from a.calcario and b.dose = a.dose
                and b.dose_gesso is not distinct from a.dose_gesso and b.os = a.os) then
    raise exception 'O talhão % já tem esta aplicação', new.talhao_num;
  end if;
  return new;
end $$;

-- Autoria: quem cria e quem altera vêm sempre da sessão; fazenda e criação não mudam depois.
create or replace function hub.corretivo_autoria()
returns trigger language plpgsql security definer set search_path = hub as $$
begin
  if tg_op = 'INSERT' then
    new.criado_por := coalesce(auth.uid(), new.criado_por);
    new.criado_em := now();
  else
    new.cod_faz := old.cod_faz; new.criado_por := old.criado_por; new.criado_em := old.criado_em;
  end if;
  new.alterado_por := coalesce(auth.uid(), new.alterado_por);
  new.alterado_em := now();
  return new;
end $$;
drop trigger if exists corretivo_mapas_tocar on hub.corretivo_mapas;
create trigger corretivo_mapas_autoria before insert or update on hub.corretivo_mapas
  for each row execute function hub.corretivo_autoria();

-- p_talhoes: [{"talhao_num": 3, "area_ha": 21.4, "area_editada": false}, ...] — os talhões que entram no mapa
-- com a área a usar se ainda não estiverem nele (os que já estão mantêm a área gravada).
create or replace function hub.corretivo_garantir_talhoes(p_mapa_id bigint, p_talhoes jsonb)
returns void language sql security definer set search_path = hub as $$
  insert into hub.corretivo_talhoes (mapa_id, talhao_num, area_ha, area_editada)
  select p_mapa_id, (x->>'talhao_num')::int, (x->>'area_ha')::numeric, coalesce((x->>'area_editada')::boolean, false)
    from jsonb_array_elements(p_talhoes) x
  on conflict (mapa_id, talhao_num) do nothing;
$$;

create or replace function hub.corretivo_aplicar(p_mapa_id bigint, p_aplicacao jsonb, p_talhoes jsonb)
returns bigint language plpgsql security definer set search_path = hub as $$
declare v_id bigint; v_ordem int;
begin
  if not hub.pode_usar_corretivos() then raise exception 'Sem acesso aos Corretivos'; end if;
  if jsonb_array_length(coalesce(p_talhoes, '[]'::jsonb)) = 0 then raise exception 'Marque ao menos um talhão'; end if;
  perform hub.corretivo_travar_mapa(p_mapa_id);
  perform hub.corretivo_garantir_talhoes(p_mapa_id, p_talhoes);
  select coalesce(max(ordem), 0) + 1 into v_ordem from hub.corretivo_aplicacoes where mapa_id = p_mapa_id;
  insert into hub.corretivo_aplicacoes (mapa_id, tipo, calcario, dose, dose_gesso, os, ordem)
  values (p_mapa_id, p_aplicacao->>'tipo', nullif(p_aplicacao->>'calcario', ''), (p_aplicacao->>'dose')::numeric,
          (p_aplicacao->>'dose_gesso')::numeric, trim(p_aplicacao->>'os'), v_ordem)
  returning id into v_id;
  insert into hub.corretivo_aplicacao_talhoes (aplicacao_id, mapa_id, talhao_num)
  select v_id, p_mapa_id, (x->>'talhao_num')::int from jsonb_array_elements(p_talhoes) x;
  return v_id;
end $$;

-- p_campos: {"dose": 2, "dose_gesso": null, "os": "4520"}; p_talhoes: a lista FINAL de talhões da aplicação.
create or replace function hub.corretivo_editar_aplicacao(p_aplicacao_id bigint, p_campos jsonb, p_talhoes jsonb)
returns void language plpgsql security definer set search_path = hub as $$
declare a hub.corretivo_aplicacoes; v_saem int[]; v_ficam int[];
begin
  if not hub.pode_usar_corretivos() then raise exception 'Sem acesso aos Corretivos'; end if;
  if jsonb_array_length(coalesce(p_talhoes, '[]'::jsonb)) = 0 then raise exception 'Marque ao menos um talhão'; end if;
  select * into a from hub.corretivo_aplicacoes where id = p_aplicacao_id;
  if a.id is null then raise exception 'Aplicação % não existe', p_aplicacao_id; end if;
  perform hub.corretivo_travar_mapa(a.mapa_id);
  select array_agg((x->>'talhao_num')::int) into v_ficam from jsonb_array_elements(p_talhoes) x;
  select array_agg(talhao_num) into v_saem from hub.corretivo_aplicacao_talhoes
   where aplicacao_id = a.id and not (talhao_num = any (v_ficam));
  update hub.corretivo_aplicacoes
     set dose = (p_campos->>'dose')::numeric, dose_gesso = (p_campos->>'dose_gesso')::numeric, os = trim(p_campos->>'os')
   where id = a.id;
  perform hub.corretivo_garantir_talhoes(a.mapa_id, p_talhoes);
  -- Vínculos: remove os que saíram e regrava os que ficam (o gatilho confere duplicada com os valores novos).
  delete from hub.corretivo_aplicacao_talhoes where aplicacao_id = a.id;
  insert into hub.corretivo_aplicacao_talhoes (aplicacao_id, mapa_id, talhao_num)
  select a.id, a.mapa_id, t from unnest(v_ficam) t;
  delete from hub.corretivo_talhoes t
   where t.mapa_id = a.mapa_id and t.talhao_num = any (coalesce(v_saem, '{}'))
     and not exists (select 1 from hub.corretivo_aplicacao_talhoes x where x.mapa_id = t.mapa_id and x.talhao_num = t.talhao_num);
end $$;

create or replace function hub.corretivo_excluir_aplicacao(p_aplicacao_id bigint)
returns void language plpgsql security definer set search_path = hub as $$
declare a hub.corretivo_aplicacoes; v_tal int[];
begin
  if not hub.pode_usar_corretivos() then raise exception 'Sem acesso aos Corretivos'; end if;
  select * into a from hub.corretivo_aplicacoes where id = p_aplicacao_id;
  if a.id is null then return; end if;
  perform hub.corretivo_travar_mapa(a.mapa_id);
  select array_agg(talhao_num) into v_tal from hub.corretivo_aplicacao_talhoes where aplicacao_id = a.id;
  delete from hub.corretivo_aplicacoes where id = a.id;
  delete from hub.corretivo_talhoes t
   where t.mapa_id = a.mapa_id and t.talhao_num = any (coalesce(v_tal, '{}'))
     and not exists (select 1 from hub.corretivo_aplicacao_talhoes x where x.mapa_id = t.mapa_id and x.talhao_num = t.talhao_num);
end $$;

-- RLS: o acesso é calculado uma vez por consulta, não linha a linha.
do $$
declare t text;
begin
  foreach t in array array['corretivo_mapas', 'corretivo_talhoes', 'corretivo_aplicacoes', 'corretivo_aplicacao_talhoes'] loop
    execute format('drop policy if exists corretivos on hub.%I', t);
    execute format('create policy corretivos on hub.%I for all to authenticated '
                   'using ((select hub.pode_usar_corretivos())) with check ((select hub.pode_usar_corretivos()))', t);
  end loop;
end $$;

revoke all on function hub.corretivo_travar_mapa(bigint) from public, anon, authenticated;
revoke all on function hub.corretivo_garantir_talhoes(bigint, jsonb) from public, anon, authenticated;
revoke all on function hub.corretivo_aplicar(bigint, jsonb, jsonb) from public, anon;
revoke all on function hub.corretivo_editar_aplicacao(bigint, jsonb, jsonb) from public, anon;
revoke all on function hub.corretivo_excluir_aplicacao(bigint) from public, anon;
grant execute on function hub.corretivo_aplicar(bigint, jsonb, jsonb) to authenticated, service_role;
grant execute on function hub.corretivo_editar_aplicacao(bigint, jsonb, jsonb) to authenticated, service_role;
grant execute on function hub.corretivo_excluir_aplicacao(bigint) to authenticated, service_role;
grant execute on function hub.corretivo_travar_mapa(bigint) to service_role;
grant execute on function hub.corretivo_garantir_talhoes(bigint, jsonb) to service_role;

commit;
