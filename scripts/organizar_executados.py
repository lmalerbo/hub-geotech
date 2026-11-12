"""Organiza os dados brutos de execucao (JD-Data .jdl e GS3 .fdl/.fdd) de uma safra.

Duas fases, para conferir antes de copiar:

  python organizar_executados.py manifesto <raiz_safra> <manifesto.csv> --frotas-maquinas frotas_maquinas.csv
  python organizar_executados.py copiar    <raiz_safra> <manifesto.csv>

Destino (dentro da propria raiz, nada e movido nem apagado):
  BRUTOS/<OPERACAO>/<FAZENDA>/<FROTA>/JD-Data/log/<sessao>/*.jdl
  BRUTOS/<OPERACAO>/<FAZENDA>/<FROTA>/GS3_2630/.../Documentation/*.fdl|.fdd
  BRUTOS/<OPERACAO>/_GUIAS/<FROTA>/...   (FileServer e o resto da arvore GS3_2630)
  PRODUTOS/<caminho original>             (dwg, dxf, shp, csv, txt...)
  _PACOTES/<caminho original>             (zip, rar)

Duplicatas (mesmo nome + tamanho) viram uma copia so. Frota e operacao do .jdl
vem do numero de serie gravado nele (frotas_maquinas.csv), nao do nome da pasta;
a fazenda vem da pasta de sessao do log (ex. '2026_US PEDRA_10010Rev1_Parte 1')
ou, no GS3, do XML do .fdl.
"""
import argparse
import collections
import csv
import os
import re
import shutil
import sys

DESTINOS = ("BRUTOS", "PRODUTOS", "_PACOTES")
IGNORAR_RAIZ = re.compile(r"^(VINHA|BRUTOS$|PRODUTOS$|_PACOTES$)", re.I)
RE_SERIE = re.compile(rb"BM\d{4}[A-Z]\d{6}")
RE_FAZ_REV = re.compile(r"(?<!\d)(\d{5})\s*[_ ]?\s*REV\s*(\d+)", re.I)
RE_FAZ_NOME = re.compile(r"^(\d{5})(?:\s+[A-Za-z]|$)")
RE_FAZ_SOLTA = re.compile(r"(?<!\d)(\d{5})(?!\d)")
RE_REV_SOLTA = re.compile(r"(?<![A-Za-z\d])REV\s*_?(\d+)", re.I)
PACOTES = {".zip", ".rar", ".7z"}
BRUTOS_GS3 = {".fdl", ".fdd"}
PASTA_GS3 = "gs3_2630"


def carregar_frotas(caminho):
    """serie -> (frota, operacao); frotas: nome em pasta (atual ou antigo) -> (frota atual, operacao)."""
    por_serie, frotas = {}, {}
    if caminho and os.path.exists(caminho):
        with open(caminho, encoding="utf-8-sig") as f:
            for l in csv.DictReader(f, delimiter=";"):
                por_serie[l["serie"]] = (l["frota"], l["operacao"])
                frotas[l["frota"]] = (l["frota"], l["operacao"])
                for antigo in filter(None, (l.get("nomes_antigos") or "").split(",")):
                    frotas.setdefault(antigo.strip(), (l["frota"], l["operacao"]))
    return por_serie, frotas


def serie_do_jdl(caminho):
    try:
        with open(caminho, "rb") as f:
            m = RE_SERIE.search(f.read(1024))
    except OSError:
        return ""
    return m.group(0).decode() if m else ""


def fazenda_do_fdl(caminho):
    """Nome da fazenda da sessao no XML do .fdl (mesma regra de gs3_documentacao.ler_sessao)."""
    try:
        x = open(caminho, encoding="latin-1").read()
    except OSError:
        return ""
    campo = re.search(r'<FieldRef eridRef="([^"]+)"', x)
    fazendas = dict(re.findall(r'<rcdsetup:Farm [^>]*erid="([^"]+)" name="([^"]*)"', x))
    talhao_fazenda = dict(re.findall(r'<rcdsetup:Field [^>]*erid="([^"]+)"[^>]*farmRef="([^"]+)"', x))
    return fazendas.get(talhao_fazenda.get(campo.group(1) if campo else None), "")


def fazenda_de_textos(textos, frotas):
    """Codigo da fazenda a partir de nomes (pasta de sessao primeiro, depois as pastas acima).
    'XXXXXRevN' tem prioridade; depois 'XXXXX NOME'; depois um codigo de 5 digitos que nao seja frota."""
    for t in textos:
        m = RE_FAZ_REV.search(t)
        if m:
            return f"{m.group(1)}Rev{int(m.group(2))}"
    cod = ""
    for t in textos:
        m = RE_FAZ_NOME.match(t.strip())
        if m and m.group(1) not in frotas:
            cod = m.group(1)
            break
    if not cod:
        cod = next((c for t in textos for c in RE_FAZ_SOLTA.findall(t) if c not in frotas), "")
    # revisao escrita longe do codigo: 'BL STA JOANA REV1' dentro de '10609 SANTA JOANA'
    rev = next((m.group(1) for t in textos for m in [RE_REV_SOLTA.search(t)] if m), None)
    return f"{cod}Rev{int(rev)}" if cod and rev is not None else cod


def frota_de_pastas(partes, frotas):
    for p in reversed(partes):
        for cod in re.findall(r"(?<!\d)(\d{5}|\d{3})(?!\d)", p):
            if cod in frotas:
                return frotas[cod][0]
    return ""


def operacao_da_frota(frota, frotas):
    return frotas.get(frota, ("", ""))[1]


def cauda_desde(partes, nome_pasta):
    """Caminho a partir da pasta `nome_pasta` (inclusive), sem diferenciar maiusculas."""
    baixo = [p.lower() for p in partes]
    if nome_pasta in baixo:
        return partes[baixo.index(nome_pasta):]
    return None


def classificar(raiz, rel, por_serie, frotas):
    """-> dict com destino e metadados de um arquivo."""
    partes = rel.replace("\\", "/").split("/")
    nome = partes[-1]
    ext = os.path.splitext(nome)[1].lower()
    operacao_pasta = partes[0].upper() if partes[0].upper() in ("CANA", "TORTA") else ""
    r = {"origem": rel, "tipo": "", "operacao": operacao_pasta, "fazenda": "", "frota": "",
         "serie": "", "destino": "", "obs": ""}

    if ext in PACOTES:
        r["tipo"], r["destino"] = "pacote", "/".join(["_PACOTES"] + partes)
        return r

    if ext == ".jdl":
        r["tipo"] = "jdl"
        r["serie"] = serie_do_jdl(os.path.join(raiz, rel))
        frota, op = por_serie.get(r["serie"], ("", ""))
        if not frota:
            frota = frota_de_pastas(partes[:-1], frotas) or (f"SERIE_{r['serie']}" if r["serie"] else "SEM_FROTA")
            r["obs"] = "serie fora da tabela" if r["serie"] else "sem serie no arquivo"
        r["frota"], r["operacao"] = frota, op or operacao_da_frota(frota, frotas) or operacao_pasta
        cauda = cauda_desde(partes, "log")
        sessao = cauda[1] if cauda and len(cauda) > 2 else ""
        r["fazenda"] = fazenda_de_textos([sessao] + list(reversed(partes[:-1])), frotas) or "SEM_FAZENDA"
        cauda = ["JD-Data"] + cauda if cauda else ["JD-Data", "log", nome]
        r["destino"] = "/".join(["BRUTOS", r["operacao"] or "SEM_OPERACAO", r["fazenda"], r["frota"]] + cauda)
        return r

    cauda_gs3 = cauda_desde(partes, PASTA_GS3)
    if ext in BRUTOS_GS3 and cauda_gs3:
        r["tipo"] = "gs3"
        r["frota"] = frota_de_pastas(partes[:-1], frotas) or "SEM_FROTA"
        r["operacao"] = operacao_da_frota(r["frota"], frotas) or operacao_pasta or "CANA"
        fdl = os.path.join(raiz, rel)[:-4] + ".fdl"
        nome_faz = fazenda_do_fdl(fdl)
        r["fazenda"] = fazenda_de_textos([nome_faz] + list(reversed(partes[:-1])), frotas) or "SEM_FAZENDA"
        if nome_faz and nome_faz not in r["fazenda"]:
            r["obs"] = f"fazenda no fdl: {nome_faz}"
        r["destino"] = "/".join(["BRUTOS", r["operacao"], r["fazenda"], r["frota"]] + cauda_gs3)
        return r

    cauda_fs = cauda_desde(partes, "fileserver") or cauda_gs3
    if cauda_fs:
        r["tipo"] = "guia"
        r["frota"] = frota_de_pastas(partes[:-1], frotas) or "SEM_FROTA"
        r["operacao"] = operacao_da_frota(r["frota"], frotas) or operacao_pasta or "SEM_OPERACAO"
        r["destino"] = "/".join(["BRUTOS", r["operacao"], "_GUIAS", r["frota"]] + cauda_fs)
        return r

    r["tipo"], r["destino"] = "produto", "/".join(["PRODUTOS"] + partes)
    return r


def qualidade(r):
    """Entre copias do mesmo arquivo, prefere a com fazenda e frota mais bem identificadas."""
    return (r["fazenda"].startswith("SEM") is False, "Rev" in r["fazenda"],
            not r["frota"].startswith(("SEM", "SERIE")), "unificado" not in r["origem"].lower())


def herdar_frota_da_sessao(grupos):
    """.jdl sem numero de serie (arquivos curtos) recebem a frota mais comum entre
    os .jdl com serie da mesma pasta de sessao."""
    por_pasta = collections.defaultdict(collections.Counter)
    for copias in grupos.values():
        for r in copias:
            if r["tipo"] == "jdl" and r["serie"]:
                por_pasta[os.path.dirname(r["origem"])][(r["frota"], r["operacao"])] += 1
    for copias in grupos.values():
        for r in copias:
            if r["tipo"] == "jdl" and not r["serie"] and por_pasta[os.path.dirname(r["origem"])]:
                frota, op = por_pasta[os.path.dirname(r["origem"])].most_common(1)[0][0]
                antigo = f"/{r['operacao']}/{r['fazenda']}/{r['frota']}/"
                r["frota"], r["operacao"] = frota, op
                r["destino"] = r["destino"].replace(antigo, f"/{op}/{r['fazenda']}/{frota}/", 1)
                r["obs"] = "sem serie; frota da sessao"


def renomear_colisoes(escolhidos):
    """Arquivos diferentes com o mesmo destino (ex. ContextData/*.BIN do GS3 em dois
    pen-drives): o maior fica com o nome; os outros ganham '__<pasta de origem>'."""
    por_destino = collections.defaultdict(list)
    for r in escolhidos:
        por_destino[r["destino"].lower()].append(r)
    for rs in por_destino.values():
        for r in sorted(rs, key=lambda r: -r["tamanho"])[1:]:
            base, ext = os.path.splitext(r["destino"])
            origem = "_".join(r["origem"].split("/")[:2]).replace(" ", "_")
            r["destino"] = f"{base}__{origem}{ext}"
            r["obs"] = (r["obs"] + "; " if r["obs"] else "") + "versao mais antiga/menor renomeada"


def gerar_manifesto(raiz, saida, frotas_csv):
    por_serie, frotas = carregar_frotas(frotas_csv)
    grupos = collections.defaultdict(list)
    n = 0
    for dirpath, dirnames, filenames in os.walk(raiz):
        if os.path.samefile(dirpath, raiz):
            dirnames[:] = [d for d in dirnames if not IGNORAR_RAIZ.match(d)]
        for nome in filenames:
            p = os.path.join(dirpath, nome)
            rel = os.path.relpath(p, raiz).replace("\\", "/")
            try:
                tam = os.path.getsize(p)
            except OSError:
                continue
            r = classificar(raiz, rel, por_serie, frotas)
            r["tamanho"] = tam
            # pacotes e produtos guardam o caminho original, entao nao deduplicam
            chave = (nome.lower(), tam) if r["tipo"] in ("jdl", "gs3", "guia") else ("#", rel)
            grupos[chave].append(r)
            n += 1
            if n % 2000 == 0:
                print(f"  {n} arquivos lidos...", file=sys.stderr)

    herdar_frota_da_sessao(grupos)
    escolhidos = [max(copias, key=qualidade) for copias in grupos.values()]
    renomear_colisoes(escolhidos)
    campos = ["destino", "origem", "tipo", "operacao", "fazenda", "frota", "serie", "tamanho",
              "copias", "conflito", "obs"]
    resumo = collections.Counter()
    with open(saida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        for copias, melhor in zip(grupos.values(), escolhidos):
            destinos = {(c["fazenda"], c["frota"]) for c in copias}
            melhor["copias"] = len(copias)
            melhor["conflito"] = " | ".join(sorted(f"{a}/{b}" for a, b in destinos)) if len(destinos) > 1 else ""
            w.writerow(melhor)
            resumo[(melhor["tipo"], melhor["operacao"])] += 1
    print(f"{n} arquivos lidos, {sum(resumo.values())} no manifesto -> {saida}")
    for (tipo, op), q in sorted(resumo.items()):
        print(f"  {tipo:8} {op or '-':13} {q}")


def copiar(raiz, manifesto):
    feitos = pulados = 0
    with open(manifesto, encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    for i, l in enumerate(linhas, 1):
        if not l["destino"].startswith(DESTINOS):
            raise SystemExit(f"destino fora de {DESTINOS}: {l['destino']}")
        orig = os.path.join(raiz, l["origem"])
        dest = os.path.join(raiz, l["destino"])
        if os.path.exists(dest) and os.path.getsize(dest) == int(l["tamanho"]):
            pulados += 1
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(orig, dest)
        feitos += 1
        if i % 1000 == 0:
            print(f"  {i}/{len(linhas)}", file=sys.stderr)
    print(f"copiados {feitos}, ja existiam {pulados}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fase", choices=["manifesto", "copiar"])
    ap.add_argument("raiz")
    ap.add_argument("manifesto")
    ap.add_argument("--frotas-maquinas", default=r"I:\Projetos\PARALELISMO\PEDRA\frotas_maquinas.csv")
    a = ap.parse_args()
    if a.fase == "manifesto":
        gerar_manifesto(a.raiz, a.manifesto, a.frotas_maquinas)
    else:
        copiar(a.raiz, a.manifesto)


if __name__ == "__main__":
    main()
