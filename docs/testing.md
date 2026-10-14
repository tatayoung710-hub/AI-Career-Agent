# 验证结果与边界

本地验证（2026-10-14）：

| 范围 | 方法 | 结果 |
|---|---|---|
| 后端代码规范 | `python -m ruff check app tests` | 通过 |
| 后端工作流 | `python -m pytest -q tests` | 5 项通过 |
| 前端类型与生产构建 | `pnpm build`（`tsc -b && vite build`） | 通过 |
| 模块加载 | 导入 FastAPI app | 10 条 API 路由组装成功 |
| OpenAI 在线请求 | 未配置用户 API Key | 未执行；缺少密钥时端点返回 503 |
| Docker Compose / 真实 PostgreSQL | 本机未安装 Docker | 未执行；CI 启动 PostgreSQL 17 作验证 |
| 招聘网站/公众号/小程序投递 | 无授权连接器及账户 | 未执行；不计为已提交 |

后端测试覆盖兴趣不能当工作经历、未确认事实和无依据数字不能进入简历、TXT 简历上传、来源目录、岗位和投递状态流转、乐观锁冲突、1000 条目标策略、同一日期批次幂等，以及 AI 未配置时的明确错误。

GitHub Actions 对真实 PostgreSQL 17 执行 Alembic upgrade/check、Ruff 和 pytest，并构建前端。首次运行在发布后自动启动；请在仓库的 Actions 页面查看最终状态，不以“已触发”代替“已通过”。

当前尚未覆盖浏览器端到端测试、人工视觉 QA、PostgreSQL 并发压力测试和真实邮件沙箱测试。部署前需要加入备份/恢复演练、限流监控、文件保留期限、AI 内容审核和依赖安全扫描。

PDF / DOCX / TXT 支持文本提取；加密/损坏文件会报错，扫描 PDF 需要用户先做 OCR。来源通用抓取使用来源类型和主机允许列表限制。公众号和小程序以人工导入为主；BOSS 仅保留岗位入口与材料准备。SMTP 开启也需要服务端密钥、精确招聘地址 allowlist 与策略许可，`mail_accepted` 不是 `application_received`。
