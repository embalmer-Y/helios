"""R-PROTO-LEARN.P-TEMPORAL — RealRPEConfig P5 surface tests.

小黑 2026-06-20 拍板: 选项 A 解冻 RealRPEConfig + update_*_weights methods
+ p5_parameter_mapping + apply_p5_policy override. Sum-to-1.0 invariant
preserved via renormalize-then-validate path.
"""

from helios_v2.rpe.contracts import RealRPEConfig


def test_realrpeconfig_unfrozen():
    """RealRPEConfig is no longer frozen; fields can be reassigned."""
    cfg = RealRPEConfig()
    cfg.w_success = 0.5  # would raise FrozenInstanceError pre-P-TEMPORAL
    assert cfg.w_success == 0.5


def test_update_dopamine_weights_renormalizes():
    cfg = RealRPEConfig()
    cfg.update_dopamine_weights(0.85, 0.42, 0.13)
    s = cfg.w_success + cfg.w_response_accepted + cfg.w_latency
    assert abs(s - 1.0) < 1e-4
    # 0.85 was largest -> should dominate
    assert cfg.w_success > 0.5


def test_update_dopamine_weights_all_zero_fallback():
    cfg = RealRPEConfig()
    cfg.update_dopamine_weights(0.0, 0.0, 0.0)
    # Fallback to (1/3, 1/3, 1/3) when all-zero
    assert abs(cfg.w_success - 1/3) < 1e-4
    assert abs(cfg.w_response_accepted - 1/3) < 1e-4
    assert abs(cfg.w_latency - 1/3) < 1e-4


def test_update_ne_weights_renormalizes():
    cfg = RealRPEConfig()
    cfg.update_ne_weights(0.2, 0.7, 0.1)
    s = cfg.w_ne_executed + cfg.w_ne_failure + cfg.w_ne_latency
    assert abs(s - 1.0) < 1e-4
    # 0.7 was largest -> NE failure dominant
    assert cfg.w_ne_failure > 0.4


def test_update_ser_weights_pair_renormalize():
    cfg = RealRPEConfig()
    cfg.update_ser_weights(0.3, 0.6)
    s = cfg.w_ser_alignment + cfg.w_ser_consecutive
    assert abs(s - 1.0) < 1e-4
    assert cfg.w_ser_consecutive > cfg.w_ser_alignment


def test_update_cor_weights_renormalizes():
    cfg = RealRPEConfig()
    cfg.update_cor_weights(0.1, 0.8, 0.1)
    s = cfg.w_cor_unresolved + cfg.w_cor_candidate + cfg.w_cor_suppressed
    assert abs(s - 1.0) < 1e-4
    assert cfg.w_cor_candidate > 0.5


def test_update_reward_shaping_clipped():
    cfg = RealRPEConfig()
    cfg.update_reward_shaping(success_value=2.0, failure_value=-2.0)
    # Clipped to [-1, 1]
    assert cfg.success_value == 1.0
    assert cfg.failure_value == -1.0


def test_update_reward_shaping_int_clamped():
    cfg = RealRPEConfig()
    cfg.update_reward_shaping(latency_max_ticks=-5)
    assert cfg.latency_max_ticks == 1  # max(1, -5) = 1


def test_apply_p5_policy_full_18_dim():
    cfg = RealRPEConfig()
    class FakeSnap:
        policy_output = (0.85, 0.42, 0.13, 0.6, 0.3, 0.1, 0.7, 0.3, 0.6, 0.3, 0.1,
                         0.9, 0.1, 0.8, 0.2, 0.1, 0.2, 0.1)
    cfg.apply_p5_policy(FakeSnap())
    # All 4 weight triples should sum to ~1.0
    assert abs(cfg.w_success + cfg.w_response_accepted + cfg.w_latency - 1.0) < 1e-4
    assert abs(cfg.w_ne_executed + cfg.w_ne_failure + cfg.w_ne_latency - 1.0) < 1e-4
    assert abs(cfg.w_ser_alignment + cfg.w_ser_consecutive - 1.0) < 1e-4
    assert abs(cfg.w_cor_unresolved + cfg.w_cor_candidate + cfg.w_cor_suppressed - 1.0) < 1e-4
    # Reward shaping signed mapping (2*out-1 for [-1, 1])
    assert abs(cfg.success_value - 0.8) < 1e-4  # 2*0.9-1
    assert cfg.latency_max_ticks == 10  # round(0.1*100)


def test_p5_parameter_mapping_classvar():
    cfg = RealRPEConfig()
    assert "w_success" in cfg.p5_parameter_mapping
    assert cfg.p5_parameter_mapping["w_success"] == "dopamine"
    assert cfg.p5_parameter_mapping["w_ne_executed"] == "norepinephrine"
    assert cfg.p5_parameter_mapping["w_ser_alignment"] == "serotonin"
    assert cfg.p5_parameter_mapping["w_cor_unresolved"] == "cortisol"


def test_sum_to_one_invariant_preserved_under_repeated_update():
    cfg = RealRPEConfig()
    for i in range(20):
        cfg.update_dopamine_weights(
            0.3 + 0.5 * (i % 3),
            0.4 - 0.1 * (i % 5),
            0.5 + 0.2 * (i % 2),
        )
        s = cfg.w_success + cfg.w_response_accepted + cfg.w_latency
        assert abs(s - 1.0) < 1e-4, f"invariant broken at iter {i}"


def test_initial_construction_unchanged():
    """Backwards compat: RealRPEConfig() with no args gives same defaults as before."""
    cfg = RealRPEConfig()
    assert cfg.w_success == 0.4
    assert cfg.w_response_accepted == 0.3
    assert cfg.w_latency == 0.3
    assert cfg.success_value == 1.0
    assert cfg.failure_value == -0.3
    assert cfg.accepted_value == 0.8
    assert cfg.rejected_value == -0.5