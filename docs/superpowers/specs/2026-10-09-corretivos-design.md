# Corretivos: gerador de mapa de aplicação de corretivos

**Data:** 09/10/2026 · **Status:** aprovada em 11/10/2026 (inclusive as 7 decisões: acesso por módulo, aplicação repetida recusada, salvamento automático, exclusão com confirmação, quadros separados por Blend, layout comum com teste de regressão do Drone, fonte Selawik). Desenvolvimento a partir de 13/10/2026 às 7h.

## 1. Objetivo

Substituir o mapa de corretivos feito à mão no QGIS. O usuário escolhe a fazenda, marca talhões, lança as aplicações (produto, dose, O.S.) e baixa um PDF pronto para o **operador no campo**. O foco é o operador entender o mapa de relance.

Fora do escopo: publicar no portal, fila/aprovação, avisos no sininho, shapefile para máquina, integração com o sistema de O.S.

## 2. Onde fica

- Página própria **`app/corretivos.html`** (+ `app/corretivos.js`), no mesmo site do Hub (GitHub Pages), ao lado do `portal.html`.
- Mesmo login do Hub (Supabase Auth). Sem login, mostra a tela de entrada do Hub.
- Cadastrada no menu **Ferramentas** do Hub (parâmetro `ferramentas`, editado pelo admin). Não entra no menu de módulos.
- **Acesso:** módulo novo `corretivos` em `hub.modulos`. Usa quem é admin ou tem o módulo liberado em `hub.usuario_modulos` (qualquer papel). O admin libera na tela de Usuários, como os outros módulos. O menu lateral do Hub ignora o módulo `corretivos` (ele só aparece em Ferramentas).

## 3. Regras do domínio

**Mapa** = uma fazenda + uma **operação** (SubSolagem, SuperGrade ou Arado) + data. A fazenda pode ter vários mapas ao mesmo tempo, independentes. Não há versões: o mapa é editado e o PDF baixado de novo.

**Tipos de aplicação:**

| Tipo | Subtipo | Doses (t/ha) |
|---|---|---|
| Calcário | Dolomítico ou PH7 | 1 |
| Fosfato | — | 1 |
| Blend | calcário Dolomítico ou PH7 + Gesso | 2 (calcário e gesso) |

- Cada aplicação tem **dose** (digitada, > 0), **O.S.** (texto digitado, obrigatório) e a lista de **talhões** em que entra.
- **Total = área do talhão × dose**, em toneladas, calculado sempre (nunca gravado). No Blend, um total para o calcário e outro para o gesso.
- Uma aplicação vale para o talhão inteiro. Um talhão pode receber mais de uma aplicação (sem limite fixo).
- Um mapa pode ter várias O.S. (uma por aplicação).
- **Área:** vem da área produtiva da Base (`hub.talhoes.area_ha`). O usuário pode editar a área de um talhão no mapa; a edição vale para todas as aplicações daquele talhão naquele mapa e fica marcada como editada.
- A mesma aplicação (mesmo tipo/subtipo/dose/O.S.) lançada de novo num talhão que já a tem é recusada (evita duplicar).

## 4. Dados (schema `hub`)

```
corretivo_mapas
  id bigserial pk
  cod_faz int not null            -- fazenda da Base
  operacao text not null check (operacao in ('subsolagem','supergrade','arado'))
  data date not null default current_date
  criado_por uuid, criado_em timestamptz
  alterado_por uuid, alterado_em timestamptz

corretivo_talhoes                 -- talhões que entram no mapa
  mapa_id bigint fk on delete cascade
  talhao_num int
  area_ha numeric not null        -- copiada da Base ao entrar; editável
  area_editada boolean not null default false
  pk (mapa_id, talhao_num)

corretivo_aplicacoes
  id bigserial pk
  mapa_id bigint fk on delete cascade
  tipo text check (tipo in ('calcario','fosfato','blend'))
  calcario text check (calcario in ('dolomitico','ph7'))   -- obrigatório em calcario/blend, nulo em fosfato
  dose numeric not null check (dose > 0)                   -- calcário/fosfato; no blend, a dose do calcário
  dose_gesso numeric check (dose_gesso > 0)                -- só no blend (obrigatória)
  os text not null
  ordem int                                                -- ordem de lançamento (1ª, 2ª…)

corretivo_aplicacao_talhoes
  aplicacao_id bigint fk on delete cascade
  mapa_id bigint, talhao_num int  -- fk para corretivo_talhoes (o talhão precisa estar no mapa)
  pk (aplicacao_id, talhao_num)
```

- Talhão sai de `corretivo_talhoes` quando não tem mais nenhuma aplicação (limpeza feita pela tela ao remover).
- **RLS:** ler e escrever só quem `hub.pode_usar_corretivos()` (admin ou módulo `corretivos`). Escrita direta nas tabelas pelo supabase-js (sem RPC), com `alterado_por/alterado_em` preenchidos por trigger.
- Excluir mapa: permitido a quem tem acesso, com confirmação; vai para o `log_auditoria`.
- Geometria: `hub.talhao_geom` (4326, já existe, atualizada pela rodada diária). Talhão do mapa que não está mais na Base aparece com aviso na tela e fica fora do desenho do PDF (mas continua na tabela).

## 5. Telas

**Lista (abertura):** busca de fazenda → mapas da fazenda (operação, data, O.S., quem alterou) → abrir ou **Novo mapa** (pede operação).

**Tela de trabalho (layout A aprovado):**
- Mapa grande à esquerda (MapLibre, igual ao Drone) com os talhões da fazenda pintados pela aplicação (meio a meio quando há duas). Clicar marca/desmarca (contorno verde). "Selecionar todos" e "Limpar seleção".
- Painel à direita:
  - **Nova aplicação:** talhões marcados com a área de cada um (editável), tipo → subtipo → dose(s) → O.S. → **Aplicar aos marcados**.
  - **Lista das aplicações** do mapa: cor, produto, dose, O.S., talhões, total em t. Clicar destaca os talhões no mapa; dá para editar (dose, O.S., talhões) ou excluir.
  - **Baixar PDF.**
- Salva a cada ação (sem botão Salvar).

## 6. Visual

**Paleta (uma cor por tipo):**

| Tipo | Cor |
|---|---|
| Calcário Dolomítico | `#2f6db5` azul |
| Calcário PH7 | `#22a39f` verde-água |
| Fosfato | `#e07b1a` laranja |
| Blend (qualquer calcário) | `#7b4fb3` roxo |
| Sem aplicação | `#e4e7e8` cinza |

**Duas aplicações no mesmo talhão:** meio a meio na diagonal (opção B aprovada), na ordem de lançamento. Com três ou mais, faixas iguais.

## 7. PDF

Mesmo esqueleto do PDF do Drone (layout v6: faixa verde, mapa com logo e escala, tabela, carimbo, orientação automática, tabela longa nas páginas seguintes). Muda:

- **Mapa:** talhões pintados pela aplicação (meio a meio), cinza sem aplicação, número do talhão; legenda só com os tipos usados + "◩ duas aplicações".
- **Tabela "APLICAÇÕES POR TALHÃO":** Talhão · Área (ha) · Aplicação · Dose (t/ha) · Total (t) · O.S. Uma linha por aplicação; o Blend abre em "Blend · Dolomítico" e "+ Gesso". Área editada com `*` e nota. Linha de total da área.
- **Carimbo:** tag `CORRETIVO · <OPERAÇÃO>`; fazenda; abaixo "MAPA DE APLICAÇÃO · CORRETIVOS · O.S. …". Um **quadro por produto** com o total em t: Calcário Dolomítico, Calcário PH7, Fosfato e **Blend à parte** (Blend Dolomítico e Blend PH7 como quadros separados se ambos existirem; dentro do quadro do Blend, o detalhe "calcário X t + gesso Y t"). Quadros só dos produtos usados. Linha com escala, área total e nº de talhões, safra.
- Rodapé: "Gerado em dd/mm/aaaa por <nome>". Sem "Revisão".
- Nome do arquivo: `corretivo_<cod_faz>_<operacao>_<aaaa-mm-dd>.pdf`.

## 8. Geração do PDF no navegador (Pyodide)

Validado no teste de 09/10/2026: o `drone/mapa_pdf.py`, sem alteração, rodou no navegador e gerou PDF **idêntico** ao do servidor (0% de pixels diferentes). Tempos: 15–30 s na 1ª abertura sem cache, ~5 s no 1º PDF, < 1 s nos seguintes.

- Pyodide (jsdelivr, versão fixada) + pacotes `matplotlib`, `shapely`, `pandas`, `pyproj`, `geopandas`.
- Carrega **em segundo plano** quando a página abre; o botão "Baixar PDF" mostra "preparando…" até ficar pronto.
- **Código compartilhado:** o layout comum (página, faixa, moldura, logo, escala, grade da tabela, carimbo, paginação) sai do `drone/mapa_pdf.py` para um módulo comum `mapas/layout.py`; `drone/mapa_pdf.py` e o novo `mapas/corretivo_pdf.py` usam esse módulo. O PDF do Drone não pode mudar (teste de regressão compara com o PDF atual).
- **Deploy:** o workflow do Pages copia `mapas/*.py` e o logo para `app/py/` (fonte única no repositório; o gatilho do workflow passa a incluir `mapas/**`).
- **Fonte:** Selawik (licença aberta da Microsoft, mesmas medidas da Segoe UI), servida em `app/py/fontes/`. A Segoe UI não pode ser publicada. O Drone continua com Segoe UI no servidor por enquanto.
- Entrada do gerador: geometria de `talhao_geom` (4326) convertida para 31983 dentro do Python; aplicações e áreas montadas pela tela em JSON.

## 9. Erros

- Pyodide não carrega (rede/CDN): mensagem "Não foi possível preparar o gerador de PDF; recarregue a página" e botão Tentar de novo. Os dados do mapa já estão salvos.
- Fazenda sem geometria em `talhao_geom`: tela avisa e o PDF sai sem o desenho daquele talhão.
- Validações na tela antes de gravar: talhão marcado, dose > 0, O.S. preenchida, subtipo e (no Blend) dose do gesso. O banco repete as checagens (checks/constraints).

## 10. Testes

- **Python (pytest):** `mapas/corretivo_pdf.py` — linhas da tabela (Blend abre em duas, área editada com `*`), totais por produto (Blend separado), cores/meio a meio, paginação com muitas linhas; regressão do Drone (PDF de amostra igual ao atual).
- **JS (`node --test`):** funções puras da tela — total por aplicação, totais por produto, validação do formulário, montagem do JSON para o gerador.
- **E2E (Playwright, conta de teste):** cria um mapa numa fazenda de teste, lança 2 aplicações (uma Blend) em talhões que se sobrepõem, edita uma área, baixa o PDF no navegador, confere o PDF e **exclui o mapa de teste** (dado criado pelo próprio teste, não dado real).

## 11. Futuro (fora desta entrega)

- Levar a geração do PDF do Drone para o navegador com a mesma tecnologia (dispensaria o agente para o PDF).
