# 布尔群体文件交接例程

本目录是原创 MIT 合成数据与仅读最终文件的标准库接收器。`input.fcs` 为 8 事件×3 通道，X=0..7、B=2/6/4/8/10/12/14/16、ID=2^64+X，位宽为 8/8/65。B 的线性增益为 2，源 ANALYSIS 有一条 NOTE；源文件不修改，子集明确 `drop_analysis:true`。

`options.json` 故意将引用者放在定义者前面。base 是 X∈[1,7)，A 是 base 内缩放 B∈[2,6)，B 是 base 内精确 ID∈[2^64+3,2^64+7)。这些标签只为核对数值，不代表生物学分类。

| 群体 | 原事件索引 |
|---|---|
| A | 1,2,3,4 |
| B | 3,4,5,6 |
| intersection=A AND B | 3,4 |
| union=A OR B | 1,2,3,4,5,6 |
| notA=union 内 NOT A | 5,6 |
| after=notA 下多边形 | 6 |
| rootNotA=全体内 NOT A | 0,5,6,7 |

还包含双重 NOT、重复引用和父群体兼作引用。`expected.json` 固定全部 11 群体的索引、计数及比例，不由产品计算生成。`subset.json` 输出 intersection 的 ID/B 两列，保留精确 65 位整数；`csv.json` 输出 union，附源索引及 intersection/notA 的成员列。

从仓库根目录运行，NEW 路径须不存在：

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs populations examples/boolean-gates/input.fcs --options examples/boolean-gates/options.json > NEW-populations.json
python examples/boolean-gates/receive.py NEW-populations.json --kind json --expected examples/boolean-gates/expected.json
node tools/fcs.mjs subset examples/boolean-gates/input.fcs NEW.fcs --options examples/boolean-gates/subset.json
python examples/boolean-gates/receive.py NEW.fcs --kind fcs --expected examples/boolean-gates/subset-expected.json
node tools/fcs.mjs csv examples/boolean-gates/input.fcs NEW.csv --options examples/boolean-gates/csv.json
python examples/boolean-gates/receive.py NEW.csv --kind csv --expected examples/boolean-gates/csv-expected.json
```

接收器不导入产品或生成器，FCS 按各字节的各位重建整数，核对所有非布局元数据、实际段边界、填充位、完整 DATA 和精确值。布局位置由实际文件验证；预期不固定重新编码后的绝对偏移。CSV 按 CSV 规则核对全部单元格，JSON 核对全部字段和数组。产品运行只需 MoonBit 构建与 Node.js，Python 为验证工具。

`geometric-report.json` 是同一输入在接纳版本的纯几何计划 stdout；`geometric-provenance.json` 固定其源码提交、编译桥接及输入/选项/输出身份，文本比较域为 UTF-8/LF。公共 MoonBit 调用例程在 [boolean-consumer](../boolean-consumer)，完整语义和枚举扩展兼容限制见 [BOOLEAN-GATES.md](../../BOOLEAN-GATES.md)。
