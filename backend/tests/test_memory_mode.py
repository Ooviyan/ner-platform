"""The suite must run without a database, whatever is listening on 5432."""

from app.database import db_available, db_status


def test_suite_runs_on_the_in_memory_seed():
    assert db_available() is False
    assert db_status()["mode"] == "memory-seed"
