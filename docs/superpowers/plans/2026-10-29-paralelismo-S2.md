# S2 — P3a: Pyodide, OPFS e fila de processamento

> **Execução:** sessão autônoma, camada 3 (o plano geral põe Web Worker e OPFS na camada 3, e a prova usa as amostras reais). Passos com caixas; TDD; um commit por tarefa. A tela fica para a S3.

**Objetivo:** a metade de lógica da P3: do `File` do pen-drive até o resultado por fazenda, sem tela e sem banco.

**Arquitetura:**
- Página: `app/paralelismo-fila.js` lê cada arquivo do pen-drive, calcula SHA-256, identifica e copia para o OPFS. Depois mantém a fila de um item por vez. Sem DOM.
- Web Worker: `app/paralelismo-worker.js` carrega o Pyodide e, por fazenda e frota, lê um arquivo por vez do OPFS.
- Python: `paralelismo/navegador.py` junta os pontos, gera as linhas, descarta os pontos e roda a análise. Testável com pytest, sem navegador.

**Tecnologias:** Pyodide 0.27.7, pyshp 2.3.1 (a versão validada no Python nativo), OPFS, Web Locks, `crypto.subtle`, `node --test`, pytest, Playwright + Edge.

**Spec:** `docs/superpowers/specs/2026-10-26-paralelismo-design.md` (§3, §4, §8, §10).

## Restrições globais

As do plano geral, em especial: parâmetros fixos; dado real nunca no git nem em executor externo; nada de banco real; Pyodide 0.27.7. Mais os limites da sessão: sem push, merge, deploy ou release.

## Decisões de padrão (o usuário delegou; registradas no relatório)

1. **Só `.jdl`, `.fdl` e `.fdd` passam por SHA-256 e cópia.** `.pth` e `.pvf` entram só pelo nome, porque servem para o aviso "sem documentação". O resto é ignorado. A spec diz "cada arquivo", mas o banco só aceita esses três tipos e um pen-drive pode ter GB de outras coisas.
2. **Nomes no OPFS** são `f000001.jdl` etc.: o caminho original pode ter caracteres inválidos, e ele fica na lista devolvida à página.
3. **Sobra = pasta no OPFS sem Web Lock ativo.** Cada item segura um lock `par-opfs-<id>` enquanto a aba vive; assim a segunda aba não oferece descartar a cópia em uso, e fechar a página libera o lock sozinho.
4. **Sobras só se descartam, não se retomam** (o plano geral diz "oferecer descartar"), então não há arquivo de metadados.
5. **Duração do GS3 no aviso de frota sem trabalho: 1 s por registro** (o `.jdl` é 0,2 s). Nada no código diz a frequência do GS3; fica como constante, e a conferência vai para as pendências.
6. **Mensagens do Worker** seguem o plano geral (`progresso`, `pronto`, `erro`), com `id` do item, `fase` e `pct_item` a mais, para a faixa de fases da S3.
7. **O recálculo da P4** é um item sem grupos: `fazendas[i].vigentes` já mesclado e `grupos: []`. Não precisa de mensagem nova.
8. **Depois de `erro` a fila encerra o Worker** e cria outro no item seguinte, porque o Pyodide pode ter ficado inconsistente.
9. **Data das linhas:** a data com mais pontos no grupo, como no `_linhas` da regressão. Se nenhum arquivo tem data, `null`.
10. **Manifesto:** ganha `modulos: {corretivos: [...], paralelismo: [...]}`; `arquivos` (a união) continua por um tempo, para a página do Corretivos ainda em cache.

## Foco da revisão

1. Arquivo truncado ou ilegível: pulado e listado; o resto da rodada processa.
2. Pen-drive retirado durante a cópia: o arquivo vai para `falhas`; depois da cópia, o processamento não depende mais dele.
3. Espaço do OPFS esgotado: mensagem clara e nada de cópia pela metade.
4. Página fechada no meio: a reabertura vê a sobra; outra aba viva não vê a cópia em uso como sobra.
5. `.fdl` novo com `.fdd` já analisado, e o inverso (GS3 que acumula sessões): o par é encontrado na lista completa; `.fdd` sem `.fdl` novo é listado.

---

### Tarefa 1: manifesto por módulo e `pyshp` fixado

**Arquivos:** `mapas/publicar.py`, `app/corretivos-pdf.js`, `tests/mapas/test_publicar.py`.

**Produz:** `py/manifest.json` com `{arquivos, modulos: {corretivos, paralelismo}}`; `MODULOS` em `mapas/publicar.py`.

- [ ] Teste: `modulos.paralelismo` tem só `paralelismo/*`, `modulos.corretivos` não tem nada de `paralelismo/`, a união é `arquivos`, e `corretivos-pdf.js` lê `modulos.corretivos`. Ver falhar.
- [ ] Implementar. Ver passar. Commit.

### Tarefa 2: `paralelismo/navegador.py`

**Arquivos:** `paralelismo/navegador.py`, `tests/paralelismo/test_navegador.py`, `mapas/publicar.py`.

**Produz:**
- `Grupo(frota).ler(tipo: 'jdl'|'gs3', caminho, data) -> {'pontos', 'registros', 'legivel'}`: lê e **apaga** o arquivo (e o `.fdd` ao lado), mesmo em erro.
- `Grupo.fechar() -> {'frota', 'data', 'linhas', 'duracao_total_s', 'duracao_trabalho_s', 'sem_trabalho'}`: descarta os pontos; segunda chamada dá erro.
- `analisar(linhas_json, talhoes_json, prefixo) -> (resultado_json, zip_bytes)`.

**Testes:** pontos acumulados na ordem de leitura e iguais a `linhas_do_grupo` direto; arquivo apagado depois de ler, também quando o leitor levanta exceção; ilegível dá `legivel: False` e não quebra; data é a mais frequente por ponto; sem data dá `None`; fechar duas vezes dá erro; sem trabalho com JDL de mais de 1 h; `analisar` sem linhas devolve totais zerados e zip válido; zip tem `_Amostras` e `_Linhas`.

- [ ] Testes, ver falhar, implementar, ver passar. Publicar o módulo em `MODULOS['paralelismo']`. Commit.

### Tarefa 3: plano do item, OPFS e fila

**Arquivos:** `app/paralelismo-puro.js`, `tests/app/paralelismo_puro.test.js`, `app/paralelismo-fila.js`, `tests/app/paralelismo_fila.test.js`.

**Consome:** `parConferencia`, `parExtensao`, `parSemExtensao`, `parIdentificarJdl`, `parIdentificarFdl`.

**Produz:**
- `parPlanoDoItem(grupos, todos) -> {fazendas: [{operacao, cod_faz, grupos: [{frota, arquivos: [{tipo, caminho, opfs, opfs_fdd, data, bytes}]}]}], pulados: [{caminho, motivo}]}`. Motivos: `sem_frota`, `sem_fazenda`, `sem_fdd`, `fdd_sem_fdl`. Arquivos em ordem de caminho.
- `parOpfsCopiar(id, files, {aoProgresso}) -> {arquivos, mapas, falhas}`.
- `parOpfsLer(id, nome) -> Uint8Array`, `parOpfsSobras() -> [{id, arquivos, bytes, modificado_em}]`, `parOpfsDescartar(id)`.
- `parCriarFila({criarWorker, buscarBase, aoMudar}) -> {adicionar, remover, tentarDeNovo, itens}`. Estados: `na_fila`, `processando`, `pronto`, `erro`. `buscarBase(operacao, cod_faz) -> {analise_id, linhas, talhoes}`.

**Testes (OPFS falso em memória; o real é provado na Tarefa 4):** cópia com SHA-256 conhecido; identificação ligada aos arquivos; `.pth` sem cópia; outros ignorados; falha de leitura vai para `falhas`; cota esgotada apaga a pasta e levanta `PAR_ERRO_ESPACO`; sobras sem as travadas; descartar solta a trava. Fila: um por vez em ordem; base buscada antes de postar; erro não para os seguintes e troca o Worker; `onerror` do Worker vira erro com o texto da spec §10; `tentarDeNovo` reaproveita; remover cancela o que está rodando; progresso de item antigo é ignorado.

- [ ] Testes, ver falhar, implementar, ver passar. Commit.

### Tarefa 4: Web Worker e prova no Edge

**Arquivos:** `app/paralelismo-worker.js`, `tests/app/teste_paralelismo_worker.py`, `tests/paralelismo/test_navegador.py` (versão fixada).

**Mensagens:** entra `{tipo: 'processar', item}`; saem `{tipo: 'progresso', id, fazenda, pct, pct_item, fase}`, `{tipo: 'pronto', id, resultado}` e `{tipo: 'erro', id, msg}`.

**Resultado:** `{id, pulados, fazendas: [{operacao, cod_faz, base_analise_id, linhas_novas, sem_trabalho: [...], analise, shapefile: Uint8Array}]}`.

**Prova no Edge (servidor só em 127.0.0.1; `app/` + `py/` publicado numa pasta temporária + amostras):**
1. Amostras reais pelo caminho inteiro (OPFS → fila → Worker): `.jdl` e `.fdl`+`.fdd` em duas fazendas. Contagens iguais às do Python nativo, inclusive por talhão, e coordenadas a menos de 1 µm.
2. Vigentes iguais às novas: a mescla não duplica.
3. Pasta sintética por `<input webkitdirectory>`, com arquivo corrompido: pulado e listado; o resto processa.
4. Sobras: outra aba não vê a cópia em uso; fechada a primeira, vê; descartar limpa.
5. Só `py/paralelismo/*` baixado pelo Worker; só `mapas/...` pelo Corretivos.
6. Pyodide inacessível: texto da spec §10.

- [ ] Teste de versão, ver falhar, escrever o Worker, rodar a prova no Edge, corrigir. Commit.

### Tarefa 5: fechamento

- [ ] `requesting-code-review`, corrigir críticos e importantes, `verification-before-completion`, `orquestra/relatorios/S2.md`, commit.
