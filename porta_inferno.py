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
# Materiali procedurali: pietra vulcanica, roccia carbonizzata, metallo annerito
#
# Ogni superficie nasce dalla somma di famiglie di dettaglio campionate a scale
# molto diverse (da ~3 unità fino al millimetro) e di maschere di degrado
# indipendenti:
#   • crepe profonde e craquelure capillare  (Voronoi "distance to edge")
#   • vaiolature vulcaniche, erosione e scheggiature concentrate sugli spigoli
#   • cenere depositata sulle facce esposte, fuliggine colata a strisce
#   • bruciature con alone di scottatura e chiazze di crosta vetrificata
# Le coordinate sono ruotate e traslate in modo diverso per ogni singolo oggetto
# (Object Info), così centinaia di conci non condividono mai lo stesso campione
# di texture, e ogni gruppo di rumori è "domain warped" per spezzare la
# regolarità tipica dei procedurali. Roughness e metallic variano con le stesse
# maschere del colore, non con un singolo rumore.
# -----------------------------------------------------------------------------
# Il grafo è impaginato per colonne semantiche; ogni colonna va a capo ogni 30
# righe così l'albero resta compatto e leggibile nello Shader Editor.
NODE_COLS = {
    "coord": -7000, "warp": -6000, "tex": -5000, "mask": -4000,
    "mix": -2000, "aux": -2000, "rough": -1000, "bump": 0, "out": 1600,
}
NODE_RIGHE_BLOCCO = 40
NODE_PASSO_RIGA = 108.0
NODE_PASSO_BLOCCO = 420.0
NODE_FRAME = {
    "coord": "Coordinate: rotazione e traslazione per oggetto",
    "warp": "Domain warping: rumori deformati",
    "tex": "Texture stratificate (macro → millimetrico)",
    "mask": "Maschere di degrado: crepe, schegge, cenere, bruciature",
    "mix": "Colore stratificato",
    "rough": "Roughness e metallic",
    "bump": "Rilievo e micro-dettaglio",
}


class Superficie:
    """Costruttore di grafi di shader: gestisce nodi, collegamenti e colonne."""

    def __init__(self, nome, viewport=(0.16, 0.15, 0.14)):
        self.mat = bpy.data.materials.new(nome)
        self.mat.diffuse_color = (viewport[0], viewport[1], viewport[2], 1.0)
        self.mat.use_nodes = True
        self.tree = self.mat.node_tree
        self.nodes = self.tree.nodes
        self.links = self.tree.links
        self.nodes.clear()
        self.colonne = {}
        self.occupato = set()
        self.bsdf = self.nodo("ShaderNodeBsdfPrincipled", "out", 0)
        self.bsdf.location = (NODE_COLS["out"] - 360, 60)
        self.output = self.nodo("ShaderNodeOutputMaterial", "out", 0)
        self.output.location = (NODE_COLS["out"] + 90, 0)
        self.L(self.bsdf.outputs["BSDF"], self.output.inputs["Surface"])

    # Scostamenti provati in ordine quando una casella è già occupata: prima di
    # fianco, poi più in basso, così i nodi di servizio non si accavallano mai.
    SPOSTAMENTI = ((0.0, 0.0), (250.0, 0.0), (0.0, -46.0), (250.0, -46.0),
                   (500.0, 0.0), (0.0, -92.0), (250.0, -92.0), (500.0, -46.0),
                   (-250.0, 0.0), (0.0, 46.0), (500.0, -92.0), (-250.0, -46.0))

    def nodo(self, tipo, col, riga, etichetta=None):
        node = self.nodes.new(tipo)
        base_x = NODE_COLS.get(col, col)
        blocco = int(riga) // NODE_RIGHE_BLOCCO
        x0 = base_x + blocco * NODE_PASSO_BLOCCO
        y0 = -(int(riga) % NODE_RIGHE_BLOCCO) * NODE_PASSO_RIGA
        for dx, dy in self.SPOSTAMENTI:
            if (x0 + dx, y0 + dy) not in self.occupato:
                x, y = x0 + dx, y0 + dy
                break
        else:  # colonna davvero satura: si scende di una riga intera
            x, y = x0, y0 - NODE_PASSO_RIGA * (1 + len(self.occupato) // 400)
        self.occupato.add((x, y))
        node.location = (x, y)
        if etichetta:
            node.label = etichetta
        self.colonne.setdefault(col, []).append(node)
        return node

    def inquadra(self):
        """Raggruppa il grafo in riquadri etichettati, uno per colonna."""
        for col, etichetta in NODE_FRAME.items():
            nodi = self.colonne.get(col) or []
            if len(nodi) < 2:
                continue
            frame = self.nodes.new("NodeFrame")
            frame.label = etichetta
            for n in nodi:
                n.parent = frame
            xs = [n.location[0] for n in nodi]
            ys = [n.location[1] for n in nodi]
            frame.location = (min(xs) - 90, max(ys) + 120)
            frame.width = (max(xs) - min(xs)) + 480
            frame.height = (max(ys) - min(ys)) + 320

    def L(self, a, b):
        if a is not None and b is not None:
            self.links.new(a, b)
        return b

    def ingresso(self, node, nome, valore):
        if nome in node.inputs:
            node.inputs[nome].default_value = valore
        return node

    def valore(self, v, col="aux", riga=0):
        """Costante numerica: finisce come default_value, non come nodo."""
        return float(v)

    def matematica(self, op, a=None, b=None, col="aux", riga=0, etichetta=None):
        n = self.nodo("ShaderNodeMath", col, riga, etichetta)
        n.operation = op
        if a is not None:
            self.costante(n.inputs[0], a)
        if b is not None:
            self.costante(n.inputs[1], b)
        return n.outputs[0]

    def vettore(self, op, a=None, b=None, col="coord", riga=0, scala=None,
                etichetta=None, uscita=0):
        n = self.nodo("ShaderNodeVectorMath", col, riga, etichetta)
        n.operation = op
        if a is not None:
            self.L(a, n.inputs[0])
        if b is not None:
            self.L(b, n.inputs[1])
        if scala is not None:
            n.inputs[3].default_value = scala
        return n.outputs[uscita]

    def combina(self, x=0.0, y=0.0, z=0.0, col="coord", riga=0):
        n = self.nodo("ShaderNodeCombineXYZ", col, riga)
        n.inputs[0].default_value = x
        n.inputs[1].default_value = y
        n.inputs[2].default_value = z
        return n.outputs[0]

    def componi(self, x, y, z, col="coord", riga=0):
        """Versione pilotata da socket: i tre assi arrivano da altri nodi."""
        n = self.nodo("ShaderNodeCombineXYZ", col, riga)
        self.L(x, n.inputs[0])
        self.L(y, n.inputs[1])
        self.L(z, n.inputs[2])
        return n.outputs[0]

    def separa(self, v, col="mask", riga=0):
        n = self.nodo("ShaderNodeSeparateXYZ", col, riga)
        self.L(v, n.inputs[0])
        return n

    def canale(self, colore, col="mask", riga=0):
        """Estrae il canale rosso da un colore (maschere in scala di grigi)."""
        n = self.nodo("ShaderNodeSeparateColor", col, riga)
        self.L(colore, n.inputs["Color"])
        return n.outputs["Red"]

    def costante(self, socket, valore):
        """Imposta un valore fisso (tupla colore o numero) oppure collega un socket."""
        if not isinstance(valore, (tuple, list, int, float)):
            self.L(valore, socket)
            return socket
        if isinstance(valore, (tuple, list)):
            socket.default_value = (tuple(valore) + (1.0,))[:4] if len(valore) == 3 else tuple(valore)
        elif socket.type == "RGBA":
            socket.default_value = (float(valore), float(valore), float(valore), 1.0)
        else:
            socket.default_value = float(valore)
        return socket

    def miscela(self, fac, a, b, col="mix", riga=0, tipo="COLORE", etichetta=None):
        n = self.nodo("ShaderNodeMix", col, riga, etichetta)
        n.data_type = "RGBA" if tipo == "COLORE" else "FLOAT"
        self.costante(n.inputs[0], fac)
        ia, ib, io = (6, 7, 2) if tipo == "COLORE" else (2, 3, 0)
        self.costante(n.inputs[ia], a)
        self.costante(n.inputs[ib], b)
        return n.outputs[io]

    def prodotto_colore(self, a, b, col="mix", riga=0, etichetta=None):
        """Moltiplicazione cromatica (la matematica su colori perderebbe i canali)."""
        n = self.nodo("ShaderNodeMix", col, riga, etichetta)
        n.data_type = "RGBA"
        n.blend_type = "MULTIPLY"
        n.inputs[0].default_value = 1.0
        self.costante(n.inputs[6], a)
        self.costante(n.inputs[7], b)
        return n.outputs[2]

    def rampa(self, fac, soglie, col="mask", riga=0, interp="LINEAR", etichetta=None):
        """Soglie: [(posizione, colore_o_valore)]; i float diventano grigi."""
        n = self.nodo("ShaderNodeValToRGB", col, riga, etichetta)
        try:
            n.color_ramp.interpolation = interp
        except Exception:
            pass
        els = n.color_ramp.elements
        for i, soglia in enumerate(soglie):
            pos, val = soglia
            if isinstance(val, (int, float)):
                rgba = (float(val), float(val), float(val), 1.0)
            else:
                rgba = (val[0], val[1], val[2], 1.0)
            el = els[i] if i < len(els) else els.new(pos)
            el.position = pos
            el.color = rgba
        if fac is not None:
            self.costante(n.inputs[0], fac)
        return n.outputs["Color"]

    def rumore(self, vett, scala=1.0, dettaglio=6.0, ruvido=0.6, distorsione=0.0,
               col="tex", riga=0, etichetta=None):
        n = self.nodo("ShaderNodeTexNoise", col, riga, etichetta)
        if vett is not None:
            self.L(vett, n.inputs["Vector"])
        self.ingresso(n, "Scale", scala)
        self.ingresso(n, "Detail", dettaglio)
        self.ingresso(n, "Roughness", ruvido)
        self.ingresso(n, "Distortion", distorsione)
        return n

    def voronoi(self, vett, scala=5.0, feature="F1", casualita=1.0,
                col="tex", riga=0, etichetta=None):
        n = self.nodo("ShaderNodeTexVoronoi", col, riga, etichetta)
        n.feature = feature
        if vett is not None:
            self.L(vett, n.inputs["Vector"])
        self.ingresso(n, "Scale", scala)
        self.ingresso(n, "Randomness", casualita)
        return n

    def onda(self, vett, scala=4.0, distorsione=6.0, dettaglio=6.0, tipo="BANDS",
             direzione="X", profilo="SIN", col="tex", riga=0, etichetta=None):
        n = self.nodo("ShaderNodeTexWave", col, riga, etichetta)
        n.wave_type = tipo
        n.wave_profile = profilo
        if tipo == "BANDS":
            n.bands_direction = direzione
        else:
            n.rings_direction = direzione
        self.ingresso(n, "Scale", scala)
        self.ingresso(n, "Distortion", distorsione)
        self.ingresso(n, "Detail", dettaglio)
        if vett is not None:
            self.L(vett, n.inputs["Vector"])
        return n


def materiale_eroso(nome, viewport, r):
    """Costruisce una superficie erosa completa a partire da una ricetta."""
    S = Superficie(nome, viewport)
    bsdf = S.bsdf
    dato = lambda c, d: r.get(c, d)

    macro_scala, macro_dett = dato("macro", (0.50, 6.0))
    meso_scala, meso_dett = dato("meso", (6.5, 8.0))
    micro_scala, micro_dett = dato("micro", (48.0, 3.0))
    medio_scala, medio_dett = dato("medio", (2.2, 7.0))
    mondo_scala, brucia_peso = dato("bruciatura", (0.33, 0.55))
    # Le misure dei difetti sono in metri: lato della cella e mezza larghezza
    # del solco.  Vengono convertite nelle unità del dominio che le ospita, così
    # ritoccare la scala di una texture non deforma crepe, vaioli e schegge.
    crepa_cella, crepa_peso, crepa_mezza = dato("crepa", (1.20, 1.0, 0.06))
    craq_cella, craq_peso, craq_mezza = dato("craquelure", (0.06, 0.42, 0.004))
    vaiolo_cella, vaiolo_peso = dato("vaioli", (0.06, 0.5))
    scheggia_cella, scheggia_peso = dato("schegge", (0.11, 0.55))
    cenere_peso = dato("cenere", 0.5)
    fuliggine_peso = dato("fuliggine", 0.4)
    usura_peso = dato("usura", 0.55)
    ruggine_peso = dato("ruggine", 0.0)
    graffio_cella, graffi_peso = dato("graffi", (0.03, 0.0))
    martell_cella, martell_peso = dato("martellatura", (0.14, 0.0))
    scaglia_cella, scaglia_peso = dato("scaglie", (0.13, 0.0))
    brace_peso = dato("brace", 0.0)
    vetro_peso = dato("vetrificato", 0.35)
    rilievo, rilievo_d = dato("rilievo", (0.55, 0.030))
    microrilievo, microrilievo_d = dato("microrilievo", (0.22, 0.005))
    grano = dato("grano", None)

    # Dalle misure in metri alle scale dei nodi: una cella di lato L sul dominio
    # di scala S si ottiene con uno Scale pari a 1/(L*S), e la soglia della rampa
    # è la mezza larghezza espressa in frazioni di cella.
    def celle(metri, scala):
        return 1.0 / max(metri * scala, 1e-4)

    def soglia(mezza, cella):
        return min(mezza / max(cella, 1e-4), 0.49)

    crepa_mult = celle(crepa_cella, macro_scala)
    crepa_largh = soglia(crepa_mezza, crepa_cella)
    craq_mult = celle(craq_cella, meso_scala)
    craq_largh = soglia(craq_mezza, craq_cella)
    vaiolo_mult = celle(vaiolo_cella, micro_scala)
    scheggia_mult = celle(scheggia_cella, meso_scala)
    martell_mult = celle(martell_cella, meso_scala)
    scaglia_mult = celle(scaglia_cella, meso_scala)
    graffio_mult = celle(graffio_cella, meso_scala)

    c_profondo = dato("col_profondo", (0.0085, 0.0090, 0.0115))
    c_base = dato("col_base", (0.052, 0.050, 0.049))
    c_chiaro = dato("col_chiaro", (0.115, 0.110, 0.104))
    c_fresco = dato("col_fresco", (0.098, 0.092, 0.085))
    c_crepa = dato("col_crepa", (0.0022, 0.0022, 0.0028))
    c_cenere = dato("col_cenere", (0.150, 0.138, 0.129))
    c_fuliggine = dato("col_fuliggine", (0.0075, 0.0068, 0.0068))
    c_bruciato = dato("col_bruciato", (0.0050, 0.0042, 0.0042))
    c_scottatura = dato("col_scottatura", (0.058, 0.024, 0.013))
    c_ruggine = dato("col_ruggine", (0.105, 0.045, 0.020))
    c_brace = dato("col_brace", (1.0, 0.17, 0.02))

    ruvido = dato("ruvido", 0.86)
    metallico = dato("metallico", 0.0)

    # ------------------------------------------------------------- coordinate
    tc = S.nodo("ShaderNodeTexCoord", "coord", 0, "Coordinate")
    geo = S.nodo("ShaderNodeNewGeometry", "coord", 6, "Geometria")
    oi = S.nodo("ShaderNodeObjectInfo", "coord", 9, "Info oggetto")
    casuale = oi.outputs["Random"]

    rot = S.nodo("ShaderNodeVectorRotate", "coord", 1, "Rotazione per oggetto")
    rot.rotation_type = "Z_AXIS"
    S.L(tc.outputs["Object"], rot.inputs["Vector"])
    S.L(S.matematica("MULTIPLY", casuale, S.valore(6.2832, "coord", 10), "coord", 2),
        rot.inputs["Angle"])

    # Ogni oggetto campiona una zona diversa della texture: posizione nel mondo
    # più un seme casuale decorrelato asse per asse.
    off_mondo = S.vettore("SCALE", oi.outputs["Location"], col="coord", riga=3, scala=3.7)
    off_seme = S.componi(
        S.matematica("MULTIPLY", casuale, S.valore(97.3, "coord", 11), "coord", 12),
        S.matematica("MULTIPLY", casuale, S.valore(151.7, "coord", 11), "coord", 13),
        S.matematica("MULTIPLY", casuale, S.valore(53.9, "coord", 11), "coord", 14),
        "coord", 15)
    P = S.vettore("ADD", S.vettore("ADD", rot.outputs[0], off_mondo, "coord", 4),
                  off_seme, "coord", 5, etichetta="Spazio texture per oggetto")
    if grano:
        P = S.vettore("MULTIPLY", P, S.combina(grano[0], grano[1], grano[2], "coord", 7),
                      "coord", 8, etichetta="Grana anisotropa")

    def gruppo(sorgente, base, ampiezza, riga, etichetta):
        """Coordinate pre-scalate e deformate: domain warping anti-regolarità."""
        v = S.vettore("SCALE", sorgente, col="warp", riga=riga, scala=base)
        n = S.rumore(v, scala=0.42, dettaglio=4.0, ruvido=0.78, distorsione=1.1,
                     col="warp", riga=riga + 1, etichetta="Deformazione " + etichetta)
        d = S.vettore("ADD", n.outputs["Color"], S.combina(-0.5, -0.5, -0.5, "warp", riga + 2),
                      col="warp", riga=riga + 2)
        d = S.vettore("SCALE", d, col="warp", riga=riga + 3, scala=ampiezza * 2.2)
        return S.vettore("ADD", v, d, col="warp", riga=riga + 4, etichetta=etichetta)

    g_macro = gruppo(P, macro_scala, 0.55, 0, "Dominio macro")
    g_meso = gruppo(P, meso_scala, 0.42, 6, "Dominio della grana")
    g_micro = S.vettore("SCALE", P, col="warp", riga=12, scala=micro_scala,
                        etichetta="Dominio del grit")
    g_medio = S.vettore("SCALE", P, col="warp", riga=16, scala=medio_scala,
                        etichetta="Dominio delle chiazze")
    g_mondo = gruppo(geo.outputs["Position"], mondo_scala, 0.30, 14, "Dominio mondo")

    # --------------------------------------------------------------- texture
    n_macro = S.rumore(g_macro, scala=1.0, dettaglio=macro_dett, ruvido=0.66,
                       distorsione=0.55, col="tex", riga=0, etichetta="Chiazze litologiche")
    n_meso = S.rumore(g_meso, scala=1.0, dettaglio=meso_dett, ruvido=0.62,
                      distorsione=0.40, col="tex", riga=2, etichetta="Grana della pietra")
    n_micro = S.rumore(g_micro, scala=1.0, dettaglio=micro_dett, ruvido=0.5,
                       distorsione=0.20, col="tex", riga=4, etichetta="Grit millimetrico")
    n_grumo = S.rumore(g_medio, scala=1.0, dettaglio=medio_dett, ruvido=0.88,
                       distorsione=0.0, col="tex", riga=6, etichetta="Aggregati e chiazze")
    n_vario = S.rumore(g_macro, scala=0.5, dettaglio=5.0, ruvido=0.70, distorsione=0.0,
                       col="tex", riga=8, etichetta="Variazione lenta")
    n_brucia = S.rumore(g_mondo, scala=1.0, dettaglio=7.0, ruvido=0.72, distorsione=1.0,
                        col="tex", riga=10, etichetta="Macchie di combustione")

    # ------------------------------------------------------- usura geometrica
    puntuta = geo.outputs["Pointiness"]
    normale = geo.outputs["Normal"]
    spigolo = S.rampa(puntuta, [(0.010, 0.0), (0.085, 0.35), (0.28, 1.0)], "mask", 2,
                      interp="EASE", etichetta="Spigoli esposti")
    concavo = S.rampa(puntuta, [(0.0, 0.0), (-0.30, 1.0)], "mask", 3, interp="EASE",
                      etichetta="Cavità")
    su = S.vettore("DOT_PRODUCT", normale, S.combina(0, 0, 1, "mask", 4), col="mask",
                   riga=4, uscita=1, etichetta="Rivolto in alto")
    rivolto_su = S.rampa(su, [(0.05, 0.0), (0.62, 1.0)], "mask", 5, interp="EASE")

    # ------------------------------------------------- prossimità al fuoco
    pm = S.separa(geo.outputs["Position"], "mask", 20)
    cal_x = S.rampa(S.matematica("ABSOLUTE", pm.outputs["X"], col="mask", riga=21),
                    [(1.4, 1.0), (7.5, 0.0)], "mask", 22, interp="EASE")
    cal_z = S.rampa(S.matematica("ABSOLUTE",
                                 S.matematica("SUBTRACT", pm.outputs["Z"],
                                              S.valore(3.2, "mask", 23), "mask", 23),
                                 col="mask", riga=24),
                    [(0.9, 1.0), (8.5, 0.12)], "mask", 25, interp="EASE")
    cal_y = S.rampa(S.matematica("ABSOLUTE", pm.outputs["Y"], col="mask", riga=26),
                    [(2.2, 1.0), (10.0, 0.22)], "mask", 27, interp="EASE")
    calore = S.matematica("MULTIPLY",
                          S.matematica("MULTIPLY", cal_x, cal_z, "mask", 28),
                          cal_y, "mask", 29, etichetta="Calore della soglia")

    # ----------------------------------------------------------------- crepe
    crepa_fac = S.voronoi(g_macro, scala=crepa_mult, feature="DISTANCE_TO_EDGE",
                          casualita=0.85, col="tex", riga=12, etichetta="Rete di crepe")
    crepa_grezza = S.rampa(crepa_fac.outputs["Distance"],
                           [(0.0, 1.0), (crepa_largh * 0.45, 0.78), (crepa_largh, 0.0)],
                           "mask", 30, interp="EASE", etichetta="Crepe profonde")
    # Le crepe si interrompono dove la roccia è compatta: niente reticolo perfetto.
    cancella = S.rampa(n_vario.outputs["Fac"], [(0.34, 0.0), (0.52, 1.0)], "mask", 31,
                       interp="EASE", etichetta="Interruzione delle crepe")
    crepe = S.matematica("MULTIPLY",
                         S.matematica("MULTIPLY", crepa_grezza, cancella, "mask", 32),
                         S.valore(crepa_peso, "mask", 33), "mask", 34, etichetta="Crepe")

    craq_fac = S.voronoi(g_meso, scala=craq_mult, feature="DISTANCE_TO_EDGE",
                         casualita=1.0, col="tex", riga=14, etichetta="Craquelure")
    craquelure = S.rampa(craq_fac.outputs["Distance"],
                         [(0.0, 1.0), (craq_largh * 0.4, 0.55), (craq_largh, 0.0)],
                         "mask", 35, interp="EASE")
    craquelure = S.matematica("MULTIPLY", craquelure, S.valore(craq_peso, "mask", 36),
                              "mask", 37, etichetta="Craquelure")

    # ------------------------------------------------- vaiolature e schegge
    if vaiolo_peso > 0.0:
        vaiolo_fac = S.voronoi(g_micro, scala=vaiolo_mult, feature="F1", casualita=1.0,
                               col="tex", riga=16, etichetta="Vaiolature")
        vaiolo_m = S.rampa(vaiolo_fac.outputs["Distance"],
                           [(0.0, 1.0), (0.16, 0.72), (0.34, 0.0)], "mask", 38,
                           interp="EASE")
        vaiolo_m = S.matematica("MULTIPLY", vaiolo_m,
                                S.rampa(n_grumo.outputs["Fac"], [(0.30, 0.0), (0.58, 1.0)],
                                        "mask", 39), "mask", 40)
        vaioli = S.matematica("MULTIPLY", vaiolo_m, S.valore(vaiolo_peso, "mask", 41),
                              "mask", 42, etichetta="Vaioli e porosità")
    else:
        vaioli = S.valore(0.0, "mask", 42)

    if scheggia_peso > 0.0:
        cella = S.voronoi(g_meso, scala=scheggia_mult, feature="F1", casualita=1.0,
                          col="tex", riga=18, etichetta="Cellule di distacco")
        scheggia_m = S.rampa(S.canale(cella.outputs["Color"], "mask", 43),
                             [(0.72, 0.0), (0.90, 1.0)], "mask", 44, interp="EASE")
        scheggia_m = S.matematica("MULTIPLY", scheggia_m,
                                  S.matematica("ADD", S.valore(0.35, "mask", 45),
                                               S.matematica("MULTIPLY", spigolo,
                                                            S.valore(0.85, "mask", 45),
                                                            "mask", 46), "mask", 47),
                                  "mask", 48)
        scheggia_m = S.matematica("MULTIPLY", scheggia_m,
                                  S.rampa(n_grumo.outputs["Fac"], [(0.22, 0.0), (0.50, 1.0)],
                                          "mask", 49), "mask", 50)
        schegge = S.matematica("MULTIPLY", scheggia_m,
                               S.valore(scheggia_peso, "mask", 51), "mask", 52,
                               etichetta="Scheggiature")
    else:
        schegge = S.valore(0.0, "mask", 52)

    # ------------------------------- bruciature, cenere, fuliggine, vetrificato
    bruciato = S.rampa(n_brucia.outputs["Fac"], [(0.33, 0.0), (0.57, 1.0)], "mask", 54,
                       interp="EASE", etichetta="Nucleo carbonizzato")
    scottatura = S.rampa(n_brucia.outputs["Fac"],
                         [(0.26, 0.0), (0.35, 1.0), (0.49, 1.0), (0.58, 0.0)], "mask", 55,
                         interp="EASE", etichetta="Alone di scottatura")
    m_bruciato = S.matematica("MULTIPLY",
                              S.matematica("MULTIPLY", bruciato, calore, "mask", 56),
                              S.valore(brucia_peso, "mask", 57), "mask", 58,
                              etichetta="Bruciature")
    m_scottato = S.matematica("MULTIPLY",
                              S.matematica("MULTIPLY", scottatura, calore, "mask", 59),
                              S.valore(min(1.0, brucia_peso * 0.85), "mask", 60), "mask", 61,
                              etichetta="Scottature")
    vetro = S.matematica("MULTIPLY",
                         S.matematica("MULTIPLY",
                                      S.rampa(n_brucia.outputs["Fac"],
                                              [(0.60, 0.0), (0.78, 1.0)], "mask", 62,
                                              interp="EASE"),
                                      calore, "mask", 63),
                         S.valore(vetro_peso, "mask", 64), "mask", 65,
                         etichetta="Crosta vetrificata")

    cenere_bassa = S.rampa(pm.outputs["Z"], [(0.15, 1.0), (7.0, 0.18)], "mask", 66,
                           interp="EASE")
    cenere_su = S.matematica("MULTIPLY", rivolto_su,
                             S.matematica("ADD", S.valore(0.35, "mask", 67),
                                          S.matematica("MULTIPLY", n_grumo.outputs["Fac"],
                                                       S.valore(0.75, "mask", 68), "mask", 69),
                                          "mask", 70), "mask", 71)
    cenere_cava = S.matematica("MULTIPLY", concavo, S.valore(0.75, "mask", 72), "mask", 73)
    m_cenere = S.matematica("MULTIPLY",
                            S.matematica("ADD", cenere_su, cenere_cava, "mask", 74),
                            S.matematica("ADD", S.valore(0.25, "mask", 75),
                                         S.matematica("MULTIPLY", cenere_bassa,
                                                      S.valore(0.85, "mask", 76), "mask", 77),
                                         "mask", 78), "mask", 79)
    # Lo spessore del deposito segue la rugosità: niente velature piatte.
    m_cenere = S.matematica("MULTIPLY", m_cenere,
                            S.rampa(S.matematica("MULTIPLY", n_grumo.outputs["Fac"],
                                                 S.valore(0.75, "mask", 143), "mask", 143),
                                    [(0.18, 0.10), (0.62, 1.0)], "mask", 143,
                                    interp="EASE"), "mask", 144)
    m_cenere = S.matematica("MULTIPLY", m_cenere, S.valore(cenere_peso, "mask", 80),
                            "mask", 81, etichetta="Depositi di cenere")

    if fuliggine_peso > 0.0:
        striscia = S.onda(S.vettore("MULTIPLY", P, S.combina(2.6, 2.6, 0.22, "tex", 20),
                                    col="tex", riga=20),
                          scala=1.15, distorsione=7.5, dettaglio=8.0, tipo="BANDS",
                          direzione="X", profilo="SIN", col="tex", riga=20,
                          etichetta="Colature di fuliggine")
        m_fuliggine = S.rampa(striscia.outputs["Fac"], [(0.52, 0.0), (0.86, 1.0)],
                              "mask", 82, interp="EASE")
        m_fuliggine = S.matematica("MULTIPLY", m_fuliggine,
                                   S.matematica("SUBTRACT", S.valore(1.0, "mask", 83),
                                                S.matematica("MULTIPLY", rivolto_su,
                                                             S.valore(0.8, "mask", 83),
                                                             "mask", 84), "mask", 85),
                                   "mask", 86)
        m_fuliggine = S.matematica("MULTIPLY", m_fuliggine,
                                   S.matematica("ADD", S.valore(0.20, "mask", 87),
                                                S.matematica("MULTIPLY", calore,
                                                             S.valore(0.9, "mask", 87),
                                                             "mask", 88), "mask", 89),
                                   "mask", 90)
        m_fuliggine = S.matematica("MULTIPLY", m_fuliggine,
                                   S.rampa(S.matematica("MULTIPLY", n_grumo.outputs["Fac"],
                                                        S.valore(0.8, "mask", 145), "mask", 145),
                                           [(0.22, 0.15), (0.68, 1.0)], "mask", 145,
                                           interp="EASE"), "mask", 146)
        m_fuliggine = S.matematica("MULTIPLY", m_fuliggine,
                                   S.valore(fuliggine_peso, "mask", 91), "mask", 92,
                                   etichetta="Fuliggine")
    else:
        m_fuliggine = S.valore(0.0, "mask", 92)

    # --------------------------- metallo: ossidi, martellatura, scaglie, graffi
    if ruggine_peso > 0.0:
        ruggine_m = S.rampa(n_grumo.outputs["Fac"], [(0.44, 0.0), (0.66, 1.0)], "mask", 94,
                            interp="EASE")
        ruggine_m = S.matematica("MULTIPLY", ruggine_m,
                                 S.matematica("ADD", S.valore(0.30, "mask", 95),
                                              S.matematica("MULTIPLY",
                                                           S.matematica("ADD", rivolto_su,
                                                                        concavo, "mask", 96),
                                                           S.valore(0.7, "mask", 97),
                                                           "mask", 98), "mask", 99),
                                 "mask", 100)
        ruggine_m = S.matematica("MULTIPLY", ruggine_m,
                                 S.matematica("SUBTRACT", S.valore(1.0, "mask", 101),
                                              S.matematica("MULTIPLY", spigolo,
                                                           S.valore(0.65, "mask", 101),
                                                           "mask", 102), "mask", 103),
                                 "mask", 104)
        m_ruggine = S.matematica("MULTIPLY", ruggine_m, S.valore(ruggine_peso, "mask", 105),
                                 "mask", 106, etichetta="Ruggine e ossidi")
    else:
        m_ruggine = S.valore(0.0, "mask", 106)

    if martell_peso > 0.0:
        martello = S.voronoi(g_meso, scala=martell_mult, feature="F1", casualita=1.0,
                             col="tex", riga=22, etichetta="Martellatura")
        m_martello = S.rampa(martello.outputs["Distance"],
                             [(0.0, 1.0), (0.22, 0.45), (0.42, 0.0)], "mask", 107,
                             interp="EASE")
        m_martello = S.matematica("MULTIPLY", m_martello,
                                  S.valore(martell_peso, "mask", 108), "mask", 109,
                                  etichetta="Conche di forgia")
    else:
        m_martello = S.valore(0.0, "mask", 109)

    if scaglia_peso > 0.0:
        scaglia = S.voronoi(g_meso, scala=scaglia_mult, feature="DISTANCE_TO_EDGE",
                            casualita=1.0, col="tex", riga=24, etichetta="Scaglie di forgia")
        m_scaglia = S.rampa(scaglia.outputs["Distance"],
                            [(0.0, 1.0), (0.05, 0.65), (0.16, 0.0)], "mask", 110,
                            interp="EASE")
        m_scaglia = S.matematica("MULTIPLY", m_scaglia,
                                 S.valore(scaglia_peso, "mask", 111), "mask", 112,
                                 etichetta="Scaglie")
    else:
        m_scaglia = S.valore(0.0, "mask", 112)

    if graffi_peso > 0.0:
        graffio = S.onda(S.vettore("MULTIPLY", g_meso, S.combina(1.0, 1.0, 0.12, "tex", 26),
                                   col="tex", riga=26),
                         scala=graffio_mult, distorsione=11.0, dettaglio=9.0, tipo="BANDS",
                         direzione="Z", profilo="SAW", col="tex", riga=26, etichetta="Graffi")
        m_graffio = S.rampa(graffio.outputs["Fac"], [(0.55, 0.0), (0.78, 1.0)], "mask", 113,
                            interp="EASE")
        m_graffio = S.matematica("MULTIPLY", m_graffio, S.valore(graffi_peso, "mask", 114),
                                 "mask", 115, etichetta="Graffi")
    else:
        m_graffio = S.valore(0.0, "mask", 115)

    # ------------------------------------------------------ spigoli consumati
    m_usura = S.matematica("MULTIPLY", spigolo,
                           S.matematica("ADD", S.valore(0.45, "mask", 116),
                                        S.matematica("MULTIPLY", n_meso.outputs["Fac"],
                                                     S.valore(0.75, "mask", 117), "mask", 118),
                                        "mask", 119), "mask", 120)
    m_usura = S.matematica("MULTIPLY", m_usura, S.valore(usura_peso, "mask", 121),
                           "mask", 122, etichetta="Bordi consumati")

    # -------------------------------------------------------------- colore
    colore = S.miscela(S.rampa(n_macro.outputs["Fac"], [(0.30, 0.0), (0.72, 1.0)],
                               "mask", 124, interp="EASE", etichetta="Litologia"),
                       c_profondo, c_base, "mix", 0, etichetta="Corpo della roccia")
    colore = S.miscela(S.matematica("MULTIPLY",
                                    S.rampa(n_grumo.outputs["Fac"], [(0.26, 0.0), (0.68, 1.0)],
                                            "mask", 141, interp="EASE",
                                            etichetta="Chiazze di erosione"),
                                    S.valore(0.75, "mask", 141), "mask", 141),
                       colore, c_profondo, "mix", 1, etichetta="Chiazze di erosione")
    colore = S.miscela(S.rampa(n_meso.outputs["Fac"], [(0.52, 0.0), (0.86, 1.0)],
                               "mask", 125, interp="EASE"),
                       colore, c_chiaro, "mix", 2, etichetta="Inclusioni chiare")
    colore = S.miscela(S.matematica("MULTIPLY", n_grumo.outputs["Fac"],
                                    S.valore(0.45, "mask", 142), "mask", 142),
                       colore, c_chiaro, "mix", 3, etichetta="Venature chiare")
    # Il grit finestto vive soprattutto nell'albedo: il denoiser spiana il
    # micro-rilievo normale, mentre la variazione di colore gli sopravvive.
    grana = S.matematica("SUBTRACT", n_micro.outputs["Fac"],
                         S.valore(0.5, "mask", 126), "mask", 126, etichetta="Grit")
    colore = S.miscela(S.matematica("MULTIPLY",
                                    S.matematica("MAXIMUM", grana,
                                                 S.valore(0.0, "mask", 126), "mask", 126),
                                    S.valore(0.85, "mask", 127), "mask", 127),
                       colore, c_chiaro, "mix", 4, etichetta="Grit chiaro")
    colore = S.miscela(S.matematica("MULTIPLY",
                                    S.matematica("MAXIMUM",
                                                 S.matematica("SUBTRACT",
                                                              S.valore(0.0, "mask", 128),
                                                              grana, "mask", 128),
                                                 S.valore(0.0, "mask", 128), "mask", 128),
                                    S.valore(0.85, "mask", 129), "mask", 129),
                       colore, c_profondo, "mix", 5, etichetta="Grit scuro")
    if vaiolo_peso > 0.0:
        colore = S.miscela(S.matematica("MULTIPLY", vaioli, S.valore(0.85, "mask", 128),
                                        "mask", 129),
                           colore, c_profondo, "mix", 5, etichetta="Vaioli")
    if scaglia_peso > 0.0:
        colore = S.miscela(S.matematica("MULTIPLY", m_scaglia, S.valore(0.8, "mask", 130),
                                        "mask", 131),
                           colore, c_crepa, "mix", 6, etichetta="Scaglie di ossido")
    if scheggia_peso > 0.0:
        colore = S.miscela(schegge, colore, c_fresco, "mix", 7, etichetta="Facce di frattura")
    colore = S.miscela(m_usura, colore, c_fresco, "mix", 8, etichetta="Spigoli consumati")
    colore = S.miscela(craquelure, colore, c_crepa, "mix", 9, etichetta="Craquelure")
    colore = S.miscela(crepe, colore, c_crepa, "mix", 10, etichetta="Crepe profonde")
    colore = S.miscela(m_scottato, colore, c_scottatura, "mix", 11, etichetta="Scottature")
    colore = S.miscela(m_bruciato, colore, c_bruciato, "mix", 12, etichetta="Bruciature")
    if ruggine_peso > 0.0:
        colore = S.miscela(m_ruggine, colore, c_ruggine, "mix", 13, etichetta="Ossidi")
    colore = S.miscela(m_fuliggine, colore, c_fuliggine, "mix", 14, etichetta="Fuliggine")
    colore = S.miscela(S.matematica("MULTIPLY", m_cenere, S.valore(0.85, "mask", 132),
                                    "mask", 133),
                       colore, c_cenere, "mix", 15, etichetta="Cenere")
    if graffi_peso > 0.0:
        colore = S.miscela(S.matematica("MULTIPLY", m_graffio, S.valore(0.5, "mask", 134),
                                        "mask", 135),
                           colore, c_chiaro, "mix", 16, etichetta="Graffi")

    # Variazione per oggetto: nessun concio è identico al vicino.
    variazione = S.rampa(casuale, [(0.0, 0.80), (0.5, 1.0), (1.0, 1.22)], "mask", 136,
                         interp="EASE", etichetta="Variazione per oggetto")
    temperatura = S.rampa(casuale, [(0.0, 0.0), (1.0, 1.0)], "mask", 137)
    colore = S.prodotto_colore(colore, variazione, "mix", 17, etichetta="Colore per oggetto")
    caldo = S.combina(1.07, 1.0, 0.95, "mix", 18)
    colore = S.miscela(S.matematica("MULTIPLY", temperatura, S.valore(0.35, "mix", 19),
                                    "mix", 19),
                       colore, S.prodotto_colore(colore, caldo, "mix", 20), "mix", 21,
                       etichetta="Temperatura per oggetto")

    # ----------------------------------------------------------- roughness
    ruv = S.valore(ruvido, "rough", 0)
    ruv = S.matematica("ADD", ruv,
                       S.matematica("MULTIPLY",
                                    S.matematica("SUBTRACT", n_macro.outputs["Fac"],
                                                 S.valore(0.5, "rough", 1), "rough", 1),
                                    S.valore(0.16, "rough", 1), "rough", 2), "rough", 2)
    ruv = S.matematica("ADD", ruv,
                       S.matematica("MULTIPLY",
                                    S.matematica("SUBTRACT", n_meso.outputs["Fac"],
                                                 S.valore(0.5, "rough", 3), "rough", 3),
                                    S.valore(0.12, "rough", 3), "rough", 4), "rough", 4)
    ruv = S.matematica("ADD", ruv,
                       S.matematica("MULTIPLY",
                                    S.matematica("SUBTRACT", n_micro.outputs["Fac"],
                                                 S.valore(0.5, "rough", 5), "rough", 5),
                                    S.valore(0.07, "rough", 5), "rough", 6), "rough", 6)
    if vaiolo_peso > 0.0:
        ruv = S.miscela(S.matematica("MULTIPLY", vaioli, S.valore(0.8, "rough", 7), "rough", 7),
                        ruv, S.valore(0.98, "rough", 7), "rough", 7, tipo="VALORE",
                        etichetta="Vaioli opachi")
    if martell_peso > 0.0:
        ruv = S.miscela(S.matematica("MULTIPLY", m_martello, S.valore(0.55, "rough", 8),
                                     "rough", 8),
                        ruv, S.valore(0.82, "rough", 8), "rough", 8, tipo="VALORE",
                        etichetta="Fondo delle conche")
    if scaglia_peso > 0.0:
        ruv = S.miscela(S.matematica("MULTIPLY", m_scaglia, S.valore(0.7, "rough", 9),
                                     "rough", 9),
                        ruv, S.valore(0.92, "rough", 9), "rough", 9, tipo="VALORE")
    ruv = S.miscela(crepe, ruv, S.valore(0.97, "rough", 10), "rough", 10, tipo="VALORE",
                    etichetta="Fondo delle crepe")
    ruv = S.miscela(craquelure, ruv, S.valore(0.93, "rough", 11), "rough", 11, tipo="VALORE")
    ruv = S.miscela(S.matematica("MULTIPLY", m_cenere, S.valore(0.55, "rough", 12), "rough", 12),
                    ruv, S.valore(0.96, "rough", 12), "rough", 12, tipo="VALORE",
                    etichetta="Cenere opaca")
    ruv = S.miscela(S.matematica("MULTIPLY", m_fuliggine, S.valore(0.45, "rough", 13),
                                 "rough", 13),
                    ruv, S.valore(0.94, "rough", 13), "rough", 13, tipo="VALORE")
    if ruggine_peso > 0.0:
        ruv = S.miscela(m_ruggine, ruv, S.valore(0.88, "rough", 14), "rough", 14,
                        tipo="VALORE", etichetta="Ruggine")
    ruv = S.miscela(S.matematica("MULTIPLY", m_usura, S.valore(0.75, "rough", 15), "rough", 15),
                    ruv, S.valore(0.46, "rough", 15), "rough", 15, tipo="VALORE",
                    etichetta="Spigoli levigati")
    if graffi_peso > 0.0:
        ruv = S.miscela(S.matematica("MULTIPLY", m_graffio, S.valore(0.7, "rough", 16),
                                     "rough", 16),
                        ruv, S.valore(0.34, "rough", 16), "rough", 16, tipo="VALORE")
    ruv = S.miscela(vetro, ruv, S.valore(0.34, "rough", 17), "rough", 17, tipo="VALORE",
                    etichetta="Crosta vetrificata")
    ruv = S.matematica("ADD", ruv,
                       S.matematica("MULTIPLY",
                                    S.matematica("SUBTRACT", casuale,
                                                 S.valore(0.5, "rough", 18), "rough", 18),
                                    S.valore(0.12, "rough", 18), "rough", 18),
                       "rough", 18, etichetta="Roughness per oggetto")
    ruv = S.matematica("MAXIMUM", ruv, S.valore(0.05, "rough", 19), "rough", 19)
    ruv = S.matematica("MINIMUM", ruv, S.valore(1.0, "rough", 20), "rough", 20)

    # ------------------------------------------------------------ metallic
    metallo = S.valore(metallico, "rough", 22)
    if metallico > 0.01:
        if ruggine_peso > 0.0:
            metallo = S.miscela(m_ruggine, metallo, S.valore(0.12, "rough", 23), "rough", 23,
                                tipo="VALORE", etichetta="Ossidi non metallici")
        metallo = S.miscela(S.matematica("MULTIPLY", m_cenere, S.valore(0.6, "rough", 24),
                                         "rough", 24),
                            metallo, S.valore(0.05, "rough", 24), "rough", 24, tipo="VALORE")
        metallo = S.miscela(S.matematica("MULTIPLY", m_fuliggine, S.valore(0.6, "rough", 25),
                                         "rough", 25),
                            metallo, S.valore(0.15, "rough", 25), "rough", 25, tipo="VALORE")
        metallo = S.miscela(S.matematica("MULTIPLY", vetro, S.valore(0.8, "rough", 26),
                                         "rough", 26),
                            metallo, S.valore(0.02, "rough", 26), "rough", 26, tipo="VALORE")
    metallo = S.matematica("MAXIMUM", metallo, S.valore(0.0, "rough", 27), "rough", 27)
    metallo = S.matematica("MINIMUM", metallo, S.valore(1.0, "rough", 28), "rough", 28)

    # -------------------------------------------------------------- rilievo
    altezza = S.matematica("ADD",
                           S.matematica("MULTIPLY", n_macro.outputs["Fac"],
                                        S.valore(0.55, "bump", 0), "bump", 0),
                           S.matematica("MULTIPLY", n_meso.outputs["Fac"],
                                        S.valore(0.45, "bump", 1), "bump", 1), "bump", 1)
    altezza = S.matematica("SUBTRACT", altezza,
                           S.matematica("MULTIPLY", n_grumo.outputs["Fac"],
                                        S.valore(0.40, "bump", 20), "bump", 20), "bump", 20)
    altezza = S.matematica("SUBTRACT", altezza,
                           S.matematica("MULTIPLY", crepe, S.valore(0.85, "bump", 2),
                                        "bump", 2), "bump", 2)
    altezza = S.matematica("SUBTRACT", altezza,
                           S.matematica("MULTIPLY", craquelure, S.valore(0.35, "bump", 3),
                                        "bump", 3), "bump", 3)
    if vaiolo_peso > 0.0:
        altezza = S.matematica("SUBTRACT", altezza,
                               S.matematica("MULTIPLY", vaioli, S.valore(0.55, "bump", 4),
                                            "bump", 4), "bump", 4)
    if scheggia_peso > 0.0:
        altezza = S.matematica("SUBTRACT", altezza,
                               S.matematica("MULTIPLY", schegge, S.valore(0.75, "bump", 5),
                                            "bump", 5), "bump", 5)
    if martell_peso > 0.0:
        altezza = S.matematica("SUBTRACT", altezza,
                               S.matematica("MULTIPLY", m_martello, S.valore(0.5, "bump", 6),
                                            "bump", 6), "bump", 6)
    if scaglia_peso > 0.0:
        altezza = S.matematica("ADD", altezza,
                               S.matematica("MULTIPLY", m_scaglia, S.valore(0.4, "bump", 7),
                                            "bump", 7), "bump", 7)
    if ruggine_peso > 0.0:
        altezza = S.matematica("ADD", altezza,
                               S.matematica("MULTIPLY", m_ruggine, S.valore(0.45, "bump", 8),
                                            "bump", 8), "bump", 8)
    altezza = S.matematica("ADD", altezza,
                           S.matematica("MULTIPLY", n_micro.outputs["Fac"],
                                        S.valore(0.18, "bump", 9), "bump", 9), "bump", 9)

    bump_macro = S.nodo("ShaderNodeBump", "bump", 12, "Rilievo macro")
    bump_macro.inputs["Strength"].default_value = rilievo
    bump_macro.inputs["Distance"].default_value = rilievo_d
    S.L(altezza, bump_macro.inputs["Height"])
    bump_micro = S.nodo("ShaderNodeBump", "bump", 14, "Micro dettaglio")
    bump_micro.inputs["Strength"].default_value = microrilievo
    bump_micro.inputs["Distance"].default_value = microrilievo_d
    S.L(n_micro.outputs["Fac"], bump_micro.inputs["Height"])
    S.L(bump_macro.outputs["Normal"], bump_micro.inputs["Normal"])

    # --------------------------------------------------------------- uscite
    S.L(colore, bsdf.inputs["Base Color"])
    S.L(ruv, bsdf.inputs["Roughness"])
    S.L(metallo, bsdf.inputs["Metallic"])
    S.L(bump_micro.outputs["Normal"], bsdf.inputs["Normal"])

    if brace_peso > 0.0:
        nucleo = S.rampa(crepe, [(0.55, 0.0), (0.95, 1.0)], "mask", 138, interp="EASE",
                         etichetta="Nucleo incandescente")
        S.costante(bsdf.inputs["Emission Color"], c_brace)
        S.L(S.matematica("MULTIPLY", nucleo, S.valore(brace_peso, "mask", 139), "mask", 140,
                         etichetta="Brace nelle crepe"),
            bsdf.inputs["Emission Strength"])
    else:
        bsdf.inputs["Emission Strength"].default_value = 0.0

    S.inquadra()
    return S.mat


# -----------------------------------------------------------------------------
# Tavolozza comune e ricette dei singoli materiali
#
# Le scale dei domini sono espresse in "venature per metro": 0.5 ≈ chiazze da
# due metri, 3.2 ≈ grana da 30 cm, 15 ≈ grit da 6-7 cm.  Le misure dei difetti
# (crepe, craquelure, vaioli, schegge, martellatura, scaglie, graffi) invece
# sono in metri e vengono convertite nella scala del dominio che le ospita, così
# si può ritoccare la grana senza deformare i dettagli.  Le scale fini sono
# calibrate sulla risoluzione di render del progetto (la porta occupa circa
# 1700 px per 18 unità: ~90 px/unità), perché il micro-dettaglio resti visibile
# senza scivolare sotto il pixel.
# -----------------------------------------------------------------------------
PIETRA_COMUNE = {
    "col_profondo": (0.0085, 0.0090, 0.0115),
    "col_base": (0.052, 0.050, 0.049),
    "col_chiaro": (0.115, 0.110, 0.104),
    "col_fresco": (0.098, 0.092, 0.085),
    "col_crepa": (0.0022, 0.0022, 0.0028),
    "col_cenere": (0.150, 0.138, 0.129),
    "col_fuliggine": (0.0075, 0.0068, 0.0068),
    "col_bruciato": (0.0050, 0.0042, 0.0042),
    "col_scottatura": (0.058, 0.024, 0.013),
}

stone = materiale_eroso(
    "Basalto vulcanico | eroso, crepato, coperto di cenere",
    (0.080, 0.076, 0.072),
    dict(PIETRA_COMUNE,
         col_profondo=(0.0185, 0.0185, 0.0205),
         col_base=(0.098, 0.092, 0.087),
         col_chiaro=(0.208, 0.196, 0.182),
         col_fresco=(0.172, 0.160, 0.146),
         col_crepa=(0.0030, 0.0029, 0.0034),
         col_cenere=(0.196, 0.180, 0.168),
         col_scottatura=(0.080, 0.032, 0.017),
         macro=(0.50, 6.0), meso=(3.23, 8.0), micro=(15.4, 3.0),
         medio=(2.00, 7.0),
         crepa=(1.29, 1.00, 0.097), craquelure=(0.167, 0.42, 0.0117),
         vaioli=(0.061, 0.50), schegge=(0.099, 0.55),
         bruciatura=(0.33, 0.62), cenere=0.46, fuliggine=0.42, usura=0.55,
         rilievo=(0.95, 0.055), microrilievo=(0.20, 0.006),
         ruvido=0.88, metallico=0.02, vetrificato=0.30, brace=0.05))

stone_light = materiale_eroso(
    "Tufo vulcanico | conci chiari e spigoli consumati",
    (0.140, 0.132, 0.122),
    dict(PIETRA_COMUNE,
         col_profondo=(0.037, 0.036, 0.038),
         col_base=(0.152, 0.143, 0.133),
         col_chiaro=(0.285, 0.268, 0.246),
         col_fresco=(0.240, 0.223, 0.203),
         col_crepa=(0.0060, 0.0058, 0.0066),
         col_cenere=(0.245, 0.226, 0.208),
         macro=(0.58, 6.0), meso=(3.44, 8.0), micro=(16.8, 3.0),
         medio=(2.20, 7.0),
         crepa=(0.99, 0.85, 0.069), craquelure=(0.139, 0.38, 0.0097),
         vaioli=(0.056, 0.42), schegge=(0.081, 0.70),
         bruciatura=(0.35, 0.50), cenere=0.55, fuliggine=0.34, usura=0.72,
         rilievo=(0.85, 0.048), microrilievo=(0.18, 0.005),
         ruvido=0.84, metallico=0.02, vetrificato=0.22))

stone_dark = materiale_eroso(
    "Roccia carbonizzata | crosta sfaldata e crepe profonde",
    (0.045, 0.042, 0.042),
    dict(PIETRA_COMUNE,
         col_profondo=(0.0085, 0.0078, 0.0082),
         col_base=(0.057, 0.053, 0.053),
         col_chiaro=(0.125, 0.117, 0.112),
         col_fresco=(0.109, 0.100, 0.093),
         col_crepa=(0.0016, 0.0015, 0.0017),
         col_cenere=(0.150, 0.136, 0.128),
         col_fuliggine=(0.0058, 0.0052, 0.0052),
         col_bruciato=(0.0040, 0.0034, 0.0034),
         col_scottatura=(0.062, 0.024, 0.012),
         macro=(0.46, 7.0), meso=(2.99, 9.0), micro=(14.0, 3.0),
         medio=(1.90, 7.0),
         crepa=(1.74, 1.00, 0.165), craquelure=(0.204, 0.55, 0.0174),
         vaioli=(0.067, 0.55), schegge=(0.134, 0.85),
         bruciatura=(0.30, 0.85), cenere=0.36, fuliggine=0.60, usura=0.42,
         rilievo=(1.05, 0.065), microrilievo=(0.22, 0.007),
         ruvido=0.92, metallico=0.03, vetrificato=0.45, brace=0.16))

stone_shadow = materiale_eroso(
    "Basalto in ombra | fondo profondo e polveroso",
    (0.030, 0.032, 0.038),
    dict(PIETRA_COMUNE,
         col_profondo=(0.0060, 0.0062, 0.0074),
         col_base=(0.043, 0.044, 0.051),
         col_chiaro=(0.095, 0.097, 0.107),
         col_fresco=(0.074, 0.075, 0.081),
         col_crepa=(0.0013, 0.0013, 0.0016),
         col_cenere=(0.115, 0.107, 0.104),
         macro=(0.44, 6.0), meso=(2.82, 8.0), micro=(12.6, 3.0),
         medio=(1.80, 7.0),
         crepa=(1.89, 0.80, 0.161), craquelure=(0.256, 0.35, 0.0179),
         vaioli=(0.074, 0.35), schegge=(0.175, 0.45),
         bruciatura=(0.30, 0.45), cenere=0.40, fuliggine=0.45, usura=0.30,
         rilievo=(0.80, 0.045), microrilievo=(0.16, 0.005),
         ruvido=0.94, metallico=0.02, vetrificato=0.20))

iron = materiale_eroso(
    "Ferro annerito | forgia, ossidi e fuliggine",
    (0.055, 0.052, 0.050),
    dict(PIETRA_COMUNE,
         col_profondo=(0.0052, 0.0049, 0.0049),
         col_base=(0.038, 0.036, 0.035),
         col_chiaro=(0.100, 0.096, 0.092),
         col_fresco=(0.086, 0.082, 0.078),
         col_crepa=(0.0018, 0.0017, 0.0017),
         col_cenere=(0.135, 0.124, 0.117),
         col_fuliggine=(0.0058, 0.0053, 0.0053),
         col_bruciato=(0.0042, 0.0037, 0.0037),
         col_scottatura=(0.060, 0.022, 0.012),
         col_ruggine=(0.095, 0.038, 0.017),
         macro=(0.85, 6.0), meso=(4.18, 8.0), micro=(17.0, 3.0),
         medio=(3.00, 7.0),
         crepa=(0.45, 0.55, 0.030), craquelure=(0.110, 0.40, 0.020),
         vaioli=(0.060, 0.00), schegge=(0.070, 0.32),
         bruciatura=(0.40, 0.60), cenere=0.30, fuliggine=0.55, usura=0.75,
         ruggine=0.42, graffi=(0.031, 0.35), martellatura=(0.14, 0.60), scaglie=(0.15, 0.60),
         rilievo=(0.70, 0.030), microrilievo=(0.20, 0.004),
         ruvido=0.62, metallico=0.94, vetrificato=0.20))

iron_leaf = materiale_eroso(
    "Ferro dei battenti | scaglie di forgia e colature di fuliggine",
    (0.048, 0.045, 0.044),
    dict(PIETRA_COMUNE,
         col_profondo=(0.0046, 0.0044, 0.0044),
         col_base=(0.034, 0.032, 0.031),
         col_chiaro=(0.092, 0.088, 0.084),
         col_fresco=(0.080, 0.076, 0.073),
         col_crepa=(0.0016, 0.0015, 0.0015),
         col_cenere=(0.115, 0.105, 0.099),
         col_fuliggine=(0.0052, 0.0048, 0.0048),
         col_bruciato=(0.0038, 0.0034, 0.0034),
         col_scottatura=(0.055, 0.020, 0.011),
         col_ruggine=(0.088, 0.035, 0.015),
         macro=(0.70, 6.0), meso=(3.78, 8.0), micro=(16.0, 3.0),
         medio=(2.80, 7.0),
         crepa=(0.68, 0.75, 0.037), craquelure=(0.120, 0.42, 0.022),
         vaioli=(0.060, 0.00), schegge=(0.085, 0.42),
         bruciatura=(0.36, 0.72), cenere=0.28, fuliggine=0.66, usura=0.70,
         ruggine=0.30, graffi=(0.035, 0.30), martellatura=(0.14, 0.68), scaglie=(0.14, 0.78),
         rilievo=(0.80, 0.034), microrilievo=(0.20, 0.004),
         ruvido=0.65, metallico=0.92, vetrificato=0.18, brace=0.05))

bronze = materiale_eroso(
    "Bronzo annerito | patina, ossidi e colature",
    (0.080, 0.048, 0.024),
    dict(PIETRA_COMUNE,
         col_profondo=(0.0082, 0.0050, 0.0030),
         col_base=(0.058, 0.034, 0.016),
         col_chiaro=(0.185, 0.113, 0.047),
         col_fresco=(0.150, 0.092, 0.038),
         col_crepa=(0.0026, 0.0019, 0.0014),
         col_cenere=(0.155, 0.135, 0.118),
         col_fuliggine=(0.0062, 0.0050, 0.0042),
         col_bruciato=(0.0044, 0.0034, 0.0028),
         col_scottatura=(0.080, 0.032, 0.014),
         col_ruggine=(0.060, 0.070, 0.042),
         macro=(0.95, 6.0), meso=(4.62, 8.0), micro=(18.0, 3.0),
         medio=(3.20, 7.0),
         crepa=(0.35, 0.45, 0.026), craquelure=(0.100, 0.38, 0.018),
         vaioli=(0.060, 0.00), schegge=(0.055, 0.30),
         bruciatura=(0.42, 0.55), cenere=0.28, fuliggine=0.50, usura=0.90,
         ruggine=0.34, graffi=(0.028, 0.30), martellatura=(0.13, 0.48), scaglie=(0.10, 0.55),
         rilievo=(0.58, 0.022), microrilievo=(0.18, 0.003),
         ruvido=0.48, metallico=0.90, vetrificato=0.15))

gold = materiale_eroso(
    "Ottone antico | iscrizioni annerite e spigoli lucidi",
    (0.32, 0.19, 0.065),
    dict(PIETRA_COMUNE,
         col_profondo=(0.024, 0.0110, 0.0036),
         col_base=(0.180, 0.102, 0.032),
         col_chiaro=(0.520, 0.325, 0.114),
         col_fresco=(0.430, 0.270, 0.094),
         col_crepa=(0.0050, 0.0029, 0.0018),
         col_cenere=(0.175, 0.148, 0.122),
         col_fuliggine=(0.0092, 0.0068, 0.0046),
         col_bruciato=(0.0058, 0.0040, 0.0027),
         col_scottatura=(0.100, 0.038, 0.015),
         col_ruggine=(0.078, 0.082, 0.048),
         macro=(1.15, 6.0), meso=(4.20, 8.0), micro=(14.0, 3.0),
         medio=(3.60, 7.0),
         crepa=(0.24, 0.35, 0.018), craquelure=(0.090, 0.34, 0.016),
         vaioli=(0.060, 0.00), schegge=(0.045, 0.28),
         bruciatura=(0.48, 0.45), cenere=0.24, fuliggine=0.42, usura=0.95,
         ruggine=0.22, graffi=(0.025, 0.35), martellatura=(0.11, 0.42), scaglie=(0.08, 0.42),
         rilievo=(0.58, 0.020), microrilievo=(0.20, 0.004),
         ruvido=0.40, metallico=0.92, vetrificato=0.12))

bone = materiale_eroso(
    "Osso consunto | avorio affumicato e screpolato",
    (0.30, 0.255, 0.200),
    dict(PIETRA_COMUNE,
         col_profondo=(0.038, 0.031, 0.024),
         col_base=(0.215, 0.176, 0.130),
         col_chiaro=(0.470, 0.412, 0.312),
         col_fresco=(0.395, 0.343, 0.258),
         col_crepa=(0.011, 0.009, 0.007),
         col_cenere=(0.205, 0.180, 0.157),
         col_fuliggine=(0.013, 0.010, 0.009),
         col_bruciato=(0.0090, 0.0074, 0.0065),
         col_scottatura=(0.095, 0.045, 0.022),
         macro=(1.90, 6.0), meso=(5.00, 9.0), micro=(14.0, 3.0),
         medio=(4.50, 7.0),
         crepa=(0.26, 0.30, 0.018), craquelure=(0.075, 0.55, 0.010),
         vaioli=(0.050, 0.35), schegge=(0.050, 0.30),
         bruciatura=(0.55, 0.50), cenere=0.28, fuliggine=0.45, usura=0.80,
         rilievo=(0.62, 0.020), microrilievo=(0.22, 0.004),
         ruvido=0.68, metallico=0.02, vetrificato=0.10))

bone_shadow = materiale_eroso(
    "Osso in ombra | teschio annerito dal fumo",
    (0.14, 0.12, 0.095),
    dict(PIETRA_COMUNE,
         col_profondo=(0.016, 0.013, 0.011),
         col_base=(0.090, 0.074, 0.055),
         col_chiaro=(0.210, 0.178, 0.130),
         col_fresco=(0.165, 0.138, 0.104),
         col_crepa=(0.0050, 0.0040, 0.0034),
         col_cenere=(0.145, 0.126, 0.111),
         col_fuliggine=(0.0078, 0.0064, 0.0055),
         col_bruciato=(0.0054, 0.0045, 0.0040),
         col_scottatura=(0.070, 0.030, 0.015),
         macro=(1.90, 6.0), meso=(5.00, 9.0), micro=(14.0, 3.0),
         medio=(4.50, 7.0),
         crepa=(0.26, 0.35, 0.018), craquelure=(0.075, 0.60, 0.010),
         vaioli=(0.050, 0.35), schegge=(0.050, 0.30),
         bruciatura=(0.55, 0.62), cenere=0.24, fuliggine=0.60, usura=0.70,
         rilievo=(0.60, 0.018), microrilievo=(0.20, 0.004),
         ruvido=0.72, metallico=0.02, vetrificato=0.10))

void_mat = materiale_eroso(
    "Vuoto | nero profondo e poroso",
    (0.005, 0.005, 0.007),
    dict(PIETRA_COMUNE,
         col_profondo=(0.0011, 0.0011, 0.0015),
         col_base=(0.0045, 0.0045, 0.0058),
         col_chiaro=(0.013, 0.013, 0.016),
         col_fresco=(0.010, 0.010, 0.012),
         col_crepa=(0.0005, 0.0005, 0.0006),
         col_cenere=(0.024, 0.023, 0.024),
         col_fuliggine=(0.0015, 0.0014, 0.0015),
         col_bruciato=(0.0011, 0.0010, 0.0011),
         col_scottatura=(0.014, 0.005, 0.003),
         macro=(0.60, 5.0), meso=(2.82, 7.0), micro=(12.6, 3.0),
         medio=(1.80, 7.0),
         crepa=(1.19, 0.50, 0.071), craquelure=(0.208, 0.25, 0.0104),
         vaioli=(0.074, 0.20), schegge=(0.159, 0.20),
         bruciatura=(0.30, 0.40), cenere=0.20, fuliggine=0.35, usura=0.20,
         rilievo=(0.45, 0.020), microrilievo=(0.12, 0.003),
         ruvido=0.90, metallico=0.05, vetrificato=0.10))

def principled_material(name, base=(0.2, 0.2, 0.2, 1), metallic=0.0, roughness=0.6,
                        noise_scale=0.0, bump_strength=0.0, bump_distance=0.04,
                        color_low=None, color_high=None):
    """Materiale semplice (vapori, fumo): interfaccia mantenuta per compatibilità."""
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

lava_mat = materiale_eroso(
    "Lava | crosta nera, vene incandescenti e cenere",
    (0.10, 0.020, 0.006),
    dict(PIETRA_COMUNE,
         col_profondo=(0.0026, 0.0016, 0.0016),
         col_base=(0.020, 0.011, 0.009),
         col_chiaro=(0.075, 0.030, 0.014),
         col_fresco=(0.060, 0.024, 0.011),
         col_crepa=(0.0010, 0.0007, 0.0007),
         col_cenere=(0.095, 0.082, 0.078),
         col_fuliggine=(0.0040, 0.0022, 0.0020),
         col_bruciato=(0.0024, 0.0014, 0.0013),
         col_scottatura=(0.140, 0.030, 0.010),
         col_brace=(1.0, 0.20, 0.014),
         macro=(0.55, 7.0), meso=(2.60, 9.0), micro=(11.2, 3.0),
         medio=(1.60, 7.0),
         crepa=(0.70, 1.00, 0.112), craquelure=(0.275, 0.65, 0.0385),
         vaioli=(0.083, 0.70), schegge=(0.226, 0.55),
         bruciatura=(0.30, 0.70), cenere=0.22, fuliggine=0.30, usura=0.25,
         rilievo=(1.00, 0.060), microrilievo=(0.22, 0.007),
         ruvido=0.78, metallico=0.05, vetrificato=0.55, brace=1.35))

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
add_box("Basamento | lastra infernale", (0, -1.2, -0.22), (17.6, 11.5, 0.42), stone_dark, 0.12)
add_box("Pianoro di basalto", (0, -7.6, -0.36), (42, 26, 0.28), stone_dark, 0.05)
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

# Four broad, worn steps. Their dark edges catch the molten spill from the portal.
for i, (yy, width, zz, thick) in enumerate([
        (-0.82, 8.6, 0.16, 0.34), (-1.57, 9.2, 0.34, 0.34),
        (-2.32, 9.8, 0.52, 0.36), (-3.07, 10.4, 0.70, 0.38)]):
    add_box(f"Gradino cerimoniale {i+1}", (0, yy, zz), (width, 0.92, thick),
            stone_light if i == 3 else stone, 0.09)
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
# Main masonry: monumental facade, nested pointed orders, towers and carvings
# -----------------------------------------------------------------------------
use_collection("01 • Architettura | basalto e conci")

# Nested pointed (Gothic) orders: three concentric archivolts, each stepped
# forward so raking light carves deep shadows between them. Asymmetric scars:
# one missing voussoir in the outer order, a master crack across the left haunch.
ORD2_IN = (4.13, 5.25, 10.75)
ORD2_OUT = (4.97, 5.35, 11.85)
ORD3_IN = (5.63, 5.05, 12.10)
ORD3_OUT = (6.47, 5.15, 13.20)

def add_order(tag, inner, outer, y0, y1, skip=()):
    for side in (-1, 1):
        for i in range(15):
            if (side, i) in skip:
                continue
            t0 = i / 15.0 + 0.005
            t1 = (i + 1) / 15.0 - 0.005
            outline = [arch_point(t0, *inner, side), arch_point(t1, *inner, side),
                       arch_point(t1, *outer, side), arch_point(t0, *outer, side)]
            add_extruded_polygon(f"Ordine {tag} | concio {side:+d}.{i+1:02d}", outline,
                                 y0, y1,
                                 random.choice([stone_light, stone_light, stone, stone_light]),
                                 bevel=0.03)
        lin = arch_points(inner[0]-0.05, inner[1], inner[2]-0.03, side, steps=72)
        add_curve(f"Ordine {tag} | gola interna {side:+d}",
                  [(x, y0-0.05, z) for x, z in lin], 0.045, bronze, resolution=3)
        lout = arch_points(outer[0]+0.02, outer[1]+0.01, outer[2]+0.03, side, steps=72)
        add_curve(f"Ordine {tag} | cordone esterno {side:+d}",
                  [(x, y0-0.02, z) for x, z in lout], 0.07, stone_light, resolution=3)

add_order(2, ORD2_IN, ORD2_OUT, -1.30, -0.94)
add_order(3, ORD3_IN, ORD3_OUT, -1.62, -1.30, skip={(-1, 7)})

# Deep shadow wall behind the orders: the facade reads as solid mass, not frame.
add_box("Fondo d'ombra | parete profonda", (0, -0.62, 11.30), (9.9, 0.5, 4.0), stone_shadow, 0.06)
# Coursed joints carved across the spandrel mass.
for jz in (9.75, 10.60, 11.45, 12.30, 13.15):
    add_box(f"Giunto corso del fondo {jz:.2f}", (0, -0.885, jz), (9.7, 0.06, 0.05), stone_dark, 0.01)

def niche_outline(cx, cz, w, drop, top):
    r = arch_points(w, cz, cz+top, side=1, steps=10)
    l = arch_points(w, cz, cz+top, side=-1, steps=10)
    return ([(cx-w, cz-drop), (cx+w, cz-drop)] +
            [(cx+x, z) for x, z in r] +
            [(cx+x, z) for x, z in reversed(l)][1:])

# Ragged teeth hanging from the mass bottom edge: erosion, not a clean line.
for k, jx in enumerate((-4.3, -3.1, -1.6, 0.4, 1.9, 3.4, 4.5)):
    add_box(f"Dente pendente del fondo {k+1}",
            (jx, -0.80, 9.30-random.uniform(0.12, 0.44)),
            (random.uniform(0.5, 0.9), 0.42, random.uniform(0.3, 0.62)),
            random.choice([stone, stone_dark]), 0.04)

# Blind arcade: two staggered rows of deeply carved pointed niches (asymmetric).
for row, zc in enumerate((9.90, 11.15)):
    off = 0.26 if row else -0.18
    for k in range(-4, 5):
        xx = k*1.08 + off
        if abs(xx) > 4.55:
            continue
        add_arch_fill(f"Nicchia cieca {row+1}.{k+5}", niche_outline(xx, zc, 0.46, 0.62, 0.72),
                      -0.885, void_mat)
        fr = arch_points(0.56, zc, zc+0.80, side=1, steps=10)
        fl = arch_points(0.56, zc, zc+0.80, side=-1, steps=10)
        pts = [(xx+x, -0.93, z) for x, z in reversed(fl)] + [(xx+x, -0.93, z) for x, z in fr][1:]
        add_curve(f"Cornice della nicchia {row+1}.{k+5}", pts, 0.05, stone, resolution=2)

# Chevron incision chasing the second order: a carved zigzag of shadow.
chev = []
for j in range(41):
    t = j / 40.0
    x, z = arch_point(t, 4.55, 5.30, 11.30, -1)
    chev.append((x, -1.34 if j % 2 else -1.44, z))
for side in (-1, 1):
    pts = [(-p[0], p[1], p[2]) for p in chev] if side > 0 else chev
    add_curve(f"Chevron inciso nell'ordine {side:+d}", pts, 0.042, stone_dark, resolution=1)

# Master crack: a diagonal scar from the outer order down through the haunch.
add_curve("Fenditura maestra | attraverso l'ordine",
          [(-5.9, -1.66, 12.2), (-5.2, -1.58, 11.3), (-4.6, -1.48, 10.5),
           (-4.2, -1.40, 9.6), (-3.9, -1.34, 8.9)], 0.035, stone_dark, resolution=2)
add_curve("Fenditura maestra | ramo",
          [(-4.6, -1.48, 10.5), (-4.1, -1.44, 10.9), (-3.6, -1.38, 11.3)],
          0.024, stone_dark, resolution=1)

# Load-bearing piers flanking the opening (inner order).
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

# Massive clustered columns: four engaged shafts around a core, deep flutes,
# heavy capitals carrying the second order.
for side in (-1, 1):
    cx = side*4.55
    add_box(f"Plinto del pilastro {side:+d}", (cx, -0.55, 0.55), (1.66, 1.52, 1.06),
            stone_light, 0.09)
    add_box(f"Anima del pilastro {side:+d}", (cx, -0.55, 3.02), (0.94, 0.94, 4.9),
            stone, 0.05)
    for q, (dx, dy) in enumerate([(-0.40, -0.40), (0.40, -0.40), (-0.40, 0.30), (0.40, 0.30)]):
        add_cylinder(f"Colonnetta impegnata {side:+d}.{q+1}", (cx+dx, -0.55+dy, 3.05),
                     0.26, 4.95, stone_light, vertices=12, bevel=0.02)
        if dy < 0:
            add_box(f"Scanalatura profonda {side:+d}.{q+1}", (cx+dx, -1.19, 3.05),
                    (0.075, 0.10, 4.5), stone_dark, 0.012)
    add_cone(f"Cappa del capitello {side:+d}", (cx, -0.55, 5.02), 0.62, 0.88, 0.46,
             stone, vertices=8)
    add_box(f"Gola del capitello {side:+d}", (cx, -0.62, 5.22), (1.42, 1.44, 0.10),
            bronze, 0.02)
    add_box(f"Abaco del pilastro {side:+d}", (cx, -0.58, 5.40), (1.70, 1.52, 0.34),
            stone_light, 0.05)
    add_ico(f"Maschera consunta del pilastro {side:+d}", (cx, -1.30, 5.40),
            (0.20, 0.10, 0.16), bone_shadow, subdivisions=1)

# Shoulder walls between columns and towers: irregular courses, one settled run.
for side in (-1, 1):
    for row in range(12):
        zc = 0.62 + row * 1.02
        if zc > 12.6:
            break
        settled = (side == 1 and row in (6, 7, 8))
        dx, dz, rot = (0.16, -0.19, 0.030) if settled else (0.0, 0.0, random.uniform(-0.012, 0.012))
        b = add_box(f"Concio di spalla {side:+d}.{row+1:02d}",
                    (side*5.35 + dx, -0.35, zc + dz), (1.06, 0.95, 0.94),
                    random.choice([stone, stone_light, stone, stone_dark]), 0.06)
        b.rotation_euler[1] = rot

# Asymmetric buttress towers: left one taller and broken, right one lower,
# leaning and crowned by a wind-tilted spire. Built to outlast millennia.
TOWERS = {-1: {"top": 14.0, "broken": True, "lean": 0.0},
          1: {"top": 12.6, "broken": False, "lean": 0.013}}
for side, spec in TOWERS.items():
    tx = side*6.75
    lean = spec["lean"]
    widths = [2.02, 1.82, 1.62, 1.42]
    zbounds = [0.0, 5.0, 9.3, 13.1, 99.0]
    for s_i in range(4):
        z0 = zbounds[s_i]
        if z0 >= spec["top"]:
            break
        z1 = min(zbounds[s_i+1], spec["top"])
        h = z1 - z0
        zc = z0 + h/2
        shift = side*lean*zc*2.2
        b = add_box(f"Torre {side:+d} | tronco {s_i+1}", (tx+shift, -0.75, zc),
                    (widths[s_i], 2.00, h), stone if s_i % 2 else stone_light, 0.07)
        b.rotation_euler[1] = side*lean + random.uniform(-0.005, 0.005)
        # deep horizontal groove at each setback
        add_box(f"Torre {side:+d} | gola del ritiro {s_i+1}", (tx+shift, -1.78, z1),
                (widths[s_i]+0.18, 0.14, 0.17), stone_dark, 0.02)
        # vertical corner incisions
        for cside in (-1, 1):
            add_box(f"Torre {side:+d} | incisione d'angolo {s_i+1}.{cside:+d}",
                    (tx+shift+cside*widths[s_i]*0.42, -1.76, zc),
                    (0.07, 0.08, h-0.25), stone_dark, 0.01)
        # rune-like dashes carved in the face
        for k in range(3):
            rz = z0 + 0.8 + k*1.15 + random.uniform(-0.15, 0.15)
            if rz > z1 - 0.4:
                continue
            add_box(f"Torre {side:+d} | tacca {s_i+1}.{k+1}",
                    (tx+shift+random.uniform(-0.35, 0.35), -1.77, rz),
                    (random.uniform(0.16, 0.34), 0.07, 0.09), stone_dark, 0.01)
    if spec["broken"]:
        for k, (dx, h, tilt) in enumerate([(-0.45, 2.0, -0.16), (0.05, 1.2, 0.05),
                                           (0.5, 2.5, 0.22)]):
            s = add_cone(f"Torre {side:+d} | dente di rovina {k+1}",
                         (tx+dx, -0.75, spec["top"]+h/2-0.25), 0.32, 0.05, h,
                         stone, vertices=5)
            s.rotation_euler[1] = tilt
        add_ico(f"Torre {side:+d} | cavità del crollo", (tx+0.1, -1.05, spec["top"]-0.15),
                (0.52, 0.36, 0.30), void_mat, subdivisions=1)
        for k in range(6):
            add_ico(f"Maceria della torre {side:+d}.{k+1}",
                    (tx+random.uniform(-1.5, 1.5), random.uniform(-2.4, -1.0), 0.14),
                    (random.uniform(0.16, 0.40), random.uniform(0.16, 0.38),
                     random.uniform(0.12, 0.30)),
                    random.choice([stone_dark, stone]), subdivisions=1)
    else:
        add_box(f"Torre {side:+d} | cornice sommitale",
                (tx+side*lean*spec["top"]*2.2, -0.80, spec["top"]+0.16),
                (1.52, 1.82, 0.32), stone_light, 0.05)
        p = add_cone(f"Torre {side:+d} | guglia inclinata",
                     (tx+side*lean*spec["top"]*2.2, -0.80, spec["top"]+1.45),
                     0.62, 0.0, 2.3, stone, vertices=8)
        p.rotation_euler[1] = 0.06
        p.rotation_euler[0] = -0.035

# Flying buttress: intact on the left, collapsed stub on the right.
fly = [(-6.75, -0.75, 10.6), (-6.30, -0.75, 11.3), (-5.70, -0.75, 11.9), (-5.35, -0.75, 12.4)]
add_curve("Arco rampante | sinistro", fly, 0.20, stone, resolution=3)
add_curve("Arco rampante | nervatura sinistra",
          [(x, y-0.20, z+0.17) for x, y, z in fly], 0.07, stone_light, resolution=3)
add_curve("Arco rampante | destro spezzato",
          [(6.75, -0.75, 10.4), (6.45, -0.75, 10.9)], 0.20, stone, resolution=3)
frag = add_ico("Frammento dell'arco caduto", (5.55, -1.95, 0.34), (0.55, 0.40, 0.30),
               stone, subdivisions=1)
frag.rotation_euler = (0.3, 0.5, 0.8)

# Heavy plinth across the facade and a narrow moulding with carved dentils.
add_box("Zoccolo continuo del portale", (0, -0.39, 0.46), (15.9, 0.95, 0.84), stone_light, 0.1)
add_box("Cimasa inferiore | bronzo scuro", (0, -0.91, 0.90), (15.7, 0.13, 0.12), bronze, 0.025)
for i in range(37):
    x = -7.65 + i * 0.425
    add_box(f"Dentello del plinto {i+1:02d}", (x, -0.91, 1.03), (0.22, 0.10, 0.11),
            stone, 0.018)

# The pointed archivolt (inner order) is assembled from bevelled voussoirs.
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

# -----------------------------------------------------------------------------
# Crown: cornice, incised frieze, broken pediment, rose window, pinnacles
# -----------------------------------------------------------------------------
add_box("Architrave | mensola alta", (0, -0.72, 14.30), (13.6, 1.35, 0.44), stone_light, 0.08)
add_box("Fascia d'ombra dell'architrave", (0, -1.42, 14.02), (13.4, 0.16, 0.15), bronze, 0.025)
# Frieze of deep glyphs: irregular widths and depths, hand-carved and worn.
for i in range(40):
    x = -6.15 + i * 0.315 + random.uniform(-0.025, 0.025)
    d = random.uniform(0.05, 0.14)
    add_box(f"Glifo inciso del fregio {i+1:02d}", (x, -1.40-d*0.5, 14.28),
            (random.uniform(0.12, 0.20), d, random.uniform(0.16, 0.32)), stone_dark, 0.012)
# Spandrel courses over the outer order.
for row in range(2):
    zc = 14.66 + row * 0.76
    for col in range(9):
        xc = -6.6 + col * 1.65 + (0.2 if row % 2 else 0)
        if abs(xc) > 6.9:
            continue
        add_box(f"Concio del coronamento {row+1}.{col+1}", (xc, -0.05, zc),
                (1.56, 0.9, 0.7), random.choice([stone, stone_light, stone]), 0.06)
# Gable field behind the broken pediment.
add_extruded_polygon("Campo del frontone",
                     [(-6.2, 15.40), (6.2, 15.40), (-0.15, 16.95)],
                     -0.35, -0.12, stone, bevel=0.05)
# Broken pediment: two raking cornices of different heights that never meet.
add_extruded_polygon("Frontone spezzato | rampa sinistra",
                     [(-6.2, 15.40), (-1.35, 17.30), (-1.35, 17.84), (-6.2, 15.98)],
                     -0.74, -0.30, stone_light, bevel=0.055)
add_extruded_polygon("Frontone spezzato | rampa destra",
                     [(6.2, 15.40), (6.2, 15.98), (1.05, 17.26), (1.05, 16.74)],
                     -0.74, -0.30, stone, bevel=0.055)
for side, tip in ((-1, (-1.35, 17.57)), (1, (1.05, 17.00))):
    add_curve(f"Cornice inclinata del frontone {side:+d}",
              [(side*6.05, -0.80, 15.56), (side*3.4, -0.80, 16.40),
               (tip[0], -0.80, tip[1])], 0.075, gold, resolution=3)
# Rose window in the pediment field: ring, dark void, gilded spokes, bone hub.
add_uv_sphere("Disco della rosa | vuoto", (-0.15, -0.30, 16.10), (1.00, 0.10, 1.00),
              void_mat, segments=24, rings=12)
add_torus("Anello della rosa", (-0.15, -0.42, 16.10), 1.04, 0.10, stone_light,
          rotation=(math.pi/2, 0, 0))
add_torus("Anello interno della rosa", (-0.15, -0.46, 16.10), 0.62, 0.05, bronze,
          rotation=(math.pi/2, 0, 0))
for k in range(12):
    a = k * math.tau / 12
    add_rod(f"Raggio della rosa {k+1}",
            (-0.15+math.cos(a)*0.10, -0.44, 16.10+math.sin(a)*0.10),
            (-0.15+math.cos(a)*0.98, -0.44, 16.10+math.sin(a)*0.98),
            0.028, gold, 6)
add_ico("Mozzo della rosa | teschio", (-0.15, -0.50, 16.10), (0.16, 0.10, 0.17),
        bone_shadow, subdivisions=2)
# Pinnacles: left one a broken stump, right one intact but weary.
x = -5.9
add_box("Pinnacolo spezzato | base", (x, -0.87, 14.70), (0.82, 0.68, 0.44), stone_light, 0.055)
st = add_cylinder("Pinnacolo spezzato | moncone", (x, -0.84, 15.16), 0.24, 0.72,
                  stone, vertices=8, bevel=0.025)
st.rotation_euler[1] = -0.05
sh = add_cone("Pinnacolo spezzato | scheggia", (x-0.10, -0.84, 15.56), 0.16, 0.0, 0.5,
              stone_dark, vertices=5)
sh.rotation_euler[1] = -0.3
x = 5.9
add_box("Pinnacolo | base", (x, -0.87, 14.70), (0.82, 0.68, 0.44), stone_light, 0.055)
add_cylinder("Fusto del pinnacolo", (x, -0.84, 15.40), 0.23, 1.18, stone, vertices=8,
             bevel=0.025)
pn_ = add_cone("Freccia del pinnacolo", (x, -0.84, 16.20), 0.33, 0.0, 0.95, stone_light,
               vertices=8)
pn_.rotation_euler[1] = 0.045
add_uv_sphere("Nodo dorato del pinnacolo", (x, -0.88, 15.17), (0.3, 0.09, 0.3), bronze,
              segments=16, rings=8)
# Central three-pronged, blackened-iron crest rising through the pediment gap.
add_rod("Asta del tridente", (-0.15, -0.62, 16.90), (-0.15, -0.62, 18.10), 0.075, iron, 12)
for s in (-1, 0, 1):
    start = (-0.15+s*0.04, -0.62, 17.35)
    midp = (-0.15+s*0.34, -0.62, 17.73 if s else 17.90)
    end = (-0.15+s*0.52, -0.62, 18.28)
    add_curve(f"Dente del tridente {s+2}", [start, midp, end], 0.065, iron, resolution=3)

# Inscription plaque and Dante's warning in raised, aged brass — slightly askew,
# resettled by centuries of tremors.
add_box("Targa della sentenza", (0.12, -1.66, 14.05), (8.8, 0.19, 0.78), stone_dark, 0.055)
add_box("Cornice della targa", (0.12, -1.78, 14.05), (8.56, 0.055, 0.62), bronze, 0.045)
add_box("Campo della targa", (0.12, -1.815, 14.05), (8.36, 0.035, 0.48), stone_dark, 0.028)

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
    obj.rotation_euler = (math.pi/2, 0, 0.010)
    data.materials.append(material)
    return obj

add_text("Avvertimento | Lasciate ogni speranza", "LASCIATE OGNI SPERANZA, VOI CH'ENTRATE",
         (0.12, -1.875, 14.06), 0.32, gold, extrude=0.015)
# Small rosettes at the corners of the inscription.
for side in (-1, 1):
    add_ico(f"Rosone della targa {side:+d}", (0.12+side*4.08, -1.88, 14.05),
            (0.11, 0.055, 0.11), gold, subdivisions=2)
    for a in range(8):
        ang = a * math.tau / 8
        add_uv_sphere("Petalo del rosone", (0.12+side*4.08 + math.cos(ang)*0.10, -1.905,
                                              14.05 + math.sin(ang)*0.10),
                      (0.025, 0.016, 0.025), bronze, segments=8, rings=6)


# -----------------------------------------------------------------------------
# Doors: hinged, partly open iron leaves with relief, straps and skull bosses
# -----------------------------------------------------------------------------
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
                         outline, -0.27, 0.23, iron_leaf, bevel=0.03, parent=root)
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
                (leaf*width*0.5, -0.474, zc), (width-0.12, 0.055, 0.07), iron_leaf, 0.018, parent=root)
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
                (leaf*0.13, -0.50, zc), (0.58, 0.095, 0.14), iron_leaf, 0.025, parent=root)
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
            y = -1.05 + (0.08 if strand else 0.0)
            rot = (math.pi/2, 0, 0) if i % 2 == 0 else (math.pi/2, 0, math.pi/2)
            add_torus(f"Catena della soglia {side:+d}.{strand+1}.{i+1:02d}",
                      (x, y, z), 0.12, 0.032, iron, rotation=rot,
                      major_segments=16, minor_segments=6)
    # A small broken chain drapes diagonally over the threshold.
    pts = [(side*2.85,-1.16,7.65),(side*2.55,-1.24,7.32),
           (side*2.30,-1.28,7.02),(side*2.14,-1.32,6.82)]
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
    x = side*5.45
    y = -1.30
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
    wing_y = -1.95
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
    x = side*3.60
    add_rod(f"Mensola | braccio di sostegno {side:+d}", (x,-0.95,5.40), (x,-1.50,5.60),
            0.05, iron, 8)
    add_box(f"Mensola del braciere {side:+d}", (x,-1.50,5.62), (0.66,0.50,0.23), stone_light, 0.055)
    add_cylinder(f"Stelo del braciere {side:+d}", (x,-1.55,6.02), 0.105,0.68,
                 iron, vertices=12, bevel=0.02)
    add_torus(f"Anello inferiore del braciere {side:+d}", (x,-1.55,5.82),
              0.21,0.035,bronze, major_segments=16, minor_segments=6)
    add_ico(f"Coppa cranica del braciere {side:+d}", (x,-1.55,6.38),
            (0.40,0.30,0.22), bronze, subdivisions=1)
    add_skull_relief(f"Maschera del braciere {side:+d}", x,-1.85,6.42,0.54,
                     skull_mat=bone_shadow,glow=False)
    for fi in range(3):
        flame_shape(f"Fiamma del braciere {side:+d}.{fi+1}",
                    x+(fi-1)*0.13,-1.59,6.48,0.23,random.uniform(0.55,1.15),
                    [flame_orange,ember,flame_red][fi],lean=random.uniform(-0.10,0.10))
    # Point lights are warm but restrained; the portal remains the focal point.
    ld = bpy.data.lights.new(f"Luce del braciere {side:+d}", "POINT")
    ld.energy = 190
    ld.color = (1.0,0.16,0.025)
    ld.shadow_soft_size = 0.55
    lo = bpy.data.objects.new(f"Luce del braciere {side:+d}", ld)
    ACTIVE.objects.link(lo)
    lo.location = (x,-1.95,6.9)

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
    for i in range(5):
        x = side*(8.6 + i*1.2)
        h = random.uniform(5.0,11.0)
        add_cone(f"Dente di basalto lontano {side:+d}.{i+1}",
                 (x,2.4, h*0.5-0.15), random.uniform(0.65,1.15), 0.0, h,
                 stone_dark, vertices=5)
# A dim blood-red atmospheric plane behind the far silhouette.
backdrop_mat = emission_material("Orizzonte | cenere rossa", (0.028,0.004,0.012), 0.45)
add_box("Fondale dell'abisso", (0,5.2,8.5), (66,0.18,36), backdrop_mat, 0.0)

# Smoke-like curls rising from the broken lintel and the burning threshold.
smoke_mat = principled_material("Fumo | cenere fredda", (0.11,0.075,0.10,1), 0.0, 0.92,
                                3.0,0.12,0.07,(0.025,0.018,0.04,1),(0.24,0.15,0.16,1))
# Smoke escapes the collapsed crown of the left tower and the burning threshold.
for i in range(3):
    x = -6.55 + i*0.42
    z0 = 13.6 + i*0.25
    pts = [(x,-0.75,z0),(x-0.25,-0.60,z0+0.55),(x+0.10,-0.45,z0+1.05),
           (x-0.35,-0.30,z0+1.55),(x-0.60,-0.15,z0+1.95)]
    add_curve(f"Vapore d'ombra | torre spezzata {i+1}", pts,
              0.03 + i*0.008, smoke_mat, resolution=3)
for side in (-1,1):
    x = side*2.95
    z0 = 5.4
    pts = [(x,-1.85,z0),(x+side*0.22,-1.75,z0+0.5),(x-side*0.10,-1.65,z0+0.95),
           (x+side*0.30,-1.55,z0+1.4),(x+side*0.55,-1.45,z0+1.7)]
    add_curve(f"Vapore d'ombra | soglia {side:+d}", pts, 0.03, smoke_mat, resolution=3)

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
add_area_light("Luna | luce principale", (-9.5,-12.5,17.5), (0,0,7.4),
               2600, (0.60,0.72,1.0), 9.0)
add_area_light("Riflesso cremisi | lato destro", (9.5,-8.0,9.0), (0,0,5.5),
               1700, (1.0,0.23,0.10), 8.0)
add_area_light("Luce di taglio | blu abissale", (3.5,3.5,15.0), (0,0,8.0),
               2800, (0.15,0.28,1.0), 7.0)
add_area_light("Luce alta | pietra e frontone", (-1.0,1.0,20.0), (0,0,10.0),
               1250, (0.72,0.54,0.35), 6.0)

for name, location, energy, color, radius in [
    ("Cuore della soglia", (0,1.45,3.2), 850, (1.0,0.075,0.018), 1.9),
    ("Lava riflessa sui gradini", (0,-2.6,1.1), 300, (1.0,0.12,0.018), 2.4),
    ("Rimbalzo rosso sulle ali", (-5.3,-1.9,3.4), 170, (0.9,0.06,0.018), 1.3),
    ("Rimbalzo rosso sulle ali | dx", (5.3,-1.9,3.4), 170, (0.9,0.06,0.018), 1.3),
    ("Brace della torre spezzata", (-6.7,-1.4,13.4), 120, (1.0,0.10,0.02), 1.1),
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
cam.location = (9.8,-32.0,10.8)
target = Vector((0.0,-0.30,9.4))
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
# Prefiltro accurato: con il micro-dettaglio dei materiali il filtro veloce
# spiana i rilievi fini proprio dove la roccia dovrebbe essere più ruvida.
scene.cycles.denoising_prefilter = "ACCURATE"
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
scene["Dimensioni indicative"] = "circa 15,0 x 18,5 x 6,0 unità Blender"

# Make the project pleasant to inspect immediately after opening in Blender.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.region_3d.view_location = (0.0,-0.1,8.6)
            space.region_3d.view_distance = 28.0
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
# L'anteprima usa lo stesso numero di campioni del render finale: con meno
# campioni il denoiser è costretto a spianare il micro-dettaglio dei materiali.
scene.render.resolution_percentage = 68
scene.cycles.samples = 48
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
