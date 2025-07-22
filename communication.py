import json
import socket
import threading
import uuid

import netifaces


class MessageBuilder:
    def __init__(self, json_string=None):
        if json_string:
            try:
                self.message = json.loads(json_string)
            except Exception:
                self.message = {}
        else:
            self.message = {}

    def set_bt_request(self, bt_mac):
        self.message["type"] = "bt_request"
        self.message["bt_mac"] = bt_mac
        self.message["communication_type"] = "server"
        self.message["request_id"] = str(uuid.uuid4())
        return self

    def set_bt_want(self, bt_mac):
        self.message["type"] = "bt_want"
        self.message["bt_mac"] = bt_mac
        self.message["communication_type"] = "server"
        return self

    def set_bt_response(self, message):
        self.message["type"] = "bt_response"
        self.message["bt_mac"] = message.get_bt_mac()
        self.message["request_id"] = message.get_request_id()
        return self

    def set_bt_is_playing(self, message):
        self.message["type"] = "bt_is_playing"
        self.message["bt_mac"] = message.get_bt_mac()
        self.message["request_id"] = message.get_request_id()
        return self

    def set_communication_type(self, value):
        self.message["communication_type"] = value
        return self

    def build(self):
        return json.dumps(self.message)

    def get_type(self):
        return self.message.get("type")

    def get_bt_mac(self):
        return self.message.get("bt_mac")

    def get_request_id(self):
        return self.message.get("request_id")


class UDPListener(threading.Thread):
    def __init__(self, on_message_callback):
        super().__init__(daemon=True)
        self.on_message_callback = on_message_callback
        self.port = 54600
        self.local_ips = self.get_all_local_ips()

    def get_all_local_ips(self):
        ips = set()
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for link in addrs[netifaces.AF_INET]:
                    ips.add(link['addr'])
        return ips

    def run(self):
        print("🟡 UDP Listener avviato.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('', self.port))
        print("📡 Sto inviando da:", sock.getsockname()[0])

        while True:
            data, addr = sock.recvfrom(15000)
            sender_ip = addr[0]

            if sender_ip in self.local_ips:
                continue  # Ignora messaggi da se stesso

            message = data.decode('utf-8')
            print(f"📩 Ricevuto UDP da {addr[0]}: {message}")
            self.on_message_callback(addr[0], MessageBuilder(message))

    def send_udp(self, target_ip="255.255.255.255", message_builder: MessageBuilder = None):
        if message_builder is None:
            return
        try:
            response = message_builder.build()
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind((get_local_ip(), 0))
                sock.sendto(response.encode(), (target_ip, 54600))
            print(f"✅ Risposta inviata via UDP a {target_ip}: {response}")
        except Exception as e:
            print(f"❌ Errore nell'invio della risposta UDP: {e}")


class TCPServer(threading.Thread):
    def __init__(self, handle_tcp_message_callback):
        super().__init__(daemon=True)
        self.port = 50505
        self.handle_tcp_message_callback = handle_tcp_message_callback

    def run(self):
        print(f"🟢 TCP Server avviato: {get_local_ip()}")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((get_local_ip(), self.port))
        server_socket.listen(5)

        while True:
            client_socket, addr = server_socket.accept()
            print(f"🔌 Connessione TCP da {addr}")
            threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()

    def handle_client(self, client_socket):
        try:
            data = client_socket.recv(4096).decode('utf-8').strip()
            print(f"💬 Messaggio TCP ricevuto: {data}")
            client_ip, _ = client_socket.getpeername()
            message = MessageBuilder(data)
            self.handle_tcp_message_callback(client_ip, message)

        except Exception as e:
            print(f"❌ Errore gestione client TCP: {e}")
        finally:
            client_socket.close()


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        # Fallback su interfacce locali, se disponibile
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr['addr']
                    if ip != "127.0.0.1":
                        return ip
        return "0.0.0.0"
    finally:
        s.close()
