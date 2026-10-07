# Módulo Drone — Parte 2: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** pôr o trabalho do Drone dentro do Hub (fila, fazenda com mapa por talhão, revisão por talhão, envios, prévia e publicação). A Normal passa a ser montada talhão a talhão, a Catação passa a ser só o último levantamento, e o portal ganha a tag de Normal incompleta.

**Arquitetura:**
- **Banco (Supabase/PostGIS):** guarda a geometria dos talhões, os talhões de cada revisão e de cada geração, e os envios de arquivo.
- **Funções `security definer`:** o Hub (usuário logado) chama essas funções para solicitar, enviar, gerar, publicar e ler o mapa.
- **Agente Python do servidor Geo:** continua fazendo todo o trabalho geográfico (ler shapefile, recortar, montar a revisão, gerar o PDF e o `.zip`, publicar).
- **Tela:** um arquivo novo, `app/drone.js`, carregado pelo `app/index.html`. O mapa usa MapLibre GL.

**Stack:**
- Python 3.12+ (geopandas, shapely 2, pyogrio, pytest);
- PostgreSQL/PostGIS (schema `hub`, PostGIS no schema `extensions`);
- JavaScript puro no navegador (supabase-js v2 já carregado e MapLibre GL 4 via jsdelivr);
- Playwright Python (Edge) para o teste da tela.

**Spec:** `docs/superpowers/specs/2026-10-07-modulo-drone-parte2-design.md` (e a Parte 1: `2026-09-29-modulo-drone-parte1-design.md`).

## Restrições globais

- CRS de cálculo: **EPSG:31983**. CRS do mapa e da `talhao_geom`: **EPSG:4326**.
- `talhao_geom`: simplificação de **0,5 m** em 31983 antes de reprojetar. `area_ha` = área da geometria em 31983.
- Cobertura da Normal = área (geometria) dos talhões da Base de hoje que têm talhão na revisão vigente ÷ área de todos os talhões da Base de hoje × 100. Completa = 100.
- Origem do talhão do projeto: `'sistema' | 'shape' | 'legado'`. `desde_rev` = número da revisão em que aquela geometria entrou.
- **Catação** = só o levantamento enviado na solicitação. Nada é herdado da revisão anterior.
- **Talhão que saiu da Base:** só aviso. O projeto não muda sozinho.
- **Uma geração aberta** (`fila`, `processando`, `pronta`) por fazenda e documento.
- **Envios:** bucket privado `drone-envios`. Caminho dos arquivos: `{cod_faz}/{timestamp}/{nome}`.
- **Papéis:**
  - editor do Drone = `hub.pode_editar('drone')`, que inclui admin;
  - solicitante = `usuarios.papel = 'solicitante'` com `drone` em `usuario_modulos`.
- **Mensagens** para o usuário em português.
- **Teste com dados reais:** salvar e restaurar, nunca apagar dado real.

## Foco da revisão

1. **Dois analistas gerando a mesma fazenda ao mesmo tempo:** a segunda geração é recusada com mensagem clara (Tarefa 1, verificação SQL).
2. **Talhão escolhido que deixou de existir na Base entre o clique e a geração:** erro listando os talhões, sem gerar nada (Tarefa 3).
3. **Shape de ajuste que não cobre um talhão marcado como "subir shape":** erro listando os talhões (Tarefa 3).
4. **Primeira Normal de uma fazenda** (sem revisão vigente) e **remoção de todos os talhões:** a primeira monta a partir do vazio; a segunda dá erro de área vazia (Tarefa 3).
5. **Envio com `.zip` de pastas aninhadas, ou com arquivo de obstáculo sem a classe no nome:** acha os `.shp` dentro do `.zip`; arquivo sem classe dá erro pedindo para escolher a classe (Tarefa 6).

---

## Estrutura de arquivos

```
supabase/migrations/20261008090000_drone_parte2.sql   tabelas, funções do Hub e do agente, storage
ingestao/talhao_geom.py                                geometria dos talhões → hub.talhao_geom (rodada diária)
ingestao/rodar_diario.py                               + etapa talhao_geom.py
drone/montagem.py                                      montar a Normal por talhão, dividir por talhão, cobertura
drone/gerador.py                                       usa montagem; grava os talhões da geração
drone/mapa_pdf.py                                      linha "Incompleta · XX% da fazenda"
drone/banco.py                                         métodos novos (talhões, envios, ajuste)
drone/publicacao.py                                    publicar(..., talhoes=None)
drone/envios.py                                        processa os envios feitos pelo Hub
drone/agente.py                                        + processar envios no ciclo
drone/revisar_legado.py                                Catação = só o último levantamento; publica com talhões
drone/migrar_parte2.py                                 carga única: talhões das revisões vigentes
drone/cli.py                                           gerar Normal = fazenda inteira (escopo nulo)
app/drone.js                                           tela do Drone
app/index.html                                         menu, view, permissões, scripts
app/portal.html                                        tag "Incompleta · XX%"
tests/drone/test_talhao_geom.py, test_montagem.py, test_gerador.py (ajustado), test_envios.py,
tests/drone/test_publicacao.py (ajustado), test_revisar_legado.py (ajustado), test_migrar_parte2.py
tests/app/teste_drone_tela.py                          Playwright (roda à mão, conta de teste)
```

---

### Tarefa 1: Migration da Parte 2

**Arquivos:**
- Criar: `supabase/migrations/20261008090000_drone_parte2.sql`

**Interfaces produzidas:**
- **Tabelas:**
  - `hub.talhao_geom(cod_faz, talhao_num, geom 4326, area_ha, atualizado_em)`
  - `hub.drone_revisao_talhoes(revisao_id, talhao_num, geom 31983, area_ha, origem, desde_rev)`
  - `hub.drone_geracao_talhoes(geracao_id, …mesmas colunas)`
  - `hub.drone_envios(id, cod_faz, tipo, classe_m, solicitacao_id, arquivos, status, erro, enviado_por, enviado_em, processado_em, iniciado_em)`
  - `hub.drone_ajuste_feicoes(envio_id, geom 31983)`
  - colunas `drone_solicitacoes.observacao` e `drone_geracoes.escopo`
  - view `hub.drone_cobertura_v(cod_faz, cobertura_pct)`
- **Agente (service_role):**
  - `talhao_geom_limpar(p_antes timestamptz) → int`
  - `drone_talhoes_vigentes(p_cod_faz int, p_documento text) → table(talhao_num, wkt, area_ha, origem, desde_rev, revisao_em)`
  - `drone_gravar_geracao_talhoes(p_geracao_id bigint, p_talhoes jsonb) → void`
  - `drone_gravar_revisao_talhoes(p_revisao_id bigint, p_talhoes jsonb) → void`
  - `drone_pegar_envio() → setof drone_envios`
  - `drone_concluir_envio(p_id bigint, p_status text, p_erro text) → void`
  - `drone_gravar_ajuste(p_envio_id bigint, p_wkts text[]) → void`
  - `drone_ajuste_wkt(p_envio_id bigint) → table(wkt text)`
  - `drone_publicar(p_cod_faz, p_documento, p_motivo, p_numero, p_arquivos, p_geracao_id, p_legado, p_talhoes jsonb default null) → bigint`
- **Hub (authenticated):**
  - `drone_solicitar(p_cod_faz int, p_tipo text, p_data_desejada date, p_observacao text) → bigint`
  - `drone_registrar_envio(p_cod_faz int, p_tipo text, p_classe_m int, p_solicitacao_id bigint, p_arquivos text[]) → bigint`
  - `drone_pedir_geracao(p_solicitacao_id bigint, p_escopo jsonb) → bigint`
  - `drone_publicar_pedido(p_geracao_id bigint, p_motivo text) → void`
  - `drone_descartar(p_geracao_id bigint) → void`
  - `drone_mapa_fazenda(p_cod_faz int) → jsonb`
  - `drone_painel() → jsonb`
  - `public.portal_drone_cobertura() → table(cod_faz int, cobertura_pct numeric)` (anon)
- **Formato do JSON de talhões** (`p_talhoes`): `[{"talhao":20,"wkt":"MULTIPOLYGON(...)","area_ha":12.3,"origem":"sistema","desde_rev":1}]`
- **Formato do escopo:** `{"incluir":[{"talhao":20,"fonte":"sistema"},{"talhao":21,"fonte":"shape","envio_id":7}],"remover":[129]}`

- [ ] **Passo 1: Escrever a migration**

```sql
-- Módulo Drone, Parte 2: geometria dos talhões, projeto por talhão, envios
-- pelo Hub e funções da tela. Spec: docs/superpowers/specs/2026-10-07-modulo-drone-parte2-design.md
begin;

-- ── execuções da ingestão: fonte nova ─────────────────────────────────
alter table hub.execucoes_ingestao drop constraint if exists execucoes_ingestao_fonte_check;
alter table hub.execucoes_ingestao add constraint execucoes_ingestao_fonte_check
  check (fonte in ('base_fazendas', 'planagri', 'icol', 'conservacao', 'dronemgmt', 'talhao_geom'));

-- ── geometria dos talhões (rodada diária) ─────────────────────────────
create table hub.talhao_geom (
  cod_faz       int not null,
  talhao_num    int not null,
  geom          extensions.geometry(MultiPolygon, 4326) not null,
  area_ha       numeric not null,
  atualizado_em timestamptz not null default now(),
  primary key (cod_faz, talhao_num)
);

create or replace function hub.talhao_geom_limpar(p_antes timestamptz)
returns int language plpgsql security definer set search_path = hub as $$
declare n int;
begin
  delete from hub.talhao_geom where atualizado_em < p_antes;
  get diagnostics n = row_count;
  return n;
end $$;

-- ── talhões das revisões e das gerações ───────────────────────────────
create table hub.drone_revisao_talhoes (
  revisao_id bigint not null references hub.projeto_revisoes (id) on delete cascade,
  talhao_num int    not null,
  geom       extensions.geometry(MultiPolygon, 31983) not null,
  area_ha    numeric not null,
  origem     text   not null check (origem in ('sistema', 'shape', 'legado')),
  desde_rev  int    not null,
  primary key (revisao_id, talhao_num)
);

create table hub.drone_geracao_talhoes (
  geracao_id bigint not null references hub.drone_geracoes (id) on delete cascade,
  talhao_num int    not null,
  geom       extensions.geometry(MultiPolygon, 31983) not null,
  area_ha    numeric not null,
  origem     text   not null check (origem in ('sistema', 'shape', 'legado')),
  desde_rev  int    not null,
  primary key (geracao_id, talhao_num)
);

alter table hub.drone_solicitacoes add column observacao text;
alter table hub.drone_geracoes add column escopo jsonb;

-- ── envios pelo Hub ───────────────────────────────────────────────────
create table hub.drone_envios (
  id             bigint generated always as identity primary key,
  cod_faz        int    not null references hub.fazendas (cod_faz),
  tipo           text   not null check (tipo in ('obstaculos', 'infestacao', 'ajuste')),
  classe_m       int    check (classe_m in (15, 25, 50)),
  solicitacao_id bigint references hub.drone_solicitacoes (id),
  arquivos       text[] not null,
  status         text   not null default 'fila' check (status in ('fila', 'processando', 'ok', 'erro')),
  erro           text,
  enviado_por    uuid references hub.usuarios (id),
  enviado_em     timestamptz not null default now(),
  iniciado_em    timestamptz,
  processado_em  timestamptz
);
create index on hub.drone_envios (status, enviado_em);

create table hub.drone_ajuste_feicoes (
  envio_id bigint not null references hub.drone_envios (id) on delete cascade,
  geom     extensions.geometry(Geometry, 31983) not null
);
create index on hub.drone_ajuste_feicoes (envio_id);

-- ── cobertura da Normal vigente ───────────────────────────────────────
create view hub.drone_cobertura_v with (security_invoker = false) as
select p.cod_faz,
       round(100 * sum(case when t.talhao_num is not null then g.area_ha else 0 end)
             / nullif(sum(g.area_ha), 0), 1) as cobertura_pct
  from hub.projetos p
  join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente and r.documento = 'normal'
  join hub.talhao_geom g on g.cod_faz = p.cod_faz
  left join hub.drone_revisao_talhoes t on t.revisao_id = r.id and t.talhao_num = g.talhao_num
 where p.modulo_id = 'drone' and p.tipo = 'individual'
 group by p.cod_faz;

-- ── funções do agente ─────────────────────────────────────────────────
create or replace function hub.drone_talhoes_vigentes(p_cod_faz int, p_documento text)
returns table (talhao_num int, wkt text, area_ha numeric, origem text, desde_rev int, revisao_em timestamptz)
language sql stable security definer set search_path = hub, extensions as $$
  select t.talhao_num, ST_AsText(t.geom), t.area_ha, t.origem, t.desde_rev, r.criado_em
    from hub.projetos p
    join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente and r.documento = p_documento
    join hub.drone_revisao_talhoes t on t.revisao_id = r.id
   where p.modulo_id = 'drone' and p.tipo = 'individual' and p.cod_faz = p_cod_faz;
$$;

create or replace function hub.drone_gravar_geracao_talhoes(p_geracao_id bigint, p_talhoes jsonb)
returns void language plpgsql security definer set search_path = hub, extensions as $$
begin
  delete from hub.drone_geracao_talhoes where geracao_id = p_geracao_id;
  insert into hub.drone_geracao_talhoes (geracao_id, talhao_num, geom, area_ha, origem, desde_rev)
  select p_geracao_id, (e->>'talhao')::int, ST_Multi(ST_GeomFromText(e->>'wkt', 31983)),
         (e->>'area_ha')::numeric, e->>'origem', (e->>'desde_rev')::int
    from jsonb_array_elements(p_talhoes) e;
end $$;

create or replace function hub.drone_gravar_revisao_talhoes(p_revisao_id bigint, p_talhoes jsonb)
returns void language plpgsql security definer set search_path = hub, extensions as $$
begin
  delete from hub.drone_revisao_talhoes where revisao_id = p_revisao_id;
  insert into hub.drone_revisao_talhoes (revisao_id, talhao_num, geom, area_ha, origem, desde_rev)
  select p_revisao_id, (e->>'talhao')::int, ST_Multi(ST_GeomFromText(e->>'wkt', 31983)),
         (e->>'area_ha')::numeric, e->>'origem', (e->>'desde_rev')::int
    from jsonb_array_elements(p_talhoes) e;
end $$;

create or replace function hub.drone_pegar_envio()
returns setof hub.drone_envios language plpgsql security definer set search_path = hub as $$
begin
  update hub.drone_envios set status = 'fila', iniciado_em = null
   where status = 'processando' and iniciado_em < now() - interval '15 minutes';
  return query
  update hub.drone_envios e set status = 'processando', iniciado_em = now()
   where e.id = (select id from hub.drone_envios where status = 'fila'
                  order by enviado_em for update skip locked limit 1)
  returning e.*;
end $$;

create or replace function hub.drone_concluir_envio(p_id bigint, p_status text, p_erro text)
returns void language sql security definer set search_path = hub as $$
  update hub.drone_envios set status = p_status, erro = left(p_erro, 1000), processado_em = now() where id = p_id;
$$;

create or replace function hub.drone_gravar_ajuste(p_envio_id bigint, p_wkts text[])
returns void language plpgsql security definer set search_path = hub, extensions as $$
begin
  delete from hub.drone_ajuste_feicoes where envio_id = p_envio_id;
  insert into hub.drone_ajuste_feicoes (envio_id, geom)
  select p_envio_id, ST_Force2D(ST_GeomFromText(w, 31983)) from unnest(p_wkts) w;
end $$;

create or replace function hub.drone_ajuste_wkt(p_envio_id bigint)
returns table (wkt text) language sql stable security definer set search_path = hub, extensions as $$
  select ST_AsText(geom) from hub.drone_ajuste_feicoes where envio_id = p_envio_id;
$$;

-- publicação: agora grava também os talhões (da geração ou do p_talhoes)
drop function hub.drone_publicar(int, text, text, int, jsonb, bigint, boolean);
create or replace function hub.drone_publicar(
  p_cod_faz int, p_documento text, p_motivo text, p_numero int, p_arquivos jsonb,
  p_geracao_id bigint default null, p_legado boolean default false, p_talhoes jsonb default null)
returns bigint language plpgsql security definer set search_path = hub, extensions as $$
declare v_proj bigint; v_rev bigint; v_num int; v_sol bigint;
begin
  insert into hub.projetos (modulo_id, tipo, cod_faz, nome)
  select 'drone', 'individual', f.cod_faz, f.nome from hub.fazendas f where f.cod_faz = p_cod_faz
  on conflict (modulo_id, cod_faz) where tipo = 'individual' do nothing;
  select id into v_proj from hub.projetos
   where modulo_id = 'drone' and tipo = 'individual' and cod_faz = p_cod_faz;
  if v_proj is null then
    raise exception 'Fazenda % não existe em hub.fazendas', p_cod_faz;
  end if;

  v_rev := hub.nova_revisao(v_proj, p_documento, p_motivo);
  select numero into v_num from hub.projeto_revisoes where id = v_rev;
  if v_num <> p_numero then
    raise exception 'A revisão mudou: arquivos enviados como Rev%, mas a próxima é Rev%. Gere o projeto de novo.',
      p_numero, v_num;
  end if;

  insert into hub.revisao_arquivos (revisao_id, nome_arquivo, release_url, tamanho_bytes)
  select v_rev, a.nome, a.url, a.tamanho
    from jsonb_to_recordset(p_arquivos) as a (nome text, url text, tamanho bigint);

  if p_geracao_id is not null then
    insert into hub.drone_revisao_talhoes (revisao_id, talhao_num, geom, area_ha, origem, desde_rev)
    select v_rev, talhao_num, geom, area_ha, origem, desde_rev
      from hub.drone_geracao_talhoes where geracao_id = p_geracao_id;
    update hub.drone_geracoes set status = 'publicada', concluido_em = now()
     where id = p_geracao_id and status = 'pronta' returning solicitacao_id into v_sol;
    if v_sol is null then
      raise exception 'Geração % não está pronta para publicar', p_geracao_id;
    end if;
    update hub.drone_geracoes set status = 'descartada'
     where solicitacao_id = v_sol and id <> p_geracao_id and status in ('fila', 'pronta', 'erro');
    update hub.drone_solicitacoes set status = 'ok', revisao_id = v_rev, concluido_em = now()
     where id = v_sol;
  elsif p_talhoes is not null then
    insert into hub.drone_revisao_talhoes (revisao_id, talhao_num, geom, area_ha, origem, desde_rev)
    select v_rev, (e->>'talhao')::int, ST_Multi(ST_GeomFromText(e->>'wkt', 31983)),
           (e->>'area_ha')::numeric, e->>'origem', (e->>'desde_rev')::int
      from jsonb_array_elements(p_talhoes) e;
  end if;

  if p_legado then
    insert into hub.drone_solicitacoes (cod_faz, tipo, origem, status, revisao_id, concluido_em)
    values (p_cod_faz, p_documento, 'legado', 'ok', v_rev, now());
  end if;
  return v_rev;
end $$;

-- ── funções do Hub (usuário logado) ───────────────────────────────────
create or replace function hub.drone_solicitar(p_cod_faz int, p_tipo text, p_data_desejada date default null,
                                               p_observacao text default null)
returns bigint language plpgsql security definer set search_path = hub as $$
declare v_id bigint;
begin
  if p_tipo not in ('normal', 'catacao') then
    raise exception 'Tipo inválido: %', p_tipo;
  end if;
  if not hub.pode_editar('drone') and not (p_tipo = 'normal' and exists (
       select 1 from hub.usuarios u join hub.usuario_modulos m on m.usuario_id = u.id and m.modulo_id = 'drone'
        where u.id = auth.uid() and u.papel = 'solicitante')) then
    raise exception 'Sem permissão para abrir solicitação de %', p_tipo;
  end if;
  if not exists (select 1 from hub.fazendas where cod_faz = p_cod_faz) then
    raise exception 'Fazenda % não existe', p_cod_faz;
  end if;
  select id into v_id from hub.drone_solicitacoes
   where cod_faz = p_cod_faz and tipo = p_tipo and origem <> 'legado' and status not in ('ok', 'cancelado')
   order by id desc limit 1;
  if v_id is not null then
    return v_id;                                   -- já existe uma aberta: reaproveita
  end if;
  insert into hub.drone_solicitacoes (cod_faz, tipo, origem, solicitante_id, data_desejada, observacao)
  values (p_cod_faz, p_tipo, 'formulario', auth.uid(), p_data_desejada, nullif(trim(p_observacao), ''))
  returning id into v_id;
  return v_id;
end $$;

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
  if exists (select 1 from unnest(p_arquivos) a where a not like p_cod_faz || '/%') then
    raise exception 'Arquivo fora da pasta da fazenda %', p_cod_faz;
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

create or replace function hub.drone_pedir_geracao(p_solicitacao_id bigint, p_escopo jsonb default null)
returns bigint language plpgsql security definer set search_path = hub as $$
declare v_sol hub.drone_solicitacoes; v_id bigint; v_inf bigint; v_ruins int[];
begin
  if not hub.pode_editar('drone') then
    raise exception 'Sem permissão para gerar projetos de drone';
  end if;
  select * into v_sol from hub.drone_solicitacoes where id = p_solicitacao_id for update;
  if v_sol.id is null then
    raise exception 'Solicitação % não existe', p_solicitacao_id;
  end if;
  if v_sol.status in ('ok', 'cancelado') then
    raise exception 'Solicitação % já está encerrada', p_solicitacao_id;
  end if;
  perform pg_advisory_xact_lock(hashtext('drone_geracao_' || v_sol.cod_faz || '_' || v_sol.tipo));
  if exists (select 1 from hub.drone_geracoes g join hub.drone_solicitacoes s on s.id = g.solicitacao_id
              where s.cod_faz = v_sol.cod_faz and s.tipo = v_sol.tipo and g.status in ('fila', 'processando', 'pronta')) then
    raise exception 'Já existe uma prévia aberta desta fazenda. Publique ou descarte antes de gerar outra.';
  end if;

  if v_sol.tipo = 'normal' then
    if p_escopo is null or (jsonb_array_length(coalesce(p_escopo->'incluir', '[]')) = 0
                            and jsonb_array_length(coalesce(p_escopo->'remover', '[]')) = 0) then
      raise exception 'Escolha ao menos um talhão para incluir, refazer ou remover';
    end if;
    select array_agg(i order by i) into v_ruins from (
      select (e->>'talhao')::int i from jsonb_array_elements(coalesce(p_escopo->'incluir', '[]')) e
      intersect
      select r::int from jsonb_array_elements_text(coalesce(p_escopo->'remover', '[]')) r) x;
    if v_ruins is not null then
      raise exception 'Talhões marcados para incluir e remover ao mesmo tempo: %', v_ruins;
    end if;
    select array_agg(x.i order by x.i) into v_ruins
      from (select (e->>'talhao')::int i from jsonb_array_elements(coalesce(p_escopo->'incluir', '[]')) e) x
     where not exists (select 1 from hub.talhao_geom g where g.cod_faz = v_sol.cod_faz and g.talhao_num = x.i);
    if v_ruins is not null then
      raise exception 'Talhões que não existem na Base de hoje: %', v_ruins;
    end if;
    if exists (select 1 from jsonb_array_elements(coalesce(p_escopo->'incluir', '[]')) e
                where e->>'fonte' = 'shape' and not exists (
                  select 1 from hub.drone_envios v where v.id = (e->>'envio_id')::bigint
                     and v.cod_faz = v_sol.cod_faz and v.tipo = 'ajuste' and v.status = 'ok')) then
      raise exception 'O shape de ajuste ainda não foi processado (ou é de outra fazenda)';
    end if;
  else
    select id into v_inf from hub.drone_infestacoes where solicitacao_id = v_sol.id order by id desc limit 1;
    if v_inf is null then
      raise exception 'Envie a infestação antes de gerar a Catação';
    end if;
  end if;

  insert into hub.drone_geracoes (solicitacao_id, infestacao_id, escopo, pedido_por)
  values (v_sol.id, v_inf, p_escopo, auth.uid()) returning id into v_id;
  update hub.drone_solicitacoes
     set status = 'em_elaboracao', iniciado_em = coalesce(iniciado_em, now()),
         responsavel_id = coalesce(responsavel_id, auth.uid())
   where id = v_sol.id;
  return v_id;
end $$;

create or replace function hub.drone_publicar_pedido(p_geracao_id bigint, p_motivo text)
returns void language plpgsql security definer set search_path = hub as $$
declare v_g hub.drone_geracoes; v_tipo text; v_cod int; v_tem_rev boolean;
begin
  if not hub.pode_editar('drone') then
    raise exception 'Sem permissão para publicar projetos de drone';
  end if;
  select * into v_g from hub.drone_geracoes where id = p_geracao_id for update;
  if v_g.id is null or v_g.status <> 'pronta' then
    raise exception 'A prévia % não está pronta para publicar', p_geracao_id;
  end if;
  select s.tipo, s.cod_faz into v_tipo, v_cod from hub.drone_solicitacoes s where s.id = v_g.solicitacao_id;
  select exists (select 1 from hub.projetos p join hub.projeto_revisoes r on r.projeto_id = p.id
                  where p.modulo_id = 'drone' and p.tipo = 'individual' and p.cod_faz = v_cod
                    and r.documento = v_tipo) into v_tem_rev;
  if v_tipo = 'normal' and v_tem_rev and length(trim(coalesce(p_motivo, ''))) = 0 then
    raise exception 'Informe o motivo da nova revisão';
  end if;
  update hub.drone_geracoes
     set publicar_pedido_em = now(), publicar_motivo = nullif(trim(p_motivo), ''), publicar_por = auth.uid(),
         publicacao_erro = null, publicacao_iniciada_em = null
   where id = p_geracao_id;
end $$;

create or replace function hub.drone_descartar(p_geracao_id bigint)
returns void language plpgsql security definer set search_path = hub as $$
begin
  if not hub.pode_editar('drone') then
    raise exception 'Sem permissão';
  end if;
  update hub.drone_geracoes set status = 'descartada'
   where id = p_geracao_id and status in ('pronta', 'erro');
  if not found then
    raise exception 'Só dá para descartar uma prévia pronta ou com erro';
  end if;
end $$;

create or replace function hub.drone_mapa_fazenda(p_cod_faz int)
returns jsonb language sql stable security definer set search_path = hub, extensions as $$
with vig as (
  select r.id, r.documento, r.numero, r.criado_em
    from hub.projeto_revisoes r join hub.projetos p on p.id = r.projeto_id
   where p.modulo_id = 'drone' and p.tipo = 'individual' and p.cod_faz = p_cod_faz and r.vigente),
n as (select t.* from hub.drone_revisao_talhoes t join vig on vig.id = t.revisao_id and vig.documento = 'normal'),
c as (select t.* from hub.drone_revisao_talhoes t join vig on vig.id = t.revisao_id and vig.documento = 'catacao'),
feats as (
  select jsonb_build_object('type', 'Feature', 'id', g.talhao_num, 'geometry', ST_AsGeoJSON(g.geom, 6)::jsonb,
           'properties', jsonb_build_object('camada', 'talhao', 'talhao', g.talhao_num, 'area_ha', round(g.area_ha, 2),
             'status', case when n.talhao_num is null then 'sem_projeto' else 'com_projeto' end,
             'desde_rev', n.desde_rev, 'origem', n.origem, 'catacao', c.talhao_num is not null)) f
    from hub.talhao_geom g
    left join n on n.talhao_num = g.talhao_num
    left join c on c.talhao_num = g.talhao_num
   where g.cod_faz = p_cod_faz
  union all
  select jsonb_build_object('type', 'Feature', 'id', 100000 + n.talhao_num,
           'geometry', ST_AsGeoJSON(ST_Transform(n.geom, 4326), 6)::jsonb,
           'properties', jsonb_build_object('camada', 'talhao', 'talhao', n.talhao_num, 'status', 'fora_da_base',
             'desde_rev', n.desde_rev, 'origem', n.origem))
    from n where not exists (select 1 from hub.talhao_geom g where g.cod_faz = p_cod_faz and g.talhao_num = n.talhao_num)
  union all
  select jsonb_build_object('type', 'Feature', 'geometry', ST_AsGeoJSON(ST_Transform(ST_Union(geom), 4326), 6)::jsonb,
           'properties', jsonb_build_object('camada', 'normal'))
    from n having count(*) > 0
  union all
  select jsonb_build_object('type', 'Feature', 'geometry', ST_AsGeoJSON(ST_Transform(ST_Union(geom), 4326), 6)::jsonb,
           'properties', jsonb_build_object('camada', 'catacao'))
    from c having count(*) > 0)
select jsonb_build_object(
  'type', 'FeatureCollection',
  'features', coalesce((select jsonb_agg(f) from feats), '[]'::jsonb),
  'normal', (select jsonb_build_object('revisao', numero, 'em', criado_em,
                                       'area_ha', (select round(sum(area_ha), 2) from n)) from vig where documento = 'normal'),
  'catacao', (select jsonb_build_object('revisao', numero, 'em', criado_em,
                                        'area_ha', (select round(sum(area_ha), 2) from c)) from vig where documento = 'catacao'),
  'cobertura_pct', (select cobertura_pct from hub.drone_cobertura_v where cod_faz = p_cod_faz));
$$;

create or replace function hub.drone_painel()
returns jsonb language sql stable security definer set search_path = hub as $$
select jsonb_build_object(
  'solicitacoes', coalesce((select jsonb_agg(x order by x->>'criado_em') from (
      select jsonb_build_object('id', s.id, 'cod_faz', s.cod_faz, 'fazenda', f.nome, 'tipo', s.tipo, 'status', s.status,
               'observacao', s.observacao, 'data_desejada', s.data_desejada, 'criado_em', s.criado_em,
               'solicitante', u.nome,
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
                            where p.modulo_id = 'drone'
                              and not exists (select 1 from hub.talhao_geom g
                                               where g.cod_faz = p.cod_faz and g.talhao_num = t.talhao_num)), '[]'::jsonb));
$$;

create or replace function public.portal_drone_cobertura()
returns table (cod_faz int, cobertura_pct numeric)
language sql stable security definer set search_path = hub as $$
  select cod_faz, cobertura_pct from hub.drone_cobertura_v;
$$;

-- ── segurança ─────────────────────────────────────────────────────────
do $$
declare t text;
begin
  foreach t in array array['talhao_geom', 'drone_revisao_talhoes', 'drone_geracao_talhoes',
                           'drone_envios', 'drone_ajuste_feicoes'] loop
    execute format('alter table hub.%I enable row level security', t);
    execute format('create policy leitura on hub.%I for select to authenticated using (true)', t);
    execute format('grant select on hub.%I to authenticated', t);
    execute format('grant all on hub.%I to service_role', t);
  end loop;
end $$;
grant select on hub.drone_cobertura_v to authenticated, service_role;

do $$
declare f text;
begin
  foreach f in array array[
    'hub.talhao_geom_limpar(timestamptz)', 'hub.drone_talhoes_vigentes(int, text)',
    'hub.drone_gravar_geracao_talhoes(bigint, jsonb)', 'hub.drone_gravar_revisao_talhoes(bigint, jsonb)',
    'hub.drone_pegar_envio()', 'hub.drone_concluir_envio(bigint, text, text)',
    'hub.drone_gravar_ajuste(bigint, text[])', 'hub.drone_ajuste_wkt(bigint)',
    'hub.drone_publicar(int, text, text, int, jsonb, bigint, boolean, jsonb)'] loop
    execute format('revoke all on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
  foreach f in array array[
    'hub.drone_solicitar(int, text, date, text)', 'hub.drone_registrar_envio(int, text, int, bigint, text[])',
    'hub.drone_pedir_geracao(bigint, jsonb)', 'hub.drone_publicar_pedido(bigint, text)',
    'hub.drone_descartar(bigint)', 'hub.drone_mapa_fazenda(int)', 'hub.drone_painel()'] loop
    execute format('revoke all on function %s from public, anon', f);
    execute format('grant execute on function %s to authenticated, service_role', f);
  end loop;
end $$;
revoke all on function public.portal_drone_cobertura() from public;
grant execute on function public.portal_drone_cobertura() to anon, authenticated, service_role;

-- ── storage: envios (editor sobe) e prévias (logado lê) ───────────────
insert into storage.buckets (id, name, public) values ('drone-envios', 'drone-envios', false)
on conflict (id) do nothing;
create policy drone_envios_sobe on storage.objects for insert to authenticated
  with check (bucket_id = 'drone-envios' and hub.pode_editar('drone'));
create policy drone_previas_le on storage.objects for select to authenticated
  using (bucket_id = 'drone-previas');

commit;
```

- [ ] **Passo 2: Pedir ao usuário que aplique no SQL Editor** (projeto `dpvsivypabmvmrrpgmhc`). Esperado: `Success. No rows returned`. Se aparecer o aviso de "tabelas sem RLS", é alarme falso: use "Run and enable RLS".

- [ ] **Passo 3: Verificação SQL (rodar e desfazer)**

```sql
begin;
-- a conta de teste vira editora do drone só dentro desta transação
select set_config('request.jwt.claims', json_build_object('sub', (select id from hub.usuarios where admin limit 1), 'role', 'authenticated')::text, true);
insert into hub.talhao_geom (cod_faz, talhao_num, geom, area_ha)
values (10974, 1, ST_Multi(ST_GeomFromText('POLYGON((-47.5 -21.4,-47.49 -21.4,-47.49 -21.39,-47.5 -21.39,-47.5 -21.4))', 4326)), 100);
select hub.drone_solicitar(10974, 'normal', null, 'teste') as sol \gset
select hub.drone_pedir_geracao(:sol, '{"incluir":[{"talhao":1,"fonte":"sistema"}],"remover":[]}');            -- ok
select hub.drone_pedir_geracao(:sol, '{"incluir":[{"talhao":1,"fonte":"sistema"}],"remover":[]}');            -- ERRO: prévia aberta
rollback;
begin;
select set_config('request.jwt.claims', json_build_object('sub', (select id from hub.usuarios where admin limit 1), 'role', 'authenticated')::text, true);
select hub.drone_pedir_geracao(hub.drone_solicitar(10974, 'normal', null, null), '{"incluir":[{"talhao":999,"fonte":"sistema"}]}'); -- ERRO: não existem na Base: {999}
rollback;
select jsonb_array_length(hub.drone_painel()->'solicitacoes') >= 0 as painel_ok;
```

O SQL Editor não interpreta `\gset`. Rode a primeira transação em duas partes, copiando o id devolvido por `drone_solicitar` no lugar de `:sol`. Esperado: a primeira chamada dá certo, a segunda falha com "Já existe uma prévia aberta", o talhão 999 dá "Talhões que não existem na Base de hoje: {999}" e o painel responde.

- [ ] **Passo 4: Commit**

```bash
git add supabase/migrations/20261008090000_drone_parte2.sql
git commit -m "Drone Parte 2: migration (talhões no banco, revisão por talhão, envios e funções da tela)"
```

---

### Tarefa 2: Geometria dos talhões na rodada diária

**Arquivos:**
- Criar: `ingestao/talhao_geom.py`, `tests/drone/test_talhao_geom.py`
- Modificar: `ingestao/rodar_diario.py:19` (lista `ETAPAS`)

**Interfaces:**
- Consome: `hub.talhao_geom`, `hub.talhao_geom_limpar(p_antes)` (Tarefa 1); `drone.base_talhoes.arquivo_mais_recente`, `drone.geometria.so_poligonos`; `comum.Hub`, `Execucao`, `agora_iso`.
- Produz: `talhao_geom.linhas(gdf) -> list[dict]` com as chaves `cod_faz`, `talhao_num`, `geom` (EWKT `SRID=4326;MULTIPOLYGON(...)`) e `area_ha` (float, 4 casas).

- [ ] **Passo 1: Teste que falha**

`tests/drone/test_talhao_geom.py`:
```python
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ingestao'))
from talhao_geom import linhas  # noqa: E402


def _gdf(**cols):
    geoms = cols.pop('geometry')
    return gpd.GeoDataFrame(cols, geometry=geoms, crs=31983)


def test_uma_linha_por_talhao_em_4326_com_area_em_31983():
    g = _gdf(SECAO=['10156', '10156', '10156'], TALHAO=[1, 1, 2],
             geometry=[box(200000, 7550000, 200100, 7550100), box(200100, 7550000, 200200, 7550100),
                       box(200300, 7550000, 200400, 7550050)])
    out = {(l['cod_faz'], l['talhao_num']): l for l in linhas(g)}
    assert set(out) == {(10156, 1), (10156, 2)}
    assert out[(10156, 1)]['area_ha'] == pytest.approx(2.0)           # duas partes viram um MultiPolygon
    assert out[(10156, 1)]['geom'].startswith('SRID=4326;MULTIPOLYGON')
    assert '-4' in out[(10156, 1)]['geom']                              # graus (longitude negativa)


def test_ignora_codigo_invalido_e_geometria_vazia():
    g = _gdf(SECAO=['abc', '99', '10156'], TALHAO=[1, 1, None],
             geometry=[box(0, 0, 10, 10), box(0, 0, 10, 10), box(0, 0, 10, 10)])
    assert linhas(g) == []
```

- [ ] **Passo 2:** `python -m pytest tests/drone/test_talhao_geom.py -v` → esperado: FALHA com `ModuleNotFoundError: No module named 'talhao_geom'`.

- [ ] **Passo 3: Implementar `ingestao/talhao_geom.py`**

```python
"""Grava a geometria de cada talhão da Base de Talhões em hub.talhao_geom (mapa do Hub, cobertura).

Lê o .shp do dia (o mesmo da Base Fazendas), simplifica 0,5 m em SIRGAS/UTM 23S e grava em WGS84.
Talhões que saíram da Base são apagados da tabela (o projeto de drone não é tocado).
Uso:  python ingestao/talhao_geom.py [--simular]
"""
import argparse
import os
import sys

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely import wkt as shapely_wkt
from shapely.ops import unary_union
from shapely.validation import make_valid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comum import Execucao, Hub, agora_iso, carregar_config  # noqa: E402
from drone.base_talhoes import arquivo_mais_recente  # noqa: E402
from drone.geometria import so_poligonos  # noqa: E402

LOTE = 200


def linhas(gdf) -> list:
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf['cod'] = pd.to_numeric(gdf['SECAO'], errors='coerce')
    gdf['tal'] = pd.to_numeric(gdf['TALHAO'], errors='coerce')
    gdf = gdf[gdf['cod'].between(10000, 99999) & gdf['tal'].between(0, 999)]
    out = []
    for (cod, tal), g in gdf.groupby(['cod', 'tal']):
        geom = so_poligonos(make_valid(make_valid(unary_union(list(g.geometry))).simplify(0.5)))
        if geom.is_empty:
            continue
        em_graus = gpd.GeoSeries([geom], crs=31983).to_crs(4326).iloc[0]
        out.append({'cod_faz': int(cod), 'talhao_num': int(tal),
                    'geom': 'SRID=4326;' + shapely_wkt.dumps(em_graus, rounding_precision=7),
                    'area_ha': round(geom.area / 1e4, 4)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true')
    args = ap.parse_args()
    cfg = carregar_config()['drone']
    _, caminho = arquivo_mais_recente(cfg['base_talhoes_pasta'], cfg['base_talhoes_padrao'])
    gdf = pyogrio.read_dataframe(caminho, columns=['SECAO', 'TALHAO']).to_crs(31983)
    dados = linhas(gdf)
    print(f'{caminho.name}: {len(dados)} talhões com geometria')
    if args.simular:
        print('Simulação: nada foi gravado.')
        return
    hub = Hub()
    with Execucao(hub, 'talhao_geom') as execucao:
        inicio = agora_iso()
        for i in range(0, len(dados), LOTE):
            hub.upsert('talhao_geom', [{**d, 'atualizado_em': inicio} for d in dados[i:i + LOTE]],
                       'cod_faz,talhao_num')
        apagados = hub.rpc('talhao_geom_limpar', {'p_antes': inicio})
        execucao.linhas_lidas = len(gdf)
        execucao.linhas_gravadas = len(dados)
    print(f'Gravado no Hub ({apagados} talhões que saíram da Base foram retirados).')


if __name__ == '__main__':
    main()
```

E em `ingestao/rodar_diario.py` troque a linha 19:
```python
ETAPAS = ['base_fazendas.py', 'talhao_geom.py', 'planagri.py', 'conservacao.py', 'icol.py']
```

- [ ] **Passo 4:** `python -m pytest tests/drone/test_talhao_geom.py -v` → 2 passed.

- [ ] **Passo 5: Primeira carga real** (depois da Tarefa 1 aplicada): `python ingestao/talhao_geom.py`. Esperado: cerca de 15 mil talhões gravados. Confira com `select count(*), count(distinct cod_faz) from hub.talhao_geom;`.

- [ ] **Passo 6: Commit**

```bash
git add ingestao/talhao_geom.py ingestao/rodar_diario.py tests/drone/test_talhao_geom.py
git commit -m "Drone Parte 2: geometria dos talhões no banco pela rodada diária"
```

---

### Tarefa 3: Montagem da Normal por talhão

**Arquivos:**
- Criar: `drone/montagem.py`, `tests/drone/test_montagem.py`

**Interfaces:**
- Consome: `drone.geometria.so_poligonos`, `drone.erros.ErroGeracao`.
- Produz (o "item" é `{'geom': MultiPolygon 31983, 'area_ha': float, 'origem': str, 'desde_rev': int}`):
  - `dividir_por_talhao(area, talhoes, origem, desde_rev) -> dict[int, item]`
  - `montar_normal(vigentes: dict[int, item], escopo: dict | None, talhoes, buffers, ajuste: list, nova_rev: int) -> dict[int, item]`
  - `uniao(itens) -> MultiPolygon`
  - `cobertura(itens, talhoes) -> float` (0–100)
  - `fora_da_base(itens, talhoes) -> list[int]`
  - `itens_para_json(itens) -> list[dict]` (formato `p_talhoes` da Tarefa 1)
- `talhoes` = GeoDataFrame com as colunas `TALHAO` (int) e `geometry` (31983), igual ao `talhoes_da_fazenda`.

- [ ] **Passo 1: Testes que falham**

`tests/drone/test_montagem.py`:
```python
import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon, box

from drone.erros import ErroGeracao
from drone.montagem import (cobertura, dividir_por_talhao, fora_da_base, itens_para_json, montar_normal, uniao)


@pytest.fixture
def base():
    """3 talhões de 1 ha lado a lado."""
    return gpd.GeoDataFrame({'TALHAO': [1, 2, 3]},
                            geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100), box(200, 0, 300, 100)], crs=31983)


def _item(geom, origem='legado', rev=0):
    return {'geom': geom, 'area_ha': geom.area / 1e4, 'origem': origem, 'desde_rev': rev}


def test_dividir_por_talhao_corta_na_borda(base):
    itens = dividir_por_talhao(box(50, 0, 250, 100), base, 'legado', 0)
    assert sorted(itens) == [1, 2, 3]
    assert itens[1]['area_ha'] == pytest.approx(0.5)
    assert itens[2]['origem'] == 'legado' and itens[2]['desde_rev'] == 0


def test_incluir_pelo_sistema_desconta_obstaculos_e_copia_o_resto(base):
    vig = {1: _item(box(0, 0, 100, 100))}
    obst = Point(150, 50).buffer(10)
    itens = montar_normal(vig, {'incluir': [{'talhao': 2, 'fonte': 'sistema'}], 'remover': []}, base, obst, [], 1)
    assert sorted(itens) == [1, 2]
    assert itens[1]['desde_rev'] == 0 and itens[1]['origem'] == 'legado'      # copiado igual
    assert itens[2]['desde_rev'] == 1 and itens[2]['origem'] == 'sistema'
    assert itens[2]['area_ha'] == pytest.approx(1 - obst.area / 1e4, rel=1e-3)


def test_refazer_substitui_e_remover_tira(base):
    vig = {1: _item(box(0, 0, 100, 50)), 2: _item(box(100, 0, 200, 100))}
    itens = montar_normal(vig, {'incluir': [{'talhao': 1, 'fonte': 'sistema'}], 'remover': [2]}, base, Polygon(), [], 3)
    assert sorted(itens) == [1]
    assert itens[1]['area_ha'] == pytest.approx(1.0) and itens[1]['desde_rev'] == 3


def test_incluir_por_shape_recorta_no_talhao(base):
    ajuste = [box(150, 0, 260, 100)]
    itens = montar_normal({}, {'incluir': [{'talhao': 2, 'fonte': 'shape', 'envio_id': 7},
                                           {'talhao': 3, 'fonte': 'shape', 'envio_id': 7}]}, base, Polygon(), ajuste, 0)
    assert itens[2]['area_ha'] == pytest.approx(0.5) and itens[2]['origem'] == 'shape'
    assert itens[3]['area_ha'] == pytest.approx(0.6)


def test_shape_que_nao_cobre_o_talhao_da_erro_listando(base):
    with pytest.raises(ErroGeracao, match=r'3'):
        montar_normal({}, {'incluir': [{'talhao': 3, 'fonte': 'shape', 'envio_id': 7}]}, base, Polygon(),
                      [box(0, 0, 50, 50)], 0)


def test_talhao_que_saiu_da_base_da_erro_sem_gerar(base):
    with pytest.raises(ErroGeracao, match=r'Base de hoje: 9'):
        montar_normal({}, {'incluir': [{'talhao': 9, 'fonte': 'sistema'}]}, base, Polygon(), [], 0)


def test_primeira_normal_parte_do_vazio_e_escopo_nulo_e_fazenda_inteira(base):
    itens = montar_normal({}, None, base, Polygon(), [], 0)
    assert sorted(itens) == [1, 2, 3] and all(v['origem'] == 'sistema' for v in itens.values())


def test_remover_tudo_da_erro_de_area_vazia(base):
    vig = {1: _item(box(0, 0, 100, 100))}
    with pytest.raises(ErroGeracao, match='vazia'):
        montar_normal(vig, {'incluir': [], 'remover': [1]}, base, Polygon(), [], 1)


def test_cobertura_fora_da_base_uniao_e_json(base):
    itens = {1: _item(box(0, 0, 100, 60)), 9: _item(box(500, 0, 510, 10))}
    assert cobertura(itens, base) == pytest.approx(100 / 3)      # talhão 1 conta inteiro, mesmo com obstáculo
    assert fora_da_base(itens, base) == [9]
    assert uniao(itens).area == pytest.approx(6000 + 100)
    j = itens_para_json(itens)
    assert {x['talhao'] for x in j} == {1, 9} and j[0]['wkt'].startswith('MULTIPOLYGON')
```

- [ ] **Passo 2:** `python -m pytest tests/drone/test_montagem.py -v` → FALHA (`ModuleNotFoundError: drone.montagem`).

- [ ] **Passo 3: Implementar `drone/montagem.py`**

```python
"""Projeto Normal por talhão (spec Parte 2, §4.1): a revisão nova parte da vigente,
troca os talhões incluídos/refeitos, tira os removidos e copia o resto."""
from shapely.ops import unary_union
from shapely.validation import make_valid

from drone.erros import ErroGeracao
from drone.geometria import so_poligonos

MINIMO_M2 = 1.0


def _item(geom, origem, desde_rev):
    return {'geom': geom, 'area_ha': geom.area / 1e4, 'origem': origem, 'desde_rev': desde_rev}


def _base(talhoes) -> dict:
    return {int(t['TALHAO']): make_valid(t.geometry) for _, t in talhoes.iterrows()}


def dividir_por_talhao(area, talhoes, origem, desde_rev) -> dict:
    itens = {}
    for n, g in _base(talhoes).items():
        p = so_poligonos(make_valid(area.intersection(g)))
        if p.area >= MINIMO_M2:
            itens[n] = _item(p, origem, desde_rev)
    return itens


def montar_normal(vigentes, escopo, talhoes, buffers, ajuste, nova_rev) -> dict:
    base = _base(talhoes)
    if escopo is None:                                   # CLI / pedido antigo: fazenda inteira pelo sistema
        escopo = {'incluir': [{'talhao': n, 'fonte': 'sistema'} for n in base], 'remover': []}
    incluir = escopo.get('incluir') or []
    remover = {int(x) for x in escopo.get('remover') or []}
    faltando = sorted(int(i['talhao']) for i in incluir if int(i['talhao']) not in base)
    if faltando:
        raise ErroGeracao(f"Talhões que não existem na Base de hoje: {', '.join(map(str, faltando))}.")
    itens = {k: v for k, v in vigentes.items() if k not in remover}
    shape = unary_union([make_valid(g) for g in ajuste]) if ajuste else None
    vazios = []
    for i in incluir:
        n, fonte = int(i['talhao']), i.get('fonte', 'sistema')
        if fonte == 'shape':
            if shape is None:
                raise ErroGeracao('Há talhões em "subir shape", mas nenhum shape de ajuste foi enviado.')
            p = so_poligonos(make_valid(shape.intersection(base[n])))
        else:
            p = so_poligonos(make_valid(base[n].difference(buffers)))
        if p.area < MINIMO_M2:
            vazios.append(n)
            continue
        itens[n] = _item(p, fonte, nova_rev)
    if vazios:
        raise ErroGeracao('Sem área de aplicação nos talhões ' + ', '.join(map(str, sorted(vazios)))
                          + ' (o shape enviado não cobre o talhão, ou os obstáculos tomam o talhão inteiro).')
    if not itens:
        raise ErroGeracao('A área de aplicação ficou vazia: o projeto ficaria sem nenhum talhão.')
    return itens


def uniao(itens):
    return so_poligonos(make_valid(unary_union([v['geom'] for v in itens.values()])))


def cobertura(itens, talhoes) -> float:
    base = _base(talhoes)
    total = sum(g.area for g in base.values())
    coberta = sum(g.area for n, g in base.items() if n in itens)
    return 100 * coberta / total if total else 0.0


def fora_da_base(itens, talhoes) -> list:
    return sorted(set(itens) - set(_base(talhoes)))


def itens_para_json(itens) -> list:
    return [{'talhao': n, 'wkt': v['geom'].wkt, 'area_ha': round(v['area_ha'], 4),
             'origem': v['origem'], 'desde_rev': v['desde_rev']} for n, v in sorted(itens.items())]
```

- [ ] **Passo 4:** `python -m pytest tests/drone/test_montagem.py -v` → 9 passed.

- [ ] **Passo 5: Commit**

```bash
git add drone/montagem.py tests/drone/test_montagem.py
git commit -m "Drone Parte 2: montagem da Normal por talhão"
```

---

### Tarefa 4: Gerador e banco por talhão (e linha "Incompleta" no PDF)

**Arquivos:**
- Modificar: `drone/gerador.py` (função `processar`), `drone/banco.py` (métodos novos), `drone/mapa_pdf.py` (`DadosMapa`, `_carimbo`), `drone/cli.py` (`gerar` passa escopo nulo)
- Testar: `tests/drone/test_gerador.py`, `tests/drone/test_mapa_pdf.py`

**Interfaces:**
- Consome: `montar_normal`, `dividir_por_talhao`, `uniao`, `cobertura`, `fora_da_base`, `itens_para_json` (Tarefa 3); `geometria.resumir`; RPCs `drone_talhoes_vigentes`, `drone_gravar_geracao_talhoes`, `drone_ajuste_wkt` (Tarefa 1).
- Produz:
  - `DroneBanco.talhoes_vigentes(cod_faz, documento) -> tuple[dict[int, item], str | None]` (itens e `criado_em` da revisão vigente)
  - `DroneBanco.gravar_geracao_talhoes(geracao_id, itens) -> None`
  - `DroneBanco.ajuste(envio_id) -> list[BaseGeometry]`
  - `DadosMapa.cobertura_pct: float | None = None`
  - `mapa_pdf.linha_incompleta(d) -> str | None`
  - `processar` grava os talhões da geração e devolve `resumo['cobertura_pct']`.

- [ ] **Passo 1: Testes que falham.** Em `tests/drone/test_gerador.py`, substitua a classe `BancoFalso` e acrescente os testes abaixo. Os testes antigos continuam, porque escopo nulo significa fazenda inteira:

```python
class BancoFalso:
    def __init__(self, tipo='normal', obstaculos=None, infestacao=None, vigentes=None, ajuste=None):
        self.tipo, self.obst, self.infest, self.previas = tipo, obstaculos or {}, infestacao, []
        self.vigentes, self.ajuste_geoms, self.gravados = vigentes or {}, ajuste or [], None

    def parametros(self):
        return {'taxa_l_ha': '10', 'agrupar_infestacao_m': '20', 'folga_infestacao_m': '5',
                'alerta_aproveitamento_min': '0.30', 'alerta_obstaculos_meses': '24'}

    def distancias(self):
        return {15: 15.0, 25: 25.0, 50: 50.0}

    def solicitacao(self, id_):
        return {'id': id_, 'cod_faz': 10156, 'tipo': self.tipo}

    def fazenda(self, cod):
        return {'cod_faz': cod, 'nome': 'POSSES'}

    def obstaculos_vigentes(self, cod):
        versoes = [{'classe_m': c, 'versao_id': c, 'enviado_em': '2023-01-01T00:00:00+00:00'} for c in self.obst]
        return self.obst, versoes

    def infestacao(self, id_):
        return self.infest

    def proximo_numero(self, cod_faz, documento):
        return 2

    def talhoes_vigentes(self, cod_faz, documento):
        return self.vigentes, '2024-01-01T00:00:00+00:00'

    def ajuste(self, envio_id):
        return self.ajuste_geoms

    def gravar_geracao_talhoes(self, geracao_id, itens):
        self.gravados = itens

    def subir_previa(self, caminho, destino):
        self.previas.append((caminho.name, destino))
        return destino


def test_normal_incorpora_talhao_e_copia_o_vigente(base, tmp_path):
    from drone.montagem import dividir_por_talhao
    import geopandas as gpd
    t = gpd.GeoDataFrame({'TALHAO': [1, 2]}, geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)], crs=31983)
    vig = dividir_por_talhao(box(0, 0, 100, 100), t, 'legado', 0)            # só o talhão 1 tem projeto
    b = BancoFalso(vigentes=vig)
    g = {'id': 7, 'solicitacao_id': 9, 'infestacao_id': None,
         'escopo': {'incluir': [{'talhao': 2, 'fonte': 'sistema'}], 'remover': []}}
    r = processar(g, b, base, tmp_path / 'w', datetime.date(2026, 10, 8))
    assert sorted(b.gravados) == [1, 2]
    assert b.gravados[1]['origem'] == 'legado' and b.gravados[2]['desde_rev'] == 2
    assert r['resumo']['cobertura_pct'] == pytest.approx(100)


def test_normal_incompleta_vira_alerta(base, tmp_path):
    b = BancoFalso()
    g = {'id': 8, 'solicitacao_id': 9, 'infestacao_id': None,
         'escopo': {'incluir': [{'talhao': 1, 'fonte': 'sistema'}], 'remover': []}}
    r = processar(g, b, base, tmp_path / 'w', datetime.date(2026, 10, 8))
    assert r['resumo']['cobertura_pct'] == pytest.approx(50)
    assert any('incompleta' in a.lower() for a in r['alertas'])


def test_catacao_grava_talhoes_sem_herdar_a_anterior(base, tmp_path):
    from drone.montagem import dividir_por_talhao
    import geopandas as gpd
    t = gpd.GeoDataFrame({'TALHAO': [1, 2]}, geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)], crs=31983)
    b = BancoFalso('catacao', infestacao=[box(40, 40, 50, 50)],
                   vigentes=dividir_por_talhao(box(100, 0, 200, 100), t, 'legado', 0))
    processar({'id': 9, 'solicitacao_id': 9, 'infestacao_id': 1}, b, base, tmp_path / 'w', datetime.date(2026, 10, 8))
    assert sorted(b.gravados) == [1]                                           # talhão 2 da anterior não vem
```

Em `tests/drone/test_mapa_pdf.py`, acrescente:
```python
def test_linha_incompleta():
    from drone.mapa_pdf import linha_incompleta
    t = _talhoes(1000, 500)
    d = DadosMapa(cod_faz=1, nome='X', tipo='normal', revisao=1, talhoes=t,
                  recorte=recortar(t, uniao_buffers({}, {})), gerado_em=datetime.date(2026, 10, 8))
    assert linha_incompleta(d) is None
    d.cobertura_pct = 31.4
    assert linha_incompleta(d) == 'Incompleta · 31% da fazenda'
    d.cobertura_pct = 100.0
    assert linha_incompleta(d) is None
```

- [ ] **Passo 2:** `python -m pytest tests/drone/test_gerador.py tests/drone/test_mapa_pdf.py -v` → FALHA (os testes novos: `AttributeError`/`ImportError`).

- [ ] **Passo 3: Implementar.**

**`drone/mapa_pdf.py`**:
- em `DadosMapa`, depois de `safra`, acrescente `cobertura_pct: float | None = None`;
- acrescente a função:
```python
def linha_incompleta(d: 'DadosMapa'):
    if d.tipo != 'normal' or d.cobertura_pct is None or d.cobertura_pct >= 99.95:
        return None
    return f'Incompleta · {d.cobertura_pct:.0f}% da fazenda'
```
- em `_carimbo`, logo depois de `pg.texto(x + 3, y + 11.5, 'MAPA DE APLICAÇÃO · DRONE', 5.5, CINZA)`, acrescente:
```python
    aviso = linha_incompleta(d)
    if aviso:
        pg.texto(x + w, y + 11.5, aviso, 5.5, '#d4890a', 'bold', ha='right')
```

**`drone/banco.py`**: acrescente, depois de `proximo_numero`:
```python
    def talhoes_vigentes(self, cod_faz, documento):
        linhas = self.rpc('drone_talhoes_vigentes', {'p_cod_faz': cod_faz, 'p_documento': documento}) or []
        itens = {l['talhao_num']: {'geom': shapely_wkt.loads(l['wkt']), 'area_ha': float(l['area_ha']),
                                   'origem': l['origem'], 'desde_rev': l['desde_rev']} for l in linhas}
        return itens, (linhas[0]['revisao_em'] if linhas else None)

    def gravar_geracao_talhoes(self, geracao_id, itens):
        from drone.montagem import itens_para_json
        self.rpc('drone_gravar_geracao_talhoes', {'p_geracao_id': geracao_id, 'p_talhoes': itens_para_json(itens)})

    def ajuste(self, envio_id) -> list:
        return [shapely_wkt.loads(l['wkt']) for l in self.rpc('drone_ajuste_wkt', {'p_envio_id': envio_id}) or []]
```

**`drone/gerador.py`**: troque os imports e o miolo de `processar` (de `infest, agrupar, folga, fora = …` até o `return`) por:
```python
from drone.geometria import blocos_catacao, recortar, resumir, uniao_buffers
from drone.montagem import cobertura, dividir_por_talhao, fora_da_base, montar_normal, uniao
```
```python
    revisao = banco.proximo_numero(cod, tipo)   # só leitura: o projeto nasce na publicação
    buffers = uniao_buffers(obst, distancias)
    extras, cob, fora = [], None, False
    agrupar = float(params.get('agrupar_infestacao_m', 20))
    folga = float(params.get('folga_infestacao_m', 5))
    if tipo == 'normal':
        vigentes, revisao_em = banco.talhoes_vigentes(cod, 'normal')
        escopo = geracao.get('escopo')
        envios = {i.get('envio_id') for i in (escopo or {}).get('incluir', []) if i.get('fonte') == 'shape'}
        ajuste = [g for e in envios if e for g in banco.ajuste(e)]
        itens = montar_normal(vigentes, escopo, talhoes, buffers, ajuste, revisao)
        recorte = resumir(talhoes, uniao(itens))
        cob = cobertura(itens, talhoes)
        if cob < 99.95:
            extras.append(f'Normal incompleta: {cob:.0f}% da fazenda tem projeto.')
        if fora_da_base(itens, talhoes):
            extras.append('Talhões fora da Base que continuam no projeto: '
                          + ', '.join(map(str, fora_da_base(itens, talhoes))) + '.')
        refeitos = {int(i['talhao']) for i in (escopo or {}).get('incluir', [])} if escopo else set(itens)
        copiados = set(itens) - refeitos
        if revisao_em and copiados and any(v['enviado_em'] > revisao_em for v in versoes):
            extras.append(f'Obstáculos atualizados depois da revisão vigente: {len(copiados)} talhões '
                          'copiados não foram refeitos.')
    else:
        if not geracao.get('infestacao_id'):
            raise ErroGeracao('Catação sem shape de infestação: envie a infestação antes de gerar.')
        infest = banco.infestacao(geracao['infestacao_id'])
        fora = not blocos_catacao(infest, agrupar, folga).difference(unary_union(list(talhoes.geometry))).is_empty
        recorte = recortar(talhoes, buffers, infestacao=infest, agrupar=agrupar, folga=folga)
        itens = dividir_por_talhao(recorte.area, talhoes, 'sistema', revisao)
    banco.gravar_geracao_talhoes(geracao['id'], itens)

    saida = Path(pasta) / f"geracao-{geracao['id']}"
    shp = gravar_aplicacao(recorte.area, int(params['taxa_l_ha']), saida / 'shape', cod)
    zip_ = montar_zip(shp, saida / f'{cod}.zip')
    pdf = saida / f'{cod}.pdf'
    orient = gerar_pdf(DadosMapa(cod, faz['nome'], tipo, revisao, talhoes, recorte, hoje, cobertura_pct=cob), pdf)

    destino = f"geracao-{geracao['id']}"
    return {
        'status': 'pronta',
        'orientacao': orient,
        'insumos': {'distancias': distancias, 'taxa_l_ha': params['taxa_l_ha'], 'agrupar_infestacao_m': agrupar,
                    'folga_infestacao_m': folga, 'base_talhoes': Path(arquivo_base).name,
                    'data_base': data_base.isoformat(), 'obstaculos': [v['versao_id'] for v in versoes],
                    'infestacao_id': geracao.get('infestacao_id'), 'escopo': geracao.get('escopo'),
                    'revisao_prevista': revisao},
        'resumo': {'por_talhao': recorte.por_talhao, 'area_total_ha': recorte.area_total_ha,
                   'aplicacao_ha': recorte.aplicacao_ha, 'cobertura_pct': cob},
        'alertas': alertas(recorte, versoes, params, hoje, fora) + extras,
        'previa_zip': banco.subir_previa(zip_, f'{destino}/{cod}.zip'),
        'previa_pdf': banco.subir_previa(pdf, f'{destino}/{cod}.pdf'),
    }
```
(remova a linha antiga `recorte = recortar(...)` e a antiga `revisao = banco.proximo_numero(...)`, que ficaram duplicadas).

**`drone/cli.py`**: no comando `gerar`, a chamada continua `b.pedir_geracao(sol['id'], inf)`. Com o escopo nulo, a Normal é gerada para a fazenda inteira e nada muda.

- [ ] **Passo 4:** `python -m pytest tests/drone -q` → todos passam (os 74 de antes + 4 novos).

- [ ] **Passo 5: Commit**

```bash
git add drone/gerador.py drone/banco.py drone/mapa_pdf.py tests/drone/test_gerador.py tests/drone/test_mapa_pdf.py
git commit -m "Drone Parte 2: gerador monta a Normal por talhão e grava os talhões da geração"
```

---

### Tarefa 5: Publicação com talhões (agente e legado)

**Arquivos:**
- Modificar: `drone/publicacao.py` (`publicar`), `drone/banco.py` (`publicar_revisao`)
- Testar: `tests/drone/test_publicacao.py`

**Interfaces:**
- Consome: `drone_publicar(..., p_talhoes)` (Tarefa 1); `itens_para_json` (Tarefa 3).
- Produz:
  - `publicar(banco, gh, cod_faz, documento, motivo, arquivos, numero_esperado=None, geracao_id=None, legado=False, talhoes=None) -> int`, onde `talhoes` é o dict de itens ou `None`;
  - `DroneBanco.publicar_revisao(cod_faz, documento, motivo, numero, arquivos, geracao_id=None, legado=False, talhoes=None) -> int`, onde `talhoes` é a lista JSON.

- [ ] **Passo 1: Teste que falha** (acrescente em `tests/drone/test_publicacao.py`; o `_BancoFalso.publicar_revisao` precisa aceitar e guardar `talhoes`):

No `_BancoFalso`, troque a assinatura e guarde o parâmetro:
```python
    def publicar_revisao(self, cod_faz, documento, motivo, numero, arquivos, geracao_id=None, legado=False,
                         talhoes=None):
        if numero != len(self.revisoes):
            raise RuntimeError('número da revisão mudou')
        if numero > 0 and not motivo:
            raise RuntimeError('motivo obrigatório')
        rev = {'id': 11 + numero, 'numero': numero, 'motivo': motivo, 'geracao_id': geracao_id, 'legado': legado,
               'arquivos': [a['nome'] for a in arquivos], 'talhoes': talhoes}
        self.revisoes.append(rev)
        return rev['id']
```
E o teste:
```python
def test_legado_publica_com_os_talhoes(tmp_path):
    from shapely.geometry import box
    b = _BancoFalso()
    itens = {1: {'geom': box(0, 0, 10, 10), 'area_ha': 0.01, 'origem': 'legado', 'desde_rev': 0}}
    publicar(b, _GhFalso(), 10156, 'normal', 'Importado do legado', _arquivos(tmp_path), legado=True, talhoes=itens)
    t = b.revisoes[0]['talhoes']
    assert t[0]['talhao'] == 1 and t[0]['origem'] == 'legado' and t[0]['wkt'].startswith('POLYGON')
```

- [ ] **Passo 2:** `python -m pytest tests/drone/test_publicacao.py -v` → FALHA (`TypeError: unexpected keyword 'talhoes'`).

- [ ] **Passo 3: Implementar**

Em `drone/publicacao.py`, troque a assinatura e a última linha de `publicar`:
```python
def publicar(banco, gh, cod_faz, documento, motivo, arquivos: dict, numero_esperado=None,
             geracao_id=None, legado=False, talhoes=None) -> int:
```
```python
    from drone.montagem import itens_para_json
    return banco.publicar_revisao(cod_faz, documento, motivo, numero, enviados, geracao_id, legado,
                                  itens_para_json(talhoes) if talhoes else None)
```
Em `drone/banco.py`, `publicar_revisao`:
```python
    def publicar_revisao(self, cod_faz, documento, motivo, numero, arquivos, geracao_id=None, legado=False,
                         talhoes=None) -> int:
        """Revisão + arquivos + talhões + conclusão da geração/solicitação numa transação (hub.drone_publicar)."""
        return self.rpc('drone_publicar', {
            'p_cod_faz': cod_faz, 'p_documento': documento, 'p_motivo': motivo, 'p_numero': numero,
            'p_arquivos': arquivos, 'p_geracao_id': geracao_id, 'p_legado': legado, 'p_talhoes': talhoes})
```
(O `itens_para_json` usa `geom.wkt`. Um `Polygon` simples sai como `POLYGON(...)`, e o SQL faz `ST_Multi`. Os dois servem.)

- [ ] **Passo 4:** `python -m pytest tests/drone -q` → tudo passa.

- [ ] **Passo 5: Commit**

```bash
git add drone/publicacao.py drone/banco.py tests/drone/test_publicacao.py
git commit -m "Drone Parte 2: publicação grava os talhões da revisão"
```

---

### Tarefa 6: Envios feitos pelo Hub (agente)

**Arquivos:**
- Criar: `drone/envios.py`, `tests/drone/test_envios.py`
- Modificar: `drone/banco.py`, `drone/agente.py`

**Interfaces:**
- Consome: `drone_pegar_envio`, `drone_concluir_envio`, `drone_gravar_ajuste` (Tarefa 1); `insumos.ler_shapefile`, `insumos.classe_pelo_nome`.
- Produz:
  - `envios.shapefiles(arquivos: list[Path], pasta: Path) -> list[Path]`
  - `envios.processar_envio(envio: dict, banco, pasta: Path) -> str` (resumo em português; lança `ErroGeracao`)
  - `agente.processar_um_envio(banco) -> bool`
  - **banco:**
    - `pegar_envio() -> dict | None`
    - `concluir_envio(id, status, erro=None)`
    - `baixar_envio(caminho, local) -> Path`
    - `gravar_ajuste(envio_id, geoms)`
    - `gravar_obstaculos(..., usuario=None)`
    - `gravar_infestacao(..., usuario=None)`

- [ ] **Passo 1: Testes que falham**

`tests/drone/test_envios.py`:
```python
import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from drone.envios import processar_envio, shapefiles
from drone.erros import ErroGeracao


def _shp(pasta, nome, geoms, crs=31983):
    pasta.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame({'id': range(len(geoms))}, geometry=geoms, crs=crs).to_file(pasta / nome)
    return pasta / nome


def test_acha_shp_dentro_de_zip_com_pastas(tmp_path):
    src = _shp(tmp_path / 'src', 'restricoes15m.shp', [Point(200000, 7550000)])
    z = tmp_path / 'envio.zip'
    with zipfile.ZipFile(z, 'w') as f:
        for p in src.parent.iterdir():
            f.write(p, f'pasta/sub/{p.name}')
    achados = shapefiles([z], tmp_path / 'x')
    assert [p.name for p in achados] == ['restricoes15m.shp']


class _Banco:
    def __init__(self, pasta_origem):
        self.origem, self.gravados = pasta_origem, []

    def baixar_envio(self, caminho, local):
        import shutil
        local.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.origem / caminho.split('/')[-1], local)
        return local

    def gravar_obstaculos(self, cod, classe, origem, arquivo, geoms, usuario=None):
        self.gravados.append(('obst', cod, classe, len(geoms)))

    def gravar_infestacao(self, sol, empresa, arquivo, geoms, usuario=None):
        self.gravados.append(('inf', sol, len(geoms)))

    def gravar_ajuste(self, envio_id, geoms):
        self.gravados.append(('aj', envio_id, len(geoms)))


def _envio(tmp_path, tipo, nomes, classe=None, sol=None):
    return {'id': 5, 'cod_faz': 10156, 'tipo': tipo, 'classe_m': classe, 'solicitacao_id': sol,
            'arquivos': [f'10156/1/{n}' for n in nomes], 'enviado_por': None}


def _partes(p):
    return [p.with_suffix(e).name for e in ('.shp', '.shx', '.dbf', '.prj', '.cpg') if p.with_suffix(e).exists()]


def test_obstaculos_classe_pelo_nome_e_junta_arquivos_da_mesma_classe(tmp_path):
    o = tmp_path / 'o'
    a = _shp(o, 'arvores15m.shp', [Point(200000, 7550000)])
    b = _shp(o, 'restricoes15m.shp', [Point(200010, 7550000), Point(200020, 7550000)])
    banco = _Banco(o)
    processar_envio(_envio(tmp_path, 'obstaculos', _partes(a) + _partes(b)), banco, tmp_path / 'w')
    assert banco.gravados == [('obst', 10156, 15, 3)]


def test_obstaculo_sem_classe_no_nome_pede_para_escolher(tmp_path):
    o = tmp_path / 'o'
    a = _shp(o, 'arvores.shp', [Point(200000, 7550000)])
    with pytest.raises(ErroGeracao, match='escolha a classe'):
        processar_envio(_envio(tmp_path, 'obstaculos', _partes(a)), _Banco(o), tmp_path / 'w')


def test_infestacao_e_ajuste(tmp_path):
    o = tmp_path / 'o'
    a = _shp(o, 'mamona.shp', [box(200000, 7550000, 200010, 7550010)])
    b = _shp(o, 'ajuste.shp', [box(200000, 7550000, 200100, 7550100)])
    banco = _Banco(o)
    processar_envio(_envio(tmp_path, 'infestacao', _partes(a), sol=3), banco, tmp_path / 'w1')
    processar_envio(_envio(tmp_path, 'ajuste', _partes(b)), banco, tmp_path / 'w2')
    assert banco.gravados == [('inf', 3, 1), ('aj', 5, 1)]


def test_envio_sem_shp_da_erro(tmp_path):
    o = tmp_path / 'o'
    o.mkdir()
    (o / 'leia.txt').write_text('x')
    with pytest.raises(ErroGeracao, match=r'\.shp'):
        processar_envio(_envio(tmp_path, 'ajuste', ['leia.txt']), _Banco(o), tmp_path / 'w')
```

- [ ] **Passo 2:** `python -m pytest tests/drone/test_envios.py -v` → FALHA (`ModuleNotFoundError: drone.envios`).

- [ ] **Passo 3: Implementar**

`drone/envios.py`:
```python
"""Envios de arquivo feitos pelo Hub (obstáculos, infestação, shape de ajuste): o navegador sobe no
Storage `drone-envios` e registra; aqui o agente baixa, valida, reprojeta e grava (spec Parte 2, §3.3)."""
import zipfile
from pathlib import Path

from drone.erros import ErroGeracao
from drone.insumos import classe_pelo_nome, ler_shapefile


def shapefiles(arquivos: list, pasta: Path) -> list:
    pasta = Path(pasta)
    for a in arquivos:
        a = Path(a)
        if a.suffix.lower() == '.zip':
            with zipfile.ZipFile(a) as z:
                z.extractall(pasta / a.stem)
    candidatos = [Path(a) for a in arquivos] + list(pasta.rglob('*'))
    return sorted({p.resolve() for p in candidatos if p.suffix.lower() == '.shp'}, key=lambda p: p.name)


def processar_envio(envio: dict, banco, pasta: Path) -> str:
    pasta = Path(pasta) / f"envio-{envio['id']}"
    locais = [banco.baixar_envio(c, pasta / 'arquivos' / c.split('/')[-1]) for c in envio['arquivos']]
    shps = shapefiles(locais, pasta / 'extraidos')
    if not shps:
        raise ErroGeracao('Nenhum shapefile (.shp) no envio. Envie o .shp com .shx, .dbf e .prj, ou um .zip.')
    lidos = []
    for shp in shps:                                     # valida tudo antes de gravar qualquer coisa
        geoms = ler_shapefile(shp)
        if not geoms:
            raise ErroGeracao(f'{shp.name} não tem nenhuma feição.')
        lidos.append((shp, geoms))
    cod, usuario, tipo = envio['cod_faz'], envio.get('enviado_por'), envio['tipo']
    if tipo == 'obstaculos':
        por_classe = {}
        for shp, geoms in lidos:
            classe = envio.get('classe_m') or classe_pelo_nome(shp.name)
            if classe is None:
                raise ErroGeracao(f'{shp.name}: não deu para saber a classe (15, 25 ou 50 m) pelo nome; '
                                  'escolha a classe no envio.')
            nomes, gs = por_classe.setdefault(classe, ([], []))
            nomes.append(shp.name)
            gs.extend(geoms)
        for classe, (nomes, gs) in sorted(por_classe.items()):
            banco.gravar_obstaculos(cod, classe, 'upload', ' + '.join(nomes), gs, usuario=usuario)
        return 'obstáculos: ' + ', '.join(f'{c} m ({len(g)} feições)' for c, (_, g) in sorted(por_classe.items()))
    geoms = [g for _, gs in lidos for g in gs]
    nomes = ' + '.join(shp.name for shp, _ in lidos)
    if tipo == 'infestacao':
        banco.gravar_infestacao(envio['solicitacao_id'], None, nomes, geoms, usuario=usuario)
        return f'infestação: {len(geoms)} feições de {len(lidos)} camada(s)'
    banco.gravar_ajuste(envio['id'], geoms)
    return f'shape de ajuste: {len(geoms)} feições'
```

`drone/banco.py`:
- em `gravar_obstaculos`, acrescente `usuario=None` à assinatura e `'p_usuario': usuario` ao dicionário do rpc;
- faça o mesmo em `gravar_infestacao`;
- acrescente os métodos:
```python
    def pegar_envio(self):
        r = self.rpc('drone_pegar_envio')
        return r[0] if r else None

    def concluir_envio(self, id_, status, erro=None):
        self.rpc('drone_concluir_envio', {'p_id': id_, 'p_status': status, 'p_erro': erro})

    def gravar_ajuste(self, envio_id, geoms):
        self.rpc('drone_gravar_ajuste', {'p_envio_id': envio_id, 'p_wkts': [g.wkt for g in geoms]})

    def baixar_envio(self, caminho: str, local: Path) -> Path:
        r = requests.get(f'{self.storage}/object/drone-envios/{caminho}', headers=self._storage_headers(), timeout=120)
        self._checar(r, 'storage')
        Path(local).parent.mkdir(parents=True, exist_ok=True)
        Path(local).write_bytes(r.content)
        return Path(local)
```

`drone/agente.py`: acrescente `from drone.envios import processar_envio` e a função:
```python
def processar_um_envio(banco) -> bool:
    e = banco.pegar_envio()
    if not e:
        return False
    _log(f"envio {e['id']} ({e['tipo']}, fazenda {e['cod_faz']})")
    try:
        _log('  ' + processar_envio(e, banco, PASTA_TRABALHO))
        banco.concluir_envio(e['id'], 'ok')
    except ErroGeracao as erro:
        banco.concluir_envio(e['id'], 'erro', str(erro))
        _log(f'  erro: {erro}')
    except Exception as erro:
        banco.concluir_envio(e['id'], 'erro', f'Erro interno ao ler o envio: {erro}')
        _log(traceback.format_exc())
    return True
```
e, em `ciclo`, troque `trabalhou = gerar_uma(banco, c)` por:
```python
    trabalhou = processar_um_envio(banco)
    trabalhou = gerar_uma(banco, c) or trabalhou
```

- [ ] **Passo 4:** `python -m pytest tests/drone -q` → tudo passa.

- [ ] **Passo 5: Commit**

```bash
git add drone/envios.py drone/banco.py drone/agente.py tests/drone/test_envios.py
git commit -m "Drone Parte 2: agente processa os envios feitos pelo Hub"
```

---

### Tarefa 7: Migração dos dados atuais

**Arquivos:**
- Criar: `drone/migrar_parte2.py`, `tests/drone/test_migrar_parte2.py`
- Modificar: `drone/revisar_legado.py` (Catação = só o último levantamento; publica com talhões)
- Testar: `tests/drone/test_revisar_legado.py`

**Interfaces:**
- Consome: `dividir_por_talhao` (Tarefa 3); `drone_gravar_revisao_talhoes` (Tarefa 1); `publicar(..., talhoes=)` (Tarefa 5); `talhoes_da_fazenda`.
- Produz:
  - `revisar_legado.precisa_refazer(usados, publicado, publicado_existe, ja_consolidado=False, tipo='normal', motivo='') -> bool`
  - `migrar_parte2.origem_da_revisao(motivo: str | None) -> str`
  - `python -m drone.migrar_parte2 [--simular]`

- [ ] **Passo 1: Testes que falham**

`tests/drone/test_migrar_parte2.py`:
```python
from drone.migrar_parte2 import origem_da_revisao


def test_origem_da_revisao():
    assert origem_da_revisao('Importado do legado (consolidado: 24/25 Rev1)') == 'legado'
    assert origem_da_revisao('Novo levantamento de infestação') == 'sistema'
    assert origem_da_revisao(None) == 'sistema'
```
Em `tests/drone/test_revisar_legado.py`, acrescente:
```python
def test_catacao_consolidada_volta_ao_ultimo_levantamento():
    m = 'Importado do legado (consolidado: 24/25 Rev0, 24/25 Rev4, 26/27 Rev3)'
    assert precisa_refazer(usados={4}, publicado=4, publicado_existe=True, ja_consolidado=True,
                           tipo='catacao', motivo=m)
    m2 = 'Importado do legado (último levantamento: 26/27 Rev3)'
    assert not precisa_refazer(usados={4}, publicado=4, publicado_existe=True, ja_consolidado=False,
                               tipo='catacao', motivo=m2)
```

- [ ] **Passo 2:** `python -m pytest tests/drone/test_migrar_parte2.py tests/drone/test_revisar_legado.py -v` → FALHA.

- [ ] **Passo 3: Implementar**

**`drone/revisar_legado.py`:**
- troque `precisa_refazer` por:
```python
def precisa_refazer(usados: set, publicado: int, publicado_existe: bool, ja_consolidado: bool = False,
                    tipo: str = 'normal', motivo: str = '') -> bool:
    if not publicado_existe:
        return True
    if tipo == 'catacao':                                # Catação = só o último levantamento (Parte 2)
        return 'último levantamento' not in (motivo or '') and ', ' in (motivo or '')
    return not ja_consolidado and usados != {publicado}
```
- no laço de `main`, no tipo `catacao`, use só o projeto mais recente. Logo depois de `todos = sorted(...)`, acrescente:
```python
                if tipo == 'catacao':
                    todos = todos[-1:]                   # só o levantamento mais recente
```
- na chamada de `precisa_refazer`, passe `tipo=tipo, motivo=revs[0]['motivo'] if revs else ''`;
- na publicação, gere os talhões e ajuste o motivo:
```python
                        itens = dividir_por_talhao(area, talhoes, 'legado', 0)
                        motivo = (f'{MOTIVO} (último levantamento: {fontes})' if tipo == 'catacao'
                                  else f'{MOTIVO} (consolidado: {fontes})')
                        publicar(banco, gh, cod, tipo, motivo, {'zip': zip_, 'pdf': pdf},
                                 numero_esperado=0, legado=True, talhoes=itens)
```
(e acrescente `from drone.montagem import dividir_por_talhao` aos imports).

**`drone/migrar_parte2.py`:**
```python
"""Carga única da Parte 2: grava os talhões (drone_revisao_talhoes) de cada revisão vigente do Drone,
recortando o .zip publicado pelos talhões da Base de hoje. Não republica nada.
Uso: python -m drone.migrar_parte2 [--simular]
Depois: python -m drone.revisar_legado   (Catações consolidadas voltam ao último levantamento)"""
import io
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import requests
from shapely.ops import unary_union

from drone.banco import DroneBanco
from drone.base_talhoes import arquivo_mais_recente, talhoes_da_fazenda
from drone.config import CRS_TRABALHO, PASTA_TRABALHO, cfg
from drone.geometria import so_poligonos
from drone.montagem import dividir_por_talhao, itens_para_json


def origem_da_revisao(motivo) -> str:
    return 'legado' if (motivo or '').startswith('Importado do legado') else 'sistema'


def geometria_publicada(url: str):
    import truststore
    truststore.inject_into_ssl()
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    pasta = PASTA_TRABALHO / 'migrar_parte2'
    pasta.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith('.shp'))
        z.extractall(pasta)
    g = gpd.read_file(pasta / nome).to_crs(CRS_TRABALHO)
    return so_poligonos(unary_union(list(g.geometry)))


def main():
    simular = '--simular' in sys.argv
    sys.stdout.reconfigure(encoding='utf-8')
    c = cfg()
    _, base = arquivo_mais_recente(c['base_talhoes_pasta'], c['base_talhoes_padrao'])
    banco = DroneBanco()
    vigentes = banco.selecionar('arquivos_vigentes', 'cod_faz,documento,revisao_id,nome_arquivo,release_url',
                                {'modulo_id': 'eq.drone', 'nome_arquivo': 'like.*.zip'})
    feitos = {r['revisao_id'] for r in banco.selecionar('drone_revisao_talhoes', 'revisao_id')}
    motivos = {r['id']: r['motivo'] for r in banco.selecionar('projeto_revisoes', 'id,motivo',
                                                              {'id': f"in.({','.join(str(v['revisao_id']) for v in vigentes)})"})} if vigentes else {}
    ok = erros = pulados = 0
    for n, v in enumerate(sorted(vigentes, key=lambda x: (x['cod_faz'], x['documento'])), 1):
        if v['revisao_id'] in feitos:
            pulados += 1
            continue
        try:
            talhoes = talhoes_da_fazenda(base, v['cod_faz'])
            area = geometria_publicada(v['release_url'])
            numero = int(v['nome_arquivo'].split('_Rev')[1].split('-')[0])
            itens = dividir_por_talhao(area, talhoes, origem_da_revisao(motivos.get(v['revisao_id'])), numero)
            if not simular:
                banco.rpc('drone_gravar_revisao_talhoes', {'p_revisao_id': v['revisao_id'],
                                                           'p_talhoes': itens_para_json(itens)})
            ok += 1
            print(f"[{n}/{len(vigentes)}] {v['cod_faz']} {v['documento']}: {len(itens)} talhões", flush=True)
        except Exception as e:
            erros += 1
            print(f"[{n}/{len(vigentes)}] {v['cod_faz']} {v['documento']}: ERRO {e}", flush=True)
    print(f'ok {ok} | erro {erros} | já tinham {pulados}' + ('  (SIMULAÇÃO — nada gravado)' if simular else ''))


if __name__ == '__main__':
    main()
```

- [ ] **Passo 4:** `python -m pytest tests/drone -q` → tudo passa.

- [ ] **Passo 5: Simular e rodar** (com as Tarefas 1 e 2 aplicadas):
  1. `python -m drone.migrar_parte2 --simular` → esperado: cerca de 650 linhas `ok`, nenhum erro (ou poucos, explicados no log).
  2. Mostre o resumo ao usuário e rode `python -m drone.migrar_parte2`.
  3. `python -m drone.revisar_legado --simular` → esperado: cerca de 26 Catações como `substituir`, e o resto `igual`. Mostre ao usuário e rode sem `--simular`.
  4. Conferência: `select count(distinct revisao_id) from hub.drone_revisao_talhoes;` deve ser igual ao número de revisões vigentes do drone.

- [ ] **Passo 6: Commit**

```bash
git add drone/migrar_parte2.py drone/revisar_legado.py tests/drone/test_migrar_parte2.py tests/drone/test_revisar_legado.py
git commit -m "Drone Parte 2: migração (talhões das revisões vigentes; Catação = último levantamento)"
```

---

### Tarefa 8: Tela do Drone — fila, fazenda e mapa (leitura)

**Arquivos:**
- Criar: `app/drone.js`
- Modificar: `app/index.html` (menu, view, `LABELS`/`MOD_AC`, permissões, `trocar`, scripts)

**Interfaces:**
- Consome: `drone_painel()`, `drone_mapa_fazenda(cod)` (Tarefa 1); as globais do `index.html` (`sb`, `EU`, `esc`, `fmtNum`, `podeEditar`, `WORKER_URL`).
- Produz (globais em `drone.js`, usadas na Tarefa 9):
  - `DR` — estado: `{painel, cod, geo, mapa, sel: Map<int,'sistema'|'shape'>, rem: Set<int>, modoRemover, doc, ajusteId, poll}`
  - `droneIniciar()`, `drCarregarPainel()`, `drAbrirFazenda(cod)`, `drRender()`, `drPintarMapa()`

- [ ] **Passo 1: Ganchos no `app/index.html`**
  - **Scripts:** depois de `<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>` (linha 568), acrescente:
    ```html
    <link href="https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
    ```
    e, logo antes de `</body>`, `<script src="drone.js"></script>`.
  - **Menu:** troque o botão `<button class="ni dim"><span class="ico ni-ico">flight</span><span class="ni-lbl">Drones<span class="soon">em breve</span></span></button>` por:
    ```html
    <button class="ni" onclick="trocar('drone',this)"><span class="ico ni-ico">flight</span><span class="ni-lbl">Drone</span></button>
    ```
  - **View:** depois do bloco `<div id="v-preparo" class="view">…</div>`, acrescente `<div id="v-drone" class="view"><div id="drone-root"></div></div>`.
  - **Rótulo e cor:** em `LABELS` e `MOD_AC` (linhas 1784–1785), acrescente `drone:'Drone'` e `drone:'var(--drones)'`.
  - **Permissões:** em `perms:{…}` (linha ~2327), acrescente `drone:mods.has('drone')||u.admin`. Em `aplicarUsuario`, acrescente `['drone','drone']` à lista do `for`. Se `ROLE_LABELS` não tiver `solicitante`, acrescente `solicitante:'Solicitante'`.
  - **Abertura da tela:** em `trocar`, no fim da função, acrescente `if(v==='drone')droneIniciar();`.

- [ ] **Passo 2: Criar `app/drone.js` (parte de leitura)**

```javascript
// Tela do Drone (spec Parte 2, §5): fila de trabalho + fazenda com mapa por talhão.
const DR={painel:null,cod:null,geo:null,mapa:null,sel:new Map(),rem:new Set(),modoRemover:false,
  doc:'normal',ajusteId:null,poll:null,info:null};
const DR_ST={aguardando_obstaculos:'aguardando obstáculos',aguardando_infestacao:'aguardando infestação',
  solicitado:'solicitado',em_elaboracao:'em elaboração',devolvido:'devolvido'};
const DR_COR={normal:'#a0694b',catacao:'#5b8c5a',sel:'#5b6ee8',rem:'#c23b3b',sem:'#e9ebef',fora:'#d4890a'};

function drEstilo(){
  if(document.getElementById('drone-css'))return;
  const s=document.createElement('style');s.id='drone-css';
  s.textContent=`
#drone-root{display:grid;grid-template-columns:330px 1fr;gap:16px}
.dr-grp{background:var(--sf);border-radius:14px;padding:10px;margin-bottom:12px;box-shadow:0 1px 3px #0000000d}
.dr-gh{display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:13px;padding:2px 4px 8px}
.dr-n{background:var(--s2);border-radius:20px;padding:1px 9px;font-size:12px}
.dr-it{display:flex;gap:10px;align-items:center;padding:8px;border-radius:10px;cursor:pointer;font-size:13px}
.dr-it:hover,.dr-it.on{background:#eef0fd}.dr-it.on{outline:1.5px solid var(--drones)}
.dr-it small{display:block;color:var(--t3);font-size:11px}.dr-it .r{margin-left:auto;font-size:11px;color:var(--t3);text-align:right}
.dr-cod{background:#eef0fd;color:var(--drones);font-weight:700;font-size:11px;border-radius:6px;padding:2px 6px}
.dr-pnl{background:var(--sf);border-radius:16px;box-shadow:0 1px 3px #0000000d;overflow:hidden;min-height:560px}
.dr-ph{display:flex;align-items:center;gap:12px;padding:16px 20px;border-bottom:1px solid var(--bd);flex-wrap:wrap}
.dr-ph .nm{font-size:17px;font-weight:600}.dr-ph .sub{color:var(--t3);font-size:12px}
.dr-docs{display:flex;gap:10px;margin-left:auto}
.dr-doc{border:1px solid var(--bd);border-radius:12px;padding:8px 12px;min-width:170px;cursor:pointer;font-size:12px}
.dr-doc.on{border-color:var(--drones);background:#f6f7fe}.dr-doc small{display:block;color:var(--t3);font-size:11px}
.dr-tag{display:inline-block;font-size:10px;font-weight:700;border-radius:6px;padding:1px 6px;margin-left:4px;background:#fdf1df;color:#d4890a}
.dr-body{display:grid;grid-template-columns:1fr 310px}
.dr-map{height:560px;border-right:1px solid var(--bd)}
.dr-leg{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--t2);padding:8px 12px}
.dr-leg i{display:inline-block;width:12px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px;border:1px solid #1f2a30}
.dr-side{padding:14px 16px;display:flex;flex-direction:column;gap:12px;font-size:12px}
.dr-box{border:1px solid var(--bd);border-radius:12px;padding:10px 12px}
.dr-box h3{font-size:12px;font-weight:600;margin-bottom:6px}
.dr-row{display:flex;justify-content:space-between;padding:2px 0}.dr-row span:last-child{color:var(--t3)}
.dr-chips{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0}
.dr-chip{font-size:11px;border-radius:6px;padding:1px 7px;background:#eef0fd;color:var(--drones);font-weight:600}
.dr-chip.r{background:#fbe0e0;color:#c23b3b}
.dr-seg{display:flex;background:var(--s2);border-radius:9px;padding:3px;gap:3px;margin:6px 0}
.dr-seg button{flex:1;border:0;background:none;padding:5px;border-radius:7px;font:inherit;font-size:11.5px;color:var(--t2);cursor:pointer}
.dr-seg button.on{background:#fff;color:var(--drones);font-weight:600;box-shadow:0 1px 2px #0002}
.dr-btn{background:var(--drones);color:#fff;border:0;border-radius:10px;padding:10px;font:inherit;font-weight:600;cursor:pointer;width:100%}
.dr-btn:disabled{opacity:.5;cursor:default}
.dr-btn2{border:1px solid var(--bd);background:#fff;border-radius:10px;padding:8px;font:inherit;color:var(--t2);cursor:pointer;width:100%}
.dr-msg{font-size:11px;color:var(--t3);text-align:center}.dr-err{color:#c23b3b;font-size:12px}
.dr-mot{width:100%;border:1px solid var(--bd);border-radius:8px;padding:7px;font:inherit;font-size:12px}
.dr-prev iframe{width:100%;height:420px;border:1px solid var(--bd);border-radius:10px}
.dr-vazio{display:flex;align-items:center;justify-content:center;height:560px;color:var(--t3)}`;
  document.head.appendChild(s);
}

async function droneIniciar(){
  drEstilo();
  const root=document.getElementById('drone-root');
  if(!root.dataset.pronto){
    root.innerHTML=`<div><div class="search-wrap"><span class="ico search-ico">search</span>
      <input class="search-inp" id="dr-busca" placeholder="Buscar fazenda ou código…" oninput="drBuscar(this.value)"></div>
      <div id="dr-busca-res"></div><div id="dr-fila"></div></div>
      <div class="dr-pnl" id="dr-faz"><div class="dr-vazio">Escolha um item da fila ou busque uma fazenda</div></div>`;
    root.dataset.pronto='1';
  }
  await drCarregarPainel();
}

async function drRpc(nome,args){
  const {data,error}=await sb.rpc(nome,args||{});
  if(error)throw new Error(error.message);
  return data;
}

async function drCarregarPainel(){
  try{DR.painel=await drRpc('drone_painel');}
  catch(e){document.getElementById('dr-fila').innerHTML=`<div class="dr-err">${esc(e.message)}</div>`;return;}
  const s=DR.painel.solicitacoes||[];
  const it=x=>{
    const g=x.geracao||{};
    const st=g.status==='pronta'?(g.publicar_pedido_em?'publicando…':`prévia pronta · ${g.alertas} alertas`)
      :g.status==='fila'||g.status==='processando'?'gerando…':g.status==='erro'?'erro na geração':DR_ST[x.status]||x.status;
    return`<div class="dr-it${DR.cod===x.cod_faz?' on':''}" onclick="drAbrirFazenda(${x.cod_faz},'${x.tipo}')">
      <span class="dr-cod">${x.cod_faz}</span><div>${esc(x.fazenda)}<small>${esc(x.observacao||st)}${x.solicitante?' · '+esc(x.solicitante):''}</small></div>
      <div class="r">${x.data_desejada?'para '+new Date(x.data_desejada+'T12:00').toLocaleDateString('pt-BR'):''}<br>${esc(st)}</div></div>`;
  };
  const grupo=(tit,lista,vazio)=>`<div class="dr-grp"><div class="dr-gh">${tit}<span class="dr-n">${lista.length}</span></div>
    ${lista.length?lista.map(it).join(''):`<div class="dr-msg">${vazio}</div>`}</div>`;
  const normal=s.filter(x=>x.tipo==='normal'&&!(x.geracao&&x.geracao.status==='pronta'));
  const cat=s.filter(x=>x.tipo==='catacao'&&!(x.geracao&&x.geracao.status==='pronta'));
  const prev=s.filter(x=>x.geracao&&x.geracao.status==='pronta');
  const inc=DR.painel.incompletas||[],obs=DR.painel.obstaculos_antigos||[],fora=DR.painel.fora_da_base||[];
  const nova=(podeEditar('drone')||(EU&&EU.role==='solicitante'&&EU.perms.drone))
    ?`<button class="dr-btn2" style="margin-bottom:12px" onclick="drNovaSolicitacao()"><span class="ico">add</span> Nova solicitação</button>`:'';
  document.getElementById('dr-fila').innerHTML=nova
    +grupo('Solicitações Normal',normal,'nenhuma')
    +grupo('Catação · aguardando',cat,'nenhuma')
    +grupo('Prévias para conferir',prev,'nenhuma')
    +`<div class="dr-grp"><div class="dr-gh">Atenção<span class="dr-n">${inc.length+obs.length+fora.length}</span></div>
      <div class="dr-it" onclick="drListarAtencao('incompletas')"><span class="ico" style="color:#d4890a">incomplete_circle</span><div>Normais incompletas<small>${inc.length} fazendas com talhões sem projeto</small></div></div>
      <div class="dr-it" onclick="drListarAtencao('obstaculos_antigos')"><span class="ico" style="color:#d4890a">history</span><div>Obstáculos com mais de 24 meses<small>${obs.length} fazendas</small></div></div>
      <div class="dr-it" onclick="drListarAtencao('fora_da_base')"><span class="ico" style="color:#d4890a">wrong_location</span><div>Talhões fora da Base<small>${fora.length} fazendas</small></div></div></div>`;
}

function drListarAtencao(chave){
  const l=DR.painel[chave]||[];
  const linhas=l.map(x=>typeof x==='object'
    ?`<div class="dr-it" onclick="drAbrirFazenda(${x.cod_faz})"><span class="dr-cod">${x.cod_faz}</span><div>${esc(x.fazenda)}</div><div class="r">${x.pct}%</div></div>`
    :`<div class="dr-it" onclick="drAbrirFazenda(${x})"><span class="dr-cod">${x}</span></div>`).join('');
  document.getElementById('dr-busca-res').innerHTML=`<div class="dr-grp"><div class="dr-gh">Atenção<button class="dr-btn2" style="width:auto;padding:2px 8px" onclick="document.getElementById('dr-busca-res').innerHTML=''">fechar</button></div>${linhas||'<div class="dr-msg">nenhuma</div>'}</div>`;
}

async function drBuscar(txt){
  const alvo=document.getElementById('dr-busca-res');
  txt=(txt||'').trim();
  if(txt.length<2){alvo.innerHTML='';return;}
  const q=/^\d+$/.test(txt)?sb.from('fazendas').select('cod_faz,nome').eq('cod_faz',Number(txt))
    :sb.from('fazendas').select('cod_faz,nome').ilike('nome',`%${txt}%`).limit(12);
  const {data}=await q;
  alvo.innerHTML=`<div class="dr-grp">${(data||[]).map(f=>`<div class="dr-it" onclick="drAbrirFazenda(${f.cod_faz})"><span class="dr-cod">${f.cod_faz}</span><div>${esc(f.nome)}</div></div>`).join('')||'<div class="dr-msg">nenhuma fazenda</div>'}</div>`;
}

async function drAbrirFazenda(cod,doc){
  DR.cod=cod;DR.doc=doc||'normal';DR.sel=new Map();DR.rem=new Set();DR.modoRemover=false;DR.ajusteId=null;
  clearTimeout(DR.poll);
  document.querySelectorAll('#dr-fila .dr-it').forEach(e=>e.classList.toggle('on',e.getAttribute('onclick')?.includes(`(${cod},`)));
  await drRecarregarFazenda();
}

async function drRecarregarFazenda(){
  const cod=DR.cod;
  try{
    const [geo,faz,sols,obst]=await Promise.all([
      drRpc('drone_mapa_fazenda',{p_cod_faz:cod}),
      sb.from('fazendas').select('cod_faz,nome').eq('cod_faz',cod).single(),
      sb.from('drone_solicitacoes').select('id,tipo,status,observacao').eq('cod_faz',cod).neq('origem','legado').not('status','in','(ok,cancelado)'),
      sb.from('drone_obstaculo_versoes').select('classe_m,versao,enviado_em').eq('cod_faz',cod).eq('vigente',true)]);
    const sIds=(sols.data||[]).map(s=>s.id);
    const ger=sIds.length?await sb.from('drone_geracoes').select('id,solicitacao_id,status,alertas,erro,previa_pdf,publicar_pedido_em,publicacao_erro,resumo')
      .in('solicitacao_id',sIds).neq('status','descartada').neq('status','publicada').order('id',{ascending:false}):{data:[]};
    const env=await sb.from('drone_envios').select('id,tipo,status,erro,enviado_em').eq('cod_faz',cod).order('id',{ascending:false}).limit(5);
    const proj=await sb.from('projetos').select('id').eq('modulo_id','drone').eq('tipo','individual').eq('cod_faz',cod);
    const revs=proj.data&&proj.data.length?await sb.from('projeto_revisoes').select('numero,documento,motivo,criado_em')
      .eq('projeto_id',proj.data[0].id).order('numero',{ascending:false}):{data:[]};
    DR.geo=geo;DR.info={faz:faz.data,sols:sols.data||[],obst:obst.data||[],ger:ger.data||[],envios:env.data||[],revs:revs.data||[]};
  }catch(e){document.getElementById('dr-faz').innerHTML=`<div class="dr-vazio dr-err">${esc(e.message)}</div>`;return;}
  drRender();
}

function drRender(){
  const g=DR.geo,i=DR.info,tal=g.features.filter(f=>f.properties.camada==='talhao');
  const area=tal.filter(f=>f.properties.status!=='fora_da_base').reduce((s,f)=>s+(f.properties.area_ha||0),0);
  const pct=g.cobertura_pct;
  const card=(doc,tit,x,extra)=>`<div class="dr-doc${DR.doc===doc?' on':''}" onclick="DR.doc='${doc}';DR.sel=new Map();DR.rem=new Set();drRender()">
    <b>${tit} · ${x?'Rev'+x.revisao:'sem projeto'}</b>${extra}<small>${x?fmtNum(x.area_ha)+' ha · '+new Date(x.em).toLocaleDateString('pt-BR'):'—'}</small></div>`;
  document.getElementById('dr-faz').innerHTML=`
    <div class="dr-ph"><span class="dr-cod" style="font-size:13px">${DR.cod}</span>
      <div><div class="nm">${esc(i.faz.nome)}</div><div class="sub">${tal.length} talhões · ${fmtNum(area)} ha</div></div>
      <div class="dr-docs">${card('normal','Normal',g.normal,pct!=null&&pct<100?`<span class="dr-tag">${Math.round(pct)}% DA FAZENDA</span>`:'')}
        ${card('catacao','Catação',g.catacao,'')}</div></div>
    <div class="dr-body"><div><div class="dr-map" id="dr-map"></div>
      <div class="dr-leg"><span><i style="background:${DR_COR[DR.doc]}"></i>área de aplicação vigente</span>
        <span><i style="background:${DR_COR.sem}"></i>sem projeto</span><span><i style="background:#fff;border-color:${DR_COR.fora}"></i>fora da Base</span>
        <span><i style="background:#d9defc;border-color:${DR_COR.sel}"></i>selecionado</span><span><i style="background:#fbe0e0;border-color:${DR_COR.rem}"></i>remover</span></div></div>
      <div class="dr-side" id="dr-side"></div></div>`;
  drPintarMapa();
  drPainelLateral();
}

function drPintarMapa(){
  const fc={type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada==='talhao')};
  const apl={type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada===DR.doc)};
  if(DR.mapa){DR.mapa.remove();DR.mapa=null;}
  const m=new maplibregl.Map({container:'dr-map',attributionControl:false,
    style:{version:8,glyphs:'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',sources:{},
      layers:[{id:'fundo',type:'background',paint:{'background-color':'#f7f8fa'}}]}});
  DR.mapa=m;
  m.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-right');
  m.on('load',()=>{
    m.addSource('tal',{type:'geojson',data:fc,promoteId:'talhao'});
    m.addSource('apl',{type:'geojson',data:apl});
    m.addLayer({id:'tal-f',type:'fill',source:'tal',paint:{'fill-color':['case',
      ['boolean',['feature-state','rem'],false],'#fbe0e0',['boolean',['feature-state','sel'],false],'#d9defc',
      ['==',['get','status'],'sem_projeto'],DR_COR.sem,'#ffffff']}});
    m.addLayer({id:'apl-f',type:'fill',source:'apl',paint:{'fill-color':DR_COR[DR.doc],'fill-opacity':.75}});
    m.addLayer({id:'tal-l',type:'line',source:'tal',paint:{'line-color':['case',
      ['boolean',['feature-state','rem'],false],DR_COR.rem,['boolean',['feature-state','sel'],false],DR_COR.sel,
      ['==',['get','status'],'fora_da_base'],DR_COR.fora,'#1f2a30'],
      'line-width':['case',['any',['boolean',['feature-state','sel'],false],['boolean',['feature-state','rem'],false],
        ['==',['get','status'],'fora_da_base']],2,0.6]}});
    m.addLayer({id:'tal-t',type:'symbol',source:'tal',layout:{'text-field':['to-string',['get','talhao']],
      'text-font':['Open Sans Semibold'],'text-size':11},paint:{'text-color':'#1f2a30','text-halo-color':'#fff','text-halo-width':1.5}});
    const b=new maplibregl.LngLatBounds();
    fc.features.forEach(f=>(f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates)
      .forEach(p=>p[0].forEach(c=>b.extend(c))));
    if(!b.isEmpty())m.fitBounds(b,{padding:30,duration:0});
    drAtualizarSelecaoMapa();
    m.on('click','tal-f',e=>drClicarTalhao(e.features[0].properties));
    m.on('mouseenter','tal-f',()=>m.getCanvas().style.cursor='pointer');
    m.on('mouseleave','tal-f',()=>m.getCanvas().style.cursor='');
  });
}

function drAtualizarSelecaoMapa(){
  const m=DR.mapa;if(!m||!m.getSource('tal'))return;
  DR.geo.features.filter(f=>f.properties.camada==='talhao').forEach(f=>{
    const n=f.properties.talhao;
    m.setFeatureState({source:'tal',id:n},{sel:DR.sel.has(n),rem:DR.rem.has(n)});
  });
}

// Ações (clique, painel lateral, envios, prévia) ficam na Tarefa 9.
function drClicarTalhao(){}
function drPainelLateral(){document.getElementById('dr-side').innerHTML='';}
function drNovaSolicitacao(){}
```

- [ ] **Passo 3: Verificação no navegador.** Sirva o app com `python -m http.server 8765 --directory app` e entre com um usuário admin. Na tela **Drone**, confira:
  - a fila carrega;
  - buscar "10008" abre a fazenda;
  - o mapa mostra 208 talhões, os sem projeto em cinza e a área marrom;
  - o cartão Normal mostra "31% DA FAZENDA";
  - trocar para o cartão Catação pinta de verde;
  - o console do navegador não tem erro.

- [ ] **Passo 4: Commit**

```bash
git add app/drone.js app/index.html
git commit -m "Drone Parte 2: tela do Drone no Hub (fila, fazenda e mapa por talhão)"
```

---

### Tarefa 9: Tela do Drone — ações

**Arquivos:**
- Modificar: `app/drone.js` (troca as três funções vazias do fim e acrescenta as ações)

**Interfaces:**
- Consome: `drone_solicitar`, `drone_registrar_envio`, `drone_pedir_geracao`, `drone_publicar_pedido`, `drone_descartar` (Tarefa 1); o bucket `drone-envios` (escrita) e o `drone-previas` (leitura); o estado `DR` e as funções da Tarefa 8; `confirmar()` do `index.html`.
- Produz: o clique no talhão (seleção e remoção), o painel "Nova revisão", envios (ajuste, obstáculos, infestação), gerar prévia, prévia com Publicar/Descartar, nova solicitação e atualização automática enquanto o agente trabalha.

- [ ] **Passo 1: Trocar o bloco final de `app/drone.js`** (as três funções vazias) por:

```javascript
function drAtual(){
  const tipo=DR.doc;
  const sol=DR.info.sols.find(s=>s.tipo===tipo)||null;
  const ger=sol?DR.info.ger.find(g=>g.solicitacao_id===sol.id)||null:null;
  return{sol,ger};
}

function drClicarTalhao(p){
  if(!podeEditar('drone')||DR.doc!=='normal')return;
  const {ger}=drAtual();if(ger)return;                       // prévia aberta: trava a seleção
  const n=p.talhao;
  if(DR.modoRemover){
    if(p.status==='sem_projeto')return;
    DR.rem.has(n)?DR.rem.delete(n):(DR.rem.add(n),DR.sel.delete(n));
  }else{
    if(p.status==='fora_da_base')return;
    DR.sel.has(n)?DR.sel.delete(n):(DR.sel.set(n,DR.fonte||'sistema'),DR.rem.delete(n));
  }
  drAtualizarSelecaoMapa();drPainelLateral();
}

function drSelecionarSemProjeto(){
  DR.geo.features.filter(f=>f.properties.camada==='talhao'&&f.properties.status==='sem_projeto')
    .forEach(f=>{DR.sel.set(f.properties.talhao,DR.fonte||'sistema');DR.rem.delete(f.properties.talhao);});
  drAtualizarSelecaoMapa();drPainelLateral();
}

function drFonte(f){DR.fonte=f;for(const k of DR.sel.keys())DR.sel.set(k,f);drPainelLateral();}

function drObstaculosHtml(){
  const linhas=[15,25,50].map(c=>{const v=DR.info.obst.find(o=>o.classe_m===c);
    return`<div class="dr-row"><span>${c} m</span><span>${v?'v'+v.versao+' · '+new Date(v.enviado_em).toLocaleDateString('pt-BR'):'sem cadastro'}</span></div>`;}).join('');
  const env=DR.info.envios.find(e=>e.status==='fila'||e.status==='processando');
  const err=DR.info.envios.find(e=>e.status==='erro');
  return`<div class="dr-box"><h3><span class="ico">warning</span> Obstáculos</h3>${linhas}
    ${env?`<div class="dr-msg">processando envio…</div>`:''}${err?`<div class="dr-err">Último envio: ${esc(err.erro)}</div>`:''}
    ${podeEditar('drone')?`<button class="dr-btn2" style="margin-top:6px" onclick="drEnviar('obstaculos')"><span class="ico">upload</span> Enviar obstáculos</button>`:''}</div>`;
}

function drPrevHtml(ger){
  if(ger.status==='fila'||ger.status==='processando')return`<div class="dr-box"><h3>Gerando prévia…</h3><div class="dr-msg">O agente está montando o PDF e o .zip. Esta tela atualiza sozinha.</div></div>`;
  if(ger.status==='erro')return`<div class="dr-box"><h3>Erro na geração</h3><div class="dr-err">${esc(ger.erro)}</div>
    <button class="dr-btn2" style="margin-top:8px" onclick="drDescartar(${ger.id})">Descartar e montar de novo</button></div>`;
  if(ger.publicar_pedido_em&&!ger.publicacao_erro)return`<div class="dr-box"><h3>Publicando…</h3><div class="dr-msg">O agente está subindo os arquivos para o portal.</div></div>`;
  const al=(ger.alertas||[]).map(a=>`<li>${esc(a)}</li>`).join('');
  return`<div class="dr-box dr-prev"><h3>Prévia pronta</h3><div id="dr-pdf"><div class="dr-msg">carregando PDF…</div></div>
    ${al?`<ul style="margin:8px 0 0 16px;color:#d4890a">${al}</ul>`:''}
    ${ger.publicacao_erro?`<div class="dr-err">Falha ao publicar: ${esc(ger.publicacao_erro)}</div>`:''}
    <div style="font-size:12px;font-weight:600;margin:8px 0 4px">Motivo</div>
    <input class="dr-mot" id="dr-mot" placeholder="ex.: completar talhões 20–33; talhão 129 reformado">
    <div style="display:flex;gap:8px;margin-top:8px"><button class="dr-btn" onclick="drPublicar(${ger.id})">Publicar</button>
    <button class="dr-btn2" onclick="drDescartar(${ger.id})">Descartar</button></div></div>`;
}

async function drMostrarPdf(ger){
  const {data,error}=await sb.storage.from('drone-previas').createSignedUrl(ger.previa_pdf,600);
  const alvo=document.getElementById('dr-pdf');if(!alvo)return;
  alvo.innerHTML=error?`<div class="dr-err">${esc(error.message)}</div>`:`<iframe src="${data.signedUrl}"></iframe>`;
}

function drPainelLateral(){
  const side=document.getElementById('dr-side');if(!side)return;
  const {sol,ger}=drAtual(),edita=podeEditar('drone');
  let h='';
  if(ger){h+=drPrevHtml(ger);}
  else if(DR.doc==='normal'&&edita){
    const prox=DR.geo.normal?DR.geo.normal.revisao+1:0;
    const inc=[...DR.sel.keys()].sort((a,b)=>a-b),rem=[...DR.rem].sort((a,b)=>a-b);
    const shape=[...DR.sel.values()].includes('shape');
    h+=`<div class="dr-box"><h3><span class="ico" style="color:var(--drones)">edit_note</span> Nova revisão · Normal Rev${prox}</h3>
      <div class="dr-msg" style="text-align:left">Clique nos talhões do mapa</div>
      <div class="dr-seg"><button class="${DR.modoRemover?'':'on'}" onclick="DR.modoRemover=false;drPainelLateral()">Incluir / refazer</button>
        <button class="${DR.modoRemover?'on':''}" onclick="DR.modoRemover=true;drPainelLateral()">Remover</button></div>
      <button class="dr-btn2" onclick="drSelecionarSemProjeto()">Selecionar todos sem projeto</button>
      <div style="font-weight:600;margin-top:8px">Incluir / refazer (${inc.length})</div>
      <div class="dr-chips">${inc.map(n=>`<span class="dr-chip">${n}</span>`).join('')||'<span class="dr-msg">nenhum</span>'}</div>
      <div class="dr-seg"><button class="${shape?'':'on'}" onclick="drFonte('sistema')">Sistema gera</button>
        <button class="${shape?'on':''}" onclick="drFonte('shape')">Subir shape</button></div>
      ${shape?`<button class="dr-btn2" onclick="drEnviar('ajuste')"><span class="ico">upload</span> ${DR.ajusteId?'Shape enviado ✓ (trocar)':'Enviar shape de ajuste'}</button>`:''}
      <div style="font-weight:600;margin-top:8px">Remover (${rem.length})</div>
      <div class="dr-chips">${rem.map(n=>`<span class="dr-chip r">${n}</span>`).join('')||'<span class="dr-msg">nenhum</span>'}</div></div>
      ${drObstaculosHtml()}
      <button class="dr-btn" ${inc.length||rem.length?'':'disabled'} onclick="drGerarNormal()"><span class="ico">play_arrow</span> Gerar prévia</button>
      <div class="dr-msg">A prévia mostra a fazenda inteira (talhões de antes + os novos). Você confere e publica.</div>`;
  }else if(DR.doc==='catacao'&&edita){
    h+=`<div class="dr-box"><h3><span class="ico" style="color:#5b8c5a">grass</span> Catação</h3>
      ${sol?`<div class="dr-row"><span>Solicitação</span><span>${esc(DR_ST[sol.status]||sol.status)}</span></div>
        <button class="dr-btn2" style="margin-top:6px" onclick="drEnviar('infestacao')"><span class="ico">upload</span> Enviar infestação (várias camadas)</button>`
      :`<button class="dr-btn2" onclick="drAbrirCatacao()"><span class="ico">add</span> Abrir Catação desta fazenda</button>`}
      <div class="dr-msg" style="margin-top:6px">Um levantamento novo substitui a Catação inteira.</div></div>
      ${drObstaculosHtml()}
      <button class="dr-btn" ${sol&&sol.status==='solicitado'?'':'disabled'} onclick="drGerarCatacao()"><span class="ico">play_arrow</span> Gerar prévia</button>`;
  }else{
    h+=drObstaculosHtml()+`<div class="dr-msg">Somente consulta.</div>`;
  }
  const hist=(DR.info.revs||[]).filter(r=>r.documento===DR.doc).map(r=>
    `<div class="dr-row"><span>Rev${r.numero} · ${new Date(r.criado_em).toLocaleDateString('pt-BR')}</span><span>${esc((r.motivo||'').slice(0,40))}</span></div>`).join('');
  h+=`<div class="dr-box"><h3><span class="ico">history</span> Histórico</h3>${hist||'<div class="dr-msg">sem revisões</div>'}</div>`;
  h+=`<div id="dr-err" class="dr-err"></div>`;
  side.innerHTML=h;
  if(ger&&ger.status==='pronta'&&!(ger.publicar_pedido_em&&!ger.publicacao_erro))drMostrarPdf(ger);
  clearTimeout(DR.poll);
  const ocupado=(ger&&(['fila','processando'].includes(ger.status)||(ger.publicar_pedido_em&&!ger.publicacao_erro)))
    ||DR.info.envios.some(e=>e.status==='fila'||e.status==='processando');
  if(ocupado)DR.poll=setTimeout(async()=>{await drRecarregarFazenda();drCarregarPainel();},5000);
}

function drErro(e){const el=document.getElementById('dr-err');if(el)el.textContent=e.message||e;}

function drEnviar(tipo){
  const inp=document.createElement('input');inp.type='file';inp.multiple=true;inp.accept='.shp,.shx,.dbf,.prj,.cpg,.zip';
  inp.onchange=async()=>{
    try{
      const pasta=`${DR.cod}/${Date.now()}`,caminhos=[];
      for(const f of inp.files){
        const c=`${pasta}/${f.name}`;
        const {error}=await sb.storage.from('drone-envios').upload(c,f);
        if(error)throw error;caminhos.push(c);
      }
      const {sol}=drAtual();
      const id=await drRpc('drone_registrar_envio',{p_cod_faz:DR.cod,p_tipo:tipo,p_classe_m:null,
        p_solicitacao_id:tipo==='infestacao'?sol.id:null,p_arquivos:caminhos});
      if(tipo==='ajuste')DR.ajusteId=id;
      await drRecarregarFazenda();
    }catch(e){drErro(e);}
  };
  inp.click();
}

async function drGerarNormal(){
  try{
    if([...DR.sel.values()].includes('shape')&&!DR.ajusteId)throw new Error('Envie o shape de ajuste antes de gerar.');
    const escopo={incluir:[...DR.sel].map(([t,f])=>f==='shape'?{talhao:t,fonte:'shape',envio_id:DR.ajusteId}:{talhao:t,fonte:'sistema'}),
      remover:[...DR.rem]};
    const sol=drAtual().sol?.id||await drRpc('drone_solicitar',{p_cod_faz:DR.cod,p_tipo:'normal',p_data_desejada:null,p_observacao:null});
    await drRpc('drone_pedir_geracao',{p_solicitacao_id:sol,p_escopo:escopo});
    DR.sel=new Map();DR.rem=new Set();
    await drRecarregarFazenda();drCarregarPainel();
  }catch(e){drErro(e);}
}

async function drAbrirCatacao(){
  try{await drRpc('drone_solicitar',{p_cod_faz:DR.cod,p_tipo:'catacao',p_data_desejada:null,p_observacao:null});
    await drRecarregarFazenda();drCarregarPainel();}catch(e){drErro(e);}
}

async function drGerarCatacao(){
  try{await drRpc('drone_pedir_geracao',{p_solicitacao_id:drAtual().sol.id,p_escopo:null});
    await drRecarregarFazenda();drCarregarPainel();}catch(e){drErro(e);}
}

async function drPublicar(id){
  try{
    const mot=document.getElementById('dr-mot').value;
    if(!await confirmar('Publicar esta revisão no portal de downloads?',{titulo:'Publicar',ok:'Publicar'}))return;
    await drRpc('drone_publicar_pedido',{p_geracao_id:id,p_motivo:mot});
    await drRecarregarFazenda();drCarregarPainel();
  }catch(e){drErro(e);}
}

async function drDescartar(id){
  try{
    if(!await confirmar('Descartar esta prévia?',{titulo:'Descartar',ok:'Descartar',perigo:true}))return;
    await drRpc('drone_descartar',{p_geracao_id:id});
    await drRecarregarFazenda();drCarregarPainel();
  }catch(e){drErro(e);}
}

async function drNovaSolicitacao(){
  const cod=Number(prompt('Código da fazenda:'));if(!cod)return;
  const obs=prompt('Observação (ex.: completar talhões do bloco norte):')||null;
  try{await drRpc('drone_solicitar',{p_cod_faz:cod,p_tipo:'normal',p_data_desejada:null,p_observacao:obs});
    await drCarregarPainel();drAbrirFazenda(cod,'normal');}catch(e){alert(e.message);}
}
```

- [ ] **Passo 2: Verificação no navegador** (admin, fazenda pequena **10974**). Os passos 2 a 4 abaixo criam dados reais. No fim, descarte a prévia e anote o id da solicitação para cancelá-la (`update hub.drone_solicitacoes set status='cancelado' where id=…`), deixando o banco como estava.
  1. Clique em 2 talhões. Os chips aparecem, e o botão Gerar prévia habilita.
  2. Clique em Gerar prévia. O painel mostra "Gerando prévia…" e, com o agente rodando (`python -m drone.agente --uma-vez`), muda sozinho para "Prévia pronta" com o PDF embutido.
  3. Clique em Descartar. A seleção volta a funcionar.
  4. Envie um obstáculo sem a classe no nome (`arvores.shp`). Depois do ciclo do agente, aparece "Último envio: … escolha a classe no envio."
  5. O console do navegador não tem erro.

- [ ] **Passo 3: Commit**

```bash
git add app/drone.js
git commit -m "Drone Parte 2: ações da tela (revisão por talhão, envios, prévia e publicação)"
```

---

### Tarefa 10: Tag "Incompleta" no portal

**Arquivos:**
- Modificar: `app/portal.html`

**Interfaces:**
- Consome: `public.portal_drone_cobertura()` (Tarefa 1).

- [ ] **Passo 1: Implementar.**
  - Em `carregar()`, depois de agrupar os arquivos, acrescente a leitura da cobertura:
    ```javascript
      try{
        const rc=await fetch(`${SB_URL}/rest/v1/rpc/portal_drone_cobertura`,{method:'POST',
          headers:{apikey:SB_KEY,Authorization:`Bearer ${SB_KEY}`,'Content-Type':'application/json'},body:'{}'});
        COB_DRONE=Object.fromEntries((rc.ok?await rc.json():[]).map(x=>[x.cod_faz,Number(x.cobertura_pct)]));
      }catch(_){COB_DRONE={};}
    ```
  - Declare `let COB_DRONE={};` junto das outras globais (perto de `const MODULOS=`).
  - Em `rotulo`, no bloco `if(mod==='drone')`, troque a linha da Normal por:
    ```javascript
        if(doc==='normal')return (ext==='pdf'?'Mapa · Aplicação Normal':'Aplicação Normal');
    ```
  - Em `arquivo(a)` (linha ~296), logo depois de `<span class="rev">${esc(a.marcador)}${a.revisao}</span>`, acrescente (cada linha de `portal_arquivos` traz `cod_faz`):
    ```javascript
    ${modulo==='drone'&&a.documento==='normal'&&COB_DRONE[a.cod_faz]<100?`<span class="bloco" style="background:#fdf1df;color:#d4890a">Incompleta · ${Math.round(COB_DRONE[a.cod_faz])}%</span>`:''}
    ```

- [ ] **Passo 2: Verificação** (Playwright, igual à Tarefa 10 da Parte 1): abra `portal.html?m=drone` servido localmente e busque "10008". A Normal aparece com "Incompleta · 31%", e a 10016 com "Incompleta · 97%". As abas Plantio, Preparo e Colheita abrem sem erro de JavaScript.

- [ ] **Passo 3: Commit**

```bash
git add app/portal.html
git commit -m "Portal: tag Incompleta na Normal do Drone"
```

---

### Tarefa 11: Teste da tela, publicação e entrega

**Arquivos:**
- Criar: `tests/app/teste_drone_tela.py`

**Interfaces:**
- Consome: a tela inteira (Tarefas 8 e 9) e a conta de teste `teste-automatizado@hub.local`. A credencial está no arquivo JSON indicado pela variável `HUB_CONTA_TESTE`, com as chaves `email` e `senha`.

- [ ] **Passo 1: Escrever o teste**

`tests/app/teste_drone_tela.py`:
```python
"""Teste da tela do Drone (Playwright + Edge). Roda à mão:
    set HUB_CONTA_TESTE=C:/caminho/conta-teste.json
    python tests/app/teste_drone_tela.py
Dá à conta de teste o papel de editor do Drone só durante o teste e devolve o papel original no fim.
Gera uma prévia da fazenda 10974 e DESCARTA (não publica nada); cancela a solicitação criada."""
import functools
import http.server
import json
import os
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from drone.banco import DroneBanco  # noqa: E402

conta = json.loads(Path(os.environ['HUB_CONTA_TESTE']).read_text(encoding='utf-8'))
b = DroneBanco()
u = b.selecionar('usuarios', 'id,papel', {'nome': 'ilike.*teste*'})[0]
papel_orig = u['papel']
tinha_drone = bool(b.selecionar('usuario_modulos', 'modulo_id', {'usuario_id': f"eq.{u['id']}", 'modulo_id': 'eq.drone'}))
falhas = []


def confere(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond:
        falhas.append(msg)


H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(RAIZ / 'app'))
srv = socketserver.TCPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{srv.server_address[1]}/index.html'
sol_criada = None
try:
    b.atualizar('usuarios', {'id': f"eq.{u['id']}"}, {'papel': 'editor'})
    if not tinha_drone:
        b.inserir('usuario_modulos', {'usuario_id': u['id'], 'modulo_id': 'drone'})
    with sync_playwright() as p:
        nav = p.chromium.launch(channel='msedge')
        pg = nav.new_page(viewport={'width': 1400, 'height': 900})
        erros = []
        pg.on('pageerror', lambda e: erros.append(str(e)))
        pg.goto(url)
        pg.fill('#f-email', conta['email']); pg.fill('#f-pass', conta['senha']); pg.click('#btn-entrar')
        pg.wait_for_selector('.ni[onclick*="drone"]', timeout=30000)
        pg.click('.ni[onclick*="drone"]')
        pg.wait_for_selector('#dr-fila .dr-grp', timeout=20000)
        confere(True, 'fila carregou')
        pg.fill('#dr-busca', '10974'); pg.wait_for_selector('#dr-busca-res .dr-it'); pg.click('#dr-busca-res .dr-it')
        pg.wait_for_selector('#dr-map canvas', timeout=20000)
        pg.wait_for_timeout(1500)
        confere(pg.locator('.dr-doc').count() == 2, 'cartões Normal e Catação')
        pg.evaluate("drSelecionarSemProjeto()")
        sem = pg.evaluate("DR.sel.size")
        if sem == 0:
            pg.evaluate("const f=DR.geo.features.find(f=>f.properties.camada==='talhao');drClicarTalhao(f.properties)")
        confere(pg.evaluate("DR.sel.size") > 0, 'seleção de talhões')
        pg.click('text=Gerar prévia')
        pg.wait_for_selector('text=Gerando prévia', timeout=15000)
        confere(True, 'pedido de geração aceito')
        sol_criada = pg.evaluate("drAtual().sol.id")
        os.system(f'"{sys.executable}" -m drone.agente --uma-vez')
        pg.evaluate("drRecarregarFazenda()")
        pg.wait_for_selector('text=Prévia pronta', timeout=60000)
        confere(pg.locator('#dr-pdf iframe').count() == 1, 'PDF da prévia embutido')
        pg.once('dialog', lambda d: d.accept())
        pg.click('button:has-text("Descartar")')
        pg.click('#confirma-sim')
        pg.wait_for_selector('text=Nova revisão', timeout=15000)
        confere(True, 'prévia descartada, seleção liberada')
        confere(not erros, f'sem erro de JavaScript {erros[:2]}')
        nav.close()
finally:
    if sol_criada:
        b.atualizar('drone_solicitacoes', {'id': f'eq.{sol_criada}'}, {'status': 'cancelado'})
    b.atualizar('usuarios', {'id': f"eq.{u['id']}"}, {'papel': papel_orig})
    if not tinha_drone:
        import requests
        requests.delete(f'{b.url}/usuario_modulos', params={'usuario_id': f"eq.{u['id']}", 'modulo_id': 'eq.drone'},
                        headers=b.headers, timeout=60)
    srv.shutdown()
print('FALHAS:', falhas if falhas else 'nenhuma')
sys.exit(1 if falhas else 0)
```

- [ ] **Passo 2: Rodar.** `python tests/app/teste_drone_tela.py` → esperado: todas as linhas com ✓ e `FALHAS: nenhuma`. Confira depois:
  - `select status from hub.drone_solicitacoes where id=<id>` → `cancelado`;
  - a conta de teste voltou ao papel original.

- [ ] **Passo 3: Suíte completa:** `python -m pytest tests/drone -q` → tudo passa.

- [ ] **Passo 4: Commit e publicação**

```bash
git add tests/app/teste_drone_tela.py
git commit -m "Drone Parte 2: teste da tela (Playwright)"
git push origin main
```
Esperado: o GitHub Pages publica o app (`gh run list -L 1`). Confira em `https://lmalerbo.github.io/hub-geotech/` que o menu Drone abre e que a Colheita continua abrindo.

- [ ] **Passo 5: Servidor Geo** (o usuário roda): `git pull`. A tarefa agendada religa o agente com o código novo em até 10 minutos. Para forçar, rode `schtasks /end /tn "Hub Geotech - Agente Drone"` e depois `schtasks /run …`.
