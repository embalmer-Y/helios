"""
helios_io/ — Helios I/O 层

包含 LLM SEC 评估、对话历史管理、响应管道、QQ 接口等。
"""

from .conversation_history import ConversationExchange, ConversationHistoryManager
from .response_pipeline import ResponsePipeline
