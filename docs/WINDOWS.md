# Windows 使用指南

## 权限与系统改动

本项目以普通用户权限运行：

- 不要求“以管理员身份运行”；
- 不写注册表；
- 不修改系统或用户 PATH；
- 不新增 Windows 环境变量；
- 不安装服务或计划任务。

虚拟环境、配置、OCR 模型和输出都位于仓库或用户显式选择的目录中。

## 推荐安装

```powershell
git clone https://github.com/zhaowl94/yuanshen.git
Set-Location yuanshen
uv sync --extra plot
uv run yuanshen-score score examples\artifact.v2.json
```

如不使用 `uv`：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[plot]"
.\.venv\Scripts\yuanshen-score.exe score examples\artifact.v2.json
```

## 本地配置

```powershell
Copy-Item config.example.toml config.local.toml
```

路径相对于配置文件解析。带空格的路径应使用 TOML 引号或 PowerShell 引号。

## OCR

EasyOCR 在 Windows 上要求先安装与硬件匹配的 PyTorch。默认 CPU 最稳妥；只有完成
CUDA、显卡驱动和 PyTorch 验证后，才在 `config.local.toml` 中设置：

```toml
[ocr]
device = "cuda"
```

## 卸载

关闭正在运行的程序后，删除 `.venv`、`.yuanshen-score` 和所需输出目录即可。没有
注册表、服务或系统环境变量需要恢复。
