-- Benchmark instances, including exclusions. The published denominator lives here.
CREATE TABLE instance (
  instance_id              TEXT PRIMARY KEY,   -- e.g. 'django__django-11099'
  source                   TEXT NOT NULL,      -- 'swebench_verified' | 'post_cutoff'
  repo                     TEXT NOT NULL,
  base_commit              TEXT NOT NULL,
  environment_setup_commit TEXT,
  gold_patch               TEXT NOT NULL,
  test_patch               TEXT,
  fail_to_pass             TEXT NOT NULL,      -- JSON array
  pass_to_pass             TEXT,               -- JSON array
  issue_text               TEXT,               -- withheld in cold/oracle conditions
  merged_at                TEXT,               -- required for post_cutoff provenance
  days_to_report           INTEGER,            -- powers the '91 days later' caption
  included                 INTEGER NOT NULL,   -- 0/1 -- FalseGreen Filter v1
  exclusion_reason         TEXT                -- 'empty_f2p'|'suite_red_at_base'|
                                               -- 'zero_coverage'|'service_restart_failed'
);
CREATE INDEX idx_instance_source_included ON instance(source, included);
CREATE INDEX idx_instance_repo            ON instance(repo);

-- One warm checkpoint per (repo, env commit). Built once; forked thousands of times.
CREATE TABLE checkpoint (
  checkpoint_id    TEXT PRIMARY KEY,
  repo             TEXT NOT NULL,
  env_commit       TEXT NOT NULL,
  contree_image_id TEXT NOT NULL,   -- provenance: proves it ran on Contree
  image_tag        TEXT NOT NULL,
  python_version   TEXT NOT NULL,
  test_command     TEXT NOT NULL,   -- deterministically detected, never model-chosen
  services_script  TEXT,            -- filesystem-only snapshots don't preserve processes
  suite_green      INTEGER NOT NULL,
  build_seconds    REAL NOT NULL,   -- the number that justifies the whole design
  built_at         TEXT NOT NULL,
  UNIQUE(repo, env_commit)
);

CREATE TABLE run (
  run_id           TEXT PRIMARY KEY,
  mode             TEXT NOT NULL,   -- 'audit' | 'bench'
  condition        TEXT NOT NULL,   -- 'cold'|'oracle'|'with_issue'|'baseline'
  backend          TEXT NOT NULL,   -- 'contree' | 'docker'  (docker never published)
  falsegreen_sha   TEXT NOT NULL,
  models_toml_hash TEXT NOT NULL,
  seed             INTEGER,
  temperature      REAL,
  started_at       TEXT NOT NULL,
  finished_at      TEXT,
  status           TEXT NOT NULL,   -- 'running'|'complete'|'partial'|'aborted'|'degraded'
  token_cost_usd   REAL DEFAULT 0,
  compute_cost_usd REAL DEFAULT 0,
  notes            TEXT
);
CREATE INDEX idx_run_condition_status ON run(condition, status);

CREATE TABLE candidate (
  candidate_id  TEXT PRIMARY KEY,
  run_id        TEXT NOT NULL REFERENCES run(run_id),
  instance_id   TEXT REFERENCES instance(instance_id),  -- NULL in audit mode
  ordinal       INTEGER NOT NULL,
  target_file   TEXT,
  target_symbol TEXT,
  hypothesis    TEXT NOT NULL,
  input_class   TEXT,
  test_code     TEXT NOT NULL,
  test_path     TEXT NOT NULL,
  model         TEXT NOT NULL,      -- resolved slug, not 'ultra'
  prompt_hash   TEXT NOT NULL,
  tokens_in     INTEGER,
  tokens_out    INTEGER,
  gen_seconds   REAL,
  UNIQUE(run_id, instance_id, ordinal)
);
CREATE INDEX idx_candidate_run      ON candidate(run_id);
CREATE INDEX idx_candidate_instance ON candidate(instance_id);

CREATE TABLE execution (
  execution_id        TEXT PRIMARY KEY,
  candidate_id        TEXT NOT NULL REFERENCES candidate(candidate_id),
  phase               TEXT NOT NULL,      -- 'base' | 'gold'
  checkpoint_id       TEXT REFERENCES checkpoint(checkpoint_id),
  fork_id              TEXT,              -- Contree fork identifier
  provider_request_id TEXT,               -- surfaced in the Provenance panel
  was_fork             INTEGER NOT NULL,  -- powers the >=95% fork-ratio claim
  exit_code            INTEGER,
  stdout_tail          TEXT,              -- last 4KB only
  duration_ms          INTEGER,
  cpu_ms                INTEGER,          -- Contree metering, not a stopwatch
  mem_peak_mb           REAL,
  io_bytes               INTEGER,
  cost_cents            REAL,
  retries               INTEGER DEFAULT 0,
  error_class           TEXT              -- 'timeout'|'429'|'5xx'|'fork_failed'|NULL
);
CREATE INDEX idx_execution_candidate ON execution(candidate_id, phase);
CREATE INDEX idx_execution_error     ON execution(error_class);

CREATE TABLE verdict (
  candidate_id   TEXT PRIMARY KEY REFERENCES candidate(candidate_id),
  fails_at_base  INTEGER,
  passes_at_gold INTEGER,
  verdict        TEXT NOT NULL,  -- 'verified'|'unverified_candidate'|
                                 -- 'no_fail_at_base'|'error'|'guardrail_blocked'
  computed_at    TEXT NOT NULL
);
CREATE INDEX idx_verdict_value ON verdict(verdict);

CREATE TABLE guardrail_event (
  event_id       TEXT PRIMARY KEY,
  candidate_id   TEXT NOT NULL REFERENCES candidate(candidate_id),
  attempted_path TEXT NOT NULL,
  rule           TEXT NOT NULL,   -- 'path_allowlist'
  action         TEXT NOT NULL,   -- 'rejected'
  occurred_at    TEXT NOT NULL
);
CREATE INDEX idx_guardrail_candidate ON guardrail_event(candidate_id);

-- Product mode only. Max 3 per run.
CREATE TABLE finding (
  finding_id       TEXT PRIMARY KEY,
  run_id           TEXT NOT NULL REFERENCES run(run_id),
  candidate_id     TEXT NOT NULL REFERENCES candidate(candidate_id),
  rank             INTEGER NOT NULL,
  title            TEXT NOT NULL,
  explanation      TEXT NOT NULL,      -- written only AFTER verdict == verified
  repro_command    TEXT NOT NULL,
  audit_cost_cents REAL NOT NULL,
  cve_reference    TEXT,               -- nullable, non-blocking enrichment
  UNIQUE(run_id, rank)
);

-- Pre-computed so the static dashboard does no arithmetic at render time.
CREATE TABLE metric_snapshot (
  snapshot_id       TEXT PRIMARY KEY,
  run_id            TEXT NOT NULL REFERENCES run(run_id),
  condition         TEXT NOT NULL,
  n_denominator     INTEGER NOT NULL,   -- N_fg, never 500
  n_verified        INTEGER NOT NULL,
  n_unverified_cand INTEGER NOT NULL,
  n_error           INTEGER NOT NULL,
  rate              REAL NOT NULL,
  wilson_low        REAL NOT NULL,
  wilson_high       REAL NOT NULL,
  cost_usd_total    REAL NOT NULL,
  cost_per_verified REAL,
  computed_at       TEXT NOT NULL
);

-- Published comparison line. Hand-curated and cited.
CREATE TABLE prior_art (
  key            TEXT PRIMARY KEY,
  label          TEXT NOT NULL,
  reported_rate  REAL,
  denominator    INTEGER,
  condition_note TEXT NOT NULL,      -- what the model was given, e.g. 'issue description available'
  citation       TEXT NOT NULL
);
