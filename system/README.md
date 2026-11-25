# 上传、审核与检索

所有入口共用 MySQL 的 smart_small。安装兼容 MySQL 9.6 导出格式的服务端和 mysql 命令行客户端，配置 MYSQL_HOST、MYSQL_PORT、MYSQL_USER、MYSQL_PASSWORD。主机默认 127.0.0.1，端口默认 3306。首次导入需要创建数据库及表的权限。

    python -m system.mysql_import
    python -m system.server

导入器在空库加载 database/smart_small.sql，保留 data_id、property_id、value_id 和原表索引。在已有完整三张核心表的库中运行时只初始化上传辅助表。原生三张表保存实体、属性和值；matsir_source、matsir_field、matsir_history 保存上传记录号、原字段、单位、分类和审核状态。评测时使用同一 SQL 文件在独立实例建立干净的 smart_small，避免上传的新材料改变答案。

打开 http://127.0.0.1:8765，导入 system/example.json，再执行页面中的双强度条件。示例中只有 sample-A 同时满足两项条件。点击明细可查看原字段与审核后的属性。原数据库的观测值没有独立单位列，离线带单位的条件仅命中有对应单位记录的上传数据；对原库可使用不带单位的条件查询。每个实体与标准属性在原库中只允许一条观测，同一条上传记录出现两列映射到同一属性时，导入事务会回滚。

默认模式使用标准字段名和数值条件。设置 MODEL_API_BASE、MODEL_API_KEY、MODEL_NAME 和 EMBEDDING_MODEL 后，运行 python -m system.server --online 启用模型分类、语义匹配和自由文本查询。在线查询从 smart_small 实时读取属性目录、匹配字段、生成标准化 SIR 并交给 MySQL 执行器。命令行也可使用 python -m system.mysql_import --online --question '哪些材料的抗拉强度大于500？'。

HTTP 接口包括 /upload、/pending、/review、/query、/api/intent/parse 和 /api/datasets/full_rows。接口使用 POST 和 application/json。重复上传按数据集、源记录号与原字段更新；待审字段经确认后写入标准属性值。配置测试数据库后运行 python -m unittest system.test_flow 可验证上传、重复导入、审核、查询与来源回查。

### Units from property descriptions

The unit explicitly recorded in `property_table.property_description` is the target
unit. No separate unit registry or manual unit-registration command is used.
After semantic matching establishes property identity, upload synchronization and
query processing compare the input unit to this description unit. Equal units retain
the original value; different compatible units are converted by the shared Pint
helper. For example, with `length` described as `长度，单位m`, 150 cm is stored as
1.5 and a query threshold of 120 cm becomes 1.2. The mapping preserves raw values
and source units; converted SIR conditions also preserve the original threshold.

Explicit unit labels (`单位为m`, `unit: m`) and unit parentheses (`模量(GPa)`) are
recognized. Missing, ambiguous, or source-dependent target units are not guessed.
An explicitly unit-bearing input whose target unit cannot be determined is rejected
for clarification. Inputs without an explicit unit retain their existing values.
Conversions are never performed between different properties or incompatible units.
The obsolete `matsir_property_unit` table, if present, is ignored; no data is dropped.
Historical data and benchmark results are not migrated by this update.

Run `python -m unittest system.test_units` for offline regression tests.
