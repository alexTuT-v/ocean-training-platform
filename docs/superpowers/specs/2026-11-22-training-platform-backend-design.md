# Training Platform 后端技术设计

日期：2026-11-22；修订：2026-11-23  
状态：已确认（所有写接口统一幂等修订版）  
范围：面试评估中的多租户证书管理后端

## 1. 目标与边界

交付可运行的 Python 后端，支持管理员查看课程完成情况、查询证书、批量颁发、撤销和 CSV 导出，覆盖评估文档 A1–A7。优先保证租户隔离、所有写接口的幂等性、准确审计、租户本地日期和 10 万行导出。读接口不产生业务副作用，每次请求重新查询已提交的最新数据。代码按 API、业务服务和数据访问层分开，保留更换存储实现的空间；本设计不包含未来功能。

不做生产级登录、云部署、通知、后台任务队列和无关的管理功能。接口以演示身份 header 模拟已登录管理员；它不能防止调用方伪造身份，不能作为生产认证方案。前端负责撤销确认与防重复点击，后端独立保证业务正确性。

评估材料要求一条命令完成依赖准备、数据初始化和应用启动；另备验证命令。默认数据保持轻量，10 万行数据通过单独脚本生成。

本文件只设计后端；完整提交仍需 React/Vue 前端。集成时由启动脚本准备 Python/Node 依赖、构建前端、初始化演示数据库，再启动 FastAPI；FastAPI 提供 `/api` 和构建后的静态前端资源，使完整应用由一条命令启动。具体前端页面与交互另行设计。

## 2. 方案选择

| 方案 | 优点 | 代价 |
| --- | --- | --- |
| A：FastAPI + Python 标准库 `sqlite3`（已选） | SQL、锁和事务边界显式；依赖少；便于说明并发幂等与导出行为 | 换数据库时需改数据访问层；需自行维护映射和 SQL |
| B：FastAPI + SQLAlchemy | 模型和查询组织方便 | SQLite 的关键事务仍需专门处理；多一层抽象和依赖 |

采用 A。服务按 `api → service → repository → SQLite` 分层。API 层只做参数解析和 HTTP 映射；service 层执行业务规则；repository 层持有参数化 SQL、事务和行映射。全部 SQL 使用参数绑定；排序列和方向只能从白名单映射，不拼接用户原文。

写接口幂等另比较过两种实现：方案 A（已选）使用统一的 `idempotency_records` 表，让批量颁发和撤销共用键冲突、响应重放与事务规则；方案 B 为每种写操作分别建记录表，局部逻辑较直观但会重复实现，且跨接口复用键时口径不一致。用户确认所有写接口需要幂等、读接口每次重新查询，因此采用统一方案 A。

## 3. 身份与租户边界

演示请求传 `X-Actor-Email`。后端在每个请求开始时查询 `admins`，得到 `admin_id`、`tenant_id` 和租户时区，生成 `ActorContext`；未知管理员返回 401。前端选择 Alice/Bob 只是切换该 header，没有登录 UI。该 header 是可信身份层的演示替身，持有人可冒充对应管理员；文档和 README 必须如实说明。

业务 API 不从 URL 或请求体接受可决定授权范围的 `tenant_id`。所有课程、学员、选课、证书、审计和幂等操作以 `ActorContext.tenant_id` 为查询条件。详情与撤销对其他租户的对象返回 404；批量颁发对其他租户的课程返回 404，且不创建证书、操作记录或审计事件。列表及导出只读取当前租户。若客户端附带未知的租户筛选参数，返回 422，避免误以为该参数生效。

## 4. 数据模型与约束

所有时间戳以 UTC ISO 8601 格式存储。SQLite 每个连接启用 `PRAGMA foreign_keys=ON`、`busy_timeout`，数据库初始化时启用 WAL。数据库文件放在项目数据目录；默认启动可重复运行且不会覆盖已有业务记录。

| 表 | 关键字段与约束 |
| --- | --- |
| `tenants` | `id`, `name`, `timezone`（IANA 名称） |
| `admins` | `id`, `tenant_id`, `email` 唯一 |
| `courses` | `id`, `tenant_id`, `title` |
| `learners` | `id`, `tenant_id`, `name` |
| `enrollments` | `id`, `tenant_id`, `course_id`, `learner_id`, `status` (`COMPLETED`/`INCOMPLETE`), `completed_at_utc`; 同租户课程与学员组合唯一 |
| `certificates` | `id`, `tenant_id`, `course_id`, `learner_id`, `serial_number` 全局唯一, `issued_at_utc`, `issued_local_date`, `status` (`ACTIVE`/`REVOKED`), `revoked_at_utc`; 部分唯一索引保证同租户、课程、学员最多一张 `ACTIVE` 证书 |
| `audit_events` | `id`, `tenant_id`, `certificate_id`, `actor_id`, `event_type` (`ISSUED`/`REVOKED`), `occurred_at_utc`, `idempotency_record_id`；每张证书每种事件至多一条 |
| `idempotency_records` | `id`, `tenant_id`, `actor_id`, `idempotency_key`, `request_fingerprint`, `operation_type`, `response_status`, `response_body_json`, `created_at_utc`, `completed_at_utc`; `(tenant_id, actor_id, idempotency_key)` 唯一 |

课程、学员、选课、证书的租户字段在写入时交叉校验，并以复合外键或等效数据库约束阻止跨租户关联。`audit_events` 对每张证书的 `ISSUED` 至多一条、`REVOKED` 至多一条；业务层同时控制事件只伴随实际状态变化写入。撤销后旧证书仍保留，后续颁发生成新序列号和新证书记录。为列表和导出准备租户与本地日期排序索引、序列号索引；10 万行场景再以查询计划核对索引效果。

## 5. API 契约

所有业务 API 要求 `X-Actor-Email`。所有写 API 额外要求非空 `Idempotency-Key`，缺失或格式错误返回 422；读 API 不使用幂等键。返回 JSON；无权限或跨租户对象使用 404，参数错误 422，幂等键冲突 409，服务错误 500。错误体含稳定的错误代码和用户可读消息，不回显其他租户对象信息。读 API 每次使用新查询读取该查询开始时已提交的数据，不缓存上次响应；单次导出保持查询自身的一致视图，后续导出重新查询。

| 方法和路径 | 用途 |
| --- | --- |
| `GET /api/me` | 返回当前管理员、租户和时区，供 UI 展示身份 |
| `GET /api/courses` | 返回当前租户课程，供批量颁发选择 |
| `GET /api/courses/{course_id}/enrollments` | 查看当前租户课程的学员完成状态与当前有效证书状态 |
| `GET /api/certificates` | `search`, `sort`, `direction`, `page`, `page_size`；搜索学员姓名或序列号；返回分页列表与总数 |
| `GET /api/certificates/{certificate_id}` | 返回证书详情，包括状态与租户本地签发日期/时间 |
| `POST /api/courses/{course_id}/bulk-issue` | 必填 `Idempotency-Key`；请求体为空 JSON 对象或省略；逐学员返回 `issued`、`skipped`、`failed` 及原因和操作状态；同键重试重放首次响应 |
| `POST /api/certificates/{certificate_id}/revoke` | 必填 `Idempotency-Key`；首次撤销改变状态并记审计；同键重试重放首次响应；新键重复撤销返回已撤销状态而不重复记审计 |
| `GET /api/certificates/export` | 使用与列表相同的 `search`、`sort`、`direction`，流式返回 CSV；不分页 |

前端已按下列 JSON 形状实现；后端不得用框架默认的 `detail` 响应替代这些字段：

| 接口 | 成功响应（字段名和层级固定） |
| --- | --- |
| `GET /api/me` | `{ "admin": { "id": 1, "email": "alice@east.test" }, "tenant": { "id": 1, "name": "East", "timezone": "Australia/Sydney" } }` |
| `GET /api/courses` | `{ "items": [{ "id": 1, "title": "Safety 101" }] }` |
| `GET /api/courses/{id}/enrollments` | `{ "course": { "id": 1, "title": "Safety 101" }, "items": [{ "learner_id": 1, "learner_name": "Alex Lee", "status": "COMPLETED", "active_certificate_id": null }] }`；`status` 仅为 `COMPLETED`/`INCOMPLETE`，有效证书 ID 可为 `null` |
| `GET /api/certificates` | `{ "items": [{ "id": 1, "serial_number": "...", "learner_name": "Alex Lee", "course_title": "Safety 101", "issued_local_date": "2026-01-11", "status": "ACTIVE" }], "page": 1, "page_size": 20, "total": 1 }`；状态仅为 `ACTIVE`/`REVOKED` |
| `GET /api/certificates/{id}` | 列表项的全部字段，另有 `issued_local_datetime`，格式为租户本地 `YYYY-MM-DD HH:mm` |
| `POST /api/courses/{id}/bulk-issue` | `{ "operation_id": 1, "status": "COMPLETED", "summary": { "issued": 1, "skipped": 1, "failed": 0 }, "outcomes": [{ "learner_id": 1, "learner_name": "Alex Lee", "result": "issued", "reason": null, "certificate_id": 1, "serial_number": "..." }] }`；每名选课学员恰有一项；`result` 为 `issued`/`skipped`/`failed`，未适用的证书字段为 `null`，跳过和失败的 `reason` 为可直接展示的非空文字 |
| `POST /api/certificates/{id}/revoke` | `{ "operation_id": 1, "certificate_id": 1, "status": "REVOKED", "changed": true }`；新键重复撤销时 `changed: false`，同键重试重放原值 |

两个写接口在同步完成后返回 `200` 和上述 JSON；不返回空的 `204` 或需要轮询的 `202`。错误体固定为 `{ "code": "STABLE_CODE", "message": "可读说明" }`，包括 FastAPI 参数校验错误；业务对象不存在或跨租户均返回不泄露对象信息的 `404`。`Idempotency-Key` 接受 1–128 个可打印的非空白 ASCII 字符，按原值比较；缺失或格式不符返回 `422`。演示系统不清理已完成的幂等记录，保证同一会话页面刷新后的未决请求仍可重放。

查询参数 `direction` 使用 `asc`/`desc`；`page` 从 1 开始，`page_size` 接受 20 且设 1–100 上限；空 `search` 表示不过滤。列表的 `items` 与 `total` 在同一只读快照中取得。GET 响应使用 `Cache-Control: no-store`，路由注册保证 `/api/certificates/export` 不被 `/{certificate_id}` 捕获。CSV 响应为 `text/csv; charset=utf-8`，列标题依次为 `learner_name,course_title,serial_number,issued_local_date`；后端不依赖前端提供的下载文件名。

列表和导出均包含 `ACTIVE` 与 `REVOKED`，搜索范围一致。首版排序白名单为 `issued_local_date`、`learner_name`、`course_title`、`serial_number`；默认 `issued_local_date DESC`。每种排序都追加 `certificate.id ASC` 作为最终稳定次序。列表分页使用 `LIMIT/OFFSET`；`page_size` 设置上限，避免单次响应过大。CSV 列顺序固定为学员姓名、课程标题、序列号、租户本地签发日期，不额外导出状态（按评估要求）。

## 6. 核心流程

### 6.1 所有写接口共用的幂等边界

客户端在一次写操作意图开始时生成随机键，并在该操作的网络重试中复用；明确发起新操作时生成新键。服务端对当前 HTTP 方法、路由模板、路径对象 ID、规范化 JSON 请求体生成 `request_fingerprint`。缺失的请求体与 `{}` 等价；有效 JSON 对象的键排序后计算指纹，空白和对象键顺序不影响指纹。当前两个写接口都只接受空 JSON 对象或省略请求体，不增加额外业务参数。同一 `(tenant_id, actor_id, idempotency_key)` 的指纹相同则重放首次已提交的 HTTP 状态码和 JSON 响应；指纹不同返回 409，不执行第二次操作。该键在批量颁发和撤销之间共享命名空间，因此跨接口复用同键也返回 409。

每个写接口先解析管理员、验证幂等键格式并解析 JSON 对象，计算请求指纹；随后开启 `BEGIN IMMEDIATE` 事务并检查幂等键。若已有记录，指纹不同优先返回 409，指纹相同则直接重放保存的响应。若无记录，再校验请求体必须为空对象，并按当前租户查目标对象；跨租户或不存在的对象返回 404，不写幂等记录。目标合法后插入 `idempotency_records`（响应字段暂空），执行业务变更与审计写入，再把最终 `response_status`、`response_body_json` 和 `completed_at_utc` 写回同一记录，最后一次性提交。这样同键改用另一课程或追加 JSON 字段仍返回 409；使用新键提交额外字段则返回 422。其他连接只看得到已完成的记录，不会看到半成品。可预期的业务无操作结果也保存为首次响应；系统性错误则整体回滚、不占用幂等键，重试可重新执行。并发重试等待写锁后读取首次结果；锁等待超时应按临时错误处理并允许客户端用同键重试。

`idempotency_records.id` 是响应中的逻辑操作 ID，也是相关审计事件的关联 ID。API 不提供实时轮询：UI 在写请求进行中显示处理中，提交后显示最终状态。当前仅有批量颁发和撤销两个写接口；后续若新增写接口，应接入同一边界，但本设计不增加新功能。

### 6.2 批量颁发

在上述写事务中遍历当前租户课程的选课记录：未完成跳过并标原因；已有 `ACTIVE` 证书跳过并标原因；已撤销证书不阻止再次颁发。对符合条件者插入证书和一条 `ISSUED` 审计事件。逐学员使用 savepoint：某条意外失败时撤回该学员的证书和事件，记录 `failed`，继续其余学员；无法可靠继续的系统性错误回滚整个操作。首次完整结果（包括各学员结果、汇总和操作状态）写入通用幂等记录的 `response_body_json`。有效态唯一索引是不同幂等键竞争颁发时的最终保护。操作同步完成，不引入任务队列。

### 6.3 撤销

在上述写事务中按当前租户再次确认目标证书。若为 `ACTIVE`，更新为 `REVOKED`、写撤销时间和一条 `REVOKED` 审计事件，并把首次响应存入幂等记录。同键重试重放该响应。若已经 `REVOKED` 且使用新键，记录本次无操作响应，但不新增撤销审计事件。UI 在发送前进行确认；服务器不依赖 UI 确认保证正确性。

### 6.4 日期、排序与导出

签发时用租户 IANA 时区将 UTC 时间转为本地时间，保存 `issued_local_date`（`YYYY-MM-DD`），用于列表排序与 CSV。详情显示可由 UTC 时间和租户时区计算本地日期时间。由此，同一 `2026-01-10T13:30:00Z` 在 Sydney 为 `2026-01-11 00:30`，在 Perth 为 `2026-01-10 21:30`。时间使用 Python `zoneinfo`，不写固定 UTC 偏移量。10 万行生成脚本也经过同一转换逻辑。

导出复用列表的租户过滤、搜索和排序构造器，但不应用分页。独立 SQLite 只读连接执行查询，游标分批读取，逐批生成 CSV，避免把 10 万行一次性装入内存。HTTP 响应以流式方式发送，正确转义逗号、引号、换行；CSV 使用 UTF-8 with BOM 仅在确认 Excel 兼容性需要时加入，默认 UTF-8。WAL 允许导出读取期间其他连接继续读写；列表请求使用自己的连接，不共享导出游标。相同排序值以证书 ID 决定稳定顺序。100,000 行、搜索、重复导出和并发列表通过 A6 专项验证，要求每次导出 60 秒内完成。

## 7. 演示数据和验证

默认种子：East (`Australia/Sydney`)/Alice (`alice@east.test`)；West (`Australia/Perth`)/Bob (`bob@west.test`)；各租户均有 `Safety 101` 和 `Alex Lee`，并包含完成、未完成、已有有效证书的选课数据。种子中加入 A5 指定 UTC 时刻的证书，保证两个时区的跨日场景可复现。种子脚本可重复运行、不复制记录。

单独的性能种子命令只向 East 生成 100,000 张证书，包含相同排序值，并记录预期行数。默认快速启动不运行性能种子。若为性能数据生成额外学员/选课，保持同一租户关联完整。

验证以 A1–A7 为主：跨租户 API 与零副作用；相同键顺序/并发重试；冲突键 409；三类学员结果；Sydney/Perth 本地日期；10 万行两次导出稳定且并发列表成功；重复撤销只有一条事件。另验证撤销接口同键重放首次响应、跨写接口同键返回 409、新键重复撤销无审计副作用，以及读接口在并发写提交后读取最新已提交状态。用 API 自动化检查数据库行数、审计计数、CSV 行数/顺序和耗时；README 给出逐项复现命令。另检查一命令启动、空结果和错误响应。

验收场景的具体断言如下，作为实施计划与验证脚本的输入：

| 场景 | 必须验证的结果 |
| --- | --- |
| A1 租户隔离 | Bob 尝试通过列表、详情、批量颁发和导出访问 East；只能获得 West 数据。跨租户详情不泄露，跨租户批量颁发不生成证书或审计事件。 |
| A2 重试安全 | Alice 用相同键顺序和并发重发同一批量请求；所有调用得到同一逻辑结果，每名合格学员至多一张证书，每次实际颁发恰一条审计事件。 |
| A3 键误用 | 同键换课程或请求体返回 409，不执行第二次、不覆盖原结果。 |
| A4 学员结果 | 只有已完成且未持有效证书者获证；未完成和重复案例跳过并说明原因。 |
| A5 时区 | 相同 UTC `2026-01-10T13:30:00Z` 在 East 显示 `2026-01-11 00:30`，在 West 显示 `2026-01-10 21:30`；排序及 CSV 使用租户本地日历日期。 |
| A6 导出增长 | East 生成 100,000 条（包含排序值相同的行），搜索排序后重复导出，两次均在 60 秒内完成，行集、顺序正确且相同排序值次序稳定；导出期间列表请求成功。 |
| A7 撤销审计 | 首次撤销更改状态并记录一条事件；重复撤销不产生额外事件。 |

## 8. 实施边界与待确定事项

已由讨论确定：完整覆盖当前后端需求；Python + SQLite；FastAPI + `sqlite3`；管理员信息由 header 标识、后端查出租户；撤销后允许重新颁发；撤销证书保留在列表和导出中；所有写接口共用幂等记录并保证重试无额外副作用；读接口无业务副作用且每次重新查询最新已提交状态。

由设计者决定的细节：`X-Actor-Email` 作为演示身份标识；API 不设租户路径；同步批量操作；重复撤销返回当前状态；列表搜索使用大小写不敏感的子串匹配；排序白名单及默认排序；CSV 不导出状态列；固定 UTF-8 编码。这些应在 README 和 API 说明中写清。

设计已由用户确认。本阶段未创建产品代码或项目脚手架。
