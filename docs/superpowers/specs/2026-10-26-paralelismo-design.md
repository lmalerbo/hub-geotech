# Paralelismo: análise do executado de plantio a partir do pen-drive

**Data:** 26/10/2026 · **Status:** aprovada em 29/10/2026 (fila de pen-drives, validação pelo editor antes do BI, acesso pelos níveis por usuário que o Hub já tem).

## 1. Objetivo

Levar para o Hub a análise de paralelismo do plantio da Usina da Pedra (cana e torta), hoje feita por scripts no notebook (`base-op/scripts/paralelismo_talhao.py` + `gerar_dash.py` + `BI_Paralelismo.html`). O usuário escolhe a pasta do pen-drive, confere o que foi encontrado, a análise roda **no navegador** e o resultado por talhão fica publicado no Hub, com painel e relatório gerencial. Os arquivos brutos ficam **arquivados como prova técnica** do que foi analisado.

Fora do escopo: AgroCAD/FME (as análises antigas entram só como histórico), mapa de amostras na tela, aviso no sininho, integração com O.S.

## 2. Onde fica

- Página própria **`app/paralelismo.html`** (+ `app/paralelismo.js`, `app/paralelismo-worker.js`), no site do Hub, como o Corretivos. Mesmo login.
- Cadastrada no menu **Ferramentas** (parâmetro `ferramentas`). Não entra no menu de módulos.
- **Acesso:** usa o controle por usuário que o Hub já tem, sem regra nova. Módulo `paralelismo` em `hub.modulos`, escondido do menu lateral; o nível de cada pessoa fica em `hub.usuario_modulos.nivel` e o admin define na tela de **Usuários**. Ali o Paralelismo ganha um cartão com o mesmo seletor dos módulos (Sem acesso, Leitura, Solicitante, Editor; hoje a opção Solicitante só aparece no Drone). O que cada nível faz:
  - **leitura:** painel (só rodadas publicadas), relatório, downloads;
  - **solicitante:** também processa pen-drives e envia a rodada para validação;
  - **editor:** também valida, ou seja, publica ou recusa as rodadas pendentes, e edita a tabela de frotas. O editor também pode processar;
  - **admin:** também exclui rodada publicada.

## 3. Regras do domínio

**Pipeline (igual ao validado, parâmetros fixos no código):**
1. Leitura:
   - `.jdl` (JDLink): trilha do trator, a cada 0,2 s, só nos instantes com estado de trabalho ligado.
   - GS3_2630 (`.fdl`/`.fdd`): antena do trator `_5140`, registros com gravação ligada.
2. Por frota e fazenda: LSFP 10 m → QBD 160° → CLE 10 m.
3. Na união das linhas da fazenda: `limpar` (passadas empilhadas, cruzamentos, linhas isoladas).
4. PLL:
   - amostra a cada 10 m;
   - ideal 2,90–3,10 m; ignora fora de 2,60–3,40 m.
5. Cada amostra vai para o talhão (polígono) onde cai. Talhão com **menos de 25 amostras** = "amostra insuficiente".
6. **Aderência** = amostras aderentes / amostras, ponderada por amostra.

**Frota:**
- Vem do **nº de série do trator** gravado no `.jdl` (`BM\d{4}[A-Z]\d{6}`), pela tabela de frotas. O nome da pasta não é confiável.
- O GS3 não grava série: na conferência, o usuário escolhe a frota de cada pasta GS3, já preenchida pelo número no nome da pasta.
- **Prestador** (PLANT CANA, Antonio Tittoto, Gabriel Prudente) aparece com o nome, sem número de frota.
- **Operação** (cana/torta) vem da frota.

**Fazenda:**
- Vem do nome gravado no monitor: pasta do log do `.jdl` (`..._10010Rev1_Parte 1`) ou `Farm` do `.fdl`.
- Os 5 dígitos dão o `cod_faz`; a revisão (`Rev1`) fica como informação.
- O talhão de cada amostra sai da geometria, não do nome.

**Rodada** = um pen-drive (um ou mais tratores). Situações:
- **na fila / processando:** só no navegador de quem processa; nada no banco;
- **pendente:** enviada para validação, com os brutos arquivados e os resultados no banco, mas **fora do painel e do relatório**;
- **publicada:** um editor validou e as análises dela viram as vigentes;
- **recusada:** um editor recusou, com motivo. As linhas dela não entram em nenhuma análise, e os brutos continuam arquivados.

**Arquivo repetido:**
- Todo arquivo bruto é identificado pelo **SHA-256**.
- Se o arquivo já foi analisado em outra rodada, é ignorado e aparece como "já analisado".
- Isso resolve o mesmo pen-drive copiado duas vezes e o GS3 que acumula sessões antigas.

**Fazenda que recebe dados novos:**
- A análise vigente de uma fazenda e operação junta as **linhas guardadas de todas as rodadas** daquela fazenda com as linhas novas, e refaz `limpar` + PLL.
- Assim não é preciso baixar de novo os brutos antigos.
- Exemplo: em 26/10, a 10966 juntou os dados da 64086/64088 de out com os de antes, e passou de 80,6% para 88,9%.

**Mês de execução:** o mês com mais amostras da análise (pela data das linhas).

## 4. Fluxo de uma rodada

**Fila (solicitante ou editor):** dá para incluir vários pen-drives em sequência. Enquanto um processa, o usuário escolhe e confere o próximo. A fila roda um pen-drive por vez, num único Web Worker, e mostra a situação de cada um: na fila, processando com %, pronto para revisar, erro.

1. **Escolher a pasta** do pen-drive (`<input webkitdirectory>`).
   - A página calcula o SHA-256 de cada arquivo e **copia os arquivos para o armazenamento do navegador (OPFS)**. Ao terminar, avisa "pode retirar o pen-drive".
   - A cópia é necessária porque o navegador perde o acesso aos arquivos quando o pen-drive sai, e a fila precisa deles depois.
   - A cópia é apagada quando a rodada é enviada ou descartada.
2. **Conferência** (nada processado ainda): tabela por trator, com série, frota, operação, fazendas, nº de arquivos e situação. Avisos:
   - **série desconhecida:** abre o cadastro de frota ali mesmo;
   - **pasta GS3 sem documentação** (só mapa de cobertura e linhas-guia, como a 62571 em 26/10): "sem executado, exportar de novo com Documentation";
   - **arquivos já analisados.**
3. **Adicionar à fila** → processar:
   - Pyodide num Web Worker (a tela não trava), com barra de progresso por fazenda.
   - Tempo medido no teste: 16 s para uma fazenda de torta pequena; 2,3 min para a 10966, com 144 sessões GS3 e 30 mil amostras.
   - A página precisa ficar aberta enquanto houver item na fila.
4. **Prévia:** aderência por fazenda, talhão e frota, comparada com a análise vigente quando a fazenda já existia. Aviso de **frota sem trabalho registrado**: trilha longa com implemento quase sempre desligado, como a 55805 na 10010 em 26/10.
5. **Enviar para validação**:
   - zipa os brutos no navegador, em partes de até 90 MB, e envia pelo Worker para o GitHub Releases;
   - grava rodada (pendente), arquivos (com SHA-256), linhas e resultados;
   - se o envio dos brutos falha, nada é gravado e o botão permite tentar de novo;
   - os arquivos de uma rodada pendente já contam como "já analisados" para as próximas, o que evita enviar o mesmo pen-drive duas vezes.
6. **Validar (editor):**
   - Aba **Pendentes** com a mesma prévia, quem processou e os avisos.
   - **Publicar:** as análises das fazendas tocadas passam a ser as vigentes e aparecem no painel e no relatório.
   - **Recusar:** pede o motivo.
   - **Fazenda que mudou desde a prévia** (outra rodada da mesma fazenda foi publicada no meio): ao publicar, a tela refaz `limpar` + PLL juntando as linhas vigentes com as da rodada. Isso roda no navegador do editor, leva de 1 a 2 min numa fazenda grande e mostra o resultado novo antes de confirmar.
   - Quem processou pode validar a própria rodada, se for editor.

## 5. Dados (schema `hub`)

```
paralelismo_frotas                -- editável pela tela (editor)
  serie text pk                   -- BM0000X000000; GS3: 'GS3:<frota>'
  frota text not null             -- '55805' ou nome do prestador
  operacao text check (operacao in ('cana','torta'))
  tipo text check (tipo in ('propria','prestador'))
  nomes_antigos text, observacao text

paralelismo_rodadas
  id bigserial pk
  descricao text                  -- ex.: 'pen-drives 26/10/2026'
  release_tag text                -- paralelismo-r<id>
  partes jsonb                    -- [{url, bytes, sha256}]
  status text check (status in ('pendente','publicada','recusada'))
  criado_por uuid, criado_em timestamptz        -- quem processou e enviou
  validado_por uuid, validado_em timestamptz, motivo_recusa text

paralelismo_arquivos              -- prova técnica + deduplicação
  sha256 text pk
  rodada_id bigint fk
  caminho text                    -- caminho relativo dentro do pen-drive
  bytes bigint, tipo text         -- jdl | fdl | fdd
  serie text, frota text, cod_faz int, fazenda_monitor text

paralelismo_linhas                -- linhas após LSFP/QBD/CLE (antes do limpar)
  id bigserial pk
  rodada_id bigint fk on delete cascade
  operacao text, cod_faz int, frota text, data date
  geom geometry(LineString, 31983)

paralelismo_analises              -- uma por (operação, fazenda) a cada rodada que a toca
  id bigserial pk
  operacao text, cod_faz int, rodada_id bigint fk
  metodo text check (metodo in ('trator','agrocad_fme'))
  mes date                        -- 1º dia do mês de execução
  amostras int, aderentes int, acima int, abaixo int
  vigente boolean                 -- a mais recente por (operação, cod_faz)
  amostras_url text               -- shapefile zipado das amostras na release

paralelismo_talhoes
  analise_id bigint fk on delete cascade
  talhao_num int
  amostras int, aderentes int, acima int, abaixo int, media_m numeric
  frotas text[]
  pk (analise_id, talhao_num)
```

- **Declividade:** coluna nova `hub.talhoes.declividade` (numeric; 99 → nulo), alimentada pela Base Fazendas em `ingestao/base_fazendas.py` (campo `DECLIVIDAD`). Área e geometria já vêm de `hub.talhoes` e `hub.talhao_geom`.
- **Enviar** = RPC `hub.paralelismo_enviar(jsonb)` numa transação. Ela grava a rodada pendente, os arquivos, as linhas, as análises (`vigente = false`) e os talhões. Pode chamar: solicitante ou editor.
- **Publicar** = RPC `hub.paralelismo_publicar(rodada_id, recalculo jsonb)`. Grava o recálculo, quando houver, marca a rodada como publicada e troca o `vigente`. Pode chamar: só editor (`hub.pode_editar('paralelismo')`).
- **Recusar** = RPC `hub.paralelismo_recusar(rodada_id, motivo)`. Pode chamar: só editor.
- **RLS:**
  - painel, relatório e leitura: só as análises de rodadas publicadas, com `hub.pode_ver('paralelismo')`;
  - rodadas pendentes: visíveis para solicitante e editor;
  - frotas: escrita só por editor;
  - excluir rodada publicada: admin, com registro em `log_auditoria`.
- **Excluir rodada:** apaga as linhas, as análises e os arquivos dela; as fazendas tocadas voltam para a análise anterior. A release continua no GitHub, porque é prova, e é marcada como "excluída" na descrição.

## 6. Arquivamento dos brutos

- Rota nova no Worker: `POST /paralelismo/parte`, com o login do usuário.
  - O banco confere o acesso (`hub.paralelismo_preparar_parte`).
  - O Worker sobe a parte na release `paralelismo-r<id>` de `lmalerbo/hub-geotech-arquivos`.
- **Esse repositório é público**, e os brutos têm GPS real. O usuário aceitou a exposição por ora (04/11/2026). Ele pretende torná-lo privado depois, com links novos de download. Tornar privado não desfaz o que já tiver sido baixado.
- Cada parte é um zip de até 90 MB, porque o limite do Worker é 100 MB por requisição. Os caminhos do pen-drive são mantidos dentro do zip.
- A release também recebe `manifesto.csv` (caminho; bytes; sha256; frota; fazenda) e os shapefiles de amostras e linhas de cada fazenda, que são o entregável para o GIS.
- Zip no navegador com **fflate** (streaming, versão fixada).

## 7. Telas

- **Painel** (abertura), com o conteúdo do BI atual lendo do banco e só as análises vigentes:
  - **Resumo:**
    - KPIs;
    - aderência por faixa de declividade;
    - aderência por mês;
    - tabela de fazendas.
  - **Talhões:**
    - dispersão aderência × declividade;
    - tabela com busca e "amostra insuficiente";
    - mapa dos talhões pintados pela aderência (MapLibre + `talhao_geom`).
  - **Fazenda:** detalhe, com os talhões e as frotas.
  - **Frentes e frotas.**
  - **Relatório:**
    - escolha de meses por caixa de seleção, padrão os 3 últimos;
    - uma seção por operação e mês;
    - Imprimir / salvar PDF, com o CSS de impressão já corrigido.
- **Processar** (solicitante e editor): escolher pen-drive, conferência, fila com a situação de cada item, prévia e **Enviar para validação**.
- **Pendentes** (editor; o solicitante vê só as próprias): prévia de cada rodada pendente, **Publicar** ou **Recusar**. Um contador aparece na aba.
- **Rodadas:** lista com data, quem processou, quem validou, situação, tratores, fazendas e link dos brutos.
- **Frotas:** tabela editável (editor).

## 8. Processamento no navegador (Pyodide)

**Validado no teste de 26/10/2026:**
- os módulos atuais, sem alteração, deram resultado **idêntico** ao Python nativo:
  - 10233Rev0 (jdl): 2.506 amostras, 77,85%;
  - 10966Rev0 (GS3): 30.395 amostras, 88,86%;
- o navegador ficou cerca de 2,7× mais lento que o Python nativo;
- pacotes do Pyodide 0.27.7 usados: `numpy`, `shapely`, `pyproj`.

**Código:**
- **Fonte única:** pasta `paralelismo/` no repositório do Hub, com `jdl.py`, `gs3.py`, `pipeline.py` e `analise.py`.
  - Vem de `base-op/scripts`: `jdl_rich_fields` (só o necessário), `jdl_documentacao`, `gs3_documentacao`, `paralelismo_pipeline` e a parte de talhão e frota de `paralelismo_talhao`.
  - O workflow do Pages copia a pasta para `app/py/paralelismo/`, como já faz com `mapas/`.
- **Memória:**
  - o JS entrega os arquivos um a um ao Worker, que converte cada um em pontos;
  - por grupo (frota, fazenda), os pontos viram linhas e são descartados;
  - só as linhas ficam na memória até o fim.
- **Shapefile:** o de amostras e linhas é gerado com `pyshp` (puro Python, via `micropip`).
- **Talhões:** os polígonos da fazenda vêm de `talhao_geom` e são convertidos para 31983 dentro do Python.

## 9. Histórico

Script único em `migracao/paralelismo_historico.py`, rodado uma vez no notebook:
- Frotas: `frotas_maquinas.csv` → `paralelismo_frotas`.
- Uma rodada "histórico até 26/10/2026", sem brutos:
  - análises e talhões vindos de `Paralelismo8.xlsx`;
  - método `agrocad_fme` nas 16 fazendas antigas de cana e `trator` nas demais;
  - mês pelo `meses_fazendas.csv` nas antigas.
- Linhas das análises `trator`: a partir dos `*_Linhas.shp` da pasta de resultado mais recente de cada fazenda, para a próxima rodada conseguir juntar dados novos aos antigos.
- `paralelismo_arquivos` com o SHA-256 dos brutos já analisados, tirados de `ORGANIZAR-02`. Assim, um arquivo antigo que reaparecer num pen-drive não é contado duas vezes.

## 10. Erros

- **Pyodide não carrega:** "Não foi possível preparar a análise; recarregue a página". Nada foi gravado.
- **Arquivo corrompido ou truncado** (ex.: `.fdd` cortado): o arquivo é pulado e listado na prévia. A leitura do catálogo GS3 já é limitada ao bloco, sem varrer para sempre.
- **Página fechada no meio:** nada é publicado; é só começar de novo.
- **Amostra fora de talhão:** contada à parte na prévia; acima de 5% numa fazenda, aparece um aviso.

## 11. Testes

- **Python (pytest):**
  - leitores com arquivos de amostra pequenos (um `.jdl` e uma sessão GS3), guardados em `tests/dados/paralelismo/`;
  - pipeline com linhas sintéticas: espaçamento conhecido dá aderência conhecida, e `limpar` remove empilhadas e cruzamentos;
  - **regressão:** 10233Rev0 com 2.506 amostras e 77,85%, contra o resultado atual.
- **JS (`node --test`):** funções puras, como o agrupamento da conferência, a divisão em partes de 90 MB, a mesclagem com a análise vigente e o cálculo do mês de execução.
- **Teste de ponta a ponta (E2E, Playwright, duas contas de teste, uma solicitante e uma editora):**
  - a solicitante coloca duas pastas de amostra na fila e envia;
  - o painel ainda não mostra a rodada;
  - a editora publica uma rodada e recusa a outra, e o painel passa a mostrar só a publicada;
  - no fim, o teste exclui as rodadas de teste.
- **RLS (SQL):** solicitante não consegue publicar e leitura não vê rodada pendente.
- Dado real não vai para executor externo: os arquivos de amostra ficam fora das tarefas delegadas à camada 1.

## 12. Futuro (fora desta entrega)

- Mapa das amostras na tela da fazenda.
- Paralelizar fazendas em mais de um Worker.
- Ler o mapa de cobertura (`.pth`/`.pvf`) do GS3 quando faltar a documentação.
- Outras usinas.
