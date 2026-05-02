import subprocess
import re
import threading
import time

from db import insert_ping


def ping_once(host, timeout_sec=2):
    """Send a single ICMP ping. Returns (latency_ms, success)."""
    try:
        result = subprocess.run(
            ['ping', '-c', '1', '-W', str(int(timeout_sec * 1000)), host],
            capture_output=True, text=True, timeout=timeout_sec + 1
        )
        if result.returncode == 0:
            match = re.search(r'time[=<](\d+\.?\d*)\s*ms', result.stdout)
            if match:
                return float(match.group(1)), True
        return None, False
    except Exception:
        return None, False


class PingMonitor:
    def __init__(self, gateway, internet_host='1.1.1.1', interval=2):
        self.gateway = gateway
        self.internet_host = internet_host
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None

        # Most-recent results, readable by the UI without a DB round-trip
        self.latest = {
            'gateway':  {'latency_ms': None, 'success': False},
            'internet': {'latency_ms': None, 'success': False},
        }
        self._lock = threading.Lock()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            start = time.time()

            results = {}

            def do_ping(host, host_type):
                latency, success = ping_once(host)
                insert_ping(host, host_type, latency, success)
                with self._lock:
                    self.latest[host_type] = {'latency_ms': latency, 'success': success}

            t1 = threading.Thread(target=do_ping, args=(self.gateway, 'gateway'), daemon=True)
            t2 = threading.Thread(target=do_ping, args=(self.internet_host, 'internet'), daemon=True)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            elapsed = time.time() - start
            self._stop.wait(max(0, self.interval - elapsed))
