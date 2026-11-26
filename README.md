# Home Server Monitor

A zero-dependency, lightweight web dashboard written in pure Python to monitor a Linux home server (CPU, RAM, Swap, Disk mounts, Uptime, Load Average, and NVIDIA GPU metrics via `nvidia-smi`).

Designed for home servers running **Immich**, **Jellyfin**, and local media/backup services.

## Features

- **Zero external dependencies:** Uses only Python 3 standard library (`http.server`, `/proc`, `shutil`).
- **Real-time Web UI:** Auto-refreshes every 3 seconds on port `8088`.
- **NVIDIA GPU Support:** Automatically detects `nvidia-smi` (e.g., GTX 1650 / RTX 3050) to display GPU load, VRAM usage, temperature, and power draw.
- **Systemd Ready:** Includes a `systemd` unit file to run reliably in the background.

## Project Structure

```text
server-monitor/
├── server.py                 # Main HTTP server & /proc metrics collector
├── server-monitor.service    # Systemd service unit file
└── README.md                 # Documentation
```

## Quick Start

### 1. Install on your Linux server

```bash
sudo mkdir -p /opt/server-monitor
sudo cp server.py /opt/server-monitor/
sudo chmod +x /opt/server-monitor/server.py
```

### 2. Run manually (for testing)

```bash
python3 /opt/server-monitor/server.py
```

Open `http://<SERVER_IP>:8088` in your browser.

### 3. Run as a background `systemd` service

```bash
sudo cp server-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now server-monitor
```

### 4. Firewall (UFW) — Allow local network only

```bash
sudo ufw allow from 192.168.0.0/24 to any port 8088 proto tcp
```

## Stop or Disable

```bash
sudo systemctl stop server-monitor && sudo systemctl disable server-monitor
```
