# CSV文件路径接收例程

原创MIT FCS3.1 I16输入的单通道X包含2/8/5/0，原DATA为`0200080005000000`。
selection.json使用严格读取，窗口start1/count2，附source_event_index。构建后从仓库根运行，输出路径须不存在：

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs csv examples/atomic-csv/input.fcs /path/to/NEW.csv --atomic-output --options examples/atomic-csv/selection.json
python examples/atomic-csv/receive.py /path/to/NEW.csv --expected examples/atomic-csv/expected.json
```

最终UTF-8表格的每行以CRLF结束，独立完整预期为：

```csv
"source_event_index","X"
1,8
2,5
```

接收方只读取CSV与明确预期，不读取原FCS、bridge或生产进程stdout。文件名在本次生产者发布时对应完整且已关闭的CSV；不依赖watcher事件调度。独立回归另在真实IO检查点启动此接收方，验证发布前名称不存在及发布后完整字节。

该脚本是自行编写的文件消费者，不是外部机构采用证据。它验证数据交换，不作生物学解释。文件系统能力、发布后cleanupPending告警及非持久事务边界见[群体CSV](../../POPULATION-CSV.md)。
