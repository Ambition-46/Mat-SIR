# 上传、审核与检索

所有入口共用 MySQL 的 smart_small。安装兼容 MySQL 9.6 导出格式的服务端和 mysql 命令行客户端，配置 MYSQL_HOST、MYSQL_PORT、MYSQL_USER、MYSQL_PASSWORD。主机默认 127.0.0.1，端口默认 3306。首次导入需要创建数据库及表的权限。

    python -m system.mysql_import
    python -m system.server

导入器在空库加载 database/smart_small.sql，保留 data_id、property_id、value_id 和原表索引。在已有完整三张核心表的库中运行时只初始化上传辅助表。原生三张表保存实体、属性和值；matsir_source、matsir_field、matsir_history 保存上传记录号、原字段、单位、分类和审核状态。评测时使用同一 SQL 文件在独立实例建立干净的 smart_small，避免上传的新材料改变答案。

打开 http://127.0.0.1:8765，导入 system/example.json，再执行页面中的双强度条件。示例中只有 sample-A 同时满足两项条件。点击明细可查看原字段与审核后的属性。原数据库的观测值没有独立单位列，离线带单位的条件仅命中有对应单位记录的上传数据；对原库可使用不带单位的条件查询。每个实体与标准属性在原库中只允许一条观测，同一条上传记录出现两列映射到同一属性时，导入事务会回滚。

默认模式使用标准字段名和数值条件。设置 MODEL_API_BASE、MODEL_API_KEY、MODEL_NAME 和 EMBEDDING_MODEL 后，运行 python -m system.server --online 启用模型分类、语义匹配和自由文本查询。在线查询从 smart_small 实时读取属性目录、匹配字段、生成标准化 SIR 并交给 MySQL 执行器。命令行也可使用 python -m system.mysql_import --online --question '哪些材料的抗拉强度大于500？'。

HTTP 接口包括 /upload、/pending、/review、/query、/api/intent/parse 和 /api/datasets/full_rows。接口使用 POST 和 application/json。重复上传按数据集、源记录号与原字段更新；待审字段经确认后写入标准属性值。配置测试数据库后运行 python -m unittest system.test_flow 可验证上传、重复导入、审核、查询与来源回查。

### Canonical units

Each physical property has one catalog identity and one registered unit. For example,
`length` is stored in `m`; observations supplied in `cm` map to `length` and are
converted before insertion. Do not create separate properties solely for convertible
units. The source mapping `matsir_field` retains `raw_value` and source `unit`;
`matsir_property_unit` associates the mapped property with its `standard_unit`.
Both upload synchronization (including reviewed fields) and query thresholds use
`system.units`. Queries without a unit use the property's registered unit. Explicit
incompatible units or missing ingestion units cause an error, never a guessed scale.
Affine conversions such as Celsius to kelvin are supported. Output values retain the
standard property unit; this does not introduce automatic conversion of output answers.

Run `python -m system.mysql_import` to add the unit registry. Register catalog units
before uploading measurements or querying with explicit units:

```sh
python -m system.configure_unit length m --stored-unit cm
python -m system.configure_unit tensile_strength MPa --stored-unit MPa
```

`--stored-unit` declares the verified unit of all existing values for that property;
it is required when any values exist. The command converts those values transactionally
and records the canonical unit. For mixed-unit legacy properties, first separate and
verify their source metadata; do not assign a guessed common source unit. Registration
is idempotent for an unchanged canonical unit. New properties approved through the
review endpoint can specify `standard_unit`. Existing registered scales are immutable
through that endpoint.

The archived SQL dump and reported benchmark results are unchanged. Run migrations
on a working copy and re-evaluate queries before reporting results for converted data.
Offline regression checks: `python -m unittest system.test_units`.
