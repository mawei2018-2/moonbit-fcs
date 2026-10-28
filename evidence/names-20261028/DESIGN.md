# 10轮设计：按PnN寻址的可移植门控与真实交换

## 已确立的证据与选择

H10-1是使用缺口：同一组通道仅改变物理顺序，数字计划按其索引合同选择不同列，这是旧API正确行为，不能计作缺陷。当前名字作为通道引用会被数字解码器拒绝。H10-3是真错：values count0/channels[99]退出0输出[]；合法channels[0]同样输出[]，必须区分两者。原始日志已保留。

H10-2先用已有数字能力执行许可RepOD原文件的层级计划与FlowIO回读，属于真实流程正对照。初设SSC区间不匹配该文件约1.16e6..2.47e6的实际数值，非空断言是演示预设错误，不是产品失败；原脚本和条件保留，并另行验证原空结果。选择可见数值区间不裁掉源数据，不作为修复。

选择有限拓展：精确PnN名字寻址，接通计划谓词与输出列选择，避免面板换序后的手工映射。不是新格式、跨样本平台或自动分类；修复顺带由统一引用校验覆盖的count0越界漏检。

## 生态与一手依据

复用09在同一工作会话完成的Mooncakes实时fcs/cytometry/gating查询及GitHub专门检索（09/RESEARCH.md和MOONCAKES-LIVE.json）；不冒称为10轮重新全量查重。尚未发现另一个同范围MoonBit FCS库，不能证明生态唯一。
[FlowKit Dimension](https://flowkit.readthedocs.io/en/latest/dimension.html)已用PnN标签标识测量维度；[FlowIO官方教程](https://flowio.readthedocs.io/en/latest/notebooks/flowio_tutorial.html)明确pnn_labels顺序对应数据列。本轮不是命名寻址算法创新，价值是已有MoonBit交换核心的可复用解析、严格歧义错误和完整第三方交付链。未复制代码或样本。

## 实现与兼容合同

1. 新增Dataset.channel_index(name)；精确、区分大小写地匹配PnN，不修剪、不把PnS当别名、不把数字字符串转成数字索引。缺失/歧义报FcsError，重复PnN文件仍可按数字索引使用，不全局拒绝。
2. gate计划中bounds的通道、polygon的x/y和integer_bounds.channel可用整数或PnN字符串。原GatePredicate/GateStep类型和gate_plan签名保持，程序调用者用channel_index构造原有Int谓词。
3. CLI values/subset/rewrite/csv的channels列表可混合整数/名字。所有引用在请求执行前验证；空值语义保持各命令原合同（values null拒绝，transform/CSV null使用默认通道）。旧单门谓词和histogram标量channel/axis仍按数字合同，本轮不扩大这些接口。
4. count0仍返回[]，但不能绕过非法通道。CSV未知/歧义列必须在创建文件前失败。名字解析由MoonBit完成，Node保持IO职责。
5. 新增可离线运行的RepOD命名计划和文件例程：原文件显式启用偏移空格兼容并记录警告；按FSC-A/SSC-A分层门控，按SSC-A/FSC-A/Time导出，明确drop分析/补偿，保留原始未补偿DATA、来源和CC BY4.0署名。固定数值条件只是格式交换示例，无生物学或临床解释。

## 验收

真实before/after漏检日志；名字/换序/数字同名/缺失歧义/合法空表核心双端；原09计划、原CLI请求合同受影响处回归一次。独立合成字节与精确值检查名字/数字混合、空行越界及错误前无输出。公开MoonBit消费双端一致。真实RepOD命名计划→导出→FlowIO原值回读，并用源DATA字节投影、NumPy独立成员条件和具名CSV列复核；只核对新选择的结果，不复跑旧372320全集/下载链。校准README、<=30行PROPOSAL、来源/编译身份、新ZIP全成员回读后才complete。
