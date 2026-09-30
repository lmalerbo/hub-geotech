-- Regra B da Colheita: voo e revoo de linhas.
--
-- O analista (por ordem do gestor) aponta talhões:
--   voar   — talhão Sem Linhas, só a partir do 4º corte (até o 3º corte o voo
--            automático do setor já cobre);
--   revoar — talhão com linhas com problema, qualquer estágio; o talhão fica
--            em REVOO (continua usando as linhas atuais até chegarem as novas).
-- Espera a data de corte da safra atual (Base Fazendas) + 100 dias e o agente
-- do servidor Geo agenda no Drone MGMT, projeto "Linhas de Colheita" (via
-- GeoMap, rotas /integracao). Acompanha agendado → voado → divulgado e avisa
-- no sininho. Quando o analista marca o tipo de linha de novo, o pedido
-- divulgado é concluído.
--
-- Estados: aguardando_corte → na_fila → agendando → agendado → voado →
--          divulgado → concluido   (ou cancelado / erro)

begin;

insert into hub.parametros (chave, valor, descricao) values
  ('colheita_dias_porte', '100', 'Dias depois do corte para o talhão ter porte de voo (Regra B)')
on conflict (chave) do nothing;

-- Safra 26-27 = abril/2026 a março/2027.
create or replace function hub.safra_colheita_inicio()
returns date language sql stable security definer set search_path = hub as $$
  select make_date(2000 + split_part(hub.safra_colheita(), '-', 1)::int, 4, 1);
$$;

-- "04º CORTE" → 4; "18 MESES", "INVERNO", "A PLANTAR"... → null.
create or replace function hub.numero_corte(p_estagio text)
returns int language sql immutable as $$
  select (regexp_match(coalesce(p_estagio, ''), '^\s*(\d+)\s*º'))[1]::int;
$$;

create table hub.colheita_voos (
  id            bigint generated always as identity primary key,
  layer         bigint not null references hub.talhoes (layer),
  tipo          text not null check (tipo in ('voar', 'revoar')),
  problema      text,
  pedido_por    text,
  apontado_por  uuid references hub.usuarios (id),
  apontado_em   timestamptz not null default now(),
  status        text not null default 'aguardando_corte' check (status in (
                  'aguardando_corte', 'na_fila', 'agendando', 'agendado', 'voado',
                  'divulgado', 'concluido', 'cancelado', 'erro')),
  data_corte    date,
  liberar_em    date,
  dronemgmt_id  uuid,
  agendado_em   timestamptz,
  voado_em      timestamptz,
  divulgado_em  timestamptz,
  concluido_em  timestamptz,
  cancelado_em  timestamptz,
  erro          text,
  updated_at    timestamptz not null default now(),
  check (tipo = 'voar' or length(trim(coalesce(problema, ''))) > 0)
);
create unique index colheita_voos_um_ativo on hub.colheita_voos (layer)
  where status not in ('concluido', 'cancelado');
create trigger colheita_voos_updated_at before update on hub.colheita_voos
  for each row execute function hub.tocar_updated_at();

-- Status do talhão agora considera o revoo, e a view mostra o pedido ativo.
create or replace view hub.colheita_talhoes with (security_invoker = true) as
select c.layer,
       t.cod_faz,
       t.talhao_num,
       t.area_ha,
       t.estagio,
       t.data_ultimo_corte,
       c.frente,
       c.periodo_op,
       c.cortado,
       c.tipo_linha,
       c.ciclo,
       c.projeto_desatualizado,
       c.updated_at,
       case
         when c.projeto_desatualizado or c.tipo_linha is null      then 'A FAZER'
         when v.tipo = 'revoar'                                     then 'REVOO'
         when c.ciclo is distinct from hub.safra_colheita()        then 'REAVALIAR'
         when c.tipo_linha = 'SEM LINHAS'                          then 'SEM LINHAS'
         else 'CONCLUIDO'
       end as status,
       v.id         as voo_id,
       v.tipo       as voo_tipo,
       v.status     as voo_status,
       v.liberar_em as voo_liberar_em
  from hub.talhao_colheita c
  join hub.talhoes t on t.layer = c.layer
  left join hub.colheita_voos v on v.layer = c.layer and v.status not in ('concluido', 'cancelado');

-- ── Avisos do sininho (por fazenda) ────────────────────────────────────
create or replace function hub.colheita_avisos_voo(p_cod_faz int)
returns void language plpgsql security definer set search_path = hub as $$
declare
  v_nome text;
  v_n    int;
  v_id   bigint;
  r      record;
begin
  select nome into v_nome from hub.fazendas where cod_faz = p_cod_faz;
  for r in select * from (values
      ('voo_agendado',   'agendado',  'voo de Linhas de Colheita agendado',
       ' talhão(ões) com voo de Linhas de Colheita agendado no Drone MGMT.'),
      ('linhas_prontas', 'divulgado', 'linhas novas prontas',
       ' talhão(ões) com voo divulgado: as linhas novas estão prontas, atualize o projeto.'),
      ('voo_erro',       'erro',      'problema no agendamento de voo',
       ' talhão(ões) com erro ao agendar ou cancelado no Drone MGMT. Veja a Fila de voos.')
    ) as a(tipo, status, titulo, texto)
  loop
    v_id := null;
    select count(*) into v_n from hub.colheita_voos
     where status = r.status and layer / 1000 = p_cod_faz;
    if v_n = 0 then
      update hub.avisos set resolvido_em = now()
       where tipo = r.tipo and cod_faz = p_cod_faz and resolvido_em is null;
    else
      insert into hub.avisos (modulo_id, tipo, cod_faz, titulo, texto)
      values ('colheita', r.tipo, p_cod_faz, p_cod_faz || ' ' || coalesce(v_nome, '') || ': ' || r.titulo, v_n || r.texto)
      on conflict (tipo, cod_faz) where resolvido_em is null
        do update set texto = excluded.texto, atualizado_em = now()
        where hub.avisos.texto is distinct from excluded.texto
      returning id into v_id;
      if v_id is not null then
        delete from hub.avisos_lidos where aviso_id = v_id;
      end if;
    end if;
  end loop;
end $$;

-- ── Fila: data de corte da safra atual + 100 dias ──────────────────────
create or replace function hub.colheita_voos_atualizar_fila()
returns int language plpgsql security definer set search_path = hub as $$
declare
  v_ini  date := hub.safra_colheita_inicio();
  v_dias int  := (select valor::int from hub.parametros where chave = 'colheita_dias_porte');
  v_n    int;
begin
  update hub.colheita_voos v
     set data_corte = x.corte,
         liberar_em = x.corte + v_dias,
         status     = case when x.corte is null then 'aguardando_corte' else 'na_fila' end
    from (select v2.id,
                 case when t.data_ultimo_corte >= v_ini and t.data_ultimo_corte < (v_ini + interval '1 year')
                      then t.data_ultimo_corte end as corte
            from hub.colheita_voos v2 join hub.talhoes t on t.layer = v2.layer
           where v2.status in ('aguardando_corte', 'na_fila')) x
   where v.id = x.id
     and (v.data_corte is distinct from x.corte
          or v.status <> case when x.corte is null then 'aguardando_corte' else 'na_fila' end);
  get diagnostics v_n = row_count;
  return v_n;
end $$;

-- ── Ações do analista ──────────────────────────────────────────────────
create or replace function hub.colheita_pedir_voo(
  p_layers bigint[], p_tipo text, p_problema text default null, p_pedido_por text default null)
returns jsonb language plpgsql security definer set search_path = hub as $$
declare
  v_criados  int := 0;
  v_ignorados jsonb := '[]'::jsonb;
  r record;
  v_faz int;
begin
  if not hub.pode_editar('colheita') then
    raise exception 'Sem permissão para pedir voo na Colheita';
  end if;
  if p_tipo not in ('voar', 'revoar') then
    raise exception 'Tipo de pedido inválido: %', p_tipo;
  end if;
  if p_tipo = 'revoar' and length(trim(coalesce(p_problema, ''))) = 0 then
    raise exception 'Informe o que está errado nas linhas';
  end if;

  for r in select c.layer, c.status, c.estagio, c.voo_id
             from hub.colheita_talhoes c where c.layer = any (p_layers) loop
    if r.voo_id is not null then
      v_ignorados := v_ignorados || jsonb_build_object('layer', r.layer, 'motivo', 'já tem pedido de voo ativo');
    elsif p_tipo = 'voar' and r.status <> 'SEM LINHAS' then
      v_ignorados := v_ignorados || jsonb_build_object('layer', r.layer, 'motivo', 'Voar é só para talhão Sem Linhas');
    elsif p_tipo = 'voar' and coalesce(hub.numero_corte(r.estagio), 0) < 4 then
      v_ignorados := v_ignorados || jsonb_build_object('layer', r.layer,
        'motivo', coalesce(r.estagio, 'sem estágio') || ': até o 3º corte o voo automático do setor já cobre');
    else
      insert into hub.colheita_voos (layer, tipo, problema, pedido_por, apontado_por)
      values (r.layer, p_tipo, nullif(trim(p_problema), ''), nullif(trim(p_pedido_por), ''), auth.uid());
      insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, usuario_id, origem)
      values ('colheita', 'talhao', r.layer, 'pedido_voo',
              p_tipo || coalesce(' · ' || nullif(trim(p_problema), ''), '') || coalesce(' · pedido por ' || nullif(trim(p_pedido_por), ''), ''),
              auth.uid(), 'usuario');
      v_criados := v_criados + 1;
    end if;
  end loop;

  perform hub.colheita_voos_atualizar_fila();
  return jsonb_build_object('criados', v_criados, 'ignorados', v_ignorados);
end $$;

create or replace function hub.colheita_cancelar_voo(p_layers bigint[])
returns int language plpgsql security definer set search_path = hub as $$
declare
  v_n int;
  v_faz int;
begin
  if not hub.pode_editar('colheita') then
    raise exception 'Sem permissão para cancelar pedido de voo na Colheita';
  end if;
  with c as (
    update hub.colheita_voos set status = 'cancelado', cancelado_em = now()
     where layer = any (p_layers) and status in ('aguardando_corte', 'na_fila', 'erro')
    returning layer, tipo
  )
  insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo, usuario_id, origem)
  select 'colheita', 'talhao', layer, 'pedido_voo', tipo, 'cancelado', auth.uid(), 'usuario' from c;
  get diagnostics v_n = row_count;
  for v_faz in select distinct (l / 1000)::int from unnest(p_layers) l loop
    perform hub.colheita_avisos_voo(v_faz);
  end loop;
  return v_n;
end $$;

-- ── Funções do agente (service_role) ───────────────────────────────────
-- Devolve os pedidos com porte (liberar_em <= hoje) e já os marca como
-- "agendando": se o agente cair no meio, o pedido não é agendado duas vezes
-- (fica em "agendando" para conferência manual).
create or replace function hub.colheita_voos_pegar_devidos(p_limite int default 100)
returns table (id bigint, layer bigint, section text, land_plot text, harvest int)
language plpgsql security definer set search_path = hub as $$
begin
  return query
  update hub.colheita_voos v set status = 'agendando'
   where v.id in (select v2.id from hub.colheita_voos v2
                   where v2.status = 'na_fila' and v2.liberar_em <= current_date
                   order by v2.liberar_em, v2.id limit p_limite for update skip locked)
  returning v.id, v.layer, (v.layer / 1000)::text, ((v.layer % 1000))::text,
            2000 + split_part(hub.safra_colheita(), '-', 1)::int;
end $$;

create or replace function hub.colheita_voo_agendado(p_id bigint, p_dronemgmt_id uuid, p_erro text default null)
returns void language plpgsql security definer set search_path = hub as $$
declare v_layer bigint;
begin
  update hub.colheita_voos
     set status       = case when p_erro is null then 'agendado' else 'erro' end,
         dronemgmt_id = coalesce(p_dronemgmt_id, dronemgmt_id),
         agendado_em  = case when p_erro is null then now() end,
         erro         = p_erro
   where id = p_id and status = 'agendando'
  returning layer into v_layer;
  if v_layer is not null then
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, origem)
    values ('colheita', 'talhao', v_layer, 'pedido_voo',
            case when p_erro is null then 'agendado no Drone MGMT (Linhas de Colheita)' else 'erro: ' || p_erro end,
            'agente_voos');
    perform hub.colheita_avisos_voo((v_layer / 1000)::int);
  end if;
end $$;

-- Situação lida no Drone MGMT: controlStatus 4..9 = voado/processando,
-- 10 = relatório divulgado, 11 = cancelado lá.
create or replace function hub.colheita_voo_situacao(p_id bigint, p_control_status int)
returns void language plpgsql security definer set search_path = hub as $$
declare
  v_novo  text;
  v_layer bigint;
begin
  v_novo := case
    when p_control_status = 10               then 'divulgado'
    when p_control_status between 4 and 9    then 'voado'
    when p_control_status = 11               then 'erro'
  end;
  if v_novo is null then
    return;
  end if;
  update hub.colheita_voos
     set status       = v_novo,
         voado_em     = case when v_novo in ('voado', 'divulgado') then coalesce(voado_em, now()) else voado_em end,
         divulgado_em = case when v_novo = 'divulgado' then now() else divulgado_em end,
         erro         = case when v_novo = 'erro' then 'cancelado no Drone MGMT' else erro end
   where id = p_id and status in ('agendado', 'voado') and status <> v_novo
  returning layer into v_layer;
  if v_layer is not null then
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, origem)
    values ('colheita', 'talhao', v_layer, 'pedido_voo', v_novo, 'agente_voos');
    perform hub.colheita_avisos_voo((v_layer / 1000)::int);
  end if;
end $$;

-- ── Marcar o tipo de linha conclui o pedido divulgado ──────────────────
create or replace function hub.colheita_marcar_tipo(p_layers bigint[], p_tipo text)
returns int language plpgsql security definer set search_path = hub as $$
declare
  v_safra text := hub.safra_colheita();
  v_n     int;
  v_faz   int;
begin
  if not hub.pode_editar('colheita') then
    raise exception 'Sem permissão para editar a Colheita';
  end if;
  if p_tipo is not null and p_tipo not in ('VANT', 'PROJETO', 'SEM LINHAS') then
    raise exception 'Tipo de linha inválido: %', p_tipo;
  end if;

  with antes as (
    select layer, tipo_linha, ciclo, projeto_desatualizado
      from hub.talhao_colheita where layer = any (p_layers) for update
  ), mudou as (
    update hub.talhao_colheita c
       set tipo_linha = p_tipo,
           ciclo = case when p_tipo is null then null else v_safra end,
           projeto_desatualizado = false
      from antes a
     where c.layer = a.layer
    returning c.layer, a.tipo_linha as tipo_ant, a.ciclo as ciclo_ant
  )
  insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo,
                                 valor_anterior, valor_novo, usuario_id, origem)
  select 'colheita', 'talhao', layer, 'tipo_linha',
         nullif(concat_ws(' · ', tipo_ant, ciclo_ant), ''),
         nullif(concat_ws(' · ', p_tipo, case when p_tipo is not null then v_safra end), ''),
         auth.uid(), 'usuario'
    from mudou;
  get diagnostics v_n = row_count;

  -- Linhas novas registradas: o pedido de voo divulgado está concluído.
  if p_tipo in ('VANT', 'PROJETO') then
    update hub.colheita_voos set status = 'concluido', concluido_em = now()
     where layer = any (p_layers) and status = 'divulgado';
  end if;

  for v_faz in select distinct (l / 1000)::int from unnest(p_layers) l loop
    perform hub.colheita_aviso_desatualizado(v_faz);
    perform hub.colheita_avisos_voo(v_faz);
  end loop;
  return v_n;
end $$;

-- ── Segurança ──────────────────────────────────────────────────────────
alter table hub.colheita_voos enable row level security;
create policy leitura_autenticado on hub.colheita_voos for select to authenticated using (true);
grant select on hub.colheita_voos to authenticated;
grant all on hub.colheita_voos to service_role;
grant select on hub.colheita_talhoes to authenticated, service_role;

do $$
declare f text;
begin
  foreach f in array array[
    'hub.safra_colheita_inicio()', 'hub.colheita_avisos_voo(int)', 'hub.colheita_voos_atualizar_fila()',
    'hub.colheita_voos_pegar_devidos(int)', 'hub.colheita_voo_agendado(bigint, uuid, text)',
    'hub.colheita_voo_situacao(bigint, int)'] loop
    execute format('revoke all on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
  foreach f in array array[
    'hub.colheita_pedir_voo(bigint[], text, text, text)', 'hub.colheita_cancelar_voo(bigint[])',
    'hub.colheita_marcar_tipo(bigint[], text)'] loop
    execute format('revoke all on function %s from public, anon', f);
    execute format('grant execute on function %s to authenticated, service_role', f);
  end loop;
end $$;
revoke all on function hub.numero_corte(text) from public, anon;
grant execute on function hub.numero_corte(text) to authenticated, service_role;

commit;
