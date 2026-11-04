# Paralelismo P2 (sessão S1): Worker e funções puras — plano de implementação

> **Para quem executa:** Worker = camada 3 (segurança). Funções puras = camada 1 (`delegar.sh -a build`, só dados sintéticos), com os testes escritos antes pelo Claude. Sessão autônoma: o usuário delegou a revisão deste detalhamento; os padrões escolhidos estão em "Decisões" e no relatório `orquestra/relatorios/S1.md`.

**Objetivo:** rotas `POST /paralelismo/parte` e `POST /paralelismo/excluida` no Worker, e todas as funções puras de `app/paralelismo-puro.js`, prontas para a P3–P5.

**Arquitetura:** o banco decide o acesso (RPCs com o token do usuário); o Worker só fala com o GitHub. As funções puras não têm DOM nem rede, são funções globais com prefixo `par`, carregadas nos testes por `vm`, como as do Drone.

**Tecnologias:** Cloudflare Worker, JS ES2020 sem build, `node --test`.

**Spec:** [2026-10-26-paralelismo-design.md](../specs/2026-10-26-paralelismo-design.md) · **Plano geral:** [2026-10-29-paralelismo.md](2026-10-29-paralelismo.md), seção P2 · **Ajustes da P1:** [2026-10-29-paralelismo-P1.md](2026-10-29-paralelismo-P1.md), ajuste 7.

## Restrições globais

- Partes de até **90 MB**; o Worker recusa corpo acima de **95 MB**. Release `paralelismo-r<id>` em `env.GH_REPO`.
- Dado real nunca vai para o executor externo nem para o git: testes usam série `BM0000X000000`, frotas 9xxxx e fazendas fictícias.
- Sem push, sem publicar o Worker, sem migration nova, sem gravar no banco real.
- Textos em português do Brasil, vírgula decimal, funções com prefixo `par`.

## Decisões (padrões escolhidos, para o usuário conferir no relatório)

1. **Resposta de `/paralelismo/parte`:** `{rodada_id, url, bytes}`. O `rodada_id` a mais é o que a tela precisa quando a primeira parte vai sem id (a RPC reserva).
2. **`rodada_ja_enviada` = sucesso sem tocar no GitHub:** 200 com `{rodada_id, ja_enviada: true, url: null, bytes: 0}`. Pelo ajuste 7 da P1, reenvio não sobrescreve a release.
3. **`nome` do asset restrito** a `^[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(zip|csv)$`. O GitHub troca caracteres como espaço, e aí a busca por nome não acharia o asset no reenvio; a tela gera nomes como `parte-001.zip`, `manifesto.csv`, `shapes-10010.zip`.
4. **Busca do asset existente** pela listagem paginada da release, para não falhar com muitas partes.
5. **`/paralelismo/excluida`** recebe JSON `{release_tag}`, o que `paralelismo_excluir` devolve. Exige `paralelismo_nivel() = 'admin'`, recusa (409) se a rodada ainda existe, não cria release (404 se não houver) e não repete a marca. A data sai no fuso de São Paulo.
6. **Pasta GS3** = caminho até o segmento que começa com `GS3`; sem ele, o que vem antes de `RCD`; sem os dois, a pasta do arquivo. Vem da estrutura real `GS3_2630/<org>/RCD/EIC/Documentation/<hex>/<uuid>.fdl` (`base-op/scripts/copiar_jdl_pendrive.py`).
7. **Fazenda do `.jdl`:** `(\d{5})Rev(\d+)` da pasta mais funda para a mais rasa; o "número isolado" só vale na pasta imediata do arquivo, porque a pasta raiz pode ser o número da frota.
8. **Data do `.fdl`:** os 10 primeiros caracteres do `timeStamp` (UTC), como na regressão validada (`inicio[:10]`).
9. **`arquivos` da conferência:** só `.jdl`, `.fdl` e `.fdd` novos, os tipos aceitos em `paralelismo_arquivos.tipo`. `.pth`/`.pvf` servem só para o diagnóstico de documentação. A documentação é avaliada com todos os arquivos, inclusive os já analisados.
10. **`parPartes`:** mantém a ordem (`.fdl` e `.fdd` vizinhos ficam juntos) e marca o item grande com `aviso: 'maior_que_limite'`, mantendo o retorno `[[...]]`.
11. **`parMesclarComVigente`:** chave `frota|data|coords em mm`, porque o `ST_AsGeoJSON` devolve no máximo 9 decimais e a linha em memória tem mais.

## Foco da revisão

1. Reenvio de parte após `paralelismo_enviar` já ter gravado: não pode alterar a release. → T1.
2. Mesmo pen-drive de novo, com `.pth` novo e sessões já analisadas: não pode virar "sem documentação". → T3.
3. Número da frota ou "2630" do `GS3_2630` lidos como fazenda ou frota. → T3.
4. Linha vigente com menos decimais que a mesma linha em memória: não pode duplicar. → T3.
5. Usuário sem acesso ou id de outro usuário: nada chega ao GitHub. → T1 e T2.

---

### Tarefa 1: `POST /paralelismo/parte` (camada 3)

**Arquivos:** modificar `worker/arquivos.js`; criar `tests/worker/paralelismo.test.js`.

**Interfaces:** form `rodada_id` (vazio na primeira parte), `nome`, `arquivo` → `{rodada_id, url, bytes}` ou `{rodada_id, ja_enviada: true, url: null, bytes: 0}`.

- [x] Escrever os testes pela rota `padrao.fetch`, com `fetch` falso no contexto `vm`: sem token 401; `Content-Length` > 95 MB 413 sem ler o form; `arquivo` > 95 MB 413; nome inválido 400 sem chamar o banco; sem permissão (RPC 400) nada no GitHub; primeira parte passa `p_rodada_id: null` e sobe em `paralelismo-r<id>`; asset de mesmo nome é substituído; `rodada_ja_enviada` = 200 sem GitHub; asset além da primeira página é achado.
- [x] Rodar `node --test tests/worker/paralelismo.test.js` e ver falhar.
- [x] Implementar `paralelismoParte` e `assetDaRelease`; trocar o despacho do `fetch` por um mapa de rotas POST.
- [x] Rodar `node --test tests/worker/` e ver passar.
- [x] Commit.

### Tarefa 2: `POST /paralelismo/excluida` (camada 3)

**Arquivos:** modificar `worker/arquivos.js`, `tests/worker/paralelismo.test.js`.

**Interfaces:** JSON `{release_tag: 'paralelismo-r<id>'}` → `{release_tag, marcada: true|false}`.

- [x] Testes: sem token 401; tag fora do padrão 400; não admin 403 sem GitHub; rodada que ainda existe 409; release inexistente 404, sem criar; acrescenta `EXCLUÍDA em dd/mm/aaaa` preservando a descrição; segunda marcação não repete.
- [x] Ver falhar, implementar `paralelismoExcluida`, ver passar.
- [x] Commit.

### Tarefa 3: funções puras (camada 1)

**Arquivos:** criar `app/paralelismo-puro.js`, `tests/app/paralelismo_puro.test.js`.

**Interfaces:** as da seção P2 do plano geral. A conferência recebe arquivos `{caminho, bytes, sha256, ...identificação}` e devolve também `tipo` (`'jdl'|'gs3'`), `frotaSugerida` e `nJaAnalisados`. `revisao` é número; `cod_faz` é número.

- [x] Escrever `tests/app/paralelismo_puro.test.js` com todos os comportamentos, inclusive o foco 2, 3 e 4.
- [x] Rodar `node --test tests/app/paralelismo_puro.test.js` e ver falhar. Commit dos testes (a worktree do executor só leva o que está versionado).
- [x] Rodar `delegar.sh -a build` com o brief; revisar o diff e rodar os testes.
- [x] Integrar. **Mudou na execução:** a revisão reprovou a entrega (6 defeitos, cada um com teste novo) e o merge do branch foi negado pelo controle de permissões. O arquivo foi reescrito pelo Claude (camada 3), sem integrar o commit do executor.

### Tarefa 4: fechamento

- [ ] `requesting-code-review` sobre `git diff d0c0546..HEAD`; corrigir o que for crítico ou importante.
- [ ] `verification-before-completion`: `node --test` em todos os testes JS e `pytest tests/paralelismo -m "not banco and not dados_reais"`.
- [ ] Escrever `orquestra/relatorios/S1.md` e commitar.

## Registro de delegação

Preenchido ao final, no relatório.
