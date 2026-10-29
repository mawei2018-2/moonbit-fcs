# 兼容重复名称文件的实际交接

本目录的原创MIT输入含3事件、两个PnN为DUP的通道，PnS为left/right，gain为2/4。它是带警告的兼容输入；严格读取应失败。

```sh
node tools/fcs.mjs rewrite examples/duplicate-write/input.fcs out.fcs --options examples/duplicate-write/rewrite.json
python examples/duplicate-write/receive.py out.fcs --expected examples/duplicate-write/expected.json
```

使用数字列1/0，既有I→D校准得到`[[3,2],[5,3],[7,5]]`，大端64位数据按原始字节核对；PnS right/left表明两个同名物理列没有串位。接收者从实际FCS计算right列合计15、left列合计10。完整元数据和自定义UTF-8值保留；布局偏移按FCS十进制数读取。

接收程序只用Python标准库，不导入生产代码或构造器。expected由生产执行前的原创源/有理数预期固定；它是实际可消费性证据，不代表外部采用。详见[修复合同](../../DUPLICATE-WRITE.md)。
