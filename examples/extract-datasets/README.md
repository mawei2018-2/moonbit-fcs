# 原链到单Dataset文件接收

原创MIT input.fcs包含三个既有格式的Dataset，HEADER位于0、2048、6144；NEXTDATA分别为2048、4096、0。它们有独立通道/ANALYSIS：FCS2.0整数、FCS3.1大端D、FCS3.0的2×2直方图。

从仓库根运行，目标目录须不存在：

```sh
node tools/fcs.mjs extract-datasets examples/extract-datasets/input.fcs extracted
python examples/extract-datasets/receive.py extracted --expected examples/extract-datasets/expected.json --source-file examples/extract-datasets/input.fcs
```

可追加`--options examples/extract-datasets/read.json`严格读取；默认读取与严格输入都由本轮小型流程检查。抽取后3个FCS均为独立3.1，接收只读取该目录和预期，不导入生产库/构造器，也不读取原链路径。

接收者完整核对元数据、ANALYSIS和原始DATA，再得到整数列合计4/6；D有限值合计4、负零1、NaN1、正负无穷各1；直方图总17、边缘[7,10]及[5,12]。NaN payload及负零按原始字节核对，未通过JSON数值往返。

预期和完整原始输入来自执行前的独立标准库构造器；源哈希与各输出字节身份分开。自编接收不是外部采用或临床验证；普通IO失败可留部分新目录，详见[完整合同](../../EXTRACT-DATASETS.md)。
