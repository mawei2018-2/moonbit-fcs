# 可离线复现的 RepOD FCS 格式交换 · 0.3.0

此工作流读取保留原字节的公开数据，按明确数值区间选择事件、重排通道并交付 FCS。
原文件见 [examples/repod](examples/repod/ATTRIBUTION.md)；作者为 Bronisz, Agnieszka，
数据集 [Flow Cytometry data, RepOD V2](https://doi.org/10.18150/JOLWGT)。
文件 96804 的公开元数据逐文件指定 CC BY 4.0，文件的 MD5 与发布端一致。
原文件未修改；其 SHA256 为 `91097cd6506972e13817bfda617ffa4fd27f81d93618554417ba39346882886c`。
来源、许可和时间见 [SOURCE.json](examples/repod/SOURCE.json)。代码仍为 MIT；数据采用 CC BY 4.0。

## 原输入与显式兼容

原输入为 FCS3.1，14,320 事件、26 通道、Float32、小端。四个空段偏移字段写成 `0` 后跟空格。
[FCS3.1 规范](https://www.citometriagic.it/wp-content/uploads/2025/02/FCS_3_1.pdf) §3.2.17
明确禁止数值 TEXT 字段加空格，因此原来的拒绝行为符合此条规范。
FlowIO 1.4.0 独立读取该原文件；本库新增可选 `allow_offset_padding=true` 来提供明确的兼容入口。

默认仍拒绝；`strict=true` 不能同时开启兼容选项。仅七个段偏移字段接受首尾 ASCII 32 空格：
`$BEGINSTEXT/$ENDSTEXT/$BEGINDATA/$ENDDATA/$BEGINANALYSIS/$ENDANALYSIS/$NEXTDATA`。
每个实际修剪的字段增加一条警告。元数据查询保留原始值；其他数值字段、空格内部断开的数值、
制表符、符号、空值和整数溢出仍拒绝。偏移一致性、段重叠、矩阵长度和文件截断检查不变。
它不会修复 PANGAEA 样本中把 supplemental TEXT 指向 primary TEXT 的其他异常。

## 复现

```sh
moon build --target js --release --deny-warn
node examples/repod-selection.mjs /path/to/NEW_DIRECTORY
python tools/verify-repod-selection.py /path/to/NEW_DIRECTORY --report /path/to/NEW_REPORT.json
python tools/run-repod-consumer.py /path/to/NEW_CONSUMER_JS --target js --expected /path/to/NEW_DIRECTORY/consumer-record.json
python tools/run-repod-consumer.py /path/to/NEW_CONSUMER_WASM --target wasm-gc --expected /path/to/NEW_DIRECTORY/consumer-record.json
```

Python 独立读者固定 FlowIO 1.4.0、NumPy 2.5.3；运行库及 Node 例程不需要这两项依赖。
所有目录须不存在。纯 MoonBit 例程是独立模块，只导入公开 FCS API 和标准库 base64，
运行器把当前源码复制到新的 `moon.work`，显式选择尚未发布的 0.3.0；解包后无 `.git` 也可执行。
输入以 base64 嵌入消费模块，不使用 JS FFI 读取文件，JS/Wasm-GC 均直接调用 MoonBit 库。

筛选是原始 FSC-A 值位于 `[500000,1000000)`，输出通道依次为原索引 `[2,0,1]`。
得到 2,117 事件、3 通道；显式丢弃补偿和 ANALYSIS，保留所选通道的名称、染色、位宽、范围、增益和放大参数。
`selected.fcs` 记录 `Non-Original`；`normalized.fcs` 保留全部事件/通道，只规范化结构元数据。
二者均可用默认严格模式读取、无警告；源数据不改写，输出附原作者署名、许可及派生修改说明。

## 独立核验范围

FlowIO/NumPy 检查源 CSV 的全部 372,320 值、选择后的 6,351 值及归一化文件的全部值。
原始与归一化 DATA 字节完全相同；选择输出的 DATA 字节等于原 DATA 对所选事件/通道的逐字节投影。
同时核对通道元数据、源/输出散列及署名副本。
两个独立消费模块的完整 JSON 结果（含选择索引、所有选择值、元数据、警告和输出文件 base64）
与 Node 文件例程一致。回执见 [本次检查](evidence/repod-20260930/LOCAL-CHECKS.json)。

本例是项目编写的格式交换消费场景，不是外部实验室采用证明。它不提供补偿应用、
临床门控、诊断、FCS3.2 或全部厂商兼容性。历史 G11 的文件级授权仍未确认，
其原文件及派生文件仍不加入仓库或发行包。
