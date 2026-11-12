# SEG4 — todo `innerHTML` do Hub passa pelo escape

**Objetivo:** nenhum dado vindo do banco, de arquivo enviado (shapefile, KML, planilha) ou do usuário chega ao HTML sem escape. Item SEG4 do plano dos pilares (Segurança).

**Contexto para o worker:**
- O app é HTML + JS puro em `app/`. O escape padrão é `esc(s)` (definido em `app/index.html` por volta da linha 2553 e repetido em `portal.html` e nos `*-demo.html`). Ele troca `& < > " '` por entidades.
- Os arquivos `app/*.js` carregados pelo `index.html` usam o `esc` global do `index.html`. Alguns têm escape próprio (ex.: `pjH` em `projetos.js`); confira o que ele faz e, se for equivalente a `esc`, ele vale.
- `esc` NÃO basta dentro de handler inline (`onclick="f('${esc(x)}')"`): o navegador decodifica `&#39;` para `'` antes de rodar o JS, e o texto fecha a string. Nesse contexto use o padrão do `portal.html` (`escJs`: escapa `\` e `'` para JS e depois aplica `esc`) ou, melhor, troque o handler inline por `data-*` + `addEventListener`. Já existe o teste `tests/app/usuarios_onclick.test.js` como exemplo.
- Valor que é número calculado pelo próprio código (`toFixed`, contagem, índice) ou texto fixo do código não precisa de escape. Qualquer coisa que veio de `fetch`/Supabase/arquivo precisa.
- Escopo: `app/*.js` e `app/*.html` (inclusive os `*-demo.html`). Atribuições a `innerHTML`, `outerHTML` e chamadas a `insertAdjacentHTML`.
- Não mude visual nem comportamento. Não mexa em `supabase/`, `ingestao/`, `worker/`.

Verificação: node --test && python -m pytest -q -p no:cacheprovider

### Tarefa 1: Inventário dos pontos de HTML

**Arquivos:**
- Criar: `docs/seguranca/2026-11-innerhtml.md`.

Liste cada atribuição a `innerHTML`/`outerHTML` e cada `insertAdjacentHTML` em `app/` numa tabela: `arquivo:linha` | o que monta | de onde vêm os dados interpolados (código fixo, número calculado, banco, arquivo enviado, usuário) | situação (`ok`, `falta esc`, `handler inline`, `atribui vazio`). Quando o HTML vem de uma função (ex.: `el.innerHTML = droCorpoHtml()`), siga até a função e classifique as interpolações dela. No fim, um resumo com a contagem por situação.

Critério: todo ponto encontrado por `grep -n -E "innerHTML|outerHTML|insertAdjacentHTML" app/*.js app/*.html` aparece na tabela. Nenhum código alterado. Commit: `docs(seg4): inventário dos pontos de innerHTML`.

### Tarefa 2: Escapar o que falta

**Arquivos:**
- Modificar: os arquivos de `app/` marcados `falta esc` ou `handler inline` no inventário.
- Criar ou modificar: testes `node --test` em `tests/app/` (ex.: `tests/app/escape_html.test.js`).
- Modificar: `docs/seguranca/2026-11-innerhtml.md` (situação passa para `corrigido`).

Aplique `esc(...)` em cada interpolação de dado externo. Nos handlers inline, troque por `data-*` + `addEventListener` quando a mudança for local e simples; senão, use o escape para JS (`escJs`, como no `portal.html`, definido uma vez no arquivo que precisar). Para as funções puras que montam HTML (as já testadas em `tests/app/*_puro.test.js`), acrescente um teste que passa um texto como `<img src=x onerror=alert(1)>` e `'); alert(1); ('` e confere que o resultado não contém `<img` nem fecha a string do handler.

Critério: verificação verde; nenhuma linha `falta esc`/`handler inline` sobra no inventário. Commit: `fix(seg4): escapa dados externos antes do innerHTML`.

### Tarefa 3: Guarda contra regressão

**Arquivos:**
- Criar: `tests/app/test_innerhtml_marcado.py` (mesmo estilo de `tests/app/test_cdn_sri.py`: docstring dizendo o porquê, lê os arquivos com `Path`).
- Modificar: os arquivos de `app/`, acrescentando o comentário `// esc-ok` no fim de cada linha de atribuição já conferida.

O teste percorre `app/*.js` e `app/*.html`, acha cada linha com `innerHTML`, `outerHTML` ou `insertAdjacentHTML` que atribui ou insere algo, e falha se nem ela nem a linha logo acima tiverem `// esc-ok`. Atenção: quando a linha abre um template literal que continua na linha seguinte, o comentário no fim dela viraria texto do HTML; nesse caso ponha `// esc-ok` sozinho na linha de cima. Exceções sem marca: atribuir string vazia (`innerHTML = ''` ou `""`) e leitura (`x = el.innerHTML`). A mensagem de falha lista `arquivo:linha` e diz: "confira o escape (docs/seguranca/2026-11-innerhtml.md) e marque com // esc-ok".

Critério: verificação verde; o teste falha se você tirar uma marca qualquer (confira e devolva a marca). Commit: `test(seg4): guarda de escape nos pontos de innerHTML`.
