# Inkbird IBBQ-4T Monitor

A small FastAPI service that polls an Inkbird IBBQ-4T over WiFi (local Tuya
protocol, no cloud) and exposes the probe temperatures via a JSON endpoint and
a minimal web dashboard.

## Endpoints

- `GET /` — live dashboard (auto-refreshing)
- `GET /api/temps` — current reading as JSON
- `GET /api/health` — service health and last error

Example `/api/temps` response:

```json
{
  "probes": [225.4, 165.2, null, null],
  "battery": 87,
  "powered_on": true,
  "unit": "F",
  "updated_at": "2026-06-29T17:00:00+00:00"
}
```

Unplugged probes return `null`.

## One-time setup: get the Tuya local key

Without this you can't talk to the device locally.

1. Pair the IBBQ-4T in the **Inkbird Pro** or **Smart Life** app so it's on
   your WiFi.
2. Create a free developer account at https://iot.tuya.com.
3. Create a Cloud Project (Smart Home category), pick the data center matching
   your region (US Central for the US).
4. Note the **Access ID** and **Access Secret** from the project Overview page.
5. Under **Devices → Link Tuya App Account**, link the same account you used
   to pair the device.
6. On your machine, run the tinytuya wizard:

   ```sh
   pip install tinytuya
   python -m tinytuya wizard
   ```

   Enter the Access ID, Access Secret, region, and a device ID when prompted.
   It writes `devices.json` containing your IBBQ-4T's `id`, `key`, `ip`, and
   `version`.

7. Also useful: `python -m tinytuya scan` to confirm the device IP and
   protocol version on your LAN.

Notes:
- The local key changes if you re-pair the device. Re-run the wizard if that
  happens.
- Set a DHCP reservation for the thermometer in your router so the IP stays
  stable.

## Running locally

```sh
cp .env.example .env
# edit .env with your real device ID, local key, IP

docker compose up --build
```

Then open http://localhost:8000.

`docker compose up -d` to run detached. `docker compose logs -f` to tail.

## Running without Docker (dev)

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env

uvicorn app.main:app --reload
```

## Project layout

```
.
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
├── .dockerignore
├── README.md
└── app/
    ├── __init__.py
    ├── config.py     # env-var loading
    ├── device.py     # tinytuya polling + DPS decoding
    └── main.py       # FastAPI app + background poll loop + dashboard
```

## Troubleshooting

- **`Bad response from device`**: device unreachable. Confirm IP, that it's
  powered on, and that nothing else is holding a Tuya connection (close the
  Inkbird Pro app on your phone).
- **`Decrypt failed`**: local key wrong or stale. Re-run
  `python -m tinytuya wizard`.
- **All probe values are `null`**: probes aren't plugged in, or the firmware
  variant detection picked the wrong decoder. Run `tinytuya scan` and check
  raw DPS — if `107` is a base64 string it's V2 firmware; if it's an integer
  it's V1. `app/device.py` autodetects based on type.
