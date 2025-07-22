import os
import sys
import threading
import time
from enum import Enum

import wx
import wx.adv
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation

from auth import get_firebase_id_token, init_realtime_db, get_devices_to_sync
from communication import UDPListener, TCPServer, MessageBuilder
from db_sync import read_devices, resource_path, disconnect_device, connect_device, is_connected
from updater import check_for_update
from user_activity import UserActivityMonitor

# Elenco delle app note per chiamate vocali/video
CALL_APPS = {'ms-teams.exe', 'zoom.exe', 'discord.exe', 'skype.exe', 'whatsapp.exe'}

session_active = False
session_start_time = 0
last_trigger_time = 0
cooldown_seconds = 5
session_duration = 10

pending_requests = {}
PENDING_TIMEOUT = 1

blocked_macs = set()

# macTest = "24:95:2F:AB:AF:6B"
macTest = "88:C9:E8:27:44:0C"

ICON_PATH = resource_path("icon_not_connected.png")
ICON_CONNECTED_PATH = resource_path("icon_connected.png")

tray_icon = None


class BluetoothPlaybackState(Enum):
    DISCONNECTED = 1
    CONNECTED_NOT_PLAYING = 2
    CONNECTED_PLAYING = 3


def any_device_connected_with_icon_update(devices=None):
    if devices is None:
        devices = read_devices()

    connected = any(device['active'] for device in devices)

    if tray_icon:
        wx.CallAfter(tray_icon.update_icon, connected)

    return connected


def is_audio_playing(threshold=0.02):
    sessions = AudioUtilities.GetAllSessions()
    audio_detected = False

    for session in sessions:
        process = session.Process
        if not process:
            continue

        name = process.name().lower()
        try:
            # Accesso all'interfaccia di controllo volume
            volume = session._ctl.QueryInterface(IAudioMeterInformation)
            peak = volume.GetPeakValue()
            state = session.State  # 0: inactive, 1: active, 2: expired (rare)

            # Caso 1: audio sopra soglia → consideriamo attivo
            if peak > threshold:
                print(f"🔊 {name} → volume: {peak:.5f} (attivo)")
                return True

            # Caso 2: app di chiamata attiva anche con volume 0 → consideriamo attiva
            if name in CALL_APPS and state == 1:
                print(f"☎️ {name} → volume: {peak:.5f} ma sessione attiva → chiamata in corso?")
                return True

            print(f"🔇 {name} → volume: {peak:.5f}")
        except Exception as e:
            print(f"⚠️ Errore su {name}: {e}")

    return False


def handle_message(sender_ip, message: MessageBuilder):
    if message.get_type() == "bt_request":
        print(f"📡 Richiesta disconnessione BT da {sender_ip} per {message.get_bt_mac()}")

        state = get_bluetooth_playback_state(message.get_bt_mac())
        if state == BluetoothPlaybackState.DISCONNECTED:
            print("🎵 La cuffia non è connessa.")
        elif state == BluetoothPlaybackState.CONNECTED_NOT_PLAYING:
            print("🎧 La cuffia è connessa ma non sta riproducendo.")
            disconnect_device(message.get_bt_mac())
            response = MessageBuilder().set_bt_response(message)
            any_device_connected_with_icon_update()
            send_message_with_response_check(target_ip=sender_ip, message_builder=response)
        elif state == BluetoothPlaybackState.CONNECTED_PLAYING:
            print("🎵 La cuffia è connessa e in riproduzione.")
            response = MessageBuilder().set_bt_is_playing(message)
            send_message_with_response_check(target_ip=sender_ip, message_builder=response)

    if message.get_type() == "bt_response":
        pending_requests.pop(message.get_request_id(), None)
        blocked_macs.add(message.get_bt_mac())
        connect_device(message.get_bt_mac())
        any_device_connected_with_icon_update()

    if message.get_type() == "bt_want":
        print(f"📡 Richiesta want BT da {sender_ip} per {message.get_bt_mac()}")
        if session_active:
            message = MessageBuilder().set_bt_request(message.get_bt_mac())
            send_message_with_response_check(target_ip=sender_ip, message_builder=message)
        else:
            print(f"⚠️ Ignoro richiesta per {message.get_bt_mac()}: sessione non attiva.")

    if message.get_type() == "bt_is_playing":
        pending_requests.pop(message.get_request_id(), None)


def send_message_with_response_check(message_builder: MessageBuilder, target_ip="255.255.255.255"):
    if message_builder.get_request_id():
        pending_requests[message_builder.get_request_id()] = time.time()

        udp_listener.send_udp(target_ip=target_ip, message_builder=message_builder)

        if "bt_request" == message_builder.get_type():
            print(f"⚠️ {PENDING_TIMEOUT}s di attesa per la risposta di {message_builder.get_request_id()}.")

            def check_response_later():
                time.sleep(PENDING_TIMEOUT)
                if message_builder.get_request_id() in pending_requests:
                    print(
                        f"⏳ Nessuna risposta per {message_builder.get_request_id()}, provo a connettere il dispositivo.")
                    connect_device(message_builder.get_bt_mac())
                    pending_requests.pop(message_builder.get_request_id(), None)

            threading.Thread(target=check_response_later, daemon=True).start()


def get_bluetooth_playback_state(mac):
    if not is_connected(mac):
        return BluetoothPlaybackState.DISCONNECTED
    if not is_audio_playing():
        return BluetoothPlaybackState.CONNECTED_NOT_PLAYING
    return BluetoothPlaybackState.CONNECTED_PLAYING


class BTTrayApp(wx.adv.TaskBarIcon):
    def __init__(self):
        super().__init__()
        self.icon = wx.Icon(ICON_PATH)
        self.SetIcon(wx.BitmapBundle(self.icon), "Bluetooth Manager")
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_UP, self.on_click)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_UP, self.on_click)

    def on_click(self, event):
        menu = wx.Menu()

        for device in read_devices():
            label = f"{'◉' if device['active'] else '◎'} {device['name']}"
            item = menu.Append(-1, label)
            self.Bind(wx.EVT_MENU,
                      lambda evt, mac=device['mac'], active=device['active']: self.toggle_device(mac, active), item)

        menu.AppendSeparator()
        quit_item = menu.Append(wx.ID_EXIT, "❌ Esci")
        self.Bind(wx.EVT_MENU, self.on_quit, quit_item)

        self.PopupMenu(menu)
        menu.Destroy()

    def toggle_device(self, mac, active):
        def task():
            if active:
                disconnect_device(mac)
            else:
                connect_device(mac)

        any_device_connected_with_icon_update()
        threading.Thread(target=task, daemon=True).start()

    def on_quit(self, event):
        self.Destroy()
        wx.CallAfter(wx.GetApp().ExitMainLoop)

    def update_icon(self, connected):
        icon_path = ICON_CONNECTED_PATH if connected else ICON_PATH
        self.icon = wx.Icon(icon_path)
        self.SetIcon(wx.BitmapBundle(self.icon), "Bluetooth Manager")


class MyApp(wx.App):
    def OnInit(self):
        self.tbicon = BTTrayApp()
        return True


def user_is_active(devices_to_sync):
    global last_trigger_time, session_active, session_start_time
    now = time.time()

    if not session_active or (now - session_start_time > session_duration):
        session_active = True
        session_start_time = now
        print("🟢 Nuova sessione utente attiva.")

    time_since_session_start = now - session_start_time
    time_since_last_trigger = now - last_trigger_time

    # Solo nel primo minuto della sessione
    if time_since_session_start <= 30 and time_since_last_trigger >= cooldown_seconds:
        last_trigger_time = now
        local_devices  = read_devices()
        # Filtra solo quelli da sincronizzare
        devices_to_check = [
            dev for dev in local_devices
            if any(sync_dev['mac'] == dev['mac'] and sync_dev.get('sync_required') for sync_dev in devices_to_sync)
        ]
        if not any_device_connected_with_icon_update(devices_to_check):
            print("💡 Utente attivo, cuffie non connesse. Invio richiesta.")
            for device in devices_to_check:
                message = MessageBuilder().set_bt_request(device['mac'])
                send_message_with_response_check(message_builder=message)
        else:
            print("✅ Almeno un dispositivo è già connesso.")


# schifo, rifare con api in diretta
def devices_connection_watcher():
    prev_connected_set = set()
    while True:
        devices = read_devices()
        any_device_connected_with_icon_update(devices=devices)
        current_connected = {d['mac'] for d in devices if d['active']}

        new_connections = current_connected - prev_connected_set
        for mac in new_connections:
            print(f"🔌 Il dispositivo {mac} si è appena CONNESSO.")
            if mac in blocked_macs:
                blocked_macs.remove(mac)
                print("DeviceStateManager", "⛔️ BT_WANT ignorato per " + mac + " (bloccato da BT_RESPONSE)")
                continue
            message = MessageBuilder().set_bt_want(mac)
            send_message_with_response_check(message_builder=message)

        new_disconnections = prev_connected_set - current_connected
        for mac in new_disconnections:
            print(f"❌ Il dispositivo {mac} si è DISCONNESSO.")

        prev_connected_set = current_connected
        time.sleep(1)


def session_timeout_watcher():
    global session_active, session_start_time
    while True:
        if session_active and (time.time() - session_start_time > 300):  # 5 minuti
            print("🔴 Sessione terminata per inattività.")
            session_active = False
        time.sleep(10)


def resource_path(relative_path):
    """ Restituisce il path assoluto anche da exe """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


if __name__ == "__main__":
    check_for_update()
    token = get_firebase_id_token()
    user_uid = init_realtime_db(token)
    devices_to_sync = get_devices_to_sync(user_uid)

    monitor = UserActivityMonitor(lambda: user_is_active(devices_to_sync))
    monitor.start()

    udp_listener = UDPListener(handle_message)
    tcp_server = TCPServer(handle_message)

    udp_listener.start()
    tcp_server.start()

    threading.Thread(target=session_timeout_watcher, daemon=True).start()
    threading.Thread(target=devices_connection_watcher, daemon=True).start()

    app = MyApp(False)
    tray_icon = app.tbicon
    any_device_connected_with_icon_update()
    app.MainLoop()
