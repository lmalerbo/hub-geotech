"""Varre um arquivo .jdl procurando varints que pareçam timestamps Unix (ms),
pra descobrir se arquivos pequenos = 1 heartbeat parado e arquivos grandes =
sessão continua de trabalho (varios timestamps ao longo do tempo)."""
import sys


def read_varint_at(buf, pos, max_bytes=6):
    result = 0
    shift = 0
    p = pos
    for _ in range(max_bytes):
        if p >= len(buf):
            return None, None
        b = buf[p]
        result |= (b & 0x7F) << shift
        p += 1
        if not (b & 0x80):
            return result, p
        shift += 7
    return None, None


def find_timestamps(buf, lo=1_700_000_000_000, hi=1_900_000_000_000):
    hits = []
    pos = 0
    n = len(buf)
    while pos < n:
        val, newpos = read_varint_at(buf, pos)
        if val is not None and lo <= val <= hi:
            hits.append((pos, val))
        pos += 1
    return hits


if __name__ == "__main__":
    path = sys.argv[1]
    buf = open(path, "rb").read()
    hits = find_timestamps(buf)
    print(f"arquivo: {path}")
    print(f"tamanho: {len(buf)} bytes")
    print(f"timestamps candidatos encontrados: {len(hits)}")
    vals = sorted(set(v for _, v in hits))
    if vals:
        import datetime
        t0 = datetime.datetime.utcfromtimestamp(vals[0] / 1000)
        t1 = datetime.datetime.utcfromtimestamp(vals[-1] / 1000)
        print(f"min: {vals[0]} ({t0} UTC)")
        print(f"max: {vals[-1]} ({t1} UTC)")
        print(f"duracao: {(vals[-1]-vals[0])/1000/60:.1f} min")
        print(f"valores distintos: {len(vals)}")
