#!/bin/bash
set -e

NEW_TOKEN=$(python3 quantum_rng.py | python3 quantum_token.py)

echo "$NEW_TOKEN" | sudo tee /etc/myservice.token >/dev/null
echo "[SECURITY] Token rotated at $(date)"
