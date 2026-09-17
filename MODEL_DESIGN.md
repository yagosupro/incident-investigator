# Model integration boundaries

The deterministic investigator remains the comparison baseline. The model path
lets a model choose evidence tools rather than following a fixed collection plan.
Both investigate synthetic data only; neither performs remediation.

## Existing solution choice

Use the existing [Ollama chat API](https://docs.ollama.com/api/chat), rather than
building an inference server or assuming a paid provider. A small stdlib adapter
keeps this four-tool learning lab dependency-free. An orchestration framework can
be reconsidered if durable workflows or more complex tool graphs become necessary.

The repository does not install Ollama, download weights, provision compute, or
include any credentials. A running local model is a separate prerequisite.

## What validation can and cannot establish

- Tool allowlisting limits which diagnostic operations are executable.
- Step and tool budgets bound repeated requests independently of model intent.
- Evidence-reference validation can reject citations to nonexistent evidence.
- Valid citations **do not prove** that the cited evidence supports the claim.
- Logs are untrusted input. Prompt instructions are not a complete defense against
  prompt injection; the executable tool boundary remains narrow and read-only.
- Scripted-model tests validate orchestration, not live model quality, reliability,
  resistance to misleading text, or diagnostic accuracy.

## Live evaluation still required

Record the exact model and runtime, run both clear and ambiguous incidents, inspect
the trace, and score claims against evidence. Publish failures as well as successes.
Do not describe offline adapter tests as a demonstrated autonomous LLM investigation.
