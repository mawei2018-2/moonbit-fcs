# CSV-only群体成员接收例程

原创MIT FCS3.1输入含65位ID及X/Y。ID为18446744073709551616加原事件号0..7，原始X/Y依次为
`[0,0]、[2,4]、[12,6]、[4,8]、[8,2]、[9,9]、[10,4]、[1,5]`。
X/Y gain为2/4，矩阵`2,X,Y,1,0.5,0,1`只用于明确选择的已有补偿视图；本例科学CSV默认输出原始精确值。

selection.json中child前向引用band：band为原X的`[0,10)`，child在band内要求scaled Y的`[1,2.5)`；id_65按原始大整数选择ID区间，never为空。四个独立源成员是：

| 群体 | 原事件号 |
|---|---|
| band | 0,1,3,4,5,7 |
| child | 1,3,5,7 |
| id_65 | 1,2,3 |
| never | 空 |

从仓库根构建后运行，输出路径须不存在：

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs csv examples/population-columns/input.fcs NEW.csv --options examples/population-columns/selection.json
python examples/population-columns/receive.py NEW.csv --expected examples/population-columns/expected.json
```

一份CSV包含source_event_index、ID/Y/X和四个成员列；例如原事件1的ID为18446744073709551617，Y/X为4/2，四个标志为1/1/1/0。接收方不读FCS/群体JSON或导入bridge，只检查收到CSV的完整独立期待：计数6/4/3/0，band与id_65交集为1/3；按X降序重排后源索引仍为2/6/5/4/3/1/7/0，并逐行保持科学值和标志关联。

可另用现有--atomic-output发布完整表，不改变标注数值。索引是所选Dataset行号，ID只是本例原创数值列，不认证实验样本。此自编实际文件消费者不等于外部采用；没有新门控算法、自动分类或生物学结论。范围见[群体CSV](../../POPULATION-CSV.md)。
