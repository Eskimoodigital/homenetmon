import json
import os

CONFIG_PATH = os.path.expanduser('~/Library/Application Support/homenetmon/settings.json')

DEFAULTS = {
    'internet_host':    '1.1.1.1',
    'gateway_override': '',        # blank = auto-detect
    'ping_interval':    2,
}

# Ordered list of (display label, ip) for the settings dropdown
PRESETS = [
    ('Cloudflare  (1.1.1.1)', '1.1.1.1'),
    ('Google      (8.8.8.8)', '8.8.8.8'),
    ('Quad9       (9.9.9.9)', '9.9.9.9'),
    ('Custom',                ''),
]


def load():
    try:
        with open(CONFIG_PATH) as f:
            return {**DEFAULTS, **json.load(f)}
    except FileNotFoundError:
        return dict(DEFAULTS)


def save(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)
