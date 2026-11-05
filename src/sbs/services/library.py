"""Bibliothèque permanente : index SQLite + images copiées dans un dossier géré."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from sbs.domain.asset import Asset, Variant

DB_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
  uuid TEXT PRIMARY KEY,
  origin TEXT NOT NULL,
  source_id TEXT NOT NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  width INTEGER NOT NULL, height INTEGER NOT NULL,
  pivot_x INTEGER NOT NULL, pivot_y INTEGER NOT NULL,
  mode TEXT NOT NULL DEFAULT '',
  image_path TEXT NOT NULL,
  normal_path TEXT, emission_path TEXT,
  sha256 TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1,
  extra_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE (origin, source_id)
);
CREATE TABLE IF NOT EXISTS variants (
  asset_uuid TEXT NOT NULL REFERENCES assets(uuid) ON DELETE CASCADE,
  name TEXT NOT NULL,
  image_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  PRIMARY KEY (asset_uuid, name)
);
CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category);
"""


class LibraryError(Exception):
    pass


class Library:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.assets_dir = self.root / "assets"
        self.thumbs_dir = self.root / "thumbs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "library.db"
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > DB_VERSION:
                raise LibraryError(f"bibliothèque créée par une version plus récente ({version})")
            db.executescript(_SCHEMA)
            db.execute(f"PRAGMA user_version = {DB_VERSION}")

    @contextmanager
    def connect(self):
        """Une connexion par appel : sûr entre threads (import en arrière-plan)."""
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    # --- lecture --------------------------------------------------------
    def count(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM assets").fetchone()[0]

    def categories(self) -> list[str]:
        with self.connect() as db:
            return [r[0] for r in db.execute("SELECT DISTINCT category FROM assets ORDER BY category")]

    def has_source(self, origin: str, source_id: str) -> bool:
        with self.connect() as db:
            return db.execute(
                "SELECT 1 FROM assets WHERE origin=? AND source_id=?", (origin, source_id)
            ).fetchone() is not None

    def find_by_source(self, origin: str, source_id: str) -> Asset | None:
        with self.connect() as db:
            r = db.execute(
                "SELECT * FROM assets WHERE origin=? AND source_id=?", (origin, source_id)
            ).fetchone()
            return self._to_asset(db, r) if r else None

    def list_assets(self, search: str = "", category: str | None = None) -> list[Asset]:
        sql, args = "SELECT * FROM assets WHERE 1=1", []
        if category:
            sql += " AND category = ?"
            args.append(category)
        if search.strip():
            like = f"%{search.strip().lower()}%"
            sql += " AND (lower(name) LIKE ? OR lower(description) LIKE ?)"
            args += [like, like]
        sql += " ORDER BY category, name"
        with self.connect() as db:
            rows = db.execute(sql, args).fetchall()
            return [self._to_asset(db, r) for r in rows]

    def get(self, uuid: str) -> Asset | None:
        with self.connect() as db:
            r = db.execute("SELECT * FROM assets WHERE uuid=?", (uuid,)).fetchone()
            return self._to_asset(db, r) if r else None

    def _to_asset(self, db: sqlite3.Connection, r: sqlite3.Row) -> Asset:
        variants = tuple(
            Variant(v["name"], v["image_path"], v["sha256"])
            for v in db.execute(
                "SELECT * FROM variants WHERE asset_uuid=? ORDER BY name", (r["uuid"],)
            )
        )
        return Asset(
            uuid=r["uuid"], source_id=r["source_id"], name=r["name"], category=r["category"],
            description=r["description"], width=r["width"], height=r["height"],
            pivot_x=r["pivot_x"], pivot_y=r["pivot_y"], mode=r["mode"],
            image_path=r["image_path"], normal_path=r["normal_path"],
            emission_path=r["emission_path"], sha256=r["sha256"], revision=r["revision"],
            variants=variants, extra=json.loads(r["extra_json"]), origin=r["origin"],
        )

    def abs_path(self, relative: str) -> Path:
        return self.root / relative

    def thumbnail_path(self, uuid: str) -> Path:
        return self.thumbs_dir / f"{uuid}.png"

    # --- écriture (utilisée par les importeurs) -------------------------
    def insert_asset(self, db: sqlite3.Connection, origin: str, a: Asset) -> None:
        db.execute(
            "INSERT INTO assets (uuid, origin, source_id, name, category, description, width, height,"
            " pivot_x, pivot_y, mode, image_path, normal_path, emission_path, sha256, revision,"
            " extra_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (a.uuid, origin, a.source_id, a.name, a.category, a.description, a.width, a.height,
             a.pivot_x, a.pivot_y, a.mode, a.image_path, a.normal_path, a.emission_path,
             a.sha256, a.revision, json.dumps(a.extra, ensure_ascii=False)),
        )
        for v in a.variants:
            db.execute(
                "INSERT INTO variants (asset_uuid, name, image_path, sha256) VALUES (?,?,?,?)",
                (a.uuid, v.name, v.image_path, v.sha256),
            )
