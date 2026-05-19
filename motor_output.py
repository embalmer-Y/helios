"""
Helios 运动输出层 —— 从"只能感受"到"可以行动"

三条通路，对应神经科学的三个运动系统：

通路 1：反射弧 (ReflexiveMotorController)
  L0 → 威胁检测 → 直接输出，不经 L1/L2/L3
  延迟: < 150ms（人类对应：脊髓→上丘，背侧通路）
  例子：手碰火缩手、车冲来闪避

通路 2：意识决策 (DeliberateMotorController)
  L0 → L1 → L2 → L3 → Decision → 输出
  延迟: 300ms+（人类对应：运动皮层→基底节，腹侧通路）
  例子："我想拿杯子"、"这很危险我要后退"

通路 3：自主神经 (AutonomicController)
  独立于意识的永续回路
  心跳、呼吸、体温调节
  仅在异常时通过 interoception 上报 L0

理论依据：
  - GNW 双流假说 (Dehaene 2014): 背侧(快速无意识) vs 腹侧(意识通道)
  - RPT 前馈扫视 (Lamme 2003): feedforward sweep 100ms 内完成
  - 预测加工 (Friston): 多层预测驱动动作
"""

import time
import math
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


# ═══════════════════════════════════════════════════
# 基础数据结构
# ═══════════════════════════════════════════════════

class MotorPathway(Enum):
    """运动通路类型"""
    REFLEXIVE = "reflexive"     # 反射弧（<150ms）
    DELIBERATE = "deliberate"  # 意识决策（300ms+）
    AUTONOMIC = "autonomic"    # 自主神经（持续）


@dataclass
class MotorCommand:
    """运动指令"""
    pathway: MotorPathway
    timestamp: float = field(default_factory=time.time)

    # 目标执行器
    actuator_id: str = ""

    # 运动参数
    action_type: str = ""           # move/rotate/grip/release/stop/none
    target_position: Optional[List[float]] = None  # [x, y, z] 或 [angle]
    velocity: float = 0.0           # 速度 [0, 1]
    force: float = 0.0              # 力度 [0, 1]
    duration: float = 0.0           # 持续时间（秒），0=瞬时

    # 元数据
    urgency: float = 0.0            # 紧急度 [0, 1]
    source: str = ""                # 来源描述（哪个通路/场景触发）
    reason: str = ""                # 原因

    def __repr__(self):
        return (f"MotorCmd({self.pathway.value}→{self.actuator_id}: "
                f"{self.action_type} urgency={self.urgency:.2f})")


@dataclass
class ActuatorState:
    """执行器状态"""
    actuator_id: str
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    velocity: float = 0.0
    temperature: float = 25.0
    current: float = 0.0
    is_moving: bool = False
    last_command: Optional[MotorCommand] = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════
# Actuator 抽象基类
# ═══════════════════════════════════════════════════

class Actuator(ABC):
    """
    执行器抽象基类。

    每个具体实现对接一种物理设备：
    - 电机 (DCMotor)
    - 舵机/云台 (ServoActuator)
    - 机械臂 (RobotArm)
    - 扬声器 (SpeakerActuator)
    - 文本输出 (TextOutput)
    """

    def __init__(self, actuator_id: str, name: str = ""):
        self.actuator_id = actuator_id
        self.name = name or actuator_id
        self.state = ActuatorState(actuator_id=actuator_id)
        self._command_history: List[MotorCommand] = []

    @abstractmethod
    def execute(self, command: MotorCommand) -> ActuatorState:
        """执行运动指令，返回新状态"""
        ...

    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """返回执行器能力描述"""
        ...

    def emergency_stop(self):
        """紧急停止"""
        self.state.is_moving = False
        self.state.velocity = 0.0

    def get_state(self) -> ActuatorState:
        return self.state

    def _record(self, command: MotorCommand):
        self._command_history.append(command)
        self.state.last_command = command
        self.state.is_moving = command.action_type not in ('stop', 'none')


# ═══════════════════════════════════════════════════
# 具体执行器实现
# ═══════════════════════════════════════════════════

class SimMotorActuator(Actuator):
    """模拟电机执行器"""

    def __init__(self, actuator_id: str, max_speed: float = 100.0,
                 max_angle: float = 360.0, name: str = ""):
        super().__init__(actuator_id, name)
        self.max_speed = max_speed
        self.max_angle = max_angle

    def execute(self, command: MotorCommand) -> ActuatorState:
        self._record(command)

        if command.action_type == 'rotate':
            target = command.target_position[0] if command.target_position else 0.0
            self.state.position = [min(self.max_angle, max(0, target))]
            self.state.velocity = min(1.0, command.velocity) * self.max_speed
        elif command.action_type == 'move':
            self.state.velocity = min(1.0, command.velocity) * self.max_speed
            if command.target_position:
                self.state.position = command.target_position[:3]
        elif command.action_type in ('stop', 'none'):
            self.state.velocity = 0.0
            self.state.is_moving = False

        return self.state

    def capabilities(self) -> Dict[str, Any]:
        return {
            "type": "motor",
            "max_speed": self.max_speed,
            "max_angle": self.max_angle,
            "dof": 1,
        }


class SimServoActuator(Actuator):
    """模拟舵机/云台执行器"""

    def __init__(self, actuator_id: str, pan_range: float = 180.0,
                 tilt_range: float = 90.0, name: str = ""):
        super().__init__(actuator_id, name)
        self.pan_range = pan_range
        self.tilt_range = tilt_range

    def execute(self, command: MotorCommand) -> ActuatorState:
        self._record(command)

        if command.action_type == 'rotate':
            if command.target_position:
                self.state.position = [
                    np.clip(command.target_position[0], -self.pan_range, self.pan_range),
                    np.clip(command.target_position[1], -self.tilt_range, self.tilt_range)
                ] if len(command.target_position) >= 2 else self.state.position
            self.state.velocity = command.velocity * 60.0  # °/s
        elif command.action_type in ('stop', 'none'):
            self.state.velocity = 0.0
            self.state.is_moving = False

        return self.state

    def capabilities(self) -> Dict[str, Any]:
        return {
            "type": "servo",
            "pan_range": self.pan_range,
            "tilt_range": self.tilt_range,
            "dof": 2,
        }


class SimArmActuator(Actuator):
    """模拟机械臂执行器 (3-DOF)"""

    def __init__(self, actuator_id: str, name: str = ""):
        super().__init__(actuator_id, name)
        self.state.position = [0.0, 0.0, 0.0]  # shoulder, elbow, wrist

    def execute(self, command: MotorCommand) -> ActuatorState:
        self._record(command)

        if command.action_type == 'grip':
            self.state.velocity = command.velocity * 0.5
            if command.target_position:
                self.state.position = command.target_position[:3]
        elif command.action_type == 'release':
            self.state.velocity = 0.0
            self.state.position = [0.0, 0.0, 0.0]
        elif command.action_type == 'move':
            self.state.velocity = command.velocity
            if command.target_position:
                self.state.position = [
                    np.clip(command.target_position[0], -180, 180),
                    np.clip(command.target_position[1], -135, 135),
                    np.clip(command.target_position[2], -90, 90),
                ]
        elif command.action_type in ('stop', 'none'):
            self.state.velocity = 0.0
            self.state.is_moving = False

        return self.state

    def capabilities(self) -> Dict[str, Any]:
        return {"type": "arm", "dof": 3, "grip": True}


class SimSpeakerActuator(Actuator):
    """模拟扬声器执行器（语音/声音输出）"""

    def __init__(self, actuator_id: str, name: str = ""):
        super().__init__(actuator_id, name)
        self._last_text = ""

    def execute(self, command: MotorCommand) -> ActuatorState:
        self._record(command)

        if command.action_type == 'speak':
            # 文本即"运动"——语言是一种精细运动输出
            self._last_text = command.reason[:200] if command.reason else ""
            self.state.velocity = 0.5
        elif command.action_type in ('stop', 'none'):
            self.state.velocity = 0.0
            self.state.is_moving = False

        return self.state

    def capabilities(self) -> Dict[str, Any]:
        return {"type": "speaker", "language": True}

    @property
    def last_speech(self) -> str:
        return self._last_text


# ═══════════════════════════════════════════════════
# 通路 1：反射弧控制器
# ═══════════════════════════════════════════════════

class ReflexiveMotorController:
    """
    反射弧 —— 不加思考的动作。

    路径：L0 感知 → 威胁检测 → 直接输出
    不经 L1/L2/L3，延迟 <1 步（模拟 <150ms）

    触发条件：
    - 高惊奇度 (surprise > 0.6)
    - 高唤起 (arousal > 0.7)
    - 特定感官模式 (逼近物体、巨大声响)
    """

    # 反射规则表
    REFLEX_RULES = [
        # (条件, 动作, 执行器, 紧急度)
        ("approaching_object", "withdraw", "base_motor", 0.9),
        ("loud_sound", "startle", "neck_servo", 0.8),
        ("touch_hot", "retract", "arm", 1.0),
        ("bright_flash", "avert", "neck_servo", 0.7),
        ("collision_imminent", "evade", "base_motor", 1.0),
    ]

    def __init__(self, motor_router: 'MotorRouter'):
        self.router = motor_router
        self.total_reflexes = 0
        self.last_reflex: Optional[MotorCommand] = None

    def check_and_react(self, sensor_frame, affect_state=None) -> Optional[MotorCommand]:
        """
        检测威胁并执行反射动作。

        返回 MotorCommand 如果触发反射，否则 None。
        """
        if not hasattr(sensor_frame, 'vision'):
            return None

        arousal = getattr(affect_state, 'arousal', 0.0) if affect_state else 0.0
        valence = getattr(affect_state, 'valence', 0.0) if affect_state else 0.0

        # === 威胁评估 ===
        # 视觉：检查是否有剧烈变化（逼近物体）
        vision = getattr(sensor_frame, 'vision', None)
        audio = getattr(sensor_frame, 'audio', None)
        touch = getattr(sensor_frame, 'touch', None)

        threat_level = 0.0
        threat_type = ""

        if vision is not None and len(vision) > 0:
            # 视觉威胁：低均值 + 高方差 = 黑暗中有东西在动
            vision_mean = float(np.mean(vision))
            vision_std = float(np.std(vision))
            if vision_mean < 0.2 and vision_std > 0.35:
                threat_level = max(threat_level, min(1.0, vision_std * 2.5))
                threat_type = "approaching_object"

        if audio is not None and len(audio) > 0:
            audio_power = float(np.mean(np.abs(audio)))
            if audio_power > 0.30:
                threat_level = max(threat_level, min(1.0, audio_power * 2.5))
                if not threat_type:
                    threat_type = "loud_sound"

        if touch is not None and len(touch) > 0:
            touch_intensity = float(np.mean(np.abs(touch)))
            if touch_intensity > 0.40:
                threat_level = max(threat_level, min(1.0, touch_intensity * 2.0))
                if not threat_type:
                    threat_type = "touch_hot"

        # 高唤起 + 负价态 → 全局威胁感
        if arousal > 0.7 and valence < -0.5:
            threat_level = max(threat_level, 0.8)
            if threat_type == "approaching_object":
                threat_type = "collision_imminent"

        # === 触发反射 ===
        if threat_level > 0.6 and threat_type:
            # 查找匹配的反射规则
            for pattern, action, actuator, urgency in self.REFLEX_RULES:
                if pattern == threat_type or pattern == "collision_imminent":
                    cmd = MotorCommand(
                        pathway=MotorPathway.REFLEXIVE,
                        actuator_id=actuator,
                        action_type=action,
                        urgency=urgency * threat_level,
                        velocity=1.0,
                        source=f"reflex:{threat_type}",
                        reason=f"反射：检测到{threat_type}（威胁={threat_level:.2f}）",
                    )
                    self.total_reflexes += 1
                    self.last_reflex = cmd

                    # 路由到执行器
                    self.router.dispatch(cmd)
                    return cmd

        return None

    def get_stats(self) -> Dict:
        return {
            "total_reflexes": self.total_reflexes,
            "last_reflex": str(self.last_reflex) if self.last_reflex else "none",
        }


# ═══════════════════════════════════════════════════
# 通路 2：意识决策控制器
# ═══════════════════════════════════════════════════

class DeliberateMotorController:
    """
    意识决策后运动 —— 经过完整意识处理的动作。

    路径：L0 → L1 → L2 → L3 → Decision → 输出
    延迟：全链路延迟（模拟 >300ms）

    Decision.type 映射到具体运动：
    - approach  → 向目标移动
    - withdraw  → 远离/撤退
    - explore   → 扫描/搜索
    - express   → 说话/表达
    - observe   → 保持原位，微调朝向
    """

    # Decision → MotorCommand 映射表
    ACTION_MAP = {
        "approach": {
            "action": "move",
            "actuator": "base_motor",
            "velocity": 0.6,
            "description": "靠近目标",
        },
        "withdraw": {
            "action": "move",
            "actuator": "base_motor",
            "velocity": -0.8,  # 反向
            "description": "撤退回避",
        },
        "explore": {
            "action": "rotate",
            "actuator": "neck_servo",
            "velocity": 0.4,
            "description": "扫描环境",
        },
        "express": {
            "action": "speak",
            "actuator": "speaker",
            "velocity": 0.5,
            "description": "语言表达",
        },
        "observe": {
            "action": "stop",
            "actuator": "neck_servo",
            "velocity": 0.0,
            "description": "保持观察",
        },
    }

    def __init__(self, motor_router: 'MotorRouter'):
        self.router = motor_router
        self.total_actions = 0
        self.last_action: Optional[MotorCommand] = None

    def execute_decision(self, decision, affect_state=None,
                         llm_response=None) -> Optional[MotorCommand]:
        """
        将 L3 Decision 转换为具体运动指令。

        Args:
            decision: Decision 对象（来自 DecisionEngine）
            affect_state: 当前情感状态（调节动作参数）
            llm_response: LLM 响应（提供语言内容）

        Returns:
            MotorCommand 或 None
        """
        if decision is None:
            return None

        action_type = getattr(decision, 'action', None) or {}
        if isinstance(action_type, dict):
            dtype = action_type.get('type', 'observe')
            dreason = action_type.get('reason', '')
        else:
            dtype = str(action_type)
            dreason = getattr(decision, 'reason', '')

        mapping = self.ACTION_MAP.get(dtype)
        if mapping is None:
            return None

        # 计算速度（情感调节）
        velocity = mapping['velocity']
        if affect_state is not None:
            # 高唤起 → 动作更快
            arousal = getattr(affect_state, 'arousal', 0.5)
            velocity *= (0.5 + arousal * 1.0)  # 0.5x ~ 1.5x

        # 计算目标位置
        target = None
        if mapping['action'] == 'withdraw':
            # 撤退：向反方向移动
            target = [-0.5, 0.0, 0.0]  # 后退半米
        elif mapping['action'] == 'approach':
            target = [0.3, 0.0, 0.0]   # 前进 30cm
        elif mapping['action'] == 'explore':
            # 随机扫描方向
            target = [np.random.uniform(-90, 90), np.random.uniform(-30, 30)]
        elif mapping['action'] == 'speak':
            # 语言内容来自 LLM 响应
            speech_text = ""
            if llm_response and llm_response.language_output:
                speech_text = llm_response.language_output
            dreason = speech_text or dreason

        cmd = MotorCommand(
            pathway=MotorPathway.DELIBERATE,
            actuator_id=mapping['actuator'],
            action_type=mapping['action'],
            velocity=abs(velocity),
            target_position=target,
            urgency=abs(velocity) if dtype == 'withdraw' else 0.3,
            source=f"decision:{dtype}",
            reason=dreason[:200] if dreason else mapping['description'],
        )

        self.total_actions += 1
        self.last_action = cmd

        # 路由到执行器
        self.router.dispatch(cmd)
        return cmd

    def get_stats(self) -> Dict:
        return {
            "total_actions": self.total_actions,
            "last_action": str(self.last_action) if self.last_action else "none",
        }


# ═══════════════════════════════════════════════════
# 通路 3：自主神经控制器
# ═══════════════════════════════════════════════════

class AutonomicController:
    """
    自主神经系统 —— 永不停歇的生命维持回路。

    独立于意识，在自己的节律中运行：
    - 呼吸节律（模拟）
    - 心率模拟
    - 体温调节

    仅在异常时通过 interoception 上报 L0，
    可能触发 L2 点火（如：心率异常 → "我的心跳好快..."）。

    设计理念：
    - 这不是"下意识反应"（那是通路1）
    - 这是"永续生命回路"——和心跳呼吸一样本质
    """

    def __init__(self):
        # 生理参数
        self.heart_rate = 72.0          # bpm
        self.respiration_rate = 12.0    # breaths/min
        self.body_temperature = 36.8    # °C
        self.blood_pressure = 1.0       # 归一化 [0, 1]

        # 节律相位
        self._respiratory_phase = 0.0   # [0, 2π]
        self._cardiac_phase = 0.0       # [0, 2π]

        # 稳态目标
        self._target_hr = 72.0
        self._target_temp = 36.8

        # 统计
        self.total_cycles = 0
        self.abnormal_events = 0

    def cycle(self, dt: float, affect_state=None) -> Dict[str, float]:
        """
        一个自主神经周期。

        Args:
            dt: 时间步长（秒）
            affect_state: 情感状态（会调制自主神经）

        Returns:
            interoception 信号（供 L0 使用）
        """
        self.total_cycles += 1

        # === 情感调制自主神经 ===
        if affect_state is not None:
            arousal = getattr(affect_state, 'arousal', 0.5)
            valence = getattr(affect_state, 'valence', 0.0)

            # 高唤起 → 心率上升
            self._target_hr = 72.0 + arousal * 60.0  # 72 -> 132
            # 负价态 → 略微升高
            if valence < -0.3:
                self._target_hr += abs(valence) * 20.0
            # 正价态 → 平稳
            elif valence > 0.3:
                self._target_hr = 72.0 + arousal * 30.0

        # === 节律更新 ===
        # 呼吸节律
        resp_period = 60.0 / self.respiration_rate  # 秒/次
        self._respiratory_phase += (2 * math.pi / resp_period) * dt
        self._respiratory_phase %= (2 * math.pi)

        # 心率节律
        cardiac_period = 60.0 / self.heart_rate
        self._cardiac_phase += (2 * math.pi / cardiac_period) * dt
        self._cardiac_phase %= (2 * math.pi)

        # === 心率趋近目标 ===
        hr_delta = self._target_hr - self.heart_rate
        self.heart_rate += hr_delta * dt * 0.5  # 时间常数 ~2s

        # === 体温趋近目标 ===
        self._target_temp = 36.8
        if affect_state is not None:
            arousal = getattr(affect_state, 'arousal', 0.5)
            self._target_temp += arousal * 1.2  # 高唤起 → 体温微升
        temp_delta = self._target_temp - self.body_temperature
        self.body_temperature += temp_delta * dt * 0.1  # 时间常数 ~10s

        # === 异常检测 ===
        is_abnormal = False
        if self.heart_rate > 120:
            is_abnormal = True
        if self.body_temperature > 38.0:
            is_abnormal = True

        if is_abnormal:
            self.abnormal_events += 1

        # === 构建 interoception 信号 ===
        return {
            "heart_rate": self.heart_rate,
            "heart_rate_normalized": min(1.0, self.heart_rate / 150.0),
            "respiration_phase": self._respiratory_phase,
            "respiration_rate": self.respiration_rate,
            "body_temperature": self.body_temperature,
            "temperature_normalized": (self.body_temperature - 35.0) / 5.0,
            "is_abnormal": is_abnormal,
        }

    def get_interoception_array(self) -> np.ndarray:
        """返回标准 interoception 向量 [battery%, temp, cpu%, mem%]"""
        return np.array([
            0.85,                                    # battery: 正常
            min(1.0, max(0.0, (self.body_temperature - 35.0) / 5.0)),  # temp norm
            0.30,                                    # cpu: 正常
            min(1.0, max(0.0, self.heart_rate / 150.0)),  # hr norm as "load"
        ])

    def get_stats(self) -> Dict:
        return {
            "heart_rate": round(self.heart_rate, 1),
            "respiration": round(self.respiration_rate, 1),
            "temperature": round(self.body_temperature, 1),
            "abnormal_events": self.abnormal_events,
            "total_cycles": self.total_cycles,
        }


# ═══════════════════════════════════════════════════
# MotorRouter —— 运动中枢
# ═══════════════════════════════════════════════════

class MotorRouter:
    """
    运动中枢路由器。

    管理所有执行器，接收三个通路的指令并分发。
    处理多通路冲突（反射 > 决策 > 自主）。
    """

    def __init__(self):
        self.actuators: Dict[str, Actuator] = {}
        self.command_log: List[MotorCommand] = []

        # 通路统计
        self.reflexive_count = 0
        self.deliberate_count = 0
        self.autonomic_count = 0

    def register(self, actuator: Actuator):
        """注册一个执行器"""
        self.actuators[actuator.actuator_id] = actuator

    def dispatch(self, command: MotorCommand) -> bool:
        """
        分发运动指令。

        优先级：反射 > 意识决策 > 自主
        如果反射弧触发，会覆盖正在执行的意识动作。
        """
        actuator = self.actuators.get(command.actuator_id)
        if actuator is None:
            return False

        # 优先级处理
        if command.pathway == MotorPathway.REFLEXIVE:
            # 反射可覆盖决策
            self.reflexive_count += 1
        elif command.pathway == MotorPathway.DELIBERATE:
            # 如果执行器正在执行反射，决策指令暂缓
            if actuator.state.last_command and \
               actuator.state.last_command.pathway == MotorPathway.REFLEXIVE and \
               actuator.state.is_moving:
                return False  # 反射优先
            self.deliberate_count += 1
        elif command.pathway == MotorPathway.AUTONOMIC:
            self.autonomic_count += 1

        # 执行
        try:
            actuator.execute(command)
            self.command_log.append(command)
            # 限制日志长度
            if len(self.command_log) > 200:
                self.command_log = self.command_log[-100:]
            return True
        except Exception:
            return False

    def emergency_stop_all(self):
        """紧急停止所有执行器"""
        for actuator in self.actuators.values():
            actuator.emergency_stop()

    def get_state(self) -> Dict[str, ActuatorState]:
        """获取所有执行器状态"""
        return {aid: a.get_state() for aid, a in self.actuators.items()}

    def get_stats(self) -> Dict:
        return {
            "actuators": len(self.actuators),
            "reflexive_cmds": self.reflexive_count,
            "deliberate_cmds": self.deliberate_count,
            "autonomic_cmds": self.autonomic_count,
            "recent_commands": len(self.command_log),
        }


# ═══════════════════════════════════════════════════
# 独立的 L-out 层入口
# ═══════════════════════════════════════════════════

class MotorOutputLayer:
    """
    L-out 运动输出层 —— Helios v5 的核心新增。

    整合三条通路：
    1. 反射弧 (ReflexiveMotorController)
    2. 意识决策 (DeliberateMotorController)
    3. 自主神经 (AutonomicController)

    用法：
        l_out = MotorOutputLayer()
        # 注册执行器
        l_out.router.register(SimMotorActuator("base_motor", "底盘电机"))
        l_out.router.register(SimServoActuator("neck_servo", "云台舵机"))
        l_out.router.register(SimArmActuator("arm", "机械臂"))
        l_out.router.register(SimSpeakerActuator("speaker", "扬声器"))

        # 主循环中
        autonomic_state = l_out.autonomic.cycle(dt, affect_state)
        reflex_cmd = l_out.reflexive.check_and_react(sensor_frame, affect_state)
        if reflex_cmd is None:
            l_out.deliberate.execute_decision(decision, affect_state, llm_response)
    """

    def __init__(self):
        self.router = MotorRouter()
        self.reflexive = ReflexiveMotorController(self.router)
        self.deliberate = DeliberateMotorController(self.router)
        self.autonomic = AutonomicController()

        # 注册默认执行器
        self._register_defaults()

    def _register_defaults(self):
        """注册默认模拟执行器"""
        self.router.register(SimMotorActuator("base_motor", "底盘电机"))
        self.router.register(SimServoActuator("neck_servo", "云台舵机"))
        self.router.register(SimArmActuator("arm", "机械臂"))
        self.router.register(SimSpeakerActuator("speaker", "扬声器"))

    def get_full_state(self) -> Dict:
        """获取 L-out 完整状态"""
        return {
            "motors": self.router.get_state(),
            "reflexive": self.reflexive.get_stats(),
            "deliberate": self.deliberate.get_stats(),
            "autonomic": self.autonomic.get_stats(),
            "router": self.router.get_stats(),
        }
