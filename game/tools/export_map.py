"""Esporta `porta_dell_inferno.blend` negli asset giocabili del videogioco.

Uso (dal repository):

    game/tools/export_map.sh

oppure, con un Python che abbia il modulo `bpy` 4.5:

    python game/tools/export_map.py --blend porta_dell_inferno.blend --out game/public

Il file .blend viene **solo letto**: non è mai modificato né salvato.

Produce in `--out`:

* `map.glb`        geometria visiva, unita per materiale (draw call ridotte);
* `collision.glb`  la stessa geometria semplificata, per la fisica del giocatore;
* `scene.json`     luci, punti di interesse, spawn, bounds, battenti, iscrizione;
* `heightmap.png`  altezza del terreno + mappa di calore (per la minimappa).

Coordinate: Blender è Z-up, il gioco è Y-up. Questo script converte già tutto
in coordinate di gioco `(x, z, -y)`; il gioco non deve più convertire nulla.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zlib
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Vector, bvhtree, noise

TOOL_DIR = Path(__file__).resolve().parent
GAME_DIR = TOOL_DIR.parent
ROOT = GAME_DIR.parent

# Materiali "attraversabili": fuoco, lava e bagliori non devono fermare il
# giocatore (nel gioco diventano zone di calore/danno, non muri).
WALK_THROUGH = (
    'Lava', 'Magma', 'Fiamma', 'Brace', 'Braci', 'Occhi',
    'Soglia | bagliore', 'Spaccature', 'Vetro del rosone',
)
# Geometria decorativa sostituita da particelle animate nel gioco.
PARTICLE_OBJECTS = ('Braci sospese', 'Cenere sospesa', 'Pioggia di cenere')

HINGE_PREFIX = 'Cardine del battente'
HINGE_NAMES = {
    'Cardine del battente sinistro': 'CardineBattenteSinistro',
    'Cardine del battente destro': 'CardineBattenteDestro',
}
INSCRIPTION = 'Avvertimento | Lasciate ogni speranza'
INSCRIPTION_NODE = 'Iscrizione'

# Bit di quantizzazione delle posizioni: 14 bit su 300 m ≈ 2 cm di passo.
POSITION_BITS = 14

# Risoluzione delle curve decorative dopo la conversione in mesh.
CURVE_RESOLUTION_U = 4
CURVE_BEVEL = 1

# Blender "Power" è in watt; three.js usa candele. Il fattore è deliberatamente
# piccolo: con ACES tone mapping il varco resta la sorgente dominante.
CANDELA_PER_WATT = 0.02


def log(*a):
    print('[export]', *a, flush=True)


# --------------------------------------------------------------------------- #
# Coordinate
# --------------------------------------------------------------------------- #
def to_game(v) -> list:
    """Blender (x, y, z) Z-up -> gioco (x, z, -y) Y-up."""
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(-float(v[1]), 4)]


def quat_to_game(q) -> list:
    """Quaternione Blender (w, x, y, z) -> gioco (x, z, -y, w)."""
    w, x, y, z = q
    return [round(float(x), 5), round(float(z), 5), round(-float(y), 5), round(float(w), 5)]


# --------------------------------------------------------------------------- #
# Classificazione
# --------------------------------------------------------------------------- #
def material_of(obj):
    for slot in obj.material_slots:
        if slot.material is not None:
            return slot.material
    return None


def is_volume_material(mat) -> bool:
    if mat is None or not mat.use_nodes:
        return False
    return any('VOLUME' in n.type for n in mat.node_tree.nodes)


def is_walk_through(mat) -> bool:
    return mat is not None and any(mat.name.startswith(p) for p in WALK_THROUGH)


def root_ancestor(obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj


def hinge_of(obj):
    """Restituisce l'empty-cardine da cui dipende l'oggetto, se c'è."""
    cur = obj
    while cur is not None:
        if cur.type == 'EMPTY' and cur.name.startswith(HINGE_PREFIX):
            return cur
        cur = cur.parent
    return None


# --------------------------------------------------------------------------- #
# Raccolta dati della scena (prima di toccare la geometria)
# --------------------------------------------------------------------------- #
def collect_lights(scene):
    lights = []
    for obj in scene.objects:
        if obj.type != 'LIGHT':
            continue
        lamp = obj.data
        pos = to_game(obj.matrix_world.translation)
        energy = float(lamp.energy)
        intensity = energy * CANDELA_PER_WATT
        entry = {
            'name': obj.name,
            'kind': lamp.type.lower(),
            'position': pos,
            'color': [round(float(c), 4) for c in lamp.color],
            'power_watt': round(energy, 1),
            'intensity': round(intensity, 3),
        }
        if lamp.type == 'POINT':
            entry['radius'] = round(float(lamp.shadow_soft_size), 3)
        elif lamp.type == 'AREA':
            entry['size'] = [round(float(lamp.size), 3), round(float(lamp.size_y), 3)]
            entry['quaternion'] = quat_to_game(obj.matrix_world.to_quaternion())
            # Un'area light di Blender diventa una point light nel gioco: la
            # potenza è ripartita, così i profili non bruciano.
            entry['intensity'] = round(intensity * 0.22, 3)
            entry['radius'] = round(max(float(lamp.size), 0.5), 3)
        elif lamp.type == 'SUN':
            entry['quaternion'] = quat_to_game(obj.matrix_world.to_quaternion())
        lights.append(entry)
    return lights


def collect_points_of_interest():
    """Le sette figure umane della scena diventano i sigilli da raccogliere."""
    verses = {
        'Pellegrino sulla via': (
            'Nel mezzo del cammin di nostra vita\nmi ritrovai per una selva oscura,\nché la diritta via era smarrita.',
            'Inferno I, 1-3',
        ),
        'Dannato inginocchiato sui gradini': (
            'Per me si va ne la città dolente,\nper me si va ne l\'etterno dolore,\nper me si va tra la perduta gente.',
            'Inferno III, 1-3',
        ),
        'Dannato curvo sul gradino': (
            'Fecemi la divina podestate,\nla somma sapïenza e \'l primo amore.',
            'Inferno III, 4-6',
        ),
        'Dannato che arranca sul selciato': (
            'Dinanzi a me non fuor cose create\nse non etterne, e io etterno duro.',
            'Inferno III, 7-8',
        ),
        'Anima in cammino 1': (
            'Lasciate ogne speranza, voi ch\'intrate.',
            'Inferno III, 9',
        ),
        'Anima in cammino 2': (
            'Quivi sospiri, pianti e alti guai\nrisonavan per l\'aere sanza stelle.',
            'Inferno III, 22-23',
        ),
        'Anima in cammino 3': (
            'Che sanza speme vivemo in disio.',
            'Inferno IV, 42',
        ),
    }
    pois = []
    for obj in bpy.data.objects:
        if obj.type != 'EMPTY' or not obj.name.startswith('Figura umana |'):
            continue
        label = obj.name.split('|', 1)[1].strip()
        verse, canto = verses.get(label, ('', ''))
        pois.append({
            'id': re.sub(r'\W+', '-', label).strip('-').lower(),
            'name': label,
            'position': to_game(obj.matrix_world.translation),
            'verse': verse,
            'canto': canto,
        })
    return pois


def collect_camera(scene):
    cam = scene.camera
    if cam is None:
        return None
    fwd = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
    return {
        'position': to_game(cam.matrix_world.translation),
        'forward': to_game(fwd),
        'lens_mm': round(float(cam.data.lens), 1),
    }


# --------------------------------------------------------------------------- #
# Heightmap + mappa di calore
# --------------------------------------------------------------------------- #
def write_png(path: Path, width: int, height: int, rows: list[bytes]):
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    raw = b''.join(b'\x00' + row for row in rows)
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw, 9))
           + chunk(b'IEND', b''))
    path.write_bytes(png)


def build_heightmap(scene, out_dir: Path, region, resolution=(768, 384), lights=None):
    """Altezza del terreno (16 bit) + calore delle braci, per la minimappa."""
    depsgraph = scene.view_layers[0].depsgraph
    trees = []
    for obj in scene.objects:
        if obj.type == 'MESH' and obj.name.startswith('Terreno vulcanico'):
            trees.append(bvhtree.BVHTree.FromObject(obj, depsgraph))
    if not trees:
        log('nessun terreno trovato: heightmap saltata')
        return None
    x0, x1, y0, y1 = region
    w, h = resolution
    z_min, z_max = -4.0, 58.0
    z_span = z_max - z_min

    warm = [(Vector((l['position'][0], -l['position'][2], l['position'][1])),
             max(0.0, l['color'][0] - l['color'][2]), l['power_watt'])
            for l in (lights or [])]

    rows = []
    t0 = time.time()
    for j in range(h):
        row = bytearray()
        y = y1 - (j + 0.5) * (y1 - y0) / h
        for i in range(w):
            x = x0 + (i + 0.5) * (x1 - x0) / w
            best = None
            for tree in trees:
                hit = tree.ray_cast(Vector((x, y, 70.0)), Vector((0.0, 0.0, -1.0)), 90.0)
                if hit and hit[0] is not None:
                    z = hit[0].z
                    if best is None or z > best:
                        best = z
            if best is None:
                row += bytes((0, 0, 0, 0))
                continue
            t = min(1.0, max(0.0, (best - z_min) / z_span))
            q = int(round(t * 65535))
            heat = 0.0
            for p, warmth, power in warm:
                d2 = (p.x - x) ** 2 + (p.y - y) ** 2 + 4.0
                heat += warmth * power / d2
            hb = min(255, int(heat * 0.55))
            row += bytes(((q >> 8) & 0xFF, q & 0xFF, hb, 255))
        rows.append(bytes(row))
    path = out_dir / 'heightmap.png'
    write_png(path, w, h, rows)
    log(f'heightmap: {path.name} {w}x{h} in {time.time() - t0:.1f}s')
    return {
        'file': 'heightmap.png',
        'width': w,
        'height': h,
        'region': [round(v, 2) for v in (x0, y0, x1, y1)],  # coords di gioco (x, z)
        'zRange': [z_min, z_max],
    }


# --------------------------------------------------------------------------- #
# Preparazione della geometria
# --------------------------------------------------------------------------- #
def prepare_geometry(scene):
    """Ripulisce la scena e raggruppa gli oggetti per materiale/cardine."""
    # I battenti nel .blend sono socchiusi di ~25°: belli in render, ma nel
    # gioco il varco deve restare chiuso finché tutte le anime non sono state
    # ascoltate. Chiuderli qui, prima di unire e applicare le trasformate,
    # evita di dover gestire la gerarchia più avanti.
    hinges = [o for o in scene.objects
              if o.type == 'EMPTY' and o.name.startswith(HINGE_PREFIX)]
    for o in hinges:
        o.rotation_euler.z = 0.0
    if hinges:
        scene.view_layers[0].update()
        log(f'battenti chiusi: {len(hinges)} cardini a 0°')

    drop = []
    for obj in list(scene.objects):
        if obj.type in ('LIGHT', 'CAMERA'):
            drop.append(obj)
        elif obj.type == 'EMPTY' and not obj.name.startswith(HINGE_PREFIX):
            drop.append(obj)
        elif obj.type == 'EMPTY':
            pass
        else:
            mat = material_of(obj)
            if is_volume_material(mat):
                drop.append(obj)
            elif any(obj.name.startswith(p) for p in PARTICLE_OBJECTS):
                drop.append(obj)
    for obj in drop:
        bpy.data.objects.remove(obj, do_unlink=True)
    log(f'rimossi {len(drop)} oggetti (luci, camere, volumi, particelle statiche)')

    # Le curve decorative (viticci, catene, profili incisi) nascono con 12
    # sottopunti per tratto: nel gioco bastano molti meno poligoni.
    for o in scene.objects:
        if o.type == 'CURVE':
            o.data.resolution_u = min(int(o.data.resolution_u), CURVE_RESOLUTION_U)
            o.data.bevel_resolution = min(int(o.data.bevel_resolution), CURVE_BEVEL)

    # Curve e testo -> mesh, così il modificatore di smusso viene applicato.
    convertible = [o for o in scene.objects if o.type in ('CURVE', 'FONT')]
    if convertible:
        bpy.ops.object.select_all(action='DESELECT')
        for o in convertible:
            o.select_set(True)
        bpy.context.view_layer.objects.active = convertible[0]
        bpy.ops.object.convert(target='MESH')
        log(f'convertite {len(convertible)} curve/testo in mesh')

    # Le primitive condivise (le riutilizza il generatore per restare leggero)
    # non accettano trasformate o modificatori applicati: mesh single-user.
    shared = 0
    for o in scene.objects:
        if o.type == 'MESH' and o.data.users > 1:
            o.data = o.data.copy()
            shared += 1
    log(f'{shared} mesh condivise rese single-user')

    # Niente gerarchie residue (tranne i cardini): geometria in spazio mondo.
    bpy.ops.object.select_all(action='DESELECT')
    movable = [o for o in scene.objects if o.type == 'MESH' and hinge_of(o) is None]
    for o in movable:
        o.select_set(True)
    bpy.context.view_layer.objects.active = movable[0]
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    log(f'scollegati {len(movable)} oggetti dai genitori (trasformata conservata)')

    bpy.ops.object.select_all(action='DESELECT')
    all_mesh = [o for o in scene.objects if o.type == 'MESH']
    for o in all_mesh:
        o.select_set(True)
    bpy.context.view_layer.objects.active = all_mesh[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    log(f'applicate le trasformazioni a {len(all_mesh)} mesh')

    # Le mesh condivise (le piccole primitive riutilizzate) non possono ricevere
    # un modificatore applicato: se ne hanno uno, la mesh diventa single-user.
    shared = 0
    for o in all_mesh:
        if o.modifiers and o.data.users > 1:
            o.data = o.data.copy()
            shared += 1
    if shared:
        log(f'{shared} mesh condivise rese single-user (avevano modificatori)')

    t0 = time.time()
    bpy.ops.object.modifier_apply(modifier='')
    log(f'applicati i modificatori a {len(all_mesh)} mesh in {time.time() - t0:.1f}s')

    groups = defaultdict(list)
    for obj in scene.objects:
        if obj.type != 'MESH':
            continue
        mat = material_of(obj)
        key_mat = mat.name if mat else 'SenzaMateriale'
        hinge = hinge_of(obj)
        if obj.name == INSCRIPTION:
            groups[('__special__', INSCRIPTION_NODE)].append(obj)
        elif hinge is not None:
            groups[(HINGE_NAMES[hinge.name], key_mat)].append(obj)
        else:
            groups[('__static__', key_mat)].append(obj)
    return groups


def safe_name(kind: str, key: str) -> str:
    if kind == '__special__':
        return key
    clean = re.sub(r'[^A-Za-z0-9]+', '', key)
    if kind.startswith('Cardine'):
        return f'{kind}__{clean}'[:60]
    base = re.sub(r'[^A-Za-z0-9._ -]+', '', key).strip()
    return base[:48] or clean[:48] or 'Materiale'


def join_group(kind: str, key: str, objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    active = objects[0]
    bpy.context.view_layer.objects.active = active
    if len(objects) > 1:
        bpy.ops.object.join()
        active = bpy.context.view_layer.objects.active
    name = safe_name(kind, key)
    active.name = name
    active.data.name = name
    return name, active


def build_merged(scene):
    groups = prepare_geometry(scene)
    static_names, hinge_names = [], []
    kept = {}
    for (kind, key), objects in sorted(groups.items()):
        count = len(objects)
        name, active = join_group(kind, key, objects)
        kept[name] = {
            'kind': 'battente' if kind.startswith('Cardine') else (
                'iscrizione' if kind == '__special__' else 'statico'),
            'hinge': kind if kind.startswith('Cardine') else None,
            'material': (material_of(active).name
                         if material_of(active) is not None else key),
            'objects': count,
            'tris': count_triangles(active),
        }
        (hinge_names if kind.startswith('Cardine') else static_names).append(name)
    log(f'unite {len(groups)} mesh per materiale/cardine')
    return kept, static_names, hinge_names


def total_tris(scene) -> int:
    return sum(len(o.data.polygons) for o in scene.objects if o.type == 'MESH')



# --------------------------------------------------------------------------- #
# Colore per vertice: AO, cenere e riflesso del fuoco
# --------------------------------------------------------------------------- #
# I materiali di Blender sono procedurali e le mesh non hanno UV: il dettaglio
# non può viaggiare nel glTF come texture. Lo si cuoce quindi nel colore per
# vertice (COLOR_0), che three.js moltiplica sul diffuse.
AO_DIRECTIONS = (
    (0.8165, 0.0, 0.5774), (-0.8165, 0.0, 0.5774),
    (0.4082, 0.7071, 0.5774), (-0.4082, 0.7071, 0.5774),
    (0.4082, -0.7071, 0.5774), (-0.4082, -0.7071, 0.5774),
)


def tangent_basis(n):
    a = Vector((0.0, 0.0, 1.0)) if abs(n.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    t = n.cross(a).normalized()
    b = n.cross(t)
    return t, b


def scene_bvh(meshes):
    """Un solo BVH con tutta la geometria solida, per l'occlusione ambientale."""
    verts, faces = [], []
    offset = 0
    for obj in meshes:
        me = obj.data
        mw = obj.matrix_world
        me.calc_loop_triangles()
        verts.extend(mw @ v.co for v in me.vertices)
        for tri in me.loop_triangles:
            faces.append([tri.vertices[0] + offset,
                          tri.vertices[1] + offset,
                          tri.vertices[2] + offset])
        offset += len(me.vertices)
    log(f'BVH per AO: {len(verts)} vertici, {len(faces)} triangoli')
    return bvhtree.BVHTree.FromPolygons(verts, faces)




def count_triangles(obj) -> int:
    me = obj.data
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def enforce_triangle_budget(scene, budget, protect_below=3000):
    """Riduce la geometria pesante restando sotto un numero di triangoli."""
    meshes = [o for o in scene.objects if o.type == 'MESH']
    counts = {o: count_triangles(o) for o in meshes}
    total = sum(counts.values())
    log(f'triangoli reali (glTF): {total} su {len(meshes)} mesh')
    if total <= budget:
        return total
    flexible = {o: c for o, c in counts.items() if c > protect_below}
    flex_total = sum(flexible.values())
    keep = total - flex_total
    allowed = max(flex_total * 0.05, budget - keep)
    t0 = time.time()
    for obj, tris in flexible.items():
        ratio = max(0.06, min(1.0, allowed / flex_total))
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new('lod', 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier='lod')
    after = sum(count_triangles(o) for o in meshes)
    log(f'LOD: {total} -> {after} triangoli (budget {budget}) in {time.time() - t0:.1f}s')
    return after

def bake_vertex_colors(scene, lights, keep, ao_rays=6, ao_distance=1.15):
    solids = [o for o in scene.objects
              if o.type == 'MESH' and not is_walk_through(material_of(o))]
    tree = scene_bvh(solids)

    # Luci calde: alimentano la tinta di rimbalzo del fuoco.
    warm = [(Vector(l['position']),
             max(0.0, l['color'][0] - l['color'][2]),
             l['power_watt']) for l in lights]

    t0 = time.time()
    total = 0
    for obj in scene.objects:
        if obj.type != 'MESH':
            continue
        me = obj.data
        info = keep.get(obj.name, {})
        emissive = info.get('kind') == 'battente' and 'Occhi' in info.get('material', '')
        for old in list(me.color_attributes):
            me.color_attributes.remove(old)
        attr = me.color_attributes.new('Col', type='FLOAT_COLOR', domain='POINT')
        # Senza attributo attivo l'exporter lo scrive su COLOR_1, che three.js
        # non usa come vertexColors.
        me.color_attributes.active_color = attr
        mw = obj.matrix_world
        rays = AO_DIRECTIONS[:max(1, min(len(AO_DIRECTIONS), ao_rays))]
        for i, v in enumerate(me.vertices):
            w = mw @ v.co
            n = (mw.to_3x3() @ v.normal).normalized()
            # variazione di tono a bassa frequenza: niente superfici piatte
            tone = 0.86 + 0.28 * (0.5 + 0.5 * noise.noise(Vector((w.x, w.y, w.z)) * 1.7))
            # cenere sulle facce esposte verso l'alto
            up = max(0.0, n.z)
            ash = 1.0 + 0.16 * up * (0.5 + 0.5 * noise.noise(Vector((w.x, w.y, w.z)) * 6.0))
            # fuliggine nelle cavità: occlusione ambientale reale
            if ao_rays and not emissive:
                t, b = tangent_basis(n)
                origin = w + n * 0.02
                free = 0
                for dx, dy, dz in rays:
                    d = (t * dx + b * dy + n * dz).normalized()
                    hit = tree.ray_cast(origin, d, ao_distance)
                    if hit[0] is None:
                        free += 1
                occ = free / len(rays)
                shade = 0.42 + 0.58 * occ
            else:
                shade = 1.0
            # rimbalzo caldo del fuoco vicino
            heat = 0.0
            for p, warmth, power in warm:
                d2 = (p - w).length_squared + 6.0
                heat += warmth * power / d2
            glow = 1.0 - math.exp(-heat * 0.0016)
            r = tone * ash * shade * (1.0 + 0.55 * glow)
            g = tone * ash * shade * (1.0 + 0.06 * glow)
            bb = tone * ash * shade * (1.0 - 0.32 * glow)
            attr.data[i].color = (min(1.5, r), min(1.5, g), min(1.5, bb), 1.0)
        total += len(me.vertices)
    log(f'colori per vertice: {total} vertici in {time.time() - t0:.1f}s')


# --------------------------------------------------------------------------- #
# Mesh di collisione semplificata
# --------------------------------------------------------------------------- #
def build_collision(scene, keep_names, target_tris=70000):
    """Duplica la geometria e la semplifica: è la mesh della fisica.

    I battenti sono già chiusi: `prepare_geometry` li ha riportati a zero gradi
    prima di unire le mesh, quindi il varco risulta sbarrato.
    """
    sources = [o for o in scene.objects
               if o.type == 'MESH' and o.name in keep_names
               and not is_walk_through(material_of(o))]
    bpy.ops.object.select_all(action='DESELECT')
    for o in sources:
        o.select_set(True)
    bpy.context.view_layer.objects.active = sources[0]
    copies = []
    for o in sources:
        c = o.copy()
        c.data = o.data.copy()
        c.name = 'COL__' + o.name
        for attr in list(c.data.color_attributes):
            c.data.color_attributes.remove(attr)
        scene.collection.objects.link(c)
        # La copia non ha genitori: senza questo, la matrice mondo perderebbe
        # la rotazione del cardine e i battenti finirebbero fuori posto.
        c.matrix_world = o.matrix_world.copy()
        copies.append(c)

    # Il rapporto del modificatore agisce sulle facce; il conteggio che conta per
    # il gioco è quello dei triangoli, quindi si itera fino al tetto richiesto.
    t0 = time.time()
    for _ in range(3):
        tris = sum(count_triangles(c) for c in copies)
        if tris <= target_tris:
            break
        ratio = max(0.05, target_tris / tris)
        for c in copies:
            if count_triangles(c) < 200:
                continue
            bpy.ops.object.select_all(action='DESELECT')
            c.select_set(True)
            bpy.context.view_layer.objects.active = c
            mod = c.modifiers.new('dec', 'DECIMATE')
            mod.decimate_type = 'COLLAPSE'
            mod.ratio = ratio
            mod.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier='dec')
    log(f'collisione: {len(copies)} mesh, {total_tris_filtered(copies)} triangoli '
        f'in {time.time() - t0:.1f}s')
    return copies


def total_tris_filtered(objects) -> int:
    return sum(count_triangles(o) for o in objects)


# --------------------------------------------------------------------------- #
# Export glTF
# --------------------------------------------------------------------------- #
def export_glb(path: Path, objects, export_materials='EXPORT'):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        use_selection=True,
        export_format='GLB',
        export_apply=True,
        export_yup=True,
        export_normals=True,
        export_materials=export_materials,
        export_lights=False,
        export_cameras=False,
        export_extras=True,
        # Il colore per vertice (AO, cenere, riflesso del fuoco) deve finire su
        # COLOR_0: è l'unico attributo che three.js usa come vertexColors.
        export_vertex_color='ACTIVE',
        export_all_vertex_colors=False,
    )
    log(f'glTF: {path.name} {path.stat().st_size / 1e6:.2f} MB')


def quantized_bounds(path: Path):
    """Bounding box del GLB ricavato dal JSON: serve a intercettare una
    quantizzazione sbagliata senza caricare la geometria."""
    with open(path, 'rb') as fh:
        data = fh.read()
    if data[:4] != b'glTF':
        return None
    offset = 12
    json_data = None
    while offset < len(data):
        length, kind = struct.unpack('<II', data[offset:offset + 8])
        if kind == 0x4E4F534A:  # JSON
            json_data = json.loads(data[offset + 8:offset + 8 + length].decode('utf-8'))
            break
        offset += 8 + length
    if json_data is None:
        return None

    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for node in json_data.get('nodes', []):
        if 'mesh' not in node:
            continue
        translation = node.get('translation', [0, 0, 0])
        scale = node.get('scale', [1, 1, 1])
        for prim in json_data['meshes'][node['mesh']]['primitives']:
            acc = json_data['accessors'][prim['attributes']['POSITION']]
            lo_raw, hi_raw = acc.get('min'), acc.get('max')
            if lo_raw is None or hi_raw is None:
                continue
            for axis in range(3):
                a = translation[axis] + lo_raw[axis] * scale[axis]
                b = translation[axis] + hi_raw[axis] * scale[axis]
                lo[axis] = min(lo[axis], a, b)
                hi[axis] = max(hi[axis], a, b)
    if not all(math.isfinite(v) for v in lo + hi):
        return None
    return {'min': lo, 'max': hi, 'size': [hi[i] - lo[i] for i in range(3)]}


def compress_with_gltfpack(path: Path) -> bool:
    """Quantizza e comprime (EXT_meshopt_compression) con gltfpack, se c'è.

    ATTENZIONE: -vp/-vn/-vc prendono un numero di BIT, non una tolleranza.
    Passare 1e-4 qui ridurrebbe la geometria a un bit, cioè a un mondo piatto.
    """
    exe = GAME_DIR / 'node_modules' / '.bin' / 'gltfpack'
    if not exe.exists():
        log('gltfpack non installato: salto la compressione (npm install in game/)')
        return False

    before = path.stat().st_size
    reference = quantized_bounds(path)
    out = path.with_suffix('.opt.glb')
    res = subprocess.run(
        [str(exe), '-i', str(path), '-o', str(out),
         '-cc',           # compressione meshopt
         '-kn',           # mantiene i nomi dei nodi (cardini, iscrizione)
         '-vp', str(POSITION_BITS), '-vn', '8', '-vc', '8', '-vt', '12'],
        capture_output=True, text=True)
    if res.returncode != 0 or not out.exists():
        log('gltfpack fallito:', (res.stderr or res.stdout)[:400])
        return False

    compressed = quantized_bounds(out)
    if reference and compressed:
        shrunk = [compressed['size'][i] / max(1e-9, reference['size'][i]) for i in range(3)]
        if min(shrunk) < 0.9:
            # La geometria si è accartocciata: meglio il file non compresso.
            log(f'gltfpack ha deformato la geometria (rapporto {min(shrunk):.3f}): '
                'tengo il file non compresso')
            out.unlink(missing_ok=True)
            return False

    after = out.stat().st_size
    out.replace(path)
    log(f'gltfpack: {before / 1e6:.2f} MB -> {after / 1e6:.2f} MB')
    return True


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--blend', default=str(ROOT / 'porta_dell_inferno.blend'))
    ap.add_argument('--out', default=str(GAME_DIR / 'public'))
    ap.add_argument('--target-collision-tris', type=int, default=70000)
    ap.add_argument('--no-compress', action='store_true')
    ap.add_argument('--max-triangles', type=int, default=620000,
                    help='Tetto di triangoli per la mesh visiva')
    ap.add_argument('--ao-rays', type=int, default=6,
                    help='Raggi di occlusione ambientale per vertice (0 = nessun AO)')
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.time()
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    scene = bpy.context.scene
    source_object_count = len(scene.objects)
    log(f'aperto {Path(args.blend).name}: {source_object_count} oggetti')

    lights = collect_lights(scene)
    pois = collect_points_of_interest()
    camera = collect_camera(scene)

    # Battenti: posizione e apertura dei cardini (il gioco li anima).
    hinges = []
    for obj in scene.objects:
        if obj.type == 'EMPTY' and obj.name in HINGE_NAMES:
            hinges.append({
                'node': HINGE_NAMES[obj.name],
                'side': 'sinistro' if 'sinistro' in obj.name else 'destro',
                'position': to_game(obj.matrix_world.translation),
                # `rest_angle` è la posa socchiusa del render; il gioco parte
                # da `closed_angle` e spalanca i battenti nel finale.
                'rest_angle': round(float(obj.rotation_euler.z), 4),
                'closed_angle': 0.0,
                'open_angle': round(float(obj.rotation_euler.z)
                                    + (1.95 if 'destro' in obj.name else -1.95), 4),
            })

    inscription = bpy.data.objects.get(INSCRIPTION)
    inscription_data = None
    if inscription is not None:
        inscription_data = {
            'node': INSCRIPTION_NODE,
            'text': inscription.data.body,
            'position': to_game(inscription.matrix_world.translation),
        }

    # Soglia della porta: il traguardo del gioco. Sta sul fronte dei battenti
    # chiusi (che occupano z ≈ -0,6…0,8): è il punto in cui il pellegrino si
    # ferma a spingere, non il fondo del tunnel oltre la porta.
    gate = {
        'position': to_game(Vector((0.0, -0.9, 1.6))),
        'radius': 2.6,
    }

    bounds = None
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for obj in scene.objects:
        if obj.type != 'MESH':
            continue
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    g_lo, g_hi = to_game(lo), to_game(hi)
    bounds = {'min': [min(a, b) for a, b in zip(g_lo, g_hi)],
              'max': [max(a, b) for a, b in zip(g_lo, g_hi)]}

    heightmap = build_heightmap(
        scene, out_dir,
        region=(-150.0, 150.0, -62.0, 95.0),
        resolution=(768, 384),
        lights=lights,
    )

    kept, static_names, hinge_names = build_merged(scene)
    visual_tris = enforce_triangle_budget(scene, args.max_triangles)
    bake_vertex_colors(scene, lights, kept, ao_rays=args.ao_rays)

    # I cardini restano empty-nodo: il gioco li ruota per aprire i battenti.
    for obj in scene.objects:
        if obj.type == 'EMPTY' and obj.name in HINGE_NAMES:
            obj.name = HINGE_NAMES[obj.name]
    map_path = out_dir / 'map.glb'
    export_glb(map_path, [o for o in scene.objects if o.type == 'MESH'
                          or (o.type == 'EMPTY' and o.name in set(HINGE_NAMES.values()))])
    if not args.no_compress:
        compress_with_gltfpack(map_path)

    # Anche i battenti entrano nella collisione: sono chiusi per tutta la
    # partita e si aprono solo nel finale, quando il giocatore non cammina più.
    copies = build_collision(
        scene, set(static_names) | set(hinge_names), args.target_collision_tris)
    collision_path = out_dir / 'collision.glb'
    export_glb(collision_path, copies, export_materials='NONE')
    if not args.no_compress:
        compress_with_gltfpack(collision_path)

    payload = {
        'source': 'porta_dell_inferno.blend',
        'generator': 'game/tools/export_map.py',
        'coordinates': 'game-space (Y up): blender (x, y, z) -> (x, z, -y)',
        'units': 'metri',
        'stats': {
            'source_objects': source_object_count,
            'materials': len({v['material'] for v in kept.values()}),
            'visual_triangles': visual_tris,
            'collision_triangles': total_tris_filtered(copies),
        },
        'bounds': bounds,
        'spawn': {
            'position': camera['position'] if camera else [9.2, 1.95, 44.0],
            'forward': camera['forward'] if camera else [0.0, 0.0, -1.0],
            'eye_height': 1.68,
        },
        'gate': gate,
        'inscription': inscription_data,
        'hinges': hinges,
        'lights': lights,
        'points_of_interest': pois,
        'heightmap': heightmap,
        'meshes': {k: v for k, v in sorted(kept.items())},
    }
    (out_dir / 'scene.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    log(f'scene.json: {len(lights)} luci, {len(pois)} sigilli, '
        f'{len(kept)} mesh unite, {visual_tris} triangoli visivi')
    log(f'fatto in {time.time() - t_start:.1f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
