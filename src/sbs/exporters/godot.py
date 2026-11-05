"""Export vers une scène Godot 4 (.tscn texte) : un Node2D par étage, un par calque, un Sprite2D par objet.

L'ordre des nœuds EST l'ordre de dessin (aucun z_index n'est utilisé) : un seul ordre, comme dans l'appli.
Pixels nets : texture_filter = nearest sur la racine. Les PNG sont copiés tels quels (transparence intacte)."""

import re
from pathlib import Path

from sbs.exporters.model import _unique, safe_name

from sbs.exporters.model import ExportScene

NEAREST = 1  # CanvasItem.TEXTURE_FILTER_NEAREST


def _q(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_tscn(scene: ExportScene, res_prefix: str = "") -> str:
    prefix = res_prefix.strip("/\\ ")
    base = f"res://{prefix + '/' if prefix else ''}sprites/"
    ids = {key: f"{n + 1}_{Path(t.filename).stem[:20]}" for n, (key, t) in enumerate(scene.textures.items())}
    out = [f"[gd_scene load_steps={len(ids) + 1} format=3]", ""]
    for key, t in scene.textures.items():
        out.append(f'[ext_resource type="Texture2D" path={_q(base + t.filename)} id={_q(ids[key])}]')
    out += ["", f"[node name={_q(scene.name)} type=\"Node2D\"]", f"texture_filter = {NEAREST}",
            "metadata/sbs_export = true", ""]
    used_floor: set[str] = set()
    for f in scene.floors:
        fname = _unique(safe_name(f.name, "etage"), used_floor)
        out.append(f'[node name={_q(fname)} type="Node2D" parent="."]')
        if not f.visible:
            out.append("visible = false")
        if f.locked:
            out.append("metadata/_edit_lock_ = true")
        out.append(f"metadata/sbs_label = {_q(f.name)}")
        out.append("")
        used_layer: set[str] = set()
        for layer in f.layers:
            lname = _unique(safe_name(layer.name, "calque"), used_layer)
            out.append(f'[node name={_q(lname)} type="Node2D" parent={_q(fname)}]')
            if not layer.visible:
                out.append("visible = false")
            if layer.locked:
                out.append("metadata/_edit_lock_ = true")
            out.append(f"metadata/sbs_label = {_q(layer.name)}")
            out.append("")
            for it in layer.items:  # déjà dans l'ordre de dessin
                tex = scene.textures[it.texture]
                out.append(f'[node name={_q(it.name)} type="Sprite2D" parent={_q(fname + "/" + lname)}]')
                out.append(f"position = Vector2({it.x}, {it.y})")
                out.append(f'texture = ExtResource({_q(ids[it.texture])})')
                out.append("centered = false")
                out.append(f"offset = Vector2({-tex.pivot[0]}, {-tex.pivot[1]})")
                out.append(f"metadata/sbs_id = {_q(it.id)}")
                out.append(f"metadata/sbs_draw_index = {it.draw_index}")
                if it.z_manual:
                    out.append(f"metadata/sbs_z = {it.z_manual}")
                if it.group_id:
                    out.append(f"metadata/sbs_group = {_q(it.group_id)}")
                out.append("")
    return "\n".join(out).rstrip() + "\n"


def project_godot(name: str) -> str:
    return (
        "; Projet de test généré par Sprite Builder Studio\n"
        "config_version=5\n\n[application]\n\n"
        f"config/name={_q(name)}\n"
        f'run/main_scene="res://{name}.tscn"\n'
        'config/features=PackedStringArray("4.2")\n\n'
        "[rendering]\n\n"
        "renderer/rendering_method=\"gl_compatibility\"\n"
        "textures/canvas_textures/default_texture_filter=0\n"
    )


class Godot4Exporter:
    name = "godot4"
    label = "Scène Godot 4 (.tscn)"

    def plan(self, scene: ExportScene, options: dict) -> dict:
        prefix = str(options.get("res_prefix", "")).replace("\\", "/").strip("/ ")
        if prefix and (not re.fullmatch(r"[0-9A-Za-z_\-]+(/[0-9A-Za-z_\-]+)*", prefix)):
            raise ValueError("chemin Godot invalide (lettres, chiffres, _ et - ; séparateur « / »)")
        files: dict = {f"{scene.name}.tscn": build_tscn(scene, prefix).encode("utf-8")}
        for t in scene.textures.values():
            files[f"sprites/{t.filename}"] = t.source
        if options.get("create_project"):
            files["project.godot"] = project_godot(scene.name).encode("utf-8")
        return files
