# 代码审计 Agent（ylinux_old）

一个由模型自己选工具、自己决定顺序的应用安全审计 Agent。审计员（auditor）读代码、记录发现；另一个独立的复核员（critic）逐条复核。它们之间的往返由门禁驱动：门禁卡的是“这类工作做没做”，不规定先做哪一步。主目标是 [gwind/ylinux_old](https://github.com/gwind/ylinux_old)（Django 1.2 / Python 2）。在完全不改代码和提示词的前提下，还跑了第二个目标 [nVisium/django.nV](https://github.com/nVisium/django.nV)。

## 三条命令

```powershell
pip install -e ".[dev]"; copy .env.example .env   # 在 .env 里填 DEEPSEEK_API_KEY
python -m audit_agent run                           # 克隆 ylinux_old 固定 commit，完整跑一遍，写到 results/<时间戳>/
python -m audit_agent replay results/run-20261021-r3   # 不需要密钥：用录下的模型响应离线重放，验证结果可复现
```

## 结果

真值和打分规则见 [DESIGN.md](DESIGN.md#准确性怎么验证)；逐条判定见 [results/EVALUATION.md](results/EVALUATION.md)，每次运行另有 `REVIEW.md`。

| 运行 | 目标 | 审计员 / 复核员 | 上报 | 精确率下限 | 召回率 | high 及以上召回 | 复核否决 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `run-20261021-r1..r3`（3 次重复） | ylinux_old | deepseek-v4-pro / 同一模型 | 14.3 ± 2.1 | 0.952 ± 0.043 | **0.573 ± 0.048** | 1.0 ± 0 | 0 / 43 |
| [`run-20261021-kimi`](results/run-20261021-kimi/report.md) | ylinux_old | deepseek-v4-pro / **kimi-k3** | 19 | 0.947 | 0.625 | 1.0 | **2 / 21** |
| [`run-20261021`](results/run-20261021/report.md) | ylinux_old | deepseek-v4-pro / 同一模型（未加 `list_endpoints` 等之前的版本） | 15 | 1.0 | 0.688 | 1.0 | 0 / 15 |
| [`nv-20261021`](results/nv-20261021/report.md) | django.nV | deepseek-v4-pro / 同一模型，代码和提示词不变 | 22 | 1.0 | 0.958 | 0.923 | 0 / 22 |
| [`run-20261020`](results/run-20261020/report.md) | ylinux_old | DeepSeek-V3，门禁加入之前 | 7 | 0.857 | 0.188 | 0.5 | — |

ylinux_old 共 32 个真问题。每次都能找到的有 15 个，3 次都漏掉的有 10 个，其中最难的是需要把两处代码连起来看的逻辑漏洞（GT-11、GT-12）。单次运行的召回率会在 0.53 到 0.69 之间波动，所以只看一次运行不能下结论。高危及以上的问题在所有新版运行里都找到了。DeepSeek 自己做复核员时，在 ylinux_old 上复核 58 次、在 django.nV 上复核 22 次，一次都没有否决；换成 Kimi 后否决了 2 条，都是严重性定高了，审计员接受了降级。

真值不是人类安全工程师标注的：它由一个开发助手标注，再由另一个独立子代理逐条回到源码交叉核对，最后由开发助手抽查高危条目，没有经过人工复核。提示词和门禁是在 ylinux_old 上迭代出来的，所以 ylinux_old 的分数属于“训练集分数”；django.nV 才是泛化检验，但它的源码里带有 OWASP 编号注释，难度低于真实项目。详见 [DESIGN.md](DESIGN.md)。

## 闭环

1. **审计员**做侦察（`list_endpoints` 给出 URL → 视图 → 装饰器和鉴权线索）、搜索、读代码，然后写发现。`finalize_report` 在门禁通过前会失败，失败原因会返回给模型。门禁要求：
   - 每条扫描线索都已处置；
   - 读过至少 80% 的视图文件；
   - 注入类等 confirmed 发现写明 `data_flow`；
   - 每条上报的发现写明 `entry_role`（匿名 / 开放注册 / 受限账号 / 特权 / 无入口）；严重性和它是否一致由复核员核对。
2. **复核员**是另一段对话，可以用另一个模型（`AUDIT_CRITIC_MODEL`）。每条发现都要先读到证据前后各 10 行，先写 `weakest_point`（这条结论最可能错在哪、怎么核对的），再给出同意或否决。
3. **退回审计员。** 否决和缺口会追加到审计员原来的对话里，最多往返 3 轮；最后仍被否决的发现降为 `needs_review`。
4. **机械核对。** 每条引用都要回到磁盘上的原文行号再比对一次，对不上的降级。
5. **输出**：`report.md`（总表 + 逐条发现）、`appendix.md`（线索、阶段、读过的文件、工具序列）、`decisions.md`（被拒的写入、改判、复核的最弱一环）、`trajectory.md`、`llm_responses.jsonl`（可重放）。

没有 shell 工具。路径解析限制在检出目录内，仓库内容在提示词里声明为不可信数据。

## 配置

密钥只从环境变量或 `.env` 读，不写进任何文件。按下表顺序取第一个有值的变量：

| 变量 | 默认 Base URL | 默认模型 |
| --- | --- | --- |
| `AUDIT_LLM_API_KEY` | `AUDIT_LLM_BASE_URL`，缺省 `https://api.deepseek.com` | `AUDIT_LLM_MODEL`，缺省 `deepseek-v4-pro` |
| `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | `deepseek-v4-pro` |
| `OPENAI_API_KEY` | `https://api.openai.com/v1` | `gpt-4o-mini` |
| `MOONSHOT_API_KEY` | `https://api.moonshot.cn/v1` | `kimi-k3` |
| `DASHSCOPE_API_KEY` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |

默认用 DeepSeek 官方接口上最强的 `deepseek-v4-pro`，并设 `reasoning_effort=max`（由 `AUDIT_LLM_REASONING_EFFORT` 控制，留空则不传）。模型返回的 `reasoning_content` 会随 assistant 消息回传，并节选进 `trajectory.md`。

复核员换模型，例如换成 Kimi：

```powershell
$env:AUDIT_CRITIC_MODEL="kimi-k3"; $env:AUDIT_CRITIC_BASE_URL="https://api.moonshot.cn/v1"; $env:AUDIT_CRITIC_API_KEY="<kimi key>"
python -m audit_agent run --run-dir results/my-kimi-run
```

## 其他命令

```powershell
# 审计本地已有的目录（不克隆）。--vendor 指定默认跳过的目录，static/media/vendor 这类目录名总是跳过
python -m audit_agent run --local --target-dir workspace/django.nV --target-url https://github.com/nVisium/django.nV --commit a48901f106da4888417339b7b44b8ed56b64c63f --vendor ""

# 重新核对一次运行的引用，并重新渲染报告
python -m audit_agent verify results/<运行目录>

# 打分；--group 汇总重复运行的均值和标准差，并为每次运行写 REVIEW.md
python -m audit_agent evaluate results/run-20261021 --group ylinux=results/run-20261021-r1,results/run-20261021-r2,results/run-20261021-r3 --out results/EVALUATION.md
python -m audit_agent evaluate results/nv-20261021 --truth eval/django_nv_truth.json --out results/EVALUATION-django.nV.md

# 单元测试，不访问模型
pytest
```

需要 Python 3.10 及以上和 Git。目标仓库克隆到 `workspace/`，该目录被忽略，不提交。如果本机 Git 配置了一个连不上的 GitHub 代理，克隆时会在这一次命令里去掉代理再重试，不修改 Git 配置。

## 工具

| 角色 | 工具 |
| --- | --- |
| 审计员 | `list_files`、`list_endpoints`、`read_file`、`search_code`、`find_references`、`pattern_scan`、`triage_leads`、`set_stage`、`upsert_finding`、`mark_reviewed`、`get_audit_state`、`resolve_gap`、`finalize_report` |
| 复核员 | `list_files`、`list_endpoints`、`read_file`、`search_code`、`find_references`、`get_audit_state`、`review_finding`、`note_gap`、`accept_report` |

- `list_endpoints` 用文本方式遍历 Django URLconf（因为目标里有 Python 2 代码，`ast` 解析不了），按 include 递归，再给出每个视图的装饰器、鉴权检查、输入来源、写操作行号和启发式标记。
- `find_references` 按词边界在代码和模板里查找一个符号的定义、导入和使用位置，用来确认某个配置项是否被覆盖、某个框架默认值是否真的生效。

## 结果文件

每次运行写到 `results/<时间戳>/`，或 `--run-dir` 指定的目录：

| 文件 | 内容 |
| --- | --- |
| `report.md` | 给人读的报告：发现总表，以及逐条的证据、数据流、入口身份、复核意见 |
| `appendix.md` | 统计、线索处置表、阶段申报、读过的文件、完整工具序列、引用核对结果 |
| `decisions.md` | 门禁拒绝、写入被退回、复核的最弱一环、缺口和改判 |
| `REVIEW.md` | `evaluate` 根据真值写的外部评审：逐条判定、漏报、陷阱。不修改 `findings.json` |
| `findings.json` / `state.json` | 模型写入的结构化发现 / 结束时的审计状态 |
| `trajectory.md` / `trace.jsonl` | 每一步的工具、参数、观察结果预览和推理节选 |
| `llm_responses.jsonl` | 每次模型响应的原文，`replay` 用它离线重放 |
| `verification.json` / `meta.json` | 引用核对结果 / 模型、commit、预算、token、工具序列（不含密钥） |

设计、准确性验证、遇到的问题和取舍写在 [DESIGN.md](DESIGN.md)。
