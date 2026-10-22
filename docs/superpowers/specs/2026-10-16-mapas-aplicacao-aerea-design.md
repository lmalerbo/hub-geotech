# Mapas de aplicação: tipo Aplicação aérea — design

Data: 16/10/2026. Pedido do Leo (conversa de 16/10). Base: ferramenta Corretivos (`app/corretivos.html`,
spec `2026-10-09-corretivos-design.md`), já no ar com o layout novo (main c9893cd).

## O que muda para quem usa

1. A ferramenta passa a se chamar **Mapas de aplicação**. Tipos de mapa: SubSolagem, SuperGrade, Arado
   (corretivos, como hoje) e o novo **Aplicação aérea**. O endereço novo é `aplicacao.html`;
   `corretivos.html` continua funcionando e leva para o novo (links salvos e o cartão do Hub não quebram).
2. No mapa aéreo, cada aplicação é: **insumo** (lista suspensa), **dose por hectare** na unidade do insumo
   (L ou kg), **O.S.** e os **talhões** marcados no mapa. Um mapa pode ter vários insumos; cada insumo tem
   uma cor; talhão com mais de um insumo aparece dividido em faixas, igual ao corretivo.
3. **Margem de 5% (talhão 400):** a tabela do PDF ganha, no fim, a linha do talhão **400** só com a
   ÁREA = 5% da soma das áreas dos talhões do mapa (sem insumo, dose ou total). A linha Total soma os
   talhões + o 400. O 400 não aparece no mapa.
4. **Total de cada insumo** (carimbo do PDF e resumo da tela) = dose × área dos talhões daquele insumo × 1,05.
   (Regra do Leo: "o total da aplicação é a área com a margem × a dose". Quando todos os insumos vão em todos
   os talhões, é exatamente área total do mapa × dose.)
5. **Cadastro de insumos:** botão "Insumos" na tela abre uma janela com a lista (nome, unidade, dose
   sugerida, código) e permite adicionar, editar e remover. Remover tira o insumo da lista suspensa, mas os
   mapas antigos continuam mostrando o nome e a unidade com que foram feitos. Começa com os 34 insumos do
   arquivo "INSUMOS AVIÃO 1" (código, nome e unidade de lá; dose sugerida = a dose média mais comum no arquivo).
   Ao escolher um insumo, a dose vem preenchida com a sugerida; o usuário pode mudar.

## Decisões técnicas

- **Banco** (migração `20261017090000_mapas_aplicacao.sql`): as tabelas `hub.corretivo_*` continuam com o
  mesmo nome (trocar nome de tabela só traria risco). `operacao` aceita `aerea`; `tipo` da aplicação aceita
  `insumo`, com `insumo_id` (referência) e **cópia** de `insumo_nome` e `insumo_unidade` no momento em que a
  aplicação é gravada. Mapa aéreo só aceita aplicação de insumo; mapa de corretivo só aceita calcário/fosfato/
  blend (conferido em `corretivo_aplicar`). A checagem de "aplicação idêntica no mesmo talhão" passa a
  considerar o insumo. Tabela nova `hub.insumos (id, codigo, nome único, unidade L|KG, dose_sugerida, ativo)`
  com RLS: quem usa a ferramenta lê e mantém o cadastro. Remover = `ativo = false`. O módulo `corretivos`
  continua com o mesmo id; só o nome exibido vira "Mapas de aplicação".
- **Dose com 3 casas** (há doses de 0,008 kg/ha). Totais com 2 casas. Unidades exibidas como `L` e `kg`.
- **Cores dos insumos:** paleta fixa de 10 cores, atribuída na ordem em que os insumos aparecem no mapa
  (ordem das aplicações); a tela e o PDF usam a mesma regra. Acima de 10 insumos a paleta repete.
- **Nomes dos insumos** no PDF e na tela em "Primeira Letra Maiúscula" (cabem melhor na tabela de letra grande);
  no cadastro ficam como vieram do sistema.
- **PDF:** o mesmo layout novo (retrato/paisagem). No aéreo: selo "APLICAÇÃO AÉREA", subtítulo
  "MAPA DE APLICAÇÃO · AÉREA · O.S. …", colunas TALHÃO | ÁREA (ha) | INSUMO | DOSE/ha | TOTAL | O.S., com a
  unidade junto do número ("0,150 L", "15,75 L"); a coluna do insumo reduz a letra (até 11 pt) se o nome não
  couber; quadros de totais com a unidade do insumo; célula de área do carimbo "ÁREA · N TALHÕES + 5%".
  Nome do arquivo: `aplicacao_aerea_<cod>_<data>.pdf`. Mapas de corretivo não mudam.

## Fora do escopo

Dose sugerida por fazenda (o arquivo tem dose média por fazenda e centro de custo); integração automática
com o sistema de insumos; renomear tabelas/funções do banco.

## Riscos

- O cadastro de insumos é editável por qualquer usuário da ferramenta (como pedido); a cópia de nome e unidade
  na aplicação impede que uma edição mude mapas antigos.
- A migração precisa ser aplicada no SQL Editor **antes** de publicar a tela nova (a tela nova lê `hub.insumos`).
