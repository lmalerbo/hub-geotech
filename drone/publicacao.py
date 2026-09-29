"""Publicação de uma revisão do projeto de drone no GitHub Releases (mesmo padrão do worker/arquivos.js)."""
import re
import unicodedata
from pathlib import Path

import requests

SUFIXO = {'normal': '-Normal', 'catacao': '-Catacao'}
MOTIVO_PADRAO = {'catacao': 'Novo levantamento de infestação'}


def nome_fazenda_arquivo(nome: str) -> str:
    s = unicodedata.normalize('NFD', nome).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'[^A-Z0-9]+', '.', s).strip('.')


def nome_arquivo(cod_faz, nome, numero, documento, ext) -> str:
    return f'{cod_faz}_{nome_fazenda_arquivo(nome)}_Rev{numero}{SUFIXO[documento]}.{ext}'


class GitHubReleases:
    def __init__(self, token: str, repo: str):
        self.repo = repo
        self.h = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                  'User-Agent': 'hub-geotech-drone'}

    def release(self, tag: str, titulo: str) -> dict:
        r = requests.get(f'https://api.github.com/repos/{self.repo}/releases/tags/{tag}', headers=self.h, timeout=60)
        if r.status_code == 404:
            r = requests.post(f'https://api.github.com/repos/{self.repo}/releases', headers=self.h, timeout=60,
                              json={'tag_name': tag, 'name': titulo, 'body': 'Arquivos publicados pelo Hub Geotech.'})
        if not r.ok:
            raise RuntimeError(f'GitHub: não foi possível abrir a release {tag} ({r.status_code})')
        return r.json()

    def subir(self, release: dict, caminho: Path, nome: str) -> tuple:
        existente = next((a for a in release.get('assets', []) if a['name'] == nome), None)
        if existente:   # reenvio depois de falha: o arquivo já é desta revisão
            return existente['browser_download_url'], existente['size']
        r = requests.post(f'https://uploads.github.com/repos/{self.repo}/releases/{release["id"]}/assets',
                          params={'name': nome}, data=Path(caminho).read_bytes(), timeout=300,
                          headers={**self.h, 'Content-Type': 'application/octet-stream'})
        if not r.ok:
            raise RuntimeError(f'GitHub: falha ao subir {nome} ({r.status_code})')
        a = r.json()
        return a['browser_download_url'], a['size']


def _nomes(cod_faz, nome, numero, documento, arquivos) -> dict:
    return {ext: nome_arquivo(cod_faz, nome, numero, documento, ext) for ext in ('zip', 'pdf') if arquivos.get(ext)}


def publicar(banco, gh, cod_faz, documento, motivo, arquivos: dict) -> int:
    faz = banco.fazenda(cod_faz)
    projeto = banco.projeto_individual(cod_faz, faz['nome'])
    vigente = banco.revisao_vigente(projeto, documento)
    rev = None
    if vigente:
        # publicação anterior interrompida (revisão aberta, arquivos faltando): continua nela
        ja = set(banco.arquivos_da_revisao(vigente['id']))
        if ja < set(_nomes(cod_faz, faz['nome'], vigente['numero'], documento, arquivos).values()):
            rev = vigente
        elif not (motivo or '').strip():
            motivo = MOTIVO_PADRAO.get(documento)
            if not motivo:
                raise RuntimeError('Informe o motivo da nova revisão do projeto Normal.')
    if rev is None:
        rev = banco.nova_revisao(projeto, documento, motivo)
    release = gh.release(f'drone-{cod_faz}', f'{faz["nome"]} — drone')
    for ext, nome in _nomes(cod_faz, faz['nome'], rev['numero'], documento, arquivos).items():
        url, tamanho = gh.subir(release, arquivos[ext], nome)
        banco.registrar_arquivo(rev['id'], nome, url, tamanho)   # upsert: repetir não duplica
    return rev['id']
