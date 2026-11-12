# UX2 — acessibilidade básica do Hub

**Objetivo:** todo controle do Hub tem nome acessível e todo modal se anuncia e fecha pelo teclado. Item UX2 do plano dos pilares (Experiência do usuário). Não é auditoria WCAG completa: só nomes, modais e imagens.

**Contexto para o worker:**
- O app é HTML + JS puro em `app/`; muito HTML nasce em template literal dentro de `app/*.js` (`corretivos.js`, `projetos.js`, `drone-*.js`, `apresentacao*.js`) e no script grande do `app/index.html`.
- Já existe `aria-label` em parte dos botões (ex.: `projetos.js`, `drone-previa.js`); siga o mesmo jeito.
- Modais usam `modal-fundo` / `modal-caixa` / `modal-t` (título) e alguns já têm `role="dialog"` (`corretivos.js`, `projetos.js`, `drone-*.js`).
- Textos em português do Brasil, curtos e de ação: "Fechar", "Fechar prévia", "Excluir talhão", "Baixar PDF". O rótulo diz o que o botão faz, não o ícone ("Fechar", não "X").
- Não mude o visual. Não remova `title` que já existe. Onde `title` e `aria-label` coexistem, deixe os dois com o mesmo sentido.
- Se o plano SEG4 já entrou no main, as linhas com `// esc-ok` continuam marcadas; não as remova.

Verificação: node --test && python -m pytest -q -p no:cacheprovider

### Tarefa 1: Botões e links só com ícone

**Arquivos:**
- Modificar: `app/*.html` e `app/*.js` onde houver `<button>` ou `<a>` sem texto visível (vazio, só `×`/`✕`/símbolo, só `<svg>` ou `<img>`) e sem `aria-label`.
- Criar: `tests/app/test_acessibilidade.py` (estilo de `tests/app/test_cdn_sri.py`: docstring com o porquê, lê os arquivos com `Path` e regex).

Acrescente `aria-label` em cada um. Se o `<svg>` é só decorativo dentro de botão com texto, ponha `aria-hidden="true"` nele. O teste `test_botoes_tem_nome` acha `<button ...>...</button>` e `<a ...>...</a>` nos `.html` e nos template literals dos `.js` cujo conteúdo, tirando tags e espaços, fica vazio ou com até 2 caracteres não alfanuméricos, e falha se a tag não tiver `aria-label` (ou `aria-labelledby`). A mensagem lista `arquivo:linha`.

Critério: verificação verde. Commit: `fix(ux2): nome acessível nos botões só com ícone`.

### Tarefa 2: Modais

**Arquivos:**
- Modificar: os modais em `app/index.html` e `app/*.js`.
- Modificar: `tests/app/test_acessibilidade.py`.

Toda `modal-caixa` (e os modais com outra classe, como `cr-modal`) ganha `role="dialog"`, `aria-modal="true"` e `aria-labelledby` apontando para o id do seu `modal-t` (crie o id quando faltar; ids únicos). Confira que `Esc` fecha cada modal; onde não fecha, acrescente um único listener de `keydown` que fecha o modal aberto por cima, reaproveitando a função de fechar que o botão já chama. Ao abrir, o foco vai para o primeiro campo ou para o botão principal; ao fechar, volta ao elemento que abriu (guarde `document.activeElement` antes de abrir). Teste `test_modais_tem_role_e_titulo`: toda ocorrência de `modal-caixa`/`cr-modal` tem `role="dialog"`, `aria-modal="true"` e `aria-labelledby`.

Critério: verificação verde. Commit: `fix(ux2): modais com role, título e Esc`.

### Tarefa 3: Imagens e campos

**Arquivos:**
- Modificar: `app/*.html` e `app/*.js` com `<img>` sem `alt` e `<input>`/`<select>`/`<textarea>` sem rótulo.
- Modificar: `tests/app/test_acessibilidade.py`.

`<img>` decorativa recebe `alt=""`; a que informa recebe `alt` descritivo. Campo sem `<label for>` nem `<label>` em volta recebe `aria-label` com o mesmo texto do rótulo visual ou do placeholder. Campos `type="hidden"` ficam de fora. Testes `test_imagens_tem_alt` e `test_campos_tem_rotulo`.

Critério: verificação verde. Commit: `fix(ux2): alt nas imagens e rótulo nos campos`.
