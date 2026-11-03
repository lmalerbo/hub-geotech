# Apresentação semanal: guia rápido

A ferramenta **Apresentação semanal** monta os 6 slides de Indicadores e Entregas da Geotecnologia:

1. Divisória
2. Colheita
3. Sistematização
4. Plantio
5. Voos com Drone
6. Drone de Aplicação

No fim, você baixa um arquivo PPTX. O notebook do Leo não é mais preciso para isso.

## Onde fica e quem acessa

- No Hub, abra o menu **Ferramentas** e clique no cartão **Apresentação semanal**. O cartão aparece para todos; nome, descrição, ícone e cor ficam em **Configurações → Ferramentas**, como as outras ferramentas.
- O administrador libera o acesso na tela **Usuários**, na aba **Ferramentas**, ligando o interruptor **Apresentação semanal**.
- Quem é admin já tem acesso.
- Sem acesso, a tela mostra: "Sua conta não tem acesso à Apresentação semanal. Peça ao administrador."

## Fluxo semanal

1. **Parâmetros.** Ao abrir, a tela já preenche a **Semana** e a data **Dados até**.
   - A semana é a quinta-feira mais recente. O número N é a quinta-feira do mês (a 1ª, 2ª, 3ª, 4ª ou 5ª quinta). O mês é o mês da quinta.
   - Os dados vão até o dia anterior à quinta. Exemplo: 29/10/2026 é a 5ª quinta de outubro, então a semana é **S5M10** e os dados vão até 28/10/2026.
   - Se precisar mudar, use o formato S5M10 (semana do mês e mês, sem zero à esquerda).
2. Clique em **Buscar dados**. A tela busca três fontes:
   - o Hub Geotech;
   - os projetos de drone;
   - os voos do GeoMap.
   A primeira chamada de voos do dia leva cerca de 2 minutos. A tela espera até 3 minutos. Enquanto espera, a linha mostra o tempo passando.
3. Escreva os textos de cada slide. Escolha o slide na lista e preencha:
   - **Subtítulo**;
   - **Destaque**;
   - **Notas do apresentador** (vão para as notas do PowerPoint, não aparecem no slide).

   O rascunho é salvo sozinho, 2 segundos depois de você parar de digitar. A linha **Rascunho salvo às** confirma. Para voltar o subtítulo ao texto padrão, clique em **Voltar ao texto padrão**.

   Os rascunhos são da semana, não de cada pessoa. Se dois editores mexerem na mesma semana, um não apaga o texto do outro: cada campo é salvo separado. Na tela de Parâmetros, o aviso **Rascunho de ...** mostra quem editou por último.
4. Clique em **Baixar PPTX**. O arquivo se chama, por exemplo, `s5m10 - Apresentacao Geotecnologia - Indicadores e Entregas.pptx`.
   - Cada slide vira uma imagem.
   - As notas do apresentador vão para as notas do PowerPoint.

Os números dos slides não são editáveis. Eles vêm do Hub e das outras fontes.

## Metas

Na tela de Parâmetros, a área **Metas** tem seis campos:

- Meta de ervas daninhas (ha)
- Meta fornecedor (ha)
- Meta de ha por dia
- Drone pendente (ha)
- Safra atual
- Início da safra

Depois de mudar, clique em **Salvar metas**. As metas valem para as próximas semanas. Embaixo do botão aparece quem alterou por último e quando.

## Quando algo dá errado

| Mensagem ou sinal na tela | O que fazer |
|---|---|
| Slide de Voos com "Dados indisponíveis" e a mensagem "A API do GeoMap não respondeu." | Clique em **Tentar de novo** no próprio slide. |
| **Baixar PPTX** desligado enquanto os voos não voltam. A linha **Falta:** mostra o que ainda não carregou. | Espere os voos ou clique em **Tentar de novo**. Os outros slides continuam editáveis. |
| Cartão **Drone de Aplicação** com a lista de projetos "sem área ou safra". | Não bloqueia o PPTX. Esses projetos ficam em "Anteriores / sem safra" e não entram na soma do realizado. |
| "Não foi possível montar os slides: ... Avise o Leo." | Avise o Leo. Normalmente é uma etapa de preparo nova que o cálculo ainda não conhece. |
| "Não foi possível salvar o rascunho" (em vermelho, ao lado de **Rascunho salvo às**) | Tente de novo: digite no campo de novo para salvar. |
| "Não foi possível gerar o PPTX. Tente de novo." | Clique em **Baixar PPTX** de novo. |

## Para o administrador

### Carga única de área e safra dos projetos de drone antigos

Os projetos de drone vindos do legado não têm área nem safra no Hub. Esta carga preenche esses dados uma vez. Os projetos feitos no Hub não precisam dela.

Rode da raiz do repositório:

1. Sem argumento, o comando só mostra o que faria, sem gravar:

   ```bash
   python -m drone.carga_area_safra
   ```

2. Confira a lista. Depois rode com `--aplicar` para gravar em `hub.projeto_revisoes`:

   ```bash
   python -m drone.carga_area_safra --aplicar
   ```

Ao final, o comando mostra quantos foram gravados e quantos ficaram sem dado. Os que falham (ZIP corrompido ou fora do ar) aparecem na lista e a carga segue com os demais.
