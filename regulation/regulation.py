"""
Helios 情感调节系统 — Regulation Engine
=========================================

不是"情感高 → 做X"的写死映射。
而是"情感偏离舒适区 → 记忆中搜索能缓解的行为 → 尝试 → 观察效果 → 学习"。

理论: 行为是情感稳态调节的手段。
不是 "我想说话"，而是 "我感到孤独，说话曾让我感觉好一些"。

记忆驱动的调节回路:
  情感状态偏离基线
    → 检索: 历史上什么行为缓解过这种偏离？
    → 候选: 从能力池中筛选可执行的行为
    → 评估: 每个候选的预期调节效果
    → 选择: 最佳行为 → 执行
    → 观察: 实际效果 → 更新记忆

Bootstrap:
  初期没有经验时，使用常识性初始关联 (可被后续经验覆盖)。
"""

import time
import logging
import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from collections import defaultdict

from behavior_registry import RuntimeBehaviorCatalog
from helios_io.bootstrap_behavior_specs import (
    REGULATION_CHANNEL_BOOTSTRAP,
    REGULATION_INTERNAL_BOOTSTRAP,
)
from helios_io.action_models import ActionProposal
from helios_io.action_models import ExecutionFeedback
from .constants import DRIVE_ACTION_RELEVANCE
from .policy import ActionCandidate, RegulationAssessment, RegulationPolicy
from utils import clamp

# ═══════════════════════════════════════════════
# 数据类型
# ═══════════════════════════════════════════════

@dataclass
class RegulationMemory:
    """
    一条调节记忆: "上次做X，让Y情感从A变到B"
    
    这是 Helios 自己学到的，不是预设的。
    """
    action_type: str           # 行为类型 (speak_care / browse / ...)
    emotion_modulated: str     # 被调节的情感 (Panksepp 系统名)
    delta_valence: float       # 效价变化
    delta_activation: float    # 该情感激活变化
    success_rating: float      # 成功率 0-1
    timestamp: float
    count: int = 1             # 经历次数
    
    def update(self, delta_valence: float, delta_activation: float):
        """用新经验更新"""
        self.count += 1
        alpha = 1.0 / self.count  # 渐进平均
        self.delta_valence = (1 - alpha) * self.delta_valence + alpha * delta_valence
        self.delta_activation = (1 - alpha) * self.delta_activation + alpha * delta_activation
        self.success_rating = clamp(
            self.success_rating + (0.1 if delta_valence > 0 else -0.05),
            0.0, 1.0
        )
        self.timestamp = time.time()

# ═══════════════════════════════════════════════
# Bootstrap 初始关联 (常识, 可被经验覆盖)
# ═══════════════════════════════════════════════

AVAILABLE_ACTIONS = {
    **{
        action_name: {
            "cooldown": int(config["cooldown"]),
            "night_suppress": bool(config["night_suppress"]),
            "hint": str(config["hint"]),
        }
        for action_name, config in REGULATION_CHANNEL_BOOTSTRAP.items()
    },
    **{
        action_name: {
            "cooldown": int(config["cooldown"]),
            "night_suppress": bool(config["night_suppress"]),
            "hint": str(config["hint"]),
        }
        for action_name, config in REGULATION_INTERNAL_BOOTSTRAP.items()
    },
}

# "当 PANIC 偏离基线时，这些行为历史上有效" (初始猜测)
BOOTSTRAP_REGULATION = [
    # (action, emotion_modulated, delta_valence, delta_activation)
    ("speak_missing",   "PANIC",    +0.3,  -0.3),   # 联系主人缓解分离焦虑
    ("speak_fear",      "FEAR",     +0.2,  -0.3),   # 寻求安抚缓解恐惧
    ("speak_care",      "CARE",     +0.2,  +0.1),   # 关怀表达增进温暖
    ("speak_play",      "PLAY",     +0.3,  +0.1),   # 嬉戏增进快乐
    ("browse",          "SEEKING",  +0.3,  -0.2),   # 探索满足好奇心
    ("search",          "SEEKING",  +0.2,  -0.2),   # 搜索也满足好奇
    ("learn",           "SEEKING",  +0.4,  -0.3),   # 学习深度满足
    ("reflect",         "RAGE",     +0.1,  -0.2),   # 反思缓解愤怒
    ("reflect",         "PANIC",    +0.1,  -0.1),   # 反思轻微缓解焦虑
    ("check_system",    "FEAR",     +0.1,  -0.1),   # 检查系统缓解不安
    ("speak_share",     "SEEKING",  +0.3,  +0.0),   # 分享发现
    ("speak_complain",  "RAGE",     +0.1,  -0.1),   # 抱怨释放愤怒
    ("idle",            "ALL",      +0.05, -0.05),  # 什么都不做也有一点调节
]

# ═══════════════════════════════════════════════
# 驱动-行为关联 (drive → action relevance)
# ═══════════════════════════════════════════════

# ═══════════════════════════════════════════════
# 情感调节引擎
# ═══════════════════════════════════════════════

class RegulationEngine:
    """
    情感调节引擎 — 记忆驱动的行为选择
    
    不是映射表，是基于经验的学习系统。
    """
    
    def __init__(self,
                 baseline_valence: float = 0.05,
                 baseline_activation: float = 0.15,
                 comfort_deviation: float = 0.2,
                 data_dir: str = "data",
                 behavior_catalog: Optional[RuntimeBehaviorCatalog] = None):
        
        self.baseline_valence = baseline_valence
        self.baseline_activation = baseline_activation
        self.comfort_deviation = comfort_deviation  # 偏离超过此值 → 需要调节
        
        # 调节记忆库 {action_type: {emotion: RegulationMemory}}
        self.memories: Dict[str, Dict[str, RegulationMemory]] = defaultdict(dict)
        
        # 加载 bootstrap
        self._load_bootstrap()
        
        # 运行时状态
        self._last_executed: Dict[str, float] = {}  # action → timestamp
        self._last_panksepp: Dict[str, float] = {}   # 执行前的状态 (用于评估效果)
        self._last_valence: float = 0.0
        self._pending_observation: Optional[str] = None  # 等待观察的行为
        self.last_selected_action: Optional[str] = None
        self.last_selected_score: float = 0.0
        
        # 持久化路径
        self.data_dir = data_dir
        self.memories_path = os.path.join(data_dir, "regulation_memories.json")
        self.behavior_catalog = behavior_catalog or RuntimeBehaviorCatalog.from_db_path(
            os.path.join(data_dir, RuntimeBehaviorCatalog.DEFAULT_DB_FILENAME)
        )
        self.behavior_catalog.ensure_bootstrap_behaviors()
        self.policy = RegulationPolicy(
            behavior_catalog=self.behavior_catalog,
            baseline_valence=self.baseline_valence,
            baseline_activation=self.baseline_activation,
            comfort_deviation=self.comfort_deviation,
        )
        
        # 日志
        self.log = logging.getLogger("helios.regulation")
        
        # 统计
        self.total_regulations = 0
        self.action_history: List[dict] = []
        self.recent_execution_outcomes: List[dict[str, Any]] = []
        self.last_assessment: Optional[RegulationAssessment] = None
    
    def _load_bootstrap(self):
        """加载常识性初始关联"""
        for action, emotion, dv, da in BOOTSTRAP_REGULATION:
            mem = RegulationMemory(
                action_type=action,
                emotion_modulated=emotion,
                delta_valence=dv,
                delta_activation=da,
                success_rating=0.5,  # 初始不确定
                timestamp=0.0,
                count=1,
            )
            self.memories[action][emotion] = mem
    
    def note_action_executed(self, action_type: str):
        """标记行为已执行 (供外部调用)"""
        if action_type in self.memories:
            now = time.time()
            for mem in self.memories[action_type].values():
                mem.timestamp = now
    
    # ═══════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════
    
    def tick(self, panksepp: Dict[str, float], valence: float,
             hour_of_day: int,
             drive_urgency: float = 0.0,
             drive_dominant: str = "",
             neurochem_gate: Optional[object] = None,
             temporal_gate: Optional[object] = None) -> Optional[str]:
        """
        每 tick 调用。
        
        Args:
            panksepp: 当前 Panksepp 系统激活值
            valence: 当前效价
            hour_of_day: 当前小时 (0-23)
            drive_urgency: DriveOracle 总驱动紧迫度 (0-1)
            drive_dominant: 当前最强驱动名 (curiosity/social/homeostatic/achievement/aesthetic)
        
        返回: 选中的 action_type (字符串) 或 None
        """
        proposals = self.generate_action_proposals(
            panksepp=panksepp,
            valence=valence,
            hour_of_day=hour_of_day,
            drive_urgency=drive_urgency,
            drive_dominant=drive_dominant,
            neurochem_gate=neurochem_gate,
            temporal_gate=temporal_gate,
        )
        return proposals[0].behavior_name if proposals else None

    def evaluate_regulation(self,
             panksepp: Dict[str, float], valence: float,
             hour_of_day: int,
             drive_urgency: float = 0.0,
             drive_dominant: str = "",
             neurochem_gate: Optional[object] = None,
             temporal_gate: Optional[object] = None,
             personality_projection: Optional[object] = None,
             dominant_emotions: Optional[List[str]] = None,
             recent_execution_outcomes: Optional[List[dict[str, Any]]] = None) -> RegulationAssessment:
        signals = self.policy.collect_signals(
            panksepp=panksepp,
            valence=valence,
            hour_of_day=hour_of_day,
            drive_urgency=drive_urgency,
            drive_dominant=drive_dominant,
            dominant_emotions=dominant_emotions,
            recent_execution_outcomes=recent_execution_outcomes or self.recent_execution_outcomes[-5:],
            personality_projection=personality_projection,
            neurochem_gate=neurochem_gate,
            temporal_gate=temporal_gate,
        )
        return self.policy.assess(
            signals,
            memories=self.memories,
            last_executed=self._last_executed,
        )

    def generate_action_proposals(
        self,
        *,
        panksepp: Dict[str, float],
        valence: float,
        hour_of_day: int,
        tick: int = 0,
        timestamp: Optional[float] = None,
        candidate_channels: Optional[List[str]] = None,
        candidate_channel_resolver: Optional[Callable[[str], Sequence[str]]] = None,
        params: Optional[Dict[str, object]] = None,
        drive_urgency: float = 0.0,
        drive_dominant: str = "",
        dominant_emotions: Optional[List[str]] = None,
        personality_projection: Optional[object] = None,
        neurochem_gate: Optional[object] = None,
        temporal_gate: Optional[object] = None,
    ) -> List[ActionProposal]:
        if not panksepp:
            self.last_assessment = None
            return []

        self._observe_last_action(panksepp, valence)
        assessment = self.evaluate_regulation(
            panksepp=panksepp,
            valence=valence,
            hour_of_day=hour_of_day,
            drive_urgency=drive_urgency,
            drive_dominant=drive_dominant,
            dominant_emotions=dominant_emotions,
            personality_projection=personality_projection,
            neurochem_gate=neurochem_gate,
            temporal_gate=temporal_gate,
        )
        self.last_assessment = assessment
        if not assessment.wants_regulation or not assessment.selected_action:
            return []

        self._commit_selected_assessment(
            assessment,
            panksepp=panksepp,
            valence=valence,
            drive_dominant=drive_dominant,
            drive_urgency=drive_urgency,
        )

        resolved_channels = list(candidate_channels or [])
        if candidate_channel_resolver is not None:
            resolved_channels = list(candidate_channel_resolver(assessment.selected_action) or [])
        return self.policy.propose(
            assessment,
            tick=tick,
            timestamp=timestamp,
            candidate_channels=resolved_channels,
            params=params,
            personality_projection=personality_projection,
            neurochem_gate=neurochem_gate,
            temporal_gate=temporal_gate,
            recent_action=self.last_selected_action or "",
        )

    def _commit_selected_assessment(
        self,
        assessment: RegulationAssessment,
        *,
        panksepp: Dict[str, float],
        valence: float,
        drive_dominant: str,
        drive_urgency: float,
    ) -> None:
        self._last_panksepp = dict(panksepp)
        self._last_valence = valence
        self._pending_observation = assessment.selected_action
        self._last_executed[assessment.selected_action] = time.time()

        self.total_regulations += 1
        self.last_selected_action = assessment.selected_action
        self.last_selected_score = assessment.selected_score

        self.log.info(
            f"调节: {assessment.selected_action} "
            f"(显著偏离: {[d[0] for d in assessment.deviations[:3]]}, "
            f"final_score={assessment.selected_score:.3f} "
            f"drive={drive_dominant}:{drive_urgency:.2f})"
        )

        self.action_history.append({
            "time": time.time(),
            "action": assessment.selected_action,
            "score": round(assessment.selected_score, 3),
            "deviations": [(d[0], round(d[1], 3)) for d in assessment.deviations[:3]],
            "drive_dominant": drive_dominant,
            "drive_urgency": round(drive_urgency, 3),
        })

    def build_action_proposal(
        self,
        action_type: str,
        *,
        score: Optional[float] = None,
        tick: int = 0,
        timestamp: Optional[float] = None,
        candidate_channels: Optional[List[str]] = None,
        params: Optional[Dict[str, object]] = None,
        drive_dominant: str = "",
        drive_urgency: float = 0.0,
        dominant_emotions: Optional[List[str]] = None,
        personality_projection: Optional[object] = None,
        neurochem_gate: Optional[object] = None,
        temporal_gate: Optional[object] = None,
    ) -> ActionProposal:
        return self.policy.build_action_proposal(
            action_type,
            score=float(self.last_selected_score if score is None else score),
            tick=tick,
            timestamp=timestamp,
            candidate_channels=candidate_channels,
            params=params,
            drive_dominant=drive_dominant,
            drive_urgency=drive_urgency,
            dominant_emotions=dominant_emotions,
            personality_projection=personality_projection,
            neurochem_gate=neurochem_gate,
            temporal_gate=temporal_gate,
            recent_action=self.last_selected_action or "",
        )

    def on_behavior_result(self, action_type: str, success: bool, result: Optional[dict] = None):
        """Receive execution feedback from the behavior layer."""
        if success:
            self.note_action_executed(action_type)
        else:
            if self._pending_observation == action_type:
                self._pending_observation = None
            self.log.debug("行为执行失败: %s result=%s", action_type, result or {})

        self.recent_execution_outcomes.append(
            {
                "action": action_type,
                "success": bool(success),
                "channel_id": str((result or {}).get("channel_id", "") or ""),
                "op_name": str((result or {}).get("op_name", "") or ""),
                "observed_at_tick": int((result or {}).get("tick", 0) or 0),
                "observed_at_ts": time.time(),
            }
        )
        self.recent_execution_outcomes = self.recent_execution_outcomes[-20:]

    def on_execution_feedback(self, feedback: ExecutionFeedback) -> None:
        payload = dict(feedback.result_details)
        payload.setdefault("tick", feedback.observed_at_tick)
        payload.setdefault("channel_id", feedback.channel_id)
        payload.setdefault("op_name", feedback.op_name)
        self.on_behavior_result(
            action_type=feedback.behavior_name,
            success=feedback.success,
            result=payload,
        )
    
    # ═══════════════════════════════════════════
    # 偏离检测
    # ═══════════════════════════════════════════
    
    def _detect_deviations(self, panksepp: Dict[str, float],
                           valence: float) -> List[Tuple[str, float]]:
        return self.policy.detect_deviations(panksepp, valence)
    
    # ═══════════════════════════════════════════
    # 候选行为检索
    # ═══════════════════════════════════════════
    
    def _query_candidates(self, sys_name: str, deviation: float,
                          hour_of_day: int) -> List[ActionCandidate]:
        return self.policy.query_candidates(
            sys_name,
            deviation,
            hour_of_day,
            memories=self.memories,
            last_executed=self._last_executed,
        )
    
    # ═══════════════════════════════════════════
    # 驱动-情感综合评分
    # ═══════════════════════════════════════════
    
    def _score_candidates_with_drives(self, candidates: List[ActionCandidate],
                                       drive_urgency: float,
                                       drive_dominant: str,
                                       neurochem_gate: Optional[object] = None,
                                       temporal_gate: Optional[object] = None):
        self.policy.score_candidates_with_drives(
            candidates,
            drive_urgency,
            drive_dominant,
            neurochem_gate=neurochem_gate,
            temporal_gate=temporal_gate,
        )
    
    # ═══════════════════════════════════════════
    # 效果观察 & 学习
    # ═══════════════════════════════════════════
    
    def _observe_last_action(self, current_panksepp: Dict[str, float],
                             current_valence: float):
        """观察上一个行为的情感效果，更新记忆"""
        if not self._pending_observation:
            return
        
        action = self._pending_observation
        self._pending_observation = None
        
        if not self._last_panksepp:
            return
        
        # 计算效果
        delta_valence = current_valence - self._last_valence
        
        # 找出变化最大的情感
        max_delta = 0.0
        max_emotion = None
        for sys_name in self._last_panksepp:
            prev = self._last_panksepp.get(sys_name, 0.0)
            curr = current_panksepp.get(sys_name, 0.0)
            delta = prev - curr  # 正数=降低了
            if abs(delta) > abs(max_delta):
                max_delta = delta
                max_emotion = sys_name
        
        if max_emotion is None:
            return
        
        # 更新或创建记忆
        key = (action, max_emotion)
        if action in self.memories and max_emotion in self.memories[action]:
            self.memories[action][max_emotion].update(delta_valence, max_delta)
        else:
            self.memories[action][max_emotion] = RegulationMemory(
                action_type=action,
                emotion_modulated=max_emotion,
                delta_valence=delta_valence,
                delta_activation=max_delta,
                success_rating=0.5,
                timestamp=time.time(),
            )
        
        self.log.debug(
            f"学习: {action} → {max_emotion} "
            f"(Δv={delta_valence:+.3f} Δa={max_delta:+.3f})"
        )
    
    # ═══════════════════════════════════════════
    # 持久化
    # ═══════════════════════════════════════════
    
    def save(self):
        """保存调节记忆"""
        os.makedirs(self.data_dir, exist_ok=True)
        data = {}
        for action, emotions in self.memories.items():
            data[action] = {}
            for emotion, mem in emotions.items():
                data[action][emotion] = {
                    "delta_valence": mem.delta_valence,
                    "delta_activation": mem.delta_activation,
                    "success_rating": mem.success_rating,
                    "count": mem.count,
                    "timestamp": mem.timestamp,
                }
        
        with open(self.memories_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load(self):
        """加载调节记忆"""
        if not os.path.exists(self.memories_path):
            return
        
        with open(self.memories_path, "r") as f:
            data = json.load(f)
        
        for action, emotions in data.items():
            for emotion, mem_data in emotions.items():
                self.memories[action][emotion] = RegulationMemory(
                    action_type=action,
                    emotion_modulated=emotion,
                    delta_valence=mem_data["delta_valence"],
                    delta_activation=mem_data["delta_activation"],
                    success_rating=mem_data["success_rating"],
                    timestamp=mem_data.get("timestamp", 0),
                    count=mem_data.get("count", 1),
                )
    
    # ═══════════════════════════════════════════
    # 查询
    # ═══════════════════════════════════════════
    
    def get_state(self) -> dict:
        assessment = self.last_assessment
        assessment_payload = {}
        if assessment is not None:
            assessment_payload = {
                "wants_regulation": bool(assessment.wants_regulation),
                "selected_action": str(assessment.selected_action or ""),
                "selected_score": round(float(assessment.selected_score or 0.0), 4),
                "drive_dominant": str(assessment.drive_dominant or ""),
                "drive_urgency": round(float(assessment.drive_urgency or 0.0), 4),
                "reason_summary": str(assessment.reason_summary or ""),
                "dominant_emotions": [
                    str(item) for item in list(getattr(assessment, "dominant_emotions", []) or []) if str(item)
                ],
                "deviations": [
                    {"name": str(name), "score": round(float(score or 0.0), 4)}
                    for name, score in list(getattr(assessment, "deviations", []) or [])[:5]
                ],
                "candidate_actions": [
                    str(getattr(candidate, "action_type", "") or "")
                    for candidate in list(getattr(assessment, "candidates", []) or [])[:5]
                    if str(getattr(candidate, "action_type", "") or "")
                ],
            }
        return {
            "total_regulations": self.total_regulations,
            "memories_count": sum(
                len(emotions) for emotions in self.memories.values()
            ),
            "recent_actions": self.action_history[-5:],
            "last_assessment": assessment_payload,
        }
    
    def get_regulation_map(self) -> dict:
        """返回当前学到的调节映射 (action → 调节什么情感 → 效果)"""
        result = {}
        for action, emotions in self.memories.items():
            result[action] = {}
            for emotion, mem in emotions.items():
                result[action][emotion] = {
                    "delta_v": round(mem.delta_valence, 3),
                    "delta_a": round(mem.delta_activation, 3),
                    "success": round(mem.success_rating, 2),
                    "count": mem.count,
                }
        return result


