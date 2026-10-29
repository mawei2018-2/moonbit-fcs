# 用通道名复用门控与交付文件

仪器文件可能包含同名但顺序不同的通道。数字索引始终指物理列；需要复用计划时，可让计划和输出列按精确PnN标签寻址。

```json
{
  "gates": [{"id":"window","bounds":[["FSC-A",500000,1000000]]}],
  "population":"window",
  "channels":["SSC-A","FSC-A","Time"]
}
```

gate计划中bounds的第一个元素、polygon的x/y及integer_bounds.channel均可用数字或名字。values/subset/rewrite/csv的channels列表也可混合两者。名字精确区分大小写，不修剪空格，不自动匹配PnS染色/别名；字符串`"0"`表示名为0的通道，数字0表示第一列。

缺失或重名引用明确失败；兼容读取的重复PnN文件仍可用数字索引。未知/歧义列使CSV和FCS导出在创建目标前失败。values请求0行时也检查通道，合法0行仍返回[]。旧单门谓词、histogram的标量channel/axis继续使用数字合同；群体FCS使用gate/subset，CSV既可读取其输出FCS，也可[直接接受gates/population](POPULATION-CSV.md)。

重复名称会给出读取警告，strict读取仍报错，不宣称这类输入严格符合规范。数字位置也用于列表重编码及C/U直方图重写/换轴；保留各原列的名称与PnS/校准/数据，既不改名，也不让字符串引用猜一个重复列。新建文件的唯一非空名称要求保持；曾在写出时误用该创建校验的反例、修复范围和独立接收见[DUPLICATE-WRITE.md](DUPLICATE-WRITE.md)。重复输出同一数字轴仍报错。

MoonBit调用方使用`dataset.channel_index("FSC-A")`取得原GatePredicate所需Int。GateStep和gate_plan类型未变，新增方法是兼容扩展；独立模块examples/named-channel-consumer可在该目录以`moon run . --target js --deny-warn`或`--target wasm-gc`运行，展示换序元数据、分层门控及65位ID导出。

## 已许可第三方文件的完整例程

```sh
moon build --target js --release --deny-warn
node examples/repod-gate-plan.mjs /path/to/NEW_DIRECTORY
python tools/verify-named-repod.py /path/to/NEW_DIRECTORY --report /path/to/NEW_REPORT.json
```

Node例程离线读取随包的RepOD文件96804。库/Node运行不依赖Python；最后一条是开发用独立FlowIO1.4.0/NumPy核验。来源与CC BY4.0署名见examples/repod，例程自动复制许可、来源和修改说明到输出。原文件不改写。

源文件有14,320事件、26通道；显式allow_offset_padding保留4条偏移空格警告。固定数值示例按FSC-A→SSC-A→二维框得到2117→1794→662事件，导出SSC-A/FSC-A/Time三列，CSV另按Time/FSC-A取列。范围仅用于格式交换，不代表生物学分类。ANALYSIS/补偿移除由例程明确请求，DATA保留原始未缩放/未补偿值。

输出含populations.json、selected.fcs、selected.csv、SOURCE/许可/署名、CHANGES.md和命令/散列回执。独立核验按源数据直接求成员，不复用产品的图/名字解析；FlowIO回读1986个输出值，并检查7944字节源DATA投影、1324个CSV值及来源元数据。Node自身的运行回执与外部读取报告分别保存。

新增名字寻址沿用[FlowKit Dimension](https://flowkit.readthedocs.io/en/latest/dimension.html)等成熟工具中的PnN维度概念；本项目独立增量是MoonBit接口、严格歧义处理及可追溯格式交换，不宣称算法首创。未提供模糊匹配、PnS自动别名、面板语义推断或跨文件合并。
