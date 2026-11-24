"""Ingest gamma-ray burst catalogues from HEASARC into SQLite.

    uv run python -m astrolib.ingest.grb [--db data/astrolib.db] [table ...]

Each HEASARC table is copied whole into a raw table named grb_<heasarc name>.
A view `grb` then unions them with common columns:
    source, name, time_mjd, time_utc, ra_deg, dec_deg, error_radius_deg,
    t90_s, fluence_erg_cm2, redshift
Columns a source doesn't have are NULL. Re-running replaces the tables.
"""
import argparse
import os
import sqlite3

import numpy as np
import pyvo

TAP_URL = "https://heasarc.gsfc.nasa.gov/xamin/vo/tap"

# HEASARC table -> description. Order is roughly modern to historical.
SOURCES = {
    "fermigbrst": "Fermi GBM Burst Catalog",
    "fermilgrb": "Fermi LAT Second GRB Catalog",
    "swiftgrb": "Swift GRB Catalog",
    "swiftgrbba": "Swift GRB compilation by Burst Advocate",
    "intspiagrb": "INTEGRAL SPI-ACS GRB Catalog",
    "hete2grb": "HETE-2 GRBs",
    "saxgrbmgrb": "BeppoSAX GRBM Catalog",
    "batsegrb": "CGRO/BATSE GRB Catalog",
    "ipngrb": "Interplanetary Network GRBs",
    "grbcat": "Catalog of GRBs (historical compilation, 1967-2001)",
}

# Unified column -> candidate source column names, first match wins.
UNIFIED = {
    "name": ["name", "gcn_name", "event_id"],
    "time_mjd": ["time", "trigger_time"],  # ISO text is converted to MJD in the view
    "ra_deg": ["ra"],
    "dec_deg": ["dec"],
    "error_radius_deg": ["error_radius", "bat_err_radius", "xrt_pos_err"],
    "t90_s": ["t90", "bat_t90", "duration"],
    "fluence_erg_cm2": ["fluence", "bat_fluence", "gbm_cat_fluence"],
    "redshift": ["redshift", "bat_redshift"],
}


def fetch(service, table):
    t = service.search(f"SELECT * FROM {table}", maxrec=1_000_000).to_table()
    keep = [c for c in t.colnames if not c.startswith("__")]
    return t[keep]


def to_sql_value(v):
    if np.ma.is_masked(v):
        return None
    if isinstance(v, (bytes, np.bytes_)):
        return v.decode(errors="replace").strip() or None
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, str):
        return v.strip() or None
    return v


def sql_type(col):
    k = col.dtype.kind
    return "INTEGER" if k in "iub" else "REAL" if k == "f" else "TEXT"


def store(db, table, t):
    name = f"grb_{table}"
    cols = ", ".join(f'"{c}" {sql_type(t[c])}' for c in t.colnames)
    db.execute(f'DROP TABLE IF EXISTS "{name}"')
    db.execute(f'CREATE TABLE "{name}" ({cols})')
    rows = ([to_sql_value(r[c]) for c in t.colnames] for r in t)
    db.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" * len(t.colnames))})', rows)


def build_view(db):
    db.execute("CREATE TABLE IF NOT EXISTS sources (table_name TEXT PRIMARY KEY, description TEXT, origin TEXT, rows INTEGER, ingested_utc TEXT)")
    selects = []
    for table in SOURCES:
        name = f"grb_{table}"
        have = {r[1] for r in db.execute(f'PRAGMA table_info("{name}")')}
        if not have:
            continue
        parts = [f"'{table}' AS source"]
        for out, cands in UNIFIED.items():
            src = next((c for c in cands if c in have), None)
            if not src:
                parts.append(f"NULL AS {out}")
            elif out == "time_mjd":
                parts.append(f"""CASE WHEN typeof("{src}") = 'text' THEN julianday("{src}") - 2400000.5 ELSE "{src}" END AS {out}""")
            else:
                parts.append(f'"{src}" AS {out}')
        selects.append(f'SELECT {", ".join(parts)} FROM "{name}"')
    db.execute("DROP VIEW IF EXISTS grb")
    if not selects:
        return
    union = "\nUNION ALL\n".join(selects)
    db.execute(f"""CREATE VIEW grb AS
        SELECT source, name, time_mjd,
               datetime((time_mjd - 40587) * 86400, 'unixepoch') AS time_utc,
               ra_deg, dec_deg, error_radius_deg, t90_s, fluence_erg_cm2, redshift
        FROM ({union})""")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="data/astrolib.db")
    ap.add_argument("tables", nargs="*", help=f"subset of: {' '.join(SOURCES)}")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)
    db = sqlite3.connect(args.db)
    service = pyvo.dal.TAPService(TAP_URL)
    build_view(db)
    for table in args.tables or SOURCES:
        t = fetch(service, table)
        store(db, table, t)
        db.execute("INSERT OR REPLACE INTO sources VALUES (?, ?, ?, ?, datetime('now'))",
                   (f"grb_{table}", SOURCES.get(table, table), f"{TAP_URL} table {table}", len(t)))
        db.commit()
        print(f"grb_{table}: {len(t)} rows")
    build_view(db)
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM grb").fetchone()[0]
    print(f"view grb: {n} rows")


if __name__ == "__main__":
    main()
