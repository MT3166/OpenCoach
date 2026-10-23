# OpenCoach 五阶段累计变更与验收

交付日期：2026-10-16。基于既有 Vue H5 + Django/DRF 工程增量开发，五阶段累计交付一个完整源码快照。没有新增第三方依赖。

## 功能与入口

| 阶段 | 实现 | 前端入口 | 主要证据 |
|---|---|---|---|
| 1 有效期 | 续课可填 expires_on；到期日当天有效；上海次日失效；有效/过期余额及7天提醒；旧购买永久有效 | 教练学员档案「录入续课」；学员首页及「我的课包」 | test_credit_expiry.py、test_stage_hardening.StageMigrationTests |
| 2 改期 | 双方改期API；原预约取消留存；目标类型/容量/冲突/有效课时检查；原子转移和幂等；学员至少提前12小时 | 学员「我的预约」与教练预约详情「改期到其他课次」 | test_reschedule_batch.py、test_stage_hardening.py、浏览器筛选重置回归 |
| 3 批量记课 | 同类同日批量提交，整批回滚；逐项幂等，整批键绑定内容；返回记录与余额 | 教练「记课」→「批量记课 / 小班结算」 | test_reschedule_batch.py、test_stage_hardening.py、浏览器错误及成功流程 |
| 4 候补 | 满员加入、查看/退出；按created_at/id递补；跳过课时无效/冲突/停用账号；取消/改期释放时原子递补；整堂取消不递补 | 学员约课「加入候补」及我的预约「我的候补」；教练课次「候补队列」 | test_waitlist.py、test_stage_hardening.StageConcurrencyTests |
| 5 月报/收尾 | 上海月份边界，七项经营指标及限定分母到课率；空月、错误输入与权限；UI直达/刷新路由 | 教练导航「月报」或记课页「查看月报」 | test_monthly_report.py、test_stage_frontend.py、真实Chrome月报核对 |

所有新增接口采用既有同域Session + CSRF、角色/对象权限与 `{error:{code,message,fields?}}`。详细接口和取舍见 `docs/superpowers/specs/2026-10-16-five-stages-design.md`；五份原始需求保存于 `docs/requirements/`。

## 关键口径与取舍

- 购买/消课旧流水与主键不变。新增消耗批次归属；新消耗先使用即将到期批次，无期限批次最后使用。历史未关联的消耗按旧购买FIFO抵扣，不写入伪造交易。
- remaining 仍为购买减消耗；expired 为过期但未消耗的批次余量；reserved 是活跃预约实际占用的有效课时；available = remaining - reserved - expired。预约持有期间课包过期，预约与名额仍保留，但失效课时不再计有效预占，且不能完课消课；需录入有效续课。直接补记过去日期同样检查操作当天有效性。
- 改期限定原课包类型。成功后再在同一事务中递补原课次；任何目标校验失败都会恢复原预约。候补不预占课时；递补才预占，开始后不再递补。候补退出是状态幂等；已递补的预约须走预约取消/改期流程。
- 批次限1–100项，每批学员/key不重复。已成功项可跨批重试返回原记录；整批key不得用于不同内容。日常简单批量页支持每人文字记录；API同时支持exercises。
- 报表预约计数按开课月份，直接记课按实际上课日期，递补按实际转正时间。过期流失按到期日次日归属月份，仅统计未消耗课时，未来尚未过期不计入。预约状态计数保留真实历史，包括整堂取消前已处理的免消课缺席；到课率分母单独排除整堂取消，只含已处理到课与缺席。直接记课单列。
- 不添加后台定时器：有效期在查询/写入时按日期判断，递补在释放事务内同步执行，避免单实例之外再维护工作进程。
- 保持同镜像交付，镜像运行期无Node。当前目录没有Git元数据，未创建提交或更改公共分支。未改动本地实例数据库和服务器，未执行线上发布。

## 数据升级

新增迁移 `0003_creditentry_expires_on_creditentry_purchase`、`0004_lessonbatch_booking_rescheduled_from`、`0005_waitlist`，只增加可空字段及新表。旧购买expires_on默认null。原有迁移测试只调整finally恢复到最新迁移，原有断言全部保留。

正式升级前使用原有backup_db备份，在独立副本运行迁移及测试；不要覆盖现有data、.env或实例密钥。快照不含数据库、依赖和编译结果：先使用现有依赖环境构建前端，再运行迁移/collectstatic，或按README构建镜像。运行新功能后不要直接降级到不认识新账本归属和候补表的旧版本；先在备份副本验证恢复方案。

## 实际验证结果

环境：Python 3.12.12、Node 24.18.0，使用现有.venv及frontend/node_modules，无安装新包。

| 实际命令（项目根目录） | 结果 |
|---|---|
| `.\.venv\Scripts\python.exe manage.py collectstatic --noinput` | 成功 |
| `.\.venv\Scripts\python.exe manage.py test --noinput` | **151项通过**，含原有116项；真实文件SQLite多线程并发及迁移测试通过 |
| `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` | No changes detected |
| `.\.venv\Scripts\python.exe manage.py check` | 0 issues |
| `npm --prefix frontend test` | **3项通过** |
| `npm --prefix frontend run build` | vue-tsc类型检查及Vite构建通过，105 modules |
| `.\.venv\Scripts\python.exe tools/verify_five_stages.py` | 隔离临时数据库 + 真实Chrome，候补→取消→递补→改期→续课→批量错误/成功→月报→到期提醒全部通过，8张390/1280宽截图，无横向溢出 |
| `impeccable.cmd detect --json <本轮14个UI目标>` | `[]`，无机械规则问题；已目视检查移动报表、到期提醒和桌面队列 |
| `python tools/package_snapshot.py` | ZIP清单、源码SHA256逐文件一致性及排除项校验通过；详见交付清单 |

浏览器验收脚本使用已安装Chrome与Python标准库，会自行创建、迁移及销毁临时数据和独立浏览器，不读取真实账号密码，也不访问远端。截图在 `artifacts/five-stages/`，不打入源码压缩包。

## 未完成项与范围说明

五份需求中明确列出的开发功能和自验证命令已完成。五份文件均引用《契约附件》，但本次输入及项目中未找到该附件；本次按明确API与现有工程约定实现。若后续补充附件，需要再核对其额外约束。本次交付为源码快照，未包含未被要求的线上部署。
