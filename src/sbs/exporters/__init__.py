"""Exporteurs isolés : chacun ne connaît que `ExportScene` (données neutres), jamais Qt ni la fenêtre.

Un exporteur qui échoue ne casse ni l'application ni les autres exporteurs : `run_export` renvoie un
rapport avec l'erreur. Les exporteurs n'écrivent que dans un dossier qu'ils possèdent (voir `base`)."""

from sbs.exporters.base import ExportReport, Exporter, run_export
from sbs.exporters.godot import Godot4Exporter
from sbs.exporters.jsonout import JsonExporter
from sbs.exporters.model import ExportScene, build_export_scene

EXPORTERS: dict[str, Exporter] = {"json": JsonExporter(), "godot4": Godot4Exporter()}

__all__ = ["EXPORTERS", "ExportReport", "ExportScene", "Exporter", "build_export_scene", "run_export"]
