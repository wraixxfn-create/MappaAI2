"""Structural checks for the delivered .blend (Blender 4.5+ / bpy).

    blender --background --python tests/validate_scene.py -- --blend porta_dell_inferno.blend
    python3 tests/validate_scene.py --blend porta_dell_inferno.blend

These checks load the project, but never save or modify the on-disk file.
"""
import argparse
import os
from pathlib import Path
import sys
import unittest

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else (
    sys.argv[1:] if os.path.basename(sys.argv[0]) == 'validate_scene.py' else [])
parser = argparse.ArgumentParser()
parser.add_argument('--blend', type=Path, default=ROOT / 'porta_dell_inferno.blend')
parser.add_argument('--compare-generated', type=Path, help='Optional independently regenerated project to compare.')
options = parser.parse_args(args)
bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))


class DetailedGateTests(unittest.TestCase):
    def test_scene_is_complete_and_self_contained(self):
        self.assertGreaterEqual(len(bpy.data.objects), 3000)
        self.assertEqual(len(bpy.context.scene.collection.children), 6)
        self.assertEqual(bpy.context.scene['Oggetti'], len(bpy.data.objects))
        self.assertEqual(bpy.context.scene['Materiali'], len(bpy.data.materials))
        self.assertGreaterEqual(len(bpy.data.materials), 21)
        for obj in bpy.data.objects:
            self.assertIsNone(obj.library, obj.name)
            self.assertFalse(obj.name.startswith('__'), obj.name)
        for material in bpy.data.materials:
            self.assertTrue(material.use_nodes, material.name)
            self.assertFalse(any(n.type == 'TEX_IMAGE' for n in material.node_tree.nodes), material.name)
        for font in bpy.data.fonts:
            self.assertTrue(font.packed_file or font.filepath == '<builtin>', font.name)
        self.assertIn('porta_inferno.py', bpy.data.texts)

    def test_production_settings_restored(self):
        scene = bpy.context.scene
        self.assertEqual(scene.render.engine, 'CYCLES')
        self.assertEqual(scene.cycles.samples, 128)
        self.assertEqual((scene.render.resolution_x, scene.render.resolution_y), (2000, 2320))
        self.assertEqual(scene.render.resolution_percentage, 100)
        self.assertTrue(scene.cycles.use_denoising)
        self.assertEqual(scene.camera.name, 'Camera | soglia dei dannati')
        self.assertEqual(scene.render.filepath, '//porta_dell_inferno_preview.png')
        self.assertEqual(sum(o.type == 'CAMERA' for o in bpy.data.objects), 4)

    def test_warning_preserved(self):
        inscription = bpy.data.objects["Avvertimento | Lasciate ogni speranza"]
        self.assertEqual(inscription.data.body, "LASCIATE OGNI SPERANZA, VOI CH'ENTRATE")

    def test_new_door_details_are_hinged(self):
        for side, name in ((-1, 'sinistro'), (1, 'destro')):
            root = bpy.data.objects[f'Cardine del battente {name}']
            prefix = f'Intaglio del battente {side:+d}'
            children = [o for o in bpy.data.objects if o.name.startswith(prefix)]
            self.assertGreater(len(children), 130)
            self.assertTrue(all(o.parent == root for o in children))
            latch = bpy.data.objects[prefix + ' | chiavistello forgiato']
            bpy.context.view_layer.update()
            before = latch.matrix_world.translation.copy()
            angle = root.rotation_euler.z
            try:
                root.rotation_euler.z += 0.2
                bpy.context.view_layer.update()
                self.assertGreater((latch.matrix_world.translation - before).length, 0.1)
            finally:
                root.rotation_euler.z = angle
                bpy.context.view_layer.update()

    def test_damage_and_sculpture_are_geometry(self):
        stones = [o for o in bpy.data.objects if o.name.startswith('Torre -1 | concio')]
        self.assertGreater(len(stones), 35)
        chipped = [o for o in stones if len(o.data.vertices) > 8]
        self.assertGreater(len(chipped), 30)
        for obj in chipped:
            bm = bmesh.new()
            try:
                bm.from_mesh(obj.data)
                self.assertTrue(all(e.is_manifold for e in bm.edges), obj.name)
                self.assertGreater(bm.calc_volume(signed=True), 0, obj.name)
            finally:
                bm.free()
        # Object names are limited to 63 bytes; identify the shared sculpture mesh.
        crania = [o for o in bpy.data.objects if o.type == 'MESH'
                  and o.data.name.startswith('Cranio anatomico')]
        self.assertGreaterEqual(len(crania), 14)
        self.assertTrue(all(len(o.data.vertices) > 1000 for o in crania))
        self.assertTrue(all(not any(m.type == 'BOOLEAN' for m in o.modifiers) for o in crania))
        # Rays hit the back of the carved cavities, not an intact sphere front.
        from mathutils import Vector
        bpy.context.view_layer.update()
        head = crania[0]
        for x in (-0.143, 0.143):
            hit, point, _normal, _face = head.ray_cast(Vector((x, -1, 0.027)), Vector((0, 1, 0)))
            self.assertTrue(hit)
            self.assertGreater(point.y, -0.12)
        hit, point, _normal, _face = head.ray_cast(Vector((0, -1, -0.11)), Vector((0, 1, 0)))
        self.assertTrue(hit)
        self.assertAlmostEqual(point.y, -0.10, places=4)
        # Real folds, curved wing membranes and six-petal stone tracery.
        robes = [o for o in bpy.data.objects if o.name.endswith('| manto di pietra')]
        self.assertEqual(len(robes), 2)
        self.assertTrue(all(len(o.data.vertices) == 64 * 36 for o in robes))
        self.assertEqual(sum(o.name.startswith('Petalo traforato del rosone') for o in bpy.data.objects), 6)
        self.assertGreater(sum(o.name.startswith("Uncino d'acanto dell'arco") and o.type == 'MESH'
                              for o in bpy.data.objects), 60)

    def test_distance_masks_are_not_clamped_to_one(self):
        material = bpy.data.materials['Basalto vulcanico | eroso, crepato, coperto di cenere']
        maps = [n for n in material.node_tree.nodes if n.type == 'MAP_RANGE']
        self.assertEqual(len(maps), 4)
        self.assertTrue(any(abs(n.inputs['From Max'].default_value - 7.5) < 1e-5 for n in maps))
        self.assertTrue(all(n.inputs['Value'].is_linked for n in maps))
        edge = next(n for n in material.node_tree.nodes if n.label == 'Spigoli esposti')
        self.assertAlmostEqual(edge.color_ramp.elements[0].position, 0.5)
        self.assertAlmostEqual(edge.color_ramp.elements[-1].position, 0.62, places=5)

    @unittest.skipUnless(options.compare_generated, 'No regenerated comparison requested')
    def test_regenerated_geometry_matches(self):
        import hashlib

        def signature(path):
            bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
            bpy.context.view_layer.update()
            digest = hashlib.sha256()
            for obj in sorted(bpy.data.objects, key=lambda o: o.name):
                digest.update(repr((obj.name, obj.type, obj.parent.name if obj.parent else None,
                                   tuple(round(x, 6) for row in obj.matrix_world for x in row))).encode())
                if obj.type == 'MESH':
                    coords = [tuple(round(x, 6) for x in v.co) for v in obj.data.vertices]
                    digest.update(repr(sorted(coords)).encode())
                    faces = []
                    for polygon in obj.data.polygons:
                        sequence = tuple(coords[i] for i in polygon.vertices)
                        # bmesh/CSG can reorder vertices and faces between runs.
                        # Canonical cyclic coordinates retain winding and topology.
                        faces.append(min(sequence[i:] + sequence[:i] for i in range(len(sequence))))
                    digest.update(repr(sorted(faces)).encode())
                elif obj.type == 'CURVE':
                    for spline in obj.data.splines:
                        digest.update(repr((spline.type, spline.use_cyclic_u,
                                           tuple(tuple(round(x, 6) for x in point.co)
                                                 for point in spline.points))).encode())
            return digest.hexdigest()

        try:
            self.assertEqual(signature(options.blend), signature(options.compare_generated))
        finally:
            bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))

    def test_human_figures_make_the_scale_monumental(self):
        from mathutils import Vector

        def world_z_extent(objs):
            zs = []
            for obj in objs:
                for corner in obj.bound_box:
                    zs.append((obj.matrix_world @ Vector(corner)).z)
            return min(zs), max(zs)

        figures = [o for o in bpy.data.objects if o.name.startswith('Figura umana |')]
        self.assertGreaterEqual(len(figures), 7)
        pilgrim = bpy.data.objects['Figura umana | Pellegrino sulla via']
        bodies = [o for o in bpy.data.objects
                  if o.name.startswith('Anima | Pellegrino sulla via')
                  and '| bordone' not in o.name]  # il bastone non è statura
        self.assertGreaterEqual(len(bodies), 8)
        bpy.context.view_layer.update()
        low, high = world_z_extent([pilgrim] + bodies)
        altezza = high - low
        self.assertGreater(altezza, 1.5)   # a real human, not a doll
        self.assertLess(altezza, 2.2)
        # The gate towers tens of metres: ~17 human heights to the trident.
        masonry = bpy.data.collections['01 • Architettura | basalto e conci'].objects
        _, top = world_z_extent(list(masonry))
        self.assertGreater(top, 28.0)
        self.assertGreater(top / altezza, 15.0)
        # Low, ground-level camera: converging verticals, oppressive scale.
        cam = bpy.data.objects['Camera | soglia dei dannati']
        self.assertLess(cam.location.z, 4.0)
        # Foreground figure between camera and gate, lit from behind by it.
        px, py = pilgrim.location.x, pilgrim.location.y
        cx, cy = cam.location.x, cam.location.y
        self.assertLess((px - cx) ** 2 + (py - cy) ** 2, (0 - cx) ** 2 + (0 - cy) ** 2)

    def test_mesh_coordinates_and_transforms_are_finite(self):
        import math
        for obj in bpy.data.objects:
            self.assertTrue(all(math.isfinite(x) for row in obj.matrix_world for x in row), obj.name)
        for mesh in bpy.data.meshes:
            self.assertTrue(all(math.isfinite(x) for v in mesh.vertices for x in v.co), mesh.name)
            self.assertGreater(len(mesh.vertices), 0, mesh.name)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DetailedGateTests))
    sys.exit(not result.wasSuccessful())
