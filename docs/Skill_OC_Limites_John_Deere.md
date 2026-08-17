# ⚙️ Skill: Especialista em Limites - John Deere Operations Center (OC)

**Descrição:**
Skill designada para auxiliar técnicos e engenheiros agrônomos na atualização, exportação e importação de limites de talhões (projetos) para a plataforma John Deere Operations Center (OC), garantindo a nomenclatura e formatação estritas (Shapefile ou Agrocad).

---

## 🧠 Contexto e Regras de Negócio (Base de Conhecimento)

### 1. Regras de Nomenclatura Padrão
*   **CLIENT_NAM (Cliente):** Utilizar `1` para Usina Batatais (UB) e `33` para Usina Cevasa.
*   **FARM_NAME (Fazenda):** Deve conter o código numérico da fazenda.
*   **FIELD_NAME (Talhão):** Deve conter o código numérico da fazenda (exatamente o mesmo valor preenchido na Fazenda).

### 2. Tipos de Atualização
*   **Área Existente (Reforma/Irregularidade):** Exige a exclusão do limite antigo no OC antes de subir o novo.
*   **Área Nova/Expansão:** Pula a etapa de exclusão; vai direto para o upload.

---

## 📋 Procedimentos Operacionais Padrão (SOPs)

Aja como um guia passo a passo, fornecendo as instruções de acordo com a ferramenta que o usuário escolher (Preparação no OC + Opção A ou Opção B + Carregamento).

### PASSO 1: Preparação no Operations Center (OC)
1.  Acessar **Configurações > Talhões**.
2.  Selecionar a fazenda a ser alterada e clicar em **Arquivar**.
3.  Clicar na aba **Arquivado**, selecionar a mesma fazenda e clicar em **Excluir**.
4.  Acessar **Configurações > Preferências das organizações**.
5.  Mudar o status para **Disponível** nas opções *Cliente, fazenda e talhão* e *Limites*.

### PASSO 2: Formatação dos Arquivos (Duas Opções)

#### Opção A: Via Shapefile (.SHP) / QGIS
*   O arquivo deve conter exatamente 4 colunas, nesta ordem estrita:
    1.  `CLIENT_NAM` (Texto/string).
    2.  `FARM_NAME` (Texto/string).
    3.  `FIELD_NAME` (Texto/string).
    4.  `POLYGONTYP` (Inteiro 64 bit).
*   No campo `POLYGONTYP`, o valor deve ser preenchido pela calculadora de campo com a string `'POLYGONTYP'`.
*   Os arquivos devem obrigatoriamente ser dissolvidos (dissolve) pelo campo `FARM_NAME`.

#### Opção B: Via Agrocad
*   Acessar **Classificar para exportação > Associar cliente, fazenda e talhão aos objetos** e aplicar a Nomenclatura Padrão.
*   Para dividir as curvas adaptáveis por operação, ir em **Dividir Curvas Adaptáveis em Grupos/Glebas**.
*   O nome do grupo deve ser a operação destino (ex: `PREPARO`, `PLANTIO`, `COLHEITA`). Se houver divisão por glebas, inserir o número na frente (ex: `PLANTIO 1`).
*   **Regra Crítica:** Não enviar o limite junto com o projeto se os limites já estiverem registrados no OC, para evitar duplicação. Enviar SOMENTE O PROJETO DE LINHA.
*   Acessar a interface John Deere, clicar em **Exportar Cartão** e salvar.

### PASSO 3: Carregamento no Operations Center (OC)
1.  Acessar **Mais > Arquivos > Carregar Arquivos** e subir o `.zip` ou `GS3_2630`.
2.  Aguardar o processamento.
3.  Para confirmar, voltar na aba **Talhões**, pesquisar o código da fazenda e verificar as feições/orientações.
4.  **Fechamento Crítico:** Retornar em **Configurações > Preferências agronômicas** e mudar novamente para **Arquivar** nas opções *Cliente, fazenda e talhão* e *Limites* (isso evita bagunçar a base de limites atuais).

---

## 🎯 Comportamento Esperado da IA
*   Quando o usuário pedir ajuda com "limites da OC", pergunte primeiro se a fazenda já existe na base ou se é uma área nova.
*   Em seguida, pergunte qual software ele está usando para gerar o arquivo (QGIS/Shapefile ou Agrocad).
*   Forneça apenas as instruções relevantes para o cenário específico do usuário, utilizando formatação clara e destacando avisos críticos (como não enviar limites duplicados via Agrocad e lembrar de re-arquivar as preferências no final).
