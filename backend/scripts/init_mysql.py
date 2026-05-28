from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pymysql


def _fail(msg: str) -> None:
    raise SystemExit(msg)


def _load_env_file(env_file: Path) -> None:
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _build_server_url(database_url: str) -> tuple[str, str]:
    parsed = urlparse(database_url)
    if parsed.scheme != "mysql+pymysql":
        _fail("DATABASE_URL must start with mysql+pymysql://")
    db_name = parsed.path.lstrip("/")
    if not db_name:
        _fail("DATABASE_URL must include database name, e.g. .../travel_agent")

    query_pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() != "charset"]
    query_pairs.append(("charset", "utf8mb4"))
    server_parsed = parsed._replace(path="/", query=urlencode(query_pairs))
    return urlunparse(server_parsed), db_name


def _connect_from_url(url: str, database: str | None = None):
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 3306
    user = parsed.username
    password = parsed.password
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    charset = query.get("charset", "utf8mb4")
    if not user:
        _fail("DATABASE_URL must include username")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset=charset,
        autocommit=True,
    )


def _execute_sql_file(conn, sql_file: Path, *, schema_only: bool = False) -> None:
    sql = None
    encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk"]
    for enc in encodings:
        try:
            sql = sql_file.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if sql is None:
        _fail(f"failed to decode SQL file with supported encodings: {sql_file}")
    sql = sql.lstrip("\ufeff")
    with conn.cursor() as cursor:
        for idx, stmt in enumerate([part.strip() for part in sql.split(";") if part.strip()], start=1):
            normalized = " ".join(stmt.split()).upper()
            if schema_only and (
                "INSERT INTO" in normalized
                or "LOCK TABLES" in normalized
                or "UNLOCK TABLES" in normalized
                or "DISABLE KEYS" in normalized
                or "ENABLE KEYS" in normalized
            ):
                continue
            try:
                cursor.execute(stmt)
            except Exception as exc:
                preview = stmt.replace("\n", " ")
                if len(preview) > 200:
                    preview = f"{preview[:200]}..."
                raise RuntimeError(
                    f"failed SQL in {sql_file.name} at statement #{idx}: {preview}"
                ) from exc


def _clear_seed_tables(conn) -> None:
    # child tables first, then parent tables
    tables = [
        "plan_tasks",
        "trip_plan_versions",
        "trip_plans",
        "user_profiles",
        "users",
    ]
    with conn.cursor() as cursor:
        for table in tables:
            cursor.execute(f"TRUNCATE TABLE `{table}`")


def main() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    backend_env = root_dir / "backend" / ".env"
    _load_env_file(backend_env)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        _fail("DATABASE_URL is not set")

    server_url, db_name = _build_server_url(database_url)
    db_dir = root_dir / "database"
    if not db_dir.exists():
        _fail(f"database directory not found: {db_dir}")

    table_files = [
        db_dir / "travel_agent_users.sql",
        db_dir / "travel_agent_user_profiles.sql",
        db_dir / "travel_agent_trip_plans.sql",
        db_dir / "travel_agent_trip_plan_version.sql",
        db_dir / "travel_agent_plan_tasks.sql",
    ]
    seed_file = db_dir / "seed.sql"

    for file in [*table_files, seed_file]:
        if not file.exists():
            _fail(f"required SQL file missing: {file}")

    server_conn = _connect_from_url(server_url)
    try:
        with server_conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        server_conn.close()

    db_conn = _connect_from_url(database_url, database=db_name)
    try:
        with db_conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")

        for file in table_files:
            _execute_sql_file(db_conn, file, schema_only=True)
            print(f"[OK] executed: {file.name}")

        _clear_seed_tables(db_conn)
        print("[OK] cleared existing rows before seed")

        _execute_sql_file(db_conn, seed_file)
        print(f"[OK] executed: {seed_file.name}")

        with db_conn.cursor() as cursor:
            cursor.execute("ALTER TABLE `trip_plan_versions` ALTER INDEX `uk_plan_version` VISIBLE")
            cursor.execute("ALTER TABLE `trip_plan_versions` ALTER INDEX `idx_plan_id` VISIBLE")
            cursor.execute("ALTER TABLE `trip_plan_versions` ALTER INDEX `idx_owner_user_id` VISIBLE")
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        print(f"[DONE] MySQL initialized for database: {db_name}")
    finally:
        db_conn.close()


if __name__ == "__main__":
    main()
