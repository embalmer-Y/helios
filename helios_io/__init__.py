"""
helios_io/ — Helios I/O 层

包含 LLM SEC 评估、对话历史管理、响应管道、QQ 接口等。
"""

from .conversation_history import ConversationExchange, ConversationHistoryManager
from .action_models import ActionDecision, ActionProposal, BehaviorSpec, ExecutionFeedback
from .bootstrap_behavior_specs import build_bootstrap_behavior_specs
from .channel import ChannelDescriptor, ChannelOpDescriptor
from .interaction_policy import InteractionAssessment, InteractionPolicy, InteractionSignals
from .planning import ExecutionPlanner, PolicyEvaluation, PolicyEvaluator, PolicyViolation
from .response_pipeline import ResponsePipeline
