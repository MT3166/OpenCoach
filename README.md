# OpenCoach

面向健身私教、瑜伽与普拉提自由教练的 H5。一个部署服务一位教练，日常围绕「记课」和「学员」：直接记一节课、确认已有预约、核对课时、录入续课、选填一句训练记录。学员可以约课、查看自己的课包与历史；课后练习和点评按需使用。

前端为 Vue 3 + TypeScript + Vite + Vue Router，后端为 Django + DRF JSON API。使用同域 Session、CSRF 与 SQLite，前端静态文件和 Python API 在同一镜像交付，运行阶段无需 Node。

## 本地启动（Windows PowerShell）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix frontend ci --include=dev
npm --prefix frontend run build
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
$env:OPENCOACH_FRONTEND_ENABLED='1'
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

使用现有 Node 24。开发时也可另开终端运行 `npm --prefix frontend run dev`，从 `http://127.0.0.1:5173/` 访问；Vite 将 API 代理到 Django 的8000端口，保持同域Cookie与CSRF。

空实例用 `manage.py createsuperuser` 显式创建教练；学员从邀请加入。需要独立演示样本时再手动运行 `manage.py seed_demo`，该命令首次输出随机初始密码，重复运行不重置已有账号和课时。部署不会自动执行它，密码不记录在仓库。

本地数据库位于 `data/db.sqlite3`，测试使用独立的 `data/test.sqlite3`。本地开发默认 DEBUG，服务器通过环境变量关闭。

## 验证

```powershell
.\.venv\Scripts\python.exe manage.py test --noinput
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
npm --prefix frontend test
npm --prefix frontend run build
```

Windows/Linux 116项后端测试覆盖 API、CSRF、角色与对象权限、旧业务、增量迁移、直接记课与预约争抢最后一次课时；3项 Node 原生测试覆盖在途请求失效、CSRF错误和退出失败后的私有数据隐藏。并发测试使用文件SQLite及独立连接，写事务为 IMMEDIATE。

不同教练实例的登录与 CSRF Cookie 名称从各自独立应用密钥派生，支持同一 IP 不同端口同时登录。训练重量最多保留两位小数，支持 0.25 kg 等常见增量。

## 测试服务器

- 目标目录：`/root/opencoach-test`
- Docker Compose 项目：`opencoach-test`
- 访问入口：`https://coach.qtedu.ac.cn/`
- 应用内部入口：`127.0.0.1:8001`，通过现有 Caddy 反向代理。
- 独立数据：`/root/opencoach-test/data/db.sqlite3`
- 应用配置：该目录的 `.env`，密钥首次部署随机生成。

2026-10-11 已从误选的旧服务器迁移，原有账号密码和业务数据保留，旧环境已撤销。`coach.qtedu.ac.cn` 的公网 HTTPS、四账号登录、课时与训练数据、权限和重启已验收，Windows/Linux 72 项测试通过。

迁移最终备份为 `data/backups/retired-old-20261011-133314.sqlite3`。完整核验记录见 `docs/superpowers/reviews/2026-10-11-server-migration.md`。

2026-10-12已部署正式版 Vue H5 和 `/api/v1/`，直接记课、续课、预约、训练与指导完成HTTPS真实流程验收。`0002_direct_lesson` 增量迁移保留原账号、关系与业务内容。新镜像 `67a95f51784d`；本轮记录见 `docs/superpowers/reviews/2026-10-11-formal-h5-acceptance.md`。

当前机器的系统 Python 已有 Paramiko，可运行项目专用部署工具。该工具只从隐藏的临时输入获取 SSH 密码并校验已知主机指纹，上传时排除本地数据库、虚拟环境、MEMORY 和真实 `.env`。

重复部署会验证已有 `.env` 的端口、DEBUG、密钥和数据路径。源码清单只清理上一次由工具上传、当前版本已删除的文件，保留未跟踪文件、实例配置与数据；源码归档不进入镜像。

```powershell
npm --prefix frontend ci --include=dev
npm --prefix frontend run build
python tools/remote.py deploy --frontend 1
```

当前服务器若直接下载依赖过慢，可以仅在构建时使用机器已有的 127.0.0.1:7890 代理（不修改系统或代理配置）：

```powershell
python tools/remote.py deploy --frontend 1 --build-proxy http://127.0.0.1:7890
```

服务器内维护：

```sh
cd /root/opencoach-test
docker compose -p opencoach-test ps
docker compose -p opencoach-test logs --tail=60 web
docker compose -p opencoach-test restart web
docker compose -p opencoach-test exec -T web python manage.py backup_db --output /app/data/backups/manual-snapshot.sqlite3
```

备份命令使用 SQLite backup 接口生成一致快照，拒绝覆盖已存在的目标。恢复时先把备份复制到独立实例的 `data/db.sqlite3`，验证内容后再进行正式实例的替换。

发布先保留当前镜像、创建一致备份，在 `data/preflight-<时间戳>/` 独立副本上验证新迁移、静态入口、API及旧镜像账目兼容；通过后生成最终切换备份并启动新服务。启动/健康失败会恢复已验证兼容的前一镜像与前端开关，数据库不降级。副本只含预检数据，不进入公网业务库。保留备份、旧镜像和副本，清理由后续维护明确执行。

`OPENCOACH_FRONTEND_ENABLED=0` 可在当前新后端保留旧HTML入口作前端回退；新API仍可查直接课程。运行新账目后切回旧镜像必须先在恢复副本确认兼容，不能删除直接消课流水。当前初始旧镜像的兼容性已在真实数据副本验证。

公网实际流程和移动视口工具：

```powershell
python tools/verify_remote.py
python tools/smoke_h5.py --origin-ip 101.201.244.115
python tools/preview.py --url https://coach.qtedu.ac.cn/student/ --username xiaoyu --output artifacts/student-mobile.png --width 390 --height 844 --origin-ip 101.201.244.115
```

HTTP验收使用已有系统curl、正常TLS证书及域名验证；密码经隐藏输入及stdin临时传递，不进命令行或配置。浏览器使用已有Chrome与独立临时视口。`smoke_h5`只为明确命名的发布验收学员写测试数据，不改既有学员账目。

域名入口使用 HTTPS，开启 `DJANGO_SECURE_COOKIES=1`，允许主机和 CSRF 来源对应 `coach.qtedu.ac.cn`。Django 信任 Caddy 的协议头，应用端口只在本机监听；新增教练实例也应保持这项入口约束。

本项目 `Caddyfile` 定义教练站路由。当前 Caddy 由 `qidu-mall-h5-web` 容器运行，读取共享文件 `/opt/qidu-mall-h5/current/Caddyfile`；部署时将本项目站点块加入共享文件并热加载。后续更新商城服务或替换该文件时，需要保留教练站路由。Caddy 使用已有持久化目录自动维护证书。

## 演示路线

1. 教练进入「记课」：直接选学员，确认课包类型与日期，选填一句记录，点击「记一节课 · 扣1次」。无需提前排课，允许补记过去日期。
2. 已有对应预约时使用快捷确认；完课后补写文字不重复消课。小班逐位学员处理。
3. 学员档案核对两类课包与流水，录入实际续课，查看统一上课历史。
4. 学员约未来课程，在「我的预约」查看或取消；教练看到同一报名和预占结果。
5. 学员在「记录」回看实际上课与教练总结，按需使用已有课后练习及点评。
6. 查本月预约到课/缺席/取消/待确认与直接记课次数。预约到课率只按已处理预约统计，直接记课不虚构应到分母。
7. 重启后核对持久化；当前「发布验收学员」是本轮测试样本，不代表真实客户。

私教和小班课时独立，预约时预占，完课后消课。自行取消须距开课至少 12 小时，缺席是否消课由教练决定。

## 独立教练实例

复用同一代码，将每位教练的目录、Compose 项目名、端口、应用密钥和 `data` 分别配置；设置 `COACH_NAME`、`BRAND_NAME`。各实例不共享账号和数据库。首版未接入在线支付、视频上传或即时聊天。

设计与实施记录位于 `docs/superpowers/`。

## 2026-10-16 五阶段扩展

已增加课包有效期及到期提醒、双方原子改期、批量记课、候补自动递补与月度经营报表。教练从记课页进入批量记课，从导航进入月报；学员从约课加入候补，在我的预约查看、退出或改期。购买到期日当天有效，旧购买默认永久有效。余额分为有效预占、可用与已过期课时。

累计改动、统计口径、迁移注意事项和实际验证结果见 [CHANGELOG-five-stages.md](CHANGELOG-five-stages.md)。五份原始需求保存在 `docs/requirements/`，新增迁移为0003–0005。

本地隔离浏览器验收（需已有Chrome和已构建前端，自动使用临时数据库，不接触现有实例）：

```powershell
.\.venv\Scripts\python.exe tools/verify_five_stages.py
```

源码交付打包：`python tools/package_snapshot.py`，输出至 `artifacts/OpenCoach-five-stages-source.zip`，含逐文件SHA256清单并自动核验排除项；拒绝覆盖同名已有包。
