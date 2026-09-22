"""FastAPI app exposing Inkbird IBBQ-4T probe temperatures over HTTP."""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .config import settings
from .device import Reading, read_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class State:
    last_reading: Optional[Reading] = None
    last_success_at: Optional[str] = None
    last_error: Optional[str] = None


state = State()


async def poll_loop() -> None:
    """Background task: poll the device on a fixed interval, update state."""
    while True:
        try:
            result = await asyncio.to_thread(
                read_status,
                settings.tuya_device_id,
                settings.tuya_device_ip,
                settings.tuya_local_key,
                settings.tuya_version,
            )
            state.last_reading = result
            state.last_success_at = datetime.now(timezone.utc).isoformat()
            state.last_error = None
            logger.info("poll ok: probes=%s battery=%s", result["probes"], result["battery"])
        except Exception as e:
            state.last_error = f"{type(e).__name__}: {e}"
            logger.warning("poll failed: %s", state.last_error)
        await asyncio.sleep(settings.poll_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Inkbird IBBQ-4T Monitor", lifespan=lifespan)


@app.get("/api/temps")
def get_temps() -> dict:
    if state.last_reading is None:
        raise HTTPException(status_code=503, detail="No reading available yet")
    return {**state.last_reading, "updated_at": state.last_success_at}


@app.get("/api/health")
def get_health() -> dict:
    return {
        "ok": state.last_reading is not None and state.last_error is None,
        "last_success_at": state.last_success_at,
        "last_error": state.last_error,
        "poll_interval_seconds": settings.poll_interval_seconds,
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Smoke Monitor</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body { font-family: -apple-system, sans-serif; background: #111; color: #eee;
         margin: 0; padding: 1rem; }
  h1 { font-size: 1rem; opacity: 0.6; font-weight: 400; margin: 0 0 1rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 1rem; }
  .probe { background: #1c1c1c; border-radius: 8px; padding: 1.5rem; text-align: center; }
  .probe .label { font-size: 0.85rem; opacity: 0.6; }
  .probe .temp { font-size: 3.5rem; font-weight: 200; margin: 0.5rem 0; }
  .probe .temp.off { opacity: 0.25; }
  .meta { margin-top: 1rem; opacity: 0.5; font-size: 0.8rem; }
  .err { color: #ff6b6b; }
</style>
</head>
<body>
  <h1>Inkbird IBBQ-4T</h1>
  <div class="grid" id="grid"></div>
  <div class="meta" id="meta">connecting…</div>
<script>
const grid = document.getElementById('grid');
const meta = document.getElementById('meta');

async function tick() {
  try {
    const r = await fetch('/api/temps');
    if (!r.ok) throw new Error('http ' + r.status);
    const d = await r.json();
    grid.innerHTML = d.probes.map((t, i) => `
      <div class="probe">
        <div class="label">Probe ${i + 1}</div>
        <div class="temp ${t === null ? 'off' : ''}">${t === null ? '—' : Math.round(t) + '°' + d.unit}</div>
      </div>`).join('');
    meta.textContent = `battery ${d.battery ?? '?'}% · updated ${new Date(d.updated_at).toLocaleTimeString()}`;
    meta.classList.remove('err');
  } catch (e) {
    meta.textContent = 'error: ' + e.message;
    meta.classList.add('err');
  }
}
tick();
setInterval(tick, 3000);
</script>
</body>
</html>
"""
