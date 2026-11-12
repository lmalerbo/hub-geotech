# Paralelismo nos dois pontos (implemento e trator): plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar tarefa por tarefa. Os passos usam caixa (`- [ ]`).

**Objetivo:** cada rodada passa a analisar e gravar os dois pontos, o implemento e o trator. O Painel e o Relatório mostram os dois, com o seletor "Os dois" (padrão) | Implemento | Trator. O histórico é refeito a partir dos BRUTOS.

**Arquitetura:** os leitores leem cada arquivo uma vez e devolvem os dois conjuntos de pontos. O `Grupo` mantém duas listas e, no `fechar`, entrega as linhas dos dois pontos. O Worker roda `analisar` uma vez por ponto. No banco, as linhas e as análises ganham a coluna `ponto`, e a análise vigente passa a ser definida por (operacao, cod_faz, ponto). O `metodo` passa a ser `pipeline` ou `agrocad_fme`.

**Stack:** Python 3.12 (núcleo `paralelismo/`, Pyodide no navegador), PostgreSQL/Supabase (schema `hub`), JS puro (`app/paralelismo*.js`), MapLibre, pytest, `node --test` e Playwright.

**Spec:** `docs/superpowers/specs/2026-10-26-paralelismo-design.md` (§3 "Ponto da análise", §4, §5, §7, §9 e §11, ajustados e aprovados em 10/11/2026). Ele complementa o plano mestre `docs/superpowers/plans/2026-10-29-paralelismo.md`, sem substituí-lo: o que este plano não muda continua valendo como está lá.

## Restrições globais

- Valores de `ponto`: `'implemento'` e `'trator'`. Valores de `metodo`: `'pipeline'` e `'agrocad_fme'`. `agrocad_fme` só existe com `ponto = 'implemento'`.
- Uma rodada do pipeline grava SEMPRE os dois pontos de cada fazenda. Uma rodada que traga só um deles é recusada (`rodada_sem_os_dois_pontos:<operacao>/<cod_faz>`).
- Pontos de origem: `.jdl` implemento = pontos de PLANTIO do GOIMP (`pontos_plantio`); `.jdl` trator = trilha de 0,2 s filtrada pelo estado de trabalho (`pontos_trator`). GS3 implemento = antena `5141`; GS3 trator = antena `5140`.
- Os parâmetros do pipeline não mudam: LSFP 10 m, QBD 160°, CLE 10 m, PLL a cada 10 m, ideal de 2,90 a 3,10 m, amostras ignoradas fora de 2,60 a 3,40 m.
- A migration nova é `supabase/migrations/20261112090000_paralelismo_dois_pontos.sql`, com o script de volta em `supabase/migrations/volta/20261112090000_paralelismo_dois_pontos_volta.sql`. Ela NÃO é aplicada pelo agente: o usuário aplica no SQL Editor.
- Nunca commitar `.jdl`, `.fdl` ou `.fdd` reais (o repositório é público). A regressão com dado real roda só com `pytest -m dados_reais` e as variáveis de ambiente.
- Só tema claro no Painel. As peças da tela são reaproveitadas, sem criar um layout-modelo novo.
- Textos da tela em pt-BR. Diferença em pontos percentuais, escrita "p.p." com uma casa decimal (ex.: "+14,3 p.p."), calculada como implemento − trator.

## Foco da revisão

1. **Fazenda só com AgroCAD (16 sem brutos):** no modo "Os dois", o trator aparece como "sem dado" e a diferença fica vazia. A média geral do trator não pode tratar essa fazenda como 0%.
2. **Rodada nova sobre uma fazenda AgroCAD:** a vigente `agrocad_fme` do implemento é trocada pela do pipeline, e a do trator nasce. O `base_analise_id` do trator é nulo, e isso não pode virar `recalculo_necessario`.
3. **Arquivo em que um ponto vem vazio** (ex.: `.jdl` sem documentação mas com trilha): o arquivo é legível, o ponto vazio dá zero linhas e o outro segue. A fazenda só é enviada se os dois pontos tiverem análise, mesmo com zero amostras.
4. **Memória no navegador:** duas listas de pontos por frota dobram o pico. A 10966 (a maior) precisa caber. O teste do Worker mede o pico com `performance.memory` no Edge.
5. **Excluir rodada:** ao excluir, a vigente anterior volta POR PONTO. Se a anterior era AgroCAD no implemento e não havia trator, o trator fica sem vigente.

---

## Mapa de arquivos

| Arquivo | Muda o quê |
|---|---|
| `supabase/migrations/20261112090000_paralelismo_dois_pontos.sql` (novo) | colunas `ponto`, `metodo` novo, índices e RPCs refeitos |
| `supabase/migrations/volta/20261112090000_paralelismo_dois_pontos_volta.sql` (novo) | desfaz a migration (apaga as linhas do implemento) |
| `paralelismo/jdl.py`, `paralelismo/gs3.py` | `ler_jdl_pontos` e `ler_gs3_pontos`: um arquivo, os dois pontos |
| `paralelismo/navegador.py` | `Grupo` com duas listas e `fechar` por ponto |
| `app/paralelismo-worker.js`, `app/paralelismo.js` | análise e prévia por ponto e envio com `ponto` |
| `app/paralelismo-puro.js` | mescla com a vigente por ponto e agregações do Painel com seletor |
| `app/paralelismo.html/.css/.js` (Painel, Fazenda, Relatório) | seletor e colunas duplas |
| `migracao/paralelismo_historico.py` (novo, S7) | reprocessa os BRUTOS e importa as 16 do AgroCAD |
| `tests/paralelismo/test_banco_sql.py`, `test_navegador.py`, `test_leitores_sinteticos.py`, `test_regressao.py`, `tests/app/paralelismo_puro.test.js`, `tests/app/teste_paralelismo_tela.py` | testes |

---

### Tarefa 1: migration dos dois pontos (camada 3, opus)

**Arquivos:**
- Criar: `supabase/migrations/20261112090000_paralelismo_dois_pontos.sql`
- Criar: `supabase/migrations/volta/20261112090000_paralelismo_dois_pontos_volta.sql`
- Testar: `tests/paralelismo/test_banco_sql.py` (fixture `enviar` passa a mandar os dois pontos)

**Interfaces:**
- Produz:
  - `hub.paralelismo_linhas.ponto text not null check (ponto in ('implemento','trator'))`.
  - `hub.paralelismo_analises.ponto text not null` (mesmo check) e `metodo text not null default 'pipeline' check (metodo in ('pipeline','agrocad_fme'))`, mais `check (metodo <> 'agrocad_fme' or ponto = 'implemento')`.
  - `unique (rodada_id, operacao, cod_faz, ponto)` e o índice único `(operacao, cod_faz, ponto) where vigente`.
  - Índice de linhas `(operacao, cod_faz, ponto)`.
  - `hub.paralelismo_linhas_vigentes(p_operacao text, p_cod_faz int, p_ponto text, p_rodada_id bigint default null) returns jsonb`: a assinatura antiga é removida com `drop function`, e as permissões são refeitas no mesmo laço `revoke/grant` da migration de 04/11.
  - `paralelismo_enviar(p jsonb)`: cada item de `linhas` e de `analises` exige `ponto`. A falta dele ou um valor inválido dispara `ponto_invalido`. O `metodo` é sempre `'pipeline'` (o RPC não aceita `agrocad_fme`, que só entra pela importação do histórico).
  - `paralelismo_publicar(p_rodada_id, p_recalculo)`: cada item do recálculo traz `ponto`. A comparação com a vigente, a troca de `vigente` e o `recalculo_necessario:<op>/<faz>/<ponto>` passam a ser por ponto.
  - `paralelismo_excluir`: o bloqueio e a volta da anterior passam a ser por (operacao, cod_faz, ponto).

- [ ] **Passo 1: testes que falham** em `test_banco_sql.py`. A fixture `enviar` monta, para cada fazenda, duas análises e as linhas com `ponto` em cada uma. Testes novos:
  - `test_rodada_grava_os_dois_pontos`: depois de enviar e publicar, `select ponto, vigente from hub.paralelismo_analises where rodada_id=%s order by ponto` == `[('implemento', True), ('trator', True)]`.
  - `test_enviar_sem_um_dos_pontos_recusa`: só o trator → `erro(r, 'rodada_sem_os_dois_pontos:cana/')`, e `conta_linhas(banco,'paralelismo_linhas',rid) == 0`.
  - `test_enviar_sem_ponto_recusa`: análise sem a chave `ponto` → `erro(r, 'ponto_invalido')`.
  - `test_linhas_vigentes_por_ponto`: linhas do implemento com 2 itens e do trator com 3 → `len(LINHAS(op,faz,'implemento',None)['linhas']) == 2`, e o mesmo para o trator, com 3.
  - `test_rodada_sobre_agrocad_troca_so_o_implemento`: insere direto (como `postgres`) uma análise vigente `ponto='implemento', metodo='agrocad_fme'` sem linhas. Envia e publica uma rodada nova com `base_analise_id` = o id da AgroCAD no implemento e nulo no trator → publica sem `recalculo_necessario`; as duas novas ficam vigentes e a AgroCAD com `vigente=false`.
  - `test_agrocad_so_no_implemento`: um insert com `ponto='trator', metodo='agrocad_fme'` levanta `CheckViolation`.
  - `test_excluir_devolve_a_anterior_por_ponto`: rodadas A e B publicadas, exclui B → as vigentes voltam a ser as de A nos dois pontos.
  - Os testes antigos de publicar, recalcular e excluir passam a conferir os dois pontos, e o `vigente(banco, cod)` ganha o parâmetro `ponto`.
- [ ] **Passo 2:** `python -m pytest tests/paralelismo/test_banco_sql.py -q` → FALHA (coluna `ponto` inexistente).
- [ ] **Passo 3:** escrever a migration. Ordem:
  1. Adicionar `ponto` com `default 'trator'` (as linhas e análises já gravadas são do trator) e depois `drop default`.
  2. Trocar o check de `metodo` e fazer o `update ... set metodo='pipeline' where metodo='trator'`.
  3. Trocar o unique e o índice de vigente.
  4. Refazer os RPCs com `create or replace` (o `drop` só no `linhas_vigentes`, porque a assinatura muda).

  A regra "dois pontos por fazenda" fica no `enviar`, logo depois do `linha_sem_analise`: agrupar `analises` por (operacao, cod_faz) e exigir `count(distinct ponto) = 2`. O script de volta apaga as linhas e análises com `ponto='implemento'`, volta `metodo` para `'trator'` e restaura as funções e índices de 04/11. Copiar as definições de lá.
- [ ] **Passo 4:** `python -m pytest tests/paralelismo/test_banco_sql.py -q` → PASSA, incluindo o `test_script_de_volta_desfaz_com_dados`, estendido para a migration nova.
- [ ] **Passo 5:** rodar a skill `backend-design:review-migration` sobre o arquivo e corrigir o que ela apontar.
- [ ] **Passo 6:** commit: `git add supabase/migrations/20261112090000_paralelismo_dois_pontos.sql supabase/migrations/volta/20261112090000_paralelismo_dois_pontos_volta.sql tests/paralelismo/test_banco_sql.py` e depois `git commit -m "Paralelismo: banco nos dois pontos (ponto, metodo pipeline, vigente por ponto)"`.

### Tarefa 2: leitores e Grupo nos dois pontos (camada 2, Haiku; a regressão real é da camada 3)

**Arquivos:**
- Modificar: `paralelismo/jdl.py`, `paralelismo/gs3.py`, `paralelismo/navegador.py`
- Testar: `tests/paralelismo/test_leitores_sinteticos.py`, `tests/paralelismo/test_navegador.py`, `tests/paralelismo/test_regressao.py`

**Interfaces:**
- Consome: `pontos_plantio`, `ler_trilha_trator` e `ler_documentacao` (jdl); `ler_sessao` e `pontos_plantio(sessao, antena)` (gs3).
- Produz:
  - `PONTOS = ('implemento', 'trator')` em `paralelismo/analise.py`.
  - `ler_jdl_pontos(caminho) -> tuple[dict[str, list[tuple[float, float]]], int]`: as chaves são `PONTOS`, e o int é o total de ticks da trilha. O arquivo é lido UMA vez: `ler_documentacao` e `ler_trilha_trator` uma vez cada, e os dois filtrados pelos mesmos eventos.
  - `ler_gs3_pontos(fdl) -> tuple[dict[str, list[tuple[float, float]]], int]`: `ler_sessao` uma vez, com `5141` → implemento e `5140` → trator.
  - `ler_jdl` e `ler_gs3` ficam como estão (o trator), usados pela regressão antiga.
  - `Grupo.ler(tipo, caminho, data)` devolve `{'pontos': {'implemento': n, 'trator': n}, 'registros', 'legivel', 'completo'}`.
  - `Grupo.fechar()` devolve `{'frota', 'data', 'pontos': {'implemento': [linhas], 'trator': [linhas]}, 'duracao_total_s', 'duracao_trabalho_s', 'sem_trabalho'}`. Cada linha é `{'frota','data','coords'}`, como hoje.
  - A duração de trabalho e a data mais frequente usam a contagem do TRATOR: a trilha é contínua; o implemento do `.jdl` são eventos.

- [ ] **Passo 1: testes que falham:**
  - `test_jdl_pontos_le_uma_vez_e_da_os_dois` (sintético, com o gerador já usado em `test_leitores_sinteticos.py`): `pts, n = ler_jdl_pontos(arq)`; `pts['trator'] == ler_jdl(arq)[0]`; `pts['implemento'] == pontos_plantio(arq)`; `n == ler_jdl(arq)[1]`.
  - `test_gs3_pontos_usa_5141_e_5140`: `pts['implemento'] == pontos_plantio(ler_sessao(fdl), '5141')`; `pts['trator'] == ler_gs3(fdl)[0]`.
  - `test_fechar_da_linhas_dos_dois_pontos` (em `test_navegador.py`, com monkeypatch de `ler_jdl_pontos`): `set(r['pontos']) == {'implemento','trator'}` e as linhas do trator iguais às do teste `test_fechar_da_as_mesmas_linhas_da_regressao`.
  - `test_ponto_vazio_nao_torna_o_arquivo_ilegivel`: implemento `[]` e trator com pontos → `legivel is True`, `r['pontos']['implemento'] == []`.
  - Ajustar os testes de `test_navegador.py` que fazem monkeypatch de `ler_jdl` para `ler_jdl_pontos`.
  - Em `test_regressao.py`, `test_regressao_10233_jdl_implemento` (`pll_total == 2468`, `59.56`) e `test_regressao_10966_gs3_implemento` (`pll_total == 30724`, `72.92`), pelo caminho `Grupo` → `fechar` → `analisar_fazenda`, nos dois pontos. Os números do trator (2506/77,85 e 30395/88,86) continuam valendo pelo mesmo caminho.
- [ ] **Passo 2:** `python -m pytest tests/paralelismo -q` → FALHA (`ler_jdl_pontos` não existe).
- [ ] **Passo 3:** implementar. O `Grupo` guarda `self.pontos = {p: [] for p in PONTOS}`, e `fechar` chama `linhas_do_grupo` uma vez por ponto, descartando cada lista logo depois (memória, spec §8).
- [ ] **Passo 4:** `python -m pytest tests/paralelismo -q` → PASSA. Na máquina do usuário: `PARALELISMO_10233=... PARALELISMO_10966=... python -m pytest -m dados_reais -q` → 4 testes passam.
- [ ] **Passo 5:** publicar o núcleo para o navegador do mesmo jeito da P0.5 (o manifesto do Pyodide) e commitar `paralelismo/ tests/paralelismo/` com a mensagem "Paralelismo: leitores e Grupo nos dois pontos".

### Tarefa 3: Worker, prévia e envio por ponto (camada 1, `-a frontend`; revisão da camada 3)

**Arquivos:**
- Modificar: `app/paralelismo-worker.js`, `app/paralelismo.js`, `app/paralelismo-puro.js`
- Testar: `tests/app/paralelismo_puro.test.js`, `tests/app/teste_paralelismo_tela.py`

**Interfaces:**
- Consome: `Grupo.fechar()` da Tarefa 2; o RPC `paralelismo_linhas_vigentes(op, faz, ponto, rodada)` e o formato do `enviar` da Tarefa 1.
- Produz:
  - `parMesclarComVigente(linhasVigentes, linhasNovas)`: inalterada, chamada uma vez por ponto.
  - `parPayloadAnalises(resultadosPorPonto, operacao, cod_faz, basePorPonto) -> analises[]`: duas entradas, cada uma com `ponto` e `metodo: 'pipeline'`.
  - O Worker roda `analisar(linhas_json, talhoes_json, prefixo)` uma vez por ponto, com o prefixo `<op>_<faz>_<ponto>`. O zip de amostras sai por ponto, e o `amostras_url` vai por análise.
  - O recálculo (`recalculo_necessario:<op>/<faz>/<ponto>`) refaz só o ponto apontado.
- [ ] **Passo 1: testes que falham:**
  - `parPayloadAnalises` devolve 2 itens ordenados `['implemento','trator']`, cada um com `metodo === 'pipeline'` e o `base_analise_id` do seu ponto.
  - Prévia na tela (modo demonstração): a tabela da prévia tem as colunas "Implemento" e "Trator" e a linha da fazenda mostra as duas aderências. O teste confere o texto de `#previa`.
  - O envio em demonstração registra um payload com `analises.length === 2 * fazendas` e todas as linhas com `ponto`.
- [ ] **Passo 2:** `node --test tests/app/paralelismo_puro.test.js` e `python -m pytest tests/app/teste_paralelismo_tela.py -q` → FALHAM.
- [ ] **Passo 3:** implementar. A prévia mostra os dois pontos lado a lado (spec §4). O mapa da prévia pinta pelo implemento, com um botão "Trator" para trocar.
- [ ] **Passo 4:** os mesmos dois comandos → PASSAM. No Edge com Playwright, as amostras de `tests/dados/paralelismo` batem com o Python nos dois pontos (o mesmo teste da S2, agora por ponto), e o pico de memória fica registrado no relatório.
- [ ] **Passo 5:** commit "Paralelismo: análise, prévia e envio nos dois pontos".

### Tarefa 4: seletor "Os dois | Implemento | Trator" no Painel (camada 1, `-a frontend`)

**Arquivos:**
- Modificar: `app/paralelismo-puro.js` (`parResumo`, `parPorFaixa`, `parPorMes`, `parTabelaFazendas`, `parTalhoesPlanos`), `app/paralelismo.js`, `app/paralelismo.html`, `app/paralelismo.css`
- Testar: `tests/app/paralelismo_puro.test.js`, `tests/app/teste_paralelismo_tela.py`

**Interfaces:**
- Consome: análises vigentes com `ponto` e `metodo`.
- Produz:
  - `parPorPonto(analises) -> Map<'op|faz', {implemento: analise|null, trator: analise|null}>`.
  - As agregações ganham o último parâmetro `ponto` (`'ambos' | 'implemento' | 'trator'`, padrão `'ambos'`). Em `'ambos'` cada linha traz `pct_implemento`, `pct_trator` e `dif_pp` (nulo se faltar um dos dois). As médias de cada ponto usam só as fazendas que têm aquele ponto.
  - `parDiferencaPp(pctImpl, pctTrator) -> string|null`, com o formato "+14,3 p.p.".
  - Selo `AgroCAD` na linha cuja análise do implemento tem `metodo === 'agrocad_fme'`, e "sem dado" no trator.
- [ ] **Passo 1: testes que falham:**
  - `parResumo(analises, base, 'ambos')`, com uma fazenda que tem os dois pontos (impl 70/100, trator 90/100) e outra só AgroCAD (impl 80/100) → `pct_implemento === 75`, `pct_trator === 90` (só uma fazenda) e `fazendas === 2`.
  - `parTabelaFazendas(..., 'ambos')`: a linha da AgroCAD tem `pct_trator === null`, `dif_pp === null` e `selo === 'AgroCAD'`; a outra, `dif_pp === -20`.
  - `parDiferencaPp(72.92, 88.86) === '−15,9 p.p.'` e `parDiferencaPp(80, null) === null`.
  - Tela: o seletor existe, começa em "Os dois" e, ao clicar "Trator", a tabela de fazendas fica com uma coluna de aderência só. A escolha não vai para a URL nem para o `localStorage`.
- [ ] **Passo 2:** os comandos da Tarefa 3 → FALHAM.
- [ ] **Passo 3:** implementar. Em "Os dois", os gráficos de faixa e de mês mostram duas séries (use a skill `dataviz` para as duas cores; o implemento é a série principal). O mapa de Talhões pinta pelo implemento, com a opção "pintar pela diferença" (escala divergente centrada em 0 p.p.).
- [ ] **Passo 4:** os comandos → PASSAM.
- [ ] **Passo 5:** commit "Paralelismo: seletor dos dois pontos no Painel".

### Tarefa 5: Fazenda, Frentes e Relatório com os dois pontos

É a sessão S6, com o pedido ajustado: as mesmas regras da Tarefa 4 valem para as abas Fazenda, Frentes e frotas e Relatório. No Relatório impresso sai o ponto escolhido no seletor. Em "Os dois", cada tabela tem duas colunas de aderência e a diferença em p.p. O critério da S6 continua sendo `@media print`, e a ele se soma `node --test tests/app/paralelismo_puro.test.js`.

### Tarefa 6: histórico reprocessado dos BRUTOS (S7, camada 3, opus; dado real)

**Arquivos:**
- Criar: `migracao/paralelismo_historico.py`
- Testar: `tests/migracao/test_paralelismo_historico.py` (banco local, dados sintéticos)

**Interfaces:**
- Consome: `ler_jdl_pontos`, `ler_gs3_pontos`, `Grupo` e `analisar_fazenda` (Tarefa 2), o schema da Tarefa 1, `frotas_maquinas.csv` e `Paralelismo8.xlsx` (só nas 16 fazendas AgroCAD).
- Produz: CLI `python migracao/paralelismo_historico.py --brutos <pasta BRUTOS local> --frotas <csv> --agrocad <Paralelismo8.xlsx> --talhoes <shp> (--simular | --gravar) --conferencia <saida.csv>`.

Regras (spec §9):
- Frota pela série do `.jdl` (`frotas_maquinas.csv`). No GS3, pelo nome da pasta `<frota>`. Arquivo sem frota vai para o relatório e não entra.
- Deduplicação por nome do `.fdl`/`.jdl`. O SHA-256 de cada bruto vai para `paralelismo_arquivos`.
- Uma rodada "Histórico reprocessado (BRUTOS até <data>)", publicada direto, com os dois pontos de cada fazenda e `metodo='pipeline'`.
- AgroCAD só nas 16 fazendas sem brutos: 10008, 10086, 10146, 10214, 10296, 10404, 10434, 10463, 10464, 10727, 10729, 10732, 10733, 10734, 10760 e 10777. Elas entram com `ponto='implemento'`, `metodo='agrocad_fme'`, sem linhas, e com o mês de `meses_fazendas.csv`.
- Conferência das 20 fazendas AgroCAD com brutos (10003, 10016, 10027, 10045, 10235, 10350, 10454, 10575, 10609, 10658, 10674, 10677, 10793, 10797, 10806, 10810, 10811, 10871, 10946 e 10949): um CSV `cod_faz, pct_agrocad, pct_pipeline_implemento, dif_pp, destaque`, com `destaque = abs(dif_pp) > 3`. O AgroCAD dessas 20 NÃO é gravado.
- `--simular` só conta (arquivos, fazendas, amostras por ponto) e escreve a conferência. `--gravar` exige que a conferência já exista e tenha sido aprovada (flag `--conferencia-aprovada`).

- [ ] **Passo 1: testes que falham** (banco local, BRUTOS sintéticos em `tmp_path`, com o gerador dos testes de leitor):
  - `test_simular_nao_grava`: depois de `--simular`, `count(*)` de `paralelismo_analises` não muda.
  - `test_gravar_cria_os_dois_pontos_por_fazenda`: 2 fazendas sintéticas → 4 análises vigentes, 2 por ponto.
  - `test_agrocad_so_nas_sem_brutos`: uma fazenda sintética da lista das 16 sem brutos entra com `metodo='agrocad_fme'`; uma da lista das 20 com brutos não ganha análise `agrocad_fme`.
  - `test_conferencia_destaca_acima_de_3pp`: AgroCAD 86,05 contra pipeline 82,00 → `destaque` verdadeiro; contra 84,00 → falso.
  - `test_gravar_sem_conferencia_aprovada_recusa`: sai com código 2 e não grava nada.
- [ ] **Passo 2:** `python -m pytest tests/migracao -q` → FALHA.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** `python -m pytest tests/migracao -q` → PASSA.
- [ ] **Passo 5:** com o usuário, copiar os BRUTOS da rede para o disco local (~4,7 GB, ~35 min), rodar `--simular` em segundo plano (~2 h 40) e entregar o CSV da conferência. NÃO gravar no banco real. A gravação é feita depois, com o usuário.
- [ ] **Passo 6:** commit "Paralelismo: histórico reprocessado dos BRUTOS nos dois pontos".

### Tarefa 7: regressão nos dois pontos e E2E (S8)

O E2E da spec §11 confere que uma rodada enviada tem 2 análises por fazenda e que o Painel em "Os dois" mostra as duas aderências. As referências são: 10233, trator 2.506/77,85% e implemento 2.468/59,56%; 10966, trator 30.395/88,86% e implemento 30.724/72,92%; 10075Rev1, implemento 13.127/87,22%. A 10075Rev1 entra como terceira variável, `PARALELISMO_10075`, na `test_regressao.py`, só no implemento e pelo `Grupo`.

---

## Mudanças no orquestrador (`orquestra/sessoes.json`)

- Nova sessão **S4b** "Dois pontos: banco, leitores, Worker e envio" (opus), antes da S5. Ela cobre as Tarefas 1, 2 e 3. Critérios: `python -m pytest tests/paralelismo -q`, `node --test tests/app/paralelismo_puro.test.js` e `python orquestra/verifica.py --existe supabase/migrations/20261112090000_paralelismo_dois_pontos.sql`.
- **S5:** o pedido passa a incluir a Tarefa 4 e a avisar que o Painel já está commitado (68d291e e dcbc866): conferir, aplicar o seletor e escrever o relatório.
- **S6:** o pedido inclui a Tarefa 5.
- **S7:** o pedido passa a ser a Tarefa 6, no lugar da importação da Paralelismo8.
- **S8:** acrescenta a Tarefa 7.
- **Portão `historico`:** passa a incluir "aplicar a migration dos dois pontos (20261112090000)".
- `orquestra/estado.json` (fora do git) foi recriado com S1 a S4 feitas: o worktree anterior foi removido junto com o estado.
