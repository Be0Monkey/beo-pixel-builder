"""Export JSON structuré : positions, pivots, ordre de dessin, étages, calques, groupes, animations."""

import json

from sbs.exporters.model import ExportScene

FORMAT = "sbs-scene-export"
VERSION = 1


class JsonExporter:
    name = "json"
    label = "JSON structuré"

    def plan(self, scene: ExportScene, options: dict) -> dict:
        copy_textures = options.get("copy_textures", True)
        doc = {
            "format": FORMAT, "version": VERSION, "name": scene.name,
            "coordinates": "pixels ; x vers la droite, y vers le bas ; (x, y) = pivot de l'objet",
            "draw_order": "du fond vers le devant : étage, calque, z manuel, profondeur (y), insertion",
            "textures": [{"file": f"textures/{t.filename}" if copy_textures else None, "key": t.key,
                          "source_id": t.source_id, "variant": t.variant, "size": [t.width, t.height],
                          "pivot": list(t.pivot), "sha256": t.sha256}
                         for t in scene.textures.values()],
            "floors": [{
                "id": f.id, "name": f.name, "visible": f.visible, "locked": f.locked,
                "elevation_px": f.elevation_px,
                "layers": [{
                    "id": layer.id, "name": layer.name, "visible": layer.visible, "locked": layer.locked,
                    "items": [{
                        "id": i.id, "name": i.name, "draw_index": i.draw_index,
                        "texture": scene.textures[i.texture].filename, "position": [i.x, i.y],
                        "top_left": [i.x - scene.textures[i.texture].pivot[0],
                                     i.y - scene.textures[i.texture].pivot[1]],
                        "z_manual": i.z_manual, "group": i.group_id, "visible": i.visible,
                    } for i in layer.items],
                } for layer in f.layers],
            } for f in scene.floors],
            "groups": scene.groups, "animations": scene.animations, "warnings": scene.warnings,
        }
        files: dict = {f"{scene.name}.json": json.dumps(doc, indent=1, ensure_ascii=False).encode("utf-8")}
        if copy_textures:
            for t in scene.textures.values():
                files[f"textures/{t.filename}"] = t.source
        return files
