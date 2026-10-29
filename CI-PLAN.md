# 本仓库CI接收边界

`.github/workflows/ci.yml`的必要作业为`test`，push/pull_request均执行。既有固定MoonBit工具链、JS/Wasm-GC测试、公开/许可文件互通、统计、COMP、事件成员列和CSV发布验证保持。真实完成以目标提交对应Actions作业及全部必要步骤终态为准；配置、推送和本地通过分别记录。

补偿中间溢出新增必要步骤 `Verify finite compensation overflow recovery with independent file consumers`，检查公开模块格式并运行 `python tools/check-compensation-overflow.py "$RUNNER_TEMP/fcs-compensation-overflow"`。六套原创完整 D64 文件以 Fraction 固定有限乘积/部分和溢出抵消、次正规数/负零、正常数与最大有限值舍入、增益缩放、真实非有限和零依赖；JS/Wasm-GC 公共 API 比较每个逆矩阵项、全部值和有限/Infinity 位模式。独立标准库进程消费完整群体/统计 JSON、原始选择 FCS 和两份 CSV，结构合法但科学值/成员/位模式被改的反例必须拒绝。普通 stdout 与接纳版本逐字节比较，旧矩阵/通道错误与已有目标守护保持。CHECKS、进程、完整输入/输出及实际编译产物上传，云端元数据和下载字节读回分别陈述。

布尔群体的必要步骤为 `Verify Boolean gate dependencies with independent complete file consumers`，检查公开调用模块格式并执行 `python tools/check-boolean-gates.py "$RUNNER_TEMP/fcs-boolean-gates"`。六套原创完整预期覆盖前向依赖菱形、AND/OR/NOT、父限制、重复引用、几何后代、空源/空父、跨分支和非有限补集；错误计划及选择/写文件路径验证未知引用、参数、视图、混合循环和已有目标保护。独立进程消费全部群体/统计 JSON、三份精确 FCS 和两份带成员列 CSV，JS/Wasm-GC 公共 API 报告也逐项核对；三份结构仍合法的错误内容必须被接收器拒绝。纯几何 stdout 与接纳版本的 UTF-8/LF 控制逐字节相等。

核心新增 DAG/枚举由双后端测试覆盖；本地运行相关旧门控和 CLI/request 回归，云端保留完整原检查。CHECKS、实际进程、完整原创输入/输出和编译桥接身份随 artifact 保留；上传和元数据仍不代表下载字节读回。

群体分位数的必要步骤为 `Verify population quantiles with independent JSON and public API consumers`。它检查独立 MoonBit 消费模块格式，并执行 `python tools/check-population-quantiles.py "$RUNNER_TEMP/fcs-population-quantiles"`：从原创 struct FCS 与有理数完整预期，核对原始/缩放/补偿、群体窗口、极值/非有限数据、错误路径、默认字节兼容及 JS/Wasm-GC 公共 API。另启仅读最终 JSON 的接收进程，覆盖全文、错误中位数及次正规数擦零反例；零与次正规数精确核对，其余 Double 数值的固定向量容差为 4 ULP，身份、模式、计数、索引和概率严格一致。新公共 API 的双端核心数值测试随既有 `moon test` 执行，原检查命令不删减。CHECKS、输入清单、进程启动记录和实际 JSON 输出随 artifact 保留。

多样本报告新增必要步骤：`Verify multi-sample population reports with independent CSV-only receivers`，执行：

```sh
python tools/check-population-report.py "$RUNNER_TEMP/fcs-population-report"
```

它生成原创完整小型FCS与独立完整CSV预期，验证样本清单/共享门计划到实际报告的流程，并另启只读CSV的接收进程，核对全部字段及透视/排序。覆盖零事件、空父、逐门视图、原始文件/Dataset关联、Unicode、读取覆盖/实际警告、晚失败无输出和已有目标保留；另检查原单样本接口。CHECKS含全部命令exit/stdout/stderr、输入/实现/实际CSV身份；运行前进程日志只记录实际cwd与三个临时目录变量。

上传的Actions artifact保留CHECKS、进程启动记录、输入清单和实际输出CSV；远端artifact元数据或上传成功本身不等于下载/二进制读回。最终交接分别标明本地源码/Git blob、原始工作副本、实际使用的编译桥接、原始CSV输出与远端CI元数据。新增报告是宿主流程，MoonBit核心/API未改时本地只运行相关宿主/接收验证，云端现有完整门仍照常执行。

重复PnN写出修复的必要步骤为`Verify positional writes of duplicate-name compatibility datasets with independent file receivers`，运行`python tools/check-duplicate-write.py "$RUNNER_TEMP/fcs-duplicate-write"`。它从原创完整兼容源独立固定全部元数据/数值与I/F/D原始DATA字节，ASCII逐字段核对；实际FCS-only进程检查全部输出并消费按PnS区分的列及C/U边缘分布。strict/名称歧义、非法输出位置/编码形状与重复名称创建的错误合同保持。CHECKS、输入清单、启动记录及实际FCS输出上传，元数据和下载字节身份分开。

`duplicate_write_wbtest.mbt`另以冻结源的原始十六进制字节，执行实际parse/write/parse以及创建错误操作；既有JS/Wasm-GC测试步骤会执行这些新测试。该修复修改私有编码元数据接线，故本地使用固定私有工具链进行check、格式化、info、相关文件双后端测试和JS release构建；公共生成接口应保持。云端完整旧门保持，不以本地结果冒充远端终态。

链式Dataset抽取新增必要步骤`Verify complete chained Dataset extraction with independent standalone file receivers`，执行`python tools/check-extract-datasets.py "$RUNNER_TEMP/fcs-extract-datasets"`。原创完整链固定0/2048/6144源偏移、I/D/C原始位模式与ANALYSIS；独立标准库进程从实际目录读取manifest及每份单Dataset FCS，逐项核对全部字段、完整DATA、ANALYSIS和来源映射，并消费整数列合计、D特殊值分类及C边缘。单Dataset/零事件、真实逐Dataset读取修正、后段损坏/坏选项和既有目标守护均覆盖；哈希自洽但数据被换位的完整伪造包必须被独立原始内容预期拒绝。

上传CHECKS、启动记录、原始输入清单和实际FCS/manifest输出。宿主入口新增，科学核心/公共API未改时本地复用已验收编译桥接并记录哈希，仅读本轮新小型输入，不重跑旧原生/科学参考生成器；云端完整原有门继续执行。远端上传/元数据仍不替代下载字节读回。
