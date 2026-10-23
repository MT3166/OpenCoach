# OpenCoach 正式版 H5 迁移实施计划

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 用户约定主代理修改代码、取舍方案和执行最终验证；子代理只做只读探索或核验，不使用子代理编码流程。

**Goal:** 将现有教练与学员的完整业务迁移到 Vue 3 + Vite H5，通过 Django + DRF API 读取和修改真实数据，并在测试域名验收。

**Architecture:** 前端负责页面、导航和表单；Django Session、CSRF、权限及现有业务服务负责身份与数据一致性。每位教练独立实例，继续使用 SQLite；本地构建的前端静态文件与 Python API 一同装入现有应用镜像，由 Caddy 保持整站反代。

**Tech Stack:** Vue 3、TypeScript、Vue Router、Vite、Django 5.2.18、Django REST Framework、SQLite、WhiteNoise 6.12、Gunicorn 23、Docker Compose。

**Spec:** `docs/superpowers/specs/2026-10-11-formal-frontend-options.md`；业务规则来自 `docs/superpowers/specs/2026-10-11-opencoach-h5-design.md`，服务器现况以 `docs/superpowers/reviews/2026-10-11-server-migration.md` 为准。

**业务范围复核（2026-10-11）：** 用户已确认教练持续记课和管理学员为习惯目标，并批准直接记课与预约快捷确认；规则来自 `docs/superpowers/specs/2026-10-11-coach-interview-requirements.md` 第10节。新增任务5A，任务2–3、6–8及10补齐轻量入口与历史验收。出勤统计口径和课后作业首版取舍仍需单独收敛，技术方案及依赖授权继续有效。

## Global Constraints

- 状态：11项任务已开发并于2026-10-12部署验收；原步骤保留为设计记录，实际分拆与验证结果以 `docs/superpowers/reviews/2026-10-11-formal-h5-acceptance.md` 为准。
- 首发范围：H5 独立交付，小程序作为客户按需选择的后续客户端；技术方案不承诺具体微信平台费用。
- 保留要求：每教练独立部署，学员端优先展示教练姓名或品牌，现有账号与业务数据保留。
- H5 前端与 API 使用同一域名，继续使用 Django Session、HttpOnly/Secure Cookie 和 CSRF；登录、退出和业务写请求均校验 CSRF。
- 学员身份从登录会话推导；创建学员、发布课程、生成邀请和录入课包必须先检查教练权限。
- 学员访问他人对象返回 404；角色不允许返回 403；未登录 API 返回 JSON 401，不跳转 HTML 登录页。
- 数据库时间使用 UTC，时间响应为带时区 ISO 8601，界面按 Asia/Shanghai 显示。
- 复用 `coaching/accounts.py`、`coaching/booking.py`、`coaching/training.py`；保留 SQLite WAL、IMMEDIATE 写事务及 20 秒等待上限。任务5A追加直接记课模型和消课来源，保留旧字段与关系，使用增量迁移；不更换数据库。
- 已批准新增包：`vue`、`vue-router`、`typescript`、`vite`、`@vitejs/plugin-vue`、`vue-tsc`、`djangorestframework`。实施时选兼容稳定版本，Python 精确锁版本、npm 提交锁文件；不额外安装 UI、状态、HTTP 或测试库。
- 不默认加入 JWT、CORS、微信 SDK、Pinia、Axios、Redis 或 PostgreSQL。
- 当前目录没有 Git 仓库，不初始化 Git、不执行提交；每任务以验证记录和 moss-mem 状态替代提交步骤。
- 当前域名是测试环境：`https://coach.qtedu.ac.cn/`；普通应用发布不修改共享 Caddy，不碰已有商城。
- 实施顺序为任务 1–5、5A、6–10；任务 1–3 交付登录、邀请、品牌与两端首页，任务 4–8（含5A）交付业务，任务 9–10 交付同镜像和测试环境切换。
- 教练日常入口以记课和学员管理为主；文字/动作选填，不能要求先做目标计划或课后提交才记课。直接记课日期默认上海今天，可补记过去，未处理预约和已上课记录的来源清楚。
- 每任务实施前读即将修改的原文；UI 修改前使用 Impeccable 的 `reference/craft-floor.md`，沿用已确认产品与品牌约束。浏览器验收先一批手机和电脑，统一修复后最多一批确认。

---

## 执行结果（2026-10-12）

- [x] 任务1：API认证、CSRF与JSON错误。
- [x] 任务2：品牌、邀请和两个首页。
- [x] 任务3：Vue入口、登录与私有数据清理。
- [x] 任务4：学员档案、邀请与课包。
- [x] 任务5：排课、预约、取消与出勤。
- [x] 任务5A：独立记课、消课来源、混合历史和增量迁移。
- [x] 任务6：教练/学员课程与课包页面、直接记课入口。
- [x] 任务7：记录、计划、提交与点评API。
- [x] 任务8：轻量文字、按需动作及训练指导页面。
- [x] 任务9：SPA深链接、静态缓存和部署保护。
- [x] 任务10：测试发布、原数据保留、真实流程、备份恢复、重启及兼容回退预检。

以下详细步骤是原计划记录，不用于重复执行已交付的部署。测试合并、薄API调用层及已保留的按需课后指导见验收文档的实现取舍。

## 文件边界

| 文件 | 责任 |
| --- | --- |
| `coaching/api/common.py` | JSON 响应、异常映射、角色权限、CSRF 保护基类、严格数值字段、分页及查询参数校验 |
| `coaching/api/serializers.py` | 只读身份、品牌、钱包、课程、预约、计划和提交表示；不包含密码、邀请摘要或数据库配置 |
| `coaching/api/auth.py` | Session、登录、退出、邀请查询与注册；请求序列化类随本模块放置 |
| `coaching/api/dashboards.py` | 教练和学员首页的聚合查询 |
| `coaching/api/students.py` | 教练学员档案、邀请、课包；学员自身钱包与流水 |
| `coaching/api/sessions.py` | 课程、预约、取消、出勤处理；调用既有服务 |
| `coaching/models.py`、`coaching/migrations/0002_direct_lesson.py`、`coaching/lessons.py`、`coaching/api/lessons.py` | 独立直接记课、对应消课关系、幂等写入及归属查询 |
| `coaching/api/training.py` | 课上记录、课后计划、草稿、正式提交和点评 |
| `coaching/api/urls.py`、`coaching/api/__init__.py` | API 路由注册和包入口 |
| `opencoach/frontend.py` | 普通文件 SPA 入口、缓存策略和限定页面路由 |
| `frontend/package.json`、`package-lock.json`、`vite.config.ts`、`tsconfig.json`、`index.html` | 已批准前端依赖、开发代理、类型检查和静态构建 |
| `frontend/src/main.ts`、`App.vue`、`router.ts` | Vue 启动、路由和角色导航 |
| `frontend/src/api/types.ts`、`client.ts` | 与后端一致的类型、fetch、CSRF、错误和请求失效处理 |
| `frontend/src/api/auth.ts`、`booking.ts`、`training.ts` | 按业务组织的薄 API 调用函数，不复制服务端业务规则 |
| `frontend/src/state/session.ts` | 响应式身份、品牌与 CSRF；登录退出清理私有数据 |
| `frontend/src/pages/`、`components/`、`styles/` | 下列任务明确的页面、少量复用组件和样式 |
| `coaching/tests/api_helpers.py`、`test_api_*.py`、`test_frontend.py` | API 契约、权限、CSRF、业务贯通、SPA 边界测试 |
| `coaching/tests/test_lessons.py`、`test_api_lessons.py`、`test_lesson_migration.py` | 直接记课、混合历史、权限、并发和增量迁移兼容 |
| `tools/deploy_support.py`、`tools/remote.py`、`tools/verify_remote.py` | 源码与构建产物白名单、部署前检查和公网验收 |
| `Dockerfile`、`.dockerignore`、`opencoach/settings.py`、`opencoach/urls.py` | DRF、前端产物和应用入口接入 |
| `README.md`、`PRODUCT.md`、`.impeccable/live/config.json` | 启动、维护、交付现状与本地 Vue 设计入口 |

`templates/` 和既有 HTML 视图在迁移中保留，便于比较与回退；旧实现退出及删除另作明确清理任务，本计划不批量删除。

## 统一接口契约

### 响应与错误

```json
{"data":{"items":[],"pagination":{"page":1,"page_size":30,"total":0}}}
```

单对象响应直接放在 `data`。所有成功写请求返回当前服务端对象；预约和购买重试返回原对象及当前状态，不声称又完成了一次操作。创建返回 201，读取、更新及幂等重试返回 200；退出返回 200 的匿名会话结构。

```json
{"error":{"code":"validation_error","message":"请检查填写内容","fields":{"units":["购买次数必须是 1–10000 的整数"]}}}
```

| HTTP | `error.code` | 条件 |
| --- | --- | --- |
| 400 | `validation_error` / `invalid_json` | 字段或查询参数错误、JSON 不能解析 |
| 401 | `unauthenticated` / `invalid_credentials` | 会话失效、未登录、账号密码不匹配 |
| 403 | `forbidden` / `csrf_failed` | 角色不符、CSRF 拒绝 |
| 404 | `not_found` | 不存在的对象、他人对象、未知 API |
| 405 | `method_not_allowed` | 方法不受支持 |
| 409 | `domain_conflict` / `invitation_invalid` | 业务冲突、邀请失效；409 详情用现有业务提示 |
| 415 | `unsupported_media_type` | 非 JSON 业务写请求 |
| 503 | `temporarily_unavailable` | 已识别 SQLite locked 写竞争，可原操作重试 |

未知程序异常保持 500，记录在服务端，JSON 提示使用通用文本，不把堆栈或数据库错误暴露给客户端。不要把所有 `OperationalError` 都吞成可重试错误。现有 `DomainError` 没有细分代码，首版使用稳定的通用 `domain_conflict`，不按中文消息猜错误类型。

列表使用 `page`、`page_size`，默认 1、30，页大小 1–100；顺序固定并含主键作为次排序。日期 `day=YYYY-MM-DD`，类型 `kind=private|group`；非法筛选返回 400。跨过最后一页返回空数组并保留 `total`。

### 身份、品牌与首页类型

```ts
export type Role = 'coach' | 'student'
export type Kind = 'private' | 'group'
export type BookingStatus = 'booked' | 'completed' | 'cancelled'
  | 'no_show_charged' | 'no_show_waived'
export interface SessionState {
  user: { id: number; username: string; display_name: string; role: Role } | null
  brand: { display_name: string; coach_name: string }
  csrf_token: string
}
export interface Wallet {
  kind: Kind; label: string; remaining: number; reserved: number; available: number
}
export interface Exercise {
  name: string; sets: number | null; reps: number | null
  weight: string | null; duration: number | null
}
export interface Course {
  id: number; title: string; kind: Kind; start: string; end: string
  location: string; capacity: number; occupied: number; slots_left: number
  cancelled: boolean; my_booking_id: number | null
}
export interface BookingData {
  id: number; status: BookingStatus; session: Course; can_cancel: boolean
}
export interface PlanSummary {
  id: number; title: string; due_date: string
  status: 'pending' | 'draft' | 'submitted' | 'reviewed'
}
export interface LessonData {
  source: 'direct' | 'booking'; id: number
  student: { id: number; name: string }; kind: Kind; occurred_on: string
  exercises: Exercise[]; note: string
}
export interface CoachDashboard {
  today: string; student_count: number; booking_count: number
  sessions: Course[]; pending_count: number
  pending: { submission_id: number; plan_id: number; student_name: string; title: string }[]
  recorded_today?: number; recent_lessons?: LessonData[]
}
export interface StudentDashboard {
  today: string; student: { id: number; name: string }; wallets: Wallet[]
  upcoming: BookingData[]; plans: PlanSummary[]; completed_count: number
}
```

品牌 `display_name` 优先为实际 `BRAND_NAME`；空值或历史默认 `OpenCoach` 时回退 `COACH_NAME`。不改已有 `.env`。匿名仅返回公开品牌、`user:null` 与 CSRF，不返回学员和课程业务数据。

教练首页统计今日未取消课程与未取消报名，待点评为已正式提交且未点评的记录；`pending_count` 为完整数量，`pending` 至多 5 项。学员首页仅含自己未来或正在进行的 3 个有效预约、两类钱包、4 个未正式提交计划及已完课数。

### 业务接口与数据范围

| 方法与 `/api/v1/` 下的路径 | 请求或响应，服务与边界 |
| --- | --- |
| GET `session/` | `SessionState`；任何身份可读 |
| POST `auth/login/` | `{username,password}` → `SessionState`，登录后更新 CSRF；已登录拒绝直接切换身份 |
| POST `auth/logout/` | `{}` → 匿名 `SessionState`，校验 CSRF |
| GET `coach/dashboard/` | `CoachDashboard`；只允许教练 |
| GET `student/dashboard/` | `StudentDashboard`；只允许绑定档案的学员 |
| GET `invitations/{token}/` | 有效时 `{student_name,expires_at}`；失效 409，不返回 token_hash |
| POST `invitations/{token}/accept/` | `{username,password,password_confirm}` → 登录后的 `SessionState`；调用 `accept_invite(token,username,password)` |
| GET / POST `coach/students/` | `q` 搜索与分页 / `{name}` → `{id,name,registered}`；调用 `create_student(name)` |
| GET `coach/students/{id}/` | `{student:{id,name,registered},wallets}`；预约、计划、流水分别用分页接口 |
| POST `coach/students/{id}/invitations/` | `{}` → `{url,expires_at}`；调用 `issue_invite(student)`，URL 用 HTTPS `/invite/{token}/` |
| GET / POST `coach/students/{id}/credits/` | 流水分页 / `{kind,units,operation_key}` → `{entry,wallets}`；调用 `add_credit(student,kind,units,operation_key)` |
| GET `student/profile/` | `{student:{id,name},wallets}`；身份从会话推导 |
| GET `student/credits/` | 仅自己的流水分页，可按 `kind` 筛选 |
| GET / POST `coach/sessions/` | 课程分页、`day/kind` / `{title,kind,start,end,location,capacity}` → `Course`；调用 `create_session(...)` |
| GET `coach/sessions/{id}/` | `Course`；报名使用下面分页接口，不向学员开放报名名单 |
| GET `coach/sessions/{id}/bookings/` | 预约分页，教练表示附 `{student:{id,name}}` |
| POST `coach/sessions/{id}/cancel/` | `{}` → `Course`；调用 `cancel_session(id,actor)` |
| GET `student/sessions/` | 未开始、未取消课程分页，`day/kind`；仅附当前学员的 `my_booking_id`，不含其他学员 |
| GET / POST `student/bookings/` | 自己的预约分页 / `{session_id,operation_key}` → `BookingData`；调用 `reserve(request.student,session_id,key)` |
| GET `coach/bookings/` | 教练预约分页，可按 `student_id/day/kind/status` 筛选；status必须是BookingStatus之一 |
| GET `coach/bookings/{id}/` | `{booking,student,record}`；教练才可读取 |
| POST `coach/bookings/{id}/cancel/`、`student/bookings/{id}/cancel/` | `{}` → `BookingData`；调用 `cancel(id,actor)`；学员先按自己过滤对象 |
| POST `coach/bookings/{id}/finish/` | `{outcome}` → `BookingData`；三种完课/缺席结局，调用 `finish(id,actor,outcome)` |
| PUT `coach/bookings/{id}/record/` | `{exercises,note}` → 课上记录；调用 `save_record(id,actor,exercises,note)` |
| GET / POST `coach/plans/` | 计划分页，可按 `student_id` / `{student_id,booking_id:null或ID,title,due_date,exercises,note}` → 计划；调用 `create_plan(student,actor,...)` |
| GET `coach/plans/{id}/`、`student/plans/{id}/` | `{plan:{id,title,due_date,exercises,note,booking_id},submission:null或对象}`；学员必须是所属对象 |
| GET `student/records/`、`student/plans/` | 自己的课上记录 / 计划分页；记录含课程摘要，不含他人档案 |
| PUT `student/plans/{id}/submission/` | `{exercises,note,intent:'draft'或'submit'}` → 提交；调用 `save_submission(id,actor,exercises,note,submit=...)` |
| PUT `coach/submissions/{id}/feedback/` | `{feedback}` → 提交；调用 `review_submission(id,actor,feedback)` |

流水 `entry` 的字段为 `id,kind,entry_type,units,booking_id,created_at`；提交字段为 `id,exercises,note,submitted_at,feedback,reviewed_at,updated_at`。课上记录为 `id,booking_id,exercises,note,updated_at`；计划列表项可附教练可见的 `student:{id,name}`，学员列表不附他人信息。不要直接序列化完整 ORM 对象或任意关系。

任务5A后，流水表示增加 `direct_lesson_id`（旧流水为null），消课来源由booking或direct_lesson其中一个确定；直接记课和统一课程历史契约见任务5A。

## 任务 1：API 基础与 Session/CSRF 认证

**Files:** 新增 `coaching/api/{__init__,common,serializers,auth,urls}.py`、`coaching/tests/api_helpers.py`、`coaching/tests/test_api_auth.py`；修改 `requirements.txt`、`opencoach/settings.py`、`opencoach/urls.py`。

**Interfaces:** `success(data,status=200)`；`error(code,message,status,fields=None)`；`api_exception_handler(exc,context)`；`csrf_failure(request,reason='')`；`ProtectedAPIView`；`IsCoach`、`IsStudent`；`session_data(request)` 返回前述 `SessionState`。

- [ ] 核实 DRF 对 Django 5.2/Python 3.12 的兼容版本，将精确版本加入 `requirements.txt`，在现有 `.venv` 安装；记录实际版本及 `pip check` 结果。安装范围已获授权。
- [ ] 新增公共测试基类：`ApiTestCase(TestCase).setUp()` 创建 `self.coach`（active/staff）、`self.student=make_student('api-student',credits=3)`、`self.other=make_student('api-other')`、`self.course=make_session()`。非 CSRF 测试用 `Client.force_login`，密码登录测试单独创建明确密码的用户。
- [ ] 写下列严格 CSRF 测试，并增加无令牌登录/退出均 403、错误凭据 401、禁用账号不能登录用例；邀请与首页权限测试在任务2接入对应接口时补齐。

```python
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

class ApiAuthTests(TestCase):
    def test_login_rotates_csrf_and_returns_session(self):
        user = get_user_model().objects.create_user(
            username='api-coach', password='Exercise-74!', is_staff=True)
        client = Client(enforce_csrf_checks=True)
        before = client.get('/api/v1/session/').json()['data']['csrf_token']
        response = client.post('/api/v1/auth/login/',
            {'username': user.username, 'password': 'Exercise-74!'},
            content_type='application/json', HTTP_X_CSRFTOKEN=before)
        self.assertEqual(response.status_code, 200)
        after = response.json()['data']['csrf_token']
        self.assertEqual(response.json()['data']['user']['role'], 'coach')
        rejected = client.post('/api/v1/auth/logout/', {},
            content_type='application/json', HTTP_X_CSRFTOKEN=before)
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json()['error']['code'], 'csrf_failed')
        accepted = client.post('/api/v1/auth/logout/', {},
            content_type='application/json', HTTP_X_CSRFTOKEN=after)
        self.assertEqual(accepted.status_code, 200)
        self.assertIsNone(accepted.json()['data']['user'])
```

- [ ] 运行 `manage.py test coaching.tests.test_api_auth --noinput`，确认新接口不存在导致失败后再实现。
- [ ] 实现 JSON-only DRF 配置及权限类。用 Django `authenticate/auth_login/auth_logout/get_token`；不是 staff 且无 Student 绑定的账号不获学员角色。登录保留旧账号密码验证，不用注册密码规则拦截已有短密码。
- [ ] 为所有不安全 API 方法执行 CSRF，包括匿名登录和邀请注册；不要只依赖 DRF SessionAuthentication 对已登录身份的 CSRF 检查。基类采用下述 dispatch 包装，设置 `CSRF_FAILURE_VIEW` 为 `csrf_failure`，旧 HTML 请求仍调用 Django 默认错误页。

```python
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.views import APIView

@method_decorator(csrf_protect, name='dispatch')
class ProtectedAPIView(APIView):
    pass
```

- [ ] 异常处理器统一 Django `PermissionDenied/Http404`、DRF 验证/解析/认证异常、`DomainError` 和已识别的 locked 错误。DRF SessionAuthentication 默认可能将未登录映射为 403，要显式保证此契约中的 401。
- [ ] 注册 `/api/v1/` 及 `/api/` 末尾 JSON 404 路由，确保 DEBUG=True 时未知 API 也不会落进 Django HTML 调试页；对应角色类先做独立权限检查，任务2以真实首页接口验证401/403。
- [ ] 再跑新测试、`pip check`、`manage.py check`、既有 `test_accounts/test_instance`；验证真正拒绝的是 CSRF 或权限，而非错误的 404/405。记录实际结果到 moss-mem。

## 任务 2：品牌、邀请与两个首页 API

**Files:** 修改 `coaching/api/{auth,serializers,urls}.py`；新增 `coaching/api/dashboards.py`、`coaching/tests/test_api_dashboards.py`；扩展 `test_api_auth.py`。

**Interfaces:** 前述 7 个首阶段接口全部可用；首页返回 `CoachDashboard/StudentDashboard`；邀请开户返回新的 `SessionState`。

- [ ] 写测试：匿名品牌配置可读但不含学员；覆盖真实品牌优先、OpenCoach 默认回退教练姓名；邀请过期/用过/重发作废、密码确认失败、账号冲突、注册后登录且 CSRF 旋转；无令牌邀请注册403、学员访问教练接口403、匿名访问受保护首页401。
- [ ] 写首页对象范围测试：

```python
import uuid
from coaching import booking
from coaching.tests.api_helpers import ApiTestCase

class ApiDashboardTests(ApiTestCase):
    def test_student_dashboard_has_only_own_booking(self):
        item = booking.reserve(self.student, self.course.id, uuid.uuid4())
        self.client.force_login(self.student.user)
        data = self.client.get('/api/v1/student/dashboard/').json()['data']
        self.assertEqual([row['id'] for row in data['upcoming']], [item.id])
        private = next(row for row in data['wallets'] if row['kind'] == 'private')
        self.assertEqual((private['remaining'], private['reserved'], private['available']), (3, 1, 2))
        self.client.force_login(self.other.user)
        other = self.client.get('/api/v1/student/dashboard/').json()['data']
        self.assertEqual(other['upcoming'], [])
```

- [ ] 运行新测试确认失败；从现有视图提取查询意图，在新 API 模块内实现，无需搬动原 HTML 视图。钱包始终调用 `booking.balances`，`my_booking_id` 仅对当前身份生成。
- [ ] 邀请 GET 用令牌 SHA256 查有效邀请；POST 通过 `accept_invite` 执行一次性开户，并禁止已登录身份直接开户切换。用户名≤150、密码≥8、确认一致，再由现有密码校验器执行强度校验。
- [ ] 待点评查询 `submitted_at IS NOT NULL AND reviewed_at IS NULL`；预约报名数排除 cancelled，上海今日边界用 `timezone.localdate()`；ISO 时间和日期字段分别输出。
- [ ] 教练首页为后续「记一节课」主动作预留入口；任务5A后返回 `recorded_today` 与最多5条 `recent_lessons`，从已确认课程和直接记课汇总，不把待点评填报当成记课前置条件。
- [ ] 运行 `manage.py test coaching.tests.test_api_auth coaching.tests.test_api_dashboards --noinput`；核对两身份同一数据库结果、404/403/401、JSON 嵌套字段，不把明文密码或邀请摘要放入响应。更新 moss-mem。

## 任务 3：Vue 启动、登录邀请与两端首页

**Files:** 新增 `frontend/package.json`、`package-lock.json`、`index.html`、`vite.config.ts`、`tsconfig.json`、`src/main.ts`、`src/App.vue`、`src/router.ts`、`src/api/{types,client,auth}.ts`、`src/state/session.ts`、`src/components/{AppShell,WalletSummary,FormFeedback}.vue`、`src/pages/{LoginPage,InvitePage,CoachDashboard,StudentDashboard}.vue`、`src/styles/{tokens,app}.css`；更新 `.impeccable/live/config.json`。

**Interfaces:** `api<T>(path,init?:RequestInit):Promise<T>` 只允许 `/api/v1/` 路径；`ApiError` 含 `code/status/fields`；`session`、`loadSession()`、`login(username,password)`、`logout()`、`resetPrivateData()`；路由 `/login/`、`/invite/:token/`、`/coach/`、`/student/`。

- [ ] 安装已批准 6 个前端包并保留 npm lock；使用当前 Node 24.18.0，`engines.node` 声明 `>=24.0.0`。设置 scripts：`dev:vite --host 127.0.0.1`、`typecheck:vue-tsc --noEmit`、`build:npm run typecheck && vite build`。用 `npm ci` 验证 lock 可复现。
- [ ] Vite 使用下面构建边界，Django 保持 `127.0.0.1:8000`；开发期间从 Vite 进入，不改远程页面入口。

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()], base: '/',
  server: { proxy: {
    '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    '/health': { target: 'http://127.0.0.1:8000', changeOrigin: false },
  } },
  build: { outDir: 'dist', assetsDir: 'static/h5' },
})
```

- [ ] 先在浏览器记录尚未能完成的目标：真实账号登录、错密码字段提示、登录后首页、退出后返回登录、另一身份重新登录不显示旧数据。采用实际演示账号在本地数据库副本核验，不写凭据进源码。
- [ ] `client.ts` 用原生 fetch，`credentials:'same-origin'`；写请求加 JSON Content-Type 和当前 `csrf_token` 的 `X-CSRFToken`。解析 `data/error`；网络异常与非法 JSON 分别提示，不以非 2xx 当成功。默认不自动重试写请求。
- [ ] 使用 AbortController 和递增 generation 保护在途请求；页面卸载取消页面请求；登录、退出、401 时清理身份和私人页 refs，旧 generation 的结果不能写入界面。私有 AppShell 用身份/generation 作 key，刷新或窗口重新获焦点时核对身份；CSRF 403 保留表单、重取会话，由用户再提交。
- [ ] 用 `shallowRef` 和 `readonly` 管理会话。启动先 GET session，登录响应替换身份和 CSRF；路由角色校验在数据请求前执行，`next` 仅接受同站已注册路由，不接受任意 URL。`/` 根据会话去登录或所属首页。
- [ ] 页面实现 loading、空列表、字段错误、断网重试；登录表单设置 autocomplete，邀请表单双密码确认，首页与导航显示 API 品牌。保持既有手机日常操作与电脑管理层级，不新增整套 UI 库。
- [ ] 教练首页突出「记一节课」和学员入口；在任务5A与6接通直接记课之前，该动作不跳到不完整的表单，也不虚构成功记录。
- [ ] 本地 Impeccable Live 插入点改为 `frontend/index.html`，工具检查实际 CSP 后再记录，不把注入脚本带入部署产物。
- [ ] 运行 `npm --prefix frontend run build`；本地浏览器按上面的身份切换流程和手机/电脑各一次检查。通过后任务 1–3 构成首个可演示闭环，保留截图和问题记录并更新 moss-mem。

## 任务 4：学员档案、邀请与课包 API

**Files:** 新增 `coaching/api/students.py`、`coaching/tests/test_api_students.py`；修改 `common.py`、`serializers.py`、`urls.py`。

**Interfaces:** 学员、邀请、购买录入和个人课包接口见表；`StrictIntegerField` 拒绝 JSON boolean、浮点和数字字符串，仅收整数；`paginate(queryset,request,serialize)` 返回统一分页 data。

- [ ] 写非法购买与角色测试，先运行确认失败：

```python
import uuid
from coaching.models import CreditEntry
from coaching.tests.api_helpers import ApiTestCase

class ApiStudentTests(ApiTestCase):
    def test_boolean_purchase_does_not_add_credit(self):
        self.client.force_login(self.coach)
        before = CreditEntry.objects.count()
        response = self.client.post(
            f'/api/v1/coach/students/{self.student.id}/credits/',
            {'kind': 'private', 'units': True, 'operation_key': str(uuid.uuid4())},
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('units', response.json()['error']['fields'])
        self.assertEqual(CreditEntry.objects.count(), before)
```

- [ ] 添加同 UUID 同请求只录一笔、同 UUID 不同数量/学员冲突、units 0/10001、姓名空/超50、无教练权限不能创建/邀请/录入、自己的流水不含他人数据、分页和非法筛选测试。
- [ ] 输入严格校验后调用 `create_student/issue_invite/add_credit`；这些服务无 actor 参数，API 权限必须先执行。购买首次/重试的201/200判定与服务调用放在同一写事务内，不在事务外预查操作键。邀请链接用 `request.build_absolute_uri`，并验证 HTTPS 代理头正确。

```python
from rest_framework import serializers

class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            raise serializers.ValidationError('请填写整数')
        return super().to_internal_value(data)
```

- [ ] `units` 范围 1–10000，UUIDField 负责格式；钱包重新从服务端计算，流水按 `-created_at,-id`，学员查自己的 user 绑定档案而非客户端 student_id。
- [ ] 运行 `manage.py test coaching.tests.test_api_students coaching.tests.test_accounts coaching.tests.test_booking --noinput`，确认无新模型迁移。记录任务结果。

## 任务 5：排课、预约、取消和出勤 API

**Files:** 新增 `coaching/api/sessions.py`、`coaching/tests/test_api_booking.py`；修改 `serializers.py`、`urls.py`。

**Interfaces:** 课程/预约接口见表，出勤 `outcome` 必须为 `completed/no_show_charged/no_show_waived`；`BookingData` 的 `can_cancel` 由后端当前时间与12小时规则决定。

- [ ] 用 `ApiTestCase` 写预约重试与伪造身份测试并运行确认失败：

```python
import uuid
from coaching.models import Booking
from coaching.tests.api_helpers import ApiTestCase

class ApiBookingTests(ApiTestCase):
    def test_reservation_retries_return_existing_booking(self):
        self.client.force_login(self.student.user)
        body = {'session_id': self.course.id, 'operation_key': str(uuid.uuid4())}
        first = self.client.post('/api/v1/student/bookings/', body,
            content_type='application/json')
        second = self.client.post('/api/v1/student/bookings/', body,
            content_type='application/json')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['data']['id'], second.json()['data']['id'])
        self.assertEqual(Booking.objects.filter(student=self.student).count(), 1)
```

- [ ] 添加拒绝额外 `student_id` 输入、跨学员取消404、私教 capacity≠1/小班<2/总上限100、JSON boolean容量、非法UUID、教练排课重叠、时间无时区、开课前出勤、重复完课/冲突结局、课程已有消课不能整堂取消、小班单人处理不影响其他人等 API 测试。服务已有边界用旧测试保留，新测试重点验证 API 接线与状态码。
- [ ] 请求序列化拒绝未约定字段，start/end 只接受带时区 ISO 字符串；教练排课仍交给 `create_session` 做事务冲突检查。列表 `occupied` 统计非取消预约，学员不返回报名名单。
- [ ] 所有预约/取消/完课调用现有服务，不拆出非事务的先查再写。201/200 通过同事务中检查操作键并调用服务区分首次与重试，避免在事务外预查制造竞争；返回重试后的真实终态。
- [ ] 使用上海时区转换，课程日期筛选采用 Django 时区查询；课程更新不提供隐式迁移已预约时间的 PATCH 操作。
- [ ] 运行 `manage.py test coaching.tests.test_api_booking coaching.tests.test_booking coaching.tests.test_concurrency --noinput`。并发测试使用现有文件 SQLite 独立连接，不能改为内存数据库或依赖不存在的行锁。

## 任务 5A：无需预约的直接记课、账目与统一已上课历史

**Files:** 修改 `coaching/models.py`、`coaching/api/{serializers,urls,dashboards}.py`；新增 `coaching/migrations/0002_direct_lesson.py`、`coaching/lessons.py`、`coaching/api/lessons.py`、`coaching/tests/{test_lessons,test_api_lessons,test_lesson_migration}.py`；扩展 `coaching/tests/test_concurrency.py`。

**Interfaces:** `record_direct_lesson(student,actor,kind,occurred_on,note,operation_key,exercises=None)` 返回 `DirectLesson`；`update_lesson_note(lesson_id,actor,note,exercises=None)` 返回当前记录；`lesson_history(student,page,page_size)` 返回统一分页，student为None仅由已通过教练权限的API调用。

```ts
export interface LessonData {
  source: 'direct' | 'booking'; id: number
  student: { id: number; name: string }; kind: Kind; occurred_on: string
  exercises: Exercise[]; note: string
}
export interface LessonResult { lesson: LessonData; wallets: Wallet[] }
```

`source + id` 为历史项的唯一身份。已上课历史包含直接记课及 completed 预约，缺席/取消仍在预约记录与流水显示，不伪装为已上课。

| 新接口 | 契约 |
| --- | --- |
| GET `/api/v1/coach/lessons/` | 统一已上课历史，可按student_id/day/kind筛选，分页；只允许教练 |
| POST `/api/v1/coach/lessons/` | `{student_id,kind,occurred_on,note,operation_key,exercises?:[]}` → `LessonResult`；仅创建直接记课；首次201、重试200 |
| GET / PATCH `/api/v1/coach/lessons/{id}/` | 指定直接记课对象 / `{note,exercises?:[]}`更新文字及可选动作 → `LessonResult`；不可改学员、日期、类型或再消课 |
| GET `/api/v1/student/lessons/` | 当前学员统一已上课历史与分页，身份从登录会话推导 |
| GET `/api/v1/student/lessons/{id}/` | 当前学员所属的直接记课对象 → `LessonResult`，他人对象404 |

来自预约的历史项沿用已有预约详情与record接口；此处 `{id}` 只指DirectLesson主键，不根据冲突数字猜来源。

- [ ] 写服务测试并运行 `manage.py test coaching.tests.test_lessons --noinput`，确认因为DirectLesson/新服务尚不存在而失败。用实际账目验证重复记课与预约预占：

```python
import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from coaching import booking, lessons
from coaching.errors import DomainError
from coaching.models import CreditEntry, DirectLesson
from coaching.tests.helpers import make_student, make_session

class DirectLessonTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create_user('lesson-coach', is_staff=True)
        self.student = make_student('lesson-student', credits=5)

    def test_retry_and_note_edit_only_charge_once(self):
        key = uuid.uuid4()
        payload = dict(student=self.student, actor=self.coach, kind='private',
            occurred_on=timezone.localdate(), note='', operation_key=key)
        first = lessons.record_direct_lesson(**payload)
        retry = lessons.record_direct_lesson(**payload)
        self.assertEqual(first.id, retry.id)
        lessons.update_lesson_note(first.id, self.coach, '深蹲和划船')
        self.assertEqual(DirectLesson.objects.count(), 1)
        self.assertEqual(CreditEntry.objects.filter(direct_lesson=first).count(), 1)
        self.assertEqual(booking.balances(self.student, 'private')['remaining'], 4)

    def test_direct_record_cannot_spend_reserved_credit(self):
        student = make_student('reserved-student', credits=1)
        booking.reserve(student, make_session().id, uuid.uuid4())
        with self.assertRaises(DomainError):
            lessons.record_direct_lesson(student, self.coach, 'private',
                timezone.localdate(), '', uuid.uuid4())
        self.assertFalse(DirectLesson.objects.filter(student=student).exists())
        self.assertEqual(booking.balances(student, 'private'),
            {'remaining': 1, 'reserved': 1, 'available': 0})
```

- [ ] 添加未绑定账号的档案可记课、未来日期拒绝、过去日期接受、同日多节新键可记录、同键异学员/类型/日期冲突、无教练权限拒绝、事务失败不留孤立记录或流水、最后1次课时的并发直接记课与直接记课/预约竞争测试。复用既有文件SQLite独立连接方法。
- [ ] 在models新增独立直接记课模型，保留真实日期；新增关系后替换消课检查约束。新表无旧数据回填要求，原列与账号关系原样保留：

```python
class DirectLesson(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='direct_lessons')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    occurred_on = models.DateField()
    exercises = models.JSONField(default=list, blank=True)
    note = models.TextField(blank=True)
    operation_key = models.UUIDField(unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-occurred_on', '-id']
```

`CreditEntry.direct_lesson` 为nullable OneToOneField，PROTECT、related_name='charge'。`valid_credit_entry` 的新条件如下，购买不能关联课程，消课只能关联一种真实来源：

```python
Q(entry_type='purchase', units__gt=0, booking__isnull=True,
  direct_lesson__isnull=True, operation_key__isnull=False) | (
    Q(entry_type='consume', units=1, operation_key__isnull=True) & (
        Q(booking__isnull=False, direct_lesson__isnull=True) |
        Q(booking__isnull=True, direct_lesson__isnull=False)
    )
)
```

- [ ] 实现服务：先 `require_coach(actor)`、校验kind/日期/文字和可选数组，再在同一IMMEDIATE写事务查operation_key、校验旧记录核心身份或返回旧结果、检查 `balances(student,kind)['available']>=1`、创建DirectLesson及一次CreditEntry consume。保存日期不得晚于上海今天；未提供动作或提供空数组可接受，非空数组仍用 `training.validate_exercises`，JSON布尔或非数组不能绕过。消费流水booking和operation_key为null，direct_lesson指向新记录。
- [ ] `update_lesson_note` 按教练权限、对象ID更新note与明确提供的exercises，未提供动作时保留原数组；不得创建消费流水。初次记录和文字更新均使用现有4000字符与数值精度规则，不新增余额缓存。
- [ ] 运行 `manage.py makemigrations coaching --name direct_lesson` 生成增量迁移并读取原文。用独立临时SQLite从0001迁移到0002，验证原用户、预约、购买/消课、训练和计划逐表内容一致，旧流水新增direct_lesson_id为null；执行完整业务/并发测试。运行 `makemigrations --check --dry-run` 确认已记录全部模型变更。测试迁移验证后恢复测试数据库最新状态。
- [ ] 写并运行API权限/CSRF/输入/分页失败测试，再实现新API。客户端不能指定actor或消费次数；GET学员接口按自己过滤。统一历史先以source/id/occurred_on组成规范化查询，用数据库union和 `-occurred_on,source,-id` 排序分页，再批量加载这一页的原对象与记录；不要加载全实例历史再在Python排序。时间按上海时区转日期，直接记录不生成时间段。
- [ ] 首页 `recorded_today` 汇总今天DirectLesson与completed预约；recent_lessons按统一规则取5条。普通私教和小班账目均使用原 `balances` 计算，它已汇总所有consume，无需另写一套余额函数。API流水增加direct_lesson_id及可读来源。
- [ ] 运行 `manage.py test coaching.tests.test_lessons coaching.tests.test_api_lessons coaching.tests.test_lesson_migration coaching.tests.test_booking coaching.tests.test_concurrency --noinput` 和check。验证ledger/source唯一约束和一笔余额竞争只一人成功；记录迁移范围与兼容边界到moss-mem。直接入口发现预约的引导由任务6落实，不自动依日期关联课程。

## 任务 6：教练排课、学员约课和课包页面

**Files:** 新增 `frontend/src/api/booking.ts`、`src/pages/{CoachSessions,CoachSession,CoachStudents,CoachStudent,CoachBooking,StudentSessions,StudentBookings,StudentProfile}.vue`、`src/components/SessionList.vue`；扩展 `types.ts`、`router.ts` 和样式。

直接记课补充：新增 `frontend/src/api/lessons.ts`、`src/pages/{CoachRecord,CoachLesson}.vue`；首页接入主动作，学员档案提供同一入口。

**Interfaces:** 页面 `/coach/sessions/`、`/coach/sessions/:id/`、`/coach/students/`、`/coach/students/:id/`、`/coach/bookings/:id/`、`/student/sessions/`、`/student/bookings/`、`/student/profile/`；使用任务 4–5 API。

新增 `/coach/lessons/new/` 直接记课、`/coach/lessons/:id/` 直接课程记录详情；调用任务5A API，`source=booking` 的历史项链接到原预约详情。

- [ ] 浏览器先记录未迁移流程：教练建学员/生成邀请/录入两类课包/排课，学员约课，教练见同一报名，取消释放、逐人完课一次。用本地独立数据进行写入验收，不改远程既有演示账目。
- [ ] `booking.ts` 以精确 payload 调用接口。创建购买或预约表单时生成 `crypto.randomUUID()`，同次网络错误重试沿用；成功或明确开始新操作才换 UUID。修改该次操作的学员、课程、类型或数量后新建操作键。

```ts
import type { BookingData } from './types'
import { api } from './client'

export async function reserveCourse(courseId: number, operationKey: string) {
  const payload = { session_id: courseId, operation_key: operationKey }
  return api<BookingData>('/api/v1/student/bookings/', {
    method: 'POST', body: JSON.stringify(payload),
  })
}
```

页面每次主动发起新预约时保存操作键，网络失败时保留它调用同一函数：

```ts
import { ref } from 'vue'
import { reserveCourse } from '../api/booking'

const booked = ref<Awaited<ReturnType<typeof reserveCourse>> | null>(null)
const pending = ref<{ courseId: number; operationKey: string } | null>(null)
async function submitReservation(courseId: number) {
  if (!pending.value || pending.value.courseId !== courseId) {
    pending.value = { courseId, operationKey: crypto.randomUUID() }
  }
  booked.value = await reserveCourse(pending.value.courseId, pending.value.operationKey)
  pending.value = null
}
```

- [ ] 教练页面实现课程名单分页、日期/类型筛选、创建课程、逐人预约详情和出勤；学员页面仅显示本人预约/余额/流水。全取消、确认完课和两种缺席需明确确认对象及课时结果，状态来自返回值。
- [ ] 数量输入严格转整数，私教容量固定1，日期输入先按上海时区生成带偏移ISO；前端帮助不能替代后端校验。购买录入和预约成功后重新拉取余额和列表，409 后刷新冲突相关信息。
- [ ] 对无幂等键的新建学员/排课禁止自动网络重试；请求结果不明先查询列表让用户核对，避免重复创建。
- [ ] 手机支持日期筛选、表单和邀请链接复制；复制失败提供可选择文本；分页不漏记录，pending 时禁用重复按钮，字段错误保留输入。
- [ ] 直接记课只要求学员、课包类型、日期；上海今天默认值清楚显示，只有一种课包可用时可预选。文字及动作选填，按钮显示「记一节课 · 扣1次」。选定学员/日期/类型后查询该学员同日同类型未处理预约：展示快捷确认和「另记一节」，由教练确定真实来源，不自动关联。网络重试保留直接记课操作键，收到记录后文字编辑使用PATCH对象ID。
- [ ] 有预约从原finish接口确认；已处理项显示当前结果而非再次可扣。无账号绑定的学员档案仍可直接记课。保存后刷新钱包和统一历史；可用不足提示录入课包，日期错误保留其余输入。
- [ ] 运行前端 build 和任务 4–5 API 测试；浏览器实际跑通流程，确认幂等重试、12小时取消提示、两类钱包与报名人数一致。更新 moss-mem。

## 任务 7：训练记录、计划、提交和点评 API

**Files:** 新增 `coaching/api/training.py`、`coaching/tests/test_api_training.py`；修改 `serializers.py`、`urls.py`。

**Interfaces:** 训练接口见表；动作使用 JSON 数组，重量响应为十进制字符串，空值为 null，duration 单位为秒。`intent` 明确区分 draft/submit。

- [ ] 写对象范围、训练校验和提交锁定测试，先运行失败：

```python
from django.utils import timezone
from coaching import training
from coaching.tests.api_helpers import ApiTestCase

class ApiTrainingTests(ApiTestCase):
    def test_submitted_plan_is_locked_and_other_student_gets_404(self):
        plan = training.create_plan(self.student, self.coach, '课后练习',
            timezone.localdate(), [{'name': '划船', 'reps': 12}], '')
        self.client.force_login(self.student.user)
        body = {'exercises': [{'name': '划船', 'reps': 12, 'weight': '9.5'}],
            'note': '完成', 'intent': 'submit'}
        path = f'/api/v1/student/plans/{plan.id}/submission/'
        self.assertEqual(self.client.put(path, body,
            content_type='application/json').status_code, 200)
        body['note'] = '改动'
        self.assertEqual(self.client.put(path, body,
            content_type='application/json').status_code, 409)
        self.client.force_login(self.other.user)
        response = self.client.get(f'/api/v1/student/plans/{plan.id}/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'not_found')
```

- [ ] 添加草稿修改、同提交重试、未正式提交不能点评、同学员预约关联、未完课不能写课上记录、动作数量1–50、名称≤80、文字≤4000、bool数值拒绝、重量0和9.5与6.25接受、超过两位精度拒绝用例。
- [ ] 预约课程的轻量记录新增note-only测试：`save_record`接受空exercises数组和有效文字，依旧要求completed与教练权限；`validate_exercises`自身及目标计划/提交动作规则保持原有严格校验。完课动作本身无需写TrainingRecord；未记录文字也显示真实已上课历史。
- [ ] 新序列化类以 JSON 数组直送 `training.validate_exercises`，捕获其 DomainError 为字段 `exercises` 的400，不经DRF IntegerField把 bool转成1。其他写入仍调用同一 `save_record/create_plan/save_submission/review_submission`。
- [ ] 教练创建计划必须先查 student 和可选 booking，并由服务复核属于同一学员。学员 GET/PUT 在查询入口按 `student__user=request.user` 过滤；避免先读别人对象再判断。
- [ ] 响应和列表 select_related 必要的课程/档案；计划状态根据 submitted_at/reviewed_at 推导，不新增状态字段或余额缓存。提交时未填写实际数据与说明仍由服务拒绝。
- [ ] 运行 `manage.py test coaching.tests.test_api_training coaching.tests.test_training --noinput`，验证更新提交/点评返回真实当前对象，其他学员无可读数据。更新 moss-mem。

## 任务 8：训练编辑、学员提交与教练点评页面

**Files:** 新增 `frontend/src/api/training.ts`、`src/components/ExerciseEditor.vue`、`src/pages/{CoachPlan,StudentTraining,StudentPlan}.vue`；扩展 `CoachBooking.vue`、`CoachStudent.vue`、`types.ts`、`router.ts`、样式。

**Interfaces:** `/coach/plans/:id/`、`/student/training/`、`/student/plans/:id/`；课上记录和建计划嵌入个人预约/档案页面；读取任务 7 的JSON，不让用户编辑原始 JSON 文本。

- [ ] 浏览器先记录不能完成的目标：教练完课后填记录和计划→学员看记录、存草稿再提交→教练点评→学员看到反馈；覆盖小班逐人记录隔离。
- [ ] 共享 ExerciseEditor 编辑 name、sets、reps、weight、duration。为空发送null，重量保留十进制字符串，整数只接受正整数；计划目标与实际结果分别展示，学员提交的动作名以计划为准。

```ts
export function emptyExercise(): Exercise {
  return { name: '', sets: null, reps: null, weight: null, duration: null }
}
export function submissionBody(rows: Exercise[], note: string, intent: 'draft' | 'submit') {
  return { exercises: rows, note, intent }
}
```

- [ ] 教练记录只在 completed 时编辑，未开始和未完课展示服务端状态。建计划允许档案单独创建或关联本人预约，计划编辑不混入新增未确认能力。
- [ ] 日常训练记录先显示一个选填文字框，详细动作编辑按需展开；直接课程使用任务5A的PATCH，预约课程使用record接口。StudentTraining主列表读取 `/api/v1/student/lessons/`，结合source导航/展示，包含未填文字的真实已上课记录；课后计划另作既有能力入口，不作为记课或阅读课上记录的前置条件。
- [ ] 学员草稿可修改，正式提交需提示锁定；提交后显示只读实际结果和点评。请求失败保留输入；相同正式提交重试可以调用已有服务，不生成新提交对象。401清空私人数据，重新登录后从 API 恢复已保存草稿。
- [ ] 教练点评写入现有单条当前点评，已点评可修正；未提交时不提供点评动作。首页待点评条目链接到实际 plan_id，处理后刷新首页待点评数量。
- [ ] 运行 build 与 `test_api_training`；浏览器完成上述双方流程、锁定和小班隔离，并检查手机长动作名、空列表和400字段提示。更新 moss-mem。

## 任务 9：SPA 路由、静态缓存与部署产物

**Files:** 新增 `opencoach/frontend.py`、`coaching/tests/test_frontend.py`；修改 `opencoach/{settings,urls}.py`、`Dockerfile`、`.dockerignore`、`.env.example`、`tools/{deploy_support,remote}.py`、`coaching/tests/test_deploy_support.py`、`README.md`。

**Interfaces:** `OPENCOACH_FRONTEND_ENABLED=1` 为迁移期入口切换开关（默认0）；`frontend/dist/index.html` 为普通文件；`frontend/dist/static/h5/*` 经 WhiteNoise 提供；发布前要求已构建 index 和引用资源完整。

- [ ] 写路由与缓存失败测试：开关启用时 `/login/`、`/coach/students/1/`、`/student/plans/1/` 返回同一 SPA；未知 `/api/v1/...` 为JSON404、缺失 `/static/h5/missing.js` 为404；POST 页面不回入口；index Cache-Control=no-store；真实 hash 资源长期缓存。用临时构建目录测试，不依赖远程环境。
- [ ] 写部署白名单失败测试：接受前端源文件、package/lock、dist/index和哈希资源；拒绝 frontend/.env、node_modules、.git、data、路径越界和符号链接；清理旧上传哈希只影响 manifest 跟踪文件，保留 .env、db和未跟踪文件。
- [ ] 入口只注册本计划列出的客户端 GET/HEAD 页面，不用匹配所有路径的兜底 SPA；API/health/static 优先。普通index不存在时返回明确503，不能偷偷回到旧页面造成混合版本。

```python
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from django.views.decorators.http import require_safe

@require_safe
def app_entry(request, **kwargs):
    path = Path(settings.FRONTEND_DIST) / 'index.html'
    if not path.is_file():
        from django.http import HttpResponse
        return HttpResponse('前端尚未构建', status=503)
    response = FileResponse(path.open('rb'), content_type='text/html; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    return response
```

- [ ] `STATICFILES_DIRS` 添加已存在的 `frontend/dist/static`，保留原static；现有 Manifest storage保留Vite原哈希文件，不能开启删除原文件而让index引用失效。配置 WhiteNoise 对 `/static/h5/` 实际哈希文件识别为immutable，并验证响应头，缺失资源不进入SPA。
- [ ] `.dockerignore` 排除 frontend/node_modules、真实前端.env、Live本地注入与本机缓存；保留 dist。Docker构建前检查dist/index与资源存在；Python镜像运行，不拉Node构建镜像。保持运行用户1000和现有持久化挂载。
- [ ] 上传源文件按明确入口+`src/`以及`dist/`收集，不直接将整个frontend递归放宽；`deploy_support.source_name` 同步同一规则。包锁与源码可以归档交接，但不上传依赖目录、敏感配置或源映射。
- [ ] `remote.py deploy` 取消自动 `seed_demo`，演示初始化只能显式单独命令；已有数据原样保留。新增可选 `--frontend 0|1`：不传时保留实例现有值；传入时只更新 `OPENCOACH_FRONTEND_ENABLED` 一行并保持.env权限0600。沿用配置预检查，成功构建后才写该开关并启动新容器；配置写入失败保留原.env和运行服务。上传/构建前本地验证产物，远程切换前保留上一运行镜像ID和配置开关，并做数据库一致备份。
- [ ] 将本地启动分成 Django API与Vite命令，生产镜像只收构建产物；记录普通发布不改 Caddy。旧HTML视图测试用开关0专门验证保留入口，SPA/API分别用开关1验证，标明历史测试归属。
- [ ] 运行 `npm --prefix frontend ci`、build、`manage.py test --noinput`、`manage.py check`、`manage.py makemigrations --check --dry-run`；部署/静态测试用DEBUG=False验证WhiteNoise真实路径。Windows不运行Gunicorn，运行镜像验收在Linux完成。

## 任务 10：测试环境发布、数据验收与回滚演练

**Files:** 修改 `tools/verify_remote.py` 的API/SPA核验；新增 `docs/superpowers/reviews/2026-10-11-formal-h5-acceptance.md`；更新 README、PRODUCT及moss-mem交接。服务器只操作 `/root/opencoach-test` 应用和其配置。

**Interfaces:** 公网 `/health/`、SPA页面和`/api/v1/`匹配同一版本；共享 Caddy 继续整站反代 `127.0.0.1:8001`。增量迁移后前端可先在兼容新账目的后端镜像中切开关0；旧镜像回退须验证新消课来源兼容，数据库不自动回退。

- [ ] 发布前输出影响面：替换OpenCoach独立应用镜像、开启SPA路由；保留原.env密钥、账号、data挂载、共享Caddy及商城。核对 SSH 指纹，用隐藏输入连接；凭据不写文件。
- [ ] 用 `backup_db` 创建带时间戳且不覆盖旧文件的一致快照；记录业务表数量、关系与关键内容，排除session和last_login。以发布当时数据库为准，不强求历史快照数量一直不变。记录旧运行镜像ID并打唯一retained标签。
- [ ] 构建前端并复核上传清单，上传后在远程构建新应用镜像；依赖下载慢时只用已有127.0.0.1:7890构建代理，不修改系统代理。构建完成才更新实例开关并替换服务。远程Linux执行完整测试并确认health成功。

```powershell
# 本地项目根目录；全部检查通过后执行部署。
npm --prefix frontend ci
npm --prefix frontend run build
.\.venv\Scripts\python.exe manage.py test --noinput
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
python tools/remote.py deploy --frontend 1
```

- [ ] `verify_remote.py` 使用实际 HTTPS：匿名会话取CSRF→教练登录→首页→退出→学员登录→首页。验证Secure/HttpOnly、CSRF旋转、403/404 JSON、深链接刷新、静态404和缓存；禁止工具自动重试非幂等写操作。确认 dist/index 与引用脚本没有 Impeccable Live 注入、源映射或开发服务器地址。
- [ ] 公网检查现有数据未变，真实账号仍登录；写流程使用明确新建验收学员和课程，记录这些新对象ID与测试来源，不修改原课包和训练样本。完整执行邀请→课包→预约→完课→记录→计划→提交→点评、重复消课、取消及小班逐人处理。
- [ ] 验收无排课/无预约的直接记课、同次请求重试、文字补写、统一历史、预约预占保护、同日真实多节与新学员之后接受邀请仍可看原记录。原流水内容与余额不因迁移变化；直接记课新增流水有来源且不会被旧列表错误当成某笔预约。
- [ ] 手机和电脑各一轮实际任务检查；统一修复后至多再一轮确认。记录身份切换无旧数据、断网保留表单、加载状态、焦点、字段label、长文本与无横向溢出。不在测试站注入Impeccable Live。
- [ ] 创建发布后备份，恢复到独立临时SQLite文件做ORM比较，重启OpenCoach容器后再次核对业务内容；不覆盖运行数据库。确认商城健康与站点配置保持原状。
- [ ] 用新后端镜像演练入口开关0/1与数据一致；直接记课历史通过新API仍可读取。数据库已有新来源后，旧镜像是否能读取钱包、继续预约消课及处理来源缺失需在独立恢复副本验证，结果记录到验收文档；未证实兼容则采用同一新后端镜像仅回退前端入口。不得自动降级数据库、删除新课时流水、执行seed_demo或全局Docker清理。
- [ ] 将版本、测试输出、手机/电脑证据、业务核验、备份和retained镜像记录到验收文档；更新README/PRODUCT的实际运行状态，moss-mem保留具体下一步和雷区。主代理完成最终验证后交付测试域名。

## 覆盖与阶段验收

| 已批准要求 | 对应任务与证据 |
| --- | --- |
| Vue3/Vite独立H5、真实登录、教练品牌、邀请 | 1–3：API认证/CSRF测试、npm构建、双方首页实际浏览器操作 |
| 教练权限、学员对象隔离和稳定JSON | 1–2、4–5、7：角色与他人对象API测试，未知接口/方法边界 |
| 排课、预约、课包、取消、完课和缺席 | 4–6：API测试、既有业务/并发测试、双方同一数据流程 |
| 直接记课、文字选填、账目与混合已上课历史 | 5A、6–8、10：幂等/预占/并发/迁移测试，直接和预约两条实际记课流程 |
| 课上记录、课后计划、草稿/提交/点评 | 7–8：精度与提交锁定测试、双方训练指导闭环 |
| 手机/电脑、加载/空/错误状态 | 3、6、8、10：有限批次的实际页面验收 |
| 私有实例、静态同镜像、深链接和持久化 | 9–10：打包白名单/SPA测试、HTTPS数据/备份/重启核验 |
| 保留测试账号、既有数据、商城与可回退 | 9–10：无seed_demo、业务快照、旧镜像、路由回退演练 |

实施方式已经由用户工程纪律确定为主线程执行，不再询问是否使用子代理编码。任务1–3通过后给出可演示结果和验证证据，再继续任务4–10（含5A）；每个检查点汇报实际结果，不把计划当作已实现功能。直接记课与教练习惯目标已获授权，不重复询问是否允许该入口。
