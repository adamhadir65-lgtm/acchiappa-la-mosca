# Acchiappa la Mosca

Backend Python e script Roblox del minigioco. Il controller di Roblox invia allo stesso server le stimolazioni visive e lo stato neurale di ogni partita; l'API aggiorna il circuito e restituisce gli spike dei neuroni di uscita.

## Circuito e limiti scientifici

`escape_circuit.json` è un sottoinsieme reale del connectome MaleCNS v1.0 del maschio di *Drosophila melanogaster*: 327 neuroni e 20.684 connessioni dirette, con cellule LC4 e LPLC2 visive, DNp01/GF e cellule TTMn, PSI e DLMn. Il server simula la dinamica con neuroni leaky-integrate-and-fire (LIF) a passi da 1 ms. Ogni istanza Roblox conserva il proprio stato neurale nella richiesta/risposta, così più worker Gunicorn non mescolano gli stati di gioco.

Il client server Roblox traduce lato del giocatore, dimensione apparente e velocità di espansione in correnti visive LC4/LPLC2. Il server restituisce l'attività bilaterale dei neuroni GF; Roblox la traduce in sterzata e velocità. Questa codifica sensoriale, i parametri LIF e la decodifica dei motoneuroni sono approssimazioni ingegneristiche. Non è il connectome completo, una replica biofisica, una mosca cosciente o un comportamento biologico convalidato.

`GET /fly-position` è conservato per compatibilità e per il volo di fondo dimostrativo; il controller aggiornato usa `POST /brain-step` per la risposta di fuga. Il volo di fondo resta una traiettoria dimostrativa basata sul vecchio modello aggregato a nove gruppi.

## Deploy del backend

1. Nella repository GitHub metti nella radice `app.py`, `requirements.txt`, `escape_circuit.json`, `connectome_weights.json` e `THIRD_PARTY_NOTICES.md`.
2. In Render crea un **Web Service** collegato alla repository, con:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
   - Piano Free oppure un piano sempre attivo.
3. Dopo che Render mostra **Live**, copia l'URL HTTPS e controlla `/health`. Su Free il servizio può sospendersi dopo inattività; la prima richiesta può attendere il riavvio.
4. In Roblox Studio abilita **Allow HTTP Requests**. In `ServerScriptService.FlyGameController` imposta l'attributo stringa `ApiBaseUrl` con l'URL del servizio senza slash finale.

## Endpoint

- `GET /health`: stato backend e dimensione del circuito LIF.
- `POST /brain-step`: accetta `dt` (0,02–0,25 s), stato `voltage` e `activity` di 327 numeri, correnti visive `L`/`R` per `LC4` e `LPLC2` (0–4). Restituisce il nuovo stato e le frequenze `GF_L_hz`, `GF_R_hz`, `GF_hz`, `DLMn_L_hz` e `DLMn_R_hz`.
- `GET /fly-position`: vecchia traiettoria dimostrativa.
- `POST /reset`: reset della vecchia traiettoria; richiede `CATCH_TOKEN` e header `X-Catch-Token`.

Esempio del corpo per `/brain-step`:

```json
{
  "dt": 0.1,
  "state": {"voltage": [0], "activity": [0]},
  "visual": {"L": {"LC4": 2.2, "LPLC2": 1.1}, "R": {"LC4": 0, "LPLC2": 0}}
}
```

Nel gioco gli array hanno esattamente 327 valori; quelli abbreviati qui sopra sono solo schematici.

## Script Roblox

- `FlyGameController.server.lua`: round, punteggio, cattura, codifica sensoriale e controllo neurale.
- `ArenaBuilder.server.lua`: crea l'arena.
- `FlyHUD.client.lua`: timer, punteggio e input di cattura.
- `FlyNotice.client.lua`: notifiche.

La posizione della mosca è server-authoritative dentro ogni partita Roblox, perciò tutti i giocatori nella stessa partita vedono lo stesso movimento. Server Roblox diversi hanno gruppi di giocatori e stimoli differenti, quindi le loro traiettorie di fuga non possono essere identiche mentre la mosca reagisce ai giocatori locali.

## Attribuzione

Il grafo neurale è derivato da MaleCNS v1.0; conserva l'attribuzione e le note in `THIRD_PARTY_NOTICES.md`. Il precedente `connectome_weights.json` rimane per il volo di fondo legacy ed è derivato dal dataset BANC v888, anch'esso attribuito nel file delle note.
