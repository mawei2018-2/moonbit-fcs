当前0.4.0合法编码范围、精度边界与完整标准终点见 [FCS31-COMPATIBILITY](FCS31-COMPATIBILITY.md)；下文保留显式非规范输入兼容的历史说明。

# 显式 TEXT 填充兼容与规范重写 · 0.2.0

FlowIO 的固定公开样本 `G11.fcs` 把主 TEXT 段后 5,714 个 ASCII 空格也包括在 HEADER 声明的段范围内。0.1.0 因声明终点不是分隔符而拒绝。0.2.0 提供 `allow_text_padding=true`；默认行为不变，操作者明确选择后可读取、筛选并重新输出 FCS3.1。

先构建，然后对自己取得的输入运行：

```sh
moon build --target js --release
node tools/fcs.mjs inspect G11.fcs --options examples/text-padding.json
node tools/fcs.mjs rewrite G11.fcs normalized.fcs --options examples/text-padding.json
node tools/fcs.mjs validate normalized.fcs --options examples/strict.json
```

`inspect` 的 warnings 报告具体段名和忽略的字节数。先查看报告再重写，输出文件必须不存在，输入文件不会修改。选项同样可传给 `subset`、`csv` 和库 API `parse/parse_all`；原始事件值不因这个兼容选项重新缩放。调用 `Dataset::write` 仍须遵守 ANALYSIS、补偿矩阵和通道变更限制。

只在分隔符不是空格时，去掉声明范围末端连续 ASCII 32；剩余内容必须原本就有完整键值对及结束分隔符。不处理制表符、NUL、换行、缺失值、缺失分隔符或截断。值内部和分隔符之前的空格原样保留。主 TEXT、补充 TEXT 和 ANALYSIS 都使用同一限定规则；段重叠和 NEXTDATA 检查仍使用原始声明范围，不能靠修剪隐藏重叠。严格模式与此选项同时启用会报错。

对应现有方案：FlowIO1.4.0 已能读取该样本，本项目没有发明修复算法；本次依据公开文件及 FCS3.1 格式边界新写限定的 MoonBit 兼容入口，未复制 FlowIO 解析代码。规范依据为 [ISAC FCS3.1](https://www.citometriagic.it/wp-content/uploads/2025/02/FCS_3_1.pdf) 的2.2.4、2.2.15及3.2.5–3.2.9。分隔符限制为 ASCII1..126，空键/空值仍无效。参照工具的偏移兼容参数见 [FlowIO 官方 API](https://flowio.readthedocs.io/en/stable/api.html)，不把 TEXT 填充与 DATA 偏移强制覆盖混为一谈。

当前仍拒绝 `data1.fcs` 的不成对 TEXT、`B01 KC-A-W---91-US.fcs` 的重叠 supplemental TEXT 及 HEADER/TEXT DATA 冲突。未知厂商尾部区段仍不保留；重写不是所有仪器软件的无损文件归档，证明的是已解析 DATA 字节及声明支持的元数据。

本次 [回执](evidence/text-padding-20260923/reference.json) 记录固定样本 SHA256：69,420 个值与 FlowIO 全量相等，重写 DATA 字节相同、选择后回读相同，并可由默认严格模式读取。没有样本身份元数据或仪器文件加入交付。

## 0.3.0 显式段偏移空格兼容

`allow_offset_padding=true` 的精确规则和有文件级授权的实际输入见 [REPOD-EXCHANGE](REPOD-EXCHANGE.md)。
FCS3.1 §3.2.17 明确禁止数值字段填充，因此此选项是非规范输入的显式兼容；默认及严格模式仍拒绝。
只接受七个段偏移字段首尾 ASCII 空格，查询原元数据不变，并逐字段警告；不作用于 TOT/PAR/PnB/PnR 等其他数值。
段范围、冲突、重叠、截断及矩阵检查仍执行，与 TEXT 段尾部空格兼容分别启用。
