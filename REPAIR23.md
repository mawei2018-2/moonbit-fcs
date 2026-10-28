# 23轮：ASCII→I的原值、有效位与校准

本轮修复真实转换缺陷，无新API或功能拓展。22及此前封存只读保留，Node适配和既有群体/CSV/源索引接口不改。

## 失败与主因

公开create成功生成Signal=[20,21,5]、PnR=10、自由ASCII源；strict inspect无警告，原门控[19,22)命中[0,1]。原rewrite I8退出0且DATA仍为[20,21,5]，但沿用PnR10，I读取只保留ceil(log2(10))=4位，values/CSV变成[4,5,5]，同一门控变空。8次before命令和原始回执保留。

这是当前已接受接口的保真问题，不把本例的规范合法性冒称为独立标准认证。07已处理F/D→I的目标范围；ASCII原整数不经PnR掩码访问，原write只复制范围，遗漏A→I的同类有效位后果。

## 最小修复

write.mbt仅新增ASCII→I范围分支。按实际导出事件/通道的BigInt值检查所需位数；线性通道及现有Time tick语义必要时用最大所选值+1补范围，保留原gain/Time刻度。值位数已被原PnR覆盖时不改范围，包括值20、PnR17这种非二次幂正对照。

对数探测器的缩放依赖原范围；若必须改范围才能在I中保存原值，则抛出不可表示错误，避免原值或校准静默变化。原有效位足够的对数转换仍成功，普通ASCII改写/源读取不收紧。真实位宽不足与负数→无符号I仍按原规则失败；不是全局拒绝ASCII越过名义范围的数据。

## 验证与实际消费

- 7项新回归在JS与Wasm-GC各通过7项：固定/自由ASCII、双端序、gain、顺序/重复事件、仅所选/空事件、PnR1单比特、非二次幂对数正对照/不可表示错误、Time tick例外及129位BigInt范围计算。
- 独立ASCII/struct/bit-reader/PnR掩码、Fraction gain和对数闭式预期，核对33次相关CLI；实际CSV和门控验证原值恢复为20/21/5、命中恢复[0,1]，gain2视图保持10/10.5/2.5。
- 初始独立工具在第23个命令遇到输入生成器追加第二个$P1E的坏样例，未进入对数转换。原输入、失败日志及工具快照保留；22个已过范围调用与断言证据保留，修正同宽元数据token构造后只补11个余下调用。修复期间产品源码未再改变，没有重跑已过调用或两端新测试。
- check/info/JS release/局部格式及CI语法通过；公开mbti、Node CLI、桥接源码不变，核心write与compiled JS有新身份。before/after桥接JS副本及SHA另存本轮报告。

```sh
moon test ascii_range23_wbtest.mbt --target js --deny-warn
moon test ascii_range23_wbtest.mbt --target wasm-gc --deny-warn
moon build --target js --release --deny-warn
python tools/check-ascii-to-integer.py /path/to/NEW_DIRECTORY
```

最后一条默认执行完整33调用；本轮记录的--section calibration用于失败样例修正后的有界续验。开发核验只需Python标准库，运行库/Node无Python依赖。输入和预期原创MIT，未下载新数据，未复跑旧群体CSV/索引列/多Dataset/时间补偿套件或旧全集。

范围是已经接受源在目标I中的可表示性，不承诺所有厂商、任意Double精度或对数参数自动重校准；没有推送、发布、远端CI或赛事验收。完整证据和当前源/编译身份见evidence/ascii-range23-20261028及23报告。
