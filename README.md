# La Porta dell'Inferno — Blender · Edizione II

Modello 3D originale ispirato all'**Inferno, Canto III** di Dante: portale gotico in basalto con tre ordini di archi a sesto acuto, torri contrafforte asimmetriche, frontone spezzato, battenti di ferro socchiusi, custodi alati, catene, fuoco e l'iscrizione *«Lasciate ogni speranza, voi ch'entrate»*. La porta si trova ora al centro di un **ambiente infernale cinematografico**: valle vulcanica nera, rupi fratturate, cenere e fumo volumetrico, braci sospese e lava in lontananza.

**Questa edizione aggiunge dettaglio alla geometria, non soltanto ai materiali.** Intagli, sculture, scheggiature, pieghe e meccanismi restano visibili anche senza texture.

## Apri il modello

Apri **`porta_dell_inferno.blend`** in Blender **4.5 o successivo**. La scena è già inquadrata; premi **F12** per il render finale.

- **3.581 oggetti**, organizzati in **6 collezioni**; le piccole primitive condividono le mesh per mantenere il progetto leggero.
- **32 materiali** inclusi (tre sono volumi procedurali), senza texture, font o librerie esterne da scaricare.
- Render finale: **Cycles CPU, 2000 × 2320 px, 128 campioni massimi**, adaptive sampling e denoise accurato.
- **4 camere**: inquadratura principale (più arretrata, per mostrare l'ambiente) e dettagli di battenti, corona/trafori e custode. Seleziona una camera di dettaglio nell'Outliner e premi **Ctrl + Numpad 0**.
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

L'illuminazione è drammatica e cinematografica: la fonte principale è il calore rosso/arancio che esce dalla porta e dalle crepe incandescenti, mentre l'ambiente porta solo una debole luce fredda di contrasto (vedi sotto). L'ottone dell'iscrizione ha una grana più fine per preservare la leggibilità del testo.

## Calore infernale integrato nella struttura

Il monumento non è più solo *illuminato* dal fuoco: il calore nasce **dentro** la pietra.

- **Vene incandescenti tra i conci**: fessure di magma con gola bruciata corrono nei giunti dei piloni, delle pareti di spalla, nei giunti radiali dell'archivolto interno, nelle torri e nello zoccolo. Il materiale `Magma | vena incandescente tra i conci` varia colore lungo ogni vena (crosta scura → rosso → arancio vivo) con rumore in coordinate mondo.
- **Lava nelle profondità della porta**: oltre la soglia, un lago di lava con croste nere e vene vive (`Lava | crosta nera…`) riempie il tunnel fra i battenti socchiusi; colate fuse scendono dalle pareti interne e una `Parete fusa` emissiva chiude la profondità, visibile nello spiraglio fra le ante. Un rivolo di lava oltrepassa la soglia e scende sui gradini cerimoniali.
- **Piccole fuoriuscite di fuoco**: lingue di fiamma e nuclei d'oro nascono dove le vene raggiungono la superficie, con faville sospese e veli di fumo caldo.
- **Illuminazione fisica**: ogni vena, specchio di lava e fuoriuscita ha una luce puntiforme dedicata (12 luci arancio/rosso) e l'emissione del magma partecipa al GI; con `diffuse_bounces = 4` il bagliore rimbalza realisticamente sul basalto, producendo riflessi caldi sui conci, sul ferro dei battenti e sui gradini.

## Illuminazione cinematografica

La scena è trattata come un set cinematografico notturno, con una gerarchia precisa tra le fonti:

- **Fonte principale dall'interno della porta**: il *Cuore della soglia* e la *Vampa dell'abisso* (5200 W) sono ora la chiave della scena; la luce rossa e arancione esce dai battenti socchiusi, bagna i gradini, il ferro e la pietra del portale.
- **Crepe incandescenti come sorgenti**: ogni vena di magma (piloni, spalle, archivolto, torri) ha una luce dedicata con energia triplicata; l'emissione del magma sale a 10 e la parete fusa nelle profondità a 6,5, così ogni giunto ardente disegna il proprio alone sulla pietra.
- **Debole luce fredda d'ambiente**: la luna (1100 W, blu) e il taglio blu abissale (650 W) restano solo per il contrasto cromatico caldo/freddo, senza competere con la chiave. I riempimenti neutri sono stati rimossi: le ombre sono profonde e nessuna luce lava i neri.
- **Volumetric fog**: la foschia di cenere è più densa (0,0060) e più anisotropa (0,52); le luci fredde hanno *Volume Scatter* spento, quindi il fumo si accende solo del calore rosso/arancio della soglia e delle crepe, con il bagliore che si diffonde come alone volumetrico.
- **Strong rim lighting**: due area light fredde fuori campo (4500 e 2200 W) tracciano i profili di corona, frontone e torre spezzata, mentre il controluce caldo della lava (12000 W) borda le rupi sullo sfondo: la sagoma scura si stacca netta dal bagliore.

## Ambiente infernale

L'ambiente è costruito come **cornice della porta**: il monumento resta l'area più luminosa e più contrastata dell'immagine, e tutto il resto guida lo sguardo verso la soglia invece di competere con essa.

- **Terreno vulcanico nero**: heightfield reale (nessun modificatore) piatto attorno al basamento, con dune basse di cenere in primo piano. Ai lati sale in una valle che si chiude verso i bordi dell'inquadratura, come una vignetta fisica. Il materiale `Terreno vulcanico | cenere nera e ossidiana` mescola basalto quasi nero, cenere sulle facce esposte, ossidiana lucida e fratture irregolari.
- **Rocce fratturate**: massi e schegge generati come inviluppi convessi irregolari, tagliati da piani netti (vere facce di frattura). Le rupi sono blocchi impilati e inclinati: **basse vicino alla porta, più alte ai bordi**, così il loro profilo scende verso la soglia. Sullo sfondo ci sono guglie lontane, in sagoma.
- **Lava solo in lontananza**: fiumi incandescenti e due laghi, con crosta nera e crepe vive (`Lava lontana | …`), incassati nella piana oltre il monumento. I fiumi convergono verso la base della porta. Sui monti dell'orizzonte non ci sono colate, per non creare un secondo punto luminoso.
- **Fumo volumetrico**: una foschia di cenere (`Principled Volume`) avvolge la valle ed è più densa al suolo. Colonne di fumo alle spalle del monumento sono illuminate dal basso dalle luci della lava; ai lati del piazzale scorrono banchi radenti, mai davanti alla soglia. Due pennacchi salgono dalla torre spezzata e dai bracieri.
- **Braci sospese e cenere**: le braci sono bipiramidi allungate lungo la direzione di volo e simulano una scia. Hanno intensità variabile, data da un attributo `calore`, e si addensano attorno alla soglia, più rade altrove. I fiocchi di cenere sono opachi e si diradano nel cono visivo davanti alla porta. Ogni sciame è una sola mesh, quindi resta leggera.
- **Luce**: il cielo è un velo di fumo arrossato verso l'orizzonte. Luci calde basse sotto le colonne di fumo creano un controluce che stacca la silhouette del monumento. Luna e luci fredde continuano a scolpire la pietra ma non accendono la foschia (`visible_volume_scatter = False`), così il volume si colora solo del calore.

Tutto l'ambiente usa semi stabili (`stable_rng`): non altera l'RNG globale né la geometria del monumento. I volumi rendono il render più lento rispetto all'edizione precedente.

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

Scena generata e verificata con **Blender 4.5 LTS** (edizione corrente: `bpy` 4.5.14 come modulo Python; il progetto resta compatibile con Blender 4.5+).
