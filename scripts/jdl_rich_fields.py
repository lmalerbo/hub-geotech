"""
Decodificador auxiliar pra extrair campos numericos adicionais dos arquivos
.jdl, alem do par latitude/longitude ja validado em jdl_gps_extract.py.

Cada registro top-level (field 4) tem, dentro do seu campo 9 (bloco de
telemetria), um "item rico" com varios campos numericos por amostra --
identificado empiricamente por ter um campo 4 (double) na faixa de altitude
plausivel (300-2000, provavelmente elevacao em metros).

Confirmado nesta sessao (farm 10454): campo 4 desse item bate com a
elevacao mostrada no AgroCAD (597.9 m) para um ponto vizinho.
Os demais campos numericos (3, 5, 8, 9, 23, 24, 25, 27, 28) sao mantidos
como CAMPO_N genericos -- ainda nao identificados com certeza (podem ser
heading, velocidade, roll/pitch, sinal, status etc, mas nao confirmados
individualmente).
"""
import struct

CAMPOS_GENERICOS = (3, 5, 8, 9, 23, 24, 25, 27, 28)


def read_varint(buf: bytes, pos: int):
    result = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def decode_flat(buf: bytes, pos: int, end: int) -> list[tuple[int, str, object]]:
    """Decodifica campos de UM nivel so (nao recursivo)."""
    out = []
    while pos < end:
        tag, pos = read_varint(buf, pos)
        field_no = tag >> 3
        wire_type = tag & 0x7
        if wire_type == 0:
            v, pos = read_varint(buf, pos)
            out.append((field_no, "varint", v))
        elif wire_type == 1:
            v = struct.unpack_from("<d", buf, pos)[0]
            out.append((field_no, "f64", v))
            pos += 8
        elif wire_type == 5:
            v = struct.unpack_from("<f", buf, pos)[0]
            out.append((field_no, "f32", v))
            pos += 4
        elif wire_type == 2:
            length, pos = read_varint(buf, pos)
            data = buf[pos:pos + length]
            pos += length
            out.append((field_no, "bytes", data))
        else:
            break
    return out


def achar_item_rico(field9_bytes: bytes) -> dict | None:
    """Dentro do conteudo do campo 9, acha o item com o campo 4 (elevacao
    aproximada, em escala bruta *1000) presente -- esse e o item que carrega
    os campos extras."""
    top = decode_flat(field9_bytes, 0, len(field9_bytes))
    for fn, wire, val in top:
        if fn == 3 and wire == "bytes":
            sub = {f: v for f, w, v in decode_flat(val, 0, len(val)) if w in ("f64", "f32", "varint")}
            if 4 in sub and isinstance(sub[4], float) and 300_000 < sub[4] < 2_000_000:
                return sub
    return None


def extrair_atributos_extra(field9_bytes: bytes) -> dict:
    """Retorna dict com ELEVATION_APROX (confirmado, faixa plausivel) +
    CAMPO_N genericos (nao identificados) a partir do item rico."""
    item = achar_item_rico(field9_bytes)
    if item is None:
        return {}
    atributos = {"ELEVATION_APROX": item[4] / 1000.0}
    for n in CAMPOS_GENERICOS:
        if n in item:
            atributos[f"CAMPO_{n}"] = item[n]
    return atributos
