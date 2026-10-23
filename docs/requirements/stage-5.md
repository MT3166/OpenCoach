# OpenCoach 二次开发任务 · 阶段 5 / 5

## ① 你的角色与当前工程

你是接手 **OpenCoach** 的资深全栈工程师（Django 5.2 + DRF + Vue 3 + Vite，SQLite，同镜像交付）。

这是**收尾阶段**，建立在阶段 1–4 之上。本阶段要求你对前四个阶段的产物做**全盘整合与加固**：既要把它们统计进经营报表，也要清理半成品、补齐边界与错误态。

## ② 环境与硬性技术约束

同前：Python 3.12、Node ≥ 24、运行期无需 Node、尽量不新增依赖。

## ③ 本阶段需求：月度经营报表 + 收尾加固

**A. 月度经营报表**

教练需要查看某个月的经营概览。请实现按 `Asia/Shanghai` 月份边界的聚合，至少包含：

- `scheduled_attended`：该月已到课（完成）的预约数。
- `scheduled_missed`：该月缺席（已消课或免消课）的预约数。
- `scheduled_cancelled`：该月取消的预约数。
- `pending`：该月已到时间但尚未处理的预约数。
- `direct_attended`：该月直接记课数。
- `waitlist_promoted`：该月由候补递补转正的人数（阶段 4）。
- `credit_expired`：该月过期流失的课时数（阶段 1）。

口径要求：

1. 预约到课率**只按已处理预约**计算；直接记课**单独展示**，不虚构"应到"分母。
2. **已整堂取消**的课次不计入应到分母。
3. 空月份返回全 0，不报错；跨月边界正确。

**B. 收尾加固**

- 覆盖前四阶段的**边界与错误态**（无效输入、越权、过期、满员、重复提交等），返回规范的 `{error:{...}}`。
- 清理本任务过程中产生的**死代码、半成品与 TODO**；确保没有留下未使用的字段或未接线的前端入口。
- 确认前端相应入口可用（教练端可查看月度报表）。

## ④ 不可违背的契约

遵守随附的《契约附件》。

**本阶段附加 API 契约（必须严格实现，供验收）：**

- 新增 `GET /api/v1/coach/reports/monthly/?month=YYYY-MM`，响应：
  ```json
  {"data": {
    "month": "YYYY-MM",
    "scheduled_attended": 0,
    "scheduled_missed": 0,
    "scheduled_cancelled": 0,
    "pending": 0,
    "direct_attended": 0,
    "waitlist_promoted": 0,
    "credit_expired": 0
  }}
  ```

## ⑤ 交付物格式

同前：完整工程快照压缩包（不含依赖/构建产物/数据库/密钥）+ 变更说明（含前四阶段的累计改动与未完成项）。

## ⑥ 自验证要求

同前：自行补测并实际运行 `manage.py test`、`makemigrations --check --dry-run`、`npm run build`；变更说明中列出实际命令与结果。

## ⑦ 明确禁止

同前。另外：**不得为了让统计数字好看而虚构数据或改动既有账目口径。**
