# Drone no Hub: guia rápido

A tela **Drone** do Hub é onde a Geo faz os projetos de aplicação por drone. Os projetos publicados vão para o portal de downloads, na aba Drone, e é de lá que os pilotos baixam.

## Os dois tipos de projeto

- **Normal:** aplicação na fazenda inteira. É o talhão menos os obstáculos (árvores 15 m, rede 25 m, demais 50 m). O projeto é montado **talhão a talhão**: dá para completar, refazer ou tirar talhões sem mexer no resto.
- **Catação:** só as manchas de infestação de um levantamento. Manchas a até 20 m viram um bloco, com 5 m de folga. Cada levantamento novo **substitui a Catação inteira**.

## A tela

- **Esquerda, a fila:** solicitações de Normal, Catações aguardando infestação, prévias para conferir e o bloco **Atenção**, que lista as Normais incompletas, os obstáculos com mais de 24 meses e os talhões que saíram da Base.
- **Direita, a fazenda:** os cartões da Normal e da Catação, o mapa por talhão e o painel de ações. A Normal mostra "XX% DA FAZENDA" quando falta talhão.
- **No mapa:**
  - marrom ou verde: área de aplicação publicada;
  - cinza: talhão sem projeto;
  - azul: talhão selecionado;
  - vermelho tracejado: talhão marcado para remover;
  - contorno laranja: talhão fora da Base.
  - A chave **mostrar obstáculos** desenha as três classes com o buffer de cada uma.

## Pedir um projeto (solicitante)

1. Clique em **Nova solicitação**.
2. Escolha a fazenda e, se quiser, a data desejada e uma observação.
3. A Geo recebe o aviso no sininho. Quando o projeto for publicado, todos com o módulo Drone recebem o aviso "Publicado".

## Completar ou refazer uma Normal (Geo)

1. Abra a fazenda pela fila, pela busca ou pelo sininho.
2. No modo **Incluir / refazer**, clique nos talhões. "Selecionar todos sem projeto" marca de uma vez os que faltam.
3. Escolha a fonte:
   - **Sistema gera:** usa o talhão da Base menos os obstáculos;
   - **Subir shape:** envia um shape feito no QGIS, e o sistema recorta por talhão.
4. Para tirar talhões, use o modo **Remover** e clique neles.
5. Clique em **Gerar prévia**. Em menos de um minuto aparecem o PDF e os alertas.
6. Confira, escreva o **motivo** (obrigatório a partir da Rev1) e clique em **Publicar**. Se algo estiver errado, clique em **Descartar** e monte de novo.

Talhões que os obstáculos tomam por inteiro ficam fora do projeto, e a prévia avisa quais são.

## Catação (Geo)

1. Na fazenda, abra o cartão **Catação** e clique em **Abrir Catação desta fazenda** (se ainda não houver uma).
2. Clique em **Enviar infestação** e envie as camadas do levantamento. Pode mandar várias de uma vez, ou um `.zip`.
3. Clique em **Gerar prévia**, confira e publique.

## Obstáculos

- Em **Enviar obstáculos**, informe a classe (15, 25 ou 50 m) ou deixe vazio para usar o nome de cada arquivo (ex.: `restricoes15m.shp`).
- Envie o `.shp` com `.shx`, `.dbf` e `.prj`, ou um `.zip`. Sem o `.prj` o envio é recusado.
- Obstáculo novo **não refaz** projeto publicado. Ele vale para as próximas gerações, e a prévia avisa quando há obstáculo mais novo do que o projeto.

## Avisos (sininho)

| Aviso | Quando some |
|---|---|
| Nova solicitação | ao gerar a prévia |
| Prévia pronta para conferir | ao publicar ou descartar |
| Erro na geração, no envio ou ao publicar | ao gerar ou enviar de novo |
| Publicado | depois de 7 dias |

## Consultas

Em **Consultas → Drone**, a tabela mostra, por fazenda: a Normal (revisão e cobertura), a Catação (revisão e área), as datas dos obstáculos e a solicitação aberta. Dá para filtrar, copiar para o Excel ou mandar a lista pelo WhatsApp.

## Quando algo dá errado

- **"Já existe uma prévia aberta":** publique ou descarte a prévia que está aberta antes de gerar outra.
- **"Talhões que não existem na Base de hoje":** o talhão saiu ou mudou de número na Base. Atualize a seleção.
- **Envio com erro:** a mensagem aparece no quadro de Obstáculos ou no botão do shape. Corrija o arquivo e envie de novo.
- **Prévia que não sai do "gerando…" por vários minutos:** o agente do servidor Geo pode estar parado. Avise o responsável pelo servidor.
