"""Gera a apresentação semanal a partir de versoes/<semana>/dados/ (rode extrair.py antes).

Uso: python scripts/gerar.py S4M10 2026-10-20

Atualiza os dois arquivos do deck (Preview.html e .dc.html), exporta os PNGs em export-slides/
e monta "<semana> - Apresentacao Geotecnologia - Indicadores e Entregas.pptx".

Regras (combinadas com o Leo na S1M10):
- Colheita: status calculado pelo Hub; Sem Linhas NÃO entra em concluído. "BIS - N" soma na Frente N.
- Sistematização = módulo Preparo; concluído = fazenda com as 4 etapas OK. Painel "Ha por Etapa" (o Hub não tem equipe).
- Plantio: concluído = status Ok.
- Voos: API do GeoMap. Metas que não vêm da API ficam em METAS abaixo.
- Drone de aplicação: o que a Geo PROJETOU (não o que aplicou), todos os produtos, em hectares
  ("Área Apli" do shape publicado). Realizado = projetos da safra atual; pendente = DRONE_PENDENTE.
"""
import collections
import datetime
import html as htmllib
import json
import pathlib
import re
import sys

SRC = pathlib.Path(__file__).resolve().parent.parent
ARQS = [SRC / "Apresentacao Geotecnologia - Preview.html",
        SRC / "Apresentacao Geotecnologia - Indicadores e Entregas.dc.html"]

# Metas e referências que não vêm de nenhuma API (mantidas da S3M8)
META_ERVAS, META_FORN, META_HA_DIA = 20863, 3500, 250
DRONE_PENDENTE = 2000
SAFRA_ATUAL, INICIO_SAFRA = "26/27", "2026-04-01"

VERDE, OURO, AZUL, CINZA, ESCURO = "#019640", "#c99a2e", "#2f6fb0", "#a7b2a9", "#16261b"
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

SEMANA, CORTE = sys.argv[1].upper(), sys.argv[2]
DADOS = SRC / "versoes" / SEMANA.lower() / "dados"
CORTE_BR = f"{CORTE[8:10]}/{CORTE[5:7]}/{CORTE[:4]}"
RODAPE = f"{SEMANA} · Dados até {CORTE_BR}"
POS = f"posição de {CORTE_BR}"
MES_CORTE = MESES[int(CORTE[5:7]) - 1].lower()


def L(nome):
    return json.loads((DADOS / f"{nome}.json").read_text(encoding="utf-8"))


def n(x):
    return f"{round(x):,}".replace(",", ".")


def pct(a, b):
    return round(100 * a / b) if b else 0


def p1(x):
    return f"{round(x, 1):g}"


# ======================= agregação =======================
def agregar():
    talhoes = {t["layer"]: t for t in L("talhoes")}
    A = {}

    ct = L("colheita_talhoes")
    st, mes, frente, faz = (collections.defaultdict(float), collections.defaultdict(lambda: collections.defaultdict(float)),
                            collections.defaultdict(lambda: collections.defaultdict(float)), collections.defaultdict(list))

    def nome_frente(f):
        if not f:
            return "Indefinida"
        m = re.match(r"^(?:BIS - )?(\d+)$", f)
        if m:
            return "Frente " + m.group(1)
        return "FOCA" if f.startswith("FOCA") else "Outras"
    for r in ct:
        ha = r["area_ha"] or 0
        st[r["status"]] += ha
        mes[str(r["periodo_op"])][r["status"]] += ha
        frente[nome_frente(r["frente"])][r["status"]] += ha
        faz[r["cod_faz"]].append(r["status"])
    outras = sorted({r["frente"] for r in ct if r["frente"] and nome_frente(r["frente"]) == "Outras"})
    A["colheita"] = dict(total=sum(st.values()), status=st, mes=mes, frente=frente, n_tal=len(ct), faz_tot=len(faz),
                         faz_conc=sum(all(s == "CONCLUIDO" for s in v) for v in faz.values()), outras=outras)

    pl = []
    for r in L("talhao_plantio"):
        t = talhoes.get(r["layer"]) or {}
        pl.append(dict(r, area_ha=t.get("area_ha") or 0, cod_faz=t.get("cod_faz")))
    pst, pmes = collections.defaultdict(float), collections.defaultdict(lambda: collections.defaultdict(float))
    for r in pl:
        pst[r["projeto"]] += r["area_ha"]
        pmes[(r["mes_plantio"] or "Indef")[:7]][r["projeto"]] += r["area_ha"]
    A["plantio"] = dict(total=sum(pst.values()), status=pst, mes=dict(sorted(pmes.items(), key=lambda x: (x[0] == "Indef", x[0]))),
                        n_tal=len(pl), n_faz=len({r["cod_faz"] for r in pl}))

    etapas = sorted([e for e in L("etapas") if e["modulo_id"] == "preparo"], key=lambda e: e["ordem"])
    entregas = {r["layer"]: r for r in L("preparo_entregas")}
    # O ciclo 25-26 (lançamento único pelo PLANAGRI) não entra no slide: estamos no ciclo 26-27.
    prep = [r for r in L("talhao_preparo") if (entregas.get(r["layer"]) or {}).get("origem") != "ciclo_25_26"]
    fora_25_26 = sum((talhoes.get(l) or {}).get("area_ha") or 0 for l, r in entregas.items() if r["origem"] == "ciclo_25_26")
    por_etapa = {e["nome"]: [set(), 0.0] for e in etapas}
    por_etapa["Entregue"] = [set(), 0.0]
    prmes = collections.defaultdict(float)
    # Início do ciclo atual: gerar.py não carrega `parametros` (colheita_safra), então usa o último 1º de abril
    # até hoje (2026-04-01 em 2026), que é o mesmo que hub.ciclo_inicio() devolve.
    hoje = datetime.date.today()
    inicio_ciclo = datetime.date(hoje.year if hoje >= datetime.date(hoje.year, 4, 1) else hoje.year - 1, 4, 1)
    total = 0.0
    for r in prep:
        t = talhoes.get(r["layer"])
        if not t:
            continue
        ha = t["area_ha"] or 0
        total += ha
        nome = "Entregue" if r["etapa"] == "Ok" else r["etapa"]
        por_etapa[nome][0].add(t["cod_faz"])
        por_etapa[nome][1] += ha
        en = entregas.get(r["layer"])
        if en and en.get("entregue_em"):   # entregue_em nulo (data vazia no sistema antigo) fica fora do gráfico mensal
            # mês pelo calendário de São Paulo (UTC-3, sem horário de verão desde 2019), não pela data UTC
            dt_sp = datetime.datetime.fromisoformat(en["entregue_em"].replace("Z", "+00:00")).astimezone(datetime.timezone(datetime.timedelta(hours=-3)))
            if en["origem"] == "lancamento_inicial":
                prmes["Lançamento inicial (jun/26)"] += ha
            elif dt_sp.date() >= inicio_ciclo:   # gráfico mensal só mostra o ciclo atual (D6)
                prmes[dt_sp.strftime("%Y-%m")] += ha
    por_etapa = {k: [len(v[0]), v[1]] for k, v in por_etapa.items()}
    A["preparo"] = dict(total=total, n_faz=len({talhoes[r["layer"]]["cod_faz"] for r in prep if r["layer"] in talhoes}),
                        n_tal=len(prep), etapa=por_etapa, fora_25_26=fora_25_26,
                        mes=dict(sorted(prmes.items(), key=lambda x: (not x[0].startswith("Lan"), x[0]))))

    # drone: safra do projeto vigente + área ("Área Apli")
    rev = {r["id"]: r for r in L("projeto_revisoes")}
    projetos = {}
    for r in L("arquivos_vigentes"):
        if r["modulo_id"] == "drone":
            projetos[(r["projeto_id"], r["documento"])] = (r["cod_faz"], rev.get(r["revisao_id"], {}))
    area = {(x[0], x[1]): x[3] or 0 for x in L("area_drone")}

    def safra(rv):
        motivo = rv.get("motivo") or ""
        s = re.findall(r"(?<!\d)(20\d\d)-(20\d\d)(?!\d)", motivo)
        if s:
            return f"{s[-1][0][2:]}/{s[-1][1][2:]}"
        s = re.findall(r"(\d\d/\d\d) Rev", motivo)
        if s:
            return max(s)
        if motivo.startswith("Importado do legado"):
            return "?"
        d = datetime.date.fromisoformat((rv.get("criado_em") or "1900-01-01")[:10])   # projeto feito no Hub
        a = d.year if d.month >= 4 else d.year - 1
        return f"{str(a)[2:]}/{str(a + 1)[2:]}"
    por = collections.defaultdict(float)
    n_proj, faz_proj = collections.Counter(), collections.defaultdict(set)
    for (pid, doc), (cod, rv) in projetos.items():
        s = safra(rv)
        por[(doc, s)] += area.get((pid, doc), 0)
        n_proj[s] += 1
        faz_proj[s].add(cod)
    por = {k: round(v) for k, v in por.items()}   # arredonda por grupo para os totais fecharem
    por_safra = collections.defaultdict(int)
    for (doc, s), v in por.items():
        por_safra[s] += v
    A["drone"] = dict(por_safra=por_safra, n_proj=n_proj, faz_safra={k: len(v) for k, v in faz_proj.items()},
                      n_base=len(projetos), faz_base=len({c for c, _ in projetos.values()}))

    A["voos"] = L("voos")
    return A


# ======================= blocos de HTML (mesma marcação da S3M8) =======================
def kpi(rotulo, valor, sub, cor, grande=False):
    fs_l, fs_v, fs_s, pad = ("14px", "38px", "14px", "20px 24px") if grande else ("13px", "32px", "13px", "18px 20px")
    return (f'<div style="flex:1;background:#ffffff;border:1px solid #e3ece0;border-top:4px solid {cor};border-radius:10px;padding:{pad};box-sizing:border-box;">'
            f'<div style="font-size:{fs_l};letter-spacing:1px;text-transform:uppercase;color:#8a978d;font-weight:600;">{rotulo}</div>'
            f'<div style="font-size:{fs_v};font-weight:700;color:{"#5b6b60" if cor == CINZA else cor};margin-top:6px;">{valor}</div>'
            f'<div style="font-size:{fs_s};color:#8a978d;margin-top:2px;">{sub}</div></div>')


def progresso(p, mt="22px"):
    return (f'<div style="display:flex;align-items:center;gap:18px;margin-top:{mt};">'
            '<span style="font-size:14px;letter-spacing:1px;text-transform:uppercase;color:#8a978d;font-weight:600;white-space:nowrap;">Progresso Geral</span>'
            f'<div style="flex:1;height:14px;background:#e3ece0;border-radius:7px;overflow:hidden;"><div style="width:{p}%;height:100%;background:linear-gradient(90deg,#019640,#7BBB34);border-radius:7px;"></div></div>'
            f'<span style="font-size:20px;font-weight:700;color:#019640;">{p}%</span></div>')


def colunas(barras, fs="10px", gap="10px", mt="10px"):
    """barras: [(rótulo, [(cor, ha), ...] de baixo para cima)]"""
    if not barras:
        return ""
    mx = max(sum(h for _, h in segs) for _, segs in barras) or 1
    out = [f'<div style="display:flex;align-items:flex-end;gap:{gap};flex:1;margin-top:{mt};">']
    for rot, segs in barras:
        tot = sum(h for _, h in segs)
        segs = [(c, h) for c, h in segs if h > 0]
        partes = "".join(f'<div style="background:{c};height:{p1(100 * h / tot)}%;{"border-radius:2px 2px 0 0;" if i == len(segs) - 1 else ""}"></div>'
                         for i, (c, h) in enumerate(segs))
        out.append(f'<div style="display:flex;flex-direction:column;align-items:center;justify-content:flex-end;flex:1;height:100%;">'
                   f'<div style="font-size:{fs};color:#8a978d;">{n(tot)}</div>'
                   f'<div style="width:100%;display:flex;flex-direction:column-reverse;height:{p1(100 * tot / mx)}%;">{partes}</div>'
                   f'<div style="font-size:{fs};color:#8a978d;margin-top:4px;">{rot}</div></div>')
    return "".join(out) + "</div>"


def linhas(itens, w_rot="70px", fs="11px", h="13px", gap="8px"):
    """itens: [(rótulo, [(cor, ha), ...] da esquerda para a direita)]; escala pelo maior total."""
    mx = max(sum(v for _, v in segs) for _, segs in itens) or 1
    out = [f'<div style="display:flex;flex-direction:column;gap:{gap};margin-top:10px;flex:1;justify-content:center;">']
    for rot, segs in itens:
        barra = "".join(f'<div style="width:{p1(100 * v / mx)}%;background:{c};"></div>' for c, v in segs if v > 0)
        out.append(f'<div style="display:flex;align-items:center;gap:8px;"><span style="width:{w_rot};font-size:{fs};color:#5b6b60;">{rot}</span>'
                   f'<div style="flex:1;height:{h};display:flex;border-radius:2px;overflow:hidden;background:#f2f6f1;">{barra}</div>'
                   f'<span style="font-size:{fs};color:#8a978d;width:44px;">{n(sum(v for _, v in segs))}</span></div>')
    return "".join(out) + "</div>"


def legenda(itens, fs="11px", mt="10px"):
    return (f'<div style="display:flex;gap:16px;margin-top:{mt};font-size:{fs};color:#5b6b60;">'
            + "".join(f'<span><span style="display:inline-block;width:9px;height:9px;background:{c};border-radius:2px;margin-right:4px;"></span>{t}</span>' for c, t in itens)
            + "</div>")


def painel(titulo, corpo, flex="1", pad="18px 22px"):
    return (f'<div style="flex:{flex};background:#ffffff;border:1px solid #e3ece0;border-radius:10px;padding:{pad};display:flex;flex-direction:column;box-sizing:border-box;">'
            f'<div style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#8a978d;font-weight:600;">{titulo}</div>{corpo}</div>')


def fonte(txt):
    return f'<div style="font-size:11px;color:#8a978d;margin-top:8px;">{txt}</div>'


def subtitulo(txt, mb="18px", fs="22px"):
    return f'<p style="margin:0 0 {mb};font-size:{fs};font-weight:300;color:#5b6b60;max-width:1600px;">{txt}</p>'


def rot_mes(chave):
    if chave == "Indef":
        return "Indef."
    a, m = chave.split("-")
    return f"{MESES[int(m) - 1]}/{a[2:]}"


# ======================= slides =======================
def colheita(A):
    c = A["colheita"]
    s, tot = c["status"], c["total"]
    conc, sl, rea, af = (s.get(k, 0) for k in ("CONCLUIDO", "SEM LINHAS", "REAVALIAR", "A FAZER"))
    p = pct(conc, tot)
    seg = lambda d: [(AZUL, d.get("A FAZER", 0)), (OURO, d.get("REAVALIAR", 0)), (CINZA, d.get("SEM LINHAS", 0)), (VERDE, d.get("CONCLUIDO", 0))]
    seg_l = lambda d: [(VERDE, d.get("CONCLUIDO", 0)), (CINZA, d.get("SEM LINHAS", 0)), (OURO, d.get("REAVALIAR", 0)), (AZUL, d.get("A FAZER", 0))]
    barras = [(MESES[m - 1], seg(c["mes"].get(str(m), {}))) for m in range(3, 13)]
    ordem = [f"Frente {i}" for i in range(1, 30)] + ["FOCA", "Outras", "Indefinida"]
    itens = [(k, seg_l(c["frente"][k])) for k in ordem if k in c["frente"]]
    sem_per = sum(c["mes"].get("None", {}).values())
    outras = " e ".join(o.title() for o in c["outras"]) or "—"
    return ('<div style="flex:1;padding:40px 100px 24px;display:flex;flex-direction:column;box-sizing:border-box;">'
            + subtitulo(f"Dados do Hub Geotech — módulo Colheita · {POS}.")
            + '<div style="display:flex;gap:16px;">'
            + kpi("Área Total", n(tot), f'{c["faz_conc"]}/{c["faz_tot"]} faz. concluídas', ESCURO)
            + kpi("Ha Concluído", n(conc), f"{p}% do total", VERDE)
            + kpi("Ha Reavaliar", n(rea), "projeto de safra anterior", OURO)
            + kpi("Ha A Fazer", n(af), "hectares restantes", AZUL)
            + kpi("Ha Sem Linhas", n(sl), "aguardando voo", CINZA)
            + "</div>" + progresso(p, "20px")
            + '<div style="display:flex;gap:20px;margin-top:22px;flex:1;">'
            + painel("Ha Programado por Mês", colunas(barras)
                     + legenda([(VERDE, "Concluído"), (CINZA, "Sem Linhas"), (OURO, "Reavaliar"), (AZUL, "A Fazer")])
                     + fonte(f"{n(sem_per)} ha sem período programado no iCol (aparecem como “Indefinida” no painel de frentes)."), "1.15")
            + painel("Ha por Frente", linhas(itens, gap="7px")
                     + fonte(f'Fonte: Hub Geotech (colheita_talhoes), {n(c["n_tal"])} talhões / {c["faz_tot"]} fazendas · dados exatos · {POS}. '
                             f"“BIS - N” somado à Frente N; FOCA agrupa as frentes FOCA; “Outras” = {outras}."))
            + "</div></div>")


def sistematizacao(A):
    pr = A["preparo"]
    tot = pr["total"]
    ent = pr["etapa"]["Entregue"]
    p = pct(ent[1], tot)
    barras = [(k if k.startswith("Lan") else rot_mes(k), [(VERDE, v)]) for k, v in pr["mes"].items()]
    itens = [(f"{e} ({v[0]})", [(VERDE if e == "Entregue" else AZUL, v[1])]) for e, v in pr["etapa"].items()]
    return ('<div style="flex:1;padding:48px 100px 30px;display:flex;flex-direction:column;box-sizing:border-box;">'
            + subtitulo(f"Dados do Hub Geotech — módulo Preparo · {POS}.")
            + '<div style="display:flex;gap:20px;">'
            + kpi("Área Total", n(tot), f'{pr["n_faz"]} fazendas', ESCURO, True)
            + kpi("Ha Concluído", n(ent[1]), f"{p}% do total · {ent[0]} fazendas entregues", VERDE, True)
            + kpi("Ha A Fazer", n(tot - ent[1]), "hectares restantes", AZUL, True)
            + "</div>" + progresso(p)
            + '<div style="display:flex;gap:20px;margin-top:24px;flex:1;">'
            + painel("Projetos Entregues pela Geotecnologia por Mês", colunas(barras, mt="12px") + legenda([(VERDE, "Entregue")], "12px", "12px"), "1", "20px 24px")
            + painel("Ha por Etapa (fazendas)", linhas(itens, "150px", "12px", "15px", "14px")
                     + fonte(f'Fonte: Hub Geotech (talhão por etapa do Preparo), {pr["n_tal"]} talhões / {pr["n_faz"]} fazendas · dados exatos · {POS}. '
                             "Cada talhão aparece na etapa em que está; “Entregue” = Ok. Mês = data da entrega no Hub; "
                             f"ciclo 25-26 fora do slide ({n(pr['fora_25_26'])} ha lançados pelo PLANAGRI)."),
                     "1", "20px 24px")
            + "</div></div>")


def plantio(A):
    pl = A["plantio"]
    s, tot = pl["status"], pl["total"]
    conc = s.get("Ok", 0)
    aberto = tot - conc
    p = pct(conc, tot)
    barras = [(rot_mes(k), [(AZUL, sum(x for st, x in v.items() if st != "Ok")), (VERDE, v.get("Ok", 0))]) for k, v in pl["mes"].items()]
    nota = (f"* De {n(aberto)} ha em aberto: {n(s.get('Aguard. Map.', 0))} ha aguardando mapeamento, {n(s.get('Pendente', 0))} ha pendentes, "
            f"{n(s.get('Ag. Mapa', 0))} ha aguardando mapa de plantio e {n(s.get('Andamento', 0))} ha em andamento.")
    return ('<div style="flex:1;padding:48px 100px 30px;display:flex;flex-direction:column;box-sizing:border-box;">'
            + subtitulo(f"Dados do Hub Geotech — módulo Plantio · {POS}.")
            + '<div style="display:flex;gap:20px;">'
            + kpi("Área Total", n(tot), f'{pl["n_faz"]} fazendas', ESCURO, True)
            + kpi("Ha Concluído", n(conc), f"{p}% do total", VERDE, True)
            + kpi("Ha A Fazer", n(aberto) + "*", "hectares restantes", AZUL, True)
            + "</div>" + progresso(p)
            + f'<div style="font-size:13px;color:#8a978d;margin-top:8px;">{nota}</div>'
            + '<div style="background:#ffffff;border:1px solid #e3ece0;border-radius:10px;padding:22px 26px;display:flex;flex-direction:column;box-sizing:border-box;margin-top:16px;flex:1;">'
            + '<div style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#8a978d;font-weight:600;">Ha Programado por Mês de Plantio</div>'
            + colunas(barras, "12px", "16px", "14px")
            + legenda([(VERDE, "Concluído"), (AZUL, "A Fazer")], "13px", "14px")
            + fonte(f'Fonte: Hub Geotech (talhao_plantio, mês de plantio do PLANAGRI), {pl["n_tal"]} talhões / {pl["n_faz"]} fazendas · dados exatos · {POS}.')
            + "</div></div>")


def voos_numeros(A):
    V = A["voos"]
    r = V["resumo"]
    forn = next((t for t in V["porTipo"] if t["tipo"] == "Falhas Plantio Forn."), {"realizadoHa": 0, "aVoarHa": 0})
    fora = max(0, META_FORN - forn["realizadoHa"] - forn["aVoarHa"])
    return r["realizadoHa"], r["aVoarHa"] + fora, fora, forn


def voos(A):
    V = A["voos"]
    r, u = V["resumo"], V["ultimos15DiasUteis"]
    real, avoar, fora, forn = voos_numeros(A)
    tot = real + avoar
    p = pct(real, tot)
    esperado = 15 * META_HA_DIA
    dm = lambda iso: f"{iso[8:10]}/{iso[5:7]}"
    consulta = (V.get("atualizadoEm") or datetime.date.today().isoformat())[:10]
    linhas_t = []
    for t in V["porTipo"]:
        proj, marca = t["realizadoHa"] + t["aVoarHa"], ""
        if t["tipo"] == "Ervas Daninhas":
            proj, marca = max(META_ERVAS, proj), "*"
        elif t["tipo"] == "Falhas Plantio Forn.":
            proj, marca = max(META_FORN, proj), "**"
        linhas_t.append((t["tipo"], t["realizadoHa"], proj, marca))
    linhas_t.sort(key=lambda x: -x[2])
    rows = []
    for nome, re_, pj, mk in linhas_t:
        w = round(100 * re_ / pj, 1) if pj else 0
        rot = f'{n(re_)}'
        dentro = f'<span style="font-size:11px;font-weight:700;color:#ffffff;white-space:nowrap;">{rot}</span>' if w >= 8 else ""
        fora_rot = "" if w >= 8 else f'<span style="position:absolute;left:{p1(w)}%;top:50%;transform:translate(6px,-50%);font-size:11px;font-weight:700;color:#2f6fb0;white-space:nowrap;">{rot}</span>'
        rows.append(f'<div style="display:flex;align-items:center;gap:10px;"><span style="width:190px;font-size:13px;color:#5b6b60;">{nome}</span>'
                    f'<div style="flex:1;height:20px;border-radius:3px;position:relative;background:rgba(47,111,176,0.28);">'
                    f'<div style="position:absolute;left:0;top:0;height:100%;width:{p1(w)}%;background:#019640;border-radius:3px;display:flex;align-items:center;justify-content:center;">{dentro}</div>{fora_rot}</div>'
                    f'<span style="font-size:13px;color:#2f6fb0;width:64px;text-align:right;">{n(pj)}{mk}</span></div>')
    nota = (f"* Inclui {n(fora)} ha de falha de plantio em área de fornecedor ainda fora do agendamento formal (meta de {n(META_FORN)} ha, "
            f"dos quais {n(forn['realizadoHa'])} ha já voados e {n(forn['aVoarHa'])} ha na fila). "
            f"** Últimos 15 dias úteis: {dm(u['de'])} a {dm(u['ate'])}/{u['ate'][:4]}, {u['diasComVoo']} dias com voo, {n(u['talhoes'])} talhões. "
            f"Esperado = 15 dias úteis × {META_HA_DIA} ha/dia (média de voo diário).")
    aviso = ""
    if V.get("desatualizado"):
        t = datetime.datetime.fromisoformat(V["atualizadoEm"].replace("Z", "+00:00")) - datetime.timedelta(hours=3)
        aviso = f" Números da última busca bem-sucedida no DroneManagement ({t:%d/%m %Hh%M})."
    return ('<div style="flex:1;padding:48px 100px 30px;display:flex;flex-direction:column;box-sizing:border-box;">'
            + subtitulo(f"Painel de controle — Voos com Drone · abr–{MES_CORTE}/{CORTE[:4]}, por tipo de missão.{aviso}")
            + '<div style="display:flex;gap:20px;">'
            + kpi("Área Total", n(tot), f'{n(r["realizadoTalhoes"])} talhões voados + {n(r["aVoarTalhoes"])} a voar', ESCURO, True)
            + kpi("Ha Realizado", n(real), f"{p}% do total", VERDE, True)
            + kpi("Ha Previsto (A Voar)", n(avoar) + "*", "hectares restantes", AZUL, True)
            + kpi("Últimos 15 Dias Úteis**", f'{n(u["ha"])} ha', f'vs. {n(esperado)} ha esperado ({pct(u["ha"], esperado)}%)', OURO, True)
            + "</div>" + progresso(p)
            + f'<div style="font-size:13px;color:#8a978d;margin-top:8px;">{nota}</div>'
            + '<div style="background:#ffffff;border:1px solid #e3ece0;border-radius:10px;padding:20px 28px;display:flex;flex-direction:column;box-sizing:border-box;margin-top:16px;flex:1;">'
            + '<div style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#8a978d;font-weight:600;">Ha Realizado × Projetado (por Tipo)</div>'
            + '<div style="display:flex;align-items:center;gap:10px;margin-top:14px;"><span style="width:190px;"></span><span style="flex:1;"></span>'
            + '<span style="font-size:11px;color:#2f6fb0;width:64px;text-align:right;font-weight:600;">Projetado</span></div>'
            + '<div style="display:flex;flex-direction:column;gap:11px;margin-top:8px;flex:1;justify-content:center;">' + "".join(rows) + "</div>"
            + '<div style="display:flex;gap:16px;margin-top:10px;font-size:12px;color:#5b6b60;">'
            + '<span><span style="display:inline-block;width:9px;height:9px;background:#019640;border-radius:2px;margin-right:4px;"></span>Realizado</span>'
            + '<span><span style="display:inline-block;width:9px;height:9px;background:rgba(47,111,176,0.28);border:1px solid #2f6fb0;border-radius:2px;margin-right:4px;"></span>Projetado</span></div>'
            + fonte(f"Fonte: GeoMap / DroneManagement (integracao/voos/indicadores). Realizado = voos com status “Voado” de 01/04 a {CORTE_BR}; "
                    f"a voar = fila liberada em {dm(consulta)}/{consulta[:4]}. Projetado = realizado + a voar. "
                    "“Outros” = Expansões, Sinistro, Ambiental, Drone Aplicação e Experimentação Agrícola. "
                    f"* Ervas Daninhas: projetado = meta oficial do ano-safra. ** Falhas Plantio Forn.: projetado = {n(META_FORN)} ha de área de fornecedor.")
            + "</div></div>")


def drone(A):
    d = A["drone"]
    real = d["por_safra"].get(SAFRA_ATUAL, 0)
    base = sum(d["por_safra"].values())
    p = pct(real, real + DRONE_PENDENTE)
    linhas_safra = [(s, d["por_safra"].get(s, 0)) for s in (SAFRA_ATUAL, "25/26", "24/25")]
    linhas_safra.append(("Anteriores / sem safra", base - sum(v for _, v in linhas_safra)))
    mx = max(v for _, v in linhas_safra) or 1
    barras = "".join(
        f'<div style="display:flex;align-items:center;gap:14px;margin-top:16px;">'
        f'<span style="width:200px;font-size:20px;color:#eaf5ee;">{s}</span>'
        f'<div style="flex:1;height:18px;background:rgba(255,255,255,.15);border-radius:4px;overflow:hidden;"><div style="width:{p1(100 * v / mx)}%;height:100%;background:{"#ffffff" if s == SAFRA_ATUAL else "#9fd6b0"};"></div></div>'
        f'<span style="width:90px;text-align:right;font-size:22px;font-weight:600;">{n(v)}</span></div>'
        for s, v in linhas_safra)
    card = lambda r, v, c: (f'<div style="flex:1;background:#f2f6f1;border-radius:10px;padding:24px 22px;border-left:6px solid {c};">'
                            f'<div style="font-size:17px;letter-spacing:1px;text-transform:uppercase;color:#8a978d;">{r}</div>'
                            f'<div style="font-size:40px;font-weight:700;color:#16261b;margin-top:8px;">{v}</div></div>')
    return ('<div style="flex:1;padding:48px 100px 30px;display:flex;flex-direction:column;box-sizing:border-box;">'
            + subtitulo("Projetos de drone de aplicação elaborados pela Geotecnologia — normal e catação.", "8px", "26px")
            + '<div style="display:flex;gap:48px;flex:1;margin-top:14px;"><div style="flex:1.3;display:flex;flex-direction:column;">'
            + '<div style="display:flex;align-items:baseline;gap:18px;">'
            + f'<div style="font-size:96px;font-weight:700;color:#019640;line-height:1;">{n(real)}</div>'
            + f'<div style="font-size:20px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:#5a9020;background:#eef6e6;padding:8px 18px;border-radius:20px;">Ha em projetos feitos na safra {SAFRA_ATUAL}</div></div>'
            + '<div style="display:flex;align-items:center;gap:18px;margin-top:22px;"><div style="flex:1;height:22px;background:#e3ece0;border-radius:11px;overflow:hidden;">'
            + f'<div style="width:{p}%;height:100%;background:linear-gradient(90deg,#019640,#7BBB34);border-radius:11px;"></div></div>'
            + f'<span style="font-size:28px;font-weight:700;color:#019640;">{p}%</span></div>'
            + '<div style="display:flex;gap:24px;margin-top:26px;">'
            + card("Área realizada", f"{n(real)} ha", VERDE) + card("Área pendente", f"{n(DRONE_PENDENTE)} ha*", AZUL)
            + "</div>"
            + f'<div style="margin-top:26px;font-size:22px;font-weight:300;color:#4a564d;line-height:1.4;">{n(d["n_proj"].get(SAFRA_ATUAL, 0))} projetos novos nesta safra (abr–{MES_CORTE}/{CORTE[:4]}), em {n(d["faz_safra"].get(SAFRA_ATUAL, 0))} fazendas.</div>'
            + '<div style="margin-top:10px;font-size:17px;font-weight:300;color:#8a978d;line-height:1.4;">* Área pendente informada pela equipe (mantida da S3M8). Progresso = realizado ÷ (realizado + pendente). Área = campo “Área Apli” (ha) do shape de aplicação publicado; safra = pasta de origem do projeto registrada na importação para o Hub (ou data da revisão, para projetos feitos no Hub).</div>'
            + "</div>"
            + '<div style="flex:1;background:#019640;border-radius:12px;padding:36px 38px;color:#ffffff;display:flex;flex-direction:column;box-sizing:border-box;">'
            + '<div style="font-size:20px;letter-spacing:1.5px;text-transform:uppercase;color:#bfe6cb;font-weight:600;">Base de projetos vigentes (ha)</div>'
            + f'<div style="font-size:96px;font-weight:700;line-height:1;margin-top:16px;">{n(base)}</div>'
            + f'<div style="font-size:22px;font-weight:300;margin-top:16px;color:#eaf5ee;line-height:1.4;">ha de aplicação em {n(d["n_base"])} projetos disponíveis no portal de downloads ({n(d["faz_base"])} fazendas) — por safra de elaboração:</div>'
            + f'<div style="margin-top:12px;">{barras}</div>'
            + '<div style="flex:1;"></div>'
            + f'<div style="font-size:16px;font-weight:300;color:#cbe8d4;line-height:1.4;">Fonte: Hub Geotech — portal de downloads, módulo Drone (revisões vigentes) · {POS}.</div>'
            + "</div></div></div>")


def divisoria(A):
    c, pr, pl = A["colheita"], A["preparo"], A["plantio"]
    v_real, v_prev, _, _ = voos_numeros(A)
    d_real = A["drone"]["por_safra"].get(SAFRA_ATUAL, 0)
    pr_conc, pl_conc, c_conc = pr["etapa"]["Entregue"][1], pl["status"].get("Ok", 0), c["status"].get("CONCLUIDO", 0)

    def item(titulo, l1, v1, l2, v2, p):
        return (f'<div><div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;">'
                f'<span style="font-size:24px;font-weight:600;">{titulo}</span>'
                f'<span style="font-size:19px;font-weight:600;color:#16261b;">{l1} <span style="color:#019640;font-weight:700;">{v1} ha</span> &nbsp;·&nbsp; {l2} <span style="color:#5b6b60;font-weight:700;">{v2} ha</span></span></div>'
                f'<div style="height:22px;background:#e3ece0;border-radius:11px;overflow:hidden;">'
                f'<div style="width:{p}%;height:100%;background:linear-gradient(90deg,#019640,#7BBB34);border-radius:11px;"></div></div></div>')
    return ('<div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:0 100px;box-sizing:border-box;">'
            '<p style="margin:0 0 30px;font-size:32px;font-weight:300;color:#5b6b60;max-width:1400px;line-height:1.4;">A seguir, o desempenho dos cinco indicadores operacionais do setor.</p>'
            '<div style="display:flex;flex-direction:column;gap:24px;max-width:1600px;">'
            + item("Projetos de Colheita", "Concluído", n(c_conc), "A Fazer", n(c["status"].get("A FAZER", 0)), pct(c_conc, c["total"]))
            + item("Projetos de Sistematização", "Concluído", n(pr_conc), "A Fazer", n(pr["total"] - pr_conc), pct(pr_conc, pr["total"]))
            + item("Projetos de Plantio", "Concluído", n(pl_conc), "A Fazer", n(pl["total"] - pl_conc), pct(pl_conc, pl["total"]))
            + item("Voos com Drone", "Realizado", n(v_real), "Previsto", n(v_prev), pct(v_real, v_real + v_prev))
            + item("Projetos de Drone de Aplicação", "Realizado", n(d_real), "Pendente", n(DRONE_PENDENTE), pct(d_real, d_real + DRONE_PENDENTE))
            + "</div></div>")


GERADORES = {"Indicadores Operacionais": divisoria, "Projetos de Colheita": colheita, "Projetos de Sistematização": sistematizacao,
             "Projetos de Plantio": plantio, "Voos com Drone": voos, "Projetos de Drone de Aplicação": drone}
NOTAS = {
    "Indicador · Projetos de Colheita": "Dados do Hub Geotech (view hub.colheita_talhoes), granularidade de talhão. Status calculado pelo Hub: Sem Linhas é categoria própria (aguarda voo) e não entra em Concluído; Reavaliar = projeto com ciclo diferente da safra atual.",
    "Indicador · Projetos de Sistematização": "Dados do Hub Geotech (módulo Preparo): área = talhões da demanda do Preparo; etapas por fazenda (Identificação → Escoamento → Observações → Preparo). Concluído = fazendas com as 4 etapas OK. O Hub não registra equipe, por isso o painel mostra a área por etapa.",
    "Indicador · Projetos de Plantio": "Dados do Hub Geotech (hub.talhao_plantio), granularidade de talhão. Concluído = status Ok; em aberto = Aguard. Map., Pendente, Andamento e Ag. Mapa. Mês de plantio vem do PLANAGRI.",
    "Indicador · Voos com Drone": f"Dados da API do GeoMap (integracao/voos/indicadores), que lê o DroneManagement. Realizado = status Voado com data de voo de 01/04 a {CORTE_BR} (horário de Brasília); a voar = fila liberada no dia da consulta. Metas que não vêm da API (Ervas Daninhas {n(META_ERVAS)} ha, área de fornecedor {n(META_FORN)} ha, {META_HA_DIA} ha/dia) mantidas da S3M8.",
    "Indicador · Projetos de Drone de Aplicação": f"Hectares de aplicação (campo Área Apli do shape publicado) dos projetos de drone (todos os produtos) do portal de downloads do Hub Geotech, documentos normal e catação. Mostra o que a Geo projetou, não o que foi aplicado. Realizado = projetos da safra {SAFRA_ATUAL}; pendente = {n(DRONE_PENDENTE)} ha informados pela equipe.",
}


def atualizar_html(A):
    for caminho in ARQS:
        secoes = re.split(r"(?=<section\b)", caminho.read_text(encoding="utf-8"))
        for i, sec in enumerate(secoes):
            m = re.search(r"<h2[^>]*>([^<]+)</h2>", sec)
            titulo = m.group(1) if m else ""
            sec = re.sub(r"S\dM\d{1,2} · Dados até \d\d/\d\d/\d{4}", RODAPE, sec)
            if titulo in GERADORES:
                marcador = ('<div style="flex:1;display:flex;flex-direction:column;justify-content:center;'
                            if titulo == "Indicadores Operacionais" else '<div style="flex:1;padding:')
                ini, fim = sec.index(marcador), sec.index('<div style="height:48px;flex:none;')
                sec = sec[:ini] + GERADORES[titulo](A) + "\n      " + sec[fim:]
                lab = re.search(r'data-label="([^"]+)"', sec)
                if lab and lab.group(1) in NOTAS:
                    sec = re.sub(r'data-speaker-notes="[^"]*"', 'data-speaker-notes="' + htmllib.escape(NOTAS[lab.group(1)]) + '"', sec, count=1)
            secoes[i] = sec
        caminho.write_text("".join(secoes), encoding="utf-8")
        print("  atualizado:", caminho.name)


NOMES = ["01-divisoria", "02-colheita", "03-sistematizacao", "04-plantio", "05-voos-drone", "06-drone-aplicacao"]


def exportar_png(pasta, escala):
    from playwright.sync_api import sync_playwright
    pasta.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=escala)
        pg.goto(ARQS[0].as_uri())
        pg.wait_for_load_state("networkidle")
        pg.evaluate("document.fonts.ready")
        for i, nome in enumerate(NOMES):
            pg.evaluate(f"""() => {{ document.querySelectorAll('.slide').forEach((s,j)=>{{s.classList.toggle('active', j=={i}); s.style.transform='none';}});
                           const nav=document.querySelector('.nav'); if (nav) nav.style.display='none'; }}""")
            pg.locator(".slide.active section").screenshot(path=str(pasta / f"{nome}.png"))
        b.close()


def montar_pptx():
    from pptx import Presentation
    dc = ARQS[1].read_text(encoding="utf-8")
    notas = [htmllib.unescape(x) for x in re.findall(r'<section[^>]*data-speaker-notes="([^"]*)"', dc)]
    prs = Presentation()
    prs.slide_width, prs.slide_height = 12192000, 6858000
    for i, nome in enumerate(NOMES):
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        sl.shapes.add_picture(str(SRC / "export-slides" / f"{nome}.png"), 0, 0, prs.slide_width, prs.slide_height)
        if i < len(notas):
            sl.notes_slide.notes_text_frame.text = notas[i]
    saida = SRC / f"{SEMANA.lower()} - Apresentacao Geotecnologia - Indicadores e Entregas.pptx"
    prs.save(saida)
    print("  pptx:", saida.name)


if __name__ == "__main__":
    A = agregar()
    atualizar_html(A)
    previa = "--previa" in sys.argv
    exportar_png(SRC / "versoes" / SEMANA.lower() / "previa" if previa else SRC / "export-slides", 1 if previa else 4)
    if not previa:
        montar_pptx()
    print("ok")
