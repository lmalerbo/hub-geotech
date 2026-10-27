# Mapas de aplicação: guia rápido

A ferramenta **Mapas de aplicação** do Hub (antes chamada Corretivos) monta dois tipos de mapa:

- **Corretivo** (SubSolagem, SuperGrade ou Arado): calcário, fosfato e blend, em t/ha;
- **Aplicação aérea**: insumos do cadastro (inseticidas, fungicidas, fertilizantes etc.), em L/ha ou kg/ha.

Você escolhe a fazenda, marca os talhões, lança as aplicações e baixa um PDF pronto para o operador de campo.
O endereço antigo (`corretivos.html`) continua funcionando e leva para o novo.
## Onde fica e quem acessa

- No Hub, abra o menu **Ferramentas** e clique em **Mapas de aplicação**. A ferramenta não aparece no menu de módulos.
- O administrador libera o acesso na tela de **Usuários**, marcando o módulo **Mapas de aplicação**. Quem é admin já tem acesso.
- Sem acesso, a tela mostra: "Sua conta não tem acesso aos Mapas de aplicação. Peça ao administrador."
## Conceitos

- **Mapa:** uma fazenda, uma operação (SubSolagem, SuperGrade, Arado ou Aplicação aérea) e uma data. A fazenda pode ter vários mapas. Não há versões: edite o mapa e baixe o PDF de novo.
- **Aplicação:** um produto com dose e O.S., lançado em um ou mais talhões. Um talhão pode receber mais de uma aplicação.
- **Total:** área do talhão × dose (toneladas no corretivo; L ou kg no aéreo). Não fica gravado; é recalculado sempre.
## Criar um mapa

1. Digite o código ou o nome da fazenda na busca e escolha a fazenda na lista.
2. Clique em **Novo mapa** e escolha **Corretivo** ou **Aplicação aérea**.
3. No corretivo, escolha a operação: SubSolagem, SuperGrade ou Arado. O botão de criar diz qual mapa vai ser criado.
4. O mapa abre com a data de hoje.

Os mapas da fazenda aparecem em linhas na lista. Para abrir um, clique na linha. Embaixo da busca, **Abertos por último** leva direto aos 3 últimos mapas abertos neste computador.

## Marcar talhões

O mapa ocupa a tela, e o botão **Baixar PDF** fica no alto, à direita.

- Passe o mouse num talhão para ver a área e o que já foi aplicado nele.
- Clique num talhão para marcar ou desmarcar. Ele ganha contorno verde.
- A barra embaixo do mapa mostra quantos talhões estão marcados e a soma em hectares. Nela, **Selecionar todos** marca todos os talhões da fazenda e **Limpar** desmarca tudo.
- Com talhões marcados, a coluna da direita abre **Nova aplicação**, com a área de cada um.

## Lançar uma aplicação (corretivo)

1. Marque os talhões no mapa.
2. Em **Tipo**, escolha Calcário, Fosfato ou Blend.
3. Em **Calcário**, escolha Dolomítico ou PH7. Esse campo não aparece em Fosfato.
4. Digite a **dose** em t/ha. No Blend, é a dose do calcário.
5. No Blend, digite também a **dose do gesso** em t/ha.
6. Digite a **O.S.**
7. Clique em **Aplicar aos marcados**. A aplicação é gravada na hora e a seleção é limpa.

Se a mesma aplicação (mesmo produto, dose e O.S.) já existir em algum dos talhões, ela não é gravada de novo nesses talhões. A tela avisa quais são e grava nos demais.
## Lançar uma aplicação (aplicação aérea)

1. Marque os talhões no mapa.
2. Em **Insumo**, escolha o produto. A unidade aparece ao lado do nome (L ou kg).
3. A **dose** vem preenchida com a dose sugerida do insumo. Confira e mude se precisar. Aceita até 3 casas (ex.: 0,008 kg/ha).
4. Digite a **O.S.** e clique em **Aplicar aos marcados**.

Lance um insumo por vez. A mesma calda com 5 produtos são 5 aplicações nos mesmos talhões.

### Margem de 5% (talhão 400)

- Na tabela do PDF aparece no fim a linha do **talhão 400**, só com a área: 5% da soma das áreas dos talhões do mapa.
- A linha **Total** soma os talhões + o 400. O carimbo mostra "ÁREA · N TALHÕES + 5%".
- O **total de cada insumo** (quadros do PDF e Resumo da tela) já inclui a margem: dose × área dos talhões daquele insumo × 1,05.
- O talhão 400 não aparece no mapa.

### Cadastro de insumos

Clique em **Insumos**, ao lado da lista de insumos:

- **Adicionar:** nome, unidade (L ou KG), dose sugerida (opcional) e código do sistema (opcional).
- **Editar:** muda nome, unidade, dose sugerida ou código. Mapas já feitos continuam com o nome e a unidade de quando foram lançados.
- **Remover:** tira o insumo da lista. Mapas já feitos continuam com ele.

O cadastro começou com os 34 insumos do arquivo "INSUMOS AVIÃO" (16/10/2026).
## Talhão com duas aplicações

- O talhão recebe as duas aplicações **meio a meio**, na diagonal, na ordem em que foram lançadas. Com três ou mais, as faixas são iguais.
- O mesmo vale para o PDF.
- Na tabela do PDF, cada aplicação ocupa uma linha.
## Editar a área de um talhão

1. Com o talhão marcado, use **Ajustar a área de algum talhão** e altere a área dele. Fora dali, a área do talhão não muda.
2. A alteração é salva quando você sai do campo.
3. A nova área vale para **todas** as aplicações daquele talhão neste mapa.
4. No PDF, a área editada aparece com `*` e uma nota.

Se o talhão ainda não tiver aplicação, a área fica guardada para a próxima aplicação.

## Ver, editar e excluir aplicações

A lista **Aplicações do mapa** é a legenda das cores:

- Clique num cartão para destacar os talhões dela no mapa. Clique de novo para tirar o destaque.
- Use o **⋯** do cartão para **Editar** (dose, dose do gesso, O.S. e talhões) ou **Excluir**. Produto e calcário não mudam; para trocar, exclua e lance de novo.
- **Excluir** pede confirmação. Não dá para desfazer.
- Talhão que fica sem nenhuma aplicação sai do mapa.

O bloco **Resumo** mostra o total por produto. O total do mapa fica sempre no pé da coluna.

## Baixar o PDF

1. Clique em **Baixar PDF**, no alto à direita da tela do mapa.
2. Na primeira vez, o botão mostra "Preparando o gerador… (só na primeira vez)". Leva uns 20 segundos. O gerador começa a carregar assim que a página abre, então muitas vezes já está pronto.
3. Depois disso, o PDF sai em poucos segundos.

O PDF tem:

- o mapa, com os talhões pintados pelas aplicações e o número de cada talhão, e a legenda;
- a tabela **Aplicações por talhão**: talhão, área, aplicação, dose, total e O.S.;
- um quadro por produto, com o total em toneladas. O Blend fica num quadro à parte, com a dose de calcário e a de gesso;
- no aéreo: a coluna **Insumo**, dose e total com a unidade de cada insumo, a linha do talhão 400 e um quadro por insumo;
- folha em pé quando a fazenda é mais alta que larga (tabela abaixo do mapa); folha deitada quando é mais larga (mapa e carimbo
  na primeira folha, tabela a partir da segunda). A letra da tabela é grande, para leitura no campo;
- o arquivo se chama `corretivo_<código da fazenda>_<operação>_<data>.pdf`, ou `aplicacao_aerea_<código>_<data>.pdf` no aéreo.


## Excluir um mapa

1. Na lista de mapas, clique no **⋯** da linha do mapa e escolha **Excluir mapa**.
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

No aéreo, cada insumo ganha uma cor na ordem em que foi lançado no mapa (azul, laranja, verde-água, roxo, vermelho…).

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
| "Escolha o insumo." | No aéreo, escolha o insumo antes de aplicar. |
| "Já existe um insumo com esse nome." | O insumo já está no cadastro. Procure na lista. |
| "Sua conta não tem acesso aos Mapas de aplicação. Peça ao administrador." | Peça ao administrador para liberar o módulo Mapas de aplicação. |
