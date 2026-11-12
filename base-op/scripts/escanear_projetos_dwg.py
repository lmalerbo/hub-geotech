r"""
Varre a pasta raiz de projetos (G:\...\FAZENDAS) e mapeia todos os DWGs de
linhas de guia (colheita) do ciclo informado, prontos pra virar entrada do
pipeline (conversao DXF -> classificacao -> Gen4/GS3_2630 -> upload API).

Convencao encontrada:
    FAZENDAS\<codigo> <NOME_FAZENDA>\<ciclo>\03 EXPORTACOES\<NN COLHEITA>\
        <codigo>_<NOME>_Exp0.dwg              -> backup, IGNORAR
        <tipo>\<codigo>_<NOME>_Exp<tipo>.dwg   -> tipo = 1L, 2L, etc.

Uso:
    python escanear_projetos_dwg.py [ciclo]
    (ciclo default: 2026-2027)
"""

import re
import sys
from pathlib import Path

RAIZ_FAZENDAS = Path(
    r"G:\GeoProc\GEOTECNOLOGIA\08 PROJETOS PILOTO AUTOMATICO\15 PROPRIO\FAZENDAS"
)

PADRAO_DWG = re.compile(r"^(\d+)_(.+)_Exp(\w+)\.dwg$", re.IGNORECASE)


def escanear(ciclo: str) -> list[dict]:
    achados = []
    for pasta_fazenda in sorted(RAIZ_FAZENDAS.iterdir()):
        if not pasta_fazenda.is_dir():
            continue
        pasta_export = pasta_fazenda / ciclo / "03 EXPORTACOES"
        if not pasta_export.exists():
            continue
        colheita = next(
            (p for p in pasta_export.iterdir() if p.is_dir() and "COLHEITA" in p.name.upper()),
            None,
        )
        if colheita is None:
            continue

        for dwg in colheita.rglob("*.dwg"):
            m = PADRAO_DWG.match(dwg.name)
            if not m:
                continue
            codigo, nome, tipo = m.groups()
            if tipo == "0":
                continue  # backup, ignorar

            pasta_tipo = dwg.parent
            dxf = pasta_tipo / (dwg.stem + ".dxf")
            gen4 = pasta_tipo / "Gen4"
            gs3 = pasta_tipo / "GS3_2630"

            achados.append({
                "codigo": codigo,
                "nome": nome,
                "tipo": tipo,
                "dwg": dwg,
                "tem_dxf": dxf.exists(),
                "tem_gen4": gen4.exists(),
                "tem_gs3": gs3.exists(),
            })
    return achados


def main():
    ciclo = sys.argv[1] if len(sys.argv) > 1 else "2026-2027"
    print(f"Escaneando ciclo {ciclo} em {RAIZ_FAZENDAS} ...\n")

    achados = escanear(ciclo)
    print(f"Total de DWGs de colheita encontrados: {len(achados)}\n")

    pendentes = [a for a in achados if not a["tem_gs3"]]
    ja_processados = [a for a in achados if a["tem_gs3"]]

    print(f"Ja com GS3_2630 gerado (AgroCAD manual, pular): {len(ja_processados)}")
    print(f"Pendentes (sem GS3_2630 ainda):                 {len(pendentes)}\n")

    print("--- pendentes ---")
    for a in pendentes:
        print(
            f"{a['codigo']} {a['nome']:<25s} {a['tipo']:<4s} "
            f"dxf={'sim' if a['tem_dxf'] else 'nao'}  "
            f"-> {a['dwg']}"
        )


if __name__ == "__main__":
    main()
