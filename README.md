# Orbit · Agent-Based PBL Learning Workspace

教学Agent现支持三个活动：真实单轮分组计算、四步拖动排序、Excel上传与二维K-means散点图。学生自由提问调用后端配置的同一个LLM，以SSE流式回复，并结合当前活动和数据库里的真实计算摘要。教学对话不控制解锁或提交。活动与文件说明见[教学Agent说明](frontend/src/projects/teaching-agent/README.md)，模型规则和接口见[小知对话说明](backend/app/projects/teaching/CHAT.md)。

教学Agent路由`/projects/teaching-agent`，首页提供第三个入口；保留Three.js小知、任务/对话模式、思考/流式回复/暂停/错误状态。目前刷新按测试要求创建新会话，后台已入库的计算和聊天仍保留。启动前后端并配置`backend/.env`的`LLM_API_KEY/LLM_BASE_URL/LLM_MODEL`后使用；无密钥会明确报错，不回退到假回复。独立于原天文和图书馆项目。

小知主形象使用 Three.js 程序化3D模型，支持拖动旋转、复位、鼠标跟随、浮动眨眼和对话状态动作。`robotModel.ts`定义模型，`RobotScene.vue`负责灯光、动画、交互及资源释放。Three.js按需加载，聊天小头像继续使用SVG；无WebGL2或上下文丢失时回退到`TeachingRobotSvg.vue`。尊重减少动态效果设置，页面隐藏/形象离屏时暂停渲染，限制像素比及帧率。无需下载外部模型。首次拉取新版后先在`frontend`执行`npm ci`。3D验证：`scripts/teaching_robot_3d_smoke.py`，包含实际WebGL旋转、状态变化、上下文丢失与无WebGL回退。

Vue 3 + TypeScript + Element Plus + Vue Flow 学习工作台，FastAPI + LangChain Tool-Calling Agent，SQLite 持久化，POST SSE 事件流。默认进入项目首页，不包含登录或管理后台。

## 两个独立项目

| 项目 | 页面路由 | API 前缀 |
| --- | --- | --- |
| 天文观测（原项目保留） | `/projects/astronomy-lab` | `/api/projects/astronomy-lab` |
| 图书馆采购推荐（新增） | `/projects/library-recommendation` | `/api/projects/library-recommendation` |

访问 `/` 进入项目首页，固定顶部菜单下方展示 Project 1「天文观测」和 Project 2「图书馆采购推荐」两个入口。两个项目顶部均可返回首页或切换项目；配置、运行、学习进度按项目和会话隔离，原天文 SQLite 记录不迁移、不清除。`GET /api/projects` 返回项目名称和入口。

前端采用 Vue Router，`App.vue` 是路由出口，两个项目工作台分别位于 `src/projects/astronomy/Workspace.vue` 和 `src/projects/library/Workspace.vue`。部署时将前端路由回退到 `index.html`，保留 `/api` 后端代理。

### 图书馆学习流程

新项目包含 PDF 原有的四个递进活动，每个活动的材料、数据、工具权限和交付由后端控制。前端不以一个“完成”按钮直接修改进度。

1. **对图书进行分组**：提交计划后进入一维数轴，自选或随机选择两个中心点，每次只计算一轮。稳定时弹窗，点击确认保存结果并进入活动二。刷新后重新填计划、重新选点，不自动恢复旧计算。
2. **为计算助手编写步骤**：面向七年级，给出角色、任务与回答规则的半开放 System Prompt。学生拖动或上移、下移七个模块排序，实时生成 Prompt。保存后提交，后端检查步骤依赖关系，通过后解锁活动三。不再要求分组预测、核查文字或一次运行；可自愿运行真实模型检验 Prompt。
3. **用Agent完成二维分组**：沿用活动二的七步算法，选150条二维借阅记录和两个特征，K固定2。Agent实际调用数据查看和完整聚类工具，交付本次运行及工具确认的两组数量，合计150条。不再要求一维/二维对比，单独手动计算不能替代Agent运行。
4. **为图书馆作出采购决策**：导入用户提供的100条阅读兴趣调查，沿用算法Prompt，增加本活动决策要求，默认K=2。Agent使用真实工具结果给出采购类型、数量和依据，合计1000册；采购表从模型回答自动填入，学生可调整，最后填写一句话反思。

学生可返回已解锁活动修改并再次提交，每次交付保存独立版本。活动二提供独立排序模板；活动三、四继承模型、算法Prompt、步骤及工具开关，另设可编辑的本活动任务要求。新活动默认值首次访问后冻结，修改前面配置不会悄悄覆盖已保存的后续配置。最终交付校验会话、活动、当前配置版本、实际工具调用与数据版本。

各活动进入或刷新仍需确认统一的两题计划卡：开始任务前准备怎么做、得到结果后准备怎么检查。首次不预选；后续回填本项目上次选择，可直接沿用。仅修改已有选择时出现修改原因题，活动中也能打开“我的计划”调整。题卡不评分，也不会因选择不当阻止开始。

数据查看工具的手动测试和 Agent 调用使用同一后端工具；返回数据按会话、活动、数据版本隔离，工具禁用后不能发起新调用。活动一进入数轴时自动读取数据。其他活动可点击工具节点调用，或由模型真实 Tool Calling 获取数据。

图书馆画布包含“计算助手大脑”和两个工具：数据查看、完整聚类。活动二仅开放数据查看；活动三、四开放完整聚类。“一轮聚类计算工具”已从画布、模型工具列表及配置项移除，活动一数轴直接调用专用单轮接口。旧预测接口仅为历史兼容保留，不再用于活动二。

Excel 存于 `backend/datasets/library/`，字段和来源见 `manifest.json`：

| 文件 | 字段 | 来源 |
| --- | --- | --- |
| `library_sample_1d.xlsx` | `id,name,borrow_count` | 从提供的 PDF 第7页录入的五本书样本 |
| `library_sample_2d.xlsx` | `id,name,borrow_count,borrow_days` | 从 PDF 第13页录入的二维样本 |
| `library_books_2d.xlsx` | 原表“借阅次数、借阅时长”，读取时映射为标准字段 | 用户提供《活动3.部分图书馆书籍数据.xlsx》，150条记录，无书名；系统生成记录编号，原表未注明时长单位 |
| `reading_interest_students.xlsx` | 中文表头映射到 `content_preference,duration_preference` | 用户提供的100条阅读兴趣调查记录 |
| `reading_interest_demo.xlsx` | `id,name,content_preference,duration_preference` | 旧30条演示表，已从活动选项移除 |

阅读兴趣两个维度均为0–100：内容从文艺到知识，时长从短到长。活动四现使用用户提供的100条调查记录，原始中文表头经manifest映射，不虚构书名，也不把样本当成全校学生。原30条演示表退出活动选项，仅保留供旧记录追溯。

工作簿已随项目提供。若缺失，可在根目录运行 `.\.venv\Scripts\python backend/scripts/create_library_datasets.py` 创建；此脚本不会覆盖现有工作簿。

新增后端代码位于 `backend/app/projects/library/`；共享的数值计算在 `clustering.py`，使用 NumPy；Excel 使用 openpyxl。两种聚类复用相同的距离、分组、中心更新与停止逻辑。距离相同时归入编号较小的组；空簇保留原中心并警告；完整运行最多100轮。标准化采用总体标准差，零方差维度按1处理，图表和分组中心返回原量表坐标。中心稳定阈值为1e-8。

SQLite 增量新增 `library_configs`、`library_submissions`、`library_drafts`、`library_predictions`、`library_analyses`、`library_runs`、`library_plans`、`library_dataset_views`，不改动天文记录。新接口包括 `learning`、按活动读取/保存 `config`、`activities/{id}/plan`、`draft`、`submit`、`predictions`、`practice-steps/{prediction_id}`、`analyses`、`dataset`、`tools/inspect_dataset`（POST，真实工具测试）及活动运行历史；参数以 `/docs` 为准。

### 图书馆验证

运行下文 pytest 与前端 build 验证计算、权限和构建。浏览器完整流程使用明确的本地模型测试替身（不调用收费模型），仍经过真实 LangChain、两个工具及独立 SQLite：

```powershell
# 根目录，终端一：隔离的测试后端8001与模型fixture8899
.\.venv\Scripts\python scripts/library_fixture_server.py

# 终端二：测试专用前端5174，使用已安装的Node
cd frontend
$env:API_TARGET = 'http://127.0.0.1:8001'
npm.cmd run dev -- --port 5174 --strictPort

# 根目录，终端三：需要 playwright 与系统 Edge
.\.venv\Scripts\python scripts/library_browser_smoke.py
```

测试数据库与截图位于被忽略的 `test-results/`；测试不连接正式8000服务，不写原项目数据库。fixture 只用于测试，正常学习必须使用 `.env` 中的真实模型服务。正常 Vite 仍默认代理8000，请勿在正常启动终端保留测试专用的 API_TARGET（可执行 `Remove-Item Env:API_TARGET -ErrorAction SilentlyContinue` 清除）。

当前验证：后端41项测试通过，包含两项目兼容、真实数据聚类、分步解锁、累计计划、Agent工具证据、采购输出解析与总量校验、旧配置迁移及会话隔离；前端类型检查和生产构建通过。完整浏览器测试使用明确的本地模型替身，经真实LangChain、工具和SQLite完成四活动。

## 快速启动（Windows PowerShell）

使用锁文件安装需要 Python 3.12+、Node.js 20.19+ 或 22.12+。本次开发已在项目 `.venv` 安装 Python 依赖，并在 `.tools/node-v22.16.0-win-x64` 放置便携 Node。其他机器可使用系统 Node。

在项目根目录：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-lock.txt
Copy-Item backend/.env.example backend/.env
```

编辑 `backend/.env`，只在后端填写自己的服务配置：

```dotenv
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-tool-calling-model
LLM_MODELS=your-tool-calling-model,another-model
DATABASE_PATH=data/workspace.db
LLM_TIMEOUT_SECONDS=60
RUN_TIMEOUT_SECONDS=180
TOOL_TIMEOUT_SECONDS=25
OPEN_METEO_API_KEY=
NASA_CONTACT=
```

模型必须支持 OpenAI Chat Completions 的 `tools` / `tool_calls` 协议和可调 temperature；部分推理模型不接受 temperature，应选择兼容模型。模型列表来自服务端环境变量，不在前端填写密钥。存在 `backend/.env` 时，其显式配置优先于继承的环境变量；未创建该文件时直接读取环境变量。没有密钥仍可学习、编辑保存配置、查看历史；运行会输出明确的配置错误，不会切换到假 LLM。

终端一：

```powershell
cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

终端二，在根目录：

```powershell
# 如果未安装系统 Node，先执行下面一行
$env:PATH = "$PWD\.tools\node-v22.16.0-win-x64;" + $env:PATH
cd frontend
npm.cmd ci
npm.cmd run dev
```

打开 http://127.0.0.1:5173 。接口文档：http://127.0.0.1:8000/docs 。Vite 将 `/api` 代理到后端。配置环境变量后需要重启后端。

macOS/Linux 对应使用 `.venv/bin/python`，其余 npm 命令相同。SQLite 默认路径相对于后端启动目录，建议始终在 `backend` 目录启动；也可设置绝对 `DATABASE_PATH`。

## 使用与验收

1. 阅读左侧四步学习内容，完成步骤会持久化学习进度。
2. 点击 Brain 修改模型、System Prompt、Temperature，点击「保存配置」。
3. 点击 Weather/Astronomy 节点，切换启用状态、温度单位或观测设备。节点和连线即时反映状态。
4. 点击「试试示例」，会生成带明确日期、北京地点和当地时间的观测任务；点击 Run Agent 或 Ctrl+Enter。未保存的修改会先保存再运行。
5. 查看 LLM 状态、工具调用参数、工具结果和最终回答；工具执行时对应节点和连线高亮。工具调用顺序由模型决定，运行轨迹不展示隐藏推理。
6. 运行「什么是 Agent？」对比不需要工具的任务；也可禁用全部工具，验证纯模型回答。
7. 打开运行历史，选择一次记录查看轨迹及当时的配置快照；刷新页面保留配置、学习进度和最近一次运行。
8. 拖动左/右/底面板之间的细分隔线调整大小；画布可缩放、平移，但不允许删除节点或自由创建工作流。

两个工具均已接入真实 HTTP API，**没有 Mock 回退**。模型自主决定是否调用，后端按模型参数执行查询。

- **Weather Tool → Open-Meteo**：地点搜索转经纬度，再查询当地今天起未来 16 天内的逐小时温度、云量、降水概率、风速、能见度与昼夜标记，返回时区和单位。免费非商业使用无需 Key，`OPEN_METEO_API_KEY` 留空；商业订阅 Key 填入后会使用 customer 端点。[官网/文档](https://open-meteo.com/en/docs)、[商业订阅与 Key 入口](https://open-meteo.com/en/pricing)。免费接口有使用限额，数据需标明来源。
- **Astronomy Tool → NASA/JPL Horizons**：查询月球、木星、土星的站心方位角、地平高度、近似视星等和照明率，并查询太阳高度。输入时间必须带 UTC 偏移，后端统一转为 UT 查询。这个接口**不需要 NASA_API_KEY**；请将 `NASA_CONTACT` 填为自己的联系邮箱或项目联系网址（不是密钥），用于 JPL 要求的 User-Agent。未填写会明确返回工具错误。[Horizons 官方文档](https://ssd-api.jpl.nasa.gov/doc/horizons.html)、[服务使用要求](https://ssd-api.jpl.nasa.gov/doc/)。[NASA 通用 API Key 申请](https://api.nasa.gov/)用于其他要求 Key 的 NASA 服务，不用于本工具。

地点可输入城市名或 `latitude,longitude`。同名地点会要求确认；无法搜索到中文城市时可提供英文城市名或坐标。坐标未带海拔时采用海平面 0 米；城市搜索使用地名数据的海拔。星历为无大气折射的计算结果，天气为预报，两者都不是现场实测。天体高于地平线不等于一定可见，还需结合天光、天气、遮挡和设备。设备选择作为模型建议的上下文，不改变星历计算，也不计算光学分辨率。

后端对地点缓存 24 小时、天气缓存 10 分钟、指定时刻的星历缓存 24 小时，缓存上限 256 条；JPL 请求按进程串行发送。V1 应使用单个 Uvicorn worker，多进程部署需共享限流器。上游限流、网络错误、缺测、日期越界和响应格式变化都会明确反馈，不生成假数据。旧会话 Prompt 保留，运行时会补充当前真实 API 的环境说明；历史 Mock 运行仍保留原始记录。

## 结构

```text
frontend/src/
  App.vue / main.ts / router.ts   应用启动与路由汇总
  pages/
    home/ProjectHome.vue         项目首页
    NotFound.vue                 未找到页面
  projects/
    astronomy/                   天文项目
      Workspace.vue / routes.ts / api.ts / types.ts
    library/                     图书馆项目
      Workspace.vue / routes.ts / api.ts / types.ts
      useLibrary.ts / library.css
      CenterExperiment.vue / AnalysisViewer.vue
  shared/
    api.ts / types.ts            HTTP、SSE、会话与公共事件类型
    components/AgentNode.vue      共用画布节点
    styles/workspace.css         基础主题与工作台通用样式
backend/app/
  main.py                        环境加载、生命周期与路由挂载
  projects/
    registry.py                  首页项目列表 API
    astronomy/
      routes.py / project.py / schemas.py
      runtime.py / tools.py / services.py
    library/
      routes.py / project.py / schemas.py
      tools.py / engine.py / clustering.py
      datasets.py / state.py
  shared/
    settings.py                  模型环境配置
    runtime.py                   通用 LangChain 执行器与事件转换
    store.py                     SQLite 公共存储
backend/datasets/library/         图书馆 Excel 与 manifest.json
backend/data/workspace.db         本地数据库（未迁移、未清空）
backend/tests/                    API、持久化、工具和 Agent 协议测试
```

前后端均按项目组织，项目内容、工具和页面在各自文件夹维护。修改天文默认 System Prompt：`backend/app/projects/astronomy/project.py`；修改图书馆学习活动：`backend/app/projects/library/project.py`。共享模块不依赖具体教学项目。

| 页面 / API | 地址 | 路由文件 |
| --- | --- | --- |
| 首页 | `/` | `frontend/src/router.ts` |
| 天文工作台 | `/projects/astronomy-lab` | `frontend/src/projects/astronomy/routes.ts` |
| 图书馆工作台 | `/projects/library-recommendation` | `frontend/src/projects/library/routes.ts` |
| 项目列表 | `/api/projects` | `backend/app/projects/registry.py` |
| 天文接口 | `/api/projects/astronomy-lab/*` | `backend/app/projects/astronomy/routes.py` |
| 图书馆接口 | `/api/projects/library-recommendation/*` | `backend/app/projects/library/routes.py` |

新增项目时，在两端各自的 `projects/` 下建立模块，前端将项目路由加入 `router.ts`，后端在 `main.py` 挂载路由并在 `registry.py` 注册项目。首页入口在 `pages/home/ProjectHome.vue` 维护。当前访问地址、会话标识、数据库表、后端 `.env` 和启动命令保持不变，目录调整后重启前后端即可。

## API 与记录

项目路径为 `/api/projects/astronomy-lab`。除项目内容与健康检查外，请求需携带 `X-Session-ID`。前端用浏览器生成的 UUID 保存在 localStorage，刷新延续同一会话；清理浏览器存储或更换浏览器会开始新会话。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 后端状态及是否配置密钥（不返回密钥） |
| GET | `/api/projects/{id}` | 学习材料、工具参数、可选模型 |
| GET / PUT | `…/config` | 读取 / 保存配置，记录字段差异 |
| POST | `…/runs` | 接受 input + config，返回 SSE |
| GET | `…/runs` | 当前会话最近 50 次运行 |
| GET | `…/runs/{run_id}` | 运行事件、结果和配置快照 |
| GET / POST | `…/activities` | 查询行为日志 / 记录步骤完成 |

SSE 以 `data: {id,run_id,type,data,timestamp}\n\n` 返回，事件类型包括 `run_start`、`llm_start`、`llm_end`、`tool_call`、`tool_result`、`tool_error`、`final`、`error`、`done`。以模型/工具级事件流输出，不做逐 token 输出，便于兼容不同供应商。停止或断开连接会取消运行并记录 cancelled；后端重启时未完成运行标为 interrupted。

SQLite 四表：configs、runs、events、actions。记录 UTC 时间、项目 ID、会话 ID，前端按浏览器本地时间显示。保存配置时记录字段 before/after（包括 Prompt、模型/参数和工具开关）；点击运行记录输入、完整配置快照及执行事件。日志含学生输入和 Prompt，适合本地教学开发。

无登录版本的会话 ID 只是记录隔离标识，不能作为正式鉴权。服务默认绑定 localhost；集成已有 PBL 平台时，由平台提供认证和学生身份映射。勿直接将此开发服务暴露为公网多用户服务。

## 测试

```powershell
cd backend
..\.venv\Scripts\python -m pytest tests -q
cd ../frontend
npm.cmd run build
```

`test_workspace.py` 覆盖配置日志、会话隔离、输入校验、SSE 成功与错误、历史快照、步骤记录和工具配置。

`test_runtime.py` 使用真实 LangChain Agent、真实 ChatOpenAI 客户端和本地 HTTP **测试替身**，验证两轮 Chat Completions、双工具请求、外部接口适配、SSE 与 SQLite 持久化。`test_services.py` 使用 HTTP 测试替身验证单位、时区、坐标顺序、星历字段、缺测、限流、错误脱敏和缓存。这些离线测试不消耗 API 额度，也不证明外部模型表现。

实际工具检查（不调用大模型）：在 backend 执行 `..\.venv\Scripts\python smoke_tools.py --weather-only`；填写 `NASA_CONTACT` 后执行 `..\.venv\Scripts\python smoke_tools.py` 验证两个真实工具。默认使用北京坐标与明天北京时间 20:00，可用 `--location "城市或经纬度"` 覆盖地点。实际 Agent 检查：执行 `..\.venv\Scripts\python smoke_live.py`，会产生模型调用费用，输出仅含事件类型和回答长度。

可选浏览器测试：在后端运行且模型服务返回错误（例如缺少 Key）的开发环境中，安装 `pip install playwright` 并使用系统 Edge，根目录执行 `.\.venv\Scripts\python scripts/browser_smoke.py`。覆盖节点配置、工具开关、保存与刷新、学习进度、SSE 错误反馈、历史快照和面板拖动；截图输出到 `test-results/workspace.png`。

API 接入验证：后端 17 项离线测试通过，TypeScript 检查和 Vite 生产构建通过；Open-Meteo 实际联网返回北京坐标的 24 小时预报；使用配置的 NASA_CONTACT 实际查询月球、木星、土星和太阳成功，取得方位角、地平高度、视星等和照明率。兼容 Horizons 实际服务返回的 1.2 与文档标注的 1.3 版本。以上工具验收没有调用大模型。生产构建仍有 Element Plus 整包引入导致的大文件提示，后续集成时可按需导入以减小体积。

生产构建输出 `frontend/dist`。由现有平台或静态服务器托管，并将 `/api` 反向代理到 FastAPI；SSE 路由需关闭代理缓冲，超时大于 RUN_TIMEOUT_SECONDS。`vite preview` 仅用于静态产物预览，不作为生产服务器。

实现参考：[LangChain create_agent 官方 API](https://reference.langchain.com/python/langchain/agents/factory/create_agent)、[Vue Flow 官方指南](https://vueflow.dev/guide)。

活动一新增 `POST /api/projects/library-recommendation/activities/group_books/center-steps?revision=0`，输入 `centers: [2, 11]` 和可选 `previous_step_id`。续轮必须使用上轮未舍入中心；验证计划、会话、配置和数据版本。无需预测记录。活动一进入实验时自动调用数据查看工具，活动二改为七模块排序，不再使用预测核查流程。浏览器单项验证：`python scripts/center_browser_smoke.py`（测试服务8001/5174）。

活动二模板和七模块定义：`backend/app/projects/library/prompt.py`；排序界面：`frontend/src/projects/library/PromptSteps.vue`。`config.prompt_steps` 保存步骤ID顺序；保存接口按该顺序生成 `system_prompt`，提交接口验证准备、计算距离、分组、更新与迭代的先后依赖。数据准备与确定中心数量可以交换先后。已保存的旧自定义 Prompt 保留，首次参与新排序后由新模板生成。

### 活动三的数据表选择

点击数据查看工具，在“选择数据表”中选择五本书一维样本或新增的150条二维数据，再调用工具。完整聚类节点显示同一选择；切换表会同步字段并清空当前的结果/比较选择，配置保存后刷新仍保留所选表。数据预览最多30行，聚类计算使用整张表的有效行，不是只计算预览。

`GET /api/projects/library-recommendation/activities/{activity}/datasets` 返回本活动允许的数据表元数据，不返回原始行。`GET …/dataset?dataset_id=…` 获取所选表的字段、行数与已有工具缓存；未调用时预览为空。手动测试与真实 Agent 的 `inspect_dataset` 均读取已保存选择；模型不能越权改为其他表。活动一、二只开放原始五本书表，活动四只开放阅读兴趣表，避免跨活动取数。

以后增加三维表：把工作簿放入 `backend/datasets/library/`，在 `manifest.json` 注册新ID，设置 `activities`、`features`、`column_map` 和新列的 `field_definitions`（`label`、`unit`、可选`range`）。数据选择列表由注册项生成，支持1–3个特征的实际计算；三维结果当前以首两个特征的二维投影呈现，并明确标注，中心仍显示所有坐标。本次未添加虚构三维教学数据。

活动三交付改为Agent对150条二维数据的两组数量，不再要求两次实验或比较文字。

五本书二维样本已退出所有活动的可选列表，原文件仅供旧运行记录追溯。已保存该选择的活动三配置会自动切换到150条二维表并增加配置版本，避免旧运行证据被当成新配置结果。

### 决策输出与计划复用

`config.system_prompt` 保存继承的算法步骤，`config.task_prompt` 保存本活动任务；运行时一并提供给模型。活动三、四均要求本次真实Agent调用数据查看及完整聚类，手动运行工具、旧配置运行或其他会话的运行不能用于交付。活动三结果数来自实际工具记录；活动四模型按JSON契约输出 `answer/purchases/rationale`，后端校验分组覆盖、非负整数与1000册总量，再通过SSE `final.decision` 返回。格式缺失或总数错误会明确报错，不补造模型建议。

交付只需选择运行：活动三后端自动保存 `group_counts/total/agent_answer`；活动四自动带入模型采购表、依据，允许学生调整并填写 `reflection`，同时保留原始 `agent_decision`。旧演示数据配置会自动迁移到实际调查表并增加配置版本，既有运行快照不修改。

旧文字计划接口保留用于历史兼容。新界面使用统一结构化题卡，不再按字数填写或拼接长段计划。旧文字不会自动转换为选择；首次替换时归档原文。

活动四按学生实际选择的数据表与特征分析、交付，不限定阅读兴趣表或100条记录。错误的数据选择也是学习证据，系统不会自动换表；仍检查运行归属、配置/数据版本、真实工具执行及采购表的数量格式与1000册总量。选择是否适合任务由学生反思和教学评价判断。后端35项测试通过。

模型输出默认上限1200 tokens（LLM_MAX_OUTPUT_TOKENS），普通回答要求不超过200个汉字；LLM_MAX_RETRIES默认0，避免超时后反复等待。聚类工具向模型仅返回分组数量、中心等摘要，完整逐行数据与迭代记录仍存SQLite供前端读取。模型服务超时会单独提示；这些设置不能保证消除上游服务延迟。

### 统一两题计划卡

四个活动共用 `PlanCard.vue`，后端题项与类别定义在 `plans.py`。两题均单选，每题三个选项，首次不预选；修改已有选择才显示三个修改原因选项，不要求为了过关修改。关闭未保存的编辑不改变原计划，活动中保存计划不重置当前实验。

`POST …/activities/{activity}/plan-card` 接收 `strategy/check/reason/phase/base_version`；`phase=before` 表示活动前确认，`during` 表示从“我的计划”进行调整。`GET …/learning` 中 `plan_card` 是项目当前版本，`GET …/plan-history` 返回当前会话的版本历史。版本冲突返回409，避免不同页面覆盖。`library_plan_versions` 按项目、会话和版本保存全部确认，记录初始、沿用、修改、未改动确认、变更字段、原因及时间。阶段和原因来自交互自报，不能当作独立验证的心理过程；选项无能力分数。

旧文字计划兼容原活动门槛和历史数据，新题卡首次替换该活动旧计划时将原文保存在 `legacy_plan_text`，不猜测选项。Agent运行快照与分析结果保存 `plan_version`，便于按时间关联计划与实际行为。研究上属于待验证的情境化支架，不能直接视为已验证的SRL量表。

浏览器专项验证：`python scripts/plan_card_browser_smoke.py`（隔离测试服务8001/5174），覆盖初始必选、原因题条件、活动中保存不丢实验、跨活动沿用、刷新与历史版本。

### 学生填写与提交结果展示

活动一达到稳定后，点击“填写结果”，学生自行填写两组数量和最终中心；后端保存 `student_result`，工具结果另存 `tool_result`，不替换学生的答案。活动三填写 `group_counts`（合计150），实际工具数量另存 `tool_group_counts`。活动四展示只读Agent参考建议，学生填写空白的采购类型与数量，保留原 `agent_decision` 与学生采购表；数量需为整数且合计1000，仍需反思。活动二保留学生排序生成的系统指令作为交付。

各活动提交后均展示“提交成功”及学生提交内容，点击后才进入下一活动。已提交活动的“我的交付”可再次查看，刷新后可恢复。填写草稿与最终答案分开存储，空白或数量合计不完整不能提交，分组和中心是否正确不在后台自动纠正。

### 测试阶段刷新清空进度
本地 backend/.env 已开启 LIBRARY_RESET_ON_REFRESH=true；示例配置默认false。开启后，刷新图书馆工作台会在加载学习状态前，通过 POST /api/projects/library-recommendation/testing/reset-progress 清空当前会话的交付、草稿与计划，从活动1开始。仅刷新触发，同一页面内切换活动或返回首页不会反复重置。模型配置、运行/分析历史与其他会话、天文项目保留。正式使用时设为false并重启后端，关闭时重置接口返回403。验证：43项后端测试、前端构建与 scripts/library_refresh_reset_smoke.py 浏览器测试通过。

查看数据工具只打开数据表，不自动切换画布。活动三、四提交本次分析产出后才展示对应运行的散点图；未提交时“分析结果”入口禁用，不自动展示历史计算。学生填写的数量与实际聚类图分开展示，图表使用交付关联运行的真实样本和分组，不根据数量凭空构造点。

测试模式 `LIBRARY_RESET_ON_REFRESH=true`：每次进入图书馆项目或刷新，清空当前会话的计划、交付、配置、数据预览、聚类与运行记录，从活动1重新开始；同次学习内的活动切换保留成果。活动4的分配依据和反思须由学生填写，各至少10个非空白字符。

模型回答使用真实流式请求，经SSE的 `llm_delta` 事件逐步显示；采购任务只显示JSON中的回答文字，最终采购结构仍由后端完整校验。右下角提供提交结果、查看我的计划、查看我的提交；计划展示累计版本，交付按活动汇总并展示对应散点图。聚类仅通过智能体工具调用运行，界面不再提供绕过智能体的“运行聚类实验”按钮。
