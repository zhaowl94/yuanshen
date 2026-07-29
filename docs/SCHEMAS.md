# 输入输出 Schema

## 标准单件输入

```json
{
  "schema_version": "2.0",
  "artifact": {
    "position": "sands",
    "main_attribute": "atk_percent",
    "level": 6,
    "rarity": 5,
    "substats": {
      "flat_def": 16,
      "energy_recharge": 5.2,
      "crit_rate": 3.9,
      "crit_damage": 6.2
    }
  },
  "roles": ["夜兰", "胡桃"],
  "ruleset": "legacy-v1",
  "runs": 10000,
  "target_level": 20,
  "seed": 42
}
```

`runs`、`target_level` 和 `seed` 可省略。CLI 参数优先于输入文件。

## 校验规则

- `rarity` 必须为 `5`；
- 等级必须在 `0`–`20` 之间；
- 副词条必须有三个或四个且数值为正；
- 等级达到 `+4` 后必须已有四个副词条；
- 主词条不得同时作为同类副词条；
- 目标等级不得低于当前等级；
- 角色必须存在于所选规则集；
- 不接受未知字段或根据数值大小猜测单位。

百分比使用百分点，例如 `crit_rate: 3.9` 表示 `3.9%`。

## 标准输出

评分输出包括：

- `schema_version`、应用版本、规则集和输入 SHA-256；
- 规范化圣遗物；
- 每个角色的当前分数。

模拟输出额外包括：

- 实际随机种子和版本化 RNG 标识；
- 运行次数与目标等级；
- 当前分数；
- 最终分数和提升量的最小值、四分位数、中位数、平均值与最大值；
- 显式 `--raw-samples` 时的原始最终分数。

## 批量清单

```json
{
  "schema_version": "2.0",
  "roles": ["夜兰"],
  "runs": 1000,
  "seed": 42,
  "items": [
    {"id": "json-1", "input": "artifact.v2.json"},
    {"id": "image-1", "image": "local-card.png"},
    {
      "id": "embedded-1",
      "artifact": {
        "position": "sands",
        "main_attribute": "atk_percent",
        "level": 6,
        "rarity": 5,
        "substats": {
          "flat_def": 16,
          "energy_recharge": 5.2,
          "crit_rate": 3.9,
          "crit_damage": 6.2
        }
      }
    }
  ]
}
```

每项必须且只能提供 `input`、`image`、`artifact` 之一。条目可覆盖 `roles`、`runs`、
`target_level` 和 `seed`。任务状态不会保存绝对截图路径。续跑会同时核对输入哈希、
执行参数哈希、结果文件存在性和结果哈希；任一不一致都会安全重算该项。
