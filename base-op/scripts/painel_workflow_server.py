"""
Servidor local do painel de acompanhamento do workflow -- serve a pagina
(painel_workflow_live.html) e um endpoint JSON que le o log ao vivo
(linhas-vant/workflow_log.jsonl) a cada requisicao, pra pagina ficar sempre
atualizada via polling (a cada 3s).

Deixe rodando (nesse terminal ou em background) enquanto o pipeline
(dxf_para_gen4.py / build_bundle_completo.py) processa fazendas -- o painel
reflete cada evento assim que e gravado no log.

Uso:
    python painel_workflow_server.py [porta]
    -> abre http://localhost:<porta> no navegador
"""

import http.server
import json
import sys
from pathlib import Path

import workflow_status as ws

HTML_PATH = Path(__file__).parent / "painel_workflow_live.html"
PORTA_PADRAO = 8899


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._servir_html()
        elif self.path == "/api/eventos":
            self._servir_json()
        else:
            self.send_response(404)
            self.end_headers()

    def _servir_html(self):
        corpo = HTML_PATH.read_text(encoding="utf-8").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _servir_json(self):
        eventos = ws.ler_eventos()
        corpo = json.dumps(eventos, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, format, *args):
        pass  # silencia o log padrao (um print por requisicao, muito verboso com polling de 3s)


def main(porta: int = PORTA_PADRAO):
    servidor = http.server.HTTPServer(("localhost", porta), Handler)
    print(f"Painel do workflow ao vivo em: http://localhost:{porta}")
    print("Deixe esse terminal aberto enquanto o pipeline processa. Ctrl+C pra parar.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else PORTA_PADRAO
    main(porta)
