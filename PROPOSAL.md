# MoonBit FCS：精确事件选择与可追溯数据交换

申报与维护账号：**mawei2018-2**。源码仓库：[mawei2018-2/moonbit-fcs](https://github.com/mawei2018-2/moonbit-fcs)。模块：**`mawei2018-2/fcs`**，源码版本 **0.5.0**，代码许可 **MIT**。

## 项目定位

MoonBit FCS 为 MoonBit 数据工具开发者提供流式细胞术 FCS 数据准备核心，连接文件读取、明确规则分组、统计与 FCS/CSV 交付。典型场景是读取仪器导出文件，选择目标事件和通道，保留来源与数值身份，交给下游脚本继续处理。核心可编译至 JS 和 Wasm-GC；Node.js 负责文件与命令行接线，运行不依赖 Python。

项目的贡献是可组合的 MoonBit 格式、精确整数与元数据交换实现，以及从命名群体到独立文件接收者的完整工作流。FlowIO、FlowKit 等已有成熟 Python 方案，本项目不主张门控算法首创或生态唯一。

## 核心功能

- **读取与精确访问**：读取 FCS2.0/3.0/3.1 的 I/A/F/D 列表数据和 C/U 直方图，解析段、通道及补偿元数据。BigInt 和十进制文本保留原始整数，支持非字节对齐和超过 64 位的精确选择；I 类型按 PnR 有效位读取。
- **命名群体与数值视图**：矩形、多边形、精确整数谓词及 AND/OR/NOT 群体引用组成完整依赖图，每步仍可声明一个父群体限制。前向引用、分支组合和后续几何门返回源事件索引、父/总群体计数及比例。通道支持数字或精确 PnN 名称，名字歧义明确失败；在源几何门和输出分别选择原值、缩放或补偿视图。
- **统计与多样本报告**：群体统计按成员位置取窗口，可选择和重排输出通道，保留完整补偿矩阵及实际测量依赖，报告有限/非有限计数、极值、均值和样本方差。可选概率数组附带有限观测的线性 type-7 中位数和分位数，保留原窗口/视图，默认报告不变。还可附带原输入哈希、所选 Dataset、原版本及实际读取警告。多样本共享门计划直接交付样本×群体计数 CSV。
- **FCS 与直方图交换**：创建、选择或换序后写出 FCS3.1，同步通道元数据与补偿矩阵；不可表示转换明确失败，失效 ANALYSIS 须显式处理。C/U 提供精确频数、轴重排与 C 边缘分布，旧 `$COMP` 按保留轴映射行列并保留系数文本。已兼容读取的重复 PnN 数据可按数字位置重写。
- **可追溯文件交付**：完整 NEXTDATA 链可抽取为独立 FCS3.1 与 manifest，记录源 Dataset 偏移、模式、读取警告及每份输出哈希。CSV 可直接导出群体窗口、精确原始整数、可选源行号和多个群体成员列，便于仅读 CSV 的接收者统计交集并保留事件关联。

## 可复现用法

按 [TOOLCHAIN.md](TOOLCHAIN.md) 使用固定 MoonBit 工具链及 Node.js ≥22，从源码构建。输出路径须尚不存在：

```sh
moon update
moon build --target js --release --deny-warn
node tools/fcs.mjs create NEW.fcs --options examples/gate-plan-events.json
node tools/fcs.mjs population-stats NEW.fcs --options examples/population-stat-window.json
```

该例创建含 65 位 ID 的文件，取命名群体第二名成员进行统计：原事件索引为 5，完整群体有 2 个事件，实际窗口有 1 个事件，报告 M/X/M 通道。公共 MoonBit 调用方在 `moon.mod` 依赖 `mawei2018-2/fcs@0.5.0`，在 `moon.pkg` 导入 `mawei2018-2/fcs`；[源码消费者](examples/gate-plan-consumer)通过工作区解析本地模块，包注册表发布状态须另行核实。

[README.md](README.md)提供完整命令、API 与使用范围；[布尔群体](BOOLEAN-GATES.md)、[群体统计](POPULATION-STATS.md)、[多样本报告](POPULATION-REPORT.md)、[群体 CSV](POPULATION-CSV.md)及[Dataset 抽取](EXTRACT-DATASETS.md)提供可执行合同与文件接收例程。

## 工程验证与边界

核心、CLI 和项目自编独立消费者由 [CI](.github/workflows/ci.yml)覆盖，包括 JS/Wasm-GC 回归、独立字节/有理数真值、FlowIO 回读与许可 RepOD 交换。验证结果须关联具体提交、输入及编译产物；实际远端执行结果见[仓库 Actions](https://github.com/mawei2018-2/moonbit-fcs/actions)。项目自编消费者证明接口可消费性，不代表外部实验室采用。

布尔群体使用同一 Dataset 的最终成员集合，NOT 取补集后再与声明的父群体求交，可能包含被源数值门排除的非有限观测。未知引用和混合循环使完整计划失败；布尔步骤不选择数值视图。公共 `GatePredicate` 新增构造器，外部穷尽匹配须补充分支，现有几何输入和 Population 结果模式保持。

缩放、补偿和统计采用 Double，不保证任意大整数精度；补偿按测量行向量 M×S⁻¹ 计算，写出 DATA 保持未补偿值。群体窗口按成员位置切片，空群体无均值、单例无样本方差。C/U 使用直方图接口，不接受列表门控或事件统计。比较检查不证明样本来源或生物面板等价。

有限观测的补偿点积若在乘加中间溢出，会用实际 binary64 观测与缓存逆矩阵系数的精确乘积和恢复最终舍入结果，避免本来有限的事件从群体和统计中消失。正常有限路径、真实非有限观测和零系数依赖规则保持；不承诺精确实数求逆或恢复此前舍入。[补偿数值合同](COMPENSATION-NUMERICS.md)提供完整位模式与文件交接例程。

处理基于内存 Bytes，CLI 读取整个输入文件。抽取与多样本报告先完成规划和计算，再创建新目标，普通 IO 失败仍可能留下部分目录。CSV 可选在写完后以同目录硬链接独占发布最终名称，须有文件系统支持；这不提供掉电持久性或多文件事务。

支持范围不含 FCS3.2、CRC 验证、全部厂商异常、GatingML/FlowJo 导入、自动门控、降维或临床诊断。兼容读取须显式选择并检查实际 warnings；哈希及源行号用于交付对应关系，不构成来源认证。

## 来源与许可

当前项目由 mawei2018 原账号的 FCS 源码和贡献历史延续，维护与申报账号为 mawei2018-2。根 [LICENSE](LICENSE) 的原版权声明及 Git 作者历史保留；历史换题说明、原申报稿与取证记录中的旧账号和旧模块名作为来源记录保留。

代码和原创合成向量为 MIT，标准库依其自身许可，FlowIO/NumPy 开发参考依其 BSD 许可。附带 RepOD 文件 96804 及派生物为 CC BY 4.0，保留 Bronisz 署名、DOI 10.18150/JOLWGT、许可和修改说明。标准 PDF 及未确权仪器数据不分发，完整说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。
