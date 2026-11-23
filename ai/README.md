# AI 交互证据与完整性声明

本目录对应评估 PDF 第 5 节。当前快照包含从需求讨论、设计、实现到最近一次 PR 验证所能取得的项目相关 Codex Desktop 会话证据。

## 文件

- `sessions/*.jsonl`：六个相关会话的按时间顺序 JSONL 记录，包含用户消息、面向用户的助手回复、工具调用及输出、错误和时间戳；主会话的四个续接段合并为一个文件。子任务会话单独保存。
- `sessions/README.md`：每个会话的原始 rollout 文件名、段数和导出处理说明。
- `session-index.csv`：按 PDF 要求列出 `session_id,purpose,tool,model,started_at,ended_at,export_file,related_commits`，全部使用 UTC。
- `decision-log.md`：记录采纳、纠正和范围权衡的真实决策，关联会话、验证证据与提交。

## 工具与导出边界

- AI 工具：Codex Desktop。索引中的模型名称来自原生会话的 `turn_context`。用户确认本项目没有其他独立 AI 会话或工具参与。
- 会话内记录的 Codex 工具包括 `exec`、`exec_command`、`apply_patch`、`write_stdin`、`js`、`wait`、`request_user_input_async`、子任务相关工具、时钟工具、网页读取工具及工作区依赖定位工具。命令行工具（如 Git、GitHub CLI、pytest、npm 和 Swift PDFKit）的原始命令及输出保留在相应工具记录中。
- 导出从本机 Codex Desktop 的原生 JSONL rollout 构建。仅对账户标识与私人邮箱、平台内部指令、不可读的加密压缩内容、内部消息元数据、私有模型推理及可能出现的凭据做标明原因的窄范围脱敏；没有把对话改写成精选提示词列表。原始 `session_meta`、消息、工具调用及输出事件仍按事件顺序保留。内部自动审批检查器不是独立的用户交互会话；其对主流程的反馈保留在主会话工具输出中。
- 本文件创建时主会话仍在进行。`session-index.csv` 的 `ended_at` 对该会话表示**本次导出的最后事件时间**，并非对话结束时间。最终提交前应重新导出此会话，并复核新增交互、提交号和脱敏情况。

## 待本人确认

- 行内 AI 自动补全：用户确认本项目未使用 Copilot、Cursor Tab 等无法导出完整对话的行内补全。
- 提交前需由候选人核对本目录是否覆盖全部实际使用的交互、文件编辑、失败尝试及敏感信息；如另有无法导出的活动，应补充完整时间顺序文本记录并说明限制。
