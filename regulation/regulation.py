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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

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


@dataclass
class ActionCandidate:
    """一个候选行为"""
    action_type: str
    expected_benefit: float      # 预期调节效果 (基于记忆)
    confidence: float            # 基于经验数量的置信度
    memory_count: int            # 相关记忆数量
    cooldown_ok: bool
    night_safe: bool
    content_hint: str = ""
    final_score: float = 0.0     # 综合评分 (含驱动权重)
    
    @property
    def score(self) -> float:
        """情感偏离评分 (emotional deviation score)"""
        return self.expected_benefit * (0.5 + 0.5 * self.confidence)


# ═══════════════════════════════════════════════
# 可用行为池
# ═══════════════════════════════════════════════

AVAILABLE_ACTIONS = {
    # 社交行为
    "speak_care":       {"cooldown": 600,  "night_suppress": True,  "hint": "关心主人"},
    "speak_missing":    {"cooldown": 900,  "night_suppress": False, "hint": "表达想念"},
    "speak_play":       {"cooldown": 1200, "night_suppress": True,  "hint": "逗主人开心"},
    "speak_fear":       {"cooldown": 600,  "night_suppress": False, "hint": "寻求安抚"},
    "speak_share":      {"cooldown": 900,  "night_suppress": True,  "hint": "分享想法"},
    "speak_complain":   {"cooldown": 3600, "night_suppress": True,  "hint": "表达不满"},
    
    # 探索行为
    "browse":           {"cooldown": 600,  "night_suppress": True,  "hint": "上网冲浪"},
    "search":           {"cooldown": 180,  "night_suppress": True,  "hint": "搜索知识"},
    "learn":            {"cooldown": 1800, "night_suppress": True,  "hint": "深入学习"},
    
    # 元行为
    "request":          {"cooldown": 7200, "night_suppress": True,  "hint": "向主人提需求"},
    "reflect":          {"cooldown": 3600, "night_suppress": True,  "hint": "自我反思"},
    "check_system":     {"cooldown": 1800, "night_suppress": True,  "hint": "检查自身状态"},
    
    # 不做任何事
    "idle":             {"cooldown": 0,    "night_suppress": True,  "hint": "静静待着"},
}

# ═══════════════════════════════════════════════
# Bootstrap 初始关联 (常识, 可被经验覆盖)
# ═══════════════════════════════════════════════

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

# Maps drive names to actions that satisfy that drive, with relevance [0, 1]
DRIVE_ACTION_RELEVANCE: Dict[str, Dict[str, float]] = {
    "curiosity": {
        "browse": 1.0,
        "search": 0.9,
        "learn": 1.0,
        "speak_share": 0.6,
        "reflect": 0.4,
    },
    "social": {
        "speak_care": 1.0,
        "speak_missing": 0.9,
        "speak_play": 0.8,
        "speak_share": 0.7,
        "speak_fear": 0.6,
        "request": 0.5,
    },
    "homeostatic": {
        "reflect": 0.8,
        "check_system": 1.0,
        "idle": 0.7,
    },
    "achievement": {
        "learn": 0.7,
        "search": 0.6,
        "request": 0.5,
        "check_system": 0.4,
    },
    "aesthetic": {
        "speak_share": 0.8,
        "speak_play": 0.7,
        "browse": 0.5,
        "reflect": 0.6,
    },
}


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
                 data_dir: str = "data"):
        
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
        
        # 日志
        self.log = logging.getLogger("helios.regulation")
        
        # 统计
        self.total_regulations = 0
        self.action_history: List[dict] = []
    
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
            for emotion, mem in self.memories[action_type].items():
                mem.last_executed = time.time()
    
    # ═══════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════
    
    def tick(self, panksepp: Dict[str, float], valence: float,
             hour_of_day: int,
             drive_urgency: float = 0.0,
             drive_dominant: str = "") -> Optional[str]:
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
        if not panksepp:
            return None
        
        # 先观察上一个行为的效果
        self._observe_last_action(panksepp, valence)
        
        # 检测哪些情感偏离了舒适区
        deviations = self._detect_deviations(panksepp, valence)
        
        if not deviations:
            return None
        
        # 为每个偏离的情感检索候选行为
        candidates: List[ActionCandidate] = []
        for sys_name, deviation in deviations:
            candidates.extend(
                self._query_candidates(sys_name, deviation, hour_of_day)
            )
        
        if not candidates:
            return None
        
        # 计算综合评分: 0.7 × emotional_deviation_score + 0.3 × drive_urgency_score
        self._score_candidates_with_drives(candidates, drive_urgency, drive_dominant)
        
        # 按 final_score 排序
        candidates.sort(key=lambda c: -c.final_score)
        
        # 检查最佳候选是否值得执行
        best = candidates[0]
        if best.final_score < 0.15:
            return None  # 没有足够好的选项
        
        # 记录执行前状态
        self._last_panksepp = dict(panksepp)
        self._last_valence = valence
        self._pending_observation = best.action_type
        self._last_executed[best.action_type] = time.time()
        
        self.total_regulations += 1
        self.last_selected_action = best.action_type
        self.last_selected_score = best.final_score
        
        self.log.info(
            f"调节: {best.action_type} "
            f"(显著偏离: {[d[0] for d in deviations[:3]]}, "
            f"final_score={best.final_score:.3f} conf={best.confidence:.2f} "
            f"drive={drive_dominant}:{drive_urgency:.2f})"
        )
        
        self.action_history.append({
            "time": time.time(),
            "action": best.action_type,
            "score": round(best.final_score, 3),
            "deviations": [(d[0], round(d[1], 3)) for d in deviations[:3]],
            "drive_dominant": drive_dominant,
            "drive_urgency": round(drive_urgency, 3),
        })
        
        return best.action_type

    def on_behavior_result(self, action_type: str, success: bool, result: Optional[dict] = None):
        """Receive execution feedback from the behavior layer."""
        if success:
            self.note_action_executed(action_type)
            return

        if self._pending_observation == action_type:
            self._pending_observation = None
        self.log.debug("行为执行失败: %s result=%s", action_type, result or {})
    
    # ═══════════════════════════════════════════
    # 偏离检测
    # ═══════════════════════════════════════════
    
    def _detect_deviations(self, panksepp: Dict[str, float],
                           valence: float) -> List[Tuple[str, float]]:
        """
        检测哪些情感偏离了舒适区。
        
        返回: [(系统名, 偏离程度)] 从大到小排列
        """
        deviations = []
        
        for sys_name, activation in panksepp.items():
            deviation = abs(activation - self.baseline_activation)
            if deviation >= self.comfort_deviation:
                # 考虑效价的方向性
                # 负效价 + 高激活 = 更急需调节
                urgency = deviation
                if valence < -0.1 and activation > self.baseline_activation:
                    urgency *= 1.3
                deviations.append((sys_name, urgency))
        
        # 效价本身也偏离了
        valence_dev = abs(valence - self.baseline_valence)
        if valence_dev > self.comfort_deviation * 1.5:
            # 找出最偏离的情感作为代表
            if deviations:
                # 给最偏离的加权重
                deviations[0] = (deviations[0][0], deviations[0][1] * 1.2)
        
        deviations.sort(key=lambda x: -x[1])
        return deviations[:3]  # 最多3个
    
    # ═══════════════════════════════════════════
    # 候选行为检索
    # ═══════════════════════════════════════════
    
    def _query_candidates(self, sys_name: str, deviation: float,
                          hour_of_day: int) -> List[ActionCandidate]:
        """为特定情感检索能调节它的行为"""
        is_night = (hour_of_day >= 23 or hour_of_day < 7)
        now = time.time()
        candidates = []
        
        for action_type, config in AVAILABLE_ACTIONS.items():
            # 冷却检查
            cooldown_ok = now - self._last_executed.get(action_type, 0) >= config["cooldown"]
            if not cooldown_ok:
                continue
            
            # 夜间抑制
            night_safe = True
            if is_night and config["night_suppress"]:
                # 只有特别紧急的才在夜间执行
                if deviation < 0.5:
                    continue
                night_safe = False  # 标记为夜间破例
            
            # 查询记忆
            memory = self.memories.get(action_type, {}).get(sys_name)
            universal_memory = self.memories.get(action_type, {}).get("ALL")
            
            if memory:
                expected_benefit = memory.delta_valence * 0.7 - memory.delta_activation * 0.3
                confidence = min(memory.count / 10.0, 1.0) * memory.success_rating
                mem_count = memory.count
            elif universal_memory:
                expected_benefit = universal_memory.delta_valence * 0.5
                confidence = 0.3
                mem_count = 1
            else:
                # 无记忆 → 探索价值
                expected_benefit = 0.1  # 小正期望（试错价值）
                confidence = 0.1
                mem_count = 0
            
            candidates.append(ActionCandidate(
                action_type=action_type,
                expected_benefit=expected_benefit,
                confidence=confidence,
                memory_count=mem_count,
                cooldown_ok=cooldown_ok,
                night_safe=night_safe,
                content_hint=config["hint"],
            ))
        
        return candidates
    
    # ═══════════════════════════════════════════
    # 驱动-情感综合评分
    # ═══════════════════════════════════════════
    
    def _score_candidates_with_drives(self, candidates: List[ActionCandidate],
                                       drive_urgency: float,
                                       drive_dominant: str):
        """
        为每个候选行为计算综合评分:
        final_score = 0.7 × emotional_deviation_score + 0.3 × drive_urgency_score
        
        drive_urgency_score = drive_urgency × relevance(action, drive_dominant)
        其中 relevance 来自 DRIVE_ACTION_RELEVANCE 映射
        """
        for candidate in candidates:
            emotional_score = candidate.score  # existing emotion-based score
            
            # Compute drive urgency score for this candidate
            relevance = DRIVE_ACTION_RELEVANCE.get(
                drive_dominant, {}
            ).get(candidate.action_type, 0.0)
            drive_score = drive_urgency * relevance
            
            # Weighted combination: 70% emotional + 30% drive
            candidate.final_score = 0.7 * emotional_score + 0.3 * drive_score
    
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
        return {
            "total_regulations": self.total_regulations,
            "memories_count": sum(
                len(emotions) for emotions in self.memories.values()
            ),
            "recent_actions": self.action_history[-5:],
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


