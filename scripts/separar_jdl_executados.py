"""Copia os logs .jdl (JDLink, trator JD 7230J) organizados por fazenda.

Definicao acertada com o usuario: o "executado" e o catalogo de canais do
trator (~150 parametros: velocidade, combustivel, torque, marcha etc. com
seus valores), que esta presente em praticamente TODO arquivo .jdl (mesma
contagem de unidades tipo 'km1hr-1'=5x, 'unitless'=33x, 'l1hr-1'=1x, tanto
em arquivos de 2,6KB quanto de 4,7MB - verificado por amostragem em toda a
base). O "POS-MAQUINA"/sujeira e o resto do envelope binario ao redor
(eventos com UUID zerado, metadados de sessao/conexao) - nao um arquivo
inteiro a descartar. Por isso o criterio passou a ser "praticamente tudo",
sem filtro por tamanho.

Mantem o .jdl como esta (sem extrair pra CSV) - so reorganiza por fazenda,
recriando a estrutura original "JD-Data/log/" dentro da pasta de cada
fazenda no destino.

Uso:
    python separar_jdl_executados.py [--dry-run]
"""
import argparse
import glob
import os
import re
import shutil


ORIGEM_PADRAO = r"D:\JD-Data\log"
DESTINO_PADRAO = (
    r"G:\GeoProc\GEOTECNOLOGIA\08 PROJETOS PILOTO AUTOMATICO"
    r"\15 PROPRIO\EXECUTADOS\2026-2027\TORTA"
)


def farm_code_from_folder(nome_pasta):
    # ex: "2026_US PEDRA_10203-10828Rev0_Parte 1" -> "10203-10828Rev0"
    m = re.search(r"US PEDRA_([\w\-]+)_Parte", nome_pasta)
    return m.group(1) if m else nome_pasta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default=ORIGEM_PADRAO)
    ap.add_argument("--destino", default=DESTINO_PADRAO)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    arquivos = glob.glob(os.path.join(args.origem, "**", "*.jdl"), recursive=True)
    print(f"total de arquivos .jdl encontrados: {len(arquivos)}")

    resumo = {}
    for f in arquivos:
        pasta_origem = os.path.basename(os.path.dirname(f))
        farm = farm_code_from_folder(pasta_origem)
        resumo[farm] = resumo.get(farm, 0) + 1

        destino_dir = os.path.join(args.destino, farm, "JD-Data", "log")
        destino_path = os.path.join(destino_dir, os.path.basename(f))

        if args.dry_run:
            continue

        os.makedirs(destino_dir, exist_ok=True)
        shutil.copy2(f, destino_path)

    print()
    print(f"{'[DRY-RUN] ' if args.dry_run else ''}resumo por fazenda:")
    total = 0
    for farm, n in sorted(resumo.items()):
        print(f"  {farm}: {n} arquivos -> {os.path.join(args.destino, farm, 'JD-Data', 'log')}")
        total += n
    print()
    print(f"total {'a copiar' if args.dry_run else 'copiado'}: {total}")
    if not args.dry_run:
        print(f"destino base: {args.destino}")


if __name__ == "__main__":
    main()
