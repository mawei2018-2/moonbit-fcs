> 2026-09-22 三份初审反馈后的当前判断：**已选定 Forth 替换方向，待公开与办理换题**。无明确实验室使用方，部分厂商样本不兼容；必须先由团队完成换题与公开地址，旧 Forth URL 不能充当新仓库。 本次差异说明：FlowIO/FlowKit 等成熟 Python 工具已解决这类交换问题。本项目贡献是 MoonBit 可复用实现与 JS/WasmGC 数据准备接口，未发现同范围公开 MoonBit 包不等于证明生态空白。 以下保留之前检索的固定提交与来源；此前“补足场景”不能理解为本次已解除价值异议。

# 编码前查重 · 2026-09-22

Mooncakes 搜索 `fcs` / `flow cytometry`，GitHub 仓库查询 `fcs moonbit` / `cytometry moonbit` / `flowio moonbit` / `flowkit moonbit`，并查看 GitLink 公开索引和官方赛事公开材料。四次 GitHub 查询均为 0 且 incomplete=false；Mooncakes 的 radioframe 命中指帧校验，不是细胞仪文件。本轮范围没有找到直接同范围 MoonBit 库；未取得完整报名名单、私有仓库或全代码索引，因此不声称首个/唯一。

编码前已排除 HEX/S-record（Zzqy-yi/firmware-image-toolkit）、EDID（BenPaoBaMingWangXing/edidkit）、MARC（Zongzuixi114514/moonmarc）、DBC、NMEA、UF2（Trylaney/moon-uf2）等已有 MoonBit 方向。

已有成熟方案包括 [FlowIO](https://github.com/whitews/FlowIO)、[FlowKit](https://github.com/whitews/FlowKit) 及专业分析软件。本项目不重新发明 FCS，不宣称超越它们；它提供 MoonBit 可直接使用、可编译到 JS/WasmGC 的文件处理核心，以及批次检查—筛选—保留原始事件位模式写出的组合任务。Node 不依赖 Python 才能运行，FlowIO 只在开发验证时使用。

与原 Forth 相比，依据是具体文件交换需求和已存在格式偏移问题，不依赖臆造的旧脚本/客户。本团队没有已确认的实验室使用方，因此当前贡献是可复用的实现和外部文件互通证据，而非落地规模。下一阶段应根据真实仪器样本完善兼容，不能用“继续堆测试数”替代用途验证。

完整原始检索位于交付总目录 `innovation-review-20260922/` 中的 `fcs-github.json`、`replacement-search.json`、`mooncakes.json`。检索会过时，提交前需由对接团队核对报名表及最终公开提交。


## 2026-09-23 继续实施前的核对

重新读取 [FlowIO官方API](https://flowio.readthedocs.io/en/stable/api.html)、固定参考提交的数据及 [ISAC FCS3.1规范](https://www.citometriagic.it/wp-content/uploads/2025/02/FCS_3_1.pdf)。FlowIO1.4.0已可读取G11，不能把兼容厂商填充的思路称为原创；本次增量是MoonBit显式选项、诊断、默认拒绝边界及已有数据选择/重写接口的接通。没有新增另一套FCS库，也没有复制FlowIO解析器。完整对照与未支持输入见 COMPATIBILITY.md。


## 2026-10-28 功能拓展09前的实时检索

通过Mooncakes官方站源码确认搜索端点后，实时查询fcs/cytometry/gating（每次上限20）。fcs返回本项目公开0.2.2和无线帧校验radioframe；cytometry仅本项目；gating返回16个模块，主要为CI、覆盖率、时序EventGate等用途，未返回同范围细胞术分层门控包。GitHub连接器对fcs language:MoonBit找到本项目，对cytometry/FlowIO/FlowKit与MoonBit组合未返回额外相关仓库。摘要/名称搜索不覆盖私有代码或完整报名名单，不能证明首个或唯一。原始查询和UTC见本轮09报告MOONCAKES-LIVE.json及RESEARCH原始响应。

[FlowKit官方](https://flowkit.readthedocs.io/en/latest/gating_strategy.html)已经成熟提供层级门、成员及父群体比例。09不声称算法首创；新增价值是已有MoonBit FCS交换核心中的GateStep/Population组合、I/A BigInt精确边界、原始事件身份，以及JS/Wasm直接消费和指定群体的FCS交付。实现未复制FlowKit源码或数据，例程原创MIT，无实验室用户或临床有效性证明。多文件平台、GatingML/FlowJo导入和自动门控不在本轮。


## 2026-10-28 通道名寻址增量10

沿用09同会话的Mooncakes/GitHub检索记录，本轮没有重复宣称完整重搜。补查[FlowKit Dimension](https://flowkit.readthedocs.io/en/latest/dimension.html)和[FlowIO官方教程](https://flowio.readthedocs.io/en/latest/notebooks/flowio_tutorial.html)：按PnN标识维度已有成熟方案，不是算法创新。增量是现有MoonBit分层门控/输出的精确名字映射、明确歧义错误、保留数字访问及可独立回读的RepOD文件交付。未复制代码/数据；无额外实验室使用或临床证明。

## 2026-10-28 指定群体直接CSV增量16

实现前重新查询Mooncakes官方fcs/cytometry（每项limit20）：fcs为本项目0.2.2与无线帧校验radioframe0.2.0，cytometry仅本项目。GitHub连接器fcs language:MoonBit返回本项目，cytometry language:MoonBit未返回额外仓库。此为有界名称/摘要检索，不覆盖私有代码、完整报名表或所有实现；原始回执见evidence/population-csv-20261028。

[FlowKit Session官方接口](https://flowkit.readthedocs.io/en/latest/session.html#flowkit.Session.get_gate_events)已能取得指定门内事件表，并单独选择补偿/变换；[官方教程](https://flowkit.readthedocs.io/en/stable/notebooks/flowkit-tutorial-part05-session-class.html#Extract-Gated-Event-Data)说明原样本事件索引保留。本次不是算法创新，而是将既有MoonBit群体成员直接连接CSV，避免当前RepOD流程的中间FCS，保持原始整数及显式视图，返回实际导出行的源Dataset索引。代码独立实现，无Python运行依赖；研究、场景/验收/兼容在实现前记录于RESEARCH.md。


## 2026-10-28 CSV可选索引列增量18

实现前重查Mooncakes fcs（limit20）及GitHub cytometry language:MoonBit，原始响应见evidence/csv-event-index-20261028；命中范围与16一致，不据此宣称生态唯一。当前CSV身份映射原在JSON回执，单文件交接需额外关联。

[FlowKit Session](https://flowkit.readthedocs.io/en/latest/session.html#flowkit.Session.get_gate_events)已有门内事件DataFrame；[pandas官方to_csv](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html)支持索引/索引列名写出。18只是已有MoonBit原Dataset索引在Node CSV中的可选序列化，默认格式保持，科学数值不变；不宣称算法创新，不复制同类代码、不引入pandas运行依赖。完整场景/验收/兼容在实现前RESEARCH.md记录。

## 2026-10-28 群体统计增量25

实现前fresh查询Mooncakes官方fcs/cytometry/robust_stats（每项limit20），fcs/cytometry相关结果与18一致；另确认[hxiuzheng/robust_stats](https://mooncakes.io/docs/hxiuzheng/robust_stats)已有通用统计能力。GitHub连接器cytometry language:MoonBit本次返回空列表。名称/摘要查询不能证明生态唯一、完整报名表或私有实现不存在，原始响应保留于25报告与本轮证据。

[FlowKit官方](https://whitews.github.io/FlowKit/)已有[门内均值比较例程](https://github.com/whitews/FlowKit/blob/master/docs/notebooks/advanced/compare-mfi-of-gated-events.ipynb)和[get_gate_events](https://flowkit.readthedocs.io/en/latest/session.html#flowkit.Session.get_gate_events)。本轮不重写统计算法或争取通用统计首创；仅将既有MoonBit门控成员、完整原通道矩阵和原有statistics连接成CLI population-stats，返回源索引且无需中间磁盘文件。内部有FCS内存副本，不宣称零拷贝、流式或外部实验室采用。代码独立实现，不引入统计包/Python运行依赖；场景、有限验收与兼容影响先记于本轮RESEARCH.md。

## 2026-10-28 群体统计报告通道增量26

实现前fresh查Mooncakes fcs/cytometry（limit20）与GitHub fcs language:MoonBit；相关结果仍为本项目与非细胞术radioframe，不证明生态唯一或私有/赛事项目不存在。[FlowKit Sample官方](https://flowkit.readthedocs.io/en/latest/sample.html#flowkit.Sample.get_events)已有区分数值视图、事件掩码及col_order通道列表的接口，本轮不主张这类选择方法首创。

差异仅是已有population-stats报告可用原PnN/数字混合选列，明确返回源channel_indices；完整原矩阵先补偿，再筛报告，未报告通道仍参与计算。省略/null保留25格式，成员索引和数值视图合同不变，无新统计算法或运行依赖。实现前场景/查重/验收与实际新核验见26报告及evidence/population-stat-channels-20261028；未重跑25全集或RepOD。

## 2026-10-28 群体成员窗口统计增量29

实现前fresh查Mooncakes fcs/cytometry（各limit20）及GitHub fcs language:MoonBit，相关结果仍为本项目与非细胞术radioframe；不证明生态唯一或完整赛事查重。[FlowKit Session](https://flowkit.readthedocs.io/en/latest/session.html#flowkit.Session.get_gate_events)已有群体事件表，[pandas iloc](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.iloc.html)已有按整数位置切片，本轮不主张位置选择或统计方法首创。

本次只将已有CSV的严格start/count合同接到population-stats：完整群体先选成员窗口，再沿用完整原矩阵视图与报告通道，明确区分群体数、窗口数和源成员索引。不同于pandas允许越界的切片，本库与现有CSV一样拒绝越界，不截断。默认格式不变，无pandas/Python运行依赖、自动按时间排序、滑动或批次平台。实现前合同与有限验收见29报告RESEARCH.md，原始回执及新消费者在本轮证据，未将旧运行算作本轮验证。
