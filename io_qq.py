"""
io_qq.py — Helios QQ 消息 I/O

当前后端: QwenPaw CLI 转发 (Phase 1)
  发送: qwenpaw channels send (HTTP → QQ Bot API)
  接收: JSONL 文件轮询 (后续升级为 WebSocket)

未来后端: napcat/LLOneBot OneBot v11 HTTP API (Phase 2)
  POST /send_private_msg  /send_group_msg
  WebSocket / 反向 HTTP 事件推送

作者: 璃光 · Helios v2.0.0-alpha
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("helios.io_qq")


# ── 消息结构 ──────────────────────────────────────

@dataclass
class QQMessage:
    """QQ 消息"""
    message_id: str = ""
    user_id: str = ""           # QQ 号
    text: str = ""              # 纯文本
    group_id: str = ""          # 群聊时非空
    is_group: bool = False
    timestamp: float = 0.0


# ── 配置 ──────────────────────────────────────────

class QQIOConfig:
    """QQ I/O 配置 (环境变量优先)"""

    def __init__(self):
        # QwenPaw CLI 模式
        self.agent_id: str = os.getenv("HELIOS_QQ_AGENT_ID", "default")
        self.channel: str = os.getenv("HELIOS_QQ_CHANNEL", "qq")
        self.user_id: str = os.getenv("HELIOS_QQ_USER_ID", "")
        self.session_id: str = os.getenv("HELIOS_QQ_SESSION_ID", "")

        # 文件接收模式
        self.incoming_path: str = os.getenv(
            "HELIOS_QQ_INCOMING_FILE",
            "/tmp/helios_incoming.jsonl",
        )

        # 超时
        self.send_timeout: float = float(os.getenv("HELIOS_QQ_SEND_TIMEOUT", "15"))


# ── QQ I/O 主类 ────────────────────────────────────

class QQIO:
    """
    统一 QQ 消息 I/O 接口

    send 和 receive 不耦合 — Helios 可以随时发消息，
    也可以随时检查是否有新消息。
    """

    def __init__(self, config: Optional[QQIOConfig] = None):
        self.cfg = config or QQIOConfig()
        self._incoming_offset = 0       # 已读行数
        self._lock = threading.Lock()
        self._auto_discovered = False

    # ── 发现配置 ─────────────────────────────────

    def discover(self) -> bool:
        """自动发现 QQ 会话参数 (通过 qwenpaw chats list)"""
        if self.cfg.user_id and self.cfg.session_id:
            return True

        try:
            result = subprocess.run(
                [
                    "qwenpaw", "chats", "list",
                    "--agent-id", self.cfg.agent_id,
                    "--channel", self.cfg.channel,
                ],
                capture_output=True, text=True,
                timeout=8,
            )
            if result.returncode != 0:
                log.warning("qwenpaw chats list 失败: %s", result.stderr.strip())
                return False

            sessions = json.loads(result.stdout)
            for s in sessions:
                if s.get("channel") == self.cfg.channel:
                    self.cfg.user_id = s["user_id"]
                    self.cfg.session_id = s["session_id"]
                    log.info(
                        "自动发现 QQ 会话: user=%s session=%s",
                        self.cfg.user_id, self.cfg.session_id,
                    )
                    return True

            log.warning("未找到 QQ 频道会话")
            return False

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            log.warning("自动发现失败: %s", e)
            return False

    # ── 发送 ─────────────────────────────────────

    def send_message(self, text: str, user_id: str = "") -> bool:
        """发送私聊消息"""
        uid = user_id or self.cfg.user_id
        sid = self.cfg.session_id

        if not uid or not sid:
            log.error("send_message: 缺少 user_id/session_id，请先调用 discover()")
            return False

        try:
            result = subprocess.run(
                [
                    "qwenpaw", "channels", "send",
                    "--agent-id", self.cfg.agent_id,
                    "--channel", self.cfg.channel,
                    "--target-user", uid,
                    "--target-session", sid,
                    "--text", text,
                ],
                capture_output=True, text=True,
                timeout=self.cfg.send_timeout,
            )

            if result.returncode != 0:
                log.warning("发送失败 (exit=%d): %s", result.returncode, result.stderr.strip())
                return False

            response = json.loads(result.stdout)
            ok = response.get("success", False)
            if ok:
                log.debug("QQ 发送成功: %s", text[:60])
            else:
                log.warning("QQ 发送失败: %s", response.get("message", ""))
            return ok

        except subprocess.TimeoutExpired:
            log.error("QQ 发送超时")
            return False
        except json.JSONDecodeError as e:
            log.error("QQ 响应解析失败: %s", e)
            return False

    # ── 接收 ─────────────────────────────────────

    def receive_messages(self) -> list[QQMessage]:
        """
        读取新消息 (JSONL 文件轮询)

        格式: {"user_id": "...", "text": "...", "message_id": "...", "timestamp": ...}

        未来: WebSocket / napcat 事件推送
        """
        path = Path(self.cfg.incoming_path)
        if not path.exists():
            return []

        messages: list[QQMessage] = []
        with self._lock:
            try:
                with open(path, "r") as f:
                    lines = f.readlines()
                new_lines = lines[self._incoming_offset:]
                self._incoming_offset = len(lines)

                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        msg = QQMessage(
                            message_id=data.get("message_id", ""),
                            user_id=data.get("user_id", ""),
                            text=data.get("text", ""),
                            group_id=data.get("group_id", ""),
                            is_group=bool(data.get("group_id", "")),
                            timestamp=data.get("timestamp", time.time()),
                        )
                        messages.append(msg)
                    except json.JSONDecodeError:
                        log.debug("跳过非法 JSON: %s", line[:80])
            except Exception as e:
                log.warning("读取 incoming 失败: %s", e)

        return messages

    def write_incoming(self, msg: QQMessage):
        """写入接收队列 (供外部中继使用)"""
        path = Path(self.cfg.incoming_path)
        with self._lock:
            try:
                with open(path, "a") as f:
                    f.write(json.dumps({
                        "user_id": msg.user_id,
                        "text": msg.text,
                        "message_id": msg.message_id,
                        "group_id": msg.group_id,
                        "timestamp": msg.timestamp or time.time(),
                    }, ensure_ascii=False) + "\n")
            except Exception as e:
                log.warning("写入 incoming 失败: %s", e)

    # ── 状态 ─────────────────────────────────────

    def get_state(self) -> dict:
        return {
            "backend": "qwenpaw_cli",
            "user_id": self.cfg.user_id,
            "channel": self.cfg.channel,
            "incoming_offset": self._incoming_offset,
        }
