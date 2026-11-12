"""Etapa 2: extrai geometrias de todos os insumos para cache (pickle):
 - projeto: polilinhas (linhas de orientacao)
 - executado AgroCAD: FIELD_POINTS com os atributos do XDATA 'IRD'
   (registro binario: strings UTF-16LE terminadas em \\0 + doubles) e as
   polilinhas das camadas 62571/64086/64088
 - drone: polilinhas do shapefile
"""
import os, pickle, struct, re
import numpy as np
import ezdxf
import shapefile

TT = r"C:\Users\lmalerbo\Documents\GitHub\base-op\trinca-teste"
CACHE = os.path.join(TT, "analise", "cache")


def parse_ird(xdata_tags):
    b = b"".join(bytes(t.value) for t in xdata_tags if t.code == 1004)
    # campos: sequencia de strings utf-16 e doubles. Mapeamento empirico:
    # [flag 1 byte] Cliente, Fazenda, Campo, ?, Operacao, Cultura, DataHora, Maquina, QualidadeGPS,
    # lat(f8), lon(f8), elev(f8), v1(f8), Status(str), v2(f8), v3(f8), largura(f8), v4(f8)
    pos = 2  # 1o "caractere" utf-16 = 0x0001 (flag)
    strs = []
    def rd_str(pos):
        end = pos
        while b[end:end + 2] != b"\x00\x00":
            end += 2
        return b[pos:end].decode("utf-16-le"), end + 2
    for _ in range(9):
        s, pos = rd_str(pos)
        strs.append(s)
    # entre a qualidade GPS e o status (On/Off) ha 4-6 doubles (varia)
    cands = [i for i in (b.find("O\0n\0\0\0".encode(), pos), b.find("O\0f\0f\0\0\0".encode(), pos)) if i >= 0]
    st = min(cands)
    nd = (st - pos) // 8
    dbl = struct.unpack_from(f"<{nd}d", b, pos)
    lat, lon, elev = dbl[0], dbl[1], dbl[2]
    v1 = dbl[3:]
    pos = st
    status, pos = rd_str(pos)
    rest = []
    while pos + 8 <= len(b):
        rest.append(struct.unpack_from("<d", b, pos)[0]); pos += 8
    return strs, (lat, lon, elev, v1), status, rest


def main():
    out = {}
    # projeto
    d = ezdxf.readfile(os.path.join(CACHE, "10658_projeto.dxf"))
    out["projeto"] = [np.array(list(e.get_points("xy"))) for e in d.modelspace().query("LWPOLYLINE")]

    # executado
    d = ezdxf.readfile(os.path.join(CACHE, "10658_executado.dxf"))
    msp = d.modelspace()
    rows = []
    for p in msp.query('POINT[layer=="FIELD_POINTS"]'):
        tags = list(p.xdata.data["IRD"]) if p.xdata and "IRD" in p.xdata.data else []
        strs, nums, status, rest = parse_ird(tags)
        loc = p.dxf.location
        rows.append(dict(handle=int(p.dxf.handle, 16), x=loc.x, y=loc.y, z=loc.z, data=strs[6], maquina=strs[7],
                         gps=strs[8], lat=nums[0], lon=nums[1], elev=nums[2], v1=nums[3], status=status,
                         rest=rest, campo=strs[2], fazenda=strs[1]))
    out["agro_pts"] = rows
    out["agro_pl"] = {}
    for lay in ("62571", "64086", "64088"):
        out["agro_pl"][lay] = [np.array(list(e.get_points("xy"))) for e in msp.query(f'LWPOLYLINE[layer=="{lay}"]')]

    sf = shapefile.Reader(os.path.join(TT, "10658_linhas-vant.shp"))
    dr = []
    for s in sf.shapes():
        pts = np.array(s.points)
        parts = list(s.parts) + [len(pts)]
        for a, bnd in zip(parts[:-1], parts[1:]):
            dr.append(pts[a:bnd])
    out["drone"] = dr
    with open(os.path.join(CACHE, "geom.pkl"), "wb") as f:
        pickle.dump(out, f)

    # resumo
    import collections
    print("projeto:", len(out["projeto"]), "polilinhas;", "comprimento total",
          round(sum(np.hypot(*np.diff(a, axis=0).T).sum() for a in out["projeto"])), "m")
    print("drone:", len(dr), "partes;", "comprimento total",
          round(sum(np.hypot(*np.diff(a, axis=0).T).sum() for a in dr)), "m")
    print("agro pts:", len(rows))
    for k in ("maquina", "gps", "status", "data", "campo", "fazenda"):
        c = collections.Counter(r[k][:10] if k == "data" else r[k] for r in rows)
        print(" ", k, c.most_common(8))
    r = rows[100000]
    print("exemplo:", {k: v for k, v in r.items()})
    for lay, L in out["agro_pl"].items():
        print("agro pl", lay, len(L), "comprimento", round(sum(np.hypot(*np.diff(a, axis=0).T).sum() for a in L)))


if __name__ == "__main__":
    main()
