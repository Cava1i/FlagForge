# FlagForge 前端

这是 FlagForge 本地 Web 控制台的 Vue 3 + Vite 前端。界面用于创建和导入 CTF 题目、编辑题目信息、上传附件文件、启动单题运行、查看运行历史和实时日志。

## 开发启动

先在仓库根目录安装依赖：

```bash
uv sync
npm --prefix frontend install
```

一键启动后端和前端：

```bash
./start.sh
```

默认访问 `http://127.0.0.1:5174`，脚本会把前端 `/api` 请求代理到
`http://127.0.0.1:5001`，并把日志写入根目录 `logs/`。

如果端口被占用：

```bash
BACKEND_PORT=5002 FRONTEND_PORT=5175 ./start.sh
```

## 手动创建题目

在“题目”页面的“手动创建题目”区域填写：

- 目录名 `slug`
- 题目名称、分类、分值、标签、连接信息、题目描述
- 附件文件 `distfiles`
- 每个附件的保存文件名

提交后，后端会写入：

```text
challenges/<slug>/metadata.yml
challenges/<slug>/distfiles/<文件名>
```

示例目录见 `../examples/manual-challenge/`。

## API 配置

侧栏进入“设置”页面后，可以配置模型 API 和 CTFd 凭据。密钥字段不会回显已有值：

- 输入新值并保存：更新 `.env`
- 留空：保持已有密钥不变
- 勾选“清空”：删除该密钥值

非敏感字段会直接显示当前值，例如 `ANTHROPIC_BASE_URL` 和 `CTFD_URL`。

## 构建

```bash
npm --prefix frontend run build
```

构建产物在 `frontend/dist/`。运行 `uv run python -m backend.web.app` 后，Flask 会直接服务构建后的前端页面。
