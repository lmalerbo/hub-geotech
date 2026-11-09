"""Toda lib de CDN do app tem versão exata e hash SRI (plano pilares SEG2).

Versão solta (ex.: supabase-js@2) muda sozinha quando sai uma nova; sem `integrity`,
um CDN comprometido entrega o código que quiser com acesso à sessão do usuário.
Ao trocar a versão de uma lib, recalcule o hash:
    curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / 'app'
CDN = re.compile(r'https://(cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com|unpkg\.com|esm\.sh)/')
TAG = re.compile(r'<(script|link)\b[^>]*>', re.I)
VERSAO_SOLTA = re.compile(r'@\d+(\.\d+)?(?=[/"\']|$)')  # @2 ou @2.1, sem o patch


def _tags_externas():
    for html in sorted(APP.glob('*.html')):
        for m in TAG.finditer(html.read_text(encoding='utf-8')):
            tag = m.group(0)
            url = re.search(r'(?:src|href)="([^"]+)"', tag)
            if url and CDN.match(url.group(1)) and 'preconnect' not in tag:
                yield html.name, tag, url.group(1)


def test_libs_de_cdn_tem_versao_exata():
    soltas = [(f, u) for f, _, u in _tags_externas() if VERSAO_SOLTA.search(u)]
    assert not soltas, f'versão solta: {soltas}'


def test_libs_de_cdn_tem_integrity_e_crossorigin():
    faltando = [(f, u) for f, t, u in _tags_externas()
                if 'integrity="sha384-' not in t or 'crossorigin="anonymous"' not in t]
    assert not faltando, f'sem SRI: {faltando}'


def test_cargas_dinamicas_tem_integrity():
    # scripts criados pelo JS (pdf.js, JSZip, Pyodide): o hash fica junto do src
    for nome in ['drone-previa.js', 'drone-obstaculos.js', 'corretivos-pdf.js']:
        js = (APP / nome).read_text(encoding='utf-8')
        assert '.integrity' in js and "'sha384-" in js, nome
        assert "crossOrigin='anonymous'" in js or "crossOrigin = 'anonymous'" in js, nome


def test_o_teste_enxerga_as_paginas():
    assert len(list(_tags_externas())) >= 10
