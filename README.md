# 隧道收敛测缝台

测量员登记里程桩号与收敛毫米值。接口进程内后台线程认领待判行（不另起 worker 容器），按绝对值是否不超过 3.0 mm 给出合格或超限。页面是 Svelte。

## 交班签出简报

页眉「交班签出」进入专页，含生成按钮、历史清单、正文预览三块：

- 测量员点「生成交班简报」，服务端把**按下瞬间**的合格 / 超限 / 待办统计与最近 3 笔提要组成正文，冻结写入 `shift_briefings` 表；当班一张单都没有也可生成，计数为零。
- 已生成简报只读：之后线上再交新单、判定翻转，都不会回改已冻结的正文与计数。二衬交班同走此一份简报，不另开旁路。
- 巡检员（inspector）可阅读历史简报与正文，不能点生成（接口返回 403）。

| 接口 | 说明 |
|------|------|
| `POST /api/briefings` | 生成冻结简报（仅测量员） |
| `GET /api/briefings` | 历史清单（登录即可，不含正文） |
| `GET /api/briefings/<id>` | 单份简报含冻结正文（登录即可） |

## 技术栈

- 后端：Flask、Gunicorn、SQLAlchemy、进程内认领线程
- 前端：Svelte、Vite、nginx 反代 `/api`
- 数据库：PostgreSQL 16

## 端口

| 服务 | 地址 |
|------|------|
| 页面 | http://localhost:3201 |
| 接口 | http://localhost:8201 |
| PostgreSQL | localhost:54401（库名 `tunnelconv`） |

## 账号

| 用户 | 密码 | 权限 |
|------|------|------|
| surveyor | surv123456 | 可提交读数、可生成交班简报 |
| inspector | insp123456 | 只读（含已生成简报），不可生成 |

## 启动

```bash
cd projects/21-tunnel-convergence-desk
docker compose up --build
```

健康检查：`GET http://localhost:8201/api/health`

## 种子

| 桩号 | 收敛 | 结论 |
|------|------|------|
| K12+180 | 1.2 mm | 合格 |
| K18+040 | 5.6 mm | 超限 |
