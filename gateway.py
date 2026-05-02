import subprocess
import re


def get_default_gateway():
    """Discover the default gateway IP on macOS using the routing table."""
    try:
        result = subprocess.run(
            ['route', '-n', 'get', 'default'],
            capture_output=True, text=True, timeout=5
        )
        match = re.search(r'gateway:\s+(\S+)', result.stdout)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None
