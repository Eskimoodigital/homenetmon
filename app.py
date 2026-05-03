import customtkinter as ctk
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from datetime import datetime
import subprocess
import numpy as np

from gateway import get_default_gateway
from db import init_db, get_recent_pings, get_stats
from pinger import PingMonitor
from config import load as load_config, save as save_config, PRESETS
from network_info import NetworkInfoPoller
from system_info import SystemInfoPoller

# ── colour palette ────────────────────────────────────────────────────────────
BG       = '#1e1e2e'
CARD_BG  = '#2a2a3e'
CHART_BG = '#16161e'
GREEN    = '#4ade80'
YELLOW   = '#facc15'
RED      = '#f87171'
BLUE     = '#60a5fa'
GREY     = '#6b7280'
TEXT     = '#e2e8f0'
TEXT_DIM = '#94a3b8'

TIME_RANGES = [('2 min', 120), ('15 min', 900), ('1 hour', 3600)]


def _safe_pct(used, total):
    return used / total if total > 0 else 0.0


def status_color(avg_ms, loss_pct):
    if avg_ms is None or loss_pct > 10:
        return RED, 'Poor'
    if avg_ms > 100 or loss_pct > 2:
        return YELLOW, 'Degraded'
    return GREEN, 'Excellent'


def diagnosis(gw_stats, inet_stats):
    gw_ok   = (gw_stats['avg_ms']   is not None and gw_stats['loss_pct']   < 5 and gw_stats['avg_ms']   < 100)
    inet_ok = (inet_stats['avg_ms'] is not None and inet_stats['loss_pct'] < 5)

    if gw_stats['count'] == 0:
        return GREY, 'Waiting for data…'
    if gw_ok and inet_ok:
        return GREEN, 'All good — network & internet healthy'
    if gw_ok and not inet_ok:
        return RED, 'ISP issue likely\nLocal network is fine'
    if not gw_ok and inet_ok:
        return YELLOW, 'WiFi / router issue\nInternet is reachable via gateway'
    return RED, 'Widespread issue\nCheck router and ISP'


# ── gauge drawing ─────────────────────────────────────────────────────────────
def _draw_gauge(ax, pct, center_text, sub_text):
    """Draw a semicircular arc gauge onto a matplotlib axes."""
    ax.clear()
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-0.55, 1.2)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_facecolor(CARD_BG)

    # Background track
    theta_bg = np.linspace(np.pi, 0, 200)
    ax.plot(np.cos(theta_bg), np.sin(theta_bg),
            color='#333355', linewidth=15, solid_capstyle='round', zorder=1)

    # Value arc
    if pct > 0.01:
        n = max(2, int(200 * pct))
        theta_val = np.linspace(np.pi, np.pi * (1 - pct), n)
        color = GREEN if pct < 0.60 else (YELLOW if pct < 0.85 else RED)
        ax.plot(np.cos(theta_val), np.sin(theta_val),
                color=color, linewidth=15, solid_capstyle='round', zorder=2)

    # Centre labels
    ax.text(0, 0.18, center_text, ha='center', va='center',
            fontsize=15, fontweight='bold', color=TEXT, zorder=3)
    ax.text(0, -0.22, sub_text, ha='center', va='center',
            fontsize=8, color=TEXT_DIM, zorder=3)

    # Scale end-points
    ax.text(-1.25, -0.1, '0', ha='center', fontsize=7, color=TEXT_DIM)
    ax.text( 1.25, -0.1, '100%', ha='center', fontsize=7, color=TEXT_DIM)


# ── gauge card ─────────────────────────────────────────────────────────────────
class GaugeCard(ctk.CTkFrame):
    def __init__(self, parent, title, on_click=None):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=10)

        cursor = 'pointinghand' if on_click else ''

        title_lbl = ctk.CTkLabel(self, text=title, font=('', 12, 'bold'),
                                 text_color=TEXT, cursor=cursor)
        title_lbl.pack(pady=(10, 0))

        self._fig = Figure(figsize=(3, 1.55), facecolor=CARD_BG)
        self._ax  = self._fig.add_subplot(111)
        self._fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

        self._mpl_canvas = FigureCanvasTkAgg(self._fig, master=self)
        tk_widget = self._mpl_canvas.get_tk_widget()
        tk_widget.pack(fill='both', expand=True, padx=4, pady=(0, 8))

        if on_click:
            tk_widget.configure(cursor=cursor)
            tk_widget.bind('<Button-1>', lambda e: on_click())
            title_lbl.bind('<Button-1>', lambda e: on_click())
            # Bind on the underlying tkinter widget, not the CTkFrame wrapper
            self._canvas.bind('<Button-1>', lambda e: on_click())

    def update(self, pct, center_text, sub_text):
        _draw_gauge(self._ax, pct, center_text, sub_text)
        self._mpl_canvas.draw_idle()


# ── stat card ─────────────────────────────────────────────────────────────────
class StatCard(ctk.CTkFrame):
    def __init__(self, parent, title, host):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=10)
        self._title_lbl = ctk.CTkLabel(self, text=title, font=('', 12, 'bold'), text_color=TEXT)
        self._title_lbl.pack(pady=(12, 0))
        self._host_lbl = ctk.CTkLabel(self, text=host, font=('', 10), text_color=TEXT_DIM)
        self._host_lbl.pack()

        self.latency = ctk.CTkLabel(self, text='— ms', font=('', 32, 'bold'), text_color=TEXT)
        self.latency.pack(pady=(6, 0))
        self.avg_lbl = ctk.CTkLabel(self, text='', font=('', 10), text_color=TEXT_DIM)
        self.avg_lbl.pack()
        self.loss   = ctk.CTkLabel(self, text='Packet loss: —', font=('', 11), text_color=TEXT_DIM)
        self.loss.pack(pady=(2, 0))
        self.minmax = ctk.CTkLabel(self, text='min / max', font=('', 10), text_color=TEXT_DIM)
        self.minmax.pack(pady=(2, 4))
        self.status = ctk.CTkLabel(self, text='● Monitoring…', font=('', 11), text_color=GREY)
        self.status.pack(pady=(0, 12))

    def set_labels(self, title, host):
        self._title_lbl.configure(text=title)
        self._host_lbl.configure(text=host)

    def update(self, current_ms, stats):
        avg = stats['avg_ms']
        mn  = stats['min_ms']
        mx  = stats['max_ms']

        # Headline: current ping (or dropped)
        if current_ms is not None:
            self.latency.configure(text=f'{current_ms:.0f} ms')
        else:
            self.latency.configure(text='dropped')

        # Secondary: 2-minute average
        self.avg_lbl.configure(text=f'2 min avg  {avg:.0f} ms' if avg else '')

        self.loss.configure(text=f'Packet loss: {stats["loss_pct"]:.1f}%')
        if mn and mx:
            self.minmax.configure(text=f'min {mn:.0f}  max {mx:.0f} ms')
        color, label = status_color(avg, stats['loss_pct'])
        self.status.configure(text=f'● {label}', text_color=color)


# ── settings dialog ───────────────────────────────────────────────────────────
class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, cfg, on_save):
        super().__init__(parent)
        self.title('Settings')
        self.geometry('400x340')
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=BG)

        self._cfg     = dict(cfg)
        self._on_save = on_save
        self._build()

    def _build(self):
        def section(text):
            ctk.CTkLabel(self, text=text, font=('', 12, 'bold'), text_color=TEXT).pack(
                anchor='w', padx=20, pady=(14, 2))

        # ── Internet host ──────────────────────────────────────────────────
        section('Internet target')

        current = self._cfg['internet_host']
        preset_labels = [lbl for lbl, _ in PRESETS]
        default_label = next((lbl for lbl, ip in PRESETS if ip == current), 'Custom')

        self._preset_var = ctk.StringVar(value=default_label)
        ctk.CTkOptionMenu(
            self, values=preset_labels, variable=self._preset_var,
            command=self._on_preset, fg_color=CARD_BG, text_color=TEXT,
            button_color=CARD_BG, button_hover_color='#3a3a5e',
            dropdown_fg_color=CARD_BG, dropdown_text_color=TEXT,
        ).pack(fill='x', padx=20, pady=(0, 4))

        ctk.CTkLabel(self, text='Custom IP or hostname', font=('', 10), text_color=TEXT_DIM).pack(
            anchor='w', padx=20)
        self._custom_var = ctk.StringVar(value=current if default_label == 'Custom' else '')
        self._custom_entry = ctk.CTkEntry(
            self, textvariable=self._custom_var,
            placeholder_text='e.g. 8.8.4.4 or example.com',
            fg_color=CARD_BG, text_color=TEXT, border_color=GREY,
        )
        self._custom_entry.pack(fill='x', padx=20, pady=(0, 4))
        self._refresh_custom_state(default_label)

        # ── Gateway override ───────────────────────────────────────────────
        section('Gateway override  (blank = auto-detect)')
        self._gw_var = ctk.StringVar(value=self._cfg.get('gateway_override', ''))
        ctk.CTkEntry(
            self, textvariable=self._gw_var,
            placeholder_text='e.g. 192.168.1.1',
            fg_color=CARD_BG, text_color=TEXT, border_color=GREY,
        ).pack(fill='x', padx=20, pady=(0, 4))

        # ── Ping interval ──────────────────────────────────────────────────
        section('Ping interval')
        row = ctk.CTkFrame(self, fg_color='transparent')
        row.pack(fill='x', padx=20, pady=(0, 4))
        self._interval_var = ctk.StringVar(value=str(self._cfg.get('ping_interval', 2)))
        for secs in ('2', '5', '10'):
            ctk.CTkRadioButton(
                row, text=f'{secs} s', variable=self._interval_var, value=secs,
                font=('', 11), text_color=TEXT,
            ).pack(side='left', padx=12)

        # ── Buttons ────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color='transparent')
        btn_row.pack(fill='x', padx=20, pady=(14, 16))
        ctk.CTkButton(
            btn_row, text='Cancel', width=100,
            fg_color=CARD_BG, hover_color='#3a3a5e', text_color=TEXT,
            command=self.destroy,
        ).pack(side='left')
        ctk.CTkButton(
            btn_row, text='Save & Restart', width=140,
            command=self._save,
        ).pack(side='right')

    def _on_preset(self, label):
        self._refresh_custom_state(label)
        # Fill in the preset IP so the user can see it / edit it
        for lbl, ip in PRESETS:
            if lbl == label and ip:
                self._custom_var.set('')
                return

    def _refresh_custom_state(self, label):
        is_custom = (label == 'Custom')
        state = 'normal' if is_custom else 'disabled'
        self._custom_entry.configure(state=state)

    def _save(self):
        label = self._preset_var.get()
        internet_host = next((ip for lbl, ip in PRESETS if lbl == label and ip), None)
        if internet_host is None:
            internet_host = self._custom_var.get().strip() or '1.1.1.1'

        new_cfg = {
            'internet_host':    internet_host,
            'gateway_override': self._gw_var.get().strip(),
            'ping_interval':    int(self._interval_var.get()),
        }
        save_config(new_cfg)
        self._on_save(new_cfg)
        self.destroy()


# ── main window ───────────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')
        self.configure(fg_color=BG)
        self.title('HomenetMon')
        self.geometry('960x820')
        self.minsize(720, 620)

        self._cfg = load_config()
        self._resolve_hosts()

        self.monitor = PingMonitor(self.gateway, self.internet_host,
                                   interval=self._cfg['ping_interval'])
        self.monitor.start()

        self.net_poller = NetworkInfoPoller(interval=15)
        self.net_poller.start()

        self.sys_poller = SystemInfoPoller(interval=2)
        self.sys_poller.start()

        self._time_range = 120
        self._build_ui()
        self._tick()
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _resolve_hosts(self):
        override = self._cfg.get('gateway_override', '').strip()
        self.gateway       = override if override else (get_default_gateway() or '192.168.1.1')
        self.internet_host = self._cfg['internet_host']

    # ── layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0, height=48)
        header.pack(fill='x')
        header.pack_propagate(False)
        ctk.CTkLabel(header, text='HomenetMon', font=('', 17, 'bold'), text_color=TEXT).pack(side='left', padx=16)
        ctk.CTkButton(
            header, text='⚙  Settings', width=110, height=30,
            fg_color='#3a3a5e', hover_color='#4a4a7e', text_color=TEXT, font=('', 11),
            command=self._open_settings,
        ).pack(side='right', padx=12)
        self._gw_label = ctk.CTkLabel(header, text=f'Gateway  {self.gateway}',
                                      font=('', 11), text_color=TEXT_DIM)
        self._gw_label.pack(side='right', padx=4)

        # Network info bar
        info_bar = ctk.CTkFrame(self, fg_color='#222235', corner_radius=0, height=30)
        info_bar.pack(fill='x')
        info_bar.pack_propagate(False)

        self._ssid_label = ctk.CTkLabel(
            info_bar, text='WiFi  —', font=('', 11), text_color=TEXT_DIM)
        self._ssid_label.pack(side='left', padx=16)

        ctk.CTkLabel(info_bar, text='|', font=('', 11), text_color='#3a3a5e').pack(side='left')

        self._ip_label = ctk.CTkLabel(
            info_bar, text='IP  —', font=('', 11), text_color=TEXT_DIM)
        self._ip_label.pack(side='left', padx=16)

        # Stat cards
        cards_row = ctk.CTkFrame(self, fg_color='transparent')
        cards_row.pack(fill='x', padx=12, pady=(12, 6))
        cards_row.columnconfigure((0, 1, 2), weight=1)

        self.gw_card   = StatCard(cards_row, 'Default Gateway  (local network)', self.gateway)
        self.gw_card.grid(row=0, column=0, padx=6, sticky='nsew')

        self.inet_card = StatCard(cards_row, f'Internet  ({self.internet_host})', self.internet_host)
        self.inet_card.grid(row=0, column=1, padx=6, sticky='nsew')

        diag = ctk.CTkFrame(cards_row, fg_color=CARD_BG, corner_radius=10)
        diag.grid(row=0, column=2, padx=6, sticky='nsew')
        ctk.CTkLabel(diag, text='Diagnosis', font=('', 12, 'bold'), text_color=TEXT).pack(pady=(12, 4))
        self.diag_dot  = ctk.CTkLabel(diag, text='●', font=('', 28), text_color=GREY)
        self.diag_dot.pack()
        self.diag_text = ctk.CTkLabel(diag, text='Waiting for data…', font=('', 11),
                                      text_color=TEXT_DIM, wraplength=200, justify='center')
        self.diag_text.pack(pady=(4, 12))

        # System resource gauges
        gauges_row = ctk.CTkFrame(self, fg_color='transparent')
        gauges_row.pack(fill='x', padx=12, pady=(0, 6))
        gauges_row.columnconfigure((0, 1, 2), weight=1)

        def open_activity_monitor():
            subprocess.Popen(['open', '-a', 'Activity Monitor'])

        def open_disk_utility():
            subprocess.Popen(['open', '-a', 'Disk Utility'])

        self.cpu_gauge  = GaugeCard(gauges_row, 'CPU Utilisation', on_click=open_activity_monitor)
        self.cpu_gauge.grid(row=0, column=0, padx=6, sticky='nsew')

        self.mem_gauge  = GaugeCard(gauges_row, 'Memory', on_click=open_activity_monitor)
        self.mem_gauge.grid(row=0, column=1, padx=6, sticky='nsew')

        self.disk_gauge = GaugeCard(gauges_row, 'Disk  /', on_click=open_disk_utility)
        self.disk_gauge.grid(row=0, column=2, padx=6, sticky='nsew')

        # Chart panel
        chart_panel = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=10)
        chart_panel.pack(fill='both', expand=True, padx=12, pady=(0, 12))

        sel = ctk.CTkFrame(chart_panel, fg_color='transparent')
        sel.pack(fill='x', padx=14, pady=(10, 0))
        ctk.CTkLabel(sel, text='Show:', font=('', 11), text_color=TEXT_DIM).pack(side='left')
        self._range_var = ctk.StringVar(value='2 min')
        for label, secs in TIME_RANGES:
            ctk.CTkRadioButton(
                sel, text=label, variable=self._range_var, value=label,
                command=lambda s=secs: self._set_range(s),
                font=('', 11), text_color=TEXT,
            ).pack(side='left', padx=10)

        self.fig = Figure(facecolor=CARD_BG)
        self.ax  = self.fig.add_subplot(111, facecolor=CHART_BG)
        self._style_ax()
        self.fig.tight_layout(pad=1.8)

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_panel)
        self.canvas.get_tk_widget().pack(fill='both', expand=True, padx=8, pady=8)

        leg = ctk.CTkFrame(chart_panel, fg_color='transparent')
        leg.pack(pady=(0, 8))
        ctk.CTkLabel(leg, text='─── Gateway', font=('', 10), text_color=BLUE).pack(side='left', padx=10)
        self._inet_legend = ctk.CTkLabel(leg, text=f'─── Internet ({self.internet_host})',
                                         font=('', 10), text_color=GREEN)
        self._inet_legend.pack(side='left', padx=10)
        ctk.CTkLabel(leg, text='✕  Dropped packet', font=('', 10), text_color=RED).pack(side='left', padx=10)

    # ── settings ──────────────────────────────────────────────────────────────
    def _open_settings(self):
        SettingsDialog(self, self._cfg, self._apply_settings)

    def _apply_settings(self, new_cfg):
        self._cfg = new_cfg
        self.monitor.stop()
        self._resolve_hosts()
        self.monitor = PingMonitor(self.gateway, self.internet_host,
                                   interval=self._cfg['ping_interval'])
        self.monitor.start()

        self._gw_label.configure(text=f'Gateway  {self.gateway}')
        self.gw_card.set_labels('Default Gateway  (local network)', self.gateway)
        self.inet_card.set_labels(f'Internet  ({self.internet_host})', self.internet_host)
        self._inet_legend.configure(text=f'─── Internet ({self.internet_host})')

    # ── helpers ───────────────────────────────────────────────────────────────
    def _style_ax(self):
        self.ax.tick_params(colors=TEXT_DIM, labelsize=8)
        for spine in self.ax.spines.values():
            spine.set_color('#333350')
        self.ax.set_ylabel('Latency (ms)', color=TEXT_DIM, fontsize=9)
        self.ax.grid(True, color='#2a2a4a', linestyle='--', linewidth=0.5)

    def _set_range(self, secs):
        self._time_range = secs

    # ── periodic update ───────────────────────────────────────────────────────
    def _tick(self):
        gw_stats   = get_stats('gateway',  120)
        inet_stats = get_stats('internet', 120)

        latest = self.monitor.latest
        gw_current   = latest['gateway']['latency_ms']   if latest['gateway']['success']   else None
        inet_current = latest['internet']['latency_ms']  if latest['internet']['success']  else None

        self.gw_card.update(gw_current, gw_stats)
        self.inet_card.update(inet_current, inet_stats)
        color, msg = diagnosis(gw_stats, inet_stats)
        self.diag_dot.configure(text_color=color)
        self.diag_text.configure(text=msg)
        self._update_network_bar()
        self._update_gauges()
        self._redraw_chart()
        self.after(1000, self._tick)

    def _update_gauges(self):
        cpu = self.sys_poller.cpu_pct
        mem = self.sys_poller.mem_data

        self.cpu_gauge.update(
            cpu / 100,
            f'{cpu:.0f}%',
            'of all cores',
        )

        used  = mem['mem_used_gb']
        total = mem['mem_total_gb']
        self.mem_gauge.update(
            _safe_pct(used, total),
            f'{used:.1f} GB',
            f'of {total:.1f} GB installed',
        )

        disk_used  = mem['disk_used_gb']
        disk_total = mem['disk_total_gb']
        self.disk_gauge.update(
            _safe_pct(disk_used, disk_total),
            f'{disk_used:.0f} GB',
            f'of {disk_total:.0f} GB',
        )

    def _update_network_bar(self):
        ssid = self.net_poller.ssid
        ip   = self.net_poller.local_ip
        self._ssid_label.configure(text=f'WiFi  {ssid}' if ssid else 'WiFi  not connected')
        self._ip_label.configure(text=f'IP  {ip}' if ip else 'IP  unknown')

    def _redraw_chart(self):
        secs      = self._time_range
        gw_rows   = get_recent_pings('gateway',  secs)
        inet_rows = get_recent_pings('internet', secs)

        self.ax.clear()
        self._style_ax()

        for rows, color in [(gw_rows, BLUE), (inet_rows, GREEN)]:
            if not rows:
                continue
            times   = [datetime.fromtimestamp(r[0]) for r in rows]
            lats    = [r[1] for r in rows]
            success = [r[2] for r in rows]

            ok_t = [t for t, l, s in zip(times, lats, success) if s and l is not None]
            ok_l = [l for _, l, s in zip(times, lats, success) if s and l is not None]
            if ok_t:
                self.ax.plot(ok_t, ok_l, color=color, linewidth=1.5, alpha=0.9)

            drop_t = [t for t, l, s in zip(times, lats, success) if not s]
            if drop_t:
                self.ax.scatter(drop_t, [0] * len(drop_t),
                                color=RED, marker='x', s=55, zorder=5, linewidths=1.8)

        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.fig.autofmt_xdate(rotation=25)
        self.canvas.draw_idle()

    def _on_close(self):
        self.monitor.stop()
        self.net_poller.stop()
        self.sys_poller.stop()
        self.destroy()


if __name__ == '__main__':
    init_db()
    app = App()
    app.mainloop()
