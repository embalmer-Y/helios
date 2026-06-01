"""
helios_io/protocols/qq.py — Helios QQ Bot I/O (独立实现 v2)

直接连接 QQ Bot API (官方 WebSocket + HTTP)：
  · Token:  POST bots.qq.com/app/getAppAccessToken
  · 接收:   WebSocket (OP_DISPATCH → C2C_MESSAGE_CREATE)
  · 发送:   POST api.sgroup.qq.com/v2/users/{openid}/messages

完全不依赖 QwenPaw，符合 [D011] 独立进程决策。

要求: pip install websocket-client requests

作者: 璃光 · Helios v2.0.0-alpha · G4
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import requests

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

log = logging.getLogger("helios.helios_io.protocols.qq")


# ═══════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════

DEFAULT_API_BASE = "https://sandbox.api.sgroup.qq.com"
TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"

# WebSocket op codes
OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_RESUME = 6
OP_RECONNECT = 7
OP_INVALID_SESSION = 9
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11

# Intents
INTENT_PUBLIC_GUILD_MESSAGES = 1 << 30
INTENT_DIRECT_MESSAGE = 1 << 12
INTENT_GROUP_AND_C2C = 1 << 25
INTENT_GUILD_MEMBERS = 1 << 1

# 重连
RECONNECT_DELAYS = [1, 2, 5, 10, 30, 60]


# ═══════════════════════════════════════════════════
# 消息结构
# ═══════════════════════════════════════════════════

@dataclass
class QQMessage:
    """接收到的 QQ 消息"""
    message_id: str = ""
    user_id: str = ""           # 发送者 QQ 号 (或 openid)
    author_id: str = ""         # QQ Bot API 的 author.id
    text: str = ""
    group_id: str = ""
    guild_id: str = ""
    is_group: bool = False
    is_guild: bool = False
    timestamp: float = 0.0
    raw: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════
# QQ Bot 客户端
# ═══════════════════════════════════════════════════

class QQBotClient:
    """
    Helios 独立 QQ Bot 客户端。

    WebSocket 接收消息 → 回调 → Helios 事件系统。
    HTTP API 发送消息。

    Usage:
        def on_msg(msg: QQMessage):
            print(f"收到: {msg.text}")

        bot = QQBotClient(
            app_id="123456",
            client_secret="your_secret",
            on_message=on_msg,
        )
        bot.start()   # 启动 WebSocket 线程
        bot.send_c2c("USER_OPENID", "你好！")
        bot.stop()
    """

    def __init__(
        self,
        app_id: str = "",
        client_secret: str = "",
        api_base: str = "",
        on_message: Optional[Callable[[QQMessage], None]] = None,
        sandbox: bool = True,
    ):
        self.app_id = app_id or os.getenv("HELIOS_QQ_APP_ID", "")
        self.client_secret = client_secret or os.getenv("HELIOS_QQ_CLIENT_SECRET", "")
        self.api_base = (api_base or os.getenv("HELIOS_QQ_API_BASE", DEFAULT_API_BASE)).rstrip("/")
        self.sandbox = sandbox
        self.on_message = on_message

        # 运行时
        self._ws: Optional[websocket.WebSocket] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._http_session: Optional[requests.Session] = None
        self._stop_event = threading.Event()
        self._heartbeat_interval = 45000  # ms
        self._last_seq: Optional[int] = None
        self._session_id: Optional[str] = None
        self._reconnect_attempts = 0

        # Token 缓存
        self._token: str = ""
        self._token_expires_at: float = 0.0
        self._token_lock = threading.Lock()

    # ── Token ───────────────────────────────────

    def _get_token(self) -> str:
        """获取/刷新 access_token (线程安全)"""
        with self._token_lock:
            now = time.time()
            if self._token and now < self._token_expires_at - 300:
                return self._token

        resp = requests.post(
            TOKEN_URL,
            json={"appId": self.app_id, "clientSecret": self.client_secret},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"Token 获取失败: {data}")

        expires_in = int(data.get("expires_in", 7200))
        with self._token_lock:
            self._token = token
            self._token_expires_at = time.time() + expires_in

        log.info("access_token 已刷新 (过期=%ds)", expires_in)
        return token

    # ── 网关 ────────────────────────────────────

    def _get_gateway_url(self) -> str:
        """获取 WebSocket 网关地址"""
        token = self._get_token()
        resp = requests.get(
            f"{self.api_base}/gateway",
            headers={"Authorization": f"QQBot {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        url = data.get("url")
        if not url:
            raise RuntimeError(f"网关地址获取失败: {data}")
        return url

    # ── 发送消息 ─────────────────────────────────

    def send_c2c(self, openid: str, text: str, msg_id: str = "") -> bool:
        """
        发送 C2C (私聊) 文本消息。

        返回: True 成功 / False 失败
        """
        token = self._get_token()
        body: dict = {
            "content": text,
            "msg_type": 0,
            "msg_seq": int(time.time() * 1000) % (1 << 31),
        }
        if msg_id:
            body["msg_id"] = msg_id

        try:
            resp = requests.post(
                f"{self.api_base}/v2/users/{openid}/messages",
                json=body,
                headers={
                    "Authorization": f"QQBot {token}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                result = resp.json()
                log.debug("C2C 发送成功: id=%s", result.get("id", ""))
                return True
            else:
                log.warning("C2C 发送失败 HTTP %d: %s", resp.status_code, resp.text[:200])
                return False
        except Exception as e:
            log.error("C2C 发送异常: %s", e)
            return False

    def send_group(self, group_openid: str, text: str, msg_id: str = "") -> bool:
        """
        发送群聊文本消息。
        """
        token = self._get_token()
        body: dict = {
            "content": text,
            "msg_type": 0,
            "msg_seq": int(time.time() * 1000) % (1 << 31),
        }
        if msg_id:
            body["msg_id"] = msg_id

        try:
            resp = requests.post(
                f"{self.api_base}/v2/groups/{group_openid}/messages",
                json=body,
                headers={
                    "Authorization": f"QQBot {token}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            return resp.status_code == 200
        except Exception as e:
            log.error("群聊发送异常: %s", e)
            return False

    # ── WebSocket 循环 ──────────────────────────

    def start(self):
        """启动 WebSocket 接收线程"""
        if not HAS_WEBSOCKET:
            raise ImportError("需要安装 websocket-client: pip install websocket-client")

        if not self.app_id or not self.client_secret:
            raise ValueError("HELIOS_QQ_APP_ID 和 HELIOS_QQ_CLIENT_SECRET 未配置")

        self._stop_event.clear()
        self._ws_thread = threading.Thread(
            target=self._run_forever,
            daemon=True,
            name="helios-qq-ws",
        )
        self._ws_thread.start()
        log.info("QQ Bot WebSocket 线程已启动")

    def stop(self):
        """停止 WebSocket"""
        self._stop_event.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._ws_thread:
            self._ws_thread.join(timeout=3)
        log.info("QQ Bot 已停止")

    def is_connected(self) -> bool:
        """WebSocket 是否已连接"""
        if self._ws is None:
            return False
        try:
            sock = self._ws.sock
            if sock is None:
                return False
            # SSL 和普通 socket 兼容
            return getattr(sock, 'connected', True)
        except Exception:
            return False

    # ── 内部: WebSocket 主循环 ───────────────────

    def _run_forever(self):
        """WebSocket 线程主循环 (带重连)"""
        while not self._stop_event.is_set():
            try:
                self._connect_loop()
            except Exception:
                log.exception("QQ WebSocket 异常，准备重连...")

            if self._stop_event.is_set():
                break

            # 重连延迟
            delay = RECONNECT_DELAYS[min(
                self._reconnect_attempts,
                len(RECONNECT_DELAYS) - 1,
            )]
            log.info("QQ WebSocket %d 秒后重连...", delay)
            self._stop_event.wait(delay)

    def _connect_loop(self):
        gateway_url = self._get_gateway_url()
        log.info("连接 QQ 网关: %s", gateway_url[:40])

        self._ws = websocket.create_connection(
            gateway_url,
            timeout=30,
        )

        try:
            self._event_loop()
        finally:
            if self._ws:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None

    def _event_loop(self):
        """WebSocket 事件循环 (单次连接)"""
        heartbeat_timer = 0.0

        while not self._stop_event.is_set():
            # 设置 recv 超时 (用于检查 stop_event)
            self._ws.settimeout(1.0)

            try:
                op_code, data = self._ws.recv_data()
            except websocket.WebSocketTimeoutException:
                # 超时 → 检查心跳
                now = time.time()
                if self._heartbeat_interval > 0 and now - heartbeat_timer > self._heartbeat_interval / 1000:
                    self._send_heartbeat()
                    heartbeat_timer = now
                continue
            except (websocket.WebSocketConnectionClosedException, ConnectionError, OSError):
                log.info("QQ WebSocket 断开")
                break

            if op_code == OP_CLOSE:
                log.info("QQ WebSocket 收到 CLOSE")
                break

            if not data:
                continue

            try:
                payload = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                continue

            op = payload.get("op")
            d = payload.get("d")
            s = payload.get("s")
            t = payload.get("t")

            if s is not None:
                self._last_seq = s

            if op == OP_HELLO:
                hi = d or {}
                self._heartbeat_interval = hi.get("heartbeat_interval", 45000)
                self._do_identify()
                heartbeat_timer = time.time()

            elif op == OP_DISPATCH:
                self._handle_dispatch(t, d or {})

            elif op == OP_HEARTBEAT_ACK:
                pass  # 正常

            elif op == OP_RECONNECT:
                log.info("QQ 服务器要求重连")
                break

            elif op == OP_INVALID_SESSION:
                log.warning("QQ session 无效，重新鉴权")
                self._session_id = None
                self._last_seq = None
                break

    def _send_heartbeat(self):
        if self._ws and self._ws.sock:
            try:
                self._ws.send(json.dumps({
                    "op": OP_HEARTBEAT,
                    "d": self._last_seq,
                }))
            except Exception:
                pass

    def _do_identify(self):
        """发送鉴权"""
        token = self._get_token()
        intents = (
            INTENT_PUBLIC_GUILD_MESSAGES
            | INTENT_GUILD_MEMBERS
            | INTENT_DIRECT_MESSAGE
            | INTENT_GROUP_AND_C2C
        )
        payload = {
            "op": OP_IDENTIFY,
            "d": {
                "token": f"QQBot {token}",
                "intents": intents,
                "shard": [0, 1],
            },
        }
        self._ws.send(json.dumps(payload))
        log.debug("OP_IDENTIFY 已发送")

    def _handle_dispatch(self, event_type: str, data: dict):
        """处理 OP_DISPATCH 事件"""
        if event_type == "READY":
            self._session_id = data.get("session_id")
            self._reconnect_attempts = 0
            log.info("QQ Bot 就绪! session=%s", self._session_id)

        elif event_type == "RESUMED":
            self._reconnect_attempts = 0
            log.info("QQ session 恢复")

        elif event_type == "C2C_MESSAGE_CREATE":
            self._on_c2c_message(data)

        elif event_type == "GROUP_AT_MESSAGE_CREATE":
            self._on_group_message(data)

        elif event_type == "GUILD_MESSAGE_CREATE":
            # 频道消息 (暂不处理)
            pass

    # ── 消息解析 ─────────────────────────────────

    def _on_c2c_message(self, data: dict):
        author = data.get("author", {})
        msg = QQMessage(
            message_id=data.get("id", ""),
            user_id=author.get("id", ""),
            author_id=author.get("id", ""),
            text=data.get("content", ""),
            is_group=False,
            timestamp=time.time(),
            raw=data,
        )
        log.info("📩 QQ私聊 [%s]: %s", msg.author_id[:10], msg.text[:60])
        if self.on_message:
            try:
                self.on_message(msg)
            except Exception:
                log.exception("on_message 回调异常")

    def _on_group_message(self, data: dict):
        author = data.get("author", {})
        group_id = data.get("group_id", "")
        msg = QQMessage(
            message_id=data.get("id", ""),
            user_id=author.get("id", ""),
            author_id=author.get("id", ""),
            text=data.get("content", ""),
            group_id=group_id,
            is_group=True,
            timestamp=time.time(),
            raw=data,
        )
        log.info("📩 QQ群聊 [%s/%s]: %s", group_id, msg.author_id[:10], msg.text[:60])
        if self.on_message:
            try:
                self.on_message(msg)
            except Exception:
                log.exception("on_message 回调异常")

    # ── 状态 ─────────────────────────────────────

    def get_state(self) -> dict:
        return {
            "backend": "qq_official_ws",
            "app_id": self.app_id,
            "connected": self.is_connected(),
            "session_id": self._session_id,
        }


# ═══════════════════════════════════════════════════
# OP_CLOSE (websocket-client 常量兼容)
# ═══════════════════════════════════════════════════

try:
    from websocket import ABNF
    OP_CLOSE = ABNF.OPCODE_CLOSE
except ImportError:
    OP_CLOSE = 8
