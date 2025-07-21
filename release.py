import os
import re
import subprocess

import requests

REPO = "paulbertoli94/BlueSync"  # ← Cambia con il tuo repo
TOKEN = os.getenv("GITHUB_TOKEN")  # Usa variabile ambiente
ICON = "icon_not_connected.ico"
VERSION_FILE = "updater.py"
EXE_NAME = "BlueSync.exe"
TAG_PREFIX = "v"


def get_next_version():
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r'CURRENT_VERSION\s*=\s*[\'"](\d+\.\d+\.\d+)[\'"]', content)
    if not match:
        raise ValueError("Versione non trovata in main.py")

    major, minor, patch = map(int, match.group(1).split('.'))
    new_version = f"{major}.{minor}.{patch + 1}"

    # Sostituisci nel file
    new_content = re.sub(
        r'__version__\s*=\s*[\'"]\d+\.\d+\.\d+[\'"]',
        f'__version__ = "{new_version}"',
        content
    )
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

    return new_version


def build_exe():
    cmd = [
        "pyinstaller", "main.py", "--onefile", "--noconsole",
        f"--icon={ICON}",
        "--add-data", "icon_connected.png;.",
        "--add-data", "icon_not_connected.png;.",
        "--add-data", "ToothTray.exe;.",
        "--name", "BlueSync"
    ]
    subprocess.run(cmd, check=True)


def git_commit_and_tag(version):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", f"Release v{version}"], check=True)
    subprocess.run(["git", "tag", f"{TAG_PREFIX}{version}"], check=True)
    subprocess.run(["git", "push"], check=True)
    subprocess.run(["git", "push", "origin", f"{TAG_PREFIX}{version}"], check=True)


def upload_release(version):
    if not TOKEN:
        print("⚠️ TOKEN non trovato. Imposta GITHUB_TOKEN come variabile ambiente.")
        return

    exe_path = os.path.join("dist", EXE_NAME)
    tag = f"{TAG_PREFIX}{version}"

    # Crea la release
    url = f"https://api.github.com/repos/{REPO}/releases"
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.post(url, headers=headers, json={
        "tag_name": tag,
        "name": f"Version {version}",
        "body": f"Release {version}",
        "draft": False,
        "prerelease": False
    })
    response.raise_for_status()
    upload_url = response.json()["upload_url"].split("{")[0]

    # Upload del file .exe
    with open(exe_path, "rb") as f:
        headers.update({"Content-Type": "application/octet-stream"})
        upload = requests.post(
            f"{upload_url}?name={EXE_NAME}",
            headers=headers,
            data=f
        )
        upload.raise_for_status()
        print(f"✅ EXE caricato su GitHub: {upload.json()['browser_download_url']}")


if __name__ == "__main__":
    print("🚀 Building & Releasing...")

    new_version = get_next_version()
    print(f"📦 Nuova versione: {new_version}")

    build_exe()
    print("🔧 EXE creato.")

    git_commit_and_tag(new_version)
    print("📤 Versione pushata su GitHub.")

    upload_release(new_version)
