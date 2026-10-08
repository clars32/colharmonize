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


def test_a_bad_answer_fails_only_its_item(tmp_path):
    d = write(tmp_path)
    b1 = json.loads((d / "batch_01.json").read_text())
    first, second = [it["item_id"] for it in b1["items"]]
    answer(d, "batch_01.json", lambda b: b["answers"][0].pop("label"))       # schema error on the first item
    got = tasks.collect(d, Ans)
    assert set(got.by_item) == {second} and "schema error" in got.failed[first]
    assert not got.complete and len(got.pending) == 2


@pytest.mark.parametrize("mutate,expect,n_failed", [
    (lambda b: b.update(content_sha256="0" * 64), "content_sha256 does not match", 2),   # untrusted file: all its items
    (lambda b: b["answers"].pop(), "no answer", 1),
    (lambda b: b["answers"].append(dict(b["answers"][0])), "answered 2 times", 1),
    (lambda b: b["answers"].append({"item_id": "stray", "label": "x"}), None, 0),       # unknown ids are ignored
])
def test_item_level_failures(tmp_path, mutate, expect, n_failed):
    d = write(tmp_path)
    answer(d, "batch_01.json", mutate)
    got = tasks.collect(d, Ans)
    assert len(got.failed) == n_failed and len(got.answers) == 2 - n_failed
    if expect:
        assert all(expect in why for why in got.failed.values())


def test_retry_batches_hold_only_failed_items_and_win(tmp_path):
    d = write(tmp_path)
    for f in ["batch_01.json", "batch_02.json", "batch_03.json"]:
        answer(d, f)
    bad = json.loads((d / "batch_02.json").read_text())["items"][0]["item_id"]
    path, given_up = tasks.write_retry(d, [bad])
    retry = json.loads(path.read_text())
    assert [it["item_id"] for it in retry["items"]] == [bad] and not given_up
    assert tasks.collect(d, Ans).pending == [path.name]
    (d / retry["answer_file"]).write_text(json.dumps({"content_sha256": retry["content_sha256"],
                                                      "answers": [{"item_id": bad, "label": "fixed"}]}))
    got = tasks.collect(d, Ans)
    assert got.complete and got.by_item[bad].label == "fixed" and len(got.answers) == 5
    tasks.write_retry(d, [bad])
    assert tasks.write_retry(d, [bad]) == (None, [bad])                     # at most two retries per item


def test_stage_problems_are_attributed_to_items():
    by_item, general = tasks.split_problems(
        ["S1::age/primary: unknown ref T9", "S1::age group: bad", "S1: split needs two rules", "something global"],
        ["S1::age", "S1::age group", "S1"])
    assert set(by_item) == {"S1::age", "S1::age group", "S1"} and general == ["something global"]
