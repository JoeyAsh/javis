"""Backup and rotation utilities for JARVIS memory database.

Provides:
- Daily gzipped backups of the SQLite database
- Automatic rotation with configurable retention period
"""

from __future__ import annotations

import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("memory_backup")


async def create_backup(db_path: str, backup_dir: str) -> str:
    """Create a gzipped backup of the database.

    Creates a backup file named jarvis-YYYY-MM-DD.db.gz in the backup
    directory. If a backup for today already exists, it will be overwritten.

    Args:
        db_path: Path to source database file.
        backup_dir: Directory for backup files.

    Returns:
        Path to the created backup file.

    Raises:
        FileNotFoundError: If source database doesn't exist.
        OSError: If backup directory can't be created or written to.
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    backup_file = backup_path / f"jarvis-{date_str}.db.gz"

    logger.info(f"Creating backup: {backup_file}")

    # Compress database to gzip
    with open(db_file, "rb") as f_in:
        with gzip.open(backup_file, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)

    backup_size = backup_file.stat().st_size
    original_size = db_file.stat().st_size
    ratio = (1 - backup_size / original_size) * 100 if original_size > 0 else 0

    logger.info(
        f"Backup created: {backup_file.name} "
        f"({backup_size:,} bytes, {ratio:.1f}% compression)"
    )

    return str(backup_file)


async def rotate_backups(backup_dir: str, keep_days: int = 14) -> int:
    """Delete backups older than keep_days.

    Scans the backup directory for files matching the pattern
    jarvis-YYYY-MM-DD.db.gz and deletes those older than the
    retention period.

    Args:
        backup_dir: Directory containing backup files.
        keep_days: Number of days to retain backups (default: 14).

    Returns:
        Number of deleted backup files.
    """
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        logger.debug(f"Backup directory doesn't exist: {backup_dir}")
        return 0

    cutoff = datetime.now() - timedelta(days=keep_days)
    deleted = 0

    for backup_file in backup_path.glob("jarvis-*.db.gz"):
        try:
            # Extract date from filename: jarvis-YYYY-MM-DD.db.gz
            date_str = backup_file.stem.replace("jarvis-", "").replace(".db", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")

            if file_date < cutoff:
                backup_file.unlink()
                deleted += 1
                logger.debug(f"Deleted old backup: {backup_file.name}")

        except ValueError:
            # Skip files that don't match expected pattern
            logger.warning(f"Skipping unrecognized backup file: {backup_file.name}")
            continue

    if deleted > 0:
        logger.info(f"Rotated {deleted} old backup(s) (keeping {keep_days} days)")

    return deleted


async def restore_backup(backup_file: str, db_path: str) -> None:
    """Restore database from a gzipped backup.

    Args:
        backup_file: Path to the .db.gz backup file.
        db_path: Destination path for restored database.

    Raises:
        FileNotFoundError: If backup file doesn't exist.
        gzip.BadGzipFile: If backup file is corrupted.
    """
    backup_path = Path(backup_file)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_file}")

    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Restoring backup: {backup_file} -> {db_path}")

    with gzip.open(backup_path, "rb") as f_in:
        with open(db_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    logger.info(f"Database restored: {db_file.stat().st_size:,} bytes")


async def list_backups(backup_dir: str) -> list[dict[str, str | int]]:
    """List available backups with metadata.

    Args:
        backup_dir: Directory containing backup files.

    Returns:
        List of backup info dicts with 'path', 'date', and 'size' keys,
        sorted by date descending (newest first).
    """
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        return []

    backups = []

    for backup_file in backup_path.glob("jarvis-*.db.gz"):
        try:
            date_str = backup_file.stem.replace("jarvis-", "").replace(".db", "")
            datetime.strptime(date_str, "%Y-%m-%d")  # Validate date format

            backups.append({
                "path": str(backup_file),
                "date": date_str,
                "size": backup_file.stat().st_size,
            })
        except ValueError:
            continue

    # Sort by date descending
    backups.sort(key=lambda x: x["date"], reverse=True)

    return backups
