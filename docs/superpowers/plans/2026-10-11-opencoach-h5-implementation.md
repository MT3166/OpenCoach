# OpenCoach H5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 用户要求主代理执行代码修改；子代理仅做独立核验。已授权开发和测试部署，直接执行，不再请求执行方式确认。

**Goal:** 交付可登录、预约、消课、记录训练和点评的真实 H5，并部署到用户服务器供演示。

**Architecture:** Django 单体应用，独立 SQLite 数据库；模板与原生 CSS/JavaScript 构建手机优先的界面。业务写入使用 IMMEDIATE 事务、唯一操作标识与对象权限；Docker Compose 独立部署。

**Tech Stack:** Python 3.12、Django 5.2.x、WhiteNoise 6.x、Linux Gunicorn 23.x、SQLite、Docker Compose。

**Spec:** `docs/superpowers/specs/2026-10-11-opencoach-h5-design.md`

## Global Constraints

- 每教练一个部署与数据目录；首个目录 `/home/mt/opencoach-test`，端口 8001。
- 预约预占 1 次对应课时，完课消耗 1 次；私教和小班课包分别管理。
- 自行取消的边界为开课前至少 12 小时；确认完课或缺席仅在开课后。
- 教练与学员两个真实账号角色；学员只能访问自己的记录，邀请有效期 7 天且一次使用。
- SQLite IMMEDIATE、WAL、20 秒忙等待；并发测试使用文件数据库。
- 依赖仅安装到项目虚拟环境或独立镜像；安装与部署已获用户批准。
- 当前无 Git 仓库，不初始化、不提交；工作目录目前只有项目记忆和规格，直接在此开发。
- SSH 密码只从临时输入读取，不保存到任何文件或 MEMORY。

## File Map

- `manage.py`、`opencoach/settings.py`、`opencoach/urls.py`、`opencoach/wsgi.py`：应用入口及配置。
- `coaching/models.py`：学员、邀请、课程、预约、课时流水、课上记录、计划及提交；动作数组作为 JSON 字段保存，避免为固定表单建立额外 CRUD。
- `coaching/accounts.py`：邀请创建、重发和注册。
- `coaching/booking.py`：排课、预约、余额、取消、完课和缺席业务。
- `coaching/training.py`：动作校验、记录、计划、提交和反馈。
- `coaching/forms.py`、`coaching/views.py`、`coaching/urls.py`：输入表单、角色权限与页面数据。
- `coaching/tests/`：账户、课时并发、训练权限及完整页面流程。
- `templates/`、`static/app.css`、`static/app.js`：手机与电脑界面。
- `coaching/management/commands/seed_demo.py`、`backup_db.py`：可重复初始化及数据库备份。
- `Dockerfile`、`compose.yaml`、`requirements.txt`、`.env.example`、`.gitignore`、`README.md`：依赖、部署和演示说明。
- `tools/remote.py`：主机指纹校验、临时密码输入、定向上传及部署命令执行，不含凭据。

## Task 1: 账号与邀请

**Files:** 项目入口配置、models.py、accounts.py、tests/test_accounts.py。

**Interfaces:**
- `create_student(name: str) -> Student`
- `issue_invite(student: Student) -> str`
- `accept_invite(token: str, username: str, password: str) -> User`
- `DomainError(message: str)`：业务校验异常，视图转换为表单提示。

- [x] 安装已批准依赖到 `.venv`，运行 `python -m django --version`，锁定实际补丁版本。
- [x] 写邀请一次性使用、过期和重发作废测试；用 `assertRaises(DomainError)` 验证旧令牌不能创建新用户。
- [x] 创建配置、数据表和仅抛出业务未实现错误的服务入口，运行 `.venv\Scripts\python manage.py test coaching.tests.test_accounts`，确认正常邀请注册测试失败。
- [x] 实现事务内校验、摘要令牌、密码验证与学员绑定：

```python
with transaction.atomic():
    invitation = Invite.objects.get(token_hash=sha256(token.encode()).hexdigest())
    if invitation.used_at or invitation.expires_at <= timezone.now():
        raise DomainError('邀请已失效')
    user = User.objects.create_user(username=username, password=password)
    invitation.student.user = user
    invitation.student.save(update_fields=['user'])
    invitation.used_at = timezone.now()
    invitation.save(update_fields=['used_at'])
```

- [x] 再运行账户测试，确认通过；记录阶段结果。

## Task 2: 排课、课时与事务

**Files:** booking.py、models.py、tests/test_booking.py、tests/test_concurrency.py。

**Interfaces:**
- `create_session(title, kind, start, end, location, capacity) -> Session`
- `add_credit(student, kind, units, operation_key) -> CreditEntry`
- `balances(student, kind) -> dict`：`remaining`、`reserved`、`available`。
- `reserve(student, session_id, operation_key) -> Booking`
- `cancel(booking_id, actor) -> Booking`
- `cancel_session(session_id, actor) -> Session`
- `finish(booking_id, actor, outcome) -> Booking`：outcome 为 completed/no_show_charged/no_show_waived。

- [x] 写预约前后余额的独立期望值测试：录入 2 次、预约 1 节后断言 `remaining=2, reserved=1, available=1`；取消后断言 `available=2`。
- [x] 写满员、时间冲突、12 小时边界、重复录入、重复完课、重新预约和缺席测试。
- [x] 保留服务入口但先抛出 DomainError，运行 booking 测试观察成功预约与扣课用例失败。
- [x] 实现事务与唯一约束，关键流程：

```python
with transaction.atomic():
    old = Booking.objects.filter(operation_key=operation_key).first()
    if old:
        return old
    session = Session.objects.get(pk=session_id)
    occupied = session.bookings.exclude(status='cancelled').count()
    if occupied >= session.capacity:
        raise DomainError('课程已满员')
    if balances(student, session.kind)['available'] < 1:
        raise DomainError('可约课时不足')
    return Booking.objects.create(student=student, session=session,
                                  operation_key=operation_key)
```

- [x] 使用两个线程、独立数据库连接和 Barrier 同时抢最后名额，断言一人成功；对同一学员剩余 1 次同时预约不同课程，断言只有一笔成功。
- [x] 运行 booking/concurrency 测试和此前账户测试，确认余额与流水一致。

## Task 3: 训练与指导

**Files:** training.py、tests/test_training.py、models.py。

**Interfaces:**
- `validate_exercises(items: list[dict]) -> list[dict]`
- `save_record(booking_id, actor, exercises, note) -> TrainingRecord`
- `create_plan(student, actor, title, due_date, exercises, note, booking=None) -> TrainingPlan`
- `save_submission(plan_id, actor, exercises, note, submit=False) -> Submission`
- `review_submission(submission_id, actor, feedback) -> Submission`

- [x] 写其他学员无法提交计划、学员不能写课上记录、正式提交后锁定、非正数组数拒绝、0 重量允许的测试。
- [x] 运行训练测试，确认未实现的成功提交与点评流程失败。
- [x] 实现权限和状态变更；动作字段使用 name/sets/reps/weight/duration，空数值保留为空，数值通过 Decimal/整数解析验证。

```python
if actor.is_staff or plan.student.user_id != actor.id:
    raise PermissionDenied
if submission.submitted_at:
    raise DomainError('已提交的训练记录不可修改')
submission.exercises = validate_exercises(exercises)
submission.note = note
if submit:
    submission.submitted_at = timezone.now()
submission.save()
```

- [x] 运行训练及既有测试，确认课上记录、计划、提交、反馈都属于指定学员。

## Task 4: H5 界面与端到端页面

**Files:** forms.py、views.py、urls.py、templates/、static/、tests/test_views.py。

**Interfaces:** `/login/`、`/logout/`、`/invite/<token>/`、`/coach/`、`/coach/sessions/`、`/coach/students/`、`/coach/bookings/<id>/`、`/coach/plans/<id>/`、`/student/`、`/student/sessions/`、`/student/bookings/`、`/student/plans/<id>/`、`/health/`。

- [x] 写 Django Client 测试：教练创建学员与课程，学员预约后教练界面显示该报名；写另一个学员访问计划返回 404、学员访问教练端返回 403。
- [x] 运行页面测试，观察不存在对应页面的失败结果。
- [x] 实现 POST-redirect-GET、CSRF、角色装饰器、对象过滤、业务错误 messages，以及 UUID 操作标识的表单重试保留。
- [x] 使用 frontend-design 实现「温暖的运动工作室」方向：奶油白背景、深墨绿、橙色行动按钮、衬线标题和清晰正文；教练页为轻量工作台，学员页为每日训练手册。
- [x] 表单动作行支持增加、删除；隐藏 JSON 不是用户输入界面，服务端重新校验所有动作数据。
- [x] 运行页面及全套测试；用浏览器打开手机宽度和电脑页面，核验无横向溢出、错误提示可读、真实请求提交成功。

## Task 5: 初始化、备份与容器

**Files:** 管理命令、Dockerfile、compose.yaml、tools/remote.py、README.md、tests/test_commands.py。

- [x] 写初始化不会覆盖现有密码或重复加课、备份能由 sqlite3 打开并读取学员与预约的测试。
- [x] 运行命令测试观察管理命令缺失的失败结果。
- [x] 实现显式 `seed_demo`，随机生成初始账号凭据，仅首次创建时输出；二次运行不重置已有账号或追加相同课包。
- [x] 实现一致备份：

```python
with sqlite3.connect(source_path) as source:
    with sqlite3.connect(backup_path) as target:
        source.backup(target)
```

- [x] 配置 Docker 镜像、静态资源收集、两 worker 与两 thread；Compose 仅增加 opencoach-test 应用，映射 8001，挂载独立 data。
- [x] tools/remote.py 用 getpass 获取 SSH 密码，验证已知主机指纹；仅上传本项目需要文件，排除 .venv、.env、本地数据库和 MEMORY。
- [x] README 写明本地启动、测试、部署、备份恢复和教练/学员演示路线，执行管理命令测试。

## Task 6: 独立核验与部署验收

- [x] 使用 requesting-code-review 派出只读探子核验权限和事务；主代理立即等待终态，按 file:line 修改问题并重跑受影响测试。
- [x] 运行 `.venv\Scripts\python manage.py test`、`manage.py check`、`manage.py makemigrations --check --dry-run`、静态资源收集。
- [x] 重新确认服务器 8001 和目标目录，将项目上传到独立目录并创建随机应用密钥；拉取基础镜像、构建并启动 Compose 应用。
- [x] 执行 migrate 和 seed_demo，检查 health、容器状态及应用日志，从外部 HTTP 请求验证可达。
- [x] 教练与学员分别登录，以真实 HTTP/浏览器提交完整预约和训练流程；重启容器，重新检查记录和余额仍存在。
- [x] 执行备份，复制到临时 SQLite 文件验证记录；保护原测试数据。
- [x] 保存两种角色的界面截图，使用 HAPI display_image 展示；更新 MEMORY 并提供入口、测试账号、验证结果及测试环境限制。

## Coverage Review

规格 1–3 对应任务 1、4；规格 4–5 对应任务 2；规格 6 对应任务 3；规格 7–8 对应任务 1–4；规格 9–10 对应任务 5–6；规格 11 对应各任务测试与任务 6 的实际验收。完整规格和依赖授权已获得，按本计划在当前会话执行。
