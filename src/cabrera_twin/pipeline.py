"""The build step: processed series → indicators → data/exports.

ingest/ fills data/processed, analysis/ computes the indicators, export/ writes
the metadata as JSON, the tables as Parquet, and a STAC catalog.
"""

from cabrera_twin.analysis import indicators
from cabrera_twin.export import stac, tables
from cabrera_twin.ingest import mpa, sst


def build() -> None:
    sst_ds = sst.open_sst()
    result = indicators.compute(sst_ds, mpa.mask_for(sst_ds))
    tables.write_meta(result, sst_ds.attrs)
    tables.write_parquet(result)
    stac.write_catalog()
