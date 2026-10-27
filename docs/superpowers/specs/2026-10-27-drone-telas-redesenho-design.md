# Drone: redesenho das telas e correções visuais

Data: 27/10/2026 · Situação: aprovado em conversa, aguardando revisão desta spec
Maquete aprovada: https://claude.ai/artifact/HGJ6zku4ABshgCFSzmDJup (6 telas, com links entre si)

## 1. Objetivo

A tela do Drone ([app/drone.js](../../../app/drone.js)) atende ao dia a dia, mas acumula informação: fila, busca, mapa, revisão, obstáculos, prévia e histórico ficam todos visíveis ao mesmo tempo, e o painel lateral empilha tudo. O objetivo é **refazer o mesmo fluxo com uma tela mais limpa**, sem mudar o que o sistema faz:

- **Início do Drone** para ver a esteira e escolher a fazenda.
- **Área de trabalho da fazenda**, com o mapa grande e só as ferramentas da etapa atual.
- **Janela de obstáculos** para subir as 3 classes de uma vez.
- **Atualização sem pisca-pisca**, com animações que mostram o andamento.

Sucesso:
- quem usa encontra a próxima ação sem procurar;
- subir obstáculos é um passo só;
- nada pisca enquanto o agente trabalha;
- erro antigo não fica preso na tela;
- dado novo aparece sem precisar atualizar a página.

## 2. Bugs que entram (sessão S0, antes do redesenho)

| Bug | Causa (no código atual) | Correção |
|---|---|---|
| O erro de obstáculos não some depois de reenviar | `drObstaculosHtml` pega o primeiro envio com `status='erro'` entre os últimos 5, de qualquer tipo ([drone.js:317](../../../app/drone.js#L317)) | Considerar só o **último envio de obstáculos**: mostrar o erro apenas se ele estiver com erro. Função pura `drUltimoEnvio(envios, tipo)` |
| O obstáculo novo só aparece no mapa depois de atualizar a página | `DR.obstGeo` fica guardado e nunca é descartado ([drone.js:822](../../../app/drone.js#L822)) | Descartar o cache quando a assinatura das versões vigentes (`classe:versao` de `DR.info.obst`) mudar |
| O mapa pisca durante o processamento | O polling de 5 s chama `drRender`, que reescreve `#dr-faz` inteiro e destrói e recria o MapLibre ([drone.js:206](../../../app/drone.js#L206)) | Correção mínima na S0: o polling chama um redesenho que mantém o mapa (atualiza as fontes com `setData`) e só refaz o painel. A correção completa vem com o motor novo (S2) |

A S0 vai para o ar sozinha, porque não depende do layout novo.

## 3. Telas

### 3.1 Início do Drone
- **Topo:** título, busca grande (nome ou código; atalho `/`) e o botão **Nova solicitação** (mesmo formulário de hoje, só restilizado).
- **Três colunas**, na ordem da esteira:
  - **Solicitações:** pedidos sem geração ativa (status `solicitado`, `aguardando_obstaculos`, `aguardando_infestacao`, ou `em_elaboracao` sem geração). Cartão: código, fazenda, chip Normal/Catação, observação ou situação, solicitante, quando pediu, data desejada.
  - **Em desenvolvimento:** geração em `fila`/`processando` (com trilho animado e tempo desde `pedido_em`), geração com `erro` (cartão com borda vermelha e a mensagem) e publicação pedida (drone pairando, "Publicando no portal…"). Publicação com erro também cai aqui, como erro.
  - **A analisar:** geração `pronta`, sem publicação pedida. Cartão com o número de alertas e o botão **Conferir**. No rodapé da coluna: "Publicadas nos últimos 7 dias: N".
- O cartão leva à área de trabalho da fazenda, já na aba do tipo dele.
- **Faixa "Atenção na base"** embaixo, com três contadores clicáveis (Normais incompletas, obstáculos com mais de 24 meses, talhões fora da Base). Cada um abre uma **lista lateral** (drawer) de fazendas. A lista de obstáculos antigos abre a fazenda com a janela de obstáculos aberta.
- Link de Ajuda (manual) na faixa.
- Coluna vazia: uma frase curta, sem caixa vazia.
- Solicitante vê a mesma tela. Ações de editor (Conferir, publicar) ficam ocultas para quem não edita.

### 3.2 Área de trabalho da fazenda (layout comum)
- **Cabeçalho fixo:** ← Início, código e nome, talhões e área. Abas **Normal | Catação**, cada uma com a revisão vigente (Normal mostra também a cobertura %). Botão **Obstáculos** com chip de situação: "3 classes · data mais recente". O chip fica âmbar quando alguma classe tem mais de 24 meses, vermelho quando o último envio deu erro e com um indicador girando quando há envio em fila ou processando. Menu **⋯** com Revisões (histórico, numa lista lateral) e Cancelar solicitação (mesmas regras de `drPodeCancelar`).
- **Barra de etapas:** Montar revisão → Gerar prévia → Conferir → Publicado. A etapa ativa vem do estado. A passagem usa `Mo.etapa`. Linha de contexto da solicitação à direita (quem pediu, observação, data).
- **Mapa** ocupando o espaço livre. **Barra de ferramentas flutuante** à esquerda (Incluir, Remover, Sem projeto, Limpar). Zoom e **Camadas** (substitui o checkbox "mostrar obstáculos") à direita. **Legenda** compacta embaixo e dica curta no topo ("Clique nos talhões…").
- **Painel direito** (340–380 px) que mostra **um estado por vez**, com a ação principal fixa no rodapé.

### 3.3 Estados do painel
1. **Montando revisão (Normal, editor, sem geração ativa):** título "Normal · RevN". Lista "Incluir ou refazer" com uma linha por talhão (número, situação sem projeto ou refazer RevX, área e o seletor Sistema/Shape **por talhão**). Se algum talhão está em Shape, aparece a área de arrastar o shape de ajuste, com a situação do envio. Seção "Remover" e nota explicativa. Rodapé: **Gerar prévia**, habilitado quando há algo a incluir ou remover.
   - Mudança de comportamento: hoje a fonte (Sistema/Shape) vale para todos os selecionados. Passa a valer **por talhão**. O escopo enviado ao agente já é por talhão (`{talhao, fonte, envio_id}`), então o agente não muda. Um único shape de ajuste serve a todos os talhões marcados como Shape, como hoje.
2. **Catação (editor):** passos numerados: (1) Solicitação aberta, ou o botão "Abrir Catação desta fazenda"; (2) Enviar infestação, com área de arrastar, lista das camadas enviadas e "Trocar arquivos"; (3) Gerar prévia. Nota: "Um levantamento novo substitui a Catação inteira". Rodapé: **Gerar prévia** (regra `drPodeGerarCatacao`).
3. **Gerando (geração em fila ou processando):** cartão com trilho animado, tempo decorrido e os passos *Pedido recebido → Processando → Prévia pronta* (só o que o agente informa). Resumo do pedido e a nota "Pode sair desta tela; a prévia aparece em A analisar e no sininho". Mapa travado (seleção desligada, navegação livre), com véu leve, faixa de varredura e os talhões da revisão pulsando.
4. **Prévia pronta:** capa do PDF (como hoje, com pdf.js) e **Abrir prévia**, que abre a janela de prévia atual sem mudança. Indicadores: área de aplicação (`resumo.aplicacao_ha`) com a diferença para a vigente (`DR.geo.normal.area_ha`) e cobertura (`resumo.cobertura_pct`) contra a vigente (só na Normal). Lista de alertas com o texto de `drone_geracoes.alertas`, campo Motivo, **Descartar** e **Publicar no portal**. No mapa, a área nova entra com fade, a borda do que é novo fica destacada e os obstáculos ficam ligados.
5. **Publicando:** `Mo.voo` sobre o mapa, como hoje.
6. **Somente consulta** (sem permissão de edição): mapa, chips e histórico, sem ações.
- Erros de ação aparecem numa linha de erro no painel, perto do botão que falhou, e somem na próxima ação.

### 3.4 Janela de obstáculos
- Abre pelo botão Obstáculos (ou pela faixa Atenção). Três cartões com a situação atual de cada classe (15/25/50 m, descrição da classe, versão, data, número de feições). O cartão fica âmbar quando passa de 24 meses.
- **Área de arrastar** (ou "Escolher arquivos"), que aceita vários `.shp/.shx/.dbf/.prj/.cpg` e `.zip`.
- **Agrupamento:** os arquivos se juntam pelo nome-base. `.zip` é aberto no navegador (JSZip, do cdnjs) e o conteúdo vira arquivos soltos. Cada camada mostra as partes presentes (.shp .shx .dbf .prj), com a que faltar em vermelho. A camada que não tem `.shp`, `.shx` ou `.dbf` bloqueia o envio.
- **Classe:** sugerida por `drClassePeloNome`, a mesma regra de `drone/insumos.py::classe_pelo_nome`, portada para JS e testada com os mesmos casos. Botões 15/25/50 por camada, com a dica "pelo nome do arquivo", "trocada por você" ou "escolha a classe". O botão de enviar só libera com todas as camadas classificadas.
- **Envio:** cada arquivo sobe renomeado com a classe na frente (`<classe>m_<nome seguro>`, por exemplo `25m_linhas_cemig.shp`). Assim o agente lê a classe pelo nome e grava tudo num **lote único** (`p_classe_m = null`). **O agente não muda.** O progresso usa `Mo.progresso` dentro da janela.
- Resumo no rodapé: "Vai criar uma versão nova de 15 m, 25 m. Classes que não aparecem aqui continuam como estão."
- Depois de enviar, a janela fecha e o chip de Obstáculos passa a "processando". Quando o agente termina, o chip volta ao normal, a camada de obstáculos é recarregada e entra no mapa com fade. Se der erro, o chip fica vermelho e a janela mostra o erro na próxima abertura.

## 4. Motor de atualização (sem pisca-pisca)

- **Mapa criado uma vez por fazenda.** Trocar de aba ou chegar dado novo só faz `setData` nas fontes (`tal`, `apl`, `obs`) e `setPaintProperty` quando a cor do documento muda. O mapa só é recriado ao trocar de fazenda.
- **Estado separado do desenho:** `drCarregarFazenda()` busca os dados e compara com o anterior. Cada parte da tela (cabeçalho, barra de etapas, painel, chip de obstáculos, mapa) tem a sua função de desenho e só é redesenhada se os dados dela mudaram (comparação por assinatura simples, JSON das partes relevantes).
- **Polling único**, só enquanto houver algo em andamento na fazenda aberta (geração em fila/processando, publicação pedida, envio em fila/processando): 5 s, como hoje. O Início tem polling próprio de 10 s, só quando alguma coluna tem item em andamento e a tela está visível (`document.visibilityState`).
- **Início:** os cartões são reconciliados por `id` (cria, atualiza ou remove). Quando um cartão muda de coluna, a mudança é animada (FLIP: mede antes e depois e anima o deslocamento com `transform`).
- **Cache de obstáculos** com chave pela assinatura das versões vigentes (bug 2).
- `prefers-reduced-motion`: todas as animações novas caem para o estado final, como já faz o `motion.js`.

## 5. Animações

Reaproveitadas de [app/motion.js](../../../app/motion.js) (contrato atual, sem mudar):
`Mo.ocupado` (botões), `Mo.progresso` (envios), `Mo.carregando`/`Mo.pronto` (entrada do Início, da fazenda e da janela), `Mo.etapa` (barra de etapas), `Mo.voo` (publicação), `Mo.concluido` (publicado, opcional).

Novas, acrescentadas ao `motion.js`/`motion.css` como extensão do contrato:
- `Mo.trilho(el)`: faixa de luz correndo num trilho fino (cartões "gerando" e painel Gerando).
- `Mo.varredura(mapaEl)` → `{parar()}`: véu leve e faixa varrendo o mapa, sem tocar no canvas (overlay em CSS).
- `Mo.mover(container, aplicar)`: FLIP para reordenar ou trocar cartões de coluna. Mede, aplica a mudança no DOM e anima.
- Pulso de contorno dos talhões em geração: feito no MapLibre animando `line-opacity` por `requestAnimationFrame` só na camada da seleção, e parado ao sair do estado.
- Fade de camada nova no mapa: `fill-opacity` de 0 ao valor final com `*-opacity-transition` do MapLibre.
- Indicador girando (chip de Obstáculos e etapa ativa): CSS puro.

## 6. Dados e banco

- **Sem mudança no agente** (Python) e sem mudança de tabelas.
- Uma migration pequena que **estende `hub.drone_painel`**:
  - a geração passa a trazer `pedido_em` e `iniciado_em`, para o tempo decorrido;
  - novo campo `publicadas_7d` (contagem de gerações publicadas nos últimos 7 dias);
  - `obstaculos_antigos` e `fora_da_base` passam a trazer `fazenda` (nome) junto do código, para a lista lateral.
- `drRecarregarFazenda` passa a buscar também `alertas` (texto) e `resumo` da geração ativa, e `n_feicoes` por versão de obstáculo (coluna já existe em `hub.drone_obstaculo_versoes`).
- A busca da área de trabalho continua lendo `fazendas` como hoje.

## 7. Organização do código

`app/drone.js` tem 837 linhas e mistura tudo. A tela nova é dividida em arquivos por responsabilidade, todos carregados por `index.html` na ordem:
- `app/drone-dados.js`: busca e estado (`DR`), assinaturas, regras puras (status → coluna, etapa ativa, `drUltimoEnvio`, `drClassePeloNome`, agrupamento de arquivos por nome-base).
- `app/drone-inicio.js`: Início (colunas, reconciliação, faixa Atenção, listas laterais, nova solicitação).
- `app/drone-fazenda.js`: área de trabalho (cabeçalho, etapas, mapa e ferramentas, estados do painel).
- `app/drone-obstaculos.js`: janela de obstáculos.
- `app/drone-previa.js`: prévia em pdf.js (o código de hoje, movido sem mudar).
- O CSS sai do `drEstilo()` em string e vai para `app/drone.css`.

## 8. Testes

- **Puros** (`node --test tests/app/drone_puro.test.js`, ampliando o existente): status → coluna; etapa ativa; `drUltimoEnvio`; assinatura que invalida o cache de obstáculos; `drClassePeloNome` com os mesmos casos do teste Python de `classe_pelo_nome`; agrupamento de arquivos (partes faltando, `.zip` expandido); renomeação `<classe>m_<nome>` que o regex do agente lê de volta; fonte por talhão gerando o escopo certo.
- **Tela** (`tests/app/teste_drone_tela.py`, ampliando): o Início mostra as 3 colunas; abrir fazenda; o mapa **não é recriado** no polling (o mesmo objeto de mapa antes e depois de um ciclo); a janela de obstáculos bloqueia sem classe e envia com nomes renomeados; o erro antigo some depois de um envio ok.
- Testes que gravam no banco salvam e restauram o valor original (regra do projeto).
- Conferência visual no navegador contra a maquete, ao fim de cada sessão de tela.

## 9. Sessões de execução

Cada sessão é curta, termina com teste e revisão do diff e entra na main antes da próxima. Execução delegada (skill `delegar`) quando couber; desenho, revisão e merge ficam com o Claude principal.

| Sessão | Conteúdo | Entra no ar? |
|---|---|---|
| **S0** | Os 3 bugs na tela atual (§2) e os testes puros deles | Sim, sozinha |
| **S1** | Divisão de `drone.js` nos arquivos da §7 **sem mudar o comportamento** e CSS em `drone.css`. Os testes atuais continuam passando | Sim (nada muda para o usuário) |
| **S2** | Motor de atualização (§4) e animações novas no `motion.js` (§5), ainda na tela atual | Sim |
| **S3** | Migration do painel (§6) e Início (§3.1) | Sim |
| **S4** | Área de trabalho: cabeçalho, etapas, mapa com ferramentas e estados do painel (§3.2–3.3) | Sim |
| **S5** | Janela de obstáculos (§3.4) | Sim |
| **S6** | Polimento (`impeccable`, `design-motion-principles`), revisão final e atualização do manual `docs/drone-manual.md` | Sim |

## 10. Fora do escopo

- Etapas intermediárias reais da geração (exigem mudar o agente).
- Editor de geometria no navegador.
- Parte 3 (Catação automática pelo Drone MGMT).
- Mudanças no portal de downloads.
