"""
Prepara os dados do painel de acompanhamento do workflow (le
linhas-vant/workflow_log.jsonl) e injeta no template HTML, pronto pra
publicar como Artifact.

Uso:
    python gerar_painel_workflow.py [template.html] [saida.html]
"""

import json
import sys
from pathlib import Path

import workflow_status as ws


def main(template_path: str, saida_path: str):
    eventos = ws.ler_eventos()
    template = Path(template_path).read_text(encoding="utf-8")
    dados_json = json.dumps(eventos, ensure_ascii=False)
    final = template.replace("__EVENTOS_JSON__", dados_json)
    Path(saida_path).write_text(final, encoding="utf-8")
    print(f"Painel gerado: {saida_path} ({len(eventos)} evento(s))")


if __name__ == "__main__":
    template = sys.argv[1] if len(sys.argv) > 1 else "painel_workflow_template.html"
    saida = sys.argv[2] if len(sys.argv) > 2 else "linhas-vant/painel_workflow.html"
    main(template, saida)
