# 0.5.0深度开发核验 · 2026-10-20

当前结果见[evidence/deep-20261020/CHECKS.json](evidence/deep-20261020/CHECKS.json)与[independent.json](evidence/deep-20261020/independent.json)。新核心测试覆盖任意宽整数、全部编码、直方图投影/宽度增长、补偿/矩阵同步、时间/放大器转换和极值几何。独立Python脚本用NumPy而非MoonBit自身作补偿参考。

下方为旧轮次的历史回执，按原版本范围阅读。

# 0.4.0本地整改验证 · 2026-10-20

本轮命令、退出码及结果见 [CHECKS](evidence/reassessment-20261020/CHECKS.json)。新增编码覆盖见 [复审材料](REASSESSMENT-20261020.md)，完整符合性边界见 [矩阵](FCS31-COMPATIBILITY.md)。新增Python核验只用标准库，不包装为FlowIO的新编码认证。

```sh
python tools/generate-standard-encodings.py --check
node tools/run-standard-encodings.mjs /path/to/NEW_DIRECTORY
python tools/verify-standard-encodings.py /path/to/NEW_DIRECTORY --report /path/to/NEW_REPORT.json
```

以下为原0.3.0及更早历史记录，原回执不覆盖0.4.0。

# 当前本地验证 · FCS 0.3.0 · 2026-09-30

本次执行记录在 [LOCAL-CHECKS.json](evidence/repod-20260930/LOCAL-CHECKS.json)；旧报告保留对应版本的历史语义。
固定工具链见 [TOOLCHAIN](TOOLCHAIN.md)。

```sh
moon fmt --check
moon info
moon check --target all --deny-warn
moon test --target js --deny-warn
moon test --target wasm-gc --deny-warn
moon build --target js --release --deny-warn
node tools/test_cli.mjs
node tools/test-request-contract.mjs
node examples/run-use-case.mjs
python tools/reference_check.py --reference-dir /path/to/PINNED_FLOWIO --report /path/to/NEW_REFERENCE.json
node examples/repod-selection.mjs /path/to/NEW_DIRECTORY
python tools/verify-repod-selection.py /path/to/NEW_DIRECTORY --report /path/to/NEW_REPORT.json
python tools/run-repod-consumer.py /path/to/NEW_CONSUMER_JS --target js --expected /path/to/NEW_DIRECTORY/consumer-record.json
python tools/run-repod-consumer.py /path/to/NEW_CONSUMER_WASM --target wasm-gc --expected /path/to/NEW_DIRECTORY/consumer-record.json
moon package --frozen
```

独立 Python 工具需 FlowIO 1.4.0 和 NumPy 2.5.3。公开回归输入取自 FlowIO 固定提交
`83d28a22d42235c10d17afb017250ee208afed95`；G11 的文件级授权仍未确认，不在本库分发。
新增 RepOD 输入位于 examples/repod，逐文件 CC BY 4.0、原字节未改、署名与许可随输出保留。
两个新核心测试覆盖默认/严格拒绝、显式兼容、原始元数据、规范回写、整数溢出和偏移重叠/冲突。
RepOD 独立对照覆盖全部源/选择值和原始 DATA 位模式；分离消费模块只调用公开 API，详情见 [REPOD-EXCHANGE](REPOD-EXCHANGE.md)。
本次使用本机 Python 的独立环境，不把它称为 CI 的 Python 3.12 或新远端 CI 成功。

## 历史验证说明

# 工具链固定版本更新（2026-09-28）

已将 .moonbit-version 更新为 0.10.14+7d59c7ec9。moon update、格式检查、JS check、JS/Wasm-GC 测试（各15项）、release JS 构建、moon info 和生成接口差异检查均通过。CLI检查通过11项，请求契约检查通过38项，node examples/run-use-case.mjs 运行完成。编译器报告16条 implicit_impl_as_method 弃用警告；CI未将警告设为失败。

本次更新未重跑 FlowIO 独立参照检查。本机只有 Python 3.14.4，没有 CI 使用的 Python 3.12；外部格式互通结果仍以单独标注日期的既有回执为准。

## Earlier 0.2.0 verification and reproduction

Earlier local verification used Moon 0.1.20260904, moonc 0.10.12+1634b282e, Node 24.11.0, FlowIO 1.4.0, and NumPy 2.5.3; that run passed 15 JS/Wasm-GC test blocks and 11 CLI groups. Compiler versions may change diagnostics or generated code, so generated-file byte hashes are not promised across versions.

```sh
moon check --target js
moon test --target js
moon test --target wasm-gc
moon build --target js --release
node tools/test_cli.mjs
node examples/run-use-case.mjs
python tools/generate_fixtures.py
moon fmt
moon info
```

合成夹具用 Python标准库生成，新增主/补充TEXT和ANALYSIS尾部填充。核心测试核对数据原始字节、值内部空格、转义、声明段重叠及错误拒绝；不是只有写出再读回的自洽检查。CLI测试从正常文件构造声明长度带空格的输入，验证默认拒绝、显式诊断、规范重写和输出拒绝覆盖。

## 独立 FlowIO 验证

建议在独立 Python 环境安装固定开发依赖：`python -m pip install flowio==1.4.0 numpy==2.5.3`。运行项目本身不依赖 Python。

```sh
python tools/reference_check.py
```

以上执行合成文件的双向写读、事件筛选、通道重排及补偿元数据检查。公开样本需另取官方仓库，固定提交后运行：

```sh
git clone https://github.com/whitews/FlowIO.git flowio-reference
git -C flowio-reference checkout --detach 83d28a22d42235c10d17afb017250ee208afed95
python tools/reference_check.py --reference-dir flowio-reference --report reference-current.json
```

脚本会核对参考 HEAD，不接受任意上游版本。当前 [reference.json](evidence/text-padding-20260923/reference.json) 是实际执行报告：三个原兼容文件加上显式选项读取的 G11，共1,488,004个值与参考一致；G11重写还逐字节比较DATA，并用FlowIO回读选择后的事件。其他异常文件继续验证拒绝。

`reference-results.json` 保留0.1.0的历史报告，不能用其中G11拒绝记录解释0.2.0显式兼容行为。当前报告记录相关源码和生成引擎SHA256，公开仪器文件与患者/研究者元数据不随本仓库再分发。CI配置已添加固定公开样本检查；尚未推送，故本次结果是本地检查而非远端CI运行证明。


## 0.2.1 请求边界与公开文件交换

修正 JS JSON 入口的小数事件/通道索引被通用整数解码器截断的问题；dataset/start/count/x/y/events/channels 必须是精确32位整数。多个事件选择器同时出现会拒绝，避免静默忽略 events。命令行选项采用严格 UTF-8 解码。MoonBit 格式解析、几何选择及写出算法未改动。

新增固定公开 G11 的数值区间选择→三通道 FCS→FlowIO 回读任务，明确丢弃不适用的补偿和分析段，保留对应通道元数据，输出源/结果散列与完成清单。见 [PUBLIC-SELECTION.md](PUBLIC-SELECTION.md)。区间仅用于可复现格式交换，不是生物学判定。当前证据在 evidence/request-20260927；0.2.0 报告保留历史语义。
