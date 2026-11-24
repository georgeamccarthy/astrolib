# astrolib

Ingest public astronomical catalogues into a local SQLite database.

## Exoplanets

```
uv run python -m astrolib.ingest.exoplanets
```

Copies the NASA Exoplanet Archive confirmed-planet table (`exo_planets`, from pscomppars) and the TESS Objects of Interest list (`exo_toi`) into `data/astrolib.db`, with all columns. The view `tess_planets` holds confirmed planets discovered by TESS.

## Gamma-ray bursts

```
uv run python -m astrolib.ingest.grb          # all sources, ~1 min
uv run python -m astrolib.ingest.grb fermigbrst swiftgrbba   # a subset
```

Downloads ten GRB catalogues from [HEASARC](https://heasarc.gsfc.nasa.gov/) via TAP into `data/astrolib.db`:

| table | source |
|---|---|
| `grb_fermigbrst` | Fermi GBM Burst Catalog (2008-present, updated continuously) |
| `grb_fermilgrb` | Fermi LAT Second GRB Catalog |
| `grb_swiftgrb` | Swift GRB Catalog (2004-2012) |
| `grb_swiftgrbba` | Swift GRBs by Burst Advocate (2004-present) |
| `grb_intspiagrb` | INTEGRAL SPI-ACS |
| `grb_hete2grb` | HETE-2 |
| `grb_saxgrbmgrb` | BeppoSAX GRBM |
| `grb_batsegrb` | CGRO/BATSE |
| `grb_ipngrb` | Interplanetary Network |
| `grb_grbcat` | Historical compilation, 1967-2001 |

Raw tables keep every HEASARC column. The `grb` view unions them with common columns
(`source, name, time_mjd, time_utc, ra_deg, dec_deg, error_radius_deg, t90_s, fluence_erg_cm2, redshift`),
NULL where a source lacks them. The `sources` table records row counts and ingest times.

The same burst appears once per instrument that saw it; the view does not cross-match.

```
sqlite3 data/astrolib.db "SELECT name, time_utc, redshift FROM grb WHERE redshift > 6 ORDER BY redshift DESC"
```
