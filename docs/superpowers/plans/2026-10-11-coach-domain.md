# OpenCoach 域名 HTTPS 接入计划

> 主代理按 executing-plans 在本会话执行；代码与最终验收由主代理处理，子代理仅用于必要的只读探索。

**Goal:** 使用用户已绑定的 https://coach.qtedu.ac.cn/ 完成迁移交付，应用内部端口无需云侧放行。

**Architecture:** 复用新机现有 host 网络 Caddy，增加单独站点块，反代到回环地址 127.0.0.1:8001。Django 只信任这条受限反代入口的协议头，配置域名允许列表、HTTPS CSRF 来源与 Secure Cookie。Caddy 为新域名单独管理公网证书；原商城路由保持原文。

**Tech Stack:** 已有 Django、SQLite、Docker Compose、Caddy v2.10.2，无新增依赖。

**Spec:** 用户提供 coach.qtedu.ac.cn 并要求使用域名；沿用已批准的 H5 业务规格及迁移后的账号与数据。

## 执行与验证

- [x] 核查 DNS、Caddy 挂载和原配置。服务器解析域名为 101.201.244.115；共享配置为 /opt/qidu-mall-h5/current/Caddyfile，实际目录是 releases/productization-5bb5782；原配置仅包含 mall.qtedu.ac.cn。
- [x] 修改部署配置测试，要求 coach.qtedu.ac.cn、HTTPS CSRF 及 Secure Cookie；增加真实代理请求下邀请链接使用 HTTPS 的回归验证，先确认失败。
- [x] 修改 tools/deploy_support.py、tools/remote.py、.env.example、tools/smoke.py，改为域名入口；compose.yaml 绑定 127.0.0.1:8001；opencoach/settings.py 配置 SECURE_PROXY_SSL_HEADER。
- [x] 新增项目 Caddyfile：`coach.qtedu.ac.cn { reverse_proxy 127.0.0.1:8001 }`，上传清单包含该文件。跑 Windows 全套测试、系统和迁移检查。
- [x] 备份原共享 Caddyfile 和实例 .env 至本实例 data/backups（不输出密钥）；更新 .env，保留密钥及业务数据；构建并重新创建应用容器，验证仅回环监听。
- [x] 保留共享配置原文，追加项目 Caddyfile 站点块；先验证候选配置，写回原挂载文件的同一 inode，再热加载。失败则恢复原配置；记录已有商城健康和 HTTP 响应。
- [x] 验证公网受信任证书、HTTP 跳转 HTTPS、登录页与静态资源、原四账号登录、CSRF 表单、Secure Cookie、余额、预约、训练和点评、权限；通过代理回归测试验证 HTTPS 邀请链接。
- [x] 在新容器跑 Linux 全套测试、备份恢复、重启持久化并再次验证域名；核查商城原服务仍正常。
- [x] 更新 README、迁移验收、MEMORY；记录共享 Caddy 配置被商城部署使用，未来发版必须保留 OpenCoach 站点块。公网验收完成后结束迁移任务。


