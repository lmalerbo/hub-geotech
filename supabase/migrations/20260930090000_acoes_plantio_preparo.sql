-- Ações feitas pela tela (usuário logado), fase 2A: as que não dependem de
-- arquivo. Mesmo fluxo dos sistemas atuais, sempre por fazenda:
--
-- Plantio (por fazenda, aplicado aos talhões dela):
--   Ag. Mapeamento → "Mapeamento concluído" → Pendente (mapeamento Sim)
--   Pendente       → "Iniciar projeto"      → Andamento
--   Retroceder para uma etapa anterior (voltar a Aguard. Map. zera o mapeamento)
--   Andamento → Ag. Mapa → Ok dependem de anexar arquivo (fase 2B).
--
-- Preparo (etapas por fazenda, em sequência):
--   concluir Identificação e Observações; reabrir qualquer etapa (reabre as
--   seguintes também). Escoamento e Projeto de Preparo exigem arquivo (2B).
--
-- Toda ação confere se quem chamou é editor do módulo (ou admin) e grava
-- cada mudança em hub.log_auditoria com o usuário.

-- Quem pode editar um módulo.
create or replace function hub.pode_editar(p_modulo text)
returns boolean
language sql
stable
security definer
set search_path = hub
as $$
  select exists (
    select 1 from hub.usuarios u
     where u.id = auth.uid()
       and (u.admin
            or (u.papel = 'editor'
                and exists (select 1 from hub.usuario_modulos m
                             where m.usuario_id = u.id and m.modulo_id = p_modulo))));
$$;

-- ── Plantio ──────────────────────────────────────────────────────────────
-- Ordem das etapas, pra saber o que é "antes" e "depois".
create or replace function hub.plantio_ordem(p_projeto text)
returns int
language sql
immutable
as $$
  select array_position(array['Aguard. Map.', 'Pendente', 'Andamento', 'Ag. Mapa', 'Ok'], p_projeto) - 1;
$$;

-- Muda a etapa dos talhões da fazenda que casam com o filtro, registra no log
-- e devolve quantos mudaram.
create or replace function hub.plantio_aplicar(
  p_cod_faz     int,
  p_de          text[],      -- só talhões nessas etapas (null = qualquer)
  p_so_mapeados boolean,     -- só talhões com mapeamento Sim
  p_para        text,
  p_mapeamento  text         -- novo mapeamento (null = não muda)
)
returns int
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_qtd int;
begin
  if not hub.pode_editar('plantio') then
    raise exception 'Sem permissão para editar o Plantio';
  end if;

  with alvo as (
    select p.layer, p.projeto as antes
      from hub.talhao_plantio p
      join hub.talhoes t on t.layer = p.layer
     where t.cod_faz = p_cod_faz
       and (p_de is null or p.projeto = any(p_de))
       and (not p_so_mapeados or p.mapeamento = 'Sim')
       and p.projeto <> p_para
  ), mudou as (
    update hub.talhao_plantio p
       set projeto    = p_para,
           mapeamento = coalesce(p_mapeamento, p.mapeamento)
      from alvo a
     where a.layer = p.layer
    returning p.layer, a.antes
  ), registro as (
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, valor_novo, usuario_id)
    select 'plantio', 'talhao', m.layer, 'projeto', m.antes, p_para, auth.uid() from mudou m
    returning 1
  )
  select count(*) into v_qtd from registro;

  if v_qtd = 0 then
    raise exception 'Nenhum talhão desta fazenda está na etapa certa para esta ação';
  end if;
  return v_qtd;
end $$;

create or replace function hub.plantio_mapeamento_concluido(p_cod_faz int)
returns int language sql security definer set search_path = hub as $$
  select hub.plantio_aplicar(p_cod_faz, array['Aguard. Map.'], false, 'Pendente', 'Sim');
$$;

create or replace function hub.plantio_iniciar(p_cod_faz int)
returns int language sql security definer set search_path = hub as $$
  select hub.plantio_aplicar(p_cod_faz, array['Pendente'], true, 'Andamento', null);
$$;

-- Só volta quem está DEPOIS da etapa escolhida (quem está antes não avança).
create or replace function hub.plantio_retroceder(p_cod_faz int, p_para text)
returns int
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_depois text[];
begin
  if hub.plantio_ordem(p_para) is null then
    raise exception 'Etapa inválida: %', p_para;
  end if;
  select array_agg(e) into v_depois
    from unnest(array['Aguard. Map.', 'Pendente', 'Andamento', 'Ag. Mapa', 'Ok']) e
   where hub.plantio_ordem(e) > hub.plantio_ordem(p_para);
  return hub.plantio_aplicar(p_cod_faz, v_depois, false, p_para,
                             case when p_para = 'Aguard. Map.' then 'Não' end);
end $$;

-- ── Preparo ──────────────────────────────────────────────────────────────
create or replace function hub.preparo_concluir_etapa(
  p_cod_faz    int,
  p_ordem      int,
  p_observacao text default null
)
returns void
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_etapa hub.etapas;
begin
  if not hub.pode_editar('preparo') then
    raise exception 'Sem permissão para editar o Preparo';
  end if;
  select * into v_etapa from hub.etapas where modulo_id = 'preparo' and ordem = p_ordem;
  if v_etapa.id is null then
    raise exception 'Etapa % do Preparo não existe', p_ordem;
  end if;
  if p_ordem in (2, 4) then
    raise exception '% exige anexar arquivos (chega na próxima versão)', v_etapa.nome;
  end if;
  if exists (
       select 1 from hub.etapas e
        where e.modulo_id = 'preparo' and e.ordem < p_ordem
          and not exists (select 1 from hub.etapa_status s
                           where s.etapa_id = e.id and s.entidade_id = p_cod_faz and s.ok)) then
    raise exception 'Conclua as etapas anteriores antes de %', v_etapa.nome;
  end if;

  insert into hub.etapa_status (etapa_id, entidade_id, ok, usuario_id, concluido_em, observacao)
  values (v_etapa.id, p_cod_faz, true, auth.uid(), now(), nullif(trim(p_observacao), ''))
  on conflict (etapa_id, entidade_id) do update
    set ok = true, usuario_id = auth.uid(), concluido_em = now(),
        observacao = coalesce(nullif(trim(p_observacao), ''), hub.etapa_status.observacao);

  insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, usuario_id)
  values ('preparo', 'fazenda', p_cod_faz, v_etapa.nome, 'concluída', auth.uid());
end $$;

-- Reabre a etapa e as seguintes (o fluxo é em sequência).
create or replace function hub.preparo_reabrir_etapa(p_cod_faz int, p_ordem int)
returns int
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_qtd int;
begin
  if not hub.pode_editar('preparo') then
    raise exception 'Sem permissão para editar o Preparo';
  end if;

  with reaberta as (
    update hub.etapa_status s
       set ok = false, usuario_id = auth.uid(), concluido_em = null
      from hub.etapas e
     where e.id = s.etapa_id and e.modulo_id = 'preparo' and e.ordem >= p_ordem
       and s.entidade_id = p_cod_faz and s.ok
    returning e.nome
  ), registro as (
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_novo, usuario_id)
    select 'preparo', 'fazenda', p_cod_faz, r.nome, 'reaberta', auth.uid() from reaberta r
    returning 1
  )
  select count(*) into v_qtd from registro;

  if v_qtd = 0 then
    raise exception 'Essa etapa não está concluída';
  end if;
  return v_qtd;
end $$;

-- Só a tela (usuário logado) chama; a checagem de editor fica dentro de cada uma.
revoke all on function hub.pode_editar(text) from public, anon;
revoke all on function hub.plantio_aplicar(int, text[], boolean, text, text) from public, anon, authenticated;
revoke all on function hub.plantio_mapeamento_concluido(int) from public, anon;
revoke all on function hub.plantio_iniciar(int) from public, anon;
revoke all on function hub.plantio_retroceder(int, text) from public, anon;
revoke all on function hub.preparo_concluir_etapa(int, int, text) from public, anon;
revoke all on function hub.preparo_reabrir_etapa(int, int) from public, anon;
grant execute on function hub.pode_editar(text) to authenticated;
grant execute on function hub.plantio_mapeamento_concluido(int) to authenticated;
grant execute on function hub.plantio_iniciar(int) to authenticated;
grant execute on function hub.plantio_retroceder(int, text) to authenticated;
grant execute on function hub.preparo_concluir_etapa(int, int, text) to authenticated;
grant execute on function hub.preparo_reabrir_etapa(int, int) to authenticated;
