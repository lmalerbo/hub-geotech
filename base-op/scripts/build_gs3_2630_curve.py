"""
Gera o binario .fdShape (GS3_2630, CurvedTrackLine) a partir de uma lista de
paths (cada path = lista de pontos [lon, lat] em graus, WGS84).

Formato descoberto por engenharia reversa (validado byte-a-byte contra 2
curvas reais da AgroCAD, ~169mil pontos, erro 0.0):

  arquivo = HEADER_GLOBAL(80B) + [BLOCO_PATH]*n_paths + FOOTER(4B)

  HEADER_GLOBAL (80 bytes):
    [0:16]  zero
    [16:18] uint16 LE = 513  (constante/versao, observada em todos os arquivos)
    [18:32] zero
    [32:36] int32 LE = 1     (constante)
    [36:48] zero
    [48:52] int32 LE = 1     (constante)
    [52:56] zero
    [56:64] int64 LE = total de registros de 20B no arquivo (ver calcular_total_registros)
    [64:80] zero

  BLOCO_PATH (por path, N pontos):
    registro0 (cabecalho/ponto0): float32(999.9) + double(lon0-ref_lon) + double(lat0-ref_lat)
    [SE for o PRIMEIRO path do arquivo: repete ponto0 mais uma vez, agora com flag
     normal float32(1.0) em vez do marcador -- observado so no path 0]
    registro[1..N-1]: float32(1.0) + double(lon_i-ref_lon) + double(lat_i-ref_lat)
    registro terminador (= copia do ultimo ponto): float32(1.0) + double + double
      -> presente em todo path, EXCETO o ULTIMO path do arquivo (o footer de
         4 bytes fecha o ultimo path, dispensando terminador ali)

  FOOTER: float32(1.0) (4 bytes)

  ref_lon/ref_lat = primeiro ponto do primeiro path (== vrReferenceLongitude/
  vrReferenceLatitude no SpatialCatalog XML).
"""

import struct

MARCADOR_HEADER = struct.pack("<f", 999.9)
FLAG_PONTO = struct.pack("<f", 1.0)
FOOTER = struct.pack("<f", 1.0)


def _registro(flag_bytes: bytes, lon_delta: float, lat_delta: float) -> bytes:
    return flag_bytes + struct.pack("<d", lon_delta) + struct.pack("<d", lat_delta)


def calcular_total_registros(paths: list[list[tuple[float, float]]]) -> int:
    """Valor declarado no header global (offset 56): total_pontos + total_paths + 1.
    Nao corresponde 1:1 aos registros fisicos de 20 bytes (o ultimo path nao tem
    terminador, compensado pelo footer de 4 bytes) -- e so a formula observada."""
    total_pontos = sum(len(p) for p in paths)
    return total_pontos + len(paths) + 1


def gerar_fdshape(paths: list[list[tuple[float, float]]]) -> bytes:
    """paths: lista de paths, cada path = lista de (lon, lat) em graus."""
    ref_lon, ref_lat = paths[0][0]

    total_registros = calcular_total_registros(paths)

    header_global = bytearray(80)
    struct.pack_into("<H", header_global, 16, 513)
    struct.pack_into("<i", header_global, 32, 1)
    struct.pack_into("<i", header_global, 48, 1)
    struct.pack_into("<q", header_global, 56, total_registros)

    partes = [bytes(header_global)]
    n_paths = len(paths)

    for i, path in enumerate(paths):
        lon0, lat0 = path[0]
        partes.append(_registro(MARCADOR_HEADER, lon0 - ref_lon, lat0 - ref_lat))

        eh_primeiro = i == 0
        eh_ultimo = i == n_paths - 1

        if eh_primeiro:
            partes.append(_registro(FLAG_PONTO, lon0 - ref_lon, lat0 - ref_lat))

        for lon, lat in path[1:]:
            partes.append(_registro(FLAG_PONTO, lon - ref_lon, lat - ref_lat))

        if not eh_ultimo:
            lon_last, lat_last = path[-1]
            partes.append(_registro(FLAG_PONTO, lon_last - ref_lon, lat_last - ref_lat))

    partes.append(FOOTER)
    return b"".join(partes)


if __name__ == "__main__":
    import json
    from pathlib import Path

    gjson_path = Path(
        "referencia_jd_samples/agrocad_real/Gen4/SpatialFiles/"
        "AdaptiveCurve4a530286-c2cc-404b-85d3-946852c4457c.gjson"
    )
    fdshape_real_path = Path(
        "referencia_jd_samples/agrocad_real/GS3_2630/US PEDRA/RCD/EIC/Fields/A2/"
        "dfe2eaa2-8e15-4c45-8317-14a4d627ed44/"
        "CurveTrack1c629809-e94f-40e3-bbeb-c143e9fa8c3c.fdShape"
    )

    g = json.loads(gjson_path.read_text(encoding="utf-8-sig"))
    paths_raw = g["geometry"]["coordinates"]
    paths = [[(p[0], p[1]) for p in path] for path in paths_raw]

    gerado = gerar_fdshape(paths)
    real = fdshape_real_path.read_bytes()

    print(f"gerado: {len(gerado)} bytes | real: {len(real)} bytes")
    if gerado == real:
        print("MATCH BYTE-A-BYTE PERFEITO")
    else:
        n = min(len(gerado), len(real))
        diffs = [i for i in range(n) if gerado[i] != real[i]]
        print(f"diferenca: {len(diffs)} bytes distintos de {n}")
        if diffs:
            primeiro = diffs[0]
            print(f"primeira diferenca no offset {primeiro}")
            print("gerado :", gerado[max(0, primeiro - 8):primeiro + 24].hex())
            print("real   :", real[max(0, primeiro - 8):primeiro + 24].hex())
