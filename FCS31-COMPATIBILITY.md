# FCS3.1编码、转换与分析合同 · 0.5.0

依据[ISAC FCS3.1](https://www.citometriagic.it/wp-content/uploads/2025/02/FCS_3_1.pdf)的DATATYPE、MODE、PnB/PnR、DATA和SPILLOVER定义；相关直方图频数字段采用[ISAC FCS API](https://murphylab.web.cmu.edu/FCSAPI/FCSAPIv0108.html)的宽字段访问约定。ASCII、C/U弃用不等于非法，本版均实现读取、访问与写出。

| 功能 | 核心入口与行为 |
|---|---|
| 任意位宽I | BigInt逐位访问及有效位掩码，跨参数/事件无行填充；写出保留分配位，末尾未用位清零 |
| 精确门控 | `rectangle_exact(Array[IntegerBounds])`，半开区间，I/A共用BigInt；JSON `integer_bounds:[{channel,lower,upper}]`接入普通gate/subset |
| 四类创建与转换 | 同一个`create`/`write`接受Encoding；ASCII宽度0为自由格式；F/D对应32/64位 |
| C直方图 | PnR是各轴箱数，第一轴最快变化；每频数字段采用各轴PnB的最大存储宽度；坐标0起始，轴重排按坐标而非列表列复制 |
| U直方图 | 第一个轴全部频数后接下一轴，使用各轴PnB；I/A精确核对每轴的总频数与TOT一致 |
| 直方图重写 | C子集为边缘分布，U子集为轴选择；频数加法不经Double，必要时扩大PnB；TOT字符串保留任意大计数 |
| 补偿 | 标准源染料行矩阵S；线性scale事件行e×S^-1，主元消去，缓存逆矩阵；不将补偿后的值冒充原始未补偿DATA |
| SPILL/SPILLOVER同步 | 保留通道顺序决定新矩阵顺序，主子矩阵对应保留的染料；维度小于2不再保留具名交叉补偿关键字 |
| 极值几何 | IEEE有限值的行列式使用精确回退，包含边界，不设人为坐标/顶点上限 |

`Channel.range`现在是原始十进制字符串，避免将大PnR经过Double后丢位；`Dataset.total_events`保存精确TOT。`Dataset.events`只表示L模式可索引行数，C/U通过histogram接口访问计数。`integer_value`与JSON整数输出精确；`value`及补偿/统计的数值结果为Double，调用方选择数值视图时仍应保留精确整数身份。

主create示例：`create(["A"], [], integer_values=["18446744073709551617"], encoding={kind:Integer,widths:[65],order:LittleEndian})`。
主write示例：`dataset.write(encoding={kind:Ascii,widths:[0],order:LittleEndian})`。
直方图：`create_histogram(["A","B"],[2,2],["1","2","3","4"],mode=Correlated,encoding={kind:Integer,widths:[16,16],order:LittleEndian})`自动计算TOT。

转换不默默量化不适合目标类型的值：负数不能写入无符号I，非整数不能无损写成整数，有限数溢出Float32时报错。整数重打包保留原PnR可表示的放大器语义；要求更窄且无法保存原对数范围的编码时返回输入可表示性错误。TEXT、补充TEXT、ANALYSIS及段重叠遵循现有结构检查；修改使ANALYSIS失效时须由调用方明确处理。CRC依赖原字节，重写时不沿用旧校验值。

旧`$COMP`的[FCS3.0主文3.2.20](https://bioc.r-universe.dev/flowCore/doc/fcs3.html)定义为维度n及按行存放的n×n系数，n对应采集参数数目。C/U改轴时按保留源轴同时选择/重排行列，更新维度，逐字复制系数，不经Double、不应用补偿到DATA；单轴保留1×1 COMP。它保留的是所选轴之间的原矩阵项，不承诺等价于全维补偿后再投影。原轴顺序不变则保留整个值；`drop_spillover=true`仍可显式移除。

COMP维度须能对应源通道数及完整方阵字段数，才有确定的位置映射；无法对应时仅改轴写出明确失败，不猜测或静默删除。解析接受域、原轴重写和显式移除不受此操作检查影响，系数字符串不新增数值转换/验证。L模式既有显式移除规则保持。FCS3.1附录B已用SPILLOVER替代COMP，本实现不把旧COMP冒充具名SPILLOVER。持续独立回归保留原始FCS3.0 I16输入和全部原逐箱预期，并检查非对称矩阵、精确小数/指数文本、连续投影和错误路径，见`tools/check-histogram-comp.py`。

对于当前API接受的ASCII原值，A访问不使用I的PnR有效位掩码。A→I时，线性通道及既有Time tick语义只在所选值需要更多有效位时扩输出范围；空/未导出事件不造成扩范围。对数探测器的原有效位已足够时保留范围及校准，只有必须扩范围而会改变校准的目标才失败。ASCII读取/改写与I/A/F/D原有其他转换保持。实际反例、边界及当前身份见[REPAIR23.md](REPAIR23.md)。

实例、结果和实际命令在[evidence/deep-20261020](evidence/deep-20261020/CHECKS.json)；历史申报原稿保留，当前实现与0.4.0旧说明分开记录。
