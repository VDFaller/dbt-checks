"""Create a fresh DuckDB database and preload the physical Jaffle sources."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(
    os.environ.get("JAFFLE_SHOP_DB_PATH", PROJECT_DIR / "target" / "jaffle_shop.duckdb")
).resolve()


def main() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH.unlink(missing_ok=True)
    env = os.environ.copy()
    env["JAFFLE_SHOP_DB_PATH"] = str(DATABASE_PATH)
    env["JAFFLE_SHOP_SOURCE_DIR"] = str(PROJECT_DIR)
    subprocess.run(
        [
            "dbt", "run-operation", "setup_sources",
            "--project-dir", str(PROJECT_DIR),
            "--profiles-dir", str(PROJECT_DIR),
        ],
        cwd=PROJECT_DIR,
        env=env,
        check=True,
    )
    if not DATABASE_PATH.exists():
        raise RuntimeError(f"dbt connected without creating the expected DuckDB file: {DATABASE_PATH}")
    print(f"Created {DATABASE_PATH} with raw_customers and raw_orders")


if __name__ == "__main__":
    main()
