-- Metas e rascunho da Apresentação semanal (spec 2026-10-29, D6).
begin;

create table hub.apresentacao_metas (
  chave          text primary key,
  valor          text not null,
  rotulo         text not null,
  atualizado_por uuid references hub.usuarios (id) default auth.uid(),
  atualizado_em  timestamptz not null default now()
);
insert into hub.apresentacao_metas (chave, valor, rotulo) values
  ('meta_ervas_ha', '20863', 'Ervas daninhas (ha)'),
  ('meta_fornecedor_ha', '3500', 'Fornecedor (ha)'),
  ('meta_ha_dia', '250', 'Ritmo de voo (ha/dia)'),
  ('drone_pendente_ha', '2000', 'Drone pendente (ha)'),
  ('safra_atual', '26/27', 'Safra atual'),
  ('inicio_safra', '2026-04-01', 'Início da safra');

create table hub.apresentacao_semanas (
  semana         text primary key check (semana ~ '^S[1-5]M([1-9]|1[0-2])$'),
  corte          date not null,
  textos         jsonb not null default '{}',
  atualizado_por uuid references hub.usuarios (id) default auth.uid(),
  atualizado_em  timestamptz not null default now()
);

create or replace function hub.apresentacao_carimbo()
returns trigger language plpgsql as $$
begin new.atualizado_por := auth.uid(); new.atualizado_em := now(); return new; end $$;
create trigger apresentacao_metas_carimbo before update on hub.apresentacao_metas
  for each row execute function hub.apresentacao_carimbo();

alter table hub.apresentacao_metas enable row level security;
alter table hub.apresentacao_semanas enable row level security;
create policy ferramenta on hub.apresentacao_metas for all to authenticated
  using (hub.pode_usar_apresentacao()) with check (hub.pode_usar_apresentacao());
create policy ferramenta on hub.apresentacao_semanas for select to authenticated
  using (hub.pode_usar_apresentacao());
grant select, update on hub.apresentacao_metas to authenticated;
grant select on hub.apresentacao_semanas to authenticated;

-- Grava um campo de um slide sem apagar os outros (dois editores na mesma semana).
create or replace function hub.apresentacao_texto_salvar(p_semana text, p_corte date, p_slide text, p_campo text, p_valor text)
returns timestamptz language plpgsql security definer set search_path = hub as $$
declare v_em timestamptz := now();
begin
  if not hub.pode_usar_apresentacao() then raise exception 'Sem acesso à Apresentação semanal'; end if;
  if p_slide not in ('divisoria', 'colheita', 'sistematizacao', 'plantio', 'voos', 'drone') then raise exception 'Slide inválido'; end if;
  if p_campo not in ('subtitulo', 'destaque', 'notas') then raise exception 'Campo inválido'; end if;
  insert into hub.apresentacao_semanas (semana, corte, textos, atualizado_por, atualizado_em)
  values (p_semana, p_corte, jsonb_build_object(p_slide, jsonb_build_object(p_campo, p_valor)), auth.uid(), v_em)
  on conflict (semana) do update
    set corte = excluded.corte,
        textos = hub.apresentacao_semanas.textos
                 || jsonb_build_object(p_slide, coalesce(hub.apresentacao_semanas.textos -> p_slide, '{}') || jsonb_build_object(p_campo, p_valor)),
        atualizado_por = auth.uid(), atualizado_em = v_em;
  return v_em;
end $$;
revoke all on function hub.apresentacao_texto_salvar(text, date, text, text, text) from public, anon;
grant execute on function hub.apresentacao_texto_salvar(text, date, text, text, text) to authenticated;

commit;