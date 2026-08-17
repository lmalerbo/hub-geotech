"""Testa o mesmo probe de Files, mas no host partnerapi.deere.com (usado pelo
Douglas) em vez de api.deere.com, pra ver se o host era o problema."""

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

for host in ["partnerapi.deere.com", "api.deere.com"]:
    print(f"\n=== host={host}  org={org_id} ===")
    resp = requests.get(
        f"https://{host}/platform/organizations/{org_id}/fields",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.deere.axiom.v3+json",
        },
        params={"count": 1},
        timeout=30,
    )
    print(f"GET fields -> {resp.status_code}: {resp.text[:200]}")

    resp2 = requests.post(
        f"https://{host}/platform/organizations/{org_id}/files",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.deere.axiom.v3+json",
            "Content-Type": "application/vnd.deere.axiom.v3+json",
        },
        json={"name": "teste_gs3_2630_probe_ti.zip", "type": "SETUP"},
        timeout=30,
    )
    print(f"POST files -> {resp2.status_code}: {resp2.text[:200]}")
