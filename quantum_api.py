from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import subprocess
import time
import json
from collections import deque
from datetime import datetime

TOKEN_FILE = "/etc/myservice.token"
FAILED_WINDOW = 10       # seconds
FAILED_THRESHOLD = 5     # attempts before lockdown
BAN_DURATION = 300       # seconds an IP stays banned (5 min)

app = FastAPI(title="Quantum Adaptive Security API")

# ─────────────────────────────────────────────
# CORS — required for dashboard.html
# ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# In-memory state
# ─────────────────────────────────────────────
failures: deque = deque()           # global timestamps of failed auths
banned_ips: dict = {}               # { ip: banned_until_timestamp }
request_log: list = []              # last 50 requests for dashboard
rotation_log: list = []             # history of token rotations
stats = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "rotations": 0,
    "bans": 0,
}


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def load_token() -> str:
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except Exception as e:
        return f"error:{str(e)}"


def clean_failures():
    now = time.time()
    while failures and failures[0] < now - FAILED_WINDOW:
        failures.popleft()


def clean_bans():
    now = time.time()
    expired = [ip for ip, until in banned_ips.items() if until < now]
    for ip in expired:
        del banned_ips[ip]


def add_request_log(ip: str, code: int, msg: str):
    request_log.insert(0, {
        "time": datetime.now().strftime("%H:%M:%S"),
        "ip": ip,
        "code": code,
        "msg": msg,
    })
    if len(request_log) > 50:
        request_log.pop()


def ban_ip(ip: str):
    banned_ips[ip] = time.time() + BAN_DURATION
    stats["bans"] += 1
    rotation_log.insert(0, {
        "time": datetime.now().strftime("%H:%M:%S"),
        "event": f"IP BANNED: {ip} for {BAN_DURATION}s",
        "type": "ban",
    })


# ─────────────────────────────────────────────
# IP Ban middleware — checked on EVERY request
# ─────────────────────────────────────────────
@app.middleware("http")
async def ip_ban_middleware(request: Request, call_next):
    clean_bans()
    client_ip = request.client.host

    if client_ip in banned_ips:
        remaining = int(banned_ips[client_ip] - time.time())
        add_request_log(client_ip, 403, f"BANNED — {remaining}s remaining")
        return JSONResponse(
            status_code=403,
            content={"detail": "IP banned", "retry_after": remaining}
        )

    return await call_next(request)


# ─────────────────────────────────────────────
# Root
# ─────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "Quantum Adaptive Security API",
        "status": "running",
        "version": "2.0",
    }


# ─────────────────────────────────────────────
# GET /status — full dashboard snapshot
# ─────────────────────────────────────────────
@app.get("/status")
def get_status():
    clean_failures()
    clean_bans()
    token = load_token()

    return {
        "token": token,
        "token_preview": token[:12] + "..." + token[-8:] if len(token) > 20 else token,
        "failures_in_window": len(failures),
        "threshold": FAILED_THRESHOLD,
        "window_secs": FAILED_WINDOW,
        "stats": stats,
        "banned_ips": {
            ip: {"banned_until": until, "remaining_secs": max(0, int(until - time.time()))}
            for ip, until in banned_ips.items()
        },
        "request_log": request_log[:20],
        "rotation_log": rotation_log[:10],
        "server_time": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────
# POST /auth — simulate auth attempt
# ─────────────────────────────────────────────
@app.post("/auth")
async def auth_attempt(request: Request):
    client_ip = request.client.host
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    provided_token = body.get("token", "")

    stats["total"] += 1
    clean_failures()

    real_token = load_token()

    if provided_token == real_token:
        stats["success"] += 1
        add_request_log(client_ip, 200, "Auth success")
        return {"status": 200, "message": "Access granted"}

    # — Failed auth —
    stats["failed"] += 1
    failures.append(time.time())
    add_request_log(client_ip, 401, "Bad token")

    clean_failures()
    fail_count = len(failures)

    # Check lockdown threshold
    if fail_count >= FAILED_THRESHOLD:
        # Rotate token
        rotation_log.insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "event": f"QUANTUM LOCKDOWN triggered by {client_ip} ({fail_count} failures)",
            "type": "rotation",
        })
        try:
            subprocess.run(["bash", "./rotate_token.sh"], check=True)
            stats["rotations"] += 1
            failures.clear()
            rotation_log[0]["event"] += " — token rotated OK"
        except Exception as e:
            rotation_log[0]["event"] += f" — rotation FAILED: {e}"

        # Ban the offending IP
        ban_ip(client_ip)

        return JSONResponse(
            status_code=401,
            content={
                "status": 401,
                "message": "Unauthorized — quantum lockdown triggered, IP banned",
                "failures": fail_count,
            }
        )

    return JSONResponse(
        status_code=401,
        content={
            "status": 401,
            "message": "Unauthorized",
            "failures_in_window": fail_count,
            "threshold": FAILED_THRESHOLD,
        }
    )


# ─────────────────────────────────────────────
# POST /rotate — manual token rotation
# ─────────────────────────────────────────────
@app.post("/rotate")
def rotate_token():
    try:
        subprocess.run(["bash", "./rotate_token.sh"], check=True)
        stats["rotations"] += 1
        rotation_log.insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "event": "MANUAL rotation by operator",
            "type": "manual",
        })
        return {"status": "token rotated successfully", "time": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "rotation failed", "error": str(e)}


# ─────────────────────────────────────────────
# POST /unban — remove an IP from ban list
# ─────────────────────────────────────────────
@app.post("/unban")
async def unban_ip(request: Request):
    body = await request.json()
    ip = body.get("ip", "")
    if ip in banned_ips:
        del banned_ips[ip]
        rotation_log.insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "event": f"IP UNBANNED: {ip} by operator",
            "type": "unban",
        })
        return {"status": "unbanned", "ip": ip}
    return {"status": "ip not in ban list", "ip": ip}


# ─────────────────────────────────────────────
# GET /banned — list all banned IPs
# ─────────────────────────────────────────────
@app.get("/banned")
def list_banned():
    clean_bans()
    return {
        "banned": {
            ip: {
                "remaining_secs": max(0, int(until - time.time())),
                "banned_until": datetime.fromtimestamp(until).strftime("%H:%M:%S"),
            }
            for ip, until in banned_ips.items()
        },
        "count": len(banned_ips),
    }


# ─────────────────────────────────────────────
# POST /run-shor — Shor's algorithm demo
# ─────────────────────────────────────────────
@app.post("/run-shor")
def run_shor():
    try:
        # NOTE: Shor via qiskit.algorithms is deprecated in newer Qiskit.
        # This uses qiskit_algorithms (the maintained fork).
        from qiskit_algorithms import Shor
        from qiskit_aer import AerSimulator
        from qiskit.primitives import Sampler

        backend = AerSimulator()
        shor = Shor(sampler=Sampler())
        result = shor.factor(15)

        return {
            "number": 15,
            "factors": result.factors,
            "note": "Quantum Shor factoring via AerSimulator",
        }
    except ImportError:
        # Fallback — classical factoring for demo if qiskit_algorithms not installed
        return {
            "number": 15,
            "factors": [[3, 5]],
            "note": "Classical fallback — install qiskit-algorithms for real Shor",
        }
    except Exception as e:
        return {"number": 15, "error": str(e)}


# ─────────────────────────────────────────────
# Run: uvicorn quantum_api:app --host 0.0.0.0 --port 8000 --reload
# ─────────────────────────────────────────────
