"""Bibliothèque permanente : index SQLite + images copiées dans un dossier géré."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import shutil
import uuid as uuidlib
from collections.abc import Callable

from sbs.domain.asset import Anchor, Asset, Variant

DB_VERSION = 2
MAX_ANCHORS = 32

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
  anchors_json TEXT NOT NULL DEFAULT '[]',
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


def dump_anchors(anchors) -> str:
    return json.dumps([[a.name, a.x, a.y] for a in anchors], ensure_ascii=False)


def parse_anchors(text: str) -> tuple[Anchor, ...]:
    try:
        return tuple(Anchor(str(n), int(x), int(y)) for n, x, y in json.loads(text or "[]"))
    except (ValueError, TypeError):
        return ()  # donnée abîmée : on ignore les ancrages plutôt que de planter


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
            cols = {r[1] for r in db.execute("PRAGMA table_info(assets)")}
            if "anchors_json" not in cols:  # migration 1 -> 2
                db.execute("ALTER TABLE assets ADD COLUMN anchors_json TEXT NOT NULL DEFAULT '[]'")
            db.execute(f"PRAGMA user_version = {DB_VERSION}")
        self._listeners: list[Callable[[str], None]] = []

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
            anchors=parse_anchors(r["anchors_json"]),
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
            " extra_json, anchors_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (a.uuid, origin, a.source_id, a.name, a.category, a.description, a.width, a.height,
             a.pivot_x, a.pivot_y, a.mode, a.image_path, a.normal_path, a.emission_path,
             a.sha256, a.revision, json.dumps(a.extra, ensure_ascii=False),
             dump_anchors(a.anchors)),
        )
        for v in a.variants:
            db.execute(
                "INSERT INTO variants (asset_uuid, name, image_path, sha256) VALUES (?,?,?,?)",
                (a.uuid, v.name, v.image_path, v.sha256),
            )

    # --- modification d'une ressource (source commune) ---------------------------------
    def add_listener(self, fn: Callable[[str], None]) -> None:
        """fn(uuid) est appelé après chaque modification d'une ressource."""
        self._listeners.append(fn)

    def _changed(self, uuid: str) -> None:
        for fn in list(self._listeners):
            fn(uuid)

    @staticmethod
    def check_geometry(asset: Asset, pivot: tuple[int, int], anchors) -> tuple[Anchor, ...]:
        """Valide pivot et ancrages (entiers, dans l'image, noms uniques et non vides)."""
        for v in pivot:
            if isinstance(v, bool) or not isinstance(v, int):
                raise LibraryError("le pivot doit être formé de nombres entiers")
        if not (0 <= pivot[0] <= asset.width and 0 <= pivot[1] <= asset.height):
            raise LibraryError(f"le pivot doit rester dans l'image ({asset.width}×{asset.height})")
        out, names = [], set()
        if len(anchors) > MAX_ANCHORS:
            raise LibraryError(f"{MAX_ANCHORS} ancrages au maximum")
        for a in anchors:
            name = str(a.name).strip()
            if not name or name in names:
                raise LibraryError("chaque ancrage a un nom unique et non vide")
            if not (0 <= a.x <= asset.width and 0 <= a.y <= asset.height):
                raise LibraryError(f"l'ancrage « {name} » est hors de l'image")
            names.add(name)
            out.append(Anchor(name, int(a.x), int(a.y)))
        return tuple(out)

    def update_geometry(self, uuid: str, pivot: tuple[int, int], anchors, revision: int | None = None) -> Asset:
        """Change pivot et ancrages de la SOURCE : toutes les instances liées suivent.
        `revision` n'est fourni que par l'annulation (retour exact à l'état précédent)."""
        asset = self.get(uuid)
        if asset is None:
            raise LibraryError("ressource inconnue")
        anchors = self.check_geometry(asset, pivot, anchors)
        rev = asset.revision + 1 if revision is None else revision
        with self.connect() as db:
            db.execute("UPDATE assets SET pivot_x=?, pivot_y=?, anchors_json=?, revision=? WHERE uuid=?",
                       (pivot[0], pivot[1], dump_anchors(anchors), rev, uuid))
        self._changed(uuid)
        return self.get(uuid)

    def clone_asset(self, uuid: str) -> Asset:
        """Copie indépendante d'une ressource (images comprises) : sert à « modifier cette instance seulement »."""
        src = self.get(uuid)
        if src is None:
            raise LibraryError("ressource inconnue")
        new = str(uuidlib.uuid4())
        old_dir, new_dir = self.assets_dir / src.uuid, self.assets_dir / new
        try:
            shutil.copytree(old_dir, new_dir)
        except OSError as exc:
            shutil.rmtree(new_dir, ignore_errors=True)
            raise LibraryError(f"copie impossible : {exc}") from exc

        def move(rel: str | None) -> str | None:
            return rel.replace(f"assets/{src.uuid}/", f"assets/{new}/") if rel else rel

        from dataclasses import replace
        clone = replace(
            src, uuid=new, source_id=f"{src.source_id}__copie_{new[:8]}", name=f"{src.name} (copie)",
            image_path=move(src.image_path), normal_path=move(src.normal_path),
            emission_path=move(src.emission_path), revision=1, origin="local",
            variants=tuple(Variant(v.name, move(v.image_path), v.sha256) for v in src.variants),
            extra={**src.extra, "copie_de": src.uuid},
        )
        try:
            with self.connect() as db:
                self.insert_asset(db, "local", clone)
            thumb = self.thumbnail_path(src.uuid)
            if thumb.is_file():
                self.thumbs_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(thumb, self.thumbnail_path(new))
        except Exception:
            shutil.rmtree(new_dir, ignore_errors=True)
            raise
        return self.get(new)
