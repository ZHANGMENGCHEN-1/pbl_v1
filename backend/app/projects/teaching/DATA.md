# 教学数据与埋点（第一期）

## 身份与存储

沿用 `DATABASE_PATH` 指定的 SQLite 数据库；默认从 backend 启动时为 `backend/data/workspace.db`。
学生登记入口为 `POST /api/projects/teaching-agent/student`，使用 `X-Session-ID` 关联班级和学号。学号按 TEXT 保存，保留前导零。
`teaching_students.source_route` 区分 `teaching-agent`（原版）、`meaning-making`（完整副本）和 `learning-activities`（纯活动版）。旧记录默认归原版；同一会话不得改绑其他入口。三个入口共用后端接口，以各自独立的会话隔离数据；按 project/session 关联此表可区分交付与埋点来源。
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
| teaching_state_measurements | A/B/C班一次有效交付后的四题状态测量 | 身份、source_route、activity、submission_id、ratings、created、request_id |

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
| state_measurement_submitted | 三班四题1–5分自评保存成功，关联 measurement ID 与 submission_id |
| reflection_opening_requested | C班测量保存后平台请求模型开场，关联 chat ID；不计作学生主动求助 |

前端只能上报 activity_entered，不能伪造成功/完成事件。页面停留时间不等于有效学习时间。
事件是历史事实，例如 cancelled 后才收到暂停通知，chat_finished 事件可能仍描述先前状态；当前最终状态以 teaching_chats 为准。
浏览器本地校验未发请求的错误、未送达服务器的断网请求不在 operation_failed 范围。

## A/B/C班状态测量与C班模型策略

`POST /api/projects/teaching-agent/state-measurements` 接受登记 source_route 为 learning-activities（A班）、teaching-agent（B班）、meaning-making（C班）的会话。请求含本会话的 submission_id、request_id 以及四个原始整数评分 difficulty、boredom、frustration、self_efficacy，各为1–5；不计算总分，不反转存储第4题。活动2仅排序正确的交付可以提交结束测量。

一份活动交付只保存一份测量；同内容重试返回原记录，改变已保存评分或复用请求编号到另一交付返回409，不覆盖历史。新交付可以关联新测量。数据独立保存在 teaching_state_measurements，不能访问其他会话的交付。

### 调查编号、版本与作答时间

原表保留，并增量添加下列字段。每次调查指四题全部答完且服务器保存成功的一份记录，不是单独一个滑块，也不是按钮点击次数。

| 字段 | 定义 |
| --- | --- |
| student_survey_no | 同 project＋source_route＋班级＋学号的累计调查次序，从1开始，跨会话延续；A/B/C入口分别计数 |
| session_survey_no | 本次学习会话第几次调查，从1开始；正常完成三个活动通常为1、2、3 |
| activity_survey_no | 本会话内当前活动第几次调查，重复有效交付后继续累计 |
| activity_number | 活动1、2或3；不能拿它代替调查次序 |
| survey_phase | 当前为 post_activity，即活动交付后的测量 |
| questionnaire_version | 新界面使用 learning-state-v3，四题原始分数独立保存，不求总分、不反转存储第4题；未传版本的旧客户端继续按v1保存 |
| response_mode | 新界面为 slider-5point-v1，表示1–5整数滑块 |
| started_at | 浏览器创建本次调查窗口的时间，规范化保存为UTC；客户端时钟，仅用于辅助分析 |
| response_duration_ms | 从窗口创建到首次完整作答并点击保存的经过时间，由performance计时；首次有效请求后冻结，网络重试不会延长或覆盖 |
| created | 后端成功保存时间，UTC；记录排序和编号以服务端为准，不依赖客户端时钟 |

数据库写事务 BEGIN IMMEDIATE 内分配编号并保存，三个计数范围各有唯一索引。重复request_id或相同交付的幂等重试返回原记录、原编号和原时间信息。

初始化会升级现有表；旧记录首次按created/id顺序补编号，之后不重新编号。无法确认的旧问卷版本、交互方式写为legacy-unspecified，缺失的开始时间、耗时保持NULL。原ID、原评分、原交付关联和原保存时间不变。

查看或导出可使用只读视图 `teaching_state_measurement_records`，将ratings JSON展开为difficulty、boredom、frustration、self_efficacy四列，并将created显示为submitted_at：

```sql
SELECT class_name,student_number,source_route,session,
       student_survey_no,session_survey_no,activity_survey_no,activity_number,
       difficulty,boredom,frustration,self_efficacy,
       questionnaire_version,response_mode,submitted_at,response_duration_ms
FROM teaching_state_measurement_records
ORDER BY submitted_at,id;
```

学生标识沿用班级＋学号，入口标识用于区分A/B/C组；会话ID区分同一学生的多次学习。新增字段不需要向学生展示，不增加问卷界面内容。

问卷v2：第1题保持原陈述，五级选项为“完全不符合、不太符合、一般、比较符合、完全符合”；第2、3题保持原无聊/沮丧陈述，选项为“一点也不、有一点、中等程度、比较强烈、非常强烈”；第4题改为“对于完成接下来的学习任务，你有多大信心？”，选项为“完全没信心、不太有信心、有一些信心、比较有信心、非常有信心”。每题各自显示一行选项，仍存1–5整数。

v1为原四个陈述及统一“非常不同意、不同意、既不同意也不反对、同意、非常同意”选项。v3前三题保持原文，第4题改为“对于完成接下来的学习任务，我很有信心。”，统一选项为“非常不同意、不太同意、有点同意、比较同意、非常同意”，四题共用顶部一行说明。v1/v2历史记录不改写；同一次交付已有已知版本的测量，不允许以其他版本覆盖。分析时按版本区分。

C班聚焦交流传入 context.measurement_id，由后端读取评分与交付并选择Content/Task/Experience/Self/Positive；不接受前端自报策略或评分。开场purpose=reflection_opening、question_source=platform；追问为question/student。聊天context保留关联ID、策略和版本、实际交付摘要、generation_attempts=1和delivery=streaming。按最新要求，C班收到正文立即流式转发，不等待整段校验、不额外重写、不按字符截断；100字保留为提示词生成目标。A班没有模型，B班继续普通教学对话，不使用评分策略。

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
