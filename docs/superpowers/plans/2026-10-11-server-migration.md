# OpenCoach 测试服务器迁移计划

> 主代理按 executing-plans 在本会话执行；用户约定子代理仅只读探索与核验，代码和最终验证由主代理处理。

**Goal:** 将现有 OpenCoach 实例迁移到 101.201.244.115，保留账号及业务数据，撤销 192.3.233.180 的本项目部署。

**Architecture:** SQLite 一致备份和实例配置迁移，使用已有部署工具上传相同应用到独立目录。新环境验收后停止旧实例，比较停机后的最终数据库；存在新增数据时再次同步后验收，最后清理旧专用资源。

**Tech Stack:** Django、SQLite、Docker Compose、已有 Paramiko；不新增依赖。

**Spec:** 用户本轮服务器纠正指令；业务规格为 docs/superpowers/specs/2026-10-11-opencoach-h5-design.md。

## 约束

- 新 SSH 用户 root，旧用户 mt；密码只走隐藏临时输入，不入仓库或记忆。
- 保留已有账号、密码散列、应用密钥、账目、预约、训练及反馈。
- 不碰任一服务器其他服务；不执行 Docker 全局 prune。
- 部署目录需有本项目标记，数据挂载对 UID/GID 1000 可写。
- 不初始化 Git 或提交，不安装未批准的依赖。

## 执行与验证

- [x] SSH 只读核查两机：操作系统、运行工具、磁盘与内存、8001 端口、已有容器、目标目录标记；固定新主机指纹。
- [x] 修改 tools/remote.py 的 host/user/target/fingerprint、父目录和配置；修改 tools/deploy_support.py、.env.example、tools/smoke.py 的目标 IP；tools/verify_remote.py 使用新机已有网站健康检查；调整 coaching/tests/test_deploy_support.py 并确认新地址配置接受、旧配置拒绝。
- [x] 执行 `.\.venv\Scripts\python.exe manage.py test --noinput`、`check`、`makemigrations --check --dry-run`，69 项测试通过。
- [x] 旧实例执行一致备份；读回备份和 .env，仅在内存及临时目录转移。新 .env 仅替换 allowed-hosts 与 CSRF 中的旧 IP。
- [x] 上传新源码和数据库；为独立 data 设置 1000:1000 所有权。直接构建下载过慢，使用既有代理执行 `docker build --network=host` 后启动成功，不重置数据。
- [x] 新服务器全套测试、备份恢复和重启验证通过；SSH 通道 HTTP 登录与静态资源、四个实际账号、余额、训练和点评通过。
- [x] 用户提供 coach.qtedu.ac.cn 后改用域名 HTTPS 公网入口，验证实际 health、静态资源、四账号登录与训练课时数据通过；8001 仅本机监听，无需云侧放行。
- [x] 撤销影响范围先向用户列明；停旧 web 后做最终备份，比对账号和业务数据完全一致。因用户明确要求撤销误部署，在新实例内部验收完成后撤销旧环境；公网端口单独跟进。
- [x] 核查目录标记、Compose labels 和已记录镜像 ID 后，仅移除旧项目容器、专用网络、专用镜像及 /home/mt/opencoach-test。旧完整备份保留在新实例 data/backups。
- [x] 最终运行检查、域名公网验收和交接文档；迁移结果以域名 HTTPS 为最终交付，详见域名接入计划与迁移验收。
