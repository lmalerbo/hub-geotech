"""Interface pra copiar dados de executados de pen-drive (JDLink .jdl ou
GS3_2630) pra pasta de executados, organizados por fazenda.

Uso: da duplo-clique (ou "python copiar_jdl_pendrive.py"). Abre uma janela
com campos de origem/destino (cada um com botao "Procurar..."), botao
"Copiar" e um log de progresso. Detecta sozinho qual formato tem na
origem (pode ter os dois juntos, ex: apontando pra raiz do pen-drive).

  Origem: pasta do pen-drive. Pode ser:
    - a pasta "log" dentro de JD-Data (ex: D:\\JD-Data\\log), ou uma pasta
      acima que contenha isso (ex: D:\\ com JD-Data dentro)
    - a pasta GS3_2630 (ex: D:\\GS3_2630), ou uma pasta acima
  Destino: a pasta da campanha dentro de EXECUTADOS
           (ex: G:\\...\\EXECUTADOS\\2026-2027\\TORTA, ou ADUBO, GRADE etc.)

JDLink (.jdl): cada arquivo vira <destino>\\<fazenda>\\JD-Data\\log\\<arquivo>.jdl
- fazenda vem do nome da pasta de origem (convencao "US PEDRA_<fazenda>_Parte").

GS3_2630: le o setup.fds de cada organizacao (RCD\\EIC\\setup.fds) pra montar
o mapa campo->fazenda (elementos <Field erid=... farmRef=...> e <Farm erid=...
name=...>). Com isso classifica cada arquivo da arvore RCD:
  - dentro de Fields/<hex>/<uuid>/... ou StoredMaps/<hex>/<uuid>/...: o uuid
    da pasta E o erid do campo -> resolve fazenda direto.
  - dentro de Documentation/<hex>/<uuid>.fdl (+.fdd): le o <FieldRef eridRef=.../>
    no .fdl pra saber o campo, dai resolve fazenda.
  - fazenda resolvida  -> <destino>\\<fazenda>\\GS3_2630\\<org>\\RCD\\<caminho original>
  - campo referenciado mas nao existe mais na config atual (fazenda/ciclo
    antigo, sem como recuperar o nome)  -> <destino>\\SEM_FAZENDA_IDENTIFICADA\\...
  - resto (DebugFiles, banco de dados, curvas soltas, etc. - nao pertence a
    nenhum campo especifico) -> <destino>\\_COMUM\\... (copiado uma unica vez,
    nao duplicado por fazenda)

Arquivos ja copiados (mesmo nome e tamanho) sao pulados - seguro rodar de
novo com o mesmo pen-drive.

Copia em paralelo (threads de I/O) porque o destino costuma ser rede - la
o gargalo e a latencia da rede, nao a CPU, entao varias copias simultaneas
terminam bem mais rapido que uma de cada vez.
"""
import ctypes
import os
import queue
import re
import shutil
import sys
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import filedialog, scrolledtext, ttk

MAX_THREADS = 8

COMUM = "_COMUM"
SEM_FAZENDA = "SEM_FAZENDA_IDENTIFICADA"

RE_FARM_TAG = re.compile(r'<Farm\b[^>]*erid="\{([^}]+)\}"[^>]*name="([^"]*)"')
RE_FIELD_TAG = re.compile(r'<Field\b[^>]*/>')
RE_ERID = re.compile(r'erid="\{([^}]+)\}"')
RE_FARMREF = re.compile(r'farmRef="\{([^}]+)\}"')
RE_FIELDREF = re.compile(r'<FieldRef eridRef="\{([^}]+)\}"')


def caminho_recurso(nome_relativo):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nome_relativo)


def preparar_dpi():
    """Avisa o Windows que o app trata DPI sozinho, senao ele estica a
    janela como bitmap pra compensar tela de alta densidade e borra tudo
    (inclusive o icone). Retorna o fator de escala real da tela (1.0 =
    100%, 1.5 = 150% etc.) pra ajustar geometria/fonte proporcionalmente.
    """
    if sys.platform != "win32":
        return 1.0
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
    try:
        dc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, dc)
        return dpi / 96.0
    except (AttributeError, OSError):
        return 1.0


def listar_arquivos(origem):
    """Varre recursivamente com os.scandir (mais rapido que glob recursivo).
    Retorna lista de caminhos de arquivo."""
    encontrados = []
    pilha = [origem]
    while pilha:
        atual = pilha.pop()
        try:
            with os.scandir(atual) as it:
                for entrada in it:
                    if entrada.is_dir(follow_symlinks=False):
                        pilha.append(entrada.path)
                    else:
                        encontrados.append(entrada.path)
        except OSError:
            continue
    return encontrados


# ---------------------------------------------------------------------
# JDLink (.jdl)
# ---------------------------------------------------------------------

def farm_code_from_folder(nome_pasta):
    # ex: "2026_US PEDRA_10203-10828Rev0_Parte 1" -> "10203-10828Rev0"
    m = re.search(r"US PEDRA_([\w\-]+)_Parte", nome_pasta)
    return m.group(1) if m else nome_pasta


def plano_copia_jdl(origem, destino, arquivos):
    plano = []
    for f in arquivos:
        if not f.lower().endswith(".jdl"):
            continue
        pasta_origem = os.path.basename(os.path.dirname(f))
        farm = farm_code_from_folder(pasta_origem)
        destino_path = os.path.join(destino, farm, "JD-Data", "log", os.path.basename(f))
        plano.append((f, destino_path, farm))
    return plano


# ---------------------------------------------------------------------
# GS3_2630
# ---------------------------------------------------------------------

def encontrar_organizacoes_gs3(arquivos):
    """Acha cada <org> a partir do caminho de um setup.fds em
    .../<org>/RCD/EIC/setup.fds. Retorna {org_dir: caminho_setup_fds}."""
    orgs = {}
    for f in arquivos:
        if os.path.basename(f).lower() != "setup.fds":
            continue
        eic_dir = os.path.dirname(f)
        if os.path.basename(eic_dir) != "EIC":
            continue
        rcd_dir = os.path.dirname(eic_dir)
        if os.path.basename(rcd_dir) != "RCD":
            continue
        org_dir = os.path.dirname(rcd_dir)
        orgs[org_dir] = f
    return orgs


def carregar_mapa_fazendas(caminho_setup_fds):
    """Le o setup.fds e devolve uma funcao uuid_do_campo -> nome_da_fazenda
    (ou None se o campo nao existe mais na configuracao atual)."""
    try:
        texto = open(caminho_setup_fds, encoding="latin1", errors="replace").read()
    except OSError:
        return lambda _uuid: None

    farms = dict(RE_FARM_TAG.findall(texto))
    campo_para_farmref = {}
    for tag in RE_FIELD_TAG.findall(texto):
        e = RE_ERID.search(tag)
        fr = RE_FARMREF.search(tag)
        if e and fr:
            campo_para_farmref[e.group(1)] = fr.group(1)

    def farm_do_campo(uuid_campo):
        farmref = campo_para_farmref.get(uuid_campo)
        if farmref:
            return farms.get(farmref)
        return None

    return farm_do_campo


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _fieldref_do_fdl(caminho_fdl):
    try:
        with open(caminho_fdl, encoding="latin1", errors="replace") as fh:
            trecho = fh.read(4000)
    except OSError:
        return None
    m = RE_FIELDREF.search(trecho)
    return m.group(1) if m else None


def plano_copia_gs3(arquivos, destino, org_dir, caminho_setup_fds):
    farm_do_campo = carregar_mapa_fazendas(caminho_setup_fds)
    org_nome = os.path.basename(org_dir)
    rcd_dir = os.path.join(org_dir, "RCD")

    cache_fieldref = {}
    plano = []

    for f in arquivos:
        if not f.startswith(rcd_dir + os.sep) and f != rcd_dir:
            continue
        rel = os.path.relpath(f, rcd_dir)
        partes = rel.split(os.sep)

        categoria = None  # ("fazenda", nome) | ("sem_fazenda", None) | ("comum", None)

        for chave in ("Fields", "StoredMaps"):
            if chave in partes:
                i = partes.index(chave)
                if i + 2 < len(partes) and _UUID_RE.match(partes[i + 2]):
                    farm = farm_do_campo(partes[i + 2])
                    categoria = ("fazenda", farm) if farm else ("sem_fazenda", None)
                break

        if categoria is None and "Documentation" in partes:
            nome = partes[-1]
            base, ext = os.path.splitext(nome)
            if ext.lower() in (".fdl", ".fdd"):
                if base not in cache_fieldref:
                    fdl_path = os.path.join(os.path.dirname(f), base + ".fdl")
                    fieldref = _fieldref_do_fdl(fdl_path) if os.path.exists(fdl_path) else None
                    cache_fieldref[base] = fieldref
                fieldref = cache_fieldref[base]
                farm = farm_do_campo(fieldref) if fieldref else None
                categoria = ("fazenda", farm) if farm else ("sem_fazenda", None)

        if categoria is None:
            categoria = ("comum", None)

        tipo, farm = categoria
        if tipo == "fazenda":
            raiz_destino = os.path.join(destino, farm)
        elif tipo == "sem_fazenda":
            raiz_destino = os.path.join(destino, SEM_FAZENDA)
        else:
            raiz_destino = os.path.join(destino, COMUM)

        destino_path = os.path.join(raiz_destino, "GS3_2630", org_nome, "RCD", rel)
        rotulo_farm = farm if tipo == "fazenda" else (SEM_FAZENDA if tipo == "sem_fazenda" else COMUM)
        plano.append((f, destino_path, rotulo_farm))

    return plano


class App:
    CORES = {
        "info": "#1a5fb4",
        "ok": "#2d7d46",
        "skip": "#7a7a7a",
        "erro": "#c0392b",
    }

    def __init__(self, root, escala=1.0):
        self.root = root
        root.title("Copiar Executados")
        root.geometry(f"{int(760 * escala)}x{int(560 * escala)}")
        root.minsize(int(640 * escala), int(440 * escala))

        icone = caminho_recurso("assets/icone_jdl.ico")
        if os.path.exists(icone):
            try:
                root.iconbitmap(icone)
            except tk.TclError:
                pass

        self.style = ttk.Style(root)
        for tema in ("vista", "xpnative", "clam"):
            if tema in self.style.theme_names():
                self.style.theme_use(tema)
                break
        self.style.configure("Acao.TButton", font=("Segoe UI", 11, "bold"), padding=10)
        self.style.configure("TLabelframe.Label", font=("Segoe UI", 9, "bold"))

        self.fila = queue.Queue()
        self.rodando = False

        # --- origem / destino ---
        frame_caminhos = ttk.LabelFrame(root, text="Origem e destino")
        frame_caminhos.pack(fill="x", padx=10, pady=(10, 6))
        frame_caminhos.columnconfigure(0, weight=1)

        ttk.Label(
            frame_caminhos, text="Origem (pen-drive: pasta JD-Data, GS3_2630, ou raiz com as duas):"
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 0))
        self.origem_var = tk.StringVar()
        ttk.Entry(frame_caminhos, textvariable=self.origem_var).grid(
            row=1, column=0, sticky="ew", padx=(8, 6), pady=(0, 8)
        )
        ttk.Button(frame_caminhos, text="Procurar...", command=self.escolher_origem).grid(
            row=1, column=1, padx=(0, 8), pady=(0, 8)
        )

        ttk.Label(frame_caminhos, text="Destino (pasta da campanha em EXECUTADOS):").grid(
            row=2, column=0, sticky="w", padx=8
        )
        self.destino_var = tk.StringVar()
        ttk.Entry(frame_caminhos, textvariable=self.destino_var).grid(
            row=3, column=0, sticky="ew", padx=(8, 6), pady=(0, 8)
        )
        ttk.Button(frame_caminhos, text="Procurar...", command=self.escolher_destino).grid(
            row=3, column=1, padx=(0, 8), pady=(0, 8)
        )

        # --- acao ---
        self.btn_copiar = ttk.Button(
            root, text="Copiar", command=self.iniciar_copia, style="Acao.TButton"
        )
        self.btn_copiar.pack(fill="x", padx=10, pady=4)

        # --- progresso ---
        frame_prog = ttk.Frame(root)
        frame_prog.pack(fill="x", padx=10, pady=(2, 6))
        frame_prog.columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(frame_prog, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.contador_var = tk.StringVar(value="")
        ttk.Label(frame_prog, textvariable=self.contador_var, width=14, anchor="e").grid(
            row=0, column=1
        )

        self.arquivo_atual_var = tk.StringVar(value="")
        ttk.Label(
            root, textvariable=self.arquivo_atual_var, foreground="#666666", font=("Segoe UI", 8)
        ).pack(fill="x", padx=12)

        # --- log ---
        frame_log = ttk.LabelFrame(root, text="Log")
        frame_log.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        self.log = scrolledtext.ScrolledText(
            frame_log, state="disabled", font=("Consolas", 9), borderwidth=0
        )
        self.log.pack(fill="both", expand=True, padx=6, pady=6)
        for tag, cor in self.CORES.items():
            self.log.tag_config(tag, foreground=cor)

        self.root.after(100, self.poll_fila)

    def escolher_origem(self):
        p = filedialog.askdirectory(
            title="Selecione a pasta do pen-drive (JD-Data, GS3_2630, ou a raiz)"
        )
        if p:
            self.origem_var.set(p)

    def escolher_destino(self):
        p = filedialog.askdirectory(
            title="Selecione a pasta da campanha em EXECUTADOS"
        )
        if p:
            self.destino_var.set(p)

    def escrever(self, texto, tag="info"):
        self.log.configure(state="normal")
        self.log.insert("end", texto + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def iniciar_copia(self):
        if self.rodando:
            return
        origem = self.origem_var.get().strip()
        destino = self.destino_var.get().strip()

        if not origem or not os.path.isdir(origem):
            self.escrever("ERRO: escolha uma pasta de origem valida.", "erro")
            return
        if not destino:
            self.escrever("ERRO: escolha uma pasta de destino.", "erro")
            return

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

        self.rodando = True
        self.btn_copiar.configure(state="disabled", text="Copiando...")
        self.progress["value"] = 0
        self.contador_var.set("")
        self.arquivo_atual_var.set("")

        t = threading.Thread(target=self.copiar, args=(origem, destino), daemon=True)
        t.start()

    def _copiar_um(self, origem_path, destino_path, farm):
        nome = os.path.basename(origem_path)
        try:
            if (
                os.path.exists(destino_path)
                and os.path.getsize(destino_path) == os.path.getsize(origem_path)
            ):
                return farm, "pulado", nome
            os.makedirs(os.path.dirname(destino_path), exist_ok=True)
            shutil.copy2(origem_path, destino_path)
            return farm, "copiado", nome
        except OSError as e:
            return farm, f"erro: {e}", nome

    def copiar(self, origem, destino):
        self.fila.put(("log", f"Origem: {origem}", "info"))
        self.fila.put(("log", f"Destino: {destino}", "info"))
        self.fila.put(("log", "Procurando arquivos...", "info"))

        todos = listar_arquivos(origem)

        plano = []

        plano_jdl = plano_copia_jdl(origem, destino, todos)
        if plano_jdl:
            self.fila.put(("log", f"JDLink (.jdl): {len(plano_jdl)} arquivo(s).", "info"))
            plano.extend(plano_jdl)

        orgs = encontrar_organizacoes_gs3(todos)
        for org_dir, setup_fds in orgs.items():
            plano_gs3 = plano_copia_gs3(todos, destino, org_dir, setup_fds)
            self.fila.put((
                "log",
                f"GS3_2630 ({os.path.basename(org_dir)}): {len(plano_gs3)} arquivo(s).",
                "info",
            ))
            plano.extend(plano_gs3)

        self.fila.put(("log", "", "info"))

        if not plano:
            self.fila.put(("log", "Nada encontrado (nem .jdl, nem GS3_2630/setup.fds).", "erro"))
            self.fila.put(("fim", None))
            return

        self.fila.put(("max", len(plano)))

        resumo = {}
        concluidos = 0
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futuros = {
                executor.submit(self._copiar_um, src, dst, farm): src
                for src, dst, farm in plano
            }
            for futuro in as_completed(futuros):
                farm, status, nome = futuro.result()
                concluidos += 1
                self.fila.put(("progresso", concluidos, nome))

                c = resumo.setdefault(farm, {"copiado": 0, "pulado": 0, "erro": 0})
                if status == "copiado":
                    c["copiado"] += 1
                elif status == "pulado":
                    c["pulado"] += 1
                else:
                    c["erro"] += 1
                    self.fila.put(("log", f"  {nome}: {status}", "erro"))

        self.fila.put(("log", "Resumo por fazenda:", "info"))
        total_c = total_p = total_e = 0
        for farm, c in sorted(resumo.items()):
            tag = "erro" if c["erro"] else "ok"
            self.fila.put((
                "log",
                f"  {farm}: {c['copiado']} copiados, {c['pulado']} ja existiam"
                + (f", {c['erro']} com erro" if c["erro"] else ""),
                tag,
            ))
            total_c += c["copiado"]
            total_p += c["pulado"]
            total_e += c["erro"]

        self.fila.put(("log", "", "info"))
        resumo_final = f"Total: {total_c} copiados, {total_p} pulados"
        if total_e:
            resumo_final += f", {total_e} com erro"
        self.fila.put(("log", resumo_final, "erro" if total_e else "ok"))
        self.fila.put(("fim", None))

    def poll_fila(self):
        try:
            while True:
                item = self.fila.get_nowait()
                tipo = item[0]
                if tipo == "log":
                    self.escrever(item[1], item[2])
                elif tipo == "max":
                    self.progress["maximum"] = item[1]
                elif tipo == "progresso":
                    self.progress["value"] = item[1]
                    total = int(self.progress["maximum"] or 1)
                    self.contador_var.set(f"{item[1]} / {total}")
                    self.arquivo_atual_var.set(item[2])
                elif tipo == "fim":
                    self.rodando = False
                    self.btn_copiar.configure(state="normal", text="Copiar")
                    self.arquivo_atual_var.set("")
        except queue.Empty:
            pass
        self.root.after(100, self.poll_fila)


def main():
    escala = preparar_dpi()
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", escala * 96.0 / 72.0)
    except tk.TclError:
        pass
    App(root, escala)
    root.mainloop()


if __name__ == "__main__":
    main()
