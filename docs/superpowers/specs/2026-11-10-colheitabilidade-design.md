# Colheitabilidade no Hub — linhas de colheita classificadas em partes (design)

Data: 2026-11-10 · Status: aguardando revisão do usuário

## 1. Objetivo

Levar para o Hub o pipeline de colheitabilidade que hoje roda no `base-op` (no PC do Leo): a equipe sobe as linhas de colheita de uma fazenda (Exp1L ou Exp2L), o Hub classifica as linhas em **partes**, gera o pacote dos monitores e o **Mapa de partes**, mostra uma prévia para conferência e, ao publicar, disponibiliza o projeto e o mapa no **portal de downloads da Colheita**.

Hoje o `.zip` dos monitores e o mapa de partes são feitos à mão (AgroCAD/Civil3D) e enviados na Colheita. Com esta entrega, a equipe envia só as linhas.

**Depois (fora desta spec, cada um com spec própria):**
- Enviar o projeto publicado ao **Operations Center** (API John Deere, org US PEDRA `2285801`) e criar o **plano de trabalho**. A fonte será o shapefile classificado da geração publicada (§4).
- Mover linhas entre partes à mão, quando o **editor de geometrias** (spec de 09/11/2026) sair do laboratório.

## 2. Decisões

| Tema | Decisão |
|---|---|
| Onde roda | **Agente no servidor Geo**, no molde do agente do Drone (fila no banco, laço contínuo). Nada do pipeline roda no navegador. |
| Entrada | `.dwg` (convertido com ODA File Converter no servidor), `.dxf` ou shapefile (`.zip` ou `.shp/.shx/.dbf/.prj` soltos). Um arquivo por tipo (1L ou 2L). |
| Camadas | 1L: `01_Linhas_Vant` + `02_Linhas_Cana`. 2L: `03_Desdobra_Vant` + `04_Desdobra_Cana`. Shapefile: todas as linhas do arquivo. |
| Unidade | Uma **geração** por fazenda e tipo. Subir o 2L não mexe no 1L. |
| Conferência | Prévia obrigatória: **regerar** (outros parâmetros, sem reenviar o arquivo), **publicar** (com nota) ou **descartar**. |
| Mapa de partes | Continua **um documento por fazenda**: PDF com uma página por tipo (1: 1L, 2: 2L), montado na publicação com a versão publicada de cada tipo. Sem o outro tipo, uma página só. |
| Contexto do mapa | Talhões da **base de talhões do Hub**, não mais os DWG de `material-mapa/`. Estilo do mapa: o do `base-op` (talhão inteiro na cor da parte majoritária, número, carimbo lateral, norte, legenda). |
| Código | Pasta nova `colheitabilidade/` na raiz do hub-geotech, copiada e limpa do `base-op` (como o `paralelismo/`): sem caminhos do `G:`, sem `material-mapa`, sem `workflow_status`. |
| Brutos | Na release de trabalho em `lmalerbo/hub-geotech-arquivos`, **pública por ora** (decisão do usuário em 10/11/2026, a mesma do Paralelismo). Tornar privado é trabalho à parte. |
| Envio manual | O envio de hoje (`.dwg` + `.zip` prontos) continua existindo durante a transição ("Já tenho o .zip"). |
| Permissão | Quem pode editar a Colheita (`hub.pode_editar('colheita')`) gera, publica e descarta. Leitura vê a prévia e o portal. |

**Parâmetros padrão (iguais ao validado no `base-op`):** simplificação **0,01 m**; preenchimento com espaçamento máximo de **12 m** entre vértices; tamanho-alvo **1,3 MB** por parte, mínimo **0,7 MB**, máximo **2,0 MB**; distância de conexão de ilha **4,0 m**; fusão de fragmentos entre ilhas abaixo de **0,1 MB**. Regerar pode mudar alvo, mínimo, máximo e distância de ilha.

## 3. Fluxo

```
Hub (Colheita › fazenda)          Worker (Cloudflare)          Banco (hub)               Servidor Geo (agente)
1. sobe DWG/DXF/SHP (1L ou 2L) ─▶ guarda o bruto na release ─▶ colheita_geracoes
                                                               status = na_fila
                                                                     │ agente pega (ciclo ~1 min)
                                                                     ▼
                                                               2. processando: converter → linhas → classificar
                                                                  → mapa (1 página) → pacote .zip → prévia GeoJSON
                                                                  sobe as saídas na release
                                                               status = previa
3. abre a prévia → regerar | publicar | descartar
4. publicar (nota) ────────────────────────────────────────▶ status = publicando
                                                               5. agente monta o PDF de 2 páginas, registra
                                                                  .dwg/.zip no Exp1L|Exp2L e o .pdf no Mapa,
                                                                  grava a nota (colheita_nota_arquivo)
                                                               status = publicada → aparece no portal
```

- **Fases do processamento** (gravadas pelo agente em `fase`, lidas pela tela): `convertendo → lendo linhas → classificando → mapa → pacote → enviando`.
- **Regerar** cria uma geração nova que aponta para o mesmo bruto (`bruto_de`), com os parâmetros novos. A anterior em `previa` vira `descartada`.
- **Nome dos arquivos publicados:** o padrão da Colheita, por exemplo `10503_SANTA.LUZIA.5_Rev0-Exp1L.zip`, `-Exp1L.dwg` e `-Mapa.pdf`. Sem controle de revisão: publicar substitui o arquivo e grava a nota, como hoje (`20261004100000_colheita_nota_arquivo.sql`).
- **`.dwg` no documento Exp1L/Exp2L:** quando a entrada é DWG, o próprio bruto é registrado. Quando é DXF ou SHP, o documento recebe só o `.zip`.

## 4. Dados

### Banco (schema `hub`)

Tabela nova `hub.colheita_geracoes`:

| Campo | Tipo | Observação |
|---|---|---|
| `id` | bigint identity | |
| `cod_faz` | int, FK fazenda | |
| `tipo` | text, `1L`\|`2L` | |
| `status` | text | `na_fila`, `processando`, `previa`, `publicando`, `publicada`, `substituida`, `erro`, `descartada`, com check |
| `fase` | text | fase atual do processamento (§3) |
| `parametros` | jsonb | alvo, mínimo, máximo e distância de ilha; o padrão é preenchido pela RPC |
| `bruto` | jsonb | nome, formato (`dwg`\|`dxf`\|`shp`), sha256, tamanho, url |
| `bruto_de` | bigint, FK `colheita_geracoes` | geração cujo bruto foi reaproveitado (regerar) |
| `saidas` | jsonb | urls de `zip`, `pdf_previa`, `previa_geojson` e `shp_classificado` |
| `relatorio` | jsonb | linhas, partes (nome, linhas, MB), partes fora da faixa, ilhas, avisos |
| `erro` | text | mensagem em português para a tela |
| `nota` | text | nota da publicação |
| `criado_por`, `criado_em`, `publicado_por`, `publicado_em`, `atualizado_em` | | |

Restrições:
- índice único parcial: uma `publicada` por `(cod_faz, tipo)`. Ao publicar, a anterior passa a `substituida` (status extra, histórico).
- índice único parcial: uma `na_fila`/`processando`/`publicando` por `(cod_faz, tipo)`.

`hub.parametros` ganha `colheitabilidade_agente_visto_em` (o "estou vivo" do agente, atualizado a cada ciclo).

RPCs (`security definer`, `search_path = hub`, conferem `pode_editar('colheita')`; as do agente aceitam só `service_role`):
- tela: `colheitabilidade_criar(cod_faz, tipo, bruto)`, `colheitabilidade_regerar(geracao_id, parametros)`, `colheitabilidade_publicar(geracao_id, nota)`, `colheitabilidade_descartar(geracao_id)`.
- agente: `colheitabilidade_pegar()` (pega a mais antiga `na_fila` ou `publicando` com `for update skip locked`), `colheitabilidade_fase(id, fase)`, `colheitabilidade_concluir(id, status, saidas, relatorio, erro)`.
- A publicação registra os arquivos pelo mesmo caminho do envio de hoje (`preparar_envio` + `registrar_arquivo`) e grava a nota com `colheita_nota_arquivo`.

**Linhas não vão para o banco.** No banco fica só o resumo por parte (em `relatorio`). O shapefile classificado da geração publicada, na release, é a fonte da etapa futura do Operations Center. Uma tabela de partes com geometria só entra se essa etapa precisar de SQL.

### Arquivos (GitHub Releases, `lmalerbo/hub-geotech-arquivos`)

- Release de trabalho `colheitabilidade` (uma para o módulo; asset nomeado `g<id>-<arquivo>`): bruto, `shp_classificado.zip`, `previa.geojson`, `previa.pdf`, `pacote.zip`.
- O que vai ao portal é registrado nos documentos da Colheita pelo caminho de hoje.
- **Prévia GeoJSON:** linhas agrupadas por parte (MultiLineString por parte) e simplificadas para exibição (tolerância de 0,5 m), em WGS84. Meta: a fazenda 10003 (cerca de 33 mil linhas por tipo) abre na prévia em até 5 s.

## 5. Núcleo `colheitabilidade/`

| Módulo | Vem de (`base-op/scripts/`) | Responsabilidade |
|---|---|---|
| `leitura.py` | `dxf_para_gen4.py`, `converter_dwg.py` | DWG→DXF pelo ODA (caminho do executável na config), DXF por camadas, shapefile; devolve linhas em EPSG:31983 |
| `preparo.py` | `dxf_para_gen4.py` | simplificação 0,01 m e preenchimento 12 m |
| `partes.py` | `classificar_partes.py` | classificação (algoritmo sem mudança; parâmetros por argumento) |
| `mapa.py` | `gerar_mapa.py` | página do mapa a partir dos talhões do Hub; PDF de 1 ou 2 páginas |
| `pacote.py` | `build_bundle_completo.py`, `build_gs3_2630_*`, `agdata_build`, `aggps_build` | Gen4, GS3_2630, AgData e AgGPS no `.zip` |
| `previa.py` | novo | GeoJSON da prévia e `relatorio` |

Interface única para o agente: `gerar(entrada, tipo, cod_faz, nome_fazenda, talhoes, parametros, pasta) -> Resultado(saidas, relatorio)`, que levanta `ErroColheitabilidade` com mensagem para a tela.

Agente: `colheitabilidade/agente.py`, chamado como o do Drone (`python -m colheitabilidade.agente`), com uma tarefa nova no Agendador do servidor Geo a cada 10 min (se já estiver no ar, a chamada é ignorada).

## 6. Telas

**Envio (janela de envio da fazenda na Colheita, `app/index.html`)**
- Os campos Exp1L e Exp2L aceitam também `.dxf` e shapefile.
- Ao soltar o arquivo: **Gerar pelo pipeline** (padrão) ou **Já tenho o .zip** (envio de hoje).
- Faixa de espera no padrão do Hub com as fases (§3), consultando o status. Pronto: leva para a prévia.
- O código novo da tela fica num arquivo próprio (`app/colheitabilidade-envio.js`), não dentro do `index.html`.

**Prévia (`app/colheitabilidade.html`, no molde do Paralelismo)**
- O mapa é o palco: talhões da fazenda e linhas coloridas por parte, com a legenda de partes e tamanhos.
- Coluna de 380 px: relatório, parâmetros usados, links do PDF e do `.zip` da prévia, ações **Regerar**, **Publicar** (pede a nota) e **Descartar**.
- Histórico das gerações da fazenda e tipo: publicada, substituídas, descartadas, com quem e quando.
- Só tema claro; peças do Hub reaproveitadas (cabeçalho, coluna, faixa de espera, camadas do mapa, `Mo.*`). A **maquete** é o primeiro passo da etapa de telas e precisa do ok do usuário.

**Portal de downloads:** sem mudança.

## 7. Erros

| Situação | O que acontece | O que a tela diz |
|---|---|---|
| DWG que o ODA não converte | `erro` | "Não foi possível abrir este DWG. Salve de novo no CAD ou envie em DXF." |
| Camada esperada ausente | `erro` | "A camada 01_Linhas_Vant não existe neste arquivo. Camadas encontradas: …" |
| Shapefile sem `.prj` ou fora de 31983/4326 | `erro` | "O shapefile não tem projeção (.prj)…" |
| Fazenda sem talhões na base do Hub | `previa` com aviso | mapa sem talhões; aviso no relatório |
| Parte fora da faixa de tamanho | `previa` com aviso | lista das partes no relatório |
| Agente parado (sinal com mais de 10 min e geração na fila) | nada muda no banco | "O servidor Geo não está processando. Avise o Leo." |
| Falha no meio da publicação | continua `publicando`, o agente tenta de novo no próximo ciclo | faixa de espera; depois de 3 tentativas vai para `erro` com o motivo |

Publicar de novo é seguro: os nomes dos arquivos são os mesmos e o Worker substitui o asset.

## 8. Pilares

- **Segurança:** as RPCs conferem `pode_editar('colheita')` no banco; as do agente aceitam só `service_role`. Os textos do usuário (nota, nome do arquivo) chegam ao HTML pelo escape do Hub. Brutos públicos por decisão do usuário. Prova: testes de RLS e permissão com leitura, solicitante e `anon` barrados.
- **Confiabilidade:** publicação idempotente; a migration tem a volta em `supabase/migrations/volta/`, ensaiada no Postgres local dos testes; o usuário aplica no Supabase. Agente parado aparece na tela.
- **Performance:** prévia simplificada, com meta de 5 s na 10003. O número é medido na etapa de telas.
- **Escalabilidade:** banco só com metadados. Teto do envio pelo Worker: 100 MB. Se aparecer DWG maior, usar o envio em partes do Paralelismo.
- **Manutenção:** testes sintéticos no CI; regressão com dados reais das fazendas 10738, 10072 e 10003 (`pytest -m dados_reais`, amostras fora do git porque o repositório é público); runbook de instalação do ODA no servidor Geo; manual do módulo atualizado.
- **Usuário:** espera, vazio e erro previstos nas duas telas; `design:accessibility-review` no fechamento.

## 9. Etapas

| Etapa | Entrega |
|---|---|
| **C0. Núcleo** | `colheitabilidade/` (§5) com testes sintéticos e regressão igual ao `base-op` nas três fazendas (mesmas partes e mesmos bytes do pacote) |
| **C1. Banco** | migration, volta, RPCs, RLS e testes |
| **C2. Agente** | laço, ODA, prévia, publicação com PDF de 2 páginas, sinal de vida, tarefa no Agendador, runbook |
| **C3. Worker** | rota para o bruto e para as saídas na release de trabalho |
| **C4. Telas** | maquete (ok do usuário), envio e prévia |
| **C5. Ponta a ponta** | uma fazenda real do envio ao portal; corte para a equipe |

Cada etapa termina com testes passando, `verification-before-completion`, `requesting-code-review` e o ok do usuário antes de mesclar na `main`.

## 10. Fora de escopo

- Envio ao Operations Center e plano de trabalho.
- Edição manual de partes (depende do editor de geometrias).
- Gerar as linhas (o DWG continua saindo do AgroCAD/Civil3D).
- Tornar as releases privadas.

## 11. Riscos

- **ODA no servidor Geo** sem admin: o `base-op` já extraiu o ODA com `msiexec /a` em `%LOCALAPPDATA%`. Repetir na conta `geotecnologia` e testar na C2 antes de qualquer outra coisa.
- **Mapa com talhões do Hub em vez do DWG de contexto:** o número do talhão e o contorno podem diferir do mapa de hoje. Comparar uma fazenda lado a lado na C0.
- **AgData usa AES com chave derivada do UUID:** a lib de criptografia precisa estar no `requirements.txt` do servidor.
