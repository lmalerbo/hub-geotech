# Mapas de aplicação: novo layout das telas

Data: 27/10/2026. Pedido do Leo: desenvolver melhor o layout de `app/aplicacao.html`.
Variações desenhadas no canvas https://claude.ai/artifact/QGhJ6aeLkAin16s7doJNsi. O Leo escolheu a **variação A**
(coluna à direita), a **lista em linhas** e o **novo mapa em dois passos**.

## Quem usa

O analista monta os mapas no escritório, sempre no computador. São uns 10 mapas por fazenda em cada safra. Ajustar a
área de um talhão é exceção. O celular não é alvo: a tela só não pode quebrar em janela estreita.

## O que muda

### Tela do mapa (variação A)
- Ocupa a janela inteira (hoje fica presa em 880 px). O cabeçalho do app some nessa tela e dá lugar a um cabeçalho do
  mapa: botão "Mapas da fazenda", título "Operação, dd/mm/aaaa", subtítulo com fazenda e quem alterou, e **Baixar PDF**
  à direita (com a barra de preparo do gerador no mesmo lugar).
- O mapa ocupa o espaço à esquerda. Por cima dele:
  - **barra de seleção** embaixo, no centro: "N talhões marcados", a lista dos talhões e a soma em ha, mais os botões
    Limpar e Selecionar todos. Sem nada marcado, ela diz "Clique nos talhões para marcar" e mostra só Selecionar todos;
  - **dica ao passar o mouse** num talhão: número, área, aplicações dele (ou "Sem aplicação") e "Clique para marcar"
    ou "Clique para desmarcar".
- Coluna da direita (380 px):
  - **Nova aplicação** só aparece aberta, com borda verde, quando há talhões marcados. O título diz "Nova aplicação nos
    N talhões". Os campos de área por talhão ficam recolhidos em "Ajustar a área de algum talhão". O botão diz
    "Aplicar nos N talhões (total previsto)". Sem talhão marcado, aparece só uma linha de orientação.
  - **Aplicações do mapa**, que serve de legenda: quadrado de cor, rótulo com dose, O.S., talhões e total. Editar e
    Excluir ficam num menu "⋯". Clicar no cartão destaca os talhões no mapa, como hoje. No fim, a linha "Sem
    aplicação: talhões …".
  - **Total do mapa** fixo no pé da coluna (e a linha da área com 5% no mapa aéreo).

### Lista de mapas
- Mapas em linhas (Tipo, Data, O.S., Talhões, Total, Alterado), com a linha inteira clicável. Excluir fica no menu "⋯".
- Abaixo da busca de fazenda, "Abertos por último": os 3 últimos mapas abertos neste navegador, de qualquer fazenda.

### Novo mapa
- Janela em dois passos: primeiro **Corretivo** ou **Aplicação aérea**, como dois cartões com ícone e uma linha de
  explicação. Para corretivo, em seguida a operação (SubSolagem, SuperGrade, Arado). O botão diz o que vai criar
  ("Criar mapa de SubSolagem").

## Fora do escopo
- Duplicar mapa (ideia do canvas, não confirmada).
- Editar os talhões de uma aplicação pelo mapa: a edição continua na janela com caixas de marcar.
- Qualquer mudança no PDF, no banco ou nas RPCs.
