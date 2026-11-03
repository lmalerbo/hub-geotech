# Apresentação semanal da Geotecnologia no Hub — design

Data: 29/10/2026. Levantamento feito com o usuário em 29/10.

## Problema

A apresentação semanal "Indicadores e Entregas do Setor de Geotecnologia" (6 slides: Divisória, Colheita, Sistematização, Plantio, Voos com Drone, Projetos de Drone de Aplicação) é gerada por dois scripts no notebook do Leo (`Documents/GitHub/src/scripts/extrair.py` e `gerar.py`). Só ele consegue gerar, as metas que não vêm de API estão fixas no código e os dados de drone dependem de baixar todos os ZIPs publicados e adivinhar a safra por regex no `motivo` da revisão.

## Objetivo

Uma tela no Hub onde **quem é editor** escolhe a semana, ajusta metas e textos, vê a prévia dos slides e baixa o PPTX, sem depender do notebook. Os números saem do Hub e batem com o deck gerado hoje pelo `gerar.py` (versão de 28/10, já com o mês de entrega do Preparo).

## Decisões

### D1. Tudo no navegador
A tela busca, calcula, desenha e exporta no navegador, como os PDFs de Corretivos. Não há servidor novo. Alternativas descartadas: GitHub Action disparado pelo botão (3–5 min, sem prévia, conta de serviço do Supabase em secret) e agente local com fila (continua dependendo do notebook).

### D2. Quem acessa: ferramenta própria
A apresentação é uma ferramenta do Hub, no padrão de Mapas de aplicação: módulo `apresentacao` em `hub.modulos`, liberado por usuário em Usuários → Ferramentas (`hub.usuario_modulos`). Função nova `hub.pode_usar_apresentacao()` = admin ou tem o módulo `apresentacao`, como `hub.pode_usar_corretivos()`. Não depende do nível nos módulos Plantio/Preparo/Colheita/Drone. O cartão em Ferramentas, no início do Hub, só aparece para quem passa nela; liberar dá acesso a tudo (metas, textos, download).

### D3. Liberdade de edição
- **Parâmetros da semana:** semana (ex.: S1M11) e data de corte, sugeridas pela regra da quinta-feira (semana N do mês = N-ésima quinta; corte = dia anterior à quinta), e as metas.
- **Textos por slide:** subtítulo, destaque/observação e notas do apresentador. Vazio = texto padrão de hoje.
- **Fora:** ligar/desligar ou reordenar slides, ajuste manual de número, layout livre. Para isso, baixar o PPTX e editar no PowerPoint.

### D4. Drone de aplicação vira dado do Hub (parte 1 do trabalho)
View nova `hub.drone_projetos_v`: uma linha por revisão vigente do módulo Drone (`projetos.modulo_id = 'drone'`, `projeto_revisoes.vigente`), com `cod_faz`, `documento` (normal | catacao), `area_aplicacao_ha` e `safra` ('26/27').
- **Projeto feito no Hub:** `area_aplicacao_ha` = `drone_geracoes.resumo->>'aplicacao_ha'` da geração `publicada` cuja solicitação aponta para a revisão; `safra` pela data de publicação (`drone_solicitacoes.concluido_em`), virando em 1º de abril.
- **Projeto do legado:** duas colunas novas em `hub.projeto_revisoes`: `area_aplicacao_ha numeric` e `safra text`, nulas para os outros módulos. Preenchidas uma única vez por `drone/carga_area_safra.py`: área = soma do campo de área do shape publicado (mesma leitura de `importar_legado.py`/`extrair.py`); safra = a gravada no `motivo` da revisão na importação (pasta "2025-2026" ou "25/26 Rev"), a mesma regra que o `gerar.py` usa hoje. Revisões que o script não resolver ficam listadas no relatório dele e nulas na view.
- A regra continua sendo "ha que a Geo **projetou**", todos os produtos.
- Projetos novos publicados aparecem sozinhos, sem carga.

### D5. Voos pelo Worker
Rota nova `GET /voos-indicadores?de=&ate=` em `worker/arquivos.js`: confere o JWT do Hub (mesmo esquema das rotas atuais), exige `pode_usar_apresentacao`, chama `https://geomap-docker.onrender.com/integracao/voos/indicadores` com `x-indicadores-token` e devolve o JSON. `INDICADORES_TOKEN` fica só nos secrets da Cloudflare.

### D6. Metas e rascunho no Supabase
- `hub.apresentacao_metas` (chave, valor, rotulo, atualizado_por, atualizado_em). Carga inicial: `meta_ervas_ha` 20863, `meta_fornecedor_ha` 3500, `meta_ha_dia` 250, `drone_pendente_ha` 2000, `safra_atual` '26/27', `inicio_safra` '2026-04-01'. Valem para as semanas seguintes; salvar é explícito ("Salvar metas").
- `hub.apresentacao_semanas` (semana pk, corte date, textos jsonb, atualizado_por, atualizado_em). `textos` = `{ "<slide>": { "subtitulo", "destaque", "notas" } }`. Salvo sozinho ~2 s após parar de digitar; vale o último que salvou, campo a campo.
- RLS nas duas: lê e grava só quem passa em `pode_usar_apresentacao()`.

## Arquitetura

Protótipo navegável das telas (entrada, busca, edição com prévia, falha do GeoMap, acesso): https://claude.ai/artifact/DBwux9Cmjqhj7LX8KMdk5E

Tela `app/apresentacao.html` com três áreas: parâmetros (semana, corte, metas), lista dos 6 slides com seus campos de texto, prévia 16:9 do slide selecionado.

| Arquivo | Faz | Depende de |
|---|---|---|
| `app/apresentacao-dados.js` | Busca: views/tabelas do Supabase (Colheita, Preparo, Plantio, `drone_projetos_v`, metas, rascunho) e voos pelo Worker | cliente Supabase do Hub, Worker |
| `app/apresentacao-calculo.js` | Funções puras: dados brutos + corte + metas → indicadores dos 6 slides. Porta as regras do `gerar.py` | nada |
| `app/apresentacao-slides.js` | Indicadores + textos → HTML dos slides no frame do design system Pedra (banner, selo, régua lateral, rodapé "S1M11 · Dados até dd/mm/aaaa") | assets em `app/assets/` |
| `app/apresentacao-exportar.js` | HTML dos slides → PPTX com cada slide como imagem 16:9 e notas do apresentador | PptxGenJS e html-to-image (CDN, versões fixas) |

Regras portadas do `gerar.py` (comentário no topo de `apresentacao-calculo.js`):
- Colheita: status do Hub; Sem Linhas não é concluído; "BIS - N" soma na Frente N.
- Sistematização = Preparo; entregue = talhão Ok; mês = data de entrega no Hub (spec de 28/10).
- Plantio: concluído = status Ok.
- Voos: números da API do GeoMap; metas de D6.
- Drone: realizado = ha da safra atual em `drone_projetos_v`; progresso = realizado ÷ (realizado + pendente); base vigente por safra (atual, 25/26, 24/25, anteriores/sem safra).
- Divisória resume os 5 indicadores com os mesmos números.

## Fluxo

1. Abre a tela: semana e corte sugeridos; carrega metas e, se existir, o rascunho da semana.
2. **Buscar dados:** as fontes carregam em paralelo, cada uma com status (carregando / ok / falhou).
3. A prévia monta os 6 slides. Editar texto ou meta só recalcula e redesenha.
4. **Baixar PPTX:** `s1m11 - Apresentacao Geotecnologia - Indicadores e Entregas.pptx`.

## Erros

- **GeoMap lento ou fora:** espera até 3 min com aviso ("a primeira chamada do dia leva ~2 min"). Se falhar, o slide de Voos mostra "dados indisponíveis" e **Tentar de novo**. O PPTX só é liberado com os 6 slides com dados.
- **Revisão de drone sem área ou safra na view:** entra em "anteriores / sem safra" ou fica fora da soma, e a tela lista quais. Avisa, não bloqueia.
- **Dois editores na mesma semana:** último que salvou vence; a tela mostra "editado por Fulano às 14:32".
- **Sessão expirada:** volta ao login; rascunho já está salvo.

## Testes

- `tests/app/apresentacao_puro.test.js`: cada regra de cálculo com dados pequenos (Sem Linhas, BIS, Preparo Ok/mês de entrega, Plantio Ok, % drone, regra da quinta-feira, formatação BR 20.863 e 12,5%).
- `tests/drone/test_drone_projetos_v.py`: projeto do Hub pega ha do `resumo`; projeto do legado pega das colunas; revisão não vigente fica fora; safra vira em abril.
- `tests/drone/test_carga_area_safra.py`: leitura do campo de área e safra do catálogo, com ZIP de exemplo.
- Worker: sem JWT → 401; sem permissão → 403; o token nunca aparece na resposta.
- **Paridade com o deck atual:** mesma semana e corte no `gerar.py` e na tela; os 6 slides batem número a número. No drone só se aceita a diferença dos ZIPs que falhavam no `extrair.py`, explicada. Na primeira semana gera-se pelos dois caminhos; os scripts só são aposentados depois do ok do Leo.
- Visual: prévia e PPTX comparados com os PNGs da última semana (frame, fontes, quebras); PPTX abre no PowerPoint com as notas.

## Ordem de entrega

1. View do drone + colunas + carga do legado (útil sozinha: dashboard e Consultas podem usá-la).
2. Tabelas de metas/rascunho, `pode_usar_apresentacao`, rota do Worker.
3. Cálculo puro + testes.
4. Tela, slides e exportação; validação de paridade.

## Fora do escopo

Guardar o PPTX gerado no Hub, histórico de versões dos textos, ligar/desligar slides, ajuste manual de número, layout livre, geração agendada.
