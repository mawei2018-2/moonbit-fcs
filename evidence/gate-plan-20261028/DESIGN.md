# 09轮拓展决策与验收合同

用户已授权在08修复封存后主动拓展同一项目；08源码包SHA为86d2d6b630d99bd34d31dd569b61d68fed28bdc88fb494f114af32ca0ffa5f4d。仅改FCS项目与本轮报告，不推送/发布，不变账号/SDK，不覆盖历史证据。

## 候选与选择

| 候选 | 使用者实际要做什么 | 当前缺口/成本 | 决定 |
|---|---|---|---|
| 命名分层门控 | 在粗选群体内继续按形状/精确ID筛选，比较分支占比，并交付该群体FCS | 现有rectangle/polygon/exact仅独立返回索引；手动相交、保存父索引和分母容易出错 | 选择：核心组合能力，可完整交付纯MoonBit API、CLI与例程 |
| 多文件批处理计划 | 一套选择条件应用于多文件，汇总散列/结果 | 当前deep-batch是验证驱动；用户批次兼容与多输出故障语义还需更大工作 | 本轮不实现 |
| 兼容文件合并 | 汇总事件而保持来源 | 任意位宽/模式/元数据/ANALYSIS的合并合同复杂 | 本轮不实现 |

## 生态与差异

Mooncakes官方站源码server_search.mbt公开实际搜索端点；已对fcs/cytometry/gating执行HTTP200实时查询（原始JSON保存）。fcs命中本项目和无线帧校验，cytometry仅本项目；gating包含CI/覆盖率/时序等不同用途。GitHub fcs language:MoonBit返回本项目；cytometry/FlowKit/FlowIO+MoonBit专门查询未返回新增相关仓库。泛gating结果存在，不将关键词命中误认成细胞术库，也不据此宣称穷尽私有仓库或首个/唯一。来源索引见RESEARCH-RAW.json、RESEARCH-MORE.json、MOONCAKES-LIVE.json。

FlowKit官方GatingStrategy/GatingResults已经提供层级、成员、计数和父群体占比；此功能不是算法创新。独立增量是本地已有MoonBit FCS交换核心中的组合API、I/A字符串BigInt精确谓词、JS/Wasm消费与原始事件身份，宿主运行不需Python。参考概念和文档，不复制FlowKit代码或样本。无已确认实验室使用方；例程为原创格式准备场景。

## 功能合同（实现前确定）

1. 新增GatePredicate（Rectangle/Polygon/Exact）、GateStep（唯一非空id、可选parent、谓词、每步scaled/compensated标志）、只读Population，以及Dataset.gate_plan。
2. 每步结果为自身谓词与父群体的交集；无parent代表全部列表事件。返回原始Dataset的升序事件索引，不能把父群体中的相对行号冒充源索引。支持前向父引用、分支及任意输入顺序，输出保持计划输入顺序。
3. 返回count、parent_count、total_count、parent_fraction和total_fraction。分母0时为None（JSON该字段省略），不编造0/0比例。空计划返回[]；空数据、空父群体仍验证谓词配置。所有步骤必须有效才返回结果。
4. 拒绝重复/空id、未知parent、循环、C/U、非法谓词/通道、Exact与scaled/compensated混用。Exact计划要求非空区间。现有单门API和CLI行为保持。
5. CLI新增populations报告，gate/subset可用gates+population选择命名群体；与现有events/bounds/vertices/integer_bounds互斥。嵌套JSON索引严格整型，不静默截断；门步骤未知字段/多个谓词明确失败。subset继续沿用ANALYSIS/drop与原始DATA写出合同。
   计划的视图标志只属于每个步骤；若计划请求同时给出顶层scaled/compensated则明确拒绝，避免静默忽略用户的视图意图。
6. 原创可运行例程创建含65位精确事件ID的数据，执行多层与分支计划并报告，导出指定群体和原始通道；给出明确索引/计数真值和运行命令。
7. 新增API为兼容性扩展，不移除或改现有签名；模块账号/版本/作者不变。无GUI、GatingML/FlowJo导入、布尔组合、多父节点、跨样本批处理、自动门控或临床结论。

## 验收

纯MoonBit回归覆盖原始索引/前向引用、分支计数、空父/空数据、图错误、三类谓词、逐步缩放/补偿；JS/Wasm均执行。独立Python手算/整数位流核对真实CLI报告与FCS输出，不复制核心拓扑算法。核对嵌套小数索引/冲突/图错误的stderr/退出1及无目标文件。独立公开MoonBit模块两端一致；真实Node例程可运行并保留输出。只重跑受新接入影响的既有选择器/请求合同/相关回归。

最后校准README、DUPLICATION和<=30行评委PROPOSAL；固定源码/编译桥身份，新ZIP逐项回读，完成本轮必做项才RESULT.complete。
