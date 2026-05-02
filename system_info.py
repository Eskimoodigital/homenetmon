import threading
import psutil


class SystemInfoPoller:
    """Polls CPU and memory usage in a background thread at a fixed interval."""

    def __init__(self, interval=2):
        self.interval = interval
        self._stop    = threading.Event()
        self._lock    = threading.Lock()
        self._data    = {
            'cpu_pct':       0.0,
            'mem_used_gb':   0.0,
            'mem_total_gb':  0.0,
            'disk_used_gb':  0.0,
            'disk_total_gb': 0.0,
        }
        self._thread = None

    def start(self):
        # Prime cpu_percent so the first real reading is meaningful
        psutil.cpu_percent(interval=None)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    @property
    def cpu_pct(self):
        with self._lock:
            return self._data['cpu_pct']

    @property
    def mem_data(self):
        with self._lock:
            return dict(self._data)

    def _refresh(self):
        cpu  = psutil.cpu_percent(interval=None)
        mem  = psutil.virtual_memory()
        # On macOS, / is the read-only system volume; user data lives on the Data volume
        _disk_path = '/System/Volumes/Data' if __import__('os').path.exists('/System/Volumes/Data') else '/'
        disk = psutil.disk_usage(_disk_path)
        with self._lock:
            self._data = {
                'cpu_pct':       cpu,
                'mem_used_gb':   mem.used   / (1024 ** 3),
                'mem_total_gb':  mem.total  / (1024 ** 3),
                'disk_used_gb':  disk.used  / (1024 ** 3),
                'disk_total_gb': disk.total / (1024 ** 3),
            }

    def _run(self):
        while not self._stop.wait(self.interval):
            self._refresh()
