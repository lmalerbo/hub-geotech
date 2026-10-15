import json

from mapas.publicar import ARQUIVOS, publicar


def test_publicar_copia_e_gera_manifesto(tmp_path):
    publicar(tmp_path)
    manifesto = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    assert manifesto['arquivos'] == ARQUIVOS
    for rel in ARQUIVOS:
        assert (tmp_path / rel).is_file(), rel
    assert 'drone/mapa_pdf.py' not in ARQUIVOS          # o navegador não precisa do código do Drone
