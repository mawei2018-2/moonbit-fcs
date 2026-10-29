# 补偿点积与中间溢出

补偿使用实际线性缩放后的测量行向量 M 乘以已计算的逆矩阵 S⁻¹。有限的观测和逆矩阵系数可能在相乘或逐项相加时先溢出，尽管最终点积能用 Double 表示。例：S=`[[1,-1],[0,0.5]]`，S⁻¹=`[[1,2],[0,2]]`；测量为 `[2^1023,-2^1023]` 时 B 应为 0，直接计算两个乘积却会形成 Infinity−Infinity。

这种非有限中间结果不应使本来有限的事件从补偿门和统计中消失。现有数值视图现在在必要时恢复该点积，公开 API、矩阵约定和写出合同保持。

## 数值合同

- 普通计算得到有限值时保持原有逐项 Double 路径及舍入，不改变其输出。
- 只有原点积为 NaN/Infinity 且所有实际依赖的缩放观测均有限时，才按这些 binary64 观测和缓存的 binary64 逆矩阵系数形成精确二进制乘积之和，再一次舍入为 Double，采用最近值、平局取偶数。
- 恢复覆盖乘积溢出和部分和溢出后的抵消，包括次正规数、带符号的下溢零及最大有限值边界；最终确实超出 Double 范围时仍为带符号 Infinity。
- 若实际依赖的观测已是 NaN/Infinity，保持原来的非有限传播。零系数不产生数据依赖，独立通道继续不受其它通道 NaN/Infinity 污染。

这以实际已缩放值和已算出的 Double 逆矩阵为准，不重新求精确实数逆矩阵，也不恢复此前校准、求逆或正常有限路径中的舍入和下溢。它不将整个补偿接口改成任意精度计算；BigInt 仅在这个非有限中间结果的后备路径使用。额外开销随实际补偿维数和所需二进制位数增长，未作性能加速承诺。

`value(compensated=true)`、补偿矩形/多边形门、群体统计和补偿 CSV 共用同一结果。布尔群体引用已完成的成员集。写出 FCS 继续保留未补偿的所选 DATA；需要补偿值交付时使用 CSV。源 DATA、ANALYSIS 和矩阵不会因数值查询而修改。

## 可运行的完整交接

从仓库根目录运行，NEW 路径须不存在：

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs populations examples/compensation-overflow/input.fcs --options examples/compensation-overflow/plan.json > NEW-populations.json
python examples/compensation-overflow/receive.py NEW-populations.json --kind json --expected examples/compensation-overflow/expected-populations.json
node tools/fcs.mjs csv examples/compensation-overflow/input.fcs NEW.csv --options examples/compensation-overflow/csv.json
python examples/compensation-overflow/receive.py NEW.csv --kind csv --expected examples/compensation-overflow/expected-csv.json
node tools/fcs.mjs subset examples/compensation-overflow/input.fcs NEW.fcs --options examples/compensation-overflow/subset.json
python examples/compensation-overflow/receive.py NEW.fcs --kind fcs --expected examples/compensation-overflow/expected-subset.json
```

[原创文件例程](examples/compensation-overflow/README.md)说明全部输入、门与输出。Python 是独立开发接收器的工具，产品运行仍只需 MoonBit 构建和 Node.js。独立公开 API 模块 [compensation-overflow-consumer](examples/compensation-overflow-consumer)在 JS/Wasm-GC 上输出六份完整文件的逆矩阵、全部补偿值及位模式，可从该目录执行 `moon run . --target js --deny-warn --frozen` 或对应 Wasm-GC 命令。

`python tools/check-compensation-overflow.py NEW_DIRECTORY` 用原创 struct 文件和 Python Fraction 真值检查全部向量；预期在修改产品前冻结。独立进程只读取实际最终 JSON/CSV/FCS，比较全部字段、单元格、原始 DATA 和有限/Infinity 位模式；NaN 只约定分类，不固定负号或 payload。错误内容即使计数和结构仍正确，也必须被接收器拒绝。普通补偿的完整 stdout 与接纳版本 UTF-8/LF 控制比较。

补偿是既有数据处理方法，[FlowKit Matrix](https://flowkit.readthedocs.io/en/latest/matrix.html)也提供该工作流。[Goldberg 数值指南](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html)说明浮点溢出、抵消和舍入问题。本实现未复制第三方代码或数据，不主张新的补偿算法、外部采用或临床有效性。
