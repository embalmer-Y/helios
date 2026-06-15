# R96 Real Semantic Embedding — Real-LLM Probe Results

> **Status (2026-06-15)**: in-progress. The **network-free B2 closure focused tests** in `tests/r96_b2_closure.py` (3 tests, CI surface) have run with full evidence; the **real-LLM probe** in `scripts/r96_b2_real_llm_probes/` is opt-in, post-merge, and the offline smoke (no `HELIOS_EMBEDDING_API_KEY`) confirms the plumbing runs end-to-end. The real-cloud run requires a credential; this file is updated with the network-free evidence below.
>
> The acceptance is the directional shift from the pre-R96 baseline of `-0.0095` (ROADMAP §9.1) to a measurable post-R96 value (absolute separation ≥ +0.05 in either direction, with the expected direction being positive for cortisol-under-negative-input).

## 1. Pre-R96 baseline (reference)

| Metric | Pre-R96 (hash embedding) | Source |
| --- | --- | --- |
| `cortisol` positive-vs-negative emotion separation | -0.0095 | ROADMAP §9.1 (2026-06 emotion long-run) |
| Per-channel mean `|Δ|` | ≈ 0.09 | ROADMAP §9.1 |
| `b2_closed` (hash) | False (n/a) | this probe |

## 2. Post-R96 real-cloud probe (post-merge, opt-in)

> The first real-LLM run is documented here after the slice merges and the operator runs the probe with `HELIOS_EMBEDDING_API_KEY` set.

**Configuration**:
- Model: `HELIOS_EMBEDDING_MODEL` resolved value (default `text-embedding-3-small`, 1536-dim)
- LLM gateway: existing R34 / R82 path (unchanged)
- Corpus: the 2026-06 89-utterance / 16-visitor emotion set
- Trace: per-tick JSONL (using the existing `_LoggingProvider` pattern from R91)

**Result (placeholder until first run)**:

| Metric | Post-R96 (real cloud) | Directional shift vs baseline |
| --- | --- | --- |
| `cortisol` positive-vs-negative emotion separation | TBD | expected: measurably increased |
| Per-channel mean `|Δ|` | TBD | expected: increased |
| `b2_closed_real_llm` | TBD | expected: True |

## 3. Validation summary

### 3.1 Network-free B2 closure (CI surface, `tests/r96_b2_closure.py`)

The three B2 shift tests drive the per-fixture owner-seam math under both the `deterministic_hash` provider (R69-equivalent placeholder) and the `openai_compatible` provider (`FakeOpenAICompatibleEmbeddingProvider` returning coherent 1536-dim unit vectors). All 3 tests pass; per-test verdicts:

| Test | Fixtures | novelty shift | prototype shift | recall-over-recency | `b2_closed` (real) | `b2_closed` (hash) |
| --- | --- | --- | --- | --- | --- | --- |
| `test_b2_novelty_signal_differs_across_providers` | 10 | 10/10 (>0.05 delta) | n/a | n/a | `True` | `False` |
| `test_b2_threat_reward_prototype_cosine_differs_across_providers` | 10 | n/a | 10/10 (≥0.05 in threat or reward) | n/a | `True` | `False` |
| `test_b2_recall_over_recency_holds_for_real_provider` | 1 (rank-2 corpus) | n/a | n/a | older-similar beats newer-distant under fake-openai (sim=1.0); under hash, the recall is the noise witness | `True` | `False` |

The 6 per-test JSON reports (one per `provider_kind` per test) are written to `helios_v2/logs/r96_b2_closure/` and are gitignored. The CI verdict is recorded in each report's top-level `b2_closed: bool` field.

**B2 shift on the R35 novelty signal** (per-fixture, real vs hash, `1 - max_cosine` to a small stored-memory corpus):
- All 10 fixtures (joy, sadness, anger, fear, surprise, disgust, calm, anticipation, trust, neutral) show a sign-or-magnitude change > 0.05 between the two providers. Joy (the only fixture with high cosine to the corpus under the fake-openai path) shows a smaller delta (~0.09) but still above the 0.05 threshold.

**B2 shift on the R40 threat / reward prototype-cosine** (per-fixture, real vs hash, `cosine(fixture, threat_prototype)` and `cosine(fixture, reward_prototype)`):
- All 10 fixtures show a change > 0.05 in either the threat or the reward cosine. The fake-openai provider's coherent vectors give the threat-labeled fixtures (anger, fear, disgust, sadness, surprise) a non-zero threat cosine and a zero reward cosine; the reward-labeled fixtures (joy, trust, anticipation, calm, neutral) the inverse; the hash provider's 16-dim noise produces ~0 in both.

**B2 shift on the R52 recall-over-recency path**:
- Under fake-openai, the older semantically-similar record (joy, sim=1.0) beats the newer less-similar record (neutral, sim=0.0) — the recall-over-recency claim holds.
- Under hash, the cosine between any 16-dim noise vector and the 1536-dim precomputed vector is essentially 0.0 — the recall is the noise witness (B2 root cause exposed).

### 3.2 Real-LLM opt-in probe (`scripts/r96_b2_real_llm_probes/`)

The probe is **opt-in and post-merge**; it requires `HELIOS_EMBEDDING_API_KEY` in `.env` to pick the real-cloud embedding path. With no credential the probe still runs end-to-end (verified by 85-utterance offline smoke on 2026-06-15) but reports `b2_closed_real_llm: None` because the hash path is the active kind.

**Offline smoke (85-utterance hash run, 2026-06-15)**:
- `embedding_provider_kind: "deterministic_hash"`, `model: "deterministic-hash"`, `dimensions: 16`
- `cortisol` positive-vs-negative emotion separation: **-0.0180** (vs pre-R96 baseline -0.0095; same order of magnitude, hash path)
- `dopamine` separation: -0.0188; `oxytocin`: -0.0167; `opioid_tone`: -0.0188
- 0/85 messages fired (offline `_FakeProvider` does not produce tool calls)
- `b2_closed_real_llm: None` (correctly: the probe did not run on the real-cloud path)
- Full per-channel / per-category breakdowns in `helios_v2/logs/r96_b2_real_llm_probes/r96_emotion_analysis.json`

**Real-cloud run (TBD; first operator run post-merge)**:
- Re-run with `HELIOS_EMBEDDING_API_KEY` set; the resolver picks `openai_compatible`, the gateway calls the real OpenAI endpoint, and the analyzer reports `b2_closed_real_llm: bool` (`True` if the directional shift on `cortisol` positive-vs-negative separation ≥ +0.05 vs the pre-R96 baseline, `False` otherwise). The per-tick trace is gitignored.

## 4. Probe artifacts

- Per-tick JSONL trace: `logs/r96_b2_real_llm_probes/{run_id}.jsonl` (gitignored)
- Analysis JSON: `logs/r96_b2_real_llm_probes/{run_id}_analysis.json` (gitignored)
- B2 closure focused tests (network-free, CI): `tests/r96_b2_closure.py` → `B2ClosureReport` per provider
- Real-cloud B2 closure (this file's §2 entry) — opt-in, post-merge

## 5. Configuration

- **Embedding model**: `text-embedding-3-small` (1536 维, OpenAI, default) or `bge-m3` (1024 维多语, R97 follow-up) per `HELIOS_EMBEDDING_MODEL`.
- **Endpoint**: `HELIOS_EMBEDDING_BASE_URL` (default `https://api.openai.com/v1`).
- **Credential**: `HELIOS_EMBEDDING_API_KEY` (distinct from `OPENAI_API_KEY` used by the LLM gateway; see `design.md` §10 risk 4 for the credential-separation rationale).
- **Probe script**: `python helios_v2/scripts/r96_b2_real_llm_probes/run.py`
- **Analysis script**: `python helios_v2/scripts/r96_b2_real_llm_probes/analyze.py`
