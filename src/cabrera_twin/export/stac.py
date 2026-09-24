"""Static STAC catalog of the processed series and the exported indicators."""

import json
from datetime import UTC, datetime

import pystac

from cabrera_twin import config

# Licences of the data, per source (the code is MIT)
LICENCES = {
    "copernicus": pystac.Link(
        rel="license",
        target="https://marine.copernicus.eu/user-corner/service-commitments-and-licence",
        title="Copernicus Marine Service licence",
    ),
    "socib": pystac.Link(
        rel="license",
        target="https://creativecommons.org/licenses/by/4.0/",
        title="SOCIB data, CC BY 4.0",
    ),
    "osm": pystac.Link(
        rel="license",
        target="https://opendatacommons.org/licenses/odbl/",
        title="MPA boundary from OpenStreetMap, ODbL",
    ),
}
PROVIDERS = [
    pystac.Provider(
        name="E.U. Copernicus Marine Service",
        roles=[pystac.ProviderRole.PRODUCER],
        url="https://marine.copernicus.eu",
    ),
    pystac.Provider(
        name="SOCIB",
        roles=[pystac.ProviderRole.PRODUCER],
        url="https://www.socib.es",
    ),
    pystac.Provider(
        name="Pierre St-Cricq dit Lompre",
        roles=[pystac.ProviderRole.PROCESSOR, pystac.ProviderRole.HOST],
        url="https://github.com/pstcricq/cabrera-mhw-twin",
    ),
]


def _bbox() -> list[float]:
    box = config.BBOX
    return [box["lon_min"], box["lat_min"], box["lon_max"], box["lat_max"]]


def _item(
    item_id: str, title: str, description: str, start: str, end: str
) -> pystac.Item:
    item = pystac.Item(
        id=item_id,
        geometry={
            "type": "Polygon",
            "coordinates": [
                [
                    [_bbox()[0], _bbox()[1]],
                    [_bbox()[2], _bbox()[1]],
                    [_bbox()[2], _bbox()[3]],
                    [_bbox()[0], _bbox()[3]],
                    [_bbox()[0], _bbox()[1]],
                ]
            ],
        },
        bbox=_bbox(),
        datetime=None,
        start_datetime=datetime.fromisoformat(start).replace(tzinfo=UTC),
        end_datetime=datetime.fromisoformat(end).replace(tzinfo=UTC),
        properties={"title": title, "description": description},
    )
    return item


def build_catalog() -> pystac.Catalog:
    """Describe the processed series and the indicators as a static STAC catalog."""
    meta = json.loads(config.META_FILE.read_text())
    last = meta["last_date"]

    catalog = pystac.Catalog(
        id="cabrera-mhw-twin",
        title="Marine heatwaves in the Cabrera National Park",
        description=(
            "Daily satellite sea surface temperature, in-situ temperature from the "
            "SOCIB Station Cabrera, and marine heatwave indicators (Hobday et al., "
            "2016, 2018) for the Cabrera Archipelago National Park."
        ),
    )

    collection = pystac.Collection(
        id="cabrera-mhw",
        description="Harmonised series and derived heatwave indicators.",
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent([_bbox()]),
            temporal=pystac.TemporalExtent(
                [
                    [
                        datetime.fromisoformat(config.SST_START).replace(tzinfo=UTC),
                        datetime.fromisoformat(last).replace(tzinfo=UTC),
                    ]
                ]
            ),
        ),
        license="other",
        providers=PROVIDERS,
        keywords=[
            "marine heatwave",
            "sea surface temperature",
            "marine protected area",
            "Balearic Islands",
            "digital twin ocean",
        ],
    )
    collection.add_links([link.clone() for link in LICENCES.values()])
    catalog.add_child(collection)

    satellite = _item(
        "satellite-sst",
        "Daily satellite SST over the MPA box",
        meta["sst_source"],
        config.SST_START,
        last,
    )
    satellite.add_asset(
        "data",
        pystac.Asset(
            href="../../../../processed/sst_cabrera_daily.zarr",
            media_type="application/vnd+zarr",
            roles=["data"],
            title="Zarr store, daily, 0.05 degrees, appended as new days arrive",
        ),
    )

    station = _item(
        "socib-station-cabrera",
        "SOCIB Station Cabrera daily temperature",
        "Daily means at 1, 13 and 16.7 m, QC flags 1-2, validating the satellite.",
        "2025-07-11",
        last,
    )
    station.add_asset(
        "data",
        pystac.Asset(
            href="../../../../processed/socib_cabrera_daily.nc",
            media_type="application/netcdf",
            roles=["data"],
            title="CF NetCDF, daily means per depth",
        ),
    )

    method = meta["method"]
    baseline = f"{method['climatology'][0]}-{method['climatology'][1]}"
    indicators = _item(
        "heatwave-indicators",
        "Marine heatwave indicators and what-if scenarios",
        (
            f"Detection with {method['reference']}, {baseline} baseline, "
            f"{method['percentile']}th percentile threshold. "
            f"Scenarios: {', '.join(meta['scenarios'])} degrees Celsius."
        ),
        config.SST_START,
        last,
    )
    indicators.add_asset(
        "meta",
        pystac.Asset(
            href="../../../meta.json",
            media_type=pystac.MediaType.JSON,
            roles=["metadata"],
            title="Provenance, method parameters and current status",
        ),
    )
    for name in ("daily", "yearly", "events", "pixels", "validation"):
        indicators.add_asset(
            name,
            pystac.Asset(
                href=f"../../../parquet/{name}.parquet",
                media_type="application/vnd.apache.parquet",
                roles=["data"],
                title=f"{name} table, queried by the API with SQL",
            ),
        )

    licences = {
        satellite: ("other", ["copernicus"]),
        station: ("CC-BY-4.0", ["socib"]),
        indicators: ("other", ["copernicus", "socib", "osm"]),
    }
    for item, (licence, sources) in licences.items():
        item.common_metadata.license = licence
        item.add_links([LICENCES[source].clone() for source in sources])
        collection.add_item(item)
    return catalog


def write_catalog() -> None:
    """Write the catalog next to the exports it describes."""
    catalog = build_catalog()
    catalog.normalize_hrefs(str(config.STAC_DIR))
    catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
