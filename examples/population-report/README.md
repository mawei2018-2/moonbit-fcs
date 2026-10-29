# 只接收多样本CSV的下游

本目录是原创MIT可运行文件例程；输入、门计划、完整预期和接收程序均随仓库提供。接收程序不导入FCS解析器、生产CLI或MoonBit桥接。

从仓库根运行，输出路径须不存在：

```sh
node tools/fcs.mjs population-report examples/population-report/samples.json out.csv --options examples/population-report/gates.json
python examples/population-report/receive.py out.csv --expected examples/population-report/expected.json
```

`panel A.fcs`有9事件及ID/X/Y。`linked.fcs`的第二Dataset有5事件，以Y/ID/X、大端保存；原文件哈希保留整个链。`empty.fcs`有合法零事件DATA。ID值超过64位，门计划包含精确ID、父子、空父及逐门缩放/补偿；群体声明顺序有前向父引用。

预期band计数分别为5、3、0；子群体为3、2、0。接收方核对18行所有字节/字段、分母为0的空比例和原文件身份，透视完整计数，再按band总比例排序得到donor β、donor α和empty。输入中的实际Unicode、逗号、引号、换行均完整通过CSV接收。数字比例沿用MoonBit Double表示，例如1/3；接收者以Fraction核对误差。

这些输入及预期由独立Python标准库位于`tools/population_report_fixtures.py`的构造器生成；它从原始字节直接解码，并用有理数谓词核对手写成员索引。不是生产实现自报的expected。此自编实际消费者证明文件可被消费，不代表第三方采用、自动面板等价或临床结论。合同见[多样本群体报告](../../POPULATION-REPORT.md)。
