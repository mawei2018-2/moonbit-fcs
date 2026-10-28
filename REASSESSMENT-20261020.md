# FCS 初审补充材料 · 2026-10-20

原驳回意见指出排除了合法ASCII和非字节对齐整数，该问题成立。0.4.0已补读入、筛选和规范重写路径；保留原申报书，不把这份本地材料当成已提交表单。[兼容矩阵](FCS31-COMPATIBILITY.md)明确未完成的直方图、宽于64位整数和完整标准终点。

## 可运行的筛选重写案例

```sh
moon build --target js --release --deny-warn
python tools/generate-standard-encodings.py --check
node tools/run-standard-encodings.mjs /path/to/NEW_DIRECTORY
python tools/verify-standard-encodings.py /path/to/NEW_DIRECTORY --report /path/to/NEW_REPORT.json
```

输入保存在 [INPUTS.json](examples/standard-encodings/INPUTS.json)，可从sourceBase64解码取得原始FCS。12组原创新输入覆盖：12位双端序手算向量、每事件18位且跨字节连续存储、混合1/7/9/31/64位、64位最大整数、非幂二精确PnR、高位掩码、定长ASCII、自由ASCII五种分隔符及显式零、混合宽度转定长、超过UInt64的ASCII整数。

例如12位输入`ABC, DEF`的DATA分别是LE `bc fa de`、BE `ab cd ef`；通道重排后读值为`DEF, ABC`。18位行选择原事件`[2,0]`和通道`[2,0]`后必须连续重打包，不能复制带行填充的字节。定长ASCII原`0012, 7 / 0003, 456`重排得到`4560003  70012`，混合自由格式仅保留定长列得到`00170003`。每组还执行全量重写与空选择；可用Double精确表达条件的10组另经数值半开筛选后写回。

Python核验器从产出HEADER/TEXT定位DATA，以整段任意精度整数/ASCII独立解码，并用位字符串构造筛选后的期望DATA。MoonBit使用逐字段位读写，二者不共用读取实现。检查每个值、存储高位、通道元数据、偏移、ORIGINALITY及未知NOTE。原始合成数据和脚本采用项目MIT，不分发标准PDF。

这份证据是独立算法的标准向量验证，**不是第三方FCS库对ASCII/bit-packed的互通认证**。FlowIO旧回归只证明其支持范围内的既有文件；新的结果见 [标准向量回执](evidence/standard-encodings-20261020.json)，完整本地执行见 [CHECKS](evidence/reassessment-20261020/CHECKS.json)。远程CI、公开发布、报名表更新和组委会复审均未执行。
