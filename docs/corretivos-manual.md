# Corretivos: guia rápido

A ferramenta **Corretivos** do Hub monta o mapa de aplicação de corretivos (calcário, fosfato e blend). Você escolhe a fazenda, marca os talhões, lança as aplicações e baixa um PDF pronto para o operador de campo.

## Onde fica e quem acessa

- No Hub, abra o menu **Ferramentas** e clique em **Corretivos**. A ferramenta não aparece no menu de módulos.
- O administrador libera o acesso na tela de **Usuários**, marcando o módulo **Corretivos**. Quem é admin já tem acesso.
- Sem acesso, a tela mostra: "Sua conta não tem acesso aos Corretivos. Peça ao administrador."

## Conceitos

- **Mapa:** uma fazenda, uma operação (SubSolagem, SuperGrade ou Arado) e uma data. A fazenda pode ter vários mapas. Não há versões: edite o mapa e baixe o PDF de novo.
- **Aplicação:** um produto com dose e O.S., lançado em um ou mais talhões. Um talhão pode receber mais de uma aplicação.
- **Total:** área do talhão × dose, em toneladas. Não fica gravado; é recalculado sempre.

## Criar um mapa

1. Digite o código ou o nome da fazenda na busca e escolha a fazenda na lista.
2. Clique em **Novo mapa** e escolha a operação.
3. O mapa abre com a data de hoje.
4. Para abrir um mapa que já existe, clique em **Abrir mapa** no cartão.

## Marcar talhões

- Clique num talhão para marcar ou desmarcar. Ele ganha contorno verde.
- **Selecionar todos** marca todos os talhões da fazenda.
- **Limpar seleção** desmarca tudo.
- Os talhões marcados aparecem em **Nova aplicação**, com a área de cada um.

## Lançar uma aplicação

1. Marque os talhões no mapa.
2. Em **Tipo**, escolha Calcário, Fosfato ou Blend.
3. Em **Calcário**, escolha Dolomítico ou PH7. Esse campo não aparece em Fosfato.
4. Digite a **dose** em t/ha. No Blend, é a dose do calcário.
5. No Blend, digite também a **dose do gesso** em t/ha.
6. Digite a **O.S.**
7. Clique em **Aplicar aos marcados**. A aplicação é gravada na hora e a seleção é limpa.

Se a mesma aplicação (mesmo produto, dose e O.S.) já existir em algum dos talhões, ela não é gravada de novo nesses talhões. A tela avisa quais são e grava nos demais.

## Talhão com duas aplicações

- O talhão recebe as duas aplicações **meio a meio**, na diagonal, na ordem em que foram lançadas. Com três ou mais, as faixas são iguais.
- O mesmo vale para o PDF.
- Na tabela do PDF, cada aplicação ocupa uma linha.

## Editar a área de um talhão

1. Com o talhão marcado, altere o valor em **Talhão X · área (ha)**.
2. A alteração é salva quando você sai do campo.
3. A nova área vale para **todas** as aplicações daquele talhão neste mapa.
4. No PDF, a área editada aparece com `*` e uma nota.

Se o talhão ainda não tiver aplicação, a área fica guardada para a próxima aplicação.

## Ver, editar e excluir aplicações

Na seção **Aplicações do mapa**:

- Clique numa aplicação para destacar os talhões dela no mapa. Clique de novo para tirar o destaque.
- **Editar** (lápis) muda dose, dose do gesso, O.S. e talhões. Produto e calcário não mudam; para trocar, exclua e lance de novo.
- **Excluir** (lixeira) pede confirmação. Não dá para desfazer.
- Talhão que fica sem nenhuma aplicação sai do mapa.

O bloco **Resumo** mostra o total por produto.

## Baixar o PDF

1. Clique em **Baixar PDF**.
2. Na primeira vez, o botão mostra "Preparando o gerador… (só na primeira vez)". Leva uns 20 segundos. O gerador começa a carregar assim que a página abre, então muitas vezes já está pronto.
3. Depois disso, o PDF sai em poucos segundos.

O PDF tem:

- o mapa, com os talhões pintados pelas aplicações e o número de cada talhão, e a legenda;
- a tabela **Aplicações por talhão**: talhão, área, aplicação, dose, total e O.S.;
- um quadro por produto, com o total em toneladas. O Blend fica num quadro à parte, com a dose de calcário e a de gesso;
- o arquivo se chama `corretivo_<código da fazenda>_<operação>_<data>.pdf`.

## Excluir um mapa

1. Na lista de mapas, clique na lixeira do cartão.
2. Confirme em **Excluir**. Em **Cancelar** nada acontece.
3. A exclusão fica registrada.

## Cores

| Tipo | Cor |
|---|---|
| Calcário Dolomítico | azul |
| Calcário PH7 | verde-água |
| Fosfato | laranja |
| Blend (qualquer calcário) | roxo |
| Sem aplicação | cinza |

Talhão com duas aplicações aparece dividido, metade de cada cor.

## Quando algo dá errado

| Mensagem na tela | O que fazer |
|---|---|
| "Não foi possível preparar o gerador de PDF. Os dados do mapa estão salvos." | Clique em **Tentar de novo**. Nada foi perdido. Se repetir, recarregue a página. |
| "Não foi possível gerar o PDF. Tente de novo." | Clique em **Baixar PDF** de novo. |
| "Talhões que saíram da Base: ..." | O talhão saiu ou mudou de número na Base. Ele continua na tabela do PDF, sem desenho. Avise a Geo. |
| "Marque ao menos um talhão no mapa." | Marque os talhões antes de aplicar. |
| "Dose deve ser maior que zero (t/ha)." / "Informe a dose do gesso (t/ha)." / "Informe a O.S." | Corrija o campo indicado e clique em **Aplicar aos marcados**. |
| "Os talhões ... já têm esta aplicação." | A mesma aplicação já está nesses talhões. Confira; se houver outros talhões, a tela já gravou neles. |
| "Não foi possível aplicar. Tente de novo." / "Não foi possível salvar a área." | Tente de novo. Se repetir, recarregue a página. |
| "Não foi possível abrir o mapa." | Clique em **Tentar de novo**. |
| "Sua conta não tem acesso aos Corretivos. Peça ao administrador." | Peça ao administrador para liberar o módulo Corretivos. |
