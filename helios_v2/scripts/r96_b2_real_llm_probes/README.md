# R96 Real-LLM Opt-In Probe

> **Status**: opt-in, post-merge. The network-free B2 closure focused tests in
> `helios_v2/tests/r96_b2_closure.py` are the CI surface; this directory holds
> the real-cloud run that exercises the B2 closure hypothesis end-to-end
> against a real LLM and a real OpenAI-compatible embedding provider.

## What this probe does

The probe re-runs the **2026-06 emotion corpus** (16 visitors, 89 utterances,
defined in `helios_v2/scripts/sim_dialogue_visitors_zh.txt`) through a fully
assembled runtime whose embedding gateway is wired through the **R96 resolver**
(`composition.embedding_provider_resolution.resolve_embedding_provider` +
`build_embedding_gateway`). When `HELIOS_EMBEDDING_API_KEY` is set in `.env`,
the resolver picks `openai_compatible` and the gateway calls the real cloud;
otherwise the resolver picks `deterministic_hash` and the R69-equivalent
hash path runs (the B2 root-cause control).

The probe records per-message biochemical deltas (`04` / `05`), LLM I/O, and
the **embedding-provider kind** on the report, so the analysis step can
distinguish a real-cloud run from a hash-placeholder run. The headline metric
is the **`cortisol` positive-vs-negative emotion separation** (the B2
falsifiable claim from ROADMAP §9.1): a measurable positive shift vs the
pre-R96 baseline of `-0.0095` closes the B2 root cause.

## Usage

```bash
# 1. Configure credentials (R96 design §10 risk 4: HELIOS_EMBEDDING_API_KEY is
#    independent of OPENAI_API_KEY).
echo 'HELIOS_EMBEDDING_API_KEY=sk-...' >> .env
echo 'HELIOS_EMBEDDING_MODEL=text-embedding-3-small' >> .env   # optional (default)

# 2. Run the probe.
python helios_v2/scripts/r96_b2_real_llm_probes/run.py
# Optional flags:
#   --messages N          cap the dialogue to the first N messages (smoke)
#   --offline              force the LLM gateway into offline (fake) mode; the
#                          embedding gateway is still routed through the R96
#                          resolver (a real key in the env still picks the
#                          real-cloud embedding provider)
#   --seed N               change the random tick-interval seed (default 20260614)
#   --out PATH             per-message report JSON path
#   --transcript PATH      readable transcript path
#   --llm-log PATH         raw LLM I/O JSONL path

# 3. Analyze the report.
python helios_v2/scripts/r96_b2_real_llm_probes/analyze.py
# Optional flags:
#   --report PATH          per-message report JSON (default: the run's --out)
#   --out PATH             analysis JSON path
```

The probe prints the headline `b2_closed_real_llm: bool | None` verdict and
the directional-shift rationale to stdout. The analysis JSON is the
machine-readable record for downstream tooling.

## Output paths (gitignored)

| Path | Content |
| --- | --- |
| `helios_v2/logs/r96_b2_real_llm_probes/r96_emotion_report.json` | per-message biochemical deltas + LLM thoughts + replies + embedding-provider kind |
| `helios_v2/logs/r96_b2_real_llm_probes/r96_emotion_transcript.txt` | readable Chinese transcript |
| `helios_v2/logs/r96_b2_real_llm_probes/r96_emotion_llm_io.jsonl` | raw LLM I/O (system/user prompt + completion), one line per call |
| `helios_v2/logs/r96_b2_real_llm_probes/r96_emotion_analysis.json` | per-channel responsibility, per-category signature, valence-group separation, B2 verdict |

The committed `probe_results.md` (under `docs/requirements/96-real-semantic-embedding/`)
records the post-merge first-run verdict; the JSON artifacts above are the
underlying evidence.

## Relationship to the network-free B2 closure tests

`tests/r96_b2_closure.py` is the **CI surface** that falsifies B2 in a
fully-deterministic, network-free way via a `FakeOpenAICompatibleEmbeddingProvider`.
This directory is the **opt-in post-merge surface** that exercises the same
corpus under the real cloud. The two surfaces are designed to agree on the
**falsifiable claim** (a measurable shift from the hash placeholder to the
real provider) but disagree on the *execution substrate* (deterministic
synthetic vectors vs real-cloud network calls).

## Risk and fallback notes

- **No `HELIOS_EMBEDDING_API_KEY`** → probe still runs, but with the hash
  gateway; `b2_closed_real_llm` is `None`. This is the *intentional*
  offline path; it documents the B2 *failing witness* under the
  pre-R96 placeholder, identical to the `b2_closed: False` verdict in the
  network-free closure tests.
- **Real cloud unavailable at runtime** (e.g. DNS / TLS failure) → the
  first `embed()` call raises `EmbeddingError` (R34 behavior); the
  runtime hard-stops the tick. The probe reports `crash: <error>` and the
  analysis step writes `b2_closed_real_llm: False` with a network-failure
  reason. There is no per-tick fall-back to hash; the hash path is a
  *startup-time* decision, not a per-tick degradation.
- **Real cloud returns a different model dimension** (e.g. operator sets
  `HELIOS_EMBEDDING_MODEL=bge-m3` for 1024-dim) → the resolver records
  the right `dimensions` on the report; the analysis step's
  per-channel facts are dimension-agnostic. The B2 verdict still applies.

## See also

- `docs/requirements/96-real-semantic-embedding/design.md` — R96 design
  (sections §5.5 and §5.8 for the closure-test and real-probe contracts).
- `docs/requirements/96-real-semantic-embedding/probe_results.md` — the
  committed B2 closure evidence (post-merge, after the first run).
- `tests/r96_b2_closure.py` — the network-free CI surface.
- `docs/ROADMAP.zh-CN.md` — B2 root cause (R96 closes it).
