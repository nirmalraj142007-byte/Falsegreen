from __future__ import annotations


class FalseGreenError(Exception):
    code: str
    exit_code: int
    remedy: str

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.remedy)


class ConfigError(FalseGreenError):
    code = "config_error"
    exit_code = 2
    remedy = "Check your FALSEGREEN_ environment variables against falsegreen.config.Settings."


class MissingCredential(ConfigError):
    code = "missing_credential"
    exit_code = 2
    remedy = "Set the missing FALSEGREEN_* credential environment variable and retry."


class SandboxError(FalseGreenError):
    code = "sandbox_error"
    exit_code = 3
    remedy = "Check sandbox backend connectivity and credentials, then retry."


class ImageImportFailed(SandboxError):
    code = "image_import_failed"
    exit_code = 3
    remedy = "Verify the OCI image reference is correct and accessible, then retry the import."


class CheckpointBuildFailed(SandboxError):
    code = "checkpoint_build_failed"
    exit_code = 3
    remedy = "Inspect the checkpoint build log for the failing setup step and fix it."


class ForkFailed(SandboxError):
    code = "fork_failed"
    exit_code = 3
    remedy = "Confirm the source checkpoint exists and the concurrency ceiling has not been exceeded."


class ExecTimeout(SandboxError):
    code = "exec_timeout"
    exit_code = 3
    remedy = "Increase exec_timeout_multiplier in Settings or investigate a hanging process."


class QuotaExhausted(SandboxError):
    code = "quota_exhausted"
    exit_code = 3
    remedy = "Wait for sandbox quota to free up or reduce max_concurrency in Settings."


class ProviderError(FalseGreenError):
    code = "provider_error"
    exit_code = 4
    remedy = "Check the model provider's status page and your API credentials."


class RateLimited(ProviderError):
    code = "rate_limited"
    exit_code = 4
    remedy = "Back off and retry with a lower request rate."


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"
    exit_code = 4
    remedy = "Check the model provider's status page and retry later."


class SchemaInvalid(ProviderError):
    code = "schema_invalid"
    exit_code = 4
    remedy = "The model response failed schema validation; inspect the raw response and repair the prompt."


class RepoError(FalseGreenError):
    code = "repo_error"
    exit_code = 5
    remedy = "Check that the target repository is a supported, buildable Python project."


class SuiteRedAtBase(RepoError):
    code = "suite_red_at_base"
    exit_code = 5
    remedy = "Confirm the base commit's test suite passes before running an audit against it."


class NoTestCommand(RepoError):
    code = "no_test_command"
    exit_code = 5
    remedy = "Add a discoverable test command (e.g. pytest configuration) to the target repository."


class UnsupportedLanguage(RepoError):
    code = "unsupported_language"
    exit_code = 5
    remedy = "FalseGreen currently supports Python repositories only."


class BudgetExceeded(FalseGreenError):
    code = "budget_exceeded"
    exit_code = 6
    remedy = "Raise budget_usd_hard_stop in Settings or reduce the run's scope."


class GuardrailViolation(FalseGreenError):
    code = "guardrail_violation"
    exit_code = 0
    remedy = "This is an expected, recorded guardrail event, not a program failure."
