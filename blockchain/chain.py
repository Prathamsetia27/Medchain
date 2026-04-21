# ============================================================
# blockchain/chain.py
# Simulates blockchain hashing for medical record integrity.
# Each record gets a SHA-256 hash linking to the previous hash,
# creating an immutable chain. Any tamper attempt changes the
# hash, which is then detected during verification.
# ============================================================

import hashlib
import json
import time


def generate_record_hash(record_data: dict, previous_hash: str = "0" * 64) -> str:
    """
    Generate SHA-256 hash for a medical record block.
    
    The hash is computed from:
      - The record data (patient id, symptoms, disease, timestamp)
      - The previous block's hash (creates the chain)
    
    This means ANY change to the record_data will produce a 
    completely different hash → tamper detected.
    """
    block_content = {
        "data": record_data,
        "previous_hash": previous_hash,
        "timestamp": record_data.get("timestamp", str(time.time()))
    }
    # Serialize deterministically (sort_keys ensures consistent ordering)
    block_string = json.dumps(block_content, sort_keys=True)
    
    # SHA-256 produces a 64-character hex digest
    return hashlib.sha256(block_string.encode()).hexdigest()


def verify_record_integrity(record_data: dict, stored_hash: str, previous_hash: str = "0" * 64) -> bool:
    """
    Recompute the hash from the current record_data and compare
    with the stored_hash. If they match → record is intact.
    If they differ → record was tampered with.
    """
    computed = generate_record_hash(record_data, previous_hash)
    return computed == stored_hash


def build_genesis_hash() -> str:
    """
    The genesis hash is the first block in the chain.
    It has no previous block, so previous_hash is all zeros.
    This is the 'anchor' of trust in the chain.
    """
    genesis_data = {"block": "GENESIS", "system": "AAROGYA_AI", "timestamp": "2024-01-01T00:00:00"}
    return generate_record_hash(genesis_data, "0" * 64)