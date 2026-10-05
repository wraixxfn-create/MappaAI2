# Il gioco — esplorare la mappa 3D

Un'esplorazione in prima persona della mappa **`porta_dell_inferno.blend`**:
la valle di cenere, la scalinata cerimoniale, il portale di basalto alto trenta
metri e la soglia oltre la quale qualcosa ti sta già guardando.

Tutto ciò che si vede — geometria, luci, proporzioni, i punti in cui stanno le
sette figure umane — viene **dal file `.blend` originale**, non da un livello
ricostruito a mano.

## Avvio

```bash
cd game
npm install          # solo la prima volta: serve a gltfpack e ai test
npm start            # apre http://localhost:8080
node server.js
```

Il server è un semplice server di file statici: nessun bundler, nessuna CDN.
Le librerie (`three`, `three-mesh-bvh`) sono già in `vendor/` e la pagina le
risolve con un'import map, quindi il gioco funziona anche offline.

## Come si gioca

Sei un pellegrino alto un metro e settantotto davanti a un monumento di
trenta. Sette anime sono ferme nella cenere, tra la processione lontana e i
gradini: raggiungile e ascolta il loro verso per raccogliere i sigilli. Solo
con tutte e sette i battenti di ferro cederanno.

| Tasto | Azione |
| --- | --- |
| `W A S D` | camminare |
| mouse / trascina a destra | guardarsi intorno |
| `Shift` | correre |
| `Spazio` | saltare (serve per la scalinata) |
| `E` | parlare con un'anima / spingere i battenti |
| `F` | accendere o spegnere la lanterna |
| `M` | mappa della valle |
| `Esc` | pausa e impostazioni |

La **speranza** si consuma nel buio e si ricarica vicino al fuoco: se si
azzera, ti rialzi sui gradini, ma le anime già ascoltate restano tue. Camminare
dentro lava e fiamme brucia.

Su telefono compaiono un joystick a sinistra e i pulsanti *salta* e *E*.

## Da .blend a gioco

Il `.blend` non è modificato: `tools/export_map.py` lo apre **in sola lettura**
e ne ricava gli asset in `public/`.

```bash
game/tools/export_map.sh     # richiede Blender 4.5+ oppure il modulo bpy
```

Produce:

| File | Contenuto |
| --- | --- |
| `map.glb` | geometria visiva, unita per materiale (48 draw call, ~620 k triangoli) |
| `collision.glb` | la stessa geometria semplificata a ~70 k triangoli, per la fisica |
| `scene.json` | 32 luci, 7 punti di interesse, spawn, soglia, cardini, iscrizione |
| `heightmap.png` | altezza del terreno (16 bit) e calore delle braci, per la minimappa |

Cosa fa l'esportatore, in sintesi:

* **converte** curve e testo in mesh e applica i modificatori (bevel, weighted
  normal, solidify): gli intagli restano geometria, non spariscono;
* **unisce** i 3 600 oggetti in 48 mesh, una per materiale (o per cardine), così
  la scena è leggera senza perdere dettaglio;
* **cuoce l'illuminazione nei colori per vertice**: i materiali di Blender sono
  procedurali e le mesh non hanno UV, quindi occlusione ambientale, cenere sulle
  facce esposte e riflesso del fuoco diventano un attributo `COLOR_0`;
* **chiude i battenti**: nel `.blend` sono socchiusi di 25° (belli in render),
  ma nel gioco il varco deve restare sbarrato finché non hai tutte le anime;
* **esporta le luci** della scena in candele; il gioco ne tiene un gruppo
  mobile di 9, scegliendo le più vicine, e fa sfarfallare quelle calde.

Coordinate: Blender è Z-up, il gioco è Y-up. L'esportatore converte tutto in
`(x, z, -y)`, così il gioco non deve più toccare nulla.

## Struttura

```
game/
├── index.html          pagina, HUD, schermate, import map
├── style.css
├── server.js           server statico (range request, MIME, nessuna dipendenza)
├── src/
│   ├── main.js         ciclo di gioco: asset, stati, interazioni
│   ├── world.js        caricamento GLB, luci della scena, materiali
│   ├── physics.js      capsula contro BVH, gradini, sbarra del varco
│   ├── player.js       input, sguardo, andatura, lanterna
│   ├── objectives.js   regole: anime, speranza, battenti
│   ├── particles.js    braci, cenere e fumo
│   ├── audio.js        vento, fuoco e campane (WebAudio, nessun file)
│   ├── hud.js          HUD, minimappa, bussola, versi
│   └── heightfield.js  heightmap e disegno della mappa
├── tools/             esportatore (.blend -> public/) e copia dei moduli
├── tests/             test headless su asset, fisica e percorribilità
└── public/            asset generati (non modificati a mano)
```

## Verifica

```bash
npm test
```

52 test headless (`node --test`) che girano sugli **asset veri**, senza WebGL:

* il modello si carica, le coordinate sono nello spazio di gioco, i colori per
  vertice ci sono tutti;
* la geometria non è schiacciata dalla quantizzazione e il terreno è un rilievo
  (due regressioni già sorprese sul fatto);
* il giocatore cade, atterra, cammina e sale la scalinata;
* **una partita simulata** percorre la valle con la fisica del gioco e verifica
  che tutte e sette le anime siano raggiungibili e che la speranza non si
  azzeri prima della soglia;
* i battenti chiusi sbarrano il passaggio e si aprono solo con tutte le anime;
* la minimappa campiona correttamente altezze e calore;
* ogni file richiesto dalla pagina esiste e nessuno dei moduli è identico a un
  altro (un refuso già capitato).

Per un'anteprima CPU della mappa, senza GPU:

```bash
node --import ./tests/register.js tools/preview.mjs --camera spawn --out /tmp/preview.png
node --import ./tests/register.js tools/preview.mjs --camera gate --out /tmp/gate.png
```

## Note tecniche

* Le dipendenze ESM in `vendor/` sono copiate da `node_modules` con
  `tools/vendor.sh`: il browser usa esattamente gli stessi file dei test.
* `EXT_meshopt_compression` è gestito da `MeshoptDecoder`; senza
  compressione il modello peserebbe ~47 MB invece di 5,3 MB.
* Attenzione a `gltfpack`: `-vp`, `-vn`, `-vc` prendono un **numero di bit**,
  non una tolleranza. Passare `1e-4` riduce la geometria a un bit, cioè a un
  mondo piatto. L'esportatore ora confronta la bounding box prima e dopo la
  compressione e, se la geometria si è accartocciata, tiene il file non
  compresso.
