# Preparo: fase de voo antes da Identificação

Data: 29/10/2026. Status: aguardando aprovação.

## Problema

Todo talhão que entra numa demanda do Preparo cai direto em **Identificação**, a primeira etapa.
A tela não distingue "o analista precisa identificar" de "ainda não há material para identificar".
Exemplo: SAO JOAO 14 (10724), 2 talhões em Identificação, voo nem solicitado.

## Regras (decididas com o usuário)

1. Sem voo não há projeto. O material vem dos projetos de voo **Sistematização** e **Expansão** do Drone MGMT.
2. Quem pede o voo é o analista do Preparo, direto no Drone MGMT. O Hub **só lê**: não agenda nem altera nada.
3. A fase é **por talhão**. O avanço pode ser parcial: com 5 de 10 talhões liberados, o analista
   segue com esses 5 ou espera o resto (o voo às vezes chega parcelado).
4. Só contam voos **dentro da safra atual**: data do registro a partir de `hub.ciclo_inicio()` (01/04).
5. O talhão está liberado quando o voo chega em **"Processado, aguardando divulgação"** ou além (divulgado).
6. Sem voo liberado, o Hub **avisa e deixa avançar**: não trava.
7. O Hub só mostra a situação, sem link para o Drone MGMT.

## Situações do talhão

Calculadas, não marcadas por ninguém. Se o talhão tiver mais de um registro na safra, vale o mais avançado.
Registros cancelados (`controlStatus` 11) não contam.

| Situação              | controlStatus no Drone MGMT                          |
|-----------------------|------------------------------------------------------|
| Voo não solicitado    | nenhum registro de Sistematização/Expansão na safra |
| Voo solicitado        | 1 a 3 (aguardar, a voar, voar novamente)             |
| Voado, processando    | 4 até antes de "Processado, aguardando divulgação"  |
| **Liberado**          | "Processado, aguardando divulgação" e divulgado     |

## Desenho

**O modelo de etapas não muda.** O talhão continua com `talhao_preparo.etapa = Identificação`. A fase de
voo é uma leitura a mais, mostrada só para os talhões que estão em Identificação, porque nas etapas
seguintes o material já foi usado.

1. **GeoMap (rota nova, só leitura):** `POST /integracao/dronemgmt/preparo/voos` recebe
   `{ itens: [{ section, landPlot }] }` (até 200) e devolve os registros dos projetos Sistematização e
   Expansão de cada talhão, sem os cancelados: `id, flightProject, controlStatus, createdUtc,
   scheduledDate, startDateFlight`. Usa a mesma consulta `formdata/query` e a mesma chave do Hub
   (`x-hub-token`) de `registrosLinhasColheita`.
2. **Banco do Hub:** guarda os registros lidos em `hub.voo_dronemgmt`. É o espelho que já existe e
   está vazio; ele já tem `projeto_voo` e `control_status`. Uma view `hub.preparo_voo_talhao`
   (`security_invoker`) devolve, por layer, a situação da tabela acima, filtrando a safra atual.
3. **Agente diário:** `ingestao/voos_preparo.py`, no molde de `voos_linhas_colheita.py`. Ele lê os
   talhões do Preparo em Identificação, consulta o GeoMap em lotes e grava em `hub.voo_dronemgmt`.
   Roda junto com o agendamento da Colheita.
4. **Tela (Etapas do Preparo):**
   - O passo Identificação mostra quanto tem em cada situação, por exemplo "Identificação 2 · sem voo 2".
   - A barra separa os talhões de Identificação entre os liberados e os que aguardam voo, com cor própria.
   - Na lista de talhões, cada talhão em Identificação mostra a etiqueta da situação.
   - Ao concluir a Identificação de talhões sem voo liberado, aparece um aviso dentro da tela
     ("X talhões sem material de voo. Avançar mesmo assim?"), sem `confirm()` do navegador.
     A decisão fica no log de auditoria.

## Levantamento de 29/10/2026 (só leitura, Drone MGMT)

29 talhões em Identificação, nenhum com material: 6 voados em 28/10 e ainda processando (status 4),
17 com voo solicitado (status 2), 5 sem voo pedido e 1 só com Levantamento Topográfico.

- **"Processado, aguardando divulgação" = `controlStatus` 9.** Confirmado: os voos de Sistematização
  em status 9 não têm `dateDisclosureProcessing`, e esses talhões já passaram da Identificação.
  Liberado = 9 ou 10.
- O nome do projeto vem em `flightProjectDetails.description` (consulta com `expand=flightProject`).
  Basta filtrar por "Sistematização" e "Expansão", sem fixar UUID.
- **Levantamento Topográfico não conta.** Não se faz projeto com ele, e até hoje ele nunca coincidiu
  com uma demanda.
- Talhões pequenos sem voo (0,5 a 2,5 ha): ainda não foi decidido se vão pedir voo. Aparecem como
  "Voo não solicitado", sem tratamento especial.

## Conferir na implementação

- O código 12 ("Importar falhas") é da Falha Soca. Confirmar se aparece nesses projetos.
- Registros com `harvest` errado: o filtro é pela data do registro, não pelo campo `harvest`.

## Fora do escopo

- Agendar voo pelo Hub.
- Travar a Identificação sem voo.
- Mudar a ordem ou os nomes das etapas.
