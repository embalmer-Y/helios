"""
Helios 安全审计日志
===================

功能:
  · 包装 LimbRouter.execute() — 透明拦截所有动作
  · 完整审计追踪: 时间/动作/参数/结果/安全判定/情感状态
  · 日志格式: JSON lines (.jsonl) — 便于搜索和分析
  · 支持 LOG 级别: full(记录一切) / action(仅动作) / blocked(仅被拦截)

使用:
  from audit_log import AuditedLimbRouter
  router = AuditedLimbRouter(log_dir="./audit")
  result = router.execute(intent, emotion_state)
"""

import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
from typing import Optional, Dict, Any

from limb import LimbRouter, ActionIntent, ActionResult


# ═══════════════════════════════════════════════
# 审计条目
# ═══════════════════════════════════════════════

class AuditLevel:
    FULL   = "full"     # 记录一切
    ACTION = "action"   # 仅记录动作执行
    BLOCKED = "blocked" # 仅记录被拦截的动作

class AuditedLimbRouter:
    """
    透明审计包装 — 与 LimbRouter 接口完全兼容
    """

    def __init__(self,
                 log_dir: str = "./audit",
                 level: str = AuditLevel.ACTION):
        self._router = LimbRouter()
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._level = level

        # 按日期分文件
        today = datetime.now().strftime("%Y-%m-%d")
        self._log_file = self._log_dir / f"limb_audit_{today}.jsonl"

        # 统计
        self.total_actions = 0
        self.blocked_actions = 0
        self.failed_actions = 0

    # ── 代理 LimbRouter 接口 ──

    @property
    def limbs(self):
        return self._router.limbs

    @property
    def safety_rules(self):
        return self._router.safety_rules

    def register_limb(self, *args, **kwargs):
        return self._router.register_limb(*args, **kwargs)

    def register_safety_rule(self, *args, **kwargs):
        return self._router.register_safety_rule(*args, **kwargs)

    # ── 核心: 拦截 execute ──

    def execute(self,
                intent: ActionIntent,
                emotion_state: Optional[Any] = None) -> ActionResult:
        """
        执行动作并记录审计日志

        与 LimbRouter.execute() 签名完全一致
        """
        start_time = time.time()

        # 执行原始动作
        result = self._router.execute(intent)

        elapsed = time.time() - start_time
        self.total_actions += 1

        if result.blocked:
            self.blocked_actions += 1
        if not result.success:
            self.failed_actions += 1

        # 是否记录
        should_log = False
        if self._level == AuditLevel.FULL:
            should_log = True
        elif self._level == AuditLevel.ACTION:
            should_log = True
        elif self._level == AuditLevel.BLOCKED and result.blocked:
            should_log = True

        if should_log:
            self._write_entry(
                intent=intent,
                result=result,
                elapsed=elapsed,
                emotion=emotion_state,
            )

        return result

    def _write_entry(self,
                     intent: ActionIntent,
                     result: ActionResult,
                     elapsed: float,
                     emotion: Optional[Any] = None):
        """写入单条审计记录"""

        # 安全脱敏: 不记录文件内容, 只记录路径/命令
        params_safe = {}
        for k, v in intent.params.items():
            if isinstance(v, str) and len(v) > 200:
                params_safe[k] = v[:200] + "...(truncated)"
            elif isinstance(v, bytes):
                params_safe[k] = f"<bytes:{len(v)}>"
            else:
                params_safe[k] = v

        entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_ms": round(elapsed * 1000, 1),
            "action": {
                "type": intent.action_type,
                "params": params_safe,
                "severity": intent.severity,
            },
            "result": {
                "success": result.success,
                "blocked": result.blocked,
                "message": result.message[:500] if result.message else "",
                "error": str(result.error)[:200] if result.error else None,
            },
        }

        # 情感状态快照
        if emotion is not None:
            try:
                entry["emotion"] = {
                    "valence": getattr(emotion, "valence", None),
                    "arousal": getattr(emotion, "arousal", None),
                    "dominant": getattr(emotion, "dominant_system", None),
                }
            except Exception:
                entry["emotion"] = {"error": "snapshot_failed"}

        # 写入
        with open(self._log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── 统计 ──

    def stats(self) -> Dict[str, Any]:
        """返回当前统计摘要"""
        return {
            "total_actions": self.total_actions,
            "blocked_actions": self.blocked_actions,
            "failed_actions": self.failed_actions,
            "blocked_rate": (self.blocked_actions / max(self.total_actions, 1)),
            "failed_rate": (self.failed_actions / max(self.total_actions, 1)),
            "log_file": str(self._log_file),
            "log_level": self._level,
        }

    def flush(self):
        """强制刷新 (JSONL 自动 flush, 此方法预留)"""
        pass


# ═══════════════════════════════════════════════
# 查询工具
# ═══════════════════════════════════════════════

def query_audit_log(log_file: str,
                    action_type: Optional[str] = None,
                    blocked_only: bool = False,
                    limit: int = 100) -> list:
    """查询审计日志"""
    results = []
    with open(log_file, "r") as f:
        for line in f:
            if len(results) >= limit:
                break
            entry = json.loads(line)
            if action_type and entry["action"]["type"] != action_type:
                continue
            if blocked_only and not entry["result"]["blocked"]:
                continue
            results.append(entry)
    return results


def audit_summary(log_file: str) -> Dict[str, Any]:
    """审计日志摘要"""
    actions = {}
    blocked = 0
    total = 0
    failed = 0

    with open(log_file, "r") as f:
        for line in f:
            entry = json.loads(line)
            total += 1
            atype = entry["action"]["type"]
            actions[atype] = actions.get(atype, 0) + 1
            if entry["result"]["blocked"]:
                blocked += 1
            if not entry["result"]["success"]:
                failed += 1

    return {
        "total": total,
        "blocked": blocked,
        "failed": failed,
        "blocked_rate": blocked / max(total, 1),
        "actions": actions,
    }
