"""
Formata um shapefile bruto de talhoes para o padrao de importacao de limites
do John Deere Operations Center (CLIENT_NAM / FARM_NAME / FIELD_NAME / POLYGONTYP).

Uso:
    python format_oc_boundaries.py [config.yaml]

Se nenhum arquivo de config for informado, usa "config.yaml" na pasta atual.
"""

import sys
import warnings
import zipfile
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

warnings.filterwarnings("ignore")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    required = ["input_dir", "farm_code_field", "client_name", "output_dir", "output_basename"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ValueError(f"Faltam campos obrigatorios no config: {missing}")

    cfg.setdefault("include_prefix", None)
    return cfg


def find_input_shapefile(input_dir: str) -> Path:
    shp_files = sorted(Path(input_dir).glob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"Nenhum .shp encontrado em '{input_dir}'. Coloque o shapefile bruto ali.")
    if len(shp_files) > 1:
        nomes = ", ".join(f.name for f in shp_files)
        raise ValueError(f"Mais de um .shp encontrado em '{input_dir}' ({nomes}). Deixe so o mais recente ali.")
    return shp_files[0]


def format_boundaries(cfg: dict) -> Path:
    input_path = find_input_shapefile(cfg["input_dir"])

    print(f"Lendo {input_path} ...")
    gdf = gpd.read_file(input_path)

    farm_field = cfg["farm_code_field"]
    if farm_field not in gdf.columns:
        raise ValueError(f"Coluna '{farm_field}' nao existe no shapefile. Colunas disponiveis: {list(gdf.columns)}")

    total_in = len(gdf)

    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        print(f"Corrigindo {invalid.sum()} geometria(s) invalida(s)...")
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].buffer(0)

    null_farm = gdf[farm_field].isna()
    if null_farm.any():
        print(f"Descartando {null_farm.sum()} linha(s) sem codigo de fazenda ('{farm_field}' nulo).")
        gdf = gdf[~null_farm].copy()

    gdf["FARM_NAME"] = gdf[farm_field].astype("int64").astype(str)

    if cfg["include_prefix"]:
        prefix = str(cfg["include_prefix"])
        before = gdf["FARM_NAME"].nunique()
        gdf = gdf[gdf["FARM_NAME"].str.startswith(prefix)].copy()
        after = gdf["FARM_NAME"].nunique()
        print(f"Mantendo so fazendas com codigo iniciado em '{prefix}': {before} -> {after} fazenda(s).")

    if gdf.empty:
        raise ValueError("Nenhuma feicao restante apos os filtros. Revise o config.")

    print(f"Dissolvendo {len(gdf)} talhao(oes) por FARM_NAME...")
    dissolved = gdf.dissolve(by="FARM_NAME", as_index=False)[["FARM_NAME", "geometry"]]

    dissolved["CLIENT_NAM"] = cfg["client_name"]
    dissolved["FIELD_NAME"] = dissolved["FARM_NAME"]
    dissolved["POLYGONTYP"] = pd.array([None] * len(dissolved), dtype="Int64")

    out = dissolved[["CLIENT_NAM", "FARM_NAME", "FIELD_NAME", "POLYGONTYP", "geometry"]]

    output_dir = Path(cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime("%d_%m_%Y")
    basename = f"{cfg['output_basename']}_{today}"
    shp_path = output_dir / f"{basename}.shp"

    out.to_file(shp_path)
    print(f"Shapefile gerado: {shp_path} ({len(out)} fazenda(s), de {total_in} talhao(oes) originais)")

    zip_path = output_dir / f"{basename}.zip"
    sidecar_exts = [".shp", ".shx", ".dbf", ".prj", ".cpg"]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for ext in sidecar_exts:
            f = output_dir / f"{basename}{ext}"
            if f.exists():
                z.write(f, arcname=f.name)

    print(f"Zip pronto para upload no Operations Center: {zip_path}")
    return zip_path


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = load_config(config_path)
    format_boundaries(config)
