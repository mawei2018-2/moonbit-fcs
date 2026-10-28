# 13轮：群体交付后的CSV数值视图与回执

限定项目和本轮报告；12轮及所有旧封存只读。只沿populations/subset后的CSV消费检查，不扩展生物面板、格式或新分析功能。

- H13-1 范围和通道失败是否在目标创建前处理：代码已有显式校验，旧测试已覆盖非法通道/合法null默认；不把原正确行为当缺陷，也不重跑同一旧全集。
- H13-2 compensated视图会执行线性缩放，CSV回执却只照抄scaled请求位，可能错误描述输出；以非单位gain/补偿矩阵和独立算式核对后再判断。
- H13-3 用具名群体选择、保留原始整数DATA/校准的FCS交付及Python csv消费者核对raw/linear/compensated视图和回执，涵盖补偿显式scaled:false与空输出；兼容既有合法参数。

接受标准：只修已复现问题；数值真值由Python struct源字节/手工行向量公式给定，回执正确描述已选视图。最小范围、一次相关消费验证；未变MoonBit核心和桥接产物按SHA核对，未变Wasm/旧全量互通不重复。

## 收敛结果

H13-1未查出新问题：范围/通道检查已有且在创建目标前执行，本轮不改、不重复旧通过场景。H13-2查实：compensated隐含缩放，原回执照抄scaled:false，实际CSV已为[[4,4],[6,6]]；只改Node回执并增加compensated选择标志。

H13-3完成：8次CLI沿具名群体[1,2]→原始整数FCS→六种CSV请求；Python struct投影8字节、Fraction闭式gain/逆矩阵和csv消费核对raw/linear/compensated及空结果。省略/显式false/显式true的scaled与compensated:true均保持既有数值。前后selected FCS及补偿CSV逐字节相同，回执改正。

actionlint通过；新增的是带非单位gain/矩阵的实际消费核验，没有布尔OR镜像单元测试。MoonBit核心/API/桥接源码及compiled JS未变，12轮compare源码分支保持。没有功能拓展、没有扩大为科学解释或来源判断；旧封存/SDK/账号/根STATE保持。范围内无剩余必做项，停止调查与重复验证。
