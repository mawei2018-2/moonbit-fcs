# implementation-03 CLI身份与小范围互通历史记录 · 2026-10-28

以下为implementation-03当时的源码身份与核验，不作为深入修复05新核心的当前绑定。05修复和新回执见[REPAIR05.md](REPAIR05.md)。03当时保留核心/API/CLI，无算法重构，新增可复现tools/check-current-cli.py和材料校准。

历史FlowIO回执tools/fcs.mjs的SHA256：be2a12ca406b71a07234012842997e59b47e7a9d885a627aea3a25e9d856a881。
当前：ed00f45986dadcb3f8ea727e3e7f7bd13f560bc0a89f3cf14ffb0b9528b721a8，与2026-10-20的0.5封存包和2026-10-27冻结包逐字节一致。
对应旧SHA的CLI源版本不在这两份可取得包中，无法重建提交原因；源码差异不能解释成FCS的TEXT排版，本轮不改CLI凑旧SHA。

03当时固定工具链重建bridge为1a6d5ad5cebfb0ab064ce612c8c4b1c7a84b3faae5dcda8d033fb0cc4074b686，与历史deep独立回执一致；05修改核心后不再沿用该build绑定。
新互通回执绑定当前CLI/核心/build，补齐当前路径证据，不推翻旧结果或宣称所有历史路径无回归。

| 本轮验证 | 范围/结果 |
|---|---|
| check / JS release build | moonc0.10.14+7d59c7ec9、deny-warn，退出0 |
| FlowIO→CLI→FlowIO | 250×4合成值，门控后50事件、3通道及矩阵重排，通过 |
| CLI→FlowIO | 大端F与D各2×2，通过 |
| 真实小投影 | RepOD96804，事件[0,7160,14319]、通道[2,0,1]；核对9值、选后4值、末事件边界1值 |
| 字节/错误 | DATA精确投影；越界事件不创建输出、负start拒绝、已有输出保留、截断拒绝 |

参考Python3.12.14、FlowIO1.4.0、NumPy2.5.3、Node24.11.0。原始命令/结果见[evidence/current-cli-20261028](evidence/current-cli-20261028)；复现见README。
投影由Python直接读取源字节生成，不以MoonBit创建/回读作oracle。源文件未改；派生目录保留CC BY4、作者Bronisz, Agnieszka、DOI10.18150/JOLWGT、文件96804及修改说明。

55项任务、宽整数/ASCII/CU/补偿及完整RepOD372,320值场景保持历史身份，本轮未重跑。
03当时历史deep回执的源码/build身份一致，无MoonBit逻辑修改。05已新增真实bug回归并验证相关双端范围，仍保留公共API及任意位宽合同。
本轮不证明所有厂商、临床有效性、远端CI或赛事通过；代码、参考工具、规范和研究数据许可各自适用。
