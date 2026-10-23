# 五阶段 Implementation Plan

**Goal:** 依次完成有效期、原子改期、批量记课、候补递补、月报，交付可验证累计源码快照。
**Architecture:** 现有域服务负责事务，DRF负责严格输入及权限，Vue复用既有页面。购买消耗批次归属用于到期与月报。
**Tech Stack:** Django5.2/DRF、SQLite WAL+IMMEDIATE、Vue3/TypeScript/Vite；Python3.12、Node>=24，无新依赖。
**Spec:** docs/superpowers/specs/2026-10-16-five-stages-design.md

主代理在当前会话实施全部代码；探子仅只读核验。每步先新增失败测试，再实现并运行对应测试。当前目录无Git，不提交。原有测试不为通过而放宽；仅必要时将迁移测试恢复到实际最新迁移，保证测试后数据库完整。

- [x] 有效期：coaching/credits.py集中购买剩余/预占分配、booking.py及lessons.py使用有效课时；models/migrations增加expires_on与purchase关联；API余额和流水接线。验证到期当日/次日、旧流水、预占保护、两类课包、真实增量迁移。
- [x] 改期：Booking.rescheduled_from及双方API；事务取消后reserve，幂等校验与失败回滚。验证12小时、越权、同类型、冲突/满员、无有效课时及重试。
- [x] 批量：LessonBatch记录整批载荷及逐项结果；输入验证与整个原子事务。验证中途失败无残留、逐项旧记录重用、重复key意图冲突及未来日期。
- [x] 候补：Waitlist模型、服务/API，取消与改期触发FIFO；整堂取消停止递补。验证跳过过期/冲突、退出、权限、同队列并发递补、并发最后有效课时。
- [x] 月报：coaching/reports.py、API、严格月份解析；验证上海跨月边界、整堂取消率、空月、直接记课及过期/递补。
- [x] 前端：类型、钱包提醒、续课到期字段、共享改期表单、双方候补入口、批量记课页、月报页及导航。沿用useResource/useAction和意图UUID，typecheck/build及浏览器真实流程检查。
- [x] 最终审计：全部测试/迁移检查/构建、独立只读复核，修复发现后重验；README/累计变更说明、标准库源码快照打包及排除项检查；moss-mem交接。
