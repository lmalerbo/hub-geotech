# Paralelismo P4 (S4) — Pendentes, Rodadas e Frotas — plano

> Sessão autônoma: o usuário delegou o detalhamento (a nota do plano-mãe sobre mostrá-lo antes não vale). Execução inline, TDD, commit por tarefa.

**Objetivo:** abas Pendentes, Rodadas (com sub-aba Frotas) funcionando por nível, com recálculo no Worker quando `paralelismo_publicar` responder `recalculo_necessario`.

**Arquitetura:** lógica sem DOM em `app/paralelismo-gestao.js` (node --test). Telas e API real em `app/paralelismo-abas.js`. Dados de demonstração em `app/paralelismo-demo.js`. A prévia lida do banco reaproveita o formato de `parPrevia` (mesmo desenho da prévia do Processar). O recálculo usa um Worker próprio e descartável (mesmo `paralelismo-worker.js`, fazenda sem `grupos`), para não se misturar com a fila de pen-drives.

**Spec / plano-mãe:** `docs/superpowers/specs/2026-10-26-paralelismo-design.md`; `2026-10-29-paralelismo.md` (seção P4, restrições globais, foco da revisão 4).

## Restrições herdadas
- Texto em pt-BR, vírgula decimal; HTML/CSS/JS puro; funções `par*`; 390 px sem rolagem horizontal; só tema claro.
- `partes[].url` e `amostras_url` são **dado não confiável** (vêm do banco, gravados por solicitantes): só viram `href` se passarem em `parUrlSegura` (https, host `github.com`, sem usuário/senha, sem espaço); senão aparecem como texto "link inválido", sem link. Sempre escapar com `parEsc`; `rel="noopener noreferrer"`, `target="_blank"`.
- O banco é a barreira (RLS/RPC); a tela só esconde o que o nível não pode.
- Nada de banco real, push, Worker publicado ou release.

## Decisões minhas (o usuário delegou)
1. Pendentes fica escondida para o nível **leitura** (o banco não mostra nada a ele).
2. Rodadas = lista das rodadas visíveis (mais novas primeiro, até 100) + sub-aba **Frotas**.
3. Frotas: editar linha e adicionar (editor/admin); **sem apagar** (nenhuma exigência; apagar frota quebra a identificação de arquivos já analisados).
4. No recálculo, `amostras_url` volta **nulo**: o shapefile antigo ficaria desatualizado e o Worker não aceita novas partes de rodada já enviada (`rodada_ja_enviada`). Fica como pendência.
5. Excluir: confirmação; depois do RPC, `POST /paralelismo/excluida`; se essa chamada falhar, a rodada já foi excluída e a tela avisa que a release não foi marcada.
6. Recusar pede o motivo num campo de texto dentro de um diálogo; vazio não envia.

## Foco da revisão (P4)
1. Solicitante/leitura vê botão de publicar/recusar/excluir/editar frota → teste de tela por nível.
2. Link malicioso (`javascript:`, `http:`, host de terceiro, aspas, `<script>`) em `partes[].url`/`amostras_url` → teste puro + teste de tela.
3. Publicar com fazenda que mudou → recálculo com as linhas vigentes + as da rodada; confirmar com `p_recalculo`; cancelar não grava.
4. Corrida: depois do recálculo outra publicação muda a vigente → novo `recalculo_necessario`; repetir até 2 vezes, depois erro claro.
5. Falha do Worker de recálculo ou do banco no meio → nada publicado, botão volta.

## Tarefa 1 — `app/paralelismo-gestao.js` + `tests/app/paralelismo_gestao.test.js`
Funções puras (sem DOM):
- `parUrlSegura(url) → string|null`
- `parRecalculoNecessario(erro) → [{operacao, cod_faz}]|null` (lê `recalculo_necessario:cana/10001,torta/10002` de `erro.message`)
- `parRodadaDoBanco(linha, nomes) → {id, descricao, status, tag, criadoPor, validadoPor, criadoEm, validadoEm, motivo, partes:[{nome, bytes, url|null, urlInvalida}], fazendas:[{operacao, cod_faz, amostras_url|null}], tratores:int, previa}`; `nomes` = mapa id→nome (falta → '—')
- `parPreviaDoBanco(analises, vigentes) → mesmo formato de parPrevia` (usa `parFormatarPct`; aviso de fora de talhão > 5% e `insuficiente` (< 25 amostras))
- `parMontarRecalculo(fazendas, baseIds) → [{operacao, cod_faz, base_analise_id, mes, amostras, aderentes, acima, abaixo, fora_talhao, pll_total, pll_aderentes, amostras_url:null, talhoes}]`
- `parPublicarComRecalculo(rodadaId, deps) → {publicada:true, recalculou:boolean}|{cancelado:true}`; `deps = {publicar(id, recalculo|null), buscarBase(op, cod, rodadaId), recalcular(entrada) → fazendas, confirmar(previa) → Promise<boolean>}`; no máximo 2 recálculos.
- `parTextoErroGestao(e) → string` (sessão, permissão, `rodada_nao_pendente`, `exclua_antes_rodada_mais_nova:<fazendas>`, `rodada_pendente_depende:<rodadas>`, `recalculo_sem_analise`, rede, genérico).
- `parValidarFrota(f) → {erro:string|null, valor}`.

Testes (antes do código): url (https github ok; `javascript:`, `http://`, `https://evil.com/x`, `https://u:p@github.com/x`, vazio, nulo → null); lista de recálculo; prévia do banco com delta e avisos; `parPublicarComRecalculo` (sem recálculo; com recálculo e confirmação; cancelado não chama publicar de novo; corrida 2 vezes ok, 3ª falha; erro de outro tipo sobe); textos de erro; frota válida/ inválida.
Commit: `Paralelismo P4: funções puras de Pendentes, Rodadas e Frotas`.

## Tarefa 2 — API (real e demo) e abas Pendentes/Rodadas/Frotas
- `app/paralelismo-abas.js`: `parApiGestaoReal` (`pendentes()`, `rodadas()`, `vigentes()`, `nomes(ids)`, `publicar(id, rec)`, `recusar(id, motivo)`, `excluir(id)`, `marcarExcluida(tag)`, `buscarBaseRodada(op, cod, rodadaId)`), `parApiG()`, `parRecalcularNoWorker(entrada)`, `parHtmlPendentes()`, `parHtmlRodadas()`, `parHtmlFrotas()`, `parLigarAbas(acao)`.
- `app/paralelismo-demo.js`: dados fictícios mutáveis (rodadas pendentes e publicada, uma que exige recálculo com `window.PAR_DEMO_RECALC`, uma com link malicioso), `publicar/recusar/excluir` simulados.
- `app/paralelismo.js`/`.html`/`.css`: aba Pendentes escondida para leitura; Rodadas com sub-abas; contador de Pendentes passa a vir de `PAR.pend`.
Commit por parte.

## Tarefa 3 — `tests/app/teste_paralelismo_gestao_tela.py` (Edge, demonstração)
Por nível (`window.PAR_DEMO_NIVEL` = leitura, solicitante, editor, admin): abas e botões visíveis/ausentes; solicitante só vê as próprias pendentes; editor publica, recusa (motivo obrigatório), recálculo com confirmação e cancelamento; admin exclui; frotas edita/adiciona (editor) e é só leitura nos outros; links: só os válidos viram `<a>`; 390 px sem rolagem horizontal.

## Tarefa 4 — revisão, verificação, relatório `orquestra/relatorios/S4.md`.
