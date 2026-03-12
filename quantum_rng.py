from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
import sys

def quantum_random_bits(n_bits=256):
    qc = QuantumCircuit(1, 1)
    qc.h(0)
    qc.measure(0, 0)

    backend = AerSimulator()
    bits = []

    for _ in range(n_bits):
        job = backend.run(qc, shots=1)
        result = job.result()
        bit = list(result.get_counts().keys())[0]
        bits.append(bit)

    return "".join(bits)

if __name__ == "__main__":
    bits = quantum_random_bits(256)
    # Convert bits to bytes and write to stdout
    b = int(bits, 2).to_bytes(len(bits) // 8, byteorder="big")
    sys.stdout.buffer.write(b)
