from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from falsegreen.store.models import (
    Candidate,
    Checkpoint,
    Execution,
    Finding,
    GuardrailEvent,
    Instance,
    MetricSnapshot,
    PriorArt,
    Run,
    Verdict,
)
from falsegreen.store.repositories import (
    CandidateRepo,
    CheckpointRepo,
    ExecutionRepo,
    FindingRepo,
    GuardrailRepo,
    InstanceRepo,
    MetricRepo,
    PriorArtRepo,
    RunRepo,
    VerdictRepo,
)

REPOSITORIES_PATH = Path(__file__).resolve().parents[2] / "falsegreen" / "store" / "repositories.py"
_SQL_KEYWORDS = ("SELECT", "INSERT", "UPDATE", "DELETE")


def test_no_f_string_sql_in_repositories() -> None:
    offenders = []
    for lineno, line in enumerate(REPOSITORIES_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        if any(keyword in line.upper() for keyword in _SQL_KEYWORDS):
            if re.search(r"""f['"]""", line):
                offenders.append(f"{lineno}: {line.strip()}")
    assert not offenders, "f-string SQL found:\n" + "\n".join(offenders)


def _instance(**overrides) -> Instance:
    defaults = dict(
        instance_id="owner__repo-1",
        source="swebench_verified",
        repo="owner/repo",
        base_commit="abc123",
        gold_patch="--- a\n+++ b\n",
        fail_to_pass=["tests.test_foo"],
        pass_to_pass=["tests.test_bar"],
        included=True,
    )
    defaults.update(overrides)
    return Instance(**defaults)


def test_instance_round_trip(conn: sqlite3.Connection) -> None:
    repo = InstanceRepo(conn)
    inst = _instance()
    repo.upsert_many([inst])
    fetched = repo.get(inst.instance_id)
    assert fetched == inst


def test_instance_denominator_excludes_not_included(conn: sqlite3.Connection) -> None:
    repo = InstanceRepo(conn)
    repo.upsert_many(
        [
            _instance(instance_id="a__a-1", included=True),
            _instance(instance_id="a__a-2", included=True),
            _instance(instance_id="a__a-3", included=False, exclusion_reason="empty_f2p"),
        ]
    )
    assert repo.denominator("swebench_verified") == 2
    assert repo.exclusion_counts("swebench_verified") == {"empty_f2p": 1}
    assert len(repo.included("swebench_verified")) == 2


def _checkpoint(**overrides) -> Checkpoint:
    defaults = dict(
        checkpoint_id="ckpt-1",
        repo="owner/repo",
        env_commit="abc123",
        contree_image_id="img-1",
        image_tag="tag-1",
        python_version="3.11",
        test_command="pytest",
        suite_green=True,
        build_seconds=12.5,
        built_at="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return Checkpoint(**defaults)


def test_checkpoint_round_trip(conn: sqlite3.Connection) -> None:
    repo = CheckpointRepo(conn)
    ckpt = _checkpoint()
    repo.upsert(ckpt)
    fetched = repo.get_by_repo_commit(ckpt.repo, ckpt.env_commit)
    assert fetched == ckpt


def _run(**overrides) -> Run:
    defaults = dict(
        run_id="run-1",
        mode="bench",
        condition="cold",
        backend="contree",
        falsegreen_sha="deadbeef",
        models_toml_hash="cafef00d",
        started_at="2026-01-01T00:00:00Z",
        status="running",
    )
    defaults.update(overrides)
    return Run(**defaults)


def test_run_round_trip_and_lifecycle(conn: sqlite3.Connection) -> None:
    repo = RunRepo(conn)
    run = _run()
    repo.create(run)

    repo.add_cost(run.run_id, token_usd=1.5, compute_usd=0.25)
    repo.add_cost(run.run_id, token_usd=1.0, compute_usd=0.25)
    repo.finish(run.run_id, "complete")

    fetched = repo.get(run.run_id)
    assert fetched.token_cost_usd == pytest.approx(2.5)
    assert fetched.compute_cost_usd == pytest.approx(0.5)
    assert fetched.status == "complete"
    assert fetched.finished_at is not None

    by_condition = repo.list_by_condition("cold")
    assert [r.run_id for r in by_condition] == ["run-1"]


def _candidate(**overrides) -> Candidate:
    defaults = dict(
        candidate_id="cand-1",
        run_id="run-1",
        ordinal=0,
        hypothesis="parse_ts mishandles a negative offset",
        test_code="def test_x(): assert True",
        test_path="tests/test_x.py",
        model="nemotron-3-ultra",
        prompt_hash="hash1",
    )
    defaults.update(overrides)
    return Candidate(**defaults)


def test_candidate_round_trip(conn: sqlite3.Connection) -> None:
    RunRepo(conn).create(_run())
    repo = CandidateRepo(conn)
    cand = _candidate()
    repo.insert(cand)

    assert repo.by_run("run-1") == [cand]
    assert repo.by_instance("nonexistent") == []


def _execution(**overrides) -> Execution:
    defaults = dict(
        execution_id="exec-1",
        candidate_id="cand-1",
        phase="base",
        was_fork=True,
    )
    defaults.update(overrides)
    return Execution(**defaults)


def test_execution_round_trip_and_aggregates(conn: sqlite3.Connection) -> None:
    RunRepo(conn).create(_run())
    CandidateRepo(conn).insert(_candidate())
    repo = ExecutionRepo(conn)

    repo.insert(_execution(execution_id="exec-1", was_fork=True))
    repo.insert(_execution(execution_id="exec-2", was_fork=False, error_class="timeout"))
    repo.insert(_execution(execution_id="exec-3", was_fork=True, error_class="timeout"))

    fetched = repo.by_candidate("cand-1")
    assert len(fetched) == 3

    assert repo.fork_ratio("run-1") == pytest.approx(2 / 3)
    assert repo.error_breakdown("run-1") == {"timeout": 2}


def test_fork_ratio_empty_run_returns_zero(conn: sqlite3.Connection) -> None:
    RunRepo(conn).create(_run())
    assert ExecutionRepo(conn).fork_ratio("run-1") == 0.0


def _verdict(**overrides) -> Verdict:
    defaults = dict(
        candidate_id="cand-1",
        fails_at_base=True,
        passes_at_gold=True,
        verdict="verified",
        computed_at="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return Verdict(**defaults)


def test_verdict_round_trip_and_counts(conn: sqlite3.Connection) -> None:
    RunRepo(conn).create(_run())
    CandidateRepo(conn).insert(_candidate())
    repo = VerdictRepo(conn)
    verdict = _verdict()
    repo.upsert(verdict)

    assert repo.counts("run-1") == {"verified": 1}

    repo.upsert(_verdict(verdict="error", fails_at_base=None, passes_at_gold=None))
    assert repo.counts("run-1") == {"error": 1}


def test_guardrail_event_round_trip(conn: sqlite3.Connection) -> None:
    RunRepo(conn).create(_run())
    CandidateRepo(conn).insert(_candidate())
    repo = GuardrailRepo(conn)
    event = GuardrailEvent(
        event_id="evt-1",
        candidate_id="cand-1",
        attempted_path="/etc/passwd",
        rule="path_allowlist",
        action="rejected",
        occurred_at="2026-01-01T00:00:00Z",
    )
    repo.insert(event)
    assert repo.by_run("run-1") == [event]


def _finding(**overrides) -> Finding:
    defaults = dict(
        finding_id="find-1",
        run_id="run-1",
        candidate_id="cand-1",
        rank=1,
        title="parse_ts mishandles a negative offset",
        explanation="explained",
        repro_command="falsegreen replay cand-1",
        audit_cost_cents=12.3,
    )
    defaults.update(overrides)
    return Finding(**defaults)


def test_finding_replace_for_run_round_trip(conn: sqlite3.Connection) -> None:
    RunRepo(conn).create(_run())
    CandidateRepo(conn).insert(_candidate())
    repo = FindingRepo(conn)
    finding = _finding()
    repo.replace_for_run("run-1", [finding])
    assert repo.by_run("run-1") == [finding]

    repo.replace_for_run("run-1", [])
    assert repo.by_run("run-1") == []


def test_finding_replace_for_run_rejects_fourth_finding(conn: sqlite3.Connection) -> None:
    RunRepo(conn).create(_run())
    CandidateRepo(conn).insert(_candidate())
    repo = FindingRepo(conn)
    findings = [_finding(finding_id=f"find-{i}", rank=i) for i in range(4)]
    with pytest.raises(ValueError):
        repo.replace_for_run("run-1", findings)


def _metric_snapshot(**overrides) -> MetricSnapshot:
    defaults = dict(
        snapshot_id="snap-1",
        run_id="run-1",
        condition="cold",
        n_denominator=449,
        n_verified=20,
        n_unverified_cand=80,
        n_error=5,
        rate=0.0445,
        wilson_low=0.029,
        wilson_high=0.068,
        cost_usd_total=120.0,
        cost_per_verified=6.0,
        computed_at="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return MetricSnapshot(**defaults)


def test_metric_snapshot_round_trip(conn: sqlite3.Connection) -> None:
    RunRepo(conn).create(_run())
    repo = MetricRepo(conn)
    snapshot = _metric_snapshot()
    repo.upsert(snapshot)
    assert repo.by_run("run-1") == [snapshot]


def test_prior_art_round_trip(conn: sqlite3.Connection) -> None:
    repo = PriorArtRepo(conn)
    entry = PriorArt(
        key="swt_bench_verified",
        label="SWT-Bench Verified (issue available)",
        reported_rate=0.49,
        denominator=433,
        condition_note="issue description available",
        citation="Mundler et al., SWT-Bench, 2024",
    )
    repo.upsert_many([entry])
    assert repo.all() == [entry]
