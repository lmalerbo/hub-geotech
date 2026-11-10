"""Todo ponto que atribui HTML dinâmico no app foi conferido e está marcado (plano SEG4).

`innerHTML = ...` com dado do banco, de arquivo enviado ou do usuário sem escape é XSS com
acesso à sessão. O inventário em docs/seguranca/2026-11-innerhtml.md lista cada ponto; esta
guarda impede que um ponto novo entre sem alguém conferir o escape.

Precisa de marca `// esc-ok` (na linha ou na linha logo acima) toda linha que atribui ou
insere HTML: `.innerHTML =`, `.innerHTML +=`, `.outerHTML =`, `.outerHTML +=` e qualquer
`insertAdjacentHTML(`. Não precisam: leitura (`x = el.innerHTML`), comparação e atribuição
de vazio pura (`''`, `""` ou dois acentos graves). Um ternário com vazio precisa de marca.

Quando a linha abre um template literal que continua na linha seguinte, o comentário no fim
dela viraria texto do HTML: ponha `// esc-ok` sozinho na linha de cima. Onde `//` não couber
(markup fora de <script>, como dentro de um atributo), vale `<!-- esc-ok -->` sozinho na
linha de cima.
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / 'app'
ATRIBUI = re.compile(r'(?:\.|\b)(?:innerHTML|outerHTML)\s*\+?=(?!=)|insertAdjacentHTML\s*\(')
VAZIO = re.compile(r'(?:\.|\b)(?:innerHTML|outerHTML)\s*=\s*(?:\'\'|""|``)\s*(?:;|$)')
MARCA = re.compile(r'//\s*esc-ok\b|<!--\s*esc-ok\s*-->')
MARCA_SOZINHA = re.compile(r'^\s*(?://\s*esc-ok\b.*|<!--\s*esc-ok\s*-->\s*)$')


def _precisa_marca(linha: str) -> bool:
    """True se a linha atribui/insere HTML e não é só atribuição de vazio."""
    if not ATRIBUI.search(linha):
        return False
    if 'insertAdjacentHTML' not in linha and VAZIO.search(linha):
        return False
    return True


def _marcado(linhas, i) -> bool:
    if MARCA.search(linhas[i]):
        return True
    return i > 0 and bool(MARCA_SOZINHA.match(linhas[i - 1]))


def _pontos():
    for arq in sorted(list(APP.glob('*.js')) + list(APP.glob('*.html'))):
        linhas = arq.read_text(encoding='utf-8').splitlines()
        for i, linha in enumerate(linhas):
            if _precisa_marca(linha):
                yield arq.name, i + 1, _marcado(linhas, i)


def test_detecta_o_que_precisa_de_marca():
    casos = [
        ("el.innerHTML = html;", True),
        ("el.innerHTML=`<b>${x}</b>`;", True),
        ("el.innerHTML += '<i></i>';", True),
        ("el.outerHTML = drCabecalhoHtml();", True),
        ("el.insertAdjacentHTML('beforeend', x);", True),
        ("el.innerHTML = c ? '' : x;", True),
        ("el.innerHTML = '' + x;", True),
        ("el.innerHTML = '';", False),
        ("el.innerHTML=\"\";", False),
        ("if(x){el.innerHTML='';return;}", False),
        ("el.innerHTML = ``", False),
        ("const h = el.innerHTML;", False),
        ("if (el.innerHTML === '') {}", False),
        ("if (el.innerHTML != x) {}", False),
    ]
    for linha, esperado in casos:
        assert _precisa_marca(linha) is esperado, linha


def test_marca_na_linha_ou_na_de_cima():
    assert _marcado(['a.innerHTML = x; // esc-ok'], 0)
    assert _marcado(['// esc-ok', 'a.innerHTML = `<p>'], 1)
    assert _marcado(['<!-- esc-ok -->', 'a.innerHTML = x'], 1)
    assert not _marcado(['// esc-ok', 'foo();', 'a.innerHTML = x'], 2)
    assert not _marcado(['a.innerHTML = x;'], 0)


def test_todo_ponto_de_innerhtml_esta_marcado():
    sem_marca = [f'{nome}:{n}' for nome, n, ok in _pontos() if not ok]
    assert not sem_marca, (
        'atribuição de HTML sem marca: ' + ', '.join(sem_marca)
        + ' — confira o escape (docs/seguranca/2026-11-innerhtml.md) e marque com // esc-ok'
    )


def test_a_varredura_enxerga_os_pontos():
    assert len(list(_pontos())) >= 100
