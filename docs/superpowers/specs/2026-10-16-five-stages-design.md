# 五阶段需求与设计

来源：Downloads/stage-1.md 至 stage-5.md。累计交付完整源码快照及变更说明；不含依赖、构建产物、数据库与密钥。未提供所引用《契约附件》，沿用现有角色权限、CSRF、JSON错误、账本约束和同镜像交付契约。

## 一、有效期与账本

- 购买新增可空 expires_on，旧购买默认 null、永久有效；流水保留，不删除或重算历史总购买/总消耗。
- 上海自然日，日期当日有效，下一日失效。预约、消课均按操作当天检查有效性，补记过去课程不能绕过当前过期检查。
- 消耗关联购买批次，先到期先消耗，无期限批次最后使用；旧未关联消耗按购买先后扣减，仅建立归属而不改历史流水。
- remaining 为购买减消耗；expired 为过期批次未消耗数量；reserved 为活跃预约实际占用的有效课时；available = remaining - expired - reserved。预约跨到期后仍保留预约历史与名额，但失效的课时不再可消耗；需有效续课后才能确认消课。
- 有效预约按创建顺序分配有效批次，直接记课保护这些预占。课包摘要提供7天内到期的未消耗批次数量与日期，含预占部分。
- API：credits POST 支持 expires_on；wallets 新增 expired 和 expiring；credit_data 新增 expires_on。

## 二、改期

- 新增双方 reschedule API，学生仅本人且原课距开课至少12小时；教练可代操作。
- 同事务取消原预约、创建目标预约；目标必须未来、未取消、不同课程、类型相同、未满员、不冲突、有有效课时。
- 新预约记录 rescheduled_from，operation_key 唯一且重试校验原预约与目标；失败回滚。成功后原课递补候补，目标结果不变。

## 三、批量记课

- batch API 接收统一 kind/occurred_on、整批 operation_key 和逐项 key、student_id、note、exercises。
- 一个事务覆盖全部记录、消耗和幂等批次记录；非法/不足/过期任一失败全部回滚。逐项重试返回旧记录，整批 key 绑定规范化载荷，防止改意图重用。
- 限1至100项，同批学员和逐项key不得重复；日期不晚于上海今天。返回 lesson_data items 与学员钱包，前端提供多学员选择及结果。

## 四、候补

- 满员且未来未取消课次才可加入；每学员每课一条 waiting；加入不预占，递补才预占。
- 释放名额的取消、改期在同事务执行FIFO递补（created_at,id）；不足有效课时、冲突或失效账号跳过并保持waiting。课程整堂取消清理waiting为cancelled，不递补；开始后不递补。
- 每条候补有唯一operation_key，递补预约使用该key形成稳定一次性结果；数据库部分唯一约束和SQLite IMMEDIATE事务防止并发超员。
- 学员加入/退出/查看自身候补，教练按课程查看队列；列表显示当前状态、顺位与递补结果。

## 五、月报及加固

- coach/reports/monthly/?month=YYYY-MM；上海月初闭区间、下月初开区间。
- 预约按课程开课时间，直接记课按occurred_on，递补按promoted_at，过期按expires_on次日计入所属月份，统计未消耗数量。
- 指定七项计数，另返回 scheduled_rate 与明确分母；整堂取消不计到课率分母，直接记课单列；空月计数0、率0。
- 各新接口沿用严格输入、角色/对象权限、CSRF、{error:{code,message,fields?}}，UI提供加载、失败重试、空态、防重复提交。

## 工程与验收

Python3.12、Node>=24，Vue/Django/SQLite WAL+IMMEDIATE不变，不新增包。按阶段补真实行为、回滚、幂等、权限、迁移及真实文件SQLite TransactionTestCase并发测试。实际运行collectstatic、全部后端测试、check、makemigrations --check --dry-run、客户端测试、包含typecheck的build。浏览器检查新增入口和移动布局。源码打包使用明确白名单并检查压缩包清单。当前目录无.git，不执行Git提交、不创建伪Git历史。不自动发布服务器。
