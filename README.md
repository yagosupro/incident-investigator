# Incident Investigator

A small, reproducible backend incident investigation lab. The goal is to demonstrate evidence-based diagnosis, bounded tool execution, and honest uncertainty—not to claim that an LLM can autonomously repair production.

## MVP scope

- Synthetic backend incidents: normal operation, slow responses, and server errors.
- Structured evidence and read-only diagnostic tools.
- A bounded investigation that cites evidence and can return insufficient evidence.
- Offline, deterministic execution without API keys or paid services.

**This first version is a deterministic diagnostic baseline, not an LLM agent.** A later model-driven investigator should be compared against this baseline on the same scenarios. No model accuracy or cost savings are claimed.

## Run

From this directory, with Python 3.10 or newer (no dependencies):

```sh
python3 -m incident_investigator demo
python3 -m incident_investigator demo --scenario error
python3 -m incident_investigator demo --scenario unknown
python3 -m unittest discover -s tests -v
```

The implementation uses Python for a zero-install first demo. A Java service is a possible later target, not a prerequisite for investigating structured backend evidence.

## Design boundaries

The diagnostic system observes a synthetic lab. It does not connect to production, restart services, modify configuration, or publish anything. Evidence must support a conclusion; an HTTP 500 alone does not establish a root cause. Known lab causes are not proof of general diagnostic ability.

## Next milestones

1. Add a model-driven tool-selection loop with a fixed step budget and explicit timeout handling.
2. Expand to held-out scenarios, ambiguous evidence, and misleading log text.
3. Measure supported diagnoses, abstentions, unsupported claims, tool calls, and runtime against the deterministic baseline.
4. Expose selected read-only tools through an existing MCP SDK if interoperability adds value.
5. Record a short demo and document failures and tradeoffs before presenting this as a finished portfolio project.

## Architecture and current limitations

`CLI → Investigator → ReadOnlyTools → localhost HTTP lab`

The lab starts on an ephemeral loopback port and shuts down after each run.
Reports contain observations, evidence IDs, timings, and the two tool calls.
The health endpoint includes an actual delay in the slow scenario; metrics are
synthetic fixtures, not production measurements. No logs or release history
are collected yet. Network timeouts propagate to the caller; failed attempts
consume the tool budget. A root cause is deliberately not inferred from symptoms.

This initial implementation was built with AI assistance and is being developed
as a learning project, not presented as independently authored production work.

## Interview walkthrough

Be prepared to explain why a diagnosis follows from particular evidence, when the system should abstain, how tool budgets are enforced, and what changes when the deterministic investigator is replaced by a model. AI-assisted implementation should be described honestly; familiarity with the code matters more than a large generated repository.
