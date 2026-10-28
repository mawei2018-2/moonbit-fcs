# MoonBit FCS 0.5.0

纯MoonBit FCS读写、精确整数门控、直方图与荧光补偿视图。模块 `mawei2018/fcs`，代码MIT；[仓库](https://github.com/mawei2018-2/moonbit-fcs)。本文对应本仓库0.5.0源码接口；模块名保留为mawei2018/fcs，请从源码构建。实际CI结果以本仓库Actions的提交关联回执为准。当前评委稿为[PROPOSAL.md](PROPOSAL.md)，账号命名申报稿保留作历史记录。

## 构建与运行

使用[固定工具链](TOOLCHAIN.md)及Node.js≥22（本轮24.11.0）。Node只处理文件/JSON；FCS解析、编码、门控、矩阵与投影在MoonBit核心。API接收内存Bytes，CLI读取整个文件，不宣称流式或无限资源。

```sh
moon update
moon check --deny-warn
moon build --target js --release --deny-warn
node tools/fcs.mjs create /path/to/NEW.fcs --options examples/events.json
node tools/fcs.mjs inspect /path/to/NEW.fcs
node tools/fcs.mjs subset /path/to/NEW.fcs /path/to/SELECTED.fcs --options examples/gate.json
```

所有输出要求新路径。真实文件完整交换例程为 `node examples/repod-selection.mjs /path/to/NEW_DIRECTORY`，详见[RepOD交换](REPOD-EXCHANGE.md)。RepOD原文件的偏移空格须显式兼容；调用方检查警告，strict不能与兼容选项组合。

CLI提供inspect/validate/metadata/stats/values/gate；populations/population-stats；subset/rewrite/csv；create/create-histogram；histogram/histogram-axis/histogram-bin/compensation。JSON通过 `--options FILE.json` 传入。

`populations`执行命名分层门控计划，gate/subset可选择指定群体。完整原始索引、父群体计数和65位ID导出示例见[门控计划](GATE-PLANS.md)。

csv也可直接接受gates/population，无需中间FCS；start/count切片群体成员，回执带实际导出行的源Dataset索引。门控与输出视图分别指定，完整用法和RepOD例程见[直接群体CSV](POPULATION-CSV.md)。

CSV可另选event_index_column，把该源Dataset索引写入首列，便于CSV单文件在下游排序/筛选后仍对应原事件；默认关闭，列名由调用方指定。

计划与输出列可使用精确PnN通道名，支持换序元数据；[具名通道与第三方交换例程](NAMED-CHANNELS.md)提供RepOD→群体FCS→FlowIO回读。

`population-stats`将gates/population接到既有MoonBit统计，报告该群体的源事件索引、有限/非有限计数、极值、均值和样本方差。可选start/count按群体成员位置取窗口，与CSV语义对齐；显式窗口另报实际events，population_events保留完整群体数。默认全部原通道；可选channels按精确PnN/数字选择和重排报告，返回源channel_indices。顶层scaled/compensated独立选择统计视图，完整通道矩阵先参与补偿，再筛报告列；无中间磁盘FCS，原文件与ANALYSIS不改。内部仍创建群体FCS内存副本；统计为Double，不保证大整数精度。用法和边界见[群体统计](POPULATION-STATS.md)。原stats仍报告整个Dataset，返回格式保持。

CLI报告和写文件回执输出到stdout（JSON），输入、参数或IO等异常写到stderr（文本）。退出码：0表示命令正常执行，1表示异常；compare返回2表示比较结果不兼容。退出0仍须查看报告字段和warnings。

`compare`以首文件为基准，比较存储模式、通道名称/顺序/位宽/范围/放大器/染色名、DATA类型、TIMESTEP及SPILLOVER，JSON逐文件显示mode。事件数、直方图频数、DATA内容和字节序可以不同；L、C、U之间不兼容。此检查用于所列结构/校准字段的流程前置判断，不证明相同生物面板、样本来源、全部元数据或数学等价。

CSV回执的scaled表示所选视图包含线性缩放，compensated表示选择补偿视图。compensated:true始终隐含scaled:true，包括显式scaled:false；这是既有数值语义。未提供补偿矩阵时补偿视图退回线性缩放，compensated不是“矩阵确实存在”的证明。零行输出仍报告所选视图。

## 公共API与范围

实际入口为 `parse(Bytes, ...)->Dataset raise FcsError`，以及parse_all、create、create_histogram；不存在规划稿的FcsDocument。完整签名见[pkg.generated.mbti](pkg.generated.mbti)，独立MoonBit消费模块见[examples/repod-consumer](examples/repod-consumer)。

| 任务 | 真实接口/合同 |
|---|---|
| 精确整数 | integer_value返回BigInt，integer_text返回十进制字符串；I按PnR有效位掩码访问 |
| 精确门控 | rectangle_exact(Array[IntegerBounds])接受字符串整数边界，半开区间；CLI使用integer_bounds |
| 创建/转换 | create的encoding/integer_values、write的encoding支持I/A/F/D；ASCII宽度0表示自由格式* |
| 交换 | write的event_indices/channel_indices同步通道元数据与补偿矩阵；ANALYSIS失效须显式处理 |
| C/U直方图 | histogram_shape/frequencies/frequency/axis/events，精确频数、C边缘分布和轴重排 |
| 数值视图 | value/statistics/rectangle/polygon支持compensated=true，线性scale后按测量行向量M×S⁻¹ |
| 分层门控 | gate_plan组合矩形/多边形/精确整数谓词，保留原始事件索引，报告父群体/总事件计数和比例 |

整数PnB不设64/1024位产品上限，正位宽、总宽度、Bytes和索引须由运行时可表示。历史向量含1位、非对齐、65/97/257/1024位；1024不是全区间穷举。大小端共用跨参数/事件连续位流和重打包。

CLI原始I/A值默认精确字符串；`exact_integers:false`显式选择Double。缩放、统计、补偿使用Double，不保证任意整数精度。S行代表源染料、列代表探测器；奇异/不可表示逆矩阵报错。写出保留未补偿DATA；通道主子矩阵不承诺等价于全通道补偿后投影。

C/U直方图选择或重排轴时，旧`$COMP`按FCS3.0的维度前缀与行优先位置同时选择/重排行列，系数字符串原样保留，单轴仍保留1×1矩阵；不将补偿应用到DATA。原轴重写保持整个COMP值，`drop_spillover:true`仍可显式移除。无法对应源轴的维度/字段数只在改轴写出时报错，读取与原轴重写仍保留原值；L模式原有显式移除规则不变。独立字节回归与范围见[FCS31-COMPATIBILITY.md](FCS31-COMPATIBILITY.md)。

声明读取FCS2.0/3.0/3.1、写出3.1；ASCII与C/U虽弃用仍有实现。结构、偏移、截断、非法索引和不可表示转换明确失败。具体布局/限制见[FCS31-COMPATIBILITY.md](FCS31-COMPATIBILITY.md)。不承诺FCS3.2、全部厂商异常、CRC验证、临床诊断或t-SNE/UMAP。

## implementation-03身份校准与历史证据

```sh
# 开发参考：FlowIO1.4.0、NumPy；不是运行时依赖
python tools/reference_check.py --report /path/to/NEW_REPORT.json
python tools/check-current-cli.py /path/to/NEW_DIRECTORY
```

第一条不传--reference-dir，只跑小型合成互通，不读取G11或旧厂商全集。第二条从已许可RepOD原文件直接投影3事件×3通道，用Python struct/原字节与FlowIO核对当前CLI的读取、重排、末事件边界及4类错误路径；生成目录保留署名/许可与完整命令。

2026-10-28的implementation-03曾通过check/JS release build、小型FlowIO互通3类案例及RepOD投影核验；该轮未修改核心。此为历史记录，当前核心修复及新源码身份见下节，不能把旧回执直接绑定到新源码。

旧FlowIO回执绑定的CLI源码SHA不同；当前CLI与两份0.5封存包一致，本轮另有绑定当前CLI/核心/build的新回执。无法从现有包重建旧差异的具体提交原因，不再以TEXT排版解释源码SHA。见[CURRENT-VALIDATION.md](CURRENT-VALIDATION.md)和[evidence/current-cli-20261028](evidence/current-cli-20261028)。

既有55项任务、宽整数/ASCII/CU/补偿独立向量和372,320源值的完整RepOD场景保持[历史身份](evidence/deep-20261020/independent.json)。深入修复05仅重跑相关范围，不重跑未变的全量数据/下载链。

## 深入修复05：代码正确性

本轮修复TEXT只转义首次分隔符、固定分隔符拒绝合法值前缀、默认浮点create返回无效补偿通道文件，以及非有限矩阵被接受/有限大矩阵消元溢出产生错误逆的问题。TEXT与ANALYSIS共用可用分隔符，键和值的每次出现都转义；create成功前校验可读性；矩阵输入检查有限性并作列/必要时行均衡后消元。公共API保持兼容，BigInt位宽与已有模式不缩减。

新增7项真实回归与相关25项既有测试在JS/Wasm-GC均通过；独立bitstring/整数、TEXT分隔符游程和闭式逆矩阵核验完成21次CLI调用。独立MoonBit消费模块两端输出一致。失败前后、范围与限制见[REPAIR05.md](REPAIR05.md)及[evidence/repair05-20261028](evidence/repair05-20261028)。

```sh
moon test correctness_wbtest.mbt --target js --deny-warn
moon test correctness_wbtest.mbt --target wasm-gc --deny-warn
moon build --target js --release --deny-warn
python tools/check-repair05.py /path/to/NEW_DIRECTORY
```

独立核验输入全为原创合成数据（MIT），不下载或复跑未确权仪器文件。数值逆仍是Double运算，不承诺任意病态矩阵的统一误差界；本次闭式反例的修复不冒称全输入数学认证。polish04补充的CLI stdout/stderr与退出码约定保留。

## 深入修复06：时间、存储模式与统计范围

F/D转I/A时，TIME通道保留原始tick与TIMESTEP；探测器通道仍正常应用gain后归一化，避免时间重复缩放或误拒绝可表示tick。C/U文件继续使用直方图API；列表事件statistics/rectangle/polygon对C/U明确报错，不再把没有列表事件伪报为零统计/空门控。

统计在有限异号极值差溢出时保留可表示均值；若Welford的中间M2溢出但样本方差可表示，再以尺度化平方和求方差。普通有限Welford路径保持，非有限测量仍单独计数，真实不可表示方差仍无数值结果。

新增4项回归、相关32项（含05修复）在JS/Wasm-GC均通过；独立struct刻度/gain及Python Fraction精确统计真值的56次CLI核对、独立MoonBit双端消费通过。CLI values/CSV也执行列表模式检查，不把C/U导出成空事件表。详见[REPAIR06.md](REPAIR06.md)与[evidence/repair06-20261028](evidence/repair06-20261028)。

```sh
moon test semantics06_wbtest.mbt --target js --deny-warn
moon test semantics06_wbtest.mbt --target wasm-gc --deny-warn
moon build --target js --release --deny-warn
python tools/check-repair06.py /path/to/NEW_DIRECTORY
```

## 深入修复07：转换后的整数范围

F/D转I/A时，目标PnR现在覆盖所选、已归一化的整数值，避免gain小于1或浮点值超过原PnR时，整数读取掩码静默改值。当前API接受的正小数PnR会转为正整数目标范围；空选择也生成可再次解析的文件。I/A源的既有放大器语义与TIME原tick/TIMESTEP保持。真实超宽、负数转无符号I及非整数转I/A仍明确失败。

新增3项与相关36项回归在JS/Wasm-GC通过；独立struct/Fraction、存储位提取及PnR掩码核对完成71次CLI调用，公开API消费模块双端通过。因write转换路径受影响，另以当前编译产物重验06的56次CLI；未复跑无关全集或下载链。见[REPAIR07.md](REPAIR07.md)与[evidence/repair07-20261028](evidence/repair07-20261028)。

```sh
moon test conversion07_wbtest.mbt --target js --deny-warn
moon test conversion07_wbtest.mbt --target wasm-gc --deny-warn
moon build --target js --release --deny-warn
python tools/check-repair07.py /path/to/NEW_DIRECTORY
```

## 深入修复08：补偿通道的独立性

补偿视图跳过逆矩阵中精确为0的权重，避免无关通道的NaN/Infinity经0乘法污染独立通道。单位矩阵和稀疏分块矩阵保持应有的依赖关系；真正非零的权重仍传播相关非有限输入，不以阈值忽略小系数。

新增2项及相关5项回归在JS/Wasm-GC通过，独立闭式矩阵/struct/Fraction核验64次CLI，双端公开API消费通过。统计、矩形/多边形门控、CSV与subset均核对，subset输出保留原始未补偿DATA字节。详见[REPAIR08.md](REPAIR08.md)与[evidence/repair08-20261028](evidence/repair08-20261028)。

```sh
moon test isolation08_wbtest.mbt --target js --deny-warn
moon test isolation08_wbtest.mbt --target wasm-gc --deny-warn
moon build --target js --release --deny-warn
python tools/check-repair08.py /path/to/NEW_DIRECTORY
```

## 功能拓展09：从独立条件到命名群体计划

GateStep以唯一id和可选parent组成单父门控树，支持前向父引用与分支；每步取自身谓词与父群体的交集，结果保持原Dataset事件索引。Population报告计数、分母及比例，空分母为None。每步可分别选择原值/缩放/补偿，Exact仍走I/A的BigInt字符串边界。CLI populations报告、gate/subset选群体与公开MoonBit API共用核心。

完整可运行Node例程与独立MoonBit模块见[GATE-PLANS.md](GATE-PLANS.md)。既有选择器、ANALYSIS显式处理及原始DATA写出合同保留；新API是兼容性扩展。不是GatingML/FlowJo导入、GUI、多父/布尔门、批次平台或自动分类。实现前的公开生态检索与FlowKit差异见[DUPLICATION.md](DUPLICATION.md)，验证记录见[FEATURE09.md](FEATURE09.md)。

新增5项与相关4项回归在双端通过；独立59次CLI、完整文件例程及公开MoonBit双端消费通过。旧38项请求边界与11项CLI回归保持通过，当前源/编译身份另有回执。

## 功能拓展10：具名通道与外部回读

新增channel_index及计划/输出列的精确PnN寻址，支持名字和数字混合；歧义不猜测，数字访问兼容重复名称。修复values零行请求漏查非法通道，保留合法空结果与原有null约定。来源、兼容与不支持项见[FEATURE10.md](FEATURE10.md)。

真实RepOD层级计划导出662事件，经FlowIO核对1986值、源DATA投影7944字节和具名CSV1324值；原数据与署名/CC BY4.0保留。新增2项及公开消费双端、61次合成CLI与受影响旧59次计划核验通过，原请求/CLI回归通过。没有重跑旧全量数据或下载链。

## 深入修复11：显式事件报告与导出一致

gate的events列表现在按当前选中Dataset校验范围，不再把负数、上界或空表中的假索引报告为成功。合法空列表、任意顺序及重复事件保持；subset的null默认全选语义不变。

37次独立调用验证边界、原始顺序和3/1事件链式Dataset；另复用10轮冻结群体的4个源索引，经FlowIO核对12值及48字节。只变JS桥接选择分支，核心/公开API保持，未重复未变的Wasm或全量互通。详见[REPAIR11.md](REPAIR11.md)。

## 深入修复12：比较前置检查的存储模式

compare现在将L/C/U模式纳入兼容键，避免相同通道配置的列表事件与直方图文件被误报兼容；报告添加mode。仍允许同模式的事件数、频数、内容和字节序不同，原通道/校准字段判断保留。

23次独立CLI调用验证六个有序跨模式组合、三个同模式正对照、多文件基准与原通道不匹配；通过前置检查的六个文件继续执行门控群体或精确直方图投影。仅修改Node比较分支，MoonBit核心、公开API和桥接编译产物身份未变。详见[REPAIR12.md](REPAIR12.md)。

## 深入修复13：CSV回执与数值视图一致

修复补偿CSV已缩放却报告scaled:false的问题；回执现在报告包含缩放的实际视图，并添加compensated选择标志。原始/仅缩放/补偿数值计算和合法参数保持。

8次CLI沿具名群体→保留原始整数DATA的FCS→六种CSV请求完成，Python csv/Fraction消费者核对非单位gain与补偿闭式真值；修复前后补偿CSV字节相同，仅回执改正。MoonBit核心、公开API、桥接源码和已编译JS身份未变。详见[REPAIR13.md](REPAIR13.md)。

## 有限审查14：来源元数据与重排交付

本轮未查出新的运行时缺陷，未修改运行代码/API。对“事件[2,0]、通道B/A重排并更新来源字段”的组合路径，以Python struct独立投影和FlowIO消费核对4个值、32字节、note覆盖及厂商/来源字段保留；源文件不变。

只补此有限审查材料，不把自填来源SHA宣称为防伪身份，也不重复既有结构字段保护、13轮CSV或旧全集。范围、复现脚本及当前身份见[REVIEW14.md](REVIEW14.md)。

## 功能拓展16：指定群体直接CSV

将已有gate_plan成员直接连接到原Dataset数值读取，按所选通道输出CSV；顶层scaled/compensated选择CSV视图，每步标志继续选择门控视图。有效空群体只输出表头，坏计划/群体/范围/列在创建目标前失败。未提供群体的既有CSV、FCS写出及所有MoonBit API保持。

19次独立CLI验证非连续成员、切片、精确原始整数、补偿/缩放、错误路径及100224个跨块值；真实RepOD直出662事件1324值，与10轮冻结成员/CSV及原F32字节一致，无中间FCS。核心/桥接编译身份未变，没有重跑旧FlowIO/全集。研究、差异与实际边界见[POPULATION-CSV.md](POPULATION-CSV.md)。

## 功能拓展18：CSV中的可选源索引列

event_index_column只增加源Dataset行号元数据，不改变科学值、门控/输出视图或群体切片。普通/群体CSV均可用，省略/null保持原格式；坏或冲突列名在目标创建前失败。索引不是仪器ID或来源认证。

14次独立调用验证非连续成员、切片、精确整数、空表、转义和跨块索引；真实CSV-only消费者核对662个索引和1324个保留科学值，排序/筛选后的332行仍对应源事件。现有RepOD例程仅增加可选模式，核心/API/桥接编译身份保持，旧套件未重复。详见[使用与边界](POPULATION-CSV.md)。

## 深入修复23：ASCII转整数不被PnR掩码改值

公开create接受的ASCII值20/21/5与PnR10，原先转I成功后读取却变4/5/5，门控与CSV随之改变。现在仅当所选ASCII原值需要更多有效位时，为线性通道/Time补足输出PnR；gain/tick语义保持。对数探测器若无法同时保留原值与范围校准，转换明确失败；有效位已足够的非二次幂范围保持，读取ASCII和普通ASCII改写不收紧。

7项新回归在JS/Wasm-GC通过；33次独立CLI核对固定/自由ASCII、双端序、gain、门控/CSV、所选/空事件、位宽错误和BigInt扩范围。独立工具初始对数样例的重复关键词错误已修正并保留原失败，前22个已过调用未重跑，只补余下11个。公开API/Node适配不变，核心与编译JS有新身份。详见[REPAIR23.md](REPAIR23.md)。

## 独立贡献与许可

FlowIO/FlowKit已有成熟Python方案。本库贡献是可组合的MoonBit精确整数与元数据交换核心，可编译JS/Wasm-GC且运行不依赖Python；不宣称算法首创、生态唯一、外部实验室采用或临床有效性。项目自编消费模块只证明可消费性。

代码和原创合成向量MIT；FlowIO/NumPy各按其BSD许可；RepOD文件96804及派生数据CC BY4.0，保留作者/DOI/许可/修改说明。G11及其它FlowIO仪器样本文件级授权未确认，不随源码分发。见[THIRD_PARTY.md](THIRD_PARTY.md)。标准PDF只查阅不分发；本地可运行不等于远端CI、公开发布或赛事验收。
