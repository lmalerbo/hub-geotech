# S2 — Tela de projetos (Plantio + Preparo)

Spec: `docs/superpowers/specs/2026-10-23-fluxo-projetos-design.md` (D1–D5, contrato). Branch `fluxo-tela`.

## Arquivos
- `app/projetos.js` (novo): tudo da tela de projetos, prefixo `Proj`/`pj`, CSS injetado (como `drone.js`).
- `app/projetos-demo.html` (novo): fixture com dados fictícios e API simulada, para conferir sem login.
- `app/index.html`: só ganchos — `<script src="projetos.js">`, e `rDet`/`rDetP`/`rFaz`/`rFazP` chamam `Proj`.
  Não toca `motion.*`, `rpcAcao`, `recarregar` (só chama), `carregarDados`, `confirmarEnvio`.

## Forma dos dados que a tela usa
`Proj.fazenda(modulo, f)` normaliza a fazenda do index:
`{modulo, cod:Number, nome, ha, talhoes:[{num, ha, e}], etapas:[{id,l,c,i}]}`
- Plantio: de `FZ[i].tals` (`num`, `ha`, `e` 0–4, Ok = 4).
- Preparo: de `FZ_P[i].tals` (mesma forma, e 0–4: Identificação, Escoamento, Observações, Projeto, Ok).
  Enquanto `FZ_P[i].tals` não existir, `rDetP` continua com a tela antiga (ver L1).

## Comportamento
- **Distribuição**: cartão da fazenda e cabeçalho mostram barra empilhada de talhões por etapa + "x/y Ok".
- **Seleção**: coluna de seleção na tabela; clicar num segmento da distribuição seleciona os talhões daquela etapa. Cada etapa presente vira um bloco de ação "N talhões em X → ação"; a ação vale para os selecionados daquela etapa (nenhum selecionado nela = todos dela).
- **Barra de etapa**: mostra a contagem por etapa; tem uma alça na etapa mais avançada dos selecionados que só arrasta (ou clica/setas) para trás. Soltar numa etapa anterior → modal com justificativa obrigatória → `projeto_retroceder` → `Mo.etapa` → aviso com **Desfazer** (`projeto_desfazer(lote_id)`). A linha do tempo também oferece Desfazer no evento mais novo se for retrocesso ainda não desfeito.
- **Nova revisão** (modal próprio, `pj-modal-rev`): documentos que mudaram (checkbox) + um campo de arquivo por documento marcado; Plantio tem "Mapa de Plantio (.pdf)" opcional; Preparo: Projeto marcado trava Exportação e Sistematização marcadas. Talhões que traz/altera (chips, padrão nenhum) com prévia do efeito (D3). Motivo obrigatório se a fazenda já tem revisão. Título "Nova revisão · Rev{maior número entre documentos + 1}".
  Confirmar: `projeto_nova_revisao` → envia cada arquivo pelo Worker (`nova=0`) com `Mo.progresso` → (se veio de uma ação de avanço) `projeto_avancar` → `recarregar()`.
- **Ações com arquivo** (Plantio Andamento; Preparo Escoamento e Projeto) abrem o mesmo modal pré-preenchido com os documentos e os talhões selecionados. Se a revisão mais recente já contém esses talhões e ainda não tem o documento, o envio **completa essa revisão** (revisão aberta, D3) em vez de abrir outra.
- **Linha do tempo**: carrega `projeto_linha_do_tempo` ao abrir a fazenda (`Mo.carregando/pronto`).
- **Conclusão**: se depois de recarregar todos os talhões estão Ok e antes não estavam → `Mo.concluido`.
- Movimento: usa `window.Mo` se existir; senão funções vazias locais (não cria `motion.js`).

## Ações (`p_acao`) por etapa atual
| Módulo | e | Ação | Botão |
|---|---|---|---|
| plantio | 0 | `mapeamento_concluido` | Mapeamento concluído |
| plantio | 1 | `iniciar` | Iniciar projeto |
| plantio | 2 | `exportacao_enviada` | Enviar exportação e projeto (modal) |
| plantio | 3 | — (mapa pelo envio; regra Ag. Mapa → Ok no `registrar_arquivo`) | Enviar Mapa de Plantio (modal) |
| preparo | 0 | `identificacao` | Confirmar identificação |
| preparo | 1 | `escoamento` | Enviar Mapa de Escoamento (modal) |
| preparo | 2 | `observacoes` | Confirmar observações |
| preparo | 3 | `projeto` | Enviar projeto, exportação e sistematização (modal) |

## Lacunas do contrato — para a coordenação (não alteradas aqui)
- **L1 — leitura da etapa por talhão do Preparo.** O contrato tem as RPCs de escrita, mas não diz como a tela lê a etapa de cada talhão do Preparo. Proposta: `carregarDados` (S4) preenche `FZ_P[i].tals=[{num,ha,e}]` a partir do que S1 gravar.
- **L2 — envio numa revisão aberta pela RPC.** `projeto_nova_revisao` devolve `revisao_id/numero/sufixo`, e "o Worker continua igual". A tela supõe que um envio com `nova=0` cai na revisão que acabou de ser aberta, ou seja, que `preparar_envio` usa a mais recente do projeto. Se não for assim, o Worker precisa aceitar `revisao_id`.
- **L3 — `p_talhoes int[]`.** A tela manda `talhao_num`, não `layer`.
- **L4 — observação do Preparo.** `projeto_avancar` não tem `p_observacao`. Hoje `preparo_concluir_etapa(…, p_observacao)` grava o texto da etapa Observações.
- **L5 — `p_para`.** A tela manda o código da etapa: Plantio usa os rótulos de hoje (`'Aguard. Map.'`, `'Pendente'`, `'Andamento'`, `'Ag. Mapa'`); Preparo usa `'identificacao'`, `'escoamento'`, `'observacoes'`, `'projeto'`.
- **L6 — forma dos eventos da linha do tempo.** `tipo` ∈ `avanco|retrocesso|desfazer|revisao|arquivo`. `detalhe` pode trazer `lote_id`, `de`, `para`, `talhoes:[num]`, `justificativa`, `desfeito:boolean`; em `revisao`: `revisao_id`, `numero`, `documentos:[cod]`, `talhoes:[{num,tipo}]`, `motivo`; em revisão antiga (numeração por documento): `documento`. A tela também lê `detalhe.mapa:boolean` (a revisão já tem o Mapa de Plantio .pdf) para saber se o mapa completa a revisão aberta.
- **L7 — quem move os talhões novos.** Num envio que vem de uma ação, `projeto_nova_revisao` aplica a D3. A tela supõe que ela move só os **alterados**, e que os **novos** andam pelo `projeto_avancar` chamado depois do envio, que confere os arquivos. Assim, um envio que falhe não deixa talhão adiantado sem arquivo.
