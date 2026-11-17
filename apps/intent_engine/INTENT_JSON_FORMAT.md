# Intent 对象 JSON 格式说明

`apps/intent_engine/models.py` 中的 `Intent` 通过 `to_dict()` 转为字典后，可直接 `json.dumps` 序列化。以下为实际运行生成的 JSON 结构。

## 顶层结构（7 个字段）

```json
{
  "intent_type": "search",
  "groups": [],
  "group_logic_op": "and",
  "target_properties": [],
  "explanation": "",
  "sort_by": null,
  "query_mode": "simple"
}
```

| 字段 | 说明 |
| --- | --- |
| `intent_type` | 枚举转字符串：`"search"` / `"compare"` |
| `groups` | `QueryGroup` 列表，每组含 `logic_op`、`conditions`、`datasets` |
| `group_logic_op` | 多组之间的逻辑：`"and"` / `"or"` / `"not"` |
| `target_properties` | 用户明确想查看的属性字段列表 |
| `explanation` | 查询意图的文字说明 |
| `sort_by` | 排序规则，如 `{"field": "tensile_strength", "order": "desc"}`，无则为 `null` |
| `query_mode` | `"simple"`（简单查询）/ `"complex"`（跨数据集查询） |

## 简单查询示例（抗拉强度 > 500 MPa）

```json
{
  "intent_type": "search",
  "groups": [
    {
      "logic_op": "and",
      "conditions": [
        {
          "field": "tensile_strength",
          "operator": ">",
          "value": 500,
          "unit": "MPa",
          "agg_func": null
        }
      ],
      "datasets": ["钛合金数据"]
    }
  ],
  "group_logic_op": "and",
  "target_properties": [],
  "explanation": "",
  "sort_by": null,
  "query_mode": "simple"
}
```

## 复杂（跨数据集）查询示例

```json
{
  "intent_type": "search",
  "groups": [
    {
      "logic_op": "and",
      "conditions": [
        {"field": "poisson_ratio", "operator": "<", "value": 4.0, "unit": null, "agg_func": null}
      ],
      "datasets": ["特殊钢-物理性能-泊松比"]
    },
    {
      "logic_op": "and",
      "conditions": [
        {"field": "loading_condition", "operator": "<", "value": 27.6, "unit": null, "agg_func": null}
      ],
      "datasets": ["高温合金-力学性能-加载条件"]
    }
  ],
  "group_logic_op": "and",
  "target_properties": ["poisson_ratio"],
  "explanation": "查找泊松比小于4.0的材料样本和加载条件小于27.6的样本",
  "sort_by": {"field": "poisson_ratio", "order": "desc"},
  "query_mode": "complex"
}
```

## 聚合查询示例（求最大抗拉强度）

聚合查询时 `operator` 和 `value` 为 `null`，靠 `agg_func` 表达：

```json
{
  "field": "tensile_strength",
  "operator": null,
  "value": null,
  "unit": null,
  "agg_func": "max"
}
```

`agg_func` 可选值：`max`、`min`、`avg`、`variance`、`sum`、`count`。

## 序列化细节

- 所有枚举（`IntentType`、`Operator`、`LogicOp`）在 `to_dict()` 里通过 `.value` 转成字符串，可直接 `json.dumps`，不会报序列化错误。
- `QueryGroup.logic_op` 定义是 `str` 类型（默认 `"and"`），而 `Intent.group_logic_op` 是 `LogicOp` 枚举——两者最终都输出字符串，但来源不同。
- `SubQuery` 类也有 `to_dict()`，但它不在 `Intent` 的结构里，是独立使用的。
- 可选字段（`unit`、`agg_func`、`sort_by`）没值时输出 `null`，空列表字段输出 `[]`。
- `Condition.operator` 可选值：`"="`、`">"`、`"<"`、`">="`、`"<="`、`"contains"`、`"!="`；聚合查询时为 `null`。
