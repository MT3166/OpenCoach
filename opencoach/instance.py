from hashlib import sha256

def cookie_names(secret):
    instance = sha256(secret.encode()).hexdigest()[:12]
    return f'oc_session_{instance}', f'oc_csrf_{instance}'
