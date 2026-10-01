# La Porta dell'Inferno — Blender · Edizione II

Modello 3D originale ispirato all'**Inferno, Canto III** di Dante: portale gotico in basalto con tre ordini di archi a sesto acuto, torri contrafforte asimmetriche, frontone spezzato, battenti di ferro socchiusi, custodi alati, catene, fuoco e l'iscrizione *«Lasciate ogni speranza, voi ch'entrate»*.

**Questa edizione aggiunge dettaglio alla geometria, non soltanto ai materiali.** Intagli, sculture, scheggiature, pieghe e meccanismi restano visibili anche senza texture.

## Apri il modello

Apri **`porta_dell_inferno.blend`** in Blender **4.5 o successivo**. La scena è già inquadrata; premi **F12** per il render finale.

- **3.313 oggetti**, organizzati in **6 collezioni**; le piccole primitive condividono le mesh per mantenere il progetto leggero.
- **22 materiali** inclusi, senza texture, font o librerie esterne da scaricare.
- Render finale: **Cycles CPU, 2000 × 2320 px, 128 campioni massimi**, adaptive sampling e denoise accurato.
- **4 camere**: inquadratura principale e dettagli di battenti, corona/trafori e custode. Seleziona una camera di dettaglio nell'Outliner e premi **Ctrl + Numpad 0**.
- I battenti sono figli degli empty **Cardine del battente sinistro/destro**: ruotali su **Z** per cambiare l'apertura. Anche i nuovi intagli, le anime in rilievo e le serrature seguono il cardine.
- Il generatore e una breve guida sono inclusi anche nei blocchi di testo del `.blend`.

### Anteprime

- **`porta_dell_inferno_preview.png`** — vista completa, 1080 × 1253 px.
- **`porta_dell_inferno_dettaglio.png`** — dettaglio dei battenti, 1080 × 1080 px.

Sono render della geometria contenuta nel `.blend`, non illustrazioni o concept separati.

## Nuovo dettaglio modellato

### Architettura e intagli gotici

- **Muratura continua nei pennacchi**: i conci seguono il profilo del grande arco e raccordano la struttura al coronamento; la cimasa non rimane sospesa sopra un vuoto.
- **Torri a conci singoli**: corsi sfalsati, cantonali alternati, giunti, superfici di frattura e spigoli tagliati. Si conservano la torre sinistra crollata e quella destra pendente.
- **Archivolti scolpiti**: foglie d'acanto lobate e ricurve con nervature, fascia di denti di cane in rilievo e borchie quadrilobate. Il concio mancante rimane una lacuna, anche negli ornamenti.
- **Capitelli a fogliame** e collarini sulle colonnette; doppie lancette sulle torri, piccoli trafori e gargoyle sopra le mensole.
- **Rosone a sei petali** con cornici di pietra, filetti d'ottone, raccordi quadrilobati, vetro cremisi e teschio centrale scolpito. Acanto lungo le rampe del frontone, senza chiuderne la frattura.
- **Anime nelle nicchie e nei medaglioni**: volti emaciati, bocche del lamento, clavicole, costole, mani e arti piegati in bassorilievo.

### Sculture e battenti

- **Crani con orbite e cavità nasale realmente scavate**, zigomi e arcate sopracciliari, mandibola a ferro di cavallo, due file di denti irregolari e sutura frontale. I tagli sono risolti nella mesh: nessun cutter nascosto o booleano da ricalcolare.
- **Corna rastremate**, con creste alla radice, al posto di tubi a diametro costante.
- **Manti dei custodi con pieghe geometriche** su 36 anelli e 64 campioni angolari, orli irregolari, dita articolate e nocche.
- **Ali ondulate con spessore** e nervature rastremate, invece di semplici lastre piatte.
- **Campi ogivali dei battenti decorati** con anime incatenate, cornici fiammeggianti, viticci forgiati e foglie; riccioli nei pannelli inferiori.
- **Meccanica distinta**: chiodi ottagonali con rondelle, nocche e perni dei cardini, teste dei perni, piastre con foro della chiave, chiavistelli e staffe.

### Usura e terreno

I conci hanno veri tagli negli angoli; gli archivolti e i pennacchi presentano scheggiature locali. I gradini sono assemblati da lastre separate, e il percorso ha pietre tagliate in pianta, schegge di basalto e ossa tra le macerie. L'usura usa semi indipendenti: aggiungere un ornamento non cambia casualmente tutta la struttura.

## Materiali procedurali stratificati

Le superfici principali condividono il generatore **`materiale_eroso`**, con ricette modificabili in `porta_inferno.py`:

- Crepe e craquelure Voronoi su scale diverse, interrotte da una maschera lenta.
- Vaiolature raggruppate, erosione, schegge e spigoli consumati.
- Cenere sulle facce esposte e nelle cavità, colature di fuliggine, bruciature e crosta vetrificata in prossimità del fuoco.
- Ferro annerito con martellatura, scaglie di forgia, ruggine, graffi e bordi lucidi; ossidi e cenere riducono la metallicità.
- Colore, roughness e metallic pilotati dalle stesse maschere; rilievo macro e micro-dettaglio separati.
- Coordinate ruotate e traslate per oggetto, con domain warping e variazione di tono per evitare campioni ripetuti.

Le crepe di shader sono ora più fini, per lasciare leggibili gli intagli e le fratture geometriche. Le maschere di distanza **in metri** vengono normalizzate con `Map Range` prima di `ColorRamp`; la curvatura `Pointiness` distingue correttamente cavità e spigoli attorno a **0,5**. I grafi conservano i riquadri etichettati nello Shader Editor.

Luce lunare fredda, fuoco della soglia e un tenue riempimento neutro rendono leggibili i bassorilievi senza appiattire le ombre. L'ottone dell'iscrizione ha una grana più fine per preservare la leggibilità del testo.

## Rigenera la scena

Con Blender installato, dalla cartella del progetto:

```bash
# Modello e anteprima principale
blender --background --python porta_inferno.py

# Include anche il dettaglio dei battenti
blender --background --python porta_inferno.py -- --detail-preview

# Solo il .blend: nessun render necessario
blender --background --python porta_inferno.py -- --no-render

# Bozza veloce, senza sovrascrivere i file principali
blender --background --python porta_inferno.py -- \
  --output-dir .cache/bozza --preview-width 480 --preview-samples 12
```

È possibile usare anche `python3 porta_inferno.py` in un ambiente con il modulo `bpy` compatibile installato.

Il `.blend` viene salvato **prima** del render, con compressione nativa di Blender. La preview usa 64 campioni massimi e adaptive sampling; il tempo su CPU dipende dalla macchina e può essere di decine di minuti. Camera, risoluzione e qualità finale sono ripristinate al termine del render, anche in caso di errore. Il percorso di render nel progetto è relativo al `.blend`, quindi il file si può spostare.

## Verifica

```bash
blender --background --python tests/validate_scene.py -- \
  --blend porta_dell_inferno.blend
```

I controlli verificano caricamento, materiali senza texture esterne, collezioni, iscrizione, impostazioni finali, camere, geometria finita, conci chiusi e orientati, profondità delle orbite con ray cast e l'effettivo movimento dei nuovi dettagli con i cardini. Il test non salva né altera il modello su disco.

Per confrontare anche geometria, curve e trasformazioni dopo una rigenerazione indipendente:

```bash
blender --background --python porta_inferno.py -- --no-render --output-dir .cache/verifica
blender --background --python tests/validate_scene.py -- \
  --blend porta_dell_inferno.blend --compare-generated .cache/verifica/porta_dell_inferno.blend
```

Scena generata e verificata con **Blender 4.5.14 LTS**.
