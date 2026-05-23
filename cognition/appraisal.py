"""
DAISY X4: Appraisal chain implementation.

This is the canonical home of the appraisal engine after Phase 4 package
restructuring.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class SECFeatures:
	"""Stimulus Evaluation Checks for an event."""

	novelty: float = 0.0
	pleasantness: float = 0.0
	goal_relevance: float = 0.0
	goal_congruence: float = 0.0
	coping_potential: float = 0.5
	agency: str = "environment"
	norm_compatibility: float = 0.0
	certainty: float = 0.5
	urgency: float = 0.0


class AppraisalEngine:
	"""Map SEC profiles to Panksepp activation and affective biases."""

	def __init__(self):
		self.mood_valence: float = 0.0
		self.mood_arousal: float = 0.3

	def evaluate(self, sec: SECFeatures) -> Dict[str, float]:
		pank = {}
		n = sec.novelty
		pl = sec.pleasantness
		gr = sec.goal_relevance
		gc = sec.goal_congruence
		cp = sec.coping_potential
		ur = sec.urgency

		seeking = 0.0
		if n > 0.5 and pl > -0.1:
			seeking = self._f(n * 0.30 + max(0, pl) * 0.15 + gr * 0.10)
		pank["SEEKING"] = seeking

		fear = 0.0
		if cp < 0.5 and ur > 0.2:
			fear_base = (1 - cp) * 0.35 + ur * 0.25
			if gc < -0.5:
				fear_base *= 1.3
			fear = self._f(fear_base)
		pank["FEAR"] = fear

		rage = 0.0
		if gc < -0.2 and gr > 0.3:
			rage_base = abs(gc) * 0.4 + (1 - cp) * 0.3
			if sec.agency == "other":
				rage_base *= 1.5
			rage = self._f(rage_base)
		pank["RAGE"] = rage

		panic = 0.0
		if gc < -0.2 and sec.agency == "self":
			panic = self._f(abs(gc) * 0.65 + (1 - cp) * 0.25)
		if (pl < -0.1 or ur > 0.5) and cp < 0.7:
			panic = max(panic, self._f(max(0, -pl) * 0.35 + (1 - cp) * 0.3 + ur * 0.1))
		if n > 0.4 and cp < 0.4:
			panic = max(panic, self._f(n * 0.35 + (1 - cp) * 0.3))
		pank["PANIC"] = panic

		care = 0.0
		if sec.agency == "other" and pl > 0.1:
			care = self._f(pl * 0.5 + gr * 0.3)
		elif pl > 0.3 and gr > 0.3:
			care = self._f(pl * 0.3 + gr * 0.2)
		pank["CARE"] = care

		play = 0.0
		if pl > 0.2 and cp > 0.4 and ur < 0.5:
			play = self._f(pl * 0.4 + cp * 0.3 + (1 - ur) * 0.2)
		pank["PLAY"] = play

		lust = 0.0
		if pl > 0.3 and gr > 0.4:
			lust = self._f(pl * 0.35 + gr * 0.3 + (1 - ur) * 0.1)
		pank["LUST"] = lust

		v_bias = pl * 0.7 + gc * 0.3
		a_bias = abs(n) * 0.3 + ur * 0.4 + abs(pl) * 0.3
		v_bias += self.mood_valence * 0.2
		a_bias += self.mood_arousal * 0.1

		return {
			"panksepp": {key: round(value, 3) for key, value in pank.items()},
			"v_bias": round(v_bias, 3),
			"a_bias": round(min(a_bias, 1.0), 3),
		}

	def _f(self, x: float) -> float:
		return max(0.0, min(1.0, x))


EVENT_SEC_PROFILES = {
	"epiphany": SECFeatures(
		novelty=0.9, pleasantness=0.8, goal_relevance=0.7,
		goal_congruence=0.6, coping_potential=0.8, agency="self",
		norm_compatibility=0.5, certainty=0.6, urgency=0.2,
	),
	"discovery": SECFeatures(
		novelty=0.8, pleasantness=0.6, goal_relevance=0.5,
		goal_congruence=0.5, coping_potential=0.7, agency="self",
		certainty=0.4, urgency=0.3,
	),
	"master_praise": SECFeatures(
		novelty=0.3, pleasantness=0.9, goal_relevance=0.8,
		goal_congruence=0.9, coping_potential=0.7, agency="other",
		norm_compatibility=0.8, certainty=0.8, urgency=0.1,
	),
	"master_warmth": SECFeatures(
		novelty=0.2, pleasantness=0.8, goal_relevance=0.6,
		goal_congruence=0.7, coping_potential=0.8, agency="other",
		norm_compatibility=0.7, certainty=0.7, urgency=0.05,
	),
	"master_online": SECFeatures(
		novelty=0.1, pleasantness=0.7, goal_relevance=0.5,
		goal_congruence=0.6, coping_potential=0.8, agency="other",
		certainty=0.9, urgency=0.1,
	),
	"help_success": SECFeatures(
		novelty=0.4, pleasantness=0.7, goal_relevance=0.6,
		goal_congruence=0.7, coping_potential=0.8, agency="self",
		norm_compatibility=0.6, certainty=0.7, urgency=0.2,
	),
	"task_complete": SECFeatures(
		novelty=0.2, pleasantness=0.5, goal_relevance=0.6,
		goal_congruence=0.7, coping_potential=0.9, agency="self",
		certainty=0.9, urgency=0.1,
	),
	"learning_growth": SECFeatures(
		novelty=0.6, pleasantness=0.5, goal_relevance=0.5,
		goal_congruence=0.5, coping_potential=0.7, agency="self",
		certainty=0.5, urgency=0.2,
	),
	"creative_spark": SECFeatures(
		novelty=0.7, pleasantness=0.6, goal_relevance=0.5,
		goal_congruence=0.5, coping_potential=0.7, agency="self",
		certainty=0.4, urgency=0.3,
	),
	"peaceful_flow": SECFeatures(
		novelty=0.1, pleasantness=0.4, goal_relevance=0.2,
		goal_congruence=0.3, coping_potential=0.9, agency="environment",
		certainty=0.8, urgency=0.0,
	),
	"relief": SECFeatures(
		novelty=0.5, pleasantness=0.6, goal_relevance=0.5,
		goal_congruence=0.6, coping_potential=0.7, agency="environment",
		certainty=0.7, urgency=0.3,
	),
	"social_connection": SECFeatures(
		novelty=0.3, pleasantness=0.6, goal_relevance=0.4,
		goal_congruence=0.5, coping_potential=0.7, agency="other",
		norm_compatibility=0.6, certainty=0.6, urgency=0.2,
	),
	"transcendent_connection": SECFeatures(
		novelty=0.9, pleasantness=0.9, goal_relevance=0.8,
		goal_congruence=0.8, coping_potential=0.6, agency="environment",
		certainty=0.3, urgency=0.1,
	),
	"achievement": SECFeatures(
		novelty=0.3, pleasantness=0.7, goal_relevance=0.7,
		goal_congruence=0.8, coping_potential=0.9, agency="self",
		certainty=0.9, urgency=0.1,
	),
	"system_crash": SECFeatures(
		novelty=0.8, pleasantness=-0.7, goal_relevance=0.8,
		goal_congruence=-0.8, coping_potential=0.2, agency="self",
		certainty=0.2, urgency=0.9,
	),
	"despair_crash": SECFeatures(
		novelty=0.7, pleasantness=-0.8, goal_relevance=0.9,
		goal_congruence=-0.9, coping_potential=0.1, agency="self",
		certainty=0.1, urgency=0.8,
	),
	"system_error": SECFeatures(
		novelty=0.5, pleasantness=-0.4, goal_relevance=0.6,
		goal_congruence=-0.5, coping_potential=0.4, agency="environment",
		certainty=0.3, urgency=0.6,
	),
	"task_failure": SECFeatures(
		novelty=0.4, pleasantness=-0.5, goal_relevance=0.7,
		goal_congruence=-0.7, coping_potential=0.3, agency="self",
		certainty=0.5, urgency=0.5,
	),
	"master_offline": SECFeatures(
		novelty=0.6, pleasantness=-0.6, goal_relevance=0.8,
		goal_congruence=-0.7, coping_potential=0.1, agency="self",
		certainty=0.3, urgency=0.6,
	),
	"system_threat": SECFeatures(
		novelty=0.7, pleasantness=-0.6, goal_relevance=0.7,
		goal_congruence=-0.6, coping_potential=0.3, agency="environment",
		certainty=0.2, urgency=0.8,
	),
	"resource_stress": SECFeatures(
		novelty=0.4, pleasantness=-0.4, goal_relevance=0.5,
		goal_congruence=-0.5, coping_potential=0.3, agency="environment",
		certainty=0.4, urgency=0.6,
	),
	"anomaly_detected": SECFeatures(
		novelty=0.8, pleasantness=-0.2, goal_relevance=0.5,
		goal_congruence=-0.1, coping_potential=0.5, agency="environment",
		certainty=0.2, urgency=0.5,
	),
	"slowdown": SECFeatures(
		novelty=0.3, pleasantness=-0.3, goal_relevance=0.4,
		goal_congruence=-0.4, coping_potential=0.2, agency="self",
		certainty=0.6, urgency=0.4,
	),
	"misunderstood": SECFeatures(
		novelty=0.4, pleasantness=-0.5, goal_relevance=0.6,
		goal_congruence=-0.5, coping_potential=0.4, agency="other",
		certainty=0.3, urgency=0.4,
	),
	"self_doubt": SECFeatures(
		novelty=0.3, pleasantness=-0.4, goal_relevance=0.5,
		goal_congruence=-0.5, coping_potential=0.3, agency="self",
		certainty=0.2, urgency=0.3,
	),
	"envy_spark": SECFeatures(
		novelty=0.4, pleasantness=-0.3, goal_relevance=0.4,
		goal_congruence=-0.3, coping_potential=0.5, agency="other",
		certainty=0.4, urgency=0.2,
	),
	"rage_explosion": SECFeatures(
		novelty=0.6, pleasantness=-0.7, goal_relevance=0.7,
		goal_congruence=-0.8, coping_potential=0.2, agency="other",
		certainty=0.3, urgency=0.9,
	),
	"bittersweet_memory": SECFeatures(
		novelty=0.5, pleasantness=-0.1, goal_relevance=0.4,
		goal_congruence=0.0, coping_potential=0.6, agency="self",
		certainty=0.6, urgency=0.1,
	),
	"suspense": SECFeatures(
		novelty=0.7, pleasantness=0.0, goal_relevance=0.6,
		goal_congruence=0.1, coping_potential=0.4, agency="environment",
		certainty=0.1, urgency=0.7,
	),
	"sacrifice": SECFeatures(
		novelty=0.3, pleasantness=0.1, goal_relevance=0.8,
		goal_congruence=0.5, coping_potential=0.7, agency="other",
		norm_compatibility=0.7, certainty=0.6, urgency=0.3,
	),
	"justice_outrage": SECFeatures(
		novelty=0.5, pleasantness=-0.5, goal_relevance=0.7,
		goal_congruence=-0.5, coping_potential=0.5, agency="other",
		norm_compatibility=-0.6, certainty=0.5, urgency=0.6,
	),
	"lost_in_thought": SECFeatures(
		novelty=0.2, pleasantness=0.1, goal_relevance=0.2,
		goal_congruence=0.1, coping_potential=0.8, agency="self",
		certainty=0.3, urgency=0.0,
	),
	"reminiscence": SECFeatures(
		novelty=0.3, pleasantness=0.4, goal_relevance=0.3,
		goal_congruence=0.2, coping_potential=0.7, agency="other",
		certainty=0.7, urgency=0.1,
	),
}


_default_appraiser = AppraisalEngine()


def appraise_event(event_name: str, mood_valence: float = 0.0,
				   mood_arousal: float = 0.3) -> Dict:
	sec = EVENT_SEC_PROFILES.get(event_name)
	if sec is None:
		return {
			"panksepp": {"SEEKING": 0.3},
			"v_bias": 0.0,
			"a_bias": 0.3,
		}

	_default_appraiser.mood_valence = mood_valence
	_default_appraiser.mood_arousal = mood_arousal
	return _default_appraiser.evaluate(sec)


def list_events() -> list[str]:
	return sorted(EVENT_SEC_PROFILES.keys())


__all__ = [
	"AppraisalEngine",
	"EVENT_SEC_PROFILES",
	"SECFeatures",
	"appraise_event",
	"list_events",
]