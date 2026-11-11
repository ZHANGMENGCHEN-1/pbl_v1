# 教学Agent：前三个活动

路由`/projects/teaching-agent`。保留Three.js小知与气泡。活动1是真实单轮计算；活动2支持随机初始化、拖动排序和规则反馈；活动3支持上传Excel、预览、二维K-means、散点图及并排提交。学生提问现通过后端同一个LLM流式回复；开场、任务提示与排序反馈仍为预设说明。教学规则、上下文和接口见[小知对话说明](../../../../backend/app/projects/teaching/CHAT.md)。

## 当前测试行为

每次刷新或重新进入页面都创建新会话，从活动1开始，不恢复浏览器历史。当前页面内保留草稿、排序和提交记录。后台保存文件、真实计算、提交与模型问答，不因刷新删除。原天文/图书馆项目不受影响。

## 活动3

学生上传`.xlsx`，第一行为不重复的非空文字列名，每行一条记录；只读取第一张工作表，界面显示工作表名。限制5MiB、3000条记录、50列；列名最多80字，单元格文字最多2000字；压缩包解压内容上限25MiB。

默认选中从左到右前两列含数值的列，学生可以调整。界面展示前20行、总数、列名、两列完整有效记录数量及未参与计算的行号/原因。空值、字符串（包括数字文本）、公式、日期、布尔值、非有限或超出±1e12数值会明确排除；不修改原始文件，不推断或转换单位，不自动换表或换列。空白数据行也计入总记录并明确排除。有效点不足2个或所有有效点重合时拒绝运行。

后台复用`library/clustering.py`的纯函数`one_step`，不依赖旧项目活动锁定。固定K=2、原始数值欧氏距离、不标准化；种子42从不同数据点中随机选初始中心；每轮重新分配并更新均值，最多100轮。若未稳定，明确提示。数值全精度计算，界面近似显示。

运行后立即显示实际轴名、分组颜色、各组数量、中心及150/3000条实际散点。坐标轴从0开始、格点为整数，原始记录查看区已移除；不要求先点击再提问。桌面宽屏下，结果和手填提交区并排；窄屏上下排列。学生自己填写两组数量和一句特点，不自动填答案，不以标准答案完全一致作为提交条件；数量须非负整数且合计实际参与计算数。

修改列或重新上传会清除当前图与答案草稿，旧文件和旧分析不会被覆盖。后端`teaching_context`包含实际文件/版本/工作表/列名、有效与排除数量及原因、范围、组数/数量/中心、收敛情况、参数和解释局限，已用于真实LLM的教学上下文；结合少量真实二维点示例解释表格的一行如何映射到图上。

## 文件

- `Workspace.vue`：任务/对话模式、气泡引导、活动推进和本次学习记录。
- `learningState.ts` / `useTeachingLearning.ts`：草稿、操作、真实提交快照、当前会话状态；每次刷新重建。
- `CenterExperiment.vue` / `calculation.ts`：活动1真实计算与手填交付。
- `AlgorithmSteps.vue` / `sorting.ts`：活动2拖动、规则反馈、每次尝试记录。
- `ExcelExperiment.vue` / `exploration.ts`：活动3上传、预览、选列、运行、并排提交、接口类型。
- `ScatterPlot.vue`：实际二维散点图、中心和原记录查看。
- `backend/app/projects/teaching/routes.py`：活动1计算与SQLite存储。
- `backend/app/projects/teaching/excel.py`：隔离上传、解析、选列诊断、真实K-means和交付保存。

## API与存储

活动3前缀`/api/projects/teaching-agent/activities/explore_2d`，`X-Session-ID`隔离本项目会话：

- `POST /datasets`：原始文件字节作为请求体，`X-File-Name`为encodeURIComponent后的文件名；返回数据ID、SHA256文件版本、工作表、列、预览和默认列。
- `GET /datasets/{id}`：读取本会话数据概要与预览。
- `POST /preview`：`dataset_id/features`，返回所选两列的有效数量和所有排除行号/原因。
- `POST /analyses`：`dataset_id/features`，计算并保存新分析，返回完整散点和结构化摘要。
- `GET /analyses/{id}`：读取本会话已保存的分析。
- `POST /submissions`：`result_id/counts/description`，保存学生答案、真实结果摘要、分析列与数据版本。

SQLite新增`teaching_datasets`（含原始文件BLOB、解析记录、项目/会话/版本）与`teaching_analyses`。交付写入`teaching_submissions`。每次上传/运行生成独立UUID，不覆盖同名文件或其他学生数据。当前无登录，会话隔离不等于正式身份鉴权。

## 验证

后端目录`python -m pytest tests -q`；前端目录`npm run build`；根目录`node scripts/teaching_learning_state_smoke.mjs`。

浏览器：先运行`python scripts/library_fixture_server.py`（隔离数据库、8001；教学计算不调用其模型模拟器），前端设置`API_TARGET=http://127.0.0.1:8001`并运行5174，再运行`python scripts/teaching_excel_browser_smoke.py`。

浏览器验证从活动1实际计算/手填，经活动2真实拖动，到活动3上传152条记录、明确排除2条、对150条真实计算、作图、整数坐标刻度、并排手填、保存，以及坏文件、改列、重合数据和移动布局。后台测试另验证版本不覆盖、其他会话不可访问、上限与缺失/非数值处理。

流式对话验证：运行`python scripts/teaching_chat_fixture_server.py`，前端5174代理8001，执行`python scripts/teaching_chat_browser_smoke.py`。该fixture使用本地模拟模型供应商，经过实际模型SDK/SSE链路，不代表外部模型实测。
