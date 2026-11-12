"""
Paralelismo a nivel de talhao, pros executados de TORTA (.jdl, JD-Data) e de
CANA (.fdl/.fdd, GS3_2630), no formato que o painel do projeto
(I:\\Projetos\\PARALELISMO\\PEDRA: gerar_dash.py + Resultados\\Paralelismo*.xlsx) usa.

Para cada fazenda: pontos de plantio por arquivo (ponto do implemento com o
trabalho ligado, ver jdl_documentacao.py / gs3_documentacao.py), marcados com
a frota (numero da pasta de origem em ...\\ORGANIZAR\\<frota>...) e a data;
LSFP -> QBD -> CLE por frota, limpar() no conjunto, PLL; cada amostra do PLL
cai num talhao da base (ponto da amostra dentro do poligono) e e
classificada em Abaixo (<2,90) / Aderente (2,90-3,10) / Acima (>3,10).

Saidas em --saida (ex.: Resultados\\20261008):
  <SECAO>_<OPERACAO>_Paralelismo.shp  segmento de cada amostra (como o FME)
  <SECAO>_<OPERACAO>_Linhas.shp       linhas usadas no PLL
  talhoes.csv / secoes.csv             agregados
e, com --planilha-base, uma copia da planilha com as linhas novas nas abas
Talhao e Secao (coluna nova Operacao) em --planilha-saida.

Uso:
  python paralelismo_talhao.py --talhoes <base.shp> --saida <pasta> --data 20261008
      [--torta <unificado> --torta-frotas <ORGANIZAR>]
      [--cana <UNIFICADO> --cana-frotas <ORGANIZAR>]
      [--planilha-base Paralelismo3.xlsx --planilha-saida Paralelismo4.xlsx]
"""
import argparse
import collections
import csv
import glob
import os
import re
import shutil

import pyproj
import shapefile
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from gs3_documentacao import ler_sessao, pontos_plantio as pontos_gs3
from jdl_documentacao import pontos_plantio as pontos_jdl_implemento, pontos_trator as pontos_jdl_trator
from paralelismo_pipeline import cle, limpar, lsfp, pll_amostras, qbd

IDEAL_MIN, IDEAL_MAX = 2.90, 3.10
LSFP_M, QBD_GRAUS, CLE_M = 10.0, 160.0, 10.0
RE_DATA_JDL = re.compile(r"^(\d{4})_(\d{2})_(\d{2})_")
RE_FROTA_CAMINHO = [re.compile(r"frota\s*(\d+)", re.I), re.compile(r"(?:^|[\\/])(\d{5})\s*-\s*\d{5}")]
RE_SERIE = re.compile(rb"BM\d{4}[A-Z]\d{6}")
FROTA_DA_SERIE: dict[str, str] = {}  # carregado de --frotas-maquinas (serie;frota)


def carregar_frotas_maquinas(caminho: str | None) -> None:
    """serie;frota[;obs] -> FROTA_DA_SERIE. A frota de um .jdl passa a vir do
    trator gravado nele (a pasta nem sempre e de uma frota so: a '21' misturava
    tres tratores, e o mesmo trator aparece como 221 e 52221)."""
    if not caminho or not os.path.exists(caminho):
        return
    with open(caminho, encoding="utf-8-sig") as f:
        for linha in list(f)[1:]:
            partes = [p.strip() for p in linha.split(";")]
            if len(partes) >= 2 and partes[0] and partes[1]:
                FROTA_DA_SERIE[partes[0]] = partes[1]


def frota_do_jdl(caminho: str, padrao: str) -> str:
    """Frota pelo numero de serie do trator dentro do .jdl; se a serie nao esta
    na tabela, a propria serie; se nao achar serie, `padrao` (nome da pasta)."""
    try:
        with open(caminho, "rb") as f:
            achadas = RE_SERIE.findall(f.read())
    except OSError:
        return padrao
    if not achadas:
        return padrao
    serie = collections.Counter(achadas).most_common(1)[0][0].decode()
    return FROTA_DA_SERIE.get(serie, serie)


MODO = "implemento"  # 'implemento' (ponto do meio da plantadeira, como o GOIMP) ou 'trator' (antena)


def pontos_jdl(caminho: str):
    return pontos_jdl_trator(caminho) if MODO == "trator" else pontos_jdl_implemento(caminho)


def classe(espacamento: float) -> str:
    if espacamento < IDEAL_MIN:
        return "Abaixo"
    if espacamento > IDEAL_MAX:
        return "Acima"
    return "Aderente"


# ── base de talhoes ──────────────────────────────────────────────────────────

class BaseTalhoes:
    def __init__(self, caminho_shp: str):
        sh = shapefile.Reader(caminho_shp, encoding="utf-8")
        campos = [f[0] for f in sh.fields[1:]]
        self.polis, self.attrs = [], []
        for s, r in zip(sh.shapes(), sh.records()):
            g = shape(s.__geo_interface__)
            if not g.is_valid:
                g = g.buffer(0)
            self.polis.append(g)
            self.attrs.append(dict(zip(campos, r)))
        self.tree = STRtree(self.polis)

    def talhao_em(self, x: float, y: float) -> dict | None:
        p = Point(x, y)
        for i in self.tree.query(p):
            if self.polis[i].contains(p):
                return self.attrs[i]
        return None


# ── frota de cada arquivo ────────────────────────────────────────────────────

def mapa_frotas(raiz_organizar: str | None, extensao: str) -> dict[str, str]:
    """{nome do arquivo: frota} varrendo <raiz>\\<frota...>\\**\\*.<ext>; a
    frota e o numero no inicio do nome da pasta (ex.: '633', '64086 executado')."""
    mapa = {}
    if not raiz_organizar:
        return mapa
    for pasta in os.listdir(raiz_organizar):
        m = re.match(r"^(\d+)", pasta)
        if not m or not os.path.isdir(os.path.join(raiz_organizar, pasta)):
            continue
        for f in glob.glob(os.path.join(raiz_organizar, pasta, "**", f"*.{extensao}"), recursive=True):
            mapa.setdefault(os.path.basename(f), m.group(1))
    return mapa


# ── leitura dos executados ───────────────────────────────────────────────────

def grupos_torta(raiz: str, frotas: dict, transformer, somente: list | None = None) -> dict[str, list]:
    """{fazenda (pasta): [(frota, data 'AAAA-MM-DD', [(x, y), ...]), ...]}"""
    out = collections.defaultdict(list)
    for pasta in sorted(p for p in glob.glob(os.path.join(raiz, "*")) if os.path.isdir(p)):
        if somente and os.path.basename(pasta) not in somente:
            continue
        for jdl in sorted(glob.glob(os.path.join(pasta, "**", "*.jdl"), recursive=True)):
            ll = pontos_jdl(jdl)
            if not ll:
                continue
            nome = os.path.basename(jdl)
            m = RE_DATA_JDL.match(nome)
            data = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""
            xs, ys = transformer.transform([lo for _, lo in ll], [la for la, _ in ll])
            out[os.path.basename(pasta)].append((frota_do_jdl(jdl, frotas.get(nome, "")), data, list(zip(xs, ys))))
    return out


def grupos_cana(raiz: str, frotas: dict, transformer) -> dict[str, list]:
    """Sessoes GS3 abaixo da raiz, agrupadas pela fazenda gravada no .fdl. A
    mesma sessao copiada em mais de uma pasta (ex.: unificado e dados-brutos,
    pen-drives repetidos) conta uma vez so, pelo nome do arquivo."""
    out = collections.defaultdict(list)
    vistos = set()
    for fdl in sorted(glob.glob(os.path.join(raiz, "**", "*.fdl"), recursive=True)):
        if os.path.basename(fdl) in vistos:
            continue
        vistos.add(os.path.basename(fdl))
        s = ler_sessao(fdl)
        ll = pontos_gs3(s, antena="5140" if MODO == "trator" else "5141")
        if not ll:
            continue
        xs, ys = transformer.transform([lo for _, lo in ll], [la for la, _ in ll])
        out[s["fazenda"]].append((frotas.get(os.path.basename(fdl), ""), s["inicio"][:10], list(zip(xs, ys))))
    return out


def grupos_jdl_soltos(raiz: str, transformer, ignorar: str | None = "ORGANIZAR",
                      ja_vistos: set | None = None) -> dict[str, list]:
    """.jdl espalhados numa arvore (ex.: EXECUTADOS/.../CANA/<frente>/<fazenda>/JD-Data):
    agrupa pela pasta do log (uma por fazenda/parte), tira duplicados pelo nome
    do arquivo (o mesmo .jdl costuma estar em mais de uma pasta) e pega a
    frota do caminho ('frota 1034 ...', '64086 - 10658 ...') -- entre as copias
    do mesmo arquivo, prefere a que tem a frota no caminho. Pastas com 'curva'
    no nome ficam de fora (gravacao de curva adaptavel/AB e projeto, nao executado)."""
    frota_de = lambda dp: next((m.group(1) for rx in RE_FROTA_CAMINHO for m in [rx.search(dp)] if m), "")
    escolhido = {}
    for dp, _, arquivos in os.walk(raiz):
        if ignorar and ignorar in os.path.relpath(dp, raiz).split(os.sep):
            continue
        if "curva" in os.path.relpath(dp, raiz).lower():
            continue  # gravacao de Curva Adaptavel / AB = linha de projeto, nao trabalho
        for nome in arquivos:
            if nome.lower().endswith(".jdl") and (nome not in escolhido or (frota_de(dp) and not frota_de(escolhido[nome]))):
                escolhido[nome] = dp
    out = collections.defaultdict(list)
    for nome, dp in sorted(escolhido.items()):
        if ja_vistos is not None:
            if nome in ja_vistos:
                continue
            ja_vistos.add(nome)
        ll = pontos_jdl(os.path.join(dp, nome))
        if not ll:
            continue
        m = RE_DATA_JDL.match(nome)
        data = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""
        xs, ys = transformer.transform([lo for _, lo in ll], [la for la, _ in ll])
        out[os.path.basename(dp)].append((frota_do_jdl(os.path.join(dp, nome), frota_de(dp)), data, list(zip(xs, ys))))
    return out


# ── processamento ────────────────────────────────────────────────────────────

def processar(operacao: str, grupos: dict, base: BaseTalhoes, pasta_saida: str, data_proc: str,
              agg_talhao: dict, agg_secao: dict) -> None:
    for fazenda, itens in sorted(grupos.items()):
        # linhas por frota (LSFP so liga pontos da mesma frota), limpeza no conjunto
        por_frota = collections.defaultdict(lambda: {"pontos": [], "datas": collections.Counter()})
        for frota, data, pts in itens:
            por_frota[frota]["pontos"].extend(pts)
            por_frota[frota]["datas"][data[:7]] += len(pts)
        linhas, meta = [], []
        for frota, d in por_frota.items():
            for l in cle(qbd(lsfp({frota: d["pontos"]}, max_dist=LSFP_M), min_angle_deg=QBD_GRAUS), min_length=CLE_M):
                linhas.append(l)
                meta.append((frota, d["datas"].most_common(1)[0][0] if d["datas"] else ""))
        limpas = {id(l) for l in limpar(linhas)}
        meta = [m for l, m in zip(linhas, meta) if id(l) in limpas]
        linhas = [l for l in linhas if id(l) in limpas]

        amostras = pll_amostras(linhas)
        fora = 0
        por_secao_shp = collections.defaultdict(list)
        for a in amostras:
            t = base.talhao_em(a.x, a.y)
            if t is None:
                fora += 1
                continue
            frota, mes = meta[a.linha]
            cl = classe(a.espacamento)
            k = (operacao, str(t["Layer"]))
            r = agg_talhao.setdefault(k, {"Secao": str(t["SECAO"]), "DESC_SECAO": t["DESC_SECAO"],
                                          "Declividade": t["DECLIVIDAD"], "Abaixo": 0, "Aderente": 0,
                                          "Acima": 0, "frotas": collections.Counter(),
                                          "meses": collections.Counter(), "fazendas": set()})
            r[cl] += 1
            r["frotas"][frota] += 1
            r["meses"][mes] += 1
            r["fazendas"].add(fazenda)
            s = agg_secao.setdefault((operacao, str(t["SECAO"])), {"Abaixo": 0, "Aderente": 0, "Acima": 0})
            s[cl] += 1
            por_secao_shp[str(t["SECAO"])].append((a, str(t["Layer"]), cl, frota))

        n_ok = len(amostras) - fora
        ide = sum(1 for a in amostras if classe(a.espacamento) == "Aderente")
        print(f"[{operacao}] {fazenda}: linhas={len(linhas)} amostras={len(amostras)} "
              f"fora de talhao={fora} ({100 * fora / max(len(amostras), 1):.1f}%) "
              f"aderente={100 * ide / max(len(amostras), 1):.2f}% secoes={sorted(por_secao_shp)}", flush=True)

        for secao, regs in por_secao_shp.items():
            caminho = os.path.join(pasta_saida, f"{secao}_{operacao}_Paralelismo")
            w = _abrir_shp(caminho, ["Layer", "Secao", "Aderencia", "Frota", "Data", "Operacao", "Espac"])
            for a, layer, cl, frota in regs:
                w.line([[(a.x, a.y), (a.x_vizinha, a.y_vizinha)]])
                w.record(layer, secao, cl, frota, data_proc, operacao, round(a.espacamento, 3))
            _fechar_shp(w, caminho)
        caminho = os.path.join(pasta_saida, f"{_nome(fazenda)}_{operacao}_Linhas")
        w = _abrir_shp(caminho, ["Layer", "Secao", "Frota", "Data", "Operacao"])
        for l, (frota, mes) in zip(linhas, meta):
            t = base.talhao_em(*l.interpolate(0.5, normalized=True).coords[0]) or {}
            w.line([list(l.coords)])
            w.record(str(t.get("Layer", "")), str(t.get("SECAO", "")), frota, data_proc, operacao)
        _fechar_shp(w, caminho)


_PRJ = None
METODO = "IMPLEMENTO"


def _abrir_shp(caminho: str, campos: list[str]):
    w = shapefile.Writer(caminho, shapeType=shapefile.POLYLINE, encoding="utf-8")
    for c in campos:
        if c == "Espac":
            w.field(c, "N", 8, 3)
        else:
            w.field(c, "C", 60)
    return w


def _fechar_shp(w, caminho: str) -> None:
    w.close()
    if _PRJ:
        shutil.copy(_PRJ, caminho + ".prj")
    with open(caminho + ".cpg", "w") as f:
        f.write("UTF-8")


def _nome(s: str) -> str:
    return re.sub(r'[\\/:*?"<>| ]+', "_", s).strip("_") or "SEM_NOME"


# ── saidas tabulares ─────────────────────────────────────────────────────────

def linhas_talhao(agg_talhao: dict, data_proc: int) -> list[list]:
    out = []
    for (operacao, layer), r in sorted(agg_talhao.items(), key=lambda kv: (kv[0][0], kv[1]["Secao"], kv[0][1])):
        total = r["Abaixo"] + r["Aderente"] + r["Acima"]
        frota = " / ".join(f for f, _ in r["frotas"].most_common() if f) or "0"
        for cl in ("Aderente", "Acima", "Abaixo"):
            out.append([data_proc, int(r["Secao"]), r["DESC_SECAO"], layer, r["Declividade"], cl, frota, "",
                        r[cl], total, round(100 * r[cl] / total, 2) if total else 0.0, operacao,
                        r["meses"].most_common(1)[0][0] if r["meses"] else "", METODO])
    return out


def linhas_secao(agg_secao: dict, data_proc: int) -> list[list]:
    out = []
    for (operacao, secao), r in sorted(agg_secao.items()):
        total = r["Abaixo"] + r["Aderente"] + r["Acima"]
        for cl in ("Aderente", "Acima", "Abaixo"):
            out.append([data_proc, int(secao), cl, r[cl], total, round(100 * r[cl] / total, 2) if total else 0.0,
                        None, operacao, METODO])
    return out


CAB_TALHAO = ["Data", "Secao", "DESC_SECAO", "Layer", "Declividade", "Aderencia", "Frota", "Frente",
              "Analisados", "Total_Analisados", "%_Aderencia", "Operacao", "Mes_Execucao", "Metodo"]
CAB_SECAO = ["Data", "Secao", "Aderencia", "Analisados_FME", "Total_Analisados", "%_Aderencia",
             "Analisados_AgroCad", "Operacao", "Metodo"]


def gravar_planilha(base_xlsx: str, saida_xlsx: str, talhao: list[list], secao: list[list]) -> None:
    """Copia a planilha e acrescenta as linhas novas nas abas Talhao e Secao;
    as linhas antigas ganham Operacao = CANA (tudo o que existia era cana)."""
    import openpyxl
    wb = openpyxl.load_workbook(base_xlsx)
    for aba, cab, novas in (("Talhao", CAB_TALHAO, talhao), ("Secao", CAB_SECAO, secao)):
        ws = wb[aba]
        atual = [c.value for c in ws[1]]
        for j, nome in enumerate(cab, start=1):
            if j > len(atual) or atual[j - 1] in (None, ""):
                ws.cell(row=1, column=j, value=nome)
        col_op, col_met = cab.index("Operacao") + 1, cab.index("Metodo") + 1
        for i in range(2, ws.max_row + 1):
            if ws.cell(row=i, column=2).value not in (None, ""):
                if ws.cell(row=i, column=col_op).value in (None, ""):
                    ws.cell(row=i, column=col_op, value="CANA")
                if ws.cell(row=i, column=col_met).value in (None, ""):
                    ws.cell(row=i, column=col_met, value="AGROCAD/FME")
        for linha in novas:
            ws.append(linha)
    wb.save(saida_xlsx)


def main():
    global _PRJ, MODO, METODO
    ap = argparse.ArgumentParser()
    ap.add_argument("--talhoes", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--data", required=True, help="data do processamento, AAAAMMDD")
    ap.add_argument("--torta")
    ap.add_argument("--torta-frotas")
    ap.add_argument("--cana")
    ap.add_argument("--cana-frotas")
    ap.add_argument("--cana-jdl", nargs="+", help="arvore(s) com .jdl soltos de cana")
    ap.add_argument("--modo", choices=["implemento", "trator"], default="implemento")
    ap.add_argument("--somente", nargs="+", help="torta: processa so estas pastas de fazenda (rodada incremental)")
    ap.add_argument("--frotas-maquinas", help="csv serie;frota (frota pelo trator gravado no .jdl)")
    ap.add_argument("--planilha-base")
    ap.add_argument("--planilha-saida")
    args = ap.parse_args()
    MODO = args.modo
    carregar_frotas_maquinas(args.frotas_maquinas)
    METODO = "TRATOR" if MODO == "trator" else "IMPLEMENTO"

    # tudo e gravado primeiro numa pasta local e so copiado pro destino (rede) no
    # fim: uma queda do drive de rede no meio nao perde o processamento
    import tempfile
    local = tempfile.mkdtemp(prefix=f"paralelismo_{args.data}_")
    print(f"pasta local de trabalho: {local}", flush=True)
    for arq in glob.glob(os.path.splitext(args.talhoes)[0] + ".*"):
        shutil.copy(arq, local)
    talhoes_local = os.path.join(local, os.path.basename(args.talhoes))
    planilha_base = None
    if args.planilha_base:
        planilha_base = os.path.join(local, "_base_" + os.path.basename(args.planilha_base))
        shutil.copy(args.planilha_base, planilha_base)
    saida_local = os.path.join(local, "saida")
    os.makedirs(saida_local)

    _PRJ = os.path.splitext(talhoes_local)[0] + ".prj"
    base = BaseTalhoes(talhoes_local)
    print(f"base de talhoes: {len(base.polis)} poligonos", flush=True)
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:31983", always_xy=True)

    agg_talhao, agg_secao = {}, {}
    if args.torta:
        frotas = mapa_frotas(args.torta_frotas, "jdl")
        processar("TORTA", grupos_torta(args.torta, frotas, transformer, args.somente), base, saida_local, args.data,
                  agg_talhao, agg_secao)
    if args.cana:
        frotas = mapa_frotas(args.cana_frotas, "fdl")
        processar("CANA", grupos_cana(args.cana, frotas, transformer), base, saida_local, args.data,
                  agg_talhao, agg_secao)
    if args.cana_jdl:
        grupos = collections.defaultdict(list)
        vistos = set()
        for raiz in args.cana_jdl:  # mesmo .jdl em duas raizes conta uma vez so
            for g, itens in grupos_jdl_soltos(raiz, transformer, ignorar=None, ja_vistos=vistos).items():
                grupos[g].extend(itens)
        processar("CANA", grupos, base, saida_local, args.data, agg_talhao, agg_secao)

    data_proc = int(args.data)
    talhao, secao = linhas_talhao(agg_talhao, data_proc), linhas_secao(agg_secao, data_proc)
    for nome, cab, linhas in (("talhoes.csv", CAB_TALHAO, talhao), ("secoes.csv", CAB_SECAO, secao)):
        with open(os.path.join(saida_local, nome), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(cab)
            w.writerows(linhas)
    print(f"talhoes: {len(agg_talhao)} | secoes: {len(agg_secao)}")
    planilha_local = None
    if planilha_base and args.planilha_saida:
        planilha_local = os.path.join(local, os.path.basename(args.planilha_saida))
        gravar_planilha(planilha_base, planilha_local, talhao, secao)

    shutil.copytree(saida_local, args.saida, dirs_exist_ok=True)
    print(f"resultados copiados para {args.saida}")
    if planilha_local:
        shutil.copy(planilha_local, args.planilha_saida)
        print(f"planilha: {args.planilha_saida}")


if __name__ == "__main__":
    main()
