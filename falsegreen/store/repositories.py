from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from falsegreen.config import get_settings
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


def _row_to_instance(row: sqlite3.Row) -> Instance:
    data = dict(row)
    data["fail_to_pass"] = json.loads(data["fail_to_pass"])
    data["pass_to_pass"] = (
        json.loads(data["pass_to_pass"]) if data["pass_to_pass"] is not None else None
    )
    data["included"] = bool(data["included"])
    return Instance.model_validate(data)


class InstanceRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert_many(self, instances: list[Instance]) -> None:
        rows = [
            (
                inst.instance_id,
                inst.source,
                inst.repo,
                inst.base_commit,
                inst.environment_setup_commit,
                inst.gold_patch,
                inst.test_patch,
                json.dumps(inst.fail_to_pass),
                json.dumps(inst.pass_to_pass) if inst.pass_to_pass is not None else None,
                inst.issue_text,
                inst.merged_at,
                inst.days_to_report,
                int(inst.included),
                inst.exclusion_reason,
            )
            for inst in instances
        ]
        query = (
            "INSERT OR REPLACE INTO instance ("
            "instance_id, source, repo, base_commit, environment_setup_commit, gold_patch, "
            "test_patch, fail_to_pass, pass_to_pass, issue_text, merged_at, days_to_report, "
            "included, exclusion_reason"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        self._conn.executemany(query, rows)

    def get(self, instance_id: str) -> Instance | None:
        query = "SELECT * FROM instance WHERE instance_id = ?"
        row = self._conn.execute(query, (instance_id,)).fetchone()
        return _row_to_instance(row) if row is not None else None

    def included(self, source: str) -> list[Instance]:
        query = "SELECT * FROM instance WHERE source = ? AND included = 1"
        rows = self._conn.execute(query, (source,)).fetchall()
        return [_row_to_instance(row) for row in rows]

    def denominator(self, source: str) -> int:
        """The published denominator: count of included=1 rows for a source. One implementation."""
        query = "SELECT COUNT(*) FROM instance WHERE source = ? AND included = 1"
        return self._conn.execute(query, (source,)).fetchone()[0]

    def exclusion_counts(self, source: str) -> dict[str, int]:
        query = (
            "SELECT exclusion_reason, COUNT(*) AS n FROM instance "
            "WHERE source = ? AND included = 0 GROUP BY exclusion_reason"
        )
        rows = self._conn.execute(query, (source,)).fetchall()
        return {row["exclusion_reason"]: row["n"] for row in rows}


class CheckpointRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, checkpoint: Checkpoint) -> None:
        query = (
            "INSERT OR REPLACE INTO checkpoint ("
            "checkpoint_id, repo, env_commit, contree_image_id, image_tag, python_version, "
            "test_command, services_script, suite_green, build_seconds, built_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        self._conn.execute(
            query,
            (
                checkpoint.checkpoint_id,
                checkpoint.repo,
                checkpoint.env_commit,
                checkpoint.contree_image_id,
                checkpoint.image_tag,
                checkpoint.python_version,
                checkpoint.test_command,
                checkpoint.services_script,
                int(checkpoint.suite_green),
                checkpoint.build_seconds,
                checkpoint.built_at,
            ),
        )

    def get_by_repo_commit(self, repo: str, env_commit: str) -> Checkpoint | None:
        query = "SELECT * FROM checkpoint WHERE repo = ? AND env_commit = ?"
        row = self._conn.execute(query, (repo, env_commit)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["suite_green"] = bool(data["suite_green"])
        return Checkpoint.model_validate(data)


class RunRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, run: Run) -> None:
        query = (
            "INSERT INTO run ("
            "run_id, mode, condition, backend, falsegreen_sha, models_toml_hash, seed, "
            "temperature, started_at, finished_at, status, token_cost_usd, compute_cost_usd, notes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        self._conn.execute(
            query,
            (
                run.run_id,
                run.mode,
                run.condition,
                run.backend,
                run.falsegreen_sha,
                run.models_toml_hash,
                run.seed,
                run.temperature,
                run.started_at,
                run.finished_at,
                run.status,
                run.token_cost_usd,
                run.compute_cost_usd,
                run.notes,
            ),
        )

    def finish(self, run_id: str, status: str) -> None:
        query = "UPDATE run SET status = ?, finished_at = ? WHERE run_id = ?"
        self._conn.execute(query, (status, datetime.now(timezone.utc).isoformat(), run_id))

    def add_cost(self, run_id: str, token_usd: float, compute_usd: float) -> None:
        query = (
            "UPDATE run SET token_cost_usd = token_cost_usd + ?, "
            "compute_cost_usd = compute_cost_usd + ? WHERE run_id = ?"
        )
        self._conn.execute(query, (token_usd, compute_usd, run_id))

    def get(self, run_id: str) -> Run | None:
        query = "SELECT * FROM run WHERE run_id = ?"
        row = self._conn.execute(query, (run_id,)).fetchone()
        return Run.model_validate(dict(row)) if row is not None else None

    def list_by_condition(self, condition: str) -> list[Run]:
        query = "SELECT * FROM run WHERE condition = ?"
        rows = self._conn.execute(query, (condition,)).fetchall()
        return [Run.model_validate(dict(row)) for row in rows]


class CandidateRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insert(self, candidate: Candidate) -> None:
        query = (
            "INSERT INTO candidate ("
            "candidate_id, run_id, instance_id, ordinal, target_file, target_symbol, "
            "hypothesis, input_class, test_code, test_path, model, prompt_hash, tokens_in, "
            "tokens_out, gen_seconds"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        self._conn.execute(
            query,
            (
                candidate.candidate_id,
                candidate.run_id,
                candidate.instance_id,
                candidate.ordinal,
                candidate.target_file,
                candidate.target_symbol,
                candidate.hypothesis,
                candidate.input_class,
                candidate.test_code,
                candidate.test_path,
                candidate.model,
                candidate.prompt_hash,
                candidate.tokens_in,
                candidate.tokens_out,
                candidate.gen_seconds,
            ),
        )

    def by_run(self, run_id: str) -> list[Candidate]:
        query = "SELECT * FROM candidate WHERE run_id = ?"
        rows = self._conn.execute(query, (run_id,)).fetchall()
        return [Candidate.model_validate(dict(row)) for row in rows]

    def by_instance(self, instance_id: str) -> list[Candidate]:
        query = "SELECT * FROM candidate WHERE instance_id = ?"
        rows = self._conn.execute(query, (instance_id,)).fetchall()
        return [Candidate.model_validate(dict(row)) for row in rows]


def _row_to_execution(row: sqlite3.Row) -> Execution:
    data = dict(row)
    data["was_fork"] = bool(data["was_fork"])
    return Execution.model_validate(data)


class ExecutionRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insert(self, execution: Execution) -> None:
        query = (
            "INSERT INTO execution ("
            "execution_id, candidate_id, phase, checkpoint_id, fork_id, provider_request_id, "
            "was_fork, exit_code, stdout_tail, duration_ms, cpu_ms, mem_peak_mb, io_bytes, "
            "cost_cents, retries, error_class"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        self._conn.execute(
            query,
            (
                execution.execution_id,
                execution.candidate_id,
                execution.phase,
                execution.checkpoint_id,
                execution.fork_id,
                execution.provider_request_id,
                int(execution.was_fork),
                execution.exit_code,
                execution.stdout_tail,
                execution.duration_ms,
                execution.cpu_ms,
                execution.mem_peak_mb,
                execution.io_bytes,
                execution.cost_cents,
                execution.retries,
                execution.error_class,
            ),
        )

    def by_candidate(self, candidate_id: str) -> list[Execution]:
        query = "SELECT * FROM execution WHERE candidate_id = ?"
        rows = self._conn.execute(query, (candidate_id,)).fetchall()
        return [_row_to_execution(row) for row in rows]

    def fork_ratio(self, run_id: str) -> float:
        query = (
            "SELECT COUNT(*) AS total, COALESCE(SUM(execution.was_fork), 0) AS forked "
            "FROM execution JOIN candidate ON candidate.candidate_id = execution.candidate_id "
            "WHERE candidate.run_id = ?"
        )
        row = self._conn.execute(query, (run_id,)).fetchone()
        if row["total"] == 0:
            return 0.0
        return row["forked"] / row["total"]

    def error_breakdown(self, run_id: str) -> dict[str, int]:
        query = (
            "SELECT execution.error_class AS error_class, COUNT(*) AS n "
            "FROM execution JOIN candidate ON candidate.candidate_id = execution.candidate_id "
            "WHERE candidate.run_id = ? AND execution.error_class IS NOT NULL "
            "GROUP BY execution.error_class"
        )
        rows = self._conn.execute(query, (run_id,)).fetchall()
        return {row["error_class"]: row["n"] for row in rows}


def _row_to_verdict(row: sqlite3.Row) -> Verdict:
    data = dict(row)
    data["fails_at_base"] = (
        bool(data["fails_at_base"]) if data["fails_at_base"] is not None else None
    )
    data["passes_at_gold"] = (
        bool(data["passes_at_gold"]) if data["passes_at_gold"] is not None else None
    )
    return Verdict.model_validate(data)


class VerdictRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, verdict: Verdict) -> None:
        query = (
            "INSERT OR REPLACE INTO verdict ("
            "candidate_id, fails_at_base, passes_at_gold, verdict, computed_at"
            ") VALUES (?, ?, ?, ?, ?)"
        )
        fails_at_base = (
            int(verdict.fails_at_base) if verdict.fails_at_base is not None else None
        )
        passes_at_gold = (
            int(verdict.passes_at_gold) if verdict.passes_at_gold is not None else None
        )
        self._conn.execute(
            query,
            (
                verdict.candidate_id,
                fails_at_base,
                passes_at_gold,
                verdict.verdict,
                verdict.computed_at,
            ),
        )

    def counts(self, run_id: str) -> dict[str, int]:
        query = (
            "SELECT verdict.verdict AS verdict, COUNT(*) AS n "
            "FROM verdict JOIN candidate ON candidate.candidate_id = verdict.candidate_id "
            "WHERE candidate.run_id = ? GROUP BY verdict.verdict"
        )
        rows = self._conn.execute(query, (run_id,)).fetchall()
        return {row["verdict"]: row["n"] for row in rows}


class GuardrailRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insert(self, event: GuardrailEvent) -> None:
        query = (
            "INSERT INTO guardrail_event ("
            "event_id, candidate_id, attempted_path, rule, action, occurred_at"
            ") VALUES (?, ?, ?, ?, ?, ?)"
        )
        self._conn.execute(
            query,
            (
                event.event_id,
                event.candidate_id,
                event.attempted_path,
                event.rule,
                event.action,
                event.occurred_at,
            ),
        )

    def by_run(self, run_id: str) -> list[GuardrailEvent]:
        query = (
            "SELECT guardrail_event.* FROM guardrail_event "
            "JOIN candidate ON candidate.candidate_id = guardrail_event.candidate_id "
            "WHERE candidate.run_id = ?"
        )
        rows = self._conn.execute(query, (run_id,)).fetchall()
        return [GuardrailEvent.model_validate(dict(row)) for row in rows]


class FindingRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def replace_for_run(self, run_id: str, findings: list[Finding]) -> None:
        cap = get_settings().max_findings_per_run
        if len(findings) > cap:
            raise ValueError(f"Cannot replace findings for run {run_id}: got {len(findings)}, cap is {cap}.")
        delete_query = "DELETE FROM finding WHERE run_id = ?"
        self._conn.execute(delete_query, (run_id,))
        insert_query = (
            "INSERT INTO finding ("
            "finding_id, run_id, candidate_id, rank, title, explanation, repro_command, "
            "audit_cost_cents, cve_reference"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        rows = [
            (
                f.finding_id,
                f.run_id,
                f.candidate_id,
                f.rank,
                f.title,
                f.explanation,
                f.repro_command,
                f.audit_cost_cents,
                f.cve_reference,
            )
            for f in findings
        ]
        self._conn.executemany(insert_query, rows)

    def by_run(self, run_id: str) -> list[Finding]:
        query = "SELECT * FROM finding WHERE run_id = ? ORDER BY rank"
        rows = self._conn.execute(query, (run_id,)).fetchall()
        return [Finding.model_validate(dict(row)) for row in rows]


class MetricRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, snapshot: MetricSnapshot) -> None:
        query = (
            "INSERT OR REPLACE INTO metric_snapshot ("
            "snapshot_id, run_id, condition, n_denominator, n_verified, n_unverified_cand, "
            "n_error, rate, wilson_low, wilson_high, cost_usd_total, cost_per_verified, "
            "computed_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        self._conn.execute(
            query,
            (
                snapshot.snapshot_id,
                snapshot.run_id,
                snapshot.condition,
                snapshot.n_denominator,
                snapshot.n_verified,
                snapshot.n_unverified_cand,
                snapshot.n_error,
                snapshot.rate,
                snapshot.wilson_low,
                snapshot.wilson_high,
                snapshot.cost_usd_total,
                snapshot.cost_per_verified,
                snapshot.computed_at,
            ),
        )

    def by_run(self, run_id: str) -> list[MetricSnapshot]:
        query = "SELECT * FROM metric_snapshot WHERE run_id = ?"
        rows = self._conn.execute(query, (run_id,)).fetchall()
        return [MetricSnapshot.model_validate(dict(row)) for row in rows]


class PriorArtRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert_many(self, entries: list[PriorArt]) -> None:
        query = (
            "INSERT OR REPLACE INTO prior_art ("
            "key, label, reported_rate, denominator, condition_note, citation"
            ") VALUES (?, ?, ?, ?, ?, ?)"
        )
        rows = [
            (
                entry.key,
                entry.label,
                entry.reported_rate,
                entry.denominator,
                entry.condition_note,
                entry.citation,
            )
            for entry in entries
        ]
        self._conn.executemany(query, rows)

    def all(self) -> list[PriorArt]:
        query = "SELECT * FROM prior_art"
        rows = self._conn.execute(query).fetchall()
        return [PriorArt.model_validate(dict(row)) for row in rows]
