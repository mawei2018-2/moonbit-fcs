# Forth 改为 FCS：换题交接 · 更新至 2026-09-29

选择 FCS 作为 Forth 的替换方向。FCS 是独立实现和独立模块，不是在旧 Forth 仓库改个名称。旧 Forth 成果继续保留，不再使用“MoonBit 此前没有任何栈式语言实现”的主张。当前没有既有 Forth 脚本或明确使用方，因此不继续为该主张扩写理由。

替换项目名称：**MoonBit FCS 事件数据检查与选择后交换**。
模块：`mawei2018/fcs`，本地 0.2.2、公开 0.2.1，MIT。0.2.2 只补充模块仓库地址元数据，算法未改。
公开地址：[https://github.com/mawei2018/moonbit-fcs](https://github.com/mawei2018/moonbit-fcs)，2026-09-29 已匿名核实；不可用旧 Forth URL 代替。

完整工作流是检查仪器文件的段/通道/事件矩阵，按明确事件条件与通道顺序选择，保留原始位模式写回 FCS3.1，再用独立 FlowIO 读取验证。已有 Python 工具成熟，MoonBit 项目可直接使用这个核心并编译至 JS/WasmGC，宿主运行无需 Python。基础实现于9月22日完成；0.2.0进一步处理公开G11样本的TEXT填充问题，并全量核对原始DATA与FlowIO回读。此次兼容增量见 COMPATIBILITY.md 和 evidence/text-padding-20260923/。

申报人可按顺序办理：

1. 将本地 `PROPOSAL.md` 与本说明用于组委会换题核对；是否允许换题以实际回复为准。这里没有代发消息。
2. 将本地新增提交同步到已有公开仓库；README、moon.mod 的 repository 与 SUBMISSION.json 已填写上述地址，无需再创建仓库。
3. 核对新增提交的 CI，依 README 构建并运行 `node examples/run-use-case.mjs`，发布对应新版本；精确提交与同一份申报稿一并交接。公开 0.2.1 的成功 CI 不证明新增提交。
4. 报名表替换名称、完整 URL、用途和差异说明。截止日期按驳回通知是 2026-09-30；申报人自行确认实际表单状态。

已有 FCS 仓库和 Mooncakes 0.2.1，本地 0.2.2 尚未推送或发布；换题与表单是否更新仍未核实，本任务没有代填表单或联系组委会。没有实验室用户证明，不做临床应用承诺。FlowIO 对照是兼容证据，不能表述为算法首创或所有厂商样本兼容。
