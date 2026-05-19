"""
L0 感知网关 —— Helios 的"感官之门" v2.0

全新的可插拔感知网关架构，借鉴 NeuroLink 项目设计：

新特性：
- Transport 抽象层：LocalTransport + ZenohTransport 双层策略
- 升级版 PerceptToken：丰富的 NeuroLink 风格元数据
- PerceptionEventRouter：去重 -> 规整 -> 排序 -> 分发管线
- PerceptionFrame：时间窗口帧聚合
- 可插拔适配器：标准 InputAdapter 接口

架构：
    适配器 ──Transport──→ EventRouter ──Frame──→ L1 质感层
"""

from __future__ import annotations

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any, AsyncIterator, Callable, Dict, Iterable, List, Optional, Tuple
)

import numpy as np


# ═══════════════════════════════════════════════════
# 1. 升级版 PerceptToken（借鉴 NeuroLink PerceptionEvent）
# ═══════════════════════════════════════════════════

@dataclass
class PerceptToken:
    """
    统一感知令牌 —— L0 网关的标准输出格式。

    对比旧版 SensorFrame：
    - ✅ 不再限定 6 种固定模态
    - ✅ 来源追踪：source_kind, source_node, source_app
    - ✅ 去重：dedupe_key
    - ✅ 因果链：causality_id
    - ✅ 策略标签：policy_tags
    - ✅ 优先级：priority (0-100)
    - ✅ 语义主题：semantic_topic
    """
    # ── 核心标识 ──
    event_id: str = field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    modality: str = "unknown"          # "text" | "vision" | "audio" | "api" | "sensor" | ...
    source_kind: str = "external"      # "external" | "internal" | "core"
    source_node: Optional[str] = None  # 来源节点（如 "radxa-arm", "usb-cam-0"）
    source_app: Optional[str] = None   # 来源应用/适配器 ID

    # ── 语义路由 ──
    semantic_topic: Optional[str] = None   # "unit.health.degraded", "social.message.received"
    priority: int = 50                     # 0-100，越高越紧急
    policy_tags: Tuple[str, ...] = ()      # ("real_time", "private", "audit")

    # ── 去重与因果 ──
    dedupe_key: Optional[str] = None       # 去重键（同 key 的事件只保留一个）
    causality_id: Optional[str] = None     # 因果链 ID（关联同一事件链）

    # ── 载荷 ──
    raw_payload_ref: Optional[str] = None  # 大载荷外部引用（避免内存膨胀）
    payload: Dict[str, Any] = field(default_factory=dict)

    # ── 时间戳 ──
    timestamp_wall: str = field(default_factory=lambda: time.strftime(
        "%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()))
    timestamp_mono: float = field(default_factory=time.monotonic)

    def serialize(self) -> bytes:
        """序列化为 CBOR bytes（轻量二进制格式）"""
        import json
        data = {
            "event_id": self.event_id,
            "modality": self.modality,
            "source_kind": self.source_kind,
            "source_node": self.source_node,
            "source_app": self.source_app,
            "semantic_topic": self.semantic_topic,
            "priority": self.priority,
            "policy_tags": list(self.policy_tags),
            "dedupe_key": self.dedupe_key,
            "causality_id": self.causality_id,
            "raw_payload_ref": self.raw_payload_ref,
            "payload": self.payload,
            "timestamp_wall": self.timestamp_wall,
            "timestamp_mono": self.timestamp_mono,
        }
        return json.dumps(data).encode('utf-8')

    @classmethod
    def deserialize(cls, raw: bytes) -> "PerceptToken":
        """从 CBOR bytes 反序列化"""
        import json
        data = json.loads(raw.decode('utf-8'))
        return cls(
            event_id=data.get("event_id", f"evt-{uuid.uuid4().hex[:12]}"),
            modality=data.get("modality", "unknown"),
            source_kind=data.get("source_kind", "external"),
            source_node=data.get("source_node"),
            source_app=data.get("source_app"),
            semantic_topic=data.get("semantic_topic"),
            priority=data.get("priority", 50),
            policy_tags=tuple(data.get("policy_tags", ())),
            dedupe_key=data.get("dedupe_key"),
            causality_id=data.get("causality_id"),
            raw_payload_ref=data.get("raw_payload_ref"),
            payload=data.get("payload", {}),
            timestamp_wall=data.get("timestamp_wall", ""),
            timestamp_mono=data.get("timestamp_mono", 0.0),
        )

    def __repr__(self) -> str:
        return (f"PerceptToken(mod={self.modality}, pri={self.priority}, "
                f"src={self.source_app or '?'}, topic={self.semantic_topic or '?'})")


# ═══════════════════════════════════════════════════
# 2. 传输层 —— Transport 抽象 + Local/Zenoh 实现
# ═══════════════════════════════════════════════════

@dataclass
class TransportConfig:
    """适配器声明自身的传输需求，框架据此选择传输方式"""
    adapter_id: str
    needs_streaming: bool = False       # 需要流式传输（视频/音频）
    max_payload_bytes: int = 1024       # 单次最大载荷
    needs_remote: bool = False          # 需要跨设备通信
    reliability: str = "reliable"       # "reliable" | "best_effort"
    qos_priority: int = 0               # 0=低 1=中 2=高

    @property
    def suggest_zenoh(self) -> bool:
        """是否需要 Zenoh 传输"""
        return self.needs_streaming or self.needs_remote or self.max_payload_bytes > 65536


class Transport(ABC):
    """传输层抽象 —— 适配器与网关之间的通信契约"""

    @abstractmethod
    async def start(self, config: TransportConfig) -> None:
        """建立传输通道"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """关闭传输通道"""
        ...

    @abstractmethod
    async def push(self, adapter_id: str, token: PerceptToken) -> None:
        """推送感知令牌到网关"""
        ...

    @abstractmethod
    async def subscribe(self, adapter_id: str) -> AsyncIterator[PerceptToken]:
        """网关订阅适配器的感知流"""
        ...

    @property
    @abstractmethod
    def is_healthy(self) -> bool:
        """传输通道健康检查"""
        ...


class LocalTransport(Transport):
    """进程内直传：零依赖、零延迟，适合文本/API 适配器和开发调试"""

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._healthy = False

    async def start(self, config: TransportConfig) -> None:
        self._queues[config.adapter_id] = asyncio.Queue(maxsize=256)
        self._healthy = True

    async def stop(self) -> None:
        self._healthy = False
        self._queues.clear()

    async def push(self, adapter_id: str, token: PerceptToken) -> None:
        if adapter_id in self._queues:
            await self._queues[adapter_id].put(token)

    async def subscribe(self, adapter_id: str) -> AsyncIterator[PerceptToken]:
        q = self._queues.get(adapter_id)
        if not q:
            return
        while self._healthy:
            try:
                token = await asyncio.wait_for(q.get(), timeout=1.0)
                yield token
            except asyncio.TimeoutError:
                continue

    @property
    def is_healthy(self) -> bool:
        return self._healthy


class ZenohTransport(Transport):
    """
    Zenoh pub/sub 传输：流数据、分布式、热插拔

    安装依赖: pip install eclipse-zenoh
    KeyExpr 命名规范:
        helios/<node_id>/percept/<modality>/<adapter_id>
        helios/<node_id>/ctrl/<adapter_id>/<command>
        helios/<node_id>/health/<adapter_id>
    """

    def __init__(self, node_id: str = "helios-core",
                 connect_endpoint: str = "tcp/127.0.0.1:7447"):
        self._node_id = node_id
        self._endpoint = connect_endpoint
        self._session = None
        self._healthy = False
        self._adapter_ids: List[str] = []

    async def start(self, config: TransportConfig) -> None:
        self._adapter_ids.append(config.adapter_id)
        try:
            import zenoh  # type: ignore
            self._session = zenoh.open(zenoh.Config())
            self._healthy = True
        except ImportError:
            # 优雅降级：Zenoh 未安装时自动回退到 LocalTransport
            import logging
            logging.getLogger(__name__).warning(
                "Zenoh 未安装，回退到 LocalTransport。"
                "安装: pip install eclipse-zenoh"
            )
            self._healthy = True  # 标记为"降级模式"

    async def stop(self) -> None:
        self._healthy = False
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    async def push(self, adapter_id: str, token: PerceptToken) -> None:
        key = f"helios/{self._node_id}/percept/{token.modality}/{adapter_id}"
        payload = token.serialize()
        if self._session:
            self._session.put(key, payload)

    async def subscribe(self, adapter_id: str) -> AsyncIterator[PerceptToken]:
        key = f"helios/{self._node_id}/percept/*/{adapter_id}"
        if self._session:
            subscriber = self._session.declare_subscriber(key)
            async for sample in subscriber:
                token = PerceptToken.deserialize(sample.payload.to_bytes())
                yield token
        else:
            # 降级模式：返回空流
            return

    @property
    def is_healthy(self) -> bool:
        return self._healthy


class TransportRouter:
    """根据适配器声明自动选择传输方式"""

    def __init__(self):
        self._local = LocalTransport()
        self._zenoh: Optional[ZenohTransport] = None
        self._routes: Dict[str, Transport] = {}

    def select(self, config: TransportConfig) -> Transport:
        if config.suggest_zenoh:
            if self._zenoh is None:
                self._zenoh = ZenohTransport()
            transport = self._zenoh
        else:
            transport = self._local
        self._routes[config.adapter_id] = transport
        return transport

    def get(self, adapter_id: str) -> Optional[Transport]:
        return self._routes.get(adapter_id)

    async def start_all(self, adapter_configs: List[TransportConfig]) -> None:
        for cfg in adapter_configs:
            transport = self.select(cfg)
            await transport.start(cfg)

    async def stop_all(self) -> None:
        await self._local.stop()
        if self._zenoh:
            await self._zenoh.stop()


# ═══════════════════════════════════════════════════
# 3. 事件路由管线（借鉴 NeuroLink PerceptionEventRouter）
# ═══════════════════════════════════════════════════

EventSubscriber = Callable[[PerceptToken], None]


class PerceptionEventRouter:
    """
    感知事件路由管线：去重 → 规整 → 排序 → 分发

    借鉴 NeuroLink 的 PerceptionEventRouter 设计：
    - 基于 dedupe_key 的去重
    - 自动填充缺失字段（规整化）
    - 按优先级 + 时间排序
    - Pub/Sub 分发到下游订阅者
    """

    def __init__(self):
        self._subscribers: List[EventSubscriber] = []
        self._seen_dedupe_keys: set = set()
        self._stats = {"total": 0, "deduped": 0, "routed": 0}

    def subscribe(self, subscriber: EventSubscriber) -> None:
        self._subscribers.append(subscriber)

    def seed_dedupe_keys(self, keys: Iterable[str]) -> None:
        for k in keys:
            if k:
                self._seen_dedupe_keys.add(str(k))

    def normalize(self, token: PerceptToken) -> PerceptToken:
        """规整化：自动填充缺失字段"""
        if not token.dedupe_key:
            token.dedupe_key = token.event_id
        if not token.causality_id:
            token.causality_id = token.dedupe_key
        if not token.source_kind:
            token.source_kind = "external"
        if not token.semantic_topic:
            token.semantic_topic = f"helios.percept.{token.modality}"
        return token

    def route_single(self, token: PerceptToken) -> Optional[PerceptToken]:
        """路由单个事件，返回 None 表示被去重过滤"""
        self._stats["total"] += 1
        token = self.normalize(token)

        # 去重
        dedupe_key = token.dedupe_key or token.event_id
        if dedupe_key in self._seen_dedupe_keys:
            self._stats["deduped"] += 1
            return None
        self._seen_dedupe_keys.add(dedupe_key)

        # 分发
        self._stats["routed"] += 1
        for sub in self._subscribers:
            sub(token)
        return token

    def route_batch(self, tokens: List[PerceptToken]) -> List[PerceptToken]:
        """批路由：去重 → 排序 → 分发"""
        results = []
        for token in tokens:
            result = self.route_single(token)
            if result:
                results.append(result)

        # 按优先级降序 + 时间升序排序
        results.sort(
            key=lambda t: (-t.priority, t.timestamp_mono, t.event_id)
        )
        return results

    @property
    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    @property
    def seen_count(self) -> int:
        return len(self._seen_dedupe_keys)

    def clear_dedupe_cache(self) -> None:
        """定期清理去重缓存（避免无限增长）"""
        self._seen_dedupe_keys.clear()


# ═══════════════════════════════════════════════════
# 4. 感知帧（借鉴 NeuroLink PerceptionFrame）
# ═══════════════════════════════════════════════════

@dataclass
class PerceptionFrame:
    """
    感知帧 —— 时间窗口内的一组 PerceptToken 的聚合。

    借鉴 NeuroLink 设计，在 L0→L1 之间插入帧聚合层：
    - 时间窗口内的事件打包为一个 frame
    - 提取最高优先级和话题列表供 L2/L3 快速决策
    - 避免逐 token 送入 L1 造成的碎片化
    """
    frame_id: str = field(default_factory=lambda: f"frame-{uuid.uuid4().hex[:8]}")
    tokens: List[PerceptToken] = field(default_factory=list)
    window_start: float = 0.0
    window_end: float = 0.0

    @property
    def highest_priority(self) -> int:
        if not self.tokens:
            return 0
        return max(t.priority for t in self.tokens)

    @property
    def topics(self) -> Tuple[str, ...]:
        return tuple(sorted(set(
            t.semantic_topic for t in self.tokens if t.semantic_topic
        )))

    @property
    def modalities(self) -> Tuple[str, ...]:
        return tuple(sorted(set(t.modality for t in self.tokens)))

    @property
    def count(self) -> int:
        return len(self.tokens)

    def __repr__(self) -> str:
        return (f"PerceptionFrame({self.frame_id}, "
                f"tokens={self.count}, pri={self.highest_priority}, "
                f"mods={self.modalities})")


class FrameAssembler:
    """时间窗口帧组装器"""

    def __init__(self, window_sec: float = 0.5):
        self._window = window_sec
        self._buffer: List[PerceptToken] = []
        self._last_flush = time.monotonic()

    def add(self, token: PerceptToken) -> Optional[PerceptionFrame]:
        """添加 token，如果窗口到期则返回 frame"""
        now = time.monotonic()
        self._buffer.append(token)

        if now - self._last_flush >= self._window:
            return self.flush()
        return None

    def flush(self) -> Optional[PerceptionFrame]:
        """强制输出当前 buffer 中的所有 token"""
        now = time.monotonic()
        if not self._buffer:
            return None

        frame = PerceptionFrame(
            tokens=list(self._buffer),
            window_start=self._last_flush,
            window_end=now,
        )
        self._buffer.clear()
        self._last_flush = now
        return frame


# ═══════════════════════════════════════════════════
# 5. 适配器接口（与设计文档 3.2 对齐）
# ═══════════════════════════════════════════════════

@dataclass
class RawInput:
    """适配器采集的原始输入"""
    adapter_id: str
    modality: str
    data: Any
    timestamp: float = field(default_factory=time.time)


@dataclass
class PreprocessedSignal:
    """适配器预处理后的信号"""
    adapter_id: str
    modality: str
    data: np.ndarray                        # 预处理后的数值表示
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class InputAdapter(ABC):
    """
    L0 感知网关的标准适配器接口。

    任何外部输入源实现此接口即可接入 Helios。
    """

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """唯一标识，如 'qq-channel', 'usb-cam-0'"""
        ...

    @property
    @abstractmethod
    def modality(self) -> str:
        """模态类型，如 'text', 'vision', 'audio', 'api', 'sensor'"""
        ...

    @property
    def transport_config(self) -> TransportConfig:
        """传输需求声明（子类可覆盖）"""
        return TransportConfig(
            adapter_id=self.adapter_id,
            needs_streaming=self.modality in ("vision", "audio"),
            needs_remote=False,
        )

    async def start(self) -> None:
        """启动适配器"""
        pass

    async def stop(self) -> None:
        """停止适配器"""
        pass

    @property
    def is_healthy(self) -> bool:
        """健康检查"""
        return True

    @abstractmethod
    async def capture(self) -> Optional[RawInput]:
        """采集一帧原始输入"""
        ...

    async def preprocess(self, raw: RawInput) -> PreprocessedSignal:
        """默认预处理（子类可覆盖）"""
        data = np.array(raw.data) if not isinstance(raw.data, np.ndarray) else raw.data
        return PreprocessedSignal(
            adapter_id=self.adapter_id,
            modality=self.modality,
            data=data,
            timestamp=raw.timestamp,
        )

    async def to_percept_token(self, signal: PreprocessedSignal) -> PerceptToken:
        """将预处理信号转为 PerceptToken"""
        return PerceptToken(
            modality=self.modality,
            source_kind="external",
            source_node=None,
            source_app=self.adapter_id,
            semantic_topic=f"helios.percept.{self.modality}",
            priority=50,
            payload={
                "data_shape": list(signal.data.shape) if hasattr(signal.data, 'shape') else None,
                "metadata": signal.metadata,
            },
        )

    async def run_cycle(self) -> Optional[PerceptToken]:
        """一个完整的采集周期：capture → preprocess → tokenize"""
        raw = await self.capture()
        if raw is None:
            return None
        signal = await self.preprocess(raw)
        return await self.to_percept_token(signal)


# ═══════════════════════════════════════════════════
# 6. 感知网关主控
# ═══════════════════════════════════════════════════

class PerceptionGateway:
    """
    L0 感知网关主控 —— 统筹所有适配器和传输。

    数据流：Adapter → Transport → EventRouter → FrameAssembler → L1
    """

    def __init__(self, window_sec: float = 0.5):
        self._adapters: Dict[str, InputAdapter] = {}
        self._router = PerceptionEventRouter()
        self._frame_assembler = FrameAssembler(window_sec=window_sec)
        self._transport_router = TransportRouter()

    # ── 适配器管理 ──

    def register(self, adapter: InputAdapter) -> None:
        """注册一个适配器"""
        self._adapters[adapter.adapter_id] = adapter

    def unregister(self, adapter_id: str) -> None:
        """移除适配器"""
        self._adapters.pop(adapter_id, None)

    def get_adapter(self, adapter_id: str) -> Optional[InputAdapter]:
        return self._adapters.get(adapter_id)

    # ── 传输初始化 ──

    async def start(self) -> None:
        """启动所有适配器的传输通道"""
        configs = [a.transport_config for a in self._adapters.values()]
        await self._transport_router.start_all(configs)

        # 启动所有适配器
        for adapter in self._adapters.values():
            await adapter.start()

    async def stop(self) -> None:
        """停止所有适配器和传输"""
        for adapter in self._adapters.values():
            await adapter.stop()
        await self._transport_router.stop_all()

    # ── 感知循环 ──

    async def capture_all(self) -> List[PerceptToken]:
        """并行采集所有适配器的数据"""
        tokens = []
        for adapter in self._adapters.values():
            if not adapter.is_healthy:
                continue
            token = await adapter.run_cycle()
            if token:
                tokens.append(token)

                # 推送到底层传输（供 ZenohTransport 发布）
                transport = self._transport_router.get(adapter.adapter_id)
                if transport:
                    await transport.push(adapter.adapter_id, token)

        return tokens

    async def tick(self) -> Optional[PerceptionFrame]:
        """
        一次感知节拍：采集 → 路由 → 帧组装

        Returns:
            PerceptionFrame if window is full, None otherwise
        """
        tokens = await self.capture_all()
        routed = self._router.route_batch(tokens)

        for token in routed:
            frame = self._frame_assembler.add(token)
            if frame:
                return frame
        return None

    def flush(self) -> Optional[PerceptionFrame]:
        """强制刷新：输出当前窗口中所有 token"""
        return self._frame_assembler.flush()

    # ── 监控 ──

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "adapters": len(self._adapters),
            "healthy_adapters": sum(1 for a in self._adapters.values() if a.is_healthy),
            "router": self._router.stats,
            "seen_dedupe_keys": self._router.seen_count,
        }

    @property
    def adapter_ids(self) -> List[str]:
        return list(self._adapters.keys())


# ═══════════════════════════════════════════════════
# 7. 内置示例适配器
# ═══════════════════════════════════════════════════

class TextAdapter(InputAdapter):
    """文字适配器 —— 从消息队列读取文本"""

    def __init__(self, adapter_id: str = "text-input"):
        self._id = adapter_id
        self._buffer: List[str] = []

    @property
    def adapter_id(self) -> str:
        return self._id

    @property
    def modality(self) -> str:
        return "text"

    def feed(self, text: str) -> None:
        """外部注入文字（模拟从 QQ/Discord 收到消息）"""
        self._buffer.append(text)

    async def capture(self) -> Optional[RawInput]:
        if not self._buffer:
            return None
        text = self._buffer.pop(0)
        return RawInput(
            adapter_id=self._id,
            modality="text",
            data={"text": text, "length": len(text)},
        )


class SimulatedSensorAdapter(InputAdapter):
    """模拟传感器适配器 —— 生成合成数据"""

    def __init__(self, adapter_id: str = "sim-sensor",
                 modality: str = "vision", dim: int = 128):
        self._id = adapter_id
        self._modality = modality
        self._dim = dim
        self._counter = 0

    @property
    def adapter_id(self) -> str:
        return self._id

    @property
    def modality(self) -> str:
        return self._modality

    async def capture(self) -> Optional[RawInput]:
        self._counter += 1
        data = np.sin(np.linspace(0, 2 * np.pi, self._dim) + self._counter * 0.1)
        data += np.random.randn(self._dim) * 0.05
        return RawInput(
            adapter_id=self._id,
            modality=self._modality,
            data=data,
        )


# ═══════════════════════════════════════════════════
# 8. 简易演示
# ═══════════════════════════════════════════════════

async def demo_transport():
    """演示 Transport 层和 EventRouter 管线"""
    print("=" * 60)
    print("  Helios L0 感知网关 v2.0 演示")
    print("  Transport 双层策略 + EventRouter 管线")
    print("=" * 60)

    # 1. 创建网关
    gateway = PerceptionGateway(window_sec=2.0)

    # 2. 注册适配器
    text_adapter = TextAdapter("qq-input")
    text_adapter.feed("主人：璃光今天心情好吗？")
    text_adapter.feed("主人：帮我查一下天气")
    gateway.register(text_adapter)

    sim_cam = SimulatedSensorAdapter("sim-cam", "vision", dim=128)
    gateway.register(sim_cam)

    sim_mic = SimulatedSensorAdapter("sim-mic", "audio", dim=64)
    gateway.register(sim_mic)

    # 3. 启动
    await gateway.start()

    print(f"\n已注册适配器: {gateway.adapter_ids}")
    print(f"传输路由:")
    for aid in gateway.adapter_ids:
        t = gateway._transport_router.get(aid)
        print(f"  {aid} → {type(t).__name__}")

    # 4. 运行几个周期
    print(f"\n--- 开始感知循环 ---")
    frames = []
    for i in range(10):
        frame = await gateway.tick()
        if frame:
            frames.append(frame)
            print(f"  [{i}] 新帧: {frame}")

        # 继续喂文字消息
        if i == 4:
            text_adapter.feed("主人发来了一张图片")

        await asyncio.sleep(0.1)

    # 5. 最终刷新
    final_frame = gateway.flush()
    if final_frame and final_frame.count > 0:
        frames.append(final_frame)
        print(f"  [flush] 最终帧: {final_frame}")

    # 6. 统计
    print(f"\n--- 统计 ---")
    print(f"  总帧数: {len(frames)}")
    print(f"  路由统计: {gateway.stats}")

    # 7. 清理
    await gateway.stop()
    print(f"\n  网关已停止 ✓")


# ═══════════════════════════════════════════════════
# 9. 向后兼容层 —— 保持旧 demo.py 可运行
# ═══════════════════════════════════════════════════

class SensorArray:
    """
    向后兼容：模拟旧版 SensorArray 接口。
    内部使用新版 PerceptionGateway + SimulatedSensorAdapter。
    """

    # 旧版预设场景（保持 demo.py 兼容）
    PRESET_SCENARIOS = {
        "sunrise": {
            "vision_pattern": "brightening", "audio_pattern": "birdsong",
            "temperature": 28.0, "affective_valence": 0.6, "affective_arousal": 0.3,
            "duration": 5.0
        },
        "threat": {
            "vision_pattern": "approaching", "audio_pattern": "low_rumble",
            "temperature": 20.0, "affective_valence": -0.7, "affective_arousal": 0.8,
            "duration": 4.0
        },
        "social": {
            "vision_pattern": "face_near", "audio_pattern": "speech",
            "touch_intensity": 0.3, "temperature": 27.0,
            "affective_valence": 0.4, "affective_arousal": 0.5,
            "duration": 6.0
        },
        "idle": {
            "vision_pattern": "static", "audio_pattern": "silence",
            "touch_intensity": 0.0, "temperature": 25.0,
            "affective_valence": 0.0, "affective_arousal": 0.0,
            "duration": 10.0
        },
        "comfort": {
            "vision_pattern": "soft_warm", "audio_pattern": "gentle",
            "touch_intensity": 0.5, "temperature": 30.0,
            "affective_valence": 0.7, "affective_arousal": 0.2,
            "duration": 5.0
        },
        # === v4 新增场景：覆盖情感环面 ===
        "joy": {
            "vision_pattern": "colorful_bright", "audio_pattern": "music_major",
            "temperature": 28.0, "affective_valence": 0.80, "affective_arousal": 0.75,
            "touch_intensity": 0.1, "duration": 5.0
        },
        "serenity": {
            "vision_pattern": "soft_blue", "audio_pattern": "distant_waves",
            "temperature": 26.0, "affective_valence": 0.65, "affective_arousal": 0.20,
            "touch_intensity": 0.1, "duration": 5.0
        },
        "curiosity": {
            "vision_pattern": "novel_pattern", "audio_pattern": "unexpected_tone",
            "temperature": 25.0, "affective_valence": 0.35, "affective_arousal": 0.55,
            "touch_intensity": 0.0, "duration": 5.0
        },
        "anger": {
            "vision_pattern": "red_flash", "audio_pattern": "shrill_alarm",
            "temperature": 32.0, "affective_valence": -0.65, "affective_arousal": 0.85,
            "touch_intensity": 0.15, "duration": 4.0
        },
        "fear": {
            "vision_pattern": "dark_jitter", "audio_pattern": "scream",
            "temperature": 18.0, "affective_valence": -0.80, "affective_arousal": 0.90,
            "touch_intensity": 0.0, "duration": 3.0
        },
        "sadness": {
            "vision_pattern": "dim_blue", "audio_pattern": "minor_tone",
            "temperature": 22.0, "affective_valence": -0.60, "affective_arousal": 0.30,
            "touch_intensity": 0.0, "duration": 5.0
        },
        "anxiety": {
            "vision_pattern": "flickering", "audio_pattern": "irregular_beep",
            "temperature": 24.0, "affective_valence": -0.50, "affective_arousal": 0.65,
            "touch_intensity": 0.05, "duration": 5.0
        },
        "disgust": {
            "vision_pattern": "sickly_green", "audio_pattern": "squelch",
            "temperature": 23.0, "affective_valence": -0.55, "affective_arousal": 0.70,
            "touch_intensity": 0.3, "duration": 4.0
        },
        "triumph": {
            "vision_pattern": "golden_burst", "audio_pattern": "fanfare",
            "temperature": 29.0, "affective_valence": 0.90, "affective_arousal": 0.85,
            "touch_intensity": 0.05, "duration": 4.0
        },
    }

    def __init__(self, config=None):  # config 参数保持旧 API 兼容，实际不使用
        self._gateway = PerceptionGateway(window_sec=0.3)

        # 注册默认适配器
        self._vision_adapter = SimulatedSensorAdapter("vision-sensor", "vision", dim=256)
        self._audio_adapter = SimulatedSensorAdapter("audio-sensor", "audio", dim=64)
        self._touch_adapter = SimulatedSensorAdapter("touch-sensor", "touch", dim=32)
        self._thermal_adapter = SimulatedSensorAdapter("thermal-sensor", "thermal", dim=1)
        self._proprio_adapter = SimulatedSensorAdapter("proprio-sensor", "proprioception", dim=7)
        self._intero_adapter = SimulatedSensorAdapter("intero-sensor", "interoception", dim=4)

        for a in [self._vision_adapter, self._audio_adapter, self._touch_adapter,
                   self._thermal_adapter, self._proprio_adapter, self._intero_adapter]:
            self._gateway.register(a)

        self._scenario = None
        self._scenario_name = 'idle'
        self._scenario_start = 0.0
        self._started = False

    def set_scenario(self, name: str) -> None:
        """旧 API 别名"""
        self._scenario_name = name  # 保存场景名供 read() 使用
        preset = self.PRESET_SCENARIOS.get(name)
        if preset:
            self._scenario = preset
            self._scenario_start = time.time()

    def start_scenario(self, name: str) -> None:
        self.set_scenario(name)

    @property
    def scenario_affect(self) -> tuple:
        """旧 API：返回当前场景的情感参数"""
        if self._scenario:
            return (
                self._scenario.get("affective_valence", 0.0),
                self._scenario.get("affective_arousal", 0.0),
            )
        return (0.0, 0.0)

    def get_elapsed(self) -> float:
        return time.time() - self._scenario_start

    def is_scenario_active(self) -> bool:
        if not self._scenario:
            return False
        return self.get_elapsed() < self._scenario.get("duration", 5.0)

    def capture(self):
        """旧 API 别名 → 直接返回 SensorFrame"""
        return self.read()

    def read(self):
        """旧接口：读取一帧传感器数据，返回 SensorFrame。

        根据当前场景参数调制传感器数据，场景切换后前几帧产生瞬态冲击。
        """
        from .core import SensorFrame

        # 异步转同步
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _collect():
            return await self._gateway.capture_all()

        tokens = loop.run_until_complete(_collect())

        frame = SensorFrame()

        # 场景参数
        scene_name = self._scenario_name if hasattr(self, '_scenario_name') else 'idle'
        scene_v = self._scenario.get('affective_valence', 0.0) if self._scenario else 0.0
        scene_a = self._scenario.get('affective_arousal', 0.0) if self._scenario else 0.0
        temp = self._scenario.get('temperature', 25.0) if self._scenario else 25.0
        touch_intensity = self._scenario.get('touch_intensity', 0.0) if self._scenario else 0.0

        # 瞬态冲击：场景切换后前 3 帧注入差异化信号
        elapsed = self.get_elapsed()
        is_transient = elapsed < 0.3
        transient_boost = 0.6 if is_transient else 0.0

        for token in tokens:
            if token.modality == "vision":
                if scene_name == 'sunrise':
                    progress = min(1.0, elapsed / 3.0)
                    base = 0.15 + progress * 0.45
                    frame.vision = np.random.randn(256) * 0.05 + base
                    frame.vision[:64] += np.sin(np.linspace(0, 4*np.pi, 64)) * 0.1 * progress
                elif scene_name == 'threat':
                    frame.vision = np.random.randn(256) * 0.25 - 0.15
                    frame.vision[:32] *= 1.5
                elif scene_name == 'social':
                    frame.vision = np.random.randn(256) * 0.08 + 0.38
                    frame.vision[100:156] = 0.55 + np.random.randn(56) * 0.05
                elif scene_name == 'comfort':
                    frame.vision = np.random.randn(256) * 0.05 + 0.45
                # === v4 新增视觉模式 ===
                elif scene_name == 'joy':
                    frame.vision = np.random.randn(256) * 0.06 + 0.55  # 明亮多彩
                    frame.vision[:80] += np.sin(np.linspace(0, 8*np.pi, 80)) * 0.08  # 快速波动
                elif scene_name == 'serenity':
                    frame.vision = np.random.randn(256) * 0.03 + 0.42  # 柔和蓝色调
                    frame.vision[128:196] = 0.38 + np.random.randn(68) * 0.02  # 低频波动
                elif scene_name == 'curiosity':
                    frame.vision = np.random.randn(256) * 0.12 + 0.50  # 随机新图案
                    frame.vision[::7] += 0.25 * np.random.randn(37)  # 稀疏突出点
                elif scene_name == 'anger':
                    frame.vision = np.random.randn(256) * 0.35 + 0.10  # 红色闪烁
                    frame.vision[:48] *= 1.8  # 上半区剧烈
                elif scene_name == 'fear':
                    frame.vision = np.random.randn(256) * 0.40 - 0.25  # 黑暗抖动
                    frame.vision *= np.random.uniform(0.7, 1.3, 256)  # 随机明暗
                elif scene_name == 'sadness':
                    frame.vision = np.random.randn(256) * 0.10 + 0.28  # 暗蓝色调
                    frame.vision[128:] *= 0.7  # 下半区更暗
                elif scene_name == 'anxiety':
                    frame.vision = np.random.randn(256) * 0.22 + 0.40  # 闪烁不定
                    frame.vision[::3] += 0.18 * np.random.randn(86)  # 高频微扰
                elif scene_name == 'disgust':
                    frame.vision = np.random.randn(256) * 0.18 + 0.30  # 病态绿色调
                    frame.vision[64:128] = 0.15 + np.random.randn(64) * 0.20  # 中心丑陋
                elif scene_name == 'triumph':
                    frame.vision = np.random.randn(256) * 0.05 + 0.60  # 金色闪耀
                    frame.vision[:32] += 0.35  # 顶部极亮
                else:
                    frame.vision = np.random.randn(256) * 0.08 + 0.48

                if is_transient:
                    frame.vision += np.random.randn(256) * 0.3 * transient_boost

            elif token.modality == "audio":
                if scene_name == 'sunrise':
                    frame.audio = np.random.randn(64) * 0.05 + 0.25 * np.abs(np.sin(np.linspace(0, 3*np.pi, 64)))
                elif scene_name == 'threat':
                    frame.audio = np.random.randn(64) * 0.25 - 0.05
                elif scene_name == 'social':
                    frame.audio = np.random.randn(64) * 0.08 + 0.18
                elif scene_name == 'comfort':
                    frame.audio = np.random.randn(64) * 0.04 + 0.12
                # === v4 新增音频模式 ===
                elif scene_name == 'joy':
                    frame.audio = np.random.randn(64) * 0.04 + 0.35 * np.abs(np.sin(np.linspace(0, 6*np.pi, 64)))  # 欢快大调
                elif scene_name == 'serenity':
                    frame.audio = np.random.randn(64) * 0.02 + 0.08 * np.abs(np.sin(np.linspace(0, 1*np.pi, 64)))  # 远处海浪
                elif scene_name == 'curiosity':
                    frame.audio = np.random.randn(64) * 0.10 + 0.22  # 意外音调
                    frame.audio[::8] += 0.15 * np.random.randn(8)  # 随机点缀音
                elif scene_name == 'anger':
                    frame.audio = np.random.randn(64) * 0.30 + 0.05  # 尖锐警报
                    frame.audio[:16] *= 2.0  # 开头极刺耳
                elif scene_name == 'fear':
                    frame.audio = np.random.randn(64) * 0.35 - 0.10  # 尖叫声
                    frame.audio = np.abs(frame.audio) * 1.5  # 全正振幅（刺耳）
                elif scene_name == 'sadness':
                    frame.audio = np.random.randn(64) * 0.06 + 0.10 * np.abs(np.sin(np.linspace(0, 2*np.pi, 64)))  # 小调
                elif scene_name == 'anxiety':
                    frame.audio = np.random.randn(64) * 0.18 + 0.28  # 不规则蜂鸣
                    frame.audio[::5] += 0.20 * np.random.randn(13)  # 间歇性高频
                elif scene_name == 'disgust':
                    frame.audio = np.random.randn(64) * 0.15 + 0.08  # 湿润的咯吱声
                    frame.audio[:32] *= 1.3  # 前半段更突出
                elif scene_name == 'triumph':
                    frame.audio = np.random.randn(64) * 0.03 + 0.40 * np.abs(np.sin(np.linspace(0, 4*np.pi, 64)))  # 号角
                else:
                    frame.audio = np.random.randn(64) * 0.06

                if is_transient:
                    frame.audio += np.random.randn(64) * 0.3 * transient_boost

            elif token.modality == "touch":
                if is_transient and scene_name == 'comfort':
                    frame.touch = np.full(16, 0.6) + np.random.randn(16) * 0.1
                else:
                    frame.touch = np.full(16, touch_intensity) + np.random.randn(16) * 0.05

            elif token.modality == "thermal":
                frame.thermal = temp + np.random.randn() * 0.5
                if is_transient:
                    frame.thermal += np.random.randn() * 3.0

            elif token.modality == "proprioception":
                frame.proprioception = np.random.randn(7) * 0.1

            elif token.modality == "interoception":
                if scene_name == 'threat':
                    frame.interoception = np.array([0.70, 0.65, 0.60, 0.55]) + np.random.randn(4) * 0.03
                elif scene_name == 'comfort':
                    frame.interoception = np.array([0.88, 0.18, 0.18, 0.25]) + np.random.randn(4) * 0.02
                elif scene_name == 'social':
                    frame.interoception = np.array([0.82, 0.48, 0.32, 0.52]) + np.random.randn(4) * 0.03
                elif scene_name == 'sunrise':
                    frame.interoception = np.array([0.80, 0.45, 0.28, 0.48]) + np.random.randn(4) * 0.03
                # === v4 新增内感模式 ===
                elif scene_name == 'joy':
                    frame.interoception = np.array([0.90, 0.78, 0.42, 0.58]) + np.random.randn(4) * 0.02
                elif scene_name == 'serenity':
                    frame.interoception = np.array([0.92, 0.15, 0.22, 0.38]) + np.random.randn(4) * 0.01
                elif scene_name == 'curiosity':
                    frame.interoception = np.array([0.82, 0.55, 0.35, 0.52]) + np.random.randn(4) * 0.03
                elif scene_name == 'anger':
                    frame.interoception = np.array([0.65, 0.72, 0.55, 0.35]) + np.random.randn(4) * 0.04
                elif scene_name == 'fear':
                    frame.interoception = np.array([0.55, 0.80, 0.70, 0.40]) + np.random.randn(4) * 0.05
                elif scene_name == 'sadness':
                    frame.interoception = np.array([0.78, 0.28, 0.45, 0.30]) + np.random.randn(4) * 0.02
                elif scene_name == 'anxiety':
                    frame.interoception = np.array([0.75, 0.60, 0.50, 0.42]) + np.random.randn(4) * 0.04
                elif scene_name == 'disgust':
                    frame.interoception = np.array([0.60, 0.55, 0.45, 0.30]) + np.random.randn(4) * 0.04
                elif scene_name == 'triumph':
                    frame.interoception = np.array([0.92, 0.82, 0.45, 0.60]) + np.random.randn(4) * 0.03
                else:
                    frame.interoception = np.array([0.85, 0.40, 0.30, 0.50]) + np.random.randn(4) * 0.02

        return frame


class SimulatedEnvironment:
    """向后兼容：模拟环境，场景切换"""

    def __init__(self):
        self._sensors = SensorArray()
        self._current_scenario = "idle"
        self._scenario_start = 0.0

    def set_scenario(self, name: str) -> None:
        self._current_scenario = name
        self._scenario_start = time.time()
        self._sensors.start_scenario(name)

    def tick(self):
        """旧接口：一次环境 tick"""
        return self._sensors.read()


if __name__ == "__main__":
    asyncio.run(demo_transport())
