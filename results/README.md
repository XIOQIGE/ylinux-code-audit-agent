# 运行结果

| 目录 | 目标 | 审计员 / 复核员 | 说明 |
| --- | --- | --- | --- |
| [`run-20261021-r1`](run-20261021-r1/report.md) | ylinux_old | `deepseek-v4-pro` / 同一模型 | 当前代码，重复运行 1 |
| [`run-20261021-r2`](run-20261021-r2/report.md) | ylinux_old | `deepseek-v4-pro` / 同一模型 | 当前代码，重复运行 2 |
| [`run-20261021-r3`](run-20261021-r3/report.md) | ylinux_old | `deepseek-v4-pro` / 同一模型 | 当前代码，重复运行 3；`replay` 示例用这一次 |
| [`run-20261021-kimi`](run-20261021-kimi/report.md) | ylinux_old | `deepseek-v4-pro` / `kimi-k3` | 当前代码，换模型复核 |
| [`nv-20261021`](nv-20261021/report.md) | django.nV | `deepseek-v4-pro` / 同一模型 | 代码和提示词不变的泛化检验 |
| [`run-20261021`](run-20261021/report.md) | ylinux_old | `deepseek-v4-pro` / 同一模型 | 加 `list_endpoints`、`entry_role`、`weakest_point` 之前；已用 `verify` 按新格式重新渲染；录制重放是之后加的，这次没有 `llm_responses.jsonl` |
| [`run-20261020`](run-20261020/report.md) | ylinux_old | SiliconFlow `DeepSeek-V3` | 门禁加入前，原样保留作对照，报告格式是旧版，没有录下的响应 |

打分：[`EVALUATION.md`](EVALUATION.md)（ylinux_old，含 r1–r3 的均值、标准差和每条真值的命中次数）、[`EVALUATION-django.nV.md`](EVALUATION-django.nV.md)。

每个运行目录里：

| 文件 | 内容 |
| --- | --- |
| `report.md` | 给人读的报告：发现总表，以及逐条的证据、数据流、入口身份、复核意见 |
| `appendix.md` | 统计、线索处置表、阶段申报、读过的文件、完整工具序列、引用核对结果 |
| `decisions.md` | 门禁拒绝、写入被退回、复核的最弱一环、缺口和改判 |
| `REVIEW.md` | 对照真值的外部评审：逐条判定、漏报、踩中的陷阱 |
| `findings.json` | 模型写入的发现，打分没有改这个文件 |
| `state.json` | 结束时的审计状态（含线索处置和复核历史） |
| `trajectory.md` / `trace.jsonl` | 每一步选了哪个工具、参数、观察预览和推理节选 |
| `llm_responses.jsonl` | 每次模型响应的原文，`python -m audit_agent replay <目录>` 用它离线重放 |
| `verification.json` | 每条引用是否出现在声称的行号里 |
| `meta.json` | 两个角色的模型、接口、commit、预算、token、完整工具序列。没有密钥 |
| `evaluation.json` | 对照真值的逐条判定（机器可读） |

引用对上不等于分类正确。误判、漏报和它们的原因写在仓库根目录的 [DESIGN.md](../DESIGN.md)。
