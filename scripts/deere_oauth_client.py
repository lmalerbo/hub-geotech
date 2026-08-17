"""
Cliente OAuth2 para a API do John Deere Operations Center (Develop with Deere).

Fluxo (Authorization Code, feito uma unica vez por usuario/organizacao):
    python deere_oauth_client.py login

Depois disso, os tokens ficam salvos em .deere_tokens.json (nao versionar / nao
compartilhar esse arquivo) e sao renovados automaticamente via refresh_token.

Requer as variaveis de ambiente:
    DEERE_CLIENT_ID
    DEERE_CLIENT_SECRET

Endpoints oficiais (exemplos publicados pela propria John Deere em
github.com/JohnDeere/MyJohnDeereAPI-OAuth2-Python-Example):
    Authorize: https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/authorize
    Token:     https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/token
    API base (sandbox):    https://sandboxapi.deere.com/platform
    API base (producao):   https://api.deere.com/platform  (confirmar no portal
                            quando o app for promovido de sandbox para producao)
"""

import base64
import json
import os
import sys
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

AUTHORIZE_URL = "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/authorize"
TOKEN_URL = "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/token"

REDIRECT_URI = "http://localhost:9090/callback"
CALLBACK_PORT = 9090
SCOPES = ["ag1", "ag2", "ag3", "org1", "org2", "files", "offline_access"]

TOKEN_STORE = ".deere_tokens.json"

# Confirmado via link "self" retornado por /organizations para esta conta/app.
API_BASE = os.environ.get("DEERE_API_BASE", "https://api.deere.com/platform")

API_ACCEPT_HEADER = "application/vnd.deere.axiom.v3+json"


def _client_credentials():
    # Aceita tanto os nomes do .env (APPLICATION_ID / SECRET, copiados do
    # portal da John Deere) quanto DEERE_CLIENT_ID / DEERE_CLIENT_SECRET.
    client_id = os.environ.get("APPLICATION_ID") or os.environ.get("DEERE_CLIENT_ID")
    client_secret = os.environ.get("SECRET") or os.environ.get("DEERE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Defina APPLICATION_ID e SECRET no arquivo .env (ou as variaveis de "
            "ambiente DEERE_CLIENT_ID / DEERE_CLIENT_SECRET) antes de rodar."
        )
    return client_id, client_secret


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")


class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code = None
    expected_state = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        state = params.get("state", [None])[0]
        code = params.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        if state != _CallbackHandler.expected_state or not code:
            self.wfile.write(b"<h1>Falha na autorizacao. Pode fechar esta aba.</h1>")
            return

        _CallbackHandler.auth_code = code
        self.wfile.write(b"<h1>Autorizado com sucesso! Pode fechar esta aba e voltar ao terminal.</h1>")

    def log_message(self, format, *args):
        pass  # silencia o log padrao do http.server


def _wait_for_callback(expected_state: str) -> str:
    _CallbackHandler.auth_code = None
    _CallbackHandler.expected_state = expected_state
    server = HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    print(f"Aguardando autorizacao em {REDIRECT_URI} ...")
    while _CallbackHandler.auth_code is None:
        server.handle_request()
    server.server_close()
    return _CallbackHandler.auth_code


def login():
    client_id, client_secret = _client_credentials()
    state = uuid.uuid4().hex

    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state,
    }
    auth_url = f"{AUTHORIZE_URL}?{urlencode(query)}"

    print("Abrindo o navegador para login/autorizacao no John Deere...")
    print(f"Se nao abrir automaticamente, acesse:\n{auth_url}\n")
    webbrowser.open(auth_url)

    code = _wait_for_callback(state)

    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": _basic_auth_header(client_id, client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()
    tokens["obtained_at"] = time.time()
    _save_tokens(tokens)
    print(f"Login concluido. Tokens salvos em {TOKEN_STORE}.")


def _save_tokens(tokens: dict):
    with open(TOKEN_STORE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)


def _load_tokens() -> dict:
    if not os.path.exists(TOKEN_STORE):
        raise RuntimeError(f"Nenhum token salvo ainda. Rode primeiro: python {sys.argv[0]} login")
    with open(TOKEN_STORE, "r", encoding="utf-8") as f:
        return json.load(f)


def _refresh_if_needed(tokens: dict) -> dict:
    expires_at = tokens["obtained_at"] + tokens.get("expires_in", 0)
    if time.time() < expires_at - 60:
        return tokens

    client_id, client_secret = _client_credentials()
    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": _basic_auth_header(client_id, client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    new_tokens = resp.json()
    new_tokens["obtained_at"] = time.time()
    new_tokens.setdefault("refresh_token", tokens["refresh_token"])
    _save_tokens(new_tokens)
    return new_tokens


def get_access_token() -> str:
    tokens = _load_tokens()
    tokens = _refresh_if_needed(tokens)
    return tokens["access_token"]


def api_get(path: str, **kwargs):
    token = get_access_token()
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    resp = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": API_ACCEPT_HEADER,
        },
        **kwargs,
    )
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, json_body: dict, **kwargs):
    token = get_access_token()
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": API_ACCEPT_HEADER,
            "Content-Type": "application/vnd.deere.axiom.v3+json",
        },
        json=json_body,
        **kwargs,
    )
    resp.raise_for_status()
    return resp


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "login":
        print(f"Uso: python {sys.argv[0]} login")
        sys.exit(1)
    login()
