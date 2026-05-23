# Helios

Helios is a continuously running affective and cognitive agent. It is organized around a main loop in `helios_main.py` and combines affective substrate modules, memory, cognition, regulation, and external I/O into one long-lived runtime.

The repository is structured so that:

- the repository root holds runtime entry surfaces and foundational affective substrate modules
- `helios_io/` owns all external interface and transport behavior
- `core/` holds transport-agnostic runtime infrastructure
- `memory/`, `cognition/`, and `regulation/` own the internal capability layers

## Repository layout

- `helios_main.py`: primary runtime entry point
- `dashboard.py` and `dashboard.html`: runtime dashboard surface
- `allostasis.py`, `daisy_emotion.py`, `mood_tracker.py`, `personality.py`, `neurochem.py`, `habituation.py`: affective and physiological substrate
- `helios_io/`: protocols, channels, passive reply pipeline, conversation history, SEC evaluation, behavior execution boundary
- `core/`: event plumbing, tick state, trigger merge, and tick guard
- `memory/`: autobiographical, episodic, semantic, working-memory, compression, and seed import logic
- `cognition/`: appraisal, drives, phi, and endogenous thinking
- `regulation/`: action selection, conation, and behavior regulation
- `research/`: active architecture docs, implementation mapping, source catalog, and foundational research notes
- `tests/`: regression and property-based tests

## Runtime model

Each tick of the runtime typically does the following:

1. collect events and channel input
2. update affective state, allostasis, mood, personality, and optional neurochemical or phi signals
3. write and consolidate memory
4. perform appraisal, drive estimation, and endogenous thinking
5. turn internal state into behavioral pressure through regulation
6. route external output back through `helios_io`

The authoritative runtime orchestration lives in `helios_main.py`. The codebase is the final source of truth when older notes and current behavior diverge.

## Getting started

Common entry points:

- run the main loop: `python helios_main.py`
- open the runtime dashboard through the dashboard assets
- use the `research/` documents when you need architecture, theory mapping, or source provenance

Runtime behavior is environment-driven. The `HeliosConfig` class in `helios_main.py` documents the main environment variables used for timing, logging, LLM access, QQ integration, and multimodal channels.

## Documentation map

Start here when learning the codebase:

1. `research/research_home.html`
2. `research/ARCHITECTURE.zh-CN.md` or `research/ARCHITECTURE.en.md`
3. `research/DESIGN_PHILOSOPHY.zh-CN.md` or `research/DESIGN_PHILOSOPHY.en.md`
4. `research/IMPLEMENTATION_REFERENCE.zh-CN.md` or `research/IMPLEMENTATION_REFERENCE.en.md`
5. `research/SOURCE_CATALOG.zh-CN.md` or `research/SOURCE_CATALOG.en.md`
6. `research/architecture_overview.html`
7. `research/current_structure.md`

Use the foundational research notes in `research/` only after the active architecture docs, because the active docs describe the current implementation while the foundational notes explain the theory behind it.

## Testing

The repository includes a broad regression suite under `tests/`. A documented validated baseline in the active structure reference is:

- `pytest -q` -> `520 passed`

If you are making structural changes, prefer validating the touched slice first and then rerunning the broader test suite.

## Development rules

- do not add new protocol clients or transport implementations at the repository root
- do not move transport-specific logic back into `core/`
- add future protocol implementations under `helios_io/protocols/`
- add future model-backed outward generation under `helios_io/llm/`
- keep `memory/`, `cognition/`, and `regulation/` focused on internal capability rather than transport details

## Status

The repository currently includes an active documentation system under `research/` with:

- architecture overviews in Chinese and English
- detailed runtime design docs in Chinese and English
- implementation-to-theory mapping docs in Chinese and English
- source catalog and collection-backlog docs in Chinese and English
- static HTML pages for visual architecture and documentation navigation