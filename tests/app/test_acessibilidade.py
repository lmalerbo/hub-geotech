"""Botões e links só com ícone têm nome acessível (plano UX2, tarefa 1).

Leitor de tela anuncia só "botão" quando não há texto nem aria-label. Um `<button>` com
`×`, só `<svg>` ou vazio precisa de `aria-label` (ou `aria-labelledby`); `title` sozinho não conta.
Nos .html varre o arquivo inteiro; nos .js, só o conteúdo dos template literals.
"""
import html as htmllib
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / 'app'
TAG = re.compile(r'<(button|a)(?=[\s>])([^>]*)>(.*?)</\1\s*>', re.I | re.S)
CRASE = re.compile(r'`[^`]*`', re.S)
TAGS = re.compile(r'<[^>]+>')
ROTULO = re.compile(r'\baria-label(?:ledby)?\s*=', re.I)


def _suspeito(conteudo):
    txt = re.sub(r'\s+', '', htmllib.unescape(TAGS.sub('', conteudo)))
    if '${' in txt or any(c.isalnum() for c in txt):
        return False
    return len(txt) <= 2


def _achar(texto, deslocamento_base=0):
    for m in TAG.finditer(texto):
        if _suspeito(m.group(3)) and not ROTULO.search(m.group(2)):
            yield texto.count('\n', 0, m.start()) + 1


def _sem_nome():
    ruins = []
    for arq in sorted(APP.glob('*.html')):
        texto = arq.read_text(encoding='utf-8')
        ruins += [f'{arq.name}:{n}' for n in _achar(texto)]
    for arq in sorted(APP.glob('*.js')):
        texto = arq.read_text(encoding='utf-8')
        for c in CRASE.finditer(texto):
            base = texto.count('\n', 0, c.start())
            ruins += [f'{arq.name}:{base + n}' for n in _achar(c.group(0))]
    return ruins


def test_botoes_tem_nome():
    ruins = _sem_nome()
    assert not ruins, 'sem nome acessível: ' + ', '.join(ruins)


def test_o_teste_enxerga_as_paginas():
    assert len(list(APP.glob('*.html'))) >= 5


# ── Tarefa 2: modais ──────────────────────────────────────────────────────────
# Só o token de classe exato `modal-caixa` ou `cr-modal` conta (a caixa que tem o título);
# `cr-modal-fundo`, `cr-modal-novo` etc. são outros tokens e não entram.
ABRE_TAG = re.compile(r'<([a-zA-Z][\w-]*)(?=[\s>])([^>]*)>', re.S)
CLASSE = re.compile(r'\bclass\s*=\s*"([^"]*)"')
CAIXAS = {'modal-caixa', 'cr-modal'}
LABELLEDBY = re.compile(r'\baria-labelledby\s*=\s*"([^"]+)"')


def _caixas(texto, base=0):
    """Rende (linha, atributos) de cada tag cuja classe tem exatamente modal-caixa/cr-modal."""
    for m in ABRE_TAG.finditer(texto):
        c = CLASSE.search(m.group(2))
        if c and CAIXAS & set(c.group(1).split()):
            yield base + texto.count('\n', 0, m.start()) + 1, m.group(2)


def _todas_caixas():
    """[(arquivo, linha, atributos, texto do arquivo, é_html)]"""
    achadas = []
    for arq in sorted(APP.glob('*.html')):
        texto = arq.read_text(encoding='utf-8')
        achadas += [(arq.name, n, a, texto, True) for n, a in _caixas(texto)]
    for arq in sorted(APP.glob('*.js')):
        texto = arq.read_text(encoding='utf-8')
        for c in CRASE.finditer(texto):
            base = texto.count('\n', 0, c.start())
            achadas += [(arq.name, n, a, texto, False) for n, a in _caixas(c.group(0), base)]
    return achadas


def _modais_sem_papel():
    ruins = []
    for nome, n, attrs, texto, _html in _todas_caixas():
        onde = f'{nome}:{n}'
        if not re.search(r'\brole\s*=\s*"dialog"', attrs):
            ruins.append(f'{onde} sem role="dialog"')
        if not re.search(r'\baria-modal\s*=\s*"true"', attrs):
            ruins.append(f'{onde} sem aria-modal="true"')
        lb = LABELLEDBY.search(attrs)
        if not lb:
            ruins.append(f'{onde} sem aria-labelledby')
            continue
        # o id referenciado existe e é único no arquivo (nos .js o título pode estar noutro literal)
        qtd = len(re.findall(r'\bid\s*=\s*"' + re.escape(lb.group(1)) + '"', texto))
        if qtd != 1:
            ruins.append(f'{onde} aria-labelledby="{lb.group(1)}" aponta para {qtd} ids')
    return ruins


def test_modais_tem_role_e_titulo():
    ruins = _modais_sem_papel()
    assert not ruins, '; '.join(ruins)


def test_o_teste_de_modais_enxerga_os_modais():
    # sem isso o teste acima passaria vazio se a regex quebrasse
    nomes = {c[0] for c in _todas_caixas()}
    assert {'index.html', 'corretivos.js', 'projetos.js'} <= nomes
    assert sum(1 for _ in _todas_caixas()) >= 11
