# Training Platform Backend Acceptance Checklist

> 验收状态更新于 2026-11-23（Asia/Shanghai）。`[x]` 表示已有下方记录或对应自动测试的实测证据；`[ ]` 表示尚未实测或需提交者本人完成。来源为已确认的后端设计、现有前端契约及评估场景 A1–A7。

## 1. 启动、数据与基础约束

- [x] 从干净环境运行唯一启动命令 `./run.sh` 后，依赖安装、SQLite 初始化、前端构建及 `127.0.0.1:8000` 服务均成功；刷新 `/certificates` 和 `/courses` 返回应用页面，`/api/me` 返回 JSON。（验证：运行命令，访问四个 URL，记录 HTTP 状态、响应类型和启动日志。）
- [x] 第二次运行 `./run.sh` 不增加演示租户、管理员、选课、证书或审计行，也不覆盖首次运行后的业务变更。（验证：两次启动前后查询数据库计数及已改动证书状态。）
- [x] 默认数据库保持轻量；单独性能命令只在指定测试数据库生成 East 的 100,000 张证书。（验证：比较默认库前后计数、性能库 East/West 计数。）
- [x] SQLite 外键、跨租户复合约束和同一租户/课程/学员最多一张 ACTIVE 证书的部分唯一索引生效。（验证：在临时库尝试非法插入，均被拒绝且无残留行。）

## 2. 请求身份与前端 API 契约

- [x] `GET /api/me` 对 Alice 和 Bob 分别返回对应管理员邮箱及 East/Sydney、West/Perth；缺失或未知 header 返回 401。（验证：分别带 `X-Actor-Email` 请求，检查 JSON 与状态码。）
- [x] 所有业务请求仅以该次 header 查出租户；请求 URL 或查询串加入 `tenant_id` 不能越权，未知租户筛选参数返回 422。（验证：交错发送 Alice/Bob 请求，尝试附带 East 的 ID，以数据库计数和响应检查。）
- [x] 课程、选课、证书列表、证书详情、批量颁发和撤销的 JSON 字段名、层级、枚举及 `null` 值与前端 DTO 一致；两个 POST 成功返回 200 JSON。（验证：运行契约测试，逐字段对比实际 HTTP 响应。）
- [x] 所有 JSON 错误均为 `{code,message}`；401、404、409、422 的错误码稳定且不暴露另一租户对象信息。（验证：分别触发四类错误并检查响应体；不出现公开的 `detail` 格式。）
- [x] 证书列表接受 `search/sort/direction/page/page_size`，`page_size=20` 可用，`total` 与当前页来自一致视图；搜索、排序、翻页结果和 URL 参数一致。（验证：使用同名学员、同名课程、相同排序值及空搜索的临时数据，比较 API 行集与总数。）
- [x] GET 请求无业务副作用且不复用旧响应；写事务提交后的下一次 GET 看到最新状态。（验证：写前后各发 GET，比对响应及审计/幂等计数；检查 `Cache-Control: no-store`。）

## 3. 写请求、幂等与审计

- [x] 缺失、空白、超长或不合法 `Idempotency-Key`，以及非对象 JSON 请求体返回 422；不创建证书、审计或幂等记录。（验证：分别请求两个 POST 并比较数据库行数。）
- [x] 同一管理员同一键、同一路径与 `{}` 请求体顺序重试，返回首次相同的 HTTP 状态码和 JSON；不会新增证书、审计或第二条操作记录。（验证：两次 POST 后比较完整响应和表计数。）
- [x] 同键并发批量颁发只产生一个逻辑操作，所有调用收到同一响应，每张实际颁发证书恰有一条 ISSUED 审计。（验证：并发请求与事务完成后查询证书、审计和幂等记录。）
- [x] 同键改课程、改证书 ID、改有效 JSON 对象字段或跨两个写接口复用时返回 409，不执行第二次操作，也不覆盖首次记录。（验证：先保存首次响应，再发送变体并逐表比较。）
- [x] 跨租户或不存在的写目标返回 404，且不写入幂等记录、证书或审计事件。（验证：Bob 用 East 的对象 ID 请求并核对数据库。）
- [x] 撤销响应丢失后用原键重试，即使证书已为 REVOKED，仍重放首次 `changed: true`；用新键重复撤销返回 `changed: false`，总共只有一条 REVOKED 审计。（验证：执行并比较两种键的完整响应和审计计数。）
- [x] 撤销后再次批量颁发会产生新序列号和新的 ACTIVE 证书，旧 REVOKED 证书和原审计仍可查询。（验证：按撤销、颁发、列表、详情顺序调用并比较两个证书 ID。）

## 4. 评估场景 A1–A7

- [x] **A1 租户隔离：** Bob 的列表与导出仅含 West；Bob 读取 East 详情或对 East 课程批量颁发得到 404；East 的证书与审计计数不变。（验证：API 验收测试加数据库计数。）
- [x] **A2 重试安全：** Alice 对同一批量请求以同键顺序和并发重发；结果相同、每个合格学员最多一张有效证书且每次实际颁发仅一条审计。（验证：并发 API 测试和数据库断言。）
- [x] **A3 键误用：** 同键换课程或改变请求体返回 409，首次结果未被覆盖。（验证：请求前后查询 `idempotency_records` 与证书/审计表。）
- [x] **A4 学员结果：** 已完成且无有效证书者 `issued`；未完成及已有有效证书者 `skipped` 且有可展示原因；单行可恢复失败为 `failed` 并不使其他合格学员丢失结果。（验证：种子课程批量 API 响应和逐学员数据库状态。）
- [x] **A5 本地日期：** 同一 `2026-01-10T13:30:00Z` 在 East 详情显示 `2026-01-11 00:30`，West 显示 `2026-01-10 21:30`；列表日期及 CSV 使用各自本地日历日期。（验证：双租户 API 与 CSV 断言。）
- [x] **A6 导出增长：** 在独立性能库准备 100,000 张 East 证书和重复排序值，按搜索/排序导出两次，每次不超过 60 秒；行数、租户、顺序完全符合请求，重复值次序一致；首个导出未结束时列表仍成功。（验证：记录两次完整下载时长、CSV 解析比对及并发列表结果。）
- [x] **A7 撤销审计：** 第一次撤销改变状态并写一条 REVOKED 审计；同键或新键重复撤销均不再写审计。（验证：API 响应与审计表计数。）

## 5. CSV、前端联调和体验

- [x] `/api/certificates/export` 返回 CSV 而非详情参数错误，响应类型为 `text/csv; charset=utf-8`；列顺序为 `learner_name,course_title,serial_number,issued_local_date`，包含有效与已撤销证书，正确转义逗号、引号和换行。（验证：下载并用标准 CSV 解析器检查列和值。）
- [ ] 在页面中切换 Alice/Bob 后，旧租户列表、详情和课程数据不再出现；后台中的 Alice 导出继续只导出 East。（验证：真实浏览器交错操作并检查下载文件及网络请求 header。）
- [ ] 课程页从确认到批量结果显示每名学员的 `issued/skipped/failed` 和原因；撤销确认后详情及列表更新；请求结果不确定时原键重试可取回首次结果。（验证：真实浏览器主流程加网络失败/响应丢失演练。）
- [ ] 证书页当前搜索、排序被导出沿用且不带分页；导出期间列表仍可搜索、排序和翻页。（验证：浏览器网络面板比较请求参数，导出未完成时操作列表。）

## 6. 自动验证、说明和提交材料

- [x] `python -m compileall -q backend`、`python -m pytest backend/tests -q`、`npm --prefix frontend test`、`npm --prefix frontend run typecheck`、`npm --prefix frontend run build` 全部通过。（验证：保存每条命令的退出码、用时和测试计数。）
- [ ] README 逐项列出 `./run.sh`、演示管理员 header、A1–A7 可复制命令、性能数据命令、已知缺陷及未完成工作。（验证：从干净环境按 README 实际复现，不仅检查文字存在。）
- [ ] 完整 AI 会话原生导出、`ai/session-index.csv`、真实决策日志、工具活动证据与完整性声明由提交者核对齐全；敏感信息已按评估要求做窄范围脱敏。（验证：逐会话核对时间范围、模型/工具、对应提交和文件可读性；缺失项保持未勾选。）
- [ ] 评估文档 Section 6 的个人书面答案由提交者独立完成，并核对提交包中有相应文件；本项目任务和本清单不提供答案内容。（验证：仅由提交者确认独立完成与文件存在。）
- [ ] 提交前记录仓库 URL、最终 commit SHA 和全部未通过条目；只有全部产品验收项有实测证据时才宣称后端完成。（验证：检查 Git 状态、提交历史与验收记录。）

## 验收记录

- 仓库：`https://github.com/alexTuT-v/ocean-training-platform.git`；工作分支：`feat/backend`。功能提交：`8a9adf4`、`1c62f38`、`6d2da6e`、`3019c23`、`dd1b2e2`、`d829422`、`40f8bde`；最终提交以 `git rev-parse HEAD` 为准。
- 2026-11-23：从该分支新建隔离检出 `.superpowers/sdd/2026-11-23-training-platform-backend/cleanstart`，无 `.venv`/`node_modules`/数据库；运行 `./run.sh` 自动安装依赖、构建前端并启动。`/`、`/certificates`、`/courses` 均返回 `200 text/html; charset=utf-8`；带 Alice header 的 `/api/me` 返回 `200 application/json`。第二次 `./run.sh` 后，租户/管理员/课程/学员/选课/证书/审计行数依次仍为 `2/2/2/6/6/2/2`，事先修改的证书状态仍为 `REVOKED`。
- 同一隔离检出运行 `.venv/bin/python -m backend.scripts.seed_performance --db data/performance.sqlite3 --tenant East --count 100000`：默认库仍只有 2 张证书，指定性能库有 East 100,000 张且无 West 证书。审查后强化的 `backend/tests/test_export_performance.py` 在另一个临时库准备 East 100,000 张与 West 1 张，真实本地 HTTP 完整下载两次，实测 `0.255s`、`0.222s`；100,001 行（含表头）每个序列号均符合预期，两次字节相同；对 100 行真实子集的两次导出也逐行一致。首次导出被测试同步点保持未结束时，Bob 列表仍只含 West，Alice 列表返回 200。
- 审查修复的 RED→GREEN：`test_unicode_casefold_search_matches_list_and_csv_without_wildcards` 从搜索结果 0 条失败到通过；前端 `retains the key when HTTP succeeds but the response body cannot be read`、课程与撤销的冲突放弃测试先失败后通过。响应体有效 JSON 但缺失写结果字段也有保留键测试。A6 属于测试覆盖缺口，增强测试直接通过现有运行时代码。
- 2026-11-23 自动验证：`.venv/bin/python -m compileall -q backend` 成功；最终 `.venv/bin/python -m pytest backend/tests -q -p no:cacheprovider` 为 `33 passed in 2.99s`；最终 `npm --prefix frontend test` 为 `25 passed`；`npm --prefix frontend run typecheck` 与 `npm --prefix frontend run build` 均成功。专项测试覆盖 A1–A7、读写契约、数据库约束、重试与跨租户边界。
- Chrome 真实页面验收：Alice/East 与 Bob/West 切换后列表、详情和课程显示各自数据；Alice 经确认弹窗批量颁发后，结果逐学员显示 `issued/skipped` 与原因，证书列表新增记录；经确认撤销后，列表与详情均显示已撤销。搜索 `Casey`、排序 `serial_number` 后下载 `certificates-East.csv`，浏览器显示 179 B、完成；服务日志对应 `GET /api/certificates/export?search=Casey&sort=serial_number&direction=desc`，不含分页。浏览器没有模拟响应丢失、单行失败或在 100,000 行导出未完成时继续操作列表，也没有验证导出途中切换管理员，故页面三项整体仍未勾选；这些边界由前端组件测试和后端并发测试分别覆盖。
- README 的命令和说明已人工核对，干净检出的 `./run.sh`、性能脚本与自动测试已实跑；A1–A7 的每条手工 `curl` 尚未逐条在该检出重演，因此 README 项保持未勾选。`ai/session-index.csv` 等 AI 会话材料不存在，Section 6 个人答案未核验；二者需提交者本人处理。最终 commit SHA 应在提交后记录，因此最后一项保持未勾选。
