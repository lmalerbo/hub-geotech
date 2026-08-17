r"""
Converte DWG -> DXF via ODA File Converter, sem precisar de AutoCAD/Civil3D
aberto manualmente.

O ODA File Converter normal (MSI) exige admin pra instalar "pra todos os
usuarios" -- nesta maquina isso nao esta disponivel, entao os arquivos foram
extraidos via instalacao administrativa (msiexec /a), que so copia os
binarios pra uma pasta sem precisar de elevacao:
    msiexec /a ODAFileConverter.msi /qn TARGETDIR="%LOCALAPPDATA%\ODAFileConverter"

Uso:
    python converter_dwg.py <pasta_entrada_com_dwgs> <pasta_saida> [recursivo]

Converte TODOS os .dwg da pasta de entrada (recursivo se pedido) pra .dxf na
pasta de saida (mesma estrutura de subpastas se recursivo).
"""

import subprocess
import sys
from pathlib import Path

EXE_PADRAO = Path.home() / "AppData" / "Local" / "ODAFileConverter" / "ODAFileConverter.exe"
VERSAO_SAIDA = "ACAD2018"


def converter_pasta(pasta_entrada: str, pasta_saida: str, recursivo: bool = False,
                     exe_path: Path = EXE_PADRAO) -> None:
    if not exe_path.exists():
        raise FileNotFoundError(
            f"ODAFileConverter.exe nao encontrado em {exe_path}. Ver docstring "
            f"deste arquivo pra instrucoes de extracao sem admin."
        )
    Path(pasta_saida).mkdir(parents=True, exist_ok=True)

    resultado = subprocess.run(
        [str(exe_path), pasta_entrada, pasta_saida, VERSAO_SAIDA, "DXF",
         "1" if recursivo else "0", "1"],
        capture_output=True, text=True, timeout=300,
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"ODAFileConverter falhou (codigo {resultado.returncode}): {resultado.stderr}")


def converter_arquivo(dwg_path: str, pasta_saida: str, exe_path: Path = EXE_PADRAO) -> Path:
    """Converte um unico .dwg -- copia pra pasta temp isolada pra nao converter
    junto outros arquivos que possam estar na mesma pasta de origem."""
    import shutil
    import tempfile

    dwg_path = Path(dwg_path)
    with tempfile.TemporaryDirectory() as tmp:
        # o ODAFileConverter so reconhece entrada com extensao .dwg -- um .dwt
        # (template) e o mesmo formato binario, so renomeia a copia temporaria
        tmp_in = Path(tmp) / (dwg_path.stem + ".dwg")
        shutil.copy2(dwg_path, tmp_in)
        converter_pasta(tmp, pasta_saida, recursivo=False, exe_path=exe_path)

    dxf_path = Path(pasta_saida) / (dwg_path.stem + ".dxf")
    if not dxf_path.exists():
        raise RuntimeError(f"Conversao nao gerou {dxf_path} (DWG pode estar corrompido ou em formato nao suportado).")
    return dxf_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python converter_dwg.py <pasta_entrada> <pasta_saida> [recursivo:1/0]")
        sys.exit(1)
    recursivo = len(sys.argv) > 3 and sys.argv[3] == "1"
    converter_pasta(sys.argv[1], sys.argv[2], recursivo)
    print(f"Conversao concluida: {sys.argv[2]}")
