# MoonBit FCS：精确事件选择与可追溯数据交换

以纯MoonBit实现流式细胞术FCS数据准备，连接读取、规则分组、统计与FCS/CSV交付。
目标用户是MoonBit数据工具开发者：读取仪器导出文件，按明确规则选择群体、校准和重排数据，交给下游脚本；不替代实验室门控判读。

- 读取FCS2.0/3.0/3.1，支持I/A/F/D、固定/自由ASCII；解析通道、段结构和补偿元数据，兼容填充须显式选择。
- BigInt/十进制文本保留原始整数，支持非字节对齐及超过64位的精确选择；I按PnR有效位读取，Double视图有精度边界。
- 矩形半开、多边形含边界与整数谓词组成命名父子/分支群体，返回源索引、计数及父/总群体比例，支持精确通道名；歧义不猜测，坏计划整次失败。
- 按gain、对数放大器和Time/TIMESTEP缩放，以测量行向量M×S⁻¹补偿；门控和统计视图独立，完整矩阵计算后筛报告列。
- 群体统计按成员位置start/count取窗口，报告有限/非有限数、极值、均值和样本方差，保留源事件/通道号，不混淆窗口与原行号，不按Time排序；空群体无均值，单例无样本方差。
- 创建或选择、换序后写FCS3.1，同步通道元数据；I/A/F/D不可表示转换明确失败，写出保留未补偿DATA，ANALYSIS失效须显式处理；L/C/U改变轴选择或顺序时，旧COMP须显式移除，原轴重写仍保留。
- CSV直接导出群体窗口及可选源行号。
- C/U直方图提供精确频数、轴重排和C边缘分布，累加不经Double，必要时扩大位宽；不套用列表门控/统计。

格式、位流、门控、矩阵与统计由MoonBit实现；核心支持JS/Wasm-GC。Node≥22负责文件/JSON与CLI接线，Python仅作开发参考；内存处理不宣称流式。
FlowIO/[FlowKit](https://whitews.github.io/FlowKit/)已有Python方案。本项目独立贡献是MoonBit可组合实现、精确整数和层级成员身份，以及选择到FCS/CSV/统计的交换链，不主张算法首创或生态唯一。

最短使用（固定工具链，输出路径须不存在）：
```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs create out.fcs --options examples/gate-plan-events.json
node tools/fcs.mjs population-stats out.fcs --options examples/population-stat-window.json
```
得到含65位ID的out.fcs和窗口统计报告：取群体第二名成员、源事件5，报告M/X/M，完整群体2个事件、实际窗口1个事件。

已有独立字节/有理数真值、FlowIO回读及许可RepOD交换证据，核心相关回归覆盖JS/Wasm-GC；上述短例与窗口/CSV交接已在本地执行通过，不代表全部组合穷举或线上验收。
不支持FCS3.2、CRC校验、全部厂商异常、GatingML/FlowJo导入、自动门控/降维或临床结论；Double统计不保证任意整数精度。
仓库：[源码](https://github.com/mawei2018-2/moonbit-fcs)；模块mawei2018/fcs，源码0.5.0；Mooncakes包发布与GitHub源码版本分别核对。
代码/合成向量为MIT，见根LICENSE；标准库依自身许可，FlowIO/NumPy开发参考为BSD-3-Clause。附带RepOD文件96804及派生物为CC BY4.0，保留Bronisz署名、DOI10.18150/JOLWGT和修改说明；标准PDF及未确权仪器数据不分发。
