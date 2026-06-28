"""helios_v3 调研 M4 ship package。

M4 Active Inference Owner (Layer 1) - v3 design §2.2 / task §2.2。

核心组件:
  - HierarchicalGenerativeModel: 5 层简化 generative model
  - proxy_free_energy: 诚实的 proxy,**不是**真 VFE(M8 升级)
  - ActiveInferenceOwner: predict / compute_proxy_free_energy /
                          minimize_proxy_free_energy / active_sampling
  - variational_free_energy_TRUE: NotImplementedError(M8 升级 placeholder)
"""
from .hierarchical_generative_model import (
    HierarchicalGenerativeModel,
    HGM_LAYER_DIMS,
    HGM_LAYER_NAMES,
    DEFAULT_HGM_LR,
)
from .active_inference_owner import (
    ActiveInferenceOwner,
    proxy_free_energy,
    compute_proxy_free_energy,
    ActiveInferenceStats,
    ActionPolicy,
)

__all__ = [
    # Hierarchical Generative Model
    "HierarchicalGenerativeModel",
    "HGM_LAYER_DIMS",
    "HGM_LAYER_NAMES",
    "DEFAULT_HGM_LR",
    # Active Inference Owner
    "ActiveInferenceOwner",
    "proxy_free_energy",
    "compute_proxy_free_energy",
    "ActiveInferenceStats",
    "ActionPolicy",
]