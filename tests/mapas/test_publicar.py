import json
from pathlib import Path

from mapas.publicar import ARQUIVOS, publicar


def test_publicar_copia_e_gera_manifesto(tmp_path):
    publicar(tmp_path)
    manifesto = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    assert manifesto['arquivos'] == ARQUIVOS
    for rel in ARQUIVOS:
        assert (tmp_path / rel).is_file(), rel
    assert 'drone/mapa_pdf.py' not in ARQUIVOS          # o navegador não precisa do código do Drone


def test_manifesto_separa_os_modulos(tmp_path):
    publicar(tmp_path)
    modulos = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))['modulos']
    assert modulos['paralelismo'] and all(rel.startswith('paralelismo/') for rel in modulos['paralelismo'])
    assert 'mapas/corretivo_pdf.py' in modulos['corretivos']
    assert not any(rel.startswith('paralelismo/') for rel in modulos['corretivos'])
    assert sorted(modulos['corretivos'] + modulos['paralelismo']) == sorted(ARQUIVOS)


def test_corretivos_baixa_so_o_modulo_dele():
    pdf = (Path(__file__).resolve().parents[2] / 'app' / 'corretivos-pdf.js').read_text(encoding='utf-8')
    assert 'modulos.corretivos' in pdf
