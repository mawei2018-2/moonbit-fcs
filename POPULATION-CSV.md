# 指定群体直接导出CSV

需要群体事件表时，可以从原FCS直接执行门控并导出CSV，不再先写一个selected.fcs。原subset→csv流程继续可用；本增量只连接已有门控成员和数值读取，没有新增门控算法或MoonBit公共类型。

## 运行

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs csv input.fcs selected.csv --options selection.json
node examples/repod-population-csv.mjs /path/to/NEW_DIRECTORY
```

selection.json示例：

```json
{
  "gates": [
    {"id":"band","compensated":true,"bounds":[["B",0,11]]}
  ],
  "population":"band",
  "channels":["ID","B","A"],
  "start":1,
  "count":2
}
```

门控在原Dataset上计算，成员按原索引升序。start/count按成员列表的位置切片，不是源文件连续行号；省略count表示从start到群体末尾。顶层scaled/compensated仅选择CSV输出视图，每一步的标志选择该步门控视图。因此补偿条件选中的事件仍能输出原始整数，也能显式输出缩放或补偿值。

补偿输出先在原Dataset的完整补偿通道空间求值，再取CSV列；它可能与先减少FCS通道、再用主子矩阵补偿的结果不同。

原始I/A继续用精确十进制字符串；缩放/补偿是已有Double视图。channels仍支持精确PnN或数字索引及混合列表，不引入别名猜测。合法空群体或群体末尾count=0输出表头。计划、群体、列和范围错误在创建目标前失败；已有输出不覆盖。

回执保留written/events/scaled/compensated，并为直接群体导出增加population、population_events和source_event_indices。population_events是切片前群体成员数；source_event_indices与实际CSV行一一对应，指options.dataset选中的原Dataset，默认Dataset0。它不是仪器事件ID、文件全局行号或来源认证。

## 将源索引写进CSV（可选）

在options中增加`"event_index_column":"source_event_index"`，就会在CSV首列写入同一原Dataset的零基事件索引。省略或null默认关闭，原CSV表头/数据/回执不变。列名可自定，但必须是非空字符串，且与所选科学数据列不同；冲突在创建目标前失败。未选中的通道名不造成冲突，原有科学数据列不自动改名。

索引不参与缩放或补偿；群体切片后依然是原Dataset索引，普通CSV则保留source start/count对应的行号。启用时回执添加event_index_column，群体回执的source_event_indices继续保留。空结果也包含所选索引列表头。

现有真实例程的默认模式不变，可另运行：

```sh
node examples/repod-population-csv.mjs /path/to/NEW_DIRECTORY --event-index-column source_event_index
```

此模式输出source_event_index/Time/FSC-A三列。下游可只读取CSV进行排序/筛选，再通过索引列关联原事件，无须先拼接JSON回执。例如Python标准库消费者：

```python
import csv
with open("inner.csv", encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))
rows.sort(key=lambda row: float(row["FSC-A"]), reverse=True)
source_event = int(rows[0]["source_event_index"])
```

索引列只是调用方选定源Dataset中的行号，单独CSV仍不认证源文件、实验样本或仪器ID。已有JSON来源回执仍可用于文件/计划身份记录。

CSV只读源FCS，不写FCS或修改ANALYSIS，所以不需要为CSV请求drop_analysis。原有FCS子集写出的ANALYSIS保护保持。列表模式限制保持，C/U仍用直方图API。未指定群体的原CSV合同不变；本增量不新增CSV对独立events/bounds/vertices选择器的支持。

## 将多个群体成员关系写入CSV（可选）

需要把多个重叠/分层群体交给只读CSV的脚本时，在现有options中增加：

```json
{
  "gates":[
    {"id":"band","bounds":[["X",0,10]]},
    {"id":"child","parent":"band","scaled":true,"bounds":[["Y",1,2.5]]}
  ],
  "channels":["X","Y"],
  "event_index_column":"source_event_index",
  "population_columns":[
    {"population":"band","column":"in_band"},
    {"population":"child","column":"in_child"}
  ]
}
```

非空population_columns要求gates；population省略或null时，导出原Dataset的start/count事件窗口并标注每一行。另指定population则保持已有“先选该群体，再取成员窗口”的行为。原科学列之后按请求顺序追加0/1，源索引仍可选放首列，回执仅增加同顺序的population_columns映射。索引指所选Dataset，不是文件全局行号或仪器ID。

成员关系由同一个既有MoonBit完整gate_plan求得一次，按原事件号映射；每步的raw/scaled/compensated决定门控，顶层视图只决定科学数据列，不重新解释0/1。空群体/零行窗口仍保留完整表头，坏计划和引用仍校验。没有新增门控/补偿算法、推断分类、布尔门依赖图或生物学标签。

column须为非空明确字符串，与实际所选科学列、源索引列以及其他成员列不重名；未导出的源通道名称可用作明确别名。精确标签不裁剪/猜测，逗号/引号/换行/UTF-8使用原表头转义。同一群体可用不同别名重复报告，复用同一成员集合；原数字选列允许的重复科学标签仍保留。不存在的群体、坏格式/别名或计划在创建目标前失败，空窗口也不隐藏它们。

此选项由Node消费，不作为新参数传入MoonBit。省略、null或[]完全关闭标注并保持旧schema/行为；关闭时，gates未配population仍按原合同失败。其他命令、原CSV及--atomic-output发布/cleanupPending合同保持。

完整原创输入、独立成员索引、65位ID及CSV-only接收脚本见[群体成员列例程](examples/population-columns/README.md)。接收脚本能只从收到的表中核对成员计数/交集、重排后逐行对应源索引和科学值。它是自编的实际文件消费者，不是第三方采用或临床有效性证明。当前仍整文件/群体结果驻留内存，不宣称流式或性能加速。

```sh
python tools/check-population-columns.py /path/to/NEW_CHECK_DIRECTORY
```

独立验收使用手写原始I65/16/16源与完整CSV期待、固定父子/重叠成员、selected Dataset和非连续群体窗口；60013行模13/7原值与三个成员标志逐项读回，覆盖多个块。原公共API可组合得到成员结果，本增量交付的是完整文件接收链，不主张算法首创。

## CSV完成后发布最终名称（可选）

只取得最终文件路径、没有生产进程stdout/退出码的接收方，可使用：

```sh
node tools/fcs.mjs csv input.fcs received.csv --atomic-output --options selection.json
```

此标志必须在输入/输出路径之后，可在`--options FILE`之前或之后；由Node主机消费，不转发为MoonBit请求参数。三项位置参数中的`--atomic-output`仍可作为原有输入/输出文件名；只有额外尾随标志才选择新模式。只适用于csv，默认命令的CSV字节、回执和错误保持。门控/窗口、精确整数、表头/源索引及科学视图继续走原生成路径。

新模式在目标父目录独占创建本次拥有的暂存文件，写完并关闭后用不替换目标的硬链接发布最终名称。正常发布前异常不生成本生产者的最终文件，也不返回成功回执；只清理本次拥有的暂存项。已有或并发创建的目标不覆盖、不删除，不退回覆盖rename或部分copy。原始FCS只读。等待旧CLI退出0再消费的调用者已经可取得完整CSV，无须为了这个流程改用新标志。

成功回执只在新模式增加`atomic_output:true, cleanupPending:false`。发布是提交点：若发布已完成、随后暂存清理失败，完整目标保留，退出0，改为`cleanupPending:true`并附绝对`stagingPath`和限长告警，例如`warning:"CSV published; staging cleanup is pending (EACCES)."`。调用方可核对返回的本次暂存路径后清理它；不要删除已发布目标。

发布前错误退出1且stdout为空，stderr形如`atomic CSV write failed (EIO); no output was published by this invocation.`；阶段为staging/write/close/publish，IO代码只保留1–40字符的ASCII大写字母/数字/下划线，否则为UNKNOWN。若正常异常处理中的暂存清理也失败，错误附上实际暂存路径与清理待办；不将既有或并发目标称为本次成功结果。

需要目标父目录的本地文件系统支持独占创建/硬链接；不支持时明确失败，不降低为copy。范围不含网络/对象存储、fsync或掉电持久性、watcher恰好一次投递、CSV与JSON回执多文件事务、强杀后自动清理，也不扩展到FCS写出命令。自行编写的[CSV-only文件接收方](examples/atomic-csv/README.md)验证完整文件交付，不代表真实第三方或机构采用。

独立验收使用完整原创I16输入和手写CSV字节、100001行模65536规则、65位整数及原门控/补偿窗口对照。外部IO检查点让另一个Python标准库进程在真实写入期间尝试打开最终路径，覆盖迟发EIO、close/link错误、目标竞争及发布后清理告警，不依赖睡眠或fs.watch时序，也不向生产代码加入测试开关：

```sh
python tools/check-atomic-csv.py /path/to/NEW_CHECK_DIRECTORY
```

## 真实文件例程与独立预期

RepOD例程离线读取已许可文件96804，复用已有inner数值门控，只导出Time/FSC-A两列。执行inspect保存4条显式偏移空格兼容警告，再直接CSV，共2次CLI；输出662事件、1324值、原Dataset事件索引回执及来源/署名/CC BY4.0说明，不生成中间FCS。数值阈值只是格式交换示例，没有生物学分类结论。

16轮实际消费以Python csv读取交付表格，用10轮冻结成员和原始F32源字节直接投影核对1324值；CSV字节与既有两步链冻结结果相同，原文件SHA保持。没有重跑旧FlowIO或全量交换。

18轮索引列模式另经实际CSV-only DictReader消费：662个索引与16冻结源映射一致，1324个科学值保持；排序/筛选后332行仍逐行对应源事件。新增14次合成调用覆盖非连续成员/切片、原始大整数、索引不被补偿、空表、nullable默认、特殊表头、列名失败，以及跨块782个索引和1564个科学值哨兵。没有重跑16旧套件或17补偿组合。

```sh
python tools/check-population-csv.py /path/to/NEW_CHECK_DIRECTORY
```

开发核验仅需Python标准库：struct/Fraction/csv构造独立预期，19次调用覆盖非连续成员、群体切片、输出视图独立、原始大整数、源ANALYSIS只读、空群体、创建前失败及783×128共100224个跨块值；一个受影响的非群体切片正对照和不可覆盖输出也通过。核心/公开API/桥接源码及编译JS身份未变，没有为未变MoonBit代码重复build/Wasm/旧测试。

## 价值与边界

现有RepOD例程原先需要subset写FCS再读CSV；直接导出减少一个用户可见的中间文件，且回执保留导出行与原Dataset的映射。源文件仍整体载入内存，门控及成员列表也在内存中，不宣称流式、无限规模或速度基准；大群体的索引回执也可能很大。

[FlowKit Session](https://flowkit.readthedocs.io/en/latest/session.html#flowkit.Session.get_gate_events)已有指定门内事件表和独立输出处理参数；[官方教程](https://flowkit.readthedocs.io/en/stable/notebooks/flowkit-tutorial-part05-session-class.html#Extract-Gated-Event-Data)说明保留原样本索引。此增量沿用成熟流程，差异是已有MoonBit精确整数/门控接口的Node连接，运行无Python依赖，不宣称算法首创或生态唯一。

实现前当前Mooncakes/GitHub检索、原缺口和完整验收见evidence/population-csv-20261028/RESEARCH.md。未新增GatingML/FlowJo导入、批次平台、自动身份认证、降维补偿等价保证或外部采用证明；未推送、发布、远端CI或赛事验收。
