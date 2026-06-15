"""Render a microscopy-inspired human preimplantation embryo hero loop.

Run with Blender:
blender --background --python scripts/render_embryo_hero.py -- --output-dir images
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import bpy
from mathutils import Vector


FRAME_START = 1
FRAME_END = 144
FPS = 24


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="images")
    parser.add_argument("--frames-dir", default="")
    argv = []
    if "--" in __import__("sys").argv:
        argv = __import__("sys").argv[__import__("sys").argv.index("--") + 1 :]
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def set_input(node, names, value) -> None:
    for name in names:
        if name in node.inputs:
            node.inputs[name].default_value = value
            return


def make_material(name: str, color, alpha: float, roughness: float = 0.72):
    base_alpha = color[3] if len(color) > 3 else alpha
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    mat.use_screen_refraction = True
    mat.diffuse_color = color[:3] + (alpha,)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        set_input(bsdf, ["Base Color"], color[:3] + (base_alpha,))
        set_input(bsdf, ["Alpha"], alpha)
        set_input(bsdf, ["Roughness"], roughness)
        set_input(bsdf, ["Metallic"], 0.0)
        set_input(bsdf, ["Transmission Weight", "Transmission"], 0.15)
        set_input(bsdf, ["IOR"], 1.34)
    return mat


def key_material_alpha(mat, keys) -> None:
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if not bsdf or "Alpha" not in bsdf.inputs:
        return
    alpha_input = bsdf.inputs["Alpha"]
    target_alpha = float(mat.get("key_alpha", 1.0))
    for frame, alpha in sorted(set(keys)):
        alpha_input.default_value = alpha * target_alpha
        alpha_input.keyframe_insert("default_value", frame=frame)
    if mat.animation_data and mat.animation_data.action and hasattr(mat.animation_data.action, "fcurves"):
        for fcurve in mat.animation_data.action.fcurves:
            for key in fcurve.keyframe_points:
                key.interpolation = "SINE"


def stage_keys(index: int):
    stage_len = 24
    fade = 7
    start = FRAME_START + index * stage_len
    hold_end = min(start + stage_len - fade, FRAME_END)
    end = min(start + stage_len, FRAME_END)
    keys = [(FRAME_START, 0.0), (max(FRAME_START, start - fade), 0.0), (start, 1.0), (hold_end, 1.0), (end, 0.0), (FRAME_END, 0.0)]
    if index == 0:
        keys = [(FRAME_START, 1.0), (18, 1.0), (25, 0.0), (132, 0.0), (FRAME_END, 1.0)]
    return keys


def add_sphere(name: str, radius: float, location, material, segments: int = 48, rings: int = 24, scale=(1, 1, 1), parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    tex = bpy.data.textures.new(f"{name}_surface_noise", type="VORONOI")
    tex.noise_scale = 1.6
    tex.intensity = 0.18
    modifier = obj.modifiers.new("subtle_surface_variation", "DISPLACE")
    modifier.strength = 0.008
    modifier.texture = tex
    return obj


def fibonacci_points(count: int, radius: float):
    points = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(count):
        y = 1 - (i / float(count - 1)) * 2
        r = math.sqrt(max(0, 1 - y * y))
        theta = golden * i
        x = math.cos(theta) * r
        z = math.sin(theta) * r
        points.append(Vector((x * radius, y * radius, z * radius)))
    return points


def add_stage_cells(root, stage_index: int, cells, cell_color=(0.83, 0.80, 0.72, 0.88), nucleus=False):
    cell_mat = make_material(f"stage_{stage_index}_blastomeres", cell_color, 0.0)
    key_material_alpha(cell_mat, stage_keys(stage_index))
    nuc_mat = make_material(f"stage_{stage_index}_subtle_nuclei", (0.58, 0.67, 0.80, 0.28), 0.0)
    nuc_mat["key_alpha"] = 0.28
    key_material_alpha(nuc_mat, stage_keys(stage_index))
    for idx, (loc, radius, scale) in enumerate(cells):
        add_sphere(f"stage_{stage_index}_cell_{idx:02d}", radius, loc, cell_mat, scale=scale, parent=root)
        if nucleus:
            offset = Vector(loc) * 0.18
            add_sphere(f"stage_{stage_index}_nucleus_{idx:02d}", radius * 0.16, Vector(loc) - offset, nuc_mat, segments=24, rings=12, parent=root)


def build_scene(output_dir: Path, frames_dir: Path) -> None:
    clear_scene()
    scene = bpy.context.scene
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.frame_set(FRAME_START)
    scene.render.fps = FPS
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100

    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene, "eevee"):
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = 64
        if hasattr(scene.eevee, "use_bloom"):
            scene.eevee.use_bloom = True
        if hasattr(scene.eevee, "bloom_intensity"):
            scene.eevee.bloom_intensity = 0.035
        if hasattr(scene.eevee, "use_gtao"):
            scene.eevee.use_gtao = True
        if hasattr(scene.eevee, "gtao_distance"):
            scene.eevee.gtao_distance = 2.5
        if hasattr(scene.eevee, "gtao_factor"):
            scene.eevee.gtao_factor = 0.65

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.color = (0.002, 0.0025, 0.005)
    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
    except Exception:
        pass

    root = bpy.data.objects.new("embryo_rotation_root", None)
    bpy.context.collection.objects.link(root)
    root.rotation_euler = (math.radians(9), 0, math.radians(-8))
    root.keyframe_insert("rotation_euler", frame=FRAME_START)
    root.rotation_euler = (math.radians(9), 0, math.radians(352))
    root.keyframe_insert("rotation_euler", frame=FRAME_END)
    if root.animation_data and root.animation_data.action and hasattr(root.animation_data.action, "fcurves"):
        for fcurve in root.animation_data.action.fcurves:
            for key in fcurve.keyframe_points:
                key.interpolation = "LINEAR"

    zona_mat = make_material("zona_pellucida_translucent", (0.72, 0.82, 0.96, 0.23), 0.23, 0.44)
    add_sphere("zona_pellucida_outer", 1.02, (0, 0, 0), zona_mat, segments=96, rings=48, scale=(1, 1, 1), parent=root)
    add_sphere("zona_pellucida_inner_rim", 0.92, (0, 0, 0), zona_mat, segments=96, rings=48, scale=(1, 1, 1), parent=root)

    membrane_mat = make_material("cleavage_boundary_shadow", (0.28, 0.35, 0.46, 0.25), 0.25, 0.9)
    membrane_mat["key_alpha"] = 0.25

    add_stage_cells(root, 0, [((0, 0, 0), 0.70, (1.03, 0.98, 1.0))], nucleus=True)
    add_sphere("zygote_pronucleus_a", 0.085, (-0.16, 0.06, 0.08), membrane_mat, segments=24, rings=12, parent=root)
    add_sphere("zygote_pronucleus_b", 0.085, (0.16, -0.04, -0.02), membrane_mat, segments=24, rings=12, parent=root)
    key_material_alpha(membrane_mat, stage_keys(0))

    add_stage_cells(
        root,
        1,
        [((-0.33, 0.02, 0), 0.50, (1.05, 0.98, 1.02)), ((0.33, -0.02, 0), 0.50, (1.05, 1.0, 0.98))],
        nucleus=False,
    )

    four = [
        ((-0.28, -0.24, 0.10), 0.39, (1.0, 1.05, 0.98)),
        ((0.30, -0.19, -0.08), 0.39, (1.02, 1.0, 1.03)),
        ((-0.10, 0.31, -0.16), 0.39, (1.04, 0.98, 1.0)),
        ((0.17, 0.24, 0.18), 0.39, (0.98, 1.03, 1.02)),
    ]
    add_stage_cells(root, 2, four)

    eight_positions = [
        (-0.36, -0.28, -0.18),
        (-0.36, 0.20, 0.18),
        (0.34, -0.24, 0.16),
        (0.32, 0.26, -0.16),
        (-0.05, -0.42, 0.18),
        (0.02, 0.42, -0.18),
        (-0.02, -0.02, 0.42),
        (0.04, 0.02, -0.42),
    ]
    add_stage_cells(root, 3, [(pos, 0.28, (1.04, 0.98, 1.02)) for pos in eight_positions])

    morula_points = fibonacci_points(20, 0.55)
    morula_cells = []
    for i, point in enumerate(morula_points):
        jitter = Vector((math.sin(i * 1.7) * 0.035, math.cos(i * 1.3) * 0.025, math.sin(i * 0.9) * 0.03))
        morula_cells.append((point + jitter, 0.185 + (i % 3) * 0.008, (1.02, 0.98, 1.0)))
    add_stage_cells(root, 4, morula_cells, cell_color=(0.80, 0.78, 0.70, 0.9))

    te_mat = make_material("stage_5_trophectoderm", (0.78, 0.77, 0.68, 0.9), 0.0)
    icm_mat = make_material("stage_5_inner_cell_mass", (0.88, 0.82, 0.70, 0.92), 0.0)
    cavity_mat = make_material("stage_5_blastocoel_cavity", (0.42, 0.62, 0.88, 0.055), 0.0)
    cavity_mat["key_alpha"] = 0.055
    for mat in (te_mat, icm_mat, cavity_mat):
        key_material_alpha(mat, stage_keys(5))
    add_sphere("blastocoel_cavity", 0.48, (0.12, -0.01, 0), cavity_mat, segments=48, rings=24, scale=(1.12, 0.95, 0.98), parent=root)
    for i, point in enumerate(fibonacci_points(34, 0.66)):
        if point.x < -0.53 and abs(point.y) < 0.45:
            continue
        add_sphere(f"blastocyst_te_cell_{i:02d}", 0.135, point, te_mat, segments=32, rings=16, scale=(1.05, 0.95, 1.0), parent=root)
    icm_offsets = [
        (-0.48, 0.00, 0.00),
        (-0.39, 0.13, 0.08),
        (-0.38, -0.13, -0.08),
        (-0.33, 0.01, 0.18),
        (-0.33, -0.02, -0.18),
        (-0.25, 0.13, -0.03),
        (-0.25, -0.12, 0.04),
        (-0.19, 0.00, 0.00),
    ]
    for i, pos in enumerate(icm_offsets):
        add_sphere(f"blastocyst_icm_cell_{i:02d}", 0.13, pos, icm_mat, segments=32, rings=16, parent=root)

    bpy.ops.object.light_add(type="AREA", location=(-2.0, -2.3, 3.2))
    key = bpy.context.object
    key.name = "large_soft_microscope_key"
    key.data.energy = 450
    key.data.size = 4.0
    bpy.ops.object.light_add(type="POINT", location=(1.4, 1.6, 1.8))
    rim = bpy.context.object
    rim.name = "cool_rim_light"
    rim.data.energy = 45
    rim.data.color = (0.62, 0.73, 1.0)

    bpy.ops.object.camera_add(location=(0, -3.5, 0.12), rotation=(math.radians(88), 0, 0))
    camera = bpy.context.object
    camera.name = "orthographic_microscope_camera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.42
    scene.camera = camera

    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(frames_dir / "embryo_hero_")
    bpy.ops.render.render(animation=True)

    scene.frame_set(126)
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 88
    scene.render.filepath = str(output_dir / "embryo-hero-poster-2026.jpg")
    bpy.ops.render.render(write_still=True)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    if args.frames_dir:
        frames_dir = Path(args.frames_dir).resolve()
    else:
        frames_dir = output_dir.parent / ".embryo_frames"
    build_scene(output_dir, frames_dir)


if __name__ == "__main__":
    main()
