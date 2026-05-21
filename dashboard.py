"""
N2: Helios 情感可视化面板 (Dashboard)
=====================================

功能:
  · 实时情感仪表盘 — Panksepp 7系统 + Φ + 神经化学 + 心境 + 异稳态
  · HTTP 服务器 + SSE 推送
  · 纯 Chart.js 前端，无外部依赖

使用:
  python3 dashboard.py [--port 8765] [--demo] [--engine helios_runner.py]

架构:
  DashboardServer (HTTP + SSE)
      ↓
  DashboardState (共享状态, 线程安全)
      ↓
  HeliosRunner (引擎循环, 后台线程)
"""

import http.server
import json
import sys
import os
import time
import threading
from pathlib import Path
from typing import Dict, Optional, List
import queue

# Helios 模块
sys.path.insert(0, os.path.dirname(__file__))
from daisy_emotion import (
    DaisySystemEngine, PANKSEPP_SYSTEMS,
    VALENCE_BIAS, AROUSAL_BIAS,
    get_activation_vector
)
from allostasis import AllostaticRegulator, AllostasisConfig
from mood_tracker import MoodTracker
from personality import PersonalityProfile
from autobiographical import AutobiographicalStore, create_autobiographical_store

# 可选模块
try:
    from neurochem import NeurochemState
    HAS_NEUROCHEM = True
except ImportError:
    HAS_NEUROCHEM = False

try:
    from phi import UnifiedPhi
    # Quick check if UnifiedPhi is functional
    p = UnifiedPhi()
    p.feed_emotional({"SEEKING": 0.1})
    p.aggregate()
    HAS_PHI = True
except (ImportError, Exception):
    HAS_PHI = False


# ═══════════════════════════════════════════════
# 共享状态
# ═══════════════════════════════════════════════

class DashboardState:
    """线程安全的仪表盘状态"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.cycle: int = 0
        self.panksepp: Dict[str, float] = {s: 0.05 for s in PANKSEPP_SYSTEMS}
        self.valence: float = 0.0
        self.arousal: float = 0.0
        self.dominant: str = ""
        self.label: str = "neutral"
        self.phi: float = 0.0
        
        # 神经化学
        self.neurochem: Dict[str, float] = {}
        
        # 心境
        self.mood_valence: float = 0.0
        self.mood_arousal: float = 0.0
        self.mood_label: str = "neutral-calm"
        
        # 异稳态
        self.allostasis_load: float = 0.0
        self.allostasis_fatigued: bool = False
        self.allostasis_recovering: bool = False
        self.allostasis_setpoints: Dict[str, float] = {}
        
        # 人格
        self.personality_summary: str = ""
        self.personality_traits: Dict[str, float] = {}
        
        # N1: 自传记忆统计
        self.autobio_stats: dict = {}
        self.autobio_narrative: str = ""
        
        # 历史 (最近200条)
        self.history: List[dict] = []
        self.max_history = 200
        
        # SSE 队列
        self._sse_queues: List[queue.Queue] = []
    
    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)
            
            # 构建完整的 per-cycle entry
            entry = {
                "cycle": self.cycle,
                "valence": round(self.valence, 3),
                "arousal": round(self.arousal, 3),
                "dominant": self.dominant,
                "label": self.label,
                "phi": round(self.phi, 4),
                "panksepp": {k: round(v, 3) for k, v in self.panksepp.items()},
                "neurochem": dict(self.neurochem),
                "mood": {
                    "valence": round(self.mood_valence, 3),
                    "arousal": round(self.mood_arousal, 3),
                    "label": self.mood_label,
                },
                "allostasis": {
                    "load": round(self.allostasis_load, 3),
                    "fatigued": self.allostasis_fatigued,
                    "recovering": self.allostasis_recovering,
                },
            }
            self.history.append(entry)
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
        
        # 推送给所有 SSE 连接
        data = json.dumps(entry)
        dead_queues = []
        for q in self._sse_queues:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead_queues.append(q)
        for q in dead_queues:
            self._sse_queues.remove(q)
    
    def add_sse_queue(self, q: queue.Queue):
        self._sse_queues.append(q)
    
    def remove_sse_queue(self, q: queue.Queue):
        if q in self._sse_queues:
            self._sse_queues.remove(q)
    
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cycle": self.cycle,
                "panksepp": dict(self.panksepp),
                "valence": round(self.valence, 3),
                "arousal": round(self.arousal, 3),
                "dominant": self.dominant,
                "label": self.label,
                "phi": round(self.phi, 4),
                "neurochem": dict(self.neurochem),
                "mood": {
                    "valence": round(self.mood_valence, 3),
                    "arousal": round(self.mood_arousal, 3),
                    "label": self.mood_label,
                },
                "allostasis": {
                    "load": round(self.allostasis_load, 3),
                    "fatigued": self.allostasis_fatigued,
                    "recovering": self.allostasis_recovering,
                    "setpoints": dict(self.allostasis_setpoints),
                },
                "personality": {
                    "summary": self.personality_summary,
                    "traits": dict(self.personality_traits),
                },
                "autobio": dict(self.autobio_stats),
                "history": self.history[-50:],  # 最近50条
            }


# ═══════════════════════════════════════════════
# Helios 运行器
# ═══════════════════════════════════════════════

class HeliosRunner:
    """后台运行 Helios 引擎，更新 DashboardState"""
    
    def __init__(self, state: DashboardState, event_source=None, autobio_store: AutobiographicalStore = None):
        self.state = state
        self.engine = DaisySystemEngine()
        self.allostasis = AllostaticRegulator()
        self.mood = MoodTracker()
        self.personality = PersonalityProfile()
        
        # 注入到引擎
        self.engine.allostasis = self.allostasis
        self.engine.mood_tracker = self.mood
        self.engine.personality = self.personality
        
        # 可选模块
        self.neurochem = NeurochemState() if HAS_NEUROCHEM else None
        self.phi_engine = UnifiedPhi() if HAS_PHI else None
        
        # N1: 自传记忆
        self.autobio = autobio_store
        
        self.event_source = event_source
        self.running = False
        self.thread = None
        self.cycle_interval = 0.15  # 150ms per cycle
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.running = False
    
    def _run(self):
        cycle = 0
        while self.running:
            # 获取事件
            triggers = {}
            if self.event_source:
                triggers = self.event_source.get_event(cycle)
            
            # 运行引擎
            state = self.engine.cycle(triggers if triggers else {})
            
            # 更新共享状态
            update_kwargs = {
                "cycle": cycle,
                "panksepp": dict(state.panksepp_activation),
                "valence": state.valence,
                "arousal": state.arousal,
                "dominant": state.dominant_system,
                "label": state.dominant_label,
            }
            
            # Φ
            if self.phi_engine and state.panksepp_activation:
                self.phi_engine.feed_emotional(state.panksepp_activation)
                update_kwargs["phi"] = self.phi_engine.aggregate()
            else:
                update_kwargs["phi"] = 0.0
            
            # 神经化学
            if self.neurochem:
                self.neurochem.tick()
                update_kwargs["neurochem"] = self.neurochem.to_dict()
            
            # 心境
            if self.mood:
                ms = self.mood.get_snapshot()
                update_kwargs["mood_valence"] = ms["valence"]
                update_kwargs["mood_arousal"] = ms["arousal"]
                update_kwargs["mood_label"] = ms["label"]
            
            # 异稳态
            if self.allostasis:
                update_kwargs["allostasis_load"] = self.allostasis.get_load_level()
                update_kwargs["allostasis_fatigued"] = self.allostasis.is_fatigued()
                update_kwargs["allostasis_recovering"] = self.allostasis.is_recovering()
                update_kwargs["allostasis_setpoints"] = {
                    s: round(st.setpoint, 3)
                    for s, st in self.allostasis.states.items()
                }
            
            # 人格 (每10周期更新一次)
            if cycle % 10 == 0 and self.personality:
                update_kwargs["personality_summary"] = self.personality.summary()
                update_kwargs["personality_traits"] = {
                    "openness": self.personality.openness,
                    "extraversion": self.personality.extraversion,
                    "agreeableness": self.personality.agreeableness,
                    "neuroticism": self.personality.neuroticism,
                    "conscientiousness": self.personality.conscientiousness,
                }
            
            # N1: 自传统计 (每50周期)
            if cycle % 50 == 0 and self.autobio:
                stats = self.autobio.get_statistics()
                update_kwargs["autobio_stats"] = stats
                update_kwargs["autobio_narrative"] = self.autobio.get_narrative(10)
            
            self.state.update(**update_kwargs)
            
            # N1: 记录自传时刻 (高Φ或重要事件)
            if self.autobio and cycle % 5 == 0:  # 每5周期检查一次
                phi = update_kwargs.get("phi", 0.0)
                valence = update_kwargs.get("valence", 0.0)
                
                # 记录条件: Φ>0.3 或 极端效价
                if phi > 0.3 or abs(valence) > 0.5:
                    event_desc = ""
                    if triggers:
                        event_desc = "+".join(triggers.keys())
                    
                    narrative = ""
                    if phi > 0.5:
                        narrative = f"⚡ 意识闪耀时刻: {state.dominant_system}主导"
                    elif abs(valence) > 0.5:
                        direction = "正向" if valence > 0 else "负向"
                        narrative = f"强烈{direction}体验: {state.dominant_system}"
                    elif phi > 0.3:
                        narrative = f"有意义的时刻: {state.dominant_system}"
                    
                    self.autobio.record(
                        panksepp=update_kwargs["panksepp"],
                        valence=valence,
                        arousal=update_kwargs.get("arousal", 0.0),
                        dominant=state.dominant_system,
                        phi=phi,
                        mood_valence=update_kwargs.get("mood_valence", 0.0),
                        mood_arousal=update_kwargs.get("mood_arousal", 0.0),
                        mood_label=update_kwargs.get("mood_label", "neutral"),
                        allostatic_load=update_kwargs.get("allostasis_load", 0.0),
                        narrative=narrative,
                        event_trigger=event_desc,
                        cycle=cycle,
                    )
            
            cycle += 1
            time.sleep(self.cycle_interval)


# ═══════════════════════════════════════════════
# HTTP 请求处理器
# ═══════════════════════════════════════════════

DASHBOARD_HTML = None

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    """HTTP + SSE 请求处理器"""
    
    # 类变量 (在启动时设置)
    state: DashboardState = None
    
    def log_message(self, format, *args):
        if "/api/stream" not in args[0]:
            super().log_message(format, *args)
    
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_html()
        elif self.path == "/api/state":
            self._serve_json(self.state.snapshot())
        elif self.path == "/api/stream":
            self._serve_sse()
        else:
            self.send_error(404)
    
    def _serve_html(self):
        global DASHBOARD_HTML
        if DASHBOARD_HTML is None:
            html_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
            if os.path.exists(html_path):
                with open(html_path, "r") as f:
                    DASHBOARD_HTML = f.read()
            else:
                DASHBOARD_HTML = _generate_inline_html()
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
    
    def _serve_json(self, data):
        body = json.dumps(data, ensure_ascii=False)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
    
    def _serve_sse(self):
        """Server-Sent Events 推送"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        q = queue.Queue(maxsize=50)
        self.state.add_sse_queue(q)
        
        try:
            # 发送初始快照
            init = self.state.snapshot()
            self.wfile.write(f"data: {json.dumps(init)}\n\n".encode("utf-8"))
            self.wfile.flush()
            
            while True:
                try:
                    data = q.get(timeout=30)
                    self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # 发送心跳
                    self.wfile.write(": heartbeat\n\n".encode("utf-8"))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.state.remove_sse_queue(q)


# ═══════════════════════════════════════════════
# 内嵌 HTML (当 dashboard.html 不存在时)
# ═══════════════════════════════════════════════

def _generate_inline_html() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Helios 情感仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a1a;color:#d0e0ff;font-family:'Segoe UI',system-ui,sans-serif;overflow-x:hidden}
.header{background:#101030;border-bottom:2px solid #203060;padding:12px 20px;display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:1.3em;color:#80b0ff}
.header .cycle{color:#6080a0;font-size:0.9em}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:12px;padding:12px;max-width:1600px;margin:0 auto}
.card{background:#101028;border:1px solid #1a1a40;border-radius:8px;padding:14px}
.card h3{margin:0 0 10px 0;font-size:0.95em;color:#6090d0;border-bottom:1px solid #1a1a40;padding-bottom:6px}
.card canvas{max-height:250px}
.mood-badge{display:inline-block;padding:4px 10px;border-radius:12px;font-size:0.85em;font-weight:600}
.mood-neg{background:#301020;color:#ff6070}
.mood-neut{background:#202030;color:#8090a0}
.mood-pos{background:#103020;color:#60ff80}
.valence-bar{height:6px;border-radius:3px;background:linear-gradient(to right,#ff4060,#8080a0,#40ff60);margin:8px 0;position:relative}
.valence-dot{width:12px;height:12px;border-radius:50%;background:white;position:absolute;top:-3px;transform:translateX(-50%);box-shadow:0 0 8px white}
.panksepp-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px 12px}
.panksepp-item{display:flex;align-items:center;gap:6px;font-size:0.82em}
.panksepp-bar{flex:1;height:14px;border-radius:3px;background:#181830;overflow:hidden}
.panksepp-fill{height:100%;border-radius:3px;transition:width 0.3s}
</style>
</head>
<body>
<div class="header">
  <h1>☀️ Helios 情感仪表盘</h1>
  <div class="cycle">周期 <span id="cycle-num">0</span></div>
</div>
<div class="grid">
  <div class="card"><h3>🎯 Panksepp 7系统 雷达</h3><canvas id="radar"></canvas></div>
  <div class="card"><h3>📊 情感时序</h3><canvas id="timeline"></canvas></div>
  <div class="card">
    <h3>💓 效价 / 唤醒 / Φ</h3>
    <div id="mood-indicator"></div>
    <div class="valence-bar"><div class="valence-dot" id="v-dot" style="left:50%"></div></div>
    <canvas id="phi-chart" style="max-height:120px"></canvas>
  </div>
  <div class="card"><h3>🧪 神经化学</h3><canvas id="neurochem"></canvas></div>
  <div class="card"><h3>⚖️ 异稳态负荷</h3><canvas id="allostasis"></canvas></div>
  <div class="card">
    <h3>📋 7系统激活柱状图</h3>
    <div class="panksepp-grid" id="panksepp-grid"></div>
  </div>
</div>

<script>
const COLORS = {
  SEEKING: '#60c0ff', PLAY: '#ffe060', CARE: '#ff80c0',
  PANIC: '#c060ff', FEAR: '#ff4040', RAGE: '#ff8040', LUST: '#ff6080'
};
const LABELS_ZH = {
  SEEKING: '探索欲', PLAY: '嬉戏', CARE: '关爱',
  PANIC: '分离痛', FEAR: '恐惧', RAGE: '愤怒', LUST: '情欲'
};
const MOOD_LABELS = {
  'calm-content':'😌 平静满足','pleased':'😊 愉悦','happy':'😄 快乐','excited':'🤩 兴奋',
  'alert-neutral':'🧐 警觉','uneasy':'😟 不安','anxious':'😰 焦虑','tense':'😬 紧张',
  'neutral-calm':'😐 中性','sad':'😢 悲伤','lethargic':'😴 倦怠','depressed':'😞 抑郁'
};

let charts = {};
let historyData = [];

function createCharts() {
  charts.radar = new Chart(document.getElementById('radar'), {
    type:'radar',data:{labels:Object.values(LABELS_ZH),datasets:[{
      label:'激活度',data:Array(7).fill(0),backgroundColor:'rgba(96,160,255,0.2)',
      borderColor:'rgba(96,160,255,0.8)',borderWidth:2,pointRadius:3
    }]},
    options:{responsive:true,scales:{r:{min:0,max:1,ticks:{stepSize:0.2,color:'#406080'},
      grid:{color:'#1a1a40'},pointLabels:{color:'#6080a0',font:{size:11}}}},
      plugins:{legend:{display:false}}}
  });
  
  charts.timeline = new Chart(document.getElementById('timeline'), {
    type:'line',data:{labels:[],datasets:[]},
    options:{responsive:true,animation:false,
      scales:{x:{display:false},y:{min:0,max:1,ticks:{color:'#406080'},grid:{color:'#1a1a30'}}},
      plugins:{legend:{position:'bottom',labels:{color:'#6080a0',font:{size:9},boxWidth:10}}}}
  });
  
  charts.phi = new Chart(document.getElementById('phi-chart'), {
    type:'line',data:{labels:[],datasets:[{
      label:'Φ',data:[],borderColor:'#ffd040',borderWidth:1.5,pointRadius:0,tension:0.3
    }]},
    options:{responsive:true,animation:false,
      scales:{x:{display:false},y:{min:0,max:1,ticks:{color:'#406080'},grid:{color:'#1a1a30'}}},
      plugins:{legend:{display:false}}}
  });
  
  charts.neurochem = new Chart(document.getElementById('neurochem'), {
    type:'line',data:{labels:[],datasets:[
      {label:'DA',data:[],borderColor:'#ff6040',borderWidth:1.2,pointRadius:0},
      {label:'OP',data:[],borderColor:'#40c0ff',borderWidth:1.2,pointRadius:0},
      {label:'OXY',data:[],borderColor:'#ff80c0',borderWidth:1.2,pointRadius:0},
      {label:'CORT',data:[],borderColor:'#c0c040',borderWidth:1.2,pointRadius:0}
    ]},
    options:{responsive:true,animation:false,
      scales:{x:{display:false},y:{min:0,max:1,ticks:{color:'#406080'},grid:{color:'#1a1a30'}}},
      plugins:{legend:{position:'bottom',labels:{color:'#6080a0',font:{size:9},boxWidth:10}}}}
  });
  
  charts.allostasis = new Chart(document.getElementById('allostasis'), {
    type:'line',data:{labels:[],datasets:[{
      label:'负荷',data:[],borderColor:'#ffa040',borderWidth:1.5,pointRadius:0,fill:true,
      backgroundColor:'rgba(255,160,64,0.1)'
    }]},
    options:{responsive:true,animation:false,
      scales:{x:{display:false},y:{min:0,max:1,ticks:{color:'#406080'},grid:{color:'#1a1a30'}}},
      plugins:{legend:{display:false}}}
  });
}

let timelineSystems = ['SEEKING','PLAY','CARE','PANIC','FEAR','RAGE','LUST'];
let timelineReady = false;

function initTimeline() {
  let ds = [];
  for (let s of timelineSystems) {
    ds.push({label:s,data:[],borderColor:COLORS[s],borderWidth:1,pointRadius:0});
  }
  charts.timeline.data.datasets = ds;
  timelineReady = true;
}

function updateDashboard(data) {
  document.getElementById('cycle-num').textContent = data.cycle;
  
  // 雷达图
  let radarData = [];
  for (let s of timelineSystems) radarData.push(data.panksepp[s] || 0);
  charts.radar.data.datasets[0].data = radarData;
  charts.radar.update('none');
  
  // 时序
  if (!timelineReady) initTimeline();
  charts.timeline.data.labels.push(data.cycle);
  if (charts.timeline.data.labels.length > 120) {
    charts.timeline.data.labels.shift();
    for (let ds of charts.timeline.data.datasets) ds.data.shift();
  }
  for (let i = 0; i < timelineSystems.length; i++) {
    charts.timeline.data.datasets[i].data.push(data.panksepp[timelineSystems[i]] || 0);
  }
  charts.timeline.update('none');
  
  // Φ
  charts.phi.data.labels.push(data.cycle);
  if (charts.phi.data.labels.length > 120) {
    charts.phi.data.labels.shift();
    charts.phi.data.datasets[0].data.shift();
  }
  charts.phi.data.datasets[0].data.push(data.phi || 0);
  charts.phi.update('none');
  
  // 神经化学
  if (data.neurochem && Object.keys(data.neurochem).length > 0) {
    charts.neurochem.data.labels.push(data.cycle);
    if (charts.neurochem.data.labels.length > 120) {
      charts.neurochem.data.labels.shift();
      for (let ds of charts.neurochem.data.datasets) ds.data.shift();
    }
    charts.neurochem.data.datasets[0].data.push(data.neurochem.dopamine || 0);
    charts.neurochem.data.datasets[1].data.push(data.neurochem.opioids || 0);
    charts.neurochem.data.datasets[2].data.push(data.neurochem.oxytocin || 0);
    charts.neurochem.data.datasets[3].data.push(data.neurochem.cortisol || 0);
    charts.neurochem.update('none');
  }
  
  // 异稳态
  let load = data.allostasis ? data.allostasis.load : 0;
  charts.allostasis.data.labels.push(data.cycle);
  if (charts.allostasis.data.labels.length > 120) {
    charts.allostasis.data.labels.shift();
    charts.allostasis.data.datasets[0].data.shift();
  }
  charts.allostasis.data.datasets[0].data.push(load);
  charts.allostasis.update('none');
  
  // 效价点
  let v = data.valence || 0;
  let vPct = ((v + 1) / 2 * 100);
  document.getElementById('v-dot').style.left = vPct + '%';
  
  // 心境标签
  let mood = data.mood || {};
  let ml = mood.label || 'neutral-calm';
  let moodClass = 'mood-neut';
  if (ml.includes('uneasy')||ml.includes('anxious')||ml.includes('tense')||ml.includes('sad')||ml.includes('depress')||ml.includes('lethargic'))
    moodClass = 'mood-neg';
  else if (ml.includes('pleased')||ml.includes('happy')||ml.includes('excite')||ml.includes('calm-content'))
    moodClass = 'mood-pos';
  document.getElementById('mood-indicator').innerHTML = 
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">' +
    '<span style="font-size:1.1em"><b>' + (data.dominant||'--') + '</b> ' +
    '<span style="color:#8090a0;font-size:0.8em">(' + (data.label||'') + ')</span></span>' +
    '<span class="mood-badge ' + moodClass + '">' + (MOOD_LABELS[ml]||ml) + '</span>' +
    '</div>';
  
  // 7系统柱状图
  let grid = document.getElementById('panksepp-grid');
  let html = '';
  for (let s of timelineSystems) {
    let v = (data.panksepp[s] || 0) * 100;
    html += '<div class="panksepp-item">' +
      '<span style="width:48px;text-align:right;font-size:0.78em;color:#6080a0">' + LABELS_ZH[s] + '</span>' +
      '<div class="panksepp-bar"><div class="panksepp-fill" style="width:' + v + '%;background:' + COLORS[s] + '"></div></div>' +
      '<span style="width:32px;font-size:0.75em">' + (data.panksepp[s]||0).toFixed(2) + '</span>' +
      '</div>';
  }
  grid.innerHTML = html;
}

// 启动
createCharts();

// SSE 连接
let es = new EventSource('/api/stream');
es.onmessage = function(e) {
  try {
    let data = JSON.parse(e.data);
    if (data.cycle !== undefined) updateDashboard(data);
  } catch(err) {}
};
es.onerror = function() { setTimeout(() => location.reload(), 3000); };
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════
# 事件源: 演示用
# ═══════════════════════════════════════════════

class DemoEventSource:
    """演示事件源 — 模拟情感事件序列"""
    
    DEMO_EVENTS = [
        # (开始周期, 事件触发)
        (0,   {"FEAR": 0.6, "PANIC": 0.3}),
        (12,  {"CARE": 0.5, "PLAY": 0.2}),
        (25,  {"SEEKING": 0.7, "LUST": 0.3}),
        (40,  {"FEAR": 0.8, "RAGE": 0.4}),
        (55,  {"PLAY": 0.6, "SEEKING": 0.2}),
        (70,  {"PANIC": 0.7, "FEAR": 0.3}),
        (85,  {"CARE": 0.6, "SEEKING": 0.1}),
        (100, {"RAGE": 0.6, "PANIC": 0.2}),
        (115, {"PLAY": 0.7, "LUST": 0.4}),
        (130, {"SEEKING": 0.8, "CARE": 0.3}),
        (150, {"FEAR": 0.5, "SEEKING": 0.2}),
        (165, {"PLAY": 0.5, "CARE": 0.5}),
        (180, {"PANIC": 0.6, "RAGE": 0.3}),
    ]
    
    def get_event(self, cycle: int) -> dict:
        for start_cycle, triggers in self.DEMO_EVENTS:
            if cycle == start_cycle:
                return dict(triggers)
        return {}


# ═══════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Helios 情感可视化面板")
    parser.add_argument("--port", type=int, default=8765, help="HTTP 端口 (默认 8765)")
    parser.add_argument("--demo", action="store_true", default=True, help="使用演示事件源")
    parser.add_argument("--interval", type=float, default=0.15, help="引擎周期间隔/秒 (默认 0.15)")
    args = parser.parse_args()
    
    # 共享状态
    state = DashboardState()
    DashboardHandler.state = state
    
    # 事件源
    event_source = DemoEventSource() if args.demo else None
    
    # Helios 运行器
    autobio = create_autobiographical_store()
    runner = HeliosRunner(state, event_source, autobio_store=autobio)
    runner.cycle_interval = args.interval
    runner.start()
    
    # HTTP 服务器
    server = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), DashboardHandler)
    print(f"☀️  Helios 仪表盘已启动 → http://localhost:{args.port}")
    print(f"    按 Ctrl+C 停止")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n关闭中...")
        runner.stop()
        autobio.close()
        server.shutdown()


if __name__ == "__main__":
    main()
