# Requirement 79 - Owner-Grounded Embodied Prompt and Structured-Thought Robustness

## 1. Task Breakdown

### T1 - Robust structured-thought JSON extraction (`11`)
Add `_extract_structured_json(text) -> str` in `internal_thought/engine.py` (strip
`<think>...</think>`, strip ```` ```json ```` / ```` ``` ```` fence, return first-`{`-to-last-`}`
substring or `""`), and call it at the start of `_parse_structured_thought` before `json.loads`.
Unconditionally active (identity on clean JSON). Add unit tests for the five extraction cases plus
the parse-and-fail-fast cases.

### T2 - Thought token budget
Raise the thought `LlmProfile.max_tokens` in `default_composition_config()` to `2048` so a
reasoning model is not truncated before the JSON. Confirm fake-provider LLM tests ignore
`max_tokens` and stay green.

### T3 - v3 owner-grounded embodied prompt path (`16`)
Add `OwnerGroundedEmbodiedPromptPath` in `prompt_contract/engine.py` (seven layers, v3 bootstrap-id
guard, natural-language schema, hard rules, upgraded anti-theatrical rule; identity rendered from
`identity_self_summary`, attention from `attention_field`, channels from `ready_channels`). Export
it. v1 path untouched. Unit tests for layer rendering, identity-from-injection, bootstrap guard.

### T4 - RuntimeProfile flag + additive request keys
Add `RuntimeProfile.embodied_prompt_mode: str = "v1"` (validate `"v1"`/`"v3"`). Confirm the v3
path reads the additive keys (`identity_self_summary`, `attention_field`, `ready_channels`) and
fails fast when absent under v3.

### T5 - Composition wiring + owner-neutral projections
In `composition/bridges.py` extend the embodied-prompt request bridge to fill the three additive
keys under v3 (projections `_attention_field_from_frame` from `07`/`08`, `_ready_channels_from_frame`
from channel-state with `available_channels` fallback, `_identity_self_summary_from_carry` from the
R68 governance carry). In `runtime_assembly.py`, under `embodied_prompt_mode == "v3"` build the
engine with the v3 path + v3 bootstrap id and the larger thought `max_tokens`. Integration test:
`assemble_runtime(embodied_prompt_mode="v3")` runs one tick; default `v1` byte-for-byte unchanged.

### T6 - Documentation sync
Update `index.md` (row 79 maturity), `OWNER_GUIDE.*` (`16` and `11` entries), `PROGRESS_FLOW.*`
(S16/S11 notes + sync line R79), `ARCHITECTURE_BOUNDARIES.md` (§4 migration note).

### T7 - Opt-in real-LLM smoke (not in CI)
A `scripts/`-level probe (reuse `run_llm_prompt_probe.py`) confirming the v3 path + a reasoning
model yields a parseable structured thought end to end.

## 2. Dependencies

1. T1, T2, T3 are independent of each other.
2. T4 precedes T5; T5 depends on T3 + T4.
3. T6 after T1-T5; T7 after T5.
4. External: `16` prompt owner, `11` thought owner, `14` carry (R68), `22` composition, `25` LLM
   profile. No new owner; no top-level contract field added/removed.

## 3. Files and Modules

1. `src/helios_v2/internal_thought/engine.py` (T1)
2. `src/helios_v2/composition/runtime_assembly.py` (T2, T5)
3. `src/helios_v2/prompt_contract/engine.py`, `prompt_contract/__init__.py` (T3)
4. `src/helios_v2/composition/profile.py` (T4)
5. `src/helios_v2/composition/bridges.py` (T5)
6. `tests/test_internal_thought_engine.py` (+ new), `tests/test_prompt_contract_v2.py` (+ new),
   `tests/test_runtime_composition.py` (+ new)
7. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`/`.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`/`.zh-CN.md`,
   `docs/ARCHITECTURE_BOUNDARIES.md` (T6)

## 4. Implementation Order

T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7.

## 5. Validation Plan

1. After T1: `pytest helios_v2/tests/test_internal_thought_engine.py -q` green (extraction + parse).
2. After T2: `pytest helios_v2/tests/test_llm_engine.py helios_v2/tests/test_internal_thought_engine.py -q` green.
3. After T3: `pytest helios_v2/tests/test_prompt_contract_v2.py -q` green.
4. After T5: `pytest helios_v2/tests/test_runtime_composition.py -q` green; default assembly regression green.
5. Guards + full: `pytest helios_v2/tests/test_composition_owner_boundary_guard.py helios_v2/tests/test_no_adhoc_logging_guard.py -q` and `pytest helios_v2/tests -q` green.

## 6. Completion Criteria

1. `11` parses `<think>`/fenced/clean JSON and fail-fasts on no-JSON (acceptance 3, 4).
2. v3 path renders identity from injection with no hardcoded identity literal; natural-language
   schema + hard rules; bootstrap guard (acceptance 1, 2).
3. Default `v1` assembly byte-for-byte unchanged; full network-free suite + both guards green
   (acceptance 5).
4. `index.md`, `OWNER_GUIDE.*`, `PROGRESS_FLOW.*`, `ARCHITECTURE_BOUNDARIES.md` updated, sync lines
   name R79 (acceptance 7).
5. Opt-in real-LLM smoke shows a parseable v3 structured thought (acceptance 6).
