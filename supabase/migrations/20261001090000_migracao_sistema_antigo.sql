-- Migração única do Plantio e do Preparo antigos para o Hub.
--
-- O script migracao/migrar_plantio_preparo.py lê os sistemas antigos, monta
-- tudo num JSON e chama esta função UMA vez. Uma chamada de função é uma
-- transação só: ou entra tudo, ou nada (se algo falhar no meio do corte, o
-- Hub fica exatamente como estava).
--
-- p_ensaio = true (padrão): grava tudo, confere e DESFAZ no final, devolvendo
-- o resumo na mensagem de erro "ENSAIO {...}". Serve pra testar antes do corte
-- sem deixar nada gravado.
--
-- Pode ser rodada mais de uma vez: tudo é upsert e o histórico antigo é
-- substituído (não duplica).
--
-- Formato de p:
--   projetos: [{modulo, tipo, cod_faz, nome, revisoes: [{documento, numero, motivo,
--              vigente, criado_em, origens: [cod_faz], arquivos: [{nome, url, tamanho,
--              publicado_em}]}]}]
--   plantio:  [{layer, mes_plantio, seq_plantio, ambiente, mapeamento, projeto}]
--   log:      [{layer, campo, anterior, novo, usuario_id, criado_em}]
--   preparo:  [{cod_faz, ordem, usuario_id, concluido_em}]
--
-- Depois do corte esta função pode ser apagada (drop function).

begin;

create or replace function hub.migrar_sistema_antigo(p jsonb, p_ensaio boolean default true)
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

  -- 1. Arquivos ANTES dos status: anexar um .pdf de Plantio dispara o
  --    "mapa → Ok", mas o status que vale é o do sistema antigo (passo 2).
  --    Individuais primeiro: os personalizados apontam pras revisões deles.
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
              coalesce((v_proj->>'criado_em')::timestamptz, now()))
      returning id into v_projeto_id;
    end if;

    -- A vigente é marcada de novo abaixo (a maior revisão de cada documento).
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

      -- Personalizado (bloco): liga às revisões vigentes das fazendas que o
      -- compõem, preferindo o documento principal (ordem de documento_tipos).
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

  -- 2. Status do Plantio. Talhão na Base Fazendas: grava. Fora dela: guarda
  --    (a rodada diária restaura quando a Base cadastrar). mes_plantio é do
  --    PLANAGRI: só entra quando o talhão ainda não tem.
  insert into talhao_plantio (layer, mes_plantio, seq_plantio, ambiente, mapeamento, projeto)
  select d.layer, d.mes_plantio, d.seq_plantio, d.ambiente, d.mapeamento, d.projeto
    from jsonb_to_recordset(p->'plantio')
         as d(layer bigint, mes_plantio date, seq_plantio text, ambiente text, mapeamento text, projeto text)
   where d.layer in (select layer from talhoes)
  on conflict (layer) do update
    set mapeamento  = excluded.mapeamento,
        projeto     = excluded.projeto,
        mes_plantio = coalesce(talhao_plantio.mes_plantio, excluded.mes_plantio),
        seq_plantio = coalesce(nullif(talhao_plantio.seq_plantio, ''), excluded.seq_plantio),
        ambiente    = coalesce(nullif(talhao_plantio.ambiente, ''), excluded.ambiente);

  insert into plantio_status_guardado (layer, mes_plantio, seq_plantio, mapeamento, projeto)
  select d.layer, d.mes_plantio, d.seq_plantio, d.mapeamento, d.projeto
    from jsonb_to_recordset(p->'plantio')
         as d(layer bigint, mes_plantio date, seq_plantio text, mapeamento text, projeto text)
   where d.layer not in (select layer from talhoes)
  on conflict (layer) do update
    set mes_plantio = excluded.mes_plantio, seq_plantio = excluded.seq_plantio,
        mapeamento  = excluded.mapeamento,  projeto     = excluded.projeto,
        guardado_em = now();

  -- O "mapa → Ok" do passo 1 foi sobrescrito pelo status antigo; o registro
  -- dele no log não aconteceu de verdade. now() é o mesmo em toda a transação.
  delete from log_auditoria where origem = 'mapa_anexado' and criado_em = now();

  -- 3. Histórico do Plantio (substitui o da migração anterior, se houver).
  delete from log_auditoria where origem = 'sistema_antigo';
  insert into log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo,
                             usuario_id, origem, criado_em)
  select 'plantio', 'talhao', l.layer, l.campo, l.anterior, l.novo, l.usuario_id, 'sistema_antigo', l.criado_em
    from jsonb_to_recordset(p->'log')
         as l(layer bigint, campo text, anterior text, novo text, usuario_id uuid, criado_em timestamptz);

  -- 4. Etapas concluídas do Preparo (por fazenda), com quem e quando.
  insert into etapa_status (etapa_id, entidade_id, ok, usuario_id, concluido_em)
  select e.id, s.cod_faz, true, s.usuario_id, s.concluido_em
    from jsonb_to_recordset(p->'preparo')
         as s(cod_faz int, ordem int, usuario_id uuid, concluido_em timestamptz)
    join etapas e on e.modulo_id = 'preparo' and e.ordem = s.ordem
  on conflict (etapa_id, entidade_id)
    do update set ok = true, usuario_id = excluded.usuario_id, concluido_em = excluded.concluido_em;

  -- 5. Conferência, feita no próprio banco depois de gravar.
  with d as (
    select * from jsonb_to_recordset(p->'plantio') as d(layer bigint, mapeamento text, projeto text)
  )
  select jsonb_build_object(
    'plantio_por_status',  (select jsonb_object_agg(projeto, n) from
                              (select t.projeto, count(*) n from talhao_plantio t join d using (layer)
                                group by t.projeto) s),
    'plantio_divergentes', (select count(*) from d join talhao_plantio t using (layer)
                             where t.projeto <> d.projeto or t.mapeamento <> d.mapeamento),
    'plantio_guardados',   (select count(*) from plantio_status_guardado g join d using (layer)),
    'log',                 (select count(*) from log_auditoria where origem = 'sistema_antigo'),
    'preparo_etapas',      (select count(*) from etapa_status es join etapas e on e.id = es.etapa_id
                             where e.modulo_id = 'preparo' and es.ok),
    'projetos',            (select count(*) from projetos),
    'revisoes',            (select count(*) from projeto_revisoes),
    'arquivos',            (select count(*) from revisao_arquivos),
    'vigentes',            (select count(*) from projeto_revisoes where vigente),
    'origens',             (select count(*) from revisao_origens)
  ) into v_resumo;

  if p_ensaio then
    raise exception 'ENSAIO %', v_resumo using errcode = 'P0001';
  end if;
  return v_resumo;
end $$;

revoke all on function hub.migrar_sistema_antigo(jsonb, boolean) from public, anon, authenticated;
grant execute on function hub.migrar_sistema_antigo(jsonb, boolean) to service_role;

commit;
