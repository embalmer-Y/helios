# Helios Personality Influence Research

> Status: Foundational Research
> Task coverage: T7-1, T7-2
> Scope: how long-horizon personality traits should bias interaction, regulation, and planning without fragmenting into ad hoc constants
> Related runtime surfaces: `personality.py`, `personality_projection.py`, `helios_io/interaction_policy.py`, `regulation/policy.py`, `helios_main.py`

> Archive note: the current implementation view now lives one level up under `docs/`. Use `../DESIGN_PHILOSOPHY.en.md` and `../IMPLEMENTATION_REFERENCE.en.md` when you need the active runtime definition.

## 1. Research Goal

This note defines the research basis for using personality as a slow control layer in Helios.

The engineering target is not a cosmetic prompt modifier. Personality should act as a stable prior that biases:

1. baseline affect sensitivity,
2. approach vs avoidance tendencies,
3. expressive intensity,
4. persistence, novelty seeking, and social risk tolerance.

## 2. Source Set

### 2.1 Trait Structure

- McCrae & Costa (1997), trait structure / Big Five stability
- Goldberg and Big Five lexical tradition

### 2.2 Personality and Primary Affect Coupling

- Davis & Panksepp (2011), primary-process emotional traits
- Panksepp (1998), affect systems as deep motivational substrates

### 2.3 Personality Change Over Time

- Roberts et al. (2006), systematic trait change across time
- related longitudinal work on trait plasticity under repeated experience

## 3. Findings Relevant to Helios

### 3.1 Personality is a prior, not a one-tick state

Trait effects should be slow and persistent. They should not flip with one message or one failed action. This matches Helios’ existing `PersonalityProfile` positioning as a long-timescale layer.

### 3.2 Trait influence is multi-surface

Research does not support reducing personality to a single “more talkative / less talkative” scalar. In Helios, useful bias surfaces include:

- social approach threshold,
- exploratory pressure,
- intimacy caution,
- recovery / persistence balance,
- preferred expressive style.

### 3.3 Personality should modulate appraisal and action preference, not replace them

Current-state affect, neurochemistry, temporal fatigue, and task context still decide what is appropriate now. Personality only changes the prior weighting.

## 4. Architectural Mapping

### 4.1 Stable trait layer

`PersonalityProfile` remains the owner of long-lived trait values and slow adaptation.

### 4.2 Runtime projection layer

Consumers should not read raw trait scalars and each invent their own multipliers. Instead, one projection object should emit normalized bias fields such as:

- `social_initiation_bias`
- `novelty_bias`
- `persistence_bias`
- `risk_tolerance_bias`
- `expressivity_bias`
- `self_disclosure_bias`

### 4.3 Consumption rule

Interaction policy, regulation policy, and planning may consume the projection. Lower layers such as channels and transport should not.

## 5. Constraints for Design

1. No scattering of raw Big Five constants across multiple scorers.
2. Personality must remain inspectable in one runtime object.
3. Projection should be deterministic for a given profile snapshot.
4. Adaptation should be slow, bounded, and separately testable from runtime scoring.
5. Policy traces should record when personality projection materially changed a score.

## 6. Why this matters for current code

Helios already implemented `PersonalityProjection`, but the research prerequisite was missing as an explicit artifact. This note closes that gap and justifies why projection exists as a distinct module rather than letting raw traits leak across the system.

## 7. Completion Statement

T7 is considered satisfied when:

1. this source note exists,
2. `docs/design.md` defines the projection boundary and consumer rules,
3. the task book reflects that personality influence is now grounded as a slow prior layer rather than an inline score hack.