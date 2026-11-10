# Editor de geometrias — núcleo e laboratório (design)

Data: 2026-11-09 · Status: aguardando revisão do usuário

## 1. Objetivo

Construir, **isolado dos módulos do Hub**, um núcleo de edição de geometrias com nível de precisão de CAD, e um laboratório local para desenvolvê-lo e aceitá-lo. O núcleo só será integrado aos módulos quando cumprir o **pacote padrão de edição** (seção 3).

Usos futuros que o desenho precisa suportar (fora do escopo desta spec, cada um com spec própria):
- **Drone:** editar e criar obstáculos, infestação e limites (insumos que regeram o projeto) **e** editar direto a área de aplicação gerada.
- **Croqui de experimento** (bloco S9): parcelas por medidas, giradas, com espaçamento só entre parcelas, numeração por criação editável, saída PDF/KML/SHP.
- **Projetos hoje feitos no AutoCAD**, dentro do Hub.
- **Geovoo:** desenhar sobre os ortomosaicos próprios (reduzidos) como fundo do mapa.

Público do laboratório: só o usuário e o Claude. Sem login, sem banco, sem dados de produção.

## 2. Decisões

| Tema | Decisão |
|---|---|
| Abordagem | Núcleo próprio; Terra Draw (MapLibre) só para o gesto no mapa |
| Mapa | MapLibre GL 4.7.1, igual ao Hub |
| Operações geométricas | JSTS (port do JTS) com modelo de precisão fixo de **1 mm** |
| Sistema de trabalho | **SIRGAS 2000 / UTM 23S (EPSG:31983)**; exibição em WGS84 |
| Fonte da verdade | Geometria guardada em UTM 23S no documento; WGS84 só é derivada para desenhar |
| Ângulos | **Azimute** (0° = Norte, sentido horário) em medidas e entrada exata |
| Alteração do documento | Só por **comandos** reversíveis (desfazer/refazer) |
| Extensibilidade | Ferramentas, comandos, snaps e formatos de arquivo são **registráveis** por um contrato fixo; as 21 ferramentas usam o mesmo contrato |
| Fundo do mapa | Trocável desde o início (satélite atual; ortomosaico do Geovoo depois) |
| Onde fica | `editor/` na raiz do hub-geotech (o Pages publica só `app/`, então o laboratório não vai ao ar) |
| Bibliotecas | Versões fixas copiadas em `editor/vendor/` (ESM), usadas pelos testes e pela página; sem npm no dia a dia |
| Testes | `tests/editor/*.test.js` com `node --test`, já rodados pelo CI (`testes.yml`) |

## 3. Pacote padrão de edição (definição de "núcleo pronto")

**Criar**
1. Ponto, linha e polígono desenhados no mapa.
2. Retângulo por medidas: largura × comprimento, ângulo (digitado ou "alinhar à aresta"), ponto de inserção clicado ou digitado, âncora no canto ou no centro.
3. Círculo; buffer a partir de uma feição (distância positiva ou negativa).

**Selecionar e transformar**
4. Selecionar um, vários (com Shift) e por caixa.
5. Mover, girar e redimensionar (com alças e com entrada exata).
6. Copiar, colar, duplicar e **matriz** (linhas × colunas, folga entre bordas em cada direção, segue a rotação da feição, numeração sequencial).

**Editar a forma**
7. Vértices: arrastar, inserir e apagar.
8. Cortar polígono com uma linha (cada pedaço vira feição própria, atributos copiados, números novos).
9. Unir (resultado pode ser multipolígono, com aviso; atributos do primeiro selecionado), recortar A − B (B fica ou some, à escolha), interseção (feição nova).
10. Furos: desenhar dentro do polígono ou usar uma feição existente como furo.

**Precisão**
11. Snap em vértice, aresta, ponto médio, interseção e perpendicular; trava ortogonal e polar (passo configurável) relativas a uma direção base (norte ou uma aresta clicada).
12. Espaçamento: folga fixa entre feições das camadas marcadas.
13. Medidas ao vivo: segmento, comprimento total, azimute e área (ha e m²).
14. Entrada exata pela linha de comando.

**Trabalho**
15. Desfazer e refazer.
16. Camadas: mostrar, ocultar e travar.
17. Atributos por feição: nome, categoria e número editável (inicial por ordem de criação), mais campos livres.
18. Validação, com painel de Problemas e botão Corrigir.

**Entrada e saída**
19. Importar e exportar KML, SHP e GeoJSON.

**CAD**
20. Paralela (offset) de linha ou contorno a X m, com o lado definido pelo mouse.
21. Aparar e estender linhas, usando qualquer aresta visível como limite.

## 4. Arquitetura

```
editor/
  nucleo/            sem DOM, testável no Node
    documento.js     camadas + feições (geometria UTM, atributos, ordem de criação)
    comandos.js      pilha de desfazer/refazer + registro de tipos de comando
    projecao.js      31983 <-> 4326 (proj4)
    geometria.js     JSTS, grade de 1 mm: unir, recortar, interseção, cortar, furo,
                     buffer, paralela, aparar, estender, validar, corrigir
    construcao.js    retângulo por medidas, círculo, matriz
    precisao.js      motor de snap (índice RBush) + travas + leitura da entrada exata
    medidas.js       comprimento, área, azimute (sempre em UTM)
    arquivos.js      registro de formatos + KML, SHP, GeoJSON
    registro.js      registro de ferramentas, comandos, snaps e formatos
  interacao/
    ponte-terradraw.js  traduz gestos do Terra Draw em chamadas ao núcleo
    contexto.js         o "ctx" entregue às ferramentas
  ferramentas/       uma ferramenta por arquivo, todas pelo contrato da seção 5
  lab.html, lab.js, lab.css   página do laboratório
  vendor/            bibliotecas fixadas
  ACEITE.md          roteiro de aceite dos 21 itens
tests/editor/        testes do núcleo e das ferramentas
```

**Regras:**
- **O núcleo é a única fonte da verdade.** O Terra Draw nunca é dono do dado. Durante o gesto ele mostra a forma provisória e consulta o `precisao` para encaixar o ponto. Ao terminar o gesto, a ponte gera um comando no núcleo e o mapa é redesenhado a partir do documento.
- Geometria guardada em UTM evita erro acumulado por idas e voltas de conversão.
- Toda geometria que sai de uma operação passa pela grade de 1 mm, o que evita lascas depois de muitos recortes.

### 4.1 Modelo de dados

- **Documento:** `{ versao, crs: "EPSG:31983", camadas: [...], feicoes: Map<id, feicao>, proximoNumero }`.
- **Camada:** `{ id, nome, visivel, travada, participaEspacamento, estilo }`.
- **Feição:** `{ id, camadaId, geometria /* GeoJSON com coordenadas UTM */, atributos: { nome, categoria, numero, ...livres }, ordem }`.
- O documento é serializável em JSON. Esse formato é usado pelo salvamento automático e, no futuro, pela persistência nos módulos.

### 4.2 Comandos

- Um tipo de comando é registrado com `{ tipo, aplicar(doc, dados) -> inverso }`: cada aplicação devolve os dados do comando inverso. Os `dados` são serializáveis.
- `executar(comando)` aplica o comando, empilha o inverso, limpa o refazer e emite `mudou`.
- Comandos compostos (ex.: matriz, cortar) entram como uma única entrada na pilha.
- Depois de cada comando, as feições alteradas são validadas (seção 6).

## 5. Contrato de extensão

Tudo que é "ferramenta" entra pelo `registro`. **As 21 ferramentas usam esse contrato, sem acesso por dentro.**

**Ferramenta:**
```js
registrarFerramenta({
  id: 'retangulo-medidas',
  nome: 'Retângulo por medidas',
  grupo: 'criar',              // criar | transformar | forma | precisao | trabalho | arquivo | cad
  icone: '...', atalho: 'R',
  exige: { selecao: null },    // ex.: { selecao: { min: 1, tipos: ['Polygon'] } }
  opcoes: [ { id: 'largura', tipo: 'numero', unidade: 'm' }, ... ],
  ativar(ctx) {}, desativar(ctx) {},
  aoPonteiro(ctx, evento) {},  // baixo / move / cima, já com o ponto encaixado pelo snap
  aoTeclado(ctx, tecla) {},
  aoEntrada(ctx, texto) {}     // linha de comando
})
```

**`ctx` entregue à ferramenta** (a única superfície disponível para ela):
- `ctx.doc`: leitura do documento e da seleção.
- `ctx.executar(comando)`: única forma de alterar o documento.
- `ctx.geometria`, `ctx.construcao`, `ctx.medidas`, `ctx.projecao`.
- `ctx.precisao`: encaixar ponto, travas e leitura da entrada exata.
- `ctx.provisorio`: desenhar a forma temporária (camada de pré-visualização).
- `ctx.terradraw(modo)`: usar um modo do Terra Draw para o gesto, quando servir.
- `ctx.avisar(texto)` e `ctx.opcoes`: valores atuais do painel da ferramenta.

**Também registráveis:** tipos de comando (`registrarComando`), modos de snap (`registrarSnap({ id, prioridade, simbolo, candidatos(ponto, indice) })`) e formatos de arquivo (`registrarFormato({ id, extensoes, importar, exportar })`).

**Perfis (integração futura):** cada módulo escolhe quais ferramentas aparecem, as camadas e de onde carregar e salvar. No laboratório, o perfil é "todas as ferramentas, arquivos locais".

**Prova do contrato:** um teste registra uma ferramenta e um snap novos, usa os dois e desfaz, sem alterar nenhum arquivo do núcleo.

## 6. Comportamento das ferramentas de precisão

- **Snap:** tolerância de cerca de 10 px de tela, convertida em metros conforme o zoom. Prioridade: vértice > interseção > médio > perpendicular > aresta > espaçamento. Cada tipo tem um marcador no cursor (□ vértice, △ médio, ✕ interseção, ⊾ perpendicular). Os modos ligam e desligam individualmente, e há uma tecla para desligar todos. Encaixa em camadas visíveis, inclusive travadas; nunca em camadas ocultas. As consultas usam índice RBush.
- **Travas:** ortogonal (0/90°) e polar (passo de 15°, 30° ou 45°, configurável), relativas à direção base. A direção base é o norte ou uma aresta clicada.
- **Entrada exata:** `x,y` (UTM absoluto), `@dx,dy` (relativo), `@dist<azimute` e, digitando só um número, essa distância na direção do mouse ou da trava. Vale também ao mover (`@10,0`) e girar (`30`).
- **Medidas ao vivo:** junto ao cursor, sempre calculadas em UTM 23S.
- **Espaçamento:** ao mover ou criar uma feição numa camada que participa do espaçamento, se a aresta mais próxima de outra feição dessas camadas estiver quase paralela (até ~5°), a feição se desloca para a folga exata e gira para ficar paralela. Não vale para camadas fora da marcação (ex.: limite do talhão).

## 7. Validação e erros

- A validade é checada com o `IsValidOp` do JSTS depois de cada comando, para as feições alteradas.
- **Operações** (unir, recortar, interseção, cortar, furo, buffer, paralela) **recusam** entrada inválida com uma mensagem que diz qual feição e onde ("o polígono 12 se cruza no vértice 4"). O documento não muda.
- **Edição de vértice** é permitida mesmo deixando a geometria inválida. A feição fica vermelha e entra no painel **Problemas**, que leva até o local e oferece **Corrigir** (GeometryFixer do JSTS, como um comando que pode ser desfeito).
- **Exportar** avisa e lista as feições inválidas antes de gerar o arquivo.
- Falha ao ler um arquivo importado mostra o motivo e não altera o documento.

## 8. Arquivos

- **Importar:** KML (togeojson), SHP em .zip (shpjs) e GeoJSON. Cada arquivo vira uma camada nova, com os atributos preservados. O sistema de coordenadas vem do `.prj`; sem ele, é deduzido pela faixa dos números (graus → 4326; metros → 31983), sempre com aviso. Z e M são descartados. Feições com várias partes são mantidas.
- **Exportar:** por camada ou tudo.
  - **SHP** (shp-write) em 4326 ou 31983, com `.prj`, num .zip com um arquivo por tipo de geometria. Avisa sobre nomes de campo com mais de 10 caracteres.
  - **KML** (tokml) com 8 casas decimais.
  - **GeoJSON** em 4326.
- **Conteúdo importado é dado, não código:** nomes e atributos nunca entram no HTML sem escape (KML pode trazer HTML embutido).
- **Salvamento automático:** o documento serializado vai para o armazenamento do navegador a cada comando e é restaurado ao abrir, com leitura e gravação protegidas contra falha. Salvar de verdade = exportar.

## 9. Laboratório (`editor/lab.html`)

- Mapa MapLibre com **fundo trocável**: satélite do Hub agora, ortomosaico do Geovoo depois (fonte raster XYZ).
- Barra de ferramentas montada a partir do registro, agrupada por `grupo`.
- Painel de camadas, painel de atributos da seleção, painel de opções da ferramenta ativa e painel Problemas.
- Linha de comando para a entrada exata e barra de medidas.
- Abre localmente, servido por um servidor estático simples (ex.: `python -m http.server`) por causa dos módulos ES.

## 10. Testes e aceite

**Automáticos** (`tests/editor/*.test.js`, no CI). Afirmam resultados numéricos, com tolerância de 1 mm:
- Retângulo 10 × 5 m no azimute 30° → lados de 10,000 e 5,000 m, área de 50,000 m².
- Matriz 3 × 4 com folga de 1 m → todas as folgas entre bordas = 1,000 m.
- Espaçamento: feição a 1,3 m com folga de 1 m → termina a 1,000 m e paralela.
- Entrada exata: `@25<90` a partir de (500000, 7500000) → (500025, 7500000).
- Ida e volta: importar → exportar → importar idêntico, nos 3 formatos e nos 2 sistemas de coordenadas.
- Para cada tipo de comando: aplicar e desfazer devolve o documento idêntico.
- Operações com casos difíceis: arestas coincidentes, furo encostado na borda, corte passando por vértice.
- Prova do contrato de extensão (seção 5).

**Aceite** (`editor/ACEITE.md`): os 21 itens, cada um com passos e resultado esperado. O Claude roda o que der pelo navegador automatizado e o usuário faz o aceite final. **Núcleo pronto = os 21 itens aprovados pelo usuário.**

**Desempenho:** cerca de 2.000 feições com o mapa fluido e o snap abaixo de ~16 ms por movimento do mouse.

## 11. Etapas de entrega

Cada etapa termina usável no laboratório e com seus testes passando.
1. **Base:** registro e contrato, documento, comandos e desfazer (15), projeção, camadas (16), atributos (17), ponto, linha e polígono (1), importar e exportar (19), página com fundo trocável.
2. **Transformar e medir:** seleção (4), mover, girar e escalar (5), vértices (7), medidas (13), retângulo por medidas e círculo (2, 3), copiar, colar e duplicar (6).
3. **Precisão:** snap com modos e marcadores (11), travas, entrada exata (14), espaçamento (12), matriz (6).
4. **Operações:** unir, recortar e interseção (9), cortar (8), furo (10), buffer (3), paralela (20), aparar e estender (21), validação com painel Problemas (18).

## 12. Pilares

- **Segurança:** laboratório local, sem login nem dados reais; conteúdo importado sempre escapado; bibliotecas fixadas em `vendor/`.
- **Confiabilidade:** toda alteração é um comando reversível; salvamento automático; operações não alteram o documento quando falham.
- **Performance:** índice espacial para o snap; meta de 2.000 feições.
- **Escalabilidade:** não se aplica nesta fase (sem servidor).
- **Manutenção:** núcleo sem DOM e testado no CI; uma ferramenta por arquivo; contrato de extensão único.
- **Usuário:** aceite pelo usuário nos 21 itens.

## 13. Fora do escopo

- Integração com Drone, croqui, AutoCAD ou Geovoo (cada uma terá spec própria, usando perfis).
- Persistência no banco, permissões e edição por várias pessoas ao mesmo tempo.
- Geração de PDF.
- Leitura de DWG/DXF.

## 14. Melhorias anotadas para depois

Ficam para a fase em que os projetos de preparo e plantio forem feitos dentro do Hub (cada uma com spec própria):
- **Importar DXF/DWG:** entra como um formato novo pelo `registrarFormato`, sem mexer no núcleo.
- **Ferramentas específicas de projeto de preparo e plantio:** entram como ferramentas novas pelo contrato da seção 5.
- **Versionamento parecido com o Git** (commits com mensagem, histórico, enviar/publicar, comparar versões, voltar atrás). A base já existe nesta spec: os comandos são serializáveis e reversíveis (seção 4.2), então um "commit" pode ser um grupo de comandos com mensagem e autor, e o histórico é a sequência deles. Por isso os comandos precisam continuar serializáveis e determinísticos.
