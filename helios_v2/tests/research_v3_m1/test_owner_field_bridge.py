"""M1-T8 OwnerFieldBridge 测试。"""
import pytest
import numpy as np

from helios_v2.research_v3_m1 import SelfModelOwner
from helios_v2.research_v3_m1.owner_field_bridge import (
    OwnerFieldBridge,
    OwnerFieldMapping,
    DEFAULT_MAPPINGS,
    fixture_neutral,
    fixture_high_activation_high_valence,
    fixture_high_threat_high_cortisol,
    fixture_low_energy_fatigue,
)
from helios_v2.research_v3_m1.projections import (
    Hormone9D, Feeling7D, Salience5D,
)
from helios_v2.research_v3_m1.aspect_state import AspectState


class TestOwnerFieldBridgeMapping:
    """映射基础测试。"""

    def test_default_bridge_has_8_mappings(self):
        """默认 bridge 有 8 个映射(对应 CDS 8 维)。"""
        bridge = OwnerFieldBridge.default()
        assert len(bridge.mappings) == 8

    def test_neutral_input_yields_zero(self):
        """所有 v2 字段为 0 → I = 0。"""
        bridge = OwnerFieldBridge.default()
        h, f, s = fixture_neutral()
        I = bridge.bridge_input(h, f, s)
        assert np.allclose(I, 0.0, atol=1e-9)

    def test_output_shape_is_8d(self):
        """输出 shape = (8,)。"""
        bridge = OwnerFieldBridge.default()
        h, f, s = fixture_high_activation_high_valence()
        I = bridge.bridge_input(h, f, s)
        assert I.shape == (8,)

    def test_output_in_valid_range(self):
        """输出每个分量 ∈ [-1, 1]。"""
        bridge = OwnerFieldBridge.default()
        for fix in [fixture_neutral, fixture_high_activation_high_valence,
                    fixture_high_threat_high_cortisol, fixture_low_energy_fatigue]:
            h, f, s = fix()
            I = bridge.bridge_input(h, f, s)
            assert np.all(I >= -1.0) and np.all(I <= 1.0), \
                f"out of range for {fix.__name__}: {I}"


class TestOwnerFieldBridgeSemantics:
    """语义验证:特定输入 → 特定 CDS 维度应该高。"""

    def test_high_positive_yields_high_affective(self):
        """高 DA/NE + 高 valence/arousal → I[affective] 高。"""
        bridge = OwnerFieldBridge.default()
        h, f, s = fixture_high_activation_high_valence()
        I = bridge.bridge_input(h, f, s)
        assert I[2] > 0.7  # affective 应该接近 1

    def test_high_threat_yields_high_ecological(self):
        """高 threat + 高 NE → I[ecological_extended] 高。"""
        bridge = OwnerFieldBridge.default()
        h, f, s = fixture_high_threat_high_cortisol()
        I = bridge.bridge_input(h, f, s)
        assert I[6] > 0.7  # ecological 应该接近 1

    def test_high_cortisol_yields_high_bodily(self):
        """高皮质醇 → I[bodily_processes] 高。"""
        bridge = OwnerFieldBridge.default()
        h, f, s = fixture_high_threat_high_cortisol()
        I = bridge.bridge_input(h, f, s)
        assert I[0] > 0.3  # bodily 应该高

    def test_high_oxytocin_yields_high_intersubjective(self):
        """高 oxytocin + 高 social_safety → I[intersubjective] 高。"""
        bridge = OwnerFieldBridge.default()
        h, f, s = fixture_high_activation_high_valence()
        I = bridge.bridge_input(h, f, s)
        assert I[3] > 0.7  # intersubjective 应该接近 1

    def test_low_energy_yields_low_overall(self):
        """低能量疲劳场景 → I 各分量普遍低(尤其 affective/narrative)。"""
        bridge = OwnerFieldBridge.default()
        h, f, s = fixture_low_energy_fatigue()
        I = bridge.bridge_input(h, f, s)
        assert I[2] < 0.5  # affective 低
        assert I[5] < 0.5  # narrative 低


class TestOwnerFieldBridgeReflect:
    """bridge_reflect 测试(M2 接口预留)。"""

    def test_reflect_shape_is_8d(self):
        """reflect 输出 shape = (8,)。"""
        bridge = OwnerFieldBridge.default()
        aspect = AspectState(
            activation=0.5, valence=0.5, arousal=0.5,
            certainty=0.5, salience=0.5, precision=0.5,
            novelty=0.5, coherence=0.5, stability=0.5, resonance=0.5,
        )
        reflect = bridge.bridge_reflect(aspect)
        assert reflect.shape == (8,)

    def test_reflect_in_valid_range(self):
        """reflect ∈ [-1, 1]。"""
        bridge = OwnerFieldBridge.default()
        aspect = AspectState(
            activation=0.9, valence=-0.9, arousal=0.9,
            certainty=0.1, salience=0.9, precision=0.1,
            novelty=0.9, coherence=0.1, stability=0.1, resonance=0.1,
        )
        reflect = bridge.bridge_reflect(aspect)
        assert np.all(reflect >= -1.0) and np.all(reflect <= 1.0)

    def test_high_arousal_yields_high_bodily_reflect(self):
        """高 arousal → I[bodily] reflect 高。"""
        bridge = OwnerFieldBridge.default()
        aspect = AspectState(
            activation=0.8, valence=0.0, arousal=0.9,
            certainty=0.5, salience=0.5, precision=0.5,
            novelty=0.5, coherence=0.5, stability=0.5, resonance=0.5,
        )
        reflect = bridge.bridge_reflect(aspect)
        assert reflect[0] > 0.3  # bodily 应该高


class TestOwnerFieldBridgeIntegration:
    """OwnerFieldBridge 跟 SelfModelOwner 集成测试。"""

    def test_bridge_drives_self_model_owner(self):
        """bridge 输入 → SelfModelOwner tick 正常工作。"""
        bridge = OwnerFieldBridge.default()
        owner = SelfModelOwner.default()
        h, f, s = fixture_high_activation_high_valence()

        I = bridge.bridge_input(h, f, s)
        result = owner.tick(I=I)

        assert result["solver_success"]
        assert np.all(result["state"] >= -10.0) and np.all(result["state"] <= 10.0)

    def test_100_ticks_with_bridge_stays_stable(self):
        """100 tick 跟 bridge 配合,CDS 稳定。"""
        bridge = OwnerFieldBridge.default()
        owner = SelfModelOwner.default()

        for tick in range(100):
            # 每 tick 选不同 fixture
            fixtures = [fixture_neutral, fixture_high_activation_high_valence,
                       fixture_high_threat_high_cortisol, fixture_low_energy_fatigue]
            fix = fixtures[tick % 4]
            h, f, s = fix()
            I = bridge.bridge_input(h, f, s)
            result = owner.tick(I=I)

            assert result["solver_success"], f"solver failed at tick {tick}"
            assert not np.any(np.isnan(result["state"])), f"NaN at tick {tick}"
            assert 0.0 <= result["kuramoto_R"] <= 1.0

    def test_bridge_output_deterministic(self):
        """相同输入 → 相同 I(确定性)。"""
        bridge = OwnerFieldBridge.default()
        h, f, s = fixture_high_activation_high_valence()

        I1 = bridge.bridge_input(h, f, s)
        I2 = bridge.bridge_input(h, f, s)
        assert np.allclose(I1, I2)

    def test_different_mappings_produce_different_output(self):
        """不同 mappings 权重 → 不同 I。"""
        h, f, s = fixture_high_activation_high_valence()

        bridge_default = OwnerFieldBridge.default()
        I_default = bridge_default.bridge_input(h, f, s)

        # 自定义映射:全部 weight = 0
        zero_mappings = tuple(
            OwnerFieldMapping() for _ in range(8)
        )
        bridge_zero = OwnerFieldBridge.with_mappings(zero_mappings)
        I_zero = bridge_zero.bridge_input(h, f, s)

        assert not np.allclose(I_default, I_zero)
        assert np.allclose(I_zero, 0.0)


class TestOwnerFieldMapping:
    """OwnerFieldMapping 单元测试。"""

    def test_default_mapping_construction(self):
        """默认 OwnerFieldMapping 是合法的。"""
        m = OwnerFieldMapping()
        assert m.bias == 0.0
        assert m.scale == 1.0
        assert m.hormone_keys == {}

    def test_8_default_mappings_are_distinct(self):
        """默认 8 个 mapping 不完全相同(每个 CDS 维度有专属权重)。"""
        for i in range(8):
            for j in range(i + 1, 8):
                mi = DEFAULT_MAPPINGS[i]
                mj = DEFAULT_MAPPINGS[j]
                # 至少一个字段权重不同
                all_keys = set(mi.hormone_keys) | set(mi.feeling_keys) | set(mi.salience_keys) | \
                           set(mj.hormone_keys) | set(mj.feeling_keys) | set(mj.salience_keys)
                differs = False
                for k in all_keys:
                    wi = (mi.hormone_keys.get(k, 0) +
                          mi.feeling_keys.get(k, 0) +
                          mi.salience_keys.get(k, 0))
                    wj = (mj.hormone_keys.get(k, 0) +
                          mj.feeling_keys.get(k, 0) +
                          mj.salience_keys.get(k, 0))
                    if abs(wi - wj) > 1e-9:
                        differs = True
                        break
                assert differs, f"mapping {i} and {j} are identical"


class TestOwnerFieldBridgeDescribe:
    """describe_mapping 可读性测试。"""

    def test_describe_returns_8_lines(self):
        """describe_mapping 输出 9 行(标题 + 8 个维度)。"""
        bridge = OwnerFieldBridge.default()
        desc = bridge.describe_mapping()
        lines = desc.strip().split("\n")
        assert len(lines) == 9  # 1 标题 + 8 维度

    def test_describe_includes_all_dimension_names(self):
        """describe 包含所有 8 个 PTS_DIMENSION_NAMES。"""
        from helios_v2.research_v3_m1.cds import PTS_DIMENSION_NAMES
        bridge = OwnerFieldBridge.default()
        desc = bridge.describe_mapping()
        for name in PTS_DIMENSION_NAMES:
            assert name in desc