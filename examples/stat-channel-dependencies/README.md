# 统计输出通道的校准依赖

本例为原创 MIT 合成 FCS3.1 I16 文件，不是生物学或临床样本。原始五行是
`[8,24,5]、[20,100,7]、[12,20,9]、[4,8,11]、[40,400,13]`，列为 Driver/Target/Unavailable。
Driver、Target 的 gain 为 2、4，第三列 gain=0。既有非严格读取接受源文件并给出该列警告；
严格读取仍失败，本例不宣称严格 FCS 标准符合性，也没有修复或忽略该列校准。

在仓库根目录构建后运行：

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs population-stats examples/stat-channel-dependencies/input.fcs --options examples/stat-channel-dependencies/population.json
```

原始 Driver 半开区间 `[0,13)` 选择源事件0/2/3，窗口 start1/count2 只统计2/3。
保留完整源通道和 `2,Driver,Target,1,0.5,0,1` 矩阵，Target 补偿值为 `(Target-Driver)/4`，
所以得到 `[2,1]`、count2、mean1.5、样本variance0.5；不能先裁掉 Driver 再补偿。
read_report 保留原来源和第三列实际警告。输出只请求 Target，不计算无关第三列的统计；
显式请求第三列的缩放/补偿、实际依赖其测量值的输出或相应门控仍会失败。
默认省略/null channels 仍计算全部输出并保留原行为。
