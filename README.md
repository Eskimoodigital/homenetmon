# HomenetMon

A lightweight macOS app that monitors your home network in real time. It compares your **default gateway** (local WiFi / router) against a stable internet host so you can distinguish between a WiFi problem and an ISP problem.

## Features

- **Real-time latency chart** — gateway and internet on the same chart, colour-coded
- **Dropped packet markers** — red ✕ on the chart wherever a packet was lost
- **Diagnosis card** — automatically interprets the data (ISP issue vs WiFi issue vs all good)
- **Current ping headline** — each network card shows the live last-ping result with the 2-minute rolling average beneath it
- **CPU, memory, and disk gauges** — semicircular arc gauges updated every 2 seconds; click CPU or Memory to open Activity Monitor, click Disk to open Disk Utility
- **Network info bar** — shows your current WiFi network name (SSID) and local IP address
- **Configurable targets** — change the internet host (Cloudflare, Google, Quad9, or custom) and ping interval via the Settings dialog
- **Persistent history** — ping results stored in SQLite; view the last 2 minutes, 15 minutes, or 1 hour
- **Packaged as a native `.app`** — double-click to launch, no terminal required

## Running from source

### First-time setup

```bash
./setup.sh
```

Or manually:

```bash
brew install python@3.13 python-tk@3.13
/opt/homebrew/bin/python3.13 -m pip install -r requirements.txt --break-system-packages
```

### Launch

```bash
/opt/homebrew/bin/python3.13 app.py
```

## Building the app

Produces `dist/HomenetMon.app` — a self-contained double-click app (~64 MB).

```bash
./build_app.sh
```

To install, drag `dist/HomenetMon.app` to your Applications folder.

> **Note:** The app is ad-hoc signed. On first launch macOS will show an "unidentified developer" warning — right-click → Open → Open anyway. A paid Apple Developer account ($99/year) removes this warning.

## Settings

Click **⚙ Settings** in the top-right corner to configure:

| Setting | Default | Options |
|---|---|---|
| Internet target | Cloudflare (1.1.1.1) | Cloudflare, Google (8.8.8.8), Quad9 (9.9.9.9), or custom |
| Gateway override | auto-detect | Any IP address |
| Ping interval | 2 s | 2 s, 5 s, 10 s |

Settings are saved to `~/Library/Application Support/homenetmon/settings.json` and take effect immediately without restarting the app.

## Diagnosis logic

| Gateway | Internet | Diagnosis |
|---|---|---|
| ✅ Good | ✅ Good | All good |
| ✅ Good | ❌ Poor | ISP issue likely |
| ❌ Poor | ✅ Good | WiFi / router issue |
| ❌ Poor | ❌ Poor | Widespread issue — check router and ISP |

## File structure

| File | Purpose |
|---|---|
| `app.py` | Main window, charts, and gauge UI |
| `pinger.py` | Background ping threads (gateway + internet) |
| `db.py` | SQLite schema and queries |
| `gateway.py` | Default gateway auto-discovery |
| `config.py` | Load / save user settings (JSON) |
| `network_info.py` | WiFi SSID and local IP detection |
| `system_info.py` | CPU, memory, and disk polling via psutil |
| `HomenetMon.spec` | PyInstaller build configuration |
| `build_app.sh` | One-command build script |
| `setup.sh` | First-time prerequisite installer |

## Data storage

| Path | Contents |
|---|---|
| `~/Library/Application Support/homenetmon/data.db` | Ping history (SQLite) |
| `~/Library/Application Support/homenetmon/settings.json` | User settings |

## Dependencies

```
customtkinter>=5.2.0
matplotlib>=3.8.0
psutil>=5.9.0
```

Install via `pip` using the Homebrew Python as shown in setup above. `tkinter` support requires the separate `python-tk@3.13` Homebrew package.
