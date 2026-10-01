"""Porta dell'Inferno — scena procedurale per Blender 4.x.

Esecuzione in Blender:
    blender --background --python porta_inferno.py

Il file .blend e l'anteprima PNG vengono salvati accanto a questo script.
Tutta la geometria e i materiali sono procedurali: nessun asset esterno richiesto.
"""
import bpy
import math
import os
import random
from mathutils import Vector

random.seed(73)
ROOT = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
BLEND_PATH = os.path.join(ROOT, "porta_dell_inferno.blend")
PREVIEW_PATH = os.path.join(ROOT, "porta_dell_inferno_preview.png")

# -----------------------------------------------------------------------------
# Scene reset + organized collections
# -----------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "La Porta dell'Inferno | Inferno, Canto III"

COLLECTIONS = {}

def new_collection(name):
    coll = bpy.data.collections.new(name)
    scene.collection.children.link(coll)
    COLLECTIONS[name] = coll
    return coll

new_collection("01 • Architettura | basalto e conci")
new_collection("02 • Portale | battenti di ferro")
new_collection("03 • Sculture | anime e guardiani")
new_collection("04 • Oltretomba | fuoco, lava, catene")
new_collection("05 • Scena | terreno, camera, luci")
ACTIVE = COLLECTIONS["01 • Architettura | basalto e conci"]

def use_collection(name):
    global ACTIVE
    ACTIVE = COLLECTIONS[name]

def link_object(obj, collection=None):
    target = collection or ACTIVE
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    target.objects.link(obj)
    return obj

# -----------------------------------------------------------------------------
# Procedural materials
# -----------------------------------------------------------------------------
def principled_material(name, base=(0.2, 0.2, 0.2, 1), metallic=0.0, roughness=0.6,
                        noise_scale=0.0, bump_strength=0.0, bump_distance=0.04,
                        color_low=None, color_high=None):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = base
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (350, 0)
    bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if noise_scale:
        tex = nodes.new("ShaderNodeTexNoise")
        tex.location = (-600, 100)
        tex.inputs["Scale"].default_value = noise_scale
        tex.inputs["Detail"].default_value = 5.0
        tex.inputs["Roughness"].default_value = 0.72
        coord = nodes.new("ShaderNodeTexCoord")
        coord.location = (-820, 100)
        links.new(coord.outputs["Generated"], tex.inputs["Vector"])
        if color_low and color_high:
            ramp = nodes.new("ShaderNodeValToRGB")
            ramp.location = (-160, 180)
            ramp.color_ramp.elements[0].position = 0.18
            ramp.color_ramp.elements[0].color = color_low
            ramp.color_ramp.elements[1].position = 0.84
            ramp.color_ramp.elements[1].color = color_high
            links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
            links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        if bump_strength:
            bump = nodes.new("ShaderNodeBump")
            bump.location = (80, -180)
            bump.inputs["Strength"].default_value = bump_strength
            bump.inputs["Distance"].default_value = bump_distance
            links.new(tex.outputs["Fac"], bump.inputs["Height"])
            links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat

stone = principled_material(
    "Basalto antico | venature e cenere", (0.16, 0.17, 0.19, 1), 0.12, 0.82,
    5.2, 0.22, 0.11,
    (0.045, 0.052, 0.067, 1), (0.29, 0.30, 0.31, 1))
stone_light = principled_material(
    "Pietra lunare | bordi consumati", (0.32, 0.30, 0.27, 1), 0.08, 0.77,
    7.0, 0.16, 0.065,
    (0.12, 0.13, 0.15, 1), (0.42, 0.39, 0.34, 1))
stone_dark = principled_material(
    "Basalto vitrificato", (0.055, 0.064, 0.079, 1), 0.3, 0.42,
    8.0, 0.12, 0.035,
    (0.018, 0.022, 0.033, 1), (0.16, 0.12, 0.11, 1))
iron = principled_material(
    "Ferro battuto | nero ossidato", (0.065, 0.075, 0.086, 1), 0.82, 0.32,
    15.0, 0.1, 0.018,
    (0.018, 0.026, 0.035, 1), (0.17, 0.13, 0.09, 1))
bronze = principled_material(
    "Bronzo annerito", (0.22, 0.105, 0.042, 1), 0.82, 0.29,
    18.0, 0.08, 0.012,
    (0.055, 0.026, 0.012, 1), (0.42, 0.22, 0.075, 1))
gold = principled_material(
    "Ottone antico | iscrizioni", (0.65, 0.36, 0.105, 1), 0.8, 0.27,
    22.0, 0.035, 0.01,
    (0.18, 0.075, 0.018, 1), (0.92, 0.61, 0.22, 1))
bone = principled_material(
    "Osso consunto", (0.52, 0.43, 0.31, 1), 0.04, 0.72,
    10.0, 0.12, 0.025,
    (0.19, 0.15, 0.11, 1), (0.73, 0.63, 0.46, 1))
bone_shadow = principled_material(
    "Osso in ombra", (0.22, 0.18, 0.14, 1), 0.16, 0.62,
    11.0, 0.08, 0.02,
    (0.08, 0.065, 0.055, 1), (0.34, 0.26, 0.17, 1))
void_mat = principled_material("Vuoto | nero profondo", (0.004, 0.003, 0.008, 1), 0.05, 0.3)


def emission_material(name, color, strength=1.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*color, 1)
    emission.inputs["Strength"].default_value = strength
    mat.node_tree.links.new(emission.outputs["Emission"], out.inputs["Surface"])
    return mat

ember = emission_material("Fiamma | oro incandescente", (1.0, 0.24, 0.025), 4.0)
flame_orange = emission_material("Fiamma | arancio infernale", (1.0, 0.055, 0.008), 2.4)
flame_red = emission_material("Brace | rosso cremisi", (0.56, 0.018, 0.009), 1.5)
eye_glow = emission_material("Occhi | brace viva", (1.0, 0.16, 0.018), 3.5)

portal_mat = bpy.data.materials.new("Soglia | bagliore ctonio procedurale")
portal_mat.use_nodes = True
pn = portal_mat.node_tree.nodes
pl = portal_mat.node_tree.links
pn.clear()
pout = pn.new("ShaderNodeOutputMaterial")
pout.location = (650, 0)
pem = pn.new("ShaderNodeEmission")
pem.location = (420, 0)
pem.inputs["Strength"].default_value = 2.2
pnoise = pn.new("ShaderNodeTexNoise")
pnoise.location = (-420, 30)
pnoise.inputs["Scale"].default_value = 5.0
pnoise.inputs["Detail"].default_value = 6.0
pnoise.inputs["Roughness"].default_value = 0.8
pcoord = pn.new("ShaderNodeTexCoord")
pcoord.location = (-640, 30)
pl.new(pcoord.outputs["Generated"], pnoise.inputs["Vector"])
pramp = pn.new("ShaderNodeValToRGB")
pramp.location = (-120, 50)
pramp.color_ramp.elements[0].position = 0.18
pramp.color_ramp.elements[0].color = (0.025, 0.001, 0.014, 1)
pramp.color_ramp.elements[1].position = 0.83
pramp.color_ramp.elements[1].color = (1.0, 0.22, 0.012, 1)
mid = pramp.color_ramp.elements.new(0.54)
mid.color = (0.42, 0.012, 0.012, 1)
pl.new(pnoise.outputs["Fac"], pramp.inputs["Fac"])
pl.new(pramp.outputs["Color"], pem.inputs["Color"])
pl.new(pem.outputs["Emission"], pout.inputs["Surface"])

lava_mat = principled_material(
    "Lava | crosta nera e vene rosse", (0.25, 0.025, 0.006, 1), 0.25, 0.31,
    4.5, 0.18, 0.035,
    (0.012, 0.006, 0.009, 1), (0.58, 0.055, 0.006, 1))
# Add emission to the lava's fissure-like high-frequency texture.
lnodes = lava_mat.node_tree.nodes
llinks = lava_mat.node_tree.links
lbsdf = next(n for n in lnodes if n.type == "BSDF_PRINCIPLED")
ltex = next(n for n in lnodes if n.type == "TEX_NOISE")
lramp = next(n for n in lnodes if n.type == "VALTORGB")
lem = lnodes.new("ShaderNodeEmission")
lem.location = (340, -360)
lem.inputs["Strength"].default_value = 1.15
lmask = lnodes.new("ShaderNodeValToRGB")
lmask.location = (-100, -300)
lmask.color_ramp.elements[0].position = 0.55
lmask.color_ramp.elements[0].color = (0, 0, 0, 1)
lmask.color_ramp.elements[1].position = 0.73
lmask.color_ramp.elements[1].color = (1, 0.18, 0.012, 1)
llinks.new(ltex.outputs["Fac"], lmask.inputs["Fac"])
llinks.new(lmask.outputs["Color"], lem.inputs["Color"])
# Keep the stone surface and a subtle self-lit molten seam in the same material.
ladd = lnodes.new("ShaderNodeAddShader")
ladd.location = (560, -40)
llinks.new(lbsdf.outputs["BSDF"], ladd.inputs[0])
llinks.new(lem.outputs["Emission"], ladd.inputs[1])
lout = next(n for n in lnodes if n.type == "OUTPUT_MATERIAL")
llinks.new(ladd.outputs["Shader"], lout.inputs["Surface"])

# -----------------------------------------------------------------------------
# Geometry helpers
# -----------------------------------------------------------------------------
def add_box(name, location, dimensions, material, bevel=0.035, parent=None, collection=None):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    if bevel and min(dimensions) > bevel * 2.2:
        mod = obj.modifiers.new("Spigoli smussati a mano", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.profile = 0.55
        obj.modifiers.new("Normali da scultura", "WEIGHTED_NORMAL")
    if parent:
        obj.parent = parent
    link_object(obj, collection)
    return obj


def add_uv_sphere(name, location, scale, material, segments=20, rings=12,
                   smooth=True, parent=None, collection=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1.0,
                                         location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    if material:
        obj.data.materials.append(material)
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    if parent:
        obj.parent = parent
    link_object(obj, collection)
    return obj


def add_ico(name, location, scale, material, subdivisions=1, parent=None, collection=None):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    if material:
        obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    link_object(obj, collection)
    return obj


def add_cylinder(name, location, radius, depth, material, vertices=20,
                 bevel=0.0, parent=None, collection=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth,
                                        location=location)
    obj = bpy.context.object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if bevel and depth > bevel * 3:
        mod = obj.modifiers.new("Bordo consumato", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        obj.modifiers.new("Normali", "WEIGHTED_NORMAL")
    if parent:
        obj.parent = parent
    link_object(obj, collection)
    return obj


def add_cone(name, location, radius1, radius2, depth, material, vertices=12,
             parent=None, collection=None):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius1, radius2=radius2,
                                    depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    link_object(obj, collection)
    return obj


def add_rod(name, a, b, radius, material, vertices=10, parent=None, collection=None):
    va, vb = Vector(a), Vector(b)
    delta = vb - va
    if delta.length < 1e-5:
        return None
    obj = add_cylinder(name, (va + vb) * 0.5, radius, delta.length, material,
                       vertices=vertices, parent=parent, collection=collection)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(delta.normalized())
    return obj


def add_curve(name, points, radius, material, cyclic=False, parent=None,
              resolution=2, collection=None):
    data = bpy.data.curves.new(name + " | curva", "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 12
    data.bevel_depth = radius
    data.bevel_resolution = resolution
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, coord in zip(spline.points, points):
        point.co = (coord[0], coord[1], coord[2], 1)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, data)
    if material:
        data.materials.append(material)
    if parent:
        obj.parent = parent
    (collection or ACTIVE).objects.link(obj)
    return obj


def add_extruded_polygon(name, outline_xz, front_y, back_y, material,
                         bevel=0.0, parent=None, collection=None):
    n = len(outline_xz)
    verts = [(x, front_y, z) for x, z in outline_xz] + [(x, back_y, z) for x, z in outline_xz]
    faces = [tuple(range(n)), tuple(range(n, 2*n))[::-1]]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n+j, n+i))
    mesh = bpy.data.meshes.new(name + " | mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    (collection or ACTIVE).objects.link(obj)
    if parent:
        obj.parent = parent
    if bevel:
        mod = obj.modifiers.new("Bordi scheggiati", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        obj.modifiers.new("Normali pesate", "WEIGHTED_NORMAL")
    return obj


def add_arch_fill(name, outline_xz, y, material, collection=None):
    verts = [(x, y, z) for x, z in outline_xz]
    faces = [tuple(range(len(verts)))]
    mesh = bpy.data.meshes.new(name + " | mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    (collection or ACTIVE).objects.link(obj)
    return obj


def parent_empty(name, location, z_rotation):
    obj = bpy.data.objects.new(name, None)
    ACTIVE.objects.link(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.48
    obj.location = location
    obj.rotation_euler[2] = z_rotation
    return obj

# -----------------------------------------------------------------------------
# Gothic profile: paired, pointed Bezier arches
# -----------------------------------------------------------------------------
INNER_A = 2.72
INNER_SPRING = 4.82
INNER_TOP = 8.93
OUTER_A = 3.52
OUTER_SPRING = 4.72
OUTER_TOP = 9.82

def arch_point(t, a, spring, top, side=-1):
    # Cubic Gothic profile, vertical at the spring and sharply pointed at the crown.
    p0 = (-a, spring)
    p1 = (-a, spring + (top - spring) * 0.40)
    p2 = (-0.53, top - (top - spring) * 0.30)
    p3 = (0.0, top)
    u = 1.0 - t
    x = u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0]
    z = u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]
    return (x if side < 0 else -x, z)


def arch_points(a, spring, top, side=-1, steps=64, t0=0.0, t1=1.0):
    return [arch_point(t0 + (t1-t0)*i/steps, a, spring, top, side) for i in range(steps+1)]

# -----------------------------------------------------------------------------
# Environment and broad stone foundation
# -----------------------------------------------------------------------------
use_collection("05 • Scena | terreno, camera, luci")
world = bpy.data.worlds.new("Notte senza stelle")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.009, 0.012, 0.025, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.22

# Ground plane and volcanic slabs.
add_box("Basamento | lastra infernale", (0, -1.2, -0.22), (13.2, 10.5, 0.42), stone_dark, 0.12)
add_box("Pianoro di basalto", (0, -7.6, -0.36), (36, 25, 0.28), stone_dark, 0.05)
# Large irregular flagstones in the foreground, aligned as a broken processional path.
for row in range(5):
    yy = -3.25 - row * 1.33
    for col in range(9):
        xx = -5.2 + col * 1.30 + (0.34 if row % 2 else 0.0)
        if abs(xx) > 5.8:
            continue
        sx = random.uniform(1.03, 1.32)
        sy = random.uniform(0.92, 1.28)
        slab = add_box(f"Lastra fratturata {row+1}.{col+1}", (xx, yy, 0.055),
                       (sx, sy, random.uniform(0.105, 0.17)),
                       random.choice([stone_dark, stone, stone]), 0.055)
        slab.rotation_euler[2] = random.uniform(-0.025, 0.025)

# Three broad, worn steps. Their dark edges catch the molten spill from the portal.
for i, (yy, width, zz, thick) in enumerate([
        (-0.82, 6.5, 0.16, 0.34), (-1.57, 6.9, 0.34, 0.34), (-2.32, 7.3, 0.52, 0.36)]):
    add_box(f"Gradino cerimoniale {i+1}", (0, yy, zz), (width, 0.92, thick),
            stone_light if i == 2 else stone, 0.09)
    add_box(f"Filo in ottone del gradino {i+1}", (0, yy-0.43, zz+thick*0.36),
            (width-0.22, 0.035, 0.025), bronze, 0.01)

# Scattered glowing cracks and embers on the approach.
use_collection("04 • Oltretomba | fuoco, lava, catene")
crack_glow = emission_material("Spaccature | filamento di lava", (1.0, 0.085, 0.006), 2.8)
for ci, points in enumerate([
    [(-4.8,-4.1,0.145),(-3.9,-4.3,0.145),(-3.2,-4.75,0.145),(-2.5,-4.9,0.145)],
    [(3.7,-3.7,0.145),(3.0,-4.15,0.145),(3.35,-4.9,0.145),(2.7,-5.35,0.145)],
    [(-1.7,-5.0,0.145),(-1.1,-5.45,0.145),(-1.4,-6.1,0.145),(-0.55,-6.65,0.145)],
    [(4.75,-6.0,0.145),(4.1,-6.3,0.145),(3.85,-7.0,0.145),(3.1,-7.35,0.145)],
    [(-4.5,-7.15,0.145),(-3.7,-7.45,0.145),(-3.2,-8.0,0.145),(-2.2,-8.2,0.145)],
    [(0.2,-3.8,0.145),(0.68,-4.35,0.145),(0.48,-4.9,0.145),(1.15,-5.25,0.145)],
]):
    add_curve(f"Crepa di lava {ci+1}", points, 0.022 if ci % 2 else 0.03, crack_glow, resolution=2)
for i in range(38):
    xx = random.uniform(-5.3, 5.3)
    yy = random.uniform(-8.4, -3.2)
    zz = random.uniform(0.16, 0.34)
    size = random.uniform(0.018, 0.055)
    add_ico(f"Favilla sospesa {i+1:02d}", (xx, yy, zz), (size, size, size*1.8),
            random.choice([ember, flame_orange]), subdivisions=1)

# -----------------------------------------------------------------------------
# Main masonry: coursed ashlar, piers, plinths and a massive upper crown
# -----------------------------------------------------------------------------
use_collection("01 • Architettura | basalto e conci")
# Side walls built from hand-sized, subtly irregular stone blocks.
for side in (-1, 1):
    for row in range(10):
        zc = 0.52 + row * 0.99
        for col in range(2):
            xbase = 4.14 + col * 1.22 + (0.17 if row % 2 else 0.0)
            if xbase > 5.35:
                continue
            xc = side * xbase
            wid = random.uniform(0.99, 1.21)
            dep = random.uniform(0.72, 0.95)
            obj = add_box(f"Concio laterale {side:+d}.{row+1:02d}.{col+1}",
                          (xc, -0.03 + random.uniform(-0.05, 0.04), zc),
                          (wid, dep, random.uniform(0.89, 1.0)),
                          random.choice([stone, stone, stone_light, stone_dark]), 0.055)
            obj.rotation_euler[1] = random.uniform(-0.012, 0.012)
    # Outer buttress pilasters articulate the facade silhouette.
    x = side * 5.42
    add_box(f"Contrafforte esterno {side:+d}", (x, -0.49, 5.1), (0.36, 0.55, 10.15),
            stone_light, 0.075)
    for z in (0.62, 4.82, 9.72):
        add_box(f"Listello del contrafforte {side:+d} @ {z:.1f}", (x, -0.82, z),
                (0.62, 0.24, 0.22), stone, 0.045)

# Upper spandrel wall over the outer arch, dressed as large cut blocks.
for row in range(2):
    zc = 10.08 + row * 0.78
    for col in range(7):
        xc = -4.98 + col * 1.66 + (0.18 if row % 2 else 0)
        if xc > 5.15:
            continue
        add_box(f"Concio del coronamento {row+1}.{col+1}",
                (xc, -0.02, zc), (1.58, 0.86, 0.72),
                random.choice([stone, stone_light, stone]), 0.06)

# Load-bearing piers flanking the opening.
for side in (-1, 1):
    add_box(f"Piede del pilone {side:+d}", (side*3.60, -0.48, 0.58),
            (1.05, 1.1, 1.08), stone_light, 0.09)
    for row in range(4):
        zc = 1.50 + row * 0.88
        add_box(f"Pilone a conci {side:+d}.{row+1}",
                (side*3.60, -0.36, zc), (0.88, 0.88, 0.82),
                random.choice([stone, stone_light, stone]), 0.06)
    add_box(f"Abaco del capitello {side:+d}", (side*3.60, -0.53, 5.15),
            (1.26, 1.02, 0.38), stone_light, 0.06)
    add_box(f"Cornice del capitello {side:+d}", (side*3.60, -0.55, 5.42),
            (1.08, 0.92, 0.18), gold, 0.035)

# Heavy plinth across the facade and a narrow moulding with carved dentils.
add_box("Zoccolo continuo del portale", (0, -0.39, 0.46), (10.9, 0.95, 0.84), stone_light, 0.1)
add_box("Cimasa inferiore | bronzo scuro", (0, -0.91, 0.90), (10.7, 0.13, 0.12), bronze, 0.025)
for i in range(25):
    x = -5.1 + i * 0.425
    add_box(f"Dentello del plinto {i+1:02d}", (x, -0.91, 1.03), (0.22, 0.10, 0.11),
            stone, 0.018)

# The pointed archivolt is assembled from individually bevelled voussoirs.
# The dark reveal gives the arch real depth; the keystone locks the two halves.
for side in (-1, 1):
    for i in range(13):
        t0 = i / 13.0 + 0.006
        t1 = (i + 1) / 13.0 - 0.006
        inner0 = arch_point(t0, INNER_A, INNER_SPRING, INNER_TOP, side)
        inner1 = arch_point(t1, INNER_A, INNER_SPRING, INNER_TOP, side)
        outer0 = arch_point(t0, OUTER_A, OUTER_SPRING, OUTER_TOP, side)
        outer1 = arch_point(t1, OUTER_A, OUTER_SPRING, OUTER_TOP, side)
        outline = [inner0, inner1, outer1, outer0]
        add_extruded_polygon(f"Concio d'arco {side:+d}.{i+1:02d}", outline,
                             -0.94, 0.10,
                             random.choice([stone, stone, stone_light, stone_dark]),
                             bevel=0.025)
    # Incised inner arris and the outer gilded fillet follow the stone curve.
    inner_line = arch_points(INNER_A-0.045, INNER_SPRING, INNER_TOP-0.02,
                             side, steps=72)
    add_curve(f"Archivolto interno | filetto {side:+d}",
              [(x, -0.995, z) for x, z in inner_line], 0.037, gold, resolution=3)
    outer_line = arch_points(OUTER_A+0.01, OUTER_SPRING+0.015, OUTER_TOP+0.02,
                             side, steps=72)
    add_curve(f"Archivolto esterno | cordone {side:+d}",
              [(x, -0.86, z) for x, z in outer_line], 0.055, stone_light, resolution=3)

# Deep side reveals under the archivolt.
for side in (-1, 1):
    add_box(f"Stipite profondo {side:+d}", (side*2.79, 0.11, 2.83),
            (0.32, 0.8, 4.22), stone_dark, 0.035)
    for z in (1.1, 2.15, 3.2, 4.25):
        add_box(f"Giunto scolpito nello stipite {side:+d}.{z:.1f}",
                (side*2.79, -0.33, z), (0.36, 0.08, 0.035), bronze, 0.008)

# Inner arch-shaped recess: visible through the open leaves.
inner_outline = [(-INNER_A, 0.58), (INNER_A, 0.58), (INNER_A, INNER_SPRING)]
right_arc = arch_points(INNER_A, INNER_SPRING, INNER_TOP, side=1, steps=48)
left_arc = arch_points(INNER_A, INNER_SPRING, INNER_TOP, side=-1, steps=48)
inner_outline += right_arc[1:]
inner_outline += list(reversed(left_arc))[1:]
add_arch_fill("Abisso | fondale ad arco", inner_outline, 1.18, portal_mat)
# A black inner frame makes the glowing plane feel recessed into an actual tunnel.
add_box("Soglia d'ombra", (0, 1.04, 0.48), (5.08, 0.18, 0.32), stone_dark, 0.035)
for side in (-1, 1):
    add_box(f"Spalla del tunnel {side:+d}", (side*2.59, 0.77, 2.78),
            (0.18, 0.48, 4.35), stone_dark, 0.035)

# Decorative roundel at the apex — the keystone is a carved, watchful skull.
add_box("Chiave di volta | mensola", (0, -0.90, 8.94), (0.92, 0.24, 0.58), stone_light, 0.08)
add_ico("Maschera della chiave di volta", (0, -1.10, 9.02), (0.32, 0.18, 0.34), bone, 2)
for sx in (-1, 1):
    add_uv_sphere("Occhio della chiave di volta", (sx*0.105, -1.265, 9.055),
                  (0.052, 0.035, 0.055), eye_glow, segments=12, rings=8)

# Cornices, broken gothic crown, and a sculptural trident finial.
add_box("Architrave | mensola alta", (0, -0.49, 10.87), (10.9, 1.0, 0.38), stone_light, 0.075)
add_box("Fascia d'ombra dell'architrave", (0, -0.98, 10.63), (10.7, 0.16, 0.13), bronze, 0.025)
# Broad triangular gable in front of the upper masonry.
front_gable = [(-5.25, 10.98), (5.25, 10.98), (0.0, 12.22)]
add_extruded_polygon("Frontone spezzato", front_gable, -0.74, -0.13, stone, bevel=0.055)
# Inner triangular recessed panel and mouldings.
add_extruded_polygon("Timpano | campo inciso",
                     [(-3.55, 11.10), (3.55, 11.10), (0.0, 11.96)],
                     -0.82, -0.73, stone_dark, bevel=0.02)
for side in (-1, 1):
    add_curve(f"Cornice inclinata del timpano {side:+d}",
              [((0.0 if side < 0 else 0.0), -0.91, 11.99),
               (side*1.65, -0.91, 11.60), (side*3.55, -0.91, 11.10),
               (side*5.10, -0.91, 10.99)], 0.075, gold, resolution=3)
# Two slender pinnacles with stepped bases and spear-shaped caps.
for side in (-1, 1):
    x = side*4.78
    add_box(f"Pinnacolo | base {side:+d}", (x, -0.87, 11.18), (0.78, 0.65, 0.42), stone_light, 0.055)
    add_cylinder(f"Fusto del pinnacolo {side:+d}", (x, -0.84, 11.88), 0.23, 1.18,
                 stone, vertices=8, bevel=0.025)
    add_cone(f"Freccia del pinnacolo {side:+d}", (x, -0.84, 12.68), 0.33, 0.0, 0.88,
             stone_light, vertices=8)
    add_uv_sphere(f"Nodo dorato del pinnacolo {side:+d}", (x, -0.88, 11.65),
                  (0.3, 0.09, 0.3), bronze, segments=16, rings=8)
# Central three-pronged, blackened-iron crest.
add_rod("Asta del tridente", (0, -0.92, 11.55), (0, -0.92, 12.78), 0.075, iron, 12)
for s in (-1, 0, 1):
    start = (s*0.04, -0.92, 12.0)
    midp = (s*0.34, -0.92, 12.38 if s else 12.55)
    end = (s*0.52, -0.92, 12.93)
    add_curve(f"Dente del tridente {s+2}", [start, midp, end], 0.065, iron, resolution=3)

# Inscription plaque and Dante's warning in raised, aged brass.
add_box("Targa della sentenza", (0, -0.99, 10.55), (7.92, 0.19, 0.72), stone_dark, 0.055)
add_box("Cornice della targa", (0, -1.11, 10.55), (7.68, 0.055, 0.57), bronze, 0.045)
add_box("Campo della targa", (0, -1.145, 10.55), (7.48, 0.035, 0.43), stone_dark, 0.028)

def add_text(name, body, location, size, material, align="CENTER", extrude=0.012):
    data = bpy.data.curves.new(name + " | caratteri", "FONT")
    data.body = body
    data.size = size
    data.align_x = align
    data.align_y = "CENTER"
    data.extrude = extrude
    data.bevel_depth = 0.003
    data.bevel_resolution = 2
    data.space_character = 1.04
    obj = bpy.data.objects.new(name, data)
    ACTIVE.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (math.pi/2, 0, 0)
    data.materials.append(material)
    return obj

add_text("Avvertimento | Lasciate ogni speranza", "LASCIATE OGNI SPERANZA, VOI CH'ENTRATE",
         (0, -1.205, 10.56), 0.29, gold, extrude=0.015)
# Small rosettes at the corners of the inscription.
for side in (-1, 1):
    add_ico(f"Rosone della targa {side:+d}", (side*3.66, -1.21, 10.55),
            (0.11, 0.055, 0.11), gold, subdivisions=2)
    for a in range(8):
        ang = a * math.tau / 8
        add_uv_sphere("Petalo del rosone", (side*3.66 + math.cos(ang)*0.10, -1.235,
                                              10.55 + math.sin(ang)*0.10),
                      (0.025, 0.016, 0.025), bronze, segments=8, rings=6)

# -----------------------------------------------------------------------------
# Doors: hinged, partly open iron leaves with relief, straps and skull bosses
# -----------------------------------------------------------------------------
def add_torus(name, location, major_radius, minor_radius, material, rotation=(0,0,0),
              parent=None, collection=None, major_segments=20, minor_segments=8):
    bpy.ops.mesh.primitive_torus_add(major_segments=major_segments, minor_segments=minor_segments,
                                     location=location, major_radius=major_radius,
                                     minor_radius=minor_radius)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = rotation
    if material:
        obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    link_object(obj, collection)
    return obj


def add_skull_relief(name, x, y, z, size, parent=None, collection=None,
                     skull_mat=bone, glow=True):
    col = collection or ACTIVE
    add_ico(name + " | cranio", (x, y, z), (0.38*size, 0.225*size, 0.42*size),
            skull_mat, subdivisions=2, parent=parent, collection=col)
    add_ico(name + " | mandibola", (x, y-0.006*size, z-0.27*size),
            (0.31*size, 0.19*size, 0.20*size), skull_mat, subdivisions=1,
            parent=parent, collection=col)
    # Recessed sockets, surrounded by raised orbital ridges.
    for side in (-1, 1):
        ex = x + side*0.145*size
        ez = z + 0.045*size
        add_uv_sphere(name + " | orbita", (ex, y-0.195*size, ez),
                      (0.105*size, 0.045*size, 0.12*size), void_mat,
                      segments=14, rings=8, parent=parent, collection=col)
        orbit = []
        for j in range(25):
            a = math.tau*j/24
            orbit.append((ex+math.cos(a)*0.112*size, y-0.225*size,
                          ez+math.sin(a)*0.132*size))
        add_curve(name + " | arcata dell'orbita", orbit, 0.026*size, skull_mat,
                  parent=parent, resolution=2, collection=col)
        if glow:
            add_uv_sphere(name + " | brace nell'occhio", (ex, y-0.244*size, ez),
                          (0.033*size, 0.02*size, 0.034*size), eye_glow,
                          segments=10, rings=6, parent=parent, collection=col)
    # Nasal cavity: a tiny inverted triangular recess.
    add_extruded_polygon(name + " | cavità nasale",
                         [(x-0.066*size,z-0.02*size), (x+0.066*size,z-0.02*size),
                          (x,z-0.19*size)], y-0.225*size, y-0.21*size,
                         void_mat, parent=parent, collection=col)
    # Brow ridge and five individually modelled teeth.
    brow = [(x-0.27*size,y-0.23*size,z+0.18*size),
            (x-0.13*size,y-0.25*size,z+0.22*size),
            (x,y-0.255*size,z+0.18*size),
            (x+0.13*size,y-0.25*size,z+0.22*size),
            (x+0.27*size,y-0.23*size,z+0.18*size)]
    add_curve(name + " | arcata sopracciliare", brow, 0.045*size, skull_mat,
              parent=parent, resolution=3, collection=col)
    for tooth in range(5):
        tx = x + (tooth-2)*0.095*size
        add_box(name + f" | dente {tooth+1}", (tx, y-0.223*size, z-0.345*size),
                (0.07*size, 0.075*size, 0.115*size), skull_mat, 0.012*size,
                parent=parent, collection=col)
    # Short curled horns, a little more infernal than anatomical.
    for side in (-1, 1):
        pts = [(x+side*0.26*size, y-0.12*size, z+0.28*size),
               (x+side*0.43*size, y-0.13*size, z+0.48*size),
               (x+side*0.51*size, y-0.11*size, z+0.66*size),
               (x+side*0.42*size, y-0.12*size, z+0.70*size)]
        add_curve(name + " | corno", pts, 0.045*size, skull_mat,
                  parent=parent, resolution=3, collection=col)

use_collection("02 • Portale | battenti di ferro")
DOOR_Y = 0.18
for side in (-1, 1):
    leaf = -side
    # Hinge pivots swing outward toward the viewer, revealing the living abyss.
    root = parent_empty("Cardine del battente sinistro" if side < 0 else "Cardine del battente destro",
                        (side*INNER_A, DOOR_Y, 0), -math.radians(25) if side < 0 else math.radians(25))
    root["funzione"] = "Battente apribile; ruotare l'empty attorno a Z per modificare l'apertura."
    t_stop = 0.955
    outline = [(0.0, 0.68), (leaf*(INNER_A-0.16), 0.68)]
    for j in range(32, -1, -1):
        t = t_stop * j / 32
        px, pz = arch_point(t, INNER_A, INNER_SPRING, INNER_TOP, -1 if side < 0 else 1)
        local_x = leaf*(INNER_A-abs(px))
        outline.append((local_x, pz))
    add_extruded_polygon("Battente scolpito | sinistro" if side < 0 else "Battente scolpito | destro",
                         outline, -0.27, 0.23, iron, bevel=0.03, parent=root)
    # Recessed plates sit proud of the door leaf and catch the orange edge light.
    for row, zc in enumerate((1.60, 3.00, 4.42)):
        add_box(f"Pannello ribassato {side:+d}.{row+1}", (leaf*1.31, -0.292, zc),
                (1.78, 0.075, 1.13), stone_dark, 0.12, parent=root)
        add_box(f"Listello interno pannello {side:+d}.{row+1}", (leaf*1.31, -0.338, zc),
                (1.52, 0.036, 0.87), bronze, 0.075, parent=root)
        add_box(f"Campo d'ombra pannello {side:+d}.{row+1}", (leaf*1.31, -0.361, zc),
                (1.37, 0.028, 0.71), iron, 0.06, parent=root)
    # Four heavy cross-straps, capped with forged rivets.
    for band_i, zc in enumerate((1.03, 2.47, 4.05, 5.52)):
        width = INNER_A - 0.28
        add_box(f"Spranga di rinforzo {side:+d}.{band_i+1}",
                (leaf*width*0.5, -0.385, zc), (width, 0.145, 0.17), bronze, 0.035, parent=root)
        add_box(f"Battuta in ferro {side:+d}.{band_i+1}",
                (leaf*width*0.5, -0.474, zc), (width-0.12, 0.055, 0.07), iron, 0.018, parent=root)
        for col in range(7):
            lx = leaf*(0.20 + col*(width-0.40)/6)
            add_uv_sphere(f"Ribattino {side:+d}.{band_i+1}.{col+1}",
                          (lx, -0.515, zc), (0.052, 0.033, 0.052), gold,
                          segments=12, rings=8, parent=root)
    # Raised stile ribs frame each leaf; diagonal tracery follows the pointed top.
    for xlocal in (leaf*0.16, leaf*(INNER_A-0.23)):
        add_box(f"Costola verticale del battente {side:+d}",
                (xlocal, -0.37, 3.05), (0.105, 0.13, 4.0), bronze, 0.035, parent=root)
        add_box(f"Filo d'acciaio della costola {side:+d}",
                (xlocal, -0.45, 3.05), (0.035, 0.035, 3.84), gold, 0.01, parent=root)
    top_trim = []
    for j in range(38):
        t = t_stop*j/37
        px, pz = arch_point(t, INNER_A, INNER_SPRING, INNER_TOP, -1 if side < 0 else 1)
        top_trim.append((leaf*(INNER_A-abs(px)), -0.405, pz-0.095))
    add_curve(f"Profilo gotico inciso sul battente {side:+d}", top_trim, 0.035, gold,
              parent=root, resolution=3)
    # Large demon-mask bosses and a concentric forged halo on each door.
    boss_x = leaf*1.31
    add_torus(f"Aureola del mascherone {side:+d}", (boss_x, -0.56, 3.37),
              0.63, 0.055, gold, rotation=(math.pi/2,0,0), parent=root)
    add_torus(f"Corona interna del mascherone {side:+d}", (boss_x, -0.565, 3.37),
              0.47, 0.025, bronze, rotation=(math.pi/2,0,0), parent=root)
    add_skull_relief("Mascherone infernale del battente", boss_x, -0.53, 3.36,
                     1.28, parent=root, skull_mat=bone, glow=True)
    # Smaller roundels, decorative radial spokes and a central hanging ring.
    for zc in (1.66, 5.08):
        add_torus(f"Rosone minore {side:+d} @ {zc:.1f}", (leaf*1.31, -0.46, zc),
                  0.23, 0.035, gold, rotation=(math.pi/2,0,0), parent=root)
        add_ico(f"Borchia del rosone {side:+d}", (leaf*1.31, -0.50, zc),
                (0.11,0.08,0.11), bronze, subdivisions=2, parent=root)
        for k in range(8):
            a = k*math.tau/8
            add_rod("Raggio del rosone", (leaf*1.31+math.cos(a)*0.11,-0.49,zc+math.sin(a)*0.11),
                    (leaf*1.31+math.cos(a)*0.19,-0.49,zc+math.sin(a)*0.19),
                    0.012, gold, 6, parent=root)
    handle_x = leaf*(INNER_A-0.46)
    add_torus(f"Anello di presa {side:+d}", (handle_x, -0.57, 3.05), 0.16, 0.038,
              bronze, rotation=(math.pi/2,0,0), parent=root)
    add_uv_sphere(f"Chiodo del battente {side:+d}", (handle_x, -0.55, 3.05),
                  (0.07,0.05,0.07), gold, segments=12, rings=8, parent=root)
    # Three massive strap hinges at the outer edge.
    for h_i, zc in enumerate((1.40, 3.52, 5.70)):
        add_box(f"Bandella del cardine {side:+d}.{h_i+1}",
                (leaf*0.13, -0.50, zc), (0.58, 0.095, 0.14), iron, 0.025, parent=root)
        add_cylinder(f"Barilotto del cardine {side:+d}.{h_i+1}",
                     (leaf*0.025, -0.53, zc), 0.105, 0.78, bronze, vertices=16,
                     bevel=0.02, parent=root)
        add_torus(f"Anello del cardine {side:+d}.{h_i+1}",
                  (leaf*0.025, -0.53, zc), 0.14, 0.025, gold,
                  parent=root, rotation=(0,0,0))

# -----------------------------------------------------------------------------
# The burning threshold: ragged flames, inner lava, and hanging chains
# -----------------------------------------------------------------------------
use_collection("04 • Oltretomba | fuoco, lava, catene")

def flame_shape(name, x, y, z, width, height, material, lean=0.0):
    outline = [
        (x-width*0.48, z),
        (x-width*0.40, z+height*0.19),
        (x-width*0.22, z+height*0.39),
        (x-width*0.31+lean*0.3, z+height*0.59),
        (x-width*0.12+lean*0.55, z+height*0.78),
        (x+lean, z+height),
        (x+width*0.10+lean*0.6, z+height*0.69),
        (x+width*0.34+lean*0.3, z+height*0.52),
        (x+width*0.45, z+height*0.28),
        (x+width*0.48, z),
    ]
    return add_extruded_polygon(name, outline, y, y+0.10, material, bevel=0.01)

# Hot fissures inside the throat of the arch.
for i in range(7):
    xx = -2.18 + i*0.72
    flame_shape(f"Lingua di fuoco nella soglia {i+1}", xx, 0.96,
                0.80 + random.uniform(0.0,0.35), random.uniform(0.30,0.68),
                random.uniform(1.55,3.15), random.choice([flame_orange, flame_red, ember]),
                random.uniform(-0.22,0.22))
    if i in (1,3,5):
        flame_shape(f"Nucleo d'oro della fiamma {i+1}", xx+0.04, 0.83, 0.82,
                    0.19, random.uniform(1.0,1.8), ember, random.uniform(-0.12,0.12))
# A broad dark, broken lava shelf at the far side of the threshold.
for i in range(5):
    xx = -2.25 + i*1.12
    add_ico(f"Crosta di lava {i+1}", (xx, 0.70, 0.82),
            (random.uniform(0.40,0.75),0.35,random.uniform(0.12,0.25)), lava_mat, subdivisions=1)

# Ornate iron chains: alternating vertical/sideways links hanging from the leaf heads.
for side in (-1, 1):
    for strand in range(2):
        x = side*(2.92 + strand*0.22)
        for i in range(15):
            z = 7.76 - i*0.33
            y = -0.46 + (0.08 if strand else 0.0)
            rot = (math.pi/2, 0, 0) if i % 2 == 0 else (math.pi/2, 0, math.pi/2)
            add_torus(f"Catena della soglia {side:+d}.{strand+1}.{i+1:02d}",
                      (x, y, z), 0.12, 0.032, iron, rotation=rot,
                      major_segments=16, minor_segments=6)
    # A small broken chain drapes diagonally over the threshold.
    pts = [(side*2.85,-0.58,7.65),(side*2.55,-0.72,7.32),
           (side*2.30,-0.82,7.02),(side*2.14,-0.88,6.82)]
    add_curve(f"Catena spezzata | tratto {side:+d}", pts, 0.06, bronze, resolution=3)

# -----------------------------------------------------------------------------
# Paired stone wraiths: hooded damned souls, torn wings and restrained chains
# -----------------------------------------------------------------------------
use_collection("03 • Sculture | anime e guardiani")

def add_robe_mesh(name, cx, cy, z_base, ringspec, material):
    n = 12
    verts = []
    faces = []
    for z, rx, ry, offset_x in ringspec:
        for j in range(n):
            a = math.tau*j/n
            verts.append((cx + offset_x + rx*math.cos(a), cy + ry*math.sin(a), z))
    for r in range(len(ringspec)-1):
        for j in range(n):
            a = r*n+j
            b = r*n+(j+1)%n
            faces.append((a,b,b+n,a+n))
    faces.append(tuple(range(n-1,-1,-1)))
    faces.append(tuple(range((len(ringspec)-1)*n, len(ringspec)*n)))
    mesh = bpy.data.meshes.new(name + " | drappeggio")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    ACTIVE.objects.link(obj)
    for p in mesh.polygons:
        p.use_smooth = True
    return obj


def guardian(side):
    x = side*4.58
    y = -1.10
    out = -1 if side < 0 else 1
    label = "Custode dell'Antinferno | sinistro" if side < 0 else "Custode dell'Antinferno | destro"
    # Pedestal: carved, battered, and pinned to the approach.
    add_box(label + " | basamento", (x, y, 0.66), (1.26, 1.12, 0.74), stone_light, 0.09)
    add_box(label + " | fascia bronzea", (x, y-0.58, 0.90), (1.19, 0.075, 0.13), bronze, 0.025)
    add_box(label + " | dado", (x, y, 1.18), (0.96, 0.87, 0.30), stone_dark, 0.055)
    add_ico(label + " | teschio del piede", (x, y-0.46, 0.70),
            (0.23,0.12,0.22), bone_shadow, subdivisions=1)

    # Cloak / shroud built as a smoothed ring loft, not a primitive cone.
    add_robe_mesh(label + " | manto di pietra", x, y, 1.30,
                  [(1.27,0.37,0.32,0.00),(1.40,0.53,0.38,0.00),
                   (1.72,0.48,0.33,0.00),(2.15,0.39,0.30,0.00),
                   (2.55,0.31,0.27,0.00),(2.93,0.39,0.31,0.00),
                   (3.12,0.35,0.30,0.00)], stone)
    # Hood shell and deep face opening.
    add_ico(label + " | cappuccio", (x,y-0.02,3.43), (0.48,0.39,0.60), bone_shadow, subdivisions=2)
    add_ico(label + " | ombra del volto", (x,y-0.355,3.42), (0.31,0.11,0.40), void_mat, subdivisions=2)
    add_skull_relief(label + " | volto dannato", x, y-0.43, 3.40, 0.77,
                     skull_mat=bone, glow=True)
    # Hood rim arcs and a small crown of fractured stone points.
    for s in (-1,1):
        add_curve(label + " | bordo del cappuccio",
                  [(x+s*0.31,y-0.43,3.77),(x+s*0.40,y-0.39,3.53),
                   (x+s*0.32,y-0.43,3.25)], 0.055, stone_light, resolution=3)
        add_cone(label + " | spina del cappuccio", (x+s*0.19,y-0.18,4.00),
                 0.12,0.0,0.42, stone_light, vertices=7)
    # Arms folded in supplication, with knuckled hands and visible bone fingers.
    shoulders = [(x-out*0.32,y-0.02,2.95),(x+out*0.32,y-0.02,2.95)]
    elbows = [(x-out*0.48,y-0.28,2.57),(x+out*0.48,y-0.28,2.56)]
    wrists = [(x-out*0.12,y-0.52,2.35),(x+out*0.12,y-0.52,2.34)]
    for i in range(2):
        add_rod(label + " | braccio", shoulders[i], elbows[i], 0.14, stone_light, vertices=12)
        add_rod(label + " | avambraccio", elbows[i], wrists[i], 0.11, bone_shadow, vertices=10)
        add_uv_sphere(label + " | mano", wrists[i], (0.13,0.10,0.15), bone, segments=12, rings=8)
        direction = -1 if i == 0 else 1
        for f in range(3):
            start = (wrists[i][0]+direction*(f-1)*0.045, wrists[i][1]-0.03, wrists[i][2]-0.06)
            end = (start[0]+direction*0.025, start[1]-0.015, start[2]-0.19)
            add_rod(label + " | falange", start, end, 0.024, bone, vertices=7)
    # Tattered bat-wing relief on the outer side; slender ribs emerge from the shroud.
    wing_y = -0.81
    wing_outline = [
        (x+out*0.23,2.98),(x+out*0.48,3.25),(x+out*0.76,3.18),
        (x+out*1.24,3.05),(x+out*1.06,3.70),(x+out*1.52,4.02),
        (x+out*1.19,4.45),(x+out*1.34,5.05),(x+out*0.88,4.75),
        (x+out*0.53,4.18),(x+out*0.37,3.55)
    ]
    add_extruded_polygon(label + " | ala di pietra", wing_outline,
                         wing_y, wing_y+0.13, stone_dark, bevel=0.02)
    rib_tips = [(x+out*1.34,5.05),(x+out*1.19,4.45),(x+out*1.52,4.02),
                (x+out*1.06,3.70),(x+out*1.24,3.05)]
    for ri, tip in enumerate(rib_tips):
        add_curve(label + f" | nervatura dell'ala {ri+1}",
                  [(x+out*0.27,wing_y-0.04,3.07),
                   (x+out*0.52,wing_y-0.06,3.55+ri*0.05),
                   (tip[0],wing_y-0.04,tip[1])],
                  0.035, stone_light, resolution=3)
    # Torn cloak folds / shroud tails.
    for i in range(5):
        xx = x + (i-2)*0.12
        add_curve(label + " | piega del manto",
                  [(xx,y-0.36,2.92),(xx+(i-2)*0.04,y-0.39,2.35),
                   (xx+(i-2)*0.10,y-0.36,1.40),(xx+(i-2)*0.15,y-0.38,1.24)],
                  0.025, stone_light if i%2 else stone_dark, resolution=2)
    # Hanging broken links grasped by the outside hand.
    for i in range(8):
        zc = 2.30 - i*0.25
        lx = x + out*(0.55 + i*0.055)
        add_torus(label + f" | anello della catena {i+1}",
                  (lx,y-0.58,zc), 0.105,0.026,iron,
                  rotation=(math.pi/2,0,0) if i%2==0 else (math.pi/2,0,math.pi/2),
                  major_segments=14,minor_segments=6)

for side in (-1,1):
    guardian(side)

# Skull-faced braziers and torch sconces warm the carved masonry.
use_collection("04 • Oltretomba | fuoco, lava, catene")
for side in (-1,1):
    x = side*3.92
    add_box(f"Mensola del braciere {side:+d}", (x,-1.05,5.62), (0.66,0.50,0.23), stone_light, 0.055)
    add_cylinder(f"Stelo del braciere {side:+d}", (x,-1.10,6.02), 0.105,0.68,
                 iron, vertices=12, bevel=0.02)
    add_torus(f"Anello inferiore del braciere {side:+d}", (x,-1.10,5.82),
              0.21,0.035,bronze, major_segments=16, minor_segments=6)
    add_ico(f"Coppa cranica del braciere {side:+d}", (x,-1.10,6.38),
            (0.40,0.30,0.22), bronze, subdivisions=1)
    add_skull_relief(f"Maschera del braciere {side:+d}", x,-1.40,6.42,0.54,
                     skull_mat=bone_shadow,glow=False)
    for fi in range(3):
        flame_shape(f"Fiamma del braciere {side:+d}.{fi+1}",
                    x+(fi-1)*0.13,-1.14,6.48,0.23,random.uniform(0.55,1.15),
                    [flame_orange,ember,flame_red][fi],lean=random.uniform(-0.10,0.10))
    # Point lights are warm but restrained; the portal remains the focal point.
    ld = bpy.data.lights.new(f"Luce del braciere {side:+d}", "POINT")
    ld.energy = 190
    ld.color = (1.0,0.16,0.025)
    ld.shadow_soft_size = 0.55
    lo = bpy.data.objects.new(f"Luce del braciere {side:+d}", ld)
    ACTIVE.objects.link(lo)
    lo.location = (x,-1.5,6.9)

# -----------------------------------------------------------------------------
# Surface accents: cracks on the stones, rosettes and tiny damned faces
# -----------------------------------------------------------------------------
use_collection("01 • Architettura | basalto e conci")
crack_mat = stone_dark
# Delicate branching cracks hand-etched into selected front stones.
for i, (x,z) in enumerate([(-4.75,7.65),(-4.10,3.78),(4.80,8.55),(4.12,2.75),
                           (-5.15,5.46),(5.03,6.12),(-4.32,9.22),(4.44,4.42)]):
    y = -0.56
    s = -1 if i%2 else 1
    add_curve(f"Fenditura nel concio {i+1}",
              [(x,y,z+0.34),(x+s*0.08,y-0.012,z+0.13),(x-s*0.04,y-0.014,z-0.03),
               (x+s*0.17,y-0.01,z-0.21),(x+s*0.21,y-0.01,z-0.34)],
              0.013, stone_dark, resolution=1)
    add_curve(f"Ramo della fenditura {i+1}",
              [(x-s*0.04,y-0.014,z-0.03),(x-s*0.22,y-0.01,z+0.03),
               (x-s*0.29,y-0.01,z+0.17)], 0.010, stone_dark, resolution=1)

# Small carved skulls mounted in the lower arch spandrels, like votive warnings.
for side in (-1,1):
    for j, zc in enumerate((6.10,7.25)):
        xx = side*(3.15 - j*0.35)
        add_torus(f"Aureola votiva {side:+d}.{j+1}", (xx,-1.0,zc),
                  0.22,0.026,gold,rotation=(math.pi/2,0,0),major_segments=20,minor_segments=6)
        add_skull_relief(f"Teschio votivo {side:+d}.{j+1}",xx,-0.98,zc,0.43,
                         skull_mat=bone_shadow,glow=(j==1))

# -----------------------------------------------------------------------------
# Backdrop, infernal atmosphere, camera and cinematic light
# -----------------------------------------------------------------------------
use_collection("04 • Oltretomba | fuoco, lava, catene")
# Low silhouette of broken basalt teeth behind the monument.
for side in (-1,1):
    for i in range(4):
        x = side*(6.8 + i*1.05)
        h = random.uniform(4.0,8.0)
        add_cone(f"Dente di basalto lontano {side:+d}.{i+1}",
                 (x,2.4, h*0.5-0.15), random.uniform(0.55,0.95), 0.0, h,
                 stone_dark, vertices=5)
# A dim blood-red atmospheric plane behind the far silhouette.
backdrop_mat = emission_material("Orizzonte | cenere rossa", (0.028,0.004,0.012), 0.45)
add_box("Fondale dell'abisso", (0,5.2,5.8), (60,0.18,28), backdrop_mat, 0.0)

# Smoke-like curls rising from the broken lintel and the burning threshold.
smoke_mat = principled_material("Fumo | cenere fredda", (0.11,0.075,0.10,1), 0.0, 0.92,
                                3.0,0.12,0.07,(0.025,0.018,0.04,1),(0.24,0.15,0.16,1))
for side in (-1,1):
    for i in range(3):
        x = side*(2.8 + i*0.58)
        z0 = 7.9 + i*0.2
        pts = [(x,-0.16,z0),(x+side*0.20,-0.05,z0+0.45),
               (x-side*0.12,0.05,z0+0.92),(x+side*0.30,0.02,z0+1.35),
               (x+side*0.54,0.11,z0+1.65)]
        add_curve(f"Vapore d'ombra {side:+d}.{i+1}", pts,
                  0.025 + i*0.008, smoke_mat, resolution=3)

use_collection("05 • Scena | terreno, camera, luci")

def add_area_light(name, location, target, energy, color, size, shape="DISK"):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = shape
    data.size = size
    obj = bpy.data.objects.new(name, data)
    ACTIVE.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()
    return obj

# Cool moonlight carves the basalt; hot light leaks from inside the gate.
add_area_light("Luna | luce principale", (-8.0,-11.0,15.0), (0,0,5.4),
               1850, (0.60,0.72,1.0), 8.0)
add_area_light("Riflesso cremisi | lato destro", (8.0,-7.0,8.0), (0,0,4.7),
               1300, (1.0,0.23,0.10), 7.0)
add_area_light("Luce di taglio | blu abissale", (3.0,3.0,12.5), (0,0,6.0),
               2100, (0.15,0.28,1.0), 6.0)
add_area_light("Luce alta | pietra e frontone", (-1.0,1.0,17.0), (0,0,7.0),
               950, (0.72,0.54,0.35), 5.5)

for name, location, energy, color, radius in [
    ("Cuore della soglia", (0,1.45,3.2), 850, (1.0,0.075,0.018), 1.9),
    ("Lava riflessa sui gradini", (0,-2.3,1.1), 320, (1.0,0.12,0.018), 2.2),
    ("Rimbalzo rosso sulle ali", (-4.2,-1.5,3.4), 150, (0.9,0.06,0.018), 1.3),
    ("Rimbalzo rosso sulle ali | dx", (4.2,-1.5,3.4), 150, (0.9,0.06,0.018), 1.3),
]:
    data = bpy.data.lights.new(name,"POINT")
    data.energy = energy
    data.color = color
    data.shadow_soft_size = radius
    obj = bpy.data.objects.new(name,data)
    ACTIVE.objects.link(obj)
    obj.location = location

# Portrait camera, slightly off-axis for visible jamb depth and open door thickness.
cam_data = bpy.data.cameras.new("Camera | soglia dei dannati")
cam = bpy.data.objects.new("Camera | soglia dei dannati",cam_data)
ACTIVE.objects.link(cam)
cam.location = (8.2,-29.0,13.1)
target = Vector((0.0,-0.10,6.0))
cam.rotation_euler = (target-Vector(cam.location)).to_track_quat("-Z","Y").to_euler()
cam_data.lens = 50
cam_data.dof.use_dof = True
cam_data.dof.focus_object = None
cam_data.dof.focus_distance = (target-Vector(cam.location)).length
cam_data.dof.aperture_fstop = 9.0
scene.camera = cam

# Cycles CPU is deterministic and works without a GPU; denoising preserves small carvings.
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 48
scene.cycles.preview_samples = 16
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPENIMAGEDENOISE"
scene.render.resolution_x = 1500
scene.render.resolution_y = 1740
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = False
scene.render.filepath = PREVIEW_PATH
scene.render.image_settings.color_depth = "8"
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0
scene.render.resolution_percentage = 100

# Subtle fog glow on the brass, eyes and lava.
scene.use_nodes = True
nt = scene.node_tree
nt.nodes.clear()
rl = nt.nodes.new("CompositorNodeRLayers")
rl.location = (-300,0)
glow = nt.nodes.new("CompositorNodeGlare")
glow.glare_type = "FOG_GLOW"
glow.quality = "HIGH"
glow.threshold = 1.35
glow.size = 7
glow.location = (0,0)
comp = nt.nodes.new("CompositorNodeComposite")
comp.location = (230,0)
nt.links.new(rl.outputs["Image"],glow.inputs["Image"])
nt.links.new(glow.outputs["Image"],comp.inputs["Image"])

# Metadata for anyone inspecting the .blend.
scene["Opera"] = "La Porta dell'Inferno — interpretazione originale da Inferno, Canto III"
scene["Iscrizione"] = "Lasciate ogni speranza, voi ch'entrate"
scene["Nota"] = "Modello procedurale: architettura, battenti, rilievi e materiali sono modificabili."
scene["Dimensioni indicative"] = "circa 12,4 x 13,0 x 5,5 unità Blender"

# Make the project pleasant to inspect immediately after opening in Blender.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.region_3d.view_location = (0.0,-0.1,5.9)
            space.region_3d.view_distance = 23.5
            space.region_3d.view_rotation = cam.rotation_euler.to_quaternion()
            space.region_3d.view_perspective = "PERSP"
            space.shading.type = "SOLID"
            space.shading.light = "STUDIO"
            space.shading.color_type = "MATERIAL"
            space.shading.show_cavity = True
            space.shading.cavity_type = "BOTH"
            space.shading.curvature_ridge_factor = 1.25
            space.shading.curvature_valley_factor = 1.0

# Pack fonts and any future image datablocks so the .blend is self-contained.
try:
    bpy.ops.file.pack_all()
except Exception:
    pass
bpy.ops.object.select_all(action="DESELECT")
bpy.context.view_layer.objects.active = None
bpy.context.scene.cursor.location = (0,0,0)

# Save a full-quality Blender project, then render a lightweight preview image.
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
scene.render.resolution_percentage = 68
scene.cycles.samples = 22
scene.render.filepath = PREVIEW_PATH
bpy.ops.render.render(write_still=True)
# Restore production settings and save once more so opening the project is ready for a final render.
scene.render.resolution_percentage = 100
scene.cycles.samples = 48
scene.render.filepath = PREVIEW_PATH
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
print("Creato:", BLEND_PATH)
print("Anteprima:", PREVIEW_PATH)
print("Oggetti:", len(bpy.data.objects), " | Materiali:", len(bpy.data.materials))
