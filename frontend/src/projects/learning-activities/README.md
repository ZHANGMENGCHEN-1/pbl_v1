# 图书分类学习活动（纯活动版）

路由：`/projects/learning-activities`。本目录保存独立的任务组件和会话逻辑，后续可单独修改。

不加载机器人、对话框或模型聊天。填写班级和学号后直接展示活动1；逐轮计算、保存本轮分组作答、最终交付完成后进入活动2。排序正确后点击“进入活动3”，上传Excel并完成分析和交付。保留活动解锁和前面活动回看；学习记录从顶部右上角按钮打开右侧抽屉，不提供重新开始按钮。

每个活动有效提交后，先关闭任务并进入无机器人的活动回顾聚焦界面，弹出与B/C班相同的四题1–5分状态测量。保存后手动前往下一活动，最后一个活动保存后可查看记录；不发起模型请求。状态测量组件位于 `../teaching-shared/StateMeasurement.vue`。

复用现有 `/api/projects/teaching-agent` 计算、上传和交付接口，使用独立 session 隔离数据。登记时传入 `source_route=learning-activities`，后台 `teaching_students.source_route` 标识入口，可用 project/session 关联交付、聊天和埋点。刷新仍按原规则创建新会话。

原版 `/projects/teaching-agent` 与完整副本 `/projects/meaning-making` 各有独立前端目录。修改本目录不会改变其他版本的界面或前端流程。
