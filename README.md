# La Porta dell'Inferno — Blender

Modello 3D originale ispirato all'**Inferno, Canto III** di Dante: portale gotico in basalto, battenti di ferro socchiusi, mascheroni e teschi scolpiti, custodi alati, catene, fiamme, lava e l'iscrizione *«Lasciate ogni speranza, voi ch'entrate»*.

## Apri il modello

Apri **`porta_dell_inferno.blend`** in Blender (consigliato Blender 4.5 o successivo). La scena è già inquadrata e organizzata in collezioni; premi **F12** per il render. L'anteprima pronta è **`porta_dell_inferno_preview.png`**.

- 820 oggetti, suddivisi in 5 collezioni per architettura, porte, sculture, inferi e scena.
- Materiali procedurali inclusi nel file, senza texture esterne.
- Render configurato con Cycles CPU, 1500 × 1740 px, 48 campioni.
- I due battenti sono raggruppati sotto gli empty **Cardine del battente sinistro/destro**: ruotali sull'asse Z per cambiare l'apertura.

## Rigenera la scena

Con Blender installato, dalla cartella del progetto:

```bash
blender --background --python porta_inferno.py
```

Lo script ricrea il `.blend` e la preview PNG nella stessa cartella.
