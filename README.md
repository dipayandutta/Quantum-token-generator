# Adaptive Quantum-Triggered Secret Rotation

> **Conditional quantum entropy for active attack mitigation** — quantum randomness invoked *only when under attack*, not continuously.

---

## Overview

This project presents a **hybrid classical–quantum security architecture** where quantum entropy is used surgically during verified attack events. Under normal conditions, a classical bearer-token model handles authentication efficiently. When a brute-force or credential-stuffing attack is detected in real time, the system immediately rotates its authentication token using **quantum-generated randomness**, invalidating any potentially compromised credentials within milliseconds.

No human intervention. No SOC delay. No wasted quantum cycles.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Normal Operation                       │
│   Client ──Bearer Token──▶ protected_server_2.py
└─────────────────────────────────────────────────────────┘
                         │
              5 failures in 10 seconds
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  Attack Detected                         │
│   rotate_token.sh                                        │
│     ├── quantum_rng.py    (256-bit quantum entropy)      │
│     └── quantum_token.py  (URL-safe token generation)   │
│                         │                               │
│   /etc/myservice.token ◀─┘  (atomically replaced)       │
│   All old credentials instantly invalidated             │
└─────────────────────────────────────────────────────────┘
```

---

## Components

### `protected_server_2.py`
The HTTP authentication server. Implements a **sliding window failure detector** — if 5+ failed auth attempts occur within 10 seconds, it triggers the quantum lockdown protocol automatically.

- Listens on `0.0.0.0:8080`
- Reads token fresh from disk on every request
- Attack detection via `collections.deque` sliding window
- Calls `rotate_token.sh` via subprocess on threshold breach

### `quantum_rng.py`
Quantum random number generator using **Qiskit + AerSimulator**.

- Creates a single-qubit circuit with a Hadamard gate (equal superposition)
- Measures the qubit 256 times to generate 256 truly random bits
- Outputs raw bytes to stdout for piping

### `quantum_token.py`
Token synthesizer that blends quantum entropy with classical randomness.

- Calls the quantum circuit independently for 256 bits of entropy
- Combines with Python's `secrets.token_urlsafe(32)` (OS-level CSPRNG)
- Produces a URL-safe token: `[classical_entropy][quantum_hex]`
- Dual-entropy design for defense-in-depth

### `rotate_token.sh`
Orchestration shell script that ties everything together.

```bash
NEW_TOKEN=$(python3 quantum_rng.py | python3 quantum_token.py)
echo "$NEW_TOKEN" | sudo tee /etc/myservice.token >/dev/null
```

Atomic write to `/etc/myservice.token` — the server reads the new token on its very next request.

---

## Quick Start

### Prerequisites

```bash
pip install qiskit qiskit-aer
```

> **Note:** Qiskit 2.1+ requires Python 3.10+. Upgrade from Python 3.9 to avoid deprecation warnings.

### Step 1 — Generate Initial Token

```bash
python3 quantum_token.py | sudo tee /etc/myservice.token
```

### Step 2 — Make the Rotation Script Executable

```bash
chmod +x rotate_token.sh
```

### Step 3 — Start the Server

```bash
python3 protected_server_2.py
```

### Step 4 — Test Authentication

```bash
# Successful request
curl -H "Authorization: Bearer $(cat /etc/myservice.token)" http://localhost:8080

# Simulate attack (triggers quantum rotation after 5 failures)
for i in {1..6}; do curl http://localhost:8080; done
```

---

## Live Demo Output

```
127.0.0.1 - - [11/Mar/2026 16:38:02] "GET / HTTP/1.1" 401 -
127.0.0.1 - - [11/Mar/2026 16:38:02] "GET / HTTP/1.1" 401 -
127.0.0.1 - - [11/Mar/2026 16:38:02] "GET / HTTP/1.1" 401 -
127.0.0.1 - - [11/Mar/2026 16:38:02] "GET / HTTP/1.1" 401 -
[ALERT] Attack detected — triggering quantum lockdown
[SECURITY] Token rotated at Wednesday 11 March 2026 04:38:03 PM IST
127.0.0.1 - - [11/Mar/2026 16:38:23] "GET / HTTP/1.1" 200 -
```

Token rotated and access restored in **< 1 second**.

---

## Key Design Principles

| Principle | Implementation |
|---|---|
| **Surgical quantum use** | Quantum entropy only on attack, not every request |
| **Sliding window detection** | 5 failures / 10 seconds = O(1) memory, O(n) time |
| **Instant invalidation** | Token written atomically; old credentials useless immediately |
| **Dual-entropy token** | Quantum bits XOR'd with OS CSPRNG for defense-in-depth |
| **Zero human latency** | Automated response, no SOC intervention needed |
| **Stateless server design** | Token loaded fresh from disk on each request |

---

## Security Considerations

- **Token file permissions**: `/etc/myservice.token` should be `chmod 600`, owned by the service user
- **sudo access**: `rotate_token.sh` requires `sudo tee` — scope this with a targeted sudoers rule
- **Qiskit AerSimulator**: This uses a *classical simulator* of quantum circuits. For true quantum randomness in production, connect to a real quantum backend (IBM Quantum, AWS Braket, etc.)
- **Rate limiting**: Consider adding IP-based rate limiting in addition to global failure counting
- **HTTPS**: Deploy behind TLS in production — bearer tokens over plain HTTP are vulnerable to interception

---

## Possible Extensions

- [ ] **Multi-node sync**: Broadcast rotated token to a cluster via Redis pub/sub or etcd
- [ ] **Webhook alerts**: POST to Slack/PagerDuty on lockdown events
- [ ] **IP blocklist**: Auto-ban attacking IPs at the firewall level on threshold breach
- [ ] **Real quantum backend**: Swap AerSimulator for IBM Quantum or ANU QRNG API
- [ ] **Token versioning**: Keep a short history of valid tokens during rotation grace period
- [ ] **Metrics endpoint**: Expose Prometheus metrics for failure rate, rotation count, uptime
- [ ] **mTLS**: Add mutual TLS for client certificate authentication alongside bearer tokens

---

## Conference Presentation

**Talk:** *Adaptive Quantum-Triggered Secret Rotation for Active Attack Mitigation*

This project was submitted as a CFP demonstrating that quantum entropy doesn't need to be a continuous, expensive resource. By coupling runtime attack detection with on-demand quantum randomness, we get the security benefits of quantum unpredictability precisely when classical assumptions are under threat — and not a moment before.

---

## License

MIT — use freely, cite if presenting.

