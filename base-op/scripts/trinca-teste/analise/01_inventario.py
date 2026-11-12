"""Etapa 1: converte os DWGs em DXF, extrai ticks do .jdl e faz o inventario
de camadas/entidades/extensao de cada arquivo. Salva caches em analise/cache."""
import os, sys, glob, collections, json
import numpy as np

BASE = r"C:\Users\lmalerbo\Documents\GitHub\base-op"
TT = os.path.join(BASE, "trinca-teste")
OUT = os.path.join(TT, "analise")
CACHE = os.path.join(OUT, "cache")
sys.path.insert(0, os.path.join(BASE, "scripts"))
os.makedirs(CACHE, exist_ok=True)

import ezdxf
import shapefile
from converter_dwg import converter_arquivo


def inventario_dxf(dxf):
    doc = ezdxf.readfile(dxf)
    msp = doc.modelspace()
    cont = collections.Counter()
    ext = {}
    for e in msp:
        k = (e.dxf.layer, e.dxftype())
        cont[k] += 1
        try:
            if e.dxftype() == "POINT":
                pts = [(e.dxf.location.x, e.dxf.location.y)]
            elif e.dxftype() == "LWPOLYLINE":
                pts = [p[:2] for p in e.get_points("xy")]
            elif e.dxftype() == "POLYLINE":
                pts = [v.dxf.location[:2] for v in e.vertices]
            elif e.dxftype() == "LINE":
                pts = [e.dxf.start[:2], e.dxf.end[:2]]
            elif e.dxftype() == "INSERT":
                pts = [e.dxf.insert[:2]]
            elif e.dxftype() in ("TEXT", "MTEXT"):
                pts = [e.dxf.insert[:2]]
            else:
                pts = []
        except Exception:
            pts = []
        if pts:
            a = np.array(pts, float)
            lo, hi = a.min(0), a.max(0)
            if k in ext:
                lo = np.minimum(lo, ext[k][0]); hi = np.maximum(hi, ext[k][1])
            ext[k] = (lo, hi)
    print(f"\n=== {os.path.basename(dxf)} | INSUNITS={doc.header.get('$INSUNITS')}")
    for k, n in sorted(cont.items()):
        e = ext.get(k)
        es = f"x[{e[0][0]:.1f},{e[1][0]:.1f}] y[{e[0][1]:.1f},{e[1][1]:.1f}]" if e else ""
        print(f"  layer={k[0]!r:40s} {k[1]:12s} n={n:7d} {es}")
    # blocos com atributos (ex.: tab_espac do PLL)
    for ins in msp.query("INSERT"):
        if ins.attribs:
            print("  INSERT", ins.dxf.name, ins.dxf.layer, {a.dxf.tag: a.dxf.text for a in ins.attribs})
    for t in msp.query("TEXT MTEXT"):
        txt = t.dxf.text if t.dxftype() == "TEXT" else t.text
        print("  TXT", t.dxf.layer, repr(txt[:120]))
    return doc


def main():
    for nome in ("10658_projeto.dwg", "10658_executado.dwg"):
        dxf = os.path.join(CACHE, nome.replace(".dwg", ".dxf"))
        if not os.path.exists(dxf):
            dxf = str(converter_arquivo(os.path.join(TT, nome), CACHE))
        inventario_dxf(dxf)

    sf = shapefile.Reader(os.path.join(TT, "10658_linhas-vant.shp"))
    print("\n=== 10658_linhas-vant.shp", sf.shapeTypeName, len(sf), "bbox", sf.bbox)
    print("  campos:", [f[0] for f in sf.fields[1:]])
    for r in sf.records()[:5]:
        print("  ", r)

    tick_cache = os.path.join(CACHE, "ticks.npz")
    if not os.path.exists(tick_cache):
        from jdl_gps_extract import extrair_ticks_de_arquivo
        import pyproj
        tr = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:31983", always_xy=True)
        pasta = os.path.join(TT, "10658_arquivos-trator")
        arqs = sorted(glob.glob(os.path.join(pasta, "**", "*.jdl"), recursive=True))
        xs, ys, fid = [], [], []
        for i, a in enumerate(arqs):
            t = extrair_ticks_de_arquivo(a)
            if not t:
                continue
            la = np.array(t)
            x, y = tr.transform(la[:, 1], la[:, 0])
            xs.append(x); ys.append(y); fid.append(np.full(len(x), i))
        np.savez(tick_cache, x=np.concatenate(xs), y=np.concatenate(ys), f=np.concatenate(fid),
                 nomes=np.array([os.path.basename(a) for a in arqs]))
    d = np.load(tick_cache)
    print(f"\n=== ticks .jdl: {len(d['x'])} pontos de {len(np.unique(d['f']))} arquivos com ticks;"
          f" x[{d['x'].min():.1f},{d['x'].max():.1f}] y[{d['y'].min():.1f},{d['y'].max():.1f}]")


if __name__ == "__main__":
    main()
