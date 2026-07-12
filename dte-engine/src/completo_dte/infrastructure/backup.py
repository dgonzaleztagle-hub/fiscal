"""Respaldo verificable del adaptador SQLite local."""

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupManifest:
    database_sha256: str
    database_size: int
    created_at: str
    integrity: str

    def to_json(self) -> bytes:
        return (json.dumps(self.__dict__, sort_keys=True, indent=2) + "\n").encode()


class SqliteBackupService:
    def backup(self, source: str | Path, destination: str | Path) -> BackupManifest:
        source = Path(source)
        destination = Path(destination)
        if not source.is_file() or destination.exists():
            raise BackupError("Origen inexistente o destino de respaldo ya ocupado")
        source_connection = sqlite3.connect(source)
        destination_connection = sqlite3.connect(destination)
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
            source_connection.close()
        integrity = self._integrity(destination)
        if integrity != "ok":
            destination.unlink(missing_ok=True)
            raise BackupError("El respaldo no superó PRAGMA integrity_check")
        payload = destination.read_bytes()
        return BackupManifest(
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            integrity,
        )

    def restore(
        self,
        backup: str | Path,
        target: str | Path,
        manifest: BackupManifest,
    ) -> None:
        backup = Path(backup)
        target = Path(target)
        if not backup.is_file() or target.exists():
            raise BackupError("Respaldo inexistente o destino de restauración ocupado")
        payload = backup.read_bytes()
        if (
            len(payload) != manifest.database_size
            or hashlib.sha256(payload).hexdigest() != manifest.database_sha256
        ):
            raise BackupError("El respaldo no coincide con su manifiesto")
        source_connection = sqlite3.connect(backup)
        target_connection = sqlite3.connect(target)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()
        if self._integrity(target) != "ok":
            target.unlink(missing_ok=True)
            raise BackupError("La base restaurada no superó integrity_check")

    @staticmethod
    def _integrity(database: Path) -> str:
        connection = sqlite3.connect(database)
        try:
            return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        finally:
            connection.close()
