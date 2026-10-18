"""Run database migrations.

  python -m src.db.migrate_cli upgrade     bring the database to the latest schema (safe to repeat)
  python -m src.db.migrate_cli current     show the schema version
  python -m src.db.migrate_cli sql         print the SQL instead of running it
Uses DATABASE_URL, the same setting as the application.
"""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]


def alembic_config(connection=None) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def upgrade(connection=None, revision: str = "head") -> None:
    command.upgrade(alembic_config(connection), revision)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    action = args[0] if args else "upgrade"
    cfg = alembic_config()
    if action == "upgrade":
        command.upgrade(cfg, "head")
    elif action == "current":
        command.current(cfg, verbose=True)
    elif action == "sql":
        command.upgrade(cfg, "head", sql=True)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
