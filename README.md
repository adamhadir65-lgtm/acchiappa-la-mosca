# Acchiappa la Mosca

Questa cartella contiene l'API Python e gli script Roblox pronti da copiare.

## Modello e limiti di sincronizzazione

`connectome_weights.json` è stato ricavato dall'intero edgelist neuronale BANC v888 v3: 12.399.147 connessioni, con conteggi sinaptici, sono state aggregate fra nove popolazioni (afferenti, interneuroni ed efferenti, separate per lato). `prepare_connectome.py` ripete questa riduzione partendo dai dati pubblici. A ogni richiesta `app.py` calcola una piccola rete di attività di popolazione usando quella matrice e un input visivo periodico dimostrativo; i segnali efferenti influenzano posizione, quota e orientamento.

Questo è un **modello ridotto basato sulla topologia del connectome**, non la simulazione completa di 188 mila neuroni: non riproduce spike, fisiologia sinaptica, occhi, muscoli o un comportamento biologicamente validato. L'input è una funzione periodica fissa, non la scena di Roblox né i giocatori. L'articolo BANC descrive circa 188 mila neuroni e 199 milioni di sinapsi nel cervello e cordone nervoso; alcune cellule visive sono mancanti. Il modello usa le connessioni aggregate del rilascio BANC v888 v3 e non ha la precisione necessaria per affermare che la mosca si muova come un animale reale.

A parità di ora UTC e ancora di reset il modello restituisce le stesse coordinate. `POST /reset` sposta l'ancora della traiettoria. Il token resta in `CATCH_TOKEN` su Render e in `FlyCatchToken` su Roblox; non salvarlo nei file del progetto.

Il reset è conservato in memoria e si perde al riavvio/sleep dell'istanza Render. Il piano Free non garantisce disponibilità 24/7: Render sospende il servizio dopo 15 minuti senza richieste in ingresso; la riattivazione può richiedere circa un minuto. La prima posizione rimane visibile mentre lo script Roblox ritenta. I server ottengono coordinate riferite allo stesso orologio, ma il polling HTTP e la replica fisica Roblox non sono sincronizzati frame per frame. Ogni server interroga ogni secondo; non è un sistema adatto a centinaia di server senza ridurre il polling o passare a un servizio sempre attivo.

## Crea e carica la repository GitHub

1. Su GitHub seleziona **New repository**, chiamala `acchiappa-la-mosca`, scegli pubblico o privato e crea la repository. Per il caricamento via Render, autorizza Render a leggere la repository privata se hai scelto tale opzione.
2. Carica nella radice `app.py`, `requirements.txt`, `connectome_weights.json` e `README.md` tramite **Add file > Upload files**, quindi **Commit changes**. `prepare_connectome.py` e `requirements-connectome.txt` servono solo se vuoi rigenerare la matrice dai dati sorgente. Gli script `.lua` vanno importati in Roblox Studio e non servono al deploy Python.
3. In alternativa, apri una shell nella cartella di questi file e usa i comandi qui sotto, sostituendo utente e repository:

```text
git init
git add app.py requirements.txt connectome_weights.json README.md
git commit -m "Crea API della mosca"
git branch -M main
git remote add origin https://github.com/IL-TUO-UTENTE/acchiappa-la-mosca.git
git push -u origin main
```

## Deploy su Render Free

1. Accedi a [Render](https://render.com/) e collega l'account GitHub.
2. Dashboard > **New + > Web Service**; seleziona la repository e il branch `main`.
3. Imposta runtime **Python 3**, **Build Command** `pip install -r requirements.txt`, **Start Command** `gunicorn app:app`, piano **Free**.
4. In **Environment Variables** aggiungi `CATCH_TOKEN` con una stringa casuale lunga. Conserva il valore: lo userai nel secret Roblox. Non scriverlo nel codice o in GitHub.
5. Seleziona **Create Web Service** e attendi lo stato Live.
6. Copia l'URL HTTPS `https://<nome-servizio>.onrender.com`. Controlla `https://<nome-servizio>.onrender.com/health` nel browser.

Render assegna l'URL pubblico `onrender.com` e documenta questi comandi di build/avvio nella propria guida Flask. La modalità Free può andare in sleep, riavviarsi e perdere dati locali: non promette un servizio sempre sveglio o stato persistente.

## Configura Roblox Studio

1. In `Workspace` crea un `Model` chiamato `Fly`; metti al suo interno le parti grafiche e una `BasePart` chiamata `Hitbox`. Imposta la hitbox `CanCollide = false`, `CanTouch = true`; durante il gioco puoi impostare `Transparency = 1`.
2. Scegli il pivot del modello e imposta un `PrimaryPart`. Salda le parti fra loro con `WeldConstraint`; se il controller deve comandare tutto il movimento senza fisica, ancora (`Anchored = true`) le parti.
3. Crea un `Script` in `ServerScriptService` e incolla `FlyController.server.lua`. Dopo il deploy, seleziona lo Script e aggiungi un attributo stringa `ApiBaseUrl` con l'URL Render effettivo senza slash finale. Finché l'attributo è vuoto, il prototipo usa una traiettoria locale temporanea.
4. Crea un `LocalScript` in `StarterPlayer > StarterPlayerScripts` e incolla `FlyNotice.client.lua` per mostrare l'avviso di cattura a tutti i giocatori della partita.
5. In Roblox Studio apri **File > Experience Settings (o Game Settings) > Security** e attiva **Allow HTTP Requests**.
6. Nel Creator Dashboard dell'esperienza crea un secret chiamato `FlyCatchToken` con lo stesso valore usato come Render `CATCH_TOKEN`. Il token è usato solo dallo Script server per autorizzare il POST `/reset`.
7. Avvia un test con più giocatori. La mosca deve muoversi; toccando la hitbox il giocatore riceve un punto e tutti vedono la notifica.

Il punteggio incluso vive solo nella partita corrente. Per salvarlo tra sessioni serve un DataStore Roblox e una regola per impedire che copie della mosca in server diversi assegnino punti duplicati.

## Dati e licenze

Il modello aggregato deriva da **BANC v888**, depositato su Harvard Dataverse con licenza **CC BY 4.0**. Mantieni l'attribuzione riportata in `THIRD_PARTY_NOTICES.md` se ridistribuisci il file dei pesi o il gioco. Il codice Python di questa cartella è separato dai dati e non cambia la licenza del dataset.

Per rigenerare `connectome_weights.json` dai file sorgente:

```text
pip install -r requirements-connectome.txt
python prepare_connectome.py --data-dir data/banc --output connectome_weights.json
```

Lo script scarica circa 417 MB di dati pubblici al primo avvio e processa l'elenco in blocchi. Non carica il grafo completo sul server Render.

## Endpoint

- `GET /health`: stato del servizio, versione del dataset e conteggio degli archi usati.
- `GET /fly-position`: coordinate `x`, `y`, `z`, `rotation` in gradi, velocità, attività delle nove popolazioni, livello di simulazione e timestamp UTC.
- `POST /reset`: riavvia la traiettoria; richiede header `X-Catch-Token` uguale al segreto `CATCH_TOKEN`.

Quando Render si sta riattivando le richieste possono fallire o essere lente. Lo script mantiene l'ultima posizione e riprova dopo un secondo. Non affidarti a ping automatici per aggirare lo sleep del piano gratuito.
