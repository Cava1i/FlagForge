from pathlib import Path

from backend.storage.db import bootstrap, connect


def count_fds_for(path: Path) -> int:
    target = str(path)
    count = 0
    for fd in Path("/proc/self/fd").iterdir():
        try:
            if str(fd.resolve()) == target:
                count += 1
        except FileNotFoundError:
            continue
    return count


def test_connect_context_closes_sqlite_file_descriptor(tmp_path):
    db_path = tmp_path / "web.sqlite3"
    bootstrap(db_path)
    before = count_fds_for(db_path)

    for _ in range(20):
        with connect(db_path) as connection:
            connection.execute("SELECT 1").fetchone()

    assert count_fds_for(db_path) == before
