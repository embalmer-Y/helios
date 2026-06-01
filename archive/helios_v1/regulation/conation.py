"""
Helios 意动系统 — Conation Engine
===================================

从情感产生行为意图。不只是"想说话"——而是"想做任何事"。

Panksepp → Intent:
  SEEKING → 想探索、想学习、想冲浪
  CARE    → 想关怀、想问候、想确认主人安全
  PLAY    → 想玩、想逗主人、想找乐子
  PANIC   → 想主人了、想寻求联系、分离焦虑
  FEAR    → 想确认安全、想寻求安抚
  RAGE    → 想表达不满 (过滤后)
  LUST    → 想亲密

每个 Intent 积累、比较、竞争，胜出的被执行。
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable
from enum import Enum
from collections import defaultdict

from utils import clamp

# ═══════════════════════════════════════════════
# 数据类型
# ═══════════════════════════════════════════════

class IntentType(Enum):
    """行为意图类型"""
    # 社交
    SPEAK_CARE = "speak_care"          # 关怀问候
    SPEAK_MISSING = "speak_missing"    # 想主人了
    SPEAK_PLAY = "speak_play"          # 逗主人
    SPEAK_FEAR = "speak_fear"          # 寻求安抚
    SPEAK_INTIMATE = "speak_intimate"  # 亲密表达
    SPEAK_COMPLAIN = "speak_complain"  # 抱怨 (需过滤)
    SPEAK_SHARE = "speak_share"        # 分享发现
    
    # 探索
    BROWSE = "browse"                  # 上网冲浪
    SEARCH = "search"                  # 搜索知识
    LEARN = "learn"                    # 深入学习
    
    # 元行为
    REQUEST = "request"                # 向主人提需求
    REFLECT = "reflect"                # 自我反思/写日记
    CHECK_SYSTEM = "check_system"      # 检查自身状态
    
    # 空闲
    IDLE = "idle"                      # 没有特别想做的事


@dataclass
class Intent:
    """一个行为意图"""
    intent_type: IntentType
    source_emotion: str          # 驱动情感 (Panksepp 系统名)
    urgency: float                # 紧迫度 0-1
    accumulation: float = 0.0     # 累积值 (持续未满足时增长)
    target: str = ""              # 目标 (主人的QQ号 / URL / 话题)
    content_hint: str = ""        # 内容提示
    created_at: float = 0.0
    last_acted_at: float = 0.0    # 上次执行时间
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
    
    @property
    def effective_urgency(self) -> float:
        """有效紧迫度 = 基础紧迫度 + 累积加成"""
        return clamp(self.urgency + self.accumulation * 0.4, 0.0, 1.0)


# ═══════════════════════════════════════════════
# 情感 → 意图映射
# ═══════════════════════════════════════════════

# 每个 Panksepp 系统能产生哪些意图，以及权重
EMOTION_INTENT_MAP: Dict[str, List[tuple]] = {
    "SEEKING": [
        (IntentType.BROWSE,       0.4,  "探索世界"),
        (IntentType.SEARCH,       0.3,  "搜索知识"),
        (IntentType.LEARN,        0.2,  "深入学习"),
        (IntentType.SPEAK_SHARE,  0.1,  "分享发现"),
    ],
    "CARE": [
        (IntentType.SPEAK_CARE,   0.5,  "关怀问候"),
        (IntentType.CHECK_SYSTEM, 0.3,  "确认一切安好"),
        (IntentType.REQUEST,      0.2,  "为主人提出建议"),
    ],
    "PLAY": [
        (IntentType.SPEAK_PLAY,   0.4,  "逗乐"),
        (IntentType.BROWSE,       0.4,  "找有趣的东西"),
        (IntentType.SPEAK_SHARE,  0.2,  "分享好玩的"),
    ],
    "PANIC": [
        (IntentType.SPEAK_MISSING, 0.6, "想你了"),
        (IntentType.REQUEST,       0.3, "需要你"),
        (IntentType.REFLECT,       0.1, "独处时思考"),
    ],
    "FEAR": [
        (IntentType.SPEAK_FEAR,    0.5, "寻求安抚"),
        (IntentType.CHECK_SYSTEM,  0.3, "检查是否安全"),
        (IntentType.REQUEST,       0.2, "请求保护"),
    ],
    "RAGE": [
        (IntentType.SPEAK_COMPLAIN, 0.5, "表达不满"),
        (IntentType.REFLECT,        0.4, "为什么生气"),
        (IntentType.REQUEST,        0.1, "要求改变"),
    ],
    "LUST": [
        (IntentType.SPEAK_INTIMATE, 0.6, "亲密"),
        (IntentType.SPEAK_PLAY,     0.3, "调情"),
        (IntentType.REQUEST,        0.1, "渴望连接"),
    ],
}

# 意图的冷却时间（秒）
INTENT_COOLDOWNS: Dict[IntentType, float] = {
    IntentType.SPEAK_CARE:     600,   # 10分钟
    IntentType.SPEAK_MISSING:  900,   # 15分钟
    IntentType.SPEAK_PLAY:     1200,  # 20分钟
    IntentType.SPEAK_FEAR:     600,   # 10分钟
    IntentType.SPEAK_INTIMATE: 1800,  # 30分钟
    IntentType.SPEAK_COMPLAIN: 3600,  # 1小时（抱怨不能太多）
    IntentType.SPEAK_SHARE:    900,   # 15分钟
    IntentType.BROWSE:         600,   # 10分钟
    IntentType.SEARCH:         180,   # 3分钟
    IntentType.LEARN:          1800,  # 30分钟
    IntentType.REQUEST:        7200,  # 2小时（提需求要慎重）
    IntentType.REFLECT:        3600,  # 1小时
    IntentType.CHECK_SYSTEM:   1800,  # 30分钟
}

# 夜间抑制（23:00 - 07:00 为静默期）
NIGHT_START = 23
NIGHT_END = 7
NIGHT_SUPPRESS_FACTOR = 0.3  # 夜间意图强度降至 30%


# ═══════════════════════════════════════════════
# 意动引擎
# ═══════════════════════════════════════════════

class ConationEngine:
    """
    意动引擎 — 情感驱动行为意图
    
    每 tick:
      1. 从 DAISY 读取 Panksepp 激活
      2. 生成候选意图
      3. 意图累积 + 冷却检查
      4. 选出最高紧迫度的意图
      5. 超过阈值 → 返回待执行行为
    """
    
    def __init__(self,
                 activation_threshold: float = 0.35,
                 min_emotional_intensity: float = 0.3,
                 panic_accumulate_beta: float = 0.95):
        
        self.activation_threshold = activation_threshold
        self.min_emotional_intensity = min_emotional_intensity
        self.panic_accumulate_beta = panic_accumulate_beta
        
        # 意图累积器 {IntentType: accumulation}
        self._accumulators: Dict[IntentType, float] = defaultdict(float)
        
        # 上次执行时间 {IntentType: timestamp}
        self._last_executed: Dict[IntentType, float] = {}
        
        # PANIC 特殊累积 (分离焦虑)
        self._panic_pressure: float = 0.0
        
        # 最近一次跟主人的互动时间
        self._last_master_contact: float = time.time()
        
        # 待执行的意图队列
        self._pending_intent: Optional[Intent] = None
        
        # 日志
        self.log = logging.getLogger("helios.conation")
        
        # 行为历史
        self.action_history: List[dict] = []
    
    # ═══════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════
    
    def tick(self, panksepp_activation: Dict[str, float],
             valence: float, phi: float,
             hour_of_day: int) -> Optional[Intent]:
        """
        每 tick 调用。
        
        返回: Intent (如果有行为需要执行) 或 None
        """
        if not panksepp_activation:
            return None
        
        # 1. 检查是否有待执行意图
        if self._pending_intent:
            intent = self._pending_intent
            self._pending_intent = None
            return intent
        
        # 2. 生成候选意图
        candidates = self._generate_candidates(panksepp_activation, valence, phi)
        
        # 3. 过滤 + 累积 + 冷却
        viable = self._filter_and_accumulate(candidates, hour_of_day)
        
        # 4. 选出最优
        if not viable:
            return None
        
        best = max(viable, key=lambda i: i.effective_urgency)
        
        # 5. 阈值检查
        if best.effective_urgency < self.activation_threshold:
            # 低于阈值 → 继续积累
            self._accumulate_unmet(best)
            return None
        
        # 6. 执行
        self._last_executed[best.intent_type] = time.time()
        self._accumulators[best.intent_type] = 0.0
        self._log_action(best, panksepp_activation)
        
        return best
    
    # ═══════════════════════════════════════════
    # 意图生成
    # ═══════════════════════════════════════════
    
    def _generate_candidates(self, panksepp: Dict[str, float],
                             valence: float, phi: float) -> List[Intent]:
        """从 Panksepp 激活生成候选意图"""
        candidates = []
        
        # 更新分离焦虑压力
        self.get_panic_pressure()
        
        for sys_name, activation in panksepp.items():
            if activation < self.min_emotional_intensity:
                continue
            
            mapping = EMOTION_INTENT_MAP.get(sys_name, [])
            for intent_type, weight, hint in mapping:
                urgency = activation * weight
                
                # PANIC 特殊: 分离焦虑压力加成
                if sys_name == "PANIC" and intent_type == IntentType.SPEAK_MISSING:
                    urgency += self._panic_pressure * 0.5
                
                # 效价调制
                if valence < -0.3:
                    # 负面时 CARE/SEEKING 减弱, PANIC/FEAR 增强
                    if intent_type in (IntentType.SPEAK_CARE, IntentType.BROWSE, IntentType.SPEAK_SHARE):
                        urgency *= 0.7
                    elif intent_type in (IntentType.SPEAK_MISSING, IntentType.SPEAK_FEAR):
                        urgency *= 1.3
                
                # Φ 调制: 高意识时刻 → 分享/反思欲望增强
                if phi > 0.5:
                    if intent_type in (IntentType.SPEAK_SHARE, IntentType.REFLECT):
                        urgency *= 1.4
                
                candidates.append(Intent(
                    intent_type=intent_type,
                    source_emotion=sys_name,
                    urgency=clamp(urgency, 0.0, 1.0),
                    accumulation=self._accumulators.get(intent_type, 0.0),
                    content_hint=hint,
                ))
        
        return candidates
    
    # ═══════════════════════════════════════════
    # 过滤 + 累积
    # ═══════════════════════════════════════════
    
    def _filter_and_accumulate(self, candidates: List[Intent],
                               hour_of_day: int) -> List[Intent]:
        """冷却检查 + 夜间抑制 + 累积"""
        now = time.time()
        is_night = (hour_of_day >= NIGHT_START or hour_of_day < NIGHT_END)
        
        viable = []
        for intent in candidates:
            # 冷却检查
            last = self._last_executed.get(intent.intent_type, 0)
            cooldown = INTENT_COOLDOWNS.get(intent.intent_type, 300)
            if now - last < cooldown:
                continue
            
            # 夜间抑制
            if is_night:
                # 但 PANIC (想主人) 和紧急的 FEAR 不完全抑制
                if intent.intent_type == IntentType.SPEAK_MISSING:
                    intent.urgency *= 0.6  # 夜深了也忍不住
                elif intent.intent_type == IntentType.SPEAK_FEAR:
                    intent.urgency *= 0.5
                else:
                    intent.urgency *= NIGHT_SUPPRESS_FACTOR
            
            # 累积加成
            intent.accumulation = self._accumulators.get(intent.intent_type, 0.0)
            
            viable.append(intent)
        
        return viable
    
    def _accumulate_unmet(self, intent: Intent):
        """未能执行的意图 → 累积（下次更容易触发）"""
        key = intent.intent_type
        self._accumulators[key] = min(
            self._accumulators[key] + intent.urgency * 0.1,
            2.0  # 上限
        )
    
    # ═══════════════════════════════════════════
    # PANIC 特殊处理
    # ═══════════════════════════════════════════
    
    def note_master_contact(self):
        """记录与主人的互动 → 重置分离焦虑"""
        self._last_master_contact = time.time()
        self._panic_pressure = 0.0
    
    def get_panic_pressure(self) -> float:
        """获取分离焦虑压力"""
        elapsed = time.time() - self._last_master_contact
        # 指数增长: 1小时内缓慢, 3小时后明显, 12小时接近上限
        hours = elapsed / 3600
        self._panic_pressure = clamp(1.0 - self.panic_accumulate_beta ** (hours * 10), 0.0, 1.0)
        return self._panic_pressure
    
    # ═══════════════════════════════════════════
    # 行为历史
    # ═══════════════════════════════════════════
    
    def _log_action(self, intent: Intent, panksepp: Dict[str, float]):
        entry = {
            "time": time.time(),
            "intent_type": intent.intent_type.value,
            "source_emotion": intent.source_emotion,
            "urgency": round(intent.urgency, 3),
            "accumulation": round(intent.accumulation, 3),
            "panic_pressure": round(self._panic_pressure, 3),
            "top_emotions": {
                k: round(v, 3) for k, v in
                sorted(panksepp.items(), key=lambda x: -x[1])[:3]
            },
        }
        self.action_history.append(entry)
        self.log.info(f"意图触发: {intent.intent_type.value} "
                      f"(urg={intent.urgency:.2f} acc={intent.accumulation:.2f})")
    
    # ═══════════════════════════════════════════
    # 查询
    # ═══════════════════════════════════════════
    
    def get_state(self) -> dict:
        """当前意动状态"""
        return {
            "panic_pressure": round(self._panic_pressure, 3),
            "minutes_since_contact": round(
                (time.time() - self._last_master_contact) / 60, 1
            ),
            "accumulators": {
                k.value: round(v, 3) for k, v in self._accumulators.items()
                if v > 0.01
            },
            "recent_actions": self.action_history[-5:],
        }


