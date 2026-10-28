# 14轮：来源元数据与重排交付的有限审查

本轮没有确认新的运行时缺陷，没有功能拓展或运行代码/API修改。仅审查已有subset的组合使用链；不以文档更新冒称修复。

## 范围与结论

write.mbt中的edits已有结构关键词和参数字段禁止编辑，既有core_wbtest有$PAR保护案例；本轮只检查源码与旧覆盖，不重复这一已通过测试。TEXT分隔符和UTF-8既有05轮覆盖也未重复运行。

新增的组合回执使用原创MIT合成输入：Python struct直接构造大端D64的3事件×2通道文件，带NOTE、SOURCE_SAMPLE和VENDOR_CUSTOM。subset显式选事件[2,0]、通道B/A，同时用小写note覆盖原NOTE，附加源文件SHA、事件与列映射。

2次CLI调用完成subset与strict metadata读取；Python独立读取输出HEADER定位DATA，逐字节比对[[30.125,3.75],[10.5,1.25]]的32字节投影。NOTE仅一项且为reviewed；未编辑的批次/厂商字段保留，附加来源记录等于本次输入身份与映射。

FlowIO1.4.0 preprocess=False实际读取交付文件，经NumPy2.5.3核对2行B/A、4个数值以及全部6项预期元数据。源文件SHA未变。这一范围未查出缺陷；没有扩大搜索或强凑运行时修改。

## 复现与证据

已有开发参考依赖为FlowIO1.4.0/NumPy2.5.3；构建JS桥后，使用对应开发Python运行：

```sh
python evidence/metadata-review-20261028/audit_delivery.py /path/to/NEW_DIRECTORY
```

脚本随本包保存，默认从所在evidence目录定位项目根；另可用--project指定根目录。结果保存COMMANDS.json/RESULT.json，输入为独立struct字节，消费者为真实FlowIO读取，没有从本库values结果生成预期。

当前命令/回执及源身份见evidence/metadata-review-20261028和14轮报告。运行代码、公开API、CI、Node CLI、桥接源码及已编译JS的SHA保持；只更新README/评委稿并加入本审查材料。未运行未变build/核心/Wasm/13轮CSV/旧全量互通/下载链，也未为文档加入单元测试。

## 实际边界

只验证一个来源元数据与重排组合，不能推出所有元数据或所有厂商均正确。来源SHA/映射是调用方填入的记录；本次核对一致不等于来源经过认证、防篡改或外部实验室采用。审查用合成输入及脚本MIT，没有新增第三方数据处理。

旧修复与封存保留；没有推送、发布、远端CI或赛事验收结论。
