# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Python interpreter

Always use `/opt/homebrew/bin/python3.13`. The pyenv Python (default `python3` on this machine) was built without tkinter support and will crash on import.

```bash
/opt/homebrew/bin/python3.13 app.py          # run from source
/opt/homebrew/bin/python3.13 -m pip install -r requirements.txt --break-system-packages
```

## Common commands

```bash
# Verify a change hasn't broken imports (run after every edit to app.py)
/opt/homebrew/bin/python3.13 -c "import app; print('OK')"

# Run the app
/opt/homebrew/bin/python3.13 app.py

# Build the .app bundle
./build_app.sh
```

## Architecture

The app is a single-window customtkinter UI that composes several independent background pollers. Each poller runs on a daemon thread and writes to a shared lock-protected dict; the UI reads from those dicts on a 1-second `after()` tick.

```
Pollers (background threads)         UI tick (every 1 s)
─────────────────────────────        ────────────────────────────────
PingMonitor      → db.py (SQLite)  → StatCard × 2  (current + avg ping)
                 → monitor.latest  ↗
NetworkInfoPoller → ssid / local_ip → info bar labels
SystemInfoPoller  → cpu / mem / disk → GaugeCard × 3
```

`_tick()` in `App` is the single update loop — all UI refreshes happen there.

Historical ping data is queried from SQLite (`get_recent_pings`, `get_stats`) rather than kept in memory, so the chart and stats always reflect persisted data.

## Known gotchas

**Disk path** — use `/System/Volumes/Data`, not `/`. On macOS, `/` is the read-only system volume (~10 GB); all user data is on the Data volume.

**Memory percentage** — calculate as `mem.used / mem.total`, not `psutil.virtual_memory().percent`. On macOS, psutil's `percent` uses `(total - available) / total` which includes inactive/cached pages and will read ~70% when actual usage is ~30%.

**SSID detection** — `airport -I` is removed on macOS Sequoia. Use `system_profiler SPAirPortDataType` and parse the line immediately after `Current Network Information:`.

**GaugeCard internal attribute** — do not use `self._canvas` inside `GaugeCard` (a `ctk.CTkFrame` subclass). customtkinter uses `_canvas` internally; overwriting it causes a crash when `bind()` is called. Use `self._mpl_canvas` instead.

**Binding clicks on a CTkFrame subclass** — `CTkFrame.bind()` routes through customtkinter's internal canvas, not the outer frame. To make a `GaugeCard` clickable, bind `<Button-1>` directly on `self._canvas` (the internal tkinter canvas), the matplotlib `tk_widget`, and any child labels individually. Do not call `self.bind()` on the frame itself.

**PyInstaller signing** — after building, run `xattr -cr dist/HomenetMon.app` before `codesign` or the `--deep` flag fails with "resource fork or detritus not allowed".

## Settings and data storage

| Path | Contents |
|---|---|
| `~/Library/Application Support/homenetmon/data.db` | SQLite ping history |
| `~/Library/Application Support/homenetmon/settings.json` | User settings (internet host, gateway override, ping interval) |
