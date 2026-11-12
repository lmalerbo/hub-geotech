"""PLL (nosso) sem recorte, em cada fonte inteira -- o numero que o usuario
veria rodando o pipeline na fazenda toda. Areas cobertas diferem entre fontes!"""
import pickle, time
from lib_geo import *
from paralelismo_pipeline import pll

Lk = pickle.load(open(os.path.join(CACHE, "linhas.pkl"), "rb"))
for nome, L in [("ticks .jdl (pipeline atual, todos os ticks)", Lk["tick_lines"]),
                ("ticks documentados (a <30cm de ponto AgroCAD On)", Lk["tick_doc_lines"]),
                ("AgroCAD polilinhas do executado.dwg", Lk["agro_own"]),
                ("AgroCAD nosso LSFP/QBD/CLE nos FIELD_POINTS", Lk["agro_ours"])]:
    t0 = time.time()
    r = pll(L)
    print(f"{nome:50s} linhas={len(L):5d} km={sum(l.length for l in L)/1000:6.1f} | amostras={r.total_amostras:6d} "
          f"abaixo={r.pct_abaixo:5.1f}% ideal={r.pct_ideal:5.1f}% acima={r.pct_acima:5.1f}% media={r.espacamento_medio:.3f} ({time.time()-t0:.0f}s)")
