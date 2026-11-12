"""Sonda (somente cria o registro do arquivo, NAO sobe o binario ainda): testa
se a API de Files aceita criar um arquivo tipo SETUP na organizacao -- primeiro
passo pra automatizar o upload do zip GS3_2630 direto pela API."""

import yaml

import deere_oauth_client as d

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
org_id = cfg["org_id"]

body = {"name": "teste_gs3_2630_probe.zip", "type": "SETUP"}

print(f"POST /organizations/{org_id}/files  body={body}")
try:
    resp = d.api_post(f"/organizations/{org_id}/files", body)
    print(f"Status: {resp.status_code}")
    print(f"Location: {resp.headers.get('Location')}")
    print(f"Corpo: {resp.text[:500]}")
except Exception as e:
    print(f"ERRO: {e}")
    if hasattr(e, "response") and e.response is not None:
        print(f"Status: {e.response.status_code}")
        print(f"Corpo: {e.response.text[:500]}")
