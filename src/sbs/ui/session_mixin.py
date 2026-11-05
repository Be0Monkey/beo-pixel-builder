"""Robustesse de la session : sauvegardes versionnées, récupération après arrêt brutal, options,
raccourcis personnalisables et espaces de travail (dispositions de panneaux nommées).

Mélangé à `MainWindow` ; ne dépend que de ses attributs (prefs, library, meta, path, history…).
"""

import base64
import dataclasses
from pathlib import Path

from PySide6.QtCore import QByteArray, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox

from sbs.domain.ids import new_id
from sbs.services.backups import DEFAULT_KEEP, MAX_KEEP, BackupStore, RecoveryStore
from sbs.services.project_io import ProjectError, load_project, serialize_project

DEFAULT_AUTOSAVE_MINUTES = 2
MAX_WORKSPACES = 20


def _clean(text: str) -> str:
    return text.replace("&", "").strip()


class SessionMixin:
    # ------------------------------------------------------------------ initialisation
    def _init_session(self) -> None:
        self.data_dir = Path(self.prefs.path).parent
        self.backups = BackupStore(self.data_dir / "backups", self._pref_int("backup.keep", DEFAULT_KEEP, 1, MAX_KEEP))
        self.recovery = RecoveryStore(self.data_dir / "recovery")
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self.autosave_now)
        self.apply_autosave_settings()

    def _pref_int(self, key: str, default: int, lo: int, hi: int) -> int:
        v = self.prefs.get(key, default)
        return v if isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi else default

    def apply_autosave_settings(self) -> None:
        minutes = self._pref_int("autosave.minutes", DEFAULT_AUTOSAVE_MINUTES, 0, 120)
        self._autosave_timer.stop()
        if minutes > 0:
            self._autosave_timer.start(minutes * 60_000)

    # ------------------------------------------------------------------ sauvegarde automatique
    def autosave_now(self) -> bool:
        """Copie de secours du travail non enregistré. Ne lève jamais : un échec est seulement signalé."""
        if not self.dirty:
            return False
        try:
            meta = dataclasses.replace(self.meta)  # copie : la sérialisation modifie `meta`
            text = serialize_project(meta, self.scene_model, self.library)
            name = self.path.stem if self.path else self.meta.name
            self.recovery.write(self.meta.id, text, name, self.path)
            return True
        except (OSError, ValueError) as exc:
            self.statusBar().showMessage(f"Sauvegarde automatique impossible : {exc}", 6000)
            return False

    def _after_saved(self, path: Path) -> None:
        """Après un enregistrement réussi : la copie de secours est inutile, on range une version."""
        self.recovery.clear(self.meta.id)
        self.backups.snapshot(path, self.meta.id)

    # ------------------------------------------------------------------ récupération
    def _ask_recovery(self, entry) -> str:
        """'recover' | 'later' | 'delete'."""
        box = QMessageBox(self)
        box.setWindowTitle("Travail non enregistré retrouvé")
        origin = f"\nProjet d'origine : {entry.origin_path}" if entry.origin_path else ""
        box.setText(f"L'application s'est arrêtée sans enregistrer « {entry.name} » "
                    f"(dernière copie automatique : {entry.saved_at} UTC).{origin}\n\nVeux-tu le récupérer ?")
        recover = box.addButton("Récupérer", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Plus tard", QMessageBox.ButtonRole.RejectRole)
        delete = box.addButton("Supprimer cette copie", QMessageBox.ButtonRole.DestructiveRole)
        box.exec()
        clicked = box.clickedButton()
        return "recover" if clicked is recover else "delete" if clicked is delete else "later"

    def offer_recovery(self) -> bool:
        """À appeler au démarrage. True si un travail a été rouvert."""
        if self.dirty:
            return False
        entries = [e for e in self.recovery.pending() if e.project_id != self.meta.id]
        if not entries:
            return False
        entry = entries[0]
        choice = self._ask_recovery(entry)
        if choice == "delete":
            self.recovery.clear(entry.project_id)
            return False
        if choice != "recover":
            return False
        ok = self.open_recovery(entry.file, Path(entry.origin_path) if entry.origin_path else None)
        if not ok:  # copie abîmée : on la met de côté pour ne pas la reproposer à chaque démarrage
            self._quarantine(entry.file)
            return False
        if len(entries) > 1:
            self.statusBar().showMessage(
                f"{len(entries) - 1} autre(s) récupération(s) disponible(s) : Fichier > Versions et récupération…", 8000)
        return True

    def _quarantine(self, file: Path) -> None:
        try:
            file.replace(file.with_name(file.name + ".abimee"))
            info = file.with_name(file.stem + ".info.json")
            info.unlink(missing_ok=True)
        except OSError:
            pass

    def open_recovery(self, file: Path, origin: Path | None) -> bool:
        """Rouvre une copie automatique comme travail non enregistré (le fichier d'origine n'est pas touché
        tant que tu n'enregistres pas)."""
        try:
            result = load_project(file, self.library)
        except ProjectError as exc:
            QMessageBox.critical(self, "Récupération impossible", f"{exc}\n\nLa copie a été mise de côté.")
            return False
        self._apply(result.meta, result.instances, origin, result.floors, result.groups, result.animations)
        self.dirty = True
        self.statusBar().showMessage("Travail récupéré : enregistre-le pour le conserver.", 8000)
        return True

    def open_version(self, file: Path, label: str = "") -> bool:
        """Ouvre une ancienne version comme copie non enregistrée (nouveau projet, nouvel identifiant)."""
        if not self._confirm_discard():
            return False
        try:
            result = load_project(file, self.library)
        except ProjectError as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc))
            return False
        meta = result.meta
        meta.id, meta.name = new_id(), f"{meta.name} (version {label})".strip()
        self._apply(meta, result.instances, None, result.floors, result.groups, result.animations)
        self.dirty = True
        return True

    def open_versions_dialog(self) -> None:
        from sbs.ui.versions_dialog import VersionsDialog
        dlg = VersionsDialog(self.backups.versions(self.meta.id), self.recovery.pending(), self)
        if dlg.exec() and (choice := dlg.choice()):
            kind, obj = choice
            if kind == "version":
                self.open_version(obj.path, obj.created)
            elif self._confirm_discard():
                origin = Path(obj.origin_path) if obj.origin_path else None
                self.open_recovery(obj.file, origin)

    # ------------------------------------------------------------------ options et raccourcis
    def _collect_actions(self) -> None:
        """Repère toutes les actions de menu (identifiant stable) et mémorise leurs raccourcis par défaut."""
        self.shortcut_actions: dict[str, QAction] = {}
        self.default_shortcuts: dict[str, list[str]] = {}
        self.shortcut_labels: dict[str, str] = {}

        def walk(menu: QMenu, prefix: str) -> None:
            for act in menu.actions():
                if act.isSeparator():
                    continue
                if act.menu() is not None:
                    walk(act.menu(), f"{prefix}/{_clean(act.text())}")
                    continue
                sid = act.objectName() or f"{prefix}/{_clean(act.text())}"
                if sid in self.shortcut_actions:
                    continue
                self.shortcut_actions[sid] = act
                self.default_shortcuts[sid] = [s.toString() for s in act.shortcuts()]
                self.shortcut_labels[sid] = f"{prefix.split('/')[0]} › {_clean(act.text()).split(' : ')[0]}"
        for top in self.menuBar().actions():
            if top.menu() is not None:
                walk(top.menu(), _clean(top.text()))

    def shortcut_overrides(self) -> dict[str, str]:
        raw = self.prefs.get("shortcuts", {})
        return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(raw, dict) else {}

    def effective_shortcuts(self, overrides: dict[str, str] | None = None) -> dict[str, list[str]]:
        ov = self.shortcut_overrides() if overrides is None else overrides
        out = {}
        for sid in self.shortcut_actions:
            if sid in ov:
                out[sid] = [ov[sid]] if ov[sid] else []
            else:
                out[sid] = list(self.default_shortcuts[sid])
        return out

    def apply_shortcuts(self) -> None:
        for sid, seqs in self.effective_shortcuts().items():
            self.shortcut_actions[sid].setShortcuts([QKeySequence(s) for s in seqs])

    def check_shortcut_conflicts(self, effective: dict[str, list[str]]) -> None:
        owners: dict[str, str] = {}
        for sid, seqs in effective.items():
            for s in seqs:
                key = QKeySequence(s).toString()
                if not key:
                    continue
                if key in owners and owners[key] != sid:
                    raise ValueError(f"Le raccourci {key} est utilisé par « {self.shortcut_labels[owners[key]]} » "
                                     f"et par « {self.shortcut_labels[sid]} ».")
                owners[key] = sid

    def apply_options(self, autosave_minutes: int, backup_keep: int, shortcuts: dict[str, str]) -> None:
        """Valide puis enregistre les options. Lève ValueError (message clair) sans rien changer."""
        if not 0 <= autosave_minutes <= 120:
            raise ValueError("La sauvegarde automatique doit être entre 0 (désactivée) et 120 minutes.")
        if not 1 <= backup_keep <= MAX_KEEP:
            raise ValueError(f"Le nombre de versions doit être entre 1 et {MAX_KEEP}.")
        overrides: dict[str, str] = {}
        for sid, seq in shortcuts.items():
            if sid not in self.shortcut_actions:
                continue  # identifiant inconnu : ignoré
            seq = QKeySequence(seq).toString()
            default = self.default_shortcuts[sid]
            if seq == (default[0] if default else "") or (len(default) > 1 and seq in default):
                continue  # inchangé : on garde les valeurs par défaut (y compris les doubles)
            overrides[sid] = seq
        self.check_shortcut_conflicts(self.effective_shortcuts(overrides))
        self.prefs.set("autosave.minutes", autosave_minutes)
        self.prefs.set("backup.keep", backup_keep)
        self.prefs.set("shortcuts", overrides)
        self.backups.keep = backup_keep
        self.apply_autosave_settings()
        self.apply_shortcuts()
        try:
            self.prefs.save()
        except OSError as exc:
            QMessageBox.warning(self, "Options", f"Options appliquées mais non enregistrées : {exc}")

    def open_options(self, start_tab: int = 0) -> None:
        from sbs.ui.options_dialog import OptionsDialog
        eff = self.effective_shortcuts()
        table = {sid: (self.shortcut_labels[sid], self.default_shortcuts[sid], eff[sid][0] if eff[sid] else "")
                 for sid in self.shortcut_actions}
        dlg = OptionsDialog(self._pref_int("autosave.minutes", DEFAULT_AUTOSAVE_MINUTES, 0, 120),
                            self.backups.keep, table, self, start_tab)
        if dlg.exec():
            try:
                self.apply_options(*dlg.values())
            except ValueError as exc:
                QMessageBox.warning(self, "Options", str(exc))

    # ------------------------------------------------------------------ espaces de travail
    def workspace_names(self) -> list[str]:
        raw = self.prefs.get("workspaces", {})
        return sorted(raw) if isinstance(raw, dict) else []

    def save_workspace(self, name: str) -> str:
        name = " ".join(str(name).split())
        if not name or len(name) > 40:
            raise ValueError("Le nom d'un espace de travail doit faire entre 1 et 40 caractères.")
        raw = self.prefs.get("workspaces", {})
        spaces = dict(raw) if isinstance(raw, dict) else {}
        if name not in spaces and len(spaces) >= MAX_WORKSPACES:
            raise ValueError(f"Maximum {MAX_WORKSPACES} espaces de travail : supprime-en un d'abord.")
        spaces[name] = base64.b64encode(bytes(self.saveState())).decode("ascii")
        self.prefs.set("workspaces", spaces)
        self.prefs.save()
        return name

    def load_workspace(self, name: str) -> bool:
        raw = self.prefs.get("workspaces", {})
        data = raw.get(name) if isinstance(raw, dict) else None
        if not isinstance(data, str):
            return False
        try:
            ok = self.restoreState(QByteArray(base64.b64decode(data)))
        except (ValueError, TypeError):
            ok = False
        if not ok:
            self.reset_layout()  # jamais de panneau perdu
            return False
        return True

    def delete_workspace(self, name: str) -> bool:
        raw = self.prefs.get("workspaces", {})
        if not isinstance(raw, dict) or name not in raw:
            return False
        spaces = {k: v for k, v in raw.items() if k != name}
        self.prefs.set("workspaces", spaces)
        self.prefs.save()
        return True

    def _fill_workspace_menu(self) -> None:
        m = self.workspace_menu
        m.clear()
        m.addAction("Disposition par défaut", self.reset_layout)
        m.addAction("Enregistrer la disposition actuelle…", self._ask_save_workspace)
        names = self.workspace_names()
        if names:
            m.addSeparator()
            for n in names:
                m.addAction(n, lambda _=False, n=n: self.load_workspace(n))
            sub = m.addMenu("Supprimer")
            for n in names:
                sub.addAction(n, lambda _=False, n=n: self.delete_workspace(n))

    def _ask_save_workspace(self) -> None:
        name, ok = QInputDialog.getText(self, "Espace de travail", "Nom de cette disposition :")
        if ok:
            try:
                self.save_workspace(name)
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "Espace de travail", str(exc))
