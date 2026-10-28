# 第29轮实现前研究：群体成员窗口统计

## 场景与候选

已有CSV可按gates/population的成员位置start/count切片，population-stats却明确拒绝这两个选项；调用方无法直接取得与该CSV窗口一致的统计。这是小型组合缺口，不称为已有合同的缺陷。本轮只接通单窗口，不增加滑动/按时间排序、批次分析、统计量或新格式。

## 查重与差异

fresh Mooncakes官方fcs/cytometry搜索各limit20，fcs仍为本项目0.2.2和radioframe0.2.0，cytometry仅本项目；GitHub fcs language:MoonBit命中本项目。原始回执保留，名称/摘要范围不证明私有/赛事项目不存在或生态唯一。

[FlowKit Session.get_gate_events](https://flowkit.readthedocs.io/en/latest/session.html#flowkit.Session.get_gate_events)已有指定群体事件表；[pandas iloc官方](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.iloc.html)已有按整数位置选择和切片。此类窗口选择成熟，本轮不主张算法首创。pandas切片可容忍越界；本项目选择沿用已有CSV严格start/count合同，越界错误而不截断。差异只是本地MoonBit群体交换CLI中，原成员/完整矩阵数值视图/报告通道与同一窗口统计的连接；独立实现，不引入pandas或Python运行依赖。

## 有限合同

population-stats新增start/count，位置属于完整群体成员序列，不是原Dataset行号，不排序。默认start0、count=群体长-start；都是非负精确32位索引，start<=群体长且count<=剩余长度。空窗口、起点在末尾、空群体可合法返回空统计；坏计划/通道在零窗口也校验。

先执行完整群体计划，再对成员序列取窗口，将实际原事件索引交给已有全通道统计。完整补偿后筛报告通道规则不变，门控视图/顶层统计视图仍独立。population_events始终是完整群体长；source_event_indices只列实际窗口；显式给出任一窗口参数时额外events表示实际窗口长度。不传两者保持26旧格式。ChannelStats仍按实际有限值计数，非有限另计，不以完整群体作均值/方差分母。

25保留的start:0原请求/源不删除；在当前核验工具按新合同改为成功并核独立统计、群体/窗口计数与源索引。其旧拒绝回执冻结保留，只单独新验已改变的合同；不跑25/26旧全集、27/28链或RepOD。

## 有限验收与工具边界

新原创MIT非连续65位ID群体，用独立bits/struct/Fraction及闭式补偿预期核对首/中/尾/全/空窗口、仅start或count、非法范围/类型、零窗口仍查坏群体/通道、非零Dataset、窗口内非有限计数、完整矩阵/重复报告列、实际同窗口CSV及便携新选项。默认格式与显式全窗口除events字段外相同。原源/ANALYSIS不变。

只改Node组合及相关说明/例程/核验/CI，不改MoonBit核心/API/编译产物，不运行SDK/包管理器；Node缓存/TEMP/TMP只写29报告，Python-B和sys.dont_write_bytecode禁辅助pyc。新相关检查一次干净通过后封包逐项读回，不重复未变已过检查，无推送发布赛事提交。
