"""Encrypted, write-once local object storage behind a small adapter interface."""

import os
from pathlib import Path, PurePosixPath
from secrets import token_bytes

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class StorageUnavailable(Exception):
    pass


class LocalObjectStorage:
    def __init__(self, root: Path, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES-256-GCM requires a 32-byte key")
        self._root = root.resolve()
        self._cipher = AESGCM(key)
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _path(self, object_key: str) -> Path:
        key = PurePosixPath(object_key)
        if key.is_absolute() or not key.parts or any(part in {".", ".."} for part in key.parts):
            raise ValueError("Invalid object key")
        path = self._root.joinpath(*key.parts)
        if not path.resolve().is_relative_to(self._root):
            raise ValueError("Invalid object key")
        return path

    def write_once(self, object_key: str, payload: bytes) -> None:
        path = self._path(object_key)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        nonce = token_bytes(12)
        sealed = nonce + self._cipher.encrypt(nonce, payload, object_key.encode("utf-8"))
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(sealed)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def read(self, object_key: str) -> bytes:
        sealed = self._path(object_key).read_bytes()
        return self._cipher.decrypt(sealed[:12], sealed[12:], object_key.encode("utf-8"))


def storage_from_settings(settings) -> LocalObjectStorage:
    if settings.storage_encryption_key is None:
        raise StorageUnavailable("Storage encryption key is not configured")
    return LocalObjectStorage(
        settings.storage_root,
        settings.storage_encryption_key.get_secret_value().encode("utf-8"),
    )
