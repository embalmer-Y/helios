"""DAISY 快速验证脚本"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from daisy_emotion import DaisySystemEngine, get_activation_vector, get_opponent_state

e = DaisySystemEngine()

# 模拟事件序列
events = [
    (0,  {"FEAR": 0.6, "PANIC": 0.3}),              # 威胁事件
    (8,  {"CARE": 0.5, "PLAY": 0.2}),               # 社交温暖
    (20, {"SEEKING": 0.7, "LUST": 0.3}),            # 发现
    (35, {"FEAR": 0.8, "RAGE": 0.4}),               # 严重威胁
    (50, {"PLAY": 0.6, "SEEKING": 0.2}),            # 嬉戏
    (65, {"PANIC": 0.7, "FEAR": 0.3}),              # 分离
    (80, {"CARE": 0.6, "SEEKING": 0.1}),            # 关爱
]

dom_count = {}
all_acts = []

for cycle in range(100):
    trig = {}
    for ev_cycle, ev_trig in events:
        if cycle == ev_cycle:
            trig = ev_trig
            break
    
    state = e.cycle(triggers=trig if trig else None)
    dom = state.dominant_system
    dom_count[dom] = dom_count.get(dom, 0) + 1
    
    if cycle % 5 == 0:
        acts = get_activation_vector(e)
        b_state = get_opponent_state(e)
        # Show top 3 systems
        top3 = sorted(acts.items(), key=lambda x: -x[1])[:3]
        top_str = " ".join(f"{n[:4]}={v:.2f}" for n, v in top3)
        b_str = f"b:{dom[:4]}={b_state.get(e.opponents[dom].opponent,0):.2f}" if dom in e.opponents else ""
        print(f"  c{cycle:>3d} dom={dom:>8} [{top_str}] {b_str}")
    
    all_acts.append(state.panksepp_activation)

# Summary
print()
total = sum(dom_count.values())
print("═══ Dominance Distribution ═══")
for d in sorted(dom_count, key=lambda x: -dom_count[x]):
    pct = 100 * dom_count[d] / total
    bar = "█" * int(pct / 2)
    print(f"  {d:>10}: {dom_count[d]:3d} ({pct:5.1f}%) {bar}")

# Co-activation stats
print()
print("═══ Average Co-activation ═══")
for name in ["SEEKING", "PLAY", "CARE", "PANIC", "FEAR", "RAGE", "LUST"]:
    avg = sum(a[name] for a in all_acts) / len(all_acts)
    print(f"  {name:>10}: {avg:.3f}")
