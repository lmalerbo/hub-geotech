# Mapas de aplicação: título do tipo e layout do Aéreo (tela + PDF)

Data: 28/10/2026 · Aprovado em conversa pelo Leo em 28/10/2026.

## Objetivo

1. Nos dois tipos de mapa (corretivo e aéreo), o tipo do mapa deixa de ser uma etiqueta pequena no carimbo e vira
   um título em destaque.
2. No aéreo, todos os talhões recebem sempre os mesmos insumos. O mapa deixa de separar insumo por talhão, na tela e
   no PDF. A tabela mostra só talhão, área e total, e o insumo aparece só na legenda e nos cards de totais. Os cards
   ganham destaque.

3. Corretivo ganha a operação de preparo **Experimento** (pedido de 28/10), com o mesmo preenchimento das outras
   (calcário, fosfato, blend, dose, O.S.).

## Operação Experimento (corretivo)

- Chave `experimento`, nome `Experimento`. Aparece no "Novo mapa" junto de SubSolagem, SuperGrade e Arado; na lista
  de mapas com cor própria (`--experimento: #c2557a`); no PDF o título fica `CORRETIVO · EXPERIMENTO`.
- Migração nova `supabase/migrations/20261028090000_operacao_experimento.sql` troca a regra
  `corretivo_mapas_operacao_check` para aceitar `experimento`. O Leo aplica a migração antes do deploy da tela.

## Fora do escopo

- Banco de dados: só a migração do Experimento. As tabelas e RPCs `corretivo_*` continuam como estão.
- PDF do Drone (`mapas/layout.py` não muda; a regressão `tests/drone/test_mapa_pdf_regressao.py` continua passando).
- Tabela, mapa e cards do corretivo: só o título muda.

## Modelo (sem mudar o banco)

No aéreo, cada insumo continua sendo uma aplicação (`corretivo_aplicacoes`) com a sua lista de talhões. A regra
nova é que **todas as aplicações do mapa têm a mesma lista de talhões**, os "talhões do mapa".

- Talhões do mapa = união dos talhões de todas as aplicações. Mapas antigos com listas diferentes continuam abrindo;
  a primeira mudança de talhões feita na tela iguala todas as listas.
- O PDF não depende dessa regra para estar certo: soma por talhão o que está gravado de verdade.

## PDF (`mapas/corretivo_pdf.py`, `mapas/corretivo_dados.py`)

### Título do tipo (corretivo e aéreo)

- A etiqueta verde de 4,5 pt sai. A primeira linha do bloco de identificação do carimbo passa a ser o tipo, em
  negrito, na cor da marca (`MARCA`), com cerca de 11 pt (reduz até caber em `WA − 6`): `APLICAÇÃO AÉREA` ou
  `CORRETIVO · SUBSOLAGEM` / `SUPERGRADE` / `ARADO`.
- Embaixo vêm, como hoje, `cod_faz · nome` e a linha `MAPA DE APLICAÇÃO · … · O.S. …`.
- Se for preciso, a altura mínima do carimbo cresce para caber as três linhas sem sobrepor.

### Cards de totais (aéreo)

- Um card por insumo, como hoje (`_totais_insumos`, com a margem de 5%).
- Card mais alto (cerca de 20 mm em vez de 15): nome do insumo em cerca de 6,5 pt (reduz até 5 pt; depois corta),
  valor em cerca de 16 pt (reduz até 11 pt), unidade em cerca de 8 pt.
- `_altura_carimbo` e o passo entre linhas de cards acompanham a nova altura no aéreo. No corretivo os cards ficam
  como estão.

### Tabela (aéreo)

- Colunas: `TALHÃO | ÁREA (ha) | TOTAL`. Saem INSUMO, DOSE/ha e O.S.
- Uma linha por talhão, sem linhas extras por insumo.
- TOTAL do talhão = soma de `área × dose` de todos os insumos daquele talhão, agrupada por unidade:
  só L → `29,45 L`; L e kg → `29,45 L + 3,00 kg`. Talhão sem insumo → `—`.
- Linha do talhão 400 (margem): área = 5% da soma, como hoje, e TOTAL = soma de `margem × dose` de cada insumo,
  agrupada por unidade.
- Linha final `Total`: área total e a soma por unidade (fecha com a soma dos cards).
- Nota de rodapé da tabela: `* área editada · talhão 400 = margem de 5% da área · TOTAL = soma dos insumos do talhão`.
- Letra das linhas continua em 12 pt; paginação continua igual, agora com uma linha por talhão.

### Mapa e legenda (aéreo)

- Todo talhão do mapa com pelo menos um insumo é pintado de uma cor só (a primeira cor de `PALETA_INSUMOS`), sem
  faixas. Talhão do mapa sem insumo: `SEM_APLICACAO`. Talhão da fazenda fora do mapa: branco, como hoje.
- Legenda dentro do mapa: um item `■ Área de aplicação` e, embaixo, o nome de cada insumo (sem quadrado de cor e sem
  dose), na ordem das aplicações. O item `◩ duas aplicações` não aparece no aéreo.

## Tela (`app/corretivos.js`, `app/corretivos-pdf.js` se precisar)

No aéreo:

- **Talhões do mapa.** A seção de seleção continua (clicar no mapa, "Selecionar todos", "Limpar"). Com talhões
  marcados, o painel oferece **Incluir no mapa** (para os que ainda não estão) e **Tirar do mapa** (para os que
  estão). Cada ação regrava todas as aplicações do mapa com a nova lista, uma `editarAplicacao` por insumo, em
  sequência. Se uma falhar, a tela avisa ("Não foi possível atualizar todos os insumos. Tente de novo.") e recarrega
  o mapa; repetir a ação iguala as listas.
- **Novo insumo.** O formulário (insumo, dose, O.S.) fica sempre disponível, sem precisar marcar talhões, e grava
  com os talhões do mapa. Se o mapa ainda não tem talhões, usa os marcados; sem nenhum, pede para marcar.
- **Editar insumo.** O diálogo perde a lista de talhões; muda só dose e O.S.
- **Mapa na tela.** Uma cor só para os talhões do mapa, igual ao PDF.
- **Cards de aplicação e "Total do mapa".** Continuam mostrando o insumo, a dose e o total de cada um.
- Ajustar a área de um talhão continua como hoje.

O corretivo não muda na tela.

## Testes

- `tests/drone/test_mapa_pdf_regressao.py`: continua passando, sem mudar a imagem de referência.
- Testes do PDF dos mapas de aplicação: atualizar para a tabela de três colunas (inclusive L + kg, talhão 400 e linha
  `Total`), o título do tipo nos dois tipos, os cards maiores e o mapa de uma cor só.
- Unitários da tela (`node --test tests/app/*.test.js`): talhões do mapa = união; incluir e tirar regravam todos os
  insumos; novo insumo usa os talhões do mapa.
- Demo (`corretivos-demo.js`) e E2E real (`tests/app/teste_corretivos_tela.py`), atualizados para o fluxo novo do
  aéreo. O E2E salva e restaura os dados que alterar.
