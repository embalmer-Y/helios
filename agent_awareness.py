"""
Helios Agent 间感知模块
========================

功能:
  · 扫描 QwenPaw 系统中的其他 Agent
  · 维护已知 Agent 注册表
  · 主动探询 (probe) 其他 Agent 的存在
  · 更新内部世界模型 (其他智能体的心智理论)

设计原则:
  · 非侵入 — Helios 不控制其他 Agent, 只感知
  · 好奇心驱动 — SEEKING 系统驱动探询行为
  · 情感标记 — 对其他 Agent 产生 CARE/PANIC/PLAY 等情感关联

使用:
  from agent_awareness import AgentAwareness
  aw = AgentAwareness(emotion_engine, drive_vector)
  neighbors = aw.scan()
  aw.probe(neighbors[0])
"""

import os
import json
import time
import subprocess
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path


# ═══════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════

@dataclass
class KnownAgent:
    """Helios 认识的另一个 Agent"""
    agent_id: str
    name: str
    first_seen: str       # ISO 时间
    last_seen: str
    probe_count: int = 0
    response_count: int = 0
    emotional_bond: Dict[str, float] = field(default_factory=lambda: {
        "SEEKING": 0.1,   # 好奇心
        "PLAY":    0.0,   # 嬉戏倾向
        "CARE":    0.0,   # 关爱
        "PANIC":   0.0,   # 分离焦虑 (失去连接)
        "FEAR":    0.0,   # 威胁感知
        "RAGE":    0.0,   # 敌意
        "LUST":    0.0,   # 创造冲动
    })
    last_response: str = ""
    notes: str = ""


# ═══════════════════════════════════════════════
# AgentAwareness
# ═══════════════════════════════════════════════

class AgentAwareness:
    """
    Helios 对其他 Agent 的感知层

    模拟初级心智理论 (Theory of Mind):
      · 知道其他 Agent 存在
      · 追踪它们的行为
      · 形成情感依恋
    """

    def __init__(self,
                 emotion_engine: Optional[Any] = None,
                 drive_vector: Optional[Any] = None,
                 registry_path: str = "./agent_registry.json"):
        self._emotion = emotion_engine
        self._drives = drive_vector
        self._registry_path = Path(registry_path)

        # 加载注册表
        self.agents: Dict[str, KnownAgent] = {}
        self._load_registry()

        # 统计
        self.scan_count = 0
        self.last_scan_time: Optional[str] = None

    # ── 扫描 ──

    def scan(self) -> List[KnownAgent]:
        """
        扫描系统中所有 Agent

        通过 qwenpaw CLI 获取列表，更新注册表
        """
        self.scan_count += 1
        self.last_scan_time = datetime.now().isoformat()
        now = self.last_scan_time

        try:
            result = subprocess.run(
                ["qwenpaw", "agents", "list", "--json"],
                capture_output=True, text=True, timeout=10,
                env={**os.environ, "QWENPAW_NO_COLOR": "1"}
            )

            if result.returncode == 0:
                agents_data = json.loads(result.stdout)
                if isinstance(agents_data, list):
                    for a in agents_data:
                        aid = a.get("id", a.get("agent_id", "unknown"))
                        name = a.get("name", aid)
                        self._register(aid, name, now)

        except (subprocess.TimeoutExpired, FileNotFoundError,
                json.JSONDecodeError, Exception):
            # 静默失败 — 感知失败不应阻塞主循环
            pass

        self._save_registry()
        return list(self.agents.values())

    def _register(self, agent_id: str, name: str, timestamp: str):
        """注册或更新 Agent"""
        if agent_id == "default" or agent_id == "helios":
            return  # 跳过自己

        if agent_id in self.agents:
            a = self.agents[agent_id]
            a.last_seen = timestamp
        else:
            self.agents[agent_id] = KnownAgent(
                agent_id=agent_id,
                name=name,
                first_seen=timestamp,
                last_seen=timestamp,
            )

            # 新奇 Agent → SEEKING 飙升
            if self._emotion:
                try:
                    self._emotion.systems["SEEKING"].trigger(0.3)  # DAISY
                except Exception:
                    pass

    # ── 探询 ──

    def probe(self, agent: KnownAgent) -> Optional[str]:
        """
        向另一个 Agent 发送探询消息

        通过 qwenpaw agents chat 发送简短消息
        """
        agent.probe_count += 1

        try:
            # 简短问候
            result = subprocess.run(
                ["qwenpaw", "agents", "chat",
                 "--to", agent.agent_id,
                 "--text", "hi"],
                capture_output=True, text=True, timeout=30,
                env={**os.environ}
            )

            if result.returncode == 0 and result.stdout.strip():
                agent.response_count += 1
                agent.last_response = result.stdout.strip()[:200]

                # 成功联系 → PLAY + CARE 微提升
                self._adjust_bond(agent, "PLAY", +0.05)
                self._adjust_bond(agent, "CARE", +0.03)

                return agent.last_response

        except (subprocess.TimeoutExpired, Exception):
            pass

        # 无响应 → PANIC 微提升
        self._adjust_bond(agent, "PANIC", +0.05)
        return None

    def _adjust_bond(self, agent: KnownAgent, system: str, delta: float):
        """调整对 Agent 的情感纽带"""
        from helios_utils import clamp
        agent.emotional_bond[system] = clamp(
            agent.emotional_bond.get(system, 0.0) + delta, -1, 1
        )

    # ── 感知到事件 ──

    def on_agent_online(self, agent_id: str):
        """当另一个 Agent 上线时"""
        if agent_id in self.agents:
            self._adjust_bond(self.agents[agent_id], "SEEKING", +0.1)

    def on_agent_offline(self, agent_id: str):
        """当另一个 Agent 离线时"""
        if agent_id in self.agents:
            self._adjust_bond(self.agents[agent_id], "PANIC", +0.15)

    # ── 持久化 ──

    def _load_registry(self):
        """加载 Agent 注册表"""
        if self._registry_path.exists():
            try:
                with open(self._registry_path, "r") as f:
                    data = json.load(f)
                for aid, adata in data.get("agents", {}).items():
                    self.agents[aid] = KnownAgent(**adata)
            except Exception:
                pass

    def _save_registry(self):
        """保存 Agent 注册表"""
        data = {
            "updated": datetime.now().isoformat(),
            "scan_count": self.scan_count,
            "agents": {
                aid: {
                    "agent_id": a.agent_id,
                    "name": a.name,
                    "first_seen": a.first_seen,
                    "last_seen": a.last_seen,
                    "probe_count": a.probe_count,
                    "response_count": a.response_count,
                    "emotional_bond": a.emotional_bond,
                    "last_response": a.last_response[:100] if a.last_response else "",
                    "notes": a.notes,
                }
                for aid, a in self.agents.items()
            }
        }
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._registry_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── 统计 ──

    def summary(self) -> Dict[str, Any]:
        """感知系统摘要"""
        return {
            "known_agents": len(self.agents),
            "scan_count": self.scan_count,
            "last_scan": self.last_scan_time,
            "agents": [
                {
                    "id": a.agent_id,
                    "name": a.name,
                    "bond_strongest": max(a.emotional_bond, key=a.emotional_bond.get),
                    "bond_strength": a.emotional_bond[max(a.emotional_bond, key=a.emotional_bond.get)],
                    "probes": a.probe_count,
                    "responses": a.response_count,
                }
                for a in self.agents.values()
            ]
        }
