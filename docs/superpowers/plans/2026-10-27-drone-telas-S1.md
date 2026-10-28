# Drone S1: dividir `drone.js` sem mudar o comportamento — plano em passos

> **Para quem executa:** detalhamento da seção S1 de [2026-10-27-drone-telas-redesenho.md](2026-10-27-drone-telas-redesenho.md). Execução pela skill `delegar`: o operacional sai para o executor barato, e revisão e merge ficam com o Claude principal. Marque as caixas (`- [ ]`) conforme avança.

**Objetivo:** trocar `app/drone.js` (867 linhas) por quatro arquivos por responsabilidade e um `app/drone.css`, sem mudar nenhum comportamento.

**Arquitetura:** o corte é feito por um script determinístico, não à mão. O script separa o arquivo em blocos de topo (cada `function`/`const` na coluna 0, junto com os comentários colados logo acima), manda cada bloco para um arquivo conforme uma tabela de nomes e mantém a ordem original dentro de cada arquivo. O CSS das duas strings (`drEstilo`, `drPrevEstilo`) vai literal para `drone.css`; as duas funções e as 4 chamadas somem. No navegador, scripts clássicos compartilham os `const` de topo, então a ordem dados → prévia → início → fazenda basta. Conferido também no `vm` do Node: dois `runInContext` no mesmo contexto enxergam o `const` um do outro.

**Tecnologias:** JS puro (scripts clássicos), Python 3 (script de corte, roda uma vez fora do repositório), `node --test`, Playwright + Edge (teste de tela já existente).

**Spec:** [§7 de 2026-10-27-drone-telas-redesenho-design.md](../specs/2026-10-27-drone-telas-redesenho-design.md)

## Restrições globais

- Cópia literal: nenhuma linha de código muda, exceto a remoção de `drEstilo();` e `drPrevEstilo();` e das duas funções de estilo. Cada arquivo novo ganha só uma linha de comentário no topo.
- Nenhuma asserção dos testes muda. O comando é `node --test tests/app/*.test.js`; sem o glob, falha. Hoje são 46 testes.
- O agente Python (`drone/`) não muda. Os scripts antigos em `drone/trabalho/edita_*.py` citam `app/drone.js`, mas são histórico de edições já aplicadas e ficam como estão.
- Teste de tela só com a fazenda 10974 livre (regra de `tests/app/teste_drone_tela.py`).
- Antes de mesclar: verificação, revisão do diff e **ok do usuário**. O push exige trocar a conta do `gh` (memória `reference-github-contas-push`).

## Foco da revisão

1. **Bloco no arquivo errado ou perdido:** o script imprime a lista do que foi para cada arquivo e confere se a soma das linhas fecha com o original (menos as linhas de estilo). Fecha errado → o script para.
2. **Cascata do CSS:** antes, o `<style>` entrava no fim do `<head>` na hora de abrir a tela. Agora o `<link>` fica depois do CSS do MapLibre. Todos os seletores têm prefixo `.dr`/`.drp` (conferido), então não há disputa com o resto da página.
3. **A prévia sem `drPrevEstilo()`:** ela abre também a partir do mapa/painel, não só via `droneIniciar`. Com o CSS sempre carregado, isso continua coberto; conferir no navegador.
4. **Ordem de carga:** uma função de um arquivo chamando a de outro só na hora do clique, nunca no carregamento. O script garante que não há código solto no topo (só `function`/`const`); se encontrar outra coisa, para.
5. **Cache do navegador/Pages:** o `index.html` novo pede arquivos novos; o `drone.js` antigo some do servidor. Sem service worker no app, nada a invalidar.

---

### Tarefa S1.1: cortar o arquivo e religar `index.html` e o teste puro

**Arquivos:**
- Criar: `app/drone-dados.js`, `app/drone-previa.js`, `app/drone-inicio.js`, `app/drone-fazenda.js`, `app/drone.css`
- Remover: `app/drone.js`
- Modificar: `app/index.html` (linha 3032 e o `<head>` depois da linha 659), `tests/app/drone_puro.test.js:9`
- Script (fora do repo): `<scratchpad>/dividir_drone.py`

**Tabela de destino** (o que não está listado vai para `drone-fazenda.js`):

| Arquivo | Blocos |
|---|---|
| `drone-dados.js` | `DR`, `DR_ST`, `DR_COR`, `drBotao`, `drRpc`, `drMapaReaproveitavel`, `drPodeGerarCatacao`, `drNomeSeguro`, `drClasseEscolhida`, `drPodeCancelar`, `drAtual`, `drValidarSolicitacao`, `DR_OBS_COR`, `drRotuloShape`, `drUltimoEnvio`, `drAssinaturaObst` |
| `drone-previa.js` | `DRP`, `DRP_PDFJS`, `DRP_PASSOS`, `drPrevPassosHtml`, `drPrevHtml`, `drPdfjs`, `drPrevCarregar`, `drPrevOuvir`, `drDesenharPagina`, `drMostrarPdf`, `drPrevAbrir`, `drPrevFechar`, `drPrevMontar`, `drPrevLarguraAjuste`, `drPrevZoom`, `drPrevRedesenhar`, `drPrevBaixar`, `drPrevAcao` |
| `drone-inicio.js` | `droneIniciar`, `drCarregarPainel`, `drListarAtencao`, `drBuscar`, `drNovaSolicitacao`, `drIrFazenda`, `drCancelar` |
| `drone.css` | o texto de `drEstilo` e depois o de `drPrevEstilo` (as funções somem) |
| `drone-fazenda.js` | o resto: `drAbrirFazenda`, `drRecarregarFazenda`, `drCabecalhoHtml`, `drAtualizarFontesMapa`, `drRender`, `drVooPublicacao`, `drPintarMapa`, `drAtualizarSelecaoMapa`, `drClicarTalhao`, `drSelecionarSemProjeto`, `drFonte`, `drObstaculosHtml`, `drPainelLateral`, `drErro`, `drEnviar`, `drSubirComProgresso`, `drGerarNormal`, `drAbrirCatacao`, `drGerarCatacao`, `drPublicar`, `drDescartar`, `drObstaculos` |

- [ ] **Passo 1: criar o branch e o worktree**

```bash
git worktree add ../hub-geotech-drone-s1 -b drone-s1 main
cd ../hub-geotech-drone-s1
node --test tests/app/*.test.js   # esperado: 46 passam (linha de base)
```

- [ ] **Passo 2: escrever o script de corte** em `<scratchpad>/dividir_drone.py`

```python
"""Corta app/drone.js em 4 arquivos + drone.css, copiando literal. Uso: python dividir_drone.py <raiz do repo>"""
import re, sys, collections
from pathlib import Path

raiz = Path(sys.argv[1]); app = raiz / 'app'
orig = (app / 'drone.js').read_text(encoding='utf-8').split('\n')
if orig and orig[-1] == '':
    orig = orig[:-1]

DESTINO = {}
for arq, nomes in {
    'dados': 'DR DR_ST DR_COR drBotao drRpc drMapaReaproveitavel drPodeGerarCatacao drNomeSeguro drClasseEscolhida '
             'drPodeCancelar drAtual drValidarSolicitacao DR_OBS_COR drRotuloShape drUltimoEnvio drAssinaturaObst',
    'previa': 'DRP DRP_PDFJS DRP_PASSOS drPrevPassosHtml drPrevHtml drPdfjs drPrevCarregar drPrevOuvir drDesenharPagina '
              'drMostrarPdf drPrevAbrir drPrevFechar drPrevMontar drPrevLarguraAjuste drPrevZoom drPrevRedesenhar '
              'drPrevBaixar drPrevAcao',
    'inicio': 'droneIniciar drCarregarPainel drListarAtencao drBuscar drNovaSolicitacao drIrFazenda drCancelar',
    'estilo': 'drEstilo drPrevEstilo',
}.items():
    for n in nomes.split():
        DESTINO[n] = arq

INICIO = re.compile(r'^(?:async function|function|const)\s+([A-Za-z_$][\w$]*)')

# 1. Achar os inícios de bloco; comentários e linhas em branco colados acima vão junto com o bloco.
inicios = [i for i, l in enumerate(orig) if INICIO.match(l)]
# Código solto no topo (rodaria na carga, e a ordem entre arquivos mudaria): para.
SOLTO = re.compile(r'^(?:if|for|while|let|var|window\.|document\.|DR\w*\.|[A-Za-z_$][\w$]*\s*\()')
for i, l in enumerate(orig):
    if SOLTO.match(l):
        sys.exit(f'linha {i+1}: código solto no topo: {l[:80]!r}')
cortes = []
for i in inicios:
    j = i
    while j > 0 and (orig[j-1].startswith('//') or orig[j-1].strip() == '') and (j-1) not in cortes:
        j -= 1
    cortes.append(j)
cortes[0] = 0  # o comentário de cabeçalho (linha 1) fica com o primeiro bloco (DR, em dados)
blocos = []
for k, (c, i) in enumerate(zip(cortes, inicios)):
    fim = cortes[k+1] if k + 1 < len(cortes) else len(orig)
    blocos.append((INICIO.match(orig[i]).group(1), orig[c:fim]))

# 2. Distribuir.
saida = collections.defaultdict(list); css = []
for nome, linhas in blocos:
    arq = DESTINO.get(nome, 'fazenda')
    if arq == 'estilo':
        texto = '\n'.join(linhas)
        m = re.search(r's\.textContent=`\n?(.*?)`;', texto, re.S)
        if not m or '${' in m.group(1) or '\\' in m.group(1):
            sys.exit(f'CSS de {nome} não é literal')
        css.append(m.group(1).rstrip('\n'))
        saida['estilo'] += linhas
        continue
    saida[arq].append((nome, linhas))

# 3. Tirar as chamadas de estilo (linha que fica vazia some).
removidas = []
def limpar(linhas):
    novas = []
    for l in linhas:
        s = l.replace('drEstilo();', '').replace('drPrevEstilo();', '')
        if s != l:
            removidas.append(l)
            if s.strip() == '':
                continue
        novas.append(s)
    return novas

CAB = {
    'dados': '// Drone: estado (DR), chamadas ao banco e regras puras. Carregado por index.html antes de drone-previa/inicio/fazenda.',
    'previa': '// Drone: prévia do PDF (pdf.js). Carregado por index.html depois de drone-dados.js.',
    'inicio': '// Drone: Início (fila, Atenção, busca, nova solicitação). Carregado por index.html depois de drone-previa.js.',
    'fazenda': '// Drone: área de trabalho da fazenda (mapa, painel, envios, gerar/publicar). Carregado por index.html por último.',
}
total = 0
for arq in ('dados', 'previa', 'inicio', 'fazenda'):
    linhas = []
    for nome, b in saida[arq]:
        linhas += limpar(b)
    while linhas and linhas[-1].strip() == '':
        linhas.pop()
    total += len(linhas)
    (app / f'drone-{arq}.js').write_text(CAB[arq] + '\n' + '\n'.join(linhas) + '\n', encoding='utf-8')
    print(f'drone-{arq}.js: {len(linhas)+1} linhas ->', ', '.join(n for n, _ in saida[arq]))
(app / 'drone.css').write_text('/* Tela do Drone (antes injetado por drEstilo/drPrevEstilo em drone.js). */\n'
                               + '\n'.join(css) + '\n', encoding='utf-8')

# 4. Conferência: nenhuma linha de código perdida nem inventada.
n_chamadas = len(removidas)
def conta(ls): return collections.Counter(l for l in ls if l.strip())
esperado = conta(limpar(orig)) - conta(saida['estilo'])
obtido = collections.Counter()
for arq in ('dados', 'previa', 'inicio', 'fazenda'):
    for nome, b in saida[arq]:
        obtido += conta(limpar(b))
if esperado != obtido or n_chamadas != 4:
    sys.exit(f'CONFERÊNCIA FALHOU: faltam {esperado - obtido}, sobram {obtido - esperado}, chamadas {n_chamadas}')
print('conferência ok; chamadas de estilo removidas:', n_chamadas)
```

- [ ] **Passo 3: rodar o script**

Rodar: `python -I <scratchpad>/dividir_drone.py .`
Esperado: as 4 listas batendo com a tabela acima, `drone-fazenda.js` com exatamente os 22 nomes listados, e "conferência ok". Se a lista do fazenda tiver nome fora da tabela, parar e conferir.

- [ ] **Passo 4: conferir que as 4 chamadas sumiram e nada mais**

```bash
grep -n "drEstilo\|drPrevEstilo" app/drone-*.js     # esperado: nada
grep -c "drone-css\|drone-previa-css" app/drone-*.js  # esperado: 0 em todos
```

- [ ] **Passo 5: apagar `drone.js` e religar `index.html`**

```bash
git rm app/drone.js
```

Em `app/index.html`, trocar a linha 3032 `<script src="drone.js"></script>` por:

```html
<script src="drone-dados.js"></script>
<script src="drone-previa.js"></script>
<script src="drone-inicio.js"></script>
<script src="drone-fazenda.js"></script>
```

E logo depois da linha 659 (`<script src=".../maplibre-gl.js"></script>`) acrescentar:

```html
<link rel="stylesheet" href="drone.css">
```

- [ ] **Passo 6: religar o teste puro** em `tests/app/drone_puro.test.js:9`, trocando a linha única por:

```js
for (const f of ['drone-dados', 'drone-previa', 'drone-inicio', 'drone-fazenda'])
  vm.runInContext(fs.readFileSync(__dirname + '/../../app/' + f + '.js', 'utf8'), ctx);
```

Atualizar também o comentário da linha 1 se citar `drone.js` (hoje não cita).

- [ ] **Passo 7: rodar todos os testes**

Rodar: `node --test tests/app/*.test.js`
Esperado: 46 passam, 0 falham. `git diff main -- tests/` mostra só a troca da linha 9.

- [ ] **Passo 8: sintaxe dos 4 arquivos isolados**

Rodar: `for f in app/drone-*.js; do node --check "$f" || echo FALHOU $f; done`
Esperado: nenhuma falha.

- [ ] **Passo 9: commit**

```bash
git add app/drone-dados.js app/drone-previa.js app/drone-inicio.js app/drone-fazenda.js app/drone.css app/index.html tests/app/drone_puro.test.js
git commit -m "Drone S1: divide drone.js em dados/previa/inicio/fazenda e drone.css, sem mudar comportamento"
```

### Tarefa S1.2: teste de tela e conferência no navegador

**Arquivos:** nenhum alterado (só se aparecer erro, e aí volta para a S1.1).

- [ ] **Passo 1: teste de tela automático**

Conferir as regras no topo de `tests/app/teste_drone_tela.py` (fazenda 10974 sem solicitação aberta e fila do agente vazia) e rodar: `python tests/app/teste_drone_tela.py`
Esperado: termina sem falha. Ele gera uma prévia e descarta; nada é publicado.

- [ ] **Passo 2: conferência no navegador** (servidor local na pasta `app/` do worktree, console aberto)

Conferir, sem nenhum erro no console:
- a aba Drone abre a fila (Início) com as cores e o layout de antes;
- o sininho/aviso de Drone leva à fazenda (`drIrFazenda`);
- abrir uma fazenda mostra o mapa e o painel;
- a prévia abre, dá zoom e fecha, com o estilo de antes;
- "Nova solicitação" abre o formulário com o estilo de antes (não enviar).

Se o Chrome não conectar, a conferência fica com o usuário, como na S0.

- [ ] **Passo 3: commit** (só se a S1.2 exigiu ajuste; senão, marcar as caixas deste plano e commitar o plano)

```bash
git add docs/superpowers/plans/2026-10-27-drone-telas-S1.md
git commit -m "Plano S1: caixas marcadas"
```

### Fechamento

- [ ] `verification-before-completion` (testes rodados agora, saída lida).
- [ ] Revisão do diff (`requesting-code-review`): conferir em especial que `git diff --stat` mostra o `drone.js` saindo com 867 linhas e os novos somando 867 − linhas de estilo + 5 cabeçalhos.
- [ ] **Ok do usuário**, merge na main, push (troca de conta do `gh`), remover o worktree e o branch.
- [ ] Atualizar a memória `project_drone_telas_redesenho.md` (estado: S1 feita; próxima S2).
