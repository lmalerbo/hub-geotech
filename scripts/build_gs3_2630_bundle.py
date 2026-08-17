"""
Gera um bundle GS3_2630 (RCD/EIC/Fields/...) com Linhas de Orientacao (Curva
Adaptavel / CurvedTrackLine) a partir do MESMO shapefile de entrada usado por
build_gen4_guidance.py (colunas CLIENT_NAM / FARM_NAME / FIELD_NAME).

Formato reverso a partir de um export real do AgroCAD (ver build_gs3_2630_curve.py
para o binario .fdShape, validado byte-a-byte contra 2 curvas reais).

O TALHAO (Field) no OC corresponde a FAZENDA inteira (FARM_NAME, ja o codigo de
SECAO) -- e nao a cada "parte"/bloco em que a curva foi dividida por tamanho de
arquivo. Colocar cada parte como um Field separado faz o OC criar um talhao vazio
arquivado por parte, em vez de anexar a orientacao ao talhao real ja existente.
Entao: 1 Field por (CLIENT_NAM, FARM_NAME), com N CurvedTrackLine dentro dele
(uma por FIELD_NAME/parte original do shapefile), cada uma com seu proprio nome
= o FIELD_NAME original (ex: "1L-1", "1L-2", ...) via <CurvedTrackLine name="...">.

O bundle gerado contem, por fazenda:
    RCD/EIC/Fields/<XX>/<field_guid>/
        CurveTrack<curve_guid>.fdShape        (binario, pontos da curva -- um por parte)
        ImportExport.SpatialCatalog           (XML, uma <CurvedTrackLine> por parte)
        ExportOnly.SpatialCatalog             (XML, vazio -- so referencia o campo)
        WaterManagement.SpatialCatalog        (XML, vazio -- so referencia o campo)

Onde <XX> = 2 ultimos caracteres (maiusculos) do 1o grupo do field_guid
(convencao observada nos exports reais: fff5a402-... -> pasta "02";
dfe2eaa2-... -> pasta "A2").

NAO gerado (nao sao dados de curva, ver investigacao): global.ver, host,
setup.fds -- arquivos de nivel de sessao/dispositivo em RCD/EIC/. Recomenda-se
copia-los de um bundle de referencia real (--copiar-sidecars-de) ao montar o
pacote final, e deixar o proprio display GS3 resincronizar esses metadados.

Uso:
    python build_gs3_2630_bundle.py <shapefile_linhas.shp> <pasta_saida> [--copiar-sidecars-de <bundle_referencia>]
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd
import warnings

from build_gs3_2630_curve import gerar_fdshape

warnings.filterwarnings("ignore")

NAMESPACE = uuid.UUID("6f6b6e6f-7772-4573-a4c0-6a6f686e6465")  # mesmo namespace do build_gen4_guidance.py

# constantes observadas identicas em todos os catalogos do bundle de referencia real
SOURCE_APP_ATTRS = (
    'major="3" minor="0" build="0" revision="117" '
    'nameSourceApp="RCD Target Provider" '
    'uuidSourceApp="{b050528e-f328-4dd8-9e9c-71fe8153692e}" '
    'uuidSourceAppNode="{6a6f41f7-9f44-4174-8168-0cb0ef0842d4}"'
)


def stable_guid(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "|".join(parts)))


def pasta_campo(field_guid: str) -> str:
    return field_guid.split("-")[0][-2:].upper()


def _setup_block(client_name, client_guid, farm_name, farm_guid, field_name, field_guid, now_iso) -> str:
    return (
        "<Setup>"
        f'<rcdsetup:FileSchemaVersion nonProductionCode="0">'
        f'<bt:FileSchemaContentVersion major="3" minor="28" />'
        f'<bt:UnitOfMeasureVersion major="1" minor="43" />'
        f'<bt:RepresentationSystemVersion major="4" minor="161" />'
        f"</rcdsetup:FileSchemaVersion>"
        f"<bt:Synchronization><bt:NodeVersions>"
        f'<bt:Node uuid="{{{uuid.uuid4()}}}" lastSeen="{now_iso}" />'
        f"</bt:NodeVersions><bt:EntityDeletions /></bt:Synchronization>"
        f"<rcdsetup:Participant>"
        f'<rcdsetup:Client lastModified="1970-01-01T00:00:00" '
        f'sourceNode="{{6a6f41f7-9f44-4174-8168-0cb0ef0842d4}}" '
        f'erid="{{{client_guid}}}" name="{escape(client_name)}" />'
        f"</rcdsetup:Participant>"
        f'<rcdsetup:Farm lastModified="{now_iso}" '
        f'sourceNode="{{6a6f41f7-9f44-4174-8168-0cb0ef0842d4}}" '
        f'erid="{{{farm_guid}}}" name="{escape(farm_name)}" clientRef="{{{client_guid}}}" />'
        f'<rcdsetup:Field lastModified="{now_iso}" '
        f'sourceNode="{{6a6f41f7-9f44-4174-8168-0cb0ef0842d4}}" '
        f'erid="{{{field_guid}}}" name="{escape(field_name)}" farmRef="{{{farm_guid}}}" />'
        f"<rcdsetup:Products />"
        f"</Setup>"
    )


def _curved_track_line_xml(curve: dict, now_iso: str) -> str:
    paths = curve["paths"]
    lons = [lon for path in paths for lon, lat in path]
    lats = [lat for path in paths for lon, lat in path]
    north, south = max(lats), min(lats)
    east, west = max(lons), min(lons)
    ref_lon, ref_lat = paths[0][0]

    return (
        f'<CurvedTrackLine lastModified="{now_iso}" '
        f'sourceNode="{{6a6f41f7-9f44-4174-8168-0cb0ef0842d4}}" '
        f'erid="{{{curve["curve_guid"]}}}" spatialGeometryType="point" '
        f'fileName="CurveTrack{curve["curve_guid"]}" name="{escape(curve["curve_name"])}">'
        f'<spatial:MBR uomSource="arcdeg" uomTarget="arcdeg" '
        f'north="{north}" south="{south}" east="{east}" west="{west}" />'
        f'<spatial:dtSignalType value="dtiSignalTypeUnknown" definedTypeRepresentation="dtSignalType" />'
        f'<rcdscbase:vrEastShiftComponent value="0" sourceUOM="m" variableRepresentation="vrEastShiftComponent" />'
        f'<rcdscbase:vrNorthShiftComponent value="0" sourceUOM="m" variableRepresentation="vrNorthShiftComponent" />'
        f'<rcdscbase:vrReferenceLatitude value="{ref_lat}" sourceUOM="arcdeg" variableRepresentation="vrLatitude" />'
        f'<rcdscbase:vrReferenceLongitude value="{ref_lon}" sourceUOM="arcdeg" variableRepresentation="vrLongitude" />'
        "</CurvedTrackLine>"
    )


def build_import_export_catalog(ctx: dict) -> str:
    curvas_xml = "".join(_curved_track_line_xml(c, ctx["now_iso"]) for c in ctx["curvas"])

    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<rcdscfldie:SpatialCatalog '
        'xmlns:spatial="urn:schemas-johndeere-com:SpatialTypes" '
        'xmlns:bt="urn:schemas-johndeere-com:BasicTypes" '
        'xmlns:rep="urn:schemas-johndeere-com:Representation" '
        'xmlns:unit="urn:schemas-johndeere-com:UnitSystem" '
        'xmlns:rcdscbase="urn:schemas-johndeere-com:RCD:SpatialCatalog:Base" '
        'xmlns:rcdsetup="urn:schemas-johndeere-com:RCD:Setup" '
        'xmlns:rcdscfldie="urn:schemas-johndeere-com:RCD:SpatialCatalog:FieldImportExport">'
        '<FileSchemaVersion nonProductionCode="0">'
        '<bt:FileSchemaContentVersion major="1" minor="11" />'
        '<bt:UnitOfMeasureVersion major="1" minor="43" />'
        '<bt:RepresentationSystemVersion major="4" minor="161" />'
        "</FileSchemaVersion>"
        f'<SourceApp {SOURCE_APP_ATTRS} uuidSession="{{{uuid.uuid4()}}}" />'
        + _setup_block(
            ctx["client_name"], ctx["client_guid"],
            ctx["farm_name"], ctx["farm_guid"],
            ctx["field_name"], ctx["field_guid"],
            ctx["now_iso"],
        )
        + f'<SpatialItems eridFieldRef="{{{ctx["field_guid"]}}}">'
        + curvas_xml
        + "</SpatialItems>"
        "</rcdscfldie:SpatialCatalog>"
    )


def build_export_only_catalog(ctx: dict) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<rcdscfld:SpatialCatalog '
        'xmlns:spatial="urn:schemas-johndeere-com:SpatialTypes" '
        'xmlns:bt="urn:schemas-johndeere-com:BasicTypes" '
        'xmlns:rep="urn:schemas-johndeere-com:Representation" '
        'xmlns:unit="urn:schemas-johndeere-com:UnitSystem" '
        'xmlns:rcdscbase="urn:schemas-johndeere-com:RCD:SpatialCatalog:Base" '
        'xmlns:rcdsetup="urn:schemas-johndeere-com:RCD:Setup" '
        'xmlns:rcdscfld="urn:schemas-johndeere-com:RCD:SpatialCatalog:Field">'
        '<rcdscfld:FileSchemaVersion nonProductionCode="0">'
        '<bt:FileSchemaContentVersion major="1" minor="3" />'
        '<bt:UnitOfMeasureVersion major="1" minor="43" />'
        '<bt:RepresentationSystemVersion major="4" minor="161" />'
        "</rcdscfld:FileSchemaVersion>"
        f'<rcdscfld:SourceApp {SOURCE_APP_ATTRS} uuidSession="{{{uuid.uuid4()}}}" />'
        f'<rcdscfld:SpatialItems eridFieldRef="{{{ctx["field_guid"]}}}" />'
        "</rcdscfld:SpatialCatalog>"
    )


def build_water_management_catalog(ctx: dict) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<rcdscfldiewm:SpatialCatalog '
        'xmlns:spatial="urn:schemas-johndeere-com:SpatialTypes" '
        'xmlns:bt="urn:schemas-johndeere-com:BasicTypes" '
        'xmlns:rep="urn:schemas-johndeere-com:Representation" '
        'xmlns:unit="urn:schemas-johndeere-com:UnitSystem" '
        'xmlns:rcdscbase="urn:schemas-johndeere-com:RCD:SpatialCatalog:Base" '
        'xmlns:rcdsetup="urn:schemas-johndeere-com:RCD:Setup" '
        'xmlns:rcdscfldiewm="urn:schemas-johndeere-com:RCD:SpatialCatalog:FieldImportExportWaterManagment">'
        '<FileSchemaVersion nonProductionCode="0">'
        '<bt:FileSchemaContentVersion major="1" minor="9" />'
        '<bt:UnitOfMeasureVersion major="1" minor="43" />'
        '<bt:RepresentationSystemVersion major="4" minor="161" />'
        "</FileSchemaVersion>"
        f'<SourceApp {SOURCE_APP_ATTRS} uuidSession="{{{uuid.uuid4()}}}" />'
        + _setup_block(
            ctx["client_name"], ctx["client_guid"],
            ctx["farm_name"], ctx["farm_guid"],
            ctx["field_name"], ctx["field_guid"],
            ctx["now_iso"],
        )
        + f'<SpatialItems eridFieldRef="{{{ctx["field_guid"]}}}" />'
        "</rcdscfldiewm:SpatialCatalog>"
    )


def empacotar_zip(out_dir: str, client_name: str) -> Path:
    """Empacota RCD/ dentro de GS3_2630/<cliente>/RCD/... -- o OC so reconhece o
    Tipo como GS3_2630 (em vez de 'Invalido') com esse envelope de pasta."""
    import zipfile

    out_dir = Path(out_dir)
    rcd_dir = out_dir / "RCD"
    cliente_pasta = client_name.replace(" ", "")
    zip_path = out_dir.with_name(out_dir.name + "_GS3_2630").with_suffix(".zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in rcd_dir.rglob("*"):
            if f.is_file():
                arcname = Path("GS3_2630") / cliente_pasta / f.relative_to(out_dir)
                z.write(f, arcname=arcname)
    return zip_path


def main(shp_path: str, out_dir: str, copiar_sidecars_de: str | None = None):
    gdf = gpd.read_file(shp_path).to_crs(4326)

    required = ["CLIENT_NAM", "FARM_NAME", "FIELD_NAME"]
    missing = [c for c in required if c not in gdf.columns]
    if missing:
        raise ValueError(f"Faltam colunas no shapefile: {missing}")

    client_names = gdf["CLIENT_NAM"].unique()
    if len(client_names) > 1:
        raise ValueError(f"Mais de um CLIENT_NAM no shapefile ({client_names}); rode um cliente por vez.")
    client_name = client_names[0]
    client_guid = stable_guid("client", client_name)

    now_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="microseconds")

    fields_root = Path(out_dir) / "RCD" / "EIC" / "Fields"
    fields_root.mkdir(parents=True, exist_ok=True)

    for farm_name, rows_fazenda in gdf.groupby("FARM_NAME"):
        farm_name = str(farm_name)
        farm_guid = stable_guid("farm", client_name, farm_name)
        # 1 Field por fazenda -- mesmo nome da fazenda, pra cair no talhao real
        # ja existente no OC em vez de criar um talhao vazio por parte
        field_name = farm_name
        field_guid = stable_guid("field", client_name, farm_name)

        campo_dir = fields_root / pasta_campo(field_guid) / field_guid
        campo_dir.mkdir(parents=True, exist_ok=True)

        curvas = []
        for part_name, rows in rows_fazenda.groupby("FIELD_NAME"):
            part_name = str(part_name)
            # "curve-v2": salt diferente de "curve" (usado no 1o teste, quando cada
            # parte virava um Field separado) -- evita colisao de erid com aquelas
            # entidades ja existentes no OC, vinculadas ao Field antigo (por parte)
            curve_guid = stable_guid("curve-v2", client_name, farm_name, part_name)
            paths = [[(lon, lat) for lon, lat in geom.coords] for geom in rows.geometry]

            fdshape = gerar_fdshape(paths)
            (campo_dir / f"CurveTrack{curve_guid}.fdShape").write_bytes(fdshape)

            curvas.append({"curve_guid": curve_guid, "curve_name": part_name, "paths": paths})
            print(
                f"Fazenda {farm_name} / Parte {part_name}: {len(paths)} path(s), "
                f"{sum(len(p) for p in paths)} ponto(s) -> curva '{part_name}'"
            )

        ctx = {
            "client_name": client_name, "client_guid": client_guid,
            "farm_name": farm_name, "farm_guid": farm_guid,
            "field_name": field_name, "field_guid": field_guid,
            "now_iso": now_iso, "curvas": curvas,
        }

        (campo_dir / "ImportExport.SpatialCatalog").write_text(
            build_import_export_catalog(ctx), encoding="utf-8"
        )
        (campo_dir / "ExportOnly.SpatialCatalog").write_text(
            build_export_only_catalog(ctx), encoding="utf-8"
        )
        (campo_dir / "WaterManagement.SpatialCatalog").write_text(
            build_water_management_catalog(ctx), encoding="utf-8"
        )

        print(
            f"-> Talhao '{field_name}' com {len(curvas)} curva(s) em "
            f"Fields/{pasta_campo(field_guid)}/{field_guid}/"
        )

    if copiar_sidecars_de:
        import shutil

        origem = Path(copiar_sidecars_de)
        eic_dir = Path(out_dir) / "RCD" / "EIC"
        for nome in ["global.ver", "host", "setup.fds"]:
            achado = next(origem.rglob(nome), None)
            if achado:
                shutil.copy2(achado, eic_dir / nome)
                print(f"Copiado sidecar '{nome}' de {achado}")
            else:
                print(f"AVISO: sidecar '{nome}' nao encontrado em {origem}")
        print(
            "\nATENCAO: setup.fds copiado de outro bundle carrega o catalogo de "
            "Setup (cliente/fazenda/campo/maquinas/implementos) daquele export "
            "ORIGINAL -- confirmado que isso contamina o upload com fazenda(s), "
            "maquina(s) e implemento(s) que nao sao deste lote. So use "
            "--copiar-sidecars-de se for testar exclusivamente a leitura do "
            ".fdShape/.SpatialCatalog; para producao, teste primeiro SEM sidecars."
        )
    else:
        print(
            "\nNao inclui global.ver / host / setup.fds (nao sao dados de curva -- "
            "ver docstring; setup.fds em especial carrega cliente/fazenda/campo/"
            "maquinas de QUALQUER bundle de origem, entao copia-lo contamina o "
            "upload). Testando sem eles primeiro."
        )

    zip_path = empacotar_zip(out_dir, client_name)
    print(f"\nZip pronto pra upload: {zip_path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    copiar_de = None
    if "--copiar-sidecars-de" in args:
        i = args.index("--copiar-sidecars-de")
        copiar_de = args[i + 1]
        del args[i:i + 2]

    if len(args) != 2:
        print(
            "Uso: python build_gs3_2630_bundle.py <shapefile_linhas.shp> <pasta_saida> "
            "[--copiar-sidecars-de <bundle_referencia>]"
        )
        sys.exit(1)
    main(args[0], args[1], copiar_de)
