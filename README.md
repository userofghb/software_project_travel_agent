# 智能旅行助手

这是一个智能体旅行规划项目。用户填写出发地、目的地、日期、预算和偏好后，系统会在后台生成一份可查看、可追踪版本的旅行方案。项目为软件工程课程期末项目。

## 主要功能

- 用户注册、登录和 JWT 鉴权
- 个人偏好维护，包括旅行风格、预算、交通、住宿和兴趣标签
- 创建旅行方案，支持异步生成和任务进度查看
- 方案详情展示，包括每日行程、餐饮、住宿、预算、地图点位和天气提示
- 历史方案管理，支持方案列表、搜索、删除
- 版本管理，支持编辑、恢复、基于旧版本重新生成
- PDF 导出
- 自然语言补充需求解析，用于提取预算、交通和住宿偏好

## 技术栈

后端：

- FastAPI
- SQLModel / SQLAlchemy
- MySQL
- LangGraph
- Pydantic
- python-jose
- ReportLab

前端：

- React
- TypeScript
- Vite
- Ant Design
- React Router
- React Query
- Zustand

## 项目结构

```text
.
|-- backend/                 # FastAPI 后端
|   |-- app/
|   |   |-- agents/          # 旅行规划流水线
|   |   |-- api/             # 路由
|   |   |-- core/            # 配置和安全相关代码
|   |   |-- db/              # 数据库模型和会话
|   |   |-- dto/             # 请求/响应模型
|   |   |-- repositories/    # 数据访问层
|   |   `-- services/        # 业务逻辑
|   |-- scripts/             # 初始化和 OpenAPI 导出脚本
|   `-- tests/               # 后端测试
|-- frontend/                # React 前端
|   |-- src/
|   |   |-- api/             # 前端 API 封装
|   |   |-- components/
|   |   |-- pages/
|   |   |-- router/
|   |   `-- store/
|   `-- package.json
|-- database/                # MySQL 建表和种子数据
|-- start_backend_8000.cmd
`-- start_frontend_5173.cmd
```

## 本地运行

下面的命令以 Windows / PowerShell 为例。其他系统的命令基本一致，只是路径写法不同。

### 1. 准备 MySQL

项目默认使用 MySQL，数据库名为 `travel_agent`。先确认本机 MySQL 已启动，然后创建数据库：

```powershell
mysql -u root -p
```

```sql
CREATE DATABASE IF NOT EXISTS travel_agent
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

如果希望直接执行项目里的初始化脚本，可以先配置好 `backend/.env`，再运行：

```powershell
python backend\scripts\init_mysql.py
```

### 2. 配置后端环境变量

复制示例文件：

```powershell
copy backend\.env.example backend\.env
```

至少需要确认下面几项：

```env
SECRET_KEY=change-me-in-development
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/travel_agent?charset=utf8mb4
AGENT_PROVIDER_MODE=mock
OPENAI_API_KEY=
AMAP_API_KEY=
```

说明：

- 本地调试建议先用 `AGENT_PROVIDER_MODE=mock`，这样不依赖外部 API。
- 如果要接入真实 LLM、高德地图或天气能力，再填写对应 key，并把 provider 模式改成实际需要的值。
- 不要把自己的 `.env` 提交到仓库。

### 3. 安装后端依赖

```powershell
cd backend
python -m pip install -r requirements.txt
```

启动后端：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

正常情况下会返回：

```json
{"status":"ok"}
```

### 4. 安装前端依赖

```powershell
cd frontend
npm install
```

启动前端：

```powershell
npm run dev -- --host 127.0.0.1
```

浏览器打开：

```text
http://127.0.0.1:5173
```

前端默认请求：

```text
http://127.0.0.1:8000
```

如果后端地址有变化，可以在 `frontend/.env` 中设置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 常用脚本

后端测试：

```powershell
cd backend
python -m pytest tests -q
```

前端构建：

```powershell
cd frontend
npm run build
```

从后端 OpenAPI 重新生成前端类型：

```powershell
cd frontend
npm run generate:types
```

也可以使用根目录下的两个启动脚本：

```powershell
start_backend_8000.cmd
start_frontend_5173.cmd
```

## 接口概览

主要接口都以 `/api` 开头：

- `POST /api/auth/register`：注册
- `POST /api/auth/login`：登录
- `GET /api/auth/me`：当前用户信息
- `GET /api/profile/me`：读取个人偏好
- `PUT /api/profile/me`：更新个人偏好
- `POST /api/plans/parse`：解析补充需求
- `POST /api/plans`：创建方案生成任务
- `GET /api/tasks/{task_id}`：查询任务状态
- `GET /api/plans`：方案列表
- `GET /api/plans/{plan_id}`：方案详情
- `GET /api/plans/{plan_id}/versions`：版本列表
- `POST /api/plans/{plan_id}/versions/{version_id}/regenerate`：基于旧版本重新生成
- `GET /api/plans/{plan_id}/versions/{version_id}/export`：导出 PDF

完整接口可以在后端启动后访问：

```text
http://127.0.0.1:8000/docs
```

## 数据库表

当前核心表包括：

- `users`
- `user_profiles`
- `trip_plans`
- `trip_plan_versions`
- `plan_tasks`

方案内容使用 JSON 字段保存，便于存储每日行程、预算拆解、天气信息、地图点位和版本内容。
