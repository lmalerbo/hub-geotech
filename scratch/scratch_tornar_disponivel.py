"""Teste canario: tenta desarquivar (archived=false) UMA curva via PUT na API,
depois confere via GET se funcionou e se os dados da curva continuam intactos."""

import json
import yaml

import deere_oauth_client as d

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
org_id = cfg["org_id"]


def _list_all(path, params=None):
    items = []
    data = d.api_get(path, params=params or {"count": 100})
    items.extend(data.get("values", []))
    links = {l["rel"]: l["uri"] for l in data.get("links", [])}
    while "nextPage" in links:
        data = d.api_get(links["nextPage"])
        items.extend(data.get("values", []))
        links = {l["rel"]: l["uri"] for l in data.get("links", [])}
    return items


def api_put(path: str, json_body: dict):
    token = d.get_access_token()
    import requests
    url = path if path.startswith("http") else f"{d.API_BASE}{path}"
    resp = requests.put(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": d.API_ACCEPT_HEADER,
            "Content-Type": "application/vnd.deere.axiom.v3+json",
        },
        json=json_body,
        timeout=30,
    )
    return resp


fields = _list_all(f"/organizations/{org_id}/fields")
field = next(f for f in fields if f["name"] == "10471")
field_id = field["id"]

curvas = _list_all(
    f"/organizations/{org_id}/fields/{field_id}/guidanceLines",
    params={"status": "archived", "count": 50},
)
alvo = next(c for c in curvas if c["name"] == "1L-7")
print(f"Curva alvo: {alvo['name']} (id={alvo['id']})")
print(f"  tracksOriginalPointCount antes: {alvo['tracksOriginalPointCount']}")

body = dict(alvo)
body.pop("links", None)
body.pop("lastModifiedTime", None)
body["archived"] = False

print("\nEnviando PUT...")
resp = api_put(f"/organizations/{org_id}/fields/{field_id}/guidanceLines/{alvo['id']}", body)
print(f"Status HTTP: {resp.status_code}")
print(f"Corpo da resposta: {resp.text[:1000]}")

print("\nReconferindo via GET (status=all)...")
depois = _list_all(
    f"/organizations/{org_id}/fields/{field_id}/guidanceLines",
    params={"status": "all", "count": 50},
)
atualizado = next(c for c in depois if c["id"] == alvo["id"])
print(json.dumps(atualizado, indent=2, ensure_ascii=False))
