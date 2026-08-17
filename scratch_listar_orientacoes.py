"""Script de investigacao (somente leitura): lista as guidance lines do
talhao '10471' via API, pra ver se enxergamos as curvas recem-importadas
via arquivo e entender a estrutura exata devolvida (@type, campos, etc)."""

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


print("Listando campos (fields) da organizacao (paginado)...")
fields = _list_all(f"/organizations/{org_id}/fields")
print(f"  {len(fields)} campo(s) total")
alvo = next((f for f in fields if f["name"] == "10471"), None)
if not alvo:
    print("Field '10471' nao encontrado. Fields disponiveis:", [f["name"] for f in fields][:20])
    raise SystemExit(1)

field_id = alvo["id"]
print(f"Field '10471' -> id={field_id}")

for status in ["archived", "available", "all"]:
    valores = _list_all(
        f"/organizations/{org_id}/fields/{field_id}/guidanceLines",
        params={"status": status, "count": 50},
    )
    print(f"\nstatus={status}: {len(valores)} guidance line(s)")
    print("nomes:", sorted(v["name"] for v in valores))

print("\nJSON completo da primeira curva (status=archived):")
todas = _list_all(
    f"/organizations/{org_id}/fields/{field_id}/guidanceLines",
    params={"status": "archived", "count": 50},
)
print(json.dumps(todas[0], indent=2, ensure_ascii=False))
