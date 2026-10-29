# 重复PnN兼容数据的数字位置写出

原始文件的两个物理列可能使用相同PnN。默认读取对这种兼容输入给出`duplicate channel name DUP; use numeric indexes`，允许数字访问；strict仍拒绝。字符串`"DUP"`不能决定是哪个列，因此仍报歧义。这不是严格标准合法性、自动改名或面板等价声明。

原实现的普通列表复制和唯一名称转换可以工作，但列表指定encoding及C/U直方图写出复用了“新建文件须唯一名称”的校验，导致已接受的兼容数据用数字位置也无法交付。修复仅让这两类Dataset.write路径保留原有非空标签；新建、空名称、重复输出数字位置、严格读取和歧义名称要求保持。公共接口、解析/门控/统计/补偿模型及原CSV/报告/发布流程未改。

从源码构建后运行完整反例：

```sh
moon build --target js --release --deny-warn
node tools/fcs.mjs rewrite examples/duplicate-write/input.fcs out.fcs --options examples/duplicate-write/rewrite.json
python examples/duplicate-write/receive.py out.fcs --expected examples/duplicate-write/expected.json
```

输出路径须不存在。输入两个PnN均为DUP，PnS分别left/right；原I值为`[[4,12],[6,20],[10,28]]`，gain为2/4。例程指定数字列`[1,0]`转大端D，输出`[[3,2],[5,3],[7,5]]`、PnS为right/left、gain为1。它沿用原转换的校准语义，不计算新统计/补偿。来源警告策略保持，写出后重复PnN仍有歧义。

独立接收程序只读实际FCS和原已固定预期，不导入本库/CLI/构造器。它逐项解析HEADER/TEXT，检查每个元数据键值、段边界、完整原始DATA字节或所有固定ASCII字段，再按PnS消费列。FCS布局偏移按非负十进制数核对，合法前导零不改变值；其他元数据文本完整保留，DATA不靠生产回执判断。

开发验证：`python tools/check-duplicate-write.py /path/to/NEW_DIRECTORY`。原创兼容源覆盖I/A/F/D重编码、默认复制、C/U原轴与数字换轴及单轴控制；C的2×3频数`[1,2,3,4,5,6]`换轴为`[1,3,5,2,4,6]`、总数21，U的`[6,9,2,5,8]`换轴为`[2,5,8,6,9]`、每轴总数15。原COMP按既有规则随轴重排系数字符串，不应用到DATA。唯一名称控制和严格/创建等错误路径亦核对。

四项原生操作测试同时覆盖JS/Wasm-GC：列表转换、C频数/COMP位置、U边缘块及创建唯一性。没有重跑旧巨大样本或参考生成器。独立标准库接收证明本次实际字节/语义，不等于第三方采用、全部组合穷举或临床验证；源码0.5.0模块/许可身份保持。
