# 将链式Dataset交付为独立FCS

有些遗留FCS在一个文件中以NEXTDATA串联多个Dataset。只接收单个Dataset文件的下游需要独立文件，而调用方还要保留原始Dataset/读取警告的对应关系。现有parse_all和逐Dataset rewrite可组合完成；`extract-datasets`把这条完整交付流程接好，不增加格式、解析器、科学模型或MoonBit API。

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs extract-datasets examples/extract-datasets/input.fcs extracted
python examples/extract-datasets/receive.py extracted --expected examples/extract-datasets/expected.json --source-file examples/extract-datasets/input.fcs
```

目录`extracted`须不存在，父目录须已存在。命令生成dataset-000000.fcs、dataset-000001.fcs等，最后写manifest.json。编号按既有NEXTDATA链顺序，零基；不扫描链结束之后的任意字节来猜额外Dataset。单Dataset和零事件输入同样支持。

每份输出使用既有rewrite规范化为独立FCS3.1、NEXTDATA为0。它是完整重写，不是截取源字节范围：版本、偏移、ORIGINALITY及既有CRC/UNICODE处理会规范化，通道/事件/ANALYSIS与其它元数据继承原rewrite合同。没有选择事件、投影通道、转换encoding、门控或重新计算统计。科学DATA处理沿用原API，不能把整份文件哈希改变误当成事件值改变。

`--options read.json`可提供strict、allow_exclusive_end、latin1、allow_text_padding、allow_offset_padding，均须布尔。默认沿用读取默认；示例read.json提供strict:true。原严格/兼容开关冲突规则保持，warnings来自所选原Dataset。此命令选择整个链，不接受dataset、channels、encoding、metadata、gates或视图/窗口选项；原单Dataset命令保持原合同。

清单为schema_version:1，含source_file原参数拼写、完整实际输入buffer的source_sha256，以及datasets数组。各条目包含：

| 字段 | 含义 |
|---|---|
| dataset / source_offset | 原零基Dataset号 / 原文件中HEADER的累计字节偏移 |
| source_version / source_mode / source_events | 原版本、原模式及原事件总数；沿用native的列表整数/直方图十进制字符串类型 |
| source_warnings | 原Dataset实际读取警告，未被输出规范化掩盖 |
| file / bytes / sha256 | 本目录内固定文件名、完整输出字节数和SHA-256 |

源哈希覆盖完整输入，包括Dataset间空隙；输出哈希覆盖相应独立FCS。它们分别识别源和交付字节，均不是来源认证。source_file仅说明原路径，不是接收时必须可用的依赖；目录移交后各FCS自行包含元数据/ANALYSIS，接收无需重新打开原链。

所有选项、原链解析和全部重写完成后才创建目录，后续Dataset损坏不会留下抽取目录；已有文件/目录保持。之后的普通文件/manifest写入或关闭若发生IO失败，可能保留部分新目录，错误退出1，不自动删除或重试。这不是多文件事务、原子发布或掉电持久性。成功stdout为written、datasets、manifest三个字段的JSON。实际接收应完整读取清单及文件，不能只看目录或manifest名称存在。

当前API接收整个输入，宿主保留全部重写结果再落盘；现有桥接在每次选Dataset时会重新解析链，仍有内存和重复解析成本，不承诺流式、并行、大规模性能或无限资源。没有为了优化而改写已有科学核心。

独立检查：`python tools/check-extract-datasets.py /path/to/NEW_DIRECTORY`。原创三段链的原偏移为0/2048/6144，第二段NEXTDATA为相对4096；覆盖FCS2.0整数、FCS3.1大端D原始负零/NaN payload/无穷、FCS3.0直方图和ANALYSIS。接收程序只用标准库读取实际HEADER/TEXT/DATA/ANALYSIS与manifest，核对全部字段/完整DATA及来源，再求整数列和、特殊值分类及直方图边缘。另有单Dataset、零事件、只在第二段发生的真实偏移兼容警告、错误路径和已有目标保留。

完整伪造包的清单与全部文件哈希自洽，但两个直方图频数被交换、总数仍17；它仍必须被独立固定的原始DATA预期拒绝。此自编真实接收证明可消费性及本轮原始内容核验，不代表外部采用、全部组合穷举或临床结论。

[FlowIO官方API](https://flowio.readthedocs.io/en/latest/api.html)已有多Dataset读取和单文件写出，说明这是成熟交换场景。本项目独立宿主组合沿用自己的MoonBit实现；不声称算法首创、生态唯一或FlowIO功能对等。当前Mooncakes状态未从工具确认，源码模块身份仍为mawei2018/fcs、0.5.0。
