# La Porta dell'Inferno — Blender

Modello 3D originale ispirato all'**Inferno, Canto III** di Dante: portale gotico in basalto con **tre ordini di archi spezzati concentrici**, torri contrafforte asimmetriche (una spezzata, una pendente), frontone rotto con rosone, pilastri clusterizzati massicci, incisioni profonde e arcature cieche; battenti di ferro socchiusi, mascheroni e teschi scolpiti, custodi alati, catene, fiamme, lava e l'iscrizione *«Lasciate ogni speranza, voi ch'entrate»*.

## Apri il modello

Apri **`porta_dell_inferno.blend`** in Blender (consigliato Blender 4.5 o successivo). La scena è già inquadrata e organizzata in collezioni; premi **F12** per il render. L'anteprima pronta è **`porta_dell_inferno_preview.png`**.

- 1098 oggetti, suddivisi in 5 collezioni per architettura, porte, sculture, inferi e scena.
- Materiali procedurali inclusi nel file, senza texture esterne.
- Render configurato con Cycles CPU, 1500 × 1740 px, 48 campioni.
- I due battenti sono raggruppati sotto gli empty **Cardine del battente sinistro/destro**: ruotali sull'asse Z per cambiare l'apertura.

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

Lo script ricrea il `.blend` e la preview PNG nella stessa cartella.
