# 五阶段版本上线验收

- 日期：2026-10-16，用户明确要求部署上线。
- 公网入口：https://coach.qtedu.ac.cn/ 。沿用现有服务器101.201.244.115、目录`/root/opencoach-test`和Compose项目`opencoach-test`。
- 新镜像：`sha256:1fe88e14d88ea44c75ad5573e4456fc0230a7cc7c5fb68edda83219ab466cef2`；容器`opencoach-test-web-1` healthy。
- SSH使用本机已有密钥，主机指纹核对既有固定值；未读取或重置账号密码，未修改共享Caddy或系统代理。

## 备份、迁移与切换

1. 前端重新执行`npm --prefix frontend run build`，vue-tsc与Vite通过，105 modules。上传190个项目文件；不上传本机数据库、依赖目录或真实.env。
2. 最初Compose构建直连依赖下载缓慢，确认构建进程仍运行且旧容器healthy后，仅停止该构建；改用既有`127.0.0.1:7890`构建代理，沿用已有依赖缓存完成。没有安装buildx或新依赖。
3. 保留旧镜像`sha256:67a95f51784d3cdd84a1247b476d5affbe8c756b33273f9de42f02e2eea90324`，标签`opencoach-test-web:retained-20261016T125815Z`。
4. 一致性备份`/root/opencoach-test/data/backups/before-formal-20261016T125815Z.sqlite3`。
5. 在`/root/opencoach-test/data/preflight-20261016T125815Z/`独立副本上运行0003–0005增量迁移、数据完整性与旧数据逐表对比、SPA/API预检，以及**151项Linux后端测试**，全部通过。测试用文件SQLite，未在业务库中运行测试或seed。
6. 旧镜像对该独立副本的读写兼容预检通过。此证明限定于本次切换前的已有业务数据；用户开始写入到期课包、批量和候补后，回退需重新评估，不能直接降级数据库。
7. 最终切换备份`/root/opencoach-test/data/backups/cutover-formal-20261016T125815Z.sqlite3`。随后替换容器并等待健康检查通过。
8. 切换后与最终备份逐表比较旧业务字段、账号及密码散列，全部相同；仅忽略账号last_login等原有比较规则允许的登录时间字段。旧字段逻辑摘要：`d347d9616c2045b2c78744b1a1e9b0eda4e31ea59ac65f8847a43205a5f46224`。

## 公网与运行时证据

- HTTPS正常证书/域名验证、指定现有源站访问`/health/`返回200及`{"status":"ok"}`。新容器healthy，原商城`qidu-mall-h5-web`亦healthy。
- 实际容器`showmigrations coaching`显示0001–0005全部已应用；`makemigrations --check --dry-run`返回No changes detected。
- SQLite integrity_check与foreign_key_check通过。
- 使用服务器创建、10分钟有效且验收后删除的教练/学员会话，验证公网已鉴权接口；未创建测试账号或业务记录，未更改既有密码。
- 教练月报GET返回七项统计和到课率；非法月份400；批量/改期非法输入400；缺少CSRF的批量POST返回403。
- 学员课包包含expired/expiring；候补列表正常；访问教练月报403；非法候补加入400、不存在的退出和改期对象404。
- 独立Chrome真实加载四个390×844页面：教练月报、批量记课、学员我的课包、我的预约（含候补列表）。页面无错误提示、无横向溢出；没有在公网执行扣课、改期或候补等业务写入。
- 只读验收前后全部coaching模型和账号摘要相同：`3fe069a62587c67d5cb504907c68cf600a5b79924bc6fab1bc6939a16713cbc5`。
- 当前数据：4学员、9课次、10预约、17课时流水、5课上记录、5计划、4提交、4直接记课、0批次、0候补、5账号。这是现有数据，并非虚构新功能使用量。
- 当前2026-10月报：预约到课5、缺席0、取消3、待确认2、直接记课4、候补转正0、过期流失0；预约到课率100%，分母5。

公开验收摘要与4张截图保存在`artifacts/five-stages-live/`。临时会话已清除，验收文件不包含会话令牌或凭据。现有账号、业务数据、实例密钥、品牌、域名和应用本机监听保持原配置。
