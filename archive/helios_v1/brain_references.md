# brain_references

> 主题：人脑如何将外界刺激加工为情感与意识化思考（含记忆参与与神经化学参与）
>
> 用途：Helios 类脑架构研究对照资料（可直接下载归档）

## 1. 总体处理链路（精细版）

人脑并非单线流程，而是并行回路耦合。工程上可按以下阶段理解：

1. **刺激输入与感觉编码**：外界刺激（视觉/听觉/触觉等）与内感受信号（心率、呼吸、疼痛、饥饿）进入感觉系统。
2. **快速显著性评估**：丘脑-杏仁核快速通路优先完成威胁/奖励/新奇性粗评估。
3. **精细语义与情境评估**：感觉皮层与联合皮层进行更高分辨率识别，并回流到杏仁核、ACC、OFC/vmPFC。
4. **内稳态与身体化反应**：下丘脑、脑干、自主神经和内分泌轴触发生理反应；岛叶将内感受整合为主观“感受质感”。
5. **记忆参与与情境绑定**：海马-海马旁系统检索情景/自传记忆，杏仁核赋予记忆情绪权重。
6. **认知重评估与决策**：PFC（dlPFC/vmPFC/mPFC）与 ACC 对价值、目标冲突、自我相关性进行整合。
7. **意识化与可报告思维**：前额叶-顶叶网络与默认网络（DMN）共同支持可报告内容、反思与叙事化。
8. **行为输出与再学习**：语言/动作/自主反应输出，结果写回记忆并更新后续情绪阈值。

---

## 2. 神经化学参与（按环节）

- **多巴胺（DA）**：VTA/SNc 到纹状体与前额叶，参与奖励预测误差、动机与行动选择。
- **去甲肾上腺素（NE）**：蓝斑核（LC）投射广泛皮层，提升警觉、注意切换与不确定情境下的增益控制。
- **5-羟色胺（5-HT）**：中缝核系统，参与情绪稳态、冲动抑制、厌恶/惩罚敏感度与认知灵活性。
- **乙酰胆碱（ACh）**：基底前脑-皮层系统，强化注意定向、感觉增益与学习编码。
- **谷氨酸（Glu）/GABA**：兴奋-抑制平衡骨架，决定网络可塑性、稳定性与振荡协调。
- **皮质醇（HPA 轴）**：急慢性应激调制杏仁核/海马/PFC 权衡，影响记忆编码与认知控制。
- **催产素（OXT）与血清素-多巴胺耦合**：社会线索解释、亲密/信任与社会情绪调谐。

---

## 3. 细化流程图（含脑区与神经化学）

```mermaid
flowchart TD
    A[外界刺激 + 内感受输入] --> B[丘脑/感觉通路\n初级中继与分发]

    B --> C1[快速通路: 丘脑→杏仁核\n粗粒度威胁/奖励评估]
    B --> C2[皮层通路: 感觉皮层→联合皮层\n高分辨率语义识别]

    C1 --> D[杏仁核-ACC-OFC/vmPFC\n显著性与情绪价值整合]
    C2 --> D

    D --> E[下丘脑+脑干+ANS/HPA\n生理唤醒与应激准备]
    E --> F[岛叶(Insula)\n内感受整合→主观感受底层]

    D --> G[海马/海马旁系统\n情景与自传记忆检索]
    F --> G

    G --> H[dlPFC/vmPFC/mPFC + ACC\n重评估、目标冲突处理、自我相关解释]
    F --> H

    H --> I[前额叶-顶叶网络 + DMN\n意识化、可报告思考、叙事化]
    G --> I

    I --> J[基底节-运动/语言系统\n行动选择与外显输出]
    J --> K[行为结果/社会反馈]
    K --> L[记忆再编码与情绪阈值更新]
    L --> G

    %% Neurochemical overlays
    N1[DA: 奖励预测误差/动机\nVTA-SNc→纹状体/PFC] -.调制.-> D
    N1 -.调制.-> H
    N1 -.调制.-> J

    N2[NE: 警觉与注意增益\nLC→皮层广泛投射] -.调制.-> C1
    N2 -.调制.-> C2
    N2 -.调制.-> I

    N3[5-HT: 情绪稳态/冲动抑制\n中缝核系统] -.调制.-> D
    N3 -.调制.-> H

    N4[ACh: 注意定向/编码增强\n基底前脑→皮层] -.调制.-> C2
    N4 -.调制.-> G

    N5[皮质醇(HPA): 应激调制\n影响杏仁核-海马-PFC权衡] -.调制.-> E
    N5 -.调制.-> G
    N5 -.调制.-> H
```

---

## 4. 脑区-功能-化学耦合速查表

| 脑区/系统 | 核心功能 | 代表性化学参与 |
|---|---|---|
| 丘脑与感觉皮层 | 输入中继、特征提取 | ACh、NE |
| 杏仁核 | 显著性与情绪优先级（威胁/奖励） | NE、DA、5-HT、皮质醇 |
| 岛叶 | 内感受整合、主观感受质感 | NE、5-HT |
| 下丘脑/脑干/ANS | 内稳态、应激、自主反应 | 皮质醇、NE |
| 海马-海马旁系统 | 情景记忆、自传连续性、上下文绑定 | ACh、Glu、皮质醇 |
| ACC | 冲突监测、痛苦/努力评估、行动准备 | DA、NE |
| vmPFC/OFC | 价值评估、情绪调节、社会决策 | DA、5-HT |
| dlPFC | 工作记忆、认知控制、重评估 | DA、NE |
| DMN（mPFC/PCC 等） | 自我叙事、内省、心理模拟 | 5-HT、Glu/GABA 平衡 |
| 基底节与运动/语言输出系统 | 行动门控、策略执行 | DA、GABA |

---

## 5. 参考文献（含简要用途说明）

1. **LeDoux JE.** Rethinking the emotional brain. *Neuron* (2012).  
   用途：支撑“快速（低路）/慢速（高路）评估”与防御优先处理框架。  
   链接（开放综述入口）：https://pmc.ncbi.nlm.nih.gov/articles/PMC11530156/

2. **Pessoa L.** Emotion and cognition and the amygdala: from “what is it?” to “what’s to be done?”. *Neuropsychologia* (2010); and network-model related work.  
   用途：支撑“情绪-认知深度耦合”而非模块分离观。  
   链接：https://pmc.ncbi.nlm.nih.gov/articles/PMC3108339/

3. **Dalgleish T.** The emotional brain. *Nature Reviews Neuroscience* (2004).  
   用途：经典情绪神经回路综述，便于建立杏仁核/前额叶/扣带映射。

4. **Craig AD.** How do you feel—now? The anterior insula and human awareness. *Nature Reviews Neuroscience* (2009).  
   用途：支撑“内感受→主观感受→意识体验”的关键链路。

5. **Seth AK.** Interoceptive inference, emotion, and the embodied self. *Trends in Cognitive Sciences* (2013).  
   用途：为“身体状态参与情绪生成”提供预测加工框架。

6. **McEwen BS, Morrison JH.** The brain on stress: vulnerability and plasticity of the prefrontal cortex over the life course. *Neuron* (2013).  
   用途：说明应激激素（皮质醇）对海马/PFC/杏仁核动态权衡的影响。

7. **Yonelinas AP et al.** The hippocampus and consciousness. *Frontiers in Human Neuroscience* (2013).  
   用途：支撑海马在情景记忆与意识经验中的作用。  
   链接：https://pmc.ncbi.nlm.nih.gov/articles/PMC3667233/

8. **Pessoa L.** A network model of the emotional brain. *Trends in Cognitive Sciences* (2017).  
   用途：支持网络层级建模（情绪、执行控制、行动选择共同建模）。

9. **Menon V, Uddin LQ.** Saliency, switching, attention and control (insula/ACC network). *Brain Structure and Function* (2010).  
   用途：支撑显著性网络在注意切换与控制中的桥梁作用。

10. **Northoff G et al.** Self-referential processing in our brain: A meta-analysis of imaging studies on the self. *NeuroImage* (2006).  
    用途：支撑自我相关加工与意识化叙事网络。

11. **Aston-Jones G, Cohen JD.** An integrative theory of locus coeruleus–norepinephrine function. *Annual Review of Neuroscience* (2005).  
    用途：支撑 NE 在“警觉-探索/利用切换-增益控制”中的角色。

12. **Schultz W.** Dopamine reward prediction error coding (系列论文/综述).  
    用途：支撑多巴胺在奖励预测误差与策略更新中的核心地位。

13. **Cools R, Roberts AC, Robbins TW.** Serotoninergic regulation of emotional and behavioural control processes. *Trends in Cognitive Sciences* (2008).  
    用途：支撑 5-HT 对冲动控制、情绪稳态和决策风格的影响。

14. **Hasselmo ME, Sarter M.** Modes and models of forebrain cholinergic neuromodulation of cognition. *Neuropsychopharmacology* (2011).  
    用途：支撑 ACh 对注意与记忆编码门控作用。

15. **Pessoa L, Medina L, Desfilis E.** Save the limbic system: why remove it from the connectome? *Neuroscience & Biobehavioral Reviews* (2014).  
    用途：支持“边缘系统需以网络节点方式重释”，避免单区决定论。  
    链接：https://www.sciencedirect.com/science/article/pii/S0149763413001711

---

## 6. 对 Helios 研究使用建议（简版）

- 将本流程图作为“人脑参考层”；将 `helios_main.py` 主循环作为“工程实现层”。
- 做一对一对照时优先比较：
  1) **显著性评估是否影响全局广播**；
  2) **记忆检索是否实时改写情绪/决策**；
  3) **内感受变量是否进入思维与行为门控**；
  4) **神经化学参数是否只做噪声调制，还是决定策略切换阈值**。

