# Paralelismo P3b (S3): tela Processar, prévia e envio

> Sessão autônoma: o usuário delegou, então este detalhamento não passa por ele. As escolhas de padrão estão em "Decisões" e vão para `orquestra/relatorios/S3.md`.

**Objetivo:** `app/paralelismo.html|css|js` com login, abas, aba Processar (escolher pasta, conferência, fila, prévia, enviar), modo demonstração e erros da spec §10, mais a migration do cartão em Ferramentas. Nada vai ao GitHub nem ao banco real.

**Arquitetura:** a lógica que não precisa de DOM fica em `app/paralelismo-previa.js` (testada com `node --test`): prévia, avisos, carga do `paralelismo_enviar`, mensagens de erro. `app/paralelismo.js` liga a API (real ou demonstração), a fila da S2 e o desenho. O mapa é um `<canvas>` simples, sem MapLibre (a maquete também desenha em canvas; o MapLibre fica para o Painel, P5).

## Decisões (padrão sensato, no lugar do usuário)

1. **Arquivo cortado:** mantém o que a S2 fez (pontos aproveitados, listado como "parcial" na prévia, com aviso). Não é bloqueio: trocar é uma linha no Worker. Registrado como pendência.
2. **SHA-256 de arquivo pulado não é registrado** no envio (nota da S2): `parRegistrosAceitos` filtra pelos `pulados` do resultado, e o `.fdd` par de um `.fdl` pulado sai junto.
3. **Abas Painel, Pendentes, Rodadas** existem, com o contador de Pendentes lendo o banco; o conteúdo é "Chega na etapa P4/P5". Abertura em Processar (única funcional).
4. **Envio:** `preparar_parte` reserva o id (RPC `paralelismo_preparar_parte` direto, com o token do usuário), cada parte e cada shapefile vai por `POST {worker}/paralelismo/parte`, e só no fim chama `paralelismo_enviar`. O id fica no item para "Tentar de novo". Nome dos assets: `p<id>-<n>.zip`, `manifesto.csv`, `amostras-<operacao>-<fazenda>.zip`.
5. **Zip com fflate 0.8.2** (jsdelivr, versão fixada), streaming (`Zip` + `ZipDeflate`), um arquivo do OPFS por vez. Os arquivos zipados são os copiados (`.jdl/.fdl/.fdd`) dos grupos aceitos.
6. **Avisos na prévia:** pulados, parciais, falhas de cópia, frota sem trabalho, fora de talhão > 5%, talhão `insuficiente`, fazenda sem linhas novas (não envia análise zerada de fazenda nova).
7. **Cadastro de frota** (editor): formulário simples na conferência grava em `paralelismo_frotas` por RLS; solicitante só vê "peça ao editor".
8. **Demonstração** (`file://` ou `?demo`): login dispensado, usuário editor fictício, um item pronto de exemplo e Worker/envio simulados. Escolher pasta usa o OPFS real quando houver.
9. **Cartão:** migration `20261105090000_paralelismo_cartao.sql` acrescenta o item a `hub.parametros('ferramentas')` de forma idempotente. Não aplicada.

## Tarefas

- [x] **T1 Migration do cartão** + teste que lê o SQL e o aplica em Postgres local quando houver (idempotência).
- [x] **T2 `paralelismo-previa.js` + testes node** (TDD): `parRegistrosAceitos`, `parPrevia`, `parAvisosItem`, `parPayloadEnvio`, `parNomeParte`, `parTextoErro`.
- [x] **T3 Zip e envio** (`parEnviarItem` com `fetch`/RPC/zip injetáveis) + testes node (falha no meio, mesmo id, nada de `enviar`).
- [x] **T4 HTML/CSS/JS da tela** com API real e de demonstração.
- [x] **T5 `tests/app/teste_paralelismo_tela.py`** (Playwright + Edge, demonstração, dados sintéticos): login ausente, abas, conferência, fila, prévia, envio simulado, 390 px, erro do Pyodide.
- [x] **T6 Revisão de código, verificação, relatório.**
