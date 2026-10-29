# 布尔群体与完整依赖图

两个命名群体可以求交集、并集，或在一个父群体中排除另一群体；结果继续用于几何门、精确整数门、统计和 FCS/CSV 导出。它们操作同一 Dataset 的原事件成员集合，不修改 DATA，也不把父群体中的相对位置当作源索引。

## 直接运行

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs populations examples/boolean-gates/input.fcs --options examples/boolean-gates/options.json
node tools/fcs.mjs subset examples/boolean-gates/input.fcs NEW.fcs --options examples/boolean-gates/subset.json
python examples/boolean-gates/receive.py NEW.fcs --kind fcs --expected examples/boolean-gates/subset-expected.json
node tools/fcs.mjs csv examples/boolean-gates/input.fcs NEW.csv --options examples/boolean-gates/csv.json
python examples/boolean-gates/receive.py NEW.csv --kind csv --expected examples/boolean-gates/csv-expected.json
```

输出路径须尚不存在。例程和接收器采用原创 MIT 数据；Python 仅为独立验证所需，产品运行不依赖 Python。完整说明见[文件例程](examples/boolean-gates/README.md)。

## 计划合同

每步恰好选择 `bounds`、`vertices`、`integer_bounds` 或 `boolean` 一种谓词。布尔对象只接受 `op` 和 `refs`：

```json
{"id":"both","parent":"base","boolean":{"op":"and","refs":["A","B"]}}
```

| JSON | MoonBit `GatePredicate` | 含义 |
|---|---|---|
| `{"op":"and","refs":["A","B"]}` | `AllOf(["A", "B"])` | 已完成 A、B 群体的交集 |
| `{"op":"or","refs":["A","B"]}` | `AnyOf(["A", "B"])` | 已完成 A、B 群体的并集 |
| `{"op":"not","refs":["A"]}` | `Not("A")` | 原 Dataset 中不属于 A 的事件 |

`and/or` 至少有一个引用，单引用有效，重复引用幂等；`not` 恰好有一个引用。引用是同一计划内精确、全局唯一、非空的 ID，没有路径、别名或跨 Dataset 查找。

引用使用源群体的最终成员，已包含它自己的父群体限制和几何门数值视图。所有谓词的结果最后都与该步的 `parent` 求交；省略/null 父群体表示全部事件。因此 `parent=base` 的 `Not("A")` 等于 base 中不属于 A 的事件。父群体可以同时作为布尔操作数，只形成一条依赖。

父引用和布尔引用组成同一有向无环图。允许前向引用、不同分支、嵌套组合，以及布尔群体下的几何门；输入无需拓扑排序。输出仍按计划输入顺序排列，成员为升序、无重复的原 Dataset 索引。现有 Population 的计数和比例格式保持：父分母来自声明的 parent，未声明时为全体事件数；零分母比例省略，空计划为 `[]`。

布尔步骤的 `scaled/compensated` 必须为 false，省略时默认 false；在被引用的几何门上选择视图。精确整数门继续要求原始整数。布尔运算不重新读取浮点数，因此根 `NOT` 可能包含因 NaN/Infinity 而被源数值门排除的事件；若只允许有限观测，应先定义相应数值父群体，再在其中排除。

未知/空引用、重复/空 ID、错误操作数类型或个数、未知布尔字段、混用谓词、非法视图以及父/布尔混合循环均使整个计划失败。未选中的分支和空父群体也要检查，不按集合短路隐藏错误。CLI 退出 1、错误写 stderr；计划错误发生在创建 FCS/CSV 目标之前。已有输出文件保持独占创建规则，普通写入 IO 错误仍遵循原文件接口合同。

## 公共 API 与兼容性

`GateStep` 的字段及 `Dataset.gate_plan` 的签名和结果模式不变，新增 `AllOf(Array[String])`、`AnyOf(Array[String])`、`Not(String)` 构造器。旧几何计划仍可消费；独立字节控制保存了接纳版本同输入的完整报告。

新增公共枚举构造器会影响调用方对 `GatePredicate` 的穷尽匹配：这些调用方须增加新分支。这里不承诺所有外部源码无需修改。完整公开 API 消费模块见 [boolean-consumer](examples/boolean-consumer)，使用工作区本地模块，可分别运行 JS 和 Wasm-GC：

```sh
cd examples/boolean-consumer
moon run . --target js --deny-warn --frozen
moon run . --target wasm-gc --deny-warn --frozen
```

门控仍只支持列表模式 I/A/F/D；Exact 只适用于 I/A，C/U 使用直方图接口。实现按依赖顺序保留各群体成员数组，布尔门使用与事件数成比例的临时掩码，AND 逐引用扫描；处理整个内存 Dataset，不宣称流式或无限规模。

## 验证与范围

`python tools/check-boolean-gates.py NEW_DIRECTORY` 运行六套完整群体真值、错误计划、公开 API 双后端及最终 FCS/CSV/统计接收。原创输入为非字节对齐的 8/8/65 位整数通道，并另含空文件与非有限 Double 向量。独立标准库接收进程检查全部 JSON 字段、CSV 单元格、FCS 元数据、DATA 位与全部精确整数；故意改错 DATA、成员列和保持计数的索引也必须被拒绝。

本功能独立实现常见集合运算，[FlowKit BooleanGate](https://flowkit.readthedocs.io/en/stable/boolean_gate.html)已有 AND/OR/NOT 群体引用。本项目提供 MoonBit 公共接口、原整数身份和文件交接，不主张算法首创、生态唯一或外部实验室采用。不提供 GatingML/FlowJo 导入导出、GUI、跨文件合并、自动分类或临床诊断。
