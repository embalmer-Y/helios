# R97 去英文中心 / 中文 Appraisal Grounding — Probe Results

> **Status (2026-06-15)**: placeholder. The B3 closure focused tests in `tests/r97_b3_closure.py` are the network-free CI surface; the real-LLM probe (R96 + R97 cascade) at `scripts/r96_b2_real_llm_probes/` is opt-in, post-merge.
>
> After the first real-LLM run (post-merge, with `HELIOS_EMBEDDING_API_KEY` set), the artifacts are committed here:
> 1. The per-tick JSONL trace under `logs/r96_b2_real_llm_probes/` (gitignored; same as R96).
> 2. The analysis JSON from `analyze.py` (committed or gitignored per team policy).
> 3. A short summary below: the B3 中文 fixture threat/reward cosine 方向性提升 (R97 headline metric), the B3 closure verdict (`b3_closed: bool`), and the directional-shift assessment vs the R96 baseline.
>
> The acceptance is the directional shift from the pre-R97 baseline (Chinese fixture → English anchors → cosine ≈ 0.05) to a post-R97 value (Chinese fixture → Chinese anchors → cosine ≥ 0.3 for matching threat/reward; cosine < 0.2 for neutral Chinese).

## 1. Pre-R97 baseline (reference)

| Metric | Pre-R97 (English-only anchors) | Source |
| --- | --- | --- |
| 中文 "愤怒" 输入 → threat cosine | ≈ 0.05 (cross-language noise) | this probe (B3 root cause) |
| 中文 "喜悦" 输入 → reward cosine | ≈ 0.05 (cross-language noise) | this probe (B3 root cause) |
| 中文 "今天星期三" → threat / reward cosine | ≈ 0.05 / 0.05 (background) | this probe |
| `cortisol` 正负情绪分离 (含真实 cloud embedding) | TBD (待 R97 完成后实测) | this probe |
| `b3_closed` (English anchors) | False (n/a) | this probe |

## 2. Post-R97 probe (post-implementation, in this slice)

> The B3 closure focused tests in `tests/r97_b3_closure.py` run the R97 中文 anchor catalog against the 17-category emotion corpus (same as R96 probe) and assert `b3_closed: bool == True` for the 中文-path and `b3_closed: bool == False` for the English-only path (the B3 root-cause witness).

**Configuration**:
- Catalog: `DEFAULT_ANCHOR_CATALOG` (5 中文 threat + 5 中文 reward + 5 英文 threat + 5 英文 reward)
- Embedding provider: `R96 resolver` → 真实 cloud (or hash in offline mode)
- 中文 corpus: 17 类别 × 5 turns = 85 utterances (same as R96 probe)

**Result (placeholder until first run)**:

| Metric | Post-R97 (Chinese + English anchors) | Directional shift vs baseline |
| --- | --- | --- |
| 中文 "愤怒" → threat cosine | TBD (expected ≥ 0.3) | expected: ↑ significantly |
| 中文 "喜悦" → reward cosine | TBD (expected ≥ 0.3) | expected: ↑ significantly |
| 中文 "今天星期三" → threat / reward | TBD (expected < 0.2) | expected: stays low |
| `cortisol` 正负情绪分离 | TBD (expected ≥ +0.05 shift vs R96) | expected: ↑ directionally |
| `b3_closed` (Chinese + English anchors) | TBD | expected: True |

## 3. Validation summary (to be filled post-implementation)

- B3 closure verdict: `b3_closed: bool | None` (TBD; None when probe ran on hash path)
- 中文 threat cosine directionality: TBD
- 中文 reward cosine directionality: TBD
- 中文中性 cosine (low control): TBD
- English anchor fallback: TBD (R40 字节级保留验证)

## 4. Probe artifacts

- Per-tick JSONL trace: `logs/r96_b2_real_llm_probes/{run_id}.jsonl` (gitignored; shared with R96)
- Analysis JSON: `logs/r96_b2_real_llm_probes/{run_id}_analysis.json` (gitignored; now includes B3 fields)
- B3 closure focused tests (network-free, CI): `tests/r97_b3_closure.py` → `B3ClosureReport` per provider
- Real-cloud B3 closure (this file's §2 entry) — opt-in, post-merge

## 5. Configuration

- **Anchor catalog**: `DEFAULT_ANCHOR_CATALOG` (R97 default; bilingual first-version)
- **Embedding model**: `HELIOS_EMBEDDING_MODEL` resolved value (default `text-embedding-3-small`, 1536-dim; or `bge-m3` 1024-dim)
- **Endpoint**: `HELIOS_EMBEDDING_BASE_URL` (default `https://api.openai.com/v1`)
- **Credential**: `HELIOS_EMBEDDING_API_KEY` (distinct from `OPENAI_API_KEY`)
- **Probe script**: `python helios_v2/scripts/r96_b2_real_llm_probes/run.py` (R97 cascades automatically via `anchor_catalog` default)
- **Analysis script**: `python helios_v2/scripts/r96_b2_real_llm_probes/analyze.py` (R97 adds B3 metrics)

## 6. R97 vs R96 relationship

- R96: real embedding接入 (cloud `text-embedding-3-small` default)
- R97: 中文 anchor catalog (R97 default; bilingual first-version)
- Both required for B3 closure (B2 closure was R96 alone; B3 closure needs both)
- R98 (next slice) consumes the cascade: real embedding + Chinese anchors → emotion evaluation probes
- R99+ (dual-track memory) builds on R96 + R97 + R98
