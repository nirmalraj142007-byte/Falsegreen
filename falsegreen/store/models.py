from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Instance(BaseModel):
    model_config = ConfigDict(frozen=True)

    instance_id: str
    source: str
    repo: str
    base_commit: str
    environment_setup_commit: str | None = None
    gold_patch: str
    test_patch: str | None = None
    fail_to_pass: list[str]
    pass_to_pass: list[str] | None = None
    issue_text: str | None = None
    merged_at: str | None = None
    days_to_report: int | None = None
    included: bool
    exclusion_reason: str | None = None


class Checkpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    repo: str
    env_commit: str
    contree_image_id: str
    image_tag: str
    python_version: str
    test_command: str
    services_script: str | None = None
    suite_green: bool
    build_seconds: float
    built_at: str


class Run(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    mode: str
    condition: str
    backend: str
    falsegreen_sha: str
    models_toml_hash: str
    seed: int | None = None
    temperature: float | None = None
    started_at: str
    finished_at: str | None = None
    status: str
    token_cost_usd: float = 0
    compute_cost_usd: float = 0
    notes: str | None = None


class Candidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    run_id: str
    instance_id: str | None = None
    ordinal: int
    target_file: str | None = None
    target_symbol: str | None = None
    hypothesis: str
    input_class: str | None = None
    test_code: str
    test_path: str
    model: str
    prompt_hash: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    gen_seconds: float | None = None


class Execution(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: str
    candidate_id: str
    phase: str
    checkpoint_id: str | None = None
    fork_id: str | None = None
    provider_request_id: str | None = None
    was_fork: bool
    exit_code: int | None = None
    stdout_tail: str | None = None
    duration_ms: int | None = None
    cpu_ms: int | None = None
    mem_peak_mb: float | None = None
    io_bytes: int | None = None
    cost_cents: float | None = None
    retries: int = 0
    error_class: str | None = None


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    fails_at_base: bool | None = None
    passes_at_gold: bool | None = None
    verdict: str
    computed_at: str


class GuardrailEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    candidate_id: str
    attempted_path: str
    rule: str
    action: str
    occurred_at: str


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    finding_id: str
    run_id: str
    candidate_id: str
    rank: int
    title: str
    explanation: str
    repro_command: str
    audit_cost_cents: float
    cve_reference: str | None = None


class MetricSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    run_id: str
    condition: str
    n_denominator: int
    n_verified: int
    n_unverified_cand: int
    n_error: int
    rate: float
    wilson_low: float
    wilson_high: float
    cost_usd_total: float
    cost_per_verified: float | None = None
    computed_at: str


class PriorArt(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    reported_rate: float | None = None
    denominator: int | None = None
    condition_note: str
    citation: str
