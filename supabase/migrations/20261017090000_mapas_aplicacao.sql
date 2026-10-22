-- Mapas de aplicação (spec docs/superpowers/specs/2026-10-16-mapas-aplicacao-aerea-design.md).
-- A ferramenta Corretivos passa a se chamar "Mapas de aplicação" e ganha o tipo de mapa Aplicação aérea:
-- aplicação de INSUMO (cadastro hub.insumos) com dose por hectare na unidade do insumo (L ou KG).
-- As tabelas hub.corretivo_* mantêm o nome. Aplicar ANTES de publicar a tela nova (ela lê hub.insumos).
begin;

update hub.modulos set nome = 'Mapas de aplicação' where id = 'corretivos';

-- Cadastro de insumos: quem usa a ferramenta lê e mantém. Remover = ativo false (mapas antigos guardam cópia).
create table hub.insumos (
  id             bigint generated always as identity primary key,
  codigo         int,
  nome           text not null check (nome = trim(nome) and length(nome) > 0),
  unidade        text not null check (unidade in ('L', 'KG')),
  dose_sugerida  numeric check (dose_sugerida > 0),
  ativo          boolean not null default true,
  criado_em      timestamptz not null default now()
);
-- Nome único só entre os ativos: um insumo removido pode ser cadastrado de novo.
create unique index insumos_nome_unico on hub.insumos (upper(nome)) where ativo;
create unique index insumos_codigo_unico on hub.insumos (codigo) where ativo;

alter table hub.insumos enable row level security;
create policy insumos on hub.insumos for all to authenticated
  using ((select hub.pode_usar_corretivos())) with check ((select hub.pode_usar_corretivos()));
grant select, insert, update on hub.insumos to authenticated;
grant all on hub.insumos to service_role;

-- Lista inicial: arquivo "INSUMOS AVIÃO 1" (16/10/2026). Dose sugerida = a dose média mais comum no arquivo.
insert into hub.insumos (codigo, nome, unidade, dose_sugerida) values
  (29779,  'REGULADOR MATURADOR ETHEP', 'L',  0.08),
  (68405,  'INSETICIDA THIAMETHOXAM 7', 'KG', 0.33),
  (70438,  'FERTILIZANTE FOLIAR NORTO', 'L',  0.03),
  (300526, 'FUNGICIDA PRIORI XTRA',     'L',  0.5),
  (304384, 'REGULADOR CRESC STOLLER S', 'L',  0.5),
  (319220, 'INSETICIDA TRIFLUMUROM 48', 'L',  0.08),
  (347001, 'INSETICIDA CLORANTRANILIP', 'KG', 0.06),
  (359274, 'FERTILIZANTE BVI CANA PRE', 'L',  20),
  (375247, 'FUNGICIDA AZOXYSTR+FLUTR',  'L',  0.5),
  (397513, 'FERTILIZANTE FOLIAR AVANT', 'L',  0.03),
  (500522, 'ADJUVANTE LIQUIDO OCHIMA',  'L',  0.25),
  (500798, 'INSETICIDA CHLORANTR+LAMB', 'L',  0.1),
  (512945, 'FERTILIZANTE FOLIAR CONCO', 'L',  1),
  (513244, 'INSETICIDA REVOLUX',        'L',  0.15),
  (522645, 'FERTILIZANTE AMINOCORE BA', 'L',  0.15),
  (535986, 'REGULADOR SUMITOMO PROGIB', 'KG', 0.008),
  (538760, 'INSETICIDA BOVERIZ BEAUVE', 'KG', 0.2),
  (538761, 'INSETICIDA BEAUVERIA CORV', 'KG', 0.5),
  (539344, 'INSETICIDA SPERTO UPL',     'KG', 1.2),
  (543907, 'INOCULANTE AZOTROP',        'L',  0.3),
  (544379, 'INOCULANTE LIQUIDO KOPPER', 'L',  0.3),
  (544383, 'INSETICIDA METARRIZ PLUS',  'KG', 0.05),
  (545930, 'FERTILIZANTE REVITA',       'L',  1),
  (545931, 'FERTILIZANTE PROTEMAX',     'L',  1),
  (552163, 'INSETICIDA BOVETTUS',       'L',  0.15),
  (554070, 'INSETICIDA FRONDEO 1L',     'L',  0.05),
  (562188, 'FERTILIZANTE EUROAMINO',    'L',  1),
  (562297, 'INSETICIDA BOUVERIZ WP PR', 'KG', 0.1),
  (562351, 'INSETICIDA BEAUVERIA BASS', 'KG', 0.5),
  (562863, 'FERTILIZANTE OUROACTIVE U', 'L',  0.15),
  (562864, 'FERTILIZANTE VOLT 20L',     'L',  0.5),
  (562877, 'FERTILIZANTE UPPER 1L',     'L',  10),
  (562900, 'FERTILIZANTE TRIUNFUS CAN', 'L',  8),
  (563266, 'INSETICIDA VANTACOR 5L',    'L',  0.035);

-- Mapa aéreo.
alter table hub.corretivo_mapas drop constraint if exists corretivo_mapas_operacao_check;
alter table hub.corretivo_mapas add constraint corretivo_mapas_operacao_check
  check (operacao in ('subsolagem', 'supergrade', 'arado', 'aerea'));

-- Aplicação de insumo, com cópia de nome e unidade no momento da gravação.
alter table hub.corretivo_aplicacoes
  add column insumo_id      bigint references hub.insumos (id),
  add column insumo_nome    text,
  add column insumo_unidade text check (insumo_unidade in ('L', 'KG'));
alter table hub.corretivo_aplicacoes drop constraint if exists corretivo_aplicacoes_tipo_check;
alter table hub.corretivo_aplicacoes drop constraint if exists corretivo_aplicacoes_check;
alter table hub.corretivo_aplicacoes add constraint corretivo_aplicacoes_tipo_check
  check (tipo in ('calcario', 'fosfato', 'blend', 'insumo'));
alter table hub.corretivo_aplicacoes add constraint corretivo_aplicacoes_check check (
     (tipo = 'fosfato'  and calcario is null     and dose_gesso is null     and insumo_id is null)
  or (tipo = 'calcario' and calcario is not null and dose_gesso is null     and insumo_id is null)
  or (tipo = 'blend'    and calcario is not null and dose_gesso is not null and insumo_id is null)
  or (tipo = 'insumo'   and calcario is null     and dose_gesso is null
      and insumo_id is not null and insumo_nome is not null and insumo_unidade is not null));

-- Aplicação idêntica no mesmo talhão: agora também compara o insumo.
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
                and b.dose_gesso is not distinct from a.dose_gesso and b.os = a.os
                and b.insumo_id is not distinct from a.insumo_id) then
    raise exception 'O talhão % já tem esta aplicação', new.talhao_num;
  end if;
  return new;
end $$;

-- Aplicar: mapa aéreo só aceita insumo (ativo); mapa de corretivo só aceita calcário, fosfato e blend.
create or replace function hub.corretivo_aplicar(p_mapa_id bigint, p_aplicacao jsonb, p_talhoes jsonb)
returns bigint language plpgsql security definer set search_path = hub as $$
declare v_id bigint; v_ordem int; v_op text; v_tipo text := p_aplicacao->>'tipo'; i hub.insumos;
begin
  if not hub.pode_usar_corretivos() then raise exception 'Sem acesso aos Mapas de aplicação'; end if;
  if jsonb_array_length(coalesce(p_talhoes, '[]'::jsonb)) = 0 then raise exception 'Marque ao menos um talhão'; end if;
  select operacao into v_op from hub.corretivo_mapas where id = p_mapa_id;
  if v_op is null then raise exception 'Mapa % não existe', p_mapa_id; end if;
  if (v_op = 'aerea') <> (v_tipo = 'insumo') then
    raise exception 'Este mapa (%) não aceita aplicação do tipo %', v_op, v_tipo;
  end if;
  if v_tipo = 'insumo' then
    select * into i from hub.insumos where id = (p_aplicacao->>'insumo_id')::bigint;
    if i.id is null then raise exception 'Escolha o insumo'; end if;
    if not i.ativo then raise exception 'O insumo % foi removido do cadastro', i.nome; end if;
  end if;
  perform hub.corretivo_travar_mapa(p_mapa_id);
  perform hub.corretivo_garantir_talhoes(p_mapa_id, p_talhoes);
  select coalesce(max(ordem), 0) + 1 into v_ordem from hub.corretivo_aplicacoes where mapa_id = p_mapa_id;
  insert into hub.corretivo_aplicacoes (mapa_id, tipo, calcario, dose, dose_gesso, os, ordem,
                                        insumo_id, insumo_nome, insumo_unidade)
  values (p_mapa_id, v_tipo, nullif(p_aplicacao->>'calcario', ''), (p_aplicacao->>'dose')::numeric,
          (p_aplicacao->>'dose_gesso')::numeric, trim(p_aplicacao->>'os'), v_ordem, i.id, i.nome, i.unidade)
  returning id into v_id;
  insert into hub.corretivo_aplicacao_talhoes (aplicacao_id, mapa_id, talhao_num)
  select v_id, p_mapa_id, (x->>'talhao_num')::int from jsonb_array_elements(p_talhoes) x;
  return v_id;
end $$;

commit;
