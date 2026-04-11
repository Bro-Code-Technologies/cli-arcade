"""
game_classes/socket_client.py

Thread-safe Socket.io client wrapper for the /cli-arcade-mp namespace.
Runs python-socketio on a background daemon thread; exposes connect(),
disconnect(), emit(), poll(), and is_connected() as synchronous methods.
"""

import queue
import threading
import os

try:
    import socketio as _sio_lib
    _HAS_SOCKETIO = True
except ImportError:
    _HAS_SOCKETIO = False


class SocketClient:
    """
    Wraps a python-socketio Client so the synchronous game loop can use it
    without blocking on I/O.

    Usage::

        client = SocketClient()
        ok = client.connect(player_name='Alice')
        if ok:
            client.emit('lobby:create', {'gameType': 'star_ship_2', ...})
            for event, data in client.poll():
                ...
        client.disconnect()
    """

    NAMESPACE = '/cli-arcade-mp'

    def __init__(self):
        self._sio = None
        self._queue: queue.Queue = queue.Queue()
        self._connected = False
        self._connect_event = threading.Event()
        self._connect_error: str = ''
        self._lock = threading.Lock()
        self._player_name: str = 'Player'

    # ── public API ────────────────────────────────────────────────────────────

    def connect(self, player_name: str = 'Player', timeout: float = 8.0) -> bool:
        """Connect to the /cli-arcade-mp namespace.

        Returns True on success, False on failure.
        """
        if not _HAS_SOCKETIO:
            self._connect_error = 'python-socketio not installed. Run: pip install python-socketio[client]'
            return False

        url = os.environ.get('CLI_ARCADE_API_URL', 'https://brocodetech.com').rstrip('/')
        if not url:
            self._connect_error = 'CLI_ARCADE_API_URL environment variable is not set.'
            return False

        self._player_name = player_name
        self._connect_event.clear()
        self._connect_error = ''

        # Build a fresh client each time we (re-)connect.
        self._sio = _sio_lib.Client(reconnection=False, logger=False, engineio_logger=False)
        self._register_handlers()

        def _do_connect():
            try:
                self._sio.connect(
                    url,
                    namespaces=[self.NAMESPACE],
                    auth={'playerName': self._player_name},
                    transports=['websocket'],
                )
                # connect() blocks until disconnect on some versions — just let
                # the on_connect handler set the event.  We run sio.wait() in
                # the background so the event loop keeps running.
                self._sio.wait()
            except Exception as exc:
                with self._lock:
                    self._connected = False
                    self._connect_error = str(exc)
                self._connect_event.set()

        t = threading.Thread(target=_do_connect, daemon=True, name='socket-client')
        t.start()

        # Wait for connection or error (up to `timeout` seconds).
        self._connect_event.wait(timeout=timeout)
        return self._connected

    def disconnect(self):
        """Cleanly disconnect from the server."""
        if self._sio is not None:
            try:
                self._sio.disconnect()
            except Exception:
                pass

    def emit(self, event: str, data=None):
        """Emit an event to the server (non-blocking)."""
        if self._sio is None or not self._connected:
            return
        try:
            self._sio.emit(event, data, namespace=self.NAMESPACE)
        except Exception:
            pass

    def poll(self):
        """Drain and return all queued (event, data) tuples without blocking."""
        items = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def is_connected(self) -> bool:
        return self._connected

    def last_error(self) -> str:
        return self._connect_error

    # ── internal ──────────────────────────────────────────────────────────────

    def _push(self, event: str, data):
        self._queue.put((event, data))

    def _register_handlers(self):
        ns = self.NAMESPACE

        @self._sio.event(namespace=ns)
        def connect():  # noqa: F811
            with self._lock:
                self._connected = True
            self._connect_event.set()
            self._push('_connected', {})

        @self._sio.event(namespace=ns)
        def connect_error(data):
            with self._lock:
                self._connected = False
                self._connect_error = str(data)
            self._connect_event.set()
            self._push('_connect_error', {'message': str(data)})

        @self._sio.event(namespace=ns)
        def disconnect():  # noqa: F811
            with self._lock:
                self._connected = False
            self._push('_disconnected', {})

        # ── lobby events ──────────────────────────────────────────────────────
        for _ev in (
            'lobby:created',
            'lobby:joined',
            'lobby:player_joined',
            'lobby:player_left',
            'lobby:error',
            'lobby:list',
            'lobby:dissolved',
        ):
            # Capture loop variable
            def _make_handler(ev):
                @self._sio.on(ev, namespace=ns)
                def _handler(data=None):
                    self._push(ev, data or {})
            _make_handler(_ev)

        # ── game events ───────────────────────────────────────────────────────
        for _ev in (
            'game:start',
            'game:state',
            'game:over',
            'game:player_died',
            'game:invalid_move',
            'game:request_size',
        ):
            def _make_game_handler(ev):
                @self._sio.on(ev, namespace=ns)
                def _handler(data=None):
                    self._push(ev, data or {})
            _make_game_handler(_ev)
