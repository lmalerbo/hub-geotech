"""Desarquiva (archived=false) todas as guidance lines arquivadas de um talhao
via API do John Deere Operations Center -- alternativa a clicar manualmente em
"Tornar Disponivel" no Operations Center apos cada upload de bundle GS3_2630.

Uso:
    python tornar_disponivel_orientacoes.py <nome_do_talhao> [config.yaml]
"""

import sys

import requests
import yaml

import deere_oauth_client as d


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


def api_put(path: str, json_body: dict) -> requests.Response:
    token = d.get_access_token()
    url = path if path.startswith("http") else f"{d.API_BASE}{path}"
    return requests.put(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": d.API_ACCEPT_HEADER,
            "Content-Type": "application/vnd.deere.axiom.v3+json",
        },
        json=json_body,
        timeout=30,
    )


def main(nome_talhao: str, config_path: str = "config.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    org_id = cfg["org_id"]

    fields = _list_all(f"/organizations/{org_id}/fields")
    field = next((f for f in fields if f["name"] == nome_talhao), None)
    if not field:
        print(f"Talhao '{nome_talhao}' nao encontrado.")
        sys.exit(1)
    field_id = field["id"]

    curvas = _list_all(
        f"/organizations/{org_id}/fields/{field_id}/guidanceLines",
        params={"status": "archived", "count": 100},
    )
    print(f"Talhao '{nome_talhao}': {len(curvas)} orientacao(oes) arquivada(s)")

    ok, falhas = 0, []
    for c in curvas:
        body = dict(c)
        body.pop("links", None)
        body.pop("lastModifiedTime", None)
        body["archived"] = False
        resp = api_put(f"/organizations/{org_id}/fields/{field_id}/guidanceLines/{c['id']}", body)
        if resp.status_code == 204:
            ok += 1
            print(f"  OK  {c['name']}")
        else:
            falhas.append((c["name"], resp.status_code, resp.text[:200]))
            print(f"  FALHA {c['name']}: {resp.status_code} {resp.text[:200]}")

    print(f"\n{ok}/{len(curvas)} desarquivada(s) com sucesso.")
    if falhas:
        print("Falhas:", falhas)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tornar_disponivel_orientacoes.py <nome_do_talhao> [config.yaml]")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "config.yaml")
