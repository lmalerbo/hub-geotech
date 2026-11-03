"""Gera os HTML esperados dos slides a partir da fixture sintética, com o gerar.py de referência.

Uso: python tests/app/apresentacao/gerar_esperado.py [--mostrar-drone]

Não exporta PNG nem PPTX. Só grava os HTML em esperado/ (UTF-8, sem newline extra).
"""
import datetime
import importlib.util
import json
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
MOSTRAR_DRONE = "--mostrar-drone" in sys.argv

sys.argv = ["gerar.py", "S5M10", "2026-10-28"]
spec = importlib.util.spec_from_file_location("gerar_referencia", HERE / "referencia" / "gerar.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.DADOS = HERE / "dados"


class _Data(datetime.date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 29)


# "Hoje" fixo: só troca o date; datetime, timedelta e timezone continuam os reais.
mod.datetime = types.SimpleNamespace(date=_Data, datetime=datetime.datetime,
                                     timedelta=datetime.timedelta, timezone=datetime.timezone)

A = mod.agregar()

if MOSTRAR_DRONE:
    d = A["drone"]
    saida = {
        "por_safra": dict(d["por_safra"]),
        "n_proj": dict(d["n_proj"]),
        "faz_safra": dict(d["faz_safra"]),
        "n_base": d["n_base"],
        "faz_base": d["faz_base"],
    }
    print(json.dumps(saida, ensure_ascii=False, sort_keys=True))

GERADORES = {
    "divisoria": mod.divisoria,
    "colheita": mod.colheita,
    "sistematizacao": mod.sistematizacao,
    "plantio": mod.plantio,
    "voos": mod.voos,
    "drone": mod.drone,
}

(HERE / "esperado").mkdir(exist_ok=True)
for chave, gerador in GERADORES.items():
    html = gerador(A)
    if not isinstance(html, str):
        print(f"  aviso: {chave} devolveu {type(html).__name__}; gravando a parte HTML")
        html = html[0]
    with open(HERE / "esperado" / f"{chave}.html", "w", encoding="utf-8", newline="") as f:
        f.write(html)
    print("  gravado:", f"esperado/{chave}.html", len(html), "caracteres")
