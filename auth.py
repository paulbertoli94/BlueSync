import json
from pathlib import Path

import firebase_admin
import google
import requests
from firebase_admin import credentials, auth, firestore
from firebase_admin import db
from google_auth_oauthlib.flow import InstalledAppFlow

from communication import get_local_ip
from db_sync import read_devices

# === Config ===
CLIENT_SECRET_FILE = "client_secret.json"  # scaricato da Google Cloud Console
FIREBASE_ADMIN_CRED = "firebase-adminsdk.json"  # da Firebase > Service Account
FIREBASE_API_KEY = "AIzaSyCON1DLXlmWUiSCKe8c9SP99hGEorRyt-M"  # da Firebase > Project settings > Web API Key
TOKEN_PATH = Path("firebase_token.json")

# === Funzione per login Google + scambio token con Firebase ===
def get_firebase_id_token():
    # Se esiste un token salvato, usalo
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "r") as f:
            saved = json.load(f)
            id_token = saved.get("firebase_id_token")
            refresh_token = saved.get("refresh_token")

            try:
                auth.verify_id_token(id_token)
                print("✅ Accesso già effettuato.")
                return id_token
            except:
                print("⚠️ Token scaduto, provo a rinnovarlo...")
                if refresh_token:
                    return refresh_firebase_token(refresh_token)

    # === Primo accesso: login Google ===
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=["openid"]
    )
    creds = flow.run_local_server(port=0)
    request = google.auth.transport.requests.Request()
    creds.refresh(request)
    google_id_token = creds.id_token

    # === Scambia token con Firebase
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={FIREBASE_API_KEY}"
    payload = {
        "postBody": f"id_token={google_id_token}&providerId=google.com",
        "requestUri": "http://localhost",
        "returnIdpCredential": True,
        "returnSecureToken": True
    }
    res = requests.post(url, json=payload)
    res.raise_for_status()
    data = res.json()

    firebase_id_token = data["idToken"]
    refresh_token = data["refreshToken"]

    save_token(firebase_id_token, refresh_token)
    print("✅ Login completato con Firebase.")
    return firebase_id_token


# === Rinnovo token con refresh_token ===
def refresh_firebase_token(refresh_token):
    url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    res = requests.post(url, data=payload)
    if res.status_code == 200:
        data = res.json()
        new_id_token = data["id_token"]
        new_refresh_token = data["refresh_token"]

        save_token(new_id_token, new_refresh_token)
        print("🔁 Token rinnovato.")
        return new_id_token
    else:
        print("❌ Errore nel rinnovo:", res.text)
        return None


# === Salva token sul disco ===
def save_token(id_token, refresh_token):
    with open(TOKEN_PATH, "w") as f:
        json.dump({
            "firebase_id_token": id_token,
            "refresh_token": refresh_token
        }, f)


# === Inizializza Firestore ===
def init_firestore():
    cred = credentials.Certificate(FIREBASE_ADMIN_CRED)
    firebase_admin.initialize_app(cred)
    return firestore.client()


# === Demo: usa Firestore ===
def demo_firestore(db, user_email):
    ref = db.collection("utenti").document(user_email)
    ref.set({"ultimo_accesso": firestore.SERVER_TIMESTAMP}, merge=True)
    print("📄 Scrittura riuscita su Firestore.")


# === Funzione per login Google + scambio token con Firebase ===
def get_firebase_id_token():
    # Se esiste un token salvato, usalo
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "r") as f:
            saved = json.load(f)
            id_token = saved.get("firebase_id_token")
            refresh_token = saved.get("refresh_token")

            # Prova a verificare l'idToken
            try:
                auth.verify_id_token(id_token)
                print("✅ Accesso già effettuato.")
                return id_token
            except:
                print("⚠️ Token scaduto, provo refresh...")
                if refresh_token:
                    new_id_token = refresh_firebase_token(refresh_token)
                    if new_id_token:
                        return new_id_token

    # Step 1: login Google
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=["openid"]
    )
    creds = flow.run_local_server(port=0)

    request = google.auth.transport.requests.Request()
    creds.refresh(request)
    google_id_token = creds.id_token

    # Step 2: scambia token con Firebase via REST
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={FIREBASE_API_KEY}"
    payload = {
        "postBody": f"id_token={google_id_token}&providerId=google.com",
        "requestUri": "http://localhost",
        "returnIdpCredential": True,
        "returnSecureToken": True
    }
    res = requests.post(url, json=payload)
    res.raise_for_status()
    data = res.json()
    firebase_id_token = data["idToken"]
    refresh_token = data["refreshToken"]

    # Salva entrambi
    with open(TOKEN_PATH, "w") as f:
        json.dump({
            "firebase_id_token": firebase_id_token,
            "refresh_token": refresh_token
        }, f)

    print("✅ Login completato con Firebase.")
    return firebase_id_token


def init_realtime_db(token):
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_ADMIN_CRED)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://bluesync-6bdee-default-rtdb.europe-west1.firebasedatabase.app'
        })
    decoded = auth.verify_id_token(token)
    user_uid = decoded["uid"]
    email = decoded["email"]
    print("👤 Utente:", email)
    return user_uid


def demo_realtime_db(user_uid, device_id="device_daOj9HS5RDRiLDKcv5k8Jqt"):
    ref_path = f"devices/{user_uid}/{device_id}"
    ref = db.reference(ref_path)

    # Scrittura dati nel nodo
    ref.set({
        "ip": get_local_ip(),
        "status": "online",
        "timestamp": 1753048906  # timestamp di esempio
    })

    # Lettura e stampa
    ref_path_all = f"devices/{user_uid}"
    ref_all = db.reference(ref_path_all)
    data = ref_all.get()
    print(f"📡 Dati del user {user_uid}:\n", data)

def get_devices_to_sync(user_uid):
    """
    Legge i dispositivi locali via `read_devices`, li confronta con Firebase
    e restituisce solo quelli da sincronizzare.
    Se un dispositivo non esiste su Firebase, lo inserisce con `sync_required: true`.
    """
    bt_devices = read_devices()
    ref_base = db.reference(f"bt_devices/{user_uid}")
    devices_to_sync = []

    for device in bt_devices:
        mac = device["mac"]
        device_ref = ref_base.child(mac)
        existing = device_ref.get()

        if not existing:
            # Nuovo dispositivo → lo salviamo con sync_required: true
            device["sync_required"] = True
            device_ref.set({
                "name": device["name"],
                "active": device["active"],
                "sync_required": True
            })
            devices_to_sync.append(device)
        elif existing.get("sync_required", False):
            # Dispositivo già esistente ma ancora da sincronizzare
            device["sync_required"] = True
            devices_to_sync.append(device)

    print(f"📡 Devices to sync:\n", devices_to_sync)
    return devices_to_sync