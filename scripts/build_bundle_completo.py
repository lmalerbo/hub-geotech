"""
Orquestrador: gera os 4 formatos (Gen4, GS3_2630, AgData, AgGPS) de uma vez a
partir de um shapefile ja classificado (colunas CLIENT_NAM / FARM_NAME /
FIELD_NAME -- saida de classificar_partes.py), replicando a mesma estrutura
de pastas que o AgroCAD gera nativamente:

    <pasta_saida>/
        Gen4/MasterData.xml + SpatialFiles/*.gjson
        GS3_2630/RCD/EIC/Fields/<XX>/<field_guid>/...  (1 field por fazenda)
        AgData/Fields/<uuid>.agf                        (1 arquivo por parte)
        AgGPS/Data/<cliente>/<fazenda tipo>/<parte>/...  (1 pasta por parte)

Gen4 e GS3_2630 consolidam todas as partes de uma fazenda num unico Field
(cada parte vira uma curva nomeada dentro dele -- ver build_gs3_2630_bundle.py
pra motivo). AgData e AgGPS mantem 1 entidade por parte, que e o padrao nativo
observado no export real do AgroCAD.

Uso:
    python build_bundle_completo.py <shapefile_classificado.shp> <pasta_saida>
"""

import sys
import uuid
import warnings
from pathlib import Path

import geopandas as gpd

import workflow_status as ws

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))

from build_gs3_2630_bundle import stable_guid  # noqa: E402
from build_gs3_2630_curve import gerar_fdshape  # noqa: E402
from build_gs3_2630_bundle import (  # noqa: E402
    build_import_export_catalog, build_export_only_catalog,
    build_water_management_catalog, pasta_campo,
)
from agdata_build import build_agf  # noqa: E402
from aggps_build import build_aggps  # noqa: E402
from datetime import datetime, timezone  # noqa: E402


def gerar_gen4(client_name, farm_name, grupos_por_parte, out_dir: Path):
    """grupos_por_parte: dict part_name -> list[LineString]"""
    import json
    from xml.sax.saxutils import escape

    spatial_dir = out_dir / "Gen4" / "SpatialFiles"
    spatial_dir.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="microseconds")
    created_iso = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    client_guid = stable_guid("client", client_name)
    farm_guid = stable_guid("farm", client_name, farm_name)
    field_guid = stable_guid("field", client_name, farm_name)

    curvas_xml = []
    for part_name, lines in grupos_por_parte.items():
        curve_guid = stable_guid("curve-v2", client_name, farm_name, part_name)
        coordinates = [[[lon, lat, 0, 1] for lon, lat in line.coords] for line in lines]
        gjson = {"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": coordinates}}
        (spatial_dir / f"AdaptiveCurve{curve_guid}.gjson").write_text(json.dumps(gjson), encoding="utf-8")

        ref_lon, ref_lat = lines[0].coords[0][:2]
        curvas_xml.append(
            f'<AdaptiveCurve Archived="false" StringGuid="{curve_guid}" Name="{escape(part_name)}" TaggedEntity="{field_guid}">'
            f'<SignalType Representation="dtSignalType" Value="dtiSignalTypeUnknown" />'
            f'<Geometry><FilenameWithExtension>AdaptiveCurve{curve_guid}.gjson</FilenameWithExtension>'
            f'<Path>./SpatialFiles/</Path></Geometry>'
            f'<SpatialProjection><ProjectionType Representation="dtProjectionType" Value="dtiProjectionDeere" />'
            f'<ElevationReferencePoint Representation="vrElevation" Value="0" SourceUnit="m" /></SpatialProjection>'
            f'<ReferenceLatitude Representation="vrLatitude" Value="{ref_lat}" SourceUnit="arcdeg" />'
            f'<ReferenceLongitude Representation="vrLongitude" Value="{ref_lon}" SourceUnit="arcdeg" />'
            f'</AdaptiveCurve>'
        )

    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<SetupFile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns="urn:schemas-johndeere-com:Setup">'
        '<SourceApp minor="0" major="0" build="0" revision="0" nameSourceApp="" SourceAppClientId="" />'
        '<FileSchemaVersion nonProductionCode="0"><FileSchemaContentVersion major="2" minor="19" />'
        '<UnitOfMeasureVersion major="1" minor="8" /><RepresentationSystemVersion major="3" minor="13" />'
        '</FileSchemaVersion><Setup>'
        f'<Client Archived="false" StringGuid="{client_guid}" Name="{escape(client_name)}" />'
        f'<Farm LastModifiedDate="{now_iso}" Archived="false" StringGuid="{farm_guid}" '
        f'Name="{escape(farm_name)}" Client="{client_guid}" />'
        f'<Field LastModifiedDate="{now_iso}" Archived="false" StringGuid="{field_guid}" '
        f'Name="{escape(farm_name)}"><Farm>{farm_guid}</Farm></Field>'
        '<Inputs><Products /></Inputs><Guidance><Tracks>'
        + "".join(curvas_xml)
        + '</Tracks></Guidance>'
        '<SourceInformation><DisplayName /><Version /><SourceApplication /></SourceInformation>'
        f'<CreatedDateTime>{created_iso}</CreatedDateTime>'
        '</Setup></SetupFile>'
    )
    (out_dir / "Gen4" / "MasterData.xml").write_text(xml, encoding="utf-8")


def gerar_gs3_2630(client_name, farm_name, grupos_por_parte, out_dir: Path):
    now_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="microseconds")
    client_guid = stable_guid("client", client_name)
    farm_guid = stable_guid("farm", client_name, farm_name)
    field_guid = stable_guid("field", client_name, farm_name)

    campo_dir = out_dir / "GS3_2630" / client_name.replace(" ", "") / "RCD" / "EIC" / "Fields" / pasta_campo(field_guid) / field_guid
    campo_dir.mkdir(parents=True, exist_ok=True)

    curvas = []
    for part_name, lines in grupos_por_parte.items():
        curve_guid = stable_guid("curve-v2", client_name, farm_name, part_name)
        paths = [list(line.coords) for line in lines]
        fdshape = gerar_fdshape(paths)
        (campo_dir / f"CurveTrack{curve_guid}.fdShape").write_bytes(fdshape)
        curvas.append({"curve_guid": curve_guid, "curve_name": part_name, "paths": paths})

    ctx = {
        "client_name": client_name, "client_guid": client_guid,
        "farm_name": farm_name, "farm_guid": farm_guid,
        "field_name": farm_name, "field_guid": field_guid,
        "now_iso": now_iso, "curvas": curvas,
    }
    (campo_dir / "ImportExport.SpatialCatalog").write_text(build_import_export_catalog(ctx), encoding="utf-8")
    (campo_dir / "ExportOnly.SpatialCatalog").write_text(build_export_only_catalog(ctx), encoding="utf-8")
    (campo_dir / "WaterManagement.SpatialCatalog").write_text(build_water_management_catalog(ctx), encoding="utf-8")


def gerar_agdata(client_name, farm_name, grupos_por_parte, out_dir: Path):
    fields_dir = out_dir / "AgData" / "Fields"
    fields_dir.mkdir(parents=True, exist_ok=True)
    for part_name, lines in grupos_por_parte.items():
        field_uuid = stable_guid("agdata-field", client_name, farm_name, part_name)
        paths = [list(line.coords) for line in lines]
        agf_bytes = build_agf(field_uuid, part_name, client_name, farm_name, paths)
        (fields_dir / f"{field_uuid}.agf").write_bytes(agf_bytes)


def gerar_aggps(client_name, farm_name, grupos_por_parte, out_dir: Path):
    base = out_dir / "AgGPS" / "Data" / client_name / farm_name
    for part_name, lines in grupos_por_parte.items():
        paths = [list(line.coords) for line in lines]
        build_aggps(base / part_name, paths)


def main(shp_path: str, out_dir: str):
    gdf = gpd.read_file(shp_path).to_crs(4326)

    required = ["CLIENT_NAM", "FARM_NAME", "FIELD_NAME"]
    missing = [c for c in required if c not in gdf.columns]
    if missing:
        raise ValueError(f"Faltam colunas no shapefile: {missing}")

    client_names = gdf["CLIENT_NAM"].unique()
    if len(client_names) > 1:
        raise ValueError(f"Mais de um CLIENT_NAM no shapefile ({client_names}); rode um cliente por vez.")
    client_name = client_names[0]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # tenta inferir o tipo (1L/2L) do nome do shapefile (padrao <codigo>_<tipo>.shp)
    stem = Path(shp_path).stem
    tipo_inferido = stem.split("_", 1)[1] if "_" in stem else ""

    for farm_name, rows_fazenda in gdf.groupby("FARM_NAME"):
        farm_name = str(farm_name)
        grupos_por_parte = {
            str(part_name): list(rows.geometry)
            for part_name, rows in rows_fazenda.groupby("FIELD_NAME")
        }
        n_partes = len(grupos_por_parte)
        n_linhas = sum(len(v) for v in grupos_por_parte.values())
        print(f"Fazenda {farm_name}: {n_partes} parte(s), {n_linhas} linha(s) -> gerando 4 formatos...")

        with ws.rastrear_etapa(farm_name, farm_name, tipo_inferido, "gen4") as r:
            gerar_gen4(client_name, farm_name, grupos_por_parte, out_dir)
            r.detalhes = {"n_partes": n_partes}
        with ws.rastrear_etapa(farm_name, farm_name, tipo_inferido, "gs3_2630") as r:
            gerar_gs3_2630(client_name, farm_name, grupos_por_parte, out_dir)
            r.detalhes = {"n_partes": n_partes}
        with ws.rastrear_etapa(farm_name, farm_name, tipo_inferido, "agdata") as r:
            gerar_agdata(client_name, farm_name, grupos_por_parte, out_dir)
            r.detalhes = {"n_partes": n_partes}
        with ws.rastrear_etapa(farm_name, farm_name, tipo_inferido, "aggps") as r:
            gerar_aggps(client_name, farm_name, grupos_por_parte, out_dir)
            r.detalhes = {"n_partes": n_partes}

        print(f"  OK -> {out_dir}/{{Gen4,GS3_2630,AgData,AgGPS}}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python build_bundle_completo.py <shapefile_classificado.shp> <pasta_saida>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
