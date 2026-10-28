# 来源与第三方材料

- ISAC FCS 3.1 规范：<https://www.citometriagic.it/wp-content/uploads/2025/02/FCS_3_1.pdf>。用于确认格式语义；本仓库不分发规范 PDF。
- FlowIO 1.4.0：<https://github.com/whitews/FlowIO>，BSD-3-Clause，Scott White。通过 pip 作为独立参考安装，不是运行时依赖，未复制解析器代码。
- 公开测试文件来自 FlowIO 仓库提交 `83d28a22d42235c10d17afb017250ee208afed95` 的 `data/fcs_files/`，只在外部检出目录读取；这里保存文件名、SHA256 和统计，不重新分发仪器文件或其中的身份元数据。FlowIO 代码的 BSD 许可不能据此推定这些文件的授权；其文件级授权仍未确认。
- NumPy 2.5.3（BSD-3-Clause）用于对比数值数组。
- MoonBit 标准库使用其自身 Apache-2.0 WITH LLVM-exception 许可。项目核心无其他 Mooncakes 依赖。
- `fixtures_wbtest.mbt` 是本项目 Python 标准库脚本构造的合成输入，以项目 MIT 许可提供。

- 新增真实输入：Bronisz, Agnieszka, 2026, *Flow Cytometry data*, RepOD V2, [DOI 10.18150/JOLWGT](https://doi.org/10.18150/JOLWGT)。仅文件 96804 的原 FCS 纳入本仓库，文件级 CC BY 4.0 许可与校验见 [来源回执](examples/repod/SOURCE.json) 和 [署名](examples/repod/ATTRIBUTION.md)；原始字节未改。示例派生输出标注修改并附原署名和许可。代码 MIT 与数据 CC BY 4.0 分别适用。
- FCS3.1 §3.2.17 禁止数值 TEXT 空格填充；0.3.0 兼容入口为显式选择，默认仍拒绝，未复制 FlowIO 代码。

- 0.4.0标准编码输入、MoonBit回归和独立Python核验均为原创合成数据/实现，项目MIT；FCS3.1 PDF只在开发工作目录查阅，不随仓库或交付包分发。

- 0.5.0的wide/histogram/compensation源字节、Python解析器与MoonBit新增实现为原创MIT。NumPy.linalg.solve只作独立开发参考；FCS3.1与ISAC FCS API只用于确认布局/矩阵方向，没有复制其代码或分发标准全文。

- 2026-10-28：`tools/check-current-cli.py`为原创MIT核验代码；输入仅使用已有RepOD文件96804的3事件×3通道原字节投影。派生FCS仍为CC BY4.0，生成目录附原作者/DOI/文件号、许可及选取/重建元数据的修改说明。新回执不复跑G11或未确权仪器文件，不将数据改标MIT。
