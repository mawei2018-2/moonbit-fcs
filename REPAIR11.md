# 11轮：显式源事件列表的报告边界

范围仅为刚交付流程中的显式源索引报告→导出→外部读取。10封存件只读；本轮没有功能拓展或公开API变化。

## 实际缺陷

gate显式传events时，selected原来只依靠JSON层检查32位整数类型，直接返回数组；没有经过write的Dataset边界检查。N=3的events[3]、events[-1]、events[0,3]均退出0返回原数组，N=0甚至报告0号事件。相同非法列表交subset原本会被write拒绝，报告和文件交付的有效性不一致。

cmd/bridge/main.mbt仅补对当前选中Dataset的逐项范围检查：0<=event<events。先验证完整列表再返回；不排序、去重、截断或拒绝合法重复。空列表仍有效；subset的events:null默认全选语义保持。库算法、类型、标准编码和原有门控不变。

## 独立验证与实际消费

- before原始成功回执保存负数/上界/混合非法及空表假索引，subset原拒绝和合法逆序重复也保留。
- 原创struct字节输入的37次CLI调用通过：N=0/1/3，负数/上界/混合无效全部拒绝且无目标文件；空列表、顺序和重复逐字节核对。
- 一事件源允许[0,0,0]导出三行；链式3/1事件数据集分别按自己的TOT验证，保留A/B通道和相应源值，不能借用第一个Dataset或文件合计事件数。
- 复用10轮冻结inner群体中的[14232,10,7454,14232]。未重新计算662群体；5次真实消费调用中，合法列表报告/导出保留次序和重复，非法边界明确失败。
- FlowIO1.4.0 preprocess=False读取4行Time/FSC-A/SSC-A，与源DATA直接投影的12值、48字节一致，许可/署名及修改说明随输出保存。输入RepOD原文件SHA保持不变，数据为CC BY4.0。
- check/JS release构建、格式和本地CI语法通过；新增测试工具进入CI。只修改JS桥接事件选择分支，未重跑未变的核心/Wasm/旧全量数据或下载链。

## 复现

```sh
moon build --target js --release --deny-warn
python tools/check-event-selection.py /path/to/NEW_SYNTHETIC_DIRECTORY
python tools/check-event-selection.py /path/to/NEW_REAL_DIRECTORY --repod-only
```

最后一条使用开发用FlowIO1.4.0/NumPy，库与Node运行仍无Python依赖。实际输入/日志/源与编译身份另见11轮报告及evidence/event-selection-20261028。

边界检查只判断索引是否属于选中的Dataset，不自动证明另一文件中相同事件号的来源关系；调用方仍须匹配源身份。没有推送、发布、远端CI/native结果或赛事验收结论。旧公开API和05—10修复/封存保持。
