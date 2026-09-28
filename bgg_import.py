#!/usr/bin/env python3
"""
bgg_import.py — Cerca ogni gioco da tavolo su BoardGameGeek, scarica la
copertina, la comprime e scrive tutto in giochi_import.json nella root
del repository della webapp.

IMPORTANTE — BGG ora richiede un token di autorizzazione per usare l'API:
    1. Vai su https://boardgamegeek.com/applications
    2. Crea un'applicazione (scegli "Non-commercial")
    3. Aspetta l'approvazione (può volerci qualche giorno)
    4. Una volta approvata, torna sulla stessa pagina, clicca "Tokens"
       sulla tua applicazione e generane un token
    5. Imposta il token come variabile d'ambiente prima di eseguire lo
       script (NON scriverlo dentro questo file):

       Su Mac/Linux (terminale):
           export BGG_API_TOKEN="il-tuo-token-qui"
           python3 bgg_import.py

       Su Windows (PowerShell):
           $env:BGG_API_TOKEN="il-tuo-token-qui"
           python3 bgg_import.py

USO (dopo aver impostato il token):
    1. Metti questo file e games_list.txt nella cartella del repository
       (stesso livello di index.html).
    2. Installa le dipendenze (una volta sola):
           pip install requests pillow
       (su alcuni sistemi serve: pip3 install requests pillow --break-system-packages)
    3. Esegui (nella stessa finestra di terminale dove hai impostato la
       variabile d'ambiente sopra):
           python3 bgg_import.py
    4. Alla fine troverai "giochi_import.json" nella stessa cartella.
    5. Fai il commit/push del file nel repository (git add, commit, push),
       oppure chiedi a Claude Code di farlo per te.

Va eseguito su un computer con normale accesso a internet (il tuo PC di
casa va benissimo). Non funziona in ambienti cloud con rete ristretta.
"""

import json
import os
import re
import time
import sys
import base64
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from PIL import Image

GAMES_LIST_FILE = "games_list.txt"
OUTPUT_FILE = "giochi_import.json"
MAX_DIM = 1000
JPEG_QUALITY = 86
REQUEST_DELAY = 1.2  # secondi tra una chiamata e l'altra, per rispettare l'API di BGG
USER_AGENT = "Mozilla/5.0 (compatible; RaccoglitoreCarteImport/1.0; personal use)"

SEARCH_URL = "https://boardgamegeek.com/xmlapi2/search"
THING_URL = "https://boardgamegeek.com/xmlapi2/thing"

BGG_API_TOKEN = os.environ.get("BGG_API_TOKEN", "").strip()


def bgg_headers():
    headers = {"User-Agent": USER_AGENT}
    if BGG_API_TOKEN:
        headers["Authorization"] = f"Bearer {BGG_API_TOKEN}"
    return headers


def bgg_get(url, params, max_retries=5):
    """BGG a volte risponde 202 (richiesta accodata) mentre prepara i dati:
    va ritentata dopo una breve pausa."""
    for attempt in range(max_retries):
        resp = requests.get(url, params=params, headers=bgg_headers(), timeout=20)
        if resp.status_code == 202:
            time.sleep(2)
            continue
        if resp.status_code == 401:
            raise RuntimeError(
                "401 Unauthorized — il token BGG manca, non è ancora stato "
                "approvato, o è sbagliato. Controlla la variabile d'ambiente "
                "BGG_API_TOKEN (vedi istruzioni in cima a questo file)."
            )
        resp.raise_for_status()
        return resp.text
    raise RuntimeError(f"BGG non ha mai risposto dopo {max_retries} tentativi per {params}")


def search_game_id(name):
    xml_text = bgg_get(SEARCH_URL, {"query": name, "type": "boardgame"})
    root = ET.fromstring(xml_text)
    items = root.findall("item")
    if not items:
        return None

    # Preferisci corrispondenza esatta del nome (case-insensitive)
    name_lower = name.strip().lower()
    for item in items:
        for nm in item.findall("name"):
            if nm.get("value", "").strip().lower() == name_lower:
                return item.get("id")

    # Altrimenti il primo risultato
    return items[0].get("id")


def fetch_cover_url(bgg_id):
    xml_text = bgg_get(THING_URL, {"id": bgg_id, "type": "boardgame"})
    root = ET.fromstring(xml_text)
    item = root.find("item")
    if item is None:
        return None
    image_el = item.find("image")
    if image_el is not None and image_el.text:
        return image_el.text.strip()
    thumb_el = item.find("thumbnail")
    if thumb_el is not None and thumb_el.text:
        return thumb_el.text.strip()
    return None


def download_and_compress(image_url):
    resp = requests.get(image_url, headers=bgg_headers(), timeout=30)
    resp.raise_for_status()
    img = Image.open(BytesIO(resp.content)).convert("RGB")

    w, h = img.size
    if w > h and w > MAX_DIM:
        new_w, new_h = MAX_DIM, round(h * MAX_DIM / w)
    elif h >= w and h > MAX_DIM:
        new_h, new_w = MAX_DIM, round(w * MAX_DIM / h)
    else:
        new_w, new_h = w, h
    if (new_w, new_h) != (w, h):
        img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def main():
    if not BGG_API_TOKEN:
        print(
            "BGG_API_TOKEN non impostato localmente, procedo comunque "
            "assumendo che la rete gestisca l'autenticazione."
        )

    list_path = Path(GAMES_LIST_FILE)
    if not list_path.exists():
        print(f"ERRORE: non trovo {GAMES_LIST_FILE} nella cartella corrente.")
        sys.exit(1)

    names = [line.strip() for line in list_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Trovati {len(names)} nomi da cercare.\n")

    games = []
    not_found = []

    for i, name in enumerate(names, 1):
        print(f"[{i}/{len(names)}] {name} ...", end=" ", flush=True)
        try:
            bgg_id = search_game_id(name)
            if not bgg_id:
                print("NON TROVATO su BGG")
                not_found.append(name)
                continue
            time.sleep(REQUEST_DELAY)

            cover_url = fetch_cover_url(bgg_id)
            if not cover_url:
                print(f"trovato (id={bgg_id}) ma senza immagine")
                not_found.append(name)
                continue
            time.sleep(REQUEST_DELAY)

            data_url = download_and_compress(cover_url)
            games.append({"name": name, "bgg_id": int(bgg_id), "image": data_url})
            print(f"OK (id={bgg_id})")

        except Exception as e:
            print(f"ERRORE: {e}")
            not_found.append(name)

        time.sleep(REQUEST_DELAY)

    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "BoardGameGeek",
        "games": games,
    }
    Path(OUTPUT_FILE).write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")

    size_mb = Path(OUTPUT_FILE).stat().st_size / (1024 * 1024)
    print("\n" + "=" * 50)
    print(f"Fatto. {len(games)} giochi importati su {len(names)} richiesti.")
    print(f"File scritto: {OUTPUT_FILE} ({size_mb:.1f} MB)")
    if not_found:
        print(f"\nNon trovati o falliti ({len(not_found)}):")
        for n in not_found:
            print(f"  - {n}")


if __name__ == "__main__":
    main()
