# yuanshen-score

[![CI](https://github.com/zhaowl94/yuanshen/actions/workflows/ci.yml/badge.svg)](https://github.com/zhaowl94/yuanshen/actions/workflows/ci.yml)

一个可复现、可批处理、兼容旧输入的五星圣遗物副词条评分实验。它可以读取结构化
JSON，或通过可选的 EasyOCR 识别已裁剪的简体中文圣遗物卡片，然后按版本化角色权重
计算当前分数并模拟强化结果。

> 本项目为非官方研究工具，与米哈游没有隶属、授权或背书关系。“原神”及相关商标归
> 其权利人所有。`legacy-v1` 权重是仓库原有的自定义偏好，不代表官方结论或通用配装
> 建议。

## v1 范围

- 只正式支持五星圣遗物、简体中文裁剪卡片和副词条评分；
- 原有权重冻结为 `legacy-v1`，不会静默联网更新；
- 旧中文 JSON、旧脚本路径及旧函数在整个 1.x 系列保持兼容；
- 修复历史数据污染、路径加载、OCR 越界和随机结果不可追溯问题；
- 不包含整屏 UI 定位、整套配装、伤害计算或“最适合角色”结论。

## 快速开始

要求 Python 3.11 或 3.12。推荐使用 `uv`：

```powershell
git clone https://github.com/zhaowl94/yuanshen.git
cd yuanshen
uv sync --extra plot
uv run yuanshen-score score examples/artifact.v2.json
uv run yuanshen-score simulate examples/artifact.v2.json --seed 20260729 --plot output/result.png
```

也可以使用普通虚拟环境：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[plot]"
.\.venv\Scripts\yuanshen-score.exe score examples\artifact.v2.json
```

Conda 用户：

```powershell
conda create -n yuanshen-score python=3.12
conda activate yuanshen-score
python -m pip install -e ".[plot]"
yuanshen-score score examples\artifact.v2.json
```

以上方式都不会修改 Windows 的 PATH、注册表或系统环境变量。

## 命令

| 命令 | 作用 |
| --- | --- |
| `score` | 计算一个结构化输入的当前角色分数 |
| `simulate` | 模拟强化并输出最终分数与提升量分布 |
| `ocr` | 将已裁剪截图转换成可人工修正的 JSON |
| `run` | 串联 OCR、评分、模拟和可选绘图 |
| `batch` | 批量执行、失败隔离并支持断点续跑 |
| `models install/verify` | 显式安装或离线校验 OCR 模型 |

所有机器输出都带 `schema_version`、规则版本和输入哈希。模拟结果还会记录实际随机
种子；不指定 `--seed` 时每次自动生成，但仍可使用输出中的种子完整复现。

```powershell
# 版本化 JSON
uv run yuanshen-score simulate examples/artifact.v2.json --runs 10000 --seed 42

# CSV 摘要
uv run yuanshen-score simulate examples/artifact.v2.json --seed 42 --csv

# 批量任务
uv run yuanshen-score batch examples/batch.v2.json --output-dir output/batch-001
uv run yuanshen-score batch examples/batch.v2.json --output-dir output/batch-001 --resume
```

输出文件默认禁止覆盖；只有显式传入 `--force` 才会替换已有文件。批量状态在每项完成
后原子写入 `manifest.json`。

## OCR（可选）

结构化评分不需要 EasyOCR 或 PyTorch。截图功能单独安装：

```powershell
uv sync --extra ocr --extra plot
uv run yuanshen-score models install easyocr-zh
uv run yuanshen-score ocr path\to\cropped-card.png -o output\artifact.json
```

Windows 用户应先按照 [PyTorch 官方安装选择器](https://pytorch.org/get-started/locally/)
安装与 CPU 或 CUDA 匹配的 PyTorch。程序默认使用 CPU；CUDA 必须通过 CLI 或
`config.local.toml` 显式启用。

模型不会在评分过程中静默下载。安装命令会生成包含文件大小和 SHA-256 的本地清单，
后续运行前会离线校验。OCR 置信度不足时默认停止该项评分，并输出人工修正路径。

详细要求见 [OCR 指南](docs/OCR.md)。

## 本地配置

```powershell
Copy-Item config.example.toml config.local.toml
```

`config.local.toml`、实际输入、OCR 模型、真实截图及输出目录都已被 Git 忽略。配置
优先级为：

1. CLI 参数；
2. 输入 JSON；
3. `config.local.toml`；
4. 内置默认值。

程序不会读取配置专用的环境变量，也不会修改 Windows 环境变量。

## 旧版无缝迁移

旧命令仍可运行：

```powershell
Copy-Item calc_item_score\input_param.example.json calc_item_score\input_param.json
uv sync --extra all
uv run python calc_item_score\calc_item_score.py
```

`calc_item_score.py` 中的 `load_*`、`check_valid`、`upgrade`、`calc_score`、
`calc_score_roles`、`ocr_item` 和 `parse_result` 也保留为兼容包装器。已确认的历史
缺陷不会被复制；相关行为变化和字段映射见 [迁移指南](docs/MIGRATION.md)。

## 输入与单位

新格式使用稳定英文标识，例如 `crit_rate`、`crit_damage` 和
`energy_recharge`，同时在展示层提供中文名称。旧格式中的 `暴击`、`爆伤`、`充能`
继续接受。

百分比统一使用“百分点”：`3.9%` 在 JSON 中写作 `3.9`，不是 `0.039`。数值在核心
计算中保持十进制语义，只在输出展示层舍入。

- [输入输出 Schema](docs/SCHEMAS.md)
- [架构说明](docs/ARCHITECTURE.md)
- [Windows 指南](docs/WINDOWS.md)

## 开发与验证

```powershell
uv sync --extra dev --extra plot
uv run ruff check src calc_item_score test
uv run ruff format --check src calc_item_score test
uv run mypy src
uv run pytest -m "not real_ocr" --cov=yuanshen_score --cov-branch --cov-report=term-missing
uv build
```

CI 覆盖 Windows、Ubuntu 与 Python 3.11、3.12。核心算法要求完整分支覆盖，项目整体
分支覆盖率门槛为 90%；合并与发布还包含真实 EasyOCR CPU 冒烟测试。

## English quick start

This is an unofficial, compatibility-focused five-star artifact scoring experiment. It preserves
the legacy Chinese JSON and script interface, while adding strict schemas, deterministic
simulation, batch resume, and optional OCR.

```bash
uv sync --extra plot
uv run yuanshen-score score examples/artifact.v2.json
uv run yuanshen-score simulate examples/artifact.v2.json --seed 42
```

Python 3.11–3.12 and Windows/Ubuntu are supported. OCR, plotting, and all legacy rules are
optional or versioned; no telemetry or image upload is performed.

## 许可证

原创代码、规则文件与合成测试数据采用 [MIT License](LICENSE)。第三方商标、游戏素材
和用户自己的截图不包含在该许可范围内。
