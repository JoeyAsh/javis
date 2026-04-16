"""Unit tests for memory database backup functionality.

Tests cover:
- Backup creation with gzip compression
- Backup rotation with configurable retention
- Backup restoration
- Listing available backups
"""

import gzip
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from brain.memory.backup import (
    create_backup,
    list_backups,
    restore_backup,
    rotate_backups,
)


@pytest.fixture
def temp_dirs():
    """Provide temporary directories for database and backups."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / "data"
        backup_dir = Path(tmpdir) / "backups"
        db_dir.mkdir()
        yield {
            "db_path": str(db_dir / "jarvis.db"),
            "backup_dir": str(backup_dir),
        }


@pytest.fixture
def sample_db(temp_dirs):
    """Create a sample database file for testing."""
    db_path = temp_dirs["db_path"]
    # Create a simple file with some content
    Path(db_path).write_bytes(b"SQLite database content " * 100)
    return db_path


class TestCreateBackup:
    """Tests for create_backup function."""

    @pytest.mark.asyncio
    async def test_creates_gzipped_backup(self, sample_db, temp_dirs):
        """Test that create_backup creates a gzipped file."""
        backup_path = await create_backup(sample_db, temp_dirs["backup_dir"])

        assert Path(backup_path).exists()
        assert backup_path.endswith(".db.gz")

    @pytest.mark.asyncio
    async def test_backup_filename_contains_date(self, sample_db, temp_dirs):
        """Test that backup filename contains current date."""
        backup_path = await create_backup(sample_db, temp_dirs["backup_dir"])

        today = datetime.now().strftime("%Y-%m-%d")
        assert today in backup_path

    @pytest.mark.asyncio
    async def test_backup_is_valid_gzip(self, sample_db, temp_dirs):
        """Test that backup file is valid gzip."""
        backup_path = await create_backup(sample_db, temp_dirs["backup_dir"])

        # Should not raise
        with gzip.open(backup_path, "rb") as f:
            content = f.read()

        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_backup_creates_directory(self, sample_db, temp_dirs):
        """Test that create_backup creates backup directory if needed."""
        nested_backup_dir = str(Path(temp_dirs["backup_dir"]) / "nested" / "dir")

        backup_path = await create_backup(sample_db, nested_backup_dir)

        assert Path(backup_path).exists()

    @pytest.mark.asyncio
    async def test_backup_raises_for_missing_db(self, temp_dirs):
        """Test that create_backup raises for missing database."""
        with pytest.raises(FileNotFoundError):
            await create_backup("/nonexistent/db.sqlite", temp_dirs["backup_dir"])

    @pytest.mark.asyncio
    async def test_backup_overwrites_existing_same_day(self, sample_db, temp_dirs):
        """Test that backup for same day overwrites existing."""
        backup1 = await create_backup(sample_db, temp_dirs["backup_dir"])

        # Modify original and backup again
        Path(sample_db).write_bytes(b"Modified content " * 200)
        backup2 = await create_backup(sample_db, temp_dirs["backup_dir"])

        assert backup1 == backup2  # Same path

        # Verify content was updated
        with gzip.open(backup2, "rb") as f:
            content = f.read()
        assert b"Modified content" in content


class TestRotateBackups:
    """Tests for rotate_backups function."""

    @pytest.mark.asyncio
    async def test_deletes_old_backups(self, temp_dirs):
        """Test that old backups are deleted."""
        backup_dir = Path(temp_dirs["backup_dir"])
        backup_dir.mkdir(parents=True)

        # Create backups with dates
        dates = [
            datetime.now() - timedelta(days=20),  # Should be deleted
            datetime.now() - timedelta(days=15),  # Should be deleted
            datetime.now() - timedelta(days=10),  # Should be kept
            datetime.now() - timedelta(days=5),   # Should be kept
        ]

        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            backup_file = backup_dir / f"jarvis-{date_str}.db.gz"
            backup_file.write_bytes(b"backup content")

        deleted = await rotate_backups(str(backup_dir), keep_days=14)

        assert deleted == 2
        assert len(list(backup_dir.glob("jarvis-*.db.gz"))) == 2

    @pytest.mark.asyncio
    async def test_keeps_recent_backups(self, temp_dirs):
        """Test that recent backups are kept."""
        backup_dir = Path(temp_dirs["backup_dir"])
        backup_dir.mkdir(parents=True)

        # Create recent backups
        for i in range(5):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            backup_file = backup_dir / f"jarvis-{date_str}.db.gz"
            backup_file.write_bytes(b"backup content")

        deleted = await rotate_backups(str(backup_dir), keep_days=14)

        assert deleted == 0
        assert len(list(backup_dir.glob("jarvis-*.db.gz"))) == 5

    @pytest.mark.asyncio
    async def test_handles_nonexistent_directory(self, temp_dirs):
        """Test that nonexistent directory returns 0."""
        deleted = await rotate_backups("/nonexistent/dir", keep_days=14)

        assert deleted == 0

    @pytest.mark.asyncio
    async def test_ignores_invalid_filenames(self, temp_dirs):
        """Test that files with invalid names are skipped."""
        backup_dir = Path(temp_dirs["backup_dir"])
        backup_dir.mkdir(parents=True)

        # Create files with invalid names
        (backup_dir / "jarvis-invalid.db.gz").write_bytes(b"content")
        (backup_dir / "other-2024-01-01.db.gz").write_bytes(b"content")

        # Create one valid old backup
        old_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        (backup_dir / f"jarvis-{old_date}.db.gz").write_bytes(b"content")

        deleted = await rotate_backups(str(backup_dir), keep_days=14)

        assert deleted == 1


class TestRestoreBackup:
    """Tests for restore_backup function."""

    @pytest.mark.asyncio
    async def test_restores_backup(self, sample_db, temp_dirs):
        """Test that restore_backup correctly restores database."""
        original_content = Path(sample_db).read_bytes()

        # Create backup
        backup_path = await create_backup(sample_db, temp_dirs["backup_dir"])

        # Delete original
        Path(sample_db).unlink()
        assert not Path(sample_db).exists()

        # Restore
        await restore_backup(backup_path, sample_db)

        assert Path(sample_db).exists()
        assert Path(sample_db).read_bytes() == original_content

    @pytest.mark.asyncio
    async def test_restore_raises_for_missing_backup(self, temp_dirs):
        """Test that restore_backup raises for missing backup file."""
        with pytest.raises(FileNotFoundError):
            await restore_backup("/nonexistent/backup.db.gz", temp_dirs["db_path"])

    @pytest.mark.asyncio
    async def test_restore_creates_parent_directory(self, sample_db, temp_dirs):
        """Test that restore creates parent directory if needed."""
        backup_path = await create_backup(sample_db, temp_dirs["backup_dir"])

        new_db_path = str(Path(temp_dirs["db_path"]).parent / "nested" / "restored.db")

        await restore_backup(backup_path, new_db_path)

        assert Path(new_db_path).exists()


class TestListBackups:
    """Tests for list_backups function."""

    @pytest.mark.asyncio
    async def test_lists_backups_newest_first(self, temp_dirs):
        """Test that backups are listed newest first."""
        backup_dir = Path(temp_dirs["backup_dir"])
        backup_dir.mkdir(parents=True)

        dates = ["2024-01-01", "2024-01-15", "2024-01-10"]
        for date_str in dates:
            (backup_dir / f"jarvis-{date_str}.db.gz").write_bytes(b"content")

        backups = await list_backups(str(backup_dir))

        assert len(backups) == 3
        assert backups[0]["date"] == "2024-01-15"
        assert backups[1]["date"] == "2024-01-10"
        assert backups[2]["date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_includes_backup_metadata(self, temp_dirs):
        """Test that backup list includes path, date, and size."""
        backup_dir = Path(temp_dirs["backup_dir"])
        backup_dir.mkdir(parents=True)

        content = b"test content"
        backup_file = backup_dir / "jarvis-2024-01-15.db.gz"
        backup_file.write_bytes(content)

        backups = await list_backups(str(backup_dir))

        assert len(backups) == 1
        assert backups[0]["path"] == str(backup_file)
        assert backups[0]["date"] == "2024-01-15"
        assert backups[0]["size"] == len(content)

    @pytest.mark.asyncio
    async def test_returns_empty_for_nonexistent_dir(self, temp_dirs):
        """Test that nonexistent directory returns empty list."""
        backups = await list_backups("/nonexistent/dir")

        assert backups == []

    @pytest.mark.asyncio
    async def test_ignores_invalid_filenames(self, temp_dirs):
        """Test that invalid filenames are ignored."""
        backup_dir = Path(temp_dirs["backup_dir"])
        backup_dir.mkdir(parents=True)

        # Valid backup
        (backup_dir / "jarvis-2024-01-15.db.gz").write_bytes(b"content")
        # Invalid backups
        (backup_dir / "jarvis-invalid.db.gz").write_bytes(b"content")
        (backup_dir / "other-file.db.gz").write_bytes(b"content")

        backups = await list_backups(str(backup_dir))

        assert len(backups) == 1
        assert backups[0]["date"] == "2024-01-15"
