"""
Gera um pacote de Arquivo de Configuracao (Gen4) com Linhas de Orientacao
(Curva Adaptavel) a partir de um shapefile de linhas ja formatado
(colunas CLIENT_NAM / FARM_NAME / FIELD_NAME, uma feicao por linha/sulco).

Formato reverso a partir de um export real do AgroCAD (Gen4/MasterData.xml +
Gen4/SpatialFiles/AdaptiveCurve<guid>.gjson).

Uso:
    python build_gen4_guidance.py <shapefile_linhas.shp> <pasta_saida>
"""

import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd
import warnings

warnings.filterwarnings("ignore")

NAMESPACE = uuid.UUID("6f6b6e6f-7772-4573-a4c0-6a6f686e6465")  # namespace fixo, so pra gerar GUIDs estaveis


def stable_guid(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "|".join(parts)))


def build_gjson(lines_wgs84) -> dict:
    coordinates = []
    for line in lines_wgs84:
        path = [[lon, lat, 0, 1] for lon, lat in line.coords]
        coordinates.append(path)
    return {"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": coordinates}}


def build_master_data_xml(client_name: str, groups: list) -> str:
    now_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="microseconds")
    created_iso = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

    client_guid = stable_guid("client", client_name)

    farms_xml = []
    fields_xml = []
    curves_xml = []
    seen_farms = set()

    for farm_name, field_name, curve_guid, ref_lat, ref_lon in groups:
        farm_guid = stable_guid("farm", client_name, farm_name)
        field_guid = stable_guid("field", client_name, farm_name, field_name)

        if farm_guid not in seen_farms:
            farms_xml.append(
                f'<Farm LastModifiedDate="{now_iso}" Archived="false" StringGuid="{farm_guid}" '
                f'Name="{escape(farm_name)}" Client="{client_guid}" />'
            )
            seen_farms.add(farm_guid)

        fields_xml.append(
            f'<Field LastModifiedDate="{now_iso}" Archived="false" StringGuid="{field_guid}" '
            f'Name="{escape(field_name)}"><Farm>{farm_guid}</Farm></Field>'
        )

        curves_xml.append(
            f'<AdaptiveCurve Archived="false" StringGuid="{curve_guid}" Name="CURVA" TaggedEntity="{field_guid}">'
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
        + "".join(farms_xml)
        + "".join(fields_xml)
        + '<Inputs><Products /></Inputs><Guidance><Tracks>'
        + "".join(curves_xml)
        + '</Tracks></Guidance>'
        '<SourceInformation><DisplayName /><Version /><SourceApplication /></SourceInformation>'
        f'<CreatedDateTime>{created_iso}</CreatedDateTime>'
        '</Setup></SetupFile>'
    )
    return xml


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
    spatial_dir = out_dir / "Gen4" / "SpatialFiles"
    spatial_dir.mkdir(parents=True, exist_ok=True)

    groups = []
    for (farm_name, field_name), rows in gdf.groupby(["FARM_NAME", "FIELD_NAME"]):
        lines = list(rows.geometry)
        curve_guid = stable_guid("curve", client_name, farm_name, field_name)
        first_line = lines[0]
        ref_lon, ref_lat = first_line.coords[0][:2]

        gjson = build_gjson(lines)
        gjson_path = spatial_dir / f"AdaptiveCurve{curve_guid}.gjson"
        import json
        with open(gjson_path, "w", encoding="utf-8") as f:
            json.dump(gjson, f)

        n_pts = sum(len(l.coords) for l in lines)
        print(f"Fazenda {farm_name} / Campo {field_name}: {len(lines)} linha(s), {n_pts} ponto(s) -> {gjson_path.name}")

        groups.append((str(farm_name), str(field_name), curve_guid, ref_lat, ref_lon))

    xml = build_master_data_xml(client_name, groups)
    xml_path = out_dir / "Gen4" / "MasterData.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"MasterData.xml gerado: {xml_path}")

    zip_path = out_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in out_dir.rglob("*"):
            if f.is_file():
                z.write(f, arcname=f.relative_to(out_dir))
    print(f"Zip pronto: {zip_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python build_gen4_guidance.py <shapefile_linhas.shp> <pasta_saida>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
