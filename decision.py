"""
Helios 决策引擎 v2.0

基于 L2 广播内容 + 情感状态 + 记忆 + 自我模型 → 决策

评估维度：
- 情感偏好：当前情感状态如何影响选择
- 自我一致性：选择是否与"我是谁"一致
- 目标相关性：选择是否推进当前目标
- 预期 Φ：选择是否可能带来高度整合的体验
- 运动效益：选择是否具备可执行的物理意义

v2.0 新增：
- action 类型与 MotorOutputLayer 的 DeliberateMotorController 对齐
- 加入 approach（靠近目标）动作
- express 统一为单类型，由情感和 LLM 输出填充内容
"""

import numpy as np
from typing import List, Dict, Optional, Any

from .core import L1Output, AffectState, Decision, Goal, HeliosConfig


class DecisionEngine:
    """
    决策引擎 v2.0。

    不是冰冷的效用计算器，而是有情感偏好的决策者。
    当前情感状态、个人历史、自我认同都会影响决策。

    Action 类型与 MotorOutputLayer 对齐：
    - observe   → 保持观察（停止运动）
    - explore   → 扫描环境（云台旋转）
    - withdraw  → 撤退回避（反向移动）
    - approach  → 靠近目标（正向移动）
    - express   → 语言/情感表达（扬声器输出）
    - rest      → 低功耗待机
    - learn     → 认知加工（内部动作，无物理输出）
    """

    def __init__(self, config: HeliosConfig):
        self.config = config

        # 候选动作库 — v2 与 MotorOutputLayer 对齐
        self.action_pool = [
            {'type': 'observe',  'description': '保持观察，维持现状',
             'novelty': 0.1, 'predicted_phi': 0.3, 'movement': False},
            {'type': 'explore',  'description': '深入探索环境，扫描周围',
             'novelty': 0.6, 'predicted_phi': 0.5, 'movement': True},
            {'type': 'withdraw', 'description': '回避威胁，撤退到安全位置',
             'novelty': 0.0, 'predicted_phi': 0.1, 'movement': True},
            {'type': 'approach', 'description': '主动靠近目标或刺激源',
             'novelty': 0.4, 'predicted_phi': 0.5, 'movement': True},
            {'type': 'express',  'description': '表达情感或说出想法',
             'novelty': 0.3, 'predicted_phi': 0.4, 'movement': False},
            {'type': 'rest',     'description': '进入低功耗休息状态',
             'novelty': 0.0, 'predicted_phi': 0.05, 'movement': False},
            {'type': 'learn',    'description': '投入认知资源学习当前模式',
             'novelty': 0.4, 'predicted_phi': 0.6, 'movement': False},
        ]

        self.decision_history: List[Decision] = []

    def decide(self,
               l1_output: L1Output,
               affect: AffectState,
               memory_system,
               self_model=None,
               goal: Optional[Goal] = None) -> Optional[Decision]:
        """
        做出决策。

        Returns:
            Decision 或 None（如果没到需要决策的时刻）
        """
        # 只在有足够信息时做决策
        if l1_output.fused_qualia is None or l1_output.phi < 0.2:
            return None

        # 获取候选动作
        candidates = self._get_candidates(affect)

        # 评估每个候选
        evaluations = []
        for candidate in candidates:
            score, reasoning = self._evaluate(
                candidate=candidate,
                affect=affect,
                self_model=self_model,
                goal=goal,
                l1_output=l1_output
            )
            evaluations.append((candidate, score, reasoning))

        # 按分数排序
        evaluations.sort(key=lambda x: x[1], reverse=True)

        if not evaluations:
            return None

        best = evaluations[0]
        confidence = (
            best[1] - evaluations[1][1]
            if len(evaluations) > 1 else 0.5
        )

        decision = Decision(
            action=best[0],
            confidence=confidence,
            reasoning=best[2],
        )

        self.decision_history.append(decision)
        self.decision_history = self.decision_history[-100:]

        return decision

    def _get_candidates(self, affect: AffectState) -> List[dict]:
        """根据情感状态筛选候选动作 — v2 版本"""
        candidates = []

        for action in self.action_pool:
            # 情感过滤
            if affect.is_positive:
                # 心情好：探索、靠近、表达、学习
                if action['type'] in ['explore', 'approach', 'express', 'learn']:
                    candidates.append(action.copy())
            elif affect.is_negative:
                # 心情差：回避或保持静止
                if action['type'] in ['withdraw', 'observe', 'rest']:
                    candidates.append(action.copy())
            else:
                # 中性：都可以
                candidates.append(action.copy())

        # 确保至少有一些候选
        if not candidates:
            candidates = [self.action_pool[0].copy()]

        return candidates

    def _evaluate(self,
                  candidate: dict,
                  affect: AffectState,
                  self_model,
                  goal: Optional[Goal],
                  l1_output: L1Output) -> tuple:
        """
        五维度评估候选动作。

        Returns:
            (分数, 推理文字)
        """
        score = 0.0
        reasons = []

        # === 1. 情感偏好 (20%) ===
        if affect.is_positive and candidate['type'] in ['explore', 'approach', 'express']:
            score += 0.20
            reasons.append("心情好，愿意主动行动")
        elif affect.is_negative and candidate['type'] in ['withdraw', 'observe']:
            score += 0.20
            reasons.append("心情不好，倾向保守")
        elif candidate['type'] == 'observe':
            score += 0.10
            reasons.append("保持中性观察")

        # === 2. 自我一致性 (25%) ===
        if self_model and hasattr(self_model.state, 'self_narrative_embedding'):
            if self_model.state.self_narrative_embedding is not None:
                if self_model.total_updates > 10:
                    if candidate['type'] in ['explore', 'approach', 'learn']:
                        score += 0.25
                        reasons.append("与'探索者'自我一致")
                else:
                    if candidate['type'] in ['observe', 'rest']:
                        score += 0.20
                        reasons.append("我还年轻，保持观察")

        # === 3. 目标相关性 (20%) ===
        if goal is not None:
            relevance = goal.evaluate_relevance(candidate)
            score += relevance * 0.20
            if relevance > 0.5:
                reasons.append(f"推进目标'{goal.name}'")

        # === 4. 预期 Φ (20%) ===
        predicted_phi = candidate.get('predicted_phi', 0.3)
        score += predicted_phi * 0.20
        if predicted_phi > 0.5:
            reasons.append("预计带来丰富体验")

        # === 5. 运动效益 (15%) ===
        if candidate.get('movement', False):
            # 移动动作有物理效益
            if affect.arousal > 0.5:
                # 高唤起时倾向运动
                score += 0.15
                reasons.append("高唤起→倾向运动")
            elif affect.arousal < 0.2:
                score -= 0.05
                reasons.append("低唤起→倾向不动")
        else:
            # 非移动动作
            if affect.arousal < 0.3:
                score += 0.10
                reasons.append("低唤起→适合静止动作")

        reasoning = "; ".join(reasons) if reasons else "默认选择"

        return score, reasoning

    def reset(self):
        self.decision_history.clear()
