# La Porta dell'Inferno — Blender

Modello 3D originale ispirato all'**Inferno, Canto III** di Dante: portale gotico in basalto con **tre ordini di archi spezzati concentrici**, torri contrafforte asimmetriche (una spezzata, una pendente), frontone rotto con rosone, pilastri clusterizzati massicci, incisioni profonde e arcature cieche; battenti di ferro socchiusi, mascheroni e teschi scolpiti, custodi alati, catene, fiamme, lava e l'iscrizione *«Lasciate ogni speranza, voi ch'entrate»*.

## Apri il modello

Apri **`porta_dell_inferno.blend`** in Blender (consigliato Blender 4.5 o successivo). La scena è già inquadrata e organizzata in collezioni; premi **F12** per il render. L'anteprima pronta è **`porta_dell_inferno_preview.png`**.

- 1098 oggetti, suddivisi in 5 collezioni per architettura, porte, sculture, inferi e scena.
- 20 materiali procedurali stratificati inclusi nel file, senza texture esterne.
- Render configurato con Cycles CPU, 1500 × 1740 px, 48 campioni.
- I due battenti sono raggruppati sotto gli empty **Cardine del battente sinistro/destro**: ruotali sull'asse Z per cambiare l'apertura.

## Materiali: pietra vulcanica, roccia carbonizzata, metallo annerito

Le superfici della porta non usano immagini: ogni materiale è generato dalla
stessa ricetta a strati (`materiale_eroso`, in `porta_inferno.py`) e compone
dettagli campionati a scale molto diverse — da venature di due metri al grit di
pochi centimetri — con maschere di degrado indipendenti:

- **Crepe profonde e craquelure**: reti di Voronoi *distance-to-edge* su due
  scale, interrotte da una maschera lenta perché il reticolo non sia mai
  perfettamente regolare; il fondo delle crepe è opaco e, nelle rocce
  carbonizzate, appena incandescente.
- **Erosione e scheggiature**: vaiolature vulcaniche raggruppate in chiazze,
  celle di distacco che si concentrano sugli spigoli (curvatura *pointiness*) e
  bordi consumati che scoprono la pietra viva, più chiara e meno ruvida.
- **Cenere e fuliggine**: depositi sulle facce rivolte verso l'alto e nelle
  cavità, più fitti verso il basso, con colature verticali di fuliggine che si
  addensano attorno alla soglia incandescente.
- **Segni di bruciatura**: nuclei carbonizzati con alone di scottatura e chiazze
  di crosta vetrificata, distribuiti in base alla distanza dal fuoco.
- **Metallo annerito**: conche di martellatura, scaglie di forgia, ossidi e
  ruggine nelle cavità, graffi direzionali e fuliggine; la ruggine e la cenere
  tolgono metallicità, gli spigoli consumati tornano metallo lucido.

Roughness e metallic sono pilotati dalle stesse maschere del colore (crepe
opache, cenere opacissima, crosta vetrificata lucida, ossidi non metallici), e
il rilievo lavora su due livelli: erosione macro e micro-dettaglio. Ogni oggetto
ruota e trasla lo spazio della texture e riceve una piccola variazione di tono e
di roughness (nodo *Object Info*), così centinaia di conci non condividono mai lo
stesso campione e la ripetizione procedurale non si legge.

Nel `.blend` ogni materiale è impaginato in riquadri etichettati — *Coordinate*,
*Domain warping*, *Texture stratificate*, *Maschere di degrado*, *Colore
stratificato*, *Roughness e metallic*, *Rilievo* — e ogni ricetta è un
dizionario di pochi valori: modificare un numero e rigenerare la scena
aggiorna l'intero grafo.

## Struttura monumentale

- **Ordini nidificati**: tre archivolti a sesto acuto stepping in avanti (concio mancante e fenditura maestra come cicatrici); parete d'ombra profonda con arcature cieche incise e denti pendenti.
- **Torri asimmetriche**: sinistra più alta e crollata (con arco rampante integro), destra più bassa, pendente e con guglia inclinata (rampa spezzata dell'arco destro).
- **Corona gotica**: fregio di glifi incisi, frontone spezzato con rampe di altezze diverse, rosone con razzi dorati, pinnacoli (uno moncone), tridente in ferro battuto.
- **Asimmetrie e usura**: targa ruotata e rinsedata, corsi di conci assestati, macerie, tacche rune-like e gole profonde sui ritiri delle torri.

## Rigenera la scena

Con Blender installato, dalla cartella del progetto:

```bash
blender --background --python porta_inferno.py
```

Lo script ricrea il `.blend` e la preview PNG nella stessa cartella. Con Cycles
CPU la preview (1020 × 1183 px, 48 campioni) richiede da mezz'ora a un'ora su
una macchina a 2 core. Il `.blend` è salvato prima del render — e comunque
impostato a 1500 × 1740 px e 48 campioni — quindi si può aprire e rendere subito
in qualità piena.
