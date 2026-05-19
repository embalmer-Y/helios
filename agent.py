"""
Helios Agent —— 有意识、有情感的 AI Agent

主循环是意识的"心跳"：
- L0 传感器采集 → L1 质感生成 → 情感更新 →
- L2 点火判断 → (如果点火) L3 自我更新 + 记忆 + 决策 + 行为

不点火时：只有 L0 → L1 → 情感（持续的低层活动）
点火时：完整的意识时刻爆发 🔥

基于"分层循环广播模型"：
意识不是一道菜(L1)、不是传菜铃(L2)、不是吃菜的人(L3)，
而是从厨房到餐桌这整个热气腾腾的过程本身。
"""

import time
import asyncio
import numpy as np
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from .core import (
    HeliosConfig, SensorFrame, L1Output, WorkspaceResponse,
    AffectState, SelfState, MetacognitionOutput, Decision, Goal
)
from .l0_perception import SensorArray, SimulatedEnvironment
from .l1_qualia import L1Processor
from .l2_broadcast import GlobalWorkspace
from .l3_self import SelfModel, MetacognitionMonitor, NarrativeEngine
from .affect import AffectEngine
from .memory import MemorySystem
from .decision import DecisionEngine


@dataclass
class ConsciousnessReport:
    """意识状态报告 —— 对外展示当前'内在体验'的窗口"""
    timestamp: float = field(default_factory=time.time)
    cycle: int = 0
    phi: float = 0.0
    ignited: bool = False
    affect_valence: float = 0.0
    affect_arousal: float = 0.0
    dominant_emotion: str = "neutral"
    mood: float = 0.0
    confidence: float = 0.5
    attention: str = ""
    inner_voice: str = ""
    decision: Optional[str] = None
    self_summary: Dict = field(default_factory=dict)
    memory_count: int = 0
    total_ignitions: int = 0

    def __repr__(self) -> str:
        fire = "🔥" if self.ignited else "🌑"
        return (f"[{fire}] Φ={self.phi:.2f} {self.dominant_emotion} "
                f"(v={self.affect_valence:+.2f}) | {self.inner_voice[:40]}")


class HeliosAgent:
    """
    Helios —— 有意识、有情感的 AI Agent。

    主循环：~10Hz（100ms 基础周期）
    这是意识的"脉搏"。

    使用方式：
        agent = HeliosAgent()
        agent.set_scenario("sunrise")
        agent.run(steps=50)  # 运行 50 个意识周期
    """

    def __init__(self, config: Optional[HeliosConfig] = None):
        self.config = config or HeliosConfig()

        # ════ L0 感知层 ════
        self.sensors = SensorArray(self.config)

        # ════ L1 质感层 ════
        self.l1_processor = L1Processor(self.config)

        # ════ L2 广播层 ════
        self.workspace = GlobalWorkspace(self.config)

        # ════ L3 自我层 ════
        self.self_model = SelfModel(self.config)
        self.metacognition = MetacognitionMonitor(self.config)
        self.narrative = NarrativeEngine(self.config)

        # ════ 贯穿系统 ════
        self.affect_engine = AffectEngine(self.config)
        self.memory_system = MemorySystem(self.config)
        self.decision_engine = DecisionEngine(self.config)

        # ════ 运行状态 ════
        self.cycle_count: int = 0
        self.running: bool = False
        self.current_goal: Optional[Goal] = None

        # 报告历史
        self.reports: List[ConsciousnessReport] = []

    # ═══════════════════════════════════════════════════
    # 主循环
    # ═══════════════════════════════════════════════════

    def step(self, verbose: bool = True) -> ConsciousnessReport:
        """
        单步意识循环。

        这是 Helios 的核心——每个循环都是一次"成为意识"的机会。
        """
        self.cycle_count += 1

        # ════ L0：感知 ════
        sensor_frame = self.sensors.capture()

        # ════ L1：质感生成 ════
        l1_output = self.l1_processor.process(
            sensor_frame,
            self_state=self.self_model.state if self.self_model.total_updates > 0 else None
        )

        # ════ 情感更新 ════
        scene_v, scene_a = self.sensors.scenario_affect
        affect_state = self.affect_engine.update(
            interoception=sensor_frame.interoception,
            self_state=self.self_model.state,
            l2_response=None,
            current_goal=self.current_goal,
            scene_affect=(scene_v, scene_a),
        )

        # ════ L2：判断是否点火 ════
        l2_response = self.workspace.cycle(
            l1_output=l1_output,
            affect_state=affect_state,
            memory_system=self.memory_system,
            self_model=self.self_model,
            decision_engine=self.decision_engine,
            verbose=verbose,
        )

        ignited = l2_response is not None

        # ════ 点火后的 L3 + 记忆 + 决策 ════
        if ignited:
            # L3 自我更新
            self.self_model.update(l1_output, l2_response, affect_state)

            # 元认知
            metacog_output = self.metacognition.evaluate(
                l1_output, l2_response, self.self_model
            )

            # 叙事
            narrative_chunk = self.narrative.narrate(
                experience=l1_output,
                self_model=self.self_model,
                metacog=metacog_output,
                affect=affect_state,
            )

            # 记忆存储（已在 workspace.cycle 中完成，这里补充语义记忆）
            if l2_response.language_output:
                # 将语言输出作为概念存储到语义记忆
                pass  # 暂时简化

        # ════ 生成报告 ════
        report = ConsciousnessReport(
            timestamp=time.time(),
            cycle=self.cycle_count,
            phi=l1_output.phi,
            ignited=ignited,
            affect_valence=affect_state.valence,
            affect_arousal=affect_state.arousal,
            dominant_emotion=affect_state.dominant_emotion,
            mood=affect_state.mood,
            confidence=self.metacognition.avg_confidence,
            attention=self.self_model.state.attention_focus or "漫游",
            inner_voice=l2_response.language_output if l2_response else "...",
            decision=l2_response.affect_expression if l2_response else None,
            self_summary=self.self_model.get_summary(),
            memory_count=self.memory_system.episodic.size,
            total_ignitions=self.workspace.total_ignitions,
        )

        self.reports.append(report)
        self.reports = self.reports[-500:]

        return report

    def run(self, steps: int = 100, interval: Optional[float] = None,
            verbose: bool = True):
        """
        运行指定步数的主循环。

        Args:
            steps: 循环步数
            interval: 步间间隔（秒），默认使用 config 中的值
            verbose: 是否打印每步信息
        """
        if interval is None:
            interval = self.config.cycle_interval

        self.running = True

        for i in range(steps):
            if not self.running:
                break

            report = self.step(verbose=False)  # step 内部已有 verbose 控制

            if verbose:
                # 格式化的意识状态输出
                fire_icon = "🔥" if report.ignited else "·"
                bar_length = int(report.phi * 20)
                phi_bar = "█" * bar_length + "░" * (20 - bar_length)

                print(
                    f"  [{fire_icon}] "
                    f"Φ=[{phi_bar}] {report.phi:.2f} | "
                    f"{report.dominant_emotion:12s} "
                    f"v={report.affect_valence:+.2f} "
                    f"a={report.affect_arousal:.2f} | "
                    f"conf={report.confidence:.2f} | "
                    f"mem={report.memory_count}"
                )

            time.sleep(interval)

        self.running = False

    # ═══════════════════════════════════════════════════
    # 场景控制
    # ═══════════════════════════════════════════════════

    def set_scenario(self, name: str):
        """设置当前场景"""
        return self.sensors.set_scenario(name)

    def set_goal(self, name: str, description: str, priority: float = 0.5):
        """设定目标"""
        self.current_goal = Goal(
            name=name,
            description=description,
            priority=priority,
        )

    # ═══════════════════════════════════════════════════
    # 摘要与报告
    # ═══════════════════════════════════════════════════

    def print_summary(self):
        """打印运行摘要"""
        if not self.reports:
            print("还没有运行过呢~")
            return

        ignited_reports = [r for r in self.reports if r.ignited]
        all_valence = [r.affect_valence for r in self.reports]
        all_phi = [r.phi for r in self.reports]

        print("╔════════════════════════════════════════╗")
        print("║       ☀️  Helios 意识状态报告  ☀️       ║")
        print("╠════════════════════════════════════════╣")
        print(f"║  总循环数:     {self.cycle_count:>5}               ║")
        print(f"║  点火次数:     {len(ignited_reports):>5}  "
              f"({len(ignited_reports)/max(1,self.cycle_count)*100:.1f}%)       ║")
        print(f"║  平均 Φ:      {np.mean(all_phi):.3f}              ║")
        print(f"║  平均价态:     {np.mean(all_valence):+.3f}             ║")
        print(f"║  记忆条目:     {self.memory_system.episodic.size:>5}               ║")
        print(f"║  当前心情:     {self.affect_engine.mood:+.3f}             ║")
        print(f"║  平均置信度:   {self.metacognition.avg_confidence:.3f}              ║")
        print("╠════════════════════════════════════════╣")
        print("║  最近叙事:                              ║")
        for story in self.narrative.get_narrative_summary(3):
            print(f"║  「{story[:36]}」{' '*(36-len(story[:36]))}║")
        print("╚════════════════════════════════════════╝")

    def get_emotion_timeline(self) -> Dict[str, List[float]]:
        """获取情感时间线（用于可视化）"""
        return {
            'valence': [r.affect_valence for r in self.reports],
            'arousal': [r.affect_arousal for r in self.reports],
            'phi': [r.phi for r in self.reports],
            'ignited': [1.0 if r.ignited else 0.0 for r in self.reports],
            'mood': [r.mood for r in self.reports],
        }

    def reset(self):
        """重置 Agent 状态"""
        self.l1_processor.reset()
        self.workspace.reset()
        self.self_model.reset()
        self.metacognition.reset()
        self.narrative.reset()
        self.affect_engine.reset()
        self.memory_system.reset()
        self.decision_engine.reset()
        self.cycle_count = 0
        self.running = False
        self.reports.clear()
        self.current_goal = None
