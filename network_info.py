import subprocess
import re
import socket
import threading


def _get_wifi_ssid():
    """Return the current WiFi SSID, or None if unavailable."""
    # Primary: system_profiler — reliable on macOS Ventura/Sonoma/Sequoia
    # The SSID appears as the indented line immediately after "Current Network Information:"
    try:
        result = subprocess.run(
            ['system_profiler', 'SPAirPortDataType'],
            capture_output=True, text=True, timeout=6
        )
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            if 'Current Network Information:' in line:
                for j in range(i + 1, min(i + 4, len(lines))):
                    candidate = lines[j].strip()
                    # SSID line ends with a colon and has no key: value pattern
                    if candidate.endswith(':') and ':' not in candidate[:-1]:
                        return candidate.rstrip(':')
    except Exception:
        pass

    # Fallback: networksetup
    try:
        iface = _get_wifi_interface()
        result = subprocess.run(
            ['networksetup', '-getairportnetwork', iface],
            capture_output=True, text=True, timeout=3
        )
        match = re.search(r'Current Wi-Fi Network:\s+(.+)', result.stdout)
        if match:
            return match.group(1).strip()
    except Exception:
        pass

    return None


def _get_wifi_interface():
    """Return the Wi-Fi interface name (e.g. en0) on macOS."""
    try:
        result = subprocess.run(
            ['networksetup', '-listallhardwareports'],
            capture_output=True, text=True, timeout=3
        )
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            if 'Wi-Fi' in line or 'AirPort' in line:
                for j in range(i, min(i + 5, len(lines))):
                    m = re.search(r'Device:\s+(\S+)', lines[j])
                    if m:
                        return m.group(1)
    except Exception:
        pass
    return 'en0'


def _get_local_ip():
    """Return the local IP on the interface that routes to the internet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


class NetworkInfoPoller:
    """Polls SSID and local IP in a background thread; results readable any time."""

    def __init__(self, interval=15):
        self.interval = interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._data = {'ssid': None, 'local_ip': None}
        self._thread = None

    def start(self):
        self._refresh()          # populate immediately on start
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    @property
    def ssid(self):
        with self._lock:
            return self._data['ssid']

    @property
    def local_ip(self):
        with self._lock:
            return self._data['local_ip']

    def _refresh(self):
        ssid = _get_wifi_ssid()
        ip   = _get_local_ip()
        with self._lock:
            self._data = {'ssid': ssid, 'local_ip': ip}

    def _run(self):
        while not self._stop.wait(self.interval):
            self._refresh()
