"""
Executado de plantio do monitor GS3_2630 (RCD\\EIC\\Documentation\\<hex>\\<uuid>.fdl + .fdd).

.fdl = XML (RCDLogFile): setup da sessao (Farm/Field com nome -- e dai que
sai a fazenda, mesmo quando o setup.fds atual do monitor ja nao tem o
campo), definicao das colunas e a lista de LogDataBlock EvenByteDelta com o
filePosition de cada bloco dentro do .fdd.

.fdd = binario. Cada bloco comeca com um catalogo de colunas:
    [u16 1][u16 len][guid] ... [u16 ncol] e por coluna:
    [u16 tipo][u16 nlen+3][u16 nlen][nome][u8 flag] e
      tipo 1 (enum): [u16 qtd][u16 total][(u16 len, nome) x qtd]
      outros:        [u16 24][3 doubles: resolucao, delta maximo, valor inicial]
Depois vem a sequencia de registros, cada um com:
    marcador 02 00 XX 02 00 70 00
    u32 mascara A, u32 mascara B (1 bit por coluna, na ordem do catalogo)
    deltas inteiros das colunas com flag 0 que NAO estao em nenhuma das
      mascaras, na ordem do catalogo: tipo 4 -> int32, tipo 3 -> int16
      (valor = anterior + delta * resolucao)
    campos extras [u16 tipo][u16 len][dados]: o 1o (tipo 3, 4 bytes) vem
      sempre; os demais sao, na ordem, as colunas com bit ligado na mascara B,
      com valor absoluto (enum -> int16 com o indice do nome; numerico ->
      double, que substitui o acumulado).
Validado: as duas antenas ficam a 5,203 m constantes em 5.730 registros, e o
fim de um bloco bate (8 cm) com o valor inicial do bloco seguinte.

NavigationReference: *_5140 = GPS do trator; *_5141 = ponto calculado do
implemento (dtiComputedImplement) -- e esse que vira o executado, como o
ponto do meio da plantadeira no .jdl (jdl_documentacao.py). Section*_State
(dtiRecordingStatusOn/Off) e o liga/desliga da gravacao.
"""
import os
import re
import struct

COL_LAT = "GPSLatitude_5141"
COL_LON = "GPSLongitude_5141"
MARCADOR = re.compile(rb"\x02\x00[\x00-\x0f]\x02\x00\x70\x00")
LARGURA = {4: ("i", 4), 3: ("h", 2)}


def _u16(buf: bytes, p: int) -> int:
    return struct.unpack_from("<H", buf, p)[0]


def _coluna_valida(buf: bytes, p: int) -> bool:
    if p + 6 > len(buf):
        return False
    tipo, elen, nlen = _u16(buf, p), _u16(buf, p + 2), _u16(buf, p + 4)
    if not (0 < nlen < 64 and elen == nlen + 3 and tipo < 16):
        return False
    return all(48 <= c < 123 or c == 95 for c in buf[p + 6:p + 6 + nlen])


def ler_catalogo(buf: bytes, inicio: int, fim: int | None = None) -> tuple[list[dict], int]:
    """Procura o catalogo de colunas a partir de `inicio`, sem passar de `fim`
    (bloco truncado ou vazio -- ex.: .fdd cortado no pen-drive -- levanta
    ValueError em vez de varrer pra sempre)."""
    fim = len(buf) if fim is None else min(fim, len(buf))
    p = inicio
    while not _coluna_valida(buf, p):
        p += 1
        if p + 6 > fim:
            raise ValueError("bloco sem catalogo de colunas")
    ncol = _u16(buf, p - 2)
    cols = []
    for _ in range(ncol):
        tipo, nlen = _u16(buf, p), _u16(buf, p + 4)
        nome = buf[p + 6:p + 6 + nlen].decode("latin-1")
        q = p + 6 + nlen
        flag = buf[q]
        if tipo == 1:
            qtd, total = _u16(buf, q + 1), _u16(buf, q + 3)
            r, nomes = q + 5, []
            for _ in range(qtd):
                ln = _u16(buf, r)
                nomes.append(buf[r + 2:r + 2 + ln].decode("latin-1"))
                r += 2 + ln
            cols.append({"tipo": tipo, "nome": nome, "flag": flag, "enum": nomes})
            p = q + 5 + total
        else:
            blen = _u16(buf, q + 1)
            blob = buf[q + 3:q + 3 + blen]
            res, maxd, ini = struct.unpack("<3d", blob) if blen == 24 else (0.0, 0.0, 0.0)
            cols.append({"tipo": tipo, "nome": nome, "flag": flag, "res": res, "ini": ini})
            p = q + 3 + blen
    return cols, p


def decodificar_bloco(buf: bytes, inicio: int, fim: int) -> list[dict]:
    """Lista de registros {coluna: valor} (valores numericos ja acumulados e
    escalados; enums como nome; colunas sem novidade repetem o anterior)."""
    cols, p = ler_catalogo(buf, inicio, fim)
    delta_cols = [i for i, c in enumerate(cols) if c["flag"] == 0 and c["tipo"] in LARGURA]
    atual = {c["nome"]: c["ini"] for c in cols if c["tipo"] != 1}
    atual.update({c["nome"]: None for c in cols if c["tipo"] == 1})
    posicoes = [m.start() for m in MARCADOR.finditer(buf, p, fim)] + [fim]
    registros = []
    for a, b in zip(posicoes, posicoes[1:]):
        r = buf[a + 7:b]
        if len(r) < 8:
            continue
        mascara_a, mascara_b = struct.unpack_from("<II", r, 0)
        # colunas citadas numa das mascaras nao vem no bloco de deltas: as da
        # B vem com valor absoluto nos extras, as da A nao mudaram
        presentes = [i for i in delta_cols if not ((mascara_a | mascara_b) >> i & 1)]
        fmt = "<" + "".join(LARGURA[cols[i]["tipo"]][0] for i in presentes)
        tam = struct.calcsize(fmt)
        if len(r) < 8 + tam:
            continue
        deltas = struct.unpack_from(fmt, r, 8)
        q, extras = 8 + tam, []
        while q + 4 <= len(r):
            t, ln = struct.unpack_from("<HH", r, q)
            extras.append((t, r[q + 4:q + 4 + ln]))
            q += 4 + ln
        bits = [i for i in range(len(cols)) if mascara_b >> i & 1]
        if len(extras) == len(bits) + 1:
            extras = extras[1:]
        for i, (t, dados) in zip(bits, extras):
            c = cols[i]
            if c["tipo"] == 1 and len(dados) == 2:
                k = struct.unpack("<h", dados)[0]
                atual[c["nome"]] = c["enum"][k] if 0 <= k < len(c["enum"]) else None
            elif len(dados) == 8:
                atual[c["nome"]] = struct.unpack("<d", dados)[0]
        for i, d in zip(presentes, deltas):
            atual[cols[i]["nome"]] += d * cols[i]["res"]
        registros.append(dict(atual))
    return registros


def ler_sessao(caminho_fdl: str) -> dict:
    """{'fazenda', 'talhao', 'inicio' (ISO, UTC), 'registros'} de uma sessao .fdl/.fdd."""
    x = open(caminho_fdl, encoding="latin-1").read()
    campo = re.search(r'<FieldRef eridRef="([^"]+)"', x)
    talhoes = dict(re.findall(r'<rcdsetup:Field [^>]*erid="([^"]+)" name="([^"]*)"', x))
    fazendas = dict(re.findall(r'<rcdsetup:Farm [^>]*erid="([^"]+)" name="([^"]*)"', x))
    talhao_fazenda = dict(re.findall(r'<rcdsetup:Field [^>]*erid="([^"]+)"[^>]*farmRef="([^"]+)"', x))
    erid = campo.group(1) if campo else None
    posicoes = sorted({int(v) for v in re.findall(r'filePosition="(\d+)"', x)})
    fdd = caminho_fdl[:-4] + ".fdd"
    registros = []
    if posicoes and os.path.exists(fdd):
        buf = open(fdd, "rb").read()
        for a, b in zip(posicoes, posicoes[1:] + [len(buf)]):
            try:
                registros.extend(decodificar_bloco(buf, a, b))
            except (struct.error, IndexError, ValueError):
                continue
    inicio = re.search(r'<LogTaskRegion [^>]*timeStamp="([^"]+)"', x)
    return {"fazenda": fazendas.get(talhao_fazenda.get(erid), ""), "talhao": talhoes.get(erid, ""),
            "inicio": inicio.group(1) if inicio else "", "registros": registros}


def pontos_plantio(sessao: dict, antena: str = "5141") -> list[tuple[float, float]]:
    """(lat, lon) nos registros com gravacao ligada. antena '5141' = ponto do
    implemento (padrao, como o GOIMP); '5140' = antena do trator."""
    col_lat, col_lon = (COL_LAT, COL_LON) if antena == "5141" else (f"GPSLatitude_{antena}", f"GPSLongitude_{antena}")
    saida = []
    for reg in sessao["registros"]:
        estados = [v for k, v in reg.items() if k.startswith("Section") and k.endswith("_State")]
        if any(e == "dtiRecordingStatusOff" for e in estados):
            continue
        lat, lon = reg.get(col_lat), reg.get(col_lon)
        if lat is not None and lon is not None and -35 < lat < -5 and -75 < lon < -30:
            saida.append((lat, lon))
    return saida


def ler_gs3(caminho_fdl: str) -> tuple[list[tuple[float, float]], int]:
    """(pontos (lat, lon) da antena do trator, _5140, com gravação ligada,
    total de registros da sessão). Sem .fdd ou ilegível: ([], 0)."""
    try:
        sessao = ler_sessao(caminho_fdl)
    except (OSError, UnicodeDecodeError):
        return [], 0
    return pontos_plantio(sessao, antena="5140"), len(sessao["registros"])


def gs3_completo(caminho_fdl: str) -> bool:
    """Todo bloco citado no .fdl comeca dentro do .fdd? Corte dentro do ultimo
    bloco nao aparece aqui: o .fdl so traz onde cada bloco comeca."""
    try:
        posicoes = [int(v) for v in re.findall(r'filePosition="(\d+)"', open(caminho_fdl, encoding="latin-1").read())]
        return bool(posicoes) and max(posicoes) < os.path.getsize(caminho_fdl[:-4] + ".fdd")
    except (OSError, UnicodeDecodeError):
        return False
