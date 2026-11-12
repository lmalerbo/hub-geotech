"""Testa se o token do outro app (TI) consegue de fato chamar a API de Files
-- mesmo probe de antes (so cria o registro do arquivo, nao sobe binario)."""

from pathlib import Path

import requests
import yaml

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
org_id = cfg["org_id"]

token = Path(
    "C:/Users/lmalerbo/AppData/Local/Temp/claude/"
    "c--Users-lmalerbo-Documents-GitHub-base-op/"
    "59e388e2-69a5-4024-9648-537971c7336e/scratchpad/token_ti.txt"
).read_text().strip()

body = {"name": "teste_gs3_2630_probe_ti.zip", "type": "SETUP"}

resp = requests.post(
    f"https://api.deere.com/platform/organizations/{org_id}/files",
    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.deere.axiom.v3+json",
        "Content-Type": "application/vnd.deere.axiom.v3+json",
    },
    json=body,
    timeout=30,
)
print(f"Status: {resp.status_code}")
print(f"Location: {resp.headers.get('Location')}")
print(f"Corpo: {resp.text[:500]}")
