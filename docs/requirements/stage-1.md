# OpenCoach 二次开发任务 · 阶段 1 / 5

## ① 你的角色与当前工程

你是接手 **OpenCoach** 的资深全栈工程师。这是一个**单教练实例**的约课/课时/训练指导 H5。

- 后端：Django 5.2 + DRF（`opencoach/` 项目、`coaching/` 业务域，HTTP 层在 `coaching/api/`）。
- 前端：Vue 3 + TypeScript + Vite + Vue Router（`frontend/`）。
- 前后端打包进**同一镜像**交付，运行期不需要 Node；数据库为 SQLite（WAL + `transaction_mode=IMMEDIATE`）。
- 当前工程是一个**可运行基线**：`pip install -r requirements.txt`、`npm ci` 后 `manage.py test` 全绿、`npm run build` 成功。（本地首次跑测试前需 `manage.py collectstatic --noinput`。）

先自行通读 `README.md`、`PRODUCT.md`、`coaching/models.py`、`coaching/booking.py`、`coaching/api/*`，理解课时账本与预约的处理方式，再动手。

## ② 环境与硬性技术约束

- Python 3.12（以 `requirements.txt` 为准）、Node ≥ 24。
- 保持"运行期无需 Node"的同镜像交付方式。
- 尽量**不新增依赖**；若确有必要，必须在交付说明里给出理由与替代方案。

## ③ 本阶段需求：课包有效期与到期

教练希望卖出的课包能带**有效期**。请实现以下行为：

1. 教练录入续课时，可以**选填**一个到期日（不填则为长期有效）。
2. 学员的课时在**到期日之后**不能再用于预约或消课；教练在到期日当天仍可正常使用。
3. 教练端与学员端查看余额时，要能**区分**"剩余有效课时"和"已过期课时"。
4. 到期判定以会话时区（`Asia/Shanghai`）的**自然日**为准。
5. 既有购买记录绝大多数**没有到期日**，升级后必须视为**长期有效**——不能因为新增字段而丢失数据或把它们误判为已过期。
6. 学员端对即将到期（例如 7 天内）的课包应有可感知的提醒入口。
7. 已经存在的历史账目与流水不受影响，仍可正常查询。

## ④ 不可违背的契约

遵守随附的《契约附件》（域不变量、接口约定、前端约定、数据约定、工程约定）。

**本阶段附加 API 契约（必须严格实现，供验收）：**

- `POST /api/v1/coach/students/<pk>/credits/`：请求体在既有 `{kind, units, operation_key}` 基础上，新增可选字段 `expires_on`（`YYYY-MM-DD`，可为空）。
- 余额项 `wallets` 每个 `kind` 的返回新增字段 `expired`；语义为 `available = remaining - reserved - expired`。
- 课时流水项 `credit_data` 新增字段 `expires_on`（无到期日为 `null`）。

## ⑤ 交付物格式

返回**完整工程快照压缩包**：含全部源码与配置；**不含**依赖目录（`.venv/`、`node_modules/`）、构建产物（`dist/`、`staticfiles/`）、数据库、密钥。附一份**变更说明**（做了什么、关键取舍、未完成项）。

## ⑥ 自验证要求

自行补充/调整测试覆盖你新增的行为，并**实际运行**：

- `python manage.py test --noinput`（既有测试必须仍全绿）
- `python manage.py makemigrations --check --dry-run`
- `npm run build`（含 typecheck）

在变更说明里列出你实际跑过的命令与结果。我们会独立复核；**报告与交付的代码必须一致**。

## ⑦ 明确禁止

- 不得伪造或绕过测试；不得把"我运行了脚本"当作通过证据。
- 不得提交密钥、数据库或构建产物。
- 不得为通过检查而写死行为、放宽数据库约束或改既有测试。
