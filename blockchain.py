import hashlib
import time

def generate_hash(data):
    value = data + str(time.time())
    return hashlib.sha256(value.encode()).hexdigest()