"""
Pontos de PLANTIO do .jdl do jeito que o GOIMP do AgroCAD importa.

O GOIMP mostra, pra cada sessao, duas "documentacoes" com o mesmo horario:
(PLANTIO) e (POS_MAQUINA). A trilha tick a tick do item rico
(jdl_rich_fields.ticks_item_rico) e a posicao da maquina; o PLANTIO vem de
outro item do campo 9, o de documentacao do implemento:

  {1, 2: lat/lon (nanograus) da ponta A da faixa; 3, 4: ponta B (3,000 m da A);
   11; 12: instante (ms desde o inicio do arquivo) do 1o ponto;
   15: deltas zigzag de tempo (~200 ms); 16: zeros;
   17, 18: deltas zigzag lat/lon da ponta A; 19, 20: idem ponta B}

O ponto que o GOIMP grava e o meio da faixa (A+B)/2 -- bate 0,000 m com o
export da 10233 (10233-pontos.shp), 100% dos pontos.

Esse fluxo tambem tem trecho fora de trabalho. O que o GOIMP descarta vem do
canal booleano de estado de trabalho, item {1, 2, 3, 12}: campo 1 = deltas
zigzag dos instantes de troca, campo 2 = estado antes da 1a troca, campo 3 =
estado depois da ultima, campo 12 = instante da ultima troca (os dois de campo
2/3 como mensagem 0a 01 XX). Usando so (campo 12, campo 3) de cada registro
como linha do tempo, o ponto de documentacao com estado 1 no seu instante
reproduz a escolha do GOIMP em 97% dos pontos da 10233 (65.157 de 66.326
exportados mantidos; 2.235 a mais).
"""
import bisect
import struct


# Copiado de jdl_rich_fields.py (base-op).
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

LIMITE_TEMPO_MS = 2 ** 40  # acima disso o campo 12 veio corrompido


def _varints(b: bytes) -> list[int]:
    out, p = [], 0
    while p < len(b):
        v, p = read_varint(b, p)
        out.append(v)
    return out


def _cumsum_zigzag(b: bytes) -> list[int]:
    acc, out = 0, []
    for v in _varints(b):
        acc += _zigzag(v)
        out.append(acc)
    return out


def _registros(buf: bytes):
    pos, n = 0, len(buf)
    while pos < n:
        tag, pos = read_varint(buf, pos)
        field_no, wire_type = tag >> 3, tag & 0x7
        if wire_type == 0:
            _, pos = read_varint(buf, pos)
        elif wire_type == 1:
            pos += 8
        elif wire_type == 5:
            pos += 4
        elif wire_type == 2:
            length, pos = read_varint(buf, pos)
            data = buf[pos:pos + length]
            pos += length
            if field_no == 4:
                yield data
        else:
            return


def _e_documentacao(s: dict) -> bool:
    return (all(isinstance(s.get(k), float) for k in (1, 2, 3, 4))
            and -35e9 < s[1] < -5e9 and -35e9 < s[3] < -5e9
            and isinstance(s.get(12), int) and s[12] < LIMITE_TEMPO_MS
            and all(isinstance(s.get(k), bytes) for k in (15, 17, 18, 19, 20)))


def _e_estado_trabalho(s: dict) -> bool:
    v3 = s.get(3)
    return (sorted(s) == [1, 2, 3, 12] and isinstance(v3, bytes) and len(v3) == 3
            and v3[:2] == b"\x0a\x01" and isinstance(s.get(12), int) and s[12] < LIMITE_TEMPO_MS)


def ler_documentacao(caminho: str) -> tuple[list[tuple[int, float, float]], list[tuple[int, int]]]:
    """Retorna (pontos, eventos): pontos = [(instante_ms, lat, lon)] do meio
    da faixa do implemento; eventos = [(instante_ms, estado)] do canal de
    estado de trabalho. Arquivo corrompido devolve o que deu pra ler."""
    with open(caminho, "rb") as f:
        buf = f.read()
    pontos, eventos = [], []
    try:
        for reg in _registros(buf):
            for fn, wire, val in decode_flat(reg, 0, len(reg)):
                if fn != 9 or wire != "bytes":
                    continue
                for f2, w2, v2 in decode_flat(val, 0, len(val)):
                    if f2 != 3 or w2 != "bytes":
                        continue
                    s = {a: b for a, _, b in decode_flat(v2, 0, len(v2))}
                    if _e_estado_trabalho(s):
                        eventos.append((s[12], s[3][2]))
                    elif _e_documentacao(s):
                        tempos = _cumsum_zigzag(s[15])
                        a_lat, a_lon, b_lat, b_lon = (_cumsum_zigzag(s[k]) for k in (17, 18, 19, 20))
                        n = min(len(tempos), len(a_lat), len(a_lon), len(b_lat), len(b_lon))
                        for k in range(n):
                            lat = (s[1] + a_lat[k] + s[3] + b_lat[k]) / 2e9
                            lon = (s[2] + a_lon[k] + s[4] + b_lon[k]) / 2e9
                            pontos.append((s[12] + tempos[k], lat, lon))
    except (IndexError, struct.error, OverflowError):
        pass
    return pontos, eventos


def ler_trilha_trator(caminho: str) -> list[tuple[int, float, float]]:
    """[(instante_ms, lat, lon)] da trilha tick a tick da maquina (item rico,
    POS_MAQUINA): o campo 4 do registro e o INICIO do bloco e os ticks vem a
    cada campo5/n ms (~200 ms) depois dele. Conferido contra o fluxo de
    documentacao (10233 e 10819): com isso o trator passa no ponto do
    implemento ~2,5 s antes dele -- a distancia trator-implemento na
    plantadeira -- em vez dos ~32 s de defasagem da hipotese "campo 4 = fim"."""
    with open(caminho, "rb") as f:
        buf = f.read()
    pontos = []
    try:
        for reg in _registros(buf):
            campos = decode_flat(reg, 0, len(reg))
            topo = {fn: val for fn, wire, val in campos if wire != "bytes"}
            inicio = topo.get(4)
            if not isinstance(inicio, int) or not 0 <= inicio < LIMITE_TEMPO_MS:
                continue
            for fn, wire, val in campos:
                if fn == 9 and wire == "bytes":
                    ticks = ticks_item_rico(val)
                    passo = (topo.get(5) or 30000) / len(ticks) if ticks else 0
                    for k, (lat, lon) in enumerate(ticks):
                        pontos.append((round(inicio + passo * (k + 1)), lat, lon))
    except (IndexError, struct.error, OverflowError):
        pass
    return pontos


def _filtrar_por_estado(pontos, eventos) -> list[tuple[float, float]]:
    eventos = sorted(set(eventos))
    tempos = [t for t, _ in eventos]
    saida = []
    for t, lat, lon in sorted(set(pontos)):
        i = bisect.bisect_right(tempos, t) - 1
        if i >= 0 and eventos[i][1] == 1:
            saida.append((lat, lon))
    return saida


def pontos_trator(caminho: str) -> list[tuple[float, float]]:
    """(lat, lon) da trilha do trator (antena, a cada 0,2 s) so nos instantes
    com o estado de trabalho do implemento ligado -- mesmo recorte do
    (PLANTIO) do GOIMP, mas na posicao do trator em vez da do implemento."""
    _, eventos = ler_documentacao(caminho)
    return _filtrar_por_estado(ler_trilha_trator(caminho), eventos)


def pontos_plantio(caminho: str) -> list[tuple[float, float]]:
    """(lat, lon) dos pontos de documentacao com estado de trabalho = 1 no
    instante do ponto (antes do 1o evento conta como 0), em ordem de tempo
    (o fluxo de documentacao as vezes chega atrasado em relacao ao registro)."""
    pontos, eventos = ler_documentacao(caminho)
    return _filtrar_por_estado(pontos, eventos)


def ler_jdl(caminho: str) -> tuple[list[tuple[float, float]], int]:
    """(pontos (lat, lon) da trilha do trator com trabalho ligado, total de
    ticks da trilha). O total serve para o aviso de frota sem trabalho."""
    try:
        trilha = ler_trilha_trator(caminho)
        _, eventos = ler_documentacao(caminho)
    except OSError:
        return [], 0
    return _filtrar_por_estado(trilha, eventos), len(trilha)
