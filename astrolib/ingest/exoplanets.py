"""Ingest exoplanet tables from the NASA Exoplanet Archive into SQLite.

    uv run python -m astrolib.ingest.exoplanets [--db data/astrolib.db]

Tables (all columns kept, see https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html):
    exo_planets  pscomppars: one row per confirmed planet, best-available parameters
    exo_toi      toi: every TESS Object of Interest, with TFOPWG disposition
                 (PC candidate, APC ambiguous candidate, CP/KP confirmed/known planet,
                  FP false positive, FA false alarm)
A view `tess_planets` selects confirmed planets whose discovery facility is TESS.
"""
import argparse
import csv
import io
import os
import sqlite3
import urllib.parse
import urllib.request

TAP = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
TABLES = {"exo_planets": "pscomppars", "exo_toi": "toi"}


def fetch_csv(table):
    url = TAP + "?" + urllib.parse.urlencode({"query": f"select * from {table}", "format": "csv"})
    with urllib.request.urlopen(url, timeout=600) as r:
        return list(csv.reader(io.TextIOWrapper(r, encoding="utf-8")))


def parse(v):
    if v == "":
        return None
    for f in (int, float):
        try:
            return f(v)
        except ValueError:
            pass
    return v


def store(db, name, rows):
    header, body = rows[0], rows[1:]
    db.execute(f'DROP TABLE IF EXISTS "{name}"')
    db.execute(f'CREATE TABLE "{name}" ({", ".join(f"{chr(34)}{c}{chr(34)}" for c in header)})')
    db.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" * len(header))})',
                   ([parse(v) for v in r] for r in body))
    return len(body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="data/astrolib.db")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)
    db = sqlite3.connect(args.db)
    db.execute("CREATE TABLE IF NOT EXISTS sources (table_name TEXT PRIMARY KEY, description TEXT, origin TEXT, rows INTEGER, ingested_utc TEXT)")
    for name, table in TABLES.items():
        n = store(db, name, fetch_csv(table))
        db.execute("INSERT OR REPLACE INTO sources VALUES (?, ?, ?, ?, datetime('now'))",
                   (name, f"NASA Exoplanet Archive {table}", f"{TAP} table {table}", n))
        db.commit()
        print(f"{name}: {n} rows")
    db.execute("DROP VIEW IF EXISTS tess_planets")
    db.execute("""CREATE VIEW tess_planets AS SELECT * FROM exo_planets
                  WHERE disc_facility = 'Transiting Exoplanet Survey Satellite (TESS)'""")
    db.commit()
    print("view tess_planets:", db.execute("SELECT COUNT(*) FROM tess_planets").fetchone()[0], "rows")


if __name__ == "__main__":
    main()
