# OpenCoach 测试服务器迁移验收

- 日期：2026-10-11。
- 状态：新服务器迁移和域名 HTTPS 公网验收通过，旧部署已撤销。
- 新入口：`https://coach.qtedu.ac.cn/`，公网通过 80/443 访问；应用仅绑定本机 `127.0.0.1:8001`。
- 新实例：`/root/opencoach-test`，Compose 项目 `opencoach-test`，容器 `opencoach-test-web-1`。
- 新 SSH 主机指纹：`ssh-ed25519 SHA256:YBehY7BrQ9chKp3XfnXLNA4fij9Z0KIvF6agoDpSf08`。
- 用户明确授权服务器迁移及旧部署撤销；连接密码未保存至代码、文档或配置。

## 数据保留

沿用原有 `.env` 的独立应用密钥、品牌与教练配置，只替换允许主机和 CSRF 来源中的 IP。教练及学员原账号、密码散列、课包、预约、动作记录、计划、提交和反馈均保留，不重新初始化演示数据。

- 一致数据库备份上传后，两端 SHA256 均为 `215bd268ab7f62bae2f199036f0f114637d46881960ff3b83703100b399f8316`。
- SQLite `integrity_check` 和 `foreign_key_check` 通过。
- 停止旧应用写入后，再生成最终备份，并与新实例一致快照逐表比较；排除登录会话及 `auth_user.last_login`，其余账号字段和完整业务内容完全一致。
- 最终逻辑摘要：`fb83a5b4332a10dfd3ce6d38e429c9702a033b20b11bc217c8508480c928f19b`。
- 最终备份：新机 `data/backups/retired-old-20261011-133314.sqlite3`。
- 旧完整 SQLite 备份均复制至新机 `data/backups`；空 WAL 及其共享内存索引不作为独立备份复制。
- 新数据目录及迁移数据库属主为 `1000:1000`，与应用容器用户一致。

## 新实例验证

- Windows 72 项测试通过；系统检查通过，迁移检查无模型变更。
- 新 Linux 容器 72 项测试通过，包含并发约课和消课、权限、训练、HTTPS 代理邀请链接及部署配置校验。
- 备份恢复到独立数据库后，ORM 业务快照一致。
- 容器重启后，数据库及 ORM 业务快照一致，健康检查通过。
- 通过真实公网 HTTPS 验证登录页、静态资源和 CSRF 表单；`coach`、`xiaoyu`、`achen`、`yinuo` 均以原密码登录成功，Cookie 带 Secure，登录会话 Cookie 带 HttpOnly。
- 公网 HTTPS 读取课包、预约、训练记录及点评通过；学员访问教练页面返回 403，另一学员访问他人计划返回 404。
- 快照为 3 学员、6 预约、8 课时流水、3 训练记录、4 计划、3 提交；主学员私教剩余 10、预占 1、可约 9，小班剩余与可约均为 8。
- 新机原有 `qidu-mall-h5-web` 网站容器保持 healthy；共享 Caddy 配置保留原商城站点原文，仅追加教练域名站点块。商城首页 HTTPS 内容在配置前后 SHA256 相同。
- 从旧服务器的独立网络访问新教练域名健康检查成功，并以显式新机 IP/SNI 验证原商城 HTTPS 返回 200；旧机部署目录和 8001 监听再次确认不存在。
- HTTP 返回 308 并跳转至 `https://coach.qtedu.ac.cn/`。公网站点使用受信任的 Let's Encrypt 证书，SAN 对应 coach.qtedu.ac.cn，有效期至 2027-01-09；证书自动管理。
- 最终 Linux 备份恢复验收文件为 `data/backups/verified-20261011-152357.sqlite3`，重启后公网健康检查和登录页再次通过。
- 独立只读核验通过，未发现阻止交付的域名、代理信任边界、Cookie、CSRF 或部署源码保护问题。

镜像首次直接下载依赖过慢，仅对本次 `docker build --network=host` 提供服务器已有的 127.0.0.1:7890 HTTP/HTTPS 代理参数，锁定依赖版本不变，未安装额外软件或修改系统代理。

## 旧部署撤销

撤销前检查独立目录标记、Compose 容器和网络 labels、镜像 ID 及其他运行容器名单。仅移除 `opencoach-test-web-1`、`opencoach-test_default`、`opencoach-test-web:latest` 和 `/home/mt/opencoach-test`。

撤销后，旧机无 OpenCoach 项目容器，8001 无监听，部署目录不存在。其他五个原有容器的 ID 及运行名单一致，系统 Caddy 仍 active。未执行全局 Docker prune。

## 域名维护契约

用户提供已绑定到 101.201.244.115 的 `coach.qtedu.ac.cn` 后，公网入口改用 HTTPS 域名，原 8001 放行请求已被取代。部署工具、配置样例、校验和 HTTP 验收默认地址同步更新；应用端口仅供本机 Caddy 反代。

项目 `Caddyfile` 保存教练站点块。现有 Caddy 在 `qidu-mall-h5-web` 容器内，以 host 网络运行，读取 `/opt/qidu-mall-h5/current/Caddyfile`，本次实际文件为 `/opt/qidu-mall-h5/releases/productization-5bb5782/Caddyfile`。修改前配置备份位于 `data/backups/Caddyfile-before-coach-20261011-151748`，环境配置备份为 `data/backups/env-before-https-20261011-151748`（含应用密钥，保持 0600，勿公开）。配置先验证再原 inode 写入并热加载。

后续商城部署或替换共享 Caddyfile 时必须保留 OpenCoach 站点块。项目后续普通应用部署不修改共享 Caddyfile，也不重置现有实例密钥和数据。

工具策略拒绝删除本机临时目录 `C:\Users\honor\AppData\Local\Temp\opencoach-final-cutover-06efd_bf`，仅返回 `blocked by policy`；该目录保留一次迁移比对的临时数据库副本，不包含 SSH 密码。后续可在工具策略允许时清理，服务器撤销不受影响。
