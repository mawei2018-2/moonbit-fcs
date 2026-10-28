# 事件选择后保留通道信息再交付 FCS

在导入前核对通道和事件矩阵，将选中的事件与通道写回可交换 FCS，避免只导出 CSV 后丢失通道元数据。

## 输入、操作、输出

原创 4 事件样例；输出是格式交换数据，不是临床分析或真实用户证明。

最简运行：先按 README 构建，然后 `node examples/run-use-case.mjs`。它自动创建输出目录并执行下面命令。下列 `{out}` 是运行器替换的实际目录，不是直接输入 shell 的变量；stdin 文件由运行器传递，以避免 Windows 与 POSIX 重定向差异。

```text
node tools/fcs.mjs create {out}/events.fcs --options examples/events.json
node tools/fcs.mjs subset {out}/events.fcs {out}/selected.fcs --options examples/gate.json
node tools/fcs.mjs csv {out}/selected.fcs {out}/selected.csv
node tools/fcs.mjs inspect {out}/selected.fcs
```

观察：选出 FSC-A 在 [15,35) 的两个事件并保留两个指定通道；CSV 和 FCS 均可交付。

每一步输出见实际目录下 `step-N.stdout.txt` / `step-N.stderr.txt`；0.1.0的历史回执见 `evidence/value-rework-20260922/use-case.json`。

## 为什么保留这个实现

已有 FCS 输入、需要事件/通道选择后继续交付格式文件时评估；不是为取代成熟 Python 科研工具而强造需求。

FlowIO/FlowKit 等成熟 Python 工具已解决这类交换问题。本项目贡献是 MoonBit 可复用实现与 JS/WasmGC 数据准备接口，未发现同范围公开 MoonBit 包不等于证明生态空白。

## 不能由样例推出的结论

尚无明确实验室使用方；不做补偿应用、自动分类、FCS3.2 或临床分析。部分厂商文件明确不兼容，完整数据上限及拒绝样例见使用文档。

该样例是可修改的使用入口，不能证明存在真实用户、全部兼容或性能领先。继续投入的依据应是明确的输入或接入需求；若对接任务用既有成熟库即可完成，应优先复用而不是为保留参赛数量扩张本项目。


## 0.2.0 公开样本兼容与重写

新增入口见 [COMPATIBILITY.md](COMPATIBILITY.md)：显式读取尾部填充TEXT、先检查逐段警告，再重写到新文件并严格验证。公开G11样本的全部69,420个值、DATA原始字节及选择后结果均已与FlowIO对照；这项输入兼容证据独立于上述四事件原创示例。当前完整验证见 [TESTING.md](TESTING.md)。


## 0.2.1 请求边界与公开文件交换

修正 JS JSON 入口的小数事件/通道索引被通用整数解码器截断的问题；dataset/start/count/x/y/events/channels 必须是精确32位整数。多个事件选择器同时出现会拒绝，避免静默忽略 events。命令行选项采用严格 UTF-8 解码。MoonBit 格式解析、几何选择及写出算法未改动。

新增固定公开 G11 的数值区间选择→三通道 FCS→FlowIO 回读任务，明确丢弃不适用的补偿和分析段，保留对应通道元数据，输出源/结果散列与完成清单。见 [PUBLIC-SELECTION.md](PUBLIC-SELECTION.md)。区间仅用于可复现格式交换，不是生物学判定。当前证据在 evidence/request-20260927；0.2.0 报告保留历史语义。
