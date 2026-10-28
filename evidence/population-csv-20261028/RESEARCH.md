# 16轮实现前的场景、差异与验收

本轮只研究一个候选：指定群体直接导出CSV。没有扩展为批次平台、面板推断、新补偿算法或身份认证。

## 已存在的具体操作缺口

当前NAMED-CHANNELS.md与examples/repod-gate-plan.mjs明确采用populations→subset selected.fcs→csv selected.fcs的流程。已许可RepOD96804的inner群体为662事件，CSV仅需Time/FSC-A两列，仍须写一个中间FCS并重读；ANALYSIS/补偿的FCS处理选项也属于这个中间步骤。原接口没有承诺CSV接受群体，故这是操作缺口，不把未承诺功能包装为解析bug。

需要直接从同一个原Dataset读取群体成员的数值；以数据为目的的CSV不需要写FCS，也无需为一个不会被重写的ANALYSIS请求删除。新增回执应带实际导出行的原Dataset索引，以解释来源。

## 当前生态与同类方案

2026-10-28重查Mooncakes官方fcs/cytometry端点（每项limit20）及GitHub仓库fcs language:MoonBit / cytometry language:MoonBit。原始响应分别保存MOONCAKES-LIVE.json、GITHUB-FCS.json、GITHUB-CYTOMETRY.json。名称/摘要检索不覆盖私有代码、完整报名表或全部实现，不宣称生态唯一。

[FlowKit Session官方接口](https://flowkit.readthedocs.io/en/latest/session.html#flowkit.Session.get_gate_events)能取得指定门内事件表，并单独选择补偿/变换；[官方Session教程](https://flowkit.readthedocs.io/en/stable/notebooks/flowkit-tutorial-part05-session-class.html#Extract-Gated-Event-Data)说明保留原样本事件索引。直接获得门内表格是成熟流程，不是算法创新。本轮差异仅为已有MoonBit门控/精确整数/数值视图在Node文件适配层的直接CSV连接，不引入Python运行依赖，不复制FlowKit代码。

## 有界设计与兼容影响

- csv input.fcs output.csv --options selection.json复用现有gates/population；未提供这两项的CSV保持原start/count/channels和回执合同。
- 门控的scaled/compensated仍由每步定义。CSV顶层scaled/compensated只选输出视图，独立于门控视图；用原Dataset执行门控，不向结果FCS投影后重新门控。
- CSV的start/count在该群体的升序成员列表中切片；回执添加population、population_events及实际导出行的source_event_indices。它们指选中Dataset，不能冒称跨文件全局索引或经过认证的来源。
- 缺失/未知群体、坏计划、范围/列错误在创建目标前失败；合法空群体生成表头。既有数值、原始整数、C/U限制、不可覆盖输出及所有MoonBit API保持。
- 不引入CSV对其他旧单门选择器的支持，不新增群体内任意排序、布尔门、GatingML、批次平台或降维补偿语义。调用方仍可使用原subset→csv链。

## 验收与一次验证范围

独立struct/Fraction/csv消费者核对非连续成员、群体内切片、原始大整数与补偿输出的独立选择、空群体和创建前错误，另覆盖长连续成员跨CSV块边界。实际文件例程直接从已许可RepOD原文件输出inner群体的Time/FSC-A CSV，复用10轮冻结成员/CSV与源字节作为预期，不重跑旧FlowIO/全量交换。

只修改Node CSV适配、必要文档/例程/消费核验与CI。核心/公开API/桥接源码及编译JS保持，通过源身份确认，不为未变MoonBit代码重复build/Wasm或旧检查。
