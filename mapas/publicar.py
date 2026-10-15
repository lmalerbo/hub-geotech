"""Copia para app/py/ os arquivos que o navegador carrega no Pyodide (fonte única: mapas/).
Uso: python mapas/publicar.py [destino]   (padrão: app/py)"""
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVOS = ['mapas/__init__.py', 'mapas/layout.py', 'mapas/corretivo_dados.py', 'mapas/corretivo_pdf.py',
            'drone/assets/logo-pedra.png',
            'mapas/fontes/selawk.ttf', 'mapas/fontes/selawksb.ttf', 'mapas/fontes/selawkb.ttf']


def publicar(destino) -> None:
    destino = Path(destino)
    for rel in ARQUIVOS:
        alvo = destino / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / rel, alvo)
    (destino / 'manifest.json').write_text(json.dumps({'arquivos': ARQUIVOS}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    publicar(sys.argv[1] if len(sys.argv) > 1 else RAIZ / 'app' / 'py')
