# 运行结果

先看哪个：想了解漏洞，看根目录的 [REPORT.md](../REPORT.md)。想看 Agent 一次完整运行的原始产出，看 [`run-20261021-r3/report.md`](run-20261021-r3/report.md)。

| 目录 | 目标 | 审计员 / 复核员 | 说明 |
| --- | --- | --- | --- |
| [`run-20261021-r1`](run-20261021-r1/report.md) | ylinux_old | `deepseek-v4-pro` / 同一模型 | 当前代码，第 1 次 |
| [`run-20261021-r2`](run-20261021-r2/report.md) | ylinux_old | `deepseek-v4-pro` / 同一模型 | 当前代码，第 2 次 |
| [`run-20261021-r3`](run-20261021-r3/report.md) | ylinux_old | `deepseek-v4-pro` / 同一模型 | 当前代码，第 3 次；README 里 `replay` 的例子用的就是这次 |
| [`run-20261021-kimi`](run-20261021-kimi/report.md) | ylinux_old | `deepseek-v4-pro` / `kimi-k3` | 当前代码，复核员换模型 |
| [`nv-20261021`](nv-20261021/report.md) | django.nV | `deepseek-v4-pro` / 同一模型 | 泛化测试，代码和提示词都没改 |
| [`run-20261021`](run-20261021/report.md) | ylinux_old | `deepseek-v4-pro` / 同一模型 | 加 `list_endpoints`、`entry_role`、`weakest_point` 之前的版本。后来用 `verify` 按新格式重新生成了报告。那时还没有录制功能，所以没有 `llm_responses.jsonl` |
| [`run-20261020`](run-20261020/report.md) | ylinux_old | SiliconFlow `DeepSeek-V3` | 第一版，还没有门禁。原样保留用来对比，报告是旧格式，也没有录制 |

打分汇总：

- [`EVALUATION.md`](EVALUATION.md)：ylinux_old，包含 r1–r3 的均值、标准差，以及每条真值被找到的次数。
- [`EVALUATION-django.nV.md`](EVALUATION-django.nV.md)：django.nV。

每个运行目录里的文件：

| 文件 | 内容 |
| --- | --- |
| `report.md` | 报告正文：发现总表，以及每条发现的证据、数据流、入口身份和复核意见 |
| `appendix.md` | 统计数字、线索处置表、阶段记录、读过的文件、完整工具序列、引用核对结果 |
| `decisions.md` | 关键节点：门禁拒绝、写入被退回、复核时指出的最弱一环、缺口和改判 |
| `REVIEW.md` | 对照真值打分：逐条判定、漏报、踩中的陷阱 |
| `findings.json` | 模型写入的发现。打分不会改这个文件 |
| `state.json` | 结束时的审计状态，含线索处置和复核历史 |
| `trajectory.md` / `trace.jsonl` | 每一步调了哪个工具、参数、返回结果的开头部分和推理节选 |
| `llm_responses.jsonl` | 模型每次响应的原文，`replay` 靠它离线重放 |
| `verification.json` | 每条引用是否真的出现在它声称的行号上 |
| `meta.json` | 两个角色各自用的模型和接口，以及 commit、预算、token、完整工具序列。不含密钥 |
| `evaluation.json` | 逐条判定，机器可读格式 |

注意：引用对得上，不代表分类就是对的。误判、漏报以及原因写在 [DESIGN.md](../DESIGN.md)。
