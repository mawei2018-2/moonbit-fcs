# 群体中位数与分位数

`population-stats` 可通过 `probabilities` 在既有群体统计报告中附带分位数。它复用同一成员窗口、报告列及原值/缩放/补偿视图，便于直接交付中位数、四分位数和其它指定概率的摘要。

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs population-stats examples/population-quantiles/input.fcs --options examples/population-quantiles/options.json
```

该原创合成例程按源事件 `[1,2,3,4,5,6]` 选择群体，报告 Target/Driver/Target。请求概率为 `[1,0.5,0,0.25,0.75,0.5]`，原顺序和重复项保留。补偿后的 Target 有 4 个有限值、2 个非有限值，中位数为 10.75。完整预期及仅读最终 JSON 的接收程序见 [examples/population-quantiles](examples/population-quantiles/README.md)。

## 数据合同

`probabilities` 省略或为 null 时不增加 `quantiles` 字段，既有报告字节保持。提供时须为非空数值数组，每个数均有限且在 `[0,1]` 内。空数组、字符串、布尔、null 元素和越界值会失败，即使请求的报告列为空。

新增的 `quantiles` 数组与现有 `statistics`、`channel_names` 的顺序一致。每项完整给出：

| 字段 | 含义 |
|---|---|
| method | 固定为 `linear-type7` |
| count | 实际视图中的有限观测数 |
| nonfinite | 排除的 NaN、正 Infinity 和负 Infinity 数 |
| probabilities | 请求概率的快照，保留顺序与重复 |
| values | 相同顺序的可选 Double 结果；没有有限观测时为 null |

将有限视图值升序排列为零基 `x[0..n-1]`。`n>0` 时，`h=(n-1)*p`，在 `x[floor(h)]` 与后一观测间线性插值；`p=0/1` 返回最小/最大值。单个有限观测对所有概率返回自身。`count/nonfinite` 只描述当前成员窗口，不将全群体计数误当窗口大小。

这是常见的 type-7 样本分位数定义，数学位置参见 [R 官方 quantile 文档](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/quantile.html)。计算使用现有 Double 值，可能有浮点舍入，不保证大整数精度或其它分位数定义的等价性。补偿仍保留完整源矩阵与实际依赖；没有矩阵时按现有规则退回缩放。方法不改变 DATA、门控、源索引或 ANALYSIS。

实现每个唯一报告列保存有限观测并排序，额外空间 O(事件数)，排序时间 O(n log n)，不是流式或固定内存算法。仅支持列表事件；C/U 直方图不适用此定义。默认均值/方差等统计保留，即使请求了分位数。

## MoonBit 公共 API

`Dataset.quantiles(channel, probabilities, scaled?, compensated?) -> ChannelQuantiles raise FcsError` 直接使用 Dataset 的既有数值视图。类型的 `method_id` 字段表示方法，JSON 的对应字段名为 `method`；其余字段同上。公共 API 拒绝非有限或越界概率，空数据也校验通道、模式和概率。

实际独立消费模块见 [examples/quantile-consumer](examples/quantile-consumer)。从该目录分别执行 `moon run . --target js --deny-warn` 与 `moon run . --target wasm-gc --deny-warn`，通过源码工作区导入 `mawei2018-2/fcs`，直接解析同一原创 FCS 字节并计算三种视图。

## 场景与差异

[FlowJo 官方统计说明](https://docs.flowjo.com/flowjo/workspaces-and-samples/ws-statistics/ws-statdefinitions/)包含中位数和百分位数，并说明其多数统计先使用分箱值。本功能在请求的实际 Double 观测上按明确 type-7 定义计算，不保证与 FlowJo 分箱/变换统计相同。它为当前 MoonBit FCS 群体工作流补足可组合的顺序统计，不声称算法首创、生态唯一、外部采用或生物学结论。

代码、向量及接收程序为原创 MIT；不引入新的第三方运行依赖。
