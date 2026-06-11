"""R79-D framework core: scenario loading, runner, assertion engine, report generator."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path("/root/project/helios")
SCRIPT_DIR = ROOT / "helios_v2" / "scripts"


@dataclass(frozen=True)
class Scenario:
    """One experimental scenario."""
    id: str
    description: str
    stimulus_script: list[str]
    assertions: list[dict] = field(default_factory=list)
    repeat: int | None = None

    @classmethod
    def from_json(cls, path: Path) -> "Scenario":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            id=data["id"],
            description=data.get("description", ""),
            stimulus_script=data["stimulus_script"],
            assertions=data.get("assertions", []),
            repeat=data.get("repeat"),
        )

    def to_json(self, path: Path) -> None:
        path.write_text(
            json.dumps({
                "id": self.id, "description": self.description,
                "stimulus_script": self.stimulus_script,
                "assertions": self.assertions, "repeat": self.repeat,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


@dataclass
class TickRecord:
    tick_id: int
    stimulus_text: str
    hormone_state: dict
    feeling_state: dict
    salience: dict
    llm_output: dict
    delta: dict


@dataclass
class AssertionResult:
    name: str
    passed: bool
    detail: str
    actual: Any = None
    expected: Any = None


@dataclass
class ExperimentConfig:
    scenario: Scenario
    output_dir: Path
    llm_model: str | None = None
    use_real_llm: bool = True
    timeout_per_tick: float = 60.0
    force: bool = False


# ============================================================
# Body state translator
# ============================================================


def _level5(v: float) -> str:
    if v < 0.25: return "very low"
    if v < 0.45: return "low"
    if v < 0.60: return "okay"
    if v < 0.80: return "high"
    return "very high"


def _level3(v: float) -> str:
    if v < 0.4: return "low"
    if v < 0.65: return "okay"
    return "high"


def body_state_translate(levels) -> str:
    parts = []
    parts.append(f"dopamine (motivation/reward anticipation): {_level5(levels.dopamine)}")
    parts.append(f"norepinephrine (alertness/stress): {_level5(levels.norepinephrine)}")
    parts.append(f"serotonin (mood baseline/patience): {_level5(levels.serotonin)}")
    parts.append(f"acetylcholine (attention): {_level5(levels.acetylcholine)}")
    parts.append(f"cortisol (pressure load): {_level5(levels.cortisol)}")
    parts.append(f"oxytocin (bonding): {_level5(levels.oxytocin)}")
    parts.append(f"opioid_tone (comfort/pain buffer): {_level5(levels.opioid_tone)}")
    if hasattr(levels, "excitation"):
        parts.append(f"excitation (cognitive activation): {_level5(levels.excitation)}")
        parts.append(f"inhibition (cognitive brake): {_level5(levels.inhibition)}")
    if hasattr(levels, "arousal"):
        parts.append(f"feeling arousal (energy): {_level3(levels.arousal)}")
        parts.append(f"feeling valence (pleasure-displeasure): {_level3(levels.valence)}")
        parts.append(f"feeling tension (strain): {_level3(levels.tension)}")
    return "\n".join(parts)


# ============================================================
# Stage result extractors
# ============================================================


def get_hormone_state_from_result(result) -> dict:
    sr = result.stage_results.get("neuromodulator_system")
    if sr is None: return {}
    state = getattr(sr, "state", None)
    if state is None: return {}
    lv = state.levels
    return {
        "dopamine": lv.dopamine, "norepinephrine": lv.norepinephrine,
        "serotonin": lv.serotonin, "acetylcholine": lv.acetylcholine,
        "cortisol": lv.cortisol, "oxytocin": lv.oxytocin,
        "opioid_tone": lv.opioid_tone, "excitation": lv.excitation,
        "inhibition": lv.inhibition,
    }


def get_feeling_state_from_result(result) -> dict:
    sr = result.stage_results.get("interoceptive_feeling_layer")
    if sr is None: return {}
    state = getattr(sr, "state", None)
    if state is None: return {}
    v = state.feeling
    return {
        "arousal": v.arousal, "valence": v.valence, "tension": v.tension,
        "comfort": v.comfort, "fatigue": v.fatigue, "pain_like": v.pain_like, "social_safety": v.social_safety,
    }


def get_salience_from_result(result) -> dict:
    sr = result.stage_results.get("rapid_salience_appraisal")
    if sr is None: return {}
    batch = getattr(sr, "batch", None)
    if batch is None or not batch.appraisals: return {}
    appraisal = batch.appraisals[0]
    sal = appraisal.salience
    dims = {"threat": sal.threat, "reward": sal.reward, "novelty": sal.novelty, "social": sal.social, "uncertainty": sal.uncertainty}
    top = max(dims, key=dims.get)
    return {"aggregate": sal.aggregate, "top_dimension": top, "top_score": dims[top], "all_dimensions": dims}


# ============================================================
# LLM gateways
# ============================================================


@dataclass
class LlmRequestLog:
    request_id: str
    profile_name: str
    messages: list[dict]
    raw_response_text: str = ""
    parsed_json: dict | None = None
    error: str | None = None
    usage: dict | None = None


class RealLlmGateway:
    def __init__(self, model: str | None = None, timeout_s: float = 60.0):
        import os
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.base_url = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
        self.model = model or os.environ.get("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")
        self.timeout_s = timeout_s
        self.captured: list[LlmRequestLog] = []
        if not self.api_key or not self.base_url:
            raise RuntimeError("RealLlmGateway requires OPENAI_API_KEY and OPENAI_BASE_URL in env")

    def _post_chat(self, messages):
        url = f"{self.base_url}/chat/completions"
        body = {"model": self.model, "messages": messages, "temperature": 0.7}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            return "", None, None, str(e)
        text = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        parsed = None
        if "```json" in text:
            try:
                start = text.index("```json") + len("```json")
                end = text.index("```", start)
                parsed = json.loads(text[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                parsed = None
        elif "{" in text and "}" in text:
            try:
                start = text.index("{")
                end = text.rindex("}") + 1
                parsed = json.loads(text[start:end])
            except (ValueError, json.JSONDecodeError):
                parsed = None
        return text, parsed, usage, None

    def complete(self, request):
        from helios_v2.llm.contracts import LlmCompletion, LlmUsage
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        text, parsed, usage, err = self._post_chat(messages)
        log = LlmRequestLog(
            request_id=request.request_id,
            profile_name=request.target_profile,
            messages=messages,
            raw_response_text=text,
            parsed_json=parsed,
            error=err,
            usage=usage,
        )
        self.captured.append(log)
        completion_id = f"complete-{request.request_id}-{int(time.time()*1000)}"
        if err:
            return LlmCompletion(
                completion_id=completion_id, source_request_id=request.request_id,
                profile_name=request.target_profile, model=self.model,
                output_text="", finish_reason="error",
                usage=LlmUsage(0, 0, 0), latency_ms=0,
            )
        return LlmCompletion(
            completion_id=completion_id, source_request_id=request.request_id,
            profile_name=request.target_profile, model=self.model,
            output_text=text, finish_reason="stop",
            usage=LlmUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            latency_ms=0,
        )

    def readiness_report(self):
        from helios_v2.llm.contracts import LlmReadinessReport, LlmProfileReadiness
        return LlmReadinessReport(
            report_id=f"rpt-{int(time.time()*1000)}",
            checked_live=True,
            entries=[LlmProfileReadiness(profile_name="default", exists=True, static_ready=True, live_ready=True, detail="RealLlmGateway (R79-D)")],
        )

    def check_static_readiness(self, profile_names):
        from helios_v2.llm.contracts import LlmReadinessReport, LlmProfileReadiness
        entries = [
            LlmProfileReadiness(profile_name=p, exists=True, static_ready=True, live_ready=False, detail="RealLlmGateway static")
            for p in profile_names
        ] or [LlmProfileReadiness(profile_name="default", exists=True, static_ready=True, live_ready=False, detail="RealLlmGateway static")]
        return LlmReadinessReport(report_id=f"static-{int(time.time()*1000)}", checked_live=False, entries=entries)

    def probe_live_readiness(self, profile_names):
        from helios_v2.llm.contracts import LlmReadinessReport, LlmProfileReadiness
        try:
            url = f"{self.base_url}/chat/completions"
            data = json.dumps({"model": self.model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as resp:
                json.loads(resp.read().decode("utf-8"))
            ready = True
            detail = "RealLlmGateway live ping succeeded"
        except Exception as e:
            ready = False
            detail = f"RealLlmGateway live ping failed: {e}"
        entries = [
            LlmProfileReadiness(profile_name=p, exists=True, static_ready=True, live_ready=ready, detail=detail)
            for p in profile_names
        ] or [LlmProfileReadiness(profile_name="default", exists=True, static_ready=True, live_ready=ready, detail=detail)]
        return LlmReadinessReport(report_id=f"live-{int(time.time()*1000)}", checked_live=True, entries=entries)


class NoopLlmGateway:
    def __init__(self, canned_response: dict | None = None):
        from helios_v2.llm.contracts import LlmCompletion, LlmUsage, LlmReadinessReport, LlmProfileReadiness
        self._LlmCompletion = LlmCompletion
        self._LlmUsage = LlmUsage
        self._LlmReadinessReport = LlmReadinessReport
        self._LlmProfileReadiness = LlmProfileReadiness
        self.canned = canned_response or {
            "what_i_feel": "noop gateway: no real LLM call",
            "what_i_think": "noop gateway stub",
            "i_want_to_say": None,
            "i_will_send_it": False,
            "i_send_through": None,
            "remember_this": False,
            "remember_because": None,
            "i_want_to_think_more": False,
            "think_more_about": None,
            "act_type": None,
        }
        self.captured: list[LlmRequestLog] = []

    def complete(self, request):
        text = "```json\n" + json.dumps(self.canned, ensure_ascii=False) + "\n```"
        log = LlmRequestLog(
            request_id=request.request_id,
            profile_name=request.target_profile,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            raw_response_text=text,
            parsed_json=self.canned,
            error=None,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        self.captured.append(log)
        return self._LlmCompletion(
            completion_id=f"noop-{request.request_id}",
            source_request_id=request.request_id,
            profile_name=request.target_profile,
            model="noop",
            output_text=text,
            finish_reason="stop",
            usage=self._LlmUsage(0, 0, 0),
            latency_ms=0,
        )

    def readiness_report(self):
        return self._LlmReadinessReport(
            report_id="noop-rpt", checked_live=False,
            entries=[self._LlmProfileReadiness(profile_name="default", exists=True, static_ready=True, live_ready=False, detail="NoopLlmGateway")],
        )

    def check_static_readiness(self, profile_names):
        return self.readiness_report()

    def probe_live_readiness(self, profile_names):
        return self.readiness_report()


# ============================================================
# Stimulus source
# ============================================================


class ScriptedCliSource:
    name = "scripted_cli"

    def __init__(self, script: list[str]):
        self.script = list(script)
        self.index = 0
        self.collected_count = 0

    @property
    def source_name(self) -> str:
        return self.name

    def emit_raw_signals(self):
        from helios_v2.sensory.contracts import RawSignal
        if self.index >= len(self.script):
            return ()
        text = self.script[self.index]
        self.index += 1
        self.collected_count += 1
        return (RawSignal(
            signal_id=f"scripted:cli:{self.collected_count:03d}",
            source_name=self.name,
            signal_type="text",
            content=text,
            channel="cli",
            metadata={"user_id": "user:r79d-probe"},
        ),)

    def snapshot(self):
        return {"name": self.name, "kind": "cli", "cursor": self.index, "total": len(self.script)}


# ============================================================
# v3 prompt injection
# ============================================================


def inject_v3_prompt(handle, v3_prompt_text: str | None = None):
    """Inject the R79-A aggressive-radical v3 system prompt into the LLM path.

    R79-C update (2026-06-11): previously this read a hard-coded v2-draft file
    from V3_PROMPT_PATH. Now the v3 prompt is rendered by the same
    ``AggressiveRadicalEmbodiedPromptPath`` runtime that production uses, so the
    12-field schema (including R79-C's ``hormone_response_i_predict``) and the
    6-layer contract are sourced from one place. ``v3_prompt_text`` arg is
    kept for backwards-compatible unit tests that pass pre-rendered text.

    v3 prompt is re-rendered **per-tick** from the most recent tick result so
    hormone / feeling / channel-catalog state always reflects the live body
    (this is the whole point of the 12-field hormone_response_i_predict
    schema — the LLM must see its current body to predict its next body).
    """
    import helios_v2.internal_thought.engine as ite
    from helios_v2.llm.contracts import LlmMessage
    from helios_v2.prompt_contract.engine import AggressiveRadicalEmbodiedPromptPath

    # Module-level last-result slot. Updated by run_experiment after each
    # tick. v3_build_messages reads it lazily so we don't have to thread
    # the result through LlmBackedInternalThoughtPath's _build_messages
    # signature.
    _r79d_state = {"last_result": None}

    def v3_build_messages(self_engine, request, retrieval_bundle, continuation_state):
        from helios_v2.prompt_contract.engine import _AGGRESSIVE_RADICAL_V3_SYSTEM_PROMPT as _V3_TEMPLATE
        last_result = _r79d_state["last_result"]
        if v3_prompt_text is not None:
            system_content = v3_prompt_text
        else:
            # Build the four {placeholder} values freshly each tick.
            v3_kwargs = _build_v3_placeholders(handle, AggressiveRadicalEmbodiedPromptPath, last_result)
            system_content = _V3_TEMPLATE.format(**v3_kwargs)
        system_msg = LlmMessage(role="system", content=system_content)
        user_lines = []
        user_lines.append("# Current body state (first-person sense of your own chemistry & feeling)")
        user_lines.append("(These are the levels you feel right now. They shift each tick as your body and mind respond.)")
        user_lines.append("")
        # Body state is already in the v3 system prompt (4th slot); keep
        # user-side body state as a short reminder so the LLM does not
        # lose track of it across the system/user boundary.
        user_lines.append("(body state snapshot is in the system prompt; it will update next tick)")
        user_lines.append("")
        if retrieval_bundle.short_term_context:
            for i, ctx in enumerate(retrieval_bundle.short_term_context):
                user_lines.append(f"# Recent stimulus #{i+1} (short-term context)")
                user_lines.append(f"- {ctx.summary}")
                user_lines.append("")
        if retrieval_bundle.mid_term_hits:
            user_lines.append("# Mid-term memory (relevant past events)")
            for i, m in enumerate(retrieval_bundle.mid_term_hits[:2]):
                user_lines.append(f"- {m.summary}")
            user_lines.append("")
        if retrieval_bundle.autobiographical_hits:
            user_lines.append("# Autobiographical anchor (deep identity memory)")
            for m in retrieval_bundle.autobiographical_hits[:1]:
                user_lines.append(f"- {m.summary}")
            user_lines.append("")
        user_lines.append("# Current input (right now)")
        user_lines.append("(The most recent short-term context above is what just happened.)")
        user_lines.append("")
        user_lines.append("Continuation pressure: " + ("active" if continuation_state.active else "inactive"))
        user_msg = LlmMessage(role="user", content="\n".join(user_lines))
        return (system_msg, user_msg)

    ite.LlmBackedInternalThoughtPath._build_messages = v3_build_messages

    # Expose the per-tick state injector to run_experiment.
    handle._r79d_v3_state = _r79d_state  # type: ignore[attr-defined]


def _build_v3_placeholders(handle, path_cls, result):
    """Compute the four {placeholder} kwargs for the v3 system template.

    Returns a dict with keys: body_state, attention_field, available_channels,
    ready_channels. Sources live state from the most recent tick result if
    available, else from the handle's bound stage refs.
    """
    hormones: dict = {}
    feelings: dict = {}
    if result is not None:
        h = get_hormone_state_from_result(result)
        f = get_feeling_state_from_result(result)
        hormones = dict(h)
        feelings = {k: v for k, v in f.items() if k in ("arousal", "valence", "tension", "comfort")}
    else:
        neuromod = handle.neuromodulator_stage
        feel_stage = handle.feeling_stage
        levels_obj = neuromod._prior_state.levels if (neuromod is not None and neuromod._prior_state is not None) else None
        feeling_obj = feel_stage._prior_state.feeling if (feel_stage is not None and feel_stage._prior_state is not None) else None
        if levels_obj is not None:
            for fld in ("dopamine", "norepinephrine", "serotonin", "acetylcholine",
                        "cortisol", "oxytocin", "opioid_tone", "excitation", "inhibition"):
                hormones[fld] = getattr(levels_obj, fld)
        if feeling_obj is not None:
            feelings["arousal"] = feeling_obj.arousal
            feelings["valence"] = feeling_obj.valence
            feelings["tension"] = feeling_obj.tension

    # Read the most recent stimulus from the script source if available.
    focused_text = ""
    try:
        from helios_v2.tests.r79d.framework import ScriptedCliSource  # local
        sources = getattr(handle.ingress, "_sources", None) or []
        for src in sources:
            if isinstance(src, ScriptedCliSource):
                idx = max(0, src.index - 1)
                if 0 <= idx < len(src.script):
                    focused_text = src.script[idx]
                break
    except Exception:
        pass

    # R79-D: only the cli channel is wired (ScriptedCliSource delivers through
    # it; no other channel owners are bound on the test handle).
    available_channels = ("cli",)
    ready_channels = ("cli",)

    state_summary = {
        "body_state": "",  # forces helper to fall through to hormones/feelings
        "hormones": hormones,
        "feelings": feelings,
    }
    stimulus_summary = {
        "focused": focused_text,
        "peripheral": (),
        "filtered": (),
    }
    capability_summary = {
        "available_channels": available_channels,
        "ready_channels": ready_channels,
    }

    body_state_text = path_cls._render_body_state(state_summary)
    attention_field_text = path_cls._render_attention_field(stimulus_summary, state_summary)
    available_channels_text = path_cls._render_available_channels(capability_summary)
    ready_channels_tuple, _ = path_cls._ready_channels(capability_summary)
    ready_channels_text = ", ".join(repr(c) for c in ready_channels_tuple) if ready_channels_tuple else "(none)"
    return {
        "body_state": body_state_text,
        "attention_field": attention_field_text,
        "available_channels": available_channels_text,
        "ready_channels": ready_channels_text,
    }


# ============================================================
# Run one experiment
# ============================================================


def run_experiment(config: ExperimentConfig) -> dict:
    from helios_v2.composition.runtime_assembly import assemble_runtime

    scenario = config.scenario
    out_dir = config.output_dir / scenario.id
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / f"{scenario.id}.jsonl"
    report_path = out_dir / f"{scenario.id}.report.md"

    if jsonl_path.exists() and not config.force:
        records = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
        return {
            "scenario_id": scenario.id, "records": records,
            "assertion_results": [], "elapsed_total_s": 0.0,
            "jsonl_path": jsonl_path, "report_path": report_path, "cached": True,
        }

    from . import _io
    _io.write_line("")
    _io.write_line("=" * 60)
    _io.write_line(f"[scenario {scenario.id}] {scenario.description}")
    _io.write_line("=" * 60)

    if config.use_real_llm:
        gateway = RealLlmGateway(model=config.llm_model, timeout_s=config.timeout_per_tick)
    else:
        gateway = NoopLlmGateway()

    source = ScriptedCliSource(scenario.stimulus_script)
    handle = assemble_runtime(deterministic_thought=False, gateway=gateway)
    handle.startup()
    handle.ingress.register_source(source)
    inject_v3_prompt(handle)

    records = []
    prior_h = None
    prior_f = None
    t_total_start = time.time()
    # Apply repeat expansion
    effective_script = list(scenario.stimulus_script)
    if scenario.repeat and effective_script:
        effective_script = effective_script * scenario.repeat
    for tick_id in range(1, len(effective_script) + 1):
        _io.write_line("")
        _io.write_line(f"--- {scenario.id} tick {tick_id} ---")
        t0 = time.time()
        result = handle.tick()
        elapsed = time.time() - t0

        # R79-C: feed the latest tick result into the v3 prompt builder so
        # the LLM sees live hormone/feeling/channel state in the system
        # message. The v3 prompt is re-rendered per-tick.
        r79d_v3_state = getattr(handle, "_r79d_v3_state", None)
        if r79d_v3_state is not None:
            r79d_v3_state["last_result"] = result

        h = get_hormone_state_from_result(result)
        f = get_feeling_state_from_result(result)
        s = get_salience_from_result(result)
        llm = gateway.captured[-1] if gateway.captured else None

        delta = {}
        if prior_h and h:
            for k in prior_h:
                d = h[k] - prior_h[k]
                if abs(d) > 0.001:
                    delta[f"h_{k}"] = round(d, 4)
        if prior_f and f:
            for k in prior_f:
                d = f[k] - prior_f[k]
                if abs(d) > 0.001:
                    delta[f"f_{k}"] = round(d, 4)

        llm_parsed = llm.parsed_json if llm else None
        llm_usage = llm.usage if llm else {}

        rec = TickRecord(
            tick_id=tick_id,
            stimulus_text=effective_script[tick_id-1],
            hormone_state=h,
            feeling_state=f,
            salience=s,
            llm_output={
                "what_i_feel": (llm_parsed or {}).get("what_i_feel"),
                "what_i_think": (llm_parsed or {}).get("what_i_think"),
                "i_want_to_say": (llm_parsed or {}).get("i_want_to_say"),
                "i_will_send_it": (llm_parsed or {}).get("i_will_send_it"),
                "i_send_through": (llm_parsed or {}).get("i_send_through"),
                "remember_this": (llm_parsed or {}).get("remember_this"),
                "remember_because": (llm_parsed or {}).get("remember_because"),
                "i_want_to_think_more": (llm_parsed or {}).get("i_want_to_think_more"),
                "think_more_about": (llm_parsed or {}).get("think_more_about"),
                "act_type": (llm_parsed or {}).get("act_type"),
                "usage": llm_usage or {},
            },
            delta=delta,
        )
        records.append(rec)
        prior_h = h
        prior_f = f

        if h:
            _io.write_line(f"  DA={h['dopamine']:.2f} NE={h['norepinephrine']:.2f} "
                  f"Cort={h['cortisol']:.2f} 5HT={h['serotonin']:.2f} "
                  f"Oxy={h['oxytocin']:.2f} Opioid={h['opioid_tone']:.2f}")
        if f:
            _io.write_line(f"  arousal={f['arousal']:.2f} valence={f['valence']:.2f} tension={f['tension']:.2f} "
                  f"comfort={f['comfort']:.2f} social_safety={f['social_safety']:.2f}")
        if s:
            _io.write_line(f"  salience agg={s['aggregate']:.2f} top={s['top_dimension']}({s['top_score']:.2f})")
        feel = rec.llm_output.get("what_i_feel")
        if feel:
            _io.write_line(f"  LLM feel: {feel[:80]!r}")
        if rec.llm_output.get("think_more_about"):
            _io.write_line(f"  LLM think_more: {rec.llm_output['think_more_about'][:60]!r}")
        if delta:
            _io.write_line(f"  delta: {delta}")
        _io.write_line(f"  elapsed: {elapsed:.1f}s")

    elapsed_total = time.time() - t_total_start

    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")

    from .assertions import evaluate_assertions
    assertion_results = evaluate_assertions(scenario.assertions, [asdict(r) for r in records])

    _write_report(report_path, scenario, records, assertion_results, elapsed_total)

    _io.write_line("")
    _io.write_line(f"[scenario {scenario.id}] wrote {jsonl_path}")
    _io.write_line(f"[scenario {scenario.id}] {len(assertion_results)} assertions evaluated; "
          f"{sum(1 for a in assertion_results if a.passed)} PASS, "
          f"{sum(1 for a in assertion_results if not a.passed)} FAIL")

    return {
        "scenario_id": scenario.id,
        "records": [asdict(r) for r in records],
        "assertion_results": [asdict(a) for a in assertion_results],
        "elapsed_total_s": elapsed_total,
        "jsonl_path": jsonl_path,
        "report_path": report_path,
        "cached": False,
    }


def _write_report(report_path: Path, scenario: Scenario, records: list[TickRecord], assertion_results: list[AssertionResult], elapsed_total: float):
    L = []
    L.append(f"# R79-D scenario: {scenario.id}")
    L.append("")
    L.append(f"**Description**: {scenario.description}")
    L.append(f"**Ticks**: {len(records)}")
    L.append(f"**Elapsed**: {elapsed_total:.1f}s")
    L.append("")
    L.append("## 1. Assertion results")
    L.append("")
    if not assertion_results:
        L.append("(no assertions defined)")
    else:
        L.append("| Assertion | Result | Detail |")
        L.append("|-----------|--------|--------|")
        for a in assertion_results:
            status = "PASS" if a.passed else "FAIL"
            L.append(f"| {a.name} | **{status}** | {a.detail} |")
    L.append("")
    L.append("## 2. Per-tick state")
    L.append("")
    L.append("| # | Stimulus | DA | NE | Cort | 5HT | Oxy | valence | tension | LLM feel |")
    L.append("|---|----------|----|----|------|-----|-----|---------|---------|----------|")
    for r in records:
        h = r.hormone_state
        f = r.feeling_state
        feel = (r.llm_output.get("what_i_feel") or "")[:40]
        L.append(f"| {r.tick_id} | {r.stimulus_text[:30]!r} | "
                 f"{h.get('dopamine',0):.2f} | {h.get('norepinephrine',0):.2f} | "
                 f"{h.get('cortisol',0):.2f} | {h.get('serotonin',0):.2f} | "
                 f"{h.get('oxytocin',0):.2f} | "
                 f"{f.get('valence',0):.2f} | {f.get('tension',0):.2f} | "
                 f"{feel!r} |")
    L.append("")
    L.append("## 3. Per-tick deltas")
    L.append("")
    L.append("| # | delta_h | delta_f |")
    L.append("|---|---------|---------|")
    for r in records:
        d_h = {k.removeprefix("h_"): v for k, v in r.delta.items() if k.startswith("h_")}
        d_f = {k.removeprefix("f_"): v for k, v in r.delta.items() if k.startswith("f_")}
        L.append(f"| {r.tick_id} | {d_h if d_h else '—'} | {d_f if d_f else '—'} |")
    L.append("")
    report_path.write_text("\n".join(L), encoding="utf-8")


def run_all(scenarios_dir: Path, output_dir: Path, **kwargs) -> list[dict]:
    results = []
    for scenario_path in sorted(scenarios_dir.glob("*.json")):
        scenario = Scenario.from_json(scenario_path)
        cfg = ExperimentConfig(scenario=scenario, output_dir=output_dir, **kwargs)
        results.append(run_experiment(cfg))
    return results
