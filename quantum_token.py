# quantum_token.py
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
import secrets

def quantum_entropy(n_bits=256):
    qc = QuantumCircuit(1, 1)
    qc.h(0)
    qc.measure(0, 0)

    backend = AerSimulator()
    bits = []

    for _ in range(n_bits):
        job = backend.run(qc, shots=1)
        bit = list(job.result().get_counts().keys())[0]
        bits.append(bit)

    return int("".join(bits), 2).to_bytes(n_bits // 8, "big")

# Create a URL-safe token
entropy = quantum_entropy()
token = secrets.token_urlsafe(32) + entropy.hex()[:32]

print(token)
