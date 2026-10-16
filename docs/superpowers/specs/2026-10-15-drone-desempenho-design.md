# Drone: geração sem depender da rede + conferência do envio

**Data:** 15/10/2026 · **Origem:** medição do fluxo em 15/10 (conversa com o Leo).

## 1. Por quê

Com o servidor saudável, o fluxo já é rápido: o envio fica ok em 4 a 20 s e a prévia sai em ~20 s (15 s de fila + 6 s de processamento). O tempo perdido veio de outro lugar:

- **Infraestrutura:**
  - os obstáculos da 10613 esperaram 2h17 com o servidor parado;
  - uma prévia da 10678 falhou porque o servidor estava sem acesso à pasta `lnxfs3`;
  - durante 5 dias ninguém percebeu que o agente e a rotina diária estavam parados.
- **Retrabalho:**
  - das 16 prévias, 14 foram descartadas;
  - o mesmo `Daninhas.shp` foi enviado 5 vezes;
  - a Catação da 10678 saiu 18 vezes maior que a infestação, por um defeito já corrigido, e ninguém tinha como perceber antes de abrir o PDF.

## 2. O que muda

### 2.1 Gerar sem ler a pasta de rede
- **A rotina diária grava mais coisas** em `hub.talhao_geom`, além do que já grava:
  - a geometria **sem simplificar**, em SIRGAS 2000 / UTM 23S (`geom_proj`), que é a usada no projeto;
  - a `area_prod` da Base;
  - o nome do arquivo da Base do dia, em `hub.drone_parametros` (`base_talhoes_arquivo`).
- **O agente lê os talhões do banco** (`hub.drone_talhoes_fazenda`). Só lê a pasta de rede se a fazenda não estiver no banco; nesse caso a prévia ganha um alerta dizendo isso.
- **A geometria do projeto continua exata:** a versão simplificada (0,5 m, WGS84) segue só para o mapa.

### 2.2 Saber quando o servidor parou
- **Função `hub.drone_saude()`:** devolve o último sinal de vida do agente e a última rotina diária com sucesso.
- **Tela Drone:** faixa de aviso "O servidor Geo não responde há X min — envios e prévias ficam parados até ele voltar" quando o agente está sem sinal há mais de 5 min.
- **Sininho:**
  - agente parado há mais de 5 min: para quem tem o módulo Drone e para os admins;
  - rotina diária sem sucesso há mais de 26 h: para os admins.
  - O aviso é calculado na hora, no app, sem gravar nada.

### 2.3 Conferir o envio antes de gerar
- **Ao processar um envio de infestação,** o agente grava um resumo em `hub.drone_envios.resumo`:
  - número de **manchas** (partes separadas, não registros);
  - **área infestada**;
  - **por talhão:** manchas e hectares;
  - hectares **fora dos talhões**.
- **Envio repetido:** o agente guarda uma assinatura do conteúdo (`conteudo_hash`, sha256 dos arquivos). Se for igual à do envio anterior da mesma fazenda e do mesmo tipo, o resumo marca "mesmo arquivo do envio #N". O envio é aceito do mesmo jeito.
- **Cartão da Catação:**
  - mostra o resumo do último envio, no formato "50 manchas · 0,99 ha · talhões 2 (0,21) e 3 (0,78) · nada fora";
  - ganha a chave **mostrar manchas** no mapa (`hub.drone_infestacao_mapa`).

### 2.4 Alerta de bom senso na prévia da Catação
- Se a aplicação for mais de **5 vezes** a área infestada, a prévia ganha o alerta: "Aplicação X vezes a área infestada — confira as manchas no mapa antes de publicar".
- O limite fica no parâmetro `alerta_razao_catacao` (padrão 5).

## 3. Fora desta entrega
- prévia automática ao enviar a infestação;
- várias fazendas de uma vez;
- consulta da fila a cada 5 s;
- Parte 3 (Catação a partir do Drone MGMT).
