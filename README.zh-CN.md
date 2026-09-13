<div align="center">

<img src="docs/assets/banner.png" alt="TimmyTest — 零 Token 测试运行器与 AI 代理智能" width="100%" />

# ⚡ TimmyTest

### 零 Token 测试运行器 • AST 测试缺口分析器 • AI 代理提示词生成器 • MCP 服务器

[English](README.md) · [Türkçe](README.tr.md) · **中文**

[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/tugrakaymakcioglu/TimmyTest/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tugrakaymakcioglu/TimmyTest/actions/workflows/ci.yml)
[![测试](https://img.shields.io/badge/测试-213%20通过-brightgreen?logo=pytest&logoColor=white)](tests/)
[![许可证](https://img.shields.io/badge/许可证-Apache--2.0-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-协议就绪-purple?logo=json&logoColor=white)](#-model-context-protocol-mcp-服务器)

**在开始调试前，先给编码代理一份清晰的测试报告。**
TimmyTest 在本地运行现有测试，找出可能缺少的测试，并将失败结果汇总成可交给 Claude Code、
Codex 或 Cursor 的简短提示词。本地命令不调用 AI API；将提示词发给代理时仍会消耗代理的 token。

```bash
python -m pip install "git+https://github.com/tugrakaymakcioglu/TimmyTest.git@v2.0.0"
timmytest check .
```

目前请从 GitHub 源码安装；PyPI 尚未发布此软件包。

如果首次运行失败或报告难以理解，请在[问题页面](https://github.com/tugrakaymakcioglu/TimmyTest/issues/new/choose)
提供命令、操作系统和删除敏感信息后的输出示例。

[🚀 快速开始](#-快速开始) · [🎬 演示](#-实时演示) · [🔌 MCP 服务器](#-model-context-protocol-mcp-服务器) · [📦 安装](#-安装) · [💰 Token 节省](#-为什么选择-timmytesttoken-消耗问题)

</div>

---

## 🎬 实时演示

真实终端输出 — 在一个包含 1 个失败测试和 1 个未测试模块的演示 Python 项目上运行 `timmytest check`：

<img src="docs/assets/timmytest-demo.gif" alt="TimmyTest 演示：项目概览、测试结果、带修复建议的故障诊断、缺失测试缺口以及 AI 代理交接提示词" width="100%" />

<details>
<summary><b>📸 全分辨率截图</b></summary>

| 步骤 | 截图 |
|:---|:---|
| **项目概览** — 毫秒内检测出生态系统、框架、就绪度评分 | <img src="docs/assets/shot_a.png" width="640" alt="TimmyTest 项目概览表"/> |
| **测试执行** — 本地运行 2 个测试：1 通过、1 失败，退出码已上报 | <img src="docs/assets/shot_b.png" width="640" alt="TimmyTest 测试执行结果表"/> |
| **故障诊断** — 根因、预期与实际对比，以及基于规则的修复建议 | <img src="docs/assets/shot_c.png" width="640" alt="TimmyTest 故障诊断与修复建议"/> |
| **缺口分析** — `src/orchestrator.py` 没有测试文件；HIGH 优先级，给出确切路径 | <img src="docs/assets/shot_d.png" width="640" alt="TimmyTest 缺失测试模块表"/> |
| **代理交接** — 您的 AI 收到的高密度提示词（自动复制到剪贴板） | <img src="docs/assets/shot_e.png" width="640" alt="TimmyTest AI 代理交接提示词"/> |

</details>

---

## 💡 为什么选择 TimmyTest？Token 消耗问题

当 AI 编码代理（Claude Code、OpenAI Codex、Antigravity、Cursor、Copilot、Gemini CLI）被要求测试或修复代码时，它们通常：

1. 用上下文列出目录并查找测试配置。
2. 猜测测试运行器命令，遇到环境错误，重新读取整个测试日志。
3. 把上下文窗口浪费在原始输出上，而不是修复真正的 bug。

### 本地完成的工作

| 阶段 | 仅用 AI 代理 | 使用 TimmyTest 预检 |
| :--- | :--- | :--- |
| 项目与技术栈发现 | 代理探索仓库 | 本地检测器汇总测试配置 |
| 查找缺失测试模块 | 代理搜索源码和测试 | 本地分析器报告可能的缺口 |
| 测试执行与解析 | 代理读取原始输出 | 本地运行器汇总结果 |
| 堆栈跟踪与错误隔离 | 代理解读完整堆栈 | 基于规则的诊断给出可能的原因 |
| **交给代理** | 原始日志进入上下文 | 简短提示词进入上下文 |

实际节省量取决于仓库、测试输出和代理工作流程。我们尚未发布可重复的基准测试。

---

## 🚀 快速开始

### 0. 全屏应用
```bash
timmytest
```
像素艺术启动画面 → 系统检查 → 语言选择（Türkçe / English）→ 工作区向导 → 带有通过/失败/缺口图表
和 **RUN** 按钮的实时仪表板。`timmytest ui --fresh` 重播引导流程；管道/CI 调用保持经典命令列表（`--classic`）。

### 1. 一条命令完成 AI 设置
```bash
timmytest integrate
```
在当前仓库中生成 `.cursorrules`、`CLAUDE.md`、`AGENTS.md`、`.github/copilot-instructions.md`、
`.timmytest.yml` 和 `.cursor/mcp.json` — 您的代理将自动遵循零 token 测试实践。

### 2. 完整审计（扫描 + 运行 + 缺口 + AI 提示词）
```bash
timmytest check .
```
> 💡 *自动将高密度 AI 提示词复制到剪贴板。*

### 3. 零噪声代理输出
```bash
timmytest agent .          # 面向 AI 代理的高密度 markdown
timmytest agent . --json   # 机器可读 JSON
```

### 4. 静态缺口扫描（不执行）
```bash
timmytest scan /path/to/project
```

### 5. 带诊断的测试运行
```bash
timmytest run --only-failures --timeout 120
```

---

## 📦 安装

```bash
# 当前安装方式：公开的 GitHub 源码
python -m pip install "git+https://github.com/tugrakaymakcioglu/TimmyTest.git@v2.0.0"
timmytest check .
```

PyPI 发布仍待完成。在 [PyPI 项目页面](https://pypi.org/project/timmytest/)上线前，
请勿使用 `pip install timmytest` 或 `uvx timmytest`。

---

## 📖 支持的生态系统

TimmyTest 附带**包含 35+ 生态系统的数据驱动注册表**（外加从真实 GitHub 仓库自学的覆盖层）：

| 语言 | 测试运行器 | | 语言 | 测试运行器 |
| :--- | :--- | --- | :--- | :--- |
| **Python** | pytest、unittest | | **PHP** | phpunit |
| **JS/TS** | vitest、jest、mocha、playwright、node --test | | **Ruby** | rspec、minitest |
| **Rust** | cargo test | | **Swift** | xctest |
| **Go** | go test | | **Elixir** | exunit |
| **Java** | junit（maven/gradle） | | **Haskell** | hspec |
| **Kotlin** | kotlintest、gradle | | **C/C++** | ctest、gtest |
| **C#/.NET** | dotnet test | | **Lua** | busted |
| **Dart/Flutter** | dart test | | **Perl** | prove |
| **Solidity** | forge、hardhat | | **…以及 20+ 种** | |

<details>
<summary><b>内置的智能行为</b></summary>

- **增量运行**：`--changed` 仅执行受未提交 git 更改影响的测试；`--since main` 限定分支范围。
- **覆盖率感知**：`--coverage` 解析 `coverage.json` / `cobertura.xml` / `lcov.info`，并将低覆盖率文件标记为缺口。
- **监视模式**：`--watch` 在文件更改时重新运行审计（剪枝遍历 — 不会 stat 风暴式扫描 `node_modules`）。
- **CI 退出码**：套件级错误（无法加载的测试文件）会使 CI 失败，而不仅仅是断言失败。
- **默认安全**：无 shell、`stdin=DEVNULL`、超时时进程树终止、ReDoS 安全的扫描器。
- **自学习注册表**：`TimmyTestDev` 挖掘 GitHub 约定并扩展检测范围。

</details>

---

## 🔌 Model Context Protocol（MCP）服务器

任何兼容 MCP 的客户端（Claude Desktop、Claude Code、Cursor、Antigravity、Windsurf、Zed）都可以原生调用 TimmyTest：

| 工具 | 描述 |
| :--- | :--- |
| `timmytest_check` | 完整零 token 审计：运行测试、缺口、诊断、AI 提示词。 |
| `timmytest_scan` | 静态 AST 扫描：未测试的函数、类、缺失的测试文件。 |
| `timmytest_run` | 执行测试，返回带修复建议的孤立故障。 |
| `timmytest_prompt` | 生成高密度、token 优化的修复/编写测试提示词。 |
| `timmytest_integrate` | 将代理规则和配置安装到项目中。 |

```json
{
  "mcpServers": {
    "timmytest": { "command": "timmytest", "args": ["mcp"] }
  }
}
```

---

## 🧪 CI/CD 集成

```yaml
# .github/workflows/timmytest.yml
name: TimmyTest 审计
on: [push, pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python -m pip install "git+https://github.com/tugrakaymakcioglu/TimmyTest.git@v2.0.0"
      - run: timmytest check . --no-banner --save-report audit-report.md
      - uses: actions/upload-artifact@v4
        with: { name: timmytest-report, path: audit-report.md }
```

使用 `--fail-under 60`（就绪度 %）作为合并门禁，或依赖内置规则：
**任何断言失败或无法加载的测试文件 → 退出码 1**。

---

## 🤝 贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

```bash
git clone https://github.com/tugrakaymakcioglu/TimmyTest.git
cd TimmyTest
uv venv && .venv/Scripts/activate    # 或 source .venv/bin/activate
uv pip install -e .[dev]
python -m pytest -q                  # 213 个测试
ruff check . && mypy src
```

---

## 📄 许可证

Apache License 2.0 — 参见 [LICENSE](LICENSE)。

---

<div align="center">

**为开发者和 AI 编码代理倾情打造。**

⭐ **如果 TimmyTest 为您节省了 token，请给这个仓库加星** — 帮助更多人发现它。

[English](README.md) · [Türkçe](README.tr.md) · **中文**

</div>
