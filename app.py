from flask import Flask, jsonify, render_template
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

STATUS_CACHE_TTL = float(os.environ.get("STATUS_CACHE_TTL", "2.0"))
_STATUS_CACHE = {"ts": 0.0, "data": None}


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
    return int(round(2 * (dbm + 100)))


def system_uptime_seconds():
    if psutil:
        try:
            return int(time.time() - psutil.boot_time())
        except Exception:
            pass
    try:
        with open("/proc/uptime", "r") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return None


def top_processes(limit=10):
    if not psutil:
        return []

    procs = []
    for p in psutil.process_iter(attrs=["pid", "name", "memory_info"]):
        try:
            cpu = p.cpu_percent(interval=None)
            rss = getattr(p.info.get("memory_info"), "rss", 0) if p.info.get("memory_info") else 0
            procs.append(
                {
                    "pid": p.info["pid"],
                    "name": p.info.get("name") or "?",
                    "cpu": round(cpu, 1),
                    "rss": int(rss),
                }
            )
        except Exception:
            continue
    procs.sort(key=lambda x: x["cpu"], reverse=True)
    return procs[:limit]


def build_status():
    load1, load5, load15 = os.getloadavg()

    hostname = _run(["hostname"]) or "unknown"
    ip = get_ip()
    cpu_temp = get_cpu_temp_c()
    uptime = system_uptime_seconds()

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

    return result


def get_cached_status():
    now = time.time()
    if _STATUS_CACHE["data"] is not None and now - _STATUS_CACHE["ts"] < STATUS_CACHE_TTL:
        return _STATUS_CACHE["data"]

    data = build_status()
    _STATUS_CACHE["ts"] = now
    _STATUS_CACHE["data"] = data
    return data


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify(get_cached_status())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=18080, debug=False, use_reloader=False)
