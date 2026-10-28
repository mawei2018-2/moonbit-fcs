# 18轮实现前：CSV单文件交接中的源行索引

只研究一个候选：可选event_index_column，把已有原Dataset事件索引写为CSV首列。它不改变科学数据或身份定义。

## 当前实际操作缺口

17真实消费CSV只有Time/BUV395-A列，原事件[23,28,40]在另一份JSON回执。接收方只拿CSV后做筛选/排序，需先按行位置手工关联回执，才能保留原事件索引。16已有准确source_event_indices，缺口是单文件交接便利性，不是原值丢失或解析bug；现有回执关联流程继续可用。

## 生态与成熟同类

本轮重查Mooncakes官方fcs（limit20）及GitHub cytometry language:MoonBit，原始响应存MOONCAKES-LIVE.json/GITHUB-CYTOMETRY.json。前者为本项目0.2.2与无线帧校验radioframe0.2.0，后者未返回仓库；这是有界名称/摘要检索，不覆盖私有代码、完整报名表或全部实现，不作唯一性宣称。

[FlowKit Session](https://flowkit.readthedocs.io/en/latest/session.html#flowkit.Session.get_gate_events)已有门内事件DataFrame；16同日查阅的[官方教程](https://flowkit.readthedocs.io/en/stable/notebooks/flowkit-tutorial-part05-session-class.html#Extract-Gated-Event-Data)说明保留源事件索引。[pandas官方to_csv](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html)支持index/index_label序列化索引列。这是成熟表格交接方式，不是新分析算法。本项目差异仅是把既有MoonBit成员索引在Node CSV层可选写入文件，运行仍不依赖Python/pandas，不复制同类代码。

## 场景、验收与兼容

- CSV选项event_index_column为非空自定义列名，列写在科学数据前。省略/null默认关闭，原表头/数据/回执保持；普通CSV和群体CSV都可启用。
- 值是选中原Dataset的零基事件索引，不是群体内位置、仪器ID或文件全局行号。它不参与缩放/补偿。群体切片、视图与已有source_event_indices保持原合同。
- 索引列名不能与所选数据列同名，错误在目标创建前拒绝；未选中的通道名不造成冲突。名称按CSV原转义方式写出，包含逗号/引号/Unicode/换行仍可读取。
- 实际csv.DictReader消费者核对非连续成员、切片、精确原始整数、普通CSV范围、补偿视图、空结果、nullable默认、坏/冲突列名及跨块索引连续性。
- 现有RepOD例程新增可选命令行模式，默认调用不变。新模式写source_event_index列；下游仅凭CSV先排序/筛选，再按该列与16冻结来源/数据核对。复用旧预期，不重跑17补偿组合或16旧套件。

只修改Node CSV布局、现有例程的可选模式和必要文档/核验/CI；不改MoonBit核心/API/编译产物。没有自动身份认证、文件合并、任意成员排序、门控新算法或科学列重命名。
