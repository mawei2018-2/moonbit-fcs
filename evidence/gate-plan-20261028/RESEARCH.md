# 09轮检索记录与引用

- Mooncakes实时查询采用[官方站源码](https://github.com/moonbitlang/mooncakes.io/blob/f0c100a5a6d77bc519f9c5d4ed6a8cee8628d695/src/page/home/server_search.mbt)中的/api/v0/search?kw=...&limit=20，对fcs/cytometry/gating均取得HTTP200，响应与UTC存入MOONCAKES-LIVE.json。web读URL工具不能访问JSON端点，随后按已核实端点以Python只读获取，没有猜测路由。结果限制20项且摘要搜索非全代码索引。
- 本项目公开[Mooncakes页](https://mooncakes.io/docs/mawei2018/fcs%400.2.2)当前返回0.2.2；本地0.5.0不能冒充已发布。无线radioframe命中FCS指frame check sequence，与细胞术文件/分层门控无关。其余gating命中的CI门禁、时序EventGate也不提供本项目的FCS源索引/格式交换合同。
- GitHub连接器查询fcs language:MoonBit、cytometry language:MoonBit、cytometry MoonBit、FlowKit MoonBit、FlowIO MoonBit、flow cytometry language:MoonBit；原始响应保存。仅发现自己的FCS仓库；泛gating检索有无关用途项目，不声称完整生态空白。
- [FlowKit官方层级教程](https://flowkit.readthedocs.io/en/latest/notebooks/flowkit-tutorial-part03-gating-strategy-and-gating-results-classes.html)已经展示父子门、成员与结果计数。[官方结果API](https://flowkit.readthedocs.io/en/latest/gating_results.html)提供相对父群体和总事件的比例。新能力参考成熟工作流概念，在已有MoonBit门控与无损FCS交换接口上独立实现；不复制其源码或数据，不声称科学算法首创或取代其完整分析生态。

检索在实现前完成，只支持当前有限公开范围的差异判断；不覆盖未公开报名名单/私有代码，也不证明外部采用。
