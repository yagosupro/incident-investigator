# Incident Investigator

A small, reproducible backend incident investigation lab. The goal is to demonstrate evidence-based diagnosis, bounded tool execution, and honest uncertainty—not to claim that an LLM can autonomously repair production.

## MVP scope

- Synthetic backend incidents: normal operation, slow responses, server errors, and a release regression.
- Structured evidence and read-only diagnostic tools.
- A bounded investigation that cites evidence and can return insufficient evidence.
- Offline, deterministic execution without API keys or paid services.

**Two modes are available:** an offline deterministic baseline and a model-directed loop using a local Ollama server. The loop has been tested with scripted responses, but real model inference and diagnostic quality have not yet been verified. No model accuracy or cost savings are claimed.

## Run

From this directory, with Python 3.10 or newer (no dependencies):

```sh
python3 -m incident_investigator demo
python3 -m incident_investigator demo --scenario release_regression
python3 -m incident_investigator demo --scenario error
python3 -m incident_investigator demo --scenario unknown
python3 -m unittest discover -s tests -v
```

The implementation uses Python for a zero-install first demo. A Java service is a possible later target, not a prerequisite for investigating structured backend evidence.

## Design boundaries

The diagnostic system observes a synthetic lab. It does not connect to production, restart services, modify configuration, or publish anything. Evidence must support a conclusion; an HTTP 500 alone does not establish a root cause. Known lab causes are not proof of general diagnostic ability.

## Next milestones

1. Run and evaluate the implemented model-driven loop with an explicitly selected local model.
2. Expand to held-out scenarios, ambiguous evidence, and misleading log text.
3. Measure supported diagnoses, abstentions, unsupported claims, tool calls, and runtime against the deterministic baseline.
4. Expose selected read-only tools through an existing MCP SDK if interoperability adds value.
5. Record a short demo and document failures and tradeoffs before presenting this as a finished portfolio project.

## Architecture and current limitations

`CLI → Investigator → ReadOnlyTools → localhost HTTP lab`

The lab starts on an ephemeral loopback port and shuts down after each run.
Reports contain observations, evidence IDs, timings, and four bounded tool calls:
`health`, `metrics`, `logs`, and `releases`. The health endpoint includes an actual
delay in the slow scenario; metrics, structured logs, and release history are
synthetic fixtures, not production measurements.

In `release_regression`, a schema-validation error names the current release,
whose change list includes checkout schema validation. The fixed rule reports a
**probable**, not proven, regression and cites both log and release evidence.
In `error`, HTTP 500 is reported only as an observed symptom, without a causal
diagnosis. Temporal proximity alone is not used to infer a cause.

This is a narrow fixture-specific rule, not general root-cause analysis. Network
timeouts propagate to the caller; failed attempts consume the tool budget.
See [ROADMAP.md](ROADMAP.md) for the remaining milestones.

This initial implementation was built with AI assistance and is being developed
as a learning project, not presented as independently authored production work.

## Interview walkthrough

Be prepared to explain why a diagnosis follows from particular evidence, when the system should abstain, how tool budgets are enforced, and what changes when the deterministic investigator is replaced by a model. AI-assisted implementation should be described honestly; familiarity with the code matters more than a large generated repository.

## Local model mode (live inference not yet verified)

Requires an already running Ollama server at `127.0.0.1:11434` and an already
installed model. Replace `YOUR_LOCAL_MODEL` with its exact name:

```sh
python3 -m incident_investigator agent --model YOUR_LOCAL_MODEL --scenario release_regression --max-steps 8
```

The model chooses among `health`, `metrics`, `logs`, and `releases`. The host
enforces four tool calls and eight model decisions by default, records a trace,
and rejects malformed actions and citations to evidence it has not collected.
Model request timeout is 10 seconds; tool timeout is 1 second. Model-path failures
produce a structured report and nonzero exit status. The CLI never installs or
downloads models and has no paid-provider fallback.

Citation checking validates IDs, **not whether the evidence supports a claim**.
All accepted claims remain labeled model-generated. See [MODEL_DESIGN.md](MODEL_DESIGN.md).
The GitHub Actions workflow runs the offline suite on Python 3.10 and 3.12.
