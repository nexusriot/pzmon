# PZMon

Tiny Raspberry Pi / Linux host monitor with a simple Flask dashboard.

## What it shows

- hostname and IP
- system uptime
- CPU temperature
- load average
- CPU / memory / disk usage
- Wi-Fi signal strength
- top processes by CPU

## Run with Docker Compose

```bash
docker compose up --build -d
```

Then open:

- `http://<host-ip>:18080`

## Configuration

Environment variables:

- `WIFI_IFACE` — Wi-Fi interface name, default `wlan0`
- `STATUS_CACHE_TTL` — API cache duration in seconds, default `2.0`

## Security notes

This app is intentionally small and has **no built-in authentication**.

If you expose it beyond a trusted local network, put it behind a reverse proxy and/or firewall rules.

The provided compose file uses host networking for convenience on small self-hosted systems.
Review that choice before exposing the service.
