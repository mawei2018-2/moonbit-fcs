# 命名分层门控与群体导出

先粗选一组事件，再在其中按形状或精确ID继续筛选；每一步保留源文件事件索引和父群体分母。原有单门API适合独立条件，新gate_plan负责父子交集和分支报告，避免把父群体的相对行号当作源事件号。

## 运行完整例程

```sh
moon build --target js --release --deny-warn
node examples/run-gate-plan.mjs /path/to/NEW_DIRECTORY
```

例程只使用原创MIT合成数据。X/Y/M是便于核对的数值标签，阈值不代表生物学分类。它创建6事件×4通道I文件，其中ID为65位整数，执行[计划](examples/gate-plan.json)，生成群体报告、selected.fcs、selected.csv及命令/散列回执。

| 群体 | 父群体 | 原始事件索引 | count/parent_count |
|---|---|---|---|
| window | 全部事件 | 1,2,3,5 | 4/6 |
| shape | window | 1,2,5 | 3/4 |
| id_window | shape | 2,5 | 2/3 |
| high | window | 2,3,5 | 3/4 |
| low | window | 1 | 1/4 |

计划故意把子步骤写在父步骤前面；报告保持计划的输入顺序。导出的id_window保留通道ID/X/M，ID仍精确为18446744073709551618和18446744073709551621，未补偿DATA保持所选原始值。

## CLI计划

```sh
node tools/fcs.mjs populations input.fcs --options plan.json
node tools/fcs.mjs gate input.fcs --options selection.json
node tools/fcs.mjs subset input.fcs selected.fcs --options selection.json
node tools/fcs.mjs csv input.fcs selected.csv --options selection.json
```

plan.json含gates数组，每步id必须唯一非空；parent省略或null表示全部事件，否则引用另一id。selection.json在相同计划上加`"population":"id_window"`，可另加channels、metadata或显式drop选项。输出路径必须不存在，ANALYSIS/补偿处理继续遵循write原合同。

每步恰有一种谓词：bounds为`[[channel,lower,upper]]`的半开区间交集；vertices配合x/y指定含边界的多边形；integer_bounds为`[{"channel":3,"lower":"18446744073709551618","upper":"18446744073709551622"}]`，边界是十进制字符串，避免Double舍入。

计划的通道位置也可使用精确PnN字符串，如`["FSC-A",500000,1000000]`、`"x":"FSC-A"`及`"channel":"ID"`。channels输出列表支持名字/数字混合，避免通道换序后手工改列号。缺失/歧义名字失败，数字字符串不作索引转换；完整真实文件例程见[NAMED-CHANNELS.md](NAMED-CHANNELS.md)。

scaled/compensated是每步可选标志，默认false。它们只适用于浮点数值视图的bounds/vertices；integer_bounds要求原始整数，不能组合这两个标志。populations/gate/subset计划请求拒绝顶层scaled/compensated，避免忽略视图意图。旧的单门命令仍使用原有顶层标志。

csv的计划选择直接读取原Dataset，无须先写FCS；CSV顶层scaled/compensated专门选择输出视图，门控仍按每步标志。CSV的start/count指群体成员位置，回执source_event_indices给出实际导出行的原Dataset索引；详见[直接群体CSV](POPULATION-CSV.md)。

Population报告含id、parent、event_indices、count、parent_count、total_count、parent_fraction和total_fraction。比例为0到1；分母为0时相应比例字段省略（MoonBit为None），不伪造0/0。无parent的parent字段也省略。空计划返回[]。空父群体仍检查子谓词的形状/索引。图、谓词或引用错误使整个调用失败，不返回部分结果；CLI退出1并写stderr，subset在此之前不会创建输出。

## MoonBit API

```moonbit
let populations = dataset.gate_plan([
  @fcs.GateStep::{
    id: "window", parent: None,
    predicate: @fcs.Rectangle([
      {channel: 0, lower: 15.0, upper: 45.0},
    ]),
    scaled: false, compensated: false,
  },
])
let bytes = dataset.write(event_indices=populations[0].event_indices)
```

调用方在自身错误上下文中处理FcsError；完整导入与签名见pkg.generated.mbti。列表模式I/A/F/D共用此API，Exact仅适用于I/A；C/U没有事件群体计划。实现按每个门扫描内存Dataset并保留成员索引，不宣称流式或无限规模。

随包的独立模块可从当前源码直接运行，无需等待0.5.0发布：在examples/gate-plan-consumer目录执行`moon run . --target js --deny-warn`或`moon run . --target wasm-gc --deny-warn`。该模块只导入公开API，输出同一计划的完整群体JSON。

此功能独立实现既有矩形/多边形/精确整数选择的组合，未复制FlowKit代码或数据。[FlowKit](https://flowkit.readthedocs.io/en/latest/gating_strategy.html)已有成熟层级分析，本库的差异是MoonBit直接消费、原始整数身份及FCS交换链。不提供GatingML/FlowJo导入、GUI、多父节点/布尔门、跨样本批处理或自动分类。
