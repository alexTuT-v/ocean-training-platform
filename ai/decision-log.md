# AI 协作决策记录

本记录对应 PDF 第 5 节。时间均为 UTC；会话链接指向按时间顺序导出的完整 JSONL，具体用户指令可用表中的时间定位。提交号来自本仓库 Git 历史，验证证据来自项目测试与当前分支。

| 类型 | 决策与依据 | 会话证据 | 验证证据 | 相关提交 |
| --- | --- | --- | --- | --- |
| 采纳 | 后端使用 Python 与 SQLite。用户在明确项目约束后选择该组合，设计和实现采用 FastAPI、SQLite 的单机演示方案。 | [主会话](sessions/01a20220-b20d-7083-80b6-fd7b5928c8b9.jsonl)，用户消息 `2026-11-22T07:30:41.082Z`（“后端语言可以选择python，数据库的话sqlite吧”）。 | `backend/app/db.py`、`backend/app/main.py`；`.venv/bin/python -m pytest backend/tests -q`：40 通过（2026-11-23）。 | `8a9adf4`、`40f8bde` |
| 纠正 AI 建议 | 早期方案以 `bulk_operations` 记录批量颁发；用户追问单次颁发和其他写请求后，要求所有写接口幂等、读接口无副作用。最终用统一幂等记录约束颁发和撤销，请求键与请求指纹共同判定重试或冲突。 | [主会话](sessions/01a20220-b20d-7083-80b6-fd7b5928c8b9.jsonl)，用户消息 `2026-11-22T08:36:44.629Z`（“对于整体的接口都需要去保证幂等性”）及其前后讨论。 | `backend/tests/test_bulk_issue.py` 验证同键顺序/并发重试和冲突；`backend/tests/test_idempotency_revoke.py` 验证撤销重试及审计唯一性；后端全量测试 40 通过。 | `3019c23`、`dd1b2e2` |
| 范围权衡 | PDF 原始产品范围写为按课程颁发给全部合格学员。随后用户要求在课程完成列表中选择部分学员，可跨页保留选择；当前接口因此显式接收 `learner_ids`，页面“全选”仅选择当前页的合格学员。该选择优先满足后续明确的交互要求，也使未选学员不会被意外颁发。 | [主会话](sessions/01a20220-b20d-7083-80b6-fd7b5928c8b9.jsonl)，用户消息 `2026-11-23T13:34:45.938Z` 和 `2026-11-23T13:52:11.487Z`。 | `backend/tests/test_selected_bulk_issue.py` 验证只处理所选 ID、跨租户 ID 拒绝及幂等；`frontend/src/pages/CoursesPage.test.tsx` 验证跨页选择；后端 40、前端 32 项测试通过。 | `9545bb8` |
| 纠正演示数据时间 | 用户指出脚本把生成时间写死；演示数据与性能数据改为运行时 UTC，并按租户时区计算本地日期。PDF A5 的固定时刻作为时区换算测试样例保留，不作为每次启动的生成时刻。 | [主会话](sessions/01a20220-b20d-7083-80b6-fd7b5928c8b9.jsonl)，用户消息 `2026-11-23T13:21:04.458Z`；之后用户在 A5 复核时确认重点是区分 East 与 West 时区。 | `backend/tests/test_storage.py`、`backend/tests/test_certificate_reads.py`、`backend/tests/test_export.py`；A5 相关 13 项测试通过。 | `fc3b4fd` |

上述验证结果来自本地测试运行，不代表人工逐条执行了 README 中所有 `curl` 示例；完整命令和输出见对应会话的工具调用记录。
