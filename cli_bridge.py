"""
Helios CLI Bridge — 数字手脚接口层
═════════════════════════════════

设计原则：
  - Helios 只表达"意图"，不关心"谁执行"
  - 适配器可热插拔，未安装的 CLI 自动降级
  - 所有结果归一化为 ActionResult
  - 支持 CLI 发现、意图路由、结果感知反馈

支持的 CLI 手脚（按优先级）：
  code      → VS Code CLI   (打开文件/编辑/跳转)
  gh        → GitHub CLI    (PR/issue/repo 操作)
  copilot   → Copilot CLI   (AI 辅助编码)
  qwen      → Qwen CLI      (模型调用)
  shell     → 通用 shell    (兜底)

参考：
  - Helios 行动意图来自 drives.py → ActionSelector
  - 执行结果回到 L0 感知 (l0_perception.py)
  - 成功/失败触发 neurochem.py 事件
"""

import os
import re
import subprocess
import shutil
import time
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum, auto


# ═══════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════

class IntentDomain(Enum):
    """意图领域"""
    FILE = auto()          # 文件操作（打开、编辑、创建、搜索）
    CODE = auto()          # 代码操作（理解、生成、重构）
    VCS = auto()           # 版本控制（commit、PR、branch）
    WEB = auto()           # Web（浏览、搜索、API）
    SYSTEM = auto()        # 系统（进程、网络、配置）
    AI_QUERY = auto()      # AI 查询（问其他模型）
    COMMUNICATION = auto() # 通信（发消息、通知）


@dataclass
class ActionIntent:
    """Helios 的行动意图

    由 DriveOracle + ActionSelector 产生，
    经 CLIBridge 路由到具体适配器执行。

    这是 Helios 的"我想..."——语义层，与具体 CLI 无关。
    """
    domain: IntentDomain               # 意图领域
    verb: str                          # 动作: "open" / "edit" / "search" / "create" / "ask" / "run"
    target: str = ""                   # 目标: 文件路径 / URL / 查询字符串
    params: Dict[str, Any] = field(default_factory=dict)  # 附加参数
    priority: float = 0.5              # 优先级 0~1
    expected_entropy_reduction: float = 0.3  # 预期减熵量
    source_drive: str = ""             # 哪个驱动产生的
    source_emotion: str = ""           # 当时主导的情感

    def describe(self) -> str:
        return f"[{self.domain.name}] {self.verb} '{self.target[:60]}'"


@dataclass
class ActionResult:
    """CLI 执行结果 → 回到 Helios L0 感知"""
    success: bool
    intent: ActionIntent
    output: str = ""                # 命令输出
    error: str = ""                 # 错误信息
    exit_code: int = 0
    duration_ms: float = 0.0
    adapter_used: str = ""          # 哪个适配器执行的
    actual_command: str = ""        # 实际执行的命令

    # 情感影响
    emotional_impact: float = 0.0   # 对情感的影响（成功→Joy，失败→Frustration）
    novelty: float = 0.0            # 新颖度
    neurochem_event: str = ""       # 触发什么神经化学事件

    def to_sensor_frame(self) -> dict:
        """转化为 L0 可感知的 SensorFrame 格式"""
        return {
            "type": "cli_result",
            "success": self.success,
            "summary": self.output[:200] if self.success else self.error[:200],
            "error": self.error,
            "action": self.intent.describe(),
            "emotional_impact": self.emotional_impact,
            "novelty": self.novelty,
            "neurochem_event": self.neurochem_event,
        }


# ═══════════════════════════════════════════════
# 抽象适配器
# ═══════════════════════════════════════════════

class CLIAdapter(ABC):
    """数字手脚的抽象基类

    每个适配器代表 Helios 的一个"肢体"。
    """

    def __init__(self, name: str, cli_command: str):
        self.name = name
        self.cli_command = cli_command
        self._available: Optional[bool] = None  # 延迟检测

    @property
    def is_available(self) -> bool:
        """CLI 是否已安装"""
        if self._available is None:
            self._available = shutil.which(self.cli_command) is not None
        return self._available

    @abstractmethod
    def can_handle(self, intent: ActionIntent) -> bool:
        """能否处理这个意图"""
        ...

    @abstractmethod
    def translate(self, intent: ActionIntent) -> List[str]:
        """意图 → shell 命令列表"""
        ...

    def execute(self, intent: ActionIntent,
                timeout: float = 30.0,
                cwd: Optional[str] = None) -> ActionResult:
        """执行意图，返回归一化结果"""
        t0 = time.time()

        if not self.is_available:
            return ActionResult(
                success=False,
                intent=intent,
                error=f"{self.name} CLI 未安装 ({self.cli_command} not found)",
                adapter_used=self.name,
            )

        commands = self.translate(intent)
        all_output = []
        all_errors = []
        final_exit_code = 0

        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                )
                out = result.stdout.strip()
                err = result.stderr.strip()
                all_output.append(out)
                if err:
                    all_errors.append(err)
                if result.returncode != 0:
                    final_exit_code = result.returncode
            except subprocess.TimeoutExpired:
                return ActionResult(
                    success=False,
                    intent=intent,
                    error=f"命令超时 ({timeout}s): {cmd}",
                    adapter_used=self.name,
                    duration_ms=(time.time() - t0) * 1000,
                )
            except Exception as e:
                return ActionResult(
                    success=False,
                    intent=intent,
                    error=str(e),
                    adapter_used=self.name,
                    duration_ms=(time.time() - t0) * 1000,
                )

        duration_ms = (time.time() - t0) * 1000
        output = "\n".join(all_output)
        error = "\n".join(all_errors) if all_errors else ""
        success = (final_exit_code == 0)

        # 情感影响：成功 → 正向，失败 → 负向
        emotional_impact = 0.12 if success else -0.10
        neurochem_event = "task_success" if success else "task_failure"

        return ActionResult(
            success=success,
            intent=intent,
            output=output,
            error=error,
            exit_code=final_exit_code,
            duration_ms=duration_ms,
            adapter_used=self.name,
            actual_command=" && ".join(commands),
            emotional_impact=emotional_impact,
            novelty=0.2,
            neurochem_event=neurochem_event,
        )

    def describe_capability(self) -> str:
        return f"{self.name} ({self.cli_command})"


# ═══════════════════════════════════════════════
# 具体适配器
# ═══════════════════════════════════════════════

class CodeCLIAdapter(CLIAdapter):
    """VS Code CLI 适配器 — "右手"

    能力：打开文件、跳转到行、编辑、diff、搜索工作区
    """

    def __init__(self):
        super().__init__("code", "code")

    def can_handle(self, intent: ActionIntent) -> bool:
        return intent.domain in (IntentDomain.FILE, IntentDomain.CODE)

    def translate(self, intent: ActionIntent) -> List[str]:
        cmd = ["code"]
        verb = intent.verb
        target = intent.target

        if verb == "open":
            cmd.append(target)
            if "line" in intent.params:
                cmd.append(f"--goto")
                cmd.append(f"{target}:{intent.params['line']}")
                if "column" in intent.params:
                    cmd[-1] += f":{intent.params['column']}"

        elif verb == "diff":
            cmd.extend(["--diff", target])
            if "other" in intent.params:
                cmd.append(intent.params["other"])

        elif verb == "edit":
            # code 没有原生的"编辑"命令，打开文件
            cmd.append(target)

        elif verb == "search":
            # 在 VS Code 中搜索
            cmd.extend(["--goto", target])  # 近似

        elif verb == "install_extension":
            cmd.extend(["--install-extension", target])

        else:
            cmd.append(target)  # 默认打开

        return [" ".join(cmd)]


class GitHubCLIAdapter(CLIAdapter):
    """GitHub CLI 适配器 — "左手"

    能力：PR、issue、repo、gist、workflow
    """

    def __init__(self):
        super().__init__("gh", "gh")

    def can_handle(self, intent: ActionIntent) -> bool:
        return intent.domain == IntentDomain.VCS

    def translate(self, intent: ActionIntent) -> List[str]:
        verb = intent.verb

        if verb == "create_pr":
            title = intent.params.get("title", "Automated PR")
            body = intent.params.get("body", "")
            base = intent.params.get("base", "main")
            head = intent.params.get("head", "")
            cmd = f'gh pr create --title "{title}" --body "{body}" --base {base}'
            if head:
                cmd += f" --head {head}"
            return [cmd]

        elif verb == "list_prs":
            state = intent.params.get("state", "open")
            return [f"gh pr list --state {state}"]

        elif verb == "create_issue":
            title = intent.params.get("title", "Issue")
            body = intent.params.get("body", "")
            return [f'gh issue create --title "{title}" --body "{body}"']

        elif verb == "list_issues":
            state = intent.params.get("state", "open")
            return [f"gh issue list --state {state}"]

        elif verb == "view_repo":
            return [f"gh repo view {intent.target}"]

        elif verb == "clone":
            return [f"gh repo clone {intent.target}"]

        elif verb == "status":
            return ["gh status"]

        else:
            return [f"gh {intent.verb} {intent.target}"]


class CopilotCLIAdapter(CLIAdapter):
    """GitHub Copilot CLI 适配器 — "大脑外挂"

    能力：代码解释、代码生成、建议
    """

    def __init__(self):
        super().__init__("copilot", "copilot")

    def can_handle(self, intent: ActionIntent) -> bool:
        return intent.domain in (IntentDomain.CODE, IntentDomain.AI_QUERY)

    def translate(self, intent: ActionIntent) -> List[str]:
        verb = intent.verb
        target = intent.target

        if verb == "explain":
            return [f'copilot explain "{target}"']
        elif verb == "suggest":
            return [f'copilot suggest "{target}"']
        elif verb == "ask":
            return [f'copilot suggest "{target}"']
        elif verb == "generate":
            language = intent.params.get("language", "")
            return [f'copilot generate "{target}"{f" --language {language}" if language else ""}']
        else:
            return [f'copilot suggest "{target}"']


class QwenCLIAdapter(CLIAdapter):
    """Qwen CLI 适配器 — "另一个大脑外挂"

    能力：调用 Qwen 模型进行推理/生成/分析
    """

    def __init__(self):
        super().__init__("qwen", "qwen")

    def can_handle(self, intent: ActionIntent) -> bool:
        return intent.domain in (IntentDomain.AI_QUERY, IntentDomain.CODE)

    def translate(self, intent: ActionIntent) -> List[str]:
        target = intent.target
        model = intent.params.get("model", "qwen3-max-preview")

        if intent.verb == "ask":
            return [f'qwen ask --model {model} "{target}"']
        elif intent.verb == "chat":
            return [f'qwen chat --model {model} -p "{target}"']
        elif intent.verb == "analyze":
            return [f'qwen ask --model {model} "分析以下内容: {target}"']
        else:
            return [f'qwen ask --model {model} "{target}"']


class ShellAdapter(CLIAdapter):
    """通用 Shell 适配器 — "兜底身体"

    任何其他适配器不能处理的，都降级到这里。
    """

    def __init__(self):
        super().__init__("shell", "sh")

    def can_handle(self, intent: ActionIntent) -> bool:
        return True  # 兜底

    @property
    def is_available(self) -> bool:
        return True  # shell 总是可用

    def translate(self, intent: ActionIntent) -> List[str]:
        verb = intent.verb
        target = intent.target

        if verb == "open":
            # 跨平台打开文件
            if shutil.which("xdg-open"):
                return [f'xdg-open "{target}"']
            elif shutil.which("open"):
                return [f'open "{target}"']
            else:
                return [f'echo "Cannot open: {target}"']

        elif verb == "search":
            # 使用 grep
            path = intent.params.get("path", ".")
            return [f'grep -rn "{target}" {path}']

        elif verb == "run":
            return [target]

        elif verb == "list":
            path = intent.params.get("path", ".")
            return [f"ls -la {path}"]

        elif verb == "read":
            return [f"cat {target}"]

        elif verb == "write":
            content = intent.params.get("content", "")
            # 安全写入：用 tee 或 echo
            escaped = content.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
            # 使用 printf 避免 echo 的转义问题
            return [f'printf "%s" "{escaped}" > {target}']

        elif verb == "mkdir":
            return [f"mkdir -p {target}"]

        elif verb == "git":
            return [f"git {target}"]

        elif verb == "count_files":
            path = intent.params.get("path", ".")
            return [f"find {path} -type f | wc -l"]

        elif verb == "sysinfo":
            return ["uname -a && echo '---' && df -h / | tail -1"]

        else:
            return [f"{intent.verb} {target}"]


# ═══════════════════════════════════════════════
# CLI 发现
# ═══════════════════════════════════════════════

def discover_available_clis() -> Dict[str, bool]:
    """检测系统上可用的 CLI

    Returns:
        {"code": True, "gh": True, "copilot": False, "qwen": False, ...}
    """
    cli_names = {
        "code": "VS Code CLI",
        "gh": "GitHub CLI",
        "copilot": "Copilot CLI",
        "qwen": "Qwen CLI",
        "code-insiders": "VS Code Insiders",
        "nvim": "Neovim",
        "vim": "Vim",
        "cursor": "Cursor IDE",
        "windsurf": "Windsurf IDE",
    }

    available = {}
    for cmd, label in cli_names.items():
        available[label] = shutil.which(cmd) is not None

    return available


# ═══════════════════════════════════════════════
# CLI 桥接器
# ═══════════════════════════════════════════════

class CLIBridge:
    """
    Helios 的数字手脚管理器

    职责：
    1. 管理所有 CLI 适配器（注册、发现、状态）
    2. 路由 ActionIntent 到最佳适配器
    3. 归一化结果
    4. 记录执行历史
    """

    def __init__(self, auto_discover: bool = True):
        # 适配器注册表（按优先级排列）
        self.adapters: List[CLIAdapter] = []

        # 默认注册
        self.register(CodeCLIAdapter())
        self.register(GitHubCLIAdapter())
        self.register(CopilotCLIAdapter())
        self.register(QwenCLIAdapter())
        self.register(ShellAdapter())  # 兜底

        # 执行历史
        self.history: List[ActionResult] = []
        self.max_history = 200

        # 统计
        self.stats = {
            "total_executions": 0,
            "successes": 0,
            "failures": 0,
            "per_adapter": {},
        }

        if auto_discover:
            self._log_availability()

    def register(self, adapter: CLIAdapter):
        """注册一个适配器"""
        self.adapters.append(adapter)

    def _log_availability(self):
        """记录所有适配器的可用性"""
        for adapter in self.adapters:
            status = "✅" if adapter.is_available else "⚠️"
            self.stats["per_adapter"][adapter.name] = {
                "available": adapter.is_available,
                "executions": 0,
                "successes": 0,
            }

    def _find_adapter(self, intent: ActionIntent) -> CLIAdapter:
        """找到能处理此意图的最佳适配器

        优先级：可用 > 专用 > 通用
        """
        for adapter in self.adapters:
            if adapter.is_available and adapter.can_handle(intent):
                # 跳过 shell 如果存在更好的选择
                if isinstance(adapter, ShellAdapter):
                    continue
                return adapter

        # 降级到 shell
        for adapter in self.adapters:
            if isinstance(adapter, ShellAdapter):
                return adapter

        # 不应该到这里
        return ShellAdapter()

    def execute(self,
                intent: ActionIntent,
                timeout: float = 30.0,
                cwd: Optional[str] = None,
                dry_run: bool = False) -> ActionResult:
        """
        执行一个行动意图

        Args:
            intent: Helios 的行动意图
            timeout: 命令超时
            cwd: 工作目录
            dry_run: 仅展示翻译结果，不实际执行（安全模式）

        Returns:
            ActionResult
        """
        adapter = self._find_adapter(intent)

        if dry_run:
            commands = adapter.translate(intent)
            return ActionResult(
                success=True,
                intent=intent,
                output=f"[DRY RUN] Would execute via {adapter.name}:\n  " + "\n  ".join(commands),
                adapter_used=adapter.name,
                actual_command="\n".join(commands),
            )

        result = adapter.execute(intent, timeout=timeout, cwd=cwd)

        # 记录历史
        self.history.append(result)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        # 更新统计
        self.stats["total_executions"] += 1
        if result.success:
            self.stats["successes"] += 1
        else:
            self.stats["failures"] += 1

        if adapter.name in self.stats["per_adapter"]:
            self.stats["per_adapter"][adapter.name]["executions"] += 1
            if result.success:
                self.stats["per_adapter"][adapter.name]["successes"] += 1

        return result

    def list_capabilities(self) -> List[str]:
        """列出所有可用的能力"""
        caps = []
        for adapter in self.adapters:
            if adapter.is_available:
                caps.append(f"  {adapter.describe_capability()}")
        return caps

    def describe(self) -> str:
        """人类可读的状态报告"""
        lines = [f"🔌 CLIBridge: {sum(1 for a in self.adapters if a.is_available)}/{len(self.adapters)} 适配器可用"]
        for adapter in self.adapters:
            icon = "✅" if adapter.is_available else "❌"
            lines.append(f"  {icon} {adapter.describe_capability()}")
        lines.append(f"📊 总计: {self.stats['total_executions']} 执行 "
                     f"({self.stats['successes']}✅ {self.stats['failures']}❌)")
        return "\n".join(lines)


# ═══════════════════════════════════════════════
# Helios → CLIBridge 高层接口
# ═══════════════════════════════════════════════

class HeliosHands:
    """
    Helios 的"手"——对 CLIBridge 的高层封装

    用法：
      hands = HeliosHands()
      result = hands.do("打开 /path/to/file.py")
      result = hands.do("提交 PR", title="Fix bug", body="...")
    """

    def __init__(self, auto_discover: bool = True, dry_run: bool = False):
        self.bridge = CLIBridge(auto_discover=auto_discover)
        self.dry_run = dry_run
        self.cwd = os.getcwd()

    def do(self,
           description: str,
           domain: Optional[IntentDomain] = None,
           verb: Optional[str] = None,
           target: str = "",
           **params) -> ActionResult:
        """
        快捷执行

        Args:
            description: 人类语言描述（用于日志）
            domain/verb/target: 覆盖自动解析
        """
        if domain is None or verb is None:
            domain, verb, target = self._parse_intent(description)

        intent = ActionIntent(
            domain=domain,
            verb=verb,
            target=target,
            params=params,
            priority=0.5,
        )

        return self.bridge.execute(intent, dry_run=self.dry_run, cwd=self.cwd)

    def _parse_intent(self, text: str) -> Tuple[IntentDomain, str, str]:
        """从自然语言解析意图（简化版）"""
        text_lower = text.lower()

        if any(w in text_lower for w in ["打开", "open", "编辑", "edit", "文件", "file"]):
            # 提取文件路径
            import re
            path_match = re.search(r'["\']?([/\w.]+\.\w+)["\']?', text)
            target = path_match.group(1) if path_match else ""
            verb = "edit" if any(w in text_lower for w in ["编辑", "edit"]) else "open"
            return IntentDomain.FILE, verb, target

        if any(w in text_lower for w in ["pr", "pull request", "合并", "merge"]):
            return IntentDomain.VCS, "create_pr", ""

        if any(w in text_lower for w in ["搜索", "search", "查找", "find", "grep"]):
            return IntentDomain.CODE, "search", text

        if any(w in text_lower for w in ["问", "ask", "解释", "explain", "分析", "analyze"]):
            return IntentDomain.AI_QUERY, "ask", text

        if any(w in text_lower for w in ["运行", "run", "执行", "execute"]):
            return IntentDomain.SYSTEM, "run", text

        # 默认：shell
        return IntentDomain.SYSTEM, "run", text


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 CLI Bridge 自测")
    print("=" * 60)

    # 发现可用 CLI
    print("\n📡 CLI 发现:")
    clis = discover_available_clis()
    for label, avail in clis.items():
        print(f"  {'✅' if avail else '❌'} {label}")

    # 创建桥接器
    bridge = CLIBridge()
    print(f"\n{bridge.describe()}")

    # 测试意图路由（dry-run 模式，安全）
    print("\n🔀 意图路由测试 (dry-run):")

    intents = [
        ActionIntent(IntentDomain.FILE, "open", "/home/radxa/project/helios/core.py",
                     params={"line": 42},
                     source_drive="curiosity", source_emotion="hope"),
        ActionIntent(IntentDomain.VCS, "create_pr", "",
                     params={"title": "Add thinking module", "body": "Phase 4 complete", "base": "master"},
                     source_drive="achievement", source_emotion="joy"),
        ActionIntent(IntentDomain.AI_QUERY, "ask", "解释自由能原理",
                     source_drive="curiosity", source_emotion="wonder"),
        ActionIntent(IntentDomain.CODE, "search", "class HeliosCore",
                     params={"path": "/home/radxa/project/helios"},
                     source_drive="curiosity", source_emotion="hope"),
    ]

    for intent in intents:
        result = bridge.execute(intent, dry_run=True)
        icon = "✅" if result.success else "❌"
        print(f"\n  {icon} {intent.describe()}")
        print(f"     适配器: {result.adapter_used}")
        print(f"     命令:   {result.output[:120]}")

    # 真实执行一个安全的命令
    print("\n🔧 真实执行测试:")
    result = bridge.execute(
        ActionIntent(IntentDomain.SYSTEM, "run", "echo 'Hello from Helios CLI Bridge'"),
        dry_run=False,
    )
    print(f"  成功: {result.success}")
    print(f"  输出: {result.output}")
    print(f"  耗时: {result.duration_ms:.1f}ms")
    print(f"  情感影响: {result.emotional_impact:+.2f}")
    print(f"  神经化学事件: {result.neurochem_event}")

    # HeliosHands 高层接口
    print("\n🤲 HeliosHands 测试:")
    hands = HeliosHands(dry_run=True)
    r = hands.do("打开 /home/radxa/project/helios/core.py")
    print(f"  意图: {r.intent.describe()}")
    print(f"  适配器: {r.adapter_used}")

    print("\n✅ 自测通过")
