# Helios Source Catalog

> Status: Active
> Audience: maintainers, research curators, and future source-collection work
> Scope: in-repo research material, citation entries, and the collection backlog

## 1. Document Role

This file answers three questions:

1. which original or near-original materials already exist under `research/`
2. which modules or design decisions those materials support
3. which papers, books, or reviews still need to be added to the citation backlog

The goal is traceability and collection status, not unchecked repository growth through full external paper dumps.

## 2. Source Categories

| Category | Meaning | Handling rule |
| --- | --- | --- |
| In-Repo Source | original paper files, extracted text, or concept notes already present in the repo | preserve them and add bibliographic metadata plus relevance |
| Curated Research Note | notes that explain and translate theory into Helios-relevant language | treat them as interpretation layers between theory and implementation |
| Citation Entry | bibliographic record plus summary and Helios relevance, without requiring the full original file | safe default when redistribution is unclear |
| Collection Backlog | known-missing but useful materials to acquire later | track priority, rationale, and suggested acquisition path |

## 3. Materials Already In The Repository

### 3.1 Original or Near-Original Sources

| File | Type | Topic | Supports | Status |
| --- | --- | --- | --- | --- |
| `anthropic_emotion_paper.pdf` | PDF | external emotion research paper | `helios_io/llm_sec_evaluator.py`, `helios_io/response_pipeline.py` | present |
| `anthropic_emotion_paper.txt` | extracted text | searchable text version of the paper | same modules, plus searchable excerpts | present |
| `anthropic_emotion_concepts.txt` | concept extract | emotion, appraisal, and SEC-related concepts | `cognition/appraisal.py`, `helios_io/llm_sec_evaluator.py` | present |

### 3.2 Curated Research Notes

| File | Topic | Main supported modules |
| --- | --- | --- |
| `panksepp_helio_mapping.md` | Panksepp seven-system mapping to Helios affect surfaces | `daisy_emotion.py`, `personality.py`, `regulation/regulation.py` |
| `neurochem_model.md` | neuromodulator model | `neurochem.py`, `cognition/drives.py`, `cognition/phi.py` |
| `fep_formalization.md` | free energy formalization | `cognition/drives.py`, `allostasis.py`, `helios_main.py` |
| `friston_panksepp_synthesis.md` | bridge between FEP and primary affect systems | `helios_main.py`, `regulation/regulation.py`, `cognition/drives.py` |
| `dmn_thinking_model.md` | DMN, replay, and endogenous thought | `cognition/thinking_integration.py`, `cognition/phi.py` |
| `preconscious_path_research.md` | bounded preconscious candidate-path research | `cognition/thinking_integration.py`, `helios_main.py`, `helios_io/interaction_policy.py`, `regulation/policy.py` |
| `personality_influence_research.md` | trait-prior and personality projection research | `personality.py`, `personality_projection.py`, `helios_io/interaction_policy.py`, `regulation/policy.py` |

## 4. Citation Entries

The entries below are already referenced in code docstrings or design notes, but are not yet maintained as a structured bibliography.

| Entry | Type | Relevance to Helios | Collection status |
| --- | --- | --- | --- |
| Panksepp, J. (1998). *Affective Neuroscience* | book | primary affect-system foundation | needs full bibliographic detail |
| Russell, J. A. (1980). circumplex model of affect | paper | valence-arousal plane | needs text or summary |
| Solomon, R. L., & Corbit, J. D. (1974). opponent-process theory | paper | DAISY opponent process | needs text or summary |
| Kuppens et al. (2010). emotional inertia | paper | mood and affect persistence | needs full citation detail |
| Davidson, R. J. (2000). affective chronometry | paper / review | DAISY time-course modeling | needs summary |
| Barrett, L. F. (2017). constructed emotion / population thinking | book / paper cluster | co-activation rather than single-label emotion | needs precise citation |
| Sterling, P., & Eyer, J. (1988). allostasis | chapter / paper | `allostasis.py` | needs full bibliographic detail |
| McEwen, B. (1998). allostatic load | paper | load accumulation in `allostasis.py` | needs text or summary |
| Schulkin, J. (2003). *Rethinking Homeostasis* | book | expanded allostasis framing | needs bibliographic detail |
| McCrae, R. R., & Costa, P. T. (1997). trait structure | paper | Big Five personality layer | needs summary |
| Davis, K. L., & Panksepp, J. (2011). primary-process emotional traits | paper | personality-affect coupling | needs summary |
| Roberts et al. (2006). personality trait change | paper | long-range trait drift | needs summary |
| Tononi, G. (2004). information integration theory | paper | `cognition/phi.py` | needs summary |
| Dehaene et al. (2006). global neuronal workspace | paper | ignition and broadcast in `cognition/phi.py` | needs summary |
| Seth, A. (2011). predictive processing and conscious presence | paper | precision-weighted prediction in `cognition/phi.py` | needs summary |
| Friston, K. (2010, 2017). free energy principle / active inference | paper cluster | `cognition/drives.py`, `helios_main.py` | needs structured citation bundle |
| Gebhard, P. (2005). ALMA | paper | `mood_tracker.py` time-scale layering | needs summary |
| Baddeley, A. working memory | papers / books | `memory/memory_system.py` | needs structured citation |

## 5. Collection Backlog

### 5.1 High Priority

| Entry | Why it matters | Main target modules | Suggested action |
| --- | --- | --- | --- |
| Panksepp 1998 bibliographic record plus chapter pointers | most central source for the affect substrate | `daisy_emotion.py`, `personality.py`, `regulation/regulation.py` | add citation entry plus chapter references |
| Friston 2010 and 2017 core papers | standard citation support for the drive layer and entropy-reduction narrative | `cognition/drives.py`, `helios_main.py` | add citation entries plus short abstracts |
| Tononi 2004, Dehaene 2006, Seth 2011 | `phi.py` already cites them explicitly | `cognition/phi.py` | add citation entries |
| ALMA and emotional inertia papers | stabilizes the mood and personality time-scale story | `mood_tracker.py`, `personality.py` | add citation entries |
| the three allostasis sources | the code cites them, but the catalog does not yet | `allostasis.py` | add full bibliographic records |

### 5.2 Medium Priority

| Entry | Why it matters | Main target modules | Suggested action |
| --- | --- | --- | --- |
| opponent-process source paper | DAISY already implements it | `daisy_emotion.py` | add summary |
| Russell circumplex paper | shared basis for affect and mood | `daisy_emotion.py`, `mood_tracker.py` | add summary |
| Davis and Panksepp 2011 | personality-primary affect coupling | `personality.py` | add summary |
| Baddeley working-memory sources | rounds out the memory-subsystem references | `memory/memory_system.py` | add citation entry |

## 6. How Sources Should Link To Code

Future maintenance should follow these rules:

1. each source entry should say which modules it supports
2. each new theoretical reference in active docs should point back to an entry in this catalog
3. if a paper cannot be redistributed in full, keep a citation entry and acquisition status rather than forcing the full text into the repo
4. if a PDF is stored in-repo, add searchable extracted text or a summary whenever practical

## 7. Relationship To Other Docs

- `IMPLEMENTATION_REFERENCE.*`: module-to-theory and module-to-test mapping
- `ARCHITECTURE.*`: current structural boundaries
- `DESIGN_PHILOSOPHY.*`: where those theories appear in runtime behavior
- foundational notes: deeper conceptual explanations