# Development

## Commands

| Command | Does |
|---|---|
| `make install` | Create the environment from `uv.lock` |
| `make hooks` | Install the pre-commit hooks |
| `make fmt` | Format with ruff and apply the safe fixes |
| `make lint` | Check format and lint rules without changing files |
| `make test` | Run the tests with the coverage report |
| `make check` | `lint` then `test`, to run before committing |
| `make docs` | Preview this documentation on http://localhost:8001 |
| `make clean` | Remove caches |

## Conventions

- Code, documentation and commit messages in English.
- Comments and docstrings say **what the code does**; the reasons behind the choices live in this documentation.
- Ruff for formatting and linting, 88 columns, rules E, F, I, UP and B.
- Generated files under `data/` are left as the pipeline writes them; the pre-commit hooks skip that folder.

## Tests

The suite in `tests/` covers:

| File | Scope |
|---|---|
| `test_mhw.py` | Climatology, threshold and event rules on synthetic series |
| `test_whatif.py` | Scenarios and the share of the MPA in heatwave |
| `test_ingest.py` | Grid masking, in-situ QC and daily means on local files, REP/NRT join, Zarr append |
| `test_pipeline.py` | The whole build on a synthetic cube: every export, the STAC catalog validated against its schemas, consistency between tables |
| `test_api.py` | Every route on the committed exports, including on-demand scenarios against the precomputed ones and in-process calls against HTTP |
| `test_dashboard.py` | Every page rendered headless with `AppTest` |

No test needs network access or Copernicus credentials.

## Continuous integration

On every push and pull request, GitHub Actions installs the locked environment, runs `make lint` and `make test`, rebuilds the exports from the committed processed series and fails if they differ from the commit, then builds this documentation with `--strict`. On `main`, the documentation is published to GitHub Pages.

## Updating the data

1. `make update`, or `make data` for a full download.
2. Look at the new in-situ days (Validation page). If a sensor misbehaves, add the period and the reason to `config.SOCIB_EXCLUDE` and run `make data` again.
3. `make check`, then commit `data/processed` and `data/exports` with the code.
