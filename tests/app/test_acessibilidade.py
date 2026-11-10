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
