# 代码安全审计 Agent

这个项目让大模型自己去读一个网站的源代码，找出里面的安全漏洞，最后写成报告。

被审计的网站是 [gwind/ylinux_old](https://github.com/gwind/ylinux_old)，一个 2010 年前后用 Django 1.2（Python 2）写的中文 Linux 社区，有论坛、Wiki、附件上传和一个远程发帖接口。审计固定在 commit `8a7316deec88287d020eca21c38dad921b623ffc`，保证每次看的是同一份代码。

## 交付物在哪里

| 要求 | 位置 |
| --- | --- |
| 1. 可运行的代码 + 配置、运行、依赖的模型和 API | 代码在 `src/audit_agent/`，说明就是本文件 |
| 2. Agent 的实际运行结果 | `results/` 下每个子目录是一次真实运行，目录说明见 [results/README.md](results/README.md) |
| 2. 人类可读的分析报告 | [REPORT.md](REPORT.md)：ylinux_old 有哪些漏洞、Agent 找到了哪些、漏了哪些 |
| 3. 设计思路、怎么确认结果准确、遇到的问题和取舍 | [DESIGN.md](DESIGN.md) |

## 先认识几个词

| 词 | 意思 | 来源 |
| --- | --- | --- |
| 代码审计 | 不运行程序，直接读源码找安全问题。也叫静态分析 | 安全行业通用说法 |
| 大模型（LLM） | 像 ChatGPT、DeepSeek 这样能读写文字和代码的 AI 模型。LLM 是 Large Language Model 的缩写 | — |
| Agent（智能体） | 不是一问一答，而是让模型自己决定下一步做什么（读哪个文件、搜什么关键词），拿到结果后再决定下一步，直到完成任务 | 业界通用叫法，例如 Anthropic 的文章 [Building effective agents](https://www.anthropic.com/research/building-effective-agents) |
| 工具调用（tool calling） | 程序事先告诉模型“你可以用这些工具”，模型回复时不写答案，而是说“我要调用 `read_file`，参数是某个文件”，程序执行后把结果交回给模型 | OpenAI Chat Completions 接口的 function calling 协议，DeepSeek、Kimi 等都兼容 |
| 审计员 / 复核员 | 本项目里的两个角色。审计员负责找漏洞，复核员负责挑审计员的毛病。两者是两段互不相通的对话 | 本项目的设计 |
| 门禁 | 审计员想交卷时，程序先检查一些“该做的事做了没有”，没做完就不让交，并告诉它缺什么 | 本项目的设计 |
| 发现（finding） | Agent 记下的一条漏洞，包括位置、引用的原文、严重性、怎么触发 | — |
| 线索（lead） | 用关键词规则扫出来的可疑代码，比如出现了 `os.system`。线索不等于漏洞，要人（这里是模型）去看 | — |
| 严重性 | 从高到低 critical、high、medium、low、info，表示一个漏洞危害有多大 | 参考 [CVSS](https://www.first.org/cvss/) 的定性分级 |
| 入口身份 | 谁能触发这个漏洞：匿名访客、能自助注册的用户、已有账号的用户、管理员，或者没有网页入口 | 本项目的字段 `entry_role` |
| OWASP | 一个开放的 Web 安全社区，最有名的是“十大 Web 安全风险”清单 | [owasp.org](https://owasp.org/www-project-top-ten/) |
| CWE | 软件弱点的统一编号，比如 CWE-79 就是 XSS。报告里每条发现都尽量标了 CWE | MITRE 维护，[cwe.mitre.org](https://cwe.mitre.org/) |
| 真值（ground truth） | 事先整理好的“标准答案”：这个仓库里到底有哪些真漏洞。拿 Agent 的结果和它对比来打分 | 机器学习评测的通用说法 |
| 召回率 / 精确率 | 召回率 = 真漏洞里被找到的比例（漏得少不少）；精确率 = 报出来的里面真漏洞的比例（报得准不准） | 信息检索的标准指标 |
| 重放（replay） | 把模型当时的每一次回复录下来，以后不联网、不花钱，用录音重新跑一遍，检查结果是否一样 | 本项目的功能 |

具体的漏洞类型（XSS、CSRF、越权等）在 [REPORT.md](REPORT.md) 里遇到时再解释。

## 安装

需要：

- Python 3.10 或更新版本
- Git（用来下载被审计的仓库）

在项目根目录执行：

```powershell
pip install -e ".[dev]"
```

运行时只依赖一个第三方包 `openai==2.32.0`（OpenAI 官方的 Python 客户端，用来调兼容接口，不一定要用 OpenAI 的模型）。`[dev]` 会额外装上跑测试用的 `pytest`。

## 配置：用哪个模型、哪个 API

Agent 需要一个大模型的 API 密钥。把 `.env.example` 复制成 `.env`，填一个密钥就行：

```powershell
copy .env.example .env
# 用记事本打开 .env，填上 DEEPSEEK_API_KEY=你的密钥
```

密钥只从环境变量或 `.env` 读，不会写进任何输出文件。`.env` 不提交到仓库。

程序按下面的顺序找密钥，用第一个找到的：

| 环境变量 | 接口地址（Base URL） | 默认模型 |
| --- | --- | --- |
| `AUDIT_LLM_API_KEY` | `AUDIT_LLM_BASE_URL`，不填就是 `https://api.deepseek.com` | `AUDIT_LLM_MODEL`，不填就是 `deepseek-v4-pro` |
| `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | `deepseek-v4-pro` |
| `OPENAI_API_KEY` | `https://api.openai.com/v1` | `gpt-4o-mini` |
| `MOONSHOT_API_KEY` | `https://api.moonshot.cn/v1` | `kimi-k3` |
| `DASHSCOPE_API_KEY` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |

本项目所有正式运行用的是 DeepSeek 官方接口的 `deepseek-v4-pro`，打开了深度思考（`reasoning_effort=max`，由 `AUDIT_LLM_REASONING_EFFORT` 控制，留空就不传这个参数）。只要接口兼容 OpenAI Chat Completions 的工具调用协议，换成别家也能跑。

复核员可以单独换一个模型。我们实测换成 Kimi 后复核更严格（原因见 [DESIGN.md](DESIGN.md#4-换一个模型当复核员)），有条件的话推荐这样配：

```powershell
$env:AUDIT_CRITIC_MODEL="kimi-k3"
$env:AUDIT_CRITIC_BASE_URL="https://api.moonshot.cn/v1"
$env:AUDIT_CRITIC_API_KEY="<Kimi 的密钥>"
```

不设 `AUDIT_CRITIC_MODEL`，复核员就和审计员用同一个模型。步数上限等其他参数见 `.env.example`，默认值是审计员 80 步、复核员 40 步、退回修改 40 步、最多往返 3 轮。

## 运行

下面的命令都在项目根目录执行。

**1. 不花钱先试一下：重放一次录好的运行。** 不需要密钥，大约 1.5 秒：

```powershell
python -m audit_agent replay results/run-20261021-r3
```

它会用录下来的 92 条模型回复重新驱动整个流程，工具（读文件、搜索等）在本机真实执行。最后一行打印 `identical_to_original=True`，说明重放结果和原来那次运行完全一致。如果 `workspace/` 里还没有 ylinux_old，会先自动下载。

**2. 完整跑一次真实审计。** 需要密钥，DeepSeek 大约 11–16 分钟：

```powershell
python -m audit_agent run
```

它会把 ylinux_old 下载到 `workspace/ylinux_old` 并切到固定的 commit，然后开始审计。结果写到 `results/<时间戳>/`，先看里面的 `report.md`。

**3. 给结果打分。** 拿运行结果和真值对比，算召回率、精确率：

```powershell
python -m audit_agent evaluate results/run-20261021-r1 results/run-20261021-r2 results/run-20261021-r3 --out results/my-score.md
```

加 `--group 名字=目录1,目录2,目录3` 可以算多次运行的平均值和波动。

**4. 跑单元测试。** 测试用的是写好剧本的假模型，不联网、不花钱：

```powershell
pytest
```

现在有 28 个测试。GitHub 上每次提交都会自动跑一遍（`.github/workflows/test.yml`，Python 3.10 和 3.12）。

**其他命令：**

```powershell
# 审计一个已经在本地的目录（不下载）。这里是我们做泛化测试用的 django.nV
python -m audit_agent run --local --target-dir workspace/django.nV --target-url https://github.com/nVisium/django.nV --commit a48901f106da4888417339b7b44b8ed56b64c63f --vendor ""

# 重新核对一次运行里的代码引用，并重新生成报告
python -m audit_agent verify results/<运行目录>
```

`--vendor` 指定要默认跳过的第三方代码目录（ylinux_old 默认跳过它自带的 `lib/markdown`）。名字叫 `static`、`vendor`、以 `media` 结尾的目录总是跳过。

## 结果一览

ylinux_old 一共标注了 32 个真漏洞。详细分析在 [REPORT.md](REPORT.md)，打分方法在 [DESIGN.md](DESIGN.md#二怎么确认结果是准的)。

| 运行 | 审计员 / 复核员 | 次数 | 每次报出 | 精确率下限 | 召回率 | high 及以上召回 |
| --- | --- | --- | --- | --- | --- | --- |
| r1–r3 | DeepSeek / DeepSeek | 3 | 14.3 条 | 0.95 | 0.57 ± 0.05 | 1.0 |
| kimi1–3 | DeepSeek / Kimi | 3 | 15.7 条 | 0.93 | 0.55 ± 0.07 | 1.0 |
| 第一版（没有门禁） | DeepSeek-V3 / DeepSeek-V3 | 1 | 7 条 | 0.86 | 0.19 | 0.5 |
| django.nV（换一个项目） | DeepSeek / DeepSeek | 1 | 22 条 | 1.0 | 0.96 | 0.92 |

用大白话说：

- 6 个 high 级漏洞每次都能找到，报出来的东西平均 93% 以上是真漏洞。
- 但一次只能找到一半多一点（55%–57%），漏掉的主要是 low 级问题和需要把两段代码连起来想的逻辑漏洞。
- 第一版没有门禁，召回率只有 0.19；现在是 0.57 左右（中间模型也从 DeepSeek-V3 换成了 v4-pro，两者的功劳分不开）。
- 同一个模型给自己复核基本不会挑出毛病（80 次复核 0 次否决）；换成 Kimi 后否决了 6 次，拦住了审计员每次都会犯的一个误报。
- 这些分数有局限：标准答案不是专业安全工程师做的，规则也是在这个仓库上调出来的。详见 [DESIGN.md](DESIGN.md#6-分数的局限)。

## 一次运行里发生了什么

1. **审计员干活。** 程序把任务说明和 13 个工具交给模型。模型自己决定先列 URL、还是先搜关键词、还是先读某个文件，每次调用的结果再交还给它。它觉得找得差不多了，就调 `finalize_report` 交卷。
2. **门禁检查。** 交卷时程序检查：扫出来的每条线索都处理了吗？视图文件（`views.py`，网站处理请求的代码）读够 80% 了吗？注入类漏洞写清楚数据从哪来、流到哪了吗？每条漏洞写明谁能触发了吗？没做完就退回，告诉模型缺什么。
3. **复核员挑毛病。** 另开一段对话，复核员只看到审计员写下的漏洞清单，看不到它的思考过程。它要对每条漏洞先读源码，写下“这条最可能错在哪”，再表态同意或否决，也可以指出审计员漏看的地方（叫“缺口”）。
4. **退回修改。** 被否决的条目和缺口交回给审计员，审计员在原来的对话里改判或补查，然后再复核。最多来回 3 轮，还被否决的降为“需要再确认”。
5. **回磁盘核对。** 每条漏洞引用的代码原文，都回到文件里按行号再比一次，对不上的降级。
6. **写报告。** 生成 `report.md`（报告正文）和几个附件，每个文件的用途见 [results/README.md](results/README.md)。

Agent 不能执行任何命令，只能读被审计仓库里的文件，而且读不到仓库目录以外的东西。这样即使被审计的代码里藏着“请执行某命令”之类的文字，也没法让 Agent 去做。

## 目录

```
src/audit_agent/   Agent 本体
  agent.py           工具调用循环、审计员与复核员的往返
  tools.py           13 个工具和门禁检查
  prompts.py         给两个角色的任务说明
  llm.py             调模型接口、出错重试、录制与重放
  sandbox.py         把文件访问限制在被审计仓库里
  scanner.py         关键词规则扫描（产生线索）
  endpoints.py       从 Django 的 URL 配置列出所有网页入口
  verifier.py        结束后回磁盘核对引用
  report.py          生成报告
  evaluate.py        对照真值打分
tests/             单元测试（假模型，不联网）
eval/              真值文件（标准答案）和生成脚本
results/           每次真实运行的完整输出，以及打分汇总
REPORT.md          ylinux_old 漏洞分析报告
DESIGN.md          设计说明
```

`workspace/` 是下载被审计仓库的地方，不提交到 Git。
