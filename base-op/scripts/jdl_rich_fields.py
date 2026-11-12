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


def _zigzag(v: int) -> int:
    return (v >> 1) ^ -(v & 1)


def ticks_item_rico(field9_bytes: bytes) -> list[tuple[float, float]]:
    """Trajetoria tick a tick (0,2s, ~150 por registro de 30s) em graus decimais.

    Campos 1/2 do item rico = lat/lon base em nanograus; campos 12/13 = deltas
    zigzag (nanograus) de lat/lon, um por tick. lat_k = campo1 + soma dos k
    primeiros deltas. Validado contra o export do GOIMP da fazenda 10233: o
    ultimo tick de um registro coincide (0,0cm) com a base do seguinte, e os
    ticks ficam a ~9cm (mediana) da trilha do AgroCAD (que tem passo de ~30cm).
    A base nao entra na lista: ela e o ultimo tick do registro anterior."""
    top = decode_flat(field9_bytes, 0, len(field9_bytes))
    for fn, wire, val in top:
        if fn != 3 or wire != "bytes":
            continue
        sub = {f: v for f, w, v in decode_flat(val, 0, len(val))}
        if not (isinstance(sub.get(4), float) and 300_000 < sub[4] < 2_000_000):
            continue
        if not (isinstance(sub.get(1), float) and isinstance(sub.get(2), float)
                and isinstance(sub.get(12), bytes) and isinstance(sub.get(13), bytes)):
            return []
        dlat, dlon = [], []
        for arr, dst in ((sub[12], dlat), (sub[13], dlon)):
            p = 0
            while p < len(arr):
                v, p = read_varint(arr, p)
                dst.append(_zigzag(v))
        if len(dlat) != len(dlon):
            return []
        lat, lon = sub[1], sub[2]
        ticks = []
        for a, b in zip(dlat, dlon):
            lat += a
            lon += b
            ticks.append((lat / 1e9, lon / 1e9))
        return ticks
    return []


def estado_trabalho(field9_bytes: bytes) -> int | None:
    """Estado 0/1 do registro: item {3, 12} (sem campo 4) cujo campo 3 e a
    mensagem 0a 01 XX. Nao e o WorkStatus da plantadeira (no 10658 acerta ~78%
    contra o executado do AgroCAD; parece ser piloto automatico engatado), mas
    ajuda a separar plantio de deslocamento. None se o item nao vier."""
    estado = None
    for fn, wire, val in decode_flat(field9_bytes, 0, len(field9_bytes)):
        if fn != 3 or wire != "bytes":
            continue
        sub = {f: v for f, w, v in decode_flat(val, 0, len(val))}
        v3 = sub.get(3)
        if 4 not in sub and 12 in sub and isinstance(v3, bytes) and len(v3) == 3 and v3[:2] == b"\x0a\x01":
            estado = v3[2]
    return estado


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
