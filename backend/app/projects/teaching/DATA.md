# 教学数据与埋点（第一期）

## 身份与存储

沿用 `DATABASE_PATH` 指定的 SQLite 数据库；默认从 backend 启动时为 `backend/data/workspace.db`。
学生登记入口为 `POST /api/projects/teaching-agent/student`，使用 `X-Session-ID` 关联班级和学号。学号按 TEXT 保存，保留前导零。
班级与学号是学生自报标识，不是登录认证。同一学生多次进入页面，会有不同 session；当前刷新创建新会话的规则保持不变。

所有教学 POST（登记本身除外）要求会话先完成登记。身份从后端登记表获取，客户端不能在提交中覆盖。
新增记录在自身表内保存 `class_name`、`student_number`，也保留 `project` 和 `session`。
旧记录仅在已存在真实会话登记时补齐身份；无法确认的记录保持 NULL，不推测身份。
初始化执行可重复的增量迁移，保留旧表和旧记录。

## 表与字段

| 表 | 记录粒度 | 主要证据 |
| --- | --- | --- |
| teaching_students | 一个会话 | 班级、学号、登记时间；登记后不能改绑其他身份 |
| teaching_submissions | 一次活动交付尝试 | activity、result_id、payload、created、request_id、attempt_no |
| teaching_round_answers | 活动1某轮的一次分组作答 | result_id、每本书所选组别（1/2）、真实组别、是否匹配、计算轮次和中心、attempt_no |
| teaching_chats | 一轮问答 | question、answer、context、created、first_response_at、finished、status、stop_reason、model、prompt_version |
| teaching_steps | 活动1一轮真实计算 | 原中心、距离、分组、新中心、轮次和收敛信息 |
| teaching_datasets | 一次成功上传 | 文件、数据版本和解析结果 |
| teaching_analyses | 一次真实二维分析 | 数据集及版本、所选列和分组结果 |
| teaching_events | 一次关键过程事件 | 身份、activity、type、reference_id、data、created |

时间均为后端 UTC ISO 8601。展示时转换为北京时间。聊天 `created` 表示后端接受有效提问并创建记录的时间，`first_response_at` 是首段正文到达时间；无正文时为 NULL，`finished` 为终态保存时间。不记录推理内容。
聊天状态：`running`、`completed`、`error`、`cancelled`、`paused`、`interrupted`。
显式暂停会上报 `stop_reason=student_paused`；未收到暂停意图的断连保存为 cancelled，服务重启时遗留 running 改为 interrupted。
客户端暂停通知采用尽力上报，浏览器断网时不能保证辨认暂停意图，应结合状态分析。

活动1最终交付保留学生数量和中心、程序计算值及比较结果。中心比较允许绝对误差 0.001，容纳界面显示的三位小数；比较不是成绩，错误答案仍可提交。
活动2在后端检查完整步骤顺序；正确与错误尝试都保存，前端收到成功响应才更新交付状态。
活动3保留数量、文字解释、数据集版本及实际分析结果；仅自动比较数量，不自动评价解释内容。

## 请求去重和尝试

三个活动交付及活动1本轮作答接受 `request_id`。同一会话、活动中的同一编号重试返回原记录，不新增尝试；编号对应的答案不同则返回 409。
前端遇到网络或服务失败后保留编号，修改答案或一次提交成功后的新提交使用新编号。
活动最终交付的 attempt_no 按会话和活动累加，本轮作答按会话和 result_id 累加；历史交付不覆盖。
提交证据和成功事件在同一事务写入。旧交付 attempt_no/request_id 可以为 NULL。

## 事件字典

| type | 来源/触发 |
| --- | --- |
| student_registered | 后端登记成功，每个会话一次 |
| activity_entered | 前端进入活动阶段上报，按事件 ID 去重；失败重试一次 |
| calculation_completed | 后端创建活动1计算记录；读取已有轮次不重复生成 |
| round_answer_saved | 后端保存一次本轮分组作答 |
| submission_saved | 后端保存一次活动交付 |
| activity_completed | 后端保存有效交付，每会话每活动一次；活动2要求排序正确 |
| dataset_uploaded | 后端成功解析并保存上传文件 |
| analysis_completed | 后端保存二维计算结果 |
| help_requested | 后端保存问题，关联 chat ID |
| chat_finished | 后端保存问答终态，关联 chat ID |
| chat_pause_requested | 显式暂停，关联 chat ID |
| operation_failed | 已登记会话的教学 POST 返回 HTTP 4xx/5xx；保存路径和状态码，不存供应商敏感错误 |

前端只能上报 activity_entered，不能伪造成功/完成事件。页面停留时间不等于有效学习时间。
事件是历史事实，例如 cancelled 后才收到暂停通知，chat_finished 事件可能仍描述先前状态；当前最终状态以 teaching_chats 为准。
浏览器本地校验未发请求的错误、未送达服务器的断网请求不在 operation_failed 范围。

## 查询示例

按学生查看所有学习会话与交付（参数化传入班级、学号）：

```sql
SELECT session,activity,attempt_no,id,result_id,payload,created
FROM teaching_submissions
WHERE class_name=? AND student_number=?
ORDER BY created,id;
```

查看某会话时间线和问答：

```sql
SELECT type,activity,reference_id,data,created
FROM teaching_events WHERE project='teaching-agent' AND session=? ORDER BY created,id;

SELECT activity,question,answer,status,created,first_response_at,finished
FROM teaching_chats WHERE project='teaching-agent' AND session=? ORDER BY created,id;
```

验收使用 `tests/test_teaching_telemetry.py`、原有教学后端测试，以及 `scripts/teaching_chat_browser_smoke.py`。
浏览器测试使用独立数据库和本地模型替身，不调用付费模型；审计接口仅位于本地 fixture，不能部署到正式环境。
