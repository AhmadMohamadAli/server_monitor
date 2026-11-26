#!/usr/bin/env python3
"""
Lightweight Home Server Monitor (CPU, RAM, Swap, Disk, GPU, System Load, Services)
Runs on port 8088 using only Python's standard library.
"""

import http.server
import json
import os
import shutil
import socketserver
import subprocess
import time

PORT = int(os.environ.get("MONITOR_PORT", "8088"))


def get_cpu_usage():
    def read_stat():
        with open("/proc/stat", "r") as f:
            parts = f.readline().split()[1:8]
            vals = [int(x) for x in parts]
            idle = vals[3] + vals[4]
            total = sum(vals)
            return idle, total

    idle1, total1 = read_stat()
    time.sleep(0.2)
    idle2, total2 = read_stat()
    diff_total = total2 - total1
    diff_idle = idle2 - idle1
    if diff_total == 0:
        return 0.0
    return round(100.0 * (1.0 - diff_idle / diff_total), 1)


def get_memory_info():
    mem = {}
    with open("/proc/meminfo", "r") as f:
        for line in f:
            key, val = line.split(":", 1)
            mem[key.strip()] = int(val.strip().split()[0]) * 1024  # bytes

    total = mem.get("MemTotal", 0)
    avail = mem.get("MemAvailable", 0)
    used = max(0, total - avail)
    swap_total = mem.get("SwapTotal", 0)
    swap_free = mem.get("SwapFree", 0)
    swap_used = max(0, swap_total - swap_free)

    return {
        "total_gb": round(total / (1024**3), 2),
        "used_gb": round(used / (1024**3), 2),
        "percent": round((used / total) * 100, 1) if total else 0.0,
        "swap_total_gb": round(swap_total / (1024**3), 2),
        "swap_used_gb": round(swap_used / (1024**3), 2),
        "swap_percent": round((swap_used / swap_total) * 100, 1) if swap_total else 0.0,
    }


def get_disks():
    disks = []
    seen = set()
    with open("/proc/mounts", "r") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            dev, mount, fstype = parts[0], parts[1], parts[2]
            if not dev.startswith("/dev/") or "loop" in dev or mount in seen:
                continue
            seen.add(mount)
            try:
                usage = shutil.disk_usage(mount)
                disks.append({
                    "mount": mount,
                    "device": dev,
                    "total_gb": round(usage.total / (1024**3), 1),
                    "used_gb": round(usage.used / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent": round((usage.used / usage.total) * 100, 1) if usage.total else 0.0,
                })
            except PermissionError:
                continue
    return disks


def get_gpu_info():
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        if not out:
            return None
        name, util, mem_used, mem_total, temp, power = [x.strip() for x in out.split(",")]
        return {
            "name": name,
            "util_percent": float(util),
            "mem_used_mb": float(mem_used),
            "mem_total_mb": float(mem_total),
            "temp_c": float(temp),
            "power_w": power,
        }
    except Exception:
        return None


def get_uptime_and_load():
    with open("/proc/uptime", "r") as f:
        uptime_sec = int(float(f.readline().split()[0]))
    days, rem = divmod(uptime_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    load1, load5, load15 = os.getloadavg()
    return {
        "uptime": f"{days}d {hours}h {minutes}m",
        "load": [round(load1, 2), round(load5, 2), round(load15, 2)],
    }


def collect_metrics():
    return {
        "hostname": os.uname().nodename,
        "cpu_percent": get_cpu_usage(),
        "memory": get_memory_info(),
        "disks": get_disks(),
        "gpu": get_gpu_info(),
        "system": get_uptime_and_load(),
    }


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Server Monitor</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --ok: #22c55e;
      --warn: #f59e0b;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
    body { margin: 0; background: var(--bg); color: var(--text); padding: 20px; }
    header { display: flex; justify-content: space-between; align-items: center; max-width: 1100px; margin: 0 auto 20px; }
    h1 { margin: 0; font-size: 1.4rem; }
    .meta { color: var(--muted); font-size: 0.9rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; max-width: 1100px; margin: 0 auto; }
    .card { background: var(--card); border-radius: 12px; padding: 18px; box-shadow: 0 4px 12px rgba(0,0,0,0.25); }
    .card h2 { margin: 0 0 10px; font-size: 1rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .big { font-size: 2rem; font-weight: 700; margin-bottom: 8px; }
    .sub { color: var(--muted); font-size: 0.9rem; margin-bottom: 10px; }
    .bar { height: 10px; background: #334155; border-radius: 999px; overflow: hidden; }
    .fill { height: 100%; background: var(--accent); transition: width 0.3s ease; }
    .disk-row { margin-bottom: 12px; }
  </style>
</head>
<body>
  <header>
    <h1 id="hostname">Server Monitor</h1>
    <div class="meta" id="uptime">Loading...</div>
  </header>
  <div class="grid">
    <div class="card">
      <h2>CPU & Load</h2>
      <div class="big" id="cpu">--%</div>
      <div class="sub" id="load">Load: --</div>
      <div class="bar"><div class="fill" id="cpu-bar" style="width:0%"></div></div>
    </div>
    <div class="card">
      <h2>Memory (RAM)</h2>
      <div class="big" id="ram">--%</div>
      <div class="sub" id="ram-sub">-- / -- GB</div>
      <div class="bar"><div class="fill" id="ram-bar" style="width:0%"></div></div>
    </div>
    <div class="card">
      <h2>Swap</h2>
      <div class="big" id="swap">--%</div>
      <div class="sub" id="swap-sub">-- / -- GB</div>
      <div class="bar"><div class="fill" id="swap-bar" style="width:0%"></div></div>
    </div>
    <div class="card" id="gpu-card" style="display:none;">
      <h2>GPU (NVIDIA)</h2>
      <div class="big" id="gpu">--%</div>
      <div class="sub" id="gpu-sub">--</div>
      <div class="bar"><div class="fill" id="gpu-bar" style="width:0%"></div></div>
    </div>
    <div class="card" style="grid-column: 1 / -1;">
      <h2>Storage</h2>
      <div id="disks">Loading...</div>
    </div>
  </div>
  <script>
    function colorFor(pct) {
      if (pct >= 85) return 'var(--danger)';
      if (pct >= 70) return 'var(--warn)';
      return 'var(--ok)';
    }
    async function refresh() {
      try {
        const res = await fetch('/api/metrics');
        const d = await res.json();
        document.getElementById('hostname').textContent = d.hostname + ' — Server Monitor';
        document.getElementById('uptime').textContent = 'Uptime: ' + d.system.uptime;

        document.getElementById('cpu').textContent = d.cpu_percent + '%';
        document.getElementById('load').textContent = 'Load Avg: ' + d.system.load.join(', ');
        const cpuBar = document.getElementById('cpu-bar');
        cpuBar.style.width = d.cpu_percent + '%';
        cpuBar.style.background = colorFor(d.cpu_percent);

        document.getElementById('ram').textContent = d.memory.percent + '%';
        document.getElementById('ram-sub').textContent = d.memory.used_gb + ' / ' + d.memory.total_gb + ' GB';
        const ramBar = document.getElementById('ram-bar');
        ramBar.style.width = d.memory.percent + '%';
        ramBar.style.background = colorFor(d.memory.percent);

        document.getElementById('swap').textContent = d.memory.swap_percent + '%';
        document.getElementById('swap-sub').textContent = d.memory.swap_used_gb + ' / ' + d.memory.swap_total_gb + ' GB';
        const swapBar = document.getElementById('swap-bar');
        swapBar.style.width = d.memory.swap_percent + '%';
        swapBar.style.background = colorFor(d.memory.swap_percent);

        if (d.gpu) {
          document.getElementById('gpu-card').style.display = 'block';
          document.getElementById('gpu').textContent = d.gpu.util_percent + '%';
          document.getElementById('gpu-sub').textContent =
            `${d.gpu.name} | VRAM: ${d.gpu.mem_used_mb}/${d.gpu.mem_total_mb} MB | ${d.gpu.temp_c}°C | ${d.gpu.power_w}W`;
          const gpuBar = document.getElementById('gpu-bar');
          gpuBar.style.width = d.gpu.util_percent + '%';
          gpuBar.style.background = colorFor(d.gpu.util_percent);
        }

        const disksEl = document.getElementById('disks');
        disksEl.innerHTML = d.disks.map(dk => `
          <div class="disk-row">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
              <strong>${dk.mount}</strong>
              <span style="color:var(--muted)">${dk.used_gb} / ${dk.total_gb} GB (${dk.percent}%)</span>
            </div>
            <div class="bar"><div class="fill" style="width:${dk.percent}%;background:${colorFor(dk.percent)}"></div></div>
          </div>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }
    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/metrics":
            payload = json.dumps(collect_metrics()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path in ("/", "/index.html"):
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        return


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    with ThreadedHTTPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Serving on port {PORT}")
        httpd.serve_forever()
