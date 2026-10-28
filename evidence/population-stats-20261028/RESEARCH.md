# 第25轮实现前研究与有限合同

## 候选及查重

候选A为已有命名群体的全通道统计摘要；候选B为扩展通用/稳健统计。现有statistics已提供均值、样本方差、极值、有限/非有限计数；后者没有本项目可证实的缺口，且Mooncakes公开hxiuzheng/robust_stats提供成熟通用统计，故不实现B、不添加新统计方法或依赖。

本轮fresh查询Mooncakes官方search端点fcs/cytometry/robust_stats，每项limit20，原始响应见MOONCAKES-LIVE.json。fcs命中本项目0.2.2和radioframe0.2.0；cytometry只命中本项目；robust_stats命中通用统计包等。GitHub连接器cytometry language:MoonBit本次返回空列表。这些只是名称/摘要有界查询，不覆盖私有代码、报名表或证明首创。

公开同类：[FlowKit官方](https://whitews.github.io/FlowKit/)列出[门内MFI例程](https://github.com/whitews/FlowKit/blob/master/docs/notebooks/advanced/compare-mfi-of-gated-events.ipynb)，[Session.get_gate_events](https://flowkit.readthedocs.io/en/latest/session.html#flowkit.Session.get_gate_events)能返回指定门内事件表。统计和门控均已有成熟实现；本轮不主张科学算法创新，也不复制代码或数据。Mooncakes的[robust_stats](https://mooncakes.io/docs/hxiuzheng/robust_stats)进一步说明无需重写通用算法。本项目增量是将已有MoonBit群体、原始事件身份和现有统计接通。

## 现有缺口与方案

当前Dataset.statistics和CLI stats扫描整个Dataset；gate_plan有成员，但用户须另存群体FCS/CSV后自行汇总。新增CLI population-stats，要求gates/population，返回population、population_events、source_event_indices、channel_names、scaled/compensated和statistics。统计覆盖全部原通道，直接保留完整补偿矩阵语义；不增加通道投影、start/count切片、新统计量或跨文件汇总。

Node复用现有MoonBit query选群体，在内存中用显式events生成保留全部通道的私有FCS（drop_analysis:true只用于私有副本），再load该独立Dataset并调用既有stats。没有中间磁盘FCS，原文件与ANALYSIS不变。内存副本仍有额外分配和一次原字节拷贝，不宣称零拷贝、流式或大样本性能提升。顶层scaled/compensated选择统计视图，每步自己的flags选择门控视图；compensated隐含scaled。统计仍为Double，原始65位ID仅用于精确选群体，不承诺大整数统计精确。

新命令只接受既有解析选项dataset/strict/allow_exclusive_end/latin1/allow_text_padding/allow_offset_padding，以及gates/population/scaled/compensated；未知或不适用的选项失败。旧stats/CSV/gate/subset和全部MoonBit API/核心/编译产物不改，不收紧既有合法输入。

## 验收与缓存边界

原创MIT合成数据用独立位流/struct和Fraction预期验证非连续65位ID群体、gain、完整非单位补偿矩阵、视图分离、空/单例、非有限数据、非零Dataset、带ANALYSIS源不变、坏计划/群体/选项。一个既有许可RepOD消费以原F32字节/冻结成员独立核对新增统计，不重跑旧CSV/FlowIO或全集。只跑新相关核验、Node语法和CI语法，一次干净通过即封存。

运行仅Node24.11与Python标准库，actionlint为只读语法工具；不运行MoonBit工具链或依赖解析，不访问SDK可写缓存。NODE_COMPILE_CACHE、TEMP/TMP定向本轮报告；PYTHONDONTWRITEBYTECODE=1，脚本导入辅助工具时也设置sys.dont_write_bytecode。没有SDK复制/安装、moon update/build/check/test/info/fmt，没有旧报告缓存写入。缓存位置与命令回执另存CACHE-POLICY.json。
