import threading

from pynput import keyboard, mouse


class UserActivityMonitor:
    def __init__(self, on_activity_callback):
        self.on_activity_callback = on_activity_callback
        self._keyboard_listener = keyboard.Listener(on_press=self._on_input)
        self._mouse_listener = mouse.Listener(on_move=self._on_input)

    def _on_input(self, *args, **kwargs):
        self.on_activity_callback()

    def start(self):
        threading.Thread(target=self._keyboard_listener.start, daemon=True).start()
        threading.Thread(target=self._mouse_listener.start, daemon=True).start()
