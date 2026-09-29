# Módulo Drone — Parte 1: base, motor de geração e legado

- **Data:** 29/09/2026
- **Status:** rascunho para revisão
- **Referências:** schema `hub` (migrations de 28 e 29/09); layout aprovado em `assets/2026-09-29-drone-layout-mapa-v6.html`; catálogo da fase 1 (`catalogo_drone.xlsx`).

## 1. Contexto e objetivo

Nos módulos Plantio, Preparo e Colheita, o projeto é feito fora do sistema e o Hub só acompanha. O módulo Drone é diferente: **o próprio Hub gera o projeto de aplicação por drone.** Hoje a Geo faz esse projeto à mão no QGIS e manda os arquivos aos pilotos por WhatsApp.

O módulo tem três partes, e cada uma tem a sua própria especificação e o seu próprio plano:

| Parte | O que entrega | Esta especificação |
|---|---|---|
| **1. Base + motor + legado** | Tabelas, parâmetros, camadas de obstáculos, fila de geração, agente gerador (recorte, WGS84, áreas, PDF, `.zip`, publicação) e importação do legado | **sim** |
| 2. Telas no Hub | Formulário do solicitante, fila da Geo, uploads, botões Iniciar/Gerar/Publicar, prévia, download no portal | não |
| 3. Catação automática | Sincronização com o Drone MGMT: gatilho de entrada e retorno para "Relatório divulgado" | não |

A Parte 1 precisa funcionar e ser testável **sem as telas**: o motor é acionado por linhas na fila, e a importação do legado roda por linha de comando. As Partes 2 e 3 só leem e escrevem nas tabelas definidas aqui.

**Fora do escopo do módulo:**
- **Projeto de Experimento.** Continua manual.
- **Exportar obstáculos para o controle do T40.** Foi descartado.
- **Restrições e obstáculos como produto próprio** (fase 2 do módulo). Nesta fase eles são só insumo do recorte.

## 2. Conceitos

- **Fazenda:** `hub.fazendas` / `hub.talhoes`. A geometria dos talhões vem **sempre** da Base de Talhões do dia (`Talhoes_da_Pedra_DD_MM_AAAA_fme.shp`, EPSG:31983).
- **Camada de obstáculos da fazenda:** permanente e reaproveitada por todos os projetos da fazenda. É desenhada no QGIS e enviada como **3 arquivos, um por classe de restrição**. Cada envio de uma classe cria uma **versão** nova dela; a última é a vigente.
- **Classes de restrição:** a distância é um parâmetro editável. A lista de categorias serve só para orientar o que vai em cada arquivo.

  | Classe | Distância inicial | Categorias |
  |---|---|---|
  | 15 m | 15 m | árvore isolada |
  | 25 m | 25 m | rede de energia padrão |
  | 50 m | 50 m | rede de alta tensão, sede/casa, APP/mata/vegetação nativa, zona urbana, cultura vizinha, pasto, rodovia, represa |

- **Projeto de drone da fazenda:** um `hub.projetos` individual por fazenda no módulo `drone`, com **dois tipos de documento**, e cada um tem a sua própria sequência de revisões (Rev0, Rev1…):
  - `normal`: aplicação na fazenda inteira;
  - `catacao`: aplicação nas manchas de infestação. Cada novo levantamento de infestação vira uma nova revisão.
- **Projeto personalizado:** o mecanismo que já existe no Hub (`tipo = 'personalizado'` + `revisao_origens`), juntando revisões publicadas de fazendas diferentes. Não há regra nova na Parte 1.
- **Solicitação:** um pedido de projeto (normal ou catação) de uma fazenda, que percorre o fluxo da seção 7.
- **Geração:** uma execução do motor para uma solicitação. Pode haver várias gerações até a Geo publicar uma delas.

## 3. Regras de cálculo

Todo o geoprocessamento é feito em **SIRGAS 2000 / UTM 23S (EPSG:31983)**, e só a saída é convertida para WGS84.

**Entradas comuns**
1. Talhões da fazenda: todos os talhões com `SECAO = cod_faz` no arquivo mais recente da Base, com a geometria corrigida (`make_valid`).
2. Buffers das restrições: a união de `buffer(classe_15m, d15) ∪ buffer(classe_25m, d25) ∪ buffer(classe_50m, d50)`, usando as versões vigentes das 3 classes. Uma classe sem versão não contribui. As linhas (rede) viram faixas, e pontos e polígonos viram áreas.

**Normal:** `área_aplicação = talhões − buffers`

**Catação:** `área_aplicação = (buffer(infestação, margem) ∩ talhões) − buffers`, com margem inicial de **10 m**.

**Números calculados** (vão para o PDF e para o resumo da geração)
- Por talhão: `AREA_PROD` (atributo da Base) e aplicável (área da intersecção do talhão com a área de aplicação, em ha).
- Área total = **soma do `AREA_PROD`** dos talhões da fazenda.
- Área de aplicação total = soma do aplicável.
- As áreas são arredondadas para 2 casas **só na apresentação**.

**Parâmetros** (`hub.drone_parametros`; alterar não exige código)

| Chave | Valor inicial |
|---|---|
| `taxa_l_ha` | 10 |
| `margem_infestacao_m` | 10 |
| `alerta_aproveitamento_min` | 0,30 (fração do AREA_PROD abaixo da qual o talhão gera alerta) |
| `alerta_obstaculos_meses` | 24 |

## 4. Entrega (padrão único para projetos novos e para o legado)

Para cada revisão publicada existem dois arquivos no GitHub Releases, com o nome no padrão do Hub (sufixo do tipo de documento depois da revisão):

- `{COD}_{NOME}_Rev{N}-Normal.zip` / `.pdf`
- `{COD}_{NOME}_Rev{N}-Catacao.zip` / `.pdf`

**`.zip` (para o piloto e o DJI Agras T40):** contém **só o shapefile de aplicação**, na raiz, sem subpasta: `{COD}.shp .shx .dbf .prj .cpg`. Não leva `.qmd`, revisões antigas nem arquivos de restrição.

**Shapefile de aplicação**
- **1 feição** (MultiPolygon), em **WGS84 (EPSG:4326)**, com `.cpg` = UTF-8.
- Campos, **iguais nos dois tipos**:

| Campo | Tipo | Valor |
|---|---|---|
| `Taxa l/ha` | inteiro | `taxa_l_ha` (10) |
| `Área Apli` | real, 2 casas | área de aplicação em ha, calculada em EPSG:31983 |

**PDF:** layout **v6** aprovado (maquete em `assets/`), vetorial, em A4.
- **A orientação é automática pelo formato da fazenda:** a largura da extensão dos talhões maior que a altura resulta em paisagem, caso contrário em retrato. Os blocos e o estilo são os mesmos nas duas orientações; só o painel muda de lugar (à direita na paisagem, embaixo no retrato).
- **Quadro do mapa**, com cantos arredondados:
  - talhões em contorno com o número;
  - área de aplicação em **marrom (Normal)** ou **verde (Catação)**;
  - logo sem contorno, colado no canto superior esquerdo;
  - barra de escala sem contorno, colada no canto inferior esquerdo.
- **Painel:**
  - tabela SEÇÃO / TALHÃO / ÁREA PROD (ha) / APLICÁVEL (ha), ordenada por talhão, com total;
  - legenda;
  - etiqueta do tipo, `COD · NOME` e "Mapa de aplicação · Drone";
  - cartões "Área de aplicação" (com % da área total) e "Área total" (com o número de talhões);
  - faixa Escala (calculada) / Safra / Revisão / Norte;
  - rodapé "Pedra Agroindustrial S/A · Geotecnologia" e a data de geração.
- **O gerador é próprio, em Python.** Não depende do QGIS.

## 5. Modelo de dados

Migration nova no schema `hub`. Requer a extensão **PostGIS** no Supabase. A geometria dos obstáculos e das infestações fica no banco (é pequena, dezenas de KB por fazenda). **A geometria dos talhões não vai para o banco**, porque o agente lê o arquivo diário.

```sql
-- módulo e documentos
insert into hub.modulos (id, nome, cor, icone, ordem) values ('drone', 'Drone', '#138a3e', 'drone', <próxima ordem>);
insert into hub.documento_tipos (modulo_id, codigo, nome, marcador, sufixo, ordem) values
  ('drone','normal','Aplicação Normal','Rev','-Normal',1),
  ('drone','catacao','Aplicação Catação','Rev','-Catacao',2);

hub.drone_parametros (chave text pk, valor numeric, descricao text, atualizado_por, atualizado_em)

hub.drone_classes_restricao (
  classe_m int pk check (classe_m in (15,25,50)),   -- identidade fixa da classe (o nome do arquivo)
  distancia_m numeric not null,                     -- distância aplicada (editável)
  categorias text not null, atualizado_por, atualizado_em)

hub.drone_obstaculo_versoes (
  id bigint pk, cod_faz int fk, classe_m int fk, versao int,
  vigente bool,                      -- uma vigente por (cod_faz, classe_m)
  origem text check (origem in ('upload','legado')),
  arquivo_origem text, n_feicoes int, enviado_por uuid, enviado_em timestamptz,
  unique (cod_faz, classe_m, versao))
hub.drone_obstaculo_feicoes (versao_id fk on delete cascade, geom geometry(Geometry, 31983))

hub.drone_infestacoes (
  id bigint pk, cod_faz int fk, solicitacao_id fk, empresa text,
  arquivo_origem text, n_feicoes int, enviado_por uuid, enviado_em timestamptz)
hub.drone_infestacao_feicoes (infestacao_id fk on delete cascade, geom geometry(Geometry, 31983))

hub.drone_solicitacoes (
  id bigint pk, cod_faz int fk, tipo text check (tipo in ('normal','catacao')),
  origem text check (origem in ('formulario','dronemgmt','legado')),
  solicitante_id uuid, data_desejada date,
  status text check (status in ('solicitado','aguardando_obstaculos','aguardando_infestacao',
                                'em_elaboracao','ok','devolvido','cancelado')),
  responsavel_id uuid, motivo_devolucao text,
  revisao_id bigint fk hub.projeto_revisoes,        -- preenchido ao publicar
  criado_em, iniciado_em, concluido_em)

hub.drone_geracoes (
  id bigint pk, solicitacao_id fk,
  status text check (status in ('fila','processando','pronta','erro','publicada','descartada')),
  pedido_por uuid, pedido_em, iniciado_em, concluido_em,
  orientacao text,                   -- retrato | paisagem
  insumos jsonb,                     -- distâncias, taxa, margem, arquivo/data da Base, ids das versões de obstáculo, infestacao_id
  resumo jsonb,                      -- áreas por talhão e totais
  alertas jsonb, erro text,
  previa_pdf text, previa_zip text)  -- caminho no Storage enquanto não publicada
```

- **Toda mudança de status** de solicitação e de geração é registrada em `hub.log_auditoria`.
- **Prévia:** o `.pdf` e o `.zip` de uma geração `pronta` ficam no **Supabase Storage** (bucket privado `drone-previas`). São apagados ao publicar ou descartar, ou depois de 30 dias. O volume é pequeno e cabe no plano gratuito.
- **RLS:** segue o padrão do Hub. `authenticated` lê. As escritas da Parte 2 serão feitas por RPCs `security definer` que conferem o papel (a Parte 2 define essas RPCs). O agente usa `service_role`.
- **Papel novo:** "solicitante" do módulo `drone`, com permissão para criar e acompanhar solicitações Normais, e nada mais.

## 6. Agente gerador (servidor Geo)

É um processo Python no servidor Geo, iniciado pelo Task Scheduler no boot e reiniciado se cair. Usa o mesmo ambiente e o mesmo `comum.py` da ingestão. **Consulta a fila a cada 30 s** e processa uma geração por vez.

**Passos de uma geração** (`fila` → `processando` → `pronta` | `erro`):
1. Registra os insumos: parâmetros, versões vigentes de obstáculos, infestação e o arquivo da Base usado.
2. Lê os talhões da fazenda e os insumos, e corrige geometrias.
3. Aplica as regras da seção 3 e calcula o resumo por talhão.
4. Converte para WGS84 e grava o shapefile de aplicação.
5. Escolhe a orientação e gera o PDF (seção 4).
6. Monta o `.zip`, sobe a prévia no Storage, grava o resumo e os alertas e marca a geração como `pronta`.

**Publicação:** acionada pela Parte 2, com a geração em `pronta` + pedido de publicar.
1. Garante o projeto individual da fazenda.
2. Chama `hub.nova_revisao(projeto, documento, motivo)`. O motivo é obrigatório a partir da Rev1 e, na catação, o padrão é "Novo levantamento de infestação".
3. Sobe o `.zip` e o `.pdf` com o nome definitivo para o release da fazenda no GitHub.
4. Grava `revisao_arquivos`, apaga a prévia, marca a geração como `publicada` e a solicitação como `ok`.

As demais gerações pendentes da mesma solicitação passam a `descartada`.

**Alertas** (aparecem na prévia e não bloqueiam):
- talhão com aplicável abaixo de `alerta_aproveitamento_min` do `AREA_PROD`;
- infestação que cai fora dos talhões da fazenda;
- versão de obstáculos mais antiga que `alerta_obstaculos_meses`;
- classe de restrição sem nenhuma versão.

**Erros** (a geração vai para `erro`, com mensagem em português):
- fazenda sem talhões na Base;
- arquivo sem `.prj` ou com CRS desconhecido;
- área de aplicação vazia;
- catação sem infestação;
- falha ao ler a Base.

**Robustez:**
- Uma geração parada em `processando` por mais de 15 minutos volta para `fila`.
- O agente grava um sinal de vida em `drone_parametros` (`agente_ultimo_ciclo`), para o Hub mostrar "motor fora do ar desde…".
- Falha no GitHub durante a publicação não altera nada no banco e pode ser repetida, porque o nome do arquivo é determinístico.

## 7. Fluxo da solicitação (referência para as Partes 2 e 3)

```
Normal:  formulário → solicitado ─┬─(fazenda sem obstáculos)→ aguardando_obstaculos ─(upload)→ solicitado
Catação: Drone MGMT → aguardando_infestacao ─(upload da infestação)→ solicitado
solicitado ─(Geo "Iniciar")→ em_elaboracao ─(gerar, conferir, publicar)→ ok
qualquer status antes de ok → devolvido | cancelado
```

**Na Parte 1**, as transições automáticas são feitas por funções do banco:
- ao criar uma solicitação Normal, se a fazenda não tem versão vigente em nenhuma classe → `aguardando_obstaculos`;
- ao gravar uma versão de obstáculos → as solicitações da fazenda em `aguardando_obstaculos` voltam para `solicitado`;
- ao gravar uma infestação ligada a uma solicitação → `aguardando_infestacao` passa a `solicitado`;
- ao publicar → `ok`.

**Parte 3 (só referência):** a catação entra quando **todos** os talhões do voo `flightProject = Ervas Daninhas` da fazenda estão em "Processado, aguardando divulgação" (provável `controlStatus` 9). Ao chegar a `ok`, os talhões passam a "Relatório divulgado" (provável 10). Os códigos devem ser confirmados pela API.

## 8. Importação do legado (carga única, por linha de comando)

`drone/importar_legado.py [--simular]`. A fonte é o catálogo da fase 1 (`catalogo_drone.xlsx`) mais o CSV de rótulos manuais mais recente. Tudo roda por fazenda, e só para fazendas que existem em `hub.fazendas` (as demais vão para o relatório).

**Projetos:** para cada fazenda, o **Normal mais recente** e a **Catação mais recente**, de qualquer safra.
- "Mais recente" = maior safra, depois maior revisão, depois data de modificação mais recente.
- O shapefile é regravado no padrão da seção 4: mesma geometria, 1 feição, WGS84, `Taxa l/ha` = 10 e `Área Apli` recalculada.
- Se existir um `.pdf` na pasta do projeto ou na pasta-mãe, ele vai **como está**. Não é gerado PDF novo para o legado.
- É publicado como **Rev0**, com motivo "Importado do legado" e com a origem no `G:\` registrada, e ganha uma solicitação `origem = 'legado'`, `status = 'ok'`.

**Obstáculos:** para cada fazenda e classe, o arquivo de restrição mais recente vira a **versão 1** (`origem = 'legado'`).
- **Mapeamento pelo nome:** `restricoes15m` / `Restrições 15m` / `15m` / `15M` / `resrtricoes15m` / `retricoes15m`… → 15 m, e o mesmo para 25 m e 50 m.
- **Arquivos avulsos sem a margem no nome:**
  - Árvores → 15 m;
  - Rede (padrão) → 25 m;
  - Alta tensão, Sede, Casa → 50 m.
  - Entram na mesma versão da classe, fazendo a união.

**Relatório** (CSV + resumo no terminal): o que entrou; o que ficou de fora, com o motivo (fazenda fora da Base, arquivo ilegível, sem `.prj`, sem projeto); e os avisos (PDF ausente, área recalculada diferindo mais de 2% do valor antigo).

**Idempotência:** rodar de novo não duplica nada. Uma fazenda que já tem Rev0 importada, ou versão de obstáculo de legado, é pulada. `--simular` só produz o relatório.

## 9. Testes

- **Motor, testes automáticos com geometrias sintéticas de área conhecida:**
  - talhão sem obstáculos;
  - talhão menos árvore (15 m);
  - talhão menos rede em linha (25 m);
  - catação com margem de 10 m cortada pela borda do talhão;
  - buracos e multipartes;
  - geometria inválida;
  - resultado vazio → erro.
- **Regressão com casos reais:** gerar a 10008 (Normal) e a 10372 (Catação) a partir de insumos do legado e comparar a área aplicável com a dos projetos feitos à mão (tolerância de 2%).
- **Shapefile de saída:** CRS 4326, 1 feição, nomes e tipos exatos dos campos, `.cpg` UTF-8. Deve ser lido corretamente por geopandas e pelo QGIS.
- **PDF:** a primeira saída do gerador é comparada lado a lado com a maquete v6 e aprovada pelo usuário antes de ligar no fluxo. Depois disso, um teste confere que o PDF é gerado nas duas orientações sem erro.
- **Importação:** rodar `--simular` e conferir o relatório antes da carga real.
- **Teste de ponta a ponta com o T40:** o piloto importa um `.zip` gerado no controle.

## 10. Decisões registradas

1. **Normal é sempre a fazenda inteira.** A exceção é o projeto personalizado.
2. **Catação = infestação expandida 10 m, recortada pelos talhões, menos as restrições.** Um projeto de catação por fazenda, e cada levantamento é uma revisão.
3. **Obstáculos são desenhados no QGIS** e enviados como 3 arquivos, um por classe (15/25/50 m). Não há editor no navegador.
4. **Experimento fica fora do sistema.**
5. **Fluxo:** Solicitado → (Aguardando obstáculos / infestação) → Em elaboração → OK, sem etapa de aceite. A Geo **confere a prévia antes de publicar**.
6. **Formulário do solicitante:** fazenda, tipo e data desejada. A taxa é fixa, 10 l/ha, como parâmetro.
7. **Os pilotos baixam pelo portal**, como os operadores.
8. **Legado:** entram os projetos mais recentes de qualquer safra, mais os obstáculos como versão 1.
9. **O gerador de PDF é próprio, em Python.** Layout v6, com orientação automática.
10. **Arquitetura:** agente Python no servidor Geo, fila no banco, arquivos no GitHub Releases e prévias temporárias no Supabase Storage.
