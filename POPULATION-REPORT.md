# 多样本群体计数报告

同一显式门计划用于多个采集文件时，`population-report`把现有MoonBit `gate_plan`结果交付成一张CSV，供下游按样本/群体透视计数或比较频率。它完成文件清单到实际报告的接线，不增加门控模型、统计量或自动分类。单样本`populations`、事件CSV成员列和群体统计的参数/输出保持。

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs population-report examples/population-report/samples.json out.csv --options examples/population-report/gates.json
python examples/population-report/receive.py out.csv --expected examples/population-report/expected.json
```

输出路径须不存在。示例接收方只读CSV和独立预期，核对所有字段后生成样本×群体计数透视，并按band总群体比例排序；这是实际可消费性证据，不是外部采用或临床验证。

清单是只含`samples`的对象，数组须非空，例如：

```json
{"samples":[
  {"sample":"donor A","file":"a.fcs"},
  {"sample":"donor B","file":"linked.fcs","dataset":1}
]}
```

`sample`须为唯一的非空字符串，`file`须为非空字符串。保留大小写、空格和Unicode；不按文件名猜样本身份。同一文件可用不同样本ID和Dataset列出。相对文件路径以**清单目录**为基准，绝对路径也可用；CSV的source_file保留清单中的原拼写。`--options`路径及输出路径仍相对调用目录，遵循原CLI用法。

共享options只接受非空`gates`和既有读取键`dataset/strict/allow_exclusive_end/latin1/allow_text_padding/allow_offset_padding`。每个样本也可带这些读取键，覆盖公共默认值，包括显式`dataset:0`和布尔`false`。Dataset须为非负32位整数，标志须为布尔值；省略仍采用原读取默认。严格读取与显式兼容开关的既有冲突规则保持，实际警告随报告交付。其余清单/样本/options键报错，避免将拼写错误或未使用的窗口/视图悄悄当成有效请求。

门计划仍使用原`gates:[{id,parent?,bounds|vertices|integer_bounds,...}]`。缩放/补偿标志属于各门步骤；不接受顶层scaled/compensated、单一population筛选、start/count或事件成员列。所有样本使用同一计划，但可以有不同通道顺序/字节序；具名通道按各源的实际PnN解析。数字通道索引仍按各源的原位置解释。此命令不自动证明面板、校准或生物学含义相同；需要结构检查时先使用原`compare`。

固定列为：

| 列 | 含义 |
|---|---|
| sample / source_file | 清单中的样本ID / 原路径字符串 |
| source_sha256 / dataset | 实际加载的完整原文件SHA-256 / 所选零基Dataset |
| source_version / read_warnings | 所选原Dataset的版本 / 实际warnings数组的JSON字符串 |
| population / parent | 原群体ID / 父ID，根群体为空 |
| count / parent_count / total_count | 群体、父群体和所选Dataset事件数 |
| parent_fraction / total_fraction | 原MoonBit比值0..1；分母为0时单元格为空 |

行顺序是样本清单顺序，再按门声明顺序，包括前向父引用。计数与比例直接来自现有`populations`，不从CSV成员列重算。空群体的计数为0；空父群体或零事件Dataset的无定义比例为空，不能把它解释为测得0%。完整链式文件的哈希覆盖整个文件，Dataset列区分选择；它不是单独提取后规范化文件的哈希，也不是来源认证。CSV为UTF-8、CRLF；文本列/表头加引号，内部引号双写，逗号/换行/Unicode保留。它不执行电子表格公式清洗。

命令先校验整个清单结构和读取选项，再顺序读取、执行各样本的既有群体查询；只有全部成功才以独占新建方式写报告。后一个样本缺失、解析失败、Dataset不存在或门计划无效，都会在输出创建前失败；错误标出样本ID。已有目标不覆盖。成功stdout为`{"written":"out.csv","samples":3,"rows":18}`，错误沿用退出1及stderr文本。

每次保留一个源文件及其门控成员数组，汇总CSV行/字节在内存中累积；内存仍受单个源及完整报告大小约束。不宣称流式、零拷贝、并行批处理、掉电持久性或原子发布；正常写入阶段IO失败可能留部分新文件。原CSV的`--atomic-output`合同保持，不自动适用于本命令。

独立检查：`python tools/check-population-report.py /path/to/NEW_DIRECTORY`。原创小型原始FCS包含换序/大端、超过64位的原ID、逐门缩放/补偿、父子/空父、零事件和链式第二Dataset。原始字节独立解码及有理数谓词对照手写成员集合；完整CSV预期由这些集合计算，另起CSV-only进程检查全部字段并执行透视/排序。实际Unicode、引号和换行有物理向量。无效清单/读取选项、晚发生的文件/解析/Dataset错误、零事件坏计划和已有目标均覆盖；没有重跑旧大样本或修改科学核心。

多样本报告是成熟工作流，例如[FlowKit Session文档](https://flowkit.readthedocs.io/en/latest/session.html)的汇总报告。本实现独立编写，复用本项目既有API，不宣称FlowKit功能对等、算法首创或MoonBit生态唯一。源码模块为`mawei2018-2/fcs`，版本0.5.0；使用源码工作区构建，包注册表版本须另行核实。
