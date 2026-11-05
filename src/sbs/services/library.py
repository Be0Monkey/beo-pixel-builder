"""Bibliothèque permanente : index SQLite + images copiées dans un dossier géré."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import shutil
import uuid as uuidlib
from collections.abc import Callable

from sbs.domain.asset import Anchor, Asset, Variant

DB_VERSION = 3
MAX_TAGS = 20
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
  favorite INTEGER NOT NULL DEFAULT 0,
  tags_json TEXT NOT NULL DEFAULT '[]',
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


def parse_tags(text: str) -> tuple[str, ...]:
    try:
        return tuple(str(t) for t in json.loads(text or "[]") if str(t).strip())
    except (ValueError, TypeError):
        return ()


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
            for col, ddl in (("anchors_json", "TEXT NOT NULL DEFAULT '[]'"),  # migrations 1 -> 2 -> 3
                             ("favorite", "INTEGER NOT NULL DEFAULT 0"),
                             ("tags_json", "TEXT NOT NULL DEFAULT '[]'")):
                if col not in cols:
                    db.execute(f"ALTER TABLE assets ADD COLUMN {col} {ddl}")
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

    def list_assets(self, search: str = "", category: str | None = None,
                    favorites_only: bool = False, tag: str | None = None) -> list[Asset]:
        sql, args = "SELECT * FROM assets WHERE 1=1", []
        if category:
            sql += " AND category = ?"
            args.append(category)
        if favorites_only:
            sql += " AND favorite = 1"
        if tag:
            sql += " AND lower(tags_json) LIKE ?"
            args.append("%" + json.dumps(tag.lower(), ensure_ascii=False) + "%")
        if search.strip():
            like = f"%{search.strip().lower()}%"
            sql += " AND (lower(name) LIKE ? OR lower(description) LIKE ? OR lower(tags_json) LIKE ?)"
            args += [like, like, like]
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
            anchors=parse_anchors(r["anchors_json"]), favorite=bool(r["favorite"]),
            tags=parse_tags(r["tags_json"]),
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
            " extra_json, anchors_json, favorite, tags_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (a.uuid, origin, a.source_id, a.name, a.category, a.description, a.width, a.height,
             a.pivot_x, a.pivot_y, a.mode, a.image_path, a.normal_path, a.emission_path,
             a.sha256, a.revision, json.dumps(a.extra, ensure_ascii=False),
             dump_anchors(a.anchors), int(a.favorite), json.dumps(list(a.tags), ensure_ascii=False)),
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

    # --- organisation : favori, mots-clés, catégorie ---------------------------------------
    def _update(self, uuid: str, column: str, value) -> None:
        with self.connect() as db:
            cur = db.execute(f"UPDATE assets SET {column}=? WHERE uuid=?", (value, uuid))  # noqa: S608 (colonne fixe)
            if cur.rowcount == 0:
                raise LibraryError("ressource inconnue")

    def set_favorite(self, uuid: str, value: bool) -> None:
        self._update(uuid, "favorite", int(bool(value)))

    @staticmethod
    def clean_tags(tags) -> list[str]:
        out: list[str] = []
        for t in tags:
            t = " ".join(str(t).split())
            if t and t.lower() not in {o.lower() for o in out}:
                out.append(t[:40])
        if len(out) > MAX_TAGS:
            raise LibraryError(f"{MAX_TAGS} mots-clés au maximum")
        return out

    def set_tags(self, uuid: str, tags) -> list[str]:
        clean = self.clean_tags(tags)
        self._update(uuid, "tags_json", json.dumps(clean, ensure_ascii=False))
        return clean

    def set_category(self, uuid: str, category: str) -> str:
        category = " ".join(str(category).split())[:60]
        if not category:
            raise LibraryError("la catégorie ne peut pas être vide")
        self._update(uuid, "category", category)
        return category

    def all_tags(self) -> list[str]:
        seen: dict[str, str] = {}
        with self.connect() as db:
            for (text,) in db.execute("SELECT tags_json FROM assets WHERE tags_json != '[]'"):
                for t in parse_tags(text):
                    seen.setdefault(t.lower(), t)
        return sorted(seen.values(), key=str.lower)

    # --- images : lecture, remplacement (atelier Pixel Art), création --------------------------
    def image_relpath(self, asset: Asset, variant: str | None) -> str:
        return asset.image_for(variant)

    def image_bytes(self, uuid: str, variant: str | None = None) -> bytes:
        asset = self.get(uuid)
        if asset is None:
            raise LibraryError("ressource inconnue")
        try:
            return self.abs_path(asset.image_for(variant)).read_bytes()
        except OSError as exc:
            raise LibraryError(f"image illisible : {exc}") from exc

    @staticmethod
    def _check_png(png: bytes) -> tuple[int, int]:
        import io

        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(io.BytesIO(png)) as im:
                im.verify()
            with Image.open(io.BytesIO(png)) as im:
                if im.format != "PNG":
                    raise LibraryError("l'image doit être un PNG")
                return im.size
        except (UnidentifiedImageError, OSError, SyntaxError) as exc:
            raise LibraryError(f"PNG invalide : {exc}") from exc

    def replace_image(self, uuid: str, png: bytes, variant: str | None = None,
                      revision: int | None = None) -> Asset:
        """Remplace l'image d'une ressource (ou d'une de ses variantes) : toutes les instances liées la voient.
        La taille doit rester la même (le pivot et les ancrages dépendent d'elle)."""
        import hashlib
        asset = self.get(uuid)
        if asset is None:
            raise LibraryError("ressource inconnue")
        if variant is not None and not any(v.name == variant for v in asset.variants):
            raise LibraryError(f"variante inconnue : {variant}")
        size = self._check_png(png)
        if size != (asset.width, asset.height):
            raise LibraryError(f"taille différente ({size[0]}×{size[1]} au lieu de {asset.width}×{asset.height})")
        rel = asset.image_for(variant)
        target = self.abs_path(rel)
        tmp = target.with_name(target.name + ".tmp")
        try:
            tmp.write_bytes(png)
            import os
            os.replace(tmp, target)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise LibraryError(f"écriture impossible : {exc}") from exc
        sha = hashlib.sha256(png).hexdigest()
        rev = asset.revision + 1 if revision is None else revision
        with self.connect() as db:
            if variant is None:
                db.execute("UPDATE assets SET sha256=?, revision=? WHERE uuid=?", (sha, rev, uuid))
            else:
                db.execute("UPDATE variants SET sha256=? WHERE asset_uuid=? AND name=?", (sha, uuid, variant))
                db.execute("UPDATE assets SET revision=? WHERE uuid=?", (rev, uuid))
        if variant is None:
            from sbs.services.thumbnails import make_thumbnail
            try:
                make_thumbnail(target, self.thumbnail_path(uuid))
            except (OSError, ValueError):
                pass  # la miniature est un confort
        self._changed(uuid)
        return self.get(uuid)

    def create_asset(self, name: str, png: bytes, pivot: tuple[int, int], category: str = "divers") -> Asset:
        """Nouveau module « local » à partir d'un PNG (sprite créé dans l'atelier)."""
        import hashlib
        size = self._check_png(png)
        name = " ".join(str(name).split())[:80]
        if not name:
            raise LibraryError("le nom ne peut pas être vide")
        new = str(uuidlib.uuid4())
        rel = f"assets/{new}/sprite.png"
        probe = Asset(new, "", name, category, "", size[0], size[1], 0, 0, "", rel, None, None, "")
        self.check_geometry(probe, pivot, [])
        dst = self.abs_path(rel)
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(png)
            asset = Asset(new, f"local_{new[:8]}", name, " ".join(category.split()) or "divers", "Créé dans l'atelier",
                          size[0], size[1], pivot[0], pivot[1], "", rel, None, None,
                          hashlib.sha256(png).hexdigest(), origin="local")
            with self.connect() as db:
                self.insert_asset(db, "local", asset)
            from sbs.services.thumbnails import make_thumbnail
            self.thumbs_dir.mkdir(parents=True, exist_ok=True)
            try:
                make_thumbnail(dst, self.thumbnail_path(new))
            except (OSError, ValueError):
                pass
        except Exception:
            shutil.rmtree(dst.parent, ignore_errors=True)
            raise
        return self.get(new)

    def delete_asset(self, uuid: str) -> None:
        """Supprime une ressource jamais utilisée (nettoyage après un échec). Les projets ne sont pas touchés."""
        with self.connect() as db:
            db.execute("DELETE FROM assets WHERE uuid=?", (uuid,))
        shutil.rmtree(self.assets_dir / uuid, ignore_errors=True)
        self.thumbnail_path(uuid).unlink(missing_ok=True)
