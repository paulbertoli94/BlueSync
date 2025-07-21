import requests
import os
import sys
import tempfile
import subprocess

GITHUB_REPO = "tuo-utente/BlueSync"  # <-- Cambia con il tuo
ASSET_NAME = "BlueSync.exe"
CURRENT_VERSION = "1.0.0"

def get_latest_release():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def check_for_update():
    release = get_latest_release()
    if not release:
        print("⚠️ Nessuna release trovata.")
        return

    latest_version = release["tag_name"].lstrip("v")
    if latest_version == CURRENT_VERSION:
        print("✅ Nessun aggiornamento disponibile.")
        return

    print(f"⬇️ Nuova versione disponibile: {latest_version}")
    for asset in release["assets"]:
        if asset["name"] == ASSET_NAME:
            download_url = asset["browser_download_url"]
            temp_path = os.path.join(tempfile.gettempdir(), ASSET_NAME)

            print(f"📦 Scaricamento da {download_url}...")
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(temp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            print(f"✅ Scaricato: {temp_path}")

            # Lancia il nuovo eseguibile e chiude l'app corrente
            subprocess.Popen([temp_path])
            sys.exit()

