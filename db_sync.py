import os
import subprocess
import sys


def resource_path(relative_path):
    """ Restituisce il path assoluto anche da exe """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


EXE_PATH = resource_path("ToothTray.exe")


def run_toothtray(args, timeout=10):
    """Esegue ToothTray.exe con i parametri specificati senza mostrare la console."""
    try:
        if os.name == 'nt':
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return subprocess.run(
                [EXE_PATH] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
                startupinfo=si
            )
        else:
            return subprocess.run([EXE_PATH] + args, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        print(f"❌ Errore in ToothTray.exe con args {args}: {e}")
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr=str(e))


def read_devices():
    result_devices = []
    try:
        result = run_toothtray(['list-mac'])
        output = result.stdout.strip().splitlines()
        for line in output:
            parts = line.strip().split('|')
            if len(parts) == 3:
                active, mac, name = parts
                result_devices.append({
                    'active': active == '1',
                    'mac': mac.strip(),
                    'name': name.strip()
                })
        return result_devices
    except Exception as e:
        print(f"Errore nella lettura dispositivi: {e}")
        return []


def connect_device(mac):
    try:
        run_toothtray(['connect-by-mac', mac], timeout=10)
    except Exception as e:
        print(f"Errore nella connessione: {e}")


def disconnect_device(mac):
    try:
        run_toothtray(['disconnect-by-mac', mac], timeout=10)
    except Exception as e:
        print(f"Errore nella disconnessione: {e}")

def is_connected(mac):
    try:
        result = run_toothtray(['is-connected-by-mac', mac], timeout=2)
        output = result.stdout.strip()
        print(f"{mac} connection: {output}")
        return output == "1"
    except Exception as e:
        print(f"Errore nel controllo connessione: {e}")
        return False
