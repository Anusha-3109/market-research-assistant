"""Tests for where a deployed copy stores its data. The sign-in screen is
tested in test_sign_in.py."""

import shutil
from pathlib import Path

from agent import config, memory


# --- where data is stored -------------------------------------------------------------------

def test_without_a_data_folder_everything_stays_in_the_project():
    reports, memory_file, copy = config.storage_paths("")

    assert reports == config.PROJECT_DIR / "reports"
    assert memory_file == config.PROJECT_DIR / "data" / "memory.db"
    assert copy is None                       # nothing is copied anywhere


def test_with_a_data_folder_reports_go_there_and_memory_keeps_a_copy_there():
    reports, memory_file, copy = config.storage_paths("/mnt/markavi")

    assert reports == Path("/mnt/markavi/reports")
    assert copy == Path("/mnt/markavi/memory.db")
    # The working file is on the machine's own disk, not in the data folder.
    assert Path("/mnt/markavi") not in memory_file.parents


def test_a_data_folder_of_only_spaces_counts_as_not_set():
    assert config.storage_paths("   ") == config.storage_paths("")


# --- the copy of the memory file ---------------------------------------------------------------

def remember(path: Path, region: str) -> None:
    """Open the memory file, save one fact, and close it again."""
    checkpointer, store = memory.open_memory(path, backup=None)
    memory.save_preference(store, memory.DEFAULT_USER, "region", region)
    store.conn.close()
    checkpointer.conn.close()


def test_what_was_saved_comes_back_after_the_local_disk_is_wiped(tmp_path):
    working, copy = tmp_path / "local" / "memory.db", tmp_path / "bucket" / "memory.db"
    remember(working, "Portugal")

    assert memory.backup_memory(working, copy) is True
    shutil.rmtree(working.parent)             # what a restart in the cloud does

    checkpointer, store = memory.open_memory(working, copy)
    assert memory.load_profile(store, memory.DEFAULT_USER) == {"region": "Portugal"}
    store.conn.close()
    checkpointer.conn.close()


def test_the_copy_is_one_complete_file_with_no_leftovers(tmp_path):
    working, copy = tmp_path / "local" / "memory.db", tmp_path / "bucket" / "memory.db"
    remember(working, "Portugal")

    memory.backup_memory(working, copy)

    assert [file.name for file in copy.parent.iterdir()] == ["memory.db"]
    assert not working.with_name("memory.db.snapshot").exists()


def test_a_later_copy_replaces_the_earlier_one(tmp_path):
    working, copy = tmp_path / "local" / "memory.db", tmp_path / "bucket" / "memory.db"
    remember(working, "Portugal")
    memory.backup_memory(working, copy)
    remember(working, "Spain")
    memory.backup_memory(working, copy)
    shutil.rmtree(working.parent)

    checkpointer, store = memory.open_memory(working, copy)
    assert memory.load_profile(store, memory.DEFAULT_USER) == {"region": "Spain"}
    store.conn.close()
    checkpointer.conn.close()


def test_an_existing_memory_file_is_not_overwritten_by_an_older_copy(tmp_path):
    working, copy = tmp_path / "local" / "memory.db", tmp_path / "bucket" / "memory.db"
    remember(working, "Portugal")
    memory.backup_memory(working, copy)
    remember(working, "Spain")                # newer than the copy

    assert memory.restore_memory(working, copy) is False


def test_on_your_own_computer_no_copy_is_made(tmp_path):
    working = tmp_path / "memory.db"
    remember(working, "Portugal")

    assert memory.backup_memory(working, None) is False
    assert memory.restore_memory(working, None) is False


def test_a_folder_that_cannot_be_written_does_not_break_the_app(tmp_path):
    working = tmp_path / "local" / "memory.db"
    remember(working, "Portugal")
    blocked = tmp_path / "a-file"
    blocked.write_text("not a folder")

    # The copy would have to go inside something that is a file.
    assert memory.backup_memory(working, blocked / "memory.db") is False
