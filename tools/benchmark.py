"""Mesures de performance : `python tools/benchmark.py [--sizes 1000 5000 20000] [--no-gui]`.

Mesure, pour N objets : construction du modèle, ordre de dessin, enregistrement/relecture,
création de la scène graphique, sélection + déplacement + annulation, rendu de la vue, export PNG,
et mémoire du processus. Les résultats sont à reporter dans docs/Performances.md.
"""

import argparse
import ctypes
import os
import random
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402

from sbs.domain.scene import Instance, SceneModel  # noqa: E402
from sbs.domain.ids import new_id  # noqa: E402
from sbs.services.exporter import export_png  # noqa: E402
from sbs.services.library import Library  # noqa: E402
from sbs.services.project_io import ProjectMeta, load_project, save_project  # noqa: E402


def rss_mb() -> float:
    """Mémoire utilisée par le processus (Mo). Windows : psapi ; sinon /proc."""
    try:
        if sys.platform == "win32":
            class PMC(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
            kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
            psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
            return pmc.WorkingSetSize / 1e6
        for line in open("/proc/self/status", encoding="utf-8"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1e3
    except Exception:  # noqa: BLE001
        pass
    return float("nan")


class Timer:
    def __init__(self):
        self.rows: dict[str, float] = {}

    def run(self, name, fn):
        t = time.perf_counter()
        out = fn()
        self.rows[name] = (time.perf_counter() - t) * 1000
        return out


def make_library(root: Path, n_assets: int = 24) -> Library:
    lib = Library(root / "lib")
    rnd = random.Random(1)
    for k in range(n_assets):
        w, h = rnd.choice([16, 24, 32, 48, 64]), rnd.choice([16, 32, 48, 96])
        im = Image.new("RGBA", (w, h), (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), 255))
        import io
        buf = io.BytesIO()
        im.save(buf, "PNG")
        lib.create_asset(f"b{k}", buf.getvalue(), (w // 2, h - 1))
    return lib


def build_instances(model: SceneModel, lib: Library, n: int) -> list[Instance]:
    rnd = random.Random(7)
    uuids = [a.uuid for a in lib.list_assets()]
    span = int((n ** 0.5) * 20)
    floor, layer = model.default_target()
    return [Instance(new_id(), rnd.choice(uuids), rnd.randrange(-span, span), rnd.randrange(-span, span),
                     0, None, floor, layer, None) for _ in range(n)]


def bench(n: int, gui: bool) -> dict:
    t = Timer()
    with tempfile.TemporaryDirectory(prefix="sbs_bench_") as tmp:
        tmp = Path(tmp)
        lib = make_library(tmp)
        model = SceneModel()
        insts = build_instances(model, lib, n)
        m0 = rss_mb()
        t.run("modèle : ajout de N objets", lambda: model.replace(insts, model.floors_copy()))
        t.run("ordre de dessin", lambda: model.draw_instances())
        meta, path = ProjectMeta(), tmp / "b.sbsproj"
        t.run("enregistrement", lambda: save_project(path, meta, model, lib))
        size_mb = path.stat().st_size / 1e6
        t.run("relecture", lambda: load_project(path, lib))
        t.run("export PNG (échelle 1)", lambda: export_png(tmp / "o.png", model.draw_instances(), lib))
        out = {"n": n, "fichier_Mo": round(size_mb, 2)}
        if gui:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication([])
            from sbs.canvas.scene import CanvasScene
            from sbs.canvas.view import CanvasView
            from sbs.commands.history import History
            hist = History(model)
            def build_scene():
                sc = CanvasScene(model, lib, hist)
                sc.rebuild()  # crée un élément graphique par objet
                return sc
            scene = t.run("scène graphique : création", build_scene)
            assert len(scene.items()) >= n, "la scène graphique est vide : mesure invalide"
            view = CanvasView(scene)
            view.resize(1280, 800)
            view.show()
            app.processEvents()
            t.run("vue : un rendu complet", lambda: view.grab())

            def sel_all():
                scene.select_ids([i.id for i in model.all()])
            t.run("sélectionner tout", sel_all)

            def move():
                scene.move_selected(3, 0)
                scene.commit_positions()
            t.run("déplacer tout (1 geste)", move)
            t.run("annuler", scene.undo)
            t.run("tout supprimer", scene.remove_selected)
            t.run("annuler la suppression", scene.undo)
            out["items_scene"] = len(scene.items())
            view.close()
            app.processEvents()
        out["mémoire_Mo"] = round(rss_mb() - m0, 1)
        out["ms"] = {k: round(v, 1) for k, v in t.rows.items()}
        return out


def soak(cycles: int = 300, n: int = 2000) -> None:
    """Longue session simulée : déplacer / annuler / rétablir / supprimer / annuler, `cycles` fois."""
    import gc

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from sbs.canvas.scene import CanvasScene
    from sbs.commands.history import History
    with tempfile.TemporaryDirectory(prefix="sbs_soak_") as tmp:
        lib = make_library(Path(tmp))
        model = SceneModel()
        model.replace(build_instances(model, lib, n), model.floors_copy())
        hist = History(model)
        scene = CanvasScene(model, lib, hist)
        scene.rebuild()
        scene.select_ids([i.id for i in model.all()])
        samples = []
        for c in range(cycles):
            scene.move_selected(1, 0)
            scene.undo()
            scene.redo()
            scene.undo()
            if c % 50 == 49:
                app.processEvents()
                gc.collect()
                samples.append(round(rss_mb(), 1))
        print(f"longue session ({cycles} cycles, {n} objets) : mémoire (Mo) tous les 50 cycles = {samples}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--soak", action="store_true")
    ap.add_argument("--sizes", type=int, nargs="+", default=[1000, 5000, 20000])
    ap.add_argument("--no-gui", action="store_true")
    a = ap.parse_args()
    if a.soak:
        soak()
        return 0
    results = [bench(n, not a.no_gui) for n in a.sizes]
    names = list(results[0]["ms"])
    print("| Mesure (ms) | " + " | ".join(f"{r['n']} objets" for r in results) + " |")
    print("|---|" + "---|" * len(results))
    for k in names:
        print(f"| {k} | " + " | ".join(f"{r['ms'].get(k, float('nan')):.0f}" for r in results) + " |")
    print("| fichier projet (Mo) | " + " | ".join(str(r["fichier_Mo"]) for r in results) + " |")
    print("| mémoire ajoutée (Mo) | " + " | ".join(str(r["mémoire_Mo"]) for r in results) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
