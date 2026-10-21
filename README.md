# 代码审计 Agent

用大模型做应用安全审计的 Agent，审计目标是 [gwind/ylinux_old](https://github.com/gwind/ylinux_old)（Django 1.2 / Python 2）。

它由两段独立对话组成：

- **审计员**：自己决定调用哪些工具、按什么顺序读代码，然后记录发现。
- **复核员**：逐条复核审计员的发现，可以换成另一个模型。

两者之间靠门禁来回推动。门禁只检查“某类工作有没有做”（例如扫描线索是否都处理了、视图文件是否读够了），不规定先做哪一步。

为了检验泛化，我在不改代码和提示词的情况下又跑了 [nVisium/django.nV](https://github.com/nVisium/django.nV)。

- 分析报告：[REPORT.md](REPORT.md)
- 设计说明：[DESIGN.md](DESIGN.md)
- 运行结果：[results/](results/README.md)

## 快速开始

```powershell
pip install -e ".[dev]"; copy .env.example .env      # 在 .env 里填 DEEPSEEK_API_KEY
python -m audit_agent run                             # 克隆 ylinux_old 的固定 commit，完整跑一遍，结果写到 results/<时间戳>/
python -m audit_agent replay results/run-20261021-r3  # 不需要密钥，用录下的模型响应离线重放
```

`replay` 用来验证结果可以复现。如果 `workspace/` 里还没有目标仓库，它会先按记录的 commit 克隆。

需要 Python 3.10 以上和 Git，唯一的运行时依赖是 `openai==2.32.0`。目标仓库会克隆到 `workspace/`，这个目录不提交。

## 结果

| 运行 | 目标 | 审计员 / 复核员 | 上报 | 精确率下限 | 召回率 | high 及以上召回 | 复核否决 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `run-20261021-r1..r3`（同配置跑 3 次） | ylinux_old | deepseek-v4-pro / 同一模型 | 14.3 ± 2.1 | 0.952 ± 0.043 | **0.573 ± 0.048** | 1.0 ± 0 | 0 / 43 |
| `run-20261021-kimi..kimi3`（3 次，后两次复核中断） | ylinux_old | deepseek-v4-pro / **kimi-k3** | 15.7 ± 3.1 | 0.934 ± 0.012 | 0.552 ± 0.065 | 1.0 ± 0 | **6 / 43** |
| [`run-20261021`](results/run-20261021/report.md) | ylinux_old | deepseek-v4-pro / 同一模型（还没加 `list_endpoints` 等） | 15 | 1.0 | 0.688 | 1.0 | 0 / 15 |
| [`nv-20261021`](results/nv-20261021/report.md) | django.nV | deepseek-v4-pro / 同一模型，代码和提示词不变 | 22 | 1.0 | 0.958 | 0.923 | 0 / 22 |
| [`nv-20261021-kimi`](results/nv-20261021-kimi/report.md) | django.nV | deepseek-v4-pro / kimi-k3（复核中断） | 19 | 0.895 | 0.833 | 0.923 | 0 / 16 |
| [`run-20261020`](results/run-20261020/report.md) | ylinux_old | DeepSeek-V3，还没有门禁 | 7 | 0.857 | 0.188 | 0.5 | — |

**召回情况。** ylinux_old 一共标了 32 个真问题。审计员配置相同的 6 次运行里，13 个每次都找到了，8 个一次都没找到，剩下 11 个时有时无。单次召回率在 0.50 到 0.63 之间浮动，所以只看一次运行的结果说明不了什么。high 及以上的问题，每次新版运行都找到了。

最难的是 GT-11 和 GT-12。它们是重置口令流程里的逻辑漏洞，要把激活和重置两段代码连起来看才能发现。具体分析见 [REPORT.md](REPORT.md#漏掉的两个逻辑漏洞)。

**复核员的表现。** 用 DeepSeek 自己当复核员时，80 次复核一次都没否决过。换成 Kimi 后在 ylinux_old 上否决了 6 次，其中 3 次是审计员每次都会犯的同一个错（把附件上传判成路径穿越），DeepSeek 复核时 3 次都放过去了。另外 Kimi 提的缺口在 django.nV 上补出了一条审计员漏掉的 critical。所以如果有第二个模型的密钥，建议用它做复核员。

用 Kimi 复核的 4 次运行里有 3 次（kimi2、kimi3、nv-kimi）在复核途中因为账户余额用完中断（429），审计员部分完整，报告开头标了中断，没复核到的条目标为“未复核”。

**分数的局限。**

- 真值是我借助 Claude 标注、再开独立会话交叉核对，最后自己抽查的，没有经过专业安全人员复核。
- 提示词和门禁是在 ylinux_old 上调出来的，这里的分数偏乐观。
- django.nV 是泛化测试，但它的源码里带着标出漏洞位置的 OWASP 编号注释，难度比真实项目低。

这些在 [DESIGN.md](DESIGN.md#怎么确认结果准确) 里有详细说明。

## 流程

1. **审计员。**
   - 先做侦察：`list_endpoints` 列出 URL → 视图 → 装饰器和鉴权情况。
   - 然后搜索、读代码、写发现。
   - 门禁通过之前，`finalize_report` 会失败，并把缺什么返回给模型。门禁要求：
     - 每条扫描线索都处置过；
     - 读过至少 80% 的视图文件；
     - 注入这类 confirmed 发现要写明 `data_flow`；
     - 每条上报的发现要写明 `entry_role`（匿名 / 开放注册 / 受限账号 / 特权 / 无入口）。严重性和它对不对得上，由复核员来查。
2. **复核员。**
   - 另起一段对话，可以用另一个模型（`AUDIT_CRITIC_MODEL`）。
   - 每条发现都要先读证据前后各 10 行。
   - 先写 `weakest_point`：这条结论最可能错在哪、是怎么核对的。然后才能给出同意或否决。
3. **退回审计员。**
   - 否决意见和缺口追加到审计员原来的对话里，最多往返 3 轮。
   - 3 轮后仍被否决的发现降为 `needs_review`。
4. **机械核对。** 每条引用都回到磁盘上的原文按行号再比一次，对不上的降级。
5. **输出。** 每个运行目录里的文件说明见 [results/README.md](results/README.md)。

Agent 没有 shell 工具。路径解析限制在检出目录内，仓库里的内容在提示词里声明为不可信数据。

## 配置

密钥只从环境变量或 `.env` 读取，不会写进任何文件。程序按下表顺序取第一个有值的变量：

| 变量 | 默认 Base URL | 默认模型 |
| --- | --- | --- |
| `AUDIT_LLM_API_KEY` | `AUDIT_LLM_BASE_URL`，缺省为 `https://api.deepseek.com` | `AUDIT_LLM_MODEL`，缺省为 `deepseek-v4-pro` |
| `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | `deepseek-v4-pro` |
| `OPENAI_API_KEY` | `https://api.openai.com/v1` | `gpt-4o-mini` |
| `MOONSHOT_API_KEY` | `https://api.moonshot.cn/v1` | `kimi-k3` |
| `DASHSCOPE_API_KEY` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |

默认使用 DeepSeek 官方的 `deepseek-v4-pro`，并设置 `reasoning_effort=max`。这个值由 `AUDIT_LLM_REASONING_EFFORT` 控制，留空就不传。客户端走的是 OpenAI Chat Completions 的 tool calling 协议，兼容这个协议的网关都能用。

想让复核员换个模型（例如 Kimi），这样设置：

```powershell
$env:AUDIT_CRITIC_MODEL="kimi-k3"; $env:AUDIT_CRITIC_BASE_URL="https://api.moonshot.cn/v1"; $env:AUDIT_CRITIC_API_KEY="<kimi key>"
python -m audit_agent run --run-dir results/my-kimi-run
```

步数预算等其他配置见 `.env.example`。

## 其他命令

```powershell
# 审计本地已有的目录，不克隆。--vendor 指定要跳过的第三方目录；static、media、vendor 这类目录名总是会跳过
python -m audit_agent run --local --target-dir workspace/django.nV --target-url https://github.com/nVisium/django.nV --commit a48901f106da4888417339b7b44b8ed56b64c63f --vendor ""

# 重新核对一次运行的引用，并重新生成报告
python -m audit_agent verify results/<运行目录>

# 打分。--group 汇总多次重复运行的均值和标准差，同时给每次运行写一份 REVIEW.md
python -m audit_agent evaluate results/run-20261020 results/run-20261021 --group deepseek-x3=results/run-20261021-r1,results/run-20261021-r2,results/run-20261021-r3 --group kimi-x3=results/run-20261021-kimi,results/run-20261021-kimi2,results/run-20261021-kimi3 --out results/EVALUATION.md
python -m audit_agent evaluate results/nv-20261021 results/nv-20261021-kimi --truth eval/django_nv_truth.json --out results/EVALUATION-django.nV.md

# 单元测试，不会调用模型
pytest
```

如果本机 Git 配了一个连不上的 GitHub 代理，克隆时会只在那一次命令里去掉代理重试，不会修改你的 Git 配置。

## 工具

| 角色 | 工具 |
| --- | --- |
| 审计员 | `list_files`、`list_endpoints`、`read_file`、`search_code`、`find_references`、`pattern_scan`、`triage_leads`、`set_stage`、`upsert_finding`、`mark_reviewed`、`get_audit_state`、`resolve_gap`、`finalize_report` |
| 复核员 | `list_files`、`list_endpoints`、`read_file`、`search_code`、`find_references`、`get_audit_state`、`review_finding`、`note_gap`、`accept_report` |

- `list_endpoints`：用文本方式遍历 Django 的 URLconf，按 include 递归，列出每个视图的装饰器、鉴权检查、输入来源和写操作所在的行号。用文本方式是因为目标里有 Python 2 代码，`ast` 解析不了。
- `find_references`：按词边界在代码和模板里查一个符号的定义、导入和使用位置，用来确认某个配置项有没有被覆盖、某个框架默认值是否真的生效。

## 目录

```
src/audit_agent/   Agent 本体：循环、工具、门禁、报告渲染、打分
tests/             单元测试，用脚本化的假模型，不调用接口；CI 在 .github/workflows/test.yml
eval/              真值文件和生成脚本
results/           各次运行的完整输出和打分汇总
REPORT.md          ylinux_old 审计分析报告
DESIGN.md          设计思路、准确性验证、问题和取舍
```
