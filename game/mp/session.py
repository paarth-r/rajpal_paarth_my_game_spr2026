"""TCP host/client helpers (threads for blocking I/O)."""
import queue
import socket
import threading

from settings import MAX_MULTIPLAYERS, MP_PROTOCOL_VERSION, MULTIPLAYER_PORT
from game.mp.protocol import read_messages, write_message


class HostSession:
    def __init__(self, game, port=None):
        self.game = game
        self.port = int(port or MULTIPLAYER_PORT)
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(('0.0.0.0', self.port))
        self._listener.listen(min(32, max(8, MAX_MULTIPLAYERS * 4)))
        self._running = True
        self.pending_connections = queue.Queue()
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def _accept_loop(self):
        while self._running:
            try:
                conn, _addr = self._listener.accept()
            except OSError:
                break
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
            self.pending_connections.put(conn)

    def close(self):
        self._running = False
        try:
            self._listener.close()
        except OSError:
            pass

    def start_reader(self, sock, slot):
        t = threading.Thread(target=self._reader_loop, args=(sock, slot), daemon=True)
        t.start()

    def _reader_loop(self, sock, slot):
        buf = bytearray()
        while self._running and getattr(self.game, 'running', True):
            try:
                msgs = read_messages(sock, buf)
            except (ConnectionError, OSError, ValueError):
                self.game.mp_disconnect_queue.put(slot)
                try:
                    sock.close()
                except OSError:
                    pass
                return
            for m in msgs:
                self.game.mp_inbox.put((slot, m))

    def send_to_slot(self, sock, lock, obj):
        with lock:
            try:
                write_message(sock, obj)
            except OSError:
                pass


class ClientSession:
    def __init__(self, game, sock):
        self.game = game
        self._sock = sock
        try:
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self._sock.setblocking(True)
        self._send_lock = threading.Lock()
        self._running = True
        self._buf = bytearray()
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    def _reader_loop(self):
        while self._running and getattr(self.game, 'running', True):
            try:
                msgs = read_messages(self._sock, self._buf)
            except (ConnectionError, OSError, ValueError):
                self.game.mp_client_lost = True
                return
            for m in msgs:
                if m.get('type') == 'snapshot':
                    self.game.mp_latest_snapshot = m

    def send(self, obj):
        with self._send_lock:
            write_message(self._sock, obj)

    def close(self):
        self._running = False
        try:
            self._sock.close()
        except OSError:
            pass


def build_welcome(slot, level_name):
    return {
        'type': 'welcome',
        'version': MP_PROTOCOL_VERSION,
        'slot': slot,
        'level': level_name,
    }
