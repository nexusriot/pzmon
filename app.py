from flask import Flask, jsonify, render_template_string
import os
import time
import shutil
import subprocess
import re

try:
    import psutil
except Exception:
    psutil = None

app = Flask(__name__)
START_TIME = time.time()

# TODO: move to template
HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pi Monitor</title>
  <style>
    :root{
      --bg:#0b0f14; --card:#121826; --text:#e6edf3; --muted:#9aa4b2;
      --border:#1f2a3a; --accent:#2dd4bf;
    }
    body { margin: 18px; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background: var(--bg); color: var(--text); }
    h2 { margin: 0 0 6px 0; }
    .muted { color: var(--muted); margin: 0 0 14px 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
    .card { background: var(--card); padding: 14px; border: 1px solid var(--border); border-radius: 14px; }
    code { background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 10px; }
    .kvs b { display:inline-block; min-width: 110px; color: var(--muted); font-weight: 600; }
    canvas { width: 100%; height: 120px; border-radius: 12px; border: 1px solid var(--border); background: rgba(255,255,255,0.03); }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 6px 4px; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 13px; }
    th { color: var(--muted); font-weight: 700; }
    .pill { display:inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--border); color: var(--muted); }
  </style>
</head>
<body>
  <h2>PZMon</h2>
  <p class="muted">Auto-refresh every 2s · graphs keep last ~2 minutes</p>

  <div class="grid">
    <div class="card">
      <h3>System</h3>
      <div class="kvs" id="sys">Loading…</div>
    </div>

    <div class="card">
      <h3>Wi-Fi</h3>
      <div class="kvs" id="wifi">Loading…</div>
      <div style="margin-top:10px">
        <div class="pill">Signal history</div>
        <canvas id="wifiChart" width="600" height="180"></canvas>
      </div>
    </div>

    <div class="card">
      <h3>CPU</h3>
      <div class="kvs" id="cpu">Loading…</div>
      <div style="margin-top:10px">
        <div class="pill">CPU % history</div>
        <canvas id="cpuChart" width="600" height="180"></canvas>
      </div>
    </div>

    <div class="card">
      <h3>Memory</h3>
      <div class="kvs" id="mem">Loading…</div>
      <div style="margin-top:10px">
        <div class="pill">RAM % history</div>
        <canvas id="memChart" width="600" height="180"></canvas>
      </div>
    </div>

    <div class="card" style="grid-column: 1 / -1;">
      <h3>Top processes (CPU)</h3>
      <div id="procs">Loading…</div>
    </div>
  </div>

<script>
const HISTORY_LEN = 60; // points; 60 points * 2s = 120s history
const cpuHist = [];
const memHist = [];
const wifiHist = [];

function fmtBytes(n) {
  if (n === null || n === undefined) return "-";
  const u = ["B","KB","MB","GB","TB"];
  let i = 0; let x = n;
  while (x >= 1024 && i < u.length-1) { x /= 1024; i++; }
  return `${x.toFixed(1)} ${u[i]}`;
}

function pushHist(arr, v) {
  if (v === null || v === undefined || Number.isNaN(v)) return;
  arr.push(v);
  while (arr.length > HISTORY_LEN) arr.shift();
}

function drawLineChart(canvasId, data, minY=0, maxY=100) {
  const c = document.getElementById(canvasId);
  const ctx = c.getContext("2d");
  const w = c.width, h = c.height;

  // clear
  ctx.clearRect(0,0,w,h);

  // grid
  ctx.globalAlpha = 0.6;
  ctx.strokeStyle = "rgba(255,255,255,0.12)";
  ctx.lineWidth = 1;
  for (let i=1;i<=4;i++){
    const y = (h*i)/5;
    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke();
  }
  ctx.globalAlpha = 1.0;

  if (!data.length) return;

  const pad = 10;
  const x0 = pad, y0 = pad, x1 = w-pad, y1 = h-pad;
  const dx = (x1-x0) / Math.max(1, (HISTORY_LEN-1));

  ctx.strokeStyle = "rgba(45,212,191,0.9)";
  ctx.lineWidth = 2;

  ctx.beginPath();
  for (let i=0;i<data.length;i++){
    const v = data[i];
    const t = Math.min(1, Math.max(0, (v - minY) / (maxY - minY)));
    const x = x0 + i*dx;
    const y = y1 - t*(y1-y0);
    if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
  }
  ctx.stroke();
}

async function refresh() {
  const s = await fetch('/api/status').then(r => r.json());

  document.getElementById('sys').innerHTML =
    `<b>IP</b> <code>${s.ip}</code><br>` +
    `<b>Hostname</b> ${s.hostname}<br>` +
    `<b>Uptime</b> ${s.uptime_seconds}s<br>` +
    `<b>CPU temp</b> ${(s.cpu_temp_c ?? "-")} °C<br>` +
    `<b>Load</b> ${s.load1} / ${s.load5} / ${s.load15}<br>`;

  document.getElementById('cpu').innerHTML =
    `<b>CPU usage</b> ${(s.cpu_usage_percent ?? "-")} %<br>`;

  document.getElementById('mem').innerHTML =
    `<b>RAM</b> ${fmtBytes(s.mem_used)} / ${fmtBytes(s.mem_total)} (${s.mem_percent ?? "-"}%)<br>` +
    `<b>Disk /</b> ${fmtBytes(s.disk_used)} / ${fmtBytes(s.disk_total)} (${s.disk_percent ?? "-"}%)<br>`;

  const wifiLine = (s.wifi_signal_dbm !== null && s.wifi_signal_dbm !== undefined)
    ? `${s.wifi_signal_dbm} dBm (${s.wifi_signal_percent ?? "-"}%)`
    : "-";
  document.getElementById('wifi').innerHTML =
    `<b>Interface</b> ${s.wifi_iface || "wlan0"}<br>` +
    `<b>Signal</b> ${wifiLine}<br>`;

  // process table
  const rows = (s.top_processes || []).map(p =>
    `<tr><td>${p.pid}</td><td>${p.name}</td><td>${p.cpu}%</td><td>${fmtBytes(p.rss)}</td></tr>`
  ).join("");
  document.getElementById('procs').innerHTML =
    `<table><thead><tr><th>PID</th><th>Name</th><th>CPU</th><th>RSS</th></tr></thead><tbody>${rows}</tbody></table>`;

  // history + charts
  pushHist(cpuHist, s.cpu_usage_percent);
  pushHist(memHist, s.mem_percent);
  pushHist(wifiHist, s.wifi_signal_percent);

  drawLineChart("cpuChart", cpuHist, 0, 100);
  drawLineChart("memChart", memHist, 0, 100);
  drawLineChart("wifiChart", wifiHist, 0, 100);
}

refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""

def _run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None

def get_ip():
    out = _run(["hostname", "-I"])
    if not out:
        return "unknown"
    parts = out.split()
    return parts[0] if parts else "unknown"

def get_cpu_temp_c():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        return None

def wifi_signal_dbm(iface="wlan0"):
    """
    Returns RSSI in dBm as int, or None if unavailable.
    Uses: iw dev wlan0 link  -> "signal: -47 dBm"
    """
    out = _run(["iw", "dev", iface, "link"])
    if not out:
        return None
    m = re.search(r"signal:\s*(-?\d+)\s*dBm", out)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

def dbm_to_percent(dbm):
    if dbm is None:
        return None
    if dbm <= -100:
        return 0
    if dbm >= -50:
        return 100
    return int(round(2 * (dbm + 100)))  # linear between -100..-50

def top_processes(limit=10):
    if not psutil:
        return []
    procs = []
    for p in psutil.process_iter(attrs=["pid", "name"]):
        try:
            p.cpu_percent(None)
        except Exception:
            pass
    time.sleep(0.05)
    for p in psutil.process_iter(attrs=["pid", "name", "memory_info"]):
        try:
            cpu = p.cpu_percent(None)
            rss = getattr(p.info.get("memory_info"), "rss", 0) if p.info.get("memory_info") else 0
            procs.append({"pid": p.info["pid"], "name": p.info.get("name") or "?", "cpu": round(cpu, 1), "rss": int(rss)})
        except Exception:
            continue
    procs.sort(key=lambda x: x["cpu"], reverse=True)
    return procs[:limit]

@app.get("/")
def index():
    return render_template_string(HTML)

@app.get("/api/status")
def status():
    uptime = int(time.time() - START_TIME)
    load1, load5, load15 = os.getloadavg()

    hostname = _run(["hostname"]) or "unknown"
    ip = get_ip()
    cpu_temp = get_cpu_temp_c()

    du = shutil.disk_usage("/")
    disk_total, disk_used = du.total, du.used
    disk_percent = round((disk_used / disk_total) * 100, 1) if disk_total else None

    iface = os.environ.get("WIFI_IFACE", "wlan0")
    sig_dbm = wifi_signal_dbm(iface)
    sig_pct = dbm_to_percent(sig_dbm)

    result = {
        "hostname": hostname,
        "ip": ip,
        "uptime_seconds": uptime,
        "cpu_temp_c": cpu_temp,
        "load1": round(load1, 2),
        "load5": round(load5, 2),
        "load15": round(load15, 2),
        "disk_total": int(disk_total),
        "disk_used": int(disk_used),
        "disk_percent": disk_percent,
        "wifi_iface": iface,
        "wifi_signal_dbm": sig_dbm,
        "wifi_signal_percent": sig_pct,
        "cpu_usage_percent": None,
        "mem_total": None,
        "mem_used": None,
        "mem_percent": None,
        "top_processes": [],
    }

    if psutil:
        try:
            result["cpu_usage_percent"] = round(psutil.cpu_percent(interval=0.0), 1)
        except Exception:
            pass
        try:
            vm = psutil.virtual_memory()
            result["mem_total"] = int(vm.total)
            result["mem_used"] = int(vm.used)
            result["mem_percent"] = round(vm.percent, 1)
        except Exception:
            pass
        result["top_processes"] = top_processes()

    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=18080, debug=False, use_reloader=False)
