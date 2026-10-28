> 历史说明存档：2026-09-22 价值复核之前的 README 原文。旧版本、路径、无 remote 等状态描述不代表当前状态；当前入口为 [README](README.md)。保留其中的完整 API 用法和历史验证细节，不据旧条目宣称本轮重新通过。

# MoonBit FCS · 流式细胞仪数据检查与批处理

读取 FCS 事件文件，核对批次通道，按门控筛选事件，并输出 CSV 或保留事件原始字节的 FCS 3.1。二进制解析、统计、门控及写出均由 MoonBit 完成；Node 只处理文件、JSON 和命令行。

这是一个有明确范围的**数据准备库**。跨仪器交换的数据带有通道、放大参数和补偿矩阵，直接转 CSV 会丢掉这些描述。本项目把检查、筛选和可互操作写出放在同一条本地流程中。没有声称已接入实验室、存在本团队客户，或发明 FCS/门控算法。

## 快速运行

需要 MoonBit 工具链和 Node 22+，核心无第三方运行时依赖。在仓库根目录执行：

```sh
moon build --target js --release
node tools/fcs.mjs create demo.fcs --options examples/events.json
node tools/fcs.mjs inspect demo.fcs
node tools/fcs.mjs subset demo.fcs selected.fcs --options examples/gate.json
node tools/fcs.mjs values selected.fcs
node tools/fcs.mjs csv selected.fcs selected.csv
node tools/fcs.mjs compare demo.fcs selected.fcs
```

示例生成 4 个事件，按 `FSC-A ∈ [15,35)` 选出 2 个事件并保留前两个通道：`[[20,4],[30,8]]`。最后一步返回退出码 2，因为两个文件的通道不同，这正是批次检查应报告的问题。示例是可复现合成数据，不冒充临床/实验数据。输出路径必须不存在；换一个名字即可重复运行。

`inspect`/`validate` 会报告元数据警告；`stats` 输出各通道有限值统计；`metadata` 查看完整元数据；`values` 分块取事件；`gate` 返回可复用的事件索引；`rewrite` 重新写出独立 FCS 文件。`--help` 列出命令。

## 库接口

```moonbit
let data = @fcs.parse(bytes)
let indices = data.rectangle([{ channel: 0, lower: 15.0, upper: 35.0 }])
let output = data.write(event_indices=indices, channel_indices=[0, 1])
```

索引从 0 开始。`parse_all` 支持相对 HEADER 偏移的多数据集链；`value`、`statistics`、`rectangle`、`polygon` 默认用原始数值。显式 `scaled=true` 应用 gain/log/time 预处理，不自动应用补偿矩阵或 logicle。整数值按 `$PnR` 所需位数屏蔽填充高位；FCS 写出仍复制原始位模式，包括负零、NaN 和整数填充位。`create` 从事件优先排列的有限数值创建 Float32/Float64 文件。

矩形为下界包含、上界不包含；多边形用偶奇规则，精确浮点边界点包含，不使用 epsilon。两者排除非有限值；多边形坐标绝对值上限为 `1e100`。统计跳过并计数 NaN/Infinity，方差为样本方差 `n-1`；空集/单个样本的不可用统计以及数值溢出显示 None。读取到的结构只读，数组访问器返回副本。

## 支持范围及保护

| 能力 | 范围 |
|---|---|
| FCS 读取 | 2.0/3.0/3.1 list mode；大小端；8/16/24/32 位字节对齐无符号整数、Float32、Float64 |
| 元数据 | 大小写无关键、UTF-8 值、分隔符双写转义、补充 TEXT、ANALYSIS、数据集链 |
| 校验 | 段偏移、长度、重叠、事件形状、通道、补偿矩阵引用；typed errors |
| 写出 | 独立 FCS 3.1、事件筛选/重排、通道筛选/重排、非结构元数据更新 |
| 批次检查 | 通道顺序/名字/染色/位宽/范围/放大、数据类型、TIMESTEP、SPILLOVER 完整描述对比；按元数据文本保守比较，不作数值归一 |
| 限额 | 文件 256 MiB、1024 通道、800 万样本值、TEXT 2 MiB/4096 对、64 数据集、128 维补偿矩阵 |

默认不猜测 HEADER/TEXT 的 DATA 偏移冲突。`allow_exclusive_end=true` 只显式接受两处偏移一致、但 DATA 终点多写一字节的已知错误，并产生警告。`latin1=true` 显式允许旧厂商文本的 UTF-8 解码失败回退到 Latin-1；不自动猜测中文本地编码。`strict=true` 禁止这种回退，并将已实现的缺失字段/非规范放大警告提升为错误；**strict 不是完整 FCS 认证器**。

默认模式允许缺失 PnE 时按线性处理并警告；FCS 3.1 建议的 `PnE=f1,0` → `f1,1` 兼容修正也有警告。非正 gain 只允许原始值访问，缩放拒绝；Time 通道用 TIMESTEP，不套用放大 gain。

删除补偿矩阵引用的通道必须显式 `drop_spillover=true`；旧 `$COMP` 遇到通道变换也要求显式删除。改变事件/通道且含 ANALYSIS 时必须 `drop_analysis=true`，防止把旧分析结果当成新结果。写出保留已解析的未知关键字及 Pn 描述，设置 `ORIGINALITY=Non-Original`，重算段偏移，去除失效 CRC 和旧 UNICODE 声明。**未知厂商二进制尾段不保留，未知关键字的科学含义不作自动修正**，重用厂商分析前应核查它们。

不支持 FCS 3.2、ASCII/histogram、非字节对齐整数、厂商压缩、完整 FlowJo/GatingML、自动细胞分类。没有自动荧光补偿。CSV 非有限值按 `NaN`/`Infinity` 输出；CSV 是普通文本交换，不是电子表格公式净化器。

## 已运行验证

```sh
moon test --target js
moon test --target wasm-gc
moon build --target js --release
node tools/test_cli.mjs
python -m pip install flowio==1.4.0 numpy==2.5.3
python tools/reference_check.py
```

`fixtures_wbtest.mbt` 来自独立 Python struct 布局脚本，覆盖两种字节序、整数掩码/混合位宽、IEEE 位模式、段/数据集、边界门控、统计、错误输入及逐字节截断。`reference_check.py` 检查 FlowIO→MoonBit→FlowIO 门控/通道重排、补偿信息，以及 MoonBit Float32/64 大端输出。

公开文件复查需要单独取得 [FlowIO](https://github.com/whitews/FlowIO) 的提交 `83d28a22d42235c10d17afb017250ee208afed95`，再运行：

```sh
python tools/reference_check.py --reference-dir /path/to/FlowIO --report reference-results.json
```

本地实际结果见 [reference-results.json](reference-results.json)：`100715.fcs`（65016×16）、`3FITC_4PE_004.fcs`（94569×4）、`variable_int_example.fcs`（2×26）的 **1418584 个值全量一致**，筛选后的原始值也通过 FlowIO 回读。两个 HEADER/TEXT 偏移冲突样本按预期拒绝。

另有三种厂商异常尚未兼容：`data1.fcs` 的不成对 TEXT、`G11.fcs` 的 TEXT 尾空格、`B01 KC-A-W---91-US.fcs` 的 supplemental TEXT 指向主段。它们被明确拒绝；通过三个文件不代表所有仪器软件兼容。

## 选题、来源与申报

查重范围和现有 Python 工具的关系见 [DUPLICATION.md](DUPLICATION.md)；客观申报草稿见 [PROPOSAL.md](PROPOSAL.md)。Forth 原仓库单独保留，本项目是用户授权的换题候选，不是 Forth 的兼容版本升级；报名是否允许换题和最终审核由赛事决定。

实现依据 [ISAC FCS 3.1 规范](https://www.citometriagic.it/wp-content/uploads/2025/02/FCS_3_1.pdf) 新写；没有复制 FlowIO 解析器。FlowIO 1.4.0 作为独立参考，FlowKit 说明邻接应用生态。第三方引用和许可见 [THIRD_PARTY.md](THIRD_PARTY.md)。本项目 MIT。
