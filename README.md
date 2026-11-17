# Mat-SIR

Research implementation of Mat-SIR for materials data integration and natural-language querying, with field classification, semantic matching, EAV storage, and a 500-question benchmark.

材料字段匹配、EAV 入库和结构化查询的研究实现。

## 上传与查询

安装 MySQL 服务端和 mysql 客户端，配置 MYSQL_USER、MYSQL_PASSWORD 以及可选的 MYSQL_HOST、MYSQL_PORT。在项目根目录执行：

    python -m pip install -r requirements.txt
    python -m system.mysql_import
    python -m system.server

打开 http://127.0.0.1:8765 ，导入 system/example.json 后执行页面中的查询。两条样品中，只有 sample-A 同时满足两个强度条件。页面返回标准化 SIR、SQL、参数和命中记录。默认查询模式使用标准字段名和条件语法。在线匹配、自由文本解析和 MySQL 导入与执行见 [系统说明](system/README.md)。

## 字段匹配与评测

配置 MODEL_API_BASE、MODEL_API_KEY 和支持 qwen-plus、text-embedding-v2 的服务后运行：

    python run_fields.py static
    python run_fields.py dynamic
    python evaluate_fields.py
    python weight_sweep.py

inputs 包含字段输入、标注、标准词表、逐步加入的人审属性，以及查询问题和参考 SQL。运行器向模型提交字段名和描述，动态评测仅使用当前步骤之前已审核的属性。预测写入 fields，评测脚本从本次运行的预测计算指标。相同配置可续跑，更换模型服务或输入时请使用新的输出目录或干净工作副本。

## 分类与查询指标

classification/model.joblib 是原实验使用全部 203 条开发记录拟合的最终三分类模型。分类按 object、operate、result 的顺序输出。在线上传按字段名与描述分组，取最多五个不同的样本值，通过 text-embedding-v2 构建名称与局部上下文向量，结合从名称和描述提取的单位特征预测角色。上传响应的 classifications 给出角色和置信度，匹配器仍在全属性目录中检索。离线模式使用标准字段名进行入库和查询。

重新训练时先设置 MODEL_API_BASE 和 MODEL_API_KEY，再执行以下命令，从标注输入重新请求嵌入、拟合分类器并计算留出指标：

    python -m classification.prepare /tmp/matsir-features
    python -m classification.train /tmp/matsir-features


evaluation/query_metrics.py 对实际查询结果和参考结果计算 EX 及召回率。inputs/queries.json 包含训练和测试问题及参考 SQL，参考 SQL 使用 database/smart_small.sql 提供的属性 ID 和实体 ID。

## 测试

    python -m unittest system.test_flow apps.intent_engine.test_semantic_mapping apps.intent_engine.test_model_transport

## 500 条查询评测集

[完整评测集](inputs/sql_nl_test_samples_500_result_data.json)包含中文问题、英文问题、参考 SQL、参考结果和命中记录明细。使用 sample_id 与 inputs/queries.json 的 test 部分关联。参考 SQL 在 smart_small 上执行。

## 原始材料数据

[原始 JSON 数据目录](datasets/original/)收录 43 份材料数据文件，保留原文件名和内容。
