from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

from scripts.shep_missions import create_mission, list_missions, queue_mission


def test_create_mission_is_pure_and_validates() -> None:
    mission = create_mission(" Ship the Orca flow ", mode="fleet", base="develop", now=12)
    assert mission["goal"] == "Ship the Orca flow"
    assert mission["status"] == "queued"
    assert mission["branch_prefix"] == "swarmlet/ship-the-orca-flow"
    assert mission["created_at"] == 12


def test_queue_and_list_use_shep_canonical_store(tmp_path: Path) -> None:
    path = tmp_path / "missions.json"
    mission = queue_mission("Ship the Orca flow", path=path, now=12)
    assert list_missions(path) == [mission]
    assert json.loads(path.read_text())["schema"] == "shep-missions/v1"
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.with_name("missions.json.lock").stat().st_mode & 0o777 == 0o600


def _queue(path: str, index: int) -> None:
    queue_mission(f"Mission {index}", path=path, now=index)


def test_queue_serializes_concurrent_writers(tmp_path: Path) -> None:
    path = tmp_path / "missions.json"
    processes = [multiprocessing.Process(target=_queue, args=(str(path), index)) for index in range(4)]
    for process in processes:
        process.start()
    for process in processes:
        process.join()
        assert process.exitcode == 0
    missions = list_missions(path)
    assert len(missions) == 4
    assert {mission["goal"] for mission in missions} == {f"Mission {index}" for index in range(4)}
