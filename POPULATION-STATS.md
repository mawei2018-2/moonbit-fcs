# 指定群体的通道统计

`population-stats`把已有命名群体与MoonBit通道统计接通：用户不必先保存群体FCS/CSV，再另写汇总代码。它输出JSON，原`stats`仍统计整个Dataset并保持数组格式。

```sh
moon build --target js --release --deny-warn
node examples/run-gate-plan.mjs /path/to/NEW_DIRECTORY
node tools/fcs.mjs population-stats /path/to/NEW_DIRECTORY/events.fcs --options examples/population-stats.json
node tools/fcs.mjs population-stats /path/to/NEW_DIRECTORY/events.fcs --options examples/population-stat-channels.json
node tools/fcs.mjs population-stats /path/to/NEW_DIRECTORY/events.fcs --options examples/population-stat-window.json
```

例程为原创MIT数值样例，不表示生物学分类。选中id_window成员为源索引2、5；第一份选项默认报告全部原通道，第二份报告M/X/M及源通道号2/0/2。第三份在该群体中start1/count1，只统计源事件5，完整群体数仍为2。ID精确门控仍使用65位整数，数值统计本身为Double。

请求必须有`gates`和`population`。计划格式沿用[GATE-PLANS.md](GATE-PLANS.md)；顶层`scaled`/`compensated`选择统计视图，每步内的标志仍只控制门控。补偿隐含缩放，包括显式`scaled:false, compensated:true`；无矩阵时沿用线性缩放，compensated表示所选视图，不证明源有矩阵。

返回字段：

- `population`和`population_events`说明完整群体及其成员总数；`source_event_indices`只列实际统计窗口的原Dataset零起始成员。dataset选择非零时，索引仍属于该Dataset。
- 显式提供start或count时另有`events`，表示实际窗口行数；不传两者保持原全群体格式，没有这个字段。
- `channel_names`与`statistics`数组逐项对应；默认按完整原通道顺序，指定channels时按请求顺序。
- `statistics`保留原ChannelStats语义：count为有限测量数、nonfinite单独计数，minimum/maximum/mean及样本variance按可表示性出现。空群体每通道count/nonfinite为0、数值字段省略；单个有限值没有样本方差。
- `scaled`/`compensated`报告实际所选统计视图。空群体也保留这些标志。

可选布尔开关`include_read_report:true`追加`read_report`对象：`source_sha256`绑定读取时的完整原输入字节；`dataset`为所选Dataset零起始号（默认0）；`version`和`warnings`直接来自该原Dataset的inspect报告。warnings保留实际发生的读取修正，不因请求兼容模式就生成警告，也不取自内部已规范化的统计副本。多Dataset文件的哈希覆盖完整输入，warnings只对应所选Dataset。

省略或传false保持原schema与stdout字节，不增加read_report。true只附加来源信息，成员、窗口、通道、视图、统计值/有效性及严格/兼容接受政策均保持；错误仍只返回stderr/非零退出码，没有部分JSON。该报告不替代完整格式验证、来源真实性验证或科学判读。实际RepOD单次交付示例（新目录须不存在）：

```sh
node examples/repod-population-read-report.mjs /path/to/NEW_DIRECTORY
```

示例的`statistics.json`统计inner群体成员窗口start1/count2、Time/FSC-A两列，同时保留原文件4项真实偏移空格修正和原SHA-256；不另跑inspect或写中间FCS。Bronisz署名、DOI10.18150/JOLWGT及CC BY4.0许可随输出保留。源码原文件、DATA和ANALYSIS保持。

可选`channels:["M",0,"M"]`按精确PnN/数字混合选择、换序或重复报告项；返回`channel_indices`原Dataset零起始通道号，例子为`[2,0,2]`。只计算所请求的输出统计，重复项复用同一结果；补偿所需源测量通道和完整矩阵仍保留。无关输出通道的不可用校准不会阻断请求，真实非零依赖的校准错误仍失败。空数组返回空通道/统计数组，仍报告实际窗口的源成员；省略或null保持原全通道格式及行为，不加channel_indices。缺失/歧义名字、非法数字索引和类型失败，空群体也校验；数字字符串只作为PnN，不转索引。重复源标签可用数字位置区分。

可选start/count沿用CSV的群体成员位置：start默认0，count默认完整群体数减start，保持原顺序，不按Time或ID排序。例如成员为0/2/4/5/7，start1/count2选择原事件2/4。参数须为非负精确32位整数，start不能越过群体末尾，count不能越过剩余成员；不截断越界请求，null不代替省略。合法末尾/零长度/空群体窗口返回空统计；坏群体和通道仍失败。每通道count/nonfinite反映实际窗口，均值/方差使用其中有限值，不能以population_events作为统计分母。

命令支持解析选项dataset、strict、allow_exclusive_end、latin1、allow_text_padding、allow_offset_padding，其余接受gates/population/scaled/compensated/channels/start/count及布尔include_read_report。metadata、encoding等不适用选项报错。坏计划/群体、非布尔视图/报告标志及C/U模式也失败，不返回部分统计。旧stats/CSV/门控命令的参数合同不变。

实现先取得完整群体成员，再取实际窗口，以全部原通道构造私有FCS内存副本，复用现有MoonBit statistics。指定channels时仅求请求输出的统计，但其实际所需测量值仍从完整矩阵/原通道取得；这与先投影FCS再对主子矩阵补偿不同。默认/ null仍求全部通道。私有副本显式丢弃已失效ANALYSIS，源文件的字节和ANALYSIS保持。没有临时磁盘FCS，仍有完整门控、内存选择/拷贝和所请求统计的计算开销；不宣称零拷贝、流式或自动滑动分析。

可运行反例与闭式数值见[校准依赖示例](examples/stat-channel-dependencies/README.md)：同一个可读源的公开单通道统计和CSV已能得到Target的`[2,1]`，群体统计现在也能交付，而不计算无关的Unavailable输出。输入gain=0的警告与原严格读取政策保持，不把它宣称为严格标准合法输入。

组合入口复用现有MoonBit核心/API，不增加统计方法、自动分类、批次报告或临床结论。独立标准库核验入口为：

```sh
python tools/check-population-stats.py /path/to/NEW_DIRECTORY
python tools/check-population-read-report.py /path/to/OTHER_NEW_DIRECTORY
```

25记录以原创MIT位流/struct/Fraction预期检查视图、非连续成员、空/单例、非有限/极值、非零Dataset、ANALYSIS及错误路径；另以既有CC BY4.0 RepOD原F32字节独立选取662事件，核对全部26通道统计。它是25历史验证，未在通道增量中重跑。

通道报告增量独立核验：`python tools/check-population-stat-channels.py /path/to/NEW_DIRECTORY`。以新原创MIT数据验证完整矩阵依赖、原值/缩放/补偿、名字/索引混合换序、重复/空报告、源标签歧义、非零Dataset和原样保留的25通道请求。省略/null的兼容格式也核对。当前通道选择证据见evidence/population-stat-channels-20261028；25历史与许可在evidence/population-stats-20261028。

窗口增量独立核验：`python tools/check-population-stat-window.py /path/to/NEW_DIRECTORY`。新原创MIT数据和实际同窗口CSV核对非连续成员位置、首/中/尾/空窗口、完整矩阵/重复报告列、窗口内非有限计数、非零Dataset及严格错误路径；保留25原start0样例验证新能力。没有重跑旧全集/RepOD；研究与当前回执见evidence/population-stat-window-20261028。
