# Drone S5 — Janela de obstáculos (plano em passos)

> **Para quem executa:** detalhamento da seção S5 de [2026-10-27-drone-telas-redesenho.md](2026-10-27-drone-telas-redesenho.md). Branch `drone-s5` (worktree `../hub-geotech-drone-s5`), criado a partir da `main` (9b9fea4). Execução com a skill `delegar`, seguindo `test-driven-development`. Marque as caixas conforme avança.

**Objetivo:** trocar o envio de obstáculos de hoje (um `prompt` pedindo a classe + seletor de arquivos) pela janela da maquete: cartões com a situação das três classes, área de arrastar que aceita shapes soltos e `.zip`, lista de camadas agrupadas pelo nome-base com a classe de cada uma, e um único envio em que cada arquivo sobe renomeado `<classe>m_<nome>`. **O agente Python não muda.**

**Spec:** §3.4 de [2026-10-27-drone-telas-redesenho-design.md](../specs/2026-10-27-drone-telas-redesenho-design.md) · Maquete, tela 3 (`Obstaculos`): https://claude.ai/artifact/HGJ6zku4ABshgCFSzmDJup

**Arquivos:**
- Modificar: `app/drone-dados.js` (funções puras novas; sai `drClasseEscolhida`), `app/drone-fazenda.js` (botão Obstáculos, `n_feicoes` na busca, `DR.abrirObst`, camada ligada ao fim do envio; sai o ramo `obstaculos` de `drEnviar`), `app/drone.css` (classes `dro-*`), `app/index.html` (carrega `drone-obstaculos.js` depois de `drone-fazenda.js`), `app/drone-fazenda-demo.html` (`&jan=1`)
- Criar: `app/drone-obstaculos.js`, `tests/app/fixtures/gerar_obst.py` e os shapes que ele gera em `tests/app/fixtures/obst/`
- Testes: `tests/app/drone_puro.test.js`, `tests/drone/test_insumos.py`, `tests/app/teste_drone_tela.py`

**Decisões tomadas neste detalhamento (conferir):**
1. **O `.prj` é obrigatório, não só aviso.** A spec diz que a falta do `.prj` vira aviso, mas o agente recusa o shape sem `.prj` (`drone/insumos.py::ler_shapefile`: "veio sem o .prj") e, como o lote é tudo ou nada, uma camada sem `.prj` derrubaria o envio inteiro. Por isso, a falta de `.shp`, `.shx`, `.dbf` ou `.prj` bloqueia o envio. Só o `.cpg` é opcional.
2. **Conflito de nome:** duas camadas com o mesmo nome-base (comparado depois de `drNomeSeguro` e sem diferenciar maiúsculas, porque o agente roda no Windows) vindas de origens diferentes (dois `.zip`, ou um `.zip` e um arquivo solto), ou a mesma extensão repetida, formam **uma linha em conflito** que bloqueia o envio, com o texto "mesmo nome em a.zip e b.zip: renomeie um deles". O mesmo arquivo solto duas vezes (mesmo nome, origem e tamanho) não é conflito: o repetido é descartado.
3. **Cada linha tem um botão × para tirar a camada.** A maquete não tem, mas sem ele uma camada incompleta obrigaria a fechar e recomeçar.
4. **Arquivos que não são de shape** (`.sbn`, `.xml`, `.qmd`, `__MACOSX/`, `._*`) são ignorados, com a linha "N arquivos ignorados" embaixo da lista. `.zip` dentro de `.zip` também é ignorado.
5. **Nome enviado:** `<classe>m_<nome-base seguro>.<extensão em minúsculas>`, por exemplo `Linhas CEMIG.SHP` com 25 → `25m_Linhas_CEMIG.shp`. A extensão vai em minúsculas porque o agente acha o `.prj` com `with_suffix('.prj')`. Todos os arquivos vão para uma pasta só (`<cod>/<agora>/`), como hoje.
6. **Resumo do rodapé:** "Vai criar uma versão nova de 15 m, 25 m. Classes que não aparecem aqui continuam como estão." Quando duas camadas caem na mesma classe, ele diz "25 m (2 camadas juntas)", porque o agente junta as camadas da mesma classe numa versão só.
7. **Um envio por vez:** enquanto o último envio de obstáculos estiver na fila ou processando, a janela mostra "Processando o envio anterior…" no lugar da área de arrastar, e o botão de enviar some.
8. **Quem só lê também abre a janela, em modo consulta**: cartões das classes e o erro do último envio, sem área de arrastar nem botões. Com isso, o chip de Obstáculos vira botão para todos (na S4 era só texto para quem lê) e a lista "Obstáculos com mais de 24 meses" da faixa Atenção (`DR.abrirObst`) abre a janela para qualquer usuário. Nenhuma ação de editor aparece (Foco 4).
9. **Fechar (×, Esc ou Cancelar) descarta os arquivos escolhidos.** A janela é reaberta vazia. Ela também fecha ao trocar de fazenda ou voltar ao Início.
10. **Fim do envio:** a janela fecha e o chip passa a "processando envio…" (já sai de `drChipObstaculos`, e o polling de 5 s já liga porque `drOcupado` olha os envios). Quando o agente grava, a assinatura dos obstáculos muda, `DR.obstGeo` é invalidado e, como o envio foi feito nesta tela, a camada de obstáculos **liga sozinha** no mapa com o fade de 300 ms (`DR.obstLigarAoFim`). Se der erro, o chip fica vermelho e a janela mostra a mensagem do agente na próxima abertura.
11. **Descrição curta das classes nos cartões** fica numa constante `DR_OBS_DESC` (15: "árvore isolada", 25: "rede de energia padrão", 50: "alta tensão, sede, APP, rodovia…"), como na maquete. A lista completa de `hub.drone_classes_restricao.categorias` é longa demais para o cartão e vai no `title`. Não há busca nova no banco.
12. **Proteção nos testes de tela:** antes de abrir a janela, o teste troca `drSubirComProgresso` e o `drone_registrar_envio` de `drRpc` por funções que lançam erro. Assim, nenhum caminho do teste consegue enviar obstáculos de verdade, nem por engano. O envio real é conferido pelo usuário.

**Interfaces produzidas (puras em `app/drone-dados.js`):**
- `drClassePeloNome(nome) → 15|25|50|null`: igual a `drone/insumos.py::classe_pelo_nome`. Tira a pasta e a última extensão, tira o acento, passa para minúsculas, procura `/(\d+)\s*m(?![a-z])/` e, só se não achar, `/(\d+)$/`. Vale só 15, 25 ou 50.
- `drAgruparArquivos(arquivos: Array<{nome, tamanho, origem}>) → Array<{chave, base, origens: string[], partes: {shp?,shx?,dbf?,prj?,cpg?: índice em arquivos}, falta: string[], classe: number|null, conflito: boolean}>`. `nome` pode trazer a pasta do zip; `origem` é o nome do `.zip`, ou `''` para arquivo solto. A ordem segue a primeira aparição de cada camada.
- `drNomeComClasse(classe, nome) → string`: `${classe}m_${drNomeSeguro(base)}.${ext minúscula}`
- `drDicaClasse(sugerida, escolhida) → {texto, tom}`: "pelo nome do arquivo", "trocada por você" ou "escolha a classe" (tom `'aviso'`)
- `drPlanoEnvio(grupos, escolhas: {[chave]: 15|25|50}) → {pronto, motivo, arquivos: [{indice, nome}], resumo}`
- `drCartoesObst(obst, hoje, meses=24) → [{classe, desc, texto, velho}]`, sempre 15, 25 e 50, nessa ordem

**Interfaces produzidas (DOM em `app/drone-obstaculos.js`, estado em `DRO`):** `droAbrir()`, `droFechar()`, `droAdicionar(FileList|File[])` (async; abre `.zip` com JSZip 3.10.1 carregado sob demanda do cdnjs), `droClasse(chave, c)`, `droRemover(chave)`, `droPreparar() → {pronto, motivo, nomes}` (não sobe nada), `droEnviar()`.

---

## S5.0 Branch

- [x] **Passo 1:** `git worktree add ../hub-geotech-drone-s5 -b drone-s5 main` e rodar `node --test tests/app/*.test.js` lá. Resultado: 76 passando, nenhuma falha.

## S5.1 Funções puras (TDD, Foco 3)

**Arquivos:** `app/drone-dados.js`, `tests/app/drone_puro.test.js`

- [ ] **Passo 1: escrever os testes.** Antes da implementação, eles falham com "não é função".

```js
const A = (nome, origem = '', tamanho = 10) => ({ nome, origem, tamanho });

test('classe pelo nome do arquivo (mesma regra do agente)', () => {
  const casos = [
    ['restricoes15m.shp', 15], ['Restrições 25 m.shp', 25], ['rede_50m_cemig.shp', 50],
    ['linhas_cemig.shp', null], ['obst_30m.shp', null],
    // os mesmos de tests/drone/test_insumos.py::test_classe_pelo_nome
    ['restricoes15m', 15], ['Restrições 15m', 15], ['15M', 15], ['retricoes25m', 25], ['resrtricoes50m', 50],
    ['restricoes50m_rede', 50], ['REDE50', 50], ['restricoes10m', null], ['Arvores', null],
    ['pasta/sub/app_50m.SHP', 50], ['15m_rede_50m.shp', 15],
  ];
  for (const [n, c] of casos) assert.strictEqual(ctx.drClassePeloNome(n), c, n);
});

test('nome com a classe na frente volta à mesma classe pelo regex do agente', () => {
  assert.strictEqual(ctx.drNomeComClasse(25, 'linhas_cemig.shp'), '25m_linhas_cemig.shp');
  assert.strictEqual(ctx.drNomeComClasse(15, 'obst.zip/pasta/Rede 50m.SHP'), '15m_Rede_50m.shp');
  assert.strictEqual(ctx.drNomeComClasse(50, 'Área Mata.PRJ'), '50m_Area_Mata.prj');
  assert.strictEqual(ctx.drClassePeloNome(ctx.drNomeComClasse(25, 'linhas_cemig.shp')), 25);
  assert.strictEqual(ctx.drClassePeloNome(ctx.drNomeComClasse(15, 'rede_50m.shp')), 15);
});

test('agrupa as partes pelo nome-base, com extensão maiúscula e pasta do zip', () => {
  const g = ctx.drAgruparArquivos([A('REDE_25m.SHP'), A('rede_25m.shx'), A('rede_25m.dbf'), A('rede_25m.prj'),
    A('pasta/app_mata.shp', 'obst.zip'), A('pasta/app_mata.shx', 'obst.zip'), A('pasta/app_mata.dbf', 'obst.zip'),
    A('pasta/app_mata.prj', 'obst.zip'), A('pasta/app_mata.cpg', 'obst.zip'), A('leia-me.txt')]);
  assert.strictEqual(g.length, 2);
  assert.deepStrictEqual([...g[0].falta], []);
  assert.strictEqual(g[0].classe, 25);
  assert.strictEqual(g[0].conflito, false);
  assert.deepStrictEqual(Object.keys(g[1].partes).sort(), ['cpg', 'dbf', 'prj', 'shp', 'shx']);
  assert.deepStrictEqual([...g[1].origens], ['obst.zip']);
  assert.strictEqual(g[1].classe, null);
});

test('partes que faltam: .shx e .prj bloqueiam, .cpg não', () => {
  const g = ctx.drAgruparArquivos([A('a15m.shp'), A('a15m.dbf'), A('a15m.prj'), A('b25m.shp'), A('b25m.shx'), A('b25m.dbf')]);
  assert.deepStrictEqual([...g[0].falta], ['shx']);
  assert.deepStrictEqual([...g[1].falta], ['prj']);
});

test('mesmo nome-base em dois zips é conflito; o mesmo arquivo duas vezes não', () => {
  const partes = (o) => ['shp', 'shx', 'dbf', 'prj'].map(e => A('linhas.' + e, o));
  const g = ctx.drAgruparArquivos([...partes('a.zip'), ...partes('b.zip')]);
  assert.strictEqual(g.length, 1);
  assert.strictEqual(g[0].conflito, true);
  assert.deepStrictEqual([...g[0].origens], ['a.zip', 'b.zip']);
  const r = ctx.drAgruparArquivos([...partes(''), A('linhas.shp')]);   // repetido: mesmo nome, origem e tamanho
  assert.strictEqual(r[0].conflito, false);
});

test('nome com espaço e acento agrupa com a versão sem acento e mantém o nome para mostrar', () => {
  const g = ctx.drAgruparArquivos([A('Área de Mata 50m.shp'), A('Área de Mata 50m.shx'), A('Área de Mata 50m.dbf'), A('Área de Mata 50m.prj')]);
  assert.strictEqual(g.length, 1);
  assert.strictEqual(g[0].base, 'Área de Mata 50m');
  assert.strictEqual(g[0].classe, 50);
});

test('dica da classe', () => {
  assert.strictEqual(ctx.drDicaClasse(25, 25).texto, 'pelo nome do arquivo');
  assert.strictEqual(ctx.drDicaClasse(25, 50).texto, 'trocada por você');
  assert.strictEqual(ctx.drDicaClasse(null, 15).texto, 'trocada por você');
  assert.strictEqual(ctx.drDicaClasse(null, null).tom, 'aviso');
});

test('plano do envio: bloqueia sem classe, com parte faltando ou conflito', () => {
  const ok = ctx.drAgruparArquivos(['shp', 'shx', 'dbf', 'prj'].map(e => A('linhas.' + e)));
  assert.strictEqual(ctx.drPlanoEnvio([], {}).pronto, false);
  assert.match(ctx.drPlanoEnvio(ok, {}).motivo, /classe/);
  const p = ctx.drPlanoEnvio(ok, { [ok[0].chave]: 25 });
  assert.strictEqual(p.pronto, true);
  assert.deepStrictEqual(p.arquivos.map(a => a.nome),
    ['25m_linhas.shp', '25m_linhas.shx', '25m_linhas.dbf', '25m_linhas.prj']);
  const falta = ctx.drAgruparArquivos([A('x15m.shp'), A('x15m.dbf'), A('x15m.prj')]);
  assert.match(ctx.drPlanoEnvio(falta, { [falta[0].chave]: 15 }).motivo, /\.shx/);
});

test('resumo diz as classes novas e junta camadas da mesma classe', () => {
  const g = ctx.drAgruparArquivos(['a15m', 'b25m', 'c25m'].flatMap(b => ['shp', 'shx', 'dbf', 'prj'].map(e => A(b + '.' + e))));
  const esc = Object.fromEntries(g.map(x => [x.chave, x.classe]));
  assert.strictEqual(ctx.drPlanoEnvio(g, esc).resumo,
    'Vai criar uma versão nova de 15 m, 25 m (2 camadas juntas). Classes que não aparecem aqui continuam como estão.');
});

test('cartões das classes: sempre três, âmbar com mais de 24 meses', () => {
  const hoje = new Date('2026-10-29T12:00:00Z');
  const c = ctx.drCartoesObst([{ classe_m: 25, versao: 2, enviado_em: '2026-09-30T12:00:00Z', n_feicoes: 6 },
    { classe_m: 50, versao: 1, enviado_em: '2023-11-10T12:00:00Z', n_feicoes: 22 }], hoje);
  assert.deepStrictEqual(c.map(x => x.classe), [15, 25, 50]);
  assert.strictEqual(c[0].texto, 'sem cadastro');
  assert.strictEqual(c[1].texto, 'v2 · 30/09/2026 · 6 feições');
  assert.strictEqual(c[1].velho, false);
  assert.strictEqual(c[2].velho, true);
  assert.match(c[2].texto, /mais de 24 meses/);
});
```

- [ ] **Passo 2: implementar** em `app/drone-dados.js`, perto de `drNomeSeguro`:
  - `chave = drNomeSeguro(base).toLowerCase()`, com `base` = nome sem pasta e sem a última extensão;
  - extensões aceitas: `shp shx dbf prj cpg`, e as demais são ignoradas;
  - deduplicação por `origem|nome|tamanho` antes de agrupar;
  - `falta` na ordem `shp, shx, dbf, prj`;
  - `classe` = `drClassePeloNome` do `.shp` ou, se não houver `.shp`, do primeiro arquivo da camada;
  - `motivo` de `drPlanoEnvio`, na ordem: "Nenhuma camada para enviar." → "`<base>`: falta .shx" (primeira camada incompleta) → "`<base>`: mesmo nome em a.zip e b.zip — renomeie um deles" (origem `''` aparece como "arquivo solto") → "Escolha a classe de todas as camadas.";
  - `DR_OBS_DESC` ao lado de `DR_OBS_COR`.
  - Tirar `drClasseEscolhida` e o teste "classe escolhida no envio de obstáculos" (ninguém mais usa depois da S5.4).
- [ ] **Passo 3:** `node --test tests/app/*.test.js`. Esperado: tudo passando.
- [ ] **Passo 4:** commit `Drone S5.1: funções puras da janela de obstáculos`.

## S5.2 Prova de que o agente lê o nome renomeado

**Arquivo:** `tests/drone/test_insumos.py` (a única mudança em `drone/`, permitida pelas restrições globais)

- [ ] **Passo 1:** acrescentar ao `parametrize` de `test_classe_pelo_nome` os casos `('25m_linhas_cemig.shp', 25)` e `('15m_rede_50m.shp', 15)`.
- [ ] **Passo 2:** `pytest tests/drone/test_insumos.py -q`. Esperado: passa sem mudar o agente. Se falhar, **parar e avisar**: a regra do nome não serve, e a decisão de não mudar o agente precisa ser revista.
- [ ] **Passo 3:** commit `Drone S5.2: agente lê a classe do nome renomeado`.

## S5.3 Janela (spec §3.4, maquete tela 3)

**Arquivos:** criar `app/drone-obstaculos.js`; modificar `app/drone.css` e `app/index.html`

- [ ] **Passo 1:** `drone-obstaculos.js`, com o estado `const DRO={arquivos:[],escolhas:{},grupos:[],ignorados:0,enviando:false}`:
  - `droAbrir()`: cria `.dro-fundo > section.dro-jan[role=dialog][aria-modal=true][aria-labelledby=dro-t]` em `document.body`, com `Mo.carregando`/`Mo.pronto`. O cabeçalho tem o ícone `warning`, "Obstáculos da fazenda" e a linha `<cod> · <nome> — valem para todas as revisões (Normal e Catação)`. Depois vêm os 3 cartões (`drCartoesObst(DR.info.obst,new Date())`, bolinha com `DR_OBS_COR`, cartão âmbar se `velho`) e, se o último envio de obstáculos deu erro, uma faixa vermelha com `envio.erro`. Para o editor sem envio em andamento, aparecem a área de arrastar (`#dro-solta`, com `dragover`/`drop`) e "Escolher arquivos" (`<input type=file id=dro-inp multiple accept=".shp,.shx,.dbf,.prj,.cpg,.zip" hidden>`). Com envio em andamento, aparece "Processando o envio anterior…" (decisão 7). Em modo consulta, só os cartões e o erro (decisão 8).
  - Lista `#dro-lista` ("Camadas encontradas · N"): uma linha por grupo, com o ícone (`folder_zip` se veio de zip, `description` se não), o nome (`a.zip › base` quando veio de zip), as pílulas `.shp .shx .dbf .prj` (a que falta com a classe `falta`) e `.cpg` só se houver, a observação (conflito ou falta), os botões 15/25/50 (`aria-pressed`), a dica (`drDicaClasse`) e o × (`aria-label="Tirar <base>"`). Embaixo, "N arquivos ignorados" quando houver.
  - Rodapé: o resumo (`drPlanoEnvio(...).resumo`, ou `motivo` quando não está pronto), **Cancelar** e o botão principal. O botão vem desabilitado com "Escolha a classe de todas" (ou o motivo curto) e, quando pronto, vira "Enviar N camadas".
  - `droAdicionar(lista)`: em cada `.zip`, carrega o JSZip (uma promessa guardada; `<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js">`), percorre as entradas (sem pasta, sem `__MACOSX/`, sem `._*`, sem `.zip`) e vira `{nome: entrada.name, tamanho, origem: zip.name, arq: new File([blob], basename)}`. Os soltos viram `{nome: f.name, tamanho: f.size, origem: '', arq: f}`. Depois reagrupa, preenche `DRO.escolhas[chave]` com a sugestão só quando a chave é nova e redesenha só a lista e o rodapé. Se o zip estiver corrompido, mostra o erro na janela sem quebrar a lista.
  - `droClasse`, `droRemover` (tira os arquivos da camada e a escolha) e `droPreparar()`, que devolve `{pronto, motivo, nomes}` sem subir nada.
  - Esc e × fecham (`droFechar`, que limpa o `DRO`). O foco vai para a janela ao abrir e volta ao botão Obstáculos ao fechar.
- [ ] **Passo 2:** CSS `dro-*` em `app/drone.css`, seguindo a maquete: janela de 760 px com `max-width:100%`, raio de 20 px, cartões em grid de 3 colunas que viram 1 coluna abaixo de 640 px, área tracejada `#b9c1f3`, pílulas `.pc`/`.pc.falta` e botões de classe `.cl`/`.cl.on`. Toda animação nova respeita `prefers-reduced-motion`.
- [ ] **Passo 3:** carregar o `<script src="drone-obstaculos.js">` em `index.html` depois de `drone-fazenda.js`, e acrescentar `drone-obstaculos` ao laço do `vm` em `drone_puro.test.js`. O arquivo não pode quebrar ao ser carregado sem DOM (nada roda fora de função).
- [ ] **Passo 4:** `node --test tests/app/*.test.js` e commit `Drone S5.3: janela de obstáculos`.

## S5.4 Envio e ligação com a fazenda

**Arquivos:** `app/drone-obstaculos.js`, `app/drone-fazenda.js`, `app/drone-inicio.js`

- [ ] **Passo 1: `droEnviar()`**, com o mesmo padrão de `drEnviarArquivos`. Guarda `cod` no início; o botão fica com `Mo.ocupado`; a barra `Mo.progresso` aparece dentro do rodapé da janela. Cada arquivo de `plano.arquivos` sobe para `` `${cod}/${Date.now()}/${nome}` `` com `drSubirComProgresso`. Depois chama `drRpc('drone_registrar_envio',{p_cod_faz:cod,p_tipo:'obstaculos',p_classe_m:null,p_solicitacao_id:null,p_arquivos:caminhos})` **uma vez**. Quando dá certo, faz `droFechar()`; se `DR.cod===cod`, marca `DR.obstLigarAoFim=true` e chama `await drCarregarFazenda()`. Quando dá erro, a mensagem aparece na janela, que continua aberta com os arquivos.
- [ ] **Passo 2: `drone-fazenda.js`:**
  - o botão Obstáculos do cabeçalho chama `droAbrir()` para todos (decisão 8), e o `<span>` de quem só lê vira `<button>`;
  - `drEnviar` perde o ramo `obstaculos` (e o `prompt`);
  - a busca de `drone_obstaculo_versoes` passa a trazer `n_feicoes`;
  - em `drAbrirFazenda`: `droFechar()` no início e, depois do primeiro desenho, `if(DR.abrirObst){DR.abrirObst=false;droAbrir();}`;
  - em `drDesenhar`: quando muda a parte `obst` e `DR.obstLigarAoFim` está marcado, desmarca e chama `drObstaculos(true)`, que já faz o fade.
  - Em `drone-inicio.js`, `driVoltar` chama `droFechar()`. Atualizar o comentário da linha 242.
- [ ] **Passo 3:** `node --test tests/app/*.test.js`, carga do `index.html` sem login sem erro no console, e commit `Drone S5.4: envio pela janela e ligação com a fazenda`.

## S5.5 Demo para a conferência visual

**Arquivo:** `app/drone-fazenda-demo.html`

- [ ] **Passo 1:** `&jan=1` abre a janela depois de desenhar e chama `droAdicionar` com `File`s fictícios: `restricoes15m.{shp,shx,dbf,prj}`, `rede_energia_25m.{shp,shx,dbf,prj}`, `linhas_cemig.{shp,shx,dbf,prj}` (sem classe) e `sem_shx_50m.{shp,dbf,prj}`. Assim aparecem os quatro casos da maquete mais um bloqueio. `&obst=velho|erro|proc` continua valendo (cartão âmbar, faixa de erro, "Processando…"), e `&editar=0` mostra o modo consulta. Na demo, `drSubirComProgresso` e `drRpc` **não chamam a rede** (já é assim na demo; conferir).
- [ ] **Passo 2:** servir `app/` por http e conferir contra a maquete, tela 3, em 1440 px e em 390 px, com prints numa pasta temporária. Commit `Drone S5.5: demo da janela de obstáculos`.

## S5.6 Teste de tela até antes do envio

**Arquivos:** criar `tests/app/fixtures/gerar_obst.py` e `tests/app/fixtures/obst/*`; modificar `tests/app/teste_drone_tela.py`

- [ ] **Passo 1:** criar `gerar_obst.py`, que usa geopandas, coordenadas EPSG:4326 longe da 10974 e uma feição por camada. Ele gera `restricoes15m.*` (shp/shx/dbf/prj/cpg), `linhas_cemig.*` (sem classe no nome), `sem_shx_50m.*` (sem `.shx`), `obst.zip` (com `pasta/app_mata_50m.*`) e `outro.zip` (com `linhas_cemig.*`, para dar conflito). Rodar o script e commitar os arquivos gerados (são poucos KB).
- [ ] **Passo 2:** no teste de tela, na fase de editor (antes de passar a conta para leitura):
  1. **Proteção primeiro (decisão 12):** `window.drSubirComProgresso=()=>{throw new Error('teste: envio bloqueado')}` e um embrulho em `drRpc` que lança erro com `drone_registrar_envio`.
  2. Clicar no botão Obstáculos e conferir os 3 cartões.
  3. `set_input_files('#dro-inp', [...])` com todos os arquivos da pasta, e conferir:
     - 4 camadas na lista;
     - a linha `linhas_cemig` em conflito (arquivo solto + `outro.zip`);
     - a linha `sem_shx_50m` com `.shx` em vermelho;
     - o botão de enviar desabilitado.
  4. Tirar `sem_shx_50m` e uma das origens do conflito (tirar a camada e adicionar de novo só os soltos de `linhas_cemig`). Conferir que o botão continua desabilitado com "Escolha a classe".
  5. Clicar 25 m em `linhas_cemig` e conferir o botão habilitado e o resumo com 15 m, 25 m e 50 m.
  6. `await drCarregarFazenda()` com a janela aberta: a lista e as escolhas continuam iguais (Foco 1).
  7. `droPreparar().nomes` é igual à lista esperada (`15m_restricoes15m.shp`, …, `25m_linhas_cemig.prj`, `50m_app_mata_50m.shp`, …).
  8. Cancelar e conferir que a janela some. **Não clicar em Enviar.**
- [ ] **Passo 3:** na fase de leitura, conferir que o botão Obstáculos abre a janela sem `#dro-solta`, sem `#dro-inp` e sem botões de classe, e fechar com Esc.
- [ ] **Passo 4:** rodar `python tests/app/teste_drone_tela.py` com `HUB_CONTA_TESTE` e a 10974 livre. Da worktree, copiar `hub-geotech-supabase.env` e apagar a cópia depois. Esperado: todos ✓. Commit `Drone S5.6: teste de tela da janela de obstáculos`.

## S5.7 Verificação e revisão

- [ ] **Passo 1:** `node --test tests/app/*.test.js`, `pytest tests/drone/test_insumos.py -q`, o teste de tela e a carga sem login (skill `verification-before-completion`).
- [ ] **Passo 2:** revisão do diff com `requesting-code-review`, feita pelo Sonnet. Pontos a olhar:
  - Foco 3 inteiro: acento, espaço, `.SHP`, zip com pastas, nome repetido em dois zips, falta do `.prj`;
  - zip corrompido ou grande;
  - envio preso à fazenda de origem;
  - Foco 4 no modo consulta;
  - foco e Esc da janela;
  - o polling não fecha a janela nem apaga as escolhas.
- [ ] **Passo 3:** corrigir os achados que valerem a pena e registrar no fim deste arquivo.

## S5.8 Fechamento

- [ ] **Passo 1:** mostrar ao usuário o resumo, os prints da demo e o que ficou para ele conferir: **o envio real numa fazenda de verdade**, com um shape de cada classe; o chip passando a processando; a camada entrando com fade; e o erro (por exemplo, um shape sem feição).
- [ ] **Passo 2:** com o **ok do usuário**, mesclar `drone-s5` na `main`, enviar (trocando a conta do `gh` só durante o push) e apagar a worktree e o branch.
- [ ] **Passo 3:** atualizar a memória `project_drone_telas_redesenho` (S5 feita, próxima S6).

---

## Registro da execução

(preencher por camada: quem fez, commits, testes, achados da revisão)
