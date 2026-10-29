# 本仓库CI接收边界

`.github/workflows/ci.yml`的必要作业为`test`，push/pull_request均执行。既有固定MoonBit工具链、JS/Wasm-GC测试、公开/许可文件互通、统计、COMP、事件成员列和CSV发布验证保持。真实完成以目标提交对应Actions作业及全部必要步骤终态为准；配置、推送和本地通过分别记录。

多样本报告新增必要步骤：`Verify multi-sample population reports with independent CSV-only receivers`，执行：

```sh
python tools/check-population-report.py "$RUNNER_TEMP/fcs-population-report"
```

它生成原创完整小型FCS与独立完整CSV预期，验证样本清单/共享门计划到实际报告的流程，并另启只读CSV的接收进程，核对全部字段及透视/排序。覆盖零事件、空父、逐门视图、原始文件/Dataset关联、Unicode、读取覆盖/实际警告、晚失败无输出和已有目标保留；另检查原单样本接口。CHECKS含全部命令exit/stdout/stderr、输入/实现/实际CSV身份；运行前进程日志只记录实际cwd与三个临时目录变量。

上传的Actions artifact保留CHECKS、进程启动记录、输入清单和实际输出CSV；远端artifact元数据或上传成功本身不等于下载/二进制读回。最终交接分别标明本地源码/Git blob、原始工作副本、实际使用的编译桥接、原始CSV输出与远端CI元数据。新增报告是宿主流程，MoonBit核心/API未改时本地只运行相关宿主/接收验证，云端现有完整门仍照常执行。

重复PnN写出修复的必要步骤为`Verify positional writes of duplicate-name compatibility datasets with independent file receivers`，运行`python tools/check-duplicate-write.py "$RUNNER_TEMP/fcs-duplicate-write"`。它从原创完整兼容源独立固定全部元数据/数值与I/F/D原始DATA字节，ASCII逐字段核对；实际FCS-only进程检查全部输出并消费按PnS区分的列及C/U边缘分布。strict/名称歧义、非法输出位置/编码形状与重复名称创建的错误合同保持。CHECKS、输入清单、启动记录及实际FCS输出上传，元数据和下载字节身份分开。

`duplicate_write_wbtest.mbt`另以冻结源的原始十六进制字节，执行实际parse/write/parse以及创建错误操作；既有JS/Wasm-GC测试步骤会执行这些新测试。该修复修改私有编码元数据接线，故本地使用固定私有工具链进行check、格式化、info、相关文件双后端测试和JS release构建；公共生成接口应保持。云端完整旧门保持，不以本地结果冒充远端终态。
