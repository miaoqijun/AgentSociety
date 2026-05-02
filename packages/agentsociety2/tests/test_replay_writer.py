import pytest

from agentsociety2.storage import ReplayWriter


@pytest.mark.asyncio
async def test_replay_writer_init_creates_db(tmp_path):
    db_path = tmp_path / "nested" / "sqlite.db"
    writer = ReplayWriter(db_path)
    await writer.init()
    assert db_path.is_file()
    await writer.close()


@pytest.mark.asyncio
async def test_replay_writer_close_idempotent(tmp_path):
    db_path = tmp_path / "sqlite.db"
    writer = ReplayWriter(db_path)
    await writer.init()
    await writer.close()
    await writer.close()
