"""Validate the distributable lessons without requiring Chrome or a robot in CI."""

import json
import zipfile
from pathlib import Path


def test_original_scratch_projects_have_complete_assets_and_valid_links():
    examples = Path(__file__).resolve().parents[1] / "examples/scratch"
    names = {path.stem for path in examples.glob("*.sb3")}
    assert names == {
        "hello-cozmo",
        "square-drive",
        "cube-reaction",
        "traffic-light",
        "mood-machine",
        "ai-conversation",
        "safe-explorer",
    }
    for path in examples.glob("*.sb3"):
        with zipfile.ZipFile(path) as archive:
            project = json.loads(archive.read("project.json"))
            assert "cozmo" in project["extensions"]
            targets = project["targets"]
            assert len(targets) == 2 and targets[0]["isStage"]
            for target in targets:
                for costume in target["costumes"]:
                    assert costume["md5ext"] in archive.namelist()
                blocks = target["blocks"]
                for block in blocks.values():
                    assert block["parent"] is None or block["parent"] in blocks
                    assert block["next"] is None or block["next"] in blocks
            assert any(
                block["opcode"].startswith("cozmo_") for block in targets[1]["blocks"].values()
            )
