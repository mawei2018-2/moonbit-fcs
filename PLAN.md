# Forth 替换选题：FCS 数据检查与批处理

2026-09-22，在编码前确定范围。原 Forth 仓库保留，不伪装成它的兼容升级。用户已授权重写/换题；所有交付只在本地。

问题：流式细胞仪导出的 FCS 文件有二进制事件数据、通道描述和偏移索引，CSV 不能完整保留这些信息。跨仪器导入、文件偏移错误、批次通道不一致，以及筛选后仍需交付 FCS 的流程需要专门的格式工具。ISAC FCS 3.1 规范明确以跨仪器/分析软件交换为目标；FlowIO 的偏移不一致异常是已存在的工程问题。没有声称本团队已有仪器或接入客户。

检索：Mooncakes `fcs` / `flow cytometry`，GitHub `fcs moonbit` / `cytometry moonbit` / `flowio moonbit` / `flowkit moonbit`，GitLink公开索引和官方赛事公开资料。未找到直接同范围 MoonBit 文件库；radioframe 的 FCS 是帧校验字段，不是流式细胞仪数据。没有完整报名名单或全代码查询，不能保证无人开发。原始记录在工作区 `outputs/innovation-review-20260922/`。

排除方向：HEX/S-record、EDID、MARC、DBC、NMEA、UF2 均已找到可用或已有 MoonBit 同类，不再重复启动。

## 固定实现范围

1. FCS 2.0/3.0/3.1 的 list-mode 读取；little/big endian，8/16/24/32位字节对齐 unsigned integer、Float32/Float64；TEXT转义/大小写、通道元数据、DATA偏移与长度、supplemental TEXT、ANALYSIS、链式数据集。
2. 明确区分错误和可记录的非标准元数据。默认不静默修复偏移冲突；可显式接受已知 exclusive-end 错误并报告。
3. 事件/通道访问、原始值与显式 gain/log/time 预处理、有限值统计和矩形/多边形门控（边界规则文档化），输出索引可重复使用。
4. FCS 3.1 写出，保留原始事件位模式的筛选、通道重排/选择、元数据变更；涉及补偿矩阵时不静默删除信息。提供从数值事件创建 Float32/Float64 文件。
5. 可运行 CLI 完成检查、通道批次比较、CSV导出、筛选和重新写出；输入输出文件均真实读写，输出默认不覆盖。
6. MoonBit 核心与 Node 文件宿主分离；JS/WasmGC核心测试；FlowIO固定版本双向文件互通、公开参考FCS文件读取和数据导出核验；真实输入错误示例。
7. 中文README、可运行示例、来源/许可、CI配置、复审申报草稿和绑定提交的本地交付包。

不包含：仪器驱动、完整 FlowJo/GatingML、自动细胞分类、临床结论、完整 FCS 3.2、自定义压缩/非字节对齐整数/ASCII/histogram 模式。对这些格式给出明确拒绝，不冒充兼容。补偿矩阵仅验证/保留，不自动作荧光补偿。

参考：ISAC FCS3.1（https://www.citometriagic.it/wp-content/uploads/2025/02/FCS_3_1.pdf）；FlowIO（https://github.com/whitews/FlowIO，BSD-3-Clause）；FlowKit（https://github.com/whitews/FlowKit）。实现依据规范新写，FlowIO只作独立读写参考。没有复制它的解析器。
