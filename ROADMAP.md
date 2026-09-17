# Portfolio milestones

The goal is a small investigation system whose conclusions can be inspected and
tested. A generated explanation alone is not evidence of correctness.

## 1. Evidence-rich deterministic baseline — implemented

- Collect structured synthetic logs and deployment changes alongside health and metrics.
- Cite collected evidence for every finding.
- Distinguish observed symptoms from probable causes; a deployment near an incident
  is not, by itself, proof of causation.
- Abstain when logs or changes do not support a specific explanation.
- Keep collection read-only and bounded, with regression tests.

## 2. Model-driven investigation — implemented, live validation pending

- Introduce a model adapter separately from the existing deterministic policy.
- Allow the model to select only explicitly registered read-only tools.
- Enforce step budgets and timeouts outside the model.
- Record tool requests, observations, and final evidence references.
- Keep offline tests runnable without credentials. Select the live model route
  separately; no paid provider is assumed or required by the baseline.

## 3. Evaluation

- Build 15–20 cases, including missing evidence, conflicting observations,
  unrelated deployments, and misleading log messages.
- Reserve cases not used while tuning investigation rules or prompts.
- Compare the deterministic baseline and model investigator on identical inputs.
- Report supported diagnoses, unsupported causal claims, abstentions, tool calls,
  and elapsed time. Publish failures, not just successful examples.
- Do not call fixture-based performance production accuracy.

## 4. Presentation

- Offline CI and a reproducible quick start are implemented.
- Record a short demonstration and explain an ambiguous case.
- Document architecture, limitations, and AI-assisted implementation.
- Add MCP through an existing SDK only when a concrete client needs it.

## Interview checkpoints

Explain how an observation differs from a hypothesis, why the tool budget is
enforced in code, how evidence citations can be validated, and what the model
adds over fixed rules. Be able to modify a scenario and its test without relying
on a generated explanation.
