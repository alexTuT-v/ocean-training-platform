# Training Platform Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付与现有 React 前端契约一致、可一键启动的 Python/SQLite 后端，逐项通过评估场景 A1–A7。

**Architecture:** FastAPI 路由只解析 HTTP 与返回契约；服务层负责业务与幂等事务；repository 持有参数化 SQL。每次请求由 `X-Actor-Email` 查询管理员和租户，SQLite WAL 支持同步写事务与独立的流式导出读连接；生产构建后的前端与 `/api` 由同一应用提供。

**Tech Stack:** Python 3.11+、FastAPI、uvicorn、标准库 `sqlite3`/`zoneinfo`/`csv`、pytest、httpx；沿用现有 React + TypeScript + Vite 前端。

**Spec:** `/Users/inception/learning/ocean-training-platform/docs/superpowers/specs/2026-11-22-training-platform-backend-design.md`；前端固定契约见 `/Users/inception/learning/ocean-training-platform/frontend/src/api/types.ts` 与 `/Users/inception/learning/ocean-training-platform/docs/superpowers/plans/2026-11-23-training-platform-frontend.md`。

## Global Constraints

- 项目根目录为 `/Users/inception/learning/ocean-training-platform`；不引入生产登录、云部署、消息队列或无关功能。
- 执行 Task 7 前，工作分支必须包含现有前端实现（当前位于 `feat/frontend`）；若从仅有设计文档的 `main` 开工，先基于前端分支建后端工作分支，或待前端 PR 合并后再联调。
- 业务 API 只从 `X-Actor-Email` 解析管理员；`tenant_id` 不作为客户端授权范围输入。Alice/East 与 Bob/West 的同名课程和学员必须隔离。
- 所有 POST 必须有 `Idempotency-Key`，同键同请求重放原状态码与 JSON，跨路径或改请求体返回 409；GET 无业务副作用且每次重新查询。
- 两个 POST 接受 `{}` 或空请求体，成功返回 200 JSON；JSON 字段、枚举、错误体、CSV 列名与设计文档 §5 完全一致。
- SQLite 每连接启用外键和 `busy_timeout`；初始化启用 WAL。写请求使用 `BEGIN IMMEDIATE`，证书变更、审计和幂等结果同一事务提交。
- 证书日期使用租户 IANA 时区；列表和 CSV 按租户本地日历日期排序，所有排序以证书 ID 升序收尾。
- 默认数据保持轻量；单独命令生成 East 的 100,000 张证书。两次相同条件导出均在 60 秒内完成，导出中列表仍能成功读取。
- 一条文档化命令准备声明的依赖、初始化演示数据、构建前端并启动完整应用；README 给出 A1–A7 复现方法。
- 本计划只规划产品代码与验收。评估文档的 AI 会话证据和书面题属于提交材料：Checklist 追踪其存在与完整性，不生成或代写书面题。

## Review Focus

1. `/api/certificates/export` 与 `/{certificate_id}` 同时存在时，导出必须返回 CSV，不能被详情路由误判为无效 ID（Task 6 `test_export_route_precedes_detail`）。
2. 缺失、过长或带空白的幂等键及非对象 JSON 必须拒绝；已有键改为另一个有效 JSON 对象时优先返回 409，不消耗新业务写入（Task 4 `test_write_validation_and_conflict_order`）。
3. 撤销响应丢失后证书已变成 `REVOKED`，同键重试仍必须重放首次 `changed: true`；新键才返回 `changed: false`（Task 4 `test_revoke_lost_response_replays_first_result`）。
4. Alice 导出尚未读完时 Bob 的列表请求仍只见 West；身份不可由共享会话变量或连接状态覆盖（Task 6 `test_concurrent_export_and_other_actor_list`）。
5. 100,000 行中含相同排序值且搜索命中子集时，两次 CSV 的行序完全相同，且列表在导出期间能完成（Task 6 `test_export_100k_repeatable_with_live_list`）。

---

## File Map

| 路径 | 职责 |
| --- | --- |
| `backend/requirements.txt`, `backend/requirements-dev.txt` | 运行和验证依赖；不混入前端依赖 |
| `backend/app/db.py`, `backend/app/schema.sql`, `backend/app/seed.py`, `backend/app/dates.py` | SQLite 连接、表约束、幂等演示种子、本地日期转换 |
| `backend/app/contracts.py`, `backend/app/errors.py`, `backend/app/actor.py` | 固定 JSON 契约、统一错误、请求级管理员上下文 |
| `backend/app/course_repo.py`, `backend/app/course_service.py`, `backend/app/course_routes.py` | 课程与选课读取、批量颁发入口 |
| `backend/app/certificate_repo.py`, `backend/app/certificate_service.py`, `backend/app/certificate_routes.py` | 证书查询、详情、撤销、导出入口 |
| `backend/app/idempotency.py`, `backend/app/audit_repo.py`, `backend/app/write_service.py` | 统一写事务、键冲突、响应重放、审计和业务写操作 |
| `backend/app/export.py`, `backend/scripts/__init__.py`, `backend/scripts/seed_performance.py` | 流式 CSV 与隔离的 10 万行数据生成 |
| `backend/app/main.py`, `run.sh`, `.gitignore`, `README.md` | 应用装配、静态前端和一键启动/复现说明 |
| `backend/tests/` | 每项任务的行为测试、前端契约、A1–A7 与性能验收 |

`backend/` 和 `backend/app/` 均有 `__init__.py`。测试用临时 SQLite 文件，不接触默认 `data/`。`create_app(db_path: Path, frontend_dist: Path | None = None) -> FastAPI` 是测试和启动共用入口；路由从 `app.state.db_path` 获取数据库路径，禁止模块级共享连接。

## API JSON Contract

下列返回类型由 `backend/app/contracts.py` 中的 Pydantic 模型固定，并与前端 DTO 逐字段比对：

| 路由 | 必须返回 |
| --- | --- |
| `GET /api/me` | `admin: {id,email}`, `tenant: {id,name,timezone}` |
| `GET /api/courses` | `items: [{id,title}]` |
| `GET /api/courses/{id}/enrollments` | `course: {id,title}`, `items: [{learner_id,learner_name,status,active_certificate_id}]` |
| `GET /api/certificates` | `items: [{id,serial_number,learner_name,course_title,issued_local_date,status}]`, `page`, `page_size`, `total` |
| `GET /api/certificates/{id}` | 列表项字段加 `issued_local_datetime` |
| `POST /api/courses/{id}/bulk-issue` | `operation_id`, `status: COMPLETED`, `summary: {issued,skipped,failed}`, `outcomes: [{learner_id,learner_name,result,reason,certificate_id,serial_number}]` |
| `POST /api/certificates/{id}/revoke` | `operation_id`, `certificate_id`, `status: REVOKED`, `changed` |
| 所有 JSON 错误 | `{code,message}`；不使用 FastAPI 默认 `detail` 作为公开格式 |

## Task 1: SQLite Schema, Seed and Time Conversion

**Files:** `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/__init__.py`, `backend/app/__init__.py`, `backend/app/db.py`, `backend/app/schema.sql`, `backend/app/seed.py`, `backend/app/dates.py`, `backend/tests/conftest.py`, `backend/tests/test_storage.py`。

**Interfaces:** `connect(path: Path) -> sqlite3.Connection` 启用 `Row`、外键和 30 秒 busy timeout；`initialize_database(path: Path) -> None` 建表并启用 WAL；`seed_demo_data(path: Path) -> None` 可重复执行；`to_local(issued_at_utc: datetime, timezone: str) -> tuple[str, str]` 返回 `YYYY-MM-DD` 和 `YYYY-MM-DD HH:mm`。

- [ ] 写 `test_schema_rejects_cross_tenant_links_and_duplicate_active_certificate`、`test_seed_is_repeatable`、`test_sydney_perth_local_dates`：同租户复合约束和有效证书部分唯一索引生效；两次种子后行数相同；`2026-01-10T13:30:00Z` 对应 Sydney `2026-01-11 00:30`、Perth `2026-01-10 21:30`。
- [ ] 运行 `python -m pytest backend/tests/test_storage.py -q`，确认测试因待实现接口失败。
- [ ] 建立 schema、连接配置、UTC 时间列、默认 East/West 演示数据与本地日期函数；种子用稳定自然键和 `INSERT ... ON CONFLICT`，不覆盖既有业务记录。
- [ ] 重跑本任务测试并运行 `python -m compileall -q backend`；预期全部通过。提交 `feat: add tenant-safe sqlite schema and demo seed`。

## Task 2: Actor Context, Error Envelope and Course Reads

**Files:** `backend/app/contracts.py`, `backend/app/errors.py`, `backend/app/actor.py`, `backend/app/course_repo.py`, `backend/app/course_service.py`, `backend/app/course_routes.py`, `backend/app/main.py`, `backend/tests/test_actor_courses.py`。

**Interfaces:** `create_app(db_path: Path, frontend_dist: Path | None = None) -> FastAPI`；`resolve_actor(conn: sqlite3.Connection, email: str) -> ActorContext(admin_id, tenant_id, timezone)`；`GET /api/me`、`GET /api/courses`、`GET /api/courses/{id}/enrollments` 使用请求独立连接及 `ActorContext`。

- [ ] 写 `test_me_matches_frontend_contract`、`test_actor_is_resolved_per_request`、`test_course_enrollments_show_only_active_certificate`、`test_unknown_actor_and_cross_tenant_course`：Alice/Bob 请求可交错；缺失/未知身份返回 401；跨租户课程返回 404；全部错误体为 `{code,message}`。
- [ ] 运行 `python -m pytest backend/tests/test_actor_courses.py -q`，确认预期失败。
- [ ] 实现请求级连接与身份依赖、统一异常处理、课程读取；不接受客户端 `tenant_id` 授权参数，列表和选课只按当前租户查询。
- [ ] 重跑本任务测试和 `python -m pytest backend/tests -q`；预期通过。提交 `feat: add actor-scoped course reads`。

## Task 3: Certificate List and Detail

**Files:** `backend/app/certificate_repo.py`, `backend/app/certificate_service.py`, `backend/app/certificate_routes.py`, `backend/app/contracts.py`, `backend/app/main.py`, `backend/tests/test_certificate_reads.py`。

**Interfaces:** `GET /api/certificates?search&sort&direction&page&page_size` 返回与前端 `CertificateListResponse` 同形 JSON；`GET /api/certificates/{id}` 返回 `CertificateDetail`；`sort` 仅接受四个白名单字段，`direction` 仅 `asc`/`desc`，`page_size` 为 1–100 且默认 20。

- [ ] 写 `test_search_sort_page_and_total_share_snapshot`、`test_detail_local_datetime_and_revoked_visible`、`test_cross_tenant_detail_is_404`、`test_bad_query_and_unknown_tenant_filter_422`；含相同排序值的 ID 稳定次序、空搜索、空页、A5 日期。
- [ ] 运行 `python -m pytest backend/tests/test_certificate_reads.py -q`，确认预期失败。
- [ ] 实现参数白名单、姓名/序列号不区分大小写子串搜索、列表总数与行的同一读事务、租户范围详情和 `Cache-Control: no-store`。
- [ ] 重跑本任务测试及全量快速测试；预期通过。提交 `feat: add scoped certificate browsing`。

## Task 4: Unified Idempotency and Revocation

**Files:** `backend/app/idempotency.py`, `backend/app/audit_repo.py`, `backend/app/write_service.py`, `backend/app/certificate_routes.py`, `backend/app/contracts.py`, `backend/tests/test_idempotency_revoke.py`。

**Interfaces:** `parse_write_body(raw: bytes) -> dict` 只接受 JSON 对象或空体；`fingerprint(method: str, route_template: str, target_id: int, body: dict) -> str` 规范化 JSON 后哈希。`execute_write(conn: sqlite3.Connection, actor: ActorContext, key: str, fingerprint: str, validate_new_request: Callable[[], None], perform: Callable[[int], tuple[int, dict]]) -> tuple[int, dict]` 在 `BEGIN IMMEDIATE` 下查键、409 或重放、调用目标校验、插入记录、用记录 ID 调用业务回调、保存结果并提交；异常回滚。两个回调闭包可访问同一连接。`POST /api/certificates/{id}/revoke` 返回 `RevokeResponse`。

- [ ] 写 `test_write_validation_and_conflict_order`、`test_revoke_lost_response_replays_first_result`、`test_new_key_revoke_is_noop_with_one_audit`、`test_cross_tenant_revoke_has_no_record_or_audit`、`test_same_key_parallel_revoke_replays_one_result`；断言状态码、响应 JSON、证书状态、审计和幂等记录行数。
- [ ] 运行 `python -m pytest backend/tests/test_idempotency_revoke.py -q`，确认预期失败。
- [ ] 实现共用事务：同键同指纹优先重放，异指纹 409；新请求的额外业务字段 422；无效目标 404 且不占键；首次有效撤销 `changed: true`，新键已撤销 `changed: false`。临时锁超时允许原键重试。
- [ ] 重跑本任务测试和全量快速测试；预期通过。提交 `feat: add replay-safe certificate revocation`。

## Task 5: Bulk Issue with Per-Learner Outcomes

**Files:** `backend/app/course_routes.py`, `backend/app/course_service.py`, `backend/app/write_service.py`, `backend/app/certificate_repo.py`, `backend/app/contracts.py`, `backend/tests/test_bulk_issue.py`。

**Interfaces:** `POST /api/courses/{id}/bulk-issue` 通过 Task 4 的 `execute_write` 返回 `BulkIssueResponse`；`outcomes` 每名选课学员一项，按学员 ID 升序；`issued` 项有新证书 ID/序列号，`skipped`/`failed` 项有可展示原因且证书字段为 `null`。

- [ ] 写 `test_completed_incomplete_and_certified_outcomes`、`test_same_key_sequential_and_parallel_bulk_issue`、`test_key_reuse_across_courses_or_write_types_is_409`、`test_row_failure_rolls_back_only_that_learner`、`test_reissue_after_revocation_creates_new_serial`；按结果逐一核对证书和 `ISSUED` 审计计数。
- [ ] 运行 `python -m pytest backend/tests/test_bulk_issue.py -q`，确认预期失败。
- [ ] 在同一写事务中按学员处理选课；未完成/已有 ACTIVE 跳过；每名学员用 savepoint 保证可恢复行错误不影响其他学员；系统错误整体回滚。保存完整 `200` 响应供同键重放。
- [ ] 重跑本任务测试和全量快速测试；预期通过。提交 `feat: add idempotent bulk certificate issue`。

## Task 6: Streaming CSV and 100,000-Row Growth Check

**Files:** `backend/app/export.py`, `backend/app/certificate_routes.py`, `backend/app/certificate_repo.py`, `backend/scripts/__init__.py`, `backend/scripts/seed_performance.py`, `backend/tests/test_export.py`, `backend/tests/test_export_performance.py`。

**Interfaces:** `GET /api/certificates/export?search&sort&direction` 以 `text/csv; charset=utf-8` 流式输出四列 `learner_name,course_title,serial_number,issued_local_date`；`python -m backend.scripts.seed_performance --db <path> --tenant East --count 100000` 只向指定测试库追加所需数据，不改变默认 quick-start 数据库。

- [ ] 写 `test_export_route_precedes_detail`、`test_export_filters_sort_and_quotes_csv`、`test_concurrent_export_and_other_actor_list`；测试完整读取 CSV、正确转义逗号/引号/换行、REVOKED 保留、无分页且不混租户。
- [ ] 写 `test_export_100k_repeatable_with_live_list`：在隔离数据库生成恰好 100,000 条 East 性能证书和相同排序值，用本地 HTTP 服务真实流式下载两次；每次 60 秒内完成，匹配行数和顺序相同，导出未结束时列表请求成功。
- [ ] 运行 `python -m pytest backend/tests/test_export.py backend/tests/test_export_performance.py -q`，确认预期失败。
- [ ] 用独立只读连接、稳定排序和 `fetchmany`/生成器实现 CSV；生成器负责关闭连接；性能脚本与默认种子隔离。重跑本任务测试及全量快速测试，预期通过；提交 `feat: add stable streaming certificate export`。

## Task 7: One-Command App and Frontend Contract Integration

**Files:** `backend/app/main.py`, `run.sh`, `.gitignore`, `README.md`, `frontend/README.md`, `backend/tests/test_frontend_contract.py`, `backend/tests/test_static_app.py`。

**Interfaces:** `./run.sh` 创建/复用 `.venv`、安装声明的 Python 依赖、执行 `npm --prefix frontend ci` 和 `npm --prefix frontend run build`、幂等初始化/播种 `data/training.sqlite3`，然后以 `127.0.0.1:8000` 启动 FastAPI。`/api/*` 优先匹配 API，`/`、`/certificates`、`/courses` 及前端资源由构建产物提供。

- [ ] 写 `test_all_json_shapes_match_frontend_contract`、`test_spa_routes_and_api_do_not_shadow_each_other`、`test_get_after_committed_write_reads_new_state`；实际 HTTP 响应逐字段比对前端 DTO，刷新深链接返回 SPA，JSON/CSV 不被静态回退接管。
- [ ] 运行 `python -m pytest backend/tests/test_frontend_contract.py backend/tests/test_static_app.py -q`，确认预期失败。
- [ ] 实现静态资源装配和根启动脚本，将 `.venv/` 加入 `.gitignore`；README 写清 `./run.sh`、演示管理员 header、验证命令、10 万行脚本、已知限制和 A1–A7 可复制复现步骤。
- [ ] 重跑本任务测试；从干净的临时数据目录执行 `./run.sh`，用浏览器或 `curl` 验证 `/`、`/certificates`、`/courses`、`/api/me`，确认第二次启动不重复种子。提交 `feat: serve full app with one-command startup`。

## Task 8: Complete Acceptance and Submission Audit

**Files:** `backend/tests/test_acceptance.py`, `README.md`, `docs/superpowers/checklists/2026-11-23-training-platform-backend.md`。

**Interfaces:** 独立临时数据库的 API/数据库测试连通选课、批量颁发、证书查询、撤销与 CSV；Tasks 2–6 的专项测试提供 A1–A7 证据。Checklist 逐项记录命令、结果和未完成风险。AI 会话导出、会话索引、决策日志与个人书面答题由提交者依评估说明提供，本任务只核对存在与完整性，不制造内容。

- [ ] 写 `test_end_to_end_actor_issue_revoke_export`：从 Alice 选课、批量颁发、证书查询、撤销到 CSV 再次读取，断言 API 响应和证书/审计/幂等记录；Bob 的后续读取仍仅见 West。
- [ ] 运行 `python -m pytest backend/tests/test_acceptance.py -q`，确认测试在未满足验收前失败；补齐缺失行为后重跑到通过。
- [ ] 执行 `python -m pytest backend/tests -q`、`npm --prefix frontend test`、`npm --prefix frontend run typecheck`、`npm --prefix frontend run build`；单独记录 10 万行性能耗时、一键启动和真实浏览器主流程结果。把证据填入 Checklist，未通过项保持未勾选。
- [ ] 审核 README 与评估提交材料清单：完整会话原生导出、索引、真实决策日志和工具动作证据；用户本人独立完成书面题。只在实际材料存在时勾选；提交产品验收代码及文档 `test: verify A1-A7 and document reproduction`。

## Self-Review Result

设计 §3–4 由 Tasks 1–2/4–5 覆盖；§5 的七个 API 和错误契约由 Tasks 2–7 覆盖；§6 的幂等、批量、撤销、日期与流式导出由 Tasks 3–6 覆盖；§7 的演示数据和 A1–A7 由 Tasks 1/6/8 覆盖。一键启动和前端集成由 Task 7 覆盖。每个 Review Focus 案例有明确拥有者测试。Task 8 不代写评估文档 Section 6 的个人答案，也不把提交材料存在性误当作后端功能测试通过。
