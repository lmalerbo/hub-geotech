-- Projetos, revisões e arquivos — mesmo mecanismo pra todos os módulos.
--
-- Projeto individual: 1 fazenda, no máximo 1 por módulo.
-- Projeto personalizado: montado a partir de revisões de projetos individuais
--   (ex: Rev0 da fazenda A + Rev1 da fazenda B); as fazendas dele são as dos
--   projetos de origem.
-- Revisões (Rev0, Rev1, ...): só uma vigente por projeto; a partir da Rev1 o
--   motivo é obrigatório. Revisão não altera o status do fluxo — é só
--   versionamento. Arquivos antigos nunca são apagados (ficam no histórico);
--   o Hub e o portal mostram só os da revisão vigente.
--
-- Substitui hub.arquivos (vazia, criada na migration inicial sem revisão).

begin;

drop table hub.arquivos;

create table hub.projetos (
  id          bigint generated always as identity primary key,
  modulo_id   text not null references hub.modulos (id),
  tipo        text not null check (tipo in ('individual', 'personalizado')),
  cod_faz     int references hub.fazendas (cod_faz),
  nome        text not null,
  criado_por  uuid references hub.usuarios (id),
  criado_em   timestamptz not null default now(),
  check ((tipo = 'individual') = (cod_faz is not null))
);
create unique index projetos_individual_unico
  on hub.projetos (modulo_id, cod_faz) where tipo = 'individual';

create table hub.projeto_revisoes (
  id          bigint generated always as identity primary key,
  projeto_id  bigint not null references hub.projetos (id) on delete cascade,
  numero      int not null check (numero >= 0),
  motivo      text,
  vigente     boolean not null default true,
  criado_por  uuid references hub.usuarios (id),
  criado_em   timestamptz not null default now(),
  unique (projeto_id, numero),
  check (numero = 0 or length(trim(coalesce(motivo, ''))) > 0)
);
create unique index projeto_revisoes_uma_vigente
  on hub.projeto_revisoes (projeto_id) where vigente;

-- De quais revisões individuais uma revisão personalizada foi montada.
create table hub.revisao_origens (
  revisao_id         bigint not null references hub.projeto_revisoes (id) on delete cascade,
  origem_revisao_id  bigint not null references hub.projeto_revisoes (id),
  primary key (revisao_id, origem_revisao_id),
  check (revisao_id <> origem_revisao_id)
);

-- Metadado do arquivo; o arquivo em si fica no GitHub Releases, com a revisão
-- no nome (ex: 10728_VISCONDE.DO.PARNAIBA.3_Rev1.zip), e nunca é apagado.
create table hub.revisao_arquivos (
  id             bigint generated always as identity primary key,
  revisao_id     bigint not null references hub.projeto_revisoes (id) on delete cascade,
  nome_arquivo   text not null,
  release_url    text not null,
  tamanho_bytes  bigint,
  publicado_por  uuid references hub.usuarios (id),
  publicado_em   timestamptz not null default now(),
  unique (revisao_id, nome_arquivo)
);

-- O que o Hub e o portal mostram: só os arquivos da revisão vigente.
create view hub.arquivos_vigentes with (security_invoker = true) as
select p.id        as projeto_id,
       p.modulo_id,
       p.tipo,
       p.cod_faz,
       p.nome      as projeto,
       r.id        as revisao_id,
       r.numero    as revisao,
       a.nome_arquivo,
       a.release_url,
       a.tamanho_bytes,
       a.publicado_em
  from hub.projetos p
  join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente
  join hub.revisao_arquivos a on a.revisao_id = r.id;

-- Abre a próxima revisão de um projeto, em uma transação: a anterior deixa de
-- ser vigente e a nova nasce vigente. Só editor com acesso ao módulo (ou
-- admin) pode; as importações usam a service_role.
create or replace function hub.nova_revisao(
  p_projeto_id bigint,
  p_motivo     text,
  p_origens    bigint[] default null
)
returns bigint
language plpgsql
security definer
set search_path = hub
as $$
declare
  v_modulo text;
  v_numero int;
  v_id     bigint;
begin
  -- Trava o projeto: duas revisões simultâneas não podem ganhar o mesmo número.
  select modulo_id into v_modulo from hub.projetos where id = p_projeto_id for update;
  if v_modulo is null then
    raise exception 'Projeto % não existe', p_projeto_id;
  end if;

  if coalesce(auth.role(), '') <> 'service_role' and not exists (
       select 1
         from hub.usuarios u
        where u.id = auth.uid()
          and (u.admin
               or (u.papel = 'editor'
                   and exists (select 1 from hub.usuario_modulos m
                                where m.usuario_id = u.id and m.modulo_id = v_modulo)))) then
    raise exception 'Sem permissão para revisar projetos de %', v_modulo;
  end if;

  select coalesce(max(numero) + 1, 0) into v_numero
    from hub.projeto_revisoes where projeto_id = p_projeto_id;

  if v_numero > 0 and length(trim(coalesce(p_motivo, ''))) = 0 then
    raise exception 'Informe o motivo da Rev%', v_numero;
  end if;

  update hub.projeto_revisoes set vigente = false
   where projeto_id = p_projeto_id and vigente;

  insert into hub.projeto_revisoes (projeto_id, numero, motivo, criado_por)
  values (p_projeto_id, v_numero, nullif(trim(p_motivo), ''), auth.uid())
  returning id into v_id;

  if p_origens is not null then
    insert into hub.revisao_origens (revisao_id, origem_revisao_id)
    select v_id, unnest(p_origens);
  end if;

  return v_id;
end $$;

revoke all on function hub.nova_revisao(bigint, text, bigint[]) from public, anon;
grant execute on function hub.nova_revisao(bigint, text, bigint[]) to authenticated, service_role;

-- Segurança: mesma política das outras tabelas (logado lê; escrita via RPC/service_role).
alter table hub.projetos         enable row level security;
alter table hub.projeto_revisoes enable row level security;
alter table hub.revisao_origens  enable row level security;
alter table hub.revisao_arquivos enable row level security;
create policy leitura_autenticado on hub.projetos         for select to authenticated using (true);
create policy leitura_autenticado on hub.projeto_revisoes for select to authenticated using (true);
create policy leitura_autenticado on hub.revisao_origens  for select to authenticated using (true);
create policy leitura_autenticado on hub.revisao_arquivos for select to authenticated using (true);
grant select on hub.arquivos_vigentes to authenticated;
grant select on hub.arquivos_vigentes to service_role;

commit;
