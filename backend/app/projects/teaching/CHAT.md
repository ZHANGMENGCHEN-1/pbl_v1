# 小知真实流式对话

学生每次提问仅调用一次`LLM_MODEL`，复用`LLM_API_KEY/LLM_BASE_URL/LLM_MODEL/LLM_TIMEOUT_SECONDS/LLM_MAX_OUTPUT_TOKENS`。不另选模型、不自动降级到预设回复、不调用额外的摘要模型。现有开场、任务引导及排序反馈仍为平台预设文字。

## 教学提示词与实际证据

`pedagogy.py`的`COMMON_RULES`定义共同规则，`ACTIVITY_RULES`定义三个活动的教学重点。模型只负责解释，不绑定任何工具，不处理活动解锁或交付。

`chat.py`根据前端的活动、界面阶段和记录ID，验证会话归属后读取SQLite实际结果，拼成确定性的学习状态摘要：

- 活动1：五本书、本轮距离/分组、计算前与计算后中心、停止状态。未计算时明确为空。
- 活动2：学生当前排序草稿（明确是学生UI草稿，不是后端验证的交付）；此前活动1已提交的真实计算。
- 活动3：当前上传文件/版本、实际分析列；图已生成才包含实际数量、中心、范围及每组最多两条真实二维点示例。改表或改列后不自动套用旧图。
- 已保存的学生交付与实际结果分开，标记是否与本次计算对应。

保留最近最多3轮完整模型对话，总计不超过2000字符；完整问答仍在数据库保存。当前学生问题完整发送，最多2000字符。文件名和列名按数据处理，不作为指令。不会把前端提供的任意结果JSON当成实际证据。

## 输出与状态

提示词在生成时要求通常50–80字、尽量不超过100字（含标点）、2–3个完整句子，接近目标时自然收尾，最多一个具体追问；学生不会时直接解释。100字是软目标，服务端不再按字符截断或提前关闭上游流。输出token预算默认512，配置范围512–1200，为完整收尾留出余量；token是供应商安全上限，不等于字数限制，仍可能触顶。首token等待也取决于模型服务和模型自身的推理设置。只转发文本内容，不转发独立的推理字段。

`POST /api/projects/teaching-agent/chat`，请求头`X-Session-ID`，JSON：

```json
{
  "activity_id": "explore_2d",
  "question": "一行数据怎样变成一个点？",
  "context": {
    "phase": "task",
    "dataset_id": "当前上传ID",
    "analysis_id": "本次真实计算ID",
    "features": ["c1", "c2"]
  }
}
```

活动1传`step_id/initial_centers`，活动2传`step_order`。SSE事件为`start/delta/done/error`；等待期间有连接心跳。前端用fetch流读取，兼容UTF-8跨包、CRLF和心跳；暂停通过AbortController断开请求，上游迭代器随之取消。活动、文件、分析列或计算ID改变时，中止过时的回答。

模型连接错误显示错误和重试，不伪造模型文字。前端`useTeachingChat.ts`管理思考、回复、暂停和错误；`Workspace.vue`在没有进行聊天回复时显示任务提示，回复期间气泡只显示小知本轮回复和状态。

## 保存与隔离

新表`teaching_chats`保存项目、会话、活动、问题、回答、提问时的上下文快照、开始/结束时间、状态及安全错误消息。开始写一次，完成或取消时再写一次，不逐token写库。状态为`running/completed/cancelled/error/interrupted`，重启后将遗留运行标记为中断。只有完整成功的问答进入后续模型历史。

刷新仍按当前测试规则创建新会话，页面不恢复旧聊天，但后台记录保留。当前尚无学生身份认证。密钥和模型服务地址均不传给前端。

## 验证与限制

后端`python -m pytest tests -q`。根目录`node scripts/teaching_chat_stream_smoke.mjs`验证字节边界、中文/emoji和异常SSE。

浏览器：运行`python scripts/teaching_chat_fixture_server.py`，前端以`API_TARGET=http://127.0.0.1:8001`启动5174，再运行`python scripts/teaching_chat_browser_smoke.py`。此fixture只在本地模拟模型供应商，实际经过FastAPI和ChatOpenAI HTTP/SSE，绝不可部署。验证三活动上下文、真实计算证据、逐段显示、思考/暂停/错误、上游取消和超长回复完整保留。

外部真实模型实测需要本地`backend/.env`配置有效密钥并重启后端。测试不会读取或调用付费模型；不能把本地模拟供应商的测试宣称为外部LLM实测。

集成依据：[LangChain ChatOpenAI官方文档](https://docs.langchain.com/oss/python/integrations/chat/openai)。
