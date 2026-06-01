# Helios v2 API And Ops Contract Guide

## 1. Purpose

This document standardizes how Helios v2 modules expose APIs and ops contracts.

It exists to keep module boundaries explicit, keep ownership narrow, and prevent cross-domain leakage through undocumented helpers or ad-hoc payloads.

This guide is mandatory for all new Helios v2 modules.

## 2. Core Rules

1. Every module must have one semantic owner.
2. A module may expose public APIs, public ops contracts, or both.
3. Cross-module collaboration must use those public surfaces only.
4. Public interfaces must be documented with comments or docstrings.
5. A module must explicitly state what it owns and what it does not own.
6. If a capability is not stable enough to document, it must not be exposed as a public cross-module interface.

## 3. API Versus Ops

Use an API when:

1. another module needs a synchronous query or command against a stable owner,
2. the call is local to the runtime and does not represent a transportable action intent,
3. typed return values are clearer than an operation envelope.

Use an ops contract when:

1. the call represents a named action or command that may be routed, validated, logged, or rejected,
2. the interaction crosses an execution boundary,
3. provenance, policy review, or auditability matters,
4. the caller should not know the callee's private implementation shape.

## 4. Owner Declaration Template

Every owner module should start with a short declaration in module docstring form:

```python
"""Owner: sensory ingress.

Owns:
- external and internal stimulus normalization
- normalized stimulus API

Does not own:
- salience scoring
- memory retrieval
- action routing
"""
```

This declaration is mandatory for modules that expose cross-module APIs or ops.

## 5. Public API Rules

### 5.1 API shape

1. Keep public APIs small.
2. Prefer typed inputs and typed outputs.
3. Avoid generic `dict[str, object]` unless the contract is inherently open-ended and documented field-by-field.
4. Public APIs must not expose mutable private state references.
5. Public APIs must raise explicit exceptions for hard-stop conditions.

### 5.2 API documentation format

Each public API method or protocol method must have a docstring containing these fields in plain language:

1. `Owner` - who semantically owns this interface.
2. `Purpose` - what the interface does.
3. `Inputs` - required inputs and important constraints.
4. `Returns` - output shape and meaning.
5. `Raises` - hard-stop conditions or explicit errors.
6. `Notes` - anything the caller must not assume.

Recommended template:

```python
def get_stimuli(self) -> list[Stimulus]:
    """Owner: sensory ingress.

    Purpose:
        Return the normalized stimuli collected for the current cycle.

    Inputs:
        None.

    Returns:
        A list of normalized `Stimulus` objects owned by sensory ingress.

    Raises:
        RuntimeAbortError if stimulus collection is incomplete or invalid for the current cycle.

    Notes:
        Callers must not mutate returned objects in place unless the contract explicitly allows it.
    """
```

## 6. Ops Contract Rules

### 6.1 When to define an op

Define a named op when the interaction must be:

1. serializable or inspectable,
2. policy-checkable,
3. attributable to a source owner,
4. replayable or auditable.

### 6.2 Required op fields

Every op contract must document, at minimum:

1. `op_name` - stable command name.
2. `owner` - owner module exposing or consuming the op.
3. `purpose` - why the op exists.
4. `inputs` - required payload fields.
5. `output` or `result` - expected success shape.
6. `failure_semantics` - reject, abort, or hard-stop behavior.
7. `provenance` - how source ownership is tracked.

Recommended typed model pattern:

```python
@dataclass(frozen=True)
class RouteActionOp:
    """Owner: executive arbitration.

    Purpose:
        Describe one approved externalizable action for routing and execution.

    Failure semantics:
        Invalid routing targets raise a hard-stop contract error. Missing critical execution capabilities abort the path.
    """

    op_name: str
    origin_owner: str
    action_kind: str
    payload: Mapping[str, object]
    provenance_id: str
```

### 6.3 Ops naming rules

1. Use stable, domain-meaningful names.
2. Use verbs for commands and nouns only for snapshots or reports.
3. Avoid legacy compatibility names from Helios v1 unless the same semantics are intentionally preserved.
4. Do not overload one op name with multiple unrelated meanings.

## 7. Commenting Rules

1. Public module docstrings explain ownership.
2. Public classes explain role and failure semantics.
3. Public methods explain inputs, outputs, and raised errors.
4. Complex invariants may use a short inline comment directly above the relevant block.
5. Do not add low-value comments that restate obvious syntax.

## 8. Design-First Workflow Requirements

Before code lands for a new module or interface, the following must already exist:

1. requirement text naming the behavioral boundary,
2. design text naming the owner and interface shape,
3. task text naming touched files and validation commands.

Code review for Helios v2 should reject implementation that introduces:

1. undocumented public interfaces,
2. cross-module helper reach-through,
3. unnamed ops payloads,
4. owner ambiguity,
5. fallback behavior hidden behind interface defaults.

## 9. Review Checklist

Use this checklist before merging any new module or interface:

1. Is the owner explicit?
2. Is the module boundary narrow?
3. Is the interface exposed as API or op for a clear reason?
4. Are public methods and models documented?
5. Are hard-stop and reject semantics explicit?
6. Is provenance captured where cross-boundary actions occur?
7. Does the requirement and design text already define this interface?

## 10. Initial v2 Convention

Until a richer contract system is introduced, Helios v2 should prefer:

1. Python protocols for owner-facing APIs.
2. Frozen dataclasses for public snapshots and ops payloads.
3. Explicit exceptions for startup and runtime abort semantics.
4. Small, typed module surfaces over generic unstructured payloads.