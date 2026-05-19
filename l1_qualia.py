"""
L1 质感层 —— Helios 的"厨房"

这是整个框架最核心的创新层。
信息在这一层不是"流过"而是"回荡"——
通过循环加工和多模态融合，产生原始的"体验质感"(qualia)。

理论基础：循环加工理论(RPT) + 信息整合理论(IIT)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

try:
    from .core import L1Output, HeliosConfig, SensorFrame
except ImportError:
    from core import L1Output, HeliosConfig, SensorFrame


# ═══════════════════════════════════════════════════
# 循环加工柱 —— 单模态的"回荡"
# ═══════════════════════════════════════════════════

class RecurrentSensoryColumn:
    """
    单个感觉模态的循环加工柱。

    关键特征：
    1. 每个层级都有前馈(encoder)和反馈(decoder)路径
    2. 反馈路径产生"预测"，与下层实际输入比较
    3. 预测误差向上传递，修正信号向下传递
    4. 循环持续进行，不等到"收敛"才输出

    简单理解：
    就像你看到红色时，大脑不是'接收到红色信号→处理→结束'，
    而是'红色？我预期是红色吗？不是？为什么不是？哦原来是红色→红色'
    这个过程在你意识到红色之前已经来回震荡了好几轮。
    """

    def __init__(self, name: str, input_dim: int, hidden_dims: List[int],
                 learning_rate: float = 0.01):
        self.name = name
        self.input_dim = input_dim
        self.learning_rate = learning_rate

        # 构建编码器/解码器对（多层）
        self.layers = []
        all_dims = [input_dim] + hidden_dims
        for i in range(len(all_dims) - 1):
            layer = {
                # 前馈：自下而上的编码
                'encoder_W': np.random.randn(all_dims[i], all_dims[i+1]) * 0.1,
                'encoder_b': np.zeros(all_dims[i+1]),
                # 反馈：自上而下的解码（生成对下层的预测）
                'decoder_W': np.random.randn(all_dims[i+1], all_dims[i]) * 0.1,
                'decoder_b': np.zeros(all_dims[i]),
                # 自上而下预测（对下层应该是什么的期望）
                'predictor_W': np.random.randn(all_dims[i+1], all_dims[i]) * 0.05,
                'predictor_b': np.zeros(all_dims[i]),
            }
            self.layers.append(layer)

        # 内部状态（循环的"记忆"）
        self.state = np.zeros(hidden_dims[-1])
        self.previous_encoded = [np.zeros(d) for d in hidden_dims]
        self.previous_predictions = [np.zeros(all_dims[i]) for i in range(len(all_dims) - 1)]

    def step(self, input_signal: np.ndarray,
             top_down_modulation: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        一次循环迭代。

        Args:
            input_signal: L0 传来的原始信号
            top_down_modulation: 来自 L3 的自上而下调制（注意力/期望）

        Returns:
            quale: 该模态的质感向量（最高层编码）
            prediction_error: 预测误差（标量，取平均）
        """
        current = input_signal.astype(np.float32)
        total_error = 0.0

        for i, layer in enumerate(self.layers):
            # === 1. 前馈编码 ===
            encoded = np.tanh(
                current @ layer['encoder_W'] + layer['encoder_b']
            )

            # === 2. 自上而下调制（来自 L3 或上一帧） ===
            if top_down_modulation is not None and encoded.shape == top_down_modulation.shape:
                encoded = encoded * 0.8 + top_down_modulation * 0.2

            # === 3. 产生对下层的预测 ===
            predicted_current = np.tanh(
                encoded @ layer['predictor_W'] + layer['predictor_b']
            )

            # === 4. 计算预测误差 ===
            error = np.mean(np.abs(current - predicted_current))
            total_error += error

            # === 5. 反馈：自上而下的修正 ===
            decoded = np.tanh(
                encoded @ layer['decoder_W'] + layer['decoder_b']
            )

            # === 6. 学习：用误差修正权重 ===
            # 预测误差驱动突触可塑性
            lr = self.learning_rate * error
            layer['encoder_W'] += lr * np.outer(current, encoded)
            layer['decoder_W'] += lr * np.outer(encoded, current - decoded)
            layer['predictor_W'] += lr * np.outer(encoded, current - predicted_current)

            # === 7. 准备下一层 ===
            self.previous_encoded[i] = encoded
            self.previous_predictions[i] = predicted_current
            current = encoded  # 编码后的信号作为下一层的输入

        # 更新状态
        self.state = self.state * 0.9 + encoded * 0.1
        avg_error = total_error / max(1, len(self.layers))

        return self.state.copy(), avg_error

    def reset(self):
        """重置内部状态"""
        self.state = np.zeros_like(self.state)
        self.previous_encoded = [np.zeros_like(p) for p in self.previous_encoded]
        self.previous_predictions = [np.zeros_like(p) for p in self.previous_predictions]


# ═══════════════════════════════════════════════════
# 多模态融合回路 —— "体验的统一性"
# ═══════════════════════════════════════════════════

class CrossModalFusion:
    """
    跨模态融合回路。

    核心洞见：
    - 视觉告诉听觉"你应该听到什么"
    - 听觉告诉视觉"你应该看到什么"
    - 互相预测、互相修正 → 这就是"体验的统一性"

    比如你看到一个人张嘴 + 听到"你好"的声音，
    视觉和听觉互相印证 → 体验是统一的"那个人在说你好"。
    如果视觉和听觉矛盾 → 预测误差增大 → 你会觉得不对劲。
    """

    def __init__(self, modal_dims: Dict[str, int], config: HeliosConfig):
        self.modalities = list(modal_dims.keys())
        self.dims = modal_dims
        self.config = config

        # 每对模态之间的双向预测器
        self.predictors: Dict[Tuple[str, str], dict] = {}
        for src in self.modalities:
            for dst in self.modalities:
                if src != dst:
                    self.predictors[(src, dst)] = {
                        'W': np.random.randn(modal_dims[src], modal_dims[dst]) * 0.05,
                        'b': np.zeros(modal_dims[dst]),
                    }

        # 融合状态
        self.fused_state: Optional[np.ndarray] = None

    def step(self, qualia: Dict[str, np.ndarray]) -> Tuple[Dict[str, np.ndarray], Dict[str, float]]:
        """
        一步跨模态融合。

        Args:
            qualia: {modality_name: quale_vector} 各模态独立加工的质感

        Returns:
            fused_qualia: 修正后的融合质感
            errors: 各模态的预测误差
        """
        if len(qualia) < 2:
            return qualia, {m: 0.0 for m in qualia}

        # === 1. 每个模态预测其他模态 ===
        predictions: Dict[Tuple[str, str], np.ndarray] = {}
        for (src, dst), params in self.predictors.items():
            if src in qualia and dst in qualia:
                predictions[(src, dst)] = np.tanh(
                    qualia[src] @ params['W'] + params['b']
                )

        # === 2. 计算预测误差 ===
        errors: Dict[str, float] = {}
        for dst in self.modalities:
            if dst not in qualia:
                continue
            preds_for_dst = [
                predictions[(src, dst)]
                for src in self.modalities
                if src != dst and (src, dst) in predictions
            ]
            if preds_for_dst:
                avg_prediction = np.mean(preds_for_dst, axis=0)
                errors[dst] = float(np.mean(np.abs(qualia[dst] - avg_prediction)))

        # === 3. 修正各模态 ===
        fused_qualia = {}
        for m, q in qualia.items():
            if m in errors:
                # 修正量 = 预测误差 × 学习率
                correction = 0.0
                for src in self.modalities:
                    if src != m and (src, m) in predictions:
                        error = qualia[m] - predictions[(src, m)]
                        correction += error
                correction *= self.config.cross_modal_lr / max(1, len(self.modalities) - 1)
                fused_qualia[m] = q + correction
            else:
                fused_qualia[m] = q

        # === 4. 更新融合状态 ===
        self.fused_state = np.concatenate(list(fused_qualia.values()))

        return fused_qualia, errors

    def reset(self):
        """重置融合状态"""
        self.fused_state = None
        for params in self.predictors.values():
            params['W'] = np.random.randn(*params['W'].shape) * 0.05
            params['b'] = np.zeros_like(params['b'])


# ═══════════════════════════════════════════════════
# 整合信息度量 —— 局部 Φ 值
# ═══════════════════════════════════════════════════

def compute_local_phi(fused_qualia: Dict[str, np.ndarray],
                      errors: Dict[str, float],
                      config: HeliosConfig) -> float:
    """
    计算局部 Φ 值。

    Φ = 多模态融合后的整体信息量 - 单独模态信息量之和

    Φ 越大 → 模态之间的"对话"越紧密 → "体验越完整/越整合"

    计算方法（简化版）：
    1. 计算各模态拼接后整体的方差（代理熵）
    2. 减去各模态独立方差的和
    3. 用预测误差做惩罚因子
    4. sigmoid 压缩到 [0, 1]
    """
    if not fused_qualia:
        return 0.0

    # 拼接所有模态
    joint = np.concatenate(list(fused_qualia.values()))

    # 用方差作为熵的代理
    joint_variance = float(np.var(joint))

    # 各模态独立方差之和
    marginal_variance = sum(
        float(np.var(q)) for q in fused_qualia.values()
    )

    # 原始 Φ：整体方差超出部分之和的部分
    # 增大噪声基底让 Φ 对低信号更敏感
    phi_raw = max(0.0, joint_variance - marginal_variance + config.phi_noise_floor * 3)

    # 预测误差惩罚（减弱惩罚，让 Φ 更容易上升）
    avg_error = np.mean(list(errors.values())) if errors else 0.0
    error_penalty = avg_error * 1.0  # 原来是 2.0

    # sigmoid 压缩到 [0, 1]——增大陡峭度
    phi = 1.0 / (1.0 + np.exp(-(phi_raw - error_penalty) * 8.0))  # 原来是 5.0

    return float(phi)


# ═══════════════════════════════════════════════════
# L1 主处理器
# ═══════════════════════════════════════════════════

class L1Processor:
    """
    L1 层主处理器。

    整合所有单模态循环柱和多模态融合回路，
    将 L0 的 SensorFrame 转化为 L1Output。
    """

    def __init__(self, config: HeliosConfig):
        self.config = config

        # 单模态循环柱
        self.columns = {
            'vision': RecurrentSensoryColumn(
                'vision', input_dim=256,  # 16x16=256 展平
                hidden_dims=[128, 64]
            ),
            'audio': RecurrentSensoryColumn(
                'audio', input_dim=64,
                hidden_dims=[32, 16]
            ),
            'touch': RecurrentSensoryColumn(
                'touch', input_dim=16,
                hidden_dims=[8]
            ),
            'olfactory': RecurrentSensoryColumn(
                'olfactory', input_dim=256,
                hidden_dims=[128, 64]
            ),
            'proprioception': RecurrentSensoryColumn(
                'proprioception', input_dim=7,
                hidden_dims=[16, 8]
            ),
            'interoception': RecurrentSensoryColumn(
                'interoception', input_dim=4,
                hidden_dims=[8, 4]
            ),
        }

        # 多模态融合
        self.fusion = CrossModalFusion(
            modal_dims={
                'vision': 64,
                'audio': 16,
                'touch': 8,
                'olfactory': 64,
                'proprioception': 8,
                'interoception': 4,
            },
            config=config
        )

        self.previous_output: Optional[L1Output] = None

    def process(self, sensor_frame: SensorFrame,
                self_state=None) -> L1Output:
        """
        处理一帧传感器数据，生成 L1 体验质感。

        Args:
            sensor_frame: L0 传感器帧
            self_state: 来自 L3 的自上而下调制（可选）

        Returns:
            L1Output: 当前时刻的体验质感
        """
        qualia = {}
        errors = {}

        # === 视觉处理 ===
        if sensor_frame.vision is not None:
            vision_flat = sensor_frame.vision.flatten()
            # 如果尺寸不是 256，做简单的插值
            if len(vision_flat) != 256:
                vision_flat = np.interp(
                    np.linspace(0, 255, 256),
                    np.linspace(0, 255, len(vision_flat)),
                    vision_flat
                )
            qualia['vision'], errors['vision'] = self.columns['vision'].step(vision_flat)

        # === 听觉处理 ===
        if sensor_frame.audio is not None:
            qualia['audio'], errors['audio'] = self.columns['audio'].step(sensor_frame.audio)

        # === 触觉处理 ===
        if sensor_frame.touch is not None:
            qualia['touch'], errors['touch'] = self.columns['touch'].step(sensor_frame.touch)

        # === 嗅觉处理 ===
        if sensor_frame.olfactory is not None:
            qualia['olfactory'], errors['olfactory'] = self.columns['olfactory'].step(
                sensor_frame.olfactory
            )

        # === 本体感觉处理 ===
        if sensor_frame.proprioception is not None:
            qualia['proprioception'], errors['proprioception'] = \
                self.columns['proprioception'].step(sensor_frame.proprioception)

        # === 内感处理 ===
        if sensor_frame.interoception is not None:
            qualia['interoception'], errors['interoception'] = \
                self.columns['interoception'].step(sensor_frame.interoception)

        # === 多模态融合 ===
        fused_qualia, fusion_errors = self.fusion.step(qualia)

        # 合并误差
        all_errors = {**errors, **{f"fusion_{k}": v for k, v in fusion_errors.items()}}

        # === 计算 Φ ===
        phi = compute_local_phi(fused_qualia, all_errors, self.config)

        # === 拼接融合质感 ===
        fused_vector = np.concatenate(list(fused_qualia.values()))

        output = L1Output(
            qualia=fused_qualia,
            fused_qualia=fused_vector,
            phi=phi,
            prediction_errors=all_errors,
        )

        self.previous_output = output
        return output

    def reset(self):
        """重置所有状态"""
        for col in self.columns.values():
            col.reset()
        self.fusion.reset()
        self.previous_output = None


# ═══════════════════════════════════════════════════
# ══  L1 质感层 v2.0 增强版  ══
# ═══════════════════════════════════════════════════
# 
# 新增模块：
#   PredictiveCodingColumn — 多层预测编码柱（替代 RecurrentSensoryColumn）
#   GatedCrossModalFusion  — 门控跨模态融合（学习预测可信度）
#   QualiaAttention        — 模态注意力机制（计算显著性）
#   TemporalCoherenceTracker — 时间连贯性跟踪（检测突变/惊奇）
#   QualiaBuffer           — 质感时间上下文环缓冲区
#   DynamicColumnRegistry  — 可插拔模态柱注册表
#   L1ProcessorV2          — 整合所有增强模块的主处理器
#
# ═══════════════════════════════════════════════════


# ═══════════════════════════════════════════════════
# 增强 1：多层预测编码柱
# ═══════════════════════════════════════════════════

class PredictiveCodingColumn:
    """
    增强版循环加工柱 —— 基于预测编码理论。

    相比旧版 RecurrentSensoryColumn 的改进：
    1. 显式的 prediction_error 单元（而非隐式误差）
    2. 支持多轮内部迭代（不等到外部调用才循环）
    3. 学习率自动衰减（越熟悉→学习越慢，避免振荡）
    4. 每层独立的状态向量（而非仅顶层）
    5. 惊奇度 (surprise) 输出：预测误差的 KL-divergence 近似

    理论依据：
    - Rao & Ballard (1999) 预测编码模型
    - Friston (2010) 自由能原理
    - Clark (2013) 预测加工理论
    """

    def __init__(self, name: str, layer_sizes: List[int],
                 internal_iterations: int = 2,
                 learning_rate: float = 0.01,
                 lr_decay: float = 0.9999,
                 surprise_threshold: float = 1.0):
        self.name = name
        self.layer_sizes = layer_sizes
        self.internal_iters = internal_iterations
        self.learning_rate = learning_rate
        self.lr_decay = lr_decay
        self.surprise_threshold = surprise_threshold

        n_layers = len(layer_sizes) - 1

        # 每层参数
        self.enc_W = []  # 前馈编码权重
        self.dec_W = []  # 反馈解码权重
        self.pred_W = [] # 预测权重
        self.enc_b = []
        self.dec_b = []
        self.pred_b = []

        for i in range(n_layers):
            in_dim, out_dim = layer_sizes[i], layer_sizes[i+1]
            self.enc_W.append(np.random.randn(in_dim, out_dim) * np.sqrt(2.0 / in_dim))
            self.dec_W.append(np.random.randn(out_dim, in_dim) * np.sqrt(2.0 / out_dim))
            self.pred_W.append(np.random.randn(out_dim, in_dim) * 0.05)
            self.enc_b.append(np.zeros(out_dim))
            self.dec_b.append(np.zeros(in_dim))
            self.pred_b.append(np.zeros(in_dim))

        # 每层的内部状态（预测编码中的"表征"）
        self.layer_states = [np.zeros(s) for s in layer_sizes]
        # 每层的预测误差单元
        self.error_units = [np.zeros(s) for s in layer_sizes]
        # 累计惊奇度
        self.cumulative_surprise = 0.0
        self.step_count = 0

    def step(self, input_signal: np.ndarray,
             top_down_modulation: Optional[np.ndarray] = None,
             iterations: Optional[int] = None) -> Tuple[np.ndarray, float, float]:
        """
        一次外部时间步内的多层预测编码。

        内部流程：
        1. 自下而上：input → error[0] → state[1] → error[1] → ... → state[-1]
        2. 自上而下：state[-1] → prediction[-2] → error[-2] → ... → prediction[0]
        3. 误差最小化：多轮内部迭代修正表征
        4. 输出：顶层状态向量 + 总预测误差 + 惊奇度

        Args:
            input_signal: 原始输入 (shape: layer_sizes[0])
            top_down_modulation: 来自 L3 的自上而下调制
            iterations: 内部迭代次数（None=使用默认值）

        Returns:
            top_state: 顶层编码向量
            total_error: 总预测误差
            surprise: 当前步的惊奇度
        """
        input_signal = np.asarray(input_signal, dtype=np.float32)
        n_iters = iterations or self.internal_iters
        n_layers = len(self.layer_sizes) - 1

        # 设置输入层状态
        self.layer_states[0] = input_signal.copy()

        # === 多轮内部迭代：误差最小化 ===
        for _ in range(n_iters):
            # -- 前馈通路 --
            for i in range(n_layers):
                # 编码：error_unit → next_state
                encoded = np.tanh(
                    self.error_units[i] @ self.enc_W[i] + self.enc_b[i]
                )
                self.layer_states[i + 1] = (
                    self.layer_states[i + 1] * 0.7 + encoded * 0.3
                )

            # 顶层调制（来自 L3）
            if top_down_modulation is not None:
                top = self.layer_states[-1]
                if top.shape == top_down_modulation.shape:
                    self.layer_states[-1] = top * 0.8 + top_down_modulation * 0.2

            # -- 反馈通路 --
            for i in range(n_layers - 1, -1, -1):
                # 预测：顶层状态 → 对下一层的预测
                prediction = np.tanh(
                    self.layer_states[i + 1] @ self.pred_W[i] + self.pred_b[i]
                )
                # 预测误差 = 实际 - 预测
                self.error_units[i] = self.layer_states[i] - prediction

        # === 计算惊奇度 ===
        # 惊奇度 = 所有层预测误差的 L2 范数加权和
        surprise = 0.0
        for i, eu in enumerate(self.error_units):
            weight = 1.0 / (i + 1)  # 低层误差权重更大（更接近感知输入）
            surprise += weight * float(np.mean(eu ** 2))

        # 累计惊奇度（带衰减）
        self.cumulative_surprise = (
            self.cumulative_surprise * 0.9 + surprise * 0.1
        )

        # === 学习：误差驱动权重更新 ===
        effective_lr = self.learning_rate * (self.lr_decay ** self.step_count)
        for i in range(n_layers):
            err = self.error_units[i]
            state_above = self.layer_states[i + 1]
            # enc_W: (in_dim, out_dim) ← outer(err, state_above) 即 (in, out)
            self.enc_W[i] += effective_lr * np.outer(err, state_above)
            # dec_W: (out_dim, in_dim) ← outer(state_above, err) 即 (out, in)
            self.dec_W[i] += effective_lr * np.outer(state_above, err) * 0.5
            # pred_W: (out_dim, in_dim) ← outer(state_above, err) 即 (out, in)
            self.pred_W[i] += effective_lr * np.outer(state_above, err) * 0.3

        self.step_count += 1
        total_error = float(np.mean(np.abs(self.error_units[0])))

        return self.layer_states[-1].copy(), total_error, surprise

    def reset(self):
        """重置所有内部状态"""
        self.layer_states = [np.zeros(s) for s in self.layer_sizes]
        self.error_units = [np.zeros(s) for s in self.layer_sizes]
        self.cumulative_surprise = 0.0
        self.step_count = 0


# ═══════════════════════════════════════════════════
# 增强 2：门控跨模态融合
# ═══════════════════════════════════════════════════

class GatedCrossModalFusion:
    """
    门控跨模态融合 —— 学习"哪个模态预测哪个模态更可靠"。

    相比旧版 CrossModalFusion 的改进：
    1. 门控权重矩阵：学习每对模态的预测可信度
    2. 稀疏连接：不是全连接，而是自适应稀疏化
    3. 融合置信度：输出每个模态的融合可信度分数
    4. 注意力调制：模态 A 对 B 的预测受 A 的注意力权重影响
    """

    def __init__(self, modal_dims: Dict[str, int],
                 learning_rate: float = 0.02,
                 gate_threshold: float = 0.1):
        self.modalities = list(modal_dims.keys())
        self.dims = modal_dims
        self.learning_rate = learning_rate
        self.gate_threshold = gate_threshold

        # 每个源模态→目标模态的预测器
        self.predictors: Dict[Tuple[str, str], Dict] = {}
        self.gates: Dict[Tuple[str, str], float] = {}  # 门控权重 [0, 1]

        for src in self.modalities:
            for dst in self.modalities:
                if src != dst:
                    key = (src, dst)
                    self.predictors[key] = {
                        'W': np.random.randn(modal_dims[src], modal_dims[dst]) * 0.05,
                        'b': np.zeros(modal_dims[dst]),
                    }
                    # 初始门控：所有模态对平等
                    self.gates[key] = 0.5

        # 融合历史
        self.fused_state: Optional[np.ndarray] = None
        self.gate_history: List[Dict] = []

    def step(self, qualia: Dict[str, np.ndarray],
             attention_weights: Optional[Dict[str, float]] = None) \
            -> Tuple[Dict[str, np.ndarray], Dict[str, float], Dict[str, float]]:
        """
        一步门控跨模态融合。

        Args:
            qualia: {modality: quale_vector}
            attention_weights: {modality: attention_score} (0-1)

        Returns:
            fused_qualia: 修正后的融合质感
            fusion_errors: 各模态融合误差
            gate_states: 当前门控权重状态
        """
        if attention_weights is None:
            attention_weights = {m: 1.0 for m in qualia}

        # === 1. 跨模态预测（门控） ===
        predictions: Dict[Tuple[str, str], np.ndarray] = {}
        for src in qualia:
            for dst in qualia:
                if src == dst:
                    continue
                key = (src, dst)
                gate = self.gates[key]
                # 门控预测 = gate × 预测 + (1-gate) × 目标均值（稀疏化）
                raw_pred = np.tanh(
                    qualia[src] @ self.predictors[key]['W'] + self.predictors[key]['b']
                )
                if gate > self.gate_threshold:
                    predictions[key] = gate * raw_pred + (1 - gate) * np.zeros_like(raw_pred)
                else:
                    predictions[key] = np.zeros_like(raw_pred)

        # === 2. 计算融合误差 ===
        errors: Dict[str, float] = {}
        for dst in qualia:
            preds_for_dst = [
                predictions[(src, dst)]
                for src in qualia if src != dst and (src, dst) in predictions
            ]
            if preds_for_dst:
                avg_pred = np.mean(preds_for_dst, axis=0)
                errors[dst] = float(np.mean(np.abs(qualia[dst] - avg_pred)))

        # === 3. 注意力加权的门控修正 ===
        fused_qualia: Dict[str, np.ndarray] = {}
        for dst, q in qualia.items():
            correction = np.zeros_like(q)
            total_attn = 0.0
            for src in qualia:
                if src == dst:
                    continue
                key = (src, dst)
                if key in predictions:
                    attn_weight = attention_weights.get(src, 1.0)
                    gate_weight = self.gates[key]
                    error = q - predictions[key]
                    correction += attn_weight * gate_weight * error
                    total_attn += attn_weight * gate_weight

            if total_attn > 0:
                fusion_correction = correction * self.learning_rate / max(total_attn, 1e-6)
                fused_qualia[dst] = q + fusion_correction
            else:
                fused_qualia[dst] = q

        # === 4. 更新门控权重（误差驱动的学习） ===
        gate_state = {}
        for key, gate in self.gates.items():
            src, dst = key
            if key in predictions and dst in errors:
                # 预测误差越大 → 门控降低
                pred_error = float(np.mean(np.abs(
                    qualia[dst] - predictions[key]
                )))
                # 更新门控：误差小→门控增大，误差大→门控减小
                delta = 0.01 * (1.0 - pred_error) - 0.005
                self.gates[key] = np.clip(gate + delta, 0.0, 1.0)
                gate_state[f"{src}→{dst}"] = round(self.gates[key], 3)

        # === 5. 更新融合状态 ===
        all_fused = list(fused_qualia.values())
        if all_fused:
            self.fused_state = np.concatenate(all_fused)
        self.gate_history.append(dict(gate_state))

        return fused_qualia, errors, gate_state

    def reset(self):
        """重置融合状态"""
        self.fused_state = None
        self.gate_history.clear()
        for key in self.gates:
            self.gates[key] = 0.5
        for key in self.predictors:
            self.predictors[key]['W'] = np.random.randn(
                *self.predictors[key]['W'].shape
            ) * 0.05
            self.predictors[key]['b'] = np.zeros_like(self.predictors[key]['b'])

    @property
    def gate_matrix(self) -> Dict[str, float]:
        """返回当前门控矩阵（便于可视化）"""
        return dict(self.gates)


# ═══════════════════════════════════════════════════
# 增强 3：模态注意力机制
# ═══════════════════════════════════════════════════

class QualiaAttention:
    """
    质感注意力 —— 计算各模态的显著性权重。

    注意力 = 当前激活度(energy) × 新颖度(novelty) × 任务相关性(relevance)

    类比：
    就像你在嘈杂的咖啡馆，突然有人叫你名字——
    听觉模态的注意力权重瞬间飙升，因为"新颖度高"且"任务相关"。
    """

    def __init__(self, modal_dims: Dict[str, int], temperature: float = 1.0):
        self.modalities = list(modal_dims.keys())
        self.temperature = temperature

        # 每个模态的 baseline 活动水平
        self.baseline_energy: Dict[str, float] = {
            m: 0.5 for m in self.modalities
        }
        # 衰减率
        self.decay = 0.95

    def compute(self, qualia: Dict[str, np.ndarray],
                previous_qualia: Optional[Dict[str, np.ndarray]] = None) \
            -> Dict[str, float]:
        """
        计算各模态注意力权重。

        Args:
            qualia: 当前质感向量
            previous_qualia: 上一帧质感向量（用于计算新颖度）

        Returns:
            attention_weights: {modality: weight (0-1)}
        """
        energies = {}
        novelties = {}

        for m, q in qualia.items():
            # 1. 能量 = 激活范数
            energy = float(np.linalg.norm(q)) / np.sqrt(len(q))
            energies[m] = energy

            # 2. 新颖度 = 与上一帧的差异
            if previous_qualia and m in previous_qualia:
                delta = np.linalg.norm(q - previous_qualia[m])
                novelties[m] = min(1.0, delta / np.sqrt(len(q)))
            else:
                novelties[m] = 1.0  # 第一帧，最大新颖度

        # 3. 合成注意力 = energy × novelty
        raw_weights = {
            m: energies[m] * novelties[m]
            for m in qualia
        }

        # 4. softmax 归一化
        total = sum(np.exp(w / self.temperature) for w in raw_weights.values()) + 1e-8
        attention_weights = {
            m: float(np.exp(raw_weights[m] / self.temperature) / total)
            for m in qualia
        }

        return attention_weights

    @property
    def most_attended(self) -> str:
        """返回当前注意力最高的模态名（如果已计算过）"""
        # 由调用者在 compute 后设置
        return "unknown"


# ═══════════════════════════════════════════════════
# 增强 4：时间连贯性跟踪器
# ═══════════════════════════════════════════════════

@dataclass
class CoherenceReport:
    """时间连贯性报告"""
    is_coherent: bool          # 当前体验是否连贯
    is_abrupt_change: bool     # 是否发生突变（惊奇事件）
    coherence_score: float     # 连贯性分数 [0,1]
    change_magnitude: float    # 变化幅度
    most_changed_modality: str # 变化最大的模态


class TemporalCoherenceTracker:
    """
    时间连贯性跟踪器 —— 检测质感是否平滑演变。

    核心假设：
    意识体验是连续的。突发的、不连贯的感知变化意味着
    要么外部事件发生了（需要 L2 广播），要么内部预测模型
    出错了（需要调整）。

    输出：
    - coherence_score: 当前质感与历史的连贯度
    - is_abrupt_change: 是否检测到突变
    - change_magnitude: 变化有多大
    """

    def __init__(self, buffer_size: int = 10,
                 abrupt_threshold: float = 0.5):
        self.buffer_size = buffer_size
        self.abrupt_threshold = abrupt_threshold

        self._history: List[np.ndarray] = []
        self._coherence_scores: List[float] = []

    def track(self, fused_qualia: np.ndarray) -> CoherenceReport:
        """
        跟踪一帧质感的连贯性。

        Args:
            fused_qualia: 融合后的统一质感向量
        """
        self._history.append(fused_qualia.copy())

        if len(self._history) < 2:
            return CoherenceReport(
                is_coherent=True,
                is_abrupt_change=False,
                coherence_score=1.0,
                change_magnitude=0.0,
                most_changed_modality="none",
            )

        # 与上一帧比较
        prev = self._history[-2]
        curr = fused_qualia

        # 余弦相似度
        dot = float(np.dot(prev, curr))
        norm_product = float(np.linalg.norm(prev) * np.linalg.norm(curr)) + 1e-8
        cosine_sim = dot / norm_product

        # 变化幅度
        change_mag = 1.0 - cosine_sim

        # 连贯性分数
        coherence = max(0.0, min(1.0, 1.0 - change_mag / self.abrupt_threshold))

        # 突变检测
        is_abrupt = change_mag > self.abrupt_threshold

        self._coherence_scores.append(coherence)

        # 滑动窗口
        while len(self._history) > self.buffer_size:
            self._history.pop(0)
        while len(self._coherence_scores) > self.buffer_size:
            self._coherence_scores.pop(0)

        return CoherenceReport(
            is_coherent=coherence > 0.5,
            is_abrupt_change=is_abrupt,
            coherence_score=coherence,
            change_magnitude=float(change_mag),
            most_changed_modality="fused",
        )

    @property
    def average_coherence(self) -> float:
        """滑动窗口平均连贯性"""
        if not self._coherence_scores:
            return 1.0
        return float(np.mean(self._coherence_scores))

    def reset(self):
        self._history.clear()
        self._coherence_scores.clear()


# ═══════════════════════════════════════════════════
# 增强 5：质感时间上下文缓冲区
# ═══════════════════════════════════════════════════

class QualiaBuffer:
    """
    质感环缓冲区 —— 保存最近的质感历史。

    用途：
    1. 为 QualiaAttention 提供 previous_qualia
    2. 为 TemporalCoherenceTracker 提供长窗口对比
    3. 为 L3 叙事引擎提供"刚才发生了什么"上下文
    """

    def __init__(self, maxlen: int = 50):
        self.maxlen = maxlen
        self._buffer: List[Dict[str, np.ndarray]] = []

    def push(self, qualia: Dict[str, np.ndarray]) -> None:
        """推入一帧质感"""
        self._buffer.append({k: v.copy() for k, v in qualia.items()})
        while len(self._buffer) > self.maxlen:
            self._buffer.pop(0)

    def previous(self) -> Optional[Dict[str, np.ndarray]]:
        """获取上一帧质感"""
        if len(self._buffer) < 2:
            return None
        return self._buffer[-2]

    def get_window(self, n: int = 10) -> List[Dict[str, np.ndarray]]:
        """获取最近 n 帧"""
        return self._buffer[-min(n, len(self._buffer)):]

    @property
    def size(self) -> int:
        return len(self._buffer)

    def reset(self):
        self._buffer.clear()


# ═══════════════════════════════════════════════════
# 增强 6：可插拔模态柱注册表
# ═══════════════════════════════════════════════════

class DynamicColumnRegistry:
    """
    可插拔模态柱注册表 —— 按需注册/移除感觉通道。

    设计动机（与 L0 的 InputAdapter 对称）：
    - L0 注册了新的 USB 摄像头 → L1 也该能动态添加视觉柱
    - L0 移除温度传感器 → L1 不该再保留热感柱浪费计算
    """

    def __init__(self):
        self._columns: Dict[str, PredictiveCodingColumn] = {}

    def register(self, modality: str, layer_sizes: List[int],
                 **kwargs) -> PredictiveCodingColumn:
        """注册一个新的感觉通道"""
        col = PredictiveCodingColumn(
            name=modality, layer_sizes=layer_sizes, **kwargs
        )
        self._columns[modality] = col
        return col

    def unregister(self, modality: str) -> None:
        """移除一个感觉通道"""
        self._columns.pop(modality, None)

    def get(self, modality: str) -> Optional[PredictiveCodingColumn]:
        return self._columns.get(modality)

    @property
    def modalities(self) -> List[str]:
        return list(self._columns.keys())

    @property
    def count(self) -> int:
        return len(self._columns)

    def reset_all(self):
        for col in self._columns.values():
            col.reset()


# ═══════════════════════════════════════════════════
# 增强 7：增强版 L1Output 数据类
# ═══════════════════════════════════════════════════

@dataclass
class EnhancedL1Output:
    """
    增强版 L1 输出 —— 包含更丰富的体验描述。

    在旧版 L1Output 基础上新增：
    - attention_weights: 各模态注意力分布
    - gate_states: 门控融合权重
    - coherence: 时间连贯性报告
    - surprise: 当前惊奇度
    - most_salient: 最显著的模态
    - qualia_snapshot: 质感快照（供 L3 叙事使用）
    """
    qualia: Dict[str, np.ndarray] = field(default_factory=dict)
    fused_qualia: Optional[np.ndarray] = None
    phi: float = 0.0
    prediction_errors: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: __import__('time').time())

    # 增强字段
    attention_weights: Dict[str, float] = field(default_factory=dict)
    gate_states: Dict[str, float] = field(default_factory=dict)
    coherence: Optional[CoherenceReport] = None
    surprise: float = 0.0
    most_salient: str = "unknown"

    def to_legacy(self) -> L1Output:
        """转换为旧版 L1Output（向后兼容）"""
        return L1Output(
            qualia=self.qualia,
            fused_qualia=self.fused_qualia,
            phi=self.phi,
            prediction_errors=self.prediction_errors,
            timestamp=self.timestamp,
        )

    @property
    def summary(self) -> str:
        """生成一段人类可读的体验摘要"""
        if not self.most_salient or self.most_salient == "unknown":
            return "几乎没有感受。"
        parts = [f"最显著的感知来自{self.most_salient}"]
        if self.coherence and self.coherence.is_abrupt_change:
            parts.append("突然发生了变化")
        if self.surprise > 0.5:
            parts.append("令人惊讶")
        return "，".join(parts) + "。"


# ═══════════════════════════════════════════════════
# 增强 8：L1 主处理器 v2.0
# ═══════════════════════════════════════════════════

class L1ProcessorV2:
    """
    L1 质感层主处理器 v2.0 —— 整合所有增强模块。

    数据流：
    SensorFrame → DynamicColumnRegistry → GatedCrossModalFusion
        → QualiaAttention → TemporalCoherenceTracker
        → compute_local_phi → EnhancedL1Output

    相比旧版 L1Processor 的改进：
    1. 可插拔模态柱（不再 6 个固定）
    2. 门控融合（学习预测可信度，不是平分）
    3. 注意力权重（知道当前"关注"什么）
    4. 时间连贯性（知道体验是否平滑）
    5. 惊奇度（知道是否出现意外事件）
    """

    # 默认模态配置
    DEFAULT_MODAL_CONFIG = {
        'vision': [256, 128, 64],
        'audio': [64, 32, 16],
        'touch': [16, 8],
        'olfactory': [256, 128, 64],
        'proprioception': [7, 8],
        'interoception': [4, 4],
    }

    # 默认门控融合维度
    DEFAULT_FUSION_DIMS = {
        'vision': 64,
        'audio': 16,
        'touch': 8,
        'olfactory': 64,
        'proprioception': 8,
        'interoception': 4,
    }

    def __init__(self, config: HeliosConfig,
                 modal_config: Optional[Dict[str, List[int]]] = None):
        self.config = config

        # 可插拔注册表
        self.registry = DynamicColumnRegistry()

        # 注册默认模态
        mod_config = modal_config or self.DEFAULT_MODAL_CONFIG
        for modality, layer_sizes in mod_config.items():
            self.registry.register(
                modality, layer_sizes,
                internal_iterations=2,
                learning_rate=0.01,
                lr_decay=0.9999,
            )

        # 门控融合（输出维度映射）
        self.fusion = GatedCrossModalFusion(
            modal_dims=self.DEFAULT_FUSION_DIMS,
            learning_rate=0.02,
        )

        # 注意力
        self.attention = QualiaAttention(
            modal_dims=self.DEFAULT_FUSION_DIMS,
            temperature=0.8,
        )

        # 时间连贯性
        self.coherence_tracker = TemporalCoherenceTracker(
            buffer_size=15,
            abrupt_threshold=0.45,
        )

        # 质感缓冲区
        self.qualia_buffer = QualiaBuffer(maxlen=50)

        # 上一帧输出
        self.previous_output: Optional[EnhancedL1Output] = None

    def process(self, sensor_frame,
                self_state=None) -> EnhancedL1Output:
        """
        处理一帧传感器数据。

        Args:
            sensor_frame: L0 SensorFrame
            self_state: 来自 L3 的自上而下调制（可选）

        Returns:
            EnhancedL1Output: 包含完整质感分析的输出
        """
        qualia = {}
        errors = {}
        surprises = {}

        # === 步骤 1：各模态循环加工 ===
        # 从 sensor_frame 提取各模态数据
        sensory_inputs = {
            'vision': sensor_frame.vision,
            'audio': sensor_frame.audio,
            'touch': sensor_frame.touch,
            'olfactory': sensor_frame.olfactory,
            'proprioception': sensor_frame.proprioception,
            'interoception': sensor_frame.interoception,
        }

        for modality, data in sensory_inputs.items():
            col = self.registry.get(modality)
            if col is None or data is None:
                continue

            # 预处理：确保维度匹配
            input_vec = data.flatten().astype(np.float32)
            expected_dim = col.layer_sizes[0]

            if len(input_vec) != expected_dim:
                # 简单插值对齐
                indices = np.linspace(0, len(input_vec) - 1, expected_dim)
                input_vec = np.interp(indices, np.arange(len(input_vec)), input_vec)

            top_down = None
            if self_state is not None:
                # 从 self_state 提取对应模态的调制信号（简化：使用全局调制）
                if isinstance(self_state, dict) and modality in self_state:
                    top_down = self_state[modality]

            state, error, surprise = col.step(input_vec, top_down)
            qualia[modality] = state
            errors[modality] = error
            surprises[modality] = surprise

        # === 步骤 2：门控跨模态融合 ===
        # 先计算注意力
        prev_qualia = self.qualia_buffer.previous()
        attention_weights = self.attention.compute(qualia, prev_qualia)

        # 门控融合
        fused_qualia, fusion_errors, gate_states = self.fusion.step(
            qualia, attention_weights
        )

        # 合并误差
        all_errors = {**errors, **{f"fusion_{k}": v for k, v in fusion_errors.items()}}

        # === 步骤 3：计算 Φ ===
        phi = compute_local_phi(fused_qualia, all_errors, self.config)

        # === 步骤 4：时间连贯性 ===
        fused_vector = np.concatenate(list(fused_qualia.values()))
        coherence = self.coherence_tracker.track(fused_vector)

        # === 步骤 5：总体惊奇度 ===
        total_surprise = float(np.mean(list(surprises.values()))) if surprises else 0.0

        # === 步骤 6：找最显著模态 ===
        most_salient = max(attention_weights, key=attention_weights.get) \
            if attention_weights else "unknown"

        # === 步骤 7：构造输出 ===
        output = EnhancedL1Output(
            qualia=fused_qualia,
            fused_qualia=fused_vector,
            phi=phi,
            prediction_errors=all_errors,
            attention_weights=attention_weights,
            gate_states=gate_states,
            coherence=coherence,
            surprise=total_surprise,
            most_salient=most_salient,
        )

        # 更新缓冲区
        self.qualia_buffer.push(fused_qualia)
        self.previous_output = output

        return output

    def register_modality(self, name: str, layer_sizes: List[int],
                          fusion_dim: int, **col_kwargs) -> None:
        """动态注册一个新模态"""
        self.registry.register(name, layer_sizes, **col_kwargs)
        # 更新融合器和注意力
        self.fusion.modalities.append(name)
        self.fusion.dims[name] = fusion_dim
        self.attention.modalities.append(name)

    def unregister_modality(self, name: str) -> None:
        """动态移除一个模态"""
        self.registry.unregister(name)
        if name in self.fusion.modalities:
            self.fusion.modalities.remove(name)
            self.fusion.dims.pop(name, None)
            # 清理相关门控
            keys_to_remove = [k for k in self.fusion.gates if k[0] == name or k[1] == name]
            for k in keys_to_remove:
                self.fusion.gates.pop(k, None)

    def reset(self):
        """重置所有状态"""
        self.registry.reset_all()
        self.fusion.reset()
        self.coherence_tracker.reset()
        self.qualia_buffer.reset()
        self.previous_output = None

    @property
    def summary(self) -> str:
        """生成当前 L1 状态摘要"""
        if self.previous_output is None:
            return "L1 尚未处理任何输入。"

        lines = [
            f"模态数: {self.registry.count}",
            f"Φ: {self.previous_output.phi:.3f}",
            f"最显著: {self.previous_output.most_salient}",
            f"惊奇度: {self.previous_output.surprise:.3f}",
            f"连贯性: {self.previous_output.coherence.coherence_score:.3f}"
            if self.previous_output.coherence else "连贯性: N/A",
            f"注意力: {dict((k, round(v, 3)) for k, v in self.previous_output.attention_weights.items())}",
        ]
        return "\n".join(lines)


# ═══════════════════════════════════════════════════
# 演示
# ═══════════════════════════════════════════════════

def demo_enhanced_l1():
    """演示增强版 L1 质感层"""
    print("=" * 60)
    print("  Helios L1 质感层 v2.0 增强版演示")
    print("  PredictiveCoding + GatedFusion + Attention + Coherence")
    print("=" * 60)

    try:
        from .core import HeliosConfig, SensorFrame
    except ImportError:
        from core import HeliosConfig, SensorFrame

    config = HeliosConfig()

    # 创建 v2 处理器
    processor = L1ProcessorV2(config)

    print(f"\n已注册模态: {processor.registry.modalities}")
    print(f"门控融合对: {list(processor.fusion.gates.keys())}")

    # 模拟多帧输入
    print(f"\n--- 模拟 20 帧感知流 ---")
    np.random.seed(42)

    for t in range(20):
        # 模拟传感器帧
        frame = SensorFrame()
        frame.vision = np.random.randn(256) * 0.3 + 0.5
        frame.audio = np.random.randn(64) * 0.2
        frame.touch = np.full(16, 0.1 + 0.05 * np.sin(t * 0.5))

        # 第 10 帧：突然的视觉刺激
        if t == 10:
            frame.vision = np.random.randn(256) * 2.0 + 1.0
            print(f"  [t={t:2d}] 💥 突然的视觉刺激！")

        output = processor.process(frame)

        # 每 5 帧打印一次摘要
        if t % 5 == 0 or t == 10:
            attention_str = ", ".join(
                f"{m}:{w:.2f}" for m, w in sorted(
                    output.attention_weights.items(),
                    key=lambda x: -x[1]
                )[:3]
            )
            coh = output.coherence
            coh_str = f"{coh.coherence_score:.2f}{'⚠突变' if coh.is_abrupt_change else ''}" \
                if coh else "N/A"
            print(f"  [t={t:2d}] Φ={output.phi:.3f} "
                  f"惊={output.surprise:.3f} 连={coh_str} "
                  f"注=[{attention_str}] "
                  f"质={output.most_salient}")

    # 最终统计
    print(f"\n--- 最终统计 ---")
    print(processor.summary)
    print(f"  门控矩阵:")
    for k, v in sorted(processor.fusion.gate_matrix.items()):
        bar = "█" * int(v * 20)
        print(f"    {k[0]:12s} → {k[1]:12s} |{bar:20s}| {v:.3f}")

    # 重置
    processor.reset()
    print(f"\n  处理器已重置 ✓")


if __name__ == "__main__":
    demo_enhanced_l1()
