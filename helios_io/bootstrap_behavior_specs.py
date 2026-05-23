"""Bootstrap behavior specifications used before the DB-backed registry lands."""

from __future__ import annotations

from .action_models import BehaviorSpec


REGULATION_CHANNEL_BOOTSTRAP = {
    "speak_care": {"cooldown": 600, "night_suppress": True, "hint": "关心主人"},
    "speak_missing": {"cooldown": 900, "night_suppress": False, "hint": "表达想念"},
    "speak_play": {"cooldown": 1200, "night_suppress": True, "hint": "逗主人开心"},
    "speak_fear": {"cooldown": 600, "night_suppress": False, "hint": "寻求安抚"},
    "speak_share": {"cooldown": 900, "night_suppress": True, "hint": "分享想法"},
    "speak_complain": {"cooldown": 3600, "night_suppress": True, "hint": "表达不满"},
    "intimate": {"cooldown": 1800, "night_suppress": True, "hint": "亲密表达"},
    "request": {"cooldown": 7200, "night_suppress": True, "hint": "向主人提需求"},
}


REGULATION_INTERNAL_BOOTSTRAP = {
    "browse": {
        "description": "Explore external resources.",
        "cooldown": 600,
        "night_suppress": True,
        "hint": "上网冲浪",
    },
    "search": {
        "description": "Search for targeted information.",
        "cooldown": 180,
        "night_suppress": True,
        "hint": "搜索知识",
    },
    "learn": {
        "description": "Run a deeper learning routine.",
        "cooldown": 1800,
        "night_suppress": True,
        "hint": "深入学习",
    },
    "reflect": {
        "description": "Run an internal reflective loop.",
        "cooldown": 3600,
        "night_suppress": True,
        "hint": "自我反思",
    },
    "check_system": {
        "description": "Inspect internal runtime health.",
        "cooldown": 1800,
        "night_suppress": True,
        "hint": "检查自身状态",
    },
    "idle": {
        "description": "Remain idle without taking an external action.",
        "cooldown": 0,
        "night_suppress": True,
        "hint": "静静待着",
    },
}


def build_bootstrap_behavior_specs() -> dict[str, BehaviorSpec]:
    channel_behaviors = {
        "reply_message": BehaviorSpec(
            behavior_id="bootstrap.reply_message",
            name="reply_message",
            display_name="Reply Message",
            description="Reply to an inbound interaction through an outbound channel.",
            category="interaction",
            execution_mode="channel",
            parameter_schema={
                "target_user_id": {"required": False, "default": ""},
                "outbound_text": {"required": False, "default": ""},
                "outbound_metadata": {"required": False, "default": {}},
            },
            applicable_context={
                "policy_domains": ["interaction_passive"],
                "requires_inbound_message": True,
                "channel_delivery": "reply",
            },
            cooldown_policy={"seconds": 0, "night_suppress": False},
            cost_policy={"cost": 0.1},
            allowed_channel_ids=["qq", "tts"],
            supported_modalities=["text", "speech"],
            source_kind="bootstrap",
            source_detail={
                "phase": "transition",
                "bootstrap_profile": {
                    "policy_domains": ["interaction_passive"],
                    "hint": "回复当前输入",
                },
            },
        )
    }

    for action_name, config in REGULATION_CHANNEL_BOOTSTRAP.items():
        channel_behaviors[action_name] = BehaviorSpec(
            behavior_id=f"bootstrap.{action_name}",
            name=action_name,
            display_name=action_name.replace("_", " ").title(),
            description=f"Bootstrap outbound expression for {action_name}.",
            category="expression",
            execution_mode="channel",
            parameter_schema={
                "tick": {"required": False, "default": 0},
                "target_user_id": {"required": False, "default": ""},
            },
            applicable_context={
                "policy_domains": ["regulation_active"],
                "delivery_scope": "outbound_expression",
                "requires_target_user": action_name != "intimate",
            },
            cooldown_policy={
                "seconds": config["cooldown"],
                "night_suppress": config["night_suppress"],
            },
            cost_policy={"cost": 0.2},
            allowed_channel_ids=["qq", "tts"],
            supported_modalities=["text", "speech"],
            source_kind="bootstrap",
            source_detail={
                "phase": "transition",
                "bootstrap_profile": {
                    "policy_domains": ["regulation_active"],
                    "hint": config["hint"],
                    "legacy_action_type": action_name,
                },
            },
        )

    specs = dict(channel_behaviors)
    for action_name, config in REGULATION_INTERNAL_BOOTSTRAP.items():
        specs[action_name] = BehaviorSpec(
            behavior_id=f"bootstrap.{action_name}",
            name=action_name,
            display_name=action_name.replace("_", " ").title(),
            description=str(config["description"]),
            category="internal",
            execution_mode="internal",
            parameter_schema={"tick": {"required": False, "default": 0}},
            applicable_context={
                "policy_domains": ["regulation_active"],
                "delivery_scope": "internal",
            },
            cooldown_policy={
                "seconds": config["cooldown"],
                "night_suppress": config["night_suppress"],
            },
            cost_policy={"cost": 0.05},
            supported_modalities=["internal"],
            source_kind="bootstrap",
            source_detail={
                "phase": "transition",
                "bootstrap_profile": {
                    "policy_domains": ["regulation_active"],
                    "hint": config["hint"],
                    "legacy_action_type": action_name,
                },
            },
        )

    return specs