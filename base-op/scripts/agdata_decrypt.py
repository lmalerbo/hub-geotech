"""
Decifra arquivos .agf (formato AgData, usado por AgroCAD/Tecgraf e compativel
com equipamentos Trimble/CASE PTx).

Achado via pesquisa publica (discussoes de desenvolvedores sobre o formato
AgData da Trimble): cada .agf e um ZIP com manifest.xml (em claro) + um
<uuid>.xml.gz.enc (AES-128-CBC). A chave e derivada do proprio uuid do
manifest (sem hifens) via XOR com uma constante fixa; o IV vem no manifest.

    key = bytes(uuid_sem_hifens) XOR bytes.fromhex("e989715d4caa119b5fc8eac3ac46b7c3")
    iv  = bytes.fromhex(<iv do manifest>)
    xml = gunzip(AES_CBC_decrypt(key, iv, <uuid>.xml.gz.enc))
"""

import gzip
import re
import zipfile
from pathlib import Path

from Crypto.Cipher import AES

CONSTANTE_XOR = bytes.fromhex("e989715d4caa119b5fc8eac3ac46b7c3")


def decifrar_agf(caminho: str | Path) -> bytes:
    """Retorna o XML descomprimido (bytes) de dentro de um .agf."""
    z = zipfile.ZipFile(caminho)
    manifest = z.read("manifest.xml").decode("utf-8")

    uuid = re.search(r"<uuid>([^<]+)</uuid>", manifest).group(1)
    iv_hex = re.search(r"<iv>([^<]+)</iv>", manifest).group(1)
    entry_name = re.search(r"<entry>([^<]+)</entry>", manifest).group(1)

    uuid_bytes = bytes.fromhex(uuid.replace("-", ""))
    key = bytes(a ^ b for a, b in zip(uuid_bytes, CONSTANTE_XOR))
    iv = bytes.fromhex(iv_hex)

    dados_cifrados = z.read(entry_name)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decifrado = cipher.decrypt(dados_cifrados)

    pad_len = decifrado[-1]
    if 1 <= pad_len <= 16:
        decifrado = decifrado[:-pad_len]

    return gzip.decompress(decifrado)


if __name__ == "__main__":
    import sys

    caminho = sys.argv[1] if len(sys.argv) > 1 else (
        "referencia_jd_samples/agrocad_real/AgData/Fields/"
        "29770e8c-2d8e-4699-beda-f0e26f6730f4.agf"
    )
    xml = decifrar_agf(caminho)
    out = Path(caminho).with_suffix(".decifrado.xml")
    out.write_bytes(xml)
    print(f"Decifrado: {len(xml)} bytes -> {out}")
