-- Módulo Colheita (substitui o Expo_safra).
--
-- Por talhão a equipe marca só o TIPO DE LINHA (Linha de Vant, Desdobra de
-- Plantio, Sem Linhas). O ciclo é a safra em que o projeto de exportação é
-- feito: gravado sozinho com a safra atual (hub.parametros.colheita_safra).
-- O status é calculado (view hub.colheita_talhoes):
--   sem tipo, ou replantado (Regra A)  → A FAZER
--   tipo de uma safra anterior          → REAVALIAR
--   Sem Linhas na safra atual           → SEM LINHAS
--   Vant/Desdobra na safra atual        → CONCLUIDO
-- Na virada de safra basta trocar o parâmetro: o que não for refeito vira
-- REAVALIAR.
--
-- Regra A: talhão que fecha o Plantio (projeto → Ok) fica com o projeto de
-- colheita desatualizado (replantado) e gera aviso no sininho.
--
-- Avisos (sininho): gravados no banco, com lido/não lido por pessoa.

begin;

-- ── Parâmetros gerais ──────────────────────────────────────────────────
create table hub.parametros (
  chave         text primary key,
  valor         text not null,
  descricao     text,
  atualizado_em timestamptz not null default now()
);
insert into hub.parametros (chave, valor, descricao) values
  ('colheita_safra', '26-27', 'Safra atual do projeto de colheita (ciclo gravado ao marcar o tipo de linha)');

create or replace function hub.safra_colheita()
returns text language sql stable security definer set search_path = hub as $$
  select valor from hub.parametros where chave = 'colheita_safra';
$$;

-- ── Talhão da Colheita ─────────────────────────────────────────────────
-- status passa a ser calculado; frente é texto (o ICOL tem "BIS - 3").
alter table hub.talhao_colheita drop column status;
alter table hub.talhao_colheita
  add column periodo_op int,       -- dono: ICOL (mês operacional)
  add column cortado    boolean,   -- dono: ICOL (CORTADO / DISPONIVEL)
  add column ciclo      text,      -- safra em que o projeto de exportação foi feito
  add constraint talhao_colheita_tipo_linha_check
    check (tipo_linha in ('VANT', 'PROJETO', 'SEM LINHAS'));

create view hub.colheita_talhoes with (security_invoker = true) as
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
         when c.ciclo is distinct from hub.safra_colheita()        then 'REAVALIAR'
         when c.tipo_linha = 'SEM LINHAS'                          then 'SEM LINHAS'
         else 'CONCLUIDO'
       end as status
  from hub.talhao_colheita c
  join hub.talhoes t on t.layer = c.layer;

-- ── Avisos (sininho) ───────────────────────────────────────────────────
create table hub.avisos (
  id            bigint generated always as identity primary key,
  modulo_id     text not null references hub.modulos (id),
  tipo          text not null,
  cod_faz       int,
  titulo        text not null,
  texto         text,
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  resolvido_em  timestamptz
);
-- um aviso aberto por tipo + fazenda: novos eventos atualizam o mesmo aviso
create unique index avisos_um_aberto on hub.avisos (tipo, cod_faz) where resolvido_em is null;

create table hub.avisos_lidos (
  aviso_id   bigint not null references hub.avisos (id) on delete cascade,
  usuario_id uuid   not null references hub.usuarios (id) on delete cascade,
  lido_em    timestamptz not null default now(),
  primary key (aviso_id, usuario_id)
);

create or replace function hub.avisos_marcar_lidos(p_ids bigint[])
returns void language sql security definer set search_path = hub as $$
  insert into hub.avisos_lidos (aviso_id, usuario_id)
  select unnest(p_ids), auth.uid()
  on conflict do nothing;
$$;

-- Abre ou atualiza o aviso de "projeto desatualizado" de uma fazenda (e o
-- marca como não lido de novo), ou resolve se não sobrou talhão pendente.
create or replace function hub.colheita_aviso_desatualizado(p_cod_faz int)
returns void language plpgsql security definer set search_path = hub as $$
declare
  v_n    int;
  v_nome text;
  v_id   bigint;
begin
  select count(*) into v_n
    from hub.talhao_colheita c join hub.talhoes t on t.layer = c.layer
   where t.cod_faz = p_cod_faz and c.projeto_desatualizado;
  if v_n = 0 then
    update hub.avisos set resolvido_em = now()
     where tipo = 'colheita_desatualizado' and cod_faz = p_cod_faz and resolvido_em is null;
    return;
  end if;
  select nome into v_nome from hub.fazendas where cod_faz = p_cod_faz;
  insert into hub.avisos (modulo_id, tipo, cod_faz, titulo, texto)
  values ('colheita', 'colheita_desatualizado', p_cod_faz,
          p_cod_faz || ' ' || coalesce(v_nome, '') || ': projeto de colheita desatualizado',
          v_n || ' talhão(ões) replantado(s) no Plantio. Sugestão: Desdobra de Plantio.')
  on conflict (tipo, cod_faz) where resolvido_em is null
    do update set texto = excluded.texto, atualizado_em = now()
  returning id into v_id;
  delete from hub.avisos_lidos where aviso_id = v_id;
end $$;

-- ── Regra A: Plantio Ok → projeto de colheita desatualizado ────────────
create or replace function hub.regra_a_plantio_ok()
returns trigger language plpgsql security definer set search_path = hub as $$
begin
  -- Restauração de status do sistema antigo não é replantio de agora.
  if coalesce(current_setting('hub.sem_regra_a', true), '') = 'on' then
    return new;
  end if;
  if new.projeto = 'Ok' and old.projeto is distinct from 'Ok' then
    insert into hub.talhao_colheita (layer, projeto_desatualizado)
    values (new.layer, true)
    on conflict (layer) do update set projeto_desatualizado = true;
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo,
                                   valor_anterior, valor_novo, usuario_id, origem)
    values ('colheita', 'talhao', new.layer, 'projeto_desatualizado', null, 'replantado no Plantio',
            auth.uid(), 'regra_a_plantio');
    perform hub.colheita_aviso_desatualizado((new.layer / 1000)::int);
  end if;
  return new;
end $$;

create trigger talhao_plantio_regra_a
  after update of projeto on hub.talhao_plantio
  for each row execute function hub.regra_a_plantio_ok();

-- A restauração diária de status guardados (sistema antigo) não dispara a
-- Regra A: mesma função de antes, com o aviso no início.
create or replace function hub.restaurar_status_guardado()
returns int
language plpgsql
set search_path = hub
as $$
declare
  v_qtd int;
begin
  perform set_config('hub.sem_regra_a', 'on', true);
  with prontos as (
    delete from hub.plantio_status_guardado g
     using hub.talhoes t
     where t.layer = g.layer
    returning g.*
  ), gravados as (
    insert into hub.talhao_plantio (layer, mes_plantio, seq_plantio, mapeamento, projeto)
    select layer, mes_plantio, seq_plantio, mapeamento, projeto from prontos
    on conflict (layer) do update
      set mapeamento  = excluded.mapeamento,
          projeto     = excluded.projeto,
          seq_plantio = coalesce(hub.talhao_plantio.seq_plantio, excluded.seq_plantio)
    returning layer, projeto
  ), registro as (
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, origem)
    select 'plantio', 'talhao', layer, 'projeto', projeto, 'restaurado_sistema_antigo' from gravados
    returning 1
  )
  select count(*) into v_qtd from registro;
  perform set_config('hub.sem_regra_a', 'off', true);
  return v_qtd;
end $$;

-- ── Ação: marcar o tipo de linha (em lote) ─────────────────────────────
-- p_tipo null desfaz (volta para A FAZER). Grava o ciclo = safra atual,
-- limpa o "desatualizado" e registra no histórico.
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

  for v_faz in select distinct (l / 1000)::int from unnest(p_layers) l loop
    perform hub.colheita_aviso_desatualizado(v_faz);
  end loop;
  return v_n;
end $$;

-- ── Documentos da Colheita ─────────────────────────────────────────────
-- Nome: {cod}_{NOME.DA.FAZENDA}_Rev{n}-Exp1L.dwg (confirmado: nada depende
-- do nome antigo).
insert into hub.documento_tipos (modulo_id, codigo, nome, marcador, sufixo, ordem, extensoes) values
  ('colheita', 'exp1l', 'Exportação 1 Linha',  'Rev', '-Exp1L', 1, array['dwg', 'zip']),
  ('colheita', 'exp2l', 'Exportação 2 Linhas', 'Rev', '-Exp2L', 2, array['dwg', 'zip']),
  ('colheita', 'mapa',  'Mapa de partes',      'Rev', '-Mapa',  3, array['pdf'])
on conflict do nothing;

-- ── Segurança ──────────────────────────────────────────────────────────
alter table hub.parametros   enable row level security;
alter table hub.avisos       enable row level security;
alter table hub.avisos_lidos enable row level security;
create policy leitura_autenticado on hub.parametros for select to authenticated using (true);
create policy leitura_autenticado on hub.avisos     for select to authenticated using (true);
create policy leitura_propria     on hub.avisos_lidos for select to authenticated using (usuario_id = auth.uid());
grant select on hub.colheita_talhoes to authenticated, service_role;

revoke all on function hub.safra_colheita()                     from public, anon;
revoke all on function hub.avisos_marcar_lidos(bigint[])        from public, anon;
revoke all on function hub.colheita_aviso_desatualizado(int)    from public, anon, authenticated;
revoke all on function hub.regra_a_plantio_ok()                 from public, anon, authenticated;
revoke all on function hub.colheita_marcar_tipo(bigint[], text) from public, anon;
grant execute on function hub.safra_colheita()                     to authenticated, service_role;
grant execute on function hub.avisos_marcar_lidos(bigint[])        to authenticated;
grant execute on function hub.colheita_aviso_desatualizado(int)    to service_role;
grant execute on function hub.colheita_marcar_tipo(bigint[], text) to authenticated, service_role;

commit;
