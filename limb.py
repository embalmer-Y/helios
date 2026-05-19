"""
Helios 统一手脚接口层
═══════════════════

设计原则：
  - 一切输出皆 Limb — 物理执行器和 CLI 工具地位平等
  - 每个 Limb 自带 SafetyRule — 物理有碰撞检测，数字有命令白名单
  - 统一神经连接 — 所有 Limb 接入同一套 neurochem 反馈管道
  - 热插拔 — 添加/移除手脚不影响核心架构

架构：
  HeliosCore
      │
  Decision (7种动作类型)
      │
  HeliosBody (统一门面)
      │
  LimbRouter (安全门控 + 路由)
      ├── PhysicalLimb (motor, servo, arm, speaker)
      ├── DigitalLimb  (code, gh, copilot, qwen, shell)
      └── ...
"""

import os
import re
import time
import math
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple, Set
from enum import Enum, auto


# ═══════════════════════════════════════════════
# 基础数据结构
# ═══════════════════════════════════════════════

class LimbType(Enum):
    PHYSICAL = "physical"   # 物理执行器（电机、舵机、机械臂、扬声器）
    DIGITAL = "digital"     # 数字工具（CLI、API、文件系统）


class LimbStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"      # 可用但受限
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class ActionIntent:
    """Helios 的行动意图 — 统一格式

    不管是"转动舵机30度"还是"git commit"，
    都通过同一个意图结构表达。
    """
    domain: str = ""               # "motor" / "file" / "vcs" / "ai_query" / "system"
    verb: str = ""                 # "move" / "open" / "create_pr" / "ask" / "run"
    target: str = ""               # 目标标识（执行器ID / 文件路径 / URL）
    params: Dict[str, Any] = field(default_factory=dict)
    priority: float = 0.5          # 0~1
    source_drive: str = ""         # 哪个驱动产生的
    source_emotion: str = ""

    # 物理扩展（可选）
    velocity: float = 0.0
    force: float = 0.0
    target_position: Optional[List[float]] = None

    def describe(self) -> str:
        return f"[{self.domain}] {self.verb} '{self.target[:60]}'"


@dataclass
class ActionResult:
    """统一执行结果 — 回到 Helios 感知"""
    success: bool
    intent: ActionIntent
    limb_name: str = ""
    output: str = ""
    error: str = ""
    exit_code: int = 0
    duration_ms: float = 0.0
    actual_command: str = ""

    # 情感/神经化学影响
    emotional_impact: float = 0.0
    novelty: float = 0.0
    neurochem_event: str = ""       # "task_success" / "task_failure" / "threat_detected"

    # 物理扩展
    new_position: Optional[List[float]] = None

    def to_sensor_frame(self) -> dict:
        return {
            "type": "action_result",
            "success": self.success,
            "limb": self.limb_name,
            "summary": self.output[:200] if self.success else self.error[:200],
            "emotional_impact": self.emotional_impact,
            "novelty": self.novelty,
            "neurochem_event": self.neurochem_event,
        }


@dataclass
class LimbState:
    """手脚状态快照"""
    status: LimbStatus = LimbStatus.OFFLINE
    last_action: str = ""
    total_executions: int = 0
    successes: int = 0
    failures: int = 0
    uptime_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════
# 安全规则系统
# ═══════════════════════════════════════════════

class SafetyRule(ABC):
    """安全规则 — 每个 Limb 可以注册多条"""

    def __init__(self, name: str, severity: str = "block"):
        """
        Args:
            name: 规则名称
            severity: "block" (阻止执行) / "warn" (警告但允许) / "limit" (限制参数)
        """
        self.name = name
        self.severity = severity
        self.trigger_count = 0

    @abstractmethod
    def check(self, intent: ActionIntent) -> Tuple[bool, str]:
        """检查意图是否安全

        Returns:
            (is_safe, reason)
        """
        ...

    def triggered(self):
        self.trigger_count += 1


class VelocityLimitRule(SafetyRule):
    """物理安全：速度上限"""
    def __init__(self, max_velocity: float = 0.8):
        super().__init__("velocity_limit", "limit")
        self.max_velocity = max_velocity

    def check(self, intent: ActionIntent) -> Tuple[bool, str]:
        if intent.velocity > self.max_velocity:
            return False, f"速度 {intent.velocity:.2f} 超过上限 {self.max_velocity}"
        return True, ""


class ForceLimitRule(SafetyRule):
    """物理安全：力度上限"""
    def __init__(self, max_force: float = 0.9):
        super().__init__("force_limit", "limit")
        self.max_force = max_force

    def check(self, intent: ActionIntent) -> Tuple[bool, str]:
        if intent.force > self.max_force:
            return False, f"力度 {intent.force:.2f} 超过上限 {self.max_force}"
        return True, ""


class PathAllowlistRule(SafetyRule):
    """数字安全：路径白名单"""
    def __init__(self, allowed_paths: List[str], blocked_paths: List[str] = None):
        super().__init__("path_allowlist", "block")
        self.allowed = [os.path.abspath(p) for p in allowed_paths]
        self.blocked = [os.path.abspath(p) for p in (blocked_paths or [])]

        # 永远阻止的路径
        self.always_blocked = ["/etc/passwd", "/etc/shadow", "/boot", "/sys", "/proc"]

    def check(self, intent: ActionIntent) -> Tuple[bool, str]:
        target = os.path.abspath(intent.target) if intent.target else ""
        if not target:
            return True, ""

        # 黑名单检查
        for blocked in self.always_blocked + self.blocked:
            if target.startswith(blocked):
                return False, f"路径 {target} 在黑名单中"

        # 白名单检查
        if self.allowed:
            for allowed in self.allowed:
                if target.startswith(allowed):
                    return True, ""
            return False, f"路径 {target} 不在白名单中"

        return True, ""


class CommandAllowlistRule(SafetyRule):
    """数字安全：命令白名单"""
    def __init__(self, allowed_commands: List[str], blocked_commands: List[str] = None):
        super().__init__("command_allowlist", "block")
        self.allowed = set(allowed_commands)
        self.blocked = set(blocked_commands or [])

        # 永远阻止的危险命令
        self.always_blocked = {
            "rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:",
            "chmod 777 /", "> /dev/sda",
        }

    def check(self, intent: ActionIntent) -> Tuple[bool, str]:
        cmd = intent.verb + " " + intent.target

        for dangerous in self.always_blocked:
            if dangerous in cmd:
                return False, f"命令包含危险操作: {dangerous}"

        for blocked in self.blocked:
            if blocked in cmd:
                return False, f"命令 {blocked} 在黑名单中"

        if self.allowed:
            if intent.verb not in self.allowed:
                return False, f"动词 '{intent.verb}' 不在白名单中"

        return True, ""


class RateLimitRule(SafetyRule):
    """数字安全：频率限制"""
    def __init__(self, max_per_minute: int = 30):
        super().__init__("rate_limit", "block")
        self.max_per_minute = max_per_minute
        self._window: List[float] = []

    def check(self, intent: ActionIntent) -> Tuple[bool, str]:
        now = time.time()
        # 清理过期记录
        self._window = [t for t in self._window if now - t < 60]
        if len(self._window) >= self.max_per_minute:
            return False, f"频率超限 ({self.max_per_minute}/min)"
        self._window.append(now)
        return True, ""


class DryRunRule(SafetyRule):
    """数字安全：高风险操作需 dry-run 确认"""
    def __init__(self, risky_verbs: List[str] = None):
        super().__init__("dry_run_required", "block")
        self.risky_verbs = set(risky_verbs or [
            "rm", "delete", "drop", "truncate", "overwrite",
            "force_push", "hard_reset",
        ])

    def check(self, intent: ActionIntent) -> Tuple[bool, str]:
        if intent.verb in self.risky_verbs:
            if not intent.params.get("confirmed", False):
                return False, f"高风险操作 '{intent.verb}' 需要 explicit confirmation"
        return True, ""


# ═══════════════════════════════════════════════
# Limb 抽象基类
# ═══════════════════════════════════════════════

class Limb(ABC):
    """
    统一的手脚抽象 — Helios 的一切输出通道

    每个 Limb 是 Helios 的一个"肢体"。
    物理肢体和数字肢体地位完全平等。
    """

    def __init__(self, name: str, limb_type: LimbType):
        self.name = name
        self.limb_type = limb_type
        self.state = LimbState(status=LimbStatus.OFFLINE)

        # 安全规则
        self.safety_rules: List[SafetyRule] = []

        # 神经连接 — 对每种神经调质的敏感度
        self.neurochem_sensitivity: Dict[str, float] = {
            "dopamine": 0.3,
            "opioids": 0.2,
            "oxytocin": 0.1,
            "cortisol": 0.4,
        }

        # 能力声明
        self.capabilities: Set[str] = set()
        self.supported_verbs: Set[str] = set()

    def add_safety_rule(self, rule: SafetyRule):
        self.safety_rules.append(rule)

    def check_safety(self, intent: ActionIntent) -> Tuple[bool, str]:
        """检查所有安全规则"""
        for rule in self.safety_rules:
            safe, reason = rule.check(intent)
            if not safe:
                rule.triggered()
                if rule.severity == "block":
                    return False, f"[{rule.name}] {reason}"
        return True, ""

    @abstractmethod
    def can_handle(self, intent: ActionIntent) -> bool:
        """能否处理此意图"""
        ...

    @abstractmethod
    def _do_execute(self, intent: ActionIntent) -> ActionResult:
        """实际执行（子类实现）"""
        ...

    def execute(self, intent: ActionIntent) -> ActionResult:
        """执行意图（含安全检查）"""
        t0 = time.time()

        if self.state.status == LimbStatus.EMERGENCY_STOP:
            return ActionResult(
                success=False, intent=intent, limb_name=self.name,
                error="EMERGENCY_STOP 激活，拒绝执行",
                duration_ms=(time.time() - t0) * 1000,
            )

        # 安全检查
        safe, reason = self.check_safety(intent)
        if not safe:
            return ActionResult(
                success=False, intent=intent, limb_name=self.name,
                error=f"安全检查未通过: {reason}",
                duration_ms=(time.time() - t0) * 1000,
                neurochem_event="task_blocked",
            )

        result = self._do_execute(intent)
        result.limb_name = self.name

        # 更新状态
        self.state.total_executions += 1
        if result.success:
            self.state.successes += 1
            self.state.last_action = intent.describe()
        else:
            self.state.failures += 1

        return result

    def emergency_stop(self):
        """紧急停止"""
        self.state.status = LimbStatus.EMERGENCY_STOP

    def resume(self):
        """恢复"""
        if self.state.status == LimbStatus.EMERGENCY_STOP:
            self.state.status = LimbStatus.ONLINE if self.is_available() else LimbStatus.OFFLINE

    @abstractmethod
    def is_available(self) -> bool:
        ...

    def describe(self) -> str:
        icon = "🔧" if self.limb_type == LimbType.PHYSICAL else "💻"
        status_icon = {"online": "✅", "offline": "❌", "degraded": "⚠️",
                       "emergency_stop": "🛑"}.get(self.state.status.value, "❓")
        return f"{icon} {status_icon} {self.name} ({self.limb_type.value})"


# ═══════════════════════════════════════════════
# 物理手脚
# ═══════════════════════════════════════════════

class PhysicalLimb(Limb):
    """
    物理执行器 — 电机、舵机、机械臂、扬声器等

    包装原有的 Actuator 接口。
    """

    def __init__(self, name: str, actuator_id: str,
                 actuator: Any = None):  # Actuator from motor_output
        super().__init__(name, LimbType.PHYSICAL)
        self.actuator_id = actuator_id
        self._actuator = actuator  # 延迟绑定

        # 物理安全规则
        self.add_safety_rule(VelocityLimitRule(0.8))
        self.add_safety_rule(ForceLimitRule(0.9))

        self.supported_verbs = {"move", "rotate", "grip", "release", "stop", "speak"}
        self.capabilities = {"motor", "physical"}

        # 先假设在线（由外部注册时确认）
        self.state.status = LimbStatus.ONLINE

    def can_handle(self, intent: ActionIntent) -> bool:
        return intent.domain == "motor" and intent.target == self.actuator_id

    def _do_execute(self, intent: ActionIntent) -> ActionResult:
        t0 = time.time()

        if self._actuator is None:
            # 模拟模式
            return ActionResult(
                success=True, intent=intent, limb_name=self.name,
                output=f"[SIM] {intent.verb} on {self.actuator_id} "
                       f"(v={intent.velocity:.2f}, f={intent.force:.2f})",
                duration_ms=(time.time() - t0) * 1000,
                emotional_impact=0.05,
                neurochem_event="task_success",
            )

        # 真实执行
        try:
            cmd = type('MotorCommand', (), {
                'pathway': 'deliberate',
                'actuator_id': self.actuator_id,
                'action_type': intent.verb,
                'velocity': intent.velocity,
                'force': intent.force,
                'target_position': intent.target_position,
            })()
            self._actuator.execute(cmd)
            return ActionResult(
                success=True, intent=intent, limb_name=self.name,
                output=f"{intent.verb} on {self.actuator_id} OK",
                duration_ms=(time.time() - t0) * 1000,
                emotional_impact=0.05,
                neurochem_event="task_success",
            )
        except Exception as e:
            return ActionResult(
                success=False, intent=intent, limb_name=self.name,
                error=str(e),
                duration_ms=(time.time() - t0) * 1000,
                emotional_impact=-0.08,
                neurochem_event="task_failure",
            )

    def is_available(self) -> bool:
        return True  # 模拟执行器始终可用


# ═══════════════════════════════════════════════
# 数字手脚
# ═══════════════════════════════════════════════

class DigitalLimb(Limb):
    """
    数字工具 — CLI 命令、API 调用等

    包装原有的 CLIAdapter 接口。
    """

    def __init__(self, name: str, cli_command: str,
                 domains: List[str] = None,
                 verbs: List[str] = None,
                 work_dir: str = "/home/radxa"):
        super().__init__(name, LimbType.DIGITAL)
        self.cli_command = cli_command
        self.work_dir = work_dir
        self._available: Optional[bool] = None

        self.supported_verbs = set(verbs or [])
        self.capabilities = set(domains or [])

        # 数字安全规则
        self.add_safety_rule(CommandAllowlistRule(
            allowed_commands=verbs or [],
            blocked_commands=["rm -rf", "mkfs", "shutdown", "reboot"],
        ))
        self.add_safety_rule(RateLimitRule(30))
        self.add_safety_rule(PathAllowlistRule(
            allowed_paths=[work_dir, "/tmp", os.path.expanduser("~")],
            blocked_paths=["/etc", "/boot", "/sys", "/proc"],
        ))
        self.add_safety_rule(DryRunRule())

        self.translators: Dict[str, Callable] = {}  # verb → command builder

    def add_translator(self, verb: str, builder: Callable[[ActionIntent], str]):
        """注册动词 → 命令的翻译器"""
        self.translators[verb] = builder
        self.supported_verbs.add(verb)

    def can_handle(self, intent: ActionIntent) -> bool:
        return (intent.domain in self.capabilities and
                intent.verb in self.supported_verbs)

    def _do_execute(self, intent: ActionIntent) -> ActionResult:
        t0 = time.time()

        if not self.is_available():
            return ActionResult(
                success=False, intent=intent, limb_name=self.name,
                error=f"{self.cli_command} 未安装",
                duration_ms=(time.time() - t0) * 1000,
            )

        # 翻译意图 → shell 命令
        if intent.verb in self.translators:
            cmd = self.translators[intent.verb](intent)
        else:
            cmd = f"{self.cli_command} {intent.verb} {intent.target}"

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=intent.params.get("timeout", 30),
                cwd=intent.params.get("cwd", self.work_dir),
            )
            out = result.stdout.strip()
            err = result.stderr.strip()
            ok = result.returncode == 0

            return ActionResult(
                success=ok, intent=intent, limb_name=self.name,
                output=out, error=err, exit_code=result.returncode,
                duration_ms=(time.time() - t0) * 1000,
                actual_command=cmd,
                emotional_impact=0.12 if ok else -0.10,
                novelty=0.15,
                neurochem_event="task_success" if ok else "task_failure",
            )
        except subprocess.TimeoutExpired:
            return ActionResult(
                success=False, intent=intent, limb_name=self.name,
                error=f"超时 ({intent.params.get('timeout', 30)}s)",
                duration_ms=(time.time() - t0) * 1000,
                neurochem_event="task_failure",
            )
        except Exception as e:
            return ActionResult(
                success=False, intent=intent, limb_name=self.name,
                error=str(e),
                duration_ms=(time.time() - t0) * 1000,
                neurochem_event="task_failure",
            )

    def is_available(self) -> bool:
        if self._available is None:
            self._available = shutil.which(self.cli_command) is not None
        return self._available


# ═══════════════════════════════════════════════
# 手脚工厂 — 预置常用手脚
# ═══════════════════════════════════════════════

def create_shell_limb(work_dir: str = "/home/radxa") -> DigitalLimb:
    """创建 Shell 数字手脚（兜底）"""
    limb = DigitalLimb("shell", "sh",
                       domains=["file", "system", "code"],
                       work_dir=work_dir)

    # 注册动词翻译器
    limb.add_translator("list", lambda i: f"ls -la {i.params.get('path', '.')}")
    limb.add_translator("read", lambda i: f"cat {i.target}")
    limb.add_translator("write", lambda i:
        f'printf "%s" "{i.params.get("content", "").replace(chr(34), chr(92)+chr(34))}" > {i.target}')
    limb.add_translator("mkdir", lambda i: f"mkdir -p {i.target}")
    limb.add_translator("search", lambda i:
        f'grep -rn "{i.target}" {i.params.get("path", ".")}')
    limb.add_translator("count_files", lambda i:
        f"find {i.params.get('path', '.')} -type f | wc -l")
    limb.add_translator("sysinfo", lambda i: "uname -a && df -h / | tail -1")
    limb.add_translator("run", lambda i: i.target)
    limb.add_translator("git", lambda i: f"git {i.target}")
    limb.add_translator("open", lambda i:
        f'xdg-open "{i.target}"' if shutil.which("xdg-open")
        else f'echo "Cannot open: {i.target}"')

    return limb


def create_code_limb() -> DigitalLimb:
    """创建 VS Code 数字手脚"""
    limb = DigitalLimb("code", "code",
                       domains=["file", "code"],
                       verbs=["open", "edit", "diff", "search"])

    limb.add_translator("open", lambda i:
        f'code "{i.target}"' +
        (f' --goto "{i.target}:{i.params["line"]}"' if "line" in i.params else ""))
    limb.add_translator("diff", lambda i:
        f'code --diff "{i.target}" "{i.params.get("other", "")}"')
    limb.add_translator("edit", lambda i: f'code "{i.target}"')

    return limb


def create_gh_limb() -> DigitalLimb:
    """创建 GitHub CLI 数字手脚"""
    limb = DigitalLimb("gh", "gh",
                       domains=["vcs"],
                       verbs=["create_pr", "list_prs", "create_issue",
                              "view_repo", "clone", "status"])

    limb.add_translator("create_pr", lambda i:
        f'gh pr create --title "{i.params.get("title", "PR")}" '
        f'--body "{i.params.get("body", "")}" '
        f'--base {i.params.get("base", "main")}')
    limb.add_translator("list_prs", lambda i:
        f'gh pr list --state {i.params.get("state", "open")}')
    limb.add_translator("create_issue", lambda i:
        f'gh issue create --title "{i.params.get("title", "Issue")}" '
        f'--body "{i.params.get("body", "")}"')

    return limb


def create_physical_limbs() -> List[PhysicalLimb]:
    """创建默认物理手脚"""
    return [
        PhysicalLimb("底盘电机", "base_motor"),
        PhysicalLimb("云台舵机", "neck_servo"),
        PhysicalLimb("机械臂", "arm"),
        PhysicalLimb("扬声器", "speaker"),
    ]


# ═══════════════════════════════════════════════
# 手脚路由器
# ═══════════════════════════════════════════════

class LimbRouter:
    """
    统一手脚路由器 — 取代 MotorRouter + CLIBridge

    核心创新：数字手脚也有安全门控
    """

    def __init__(self):
        self.limbs: Dict[str, Limb] = {}
        self.history: List[ActionResult] = []
        self.max_history = 200

        # 全局紧急停止
        self.global_emergency = False

    def register(self, limb: Limb):
        """注册一个手脚"""
        self.limbs[limb.name] = limb
        limb.state.status = LimbStatus.ONLINE if limb.is_available() else LimbStatus.OFFLINE

    def unregister(self, name: str):
        """移除一个手脚"""
        self.limbs.pop(name, None)

    def emergency_stop_all(self):
        """全局紧急停止"""
        self.global_emergency = True
        for limb in self.limbs.values():
            limb.emergency_stop()

    def resume_all(self):
        """全局恢复"""
        self.global_emergency = False
        for limb in self.limbs.values():
            limb.resume()

    def find_limb(self, intent: ActionIntent) -> Optional[Limb]:
        """找到能处理此意图的最佳手脚"""
        candidates = []

        for limb in self.limbs.values():
            if limb.state.status == LimbStatus.EMERGENCY_STOP:
                continue
            if limb.can_handle(intent):
                candidates.append(limb)

        if not candidates:
            return None

        # 排序：在线 > 降级 > 离线（虽然离线不会进候选）
        # 物理优先（更直接）
        candidates.sort(key=lambda l: (
            0 if l.state.status == LimbStatus.ONLINE else 1,
            0 if l.limb_type == LimbType.PHYSICAL else 1,
        ))

        return candidates[0]

    def execute(self, intent: ActionIntent) -> ActionResult:
        """执行意图"""
        if self.global_emergency:
            return ActionResult(
                success=False, intent=intent,
                error="全局紧急停止激活",
                neurochem_event="threat_detected",
            )

        limb = self.find_limb(intent)
        if limb is None:
            return ActionResult(
                success=False, intent=intent,
                error=f"没有可用的手脚能处理: {intent.describe()}",
            )

        result = limb.execute(intent)

        # 记录历史
        self.history.append(result)
        if len(self.history) > self.max_history:
            self.history = self.history[-100:]

        return result

    def list_limbs(self) -> List[str]:
        return [limb.describe() for limb in self.limbs.values()]

    def get_stats(self) -> Dict:
        total = sum(l.state.total_executions for l in self.limbs.values())
        successes = sum(l.state.successes for l in self.limbs.values())
        return {
            "limbs": len(self.limbs),
            "online": sum(1 for l in self.limbs.values()
                         if l.state.status == LimbStatus.ONLINE),
            "total_executions": total,
            "successes": successes,
            "failures": total - successes,
            "emergency": self.global_emergency,
        }


# ═══════════════════════════════════════════════
# HeliosBody — 统一门面
# ═══════════════════════════════════════════════

class HeliosBody:
    """
    Helios 的"身体" — 所有手脚的统一入口

    用法：
      body = HeliosBody()
      body.add_default_limbs()

      result = body.act(ActionIntent(domain="system", verb="list", target="."))
      result = body.do_list()
    """

    def __init__(self):
        self.router = LimbRouter()

    def add_default_limbs(self):
        """添加所有默认手脚"""
        # 物理手脚
        for limb in create_physical_limbs():
            self.router.register(limb)

        # 数字手脚
        self.router.register(create_shell_limb())
        self.router.register(create_code_limb())
        self.router.register(create_gh_limb())

    def act(self, intent: ActionIntent) -> ActionResult:
        """执行一个意图"""
        return self.router.execute(intent)

    # 快捷方法
    def do_list(self, path: str = ".") -> ActionResult:
        return self.act(ActionIntent("system", "list", path))

    def do_read(self, path: str) -> ActionResult:
        return self.act(ActionIntent("file", "read", path))

    def do_write(self, path: str, content: str) -> ActionResult:
        return self.act(ActionIntent("file", "write", path,
                                     params={"content": content}))

    def do_search(self, query: str, path: str = ".") -> ActionResult:
        return self.act(ActionIntent("code", "search", query,
                                     params={"path": path}))

    def do_git(self, args: str) -> ActionResult:
        return self.act(ActionIntent("vcs", "git", args))

    def do_sysinfo(self) -> ActionResult:
        return self.act(ActionIntent("system", "sysinfo", ""))

    def emergency_stop(self):
        self.router.emergency_stop_all()

    def describe(self) -> str:
        lines = ["🦾 HeliosBody — 统一手脚层"]
        lines.extend(self.router.list_limbs())
        stats = self.router.get_stats()
        lines.append(f"📊 {stats['online']}/{stats['limbs']} 在线 | "
                     f"{stats['total_executions']} 执行 "
                     f"({stats['successes']}✅ {stats['failures']}❌)")
        return "\n".join(lines)


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 HeliosBody 统一手脚自测")
    print("=" * 60)

    # 创建身体
    body = HeliosBody()
    body.add_default_limbs()
    print(body.describe())

    # 测试安全规则
    print("\n🛡️ 安全规则测试:")

    # 测试1：正常操作
    r1 = body.do_list(".")
    print(f"  ✅ list: {r1.output[:60]}")

    # 测试2：路径白名单 — 尝试读取 /etc/passwd 应被阻止
    r2 = body.do_read("/etc/passwd")
    print(f"  {'❌' if not r2.success else '⚠️'} read /etc/passwd: {r2.error[:60]}")

    # 测试3：搜索代码
    r3 = body.do_search("class HeliosBody", "/home/radxa/project/helios")
    print(f"  ✅ search: {r3.output[:60] if r3.success else r3.error[:60]}")

    # 测试4：危险命令
    r4 = body.act(ActionIntent("system", "rm", "-rf /"))
    print(f"  ❌ rm -rf /: {r4.error[:60]}")

    # 测试5：sysinfo
    r5 = body.do_sysinfo()
    print(f"  ✅ sysinfo: {r5.output[:60]}")

    # 测试6：紧急停止
    print("\n🛑 紧急停止测试:")
    body.emergency_stop()
    r6 = body.do_list(".")
    print(f"  ❌ 紧急停止后: {r6.error}")

    body.router.resume_all()

    # 测试7：物理手脚
    r7 = body.act(ActionIntent("motor", "move", "base_motor",
                               velocity=0.5, force=0.3))
    print(f"  ✅ motor: {r7.output}")

    # 测试8：速度超限
    r8 = body.act(ActionIntent("motor", "move", "base_motor",
                               velocity=0.95, force=0.3))
    print(f"  ❌ overspeed: {r8.error[:60]}")

    # 统计
    print(f"\n{body.describe()}")

    print("\n✅ 自测通过")
