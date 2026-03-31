# ai-quality-lab

`ai-quality-lab` is a deterministic evaluation harness for AI workflows.  
It is designed as a public portfolio project to demonstrate practical quality engineering: reproducible scoring, structured reports, strong tests, and clear architecture.

## What This Project Demonstrates

- Building a clean Python `src`-layout project with `pyproject.toml`.
- Designing deterministic evaluators across multiple AI task types.
- Separating model inference concerns (adapters) from evaluation/scoring logic.
- Shipping practical developer ergonomics: CLI + JSON/Markdown reports + CI.

## Architecture Overview

```text
ai-quality-lab/
  datasets/                          # Public-safe example suites (JSON/YAML)
  src/ai_quality_lab/
    adapters/                        # Pluggable model adapters (offline-first)
    cli.py                           # CLI entrypoint
    loaders/                         # Dataset loading + validation
    models/                          # Core data models and typed expected outputs
    reports/                         # JSON and Markdown report writers
    scorers/                         # Deterministic scorer implementations
    simple_runner.py                 # Suite orchestration (adapter -> scorers -> results)
  tests/                             # Pytest suite
  .github/workflows/ci.yml           # Lint + test workflow
```

### Execution flow

1. Load one or more datasets.
2. Convert each case into a provider-agnostic `ModelRequest`.
3. Adapter returns prediction (offline adapters by default).
4. Scorers evaluate each case deterministically.
5. Runner aggregates suite metrics and failure reasons.
6. CLI writes detailed JSON + GitHub-friendly Markdown summary.

## Evaluation Philosophy

- **Deterministic first**: same inputs should produce the same score.
- **Transparent scoring**: each check returns pass/fail, numeric score, explanation, and details.
- **Failure-oriented reporting**: summaries highlight top reasons for failed checks.
- **Offline by default**: core harness works without paid APIs or external services.

## Supported Task Types

- `summarization`
- `classification`
- `extraction`
- `compliance` (style/policy compliance)

## Dataset Format

Datasets are JSON or YAML files with this shape:

```json
{
  "suite_name": "example_suite",
  "description": "short description",
  "cases": [
    {
      "id": "case-1",
      "task": "summarization",
      "input": {"text": "synthetic input"},
      "expected": "expected output",
      "checks": [
        {"type": "exact_match", "config": {"case_sensitive": true}}
      ],
      "prediction": "optional fixed prediction for offline runs",
      "metadata": {"optional": "context"}
    }
  ]
}
```

### Task-specific `expected` shapes

- **summarization**: string or `{ "summary": "..." }`
- **classification**: string label or `{ "label": "...", "allowed_labels": ["..."] }`
- **extraction**: object fields or `{ "fields": {...}, "required_fields": ["..."] }`
- **compliance**: `"compliant" | "non-compliant"` or `{ "verdict": "...", "policy_id": "...", "required_terms": [...] }`

See `datasets/` for compact public-safe examples.

## Scorer Overview

Deterministic scorers are implemented in `src/ai_quality_lab/scorers/simple.py`:

- `exact_match`: strict equality, optional case insensitivity.
- `allowed_labels`: validates allowed set and expected label with partial credit.
- `regex_constraints`: regex/required/forbidden/length checks with penalty-based scoring.
- `schema_validation`: JSON-schema-like structural validation.
- `field_extraction`: field-by-field comparison for structured extraction outputs.
- `rubric`: weighted deterministic criteria.

## CLI Usage

Install locally:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
```

Run a single dataset:

```bash
ai-quality-lab eval --dataset datasets/minimal_suite.json --adapter dataset --out-dir reports
```

Run a directory of datasets:

```bash
ai-quality-lab eval --datasets-dir datasets --out-dir reports --min-pass-rate 0.8 --min-average-score 0.8
```

Run recursively:

```bash
ai-quality-lab eval --datasets-dir datasets --recursive --out-dir reports --min-pass-rate 0.8 --min-average-score 0.8
```

### Adapter options

- `dataset` (default): uses case-level `prediction`, falls back to expected value.
- `echo`: echoes text-like input for local debugging.
- `mock`: deterministic local heuristics by task.

Output files:

- `reports/eval_results.json` (detailed case-level output)
- `reports/eval_summary.md` (readable summary table)

Exit codes:

- `0`: thresholds met
- `2`: threshold failure
- `1`: operational issue (for example, no dataset files found)

## Test Strategy

Tests are designed to be readable and close to behavior:

- `tests/test_loaders.py`: format handling + validation failures.
- `tests/test_scorers_simple.py`: coverage for each scorer and scorer mapping.
- `tests/test_reports_simple.py`: JSON and Markdown report content checks.
- `tests/test_cli_behavior.py`: CLI outputs, thresholds, and failure paths.
- `tests/test_adapters_simple.py`: adapter boundary behavior without live APIs.

The suite avoids overmocking; most tests run real code paths with synthetic data fixtures.

Run tests:

```bash
pytest
```

## CI

GitHub Actions workflow: `.github/workflows/ci.yml`

- Runs on `push` and `pull_request`
- Lint job: `ruff check .`
- Test job: `pytest` on Python 3.10 and 3.11
- Uses pip dependency caching for faster runs

Status badge template (replace `OWNER/REPO` after publishing):

```markdown
[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
```

## Optional OpenAI Adapter

Provider code is isolated in `src/ai_quality_lab/adapters/openai_optional.py` and is not required for core functionality.

Optional install:

```bash
pip install -e .[providers]
```

Environment variables:

- `OPENAI_API_KEY` (required)
- `AI_QUALITY_LAB_OPENAI_MODEL` (optional, default `gpt-4o-mini`)

## Future Improvements

- Add trend comparison across runs (historical benchmark tracking).
- Add richer schema support and task-specific metric plugins.
- Add optional coverage upload/artifacts in CI.
- Add typed configuration files for evaluation presets.
- Add lightweight docs site with sample reports and walkthroughs.

## Portfolio Strengths This Repo Demonstrates

- **Quality-first AI engineering**: deterministic checks with explicit pass/fail logic.
- **Clear system boundaries**: adapters isolated from scorers and reporting.
- **Offline reliability**: core harness runs without paid APIs or network dependencies.
- **Practical tooling**: CLI, structured JSON output, readable markdown summaries.
- **Test discipline**: behavior-focused tests across loaders, scorers, reports, and CLI.
- **Maintainability**: explicit models and minimal abstractions for easy extension.

## Likely Interview Questions

- Why did you prioritize deterministic scoring first?
- How does the adapter boundary prevent provider-specific leakage into evaluation logic?
- How would you evolve this into semantic/LLM-judge evaluation without losing reliability?
- How do you validate dataset quality and avoid brittle tests?
- Why both JSON and markdown reports?
- How do threshold-based exits improve CI quality gates?
- What design tradeoffs did you choose for readability vs flexibility?

## Suggested Answers (Notes)

- **Why deterministic first**
  - Creates a stable, reproducible baseline for quality.
  - Makes regressions easy to detect in CI.
  - Builds trust before adding subjective scoring layers.

- **How boundaries are enforced**
  - Runner converts cases into provider-agnostic requests.
  - Adapters only produce predictions.
  - Scorers never reference provider SDKs or transport details.

- **How to extend toward semantic eval**
  - Keep deterministic checks as non-negotiable guardrails.
  - Add semantic scorers as optional modules.
  - Benchmark semantic outputs against labeled datasets.

- **How dataset quality is managed**
  - Strict loader validation and task-specific expected schemas.
  - Public-safe synthetic examples for reproducibility.
  - Negative tests for malformed payloads and invalid configs.

- **Why JSON + markdown reports**
  - JSON supports automation and tooling integration.
  - Markdown supports quick human review and debugging.
  - Top failure reasons focus attention on actionable defects.

- **How thresholds support delivery quality**
  - Convert quality expectations into objective release gates.
  - Prevent silent regressions when datasets evolve.
  - Allow progressive tightening as model behavior improves.

- **Readability vs flexibility tradeoff**
  - Prefer explicit registries and typed models over heavy frameworks.
  - Optimize for explainability in interviews and onboarding.
  - Keep extension points small and intentional.
