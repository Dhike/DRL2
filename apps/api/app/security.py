import base64
import hashlib
import hmac
import secrets

_N = 2**15
_R = 8
_P = 1
_MAXMEM = 64 * 1024 * 1024


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=_MAXMEM,
        dklen=32,
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _derive(password, salt, _N, _R, _P)
    return "scrypt${}${}${}${}${}".format(
        _N,
        _R,
        _P,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = password_hash.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = _derive(password, salt, int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)
