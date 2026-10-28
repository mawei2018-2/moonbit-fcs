# 13轮：CSV回执描述正确数值视图

范围为已有具名群体→FCS交付→CSV消费链；12封存及旧修复只读保留。没有增加数值算法或格式能力。

## 实际问题

compensated视图在MoonBit中总是先作线性缩放，再按测量行向量M×S⁻¹计算；即使请求scaled:false也如此。CSV原回执却只取显式scaled请求位，导致已经缩放的补偿结果被标作scaled:false。

复现以gain=[2,4]、S=[[1,0.5],[0,1]]的三个整数事件为源。具名群体选择原事件[1,2]，subset输出保留原始DATA[[8,24],[12,36]]与校准元数据。Python直接读取交付CSV得到[[4,4],[6,6]]，数值正确，原回执仍为scaled:false。缺陷在描述结果的回执，不在补偿计算。

Node只修正回执：scaled为scaled或compensated视图的选择结果，新增compensated布尔字段区别仅缩放与补偿。没有改写请求参数或MoonBit数值分支；原字段written/events保留，所有既有合法请求继续有效。

## 实际消费验证

工具不从本库values结果生成真值：Python struct写源字节，按源事件序列独立投影subset DATA；Fraction计算rawA/2、rawB/4和闭式逆S⁻¹=[[1,-1/2],[0,1]]，Python csv读取实际交付表格。

8次CLI调用通过：群体报告、subset交付和六次CSV。默认raw为[[8,24],[12,36]]；仅scaled为[[4,6],[6,9]]；compensated为[[4,4],[6,6]]。补偿省略scaled、显式false、显式true均得到相同数值和scaled:true/compensated:true。末事件之后count=0仍只输出表头，并报告所选视图。

原始整数DATA的8字节、增益/矩阵、群体源索引和源文件未修改均已核对。修复前后同一补偿请求的CSV字节相同；新回执改正标签。新增消费核验进入CI，actionlint通过；没有为一个布尔表达式单独增加镜像单元测试。

```sh
moon build --target js --release --deny-warn
python tools/check-csv-view.py /path/to/NEW_DIRECTORY
```

工具及原创合成输入MIT，只需Python标准库作为开发核验；库/Node运行无Python依赖。完整前后回执、选项对象、命令、Fraction预期与身份见evidence/csv-view-20261028及13轮报告。

## 范围与限制

scaled/compensated标识所选视图，空结果也保留选择；没有矩阵时既有compensated视图只作线性缩放，布尔字段不证明矩阵存在或生物学有效性。范围/通道在创建CSV前已有校验，本轮没有把原正确行为当缺陷。

MoonBit核心、公开API、桥接源码及编译JS的SHA未变；未重复未变Wasm、12轮比较正例、旧全量互通或下载链。新增消费者是项目内可复现验证，不是外部采用证明；没有推送、发布、远端CI或赛事验收结论。
