# Módulo Drone — Parte 2: tela no Hub, projeto por talhão e Catação por levantamento

**Data:** 07/10/2026 · **Depende de:** Parte 1 (`2026-09-29-modulo-drone-parte1-design.md`), já em produção.
**Maquete aprovada:** `assets/2026-10-07-drone-hub-tela.png` (fila à esquerda, fazenda com mapa por talhão à direita, painel "Nova revisão").

## 1. Objetivo

Hoje o módulo Drone só é operado por linha de comando. A Parte 2 coloca o trabalho da Geo dentro do Hub e muda o modelo do projeto Normal:

1. **Catação = só o último levantamento.** Um levantamento novo substitui a Catação inteira. As 26 Catações do legado que foram consolidadas voltam a ter só o levantamento mais recente.
2. **Tag de Normal incompleta** no Hub e no portal ("31% da fazenda") quando algum talhão da Base de hoje está sem projeto.
3. **Normal montada por talhão.** Talhões novos ou refeitos são incorporados ao projeto vigente, e talhões podem ser removidos, numa única revisão nova.
4. **Tela do Drone no Hub**: fila de trabalho, fazenda com mapa clicável, montagem da revisão, prévia e publicação.

Fora desta parte: abertura automática da Catação pelo Drone MGMT (Parte 3) e edição de geometria no navegador (ajuste fino continua no QGIS, via "subir shape").

## 2. Conceitos

- **Talhão do projeto**: a geometria de aplicação de um talhão dentro de uma revisão. Tem uma **origem** (`sistema`, `shape`, `legado`) e a **revisão em que nasceu** (`desde_rev`).
- **Revisão Normal**: lista completa de talhões do projeto. A revisão N+1 = revisão N, com os talhões incluídos ou refeitos trocados, os removidos retirados e os outros copiados iguais.
- **Escopo de uma geração Normal**: talhões a incluir ou refazer (cada um com a fonte `sistema` ou `shape`) e talhões a remover.
- **Catação**: também guardada por talhão (para o mapa), mas sempre por inteiro: cada geração é o levantamento completo, sem herdar nada da revisão anterior.
- **Cobertura da Normal**: área dos talhões da Base de hoje que têm talhão no projeto ÷ área de todos os talhões da Base de hoje (pela geometria). 100% = completa.
- **Talhão fora da Base**: talhão que está no projeto mas não existe mais na Base. Só gera aviso; o analista remove numa revisão se for o caso.

## 3. Dados (schema `hub`)

### 3.1 Geometria dos talhões
`hub.talhao_geom (cod_faz int, talhao_num int, geom geometry(MultiPolygon, 4326), area_ha numeric, atualizado_em)`, chave `(cod_faz, talhao_num)`.
- Gravada pela **rodada diária** (07:00), no passo da Base Fazendas: lê o `.shp` do dia, simplifica (tolerância 0,5 m em 31983), reprojeta para 4326 e faz upsert. Talhões que saíram da Base são apagados desta tabela (o projeto não é tocado).
- Serve o mapa do Hub e o cálculo da cobertura.

### 3.2 Talhões das revisões
`hub.drone_revisao_talhoes (revisao_id bigint → projeto_revisoes, talhao_num int, geom geometry(MultiPolygon, 31983), area_ha numeric, origem text check in ('sistema','shape','legado'), desde_rev int)`, chave `(revisao_id, talhao_num)`.
- Gravada na **mesma transação** da publicação (`hub.drone_publicar` ganha o parâmetro `p_talhoes jsonb`: `[{talhao, wkt, origem, desde_rev}]`).
- Vale para Normal e Catação.

### 3.3 Envios de arquivo pelo Hub
O navegador não processa shapefile. Ele sobe os arquivos para o Storage e registra o envio; o **agente** valida, reprojeta e grava.
- Bucket privado `drone-envios` (apagado depois de 30 dias).
- `hub.drone_envios (id, cod_faz, tipo check in ('obstaculos','infestacao','ajuste'), classe_m int null, solicitacao_id null, arquivos text[], status check in ('fila','processando','ok','erro'), erro text, enviado_por, enviado_em, processado_em)`.
  - `obstaculos`: vira nova versão da classe (`drone_gravar_obstaculos`); a classe vem do nome do arquivo ou é escolhida na tela.
  - `infestacao`: vira `drone_infestacoes` da solicitação de Catação (`drone_gravar_infestacao`).
  - `ajuste`: shape do "subir shape" de uma geração Normal; fica em `hub.drone_ajuste_feicoes (envio_id, geom 31983)`.
- Erros de validação (sem `.prj`, coordenadas irreconhecíveis, sem feições) voltam para a tela em português.

### 3.4 Gerações
`hub.drone_geracoes` ganha `escopo jsonb` (Normal): `{"incluir":[{"talhao":20,"fonte":"sistema"},{"talhao":21,"fonte":"shape","envio_id":7}],"remover":[129]}`. Catação não usa escopo.

### 3.5 Funções para o Hub (usuário logado)
Todas `security definer`, conferindo o papel:
- `drone_solicitar(p_cod_faz, p_tipo, p_data_desejada, p_observacao)` — solicitante ou editor do Drone. Catação manual: só editor.
- `drone_registrar_envio(p_cod_faz, p_tipo, p_classe_m, p_solicitacao_id, p_arquivos)` — editor.
- `drone_pedir_geracao(p_solicitacao_id, p_escopo)` — editor. Valida o escopo: talhão a incluir tem de existir na Base; um talhão não pode estar em incluir e remover ao mesmo tempo; escopo vazio é recusado.
- `drone_pedir_publicacao(p_geracao_id, p_motivo)` e `drone_descartar_geracao(p_geracao_id)` — editor.
- `drone_mapa_fazenda(p_cod_faz)` → GeoJSON (4326) com cada talhão da Base + os talhões fora da Base, com `status` (`com_projeto`, `sem_projeto`, `fora_da_base`), `rev` e `desde_rev` da Normal vigente e `catacao` (tem mancha na Catação vigente).
- `drone_painel()` → os itens da fila e os contadores de Atenção (§5.1).
- `portal_drone_cobertura()` (anon) → `cod_faz, cobertura_pct` das Normais vigentes, para o portal.

## 4. Regras de geração (agente)

### 4.1 Normal
1. Parte da lista de talhões da Normal vigente (vazia se não há projeto).
2. Para cada talhão em **incluir**:
   - `sistema`: talhão da Base de hoje − buffers dos obstáculos vigentes (regra da Parte 1).
   - `shape`: feições do envio ∩ talhão da Base de hoje. Se a interseção for vazia, a geração dá erro dizendo quais talhões o shape não cobre.
   - O talhão entra com `origem` = fonte e `desde_rev` = número da revisão nova.
3. Talhões em **remover** saem da lista.
4. Talhões não citados são copiados iguais (mesma geometria, origem e `desde_rev`).
5. A área de aplicação é a união da lista. O `.zip` (1 feição) e o PDF (layout v6) saem da fazenda inteira. O PDF ganha a linha "Incompleta · XX% da fazenda" no carimbo quando a cobertura < 100%.
6. Alertas da Parte 1, mais: talhões fora da Base que continuam no projeto; obstáculos mais novos que o projeto em talhões não refeitos.

### 4.2 Catação
Igual à Parte 1 (blocos: agrupar 20 m + contorno + folga 5 m, ∩ talhões − buffers), sobre **só as camadas enviadas nesta solicitação**. A lista de talhões é recalculada inteira; nada vem da revisão anterior.

### 4.3 Publicação
`drone_publicar` grava a revisão, os arquivos, os talhões (`p_talhoes`) e fecha a geração e a solicitação numa transação, como na Parte 1. O número esperado continua sendo conferido.

## 5. Tela do Drone no Hub

Item novo "Drone" na navegação do Hub (`app/index.html`), no mesmo visual dos outros módulos (Poppins, cor `--drones`).

### 5.1 Fila de trabalho (coluna esquerda)
Grupos, cada um com contador:
- **Solicitações Normal**: fazenda, observação, quem pediu, data desejada; status (`aguardando obstáculos`, `solicitado`, `gerando`, `prévia pronta`).
- **Catação · aguardando infestação**.
- **Prévias para conferir**: com o número de alertas.
- **Atenção**: Normais incompletas; obstáculos com mais de 24 meses; fazendas com talhões fora da Base; projetos feitos com obstáculos mais antigos que os vigentes.
- Botão "+ Nova solicitação" e busca de fazenda (abre a fazenda direto, como nos outros módulos).

### 5.2 Fazenda (painel direito)
- **Cabeçalho**: código, nome, talhões, área; cartões da Normal (revisão, tag "XX% da fazenda" quando incompleta) e da Catação (revisão, levantamento, área).
- **Mapa** (MapLibre GL, sem mapa de fundo): talhões da Base com o número; área de aplicação vigente em marrom (Normal) ou verde (alternância Normal/Catação); sem projeto em cinza; fora da Base com contorno laranja; seleção em azul; remover em vermelho tracejado. Zoom e arrasto.
- **Painel "Nova revisão · Normal RevN"**: clique no talhão alterna entre incluir e nada; com o botão "Remover" ativo, o clique marca para remover (só talhões com projeto). Atalho "Selecionar sem projeto". Fonte por lote: "Sistema gera" ou "Subir shape" (abre o envio). Motivo obrigatório a partir da Rev1. Obstáculos usados (classe, versão, data) e "Enviar obstáculos". Botão **Gerar prévia**.
- **Catação**: "Enviar infestação" (várias camadas de uma vez) e **Gerar prévia**.
- **Prévia**: o PDF embutido (visualizador do Worker), os alertas e os botões **Publicar** e **Descartar**. Enquanto o agente gera, o painel mostra "gerando…" e atualiza sozinho.
- **Histórico**: revisões publicadas com motivo, autor e data; arquivos para baixar.

### 5.3 Papéis
- **Solicitante**: vê a fila e as fazendas; abre solicitação Normal.
- **Editor do Drone** (`usuario_modulos` com `drone`): tudo.
- **Leitura**: só vê.

## 6. Portal

Na aba Drone, a Normal com cobertura < 100% ganha a tag **"Incompleta · XX%"** ao lado do nome do arquivo (dado de `portal_drone_cobertura()`).

## 7. Migração dos dados atuais (uma vez)

1. **Geometria dos talhões**: primeira carga de `talhao_geom` pela rodada diária.
2. **Normais do legado → por talhão**: para cada Normal vigente, recorta a geometria publicada pelos talhões da Base de hoje e grava em `drone_revisao_talhoes` (`origem='legado'`, `desde_rev=0`). A parte que cair fora dos talhões de hoje é descartada (já não aparecia na tabela do PDF). Não republica nada.
3. **Catações do legado → último levantamento**: para cada Catação de legado vigente formada por mais de um projeto, substitui a Rev0 pelo levantamento mais recente sozinho (mesma mecânica do `revisar_legado.py`, que ganha esse modo) e grava os talhões. Catação com revisão feita pelo sistema (Rev1+) não é tocada.

## 8. Erros e casos-limite

- Talhão incluído que não existe mais na Base entre o pedido e a geração: a geração dá erro listando os talhões.
- Duas gerações abertas da mesma fazenda e documento: a segunda fica bloqueada até a primeira ser publicada ou descartada (evita revisões cruzadas).
- Publicação com número de revisão mudado: recusada (Parte 1); o analista gera de novo.
- Envio com erro: aparece no item da fila e no painel da fazenda com a mensagem; pode ser reenviado.
- Mapa de fazenda grande (208 talhões): geometria simplificada; carga sob demanda por fazenda.

## 9. Testes

- **Agente (pytest)**: montagem da revisão (incluir sistema/shape, remover, copiar); shape fora do talhão; cobertura; Catação sem herança; processamento de envios (prj, classe, Z).
- **Banco**: verificação SQL das funções novas com `begin … rollback` (papéis, validação do escopo, bloqueio de geração dupla).
- **Tela (Playwright, conta de teste)**: abrir fazenda, selecionar talhões, gerar prévia, publicar e conferir no portal, restaurando os dados no fim (regra dos testes com dados reais: salvar e restaurar, nunca apagar dado real).
- **Migração**: simulação (`--simular`) com relatório antes de gravar; contagem de talhões por Normal antes e depois.

## 10. Decisões tomadas no levantamento (07/10/2026)

1. Catação: sempre só o último levantamento; as 26 consolidadas voltam ao mais recente (opção A).
2. Normal incompleta: tag com a porcentagem no Hub e no portal.
3. Remoção de talhão no mesmo passo da inclusão, numa única revisão.
4. Fonte dos talhões novos: sistema gera ou shape enviado (os dois).
5. Tela abre na fila de trabalho; a fila leva à fazenda; busca direta também.
6. Mapa interativo com a geometria dos talhões no banco (opção A).
7. Layout da maquete aprovado.
8. Talhão que sumiu da Base: só aviso; o analista remove se for o caso.
9. Fluxos e papéis da seção 5 aprovados; Catação automática fica para a Parte 3.
