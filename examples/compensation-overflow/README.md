# 有限补偿结果到独立文件接收者

本目录的原创 MIT `input.fcs` 含 7 事件、A/B/C 三个 D64 通道，原 ANALYSIS 有一条 NOTE。矩阵 S 为 `[[1,-1,0],[0,0.5,0],[0,0,1]]`，逆矩阵为 `[[1,2,0],[0,2,0],[0,0,1]]`；P=2^1023。

| 原事件 | A | B | C | 补偿 B |
|---|---|---|---|---|
| 0 | P | −P | 0 | 0 |
| 1 | −P | P | 1 | 0 |
| 2 | 1 | 2 | 2 | 6 |
| 3 | P | P | 3 | Infinity |
| 4 | 0 | 0 | 4 | 0 |
| 5 | NaN | 1 | 5 | NaN |
| 6 | Infinity | −Infinity | 6 | NaN |

`plan.json` 定义补偿 B∈[−1,7) 的 finite 群体、其中 B∈[−0.5,0.5) 的 zero 群体，以及 NOT/OR 后续引用。完整结果 finite/either 为 `[0,1,2,4]`，zero 为 `[0,1,4]`，rest 为 `[2]`。标签只用于核对数值，不是生物分类。

`csv.json` 输出 either 的源行号、补偿 C/B 和 zero 成员标志；`stats.json` 对 B/C 输出完整统计与输入来源。`subset.json` 输出同一成员的原始 C/B，显式移除不再适用的 ANALYSIS 和补偿矩阵，源文件保持不变。`expected-*.json` 是独立完整预期，不从产品输出生成。

运行命令见 [COMPENSATION-NUMERICS.md](../../COMPENSATION-NUMERICS.md)。`receive.py` 只用 Python 标准库读取最终文件，不导入产品或生成器；FCS 验证全部非布局元数据、实际段边界、完整 DATA、所有值和位模式，CSV/JSON 核对全部字段。`ordinary-control.json` 及其 provenance 保存接纳版本对独立普通控制向量的 UTF-8/LF stdout 身份。

完整六文件向量由 `tools/compensation_overflow_fixtures.py` 构造，另含部分和溢出、次正规数平局/负零、正常数平局、最大有限值及增益缩放；Fraction 逐项乘加给出独立舍入预期。NaN 的 payload 不作跨后端承诺，真实非有限输入和零系数依赖规则保持。
