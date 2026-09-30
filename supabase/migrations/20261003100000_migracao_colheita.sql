-- Migração única da Colheita (Expo_safra) para o Hub.
--
-- migracao/migrar_colheita.py monta tudo num JSON e chama esta função UMA
-- vez: uma transação só (ou entra tudo, ou nada). p_ensaio = true grava,
-- confere e DESFAZ, devolvendo o resumo na mensagem "ENSAIO {...}".
-- Pode ser rodada mais de uma vez (upsert; o histórico antigo é substituído).
--
-- Formato de p:
--   projetos: [{modulo, tipo, cod_faz, nome, revisoes: [{documento, numero, motivo,
--              vigente, criado_em, origens: [cod_faz], arquivos: [{nome, url, tamanho,
--              publicado_em}]}]}]
--   talhoes:  [{layer, tipo_linha, ciclo}]
--   log:      [{layer, anterior, novo, usuario_id, criado_em}]
--
-- Depois do corte esta função pode ser apagada (drop function).

begin;

create or replace function hub.migrar_colheita_antiga(p jsonb, p_ensaio boolean default true)
returns jsonb
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_proj       jsonb;
  v_rev        jsonb;
  v_projeto_id bigint;
  v_rev_id     bigint;
  v_resumo     jsonb;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'Só a service_role roda a migração';
  end if;

  -- 1. Arquivos. Individuais primeiro: os blocos apontam pras revisões deles.
  for v_proj in
    select value from jsonb_array_elements(p->'projetos')
     order by (value->>'tipo') = 'personalizado'
  loop
    if v_proj->>'tipo' = 'individual' then
      select id into v_projeto_id from projetos
       where modulo_id = v_proj->>'modulo' and tipo = 'individual'
         and cod_faz = (v_proj->>'cod_faz')::int;
    else
      select id into v_projeto_id from projetos
       where modulo_id = v_proj->>'modulo' and tipo = 'personalizado'
         and nome = v_proj->>'nome';
    end if;

    if v_projeto_id is null then
      insert into projetos (modulo_id, tipo, cod_faz, nome, criado_em)
      values (v_proj->>'modulo', v_proj->>'tipo', (v_proj->>'cod_faz')::int,
              coalesce((select nome from fazendas where cod_faz = (v_proj->>'cod_faz')::int), v_proj->>'nome'),
              coalesce((select min((r->>'criado_em')::timestamptz)
                          from jsonb_array_elements(v_proj->'revisoes') r), now()))
      returning id into v_projeto_id;
    end if;

    update projeto_revisoes set vigente = false
     where projeto_id = v_projeto_id and vigente
       and documento in (select value->>'documento' from jsonb_array_elements(v_proj->'revisoes'));

    for v_rev in
      select value from jsonb_array_elements(v_proj->'revisoes')
       order by value->>'documento', (value->>'numero')::int
    loop
      insert into projeto_revisoes (projeto_id, documento, numero, motivo, vigente, criado_em)
      values (v_projeto_id, v_rev->>'documento', (v_rev->>'numero')::int, v_rev->>'motivo',
              (v_rev->>'vigente')::boolean, (v_rev->>'criado_em')::timestamptz)
      on conflict (projeto_id, documento, numero)
        do update set vigente = excluded.vigente
      returning id into v_rev_id;

      -- Bloco: liga às revisões vigentes das fazendas que o compõem.
      insert into revisao_origens (revisao_id, origem_revisao_id)
      select v_rev_id, orig.id
        from jsonb_array_elements_text(coalesce(v_rev->'origens', '[]'::jsonb)) o(cod_faz)
        cross join lateral (
          select r.id
            from projeto_revisoes r
            join projetos po on po.id = r.projeto_id
            join documento_tipos dt on dt.modulo_id = po.modulo_id and dt.codigo = r.documento
           where po.modulo_id = v_proj->>'modulo' and po.tipo = 'individual'
             and po.cod_faz = o.cod_faz::int and r.vigente
           order by dt.ordem
           limit 1) orig
      on conflict do nothing;

      insert into revisao_arquivos (revisao_id, nome_arquivo, release_url, tamanho_bytes, publicado_em)
      select v_rev_id, a.nome, a.url, a.tamanho, a.publicado_em
        from jsonb_to_recordset(v_rev->'arquivos')
             as a(nome text, url text, tamanho bigint, publicado_em timestamptz)
      on conflict (revisao_id, nome_arquivo)
        do update set release_url = excluded.release_url, tamanho_bytes = excluded.tamanho_bytes;
    end loop;
  end loop;

  -- 2. Tipo de linha e ciclo (os talhões já estão na demanda, vindos do ICOL).
  update talhao_colheita c
     set tipo_linha = d.tipo_linha, ciclo = d.ciclo, projeto_desatualizado = false
    from jsonb_to_recordset(p->'talhoes') as d(layer bigint, tipo_linha text, ciclo text)
   where c.layer = d.layer;

  -- 3. Histórico (substitui o da migração anterior, se houver).
  delete from log_auditoria where modulo_id = 'colheita' and origem = 'sistema_antigo';
  insert into log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo,
                             usuario_id, origem, criado_em)
  select 'colheita', 'talhao', l.layer, 'tipo_linha', l.anterior, l.novo, l.usuario_id, 'sistema_antigo', l.criado_em
    from jsonb_to_recordset(p->'log')
         as l(layer bigint, anterior text, novo text, usuario_id uuid, criado_em timestamptz);

  -- 4. Conferência, no próprio banco.
  with d as (
    select * from jsonb_to_recordset(p->'talhoes') as d(layer bigint, tipo_linha text, ciclo text)
  )
  select jsonb_build_object(
    'talhoes_gravados',    (select count(*) from d join talhao_colheita c using (layer)),
    'talhoes_divergentes', (select count(*) from d left join talhao_colheita c using (layer)
                             where c.layer is null or c.tipo_linha is distinct from d.tipo_linha
                                or c.ciclo is distinct from d.ciclo),
    'por_status',          (select jsonb_object_agg(status, n) from
                              (select status, count(*) n from colheita_talhoes group by status) s),
    'log',                 (select count(*) from log_auditoria where modulo_id = 'colheita' and origem = 'sistema_antigo'),
    'projetos',            (select count(*) from projetos where modulo_id = 'colheita'),
    'blocos',              (select count(*) from projetos where modulo_id = 'colheita' and tipo = 'personalizado'),
    'revisoes',            (select count(*) from projeto_revisoes r join projetos pr on pr.id = r.projeto_id
                             where pr.modulo_id = 'colheita'),
    'arquivos',            (select count(*) from revisao_arquivos a join projeto_revisoes r on r.id = a.revisao_id
                             join projetos pr on pr.id = r.projeto_id where pr.modulo_id = 'colheita'),
    'origens',             (select count(*) from revisao_origens o join projeto_revisoes r on r.id = o.revisao_id
                             join projetos pr on pr.id = r.projeto_id where pr.modulo_id = 'colheita')
  ) into v_resumo;

  if p_ensaio then
    raise exception 'ENSAIO %', v_resumo using errcode = 'P0001';
  end if;
  return v_resumo;
end $$;

revoke all on function hub.migrar_colheita_antiga(jsonb, boolean) from public, anon, authenticated;
grant execute on function hub.migrar_colheita_antiga(jsonb, boolean) to service_role;

commit;
