"""Command line.

`cabrera-twin fetch` downloads and harmonises the sources from scratch,
`cabrera-twin update` appends the satellite days published since the last run,
`cabrera-twin build` exports the indicators.
"""

import argparse

from cabrera_twin import pipeline
from cabrera_twin.ingest import insitu, mpa, sst


def main() -> None:
    parser = argparse.ArgumentParser(prog="cabrera-twin")
    parser.add_argument("command", choices=["fetch", "update", "build", "all"])
    args = parser.parse_args()
    if args.command in ("fetch", "all"):
        mpa.fetch_mpa()
        insitu.fetch_insitu()
        sst.fetch_sst()
    if args.command == "update":
        insitu.fetch_insitu()
        before = sst.open_sst().time.size
        after = sst.update_sst().time.size
        print(f"{after - before} new day(s), series now {after} days")
    if args.command in ("update", "build", "all"):
        pipeline.build()


if __name__ == "__main__":
    main()
