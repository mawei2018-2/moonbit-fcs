# 第26轮实现前研究：统计报告的通道选择

## 场景、查重与差异

25的population-stats已提供命名群体、源成员索引、全部原通道统计和独立视图；用户只要某几个标记或特定顺序时，目前channels被明确列为不支持。此为有限功能缺口，不把25定义内的行为冒称缺陷。本轮只扩报告选择，不增加中位数/新统计量、切片、批次平台或新文件格式。

本轮fresh查询Mooncakes官方fcs/cytometry，各limit20；fcs命中本项目0.2.2与radioframe0.2.0，cytometry仅本项目。GitHub连接器fcs language:MoonBit命中本项目。原始响应保留，不把名称/摘要搜索当作生态唯一或完整报名查重。

[FlowKit Sample官方](https://flowkit.readthedocs.io/en/latest/sample.html#flowkit.Sample.get_events)的get_events区分raw/comp/xform，并可用col_order指定PnN列表及顺序；get_channel_events支持指定通道和事件掩码。按视图选择通道是成熟做法。本轮独立复用现有MoonBit通道解析，不复制同类代码，不争取统计方法首创。差异仅是本项目现有群体统计报告可按源通道索引/精确名字选择，同时保留完整补偿计算和源事件身份。

## 有限合同与兼容

population-stats新增channels数组，复用已有channel-indices的数字/精确PnN混合寻址。只在完整原通道statistics计算后按索引取报告项，不向私有FCS的write传channel_indices，不删除补偿依赖。支持换序、重复和空数组；数组请求返回channel_indices（原Dataset零起始通道号），与channel_names/statistics逐项对应。

省略或null仍返回25原来的全通道格式，不加channel_indices。源事件索引/群体行数不受通道选择影响；每步flags控制门控，顶层flags控制统计，compensated仍隐含scaled。坏索引/类型、缺失或歧义名字在空群体下也失败；数字字符串只按精确PnN查找。原合法请求不收紧。

25核验工具中的channels:[0]原样例保留，按本轮新合同改为成功并核对输出；其他失败请求保留。该一项已变更合同的样例只单独新验，不运行25整套20CLI或RepOD，不删除历史失败输入/日志。默认控制使用新的源数据，不重计旧回执。

## 验收及运行边界

新原创MIT输入以独立位流/struct/Fraction预期核对Target单列原值/缩放/补偿、混合换序/重复、完整补偿对未报告Driver的依赖、源成员不变、空列/空群体、无选择格式兼容、重复PnN数字寻址/名字歧义、非零Dataset以及坏选择器。26脚本只导入25的原始样例生成/独立Fraction辅助函数，不调用其main。保留25已有不支持案例原输入，新增断言验证扩展而非降低数值合同。

只运行新相关消费者、Node语法与actionlint；无MoonBit核心/API/编译更改时不运行SDK/依赖/后端全集。Node缓存与TEMP/TMP只写本轮报告，Python-B及sys.dont_write_bytecode禁止辅助模块pyc；不写全局SDK/旧报告缓存。一次相关干净验证通过后只封包读回，不重复未变旧检查。无推送、发布、赛事提交或外部采用声明。
