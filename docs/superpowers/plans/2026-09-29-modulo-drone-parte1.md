# Módulo Drone — Parte 1: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** tabelas do módulo Drone no schema `hub`, um agente Python no servidor Geo que gera projetos de aplicação (recorte, shapefile WGS84, PDF v6, `.zip`) e os publica no GitHub Releases, e a importação única do legado.

**Arquitetura:** o banco (Supabase/PostGIS) guarda insumos, solicitações e a fila de gerações, e faz as transições de status por funções SQL. O agente (`drone/agente.py`) consulta a fila, processa com geopandas/shapely, gera o PDF com matplotlib, sobe a prévia no Supabase Storage e, quando alguém pede, publica no GitHub Releases, usando o mesmo padrão de nome e de release do `worker/arquivos.js`. Até as telas da Parte 2 existirem, tudo é acionado por uma CLI (`drone/cli.py`).

**Stack:** Python 3.12+ (servidor Geo via Scoop; na máquina do Leo, 3.14), geopandas + pyogrio + shapely 2 + pyproj, matplotlib, pandas/openpyxl, requests, pytest. PostgreSQL/PostGIS no Supabase (REST/PostgREST, schema `hub`).

**Spec:** `docs/superpowers/specs/2026-09-29-modulo-drone-parte1-design.md`

## Restrições globais

- CRS de trabalho: **EPSG:31983** (SIRGAS 2000 / UTM 23S). CRS de saída: **EPSG:4326**.
- Classes de restrição: **15, 25, 50** (identidade fixa); distâncias iniciais de 15/25/50 m, editáveis em `hub.drone_classes_restricao`.
- Parâmetros iniciais: `taxa_l_ha = 10`, `margem_infestacao_m = 10`, `alerta_aproveitamento_min = 0.30`, `alerta_obstaculos_meses = 24`.
- Normal: `talhões − buffers`. Catação: `(buffer(infestação, margem) ∩ talhões) − buffers`.
- Área total = **soma do `AREA_PROD`** dos talhões da fazenda na Base. Aplicável por talhão = área da intersecção, em ha.
- O shapefile de aplicação tem **1 feição**, EPSG:4326, `.cpg` UTF-8, e os campos **`Taxa l/ha`** (inteiro) e **`Área Apli`** (real, 2 casas).
- O `.zip` contém **só** `{COD}.shp .shx .dbf .prj .cpg`, na raiz.
- Nomes publicados: `{COD}_{NOME}_Rev{N}-Normal.{zip|pdf}` e `{COD}_{NOME}_Rev{N}-Catacao.{zip|pdf}`. O `{NOME}` é convertido como no worker ("VISCONDE DO PARNAÍBA 3" → "VISCONDE.DO.PARNAIBA.3"). Release com a tag `drone-{COD}` no repositório `lmalerbo/hub-geotech-arquivos`.
- PDF: layout v6 (`docs/superpowers/specs/assets/2026-09-29-drone-layout-mapa-v6.html`). Orientação automática (largura > altura da extensão dos talhões → paisagem). Normal em marrom `#a0694b`/`#5c3824`, Catação em verde `#5b8c5a`/`#2f5a2e`, marca `#138a3e`, grafite `#1f2a30`, cinza `#6b7479`, linhas `#cfd5d8`.
- Status da solicitação: `solicitado, aguardando_obstaculos, aguardando_infestacao, em_elaboracao, ok, devolvido, cancelado`. Status da geração: `fila, processando, pronta, erro, publicada, descartada`.
- O agente consulta a fila a cada **30 s**. Geração ou publicação parada há mais de **15 min** volta para a fila. As prévias ficam no bucket privado `drone-previas` e são apagadas depois de 30 dias.
- Mensagens para o usuário em **português**.
- Segredos só em `hub-geotech-supabase.env` (fora do git): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GH_TOKEN`.

## Foco da revisão

1. **Obstáculo enviado em WGS84 (graus):** tem de ser reprojetado para 31983 **antes** do buffer; caso contrário, "15" vira 15 graus. Teste na Tarefa 3.
2. **Infestação toda fora dos talhões** (resultado vazio): deve dar erro claro em português, sem travar o agente nem gerar PDF vazio. Teste na Tarefa 8.
3. **Talhão com `AREA_PROD` vazio (NaN) na Base:** a área total não pode virar NaN. Tratar como 0 e gerar alerta. Teste na Tarefa 2.
4. **Agente cai no meio de uma geração ou publicação:** a linha presa em `processando` ou `publicando` volta para a fila depois de 15 min. Verificação SQL na Tarefa 1.
5. **Repetir uma publicação ou a importação do legado depois de uma falha no GitHub:** não pode duplicar arquivo, revisão nem versão. Testes nas Tarefas 7 e 11.

---

## Estrutura de arquivos

```
drone/
  __init__.py
  erros.py            ErroGeracao
  config.py           caminhos/constantes lidos de ingestao/config.json
  geometria.py        buffers, recorte Normal/Catação, resumo por talhão
  base_talhoes.py     arquivo mais recente da Base e talhões de uma fazenda
  insumos.py          leitura/validação de shapefiles enviados; classe pelo nome do arquivo
  saida.py            shapefile de aplicação WGS84 + .zip
  mapa_pdf.py         gerador do PDF (layout v6)
  banco.py            DroneBanco: chamadas ao schema hub + Supabase Storage
  publicacao.py       GitHub Releases + publicar revisão (usado pelo agente e pelo legado)
  gerador.py          processa uma geração de ponta a ponta
  agente.py           laço da fila (geração e publicação) + sinal de vida
  cli.py              comandos manuais (solicitar, obstaculos, infestacao, gerar, publicar, status)
  importar_legado.py  carga única a partir do catálogo da fase 1
  assets/logo-pedra.png
  requirements.txt
tests/drone/
  conftest.py  test_geometria.py  test_base_talhoes.py  test_insumos.py  test_saida.py
  test_mapa_pdf.py  test_publicacao.py  test_gerador.py  test_importar_legado.py
supabase/migrations/20261002090000_modulo_drone.sql
agendamento/drone_agente.cmd   (+ trecho no agendamento/README.md e no instalar_tarefas.cmd)
```

`drone/` é um pacote; os testes rodam na raiz com `python -m pytest tests/drone -v`. O `comum.py` da ingestão é importado com `sys.path`, que é o mesmo padrão dos scripts atuais.

---

### Tarefa 1: Migration do módulo Drone

**Arquivos:**
- Criar: `supabase/migrations/20261002090000_modulo_drone.sql`

**Interfaces produzidas** (usadas pelas tarefas seguintes):
- Tabelas: `hub.drone_parametros(chave, valor text)`, `hub.drone_classes_restricao(classe_m, distancia_m)`, `hub.drone_obstaculo_versoes`, `hub.drone_obstaculo_feicoes`, `hub.drone_infestacoes`, `hub.drone_infestacao_feicoes`, `hub.drone_solicitacoes`, `hub.drone_geracoes`.
- RPCs (todas `security definer`, só para `service_role`):
  - `drone_gravar_obstaculos(p_cod_faz int, p_classe_m int, p_origem text, p_arquivo text, p_wkts text[], p_usuario uuid default null) → bigint`
  - `drone_gravar_infestacao(p_solicitacao_id bigint, p_empresa text, p_arquivo text, p_wkts text[], p_usuario uuid default null) → bigint`
  - `drone_obstaculos_vigentes(p_cod_faz int) → table(classe_m int, versao_id bigint, enviado_em timestamptz, wkt text)`
  - `drone_infestacao_wkt(p_infestacao_id bigint) → table(wkt text)`
  - `drone_pegar_geracao() → setof hub.drone_geracoes`
  - `drone_pegar_publicacao() → setof hub.drone_geracoes`
  - `drone_concluir_publicacao(p_geracao_id bigint, p_revisao_id bigint) → void`

- [ ] **Passo 1: Escrever a migration**

```sql
-- Módulo Drone, Parte 1: parâmetros, insumos (obstáculos/infestação),
-- solicitações e fila de gerações. O agente do servidor Geo usa a
-- service_role; as telas (Parte 2) terão RPCs próprias com permissão.
-- Spec: docs/superpowers/specs/2026-09-29-modulo-drone-parte1-design.md

begin;

create extension if not exists postgis with schema extensions;

insert into hub.modulos (id, nome, ordem) values ('drone', 'Drone', 5)
on conflict (id) do nothing;

-- papel novo: solicitante (abre e acompanha pedidos; não edita projeto)
alter table hub.usuarios drop constraint if exists usuarios_papel_check;
alter table hub.usuarios add constraint usuarios_papel_check
  check (papel in ('editor', 'leitura', 'solicitante'));

insert into hub.documento_tipos (modulo_id, codigo, nome, marcador, sufixo, ordem, extensoes) values
  ('drone', 'normal',  'Aplicação Normal',  'Rev', '-Normal',  1, array['zip', 'pdf']),
  ('drone', 'catacao', 'Aplicação Catação', 'Rev', '-Catacao', 2, array['zip', 'pdf'])
on conflict do nothing;

create table hub.drone_parametros (
  chave         text primary key,
  valor         text not null,
  descricao     text,
  atualizado_em timestamptz not null default now()
);
insert into hub.drone_parametros (chave, valor, descricao) values
  ('taxa_l_ha',                 '10',   'Taxa gravada no shape de aplicação (l/ha)'),
  ('margem_infestacao_m',       '10',   'Expansão do shape de infestação antes do recorte (m)'),
  ('alerta_aproveitamento_min', '0.30', 'Aplicável/AREA_PROD abaixo disso gera alerta'),
  ('alerta_obstaculos_meses',   '24',   'Obstáculos mais antigos que isso geram alerta'),
  ('agente_ultimo_ciclo',       '',     'Sinal de vida do agente (ISO 8601)');

create table hub.drone_classes_restricao (
  classe_m      int primary key check (classe_m in (15, 25, 50)),
  distancia_m   numeric not null check (distancia_m > 0),
  categorias    text not null,
  atualizado_em timestamptz not null default now()
);
insert into hub.drone_classes_restricao (classe_m, distancia_m, categorias) values
  (15, 15, 'Árvore isolada'),
  (25, 25, 'Rede de energia padrão'),
  (50, 50, 'Rede de alta tensão, sede/casa, APP/mata/vegetação nativa, zona urbana, cultura vizinha, pasto, rodovia, represa');

create table hub.drone_obstaculo_versoes (
  id             bigint generated always as identity primary key,
  cod_faz        int  not null references hub.fazendas (cod_faz),
  classe_m       int  not null references hub.drone_classes_restricao (classe_m),
  versao         int  not null,
  vigente        boolean not null default true,
  origem         text not null check (origem in ('upload', 'legado')),
  arquivo_origem text,
  n_feicoes      int  not null default 0,
  enviado_por    uuid references hub.usuarios (id),
  enviado_em     timestamptz not null default now(),
  unique (cod_faz, classe_m, versao)
);
create unique index drone_obstaculo_uma_vigente
  on hub.drone_obstaculo_versoes (cod_faz, classe_m) where vigente;

create table hub.drone_obstaculo_feicoes (
  versao_id bigint not null references hub.drone_obstaculo_versoes (id) on delete cascade,
  geom      extensions.geometry(Geometry, 31983) not null
);
create index on hub.drone_obstaculo_feicoes (versao_id);

create table hub.drone_solicitacoes (
  id               bigint generated always as identity primary key,
  cod_faz          int  not null references hub.fazendas (cod_faz),
  tipo             text not null check (tipo in ('normal', 'catacao')),
  origem           text not null check (origem in ('formulario', 'dronemgmt', 'legado')),
  solicitante_id   uuid references hub.usuarios (id),
  data_desejada    date,
  status           text not null default 'solicitado' check (status in (
                     'solicitado', 'aguardando_obstaculos', 'aguardando_infestacao',
                     'em_elaboracao', 'ok', 'devolvido', 'cancelado')),
  responsavel_id   uuid references hub.usuarios (id),
  motivo_devolucao text,
  revisao_id       bigint references hub.projeto_revisoes (id),
  criado_em        timestamptz not null default now(),
  iniciado_em      timestamptz,
  concluido_em     timestamptz
);

create table hub.drone_infestacoes (
  id             bigint generated always as identity primary key,
  cod_faz        int not null references hub.fazendas (cod_faz),
  solicitacao_id bigint references hub.drone_solicitacoes (id),
  empresa        text,
  arquivo_origem text,
  n_feicoes      int not null default 0,
  enviado_por    uuid references hub.usuarios (id),
  enviado_em     timestamptz not null default now()
);
create table hub.drone_infestacao_feicoes (
  infestacao_id bigint not null references hub.drone_infestacoes (id) on delete cascade,
  geom          extensions.geometry(Geometry, 31983) not null
);
create index on hub.drone_infestacao_feicoes (infestacao_id);

create table hub.drone_geracoes (
  id                     bigint generated always as identity primary key,
  solicitacao_id         bigint not null references hub.drone_solicitacoes (id),
  status                 text not null default 'fila' check (status in (
                           'fila', 'processando', 'pronta', 'erro', 'publicada', 'descartada')),
  infestacao_id          bigint references hub.drone_infestacoes (id),
  pedido_por             uuid references hub.usuarios (id),
  pedido_em              timestamptz not null default now(),
  iniciado_em            timestamptz,
  concluido_em           timestamptz,
  orientacao             text check (orientacao in ('retrato', 'paisagem')),
  insumos                jsonb,
  resumo                 jsonb,
  alertas                jsonb,
  erro                   text,
  previa_pdf             text,
  previa_zip             text,
  publicar_pedido_em     timestamptz,
  publicar_motivo        text,
  publicar_por           uuid references hub.usuarios (id),
  publicacao_iniciada_em timestamptz,
  publicacao_erro        text
);
create index on hub.drone_geracoes (status, pedido_em);

-- ── log das mudanças de status (entidade = fazenda) ────────────────────
create or replace function hub.drone_log_solicitacao()
returns trigger language plpgsql security definer set search_path = hub as $$
begin
  if tg_op = 'INSERT' or new.status is distinct from old.status then
    insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo,
                                   valor_anterior, valor_novo, usuario_id, origem)
    values ('drone', 'fazenda', new.cod_faz, 'solicitacao ' || new.id || ' (' || new.tipo || ')',
            case when tg_op = 'UPDATE' then old.status end, new.status, auth.uid(),
            case when auth.role() = 'service_role' then 'agente_drone' else 'usuario' end);
  end if;
  return new;
end $$;

-- ── status inicial: sem obstáculos / sem infestação ────────────────────
create or replace function hub.drone_status_inicial()
returns trigger language plpgsql security definer set search_path = hub as $$
begin
  if new.origem <> 'legado' and new.status = 'solicitado' then
    if new.tipo = 'normal' and not exists (
         select 1 from hub.drone_obstaculo_versoes v where v.cod_faz = new.cod_faz and v.vigente) then
      new.status := 'aguardando_obstaculos';
    elsif new.tipo = 'catacao' then
      new.status := 'aguardando_infestacao';
    end if;
  end if;
  return new;
end $$;

create trigger drone_solicitacao_status_inicial before insert on hub.drone_solicitacoes
  for each row execute function hub.drone_status_inicial();
create trigger drone_solicitacao_log after insert or update of status on hub.drone_solicitacoes
  for each row execute function hub.drone_log_solicitacao();

-- ── insumos ────────────────────────────────────────────────────────────
create or replace function hub.drone_gravar_obstaculos(
  p_cod_faz int, p_classe_m int, p_origem text, p_arquivo text, p_wkts text[], p_usuario uuid default null)
returns bigint language plpgsql security definer set search_path = hub, extensions as $$
declare v_versao int; v_id bigint;
begin
  perform pg_advisory_xact_lock(hashtext('drone_obst_' || p_cod_faz || '_' || p_classe_m));
  select coalesce(max(versao), 0) + 1 into v_versao
    from hub.drone_obstaculo_versoes where cod_faz = p_cod_faz and classe_m = p_classe_m;
  update hub.drone_obstaculo_versoes set vigente = false
   where cod_faz = p_cod_faz and classe_m = p_classe_m and vigente;
  insert into hub.drone_obstaculo_versoes (cod_faz, classe_m, versao, origem, arquivo_origem, n_feicoes, enviado_por)
  values (p_cod_faz, p_classe_m, v_versao, p_origem, p_arquivo, coalesce(array_length(p_wkts, 1), 0), p_usuario)
  returning id into v_id;
  insert into hub.drone_obstaculo_feicoes (versao_id, geom)
  select v_id, ST_GeomFromText(w, 31983) from unnest(p_wkts) w;
  update hub.drone_solicitacoes set status = 'solicitado'
   where cod_faz = p_cod_faz and tipo = 'normal' and status = 'aguardando_obstaculos';
  return v_id;
end $$;

create or replace function hub.drone_gravar_infestacao(
  p_solicitacao_id bigint, p_empresa text, p_arquivo text, p_wkts text[], p_usuario uuid default null)
returns bigint language plpgsql security definer set search_path = hub, extensions as $$
declare v_sol hub.drone_solicitacoes; v_id bigint;
begin
  select * into v_sol from hub.drone_solicitacoes where id = p_solicitacao_id;
  if v_sol.id is null or v_sol.tipo <> 'catacao' then
    raise exception 'Solicitação % não é uma catação', p_solicitacao_id;
  end if;
  insert into hub.drone_infestacoes (cod_faz, solicitacao_id, empresa, arquivo_origem, n_feicoes, enviado_por)
  values (v_sol.cod_faz, v_sol.id, p_empresa, p_arquivo, coalesce(array_length(p_wkts, 1), 0), p_usuario)
  returning id into v_id;
  insert into hub.drone_infestacao_feicoes (infestacao_id, geom)
  select v_id, ST_GeomFromText(w, 31983) from unnest(p_wkts) w;
  update hub.drone_solicitacoes set status = 'solicitado'
   where id = v_sol.id and status = 'aguardando_infestacao';
  return v_id;
end $$;

create or replace function hub.drone_obstaculos_vigentes(p_cod_faz int)
returns table (classe_m int, versao_id bigint, enviado_em timestamptz, wkt text)
language sql stable security definer set search_path = hub, extensions as $$
  select v.classe_m, v.id, v.enviado_em, ST_AsText(f.geom)
    from hub.drone_obstaculo_versoes v join hub.drone_obstaculo_feicoes f on f.versao_id = v.id
   where v.cod_faz = p_cod_faz and v.vigente;
$$;

create or replace function hub.drone_infestacao_wkt(p_infestacao_id bigint)
returns table (wkt text)
language sql stable security definer set search_path = hub, extensions as $$
  select ST_AsText(geom) from hub.drone_infestacao_feicoes where infestacao_id = p_infestacao_id;
$$;

-- ── fila ───────────────────────────────────────────────────────────────
create or replace function hub.drone_pegar_geracao()
returns setof hub.drone_geracoes language plpgsql security definer set search_path = hub as $$
begin
  update hub.drone_geracoes set status = 'fila', iniciado_em = null
   where status = 'processando' and iniciado_em < now() - interval '15 minutes';
  return query
  update hub.drone_geracoes g set status = 'processando', iniciado_em = now()
   where g.id = (select id from hub.drone_geracoes where status = 'fila'
                  order by pedido_em for update skip locked limit 1)
  returning g.*;
end $$;

create or replace function hub.drone_pegar_publicacao()
returns setof hub.drone_geracoes language plpgsql security definer set search_path = hub as $$
begin
  update hub.drone_geracoes set publicacao_iniciada_em = null
   where status = 'pronta' and publicacao_iniciada_em < now() - interval '15 minutes';
  return query
  update hub.drone_geracoes g set publicacao_iniciada_em = now(), publicacao_erro = null
   where g.id = (select id from hub.drone_geracoes
                  where status = 'pronta' and publicar_pedido_em is not null
                    and publicacao_iniciada_em is null and publicacao_erro is null
                  order by publicar_pedido_em for update skip locked limit 1)
  returning g.*;
end $$;

create or replace function hub.drone_concluir_publicacao(p_geracao_id bigint, p_revisao_id bigint)
returns void language plpgsql security definer set search_path = hub as $$
declare v_sol bigint;
begin
  update hub.drone_geracoes set status = 'publicada', concluido_em = now()
   where id = p_geracao_id returning solicitacao_id into v_sol;
  update hub.drone_geracoes set status = 'descartada'
   where solicitacao_id = v_sol and id <> p_geracao_id and status in ('fila', 'pronta', 'erro');
  update hub.drone_solicitacoes set status = 'ok', revisao_id = p_revisao_id, concluido_em = now()
   where id = v_sol;
end $$;

-- ── segurança ──────────────────────────────────────────────────────────
do $$
declare t text;
begin
  foreach t in array array['drone_parametros', 'drone_classes_restricao', 'drone_obstaculo_versoes',
                           'drone_obstaculo_feicoes', 'drone_infestacoes', 'drone_infestacao_feicoes',
                           'drone_solicitacoes', 'drone_geracoes'] loop
    execute format('alter table hub.%I enable row level security', t);
    execute format('create policy leitura on hub.%I for select to authenticated using (true)', t);
    execute format('grant select on hub.%I to authenticated', t);
    execute format('grant all on hub.%I to service_role', t);
  end loop;
end $$;

do $$
declare f text;
begin
  foreach f in array array[
    'hub.drone_gravar_obstaculos(int, int, text, text, text[], uuid)',
    'hub.drone_gravar_infestacao(bigint, text, text, text[], uuid)',
    'hub.drone_obstaculos_vigentes(int)', 'hub.drone_infestacao_wkt(bigint)',
    'hub.drone_pegar_geracao()', 'hub.drone_pegar_publicacao()',
    'hub.drone_concluir_publicacao(bigint, bigint)'] loop
    execute format('revoke all on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
end $$;

-- prévias temporárias (privado; só service_role grava)
insert into storage.buckets (id, name, public) values ('drone-previas', 'drone-previas', false)
on conflict (id) do nothing;

commit;
```

- [ ] **Passo 2: Aplicar no SQL Editor do Supabase** (projeto `dpvsivypabmvmrrpgmhc`), igual às migrations anteriores. Esperado: `Success. No rows returned`. Se aparecer o aviso de "tabelas sem RLS", é alarme falso (o RLS é ligado no laço `do $$`). Use "Run and enable RLS".

- [ ] **Passo 3: Verificar no SQL Editor (rodar e depois desfazer)**

```sql
begin;
-- fazenda real qualquer da Base
with f as (select cod_faz from hub.fazendas order by cod_faz limit 1)
insert into hub.drone_solicitacoes (cod_faz, tipo, origem) select cod_faz, 'normal', 'formulario' from f;
select status from hub.drone_solicitacoes order by id desc limit 1;                 -- esperado: aguardando_obstaculos
select hub.drone_gravar_obstaculos((select cod_faz from hub.fazendas order by cod_faz limit 1), 15, 'upload', 't.shp',
       array['POINT(200000 7550000)']);
select status from hub.drone_solicitacoes order by id desc limit 1;                 -- esperado: solicitado
select classe_m, wkt from hub.drone_obstaculos_vigentes((select cod_faz from hub.fazendas order by cod_faz limit 1)); -- 1 linha POINT
insert into hub.drone_geracoes (solicitacao_id) select max(id) from hub.drone_solicitacoes;
select id, status from hub.drone_pegar_geracao();                                   -- status processando
update hub.drone_geracoes set iniciado_em = now() - interval '20 minutes' where status = 'processando';
select status from hub.drone_pegar_geracao();                                       -- recuperou: volta processando (foi pra fila e foi pego)
select count(*) from hub.log_auditoria where modulo_id = 'drone';                   -- >= 2
rollback;
```

- [ ] **Passo 4: Commit**

```bash
git add supabase/migrations/20261002090000_modulo_drone.sql
git commit -m "Drone: migration do módulo (insumos, solicitações, fila de gerações)"
```

---

### Tarefa 2: Pacote, configuração e regras de geometria

**Arquivos:**
- Criar: `drone/__init__.py` (vazio), `drone/erros.py`, `drone/config.py`, `drone/geometria.py`, `drone/requirements.txt`, `tests/drone/__init__.py` (vazio), `tests/drone/conftest.py`, `tests/drone/test_geometria.py`
- Modificar: `ingestao/config.json` (bloco `drone`), `.gitignore` (`drone/trabalho/`)

**Interfaces produzidas:**
- `drone.erros.ErroGeracao(Exception)`
- `drone.config.CRS_TRABALHO = 31983`, `CRS_SAIDA = 4326`, `cfg() -> dict` (bloco `drone` do config.json), `PASTA_TRABALHO: Path`
- `drone.geometria.so_poligonos(geom) -> MultiPolygon`
- `drone.geometria.uniao_buffers(obstaculos: dict[int, list[BaseGeometry]], distancias: dict[int, float]) -> BaseGeometry`
- `drone.geometria.Recorte` (dataclass): `area: MultiPolygon` (31983), `por_talhao: list[dict]` com as chaves `talhao:int, area_prod:float, aplicavel_ha:float`, `area_total_ha: float`, `aplicacao_ha: float`, `talhoes_sem_area_prod: list[int]`
- `drone.geometria.recortar(talhoes: GeoDataFrame, buffers, infestacao: list|None = None, margem: float = 0.0) -> Recorte`. `talhoes` tem as colunas `TALHAO`, `AREA_PROD` e `geometry`, em 31983. Lança `ErroGeracao` se o resultado for vazio.

- [ ] **Passo 1: Dependências e configuração**

`drone/requirements.txt`:
```text
geopandas>=1.0
pyogrio>=0.9
shapely>=2.0
pyproj>=3.6
pandas>=2.2
openpyxl
matplotlib>=3.8
requests
truststore
pytest>=8
```

Acrescentar ao `ingestao/config.json` (dentro do objeto raiz):
```json
"drone": {
  "base_talhoes_pasta": "//lnxfs3/work3/Projetos/SHAPES_RPA",
  "base_talhoes_padrao": "Talhoes_da_Pedra_*_fme.shp",
  "arquivos_repo": "lmalerbo/hub-geotech-arquivos",
  "intervalo_s": 30,
  "catalogo_legado": "C:/Users/lmalerbo/Documents/catalogo_drone.xlsx"
}
```

Acrescentar ao `.gitignore`:
```text
drone/trabalho/
```

`drone/erros.py`:
```python
class ErroGeracao(Exception):
    """Problema nos insumos ou no resultado; a mensagem vai para a Geo (em português)."""
```

`drone/config.py`:
```python
"""Constantes e configuração do módulo Drone (bloco "drone" de ingestao/config.json)."""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRS_TRABALHO = 31983   # SIRGAS 2000 / UTM 23S — todo cálculo de área/buffer
CRS_SAIDA = 4326       # WGS84 — shapefile entregue ao piloto
PASTA_TRABALHO = RAIZ / 'drone' / 'trabalho'
LOGO = RAIZ / 'drone' / 'assets' / 'logo-pedra.png'


def cfg() -> dict:
    with open(RAIZ / 'ingestao' / 'config.json', encoding='utf-8') as f:
        return json.load(f)['drone']
```

Copiar `docs/superpowers/specs/assets/logo-pedra.png` para `drone/assets/logo-pedra.png`.

- [ ] **Passo 2: Instalar e escrever os testes (que devem falhar)**

Rodar: `pip install -r drone/requirements.txt`

`tests/drone/conftest.py`:
```python
import geopandas as gpd
import pytest
from shapely.geometry import box

CRS = 31983


@pytest.fixture
def talhoes():
    """Dois talhões de 100 x 100 m (1 ha cada), lado a lado."""
    return gpd.GeoDataFrame(
        {'TALHAO': [1, 2], 'AREA_PROD': [1.0, 1.0]},
        geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)], crs=CRS)


@pytest.fixture
def grava_shp(tmp_path):
    """grava_shp(nome, geoms, crs) -> caminho do .shp."""
    def _grava(nome, geoms, crs=CRS):
        caminho = tmp_path / f'{nome}.shp'
        gpd.GeoDataFrame({'id': list(range(len(geoms)))}, geometry=geoms, crs=crs).to_file(caminho)
        return caminho
    return _grava
```

`tests/drone/test_geometria.py`:
```python
import math

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, box

from drone.erros import ErroGeracao
from drone.geometria import recortar, uniao_buffers


def test_normal_sem_obstaculos_e_a_fazenda_inteira(talhoes):
    r = recortar(talhoes, uniao_buffers({}, {}))
    assert r.aplicacao_ha == pytest.approx(2.0)
    assert r.area_total_ha == pytest.approx(2.0)
    assert [t['aplicavel_ha'] for t in r.por_talhao] == pytest.approx([1.0, 1.0])


def test_arvore_de_15m_tira_um_circulo(talhoes):
    b = uniao_buffers({15: [Point(50, 50)]}, {15: 15})
    r = recortar(talhoes, b)
    assert r.por_talhao[0]['aplicavel_ha'] == pytest.approx(1.0 - math.pi * 15**2 / 1e4, rel=1e-2)
    assert r.por_talhao[1]['aplicavel_ha'] == pytest.approx(1.0)


def test_rede_em_linha_de_25m_vira_faixa(talhoes):
    b = uniao_buffers({25: [LineString([(0, 50), (200, 50)])]}, {25: 25})
    r = recortar(talhoes, b)
    assert r.aplicacao_ha == pytest.approx(2.0 - 200 * 50 / 1e4, rel=1e-3)


def test_catacao_expande_10m_e_recorta_no_talhao(talhoes):
    # mancha de 10 x 10 m encostada na borda esquerda: a expansão não sai do talhão
    r = recortar(talhoes, uniao_buffers({}, {}), infestacao=[box(0, 45, 10, 55)], margem=10)
    esperado = (box(0, 45, 10, 55).buffer(10).intersection(box(0, 0, 200, 100)).area) / 1e4
    assert r.aplicacao_ha == pytest.approx(esperado)
    assert r.por_talhao[1]['aplicavel_ha'] == pytest.approx(0.0)


def test_resultado_vazio_da_erro_em_portugues(talhoes):
    b = uniao_buffers({50: [box(0, 0, 200, 100)]}, {50: 50})
    with pytest.raises(ErroGeracao, match='vazia'):
        recortar(talhoes, b)


def test_infestacao_fora_dos_talhoes_da_erro(talhoes):
    with pytest.raises(ErroGeracao, match='vazia'):
        recortar(talhoes, uniao_buffers({}, {}), infestacao=[box(1000, 1000, 1010, 1010)], margem=10)


def test_geometria_invalida_e_corrigida(talhoes):
    gravata = gpd.GeoSeries.from_wkt(['POLYGON((0 0, 100 100, 100 0, 0 100, 0 0))']).iloc[0]
    r = recortar(talhoes, uniao_buffers({50: [gravata]}, {50: 1}))
    assert r.aplicacao_ha < 2.0


def test_area_prod_vazia_conta_zero_e_e_informada(talhoes):
    talhoes.loc[1, 'AREA_PROD'] = float('nan')
    r = recortar(talhoes, uniao_buffers({}, {}))
    assert r.area_total_ha == pytest.approx(1.0)
    assert r.talhoes_sem_area_prod == [2]
```

- [ ] **Passo 3: Rodar os testes para ver falhar**

Rodar: `python -m pytest tests/drone/test_geometria.py -v`
Esperado: FAIL com `ModuleNotFoundError: No module named 'drone.geometria'`

- [ ] **Passo 4: Implementar `drone/geometria.py`**

```python
"""Regras de recorte do projeto de aplicação (spec, seção 3). Tudo em EPSG:31983."""
import math
from dataclasses import dataclass, field

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import make_valid

from drone.erros import ErroGeracao

AREA_MINIMA_M2 = 1.0   # restos de recorte menores que 1 m² são descartados


def so_poligonos(geom: BaseGeometry) -> MultiPolygon:
    if geom is None or geom.is_empty:
        return MultiPolygon()
    if isinstance(geom, Polygon):
        partes = [geom]
    elif isinstance(geom, MultiPolygon):
        partes = list(geom.geoms)
    else:
        partes = [p for g in getattr(geom, 'geoms', []) for p in so_poligonos(g).geoms]
    return MultiPolygon([p for p in partes if p.area >= AREA_MINIMA_M2])


def uniao_buffers(obstaculos: dict, distancias: dict) -> BaseGeometry:
    partes = [make_valid(g).buffer(distancias[classe])
              for classe, geoms in obstaculos.items() for g in geoms if not g.is_empty]
    return unary_union(partes) if partes else Polygon()


@dataclass
class Recorte:
    area: MultiPolygon
    por_talhao: list = field(default_factory=list)
    area_total_ha: float = 0.0
    aplicacao_ha: float = 0.0
    talhoes_sem_area_prod: list = field(default_factory=list)


def recortar(talhoes: gpd.GeoDataFrame, buffers: BaseGeometry,
             infestacao: list | None = None, margem: float = 0.0) -> Recorte:
    geoms = [make_valid(g) for g in talhoes.geometry]
    uniao = unary_union(geoms)
    if infestacao is None:
        base = uniao
    else:
        mancha = unary_union([make_valid(g) for g in infestacao if not g.is_empty])
        base = mancha.buffer(margem).intersection(uniao)
    area = so_poligonos(make_valid(base.difference(buffers)))
    if area.is_empty:
        raise ErroGeracao('A área de aplicação ficou vazia: confira a infestação e os obstáculos desta fazenda.')

    por_talhao, sem_area = [], []
    for (_, t), g in sorted(zip(talhoes.iterrows(), geoms), key=lambda x: int(x[0][1]['TALHAO'])):
        area_prod = t['AREA_PROD']
        if area_prod is None or (isinstance(area_prod, float) and math.isnan(area_prod)):
            sem_area.append(int(t['TALHAO']))
            area_prod = 0.0
        por_talhao.append({'talhao': int(t['TALHAO']), 'area_prod': float(area_prod),
                           'aplicavel_ha': g.intersection(area).area / 1e4})
    return Recorte(area=area, por_talhao=por_talhao,
                   area_total_ha=sum(t['area_prod'] for t in por_talhao),
                   aplicacao_ha=area.area / 1e4, talhoes_sem_area_prod=sem_area)
```

- [ ] **Passo 5: Rodar os testes**

Rodar: `python -m pytest tests/drone/test_geometria.py -v`
Esperado: 8 passed

- [ ] **Passo 6: Commit**

```bash
git add drone tests/drone ingestao/config.json .gitignore
git commit -m "Drone: regras de recorte Normal/Catação (geometria)"
```

---

### Tarefa 3: Base de Talhões e leitura de insumos

**Arquivos:**
- Criar: `drone/base_talhoes.py`, `drone/insumos.py`, `tests/drone/test_base_talhoes.py`, `tests/drone/test_insumos.py`

**Interfaces produzidas:**
- `drone.base_talhoes.arquivo_mais_recente(pasta: str, padrao: str) -> tuple[date, Path]`, que lança `ErroGeracao` se não achar nenhum arquivo
- `drone.base_talhoes.talhoes_da_fazenda(caminho: Path, cod_faz: int) -> GeoDataFrame` (colunas `TALHAO:int`, `AREA_PROD:float`, geometry em 31983, geometria corrigida), que lança `ErroGeracao` se a fazenda não tiver talhões
- `drone.insumos.ler_shapefile(caminho: Path) -> list[BaseGeometry]` (em 31983, sem geometrias vazias), que lança `ErroGeracao` se faltar `.prj` ou o CRS for desconhecido
- `drone.insumos.classe_pelo_nome(nome: str) -> int | None` (15/25/50 ou None)

- [ ] **Passo 1: Escrever os testes**

`tests/drone/test_base_talhoes.py`:
```python
import datetime

import geopandas as gpd
import pytest
from shapely.geometry import box

from drone.base_talhoes import arquivo_mais_recente, talhoes_da_fazenda
from drone.erros import ErroGeracao


def _base(tmp_path, nome):
    gdf = gpd.GeoDataFrame(
        {'SECAO': [10156, 10156, 20001], 'TALHAO': [2.0, 1.0, 1.0], 'AREA_PROD': [3.5, 1.2, 9.9]},
        geometry=[box(100, 0, 200, 100), box(0, 0, 100, 100), box(500, 0, 600, 100)], crs=31983)
    caminho = tmp_path / nome
    gdf.to_file(caminho)
    return caminho


def test_escolhe_o_arquivo_pela_data_do_nome(tmp_path):
    _base(tmp_path, 'Talhoes_da_Pedra_30_09_2026_fme.shp')
    _base(tmp_path, 'Talhoes_da_Pedra_01_10_2026_fme.shp')
    data, caminho = arquivo_mais_recente(str(tmp_path), 'Talhoes_da_Pedra_*_fme.shp')
    assert data == datetime.date(2026, 10, 1)
    assert caminho.name == 'Talhoes_da_Pedra_01_10_2026_fme.shp'


def test_sem_arquivo_da_erro(tmp_path):
    with pytest.raises(ErroGeracao, match='Base de Talhões'):
        arquivo_mais_recente(str(tmp_path), 'Talhoes_da_Pedra_*_fme.shp')


def test_talhoes_da_fazenda_filtra_e_tipa(tmp_path):
    t = talhoes_da_fazenda(_base(tmp_path, 'Talhoes_da_Pedra_01_10_2026_fme.shp'), 10156)
    assert sorted(t['TALHAO'].tolist()) == [1, 2]
    assert t['TALHAO'].dtype.kind == 'i'
    assert t.crs.to_epsg() == 31983


def test_fazenda_sem_talhoes_da_erro(tmp_path):
    with pytest.raises(ErroGeracao, match='99999'):
        talhoes_da_fazenda(_base(tmp_path, 'Talhoes_da_Pedra_01_10_2026_fme.shp'), 99999)
```

`tests/drone/test_insumos.py`:
```python
import pytest
from shapely.geometry import LineString, Point, box

from drone.erros import ErroGeracao
from drone.insumos import classe_pelo_nome, ler_shapefile


def test_le_e_mantem_31983(grava_shp):
    geoms = ler_shapefile(grava_shp('r15', [Point(200000, 7550000)]))
    assert geoms[0].x == pytest.approx(200000)


def test_reprojeta_wgs84_para_31983_antes_do_buffer(grava_shp):
    # um ponto em graus tem de virar coordenada UTM (centenas de milhares de metros)
    geoms = ler_shapefile(grava_shp('arvores', [Point(-47.6, -21.2)], crs=4326))
    assert 150_000 < geoms[0].x < 900_000
    assert 7_000_000 < geoms[0].y < 8_000_000


def test_sem_prj_da_erro(grava_shp):
    caminho = grava_shp('rede', [LineString([(0, 0), (10, 0)])])
    caminho.with_suffix('.prj').unlink()
    with pytest.raises(ErroGeracao, match='.prj'):
        ler_shapefile(caminho)


def test_descarta_vazias(grava_shp):
    geoms = ler_shapefile(grava_shp('x', [box(0, 0, 10, 10), Point()]))
    assert len(geoms) == 1


@pytest.mark.parametrize('nome,classe', [
    ('restricoes15m', 15), ('Restrições 15m', 15), ('15M', 15), ('retricoes25m', 25),
    ('resrtricoes50m', 50), ('restricoes50m_rede', 50), ('REDE50', 50), ('restricoes10m', None), ('Arvores', None),
])
def test_classe_pelo_nome(nome, classe):
    assert classe_pelo_nome(nome) == classe
```

- [ ] **Passo 2: Rodar para ver falhar**

Rodar: `python -m pytest tests/drone/test_base_talhoes.py tests/drone/test_insumos.py -v`
Esperado: FAIL com `ModuleNotFoundError`

- [ ] **Passo 3: Implementar**

`drone/base_talhoes.py`:
```python
"""Base de Talhões do dia (Talhoes_da_Pedra_DD_MM_AAAA_fme.shp), fonte oficial da geometria."""
import datetime
import glob
import os
import re
from pathlib import Path

import pyogrio
from shapely.validation import make_valid

from drone.config import CRS_TRABALHO
from drone.erros import ErroGeracao

DATA_NO_NOME = re.compile(r'_(\d{2})_(\d{2})_(\d{4})_fme\.shp$', re.IGNORECASE)


def arquivo_mais_recente(pasta: str, padrao: str) -> tuple:
    candidatos = []
    for caminho in glob.glob(os.path.join(pasta, padrao)):
        m = DATA_NO_NOME.search(caminho)
        if m:
            dia, mes, ano = map(int, m.groups())
            candidatos.append((datetime.date(ano, mes, dia), Path(caminho)))
    if not candidatos:
        raise ErroGeracao(f'Nenhum arquivo da Base de Talhões ({padrao}) em {pasta}.')
    return max(candidatos)


def talhoes_da_fazenda(caminho: Path, cod_faz: int):
    try:
        gdf = pyogrio.read_dataframe(caminho, columns=['SECAO', 'TALHAO', 'AREA_PROD'],
                                     where=f'SECAO = {int(cod_faz)}', encoding='utf-8')
    except Exception as e:  # rede fora, arquivo corrompido
        raise ErroGeracao(f'Não foi possível ler a Base de Talhões ({caminho.name}): {e}') from e
    gdf = gdf[gdf.geometry.notna()]
    if gdf.empty:
        raise ErroGeracao(f'A fazenda {cod_faz} não tem talhões na Base de Talhões ({caminho.name}).')
    gdf = gdf.to_crs(CRS_TRABALHO)
    gdf['geometry'] = gdf.geometry.apply(make_valid)
    gdf['TALHAO'] = gdf['TALHAO'].astype(float).astype(int)
    gdf['AREA_PROD'] = gdf['AREA_PROD'].astype(float)
    return gdf[['TALHAO', 'AREA_PROD', 'geometry']].reset_index(drop=True)
```

`drone/insumos.py`:
```python
"""Leitura de shapefiles enviados (obstáculos, infestação) e classe pelo nome do arquivo."""
import re
import unicodedata
from pathlib import Path

import geopandas as gpd
from shapely.validation import make_valid

from drone.config import CRS_TRABALHO
from drone.erros import ErroGeracao

CLASSES = (15, 25, 50)


def ler_shapefile(caminho: Path) -> list:
    caminho = Path(caminho)
    if not caminho.with_suffix('.prj').exists():
        raise ErroGeracao(f'O arquivo {caminho.name} veio sem o .prj (sistema de coordenadas).')
    gdf = gpd.read_file(caminho)
    if gdf.crs is None:
        raise ErroGeracao(f'O arquivo {caminho.name} tem um sistema de coordenadas desconhecido.')
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].to_crs(CRS_TRABALHO)
    return [make_valid(g) for g in gdf.geometry]


def classe_pelo_nome(nome: str) -> int | None:
    s = unicodedata.normalize('NFD', Path(nome).stem).encode('ascii', 'ignore').decode().lower()
    m = re.search(r'(\d+)\s*m(?![a-z])', s) or re.search(r'(\d+)$', s)
    if not m:
        return None
    valor = int(m.group(1))
    return valor if valor in CLASSES else None
```

- [ ] **Passo 4: Rodar os testes**

Rodar: `python -m pytest tests/drone/test_base_talhoes.py tests/drone/test_insumos.py -v`
Esperado: 13 passed

- [ ] **Passo 5: Commit**

```bash
git add drone/base_talhoes.py drone/insumos.py tests/drone/test_base_talhoes.py tests/drone/test_insumos.py
git commit -m "Drone: leitura da Base de Talhões e dos shapefiles de insumo"
```

---

### Tarefa 4: Shapefile de aplicação e `.zip`

**Arquivos:**
- Criar: `drone/saida.py`, `tests/drone/test_saida.py`

**Interfaces produzidas:**
- `drone.saida.CAMPO_TAXA = 'Taxa l/ha'`, `CAMPO_AREA = 'Área Apli'`
- `drone.saida.gravar_aplicacao(area: MultiPolygon, taxa: int, pasta: Path, cod_faz: int) -> Path`: grava `pasta/{cod_faz}.shp` em 4326, 1 feição; a área é calculada da geometria em 31983 e arredondada para 2 casas
- `drone.saida.montar_zip(shp: Path, destino: Path) -> Path`

- [ ] **Passo 1: Escrever os testes**

`tests/drone/test_saida.py`:
```python
import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import MultiPolygon, box

from drone.saida import CAMPO_AREA, CAMPO_TAXA, gravar_aplicacao, montar_zip


def _area():
    return MultiPolygon([box(200000, 7550000, 200100, 7550100), box(200300, 7550000, 200400, 7550050)])


def test_shape_de_aplicacao_no_padrao(tmp_path):
    shp = gravar_aplicacao(_area(), 10, tmp_path, 10156)
    assert shp.name == '10156.shp'
    g = gpd.read_file(shp)
    assert len(g) == 1
    assert g.crs.to_epsg() == 4326
    assert list(g.columns) == [CAMPO_TAXA, CAMPO_AREA, 'geometry']
    assert g.loc[0, CAMPO_TAXA] == 10
    assert g.loc[0, CAMPO_AREA] == pytest.approx(1.5)
    assert shp.with_suffix('.cpg').read_text().strip().upper() in ('UTF-8', 'UTF8')


def test_zip_so_com_as_partes_do_shape_na_raiz(tmp_path):
    shp = gravar_aplicacao(_area(), 10, tmp_path / 'x', 10156)
    (shp.parent / '10156.qmd').write_text('lixo')
    z = montar_zip(shp, tmp_path / 'saida.zip')
    with zipfile.ZipFile(z) as f:
        assert sorted(f.namelist()) == ['10156.cpg', '10156.dbf', '10156.prj', '10156.shp', '10156.shx']
```

- [ ] **Passo 2: Rodar para ver falhar**

Rodar: `python -m pytest tests/drone/test_saida.py -v`
Esperado: FAIL com `ModuleNotFoundError`

- [ ] **Passo 3: Implementar `drone/saida.py`**

```python
"""Entrega para o piloto: shapefile de aplicação (WGS84, 1 feição) e .zip só com ele."""
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon

from drone.config import CRS_SAIDA, CRS_TRABALHO

CAMPO_TAXA = 'Taxa l/ha'
CAMPO_AREA = 'Área Apli'   # 10 bytes em UTF-8: cabe no limite do .dbf
PARTES = ('.shp', '.shx', '.dbf', '.prj', '.cpg')


def gravar_aplicacao(area: MultiPolygon, taxa: int, pasta: Path, cod_faz: int) -> Path:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame({CAMPO_TAXA: [int(taxa)], CAMPO_AREA: [round(area.area / 1e4, 2)]},
                           geometry=[area], crs=CRS_TRABALHO).to_crs(CRS_SAIDA)
    caminho = pasta / f'{cod_faz}.shp'
    gdf.to_file(caminho, driver='ESRI Shapefile', encoding='UTF-8', engine='pyogrio')
    if not caminho.with_suffix('.cpg').exists():
        caminho.with_suffix('.cpg').write_text('UTF-8')
    return caminho


def montar_zip(shp: Path, destino: Path) -> Path:
    shp, destino = Path(shp), Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as z:
        for ext in PARTES:
            z.write(shp.with_suffix(ext), shp.stem + ext)
    return destino
```

- [ ] **Passo 4: Rodar os testes**

Rodar: `python -m pytest tests/drone/test_saida.py -v`
Esperado: 2 passed

- [ ] **Passo 5: Commit**

```bash
git add drone/saida.py tests/drone/test_saida.py
git commit -m "Drone: shapefile de aplicação WGS84 e zip de entrega"
```

---

### Tarefa 5: Gerador do PDF (layout v6)

**Arquivos:**
- Criar: `drone/mapa_pdf.py`, `tests/drone/test_mapa_pdf.py`

**Interfaces produzidas:**
- `drone.mapa_pdf.DadosMapa` (dataclass): `cod_faz:int, nome:str, tipo:str ('normal'|'catacao'), revisao:int, talhoes:GeoDataFrame (31983), recorte:Recorte, gerado_em:date`
- `drone.mapa_pdf.orientacao(talhoes) -> 'paisagem'|'retrato'`
- `drone.mapa_pdf.safra_de(data: date) -> str` (ex.: 29/09/2026 → `'26/27'`; a safra começa em abril)
- `drone.mapa_pdf.gerar_pdf(dados: DadosMapa, destino: Path) -> str` (devolve a orientação usada)

- [ ] **Passo 1: Escrever os testes**

`tests/drone/test_mapa_pdf.py`:
```python
import datetime
import re

import geopandas as gpd
from shapely.geometry import box

from drone.geometria import recortar, uniao_buffers
from drone.mapa_pdf import DadosMapa, gerar_pdf, orientacao, safra_de


def _talhoes(largura, altura):
    return gpd.GeoDataFrame({'TALHAO': [1, 2], 'AREA_PROD': [10.0, 12.5]},
                            geometry=[box(0, 0, largura / 2, altura), box(largura / 2, 0, largura, altura)],
                            crs=31983)


def _pdf(tmp_path, t, tipo='normal'):
    d = DadosMapa(cod_faz=10156, nome='POSSES', tipo=tipo, revisao=0, talhoes=t,
                  recorte=recortar(t, uniao_buffers({}, {})), gerado_em=datetime.date(2026, 9, 29))
    destino = tmp_path / 'mapa.pdf'
    return gerar_pdf(d, destino), destino.read_bytes()


def _medidas(pdf_bytes):
    m = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)', pdf_bytes)
    return float(m.group(1)), float(m.group(2))


def test_orientacao_pelo_formato():
    assert orientacao(_talhoes(3000, 1000)) == 'paisagem'
    assert orientacao(_talhoes(1000, 3000)) == 'retrato'


def test_safra():
    assert safra_de(datetime.date(2026, 9, 29)) == '26/27'
    assert safra_de(datetime.date(2027, 3, 31)) == '26/27'
    assert safra_de(datetime.date(2027, 4, 1)) == '27/28'


def test_pdf_paisagem_a4(tmp_path):
    orient, b = _pdf(tmp_path, _talhoes(3000, 1000))
    assert orient == 'paisagem' and b.startswith(b'%PDF')
    w, h = _medidas(b)
    assert round(w) == 842 and round(h) == 595


def test_pdf_retrato_a4_catacao(tmp_path):
    orient, b = _pdf(tmp_path, _talhoes(1000, 3000), tipo='catacao')
    assert orient == 'retrato'
    w, h = _medidas(b)
    assert round(w) == 595 and round(h) == 842


def test_pdf_com_muitos_talhoes_nao_quebra(tmp_path):
    t = gpd.GeoDataFrame({'TALHAO': list(range(1, 61)), 'AREA_PROD': [5.0] * 60},
                         geometry=[box(i * 100, 0, i * 100 + 100, 100) for i in range(60)], crs=31983)
    orient, b = _pdf(tmp_path, t)
    assert b.startswith(b'%PDF')
```

- [ ] **Passo 2: Rodar para ver falhar**

Rodar: `python -m pytest tests/drone/test_mapa_pdf.py -v`
Esperado: FAIL com `ModuleNotFoundError`

- [ ] **Passo 3: Implementar `drone/mapa_pdf.py`**

```python
"""PDF do mapa de aplicação — layout v6 (spec, seção 4). Coordenadas da página em mm (origem no topo)."""
import datetime
from dataclasses import dataclass

import geopandas as gpd
import matplotlib

matplotlib.use('Agg')
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon as MplPolygon, Rectangle  # noqa: E402

from drone.config import LOGO  # noqa: E402
from drone.geometria import Recorte  # noqa: E402

MARCA, GRAFITE, CINZA, LINHA = '#138a3e', '#1f2a30', '#6b7479', '#cfd5d8'
CORES = {'normal': ('#a0694b', '#5c3824', '#8a5a3f', 'NORMAL'),
         'catacao': ('#5b8c5a', '#2f5a2e', '#4d7c4c', 'CATAÇÃO')}
MM = 1 / 25.4
plt.rcParams['font.family'] = ['Segoe UI', 'DejaVu Sans']
plt.rcParams['pdf.fonttype'] = 42


@dataclass
class DadosMapa:
    cod_faz: int
    nome: str
    tipo: str
    revisao: int
    talhoes: gpd.GeoDataFrame
    recorte: Recorte
    gerado_em: datetime.date


def orientacao(talhoes) -> str:
    minx, miny, maxx, maxy = talhoes.total_bounds
    return 'paisagem' if (maxx - minx) > (maxy - miny) else 'retrato'


def safra_de(data: datetime.date) -> str:
    ano = data.year if data.month >= 4 else data.year - 1
    return f'{ano % 100:02d}/{(ano + 1) % 100:02d}'


def br(v: float) -> str:
    return f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


class Pagina:
    """Ajuda a desenhar em mm, com y contado a partir do topo da folha."""

    def __init__(self, fig, W, H):
        self.fig, self.W, self.H = fig, W, H

    def eixo(self, x, y, w, h):
        return self.fig.add_axes([x / self.W, 1 - (y + h) / self.H, w / self.W, h / self.H])

    def caixa(self, x, y, w, h, cor_borda=LINHA, fundo='white', raio=1.6, largura=0.6):
        self.fig.patches.append(FancyBboxPatch(
            (x / self.W, 1 - (y + h) / self.H), w / self.W, h / self.H,
            boxstyle=f'round,pad=0,rounding_size={raio / self.W}', transform=self.fig.transFigure,
            facecolor=fundo, edgecolor=cor_borda, linewidth=largura))

    def texto(self, x, y, s, tam=7, cor=GRAFITE, peso='normal', ha='left', va='top', **kw):
        self.fig.text(x / self.W, 1 - y / self.H, s, fontsize=tam, color=cor, fontweight=peso,
                      ha=ha, va=va, **kw)

    def ret(self, x, y, w, h, cor):
        self.fig.patches.append(Rectangle((x / self.W, 1 - (y + h) / self.H), w / self.W, h / self.H,
                                          transform=self.fig.transFigure, color=cor, linewidth=0))


def _mapa(pg: Pagina, d: DadosMapa, x, y, w, h):
    preenche, borda, _, _ = CORES[d.tipo]
    ax = pg.eixo(x, y, w, h)
    minx, miny, maxx, maxy = d.talhoes.total_bounds
    topo, base, lado = 22, 14, 8                      # reserva para logo (cima) e escala (baixo)
    s = min((w - 2 * lado) / (maxx - minx), (h - topo - base) / (maxy - miny))   # mm por metro
    x0 = minx - (lado + ((w - 2 * lado) - (maxx - minx) * s) / 2) / s
    y0 = miny - (base + ((h - topo - base) - (maxy - miny) * s) / 2) / s
    ax.set_xlim(x0, x0 + w / s)
    ax.set_ylim(y0, y0 + h / s)
    ax.set_facecolor('#fbfcfb')
    ax.set_xticks([]), ax.set_yticks([])
    for lado_ax in ax.spines.values():
        lado_ax.set_visible(False)
    d.talhoes.plot(ax=ax, facecolor='white', edgecolor=GRAFITE, linewidth=0.5)
    gpd.GeoSeries([d.recorte.area], crs=d.talhoes.crs).plot(ax=ax, facecolor=preenche, edgecolor=borda,
                                                             linewidth=0.3, alpha=0.92)
    for _, t in d.talhoes.iterrows():
        p = t.geometry.representative_point()
        ax.text(p.x, p.y, str(int(t['TALHAO'])), fontsize=6.5, fontweight='semibold', color=GRAFITE,
                ha='center', va='center', path_effects=[pe.withStroke(linewidth=2, foreground='white')])
    # barra de escala colada no canto inferior esquerdo (sem contorno)
    barra = next(b for b in (100, 250, 500, 1000, 2000, 5000) if b * s >= 25)
    bx, by, alt = x0 + 5 / s, y0 + 3 / s, 1.3 / s
    for i, (ini, fim, cor) in enumerate([(0, .25, GRAFITE), (.25, .5, 'white'), (.5, 1, GRAFITE)]):
        ax.add_patch(Rectangle((bx + ini * barra, by), (fim - ini) * barra, alt, facecolor=cor,
                               edgecolor=GRAFITE, linewidth=0.3))
    for frac, rotulo in [(0, '0'), (.5, str(barra // 2)), (1, f'{barra} m')]:
        ax.text(bx + frac * barra, by + alt * 2.2, rotulo, fontsize=5, color=GRAFITE, ha='center' if frac else 'left')
    # moldura arredondada e logo colado no canto superior esquerdo (sem contorno)
    pg.caixa(x, y, w, h, cor_borda=GRAFITE, fundo='none', raio=3, largura=0.7)
    logo = pg.eixo(x + 2, y + 2, 34, 15)
    logo.imshow(mpimg.imread(LOGO))
    logo.axis('off')
    return round(1000 / s / 500) * 500 or 500


def _tabela(pg: Pagina, d: DadosMapa, x, y, w, h):
    preenche, borda, _, _ = CORES[d.tipo]
    linhas = d.recorte.por_talhao
    alt = min(4.2, (h - 22) / (len(linhas) + 2))
    tam = max(4.0, alt * 1.55)
    pg.texto(x, y, 'ÁREAS POR TALHÃO', 5.5, CINZA, 'semibold')
    cols = [('SEÇÃO', 0.02, 'left'), ('TALHÃO', 0.30, 'right'), ('ÁREA PROD. (ha)', 0.66, 'right'),
            ('APLICÁVEL (ha)', 0.98, 'right')]
    y0 = y + 5
    for nome, fx, ha in cols:
        pg.texto(x + fx * w, y0, nome, 5, MARCA, 'bold', ha=ha)
    pg.ret(x, y0 + 3.4, w, 0.35, GRAFITE)
    yy = y0 + 4.2
    for i, t in enumerate(linhas):
        if i % 2:
            pg.ret(x, yy, w, alt, '#f4f6f5')
        for valor, (_, fx, ha) in zip([str(d.cod_faz), str(t['talhao']), br(t['area_prod']), br(t['aplicavel_ha'])], cols):
            pg.texto(x + fx * w, yy + alt * 0.15, valor, tam, ha=ha)
        yy += alt
    pg.ret(x, yy + 0.3, w, 0.35, GRAFITE)
    for valor, (_, fx, ha) in zip(['Total', '', br(d.recorte.area_total_ha), br(d.recorte.aplicacao_ha)], cols):
        pg.texto(x + fx * w, yy + 1.2, valor, tam, peso='bold', ha=ha)
    yy += alt + 3
    pg.ret(x, yy, 5, 3, 'white'), pg.caixa(x, yy, 5, 3, GRAFITE, 'white', 0.3, 0.4)
    pg.texto(x + 6.5, yy - 0.2, 'Talhão', 5.5, CINZA)
    pg.caixa(x + 22, yy, 5, 3, borda, preenche, 0.3, 0.4)
    pg.texto(x + 28.5, yy - 0.2, 'Área de aplicação', 5.5, CINZA)


def _carimbo(pg: Pagina, d: DadosMapa, x, y, w, escala):
    _, _, cor_tag, rotulo = CORES[d.tipo]
    pg.ret(x, y, 0.9, 16, MARCA)
    pg.caixa(x + 3, y, 16, 3.6, cor_tag, cor_tag, 0.5, 0.1)
    pg.texto(x + 11, y + 0.5, rotulo, 4.5, 'white', 'bold', ha='center')
    pg.texto(x + 3, y + 5, f'{d.cod_faz} · {d.nome}', 12, peso='bold')
    pg.texto(x + 3, y + 11.5, 'MAPA DE APLICAÇÃO · DRONE', 5.5, CINZA)
    y += 19
    meia = (w - 3) / 2
    pct = d.recorte.aplicacao_ha / d.recorte.area_total_ha * 100 if d.recorte.area_total_ha else 0
    for i, (titulo, valor, extra, destaque) in enumerate([
            ('ÁREA DE APLICAÇÃO', d.recorte.aplicacao_ha, f'{br(pct)}% da área', True),
            ('ÁREA TOTAL', d.recorte.area_total_ha, f'{len(d.recorte.por_talhao)} talhões', False)]):
        cx = x + i * (meia + 3)
        pg.caixa(cx, y, meia, 15, '#b9dcc4' if destaque else LINHA, '#f1f8f3' if destaque else 'white')
        pg.texto(cx + 2.5, y + 1.8, titulo, 4.8, CINZA, 'semibold')
        pg.texto(cx + 2.5, y + 5, f'{br(valor)}', 12, MARCA if destaque else GRAFITE, 'bold')
        pg.texto(cx + meia - 2.5, y + 6.8, 'ha', 5.5, CINZA, 'semibold', ha='right')
        pg.texto(cx + 2.5, y + 11.2, extra, 5, CINZA)
    y += 18
    pg.caixa(x, y, w, 10)
    celula = (w - 14) / 3
    for i, (titulo, valor) in enumerate([('ESCALA', f'1:{escala:,}'.replace(',', '.')),
                                         ('SAFRA', safra_de(d.gerado_em)), ('REVISÃO', f'Rev{d.revisao}')]):
        cx = x + i * celula
        if i:
            pg.ret(cx, y + 1.5, 0.25, 7, LINHA)
        pg.texto(cx + 2.5, y + 1.8, titulo, 4.5, CINZA, 'semibold')
        pg.texto(cx + 2.5, y + 4.8, valor, 7, peso='semibold')
    nx, ny = x + w - 7, y + 1.3            # seta de norte desenhada
    for pts, cor in [([(0, 0), (2.4, 6), (0, 4.8), (-2.4, 6)], GRAFITE), ([(0, 0), (0, 4.8), (-2.4, 6)], CINZA)]:
        pg.fig.patches.append(MplPolygon([((nx + px) / pg.W, 1 - (ny + py) / pg.H) for px, py in pts],
                                         closed=True, transform=pg.fig.transFigure, color=cor, linewidth=0))
    pg.texto(nx, ny + 6.4, 'N', 5.5, peso='bold', ha='center')
    y += 13
    pg.ret(x, y, w, 0.2, LINHA)
    pg.texto(x, y + 1.2, 'Pedra Agroindustrial S/A · Geotecnologia', 4.8, CINZA)
    pg.texto(x + w, y + 1.2, f'Gerado em {d.gerado_em:%d/%m/%Y}', 4.8, CINZA, ha='right')


ALTURA_CARIMBO = 66


def gerar_pdf(d: DadosMapa, destino) -> str:
    orient = orientacao(d.talhoes)
    W, H = (297, 210) if orient == 'paisagem' else (210, 297)
    fig = plt.figure(figsize=(W * MM, H * MM))
    pg = Pagina(fig, W, H)
    pg.ret(0, 0, W, 4, MARCA)                                   # faixa da marca no topo
    M = 10
    if orient == 'paisagem':
        mw = W * 0.63
        escala = _mapa(pg, d, M, M, mw, H - 2 * M)
        px, pw = M + mw + 7, W - (M + mw + 7) - M
        _tabela(pg, d, px, M, pw, H - 2 * M - ALTURA_CARIMBO - 6)
        _carimbo(pg, d, px, H - M - ALTURA_CARIMBO, pw, escala)
    else:
        mh = H - 2 * M - ALTURA_CARIMBO - 8
        escala = _mapa(pg, d, M, M, W - 2 * M, mh)
        cw = (W - 2 * M - 8) / 2
        _tabela(pg, d, M, M + mh + 8, cw, ALTURA_CARIMBO)
        _carimbo(pg, d, M + cw + 8, M + mh + 8, cw, escala)
    fig.savefig(destino, format='pdf')
    plt.close(fig)
    return orient
```

- [ ] **Passo 4: Rodar os testes**

Rodar: `python -m pytest tests/drone/test_mapa_pdf.py -v`
Esperado: 5 passed

- [ ] **Passo 5: Aprovação visual com dados reais (ponto de checagem humana)**

Criar `drone/amostra_pdf.py` (fica no repositório; serve para regenerar amostras):
```python
"""Gera PDFs de amostra a partir de projetos reais do G:\\ para comparar com a maquete v6.
Uso: python -m drone.amostra_pdf <shp_base_talhoes> <cod_faz> <nome> <normal|catacao> <shp_aplicacao> <saida.pdf>"""
import datetime
import sys
from pathlib import Path

import geopandas as gpd

from drone.base_talhoes import talhoes_da_fazenda
from drone.geometria import recortar, uniao_buffers
from drone.mapa_pdf import DadosMapa, gerar_pdf

base, cod, nome, tipo, aplic, saida = sys.argv[1:7]
t = talhoes_da_fazenda(Path(base), int(cod))
infest = list(gpd.read_file(aplic).to_crs(31983).geometry)
r = recortar(t, uniao_buffers({}, {}), infestacao=infest, margem=0)
print(gerar_pdf(DadosMapa(int(cod), nome, tipo, 0, t, r, datetime.date.today()), saida))
```

Rodar as duas amostras e abrir:
```bash
python -m drone.amostra_pdf "C:/Users/lmalerbo/Documents/catalogo_drone_revisar/base de fazendas/Talhoes_da_Pedra_28_09_2026_fme.shp" 10156 POSSES normal "G:/GeoProc/GEOTECNOLOGIA/08 PROJETOS PILOTO AUTOMATICO/15 PROPRIO/FAZENDAS/10156 POSSES/2026-2027/02 PROJETO/02 DEPT TECNICO/01 DRONE/01 TOTAL/Rev0/10156.shp" drone/trabalho/amostra_10156.pdf
python -m drone.amostra_pdf "C:/Users/lmalerbo/Documents/catalogo_drone_revisar/base de fazendas/Talhoes_da_Pedra_28_09_2026_fme.shp" 10372 "SAO JOSE 18" catacao "G:/GeoProc/GEOTECNOLOGIA/08 PROJETOS PILOTO AUTOMATICO/15 PROPRIO/FAZENDAS/10372 SAO JOSE 18/2024-2025/02 PROJETO/99 GERAL/Rev0/10372 - H.shp" drone/trabalho/amostra_10372.pdf
```
Esperado: `paisagem` e `retrato`. **Mostrar os dois PDFs ao usuário ao lado da maquete v6 e só seguir com a aprovação dele.** Ajustes pedidos entram neste mesmo passo (posições em mm nas funções `_mapa`/`_tabela`/`_carimbo`) e os testes são rodados de novo.

- [ ] **Passo 6: Commit**

```bash
git add drone/mapa_pdf.py drone/amostra_pdf.py tests/drone/test_mapa_pdf.py drone/assets/logo-pedra.png
git commit -m "Drone: gerador do PDF do mapa (layout v6, orientação automática)"
```

---

### Tarefa 6: Acesso ao banco e ao Storage (`DroneBanco`)

**Arquivos:**
- Criar: `drone/banco.py`

**Interfaces consumidas:** `ingestao/comum.py` → `Hub` (`selecionar`, `inserir`, `atualizar`, `rpc`, `url`, `headers`), `carregar_env`.

**Interfaces produzidas** (`DroneBanco(Hub)`):
- `parametros() -> dict[str, str]`, `distancias() -> dict[int, float]`, `batimento() -> None`
- `fazenda(cod_faz) -> dict` (`cod_faz`, `nome`)
- `obstaculos_vigentes(cod_faz) -> tuple[dict[int, list[BaseGeometry]], list[dict]]` (geometrias por classe + versões `{classe_m, versao_id, enviado_em}`)
- `infestacao(infestacao_id) -> list[BaseGeometry]`
- `ultima_infestacao(solicitacao_id) -> int | None`
- `solicitacao(id) -> dict`, `criar_solicitacao(cod_faz, tipo, origem, status=None, data_desejada=None) -> dict`
- `pedir_geracao(solicitacao_id, infestacao_id=None) -> dict`, `pegar_geracao() -> dict | None`, `concluir_geracao(id, **campos) -> None`
- `pedir_publicacao(geracao_id, motivo=None) -> None`, `pegar_publicacao() -> dict | None`, `erro_publicacao(id, msg) -> None`
- `gravar_obstaculos(cod_faz, classe_m, origem, arquivo, geoms) -> int`, `gravar_infestacao(solicitacao_id, empresa, arquivo, geoms) -> int`
- `subir_previa(caminho: Path, destino: str) -> str`, `baixar_previa(destino: str, caminho: Path) -> Path`, `apagar_previas(destinos: list[str]) -> None`
- `projeto_individual(cod_faz, nome) -> int`, `nova_revisao(projeto_id, documento, motivo) -> dict` (`id`, `numero`), `arquivos_da_revisao(revisao_id) -> list[str]`, `registrar_arquivo(revisao_id, nome, url, tamanho) -> None`, `concluir_publicacao(geracao_id, revisao_id) -> None`, `revisao_vigente(projeto_id, documento) -> dict | None`

(Sem teste automático: é um adaptador fino de HTTP. Ele é exercitado de ponta a ponta na Tarefa 12.)

- [ ] **Passo 1: Implementar `drone/banco.py`**

```python
"""Chamadas do módulo Drone ao schema hub (service_role) e ao Supabase Storage."""
import sys
from pathlib import Path

import requests
from shapely import wkt as shapely_wkt

from drone.config import RAIZ

sys.path.insert(0, str(RAIZ / 'ingestao'))
from comum import Hub, agora_iso, carregar_env  # noqa: E402,F401  (carregar_env é reexportado para o agente)

BUCKET = 'drone-previas'


class DroneBanco(Hub):
    def __init__(self):
        super().__init__()
        self.storage = self.url.replace('/rest/v1', '/storage/v1')

    # ── parâmetros e sinal de vida ──────────────────────────────────
    def parametros(self) -> dict:
        return {p['chave']: p['valor'] for p in self.selecionar('drone_parametros', 'chave,valor')}

    def distancias(self) -> dict:
        return {c['classe_m']: float(c['distancia_m'])
                for c in self.selecionar('drone_classes_restricao', 'classe_m,distancia_m')}

    def batimento(self):
        self.atualizar('drone_parametros', {'chave': 'eq.agente_ultimo_ciclo'},
                       {'valor': agora_iso(), 'atualizado_em': agora_iso()})

    # ── leitura ─────────────────────────────────────────────────────
    def fazenda(self, cod_faz) -> dict:
        r = self.selecionar('fazendas', 'cod_faz,nome', {'cod_faz': f'eq.{cod_faz}'})
        if not r:
            raise RuntimeError(f'Fazenda {cod_faz} não existe em hub.fazendas')
        return r[0]

    def obstaculos_vigentes(self, cod_faz):
        linhas = self.rpc('drone_obstaculos_vigentes', {'p_cod_faz': cod_faz}) or []
        geoms, versoes = {}, {}
        for l in linhas:
            geoms.setdefault(l['classe_m'], []).append(shapely_wkt.loads(l['wkt']))
            versoes[l['versao_id']] = {'classe_m': l['classe_m'], 'versao_id': l['versao_id'],
                                       'enviado_em': l['enviado_em']}
        return geoms, list(versoes.values())

    def infestacao(self, infestacao_id) -> list:
        return [shapely_wkt.loads(l['wkt'])
                for l in self.rpc('drone_infestacao_wkt', {'p_infestacao_id': infestacao_id}) or []]

    def ultima_infestacao(self, solicitacao_id):
        r = self.selecionar('drone_infestacoes', 'id',
                            {'solicitacao_id': f'eq.{solicitacao_id}', 'order': 'id.desc', 'limit': '1'})
        return r[0]['id'] if r else None

    def solicitacao(self, id_) -> dict:
        return self.selecionar('drone_solicitacoes', '*', {'id': f'eq.{id_}'})[0]

    # ── escrita ─────────────────────────────────────────────────────
    def criar_solicitacao(self, cod_faz, tipo, origem, status=None, data_desejada=None) -> dict:
        linha = {'cod_faz': cod_faz, 'tipo': tipo, 'origem': origem, 'data_desejada': data_desejada}
        if status:
            linha['status'] = status
        return self.inserir('drone_solicitacoes', linha)

    def pedir_geracao(self, solicitacao_id, infestacao_id=None) -> dict:
        self.atualizar('drone_solicitacoes', {'id': f'eq.{solicitacao_id}', 'status': 'eq.solicitado'},
                       {'status': 'em_elaboracao', 'iniciado_em': agora_iso()})
        return self.inserir('drone_geracoes', {'solicitacao_id': solicitacao_id, 'infestacao_id': infestacao_id})

    def pegar_geracao(self):
        r = self.rpc('drone_pegar_geracao')
        return r[0] if r else None

    def concluir_geracao(self, id_, **campos):
        self.atualizar('drone_geracoes', {'id': f'eq.{id_}'}, {'concluido_em': agora_iso(), **campos})

    def pedir_publicacao(self, geracao_id, motivo=None):
        self.atualizar('drone_geracoes', {'id': f'eq.{geracao_id}', 'status': 'eq.pronta'},
                       {'publicar_pedido_em': agora_iso(), 'publicar_motivo': motivo, 'publicacao_erro': None})

    def pegar_publicacao(self):
        r = self.rpc('drone_pegar_publicacao')
        return r[0] if r else None

    def erro_publicacao(self, id_, msg):
        self.atualizar('drone_geracoes', {'id': f'eq.{id_}'},
                       {'publicacao_erro': msg[:1000], 'publicacao_iniciada_em': None})

    def gravar_obstaculos(self, cod_faz, classe_m, origem, arquivo, geoms) -> int:
        return self.rpc('drone_gravar_obstaculos', {
            'p_cod_faz': cod_faz, 'p_classe_m': classe_m, 'p_origem': origem, 'p_arquivo': arquivo,
            'p_wkts': [g.wkt for g in geoms]})

    def gravar_infestacao(self, solicitacao_id, empresa, arquivo, geoms) -> int:
        return self.rpc('drone_gravar_infestacao', {
            'p_solicitacao_id': solicitacao_id, 'p_empresa': empresa, 'p_arquivo': arquivo,
            'p_wkts': [g.wkt for g in geoms]})

    # ── projeto e revisões (tabelas existentes do Hub) ──────────────
    def projeto_individual(self, cod_faz, nome) -> int:
        r = self.selecionar('projetos', 'id', {'modulo_id': 'eq.drone', 'tipo': 'eq.individual',
                                               'cod_faz': f'eq.{cod_faz}'})
        if r:
            return r[0]['id']
        return self.inserir('projetos', {'modulo_id': 'drone', 'tipo': 'individual',
                                         'cod_faz': cod_faz, 'nome': nome})['id']

    def revisao_vigente(self, projeto_id, documento):
        r = self.selecionar('projeto_revisoes', 'id,numero,motivo',
                            {'projeto_id': f'eq.{projeto_id}', 'documento': f'eq.{documento}', 'vigente': 'is.true'})
        return r[0] if r else None

    def nova_revisao(self, projeto_id, documento, motivo) -> dict:
        rev_id = self.rpc('nova_revisao', {'p_projeto_id': projeto_id, 'p_documento': documento,
                                            'p_motivo': motivo, 'p_origens': None})
        return self.selecionar('projeto_revisoes', 'id,numero', {'id': f'eq.{rev_id}'})[0]

    def arquivos_da_revisao(self, revisao_id) -> list:
        return [a['nome_arquivo'] for a in self.selecionar('revisao_arquivos', 'nome_arquivo',
                                                           {'revisao_id': f'eq.{revisao_id}'})]

    def registrar_arquivo(self, revisao_id, nome, url, tamanho):
        self.upsert('revisao_arquivos', [{'revisao_id': revisao_id, 'nome_arquivo': nome,
                                          'release_url': url, 'tamanho_bytes': tamanho}],
                    'revisao_id,nome_arquivo')

    def concluir_publicacao(self, geracao_id, revisao_id):
        self.rpc('drone_concluir_publicacao', {'p_geracao_id': geracao_id, 'p_revisao_id': revisao_id})

    # ── Storage (prévias) ───────────────────────────────────────────
    def _storage_headers(self):
        return {'apikey': self.headers['apikey'], 'Authorization': self.headers['Authorization']}

    def subir_previa(self, caminho: Path, destino: str) -> str:
        r = requests.post(f'{self.storage}/object/{BUCKET}/{destino}', data=Path(caminho).read_bytes(),
                          headers={**self._storage_headers(), 'x-upsert': 'true',
                                   'Content-Type': 'application/octet-stream'}, timeout=120)
        self._checar(r, 'storage')
        return destino

    def baixar_previa(self, destino: str, caminho: Path) -> Path:
        r = requests.get(f'{self.storage}/object/{BUCKET}/{destino}', headers=self._storage_headers(), timeout=120)
        self._checar(r, 'storage')
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        Path(caminho).write_bytes(r.content)
        return Path(caminho)

    def apagar_previas(self, destinos: list):
        destinos = [d for d in destinos if d]
        if destinos:
            r = requests.delete(f'{self.storage}/object/{BUCKET}', json={'prefixes': destinos},
                                headers=self._storage_headers(), timeout=60)
            self._checar(r, 'storage')
```

- [ ] **Passo 2: Checagem rápida (sem gravar)**

Rodar: `python -c "from drone.banco import DroneBanco; b=DroneBanco(); print(b.parametros()['taxa_l_ha'], b.distancias())"`
Esperado: `10 {15: 15.0, 25: 25.0, 50: 50.0}`

- [ ] **Passo 3: Commit**

```bash
git add drone/banco.py
git commit -m "Drone: acesso ao banco e ao Storage (DroneBanco)"
```

---

### Tarefa 7: Publicação no GitHub Releases

**Arquivos:**
- Criar: `drone/publicacao.py`, `tests/drone/test_publicacao.py`

**Interfaces consumidas:** `DroneBanco` (Tarefa 6): `fazenda`, `projeto_individual`, `revisao_vigente`, `nova_revisao`, `registrar_arquivo`.

**Interfaces produzidas:**
- `drone.publicacao.nome_fazenda_arquivo(nome: str) -> str`
- `drone.publicacao.nome_arquivo(cod_faz, nome, numero, documento, ext) -> str`
- `drone.publicacao.GitHubReleases(token: str, repo: str)` com `release(tag, titulo) -> dict` e `subir(release: dict, caminho: Path, nome: str) -> tuple[str, int]` (URL, tamanho). É idempotente: se o asset com o mesmo nome já existe, reaproveita.
- `drone.publicacao.publicar(banco, gh, cod_faz, documento, motivo, arquivos: dict[str, Path]) -> int` (revisao_id; `arquivos` = `{'zip': Path, 'pdf': Path | None}`)
- `drone.publicacao.SUFIXO = {'normal': '-Normal', 'catacao': '-Catacao'}`

- [ ] **Passo 1: Escrever os testes**

`tests/drone/test_publicacao.py`:
```python
from pathlib import Path

import pytest

from drone.publicacao import GitHubReleases, nome_arquivo, nome_fazenda_arquivo, publicar


def test_nome_da_fazenda_igual_ao_worker():
    assert nome_fazenda_arquivo('VISCONDE DO PARNAÍBA 3') == 'VISCONDE.DO.PARNAIBA.3'
    assert nome_fazenda_arquivo('SANTO AGOSTINHO (STO ANTON. 9)') == 'SANTO.AGOSTINHO.STO.ANTON.9'


def test_nome_do_arquivo():
    assert nome_arquivo(10156, 'POSSES', 2, 'catacao', 'zip') == '10156_POSSES_Rev2-Catacao.zip'


class _Resposta:
    def __init__(self, status, dados):
        self.status_code, self._dados = status, dados
        self.ok = status < 400

    def json(self):
        return self._dados


def test_subir_reaproveita_asset_existente(monkeypatch, tmp_path):
    chamadas = []
    monkeypatch.setattr('drone.publicacao.requests.post', lambda *a, **k: chamadas.append(a) or _Resposta(201, {}))
    gh = GitHubReleases('t', 'dono/repo')
    arq = tmp_path / 'a.zip'
    arq.write_bytes(b'x')
    rel = {'id': 1, 'assets': [{'name': 'a.zip', 'browser_download_url': 'https://x/a.zip', 'size': 1}]}
    assert gh.subir(rel, arq, 'a.zip') == ('https://x/a.zip', 1)
    assert chamadas == []


class _BancoFalso:
    """Revisões de um único projeto/documento; a última é a vigente."""
    def __init__(self):
        self.revisoes, self.arquivos = [], []   # revisoes: [{'id', 'numero', 'motivo'}]

    def fazenda(self, cod):
        return {'cod_faz': cod, 'nome': 'POSSES'}

    def projeto_individual(self, cod, nome):
        return 7

    def revisao_vigente(self, projeto_id, documento):
        return self.revisoes[-1] if self.revisoes else None

    def nova_revisao(self, projeto_id, documento, motivo):
        if self.revisoes and not motivo:
            raise RuntimeError('motivo obrigatório')
        rev = {'id': 11 + len(self.revisoes), 'numero': len(self.revisoes), 'motivo': motivo}
        self.revisoes.append(rev)
        return rev

    def arquivos_da_revisao(self, revisao_id):
        return [nome for r, nome in self.arquivos if r == revisao_id]

    def registrar_arquivo(self, revisao_id, nome, url, tamanho):
        self.arquivos.append((revisao_id, nome))


class _GhFalso:
    def __init__(self, falhar_em=None):
        self.falhar_em = falhar_em

    def release(self, tag, titulo):
        assert tag == 'drone-10156'
        return {'id': 1, 'assets': []}

    def subir(self, rel, caminho, nome):
        if self.falhar_em and nome.endswith(self.falhar_em):
            raise RuntimeError('GitHub fora')
        return f'https://x/{nome}', 1


def _arquivos(tmp_path, pdf=True):
    zip_, pdf_ = tmp_path / 'p.zip', tmp_path / 'p.pdf'
    zip_.write_bytes(b'z')
    pdf_.write_bytes(b'p')
    return {'zip': zip_, 'pdf': pdf_ if pdf else None}


def test_publicar_cria_rev0_e_registra_zip_e_pdf(tmp_path):
    b = _BancoFalso()
    rev = publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path))
    assert rev == 11
    assert b.arquivos == [(11, '10156_POSSES_Rev0-Normal.zip'), (11, '10156_POSSES_Rev0-Normal.pdf')]


def test_catacao_nova_revisao_usa_motivo_padrao(tmp_path):
    b = _BancoFalso()
    publicar(b, _GhFalso(), 10156, 'catacao', None, _arquivos(tmp_path, pdf=False))
    publicar(b, _GhFalso(), 10156, 'catacao', None, _arquivos(tmp_path, pdf=False))
    assert b.revisoes[-1]['motivo'] == 'Novo levantamento de infestação'
    assert b.revisoes[-1]['numero'] == 1


def test_normal_nova_revisao_sem_motivo_da_erro(tmp_path):
    b = _BancoFalso()
    publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path))
    with pytest.raises(RuntimeError, match='motivo'):
        publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path))


def test_repetir_depois_de_falha_no_github_reaproveita_a_revisao(tmp_path):
    b = _BancoFalso()
    with pytest.raises(RuntimeError, match='GitHub'):
        publicar(b, _GhFalso(falhar_em='.pdf'), 10156, 'normal', None, _arquivos(tmp_path))
    rev = publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path))
    assert len(b.revisoes) == 1 and rev == 11
    assert sorted(b.arquivos_da_revisao(11)) == ['10156_POSSES_Rev0-Normal.pdf', '10156_POSSES_Rev0-Normal.zip']
```

- [ ] **Passo 2: Rodar para ver falhar**

Rodar: `python -m pytest tests/drone/test_publicacao.py -v`
Esperado: FAIL com `ModuleNotFoundError`

- [ ] **Passo 3: Implementar `drone/publicacao.py`**

```python
"""Publicação de uma revisão do projeto de drone no GitHub Releases (mesmo padrão do worker/arquivos.js)."""
import re
import unicodedata
from pathlib import Path

import requests

SUFIXO = {'normal': '-Normal', 'catacao': '-Catacao'}
MOTIVO_PADRAO = {'catacao': 'Novo levantamento de infestação'}


def nome_fazenda_arquivo(nome: str) -> str:
    s = unicodedata.normalize('NFD', nome).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'[^A-Z0-9]+', '.', s).strip('.')


def nome_arquivo(cod_faz, nome, numero, documento, ext) -> str:
    return f'{cod_faz}_{nome_fazenda_arquivo(nome)}_Rev{numero}{SUFIXO[documento]}.{ext}'


class GitHubReleases:
    def __init__(self, token: str, repo: str):
        self.repo = repo
        self.h = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                  'User-Agent': 'hub-geotech-drone'}

    def release(self, tag: str, titulo: str) -> dict:
        r = requests.get(f'https://api.github.com/repos/{self.repo}/releases/tags/{tag}', headers=self.h, timeout=60)
        if r.status_code == 404:
            r = requests.post(f'https://api.github.com/repos/{self.repo}/releases', headers=self.h, timeout=60,
                              json={'tag_name': tag, 'name': titulo, 'body': 'Arquivos publicados pelo Hub Geotech.'})
        if not r.ok:
            raise RuntimeError(f'GitHub: não foi possível abrir a release {tag} ({r.status_code})')
        return r.json()

    def subir(self, release: dict, caminho: Path, nome: str) -> tuple:
        existente = next((a for a in release.get('assets', []) if a['name'] == nome), None)
        if existente:   # reenvio depois de falha: o arquivo já é desta revisão
            return existente['browser_download_url'], existente['size']
        r = requests.post(f'https://uploads.github.com/repos/{self.repo}/releases/{release["id"]}/assets',
                          params={'name': nome}, data=Path(caminho).read_bytes(), timeout=300,
                          headers={**self.h, 'Content-Type': 'application/octet-stream'})
        if not r.ok:
            raise RuntimeError(f'GitHub: falha ao subir {nome} ({r.status_code})')
        a = r.json()
        return a['browser_download_url'], a['size']


def _nomes(cod_faz, nome, numero, documento, arquivos) -> dict:
    return {ext: nome_arquivo(cod_faz, nome, numero, documento, ext) for ext in ('zip', 'pdf') if arquivos.get(ext)}


def publicar(banco, gh, cod_faz, documento, motivo, arquivos: dict) -> int:
    faz = banco.fazenda(cod_faz)
    projeto = banco.projeto_individual(cod_faz, faz['nome'])
    vigente = banco.revisao_vigente(projeto, documento)
    rev = None
    if vigente:
        # publicação anterior interrompida (revisão aberta, arquivos faltando): continua nela
        ja = set(banco.arquivos_da_revisao(vigente['id']))
        if ja < set(_nomes(cod_faz, faz['nome'], vigente['numero'], documento, arquivos).values()):
            rev = vigente
        elif not (motivo or '').strip():
            motivo = MOTIVO_PADRAO.get(documento)
            if not motivo:
                raise RuntimeError('Informe o motivo da nova revisão do projeto Normal.')
    if rev is None:
        rev = banco.nova_revisao(projeto, documento, motivo)
    release = gh.release(f'drone-{cod_faz}', f'{faz["nome"]} — drone')
    for ext, nome in _nomes(cod_faz, faz['nome'], rev['numero'], documento, arquivos).items():
        url, tamanho = gh.subir(release, arquivos[ext], nome)
        banco.registrar_arquivo(rev['id'], nome, url, tamanho)   # upsert: repetir não duplica
    return rev['id']
```

- [ ] **Passo 4: Rodar os testes**

Rodar: `python -m pytest tests/drone/test_publicacao.py -v`
Esperado: 7 passed

- [ ] **Passo 5: Commit**

```bash
git add drone/publicacao.py tests/drone/test_publicacao.py
git commit -m "Drone: publicação da revisão no GitHub Releases"
```

---

### Tarefa 8: Processamento de uma geração (`gerador.py`)

**Arquivos:**
- Criar: `drone/gerador.py`, `tests/drone/test_gerador.py`

**Interfaces consumidas:** `talhoes_da_fazenda`, `arquivo_mais_recente` (Tarefa 3); `uniao_buffers`, `recortar` (Tarefa 2); `gravar_aplicacao`, `montar_zip` (Tarefa 4); `DadosMapa`, `gerar_pdf` (Tarefa 5); métodos do `DroneBanco` (Tarefa 6).

**Interfaces produzidas:**
- `drone.gerador.alertas(recorte, versoes, params, hoje, infestacao_fora: bool) -> list[str]`
- `drone.gerador.processar(geracao: dict, banco, base: tuple[date, Path], pasta: Path, hoje: date) -> dict`. Devolve os campos para `concluir_geracao`: `status='pronta'`, `orientacao`, `insumos`, `resumo`, `alertas`, `previa_pdf`, `previa_zip`. Lança `ErroGeracao`.

- [ ] **Passo 1: Escrever os testes (com banco falso)**

`tests/drone/test_gerador.py`:
```python
import datetime
import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from drone.erros import ErroGeracao
from drone.gerador import processar


@pytest.fixture
def base(tmp_path):
    gdf = gpd.GeoDataFrame({'SECAO': [10156, 10156], 'TALHAO': [1.0, 2.0], 'AREA_PROD': [1.0, 1.0]},
                           geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)], crs=31983)
    caminho = tmp_path / 'Talhoes_da_Pedra_01_10_2026_fme.shp'
    gdf.to_file(caminho)
    return datetime.date(2026, 10, 1), caminho


class BancoFalso:
    def __init__(self, tipo='normal', obstaculos=None, infestacao=None):
        self.tipo, self.obst, self.infest, self.previas = tipo, obstaculos or {}, infestacao, []

    def parametros(self):
        return {'taxa_l_ha': '10', 'margem_infestacao_m': '10', 'alerta_aproveitamento_min': '0.30',
                'alerta_obstaculos_meses': '24'}

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

    def revisao_vigente(self, projeto_id, documento):
        return None

    def projeto_individual(self, cod, nome):
        return 1

    def subir_previa(self, caminho, destino):
        self.previas.append((caminho.name, destino))
        return destino


def test_normal_gera_zip_pdf_e_resumo(base, tmp_path):
    b = BancoFalso(obstaculos={15: [Point(50, 50)]})
    r = processar({'id': 3, 'solicitacao_id': 9, 'infestacao_id': None}, b, base, tmp_path / 'w',
                  datetime.date(2026, 10, 2))
    assert r['status'] == 'pronta' and r['orientacao'] == 'paisagem'
    assert r['resumo']['area_total_ha'] == pytest.approx(2.0)
    assert r['insumos']['base_talhoes'] == 'Talhoes_da_Pedra_01_10_2026_fme.shp'
    assert r['previa_zip'] == 'geracao-3/10156.zip' and r['previa_pdf'] == 'geracao-3/10156.pdf'
    with zipfile.ZipFile(tmp_path / 'w' / 'geracao-3' / '10156.zip') as z:
        assert '10156.shp' in z.namelist()
    # obstáculos com mais de 24 meses e classes sem versão aparecem como alerta
    assert any('meses' in a for a in r['alertas'])
    assert any('25 m' in a for a in r['alertas'])


def test_catacao_sem_infestacao_da_erro(base, tmp_path):
    with pytest.raises(ErroGeracao, match='infestação'):
        processar({'id': 4, 'solicitacao_id': 9, 'infestacao_id': None}, BancoFalso('catacao'), base,
                  tmp_path / 'w', datetime.date(2026, 10, 2))


def test_catacao_toda_fora_dos_talhoes_da_erro(base, tmp_path):
    b = BancoFalso('catacao', infestacao=[box(5000, 5000, 5010, 5010)])
    with pytest.raises(ErroGeracao, match='vazia'):
        processar({'id': 5, 'solicitacao_id': 9, 'infestacao_id': 1}, b, base, tmp_path / 'w',
                  datetime.date(2026, 10, 2))


def test_catacao_parcialmente_fora_gera_alerta(base, tmp_path):
    b = BancoFalso('catacao', infestacao=[box(40, 40, 60, 60), box(5000, 5000, 5010, 5010)])
    r = processar({'id': 6, 'solicitacao_id': 9, 'infestacao_id': 1}, b, base, tmp_path / 'w',
                  datetime.date(2026, 10, 2))
    assert any('fora dos talhões' in a for a in r['alertas'])
```

- [ ] **Passo 2: Rodar para ver falhar**

Rodar: `python -m pytest tests/drone/test_gerador.py -v`
Esperado: FAIL com `ModuleNotFoundError`

- [ ] **Passo 3: Implementar `drone/gerador.py`**

```python
"""Processa uma geração: insumos → recorte → shapefile/zip → PDF → prévia (spec, seção 6)."""
import datetime
from pathlib import Path

from shapely.ops import unary_union

from drone.base_talhoes import talhoes_da_fazenda
from drone.erros import ErroGeracao
from drone.geometria import recortar, uniao_buffers
from drone.mapa_pdf import DadosMapa, gerar_pdf
from drone.saida import gravar_aplicacao, montar_zip


def alertas(recorte, versoes, params, hoje, infestacao_fora=False) -> list:
    msgs = []
    minimo = float(params['alerta_aproveitamento_min'])
    for t in recorte.por_talhao:
        if t['area_prod'] > 0 and t['aplicavel_ha'] < minimo * t['area_prod']:
            msgs.append(f"Talhão {t['talhao']}: aplicável {t['aplicavel_ha']:.2f} ha de {t['area_prod']:.2f} ha "
                        f"(abaixo de {minimo:.0%}).")
    for talhao in recorte.talhoes_sem_area_prod:
        msgs.append(f'Talhão {talhao} sem AREA_PROD na Base; contado como 0 na área total.')
    meses = int(params['alerta_obstaculos_meses'])
    limite = hoje - datetime.timedelta(days=30 * meses)
    for v in versoes:
        if datetime.date.fromisoformat(v['enviado_em'][:10]) < limite:
            msgs.append(f"Obstáculos da classe {v['classe_m']} m têm mais de {meses} meses.")
    classes = {v['classe_m'] for v in versoes}
    for c in (15, 25, 50):
        if c not in classes:
            msgs.append(f'Nenhum obstáculo cadastrado na classe {c} m.')
    if infestacao_fora:
        msgs.append('Parte da infestação está fora dos talhões da fazenda e foi descartada.')
    return msgs


def processar(geracao: dict, banco, base: tuple, pasta: Path, hoje: datetime.date) -> dict:
    data_base, arquivo_base = base
    sol = banco.solicitacao(geracao['solicitacao_id'])
    cod, tipo = sol['cod_faz'], sol['tipo']
    params, distancias = banco.parametros(), banco.distancias()
    faz = banco.fazenda(cod)
    talhoes = talhoes_da_fazenda(Path(arquivo_base), cod)
    obst, versoes = banco.obstaculos_vigentes(cod)

    infest, margem, fora = None, 0.0, False
    if tipo == 'catacao':
        if not geracao.get('infestacao_id'):
            raise ErroGeracao('Catação sem shape de infestação: envie a infestação antes de gerar.')
        infest = banco.infestacao(geracao['infestacao_id'])
        margem = float(params['margem_infestacao_m'])
        fora = not unary_union(infest).buffer(margem).difference(unary_union(list(talhoes.geometry))).is_empty

    recorte = recortar(talhoes, uniao_buffers(obst, distancias), infestacao=infest, margem=margem)
    projeto = banco.projeto_individual(cod, faz['nome'])
    vigente = banco.revisao_vigente(projeto, tipo)
    revisao = vigente['numero'] + 1 if vigente else 0

    saida = Path(pasta) / f"geracao-{geracao['id']}"
    shp = gravar_aplicacao(recorte.area, int(params['taxa_l_ha']), saida / 'shape', cod)
    zip_ = montar_zip(shp, saida / f'{cod}.zip')
    pdf = saida / f'{cod}.pdf'
    orient = gerar_pdf(DadosMapa(cod, faz['nome'], tipo, revisao, talhoes, recorte, hoje), pdf)

    destino = f"geracao-{geracao['id']}"
    return {
        'status': 'pronta',
        'orientacao': orient,
        'insumos': {'distancias': distancias, 'taxa_l_ha': params['taxa_l_ha'], 'margem_infestacao_m': margem,
                    'base_talhoes': Path(arquivo_base).name, 'data_base': data_base.isoformat(),
                    'obstaculos': [v['versao_id'] for v in versoes], 'infestacao_id': geracao.get('infestacao_id'),
                    'revisao_prevista': revisao},
        'resumo': {'por_talhao': recorte.por_talhao, 'area_total_ha': recorte.area_total_ha,
                   'aplicacao_ha': recorte.aplicacao_ha},
        'alertas': alertas(recorte, versoes, params, hoje, fora),
        'previa_zip': banco.subir_previa(zip_, f'{destino}/{cod}.zip'),
        'previa_pdf': banco.subir_previa(pdf, f'{destino}/{cod}.pdf'),
    }
```

- [ ] **Passo 4: Rodar os testes**

Rodar: `python -m pytest tests/drone/test_gerador.py -v`
Esperado: 4 passed

- [ ] **Passo 5: Commit**

```bash
git add drone/gerador.py tests/drone/test_gerador.py
git commit -m "Drone: processamento de uma geração (alertas, prévia)"
```

---

### Tarefa 9: Agente (laço da fila) e agendamento

**Arquivos:**
- Criar: `drone/agente.py`, `agendamento/drone_agente.cmd`
- Modificar: `agendamento/instalar_tarefas.cmd`, `agendamento/README.md`

**Interfaces consumidas:** `processar` (Tarefa 8), `publicar`, `GitHubReleases` (Tarefa 7), `DroneBanco` (Tarefa 6), `arquivo_mais_recente` (Tarefa 3), `cfg`, `PASTA_TRABALHO` (Tarefa 2).

**Interfaces produzidas:** `python -m drone.agente [--uma-vez]`; `drone.agente.ciclo(banco, gh, cfg) -> bool` (True se trabalhou em algo).

- [ ] **Passo 1: Implementar `drone/agente.py`**

```python
"""Agente do módulo Drone no servidor Geo: gera e publica o que estiver na fila.
Uso: python -m drone.agente            (laço contínuo, intervalo do config.json)
     python -m drone.agente --uma-vez  (um ciclo e sai — para testes)"""
import datetime
import sys
import time
import traceback

from drone.banco import DroneBanco, carregar_env
from drone.base_talhoes import arquivo_mais_recente
from drone.config import PASTA_TRABALHO, cfg
from drone.erros import ErroGeracao
from drone.gerador import processar
from drone.publicacao import GitHubReleases, publicar


def _log(msg):
    print(f'{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}', flush=True)


def gerar_uma(banco, c) -> bool:
    g = banco.pegar_geracao()
    if not g:
        return False
    _log(f"geração {g['id']} (solicitação {g['solicitacao_id']})")
    try:
        base = arquivo_mais_recente(c['base_talhoes_pasta'], c['base_talhoes_padrao'])
        campos = processar(g, banco, base, PASTA_TRABALHO, datetime.date.today())
        banco.concluir_geracao(g['id'], **campos)
        _log(f"  pronta ({len(campos['alertas'])} alertas)")
    except ErroGeracao as e:
        banco.concluir_geracao(g['id'], status='erro', erro=str(e))
        _log(f'  erro: {e}')
    except Exception as e:  # erro inesperado: registra e segue a fila
        banco.concluir_geracao(g['id'], status='erro', erro=f'Erro interno do gerador: {e}')
        _log(traceback.format_exc())
    return True


def publicar_uma(banco, gh) -> bool:
    g = banco.pegar_publicacao()
    if not g:
        return False
    _log(f"publicando geração {g['id']}")
    try:
        sol = banco.solicitacao(g['solicitacao_id'])
        pasta = PASTA_TRABALHO / f"publicacao-{g['id']}"
        arquivos = {'zip': banco.baixar_previa(g['previa_zip'], pasta / 'p.zip'),
                    'pdf': banco.baixar_previa(g['previa_pdf'], pasta / 'p.pdf')}
        rev = publicar(banco, gh, sol['cod_faz'], sol['tipo'], g.get('publicar_motivo'), arquivos)
        banco.concluir_publicacao(g['id'], rev)
        banco.apagar_previas([g['previa_zip'], g['previa_pdf']])
        _log(f'  publicada (revisão {rev})')
    except Exception as e:
        banco.erro_publicacao(g['id'], str(e))
        _log(f'  falha na publicação: {e}')
    return True


def ciclo(banco, gh, c) -> bool:
    banco.batimento()
    trabalhou = gerar_uma(banco, c)
    return publicar_uma(banco, gh) or trabalhou


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    c = cfg()
    banco = DroneBanco()
    gh = GitHubReleases(carregar_env()['GH_TOKEN'], c['arquivos_repo'])
    if '--uma-vez' in sys.argv:
        ciclo(banco, gh, c)
        return
    _log('agente do Drone iniciado')
    while True:
        try:
            while ciclo(banco, gh, c):   # esvazia a fila antes de dormir
                pass
        except Exception:
            _log(traceback.format_exc())   # rede/banco fora: tenta de novo no próximo ciclo
        time.sleep(c['intervalo_s'])


if __name__ == '__main__':
    main()
```

- [ ] **Passo 2: Agendamento**

`agendamento/drone_agente.cmd`:
```bat
@echo off
rem Agente do módulo Drone: fica rodando e processa a fila do Hub a cada 30 s.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set PYTHONWARNINGS=ignore
if not exist agendamento\logs mkdir agendamento\logs
python -m drone.agente >> agendamento\logs\drone_agente.log 2>&1
```

Acrescentar ao `agendamento/instalar_tarefas.cmd`, depois das tarefas existentes e no mesmo estilo delas (sem admin, usuário atual):
```bat
schtasks /Create /F /TN "Hub Geotech - Agente Drone" /SC ONLOGON /TR "\"%~dp0drone_agente.cmd\""
```

Acrescentar uma linha à tabela do `agendamento/README.md`:
```markdown
| Hub Geotech - Agente Drone | ao entrar na conta (fica rodando) | gera e publica os projetos de drone da fila (`python -m drone.agente`) |
```
E, na seção de instalação, acrescentar: `pip install -r drone/requirements.txt` e a linha `GH_TOKEN=...` no `hub-geotech-supabase.env` do servidor (o mesmo token do worker, com permissão de escrita em `lmalerbo/hub-geotech-arquivos`).

- [ ] **Passo 3: Verificação**

Rodar: `python -m drone.agente --uma-vez`
Esperado: sai sem erro (fila vazia), e `select valor from hub.drone_parametros where chave = 'agente_ultimo_ciclo'` mostra o horário atual.

- [ ] **Passo 4: Commit**

```bash
git add drone/agente.py agendamento/drone_agente.cmd agendamento/instalar_tarefas.cmd agendamento/README.md
git commit -m "Drone: agente da fila (geração e publicação) e tarefa agendada"
```

---

### Tarefa 10: CLI para operar sem as telas

**Arquivos:**
- Criar: `drone/cli.py`

**Interfaces consumidas:** `DroneBanco` (Tarefa 6), `ler_shapefile`, `classe_pelo_nome` (Tarefa 3).

**Interfaces produzidas** (`python -m drone.cli ...`):
- `solicitar <cod_faz> <normal|catacao> [--data AAAA-MM-DD]` → imprime id e status
- `obstaculos <cod_faz> <arquivo.shp> [--classe 15|25|50]` → classe pelo nome se não informada
- `infestacao <solicitacao_id> <arquivo.shp> [--empresa NOME]`
- `gerar <solicitacao_id>` → coloca na fila (catação usa a última infestação da solicitação)
- `publicar <geracao_id> [--motivo TEXTO]`
- `status <solicitacao_id>` → solicitação e gerações, com alertas e erros

- [ ] **Passo 1: Implementar `drone/cli.py`**

```python
"""Operação manual do módulo Drone enquanto as telas (Parte 2) não existem."""
import argparse
import json
from pathlib import Path

from drone.banco import DroneBanco
from drone.insumos import classe_pelo_nome, ler_shapefile


def main():
    p = argparse.ArgumentParser(prog='python -m drone.cli')
    s = p.add_subparsers(dest='cmd', required=True)
    a = s.add_parser('solicitar'); a.add_argument('cod_faz', type=int); a.add_argument('tipo', choices=['normal', 'catacao']); a.add_argument('--data')
    a = s.add_parser('obstaculos'); a.add_argument('cod_faz', type=int); a.add_argument('arquivo'); a.add_argument('--classe', type=int, choices=[15, 25, 50])
    a = s.add_parser('infestacao'); a.add_argument('solicitacao_id', type=int); a.add_argument('arquivo'); a.add_argument('--empresa')
    a = s.add_parser('gerar'); a.add_argument('solicitacao_id', type=int)
    a = s.add_parser('publicar'); a.add_argument('geracao_id', type=int); a.add_argument('--motivo')
    a = s.add_parser('status'); a.add_argument('solicitacao_id', type=int)
    args = p.parse_args()
    b = DroneBanco()

    if args.cmd == 'solicitar':
        sol = b.criar_solicitacao(args.cod_faz, args.tipo, 'formulario', data_desejada=args.data)
        print(f"solicitação {sol['id']}: {sol['status']}")
    elif args.cmd == 'obstaculos':
        classe = args.classe or classe_pelo_nome(args.arquivo)
        if not classe:
            raise SystemExit('Não deu para saber a classe pelo nome do arquivo: use --classe 15|25|50')
        geoms = ler_shapefile(Path(args.arquivo))
        print(f'versão {b.gravar_obstaculos(args.cod_faz, classe, "upload", Path(args.arquivo).name, geoms)} '
              f'da classe {classe} m ({len(geoms)} feições)')
    elif args.cmd == 'infestacao':
        geoms = ler_shapefile(Path(args.arquivo))
        print(f'infestação {b.gravar_infestacao(args.solicitacao_id, args.empresa, Path(args.arquivo).name, geoms)} '
              f'({len(geoms)} feições)')
    elif args.cmd == 'gerar':
        sol = b.solicitacao(args.solicitacao_id)
        if sol['status'] not in ('solicitado', 'em_elaboracao'):
            raise SystemExit(f"Solicitação está em '{sol['status']}': não dá para gerar agora")
        inf = b.ultima_infestacao(sol['id']) if sol['tipo'] == 'catacao' else None
        print(f"geração {b.pedir_geracao(sol['id'], inf)['id']} na fila")
    elif args.cmd == 'publicar':
        b.pedir_publicacao(args.geracao_id, args.motivo)
        print('publicação pedida; o agente publica no próximo ciclo')
    elif args.cmd == 'status':
        print(json.dumps(b.solicitacao(args.solicitacao_id), ensure_ascii=False, indent=1, default=str))
        for g in b.selecionar('drone_geracoes', 'id,status,orientacao,alertas,erro,publicacao_erro',
                              {'solicitacao_id': f'eq.{args.solicitacao_id}', 'order': 'id'}):
            print(json.dumps(g, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
```

- [ ] **Passo 2: Verificação rápida**

Rodar: `python -m drone.cli --help`
Esperado: lista os 6 comandos.

- [ ] **Passo 3: Commit**

```bash
git add drone/cli.py
git commit -m "Drone: CLI para operar solicitações, insumos e publicação"
```

---

### Tarefa 11: Importação do legado

**Arquivos:**
- Criar: `drone/importar_legado.py`, `tests/drone/test_importar_legado.py`

**Interfaces consumidas:** `DroneBanco`, `publicar`, `GitHubReleases`, `ler_shapefile`, `classe_pelo_nome`, `gravar_aplicacao`, `montar_zip`, `uniao_buffers` (não usada), `so_poligonos`.

**Interfaces produzidas:**
- `drone.importar_legado.chave_recencia(linha) -> tuple` (safra, número da revisão, modificado_em)
- `drone.importar_legado.selecionar_projetos(catalogo: DataFrame) -> DataFrame` (1 linha por `cod_fazenda` × `subtipo` ∈ {Normal, Catação}, a mais recente)
- `drone.importar_legado.classe_do_legado(linha) -> int | None`
- `drone.importar_legado.selecionar_obstaculos(catalogo) -> dict[tuple[int, int], list[str]]` ((cod_faz, classe) → caminhos do grupo mais recente)
- `python -m drone.importar_legado [--simular]` → relatório `drone/trabalho/relatorio_legado.csv`

- [ ] **Passo 1: Escrever os testes**

`tests/drone/test_importar_legado.py`:
```python
import pandas as pd

from drone.importar_legado import classe_do_legado, selecionar_obstaculos, selecionar_projetos


def _cat(linhas):
    colunas = ['cod_fazenda', 'categoria', 'subtipo', 'safra', 'revisao', 'arquivo', 'modificado_em', 'caminho']
    return pd.DataFrame(linhas, columns=colunas)


def test_projeto_mais_recente_por_fazenda_e_tipo():
    c = _cat([
        ['10156', 'Aplicação', 'Normal', '2024-2025', 'Rev0', 'a.shp', '2024-05-01', 'A'],
        ['10156', 'Aplicação', 'Normal', '2026-2027', 'Rev0', 'b.shp', '2026-01-01', 'B'],
        ['10156', 'Aplicação', 'Normal', '2026-2027', 'Rev1', 'c.shp', '2025-12-01', 'C'],
        ['10156', 'Aplicação', 'Catação', '2023-2024', 'Rev2', 'd.shp', '2023-06-01', 'D'],
        ['10156', 'Aplicação', 'Experimento', '2026-2027', 'Rev5', 'e.shp', '2026-06-01', 'E'],
        ['10156', 'Aplicação', 'Não identificado', '2026-2027', 'Rev9', 'f.shp', '2026-06-01', 'F'],
    ])
    s = selecionar_projetos(c)
    assert sorted(zip(s['subtipo'], s['caminho'])) == [('Catação', 'D'), ('Normal', 'C')]


def test_classe_do_legado():
    base = {'categoria': 'Restrição', 'subtipo': 'Buffer 15 m', 'arquivo': 'restricoes15m.shp'}
    assert classe_do_legado(pd.Series(base)) == 15
    assert classe_do_legado(pd.Series({**base, 'subtipo': 'Buffer 200 m', 'arquivo': 'x.shp'})) is None
    assert classe_do_legado(pd.Series({'categoria': 'Obstáculo', 'subtipo': 'Árvores', 'arquivo': 'Arvores.shp'})) == 15
    assert classe_do_legado(pd.Series({'categoria': 'Obstáculo', 'subtipo': 'Rede elétrica', 'arquivo': 'Rede.shp'})) == 25
    assert classe_do_legado(pd.Series({'categoria': 'Obstáculo', 'subtipo': 'Rede elétrica', 'arquivo': 'Alta tensão.shp'})) == 50
    assert classe_do_legado(pd.Series({'categoria': 'Obstáculo', 'subtipo': 'Sede', 'arquivo': 'Sede.shp'})) == 50
    assert classe_do_legado(pd.Series({'categoria': 'Obstáculo', 'subtipo': 'Obstáculos', 'arquivo': 'obstaculos.shp'})) is None


def test_obstaculos_do_grupo_mais_recente_por_classe():
    c = _cat([
        ['10008', 'Restrição', 'Buffer 15 m', '2024-2025', 'Rev1', 'restricoes15m.shp', '2024-08-09', 'VELHO15'],
        ['10008', 'Restrição', 'Buffer 15 m', '2024-2025', 'Rev3', 'restricoes15m.shp', '2024-08-09', 'NOVO15'],
        ['10008', 'Obstáculo', 'Árvores', '2024-2025', 'Rev3', 'Arvores.shp', '2024-08-09', 'ARV'],
        ['10008', 'Restrição', 'Buffer 50 m', '2024-2025', 'Rev1', 'restricoes50m.shp', '2024-08-09', 'SO50'],
    ])
    s = selecionar_obstaculos(c)
    assert sorted(s[(10008, 15)]) == ['ARV', 'NOVO15']
    assert s[(10008, 50)] == ['SO50']
```

- [ ] **Passo 2: Rodar para ver falhar**

Rodar: `python -m pytest tests/drone/test_importar_legado.py -v`
Esperado: FAIL com `ModuleNotFoundError`

- [ ] **Passo 3: Implementar `drone/importar_legado.py`**

```python
"""Carga única do legado (spec, seção 8), a partir do catálogo da fase 1 (catalogo_drone.xlsx).
Uso: python -m drone.importar_legado --simular   (só relatório)
     python -m drone.importar_legado             (grava e publica)
Roda na máquina com acesso ao G:\\ e ao catálogo. Rodar de novo não duplica nada."""
import csv
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union

from drone.banco import DroneBanco, carregar_env
from drone.config import CRS_TRABALHO, PASTA_TRABALHO, cfg
from drone.geometria import so_poligonos
from drone.insumos import classe_pelo_nome, ler_shapefile
from drone.publicacao import GitHubReleases, publicar
from drone.saida import gravar_aplicacao, montar_zip

MOTIVO = 'Importado do legado'
TIPOS = {'Normal': 'normal', 'Catação': 'catacao'}
OBSTACULO_CLASSE = {'Árvores': 15, 'Rede elétrica': 25, 'Sede': 50}


def _numero_rev(rev) -> int:
    m = re.search(r'(\d+)', str(rev or ''))
    return int(m.group(1)) if m else -1


def chave_recencia(l) -> tuple:
    return (str(l['safra'] or ''), _numero_rev(l['revisao']), str(l['modificado_em'] or ''))


def selecionar_projetos(catalogo: pd.DataFrame) -> pd.DataFrame:
    ap = catalogo[(catalogo['categoria'] == 'Aplicação') & catalogo['subtipo'].isin(TIPOS)].copy()
    ap['_k'] = ap.apply(chave_recencia, axis=1)
    return (ap.sort_values('_k').groupby(['cod_fazenda', 'subtipo'], as_index=False).tail(1)
            .drop(columns='_k').reset_index(drop=True))


def classe_do_legado(l) -> int | None:
    if l['categoria'] == 'Restrição':
        m = re.search(r'(\d+)', str(l['subtipo']))
        return int(m.group(1)) if m and int(m.group(1)) in (15, 25, 50) else classe_pelo_nome(l['arquivo'])
    if l['categoria'] == 'Obstáculo':
        nome = str(l['arquivo']).lower()
        if 'alta' in nome or 'tens' in nome:
            return 50
        return OBSTACULO_CLASSE.get(l['subtipo'])
    return None


def selecionar_obstaculos(catalogo: pd.DataFrame) -> dict:
    ob = catalogo[catalogo['categoria'].isin(['Restrição', 'Obstáculo'])].copy()
    ob['classe'] = ob.apply(classe_do_legado, axis=1)
    ob = ob[ob['classe'].notna()]
    ob['_k'] = ob.apply(lambda l: (str(l['safra'] or ''), _numero_rev(l['revisao'])), axis=1)
    saida = {}
    for (cod, classe), g in ob.groupby(['cod_fazenda', 'classe']):
        recente = g['_k'].max()
        saida[(int(cod), int(classe))] = g.loc[g['_k'] == recente, 'caminho'].tolist()
    return saida


def _pdf_do_projeto(shp: Path):
    for pasta in (shp.parent, shp.parent.parent):
        pdfs = sorted(pasta.glob('*.pdf'), key=lambda p: p.stat().st_mtime, reverse=True)
        if pdfs:
            return pdfs[0]
    return None


def main():
    simular = '--simular' in sys.argv
    sys.stdout.reconfigure(encoding='utf-8')
    c = cfg()
    cat = pd.read_excel(c['catalogo_legado'], sheet_name='Catalogo', dtype={'cod_fazenda': str})
    cat = cat[cat['cod_fazenda'].str.fullmatch(r'\d{5}', na=False)]
    banco = DroneBanco()
    gh = None if simular else GitHubReleases(carregar_env()['GH_TOKEN'], c['arquivos_repo'])
    fazendas = {f['cod_faz'] for f in banco.selecionar('fazendas', 'cod_faz')}
    legado = banco.selecionar('drone_solicitacoes', 'id,cod_faz,tipo,revisao_id', {'origem': 'eq.legado'})
    ja_legado = {(s['cod_faz'], s['tipo']) for s in legado if s['revisao_id']}
    # solicitação criada numa execução que caiu antes de publicar: reaproveita
    pendentes = {(s['cod_faz'], s['tipo']): s['id'] for s in legado if not s['revisao_id']}
    obst_legado = {(v['cod_faz'], v['classe_m']) for v in banco.selecionar('drone_obstaculo_versoes',
                                                                            'cod_faz,classe_m', {'origem': 'eq.legado'})}
    relatorio = []

    def rel(cod, item, resultado, detalhe=''):
        relatorio.append({'cod_faz': cod, 'item': item, 'resultado': resultado, 'detalhe': detalhe})

    for (cod, classe), caminhos in sorted(selecionar_obstaculos(cat).items()):
        item = f'obstáculos {classe} m'
        if cod not in fazendas:
            rel(cod, item, 'fora', 'fazenda não está na Base Fazendas'); continue
        if (cod, classe) in obst_legado:
            rel(cod, item, 'pulado', 'já importado'); continue
        try:
            geoms = [g for p in caminhos for g in ler_shapefile(Path(p))]
            if not simular:
                banco.gravar_obstaculos(cod, classe, 'legado', ' + '.join(Path(p).name for p in caminhos), geoms)
            rel(cod, item, 'ok', f'{len(geoms)} feições de {len(caminhos)} arquivo(s)')
        except Exception as e:
            rel(cod, item, 'erro', str(e))

    for _, l in selecionar_projetos(cat).iterrows():
        cod, tipo = int(l['cod_fazenda']), TIPOS[l['subtipo']]
        item = f'projeto {tipo} ({l["safra"]} {l["revisao"]})'
        if cod not in fazendas:
            rel(cod, item, 'fora', 'fazenda não está na Base Fazendas'); continue
        if (cod, tipo) in ja_legado:
            rel(cod, item, 'pulado', 'já importado'); continue
        try:
            shp = Path(l['caminho'])
            orig = gpd.read_file(shp)
            if orig.crs is None:
                raise ValueError('shape sem .prj')
            area = so_poligonos(unary_union(list(orig.to_crs(CRS_TRABALHO).geometry)))
            antigo = pd.to_numeric(orig.drop(columns='geometry').iloc[0], errors='coerce').dropna()
            antigo = [v for v in antigo if v != 10]      # o outro campo é a taxa (sempre 10)
            pdf = _pdf_do_projeto(shp)
            avisos = [] if pdf else ['sem PDF']
            if antigo and abs(area.area / 1e4 - antigo[0]) > 0.02 * antigo[0]:
                avisos.append(f'área recalculada {area.area / 1e4:.2f} ha x antiga {antigo[0]:.2f} ha')
            if not simular:
                pasta = PASTA_TRABALHO / 'legado' / f'{cod}-{tipo}'
                zip_ = montar_zip(gravar_aplicacao(area, 10, pasta / 'shape', cod), pasta / f'{cod}.zip')
                sol_id = pendentes.get((cod, tipo)) or banco.criar_solicitacao(cod, tipo, 'legado', status='ok')['id']
                # publicar() continua uma revisão interrompida, então repetir não cria Rev1
                rev = publicar(banco, gh, cod, tipo, f'{MOTIVO} ({shp})', {'zip': zip_, 'pdf': pdf})
                banco.atualizar('drone_solicitacoes', {'id': f'eq.{sol_id}'}, {'revisao_id': rev})
            rel(cod, item, 'ok', '; '.join(avisos) + f' | origem: {shp}')
        except Exception as e:
            rel(cod, item, 'erro', str(e))

    PASTA_TRABALHO.mkdir(parents=True, exist_ok=True)
    saida = PASTA_TRABALHO / 'relatorio_legado.csv'
    with open(saida, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['cod_faz', 'item', 'resultado', 'detalhe'], delimiter=';')
        w.writeheader(); w.writerows(relatorio)
    if relatorio:
        df = pd.DataFrame(relatorio)
        resumo = df.groupby([df['item'].str.split(' ').str[:2].str.join(' '), 'resultado']).size()
    else:
        resumo = 'nada a fazer'
    print(resumo)
    print(f'relatório: {saida}' + ('  (SIMULAÇÃO — nada gravado)' if simular else ''))


if __name__ == '__main__':
    main()
```

A planilha `catalogo_drone.xlsx` (aba `Catalogo`) já tem as decisões manuais da fase 1 aplicadas (fila de revisão zerada), por isso o CSV de rótulos citado na spec não precisa ser lido de novo.

- [ ] **Passo 4: Rodar os testes**

Rodar: `python -m pytest tests/drone/test_importar_legado.py -v`
Esperado: 3 passed

- [ ] **Passo 5: Simulação com os dados reais** (máquina do Leo, com `G:\` acessível)

Rodar: `python -m drone.importar_legado --simular`
Esperado: o resumo por item/resultado e o `drone/trabalho/relatorio_legado.csv`. **Mostrar o relatório ao usuário antes da carga real.**

- [ ] **Passo 6: Commit**

```bash
git add drone/importar_legado.py tests/drone/test_importar_legado.py
git commit -m "Drone: importação do legado (projetos mais recentes e obstáculos)"
```

---

### Tarefa 12: Ensaio de ponta a ponta com dados reais

**Arquivos:** nenhum código novo (só a execução; ajustes que aparecerem voltam para a tarefa dona do código).

- [ ] **Passo 1: Suíte completa**

Rodar: `python -m pytest tests/drone -v`
Esperado: todos passam.

- [ ] **Passo 2: Normal real (10008 SANTA EUGÊNIA, obstáculos do legado de 2024-25 Rev3)**

```bash
G="G:/GeoProc/GEOTECNOLOGIA/08 PROJETOS PILOTO AUTOMATICO/15 PROPRIO/FAZENDAS/10008 SANTA EUGENIA/2024-2025/02 PROJETO/99 GERAL/Rev3"
python -m drone.cli obstaculos 10008 "$G/restricoes15m.shp"
python -m drone.cli obstaculos 10008 "$G/restricoes25m.shp"
python -m drone.cli obstaculos 10008 "$G/restricoes50m.shp"
python -m drone.cli solicitar 10008 normal            # → solicitado (já tem obstáculos)
python -m drone.cli gerar <id>
python -m drone.agente --uma-vez
python -m drone.cli status <id>                       # geração 'pronta', com alertas
```
Esperado: a geração fica `pronta`. Baixar a prévia do Storage (bucket `drone-previas`, painel do Supabase) e comparar a área aplicável dos 16 talhões de 2024 com o PDF antigo `10008 - SANTA EUGENIA 1.pdf`, dentro de 2% nos talhões presentes nos dois. Diferenças maiores só se explicam por mudança da Base; anotar e mostrar ao usuário.

- [ ] **Passo 3: Catação real (10372 SÃO JOSÉ 18)**

```bash
python -m drone.cli solicitar 10372 catacao           # → aguardando_infestacao
python -m drone.cli infestacao <id> "G:/.../10372 SAO JOSE 18/2024-2025/02 PROJETO/02 DEPT TECNICO/01 DRONE/.../daninhas_indefinidas.shp" --empresa Teste
python -m drone.cli gerar <id>
python -m drone.agente --uma-vez
```
Esperado: `pronta`, em retrato, verde.

- [ ] **Passo 4: Publicar e conferir no portal**

```bash
python -m drone.cli publicar <geracao_normal>
python -m drone.agente --uma-vez
```
Esperado: a release `drone-10008` em `lmalerbo/hub-geotech-arquivos` com `10008_SANTA.EUGENIA_Rev0-Normal.zip` e `.pdf`; a solicitação `ok` com `revisao_id`; a prévia apagada do Storage; os arquivos aparecendo em `hub.arquivos_vigentes`.

- [ ] **Passo 5: Teste no T40** (humano): o piloto copia o `.zip` extraído para o pendrive, em `DJI\ShapeFile\`, e importa no controle. Registrar o resultado.

- [ ] **Passo 6: Carga real do legado** (só depois do relatório aprovado na Tarefa 11)

Rodar: `python -m drone.importar_legado`
Esperado: o mesmo total do relatório simulado. Rodar de novo deve dar só `pulado`.

- [ ] **Passo 7: Limpar os dados de ensaio** (solicitações e gerações de teste dos Passos 2 e 3, se o usuário não quiser mantê-las) e fazer o commit final das anotações, se houver.
