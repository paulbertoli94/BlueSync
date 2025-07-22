import os
import subprocess
import sys
import tempfile

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_REPO = "paulbertoli94/BlueSync"
ASSET_NAME = "BlueSync.exe"
CURRENT_VERSION = "1.0.12"
TOKEN = os.getenv("GITHUB_TOKEN")


def get_latest_release():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    print("TOKEN:", TOKEN)
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None


def check_for_update():
    # Esegui solo se è un eseguibile compilato (.exe)
    if not getattr(sys, 'frozen', False):
        print("[~] Skip aggiornamento (modalità debug).")
        return

    release = get_latest_release()
    if not release:
        print("[!] Nessuna release trovata.")
        return

    latest_version = release["tag_name"].lstrip("v")
    if latest_version == CURRENT_VERSION:
        print("[=] Nessun aggiornamento disponibile.")
        return

    print(f"[+] Nuova versione disponibile: {latest_version}")
    for asset in release["assets"]:
        if asset["name"] == ASSET_NAME:
            download_url = asset["browser_download_url"]
            temp_dir = tempfile.gettempdir()
            temp_new = os.path.join(temp_dir, "BlueSync_new.exe")
            updater_script = os.path.join(temp_dir, "updater.bat")

            print(f"[>] Scaricamento da {download_url}...")
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(temp_new, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            print(f"[✓] Scaricato in {temp_new}")

            current_path = sys.executable
            with open(updater_script, "w", encoding="utf-8") as bat:
                bat.write(f"""@echo off
timeout /t 2 >nul
taskkill /f /im "{os.path.basename(current_path)}"
move /y "{temp_new}" "{current_path}"
start "" "{current_path}"
""")

            subprocess.Popen(['cmd', '/c', 'start', '', updater_script])
            sys.exit()
