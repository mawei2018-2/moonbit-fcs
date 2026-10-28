# 12轮：compare识别存储模式

范围仅为已有compare前置检查及其后续操作域。没有扩展生物面板推断、文件来源判断或格式功能；11轮封存保持只读。

## 实际缺陷与修复

compare原键只包含channels、datatype、timestep、spillover，遗漏已由inspect提供的mode。合法的L、C、U输入可拥有完全相同的通道配置与类型，但DATA分别代表列表事件、相关直方图、非相关直方图。修复前L/C、L/U、C/U全部退出0并报告compatible:true；相同populations计划对L成功，对C/U正确拒绝。因此compare会放过不能共用列表事件流程的输入。

tools/fcs.mjs仅将mode加入原兼容键，并在每行JSON中添加mode。以首文件为基准，跨模式退出2，继续输出有效JSON；输入/IO错误仍退出1。同模式的事件数、直方图频数、DATA内容和字节序不加入兼容键。原通道/类型/TIMESTEP/SPILLOVER条件保留。

## 独立核验与消费

- 原始before回执保留三个跨模式假兼容及同一门控计划的成功/拒绝结果；输入均能正常inspect，没有把损坏文件当反例。
- 原创MIT合成输入由Python struct直接编码，回归使用16位大小端DATA。六个文件的原兼容字段相同；同模式第二文件的计数、DATA和字节序不同。
- 23次CLI调用通过：六文件inspect、六个有序跨模式比较、三个同模式比较、六次接受后消费、多文件基准一次、既有通道名称不匹配一次。
- L正对照输出源事件索引[1]与[1,2]，群体计数与分母匹配各自文件。C投影频数为[4,6]与[8,12]；U为[1,2]与[2,3]，精确字符串核对。没有全局拒绝直方图文件。
- 不兼容结果退出2、stderr为空且stdout为JSON；逐行模式可用于解释结果。混合多文件仅标记与首文件不同的输入，同模式通道不匹配仍被拒绝。
- 新核验进入CI，本地actionlint通过。核心、公开API、MoonBit桥接源码与已编译JS的SHA均未变；没有重复核心/Wasm、既有全量互通或下载链。

## 复现与边界

```sh
moon build --target js --release --deny-warn
python tools/check-compare-mode.py /path/to/NEW_DIRECTORY
```

Python仅为标准库开发核验工具，运行库和Node CLI无Python依赖。输入及精确预期来自显式事件/频数，不以本库写出/回读作真值；原始命令、前后身份与结果见evidence/compare-mode-20261028及12轮报告。

兼容只表示所列结构/校准字段相同，不证明相同生物面板、同源样本、全部元数据或数学等价。未新增第三方外部采用证明；没有推送、发布、远端CI或赛事验收结论。
