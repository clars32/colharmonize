"""The task-file protocol: what a subagent's answer must satisfy before anything uses it."""
import json

import pytest
from pydantic import BaseModel

from colharmonize import tasks


class Ans(BaseModel):
    item_id: str
    label: str


ITEMS = [{"item_id": f"i{n}", "text": f"t{n}"} for n in range(5)]


def write(tmp_path, run=1, seed=1):
    d = tmp_path / f"run{run}"
    tasks.write_batches(d, stage="demo", run=run, prompt_version="demo-1", instructions="label each item",
                        items=ITEMS, answer_model=Ans, batch_size=2, seed=seed)
    return d


def answer(d, batch_file, mutate=None):
    b = json.loads((d / batch_file).read_text())
    body = {"content_sha256": b["content_sha256"],
            "answers": [{"item_id": it["item_id"], "label": "x"} for it in b["items"]]}
    if mutate:
        mutate(body)
    (d / b["answer_file"]).write_text(json.dumps(body))


def test_batches_and_manifest(tmp_path):
    d = write(tmp_path)
    m = json.loads((d / "manifest.json").read_text())
    assert [len(b["items"]) for b in m["batches"]] == [2, 2, 1]
    assert sorted(i for b in m["batches"] for i in b["items"]) == [it["item_id"] for it in ITEMS]
    b = json.loads((d / "batch_01.json").read_text())
    assert b["answer_schema"]["required"] == ["content_sha256", "answers"]


def test_runs_differ_in_order(tmp_path):
    m1 = json.loads((write(tmp_path, run=1, seed=1001) / "manifest.json").read_text())
    m2 = json.loads((write(tmp_path, run=2, seed=2001) / "manifest.json").read_text())
    assert [b["items"] for b in m1["batches"]] != [b["items"] for b in m2["batches"]]


def test_refuses_to_overwrite_a_run(tmp_path):
    write(tmp_path)
    with pytest.raises(FileExistsError):
        write(tmp_path)


def test_pending_then_complete(tmp_path):
    d = write(tmp_path)
    assert tasks.status(d) == {"batches": 3, "answered": 0, "pending": 3}
    for f in ["batch_01.json", "batch_02.json", "batch_03.json"]:
        answer(d, f)
    got = tasks.collect(d, Ans)
    assert got.complete and len(got.answers) == 5


@pytest.mark.parametrize("mutate,expect", [
    (lambda b: b.update(content_sha256="0" * 64), "content_sha256 does not match"),
    (lambda b: b["answers"].pop(), "missing"),
    (lambda b: b["answers"].append(dict(b["answers"][0])), "duplicated"),
    (lambda b: b["answers"][0].pop("label"), "schema error"),
])
def test_bad_answers_are_rejected_whole(tmp_path, mutate, expect):
    d = write(tmp_path)
    answer(d, "batch_01.json", mutate)
    got = tasks.collect(d, Ans)
    assert not got.complete and len(got.answers) == 0
    assert expect in got.problems[0]
    assert len(got.pending) == 2
