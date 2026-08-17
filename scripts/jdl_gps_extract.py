"""
Extrai pontos GPS (latitude, longitude) + atributos de arquivos .jdl (JDLink).

Descoberto nesta sessao (farm 10454, Usina da Pedra): cada arquivo .jdl tem
uma sequencia de registros top-level (field 4), e cada registro contem:
    field 6 (submensagem de 18 bytes) = ponto GPS confiavel:
        field 1 (double) = latitude
        field 2 (double) = longitude
    field 9 (bloco grande) = telemetria; dentro dele, um "item rico" com
        elevacao aproximada + outros campos numericos ainda nao identificados
        (ver jdl_rich_fields.py)

Validado contra um ponto real mostrado no AgroCAD (farm 10454Rev0, Parte 1):
Latitude=-21.1688 Longitude=-47.6935 Elevation=597.9894 -- a extracao bateu
com esses valores (lat/lon com <2m de diferenca, elevacao ~0.09m).

Uso:
    python jdl_gps_extract.py <arquivo_ou_pasta.jdl> [--out saida.csv]
"""
import argparse
import glob
import os
import re
import struct
from datetime import datetime, timedelta

from jdl_rich_fields import read_varint, decode_flat, extrair_atributos_extra

CAMPOS_EXTRA_NOMES = ["TEMPO_MS", "DATA_HORA", "ELEVATION_APROX"] + \
    [f"CAMPO_{n}" for n in (3, 5, 8, 9, 23, 24, 25, 27, 28)]

# nome do arquivo: 2026_05_06_[07_26]_{guid}.jdl -- [HH_MM] e o horario de
# inicio do "upload"/sessao; o campo 4 do registro top-level e o tempo
# decorrido em milissegundos desde esse inicio (confirmado: sobe de forma
# monotonica e bate com o delta do campo 5 vizinho, ~30s entre amostras)
RE_NOME_ARQUIVO = re.compile(r"(\d{4})_(\d{2})_(\d{2})_\[(\d{2})_(\d{2})\]")


def horario_base_do_nome(nome_arquivo: str) -> datetime | None:
    m = RE_NOME_ARQUIVO.match(nome_arquivo)
    if not m:
        return None
    ano, mes, dia, hora, minuto = (int(x) for x in m.groups())
    return datetime(ano, mes, dia, hora, minuto)


def _decode_registro4(conteudo: bytes) -> dict | None:
    """Decodifica o conteudo de um registro top-level (field 4) e retorna
    lat/lon (do field 6) + tempo decorrido (field 4) + atributos extras (do
    field 9), ou None se nao tiver um ponto GPS valido."""
    campos = decode_flat(conteudo, 0, len(conteudo))
    lat = lon = None
    tempo_ms = None
    extras = {}
    for fn, wire, val in campos:
        if fn == 4 and wire == "varint":
            tempo_ms = val
        elif fn == 6 and wire == "bytes":
            sub = decode_flat(val, 0, len(val))
            sub_d = {f: v for f, w, v in sub if w == "f64"}
            if 1 in sub_d and 2 in sub_d:
                lat, lon = sub_d[1], sub_d[2]
        elif fn == 9 and wire == "bytes":
            extras = extrair_atributos_extra(val)
    if lat is None or lon is None:
        return None
    if not (-35.0 < lat < -5.0 and -75.0 < lon < -30.0):  # sanity check Brasil
        return None
    registro = {"latitude": lat, "longitude": lon, "TEMPO_MS": tempo_ms}
    registro.update(extras)
    return registro


def extrair_pontos(buf: bytes) -> list[tuple[int, dict]]:
    """Retorna lista de (offset, registro) achados no buffer, andando pelos
    campos top-level e decodificando cada ocorrencia do field 4."""
    pontos = []
    pos = 0
    n = len(buf)
    while pos < n:
        tag_start = pos
        try:
            tag, pos = read_varint(buf, pos)
        except IndexError:
            break
        field_no = tag >> 3
        wire_type = tag & 0x7
        if wire_type == 0:
            _, pos = read_varint(buf, pos)
        elif wire_type == 1:
            pos += 8
        elif wire_type == 5:
            pos += 4
        elif wire_type == 2:
            try:
                length, pos = read_varint(buf, pos)
            except IndexError:
                break
            data = buf[pos:pos + length]
            pos += length
            if field_no == 4:
                registro = _decode_registro4(data)
                if registro is not None:
                    pontos.append((tag_start, registro))
        else:
            break
    return pontos


def extrair_de_arquivo(caminho: str) -> list[tuple[int, dict]]:
    with open(caminho, "rb") as f:
        buf = f.read()
    try:
        pontos = extrair_pontos(buf)
    except (IndexError, struct.error):
        # arquivo truncado/corrompido -- pula em vez de derrubar o lote inteiro
        return []

    base = horario_base_do_nome(os.path.basename(caminho))
    if base is not None:
        for _, reg in pontos:
            tempo_ms = reg.get("TEMPO_MS")
            # sanity check: descarta valor absurdo (registro corrompido/desalinhado) --
            # uma sessao de ate ~7 dias (604800000 ms) e um limite generoso
            if tempo_ms is not None and 0 <= tempo_ms <= 604_800_000:
                try:
                    reg["DATA_HORA"] = (base + timedelta(milliseconds=tempo_ms)).isoformat(sep=" ")
                except OverflowError:
                    pass
    return pontos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada", help="arquivo .jdl ou pasta com .jdl")
    ap.add_argument("--out", default=None, help="CSV de saida (opcional)")
    args = ap.parse_args()

    if os.path.isdir(args.entrada):
        arquivos = sorted(glob.glob(os.path.join(args.entrada, "**", "*.jdl"), recursive=True))
    else:
        arquivos = [args.entrada]

    cabecalho = ["arquivo", "offset", "latitude", "longitude"] + CAMPOS_EXTRA_NOMES
    linhas_csv = [",".join(cabecalho)]
    total = 0
    for caminho in arquivos:
        pontos = extrair_de_arquivo(caminho)
        total += len(pontos)
        nome = os.path.basename(caminho)
        print(f"{nome}: {len(pontos)} pontos")
        for off, reg in pontos:
            valores = [nome, str(off), str(reg["latitude"]), str(reg["longitude"])]
            valores += [str(reg.get(c, "")) for c in CAMPOS_EXTRA_NOMES]
            linhas_csv.append(",".join(valores))

    print(f"\ntotal de pontos extraidos: {total}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas_csv))
        print(f"CSV salvo em: {args.out}")


if __name__ == "__main__":
    main()
