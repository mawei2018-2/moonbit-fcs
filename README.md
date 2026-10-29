# MoonBit FCS 0.5.0

MoonBit FCS 是面向流式细胞术文件的数据准备核心：读取 FCS、按明确规则选择事件和通道、计算群体统计，并交付可独立读取的 FCS、CSV 和 JSON。格式解析、整数位流、门控、矩阵及统计由 MoonBit 实现；Node.js 提供文件与命令行入口。

当前模块为 **`mawei2018-2/fcs`**，维护与申报账号为 **mawei2018-2**，源码仓库为 [mawei2018-2/moonbit-fcs](https://github.com/mawei2018-2/moonbit-fcs)。代码采用 MIT 许可。本文对应 0.5.0 源码；使用下述源码构建与工作区方式，包注册表发布状态单独核实。正式项目介绍见 [PROPOSAL.md](PROPOSAL.md)。

## 构建与开始使用

按 [TOOLCHAIN.md](TOOLCHAIN.md) 使用 `.moonbit-version` 固定的 MoonBit 工具链，并准备 Node.js ≥22。核心支持 JS 和 Wasm-GC，CLI 使用 JS 构建产物。Python、FlowIO 和 NumPy 仅用于开发验证。

在仓库根目录执行，所有输出路径须尚不存在：

```sh
moon update
moon check --target js --deny-warn
moon build --target js --release --deny-warn
node tools/fcs.mjs create NEW.fcs --options examples/gate-plan-events.json
node tools/fcs.mjs inspect NEW.fcs
node tools/fcs.mjs population-stats NEW.fcs --options examples/population-stat-window.json
```

该例创建含 65 位整数 ID 的数据，按命名群体选择成员窗口并输出统计。`population_events` 保留完整群体数，显式窗口的 `events` 表示实际参与统计的事件数，`source_event_indices` 对应原 Dataset 行号。

## 数据能力

| 场景 | 能力与入口 |
|---|---|
| 文件读取与检查 | 读取 FCS2.0/3.0/3.1、I/A/F/D 列表数据及 C/U 直方图；检查段、偏移、通道和补偿元数据。`inspect`、`validate`、`metadata` 提供结构与读取报告。 |
| 精确整数 | BigInt 和十进制文本保留原始整数，支持非字节对齐及超过 64 位的位流；`integer_value`、`integer_text`、`rectangle_exact` 提供精确访问与选择。I 类型按 PnR 有效位读取。 |
| 命名群体 | `gate_plan` 与 `populations` 组合矩形、多边形及精确整数条件，支持单父层级、前向父引用和分支，保留原事件索引、父群体及总群体比例。 |
| 数值视图与统计 | 原值、线性缩放、补偿视图可分别用于门控和输出。`population-stats` 支持群体窗口、指定通道及重排，报告有限/非有限计数、极值、均值和样本方差。 |
| FCS 交换 | `create`、`subset`、`rewrite` 写出 FCS3.1，同步所选通道元数据与补偿矩阵。不可表示的转换明确失败，失效 ANALYSIS 须显式处理。 |
| 链式 Dataset 交付 | `extract-datasets` 将完整 NEXTDATA 链拆为独立 FCS3.1 和 manifest，记录输入与输出哈希、源 Dataset 偏移、模式及实际读取警告。 |
| CSV 交接 | `csv` 可直接导出群体窗口、精确原始整数、可选源索引及多个群体的成员列；`population-report` 交付多样本×群体计数及比例表。 |
| 直方图 | 精确频数、轴重排及 C 模式边缘分布；旧 `$COMP` 按保留轴映射行列并保留系数文本，不应用于 DATA。 |

通道可按数字位置或精确 PnN 名称引用。重复 PnN 的兼容读取带警告，名字歧义会失败；数字位置仍可用于已读取数据的重写。新建文件要求唯一非空名称。整数位宽受 Bytes、索引及运行时可表示范围约束，没有以 64 位或 1024 位作为产品上限。

## 可运行工作流

- [命名门控计划](GATE-PLANS.md)：群体选择、父子计数、原始索引与精确整数 ID。
- [具名通道](NAMED-CHANNELS.md)与[RepOD 交换](REPOD-EXCHANGE.md)：许可原文件到群体 FCS、CSV 及独立读者的完整交接。
- [群体统计](POPULATION-STATS.md)：成员窗口、输出通道、实际补偿依赖与可选输入读取来源报告。
- [直接群体 CSV](POPULATION-CSV.md)：窗口及源行号；[成员列示例](examples/population-columns/README.md)演示仅凭 CSV 消费群体关系。
- [多样本群体报告](POPULATION-REPORT.md)：共享门计划、逐样本读取选项、来源与父/总群体比例。
- [完整 Dataset 抽取](EXTRACT-DATASETS.md)：链式输入、独立文件清单及仅读最终交付文件的接收程序。
- [重复通道位置写出](DUPLICATE-WRITE.md)与[格式兼容范围](FCS31-COMPATIBILITY.md)：兼容读取、重编码、直方图及元数据规则。

CLI 的 JSON 选项通过 `--options FILE.json` 传入。报告和写文件回执输出到 stdout，异常写到 stderr；退出码 0 为命令正常执行、1 为异常，`compare` 返回 2 表示所列结构/校准字段不兼容。调用方仍须检查报告字段和 warnings。

输出要求新路径。Dataset 抽取和多样本报告在规划、读取及计算成功后才创建目标；普通 IO 失败可能留下部分目录。CSV 的可选 `--atomic-output` 在关闭同目录暂存文件后以不覆盖目标的硬链接发布最终名称，需要文件系统支持；发布后暂存清理失败会返回明确成功告警。这些接口不提供掉电持久性或多文件事务。

## MoonBit 公共 API

入口包括 `parse(Bytes, ...)->Dataset raise FcsError`、`parse_all`、`create`、`create_histogram`，以及 Dataset 的数值、统计、门控和 `write` 方法。完整签名见 [pkg.generated.mbti](pkg.generated.mbti)。

项目内的独立消费者使用当前模块导入。在仓库根目录运行下列命令，消费者的 `moon.work` 将本源码和调用模块放入同一工作区，无需把新命名空间安装为注册表包：

```sh
cd examples/gate-plan-consumer
moon run . --target js --deny-warn
moon run . --target wasm-gc --deny-warn
```

消费者的 `moon.mod` 依赖为 `mawei2018-2/fcs@0.5.0`，`moon.pkg` 导入为 `mawei2018-2/fcs`。另见[具名通道消费者](examples/named-channel-consumer)和[独立 RepOD 消费者](examples/repod-consumer)；这些是项目自编集成例程。

## 数值与使用范围

原始 I/A 值在 CLI 默认用精确字符串交付；`exact_integers:false` 显式选择 Double。缩放、统计和补偿使用 Double，不保证任意大整数精度。补偿按测量行向量 M×S⁻¹ 计算，奇异或不可表示的逆矩阵报错；写回仍保留未补偿 DATA。补偿视图包含线性缩放，没有补偿矩阵时退回缩放，回执的 `compensated` 表示视图选择。

群体窗口按成员位置切片，不按 Time 排序；空群体无均值，单例无样本方差。C/U 使用直方图 API，不接受列表门控和事件统计。`compare` 检查所列模式、通道及校准字段，不证明生物面板、样本来源或全部元数据等价。

API 接收内存 Bytes，CLI 读取整个文件。兼容偏移填充等须显式选择，strict 与兼容选项不能混用。范围不含 FCS3.2、CRC 验证、全部厂商异常、GatingML/FlowJo 导入、自动门控、降维或临床诊断。

## 验证、来源与许可

[CI 工作流](.github/workflows/ci.yml)执行双端核心回归、CLI、独立字节/有理数真值、FlowIO 读取及独立消费者检查；具体提交的远端结果见 [GitHub Actions](https://github.com/mawei2018-2/moonbit-fcs/actions)。[CI-PLAN.md](CI-PLAN.md)说明验证职责，历史验证文档与 `evidence/` 保留各自当时的源码和环境身份。

项目由 mawei2018 原账号的 FCS 源码和贡献历史延续，当前由 mawei2018-2 维护。旧换题说明、账号命名申报稿和历史记录中的旧账号、模块名属于原始来源记录；现行接口及申报介绍以本文和 [PROPOSAL.md](PROPOSAL.md)为准。根 [LICENSE](LICENSE) 的版权声明及 Git 作者历史保留。

代码与原创合成向量采用 MIT；第三方标准库和开发参考分别遵循其许可。附带 RepOD 文件 96804 及派生数据采用 CC BY 4.0，保留 Bronisz 署名、DOI 10.18150/JOLWGT、许可及修改说明。标准 PDF 与未确权仪器文件不随源码分发，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。本项目提供 MoonBit 数据交换实现与验证例程，不主张门控算法首创、生态唯一、外部实验室采用或临床有效性。
