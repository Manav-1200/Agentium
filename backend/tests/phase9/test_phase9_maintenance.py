"""
Phase 9.2/9.3 — Database Maintenance & Backup Tests
Tests for configurable retention, constitution cleanup, backup rotation.
"""

import os
import pytest
import tempfile
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


class TestConstitutionPruning:
    """Tests for _prune_constitution_versions()."""

    def _make_constitution(self, version_num, constitution_id=None):
        c = MagicMock()
        c.id = constitution_id or f"C{version_num:04d}"
        c.version = version_num
        return c

    def test_no_prune_below_max(self, mock_db):
        """No pruning when fewer versions than max."""
        from backend.services.db_maintenance import DatabaseMaintenanceService

        versions = [self._make_constitution(i) for i in range(5, 0, -1)]
        mock_db.query.return_value.order_by.return_value.all.return_value = versions

        with patch("backend.services.db_maintenance.settings") as ms:
            ms.CONSTITUTION_MAX_VERSIONS = 10
            result = DatabaseMaintenanceService._prune_constitution_versions(mock_db)
            assert result == 0

    def test_prune_excess_versions(self, mock_db):
        """Excess versions are pruned, keeping latest N + version 1."""
        from backend.services.db_maintenance import DatabaseMaintenanceService

        # Create 15 versions, 15 down to 1
        versions = [self._make_constitution(i) for i in range(15, 0, -1)]
        mock_db.query.return_value.order_by.return_value.all.return_value = versions

        with patch("backend.services.db_maintenance.settings") as ms:
            ms.CONSTITUTION_MAX_VERSIONS = 5
            result = DatabaseMaintenanceService._prune_constitution_versions(mock_db)
            # Should prune versions 15 - 5 latest = 10, minus 1 for version 1 = 9
            assert result == 9
            # Ensure version 1 is NOT deleted
            deleted_ids = [call[0][0].id for call in mock_db.delete.call_args_list]
            assert "C0001" not in deleted_ids

    def test_version_1_always_kept(self, mock_db):
        """Version 1 (original constitution) must never be deleted."""
        from backend.services.db_maintenance import DatabaseMaintenanceService

        versions = [self._make_constitution(i) for i in range(12, 0, -1)]
        mock_db.query.return_value.order_by.return_value.all.return_value = versions

        with patch("backend.services.db_maintenance.settings") as ms:
            ms.CONSTITUTION_MAX_VERSIONS = 3
            DatabaseMaintenanceService._prune_constitution_versions(mock_db)
            deleted_ids = [call[0][0].id for call in mock_db.delete.call_args_list]
            assert "C0001" not in deleted_ids


class TestBackupRotation:
    """Tests for _rotate_backups()."""

    def test_rotate_keeps_newest(self):
        """Only the newest N backups should be kept."""
        from backend.services.db_maintenance import DatabaseMaintenanceService

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 10 backup files
            file_names = []
            for i in range(10):
                name = f"backup_2025010{i}_120000.sql"
                path = os.path.join(tmpdir, name)
                with open(path, "w") as f:
                    f.write(f"backup {i}")
                file_names.append(path)

            DatabaseMaintenanceService._rotate_backups(tmpdir, keep=3)

            remaining = sorted(os.listdir(tmpdir))
            assert len(remaining) == 3

    def test_rotate_no_files(self):
        """Rotation with empty directory should not error."""
        from backend.services.db_maintenance import DatabaseMaintenanceService

        with tempfile.TemporaryDirectory() as tmpdir:
            DatabaseMaintenanceService._rotate_backups(tmpdir, keep=7)
            assert len(os.listdir(tmpdir)) == 0


class TestVectorSnapshotRotation:
    """Tests for _rotate_vector_snapshots()."""

    def test_rotate_vector_snapshots(self):
        from backend.services.db_maintenance import DatabaseMaintenanceService

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(8):
                name = f"chromadb_2025010{i}_120000.tar.gz"
                path = os.path.join(tmpdir, name)
                with open(path, "w") as f:
                    f.write(f"snapshot {i}")

            DatabaseMaintenanceService._rotate_vector_snapshots(tmpdir, keep=4)

            remaining = sorted(os.listdir(tmpdir))
            assert len(remaining) == 4


class TestMaintenanceReport:
    """Tests for get_maintenance_report()."""

    def test_report_structure(self, mock_db):
        """Report should contain expected keys."""
        from backend.services.db_maintenance import DatabaseMaintenanceService

        # Mock the query chains
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        mock_db.query.return_value.count.return_value = 3

        with patch("backend.services.db_maintenance.settings") as ms:
            ms.AUDIT_LOG_RETENTION_DAYS = 90
            ms.TASK_ARCHIVE_DAYS = 30
            ms.CONSTITUTION_MAX_VERSIONS = 10

            report = DatabaseMaintenanceService.get_maintenance_report(mock_db)
            assert "audit_logs_eligible_for_cleanup" in report
            assert "tasks_eligible_for_archive" in report
            assert "constitution_versions" in report
            assert "max_kept_versions" in report
            assert "retention_config" in report
