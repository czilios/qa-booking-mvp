from pathlib import Path

import pytest

from app import migration_runner


def test_migration_preflight_rejects_source_seed_out_of_order(monkeypatch, tmp_path):
    source_dir = Path(__file__).resolve().parents[1] / "database" / "migrations"
    for source in source_dir.glob("*.sql"):
        content = source.read_text(encoding="utf-8")
        if source.name.startswith("001_"):
            content = content.replace("('DIRECT',", "('WRONG',", 1)
        (tmp_path / source.name).write_text(content, encoding="utf-8")
    monkeypatch.setattr(migration_runner, "MIGRATION_DIR", tmp_path)

    with pytest.raises(migration_runner.MigrationError, match="source seed does not match"):
        migration_runner._load_migrations()