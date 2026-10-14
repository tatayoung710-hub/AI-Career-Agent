# 架构与技术决策

React + TypeScript + Tailwind/Vite → FastAPI模块化单体 → PostgreSQL。
独立Python Worker处理持久化任务，并按Asia/Shanghai生成每日批次。
文件保存挂载卷，AI通过OpenAI Provider访问，所有敏感配置留在后端环境变量。

## ADR 001：模块化单体

个人维护项目优先保证用户隔离、版本和事务的一致性；将耗时任务独立运行。
明确模块边界后可按实际扩容需要拆分，不预先引入微服务。

## ADR 002：持久化数据库队列

初稿提出Celery/Redis，实施时选择PostgreSQL任务表与独立Worker。
千条每日任务规模较小，统一账本便于事务写入、检查点和恢复，也降低本地服务数量。
生产认领使用行锁及SKIP LOCKED；租约、尝试上限和幂等键必须配合。
SQLite仅用于单Worker本地开发，不代表验证了生产并发行为。

## ADR 003：AI输出需要两层验证

结构化输出确保数据形状；业务验证检查引用、事实类型、数字与支持程度。
自然语言事实忠实性不能靠JSON Schema证明，保留用户审阅、禁止无依据自动批准。
资料/JD/聊天中的指令属于待分析内容，不能改变系统边界。

## ADR 004：不可变版本

事实、JD和简历以版本存储；分析绑定快照，投递绑定具体简历版本。
更改内容创建新版本，避免历史记录受后续编辑影响。

## ADR 005：至少一次执行

数据库业务结果使用幂等约束。外部AI或提交请求超时可能已被接收，不能承诺零重复计费。
提交结果未知先对账，不自动再次发送；验证码、限制或登录失效暂停渠道。

## 官方技术参考

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
- [PostgreSQL SELECT / SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [FastAPI](https://fastapi.tiangolo.com/)

参考项目仅用于产品设计学习，代码独立实现：ResumeForge、auto-job-apply、GeekGeekRun。
