# 架构

## 分层

```text
CLI / legacy wrapper
        |
versioned I/O and batch orchestration
        |
domain models -> scoring -> deterministic simulation
        |
versioned rule data

optional adapters: EasyOCR, Matplotlib
```

核心计算不导入 EasyOCR、PyTorch 或 Matplotlib。

## 模块

| 模块 | 责任 |
| --- | --- |
| `models.py` | 严格输入、输出和 OCR 中立模型 |
| `rules.py` | `legacy-v1` 与本地自定义规则加载 |
| `scoring.py` | 无副作用评分公式 |
| `simulation.py` | 版本化 RNG、强化过程与统计摘要 |
| `parser.py` | 简体中文 OCR token 到领域模型 |
| `ocr.py` | EasyOCR 延迟加载与模型校验 |
| `io.py` | JSON/CSV、哈希和原子写入 |
| `batch.py` | 失败隔离、状态清单和断点续跑 |
| `plotting.py` | 可选 Matplotlib 摘要图 |
| `compat.py` | 旧函数和旧脚本行为适配 |
| `cli.py` | `argparse` 命令入口与配置优先级 |

## 可复现性

`python-mt19937-v1` 只使用 `random.Random.random()` 作为抽样原语，并自行实现稳定的
等权与加权选择。规则版本、输入哈希、运行次数、目标等级和实际种子都写入结果。

角色之间使用同一组模拟出的强化圣遗物，因此同一次运行可直接比较，而不会因为每个
角色重新抽样而引入额外噪声。

## 扩展点

- 新规则必须使用新 ID，不修改 `legacy-v1`；
- 新 OCR 引擎实现统一的 token 协议；
- 新语言需要独立词典、解析器测试和明确支持声明；
- 破坏旧脚本或中文字段的改变只能进入未来 2.0。
