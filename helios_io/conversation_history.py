"""
helios_io/conversation_history.py — Conversation History Management

维护每用户的对话历史缓冲区（最多 20 条交换），为 SEC 评估和回复生成提供上下文。

每条 ConversationExchange 记录:
  - 用户消息 + 时间戳 + SEC 评估结果（接收时写入）
  - 回复文本 + 情感上下文（发送时写入）

使用 FIFO 策略在超出 20 条时驱逐最旧条目。

Requirements: 7.4, 8.1, 8.2, 8.3, 8.4
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

log = logging.getLogger("helios.helios_io.conversation_history")

# ═══════════════════════════════════════════════════
# 默认配置
# ═══════════════════════════════════════════════════

DEFAULT_MAX_HISTORY = 20


# ═══════════════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════════════

@dataclass
class ConversationExchange:
    """
    单次对话交换记录。

    接收消息时创建 (带 timestamp + user_message + sec_result)，
    发送回复时补充 (reply + emotional_context)。
    """

    timestamp: float
    """消息接收的时间戳 (Unix epoch seconds)"""

    user_message: str
    """用户发送的消息文本"""

    conversation_key: str = ""
    """会话标识；为空表示未提供可用会话边界"""

    sec_result: Dict[str, float] = field(default_factory=dict)
    """SEC 评估结果 {novelty, pleasantness, goal_relevance, ...}"""

    reply: Optional[str] = None
    """Helios 的回复文本 (None 表示未生成回复)"""

    emotional_context: Dict[str, float] = field(default_factory=dict)
    """生成回复时的情感上下文 {dominant_system, valence, arousal, mood_label, ...}"""


# ═══════════════════════════════════════════════════
# 对话历史管理器
# ═══════════════════════════════════════════════════

class ConversationHistoryManager:
    """
    管理所有用户的对话历史。

    每个用户维护一个最多 max_history 条的 FIFO 缓冲区。
    超过限制时自动驱逐最旧条目。

    Requirements:
      - 8.1: 每用户最多 20 条交换
      - 8.2: 接收消息时追加 timestamp + SEC 结果
      - 8.3: 发送回复时追加 emotional_context
      - 8.4: 超限时丢弃最旧交换 (FIFO)
    """

    def __init__(self, max_history: int = DEFAULT_MAX_HISTORY):
        """
        Args:
            max_history: 每用户最大保存交换数 (默认 20)
        """
        if max_history < 1:
            raise ValueError(f"max_history must be >= 1, got {max_history}")
        self._max_history = max_history
        self._histories: Dict[str, Deque[ConversationExchange]] = {}

    @property
    def max_history(self) -> int:
        """每用户最大交换数"""
        return self._max_history

    def get_user_ids(self) -> List[str]:
        """返回所有有历史记录的用户 ID 列表"""
        return list(self._histories.keys())

    def get_history(self, user_id: str, conversation_key: str = "") -> List[ConversationExchange]:
        """
        获取指定用户的对话历史。

        Args:
            user_id: 用户标识符

        Returns:
            按时间顺序排列的交换列表 (最旧在前)
        """
        if user_id not in self._histories:
            return []
        history = list(self._histories[user_id])
        if not conversation_key:
            return history
        return [ex for ex in history if ex.conversation_key == conversation_key]

    def get_recent_messages(self, user_id: str, count: int = 3, conversation_key: str = "") -> List[str]:
        """
        获取最近 N 条用户消息文本，用于 SEC 评估上下文。

        Args:
            user_id: 用户标识符
            count: 要返回的最大消息数

        Returns:
            最近消息文本列表 (按时间正序)
        """
        if user_id not in self._histories:
            return []
        recent = self.get_history(user_id, conversation_key=conversation_key)[-count:]
        return [ex.user_message for ex in recent]

    def get_recent_exchange_texts(
        self,
        user_id: str,
        count: int = 5,
        conversation_key: str = "",
    ) -> List[str]:
        """获取最近 N 轮交换的文本摘要，用于记忆检索与提示词构建。"""
        history = self.get_history(user_id, conversation_key=conversation_key)[-count:]
        texts: List[str] = []
        for ex in history:
            lines = []
            if ex.user_message:
                lines.append(f"对方: {ex.user_message}")
            if ex.reply:
                lines.append(f"你: {ex.reply}")
            if lines:
                texts.append("\n".join(lines))
        return texts

    def history_length(self, user_id: str) -> int:
        """返回指定用户的当前历史长度"""
        if user_id not in self._histories:
            return 0
        return len(self._histories[user_id])

    def append_message(
        self,
        user_id: str,
        message: str,
        sec_result: Dict[str, float],
        timestamp: Optional[float] = None,
        conversation_key: str = "",
    ) -> ConversationExchange:
        """
        接收消息时追加到对话历史。

        创建一个新的 ConversationExchange，填入 timestamp、user_message
        和 sec_result。reply 和 emotional_context 留空待后续补充。

        超过 max_history 时 FIFO 驱逐最旧条目。

        Args:
            user_id: 用户标识符
            message: 用户消息文本
            sec_result: SEC 评估结果字典
            timestamp: 消息时间戳 (默认使用 time.time())

        Returns:
            创建的 ConversationExchange 实例

        Requirements: 8.2
        """
        if timestamp is None:
            timestamp = time.time()

        exchange = ConversationExchange(
            timestamp=timestamp,
            user_message=message,
            conversation_key=conversation_key,
            sec_result=dict(sec_result),  # 防御性拷贝
        )

        # 确保用户队列存在
        if user_id not in self._histories:
            self._histories[user_id] = deque(maxlen=self._max_history)

        buf = self._histories[user_id]
        buf.append(exchange)

        log.debug(
            f"追加消息到 {user_id} 历史 (长度: {len(buf)}/{self._max_history})"
        )

        return exchange

    def append_reply(
        self,
        user_id: str,
        reply: str,
        emotional_context: Dict[str, float],
        conversation_key: str = "",
    ) -> bool:
        """
        发送回复时补充最新交换的 reply 和 emotional_context。

        将 reply 文本和情感上下文写入该用户历史中最后一条交换记录。
        如果历史为空或最后一条已有 reply，则不操作并返回 False。

        Args:
            user_id: 用户标识符
            reply: Helios 生成的回复文本
            emotional_context: 回复时的情感状态字典
                例: {"dominant_system": "CARE", "valence": 0.5,
                     "arousal": 0.3, "mood_label": "content"}

        Returns:
            True 如果成功附加，False 如果无法附加

        Requirements: 8.3
        """
        if user_id not in self._histories:
            log.warning(f"无法附加回复: 用户 {user_id} 无对话历史")
            return False

        buf = self._histories[user_id]
        if len(buf) == 0:
            log.warning(f"无法附加回复: 用户 {user_id} 历史为空")
            return False

        target_exchange: Optional[ConversationExchange] = None
        for exchange in reversed(buf):
            if conversation_key and exchange.conversation_key != conversation_key:
                continue
            if exchange.reply is None:
                target_exchange = exchange
                break

        if target_exchange is None:
            log.warning(
                "无法附加回复: 用户 %s 未找到可匹配的待回复历史 (conversation_key=%s)",
                user_id,
                conversation_key or "missing",
            )
            return False

        target_exchange.reply = reply
        target_exchange.emotional_context = dict(emotional_context)  # 防御性拷贝

        log.debug(f"回复已附加到 {user_id} 最新交换")
        return True

    def clear_user(self, user_id: str) -> None:
        """清空指定用户的对话历史"""
        if user_id in self._histories:
            self._histories[user_id].clear()
            log.debug(f"已清空用户 {user_id} 的对话历史")

    def clear_all(self) -> None:
        """清空所有用户的对话历史"""
        self._histories.clear()
        log.debug("已清空所有对话历史")

    def get_state(self) -> dict:
        """返回对话历史管理器状态，用于监控"""
        user_counts = {
            uid: len(buf) for uid, buf in self._histories.items()
        }
        total = sum(user_counts.values())
        return {
            "max_history_per_user": self._max_history,
            "active_users": len(self._histories),
            "total_exchanges": total,
            "per_user_counts": user_counts,
        }
