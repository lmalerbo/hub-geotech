"""
Sincroniza limites (boundaries) de fazendas/talhoes com o John Deere Operations
Center via API, a partir do shapefile ja formatado por format_oc_boundaries.py
(colunas CLIENT_NAM / FARM_NAME / FIELD_NAME / POLYGONTYP, uma feicao por fazenda).

Usa o mesmo config.yaml de format_oc_boundaries.py e localiza sozinho o
shapefile formatado do dia (output_dir/output_basename_DD_MM_YYYY.shp).

Uso:
    python sync_boundaries_api.py [config.yaml]              -> dry-run (simula)
    python sync_boundaries_api.py [config.yaml] --live       -> grava de verdade

Requer login previo (python deere_oauth_client.py login) e .env com
APPLICATION_ID / SECRET.
"""

import sys
import warnings
from datetime import date
from pathlib import Path

import geopandas as gpd
import yaml

import deere_oauth_client as d

warnings.filterwarnings("ignore")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    required = ["org_id", "client_name", "output_dir", "output_basename"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ValueError(f"Faltam campos obrigatorios no config: {missing}")
    cfg.setdefault("only_farm_codes", None)
    cfg.setdefault("dry_run", True)
    return cfg


def find_formatted_shapefile(output_dir: str, output_basename: str) -> Path:
    today = date.today().strftime("%d_%m_%Y")
    shp_path = Path(output_dir) / f"{output_basename}_{today}.shp"
    if not shp_path.exists():
        raise FileNotFoundError(
            f"Nao achei {shp_path}. Rode primeiro: python format_oc_boundaries.py config.yaml"
        )
    return shp_path


def _list_all(path: str) -> list:
    items = []
    data = d.api_get(path, params={"count": 10})
    items.extend(data.get("values", []))
    links = {l["rel"]: l["uri"] for l in data.get("links", [])}
    while "nextPage" in links:
        data = d.api_get(links["nextPage"])
        items.extend(data.get("values", []))
        links = {l["rel"]: l["uri"] for l in data.get("links", [])}
    return items


def find_client_id(org_id: str, client_name: str) -> str:
    clients = d.api_get(f"/organizations/{org_id}/clients", params={"count": 100}).get("values", [])
    for c in clients:
        if c["name"] == client_name:
            return c["id"]
    raise ValueError(f"Client '{client_name}' nao encontrado na organizacao {org_id}")


def build_multipolygon(geom) -> list:
    """Converte uma geometria shapely (Polygon/MultiPolygon, em WGS84) para o
    formato multipolygons/rings/points {lat, lon} da API John Deere."""
    polygons = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    rings = []
    for poly in polygons:
        exterior_pts = [{"lat": lat, "lon": lon} for lon, lat in poly.exterior.coords]
        rings.append({"type": "exterior", "points": exterior_pts})
        for interior in poly.interiors:
            interior_pts = [{"lat": lat, "lon": lon} for lon, lat in interior.coords]
            rings.append({"type": "interior", "points": interior_pts})
    return [{"rings": rings}]


def ensure_farm(org_id: str, client_id: str, client_uri: str, farm_name: str, farms_by_name: dict, dry_run: bool):
    if farm_name in farms_by_name:
        return farms_by_name[farm_name]["id"], False
    print(f"  [farm nova] '{farm_name}' nao existe -> {'(dry-run) criaria' if dry_run else 'criando'}")
    if dry_run:
        return None, True
    resp = d.api_post(f"/organizations/{org_id}/farms", {"name": farm_name, "clientUri": client_uri})
    farm_id = resp.headers["Location"].rstrip("/").split("/")[-1]
    farms_by_name[farm_name] = {"id": farm_id}
    return farm_id, True


def ensure_field(org_id: str, farm_id: str, field_name: str, fields_by_name: dict, dry_run: bool):
    if field_name in fields_by_name:
        return fields_by_name[field_name]["id"], False
    print(f"  [field novo] '{field_name}' nao existe -> {'(dry-run) criaria' if dry_run else 'criando'}")
    if dry_run:
        return None, True
    farm_uri = f"{d.API_BASE}/organizations/{org_id}/farms/{farm_id}"
    resp = d.api_post(f"/organizations/{org_id}/fields", {"name": field_name, "farmLinks": [{"uri": farm_uri}]})
    field_id = resp.headers["Location"].rstrip("/").split("/")[-1]
    fields_by_name[field_name] = {"id": field_id}
    return field_id, True


def sync_one(org_id: str, client_id: str, client_uri: str, farm_name: str, field_name: str, geom_wgs84,
             farms_by_name: dict, fields_by_name: dict, dry_run: bool) -> dict:
    farm_id, farm_new = ensure_farm(org_id, client_id, client_uri, farm_name, farms_by_name, dry_run)
    if dry_run and farm_id is None:
        return {"farm_new": farm_new, "field_new": False, "boundary": "pulado (farm nova, dry-run)"}

    field_id, field_new = ensure_field(org_id, farm_id, field_name, fields_by_name, dry_run)
    if dry_run and field_id is None:
        return {"farm_new": farm_new, "field_new": field_new, "boundary": "pulado (field novo, dry-run)"}

    multipolygons = build_multipolygon(geom_wgs84)
    payload = {
        "name": f"Sync API {farm_name}",
        "active": True,
        "irrigated": False,
        "sourceType": "External",  # unico valor sem exigir licenca adicional
        "multipolygons": multipolygons,
    }

    if dry_run:
        n_pts = sum(len(r["points"]) for mp in multipolygons for r in mp["rings"])
        return {"farm_new": farm_new, "field_new": field_new, "boundary": f"criaria ({n_pts} pontos)"}

    resp = d.api_post(f"/organizations/{org_id}/fields/{field_id}/boundaries", payload)
    return {"farm_new": farm_new, "field_new": field_new, "boundary": f"criado ({resp.headers.get('Location')})"}


def main(config_path: str, force_live: bool = False):
    cfg = load_config(config_path)
    if force_live:
        cfg["dry_run"] = False
    org_id = cfg["org_id"]
    client_uri_base = f"{d.API_BASE}/organizations/{org_id}/clients"

    print("Localizando client...")
    client_id = find_client_id(org_id, cfg["client_name"])
    client_uri = f"{client_uri_base}/{client_id}"
    print(f"Client '{cfg['client_name']}' = {client_id}")

    print("Listando fazendas existentes (paginado)...")
    farms = _list_all(f"/organizations/{org_id}/farms")
    farms_by_name = {f["name"]: f for f in farms}
    print(f"  {len(farms_by_name)} fazenda(s) carregada(s)")

    print("Listando campos existentes (paginado)...")
    fields = _list_all(f"/organizations/{org_id}/fields")
    fields_by_name = {f["name"]: f for f in fields}
    print(f"  {len(fields_by_name)} campo(s) carregado(s)")

    input_shapefile = find_formatted_shapefile(cfg["output_dir"], cfg["output_basename"])
    print(f"Lendo {input_shapefile} ...")
    gdf = gpd.read_file(input_shapefile)
    gdf_wgs84 = gdf.to_crs(4326)

    only = cfg["only_farm_codes"]
    if only:
        gdf_wgs84 = gdf_wgs84[gdf_wgs84["FARM_NAME"].isin(only)]

    print(f"\n{len(gdf_wgs84)} fazenda(s) a processar. dry_run={cfg['dry_run']}\n")

    n_farms_new = n_fields_new = n_boundaries_ok = n_boundaries_falha = 0
    falhas = []
    for _, row in gdf_wgs84.iterrows():
        try:
            r = sync_one(
                org_id, client_id, client_uri,
                row["FARM_NAME"], row["FIELD_NAME"], row.geometry,
                farms_by_name, fields_by_name, cfg["dry_run"],
            )
            n_farms_new += r["farm_new"]
            n_fields_new += r["field_new"]
            n_boundaries_ok += 1
        except Exception as e:
            n_boundaries_falha += 1
            falhas.append((row["FARM_NAME"], str(e)))
            print(f"  [ERRO] fazenda {row['FARM_NAME']}: {e}")

    print("\n=== Resumo ===")
    print(f"Fazendas processadas: {len(gdf_wgs84)}")
    print(f"Fazendas novas (criadas/a criar): {n_farms_new}")
    print(f"Campos novos (criados/a criar): {n_fields_new}")
    print(f"Boundaries OK: {n_boundaries_ok}")
    print(f"Boundaries com erro: {n_boundaries_falha}")
    if falhas:
        print("\nFazendas com erro:")
        for nome, erro in falhas:
            print(f"  - {nome}: {erro}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--live"]
    force_live = "--live" in sys.argv[1:]
    config_path = args[0] if args else "config.yaml"
    main(config_path, force_live=force_live)
