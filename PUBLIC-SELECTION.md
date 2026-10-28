# 固定公开 FCS 的可追溯选择与回读

公开来源：[FlowIO](https://github.com/whitews/FlowIO)，固定提交 83d28a22d42235c10d17afb017250ee208afed95，文件 data/fcs_files/G11.fcs，SHA256 40ed9f6d4293a87077cab07a34c68b2497d4d69988adcb64a5f718098f48b56f. 文件不随本仓库分发；源项目许可及数据用途由获取方核对，不能把论文/仪器元数据当作本项目采用证明。

```sh
moon build --target js --release
node examples/public-selection.mjs /path/to/FlowIO/data/fcs_files/G11.fcs /path/to/new-result
node tools/test-request-contract.mjs
```

示例仅选择原始未缩放通道0在[1000,2000)的事件，保留通道0/1/2；不是生物学门或临床建议。输出 selected.fcs、indices.json 与最后写入的 manifest.json。manifest缺失时不能当作完整交付。显式 allow_text_padding 只容许既有披露的TEXT尾空格；结果以strict模式回读。选择后补偿矩阵和分析段显式丢弃，不声称它们仍适用。

独立验证由 tools/verify-public-selection.py 使用 FlowIO 1.4.0/NumPy 对原始未预处理矩阵计算相同数值集合，并全量比较选后数值、$PnN/$PnS/$PnE/$PnG/$PnR/$PnB 元数据、原始输入和结果散列。换题前仍需团队公开本项目、确认表单许可；旧 Forth 地址不能替代。

许可边界：公开可下载不等于可再分发；FlowIO 的 BSD 代码许可不自动证明 G11.fcs 的文件级授权。本仓库及交付包均不包含原始或派生 FCS 数据，只提供代码、统计/hash与复现入口。获取和使用原样本前需自行核对其授权；可改用有明确许可的自有数据运行相同接口。
