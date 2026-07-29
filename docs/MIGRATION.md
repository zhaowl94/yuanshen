# 从历史脚本迁移

## 兼容承诺

以下接口在整个 1.x 系列保留：

- `python calc_item_score/calc_item_score.py`；
- 顶层 `roles`、`item_path` 或 `item` 输入；
- `position`、`major_attr`、`level`、`minor_attr`；
- 原脚本中的公开函数名及主要参数、返回类型。

兼容包装器会发出 `FutureWarning`，但 1.x 不会删除接口。

## 配置迁移

旧仓库跟踪了可变的 `calc_item_score/input_param.json`。v1 将它改为本地文件：

```powershell
Copy-Item calc_item_score\input_param.example.json calc_item_score\input_param.json
Copy-Item config.example.toml config.local.toml
```

这两个实际配置文件都不会同步到 Git。

## 字段映射

| 旧字段 | 新标识 | 单位 |
| --- | --- | --- |
| `小生命` | `flat_hp` | 固定数值 |
| `小攻击` | `flat_atk` | 固定数值 |
| `小防御` | `flat_def` | 固定数值 |
| `精通` | `elemental_mastery` | 固定数值 |
| `充能` | `energy_recharge` | 百分点 |
| `大生命` | `hp_percent` | 百分点 |
| `大攻击` | `atk_percent` | 百分点 |
| `大防御` | `def_percent` | 百分点 |
| `暴击` | `crit_rate` | 百分点 |
| `爆伤` | `crit_damage` | 百分点 |

旧位置编号 `1`–`5` 分别映射为 `flower`、`plume`、`sands`、`goblet`、`circlet`。

## 有意修复的行为

以下缺陷不提供错误兼容模式：

1. `load_*` 传入自定义路径时不再引用未赋值变量。
2. `trans_role_weight` 不再修改共享角色字典。
3. 添加第四副词条时不再永久清零共享抽取权重。
4. OCR 缺字段时返回带上下文的错误，不再产生 `IndexError`。
5. 随机种子和 RNG 语义写入输出，可完整复现模拟。
6. 非法等级、角色、字段、副词条数量或单位不再静默进入计算。

因此，修复共享状态污染后，随机分布可能与旧脚本一次偶然运行的结果不同；评分公式和
`legacy-v1` 权重本身未改变。

## Python API

新代码应使用：

```python
from yuanshen_score import load_rule_set, score_artifact, simulate
from yuanshen_score.io import load_score_request

request = load_score_request("examples/artifact.v2.json")
rules = load_rule_set()
report = simulate(request.artifact, request.roles, rules, seed=42)
```

旧代码仍可导入：

```python
from calc_item_score.calc_item_score import calc_score
```
