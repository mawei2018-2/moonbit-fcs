# 带分位数的群体 JSON 交付

此目录为原创 MIT 合成数据：8 个事件、5 个通道，包含非单位 gain、稀疏补偿与非有限测量。`input.fcs` 由 `tools/population_quantile_fixtures.py` 独立使用 Python struct 构造；没有复制仪器数据或调用产品 writer。

在仓库根目录构建后，将完整 stdout 保存为一个新的文件：

```sh
node tools/fcs.mjs population-stats examples/population-quantiles/input.fcs --options examples/population-quantiles/options.json > NEW-report.json
python examples/population-quantiles/receive.py NEW-report.json --expected examples/population-quantiles/expected.json
```

接收程序只读取交付 JSON 与独立预期，不导入生产实现。它核对完整对象、源索引、列顺序、计数、统计和每个分位数；整数、概率、零与次正规数须精确一致，其余 Double 结果相对独立有理数预期最多允许 4 ULP 的舍入差异。该容差是这些固定向量的验收准则，不是全输入误差保证。

`default-report.json` 是引入分位数前的接纳版本 `f957d434b2f4b0c640077902ba3fed184b8f1e82` 对此原创输入、群体成员窗口 `[2,3,4,5]`、Target/Driver 列的真实 stdout 控制；用于证明省略或 null 请求的字节兼容。新增功能的完整合同见 [POPULATION-QUANTILES.md](../../POPULATION-QUANTILES.md)。

这些例程证明项目接口的实际可消费性，不代表外部采用或临床解释。
