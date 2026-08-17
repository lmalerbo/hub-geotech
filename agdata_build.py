"""
Gera arquivos .agf (formato AgData -- AgroCAD/Tecgraf, compativel com
equipamentos Trimble/CASE PTx) a partir de paths de linhas (lon, lat em graus).

Formato decifrado (ver agdata_decrypt.py para o achado da chave):
    .agf = ZIP { manifest.xml (claro) + <uuid>.xml.gz.enc (AES-128-CBC) }

    XML interno:
        <field uuid="..." isDeleted="false">
          <name>...</name><modified>ISO8601</modified><time>epoch</time>
          <origin>base64: geometria tipo Point</origin>
          <client>...</client><farm>...</farm>
          <landmarks>
            <line uuid="..." isDeleted="false">
              <modified>ISO8601</modified><time>epoch</time>
              <name>Line</name><category>GENERIC</category>
              <geometry>base64: geometria tipo LineString</geometry>
            </line>
            ...
          </landmarks>
        </field>

    Geometria (antes do base64):
        Point:      1 byte tipo(0x00) + 24 bytes (X,Y,Z doubles ECEF WGS84)
        LineString: 1 byte tipo(0x01) + 4 bytes contagem(int32 LE)
                    + N * 24 bytes (X,Y,Z doubles ECEF WGS84, altura=0)

    Chave AES = bytes(uuid sem hifens) XOR bytes.fromhex(CONSTANTE_XOR)
    IV = aleatorio por arquivo, guardado em claro no manifest.
"""

import base64
import gzip
import os
import struct
import uuid as uuid_mod
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from pyproj import Transformer

CONSTANTE_XOR = bytes.fromhex("e989715d4caa119b5fc8eac3ac46b7c3")
EPOCH_ISO = "1970-01-01T00:00:00.000Z"

_para_ecef = Transformer.from_crs("EPSG:4979", "EPSG:4978", always_xy=True)


def _ponto_ecef(lon: float, lat: float, h: float = 0.0) -> bytes:
    x, y, z = _para_ecef.transform(lon, lat, h)
    return struct.pack("<3d", x, y, z)


def _geometria_point(lon: float, lat: float) -> bytes:
    return b"\x00" + _ponto_ecef(lon, lat)


def _geometria_linestring(pontos: list[tuple[float, float]]) -> bytes:
    corpo = b"".join(_ponto_ecef(lon, lat) for lon, lat in pontos)
    return b"\x01" + struct.pack("<i", len(pontos)) + corpo


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_field_xml(field_uuid: str, nome: str, client_name: str, farm_name: str,
                     paths: list[list[tuple[float, float]]]) -> str:
    now_iso = _agora_iso()
    origin_lon, origin_lat = paths[0][0]
    origin_b64 = base64.b64encode(_geometria_point(origin_lon, origin_lat)).decode("ascii")

    linhas_xml = []
    for path in paths:
        line_uuid = str(uuid_mod.uuid4())
        geom_b64 = base64.b64encode(_geometria_linestring(path)).decode("ascii")
        linhas_xml.append(
            f'<line uuid="{line_uuid}" isDeleted="false">'
            f"<modified>{now_iso}</modified><time>{EPOCH_ISO}</time>"
            f"<name>Line</name><category>GENERIC</category>"
            f"<geometry>{geom_b64}</geometry></line>"
        )

    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<field uuid="{field_uuid}" isDeleted="false">'
        f"<name>{escape(nome)}</name>"
        f"<modified>{now_iso}</modified><time>{EPOCH_ISO}</time>"
        f"<origin>{origin_b64}</origin>"
        f"<client>{escape(client_name)}</client>"
        f"<farm>{escape(farm_name)}</farm>"
        "<landmarks>" + "".join(linhas_xml) + "</landmarks>"
        "</field>"
    )


def build_agf(field_uuid: str, nome: str, client_name: str, farm_name: str,
              paths: list[list[tuple[float, float]]]) -> bytes:
    xml = build_field_xml(field_uuid, nome, client_name, farm_name, paths).encode("utf-8")
    comprimido = gzip.compress(xml)

    uuid_bytes = bytes.fromhex(field_uuid.replace("-", ""))
    chave = bytes(a ^ b for a, b in zip(uuid_bytes, CONSTANTE_XOR))
    iv = os.urandom(16)

    cipher = AES.new(chave, AES.MODE_CBC, iv)
    cifrado = cipher.encrypt(pad(comprimido, AES.block_size))

    entry_name = f"{field_uuid}.xml.gz.enc"
    manifest = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f"<manifest><name>{escape(nome)}</name><uuid>{field_uuid}</uuid><source />"
        f"<key><version>0</version><iv>{iv.hex()}</iv></key>"
        f"<entries><entry>{entry_name}</entry></entries></manifest>"
    )

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.xml", manifest)
        z.writestr(entry_name, cifrado)
    return buf.getvalue()


if __name__ == "__main__":
    import json
    import sys

    sys.path.insert(0, ".")
    from agdata_decrypt import decifrar_agf

    # valida ida-e-volta: decifra o .agf real, extrai os paths de uma linha,
    # gera um .agf novo com os mesmos dados e confere se decifra igual
    real_path = (
        "referencia_jd_samples/agrocad_real/AgData/Fields/"
        "29770e8c-2d8e-4699-beda-f0e26f6730f4.agf"
    )
    xml_real = decifrar_agf(real_path).decode("utf-8")

    import re
    # <origin> nao usa a tag <geometry>, entao aqui ja sao todas as linhas reais
    linhas_geom = re.findall(r"<geometry>([^<]+)</geometry>", xml_real)
    transformer_inv = Transformer.from_crs("EPSG:4978", "EPSG:4979", always_xy=True)

    paths = []
    for geom_b64 in linhas_geom[:5]:
        blob = base64.b64decode(geom_b64)
        count = struct.unpack("<i", blob[1:5])[0]
        resto = blob[5:]
        pontos = []
        for i in range(count):
            off = i * 24
            x, y, z = struct.unpack("<3d", resto[off:off + 24])
            lon, lat, h = transformer_inv.transform(x, y, z)
            pontos.append((lon, lat))
        paths.append(pontos)

    novo_uuid = str(uuid_mod.uuid4())
    agf_bytes = build_agf(novo_uuid, "TesteRoundtrip", "US PEDRA", "10738 1L", paths)

    out_path = Path("linhas-vant") / f"{novo_uuid}.agf"
    out_path.write_bytes(agf_bytes)
    print(f"Gerado: {out_path} ({len(agf_bytes)} bytes)")

    xml_novo = decifrar_agf(out_path).decode("utf-8")
    novas_geoms = re.findall(r"<geometry>([^<]+)</geometry>", xml_novo)

    erro_max = 0.0
    for path_orig, geom_b64 in zip(paths, novas_geoms):
        blob = base64.b64decode(geom_b64)
        count = struct.unpack("<i", blob[1:5])[0]
        resto = blob[5:]
        for i in range(count):
            off = i * 24
            x, y, z = struct.unpack("<3d", resto[off:off + 24])
            lon, lat, h = transformer_inv.transform(x, y, z)
            dlon = abs(lon - path_orig[i][0])
            dlat = abs(lat - path_orig[i][1])
            erro_max = max(erro_max, dlon, dlat)

    print(f"Erro maximo (graus) apos ida-e-volta: {erro_max:.2e}")
