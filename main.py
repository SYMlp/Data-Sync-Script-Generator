# 整合所有模块，编写一个 main.py 示例
# 演示如何从头到尾使用我们创建的所有组件

# 1. 导入所有需要的类
from src.core import DatabaseConnector, MetaDataQuerier
from src.config import SyncConfig
from src.services import ConfigService
from src.generator import SqlGenerator
from src.utils import FileExporter

# 2. 定义数据库连接配置 (请根据您的本地环境修改)
# 注意：为了测试，源库和目标库暂时使用同一个库
db_config_source = {
    'host': '127.0.0.1',
    'port': 3310,
    'user': 'root',
    'password': '123456', # 请替换为您的密码
    'database': 'test' # 请替换为您的源数据库名
}

db_config_target = {
    'host': '127.0.0.1',
    'port': 3310,
    'user': 'root',
    'password': '123456', # 请替换为您的密码
    'database': 'test' # 请替换为您的目标数据库名
}

# 3. 准备测试数据 (如果数据库和表不存在，请先手动创建)
# 您可以使用 docs/主从表同步脚本生成工具平台需求文档.md 中的表结构示例
# CREATE DATABASE db_source;
# CREATE DATABASE db_target;
# USE db_source;
# CREATE TABLE t_kl_service_instance (id INT PRIMARY KEY AUTO_INCREMENT, service_name VARCHAR(255) UNIQUE, is_del TINYINT, tenant_id INT);
# CREATE TABLE t_kl_service_instance_property (id INT PRIMARY KEY AUTO_INCREMENT, service_id INT, param VARCHAR(255), value VARCHAR(255));
# INSERT INTO t_kl_service_instance VALUES (1, 'UserService', 0, 1001), (2, 'OrderService', 0, 1001), (3, 'ProductService', 1, 1001);
# INSERT INTO t_kl_service_instance_property VALUES (1, 1, 'timeout', '5000'), (2, 1, 'retry', '3'), (3, 2, 'max_orders', '100');
# USE db_target;
# CREATE TABLE t_kl_service_instance (id INT PRIMARY KEY AUTO_INCREMENT, service_name VARCHAR(255) UNIQUE, is_del TINYINT, tenant_id INT, create_time TIMESTAMP);
# CREATE TABLE t_kl_service_instance_property (id INT PRIMARY KEY AUTO_INCREMENT, service_id INT, param VARCHAR(255), value VARCHAR(255), create_time TIMESTAMP);


def main():
    """主函数，演示整个流程"""
    print("--- 流程开始 ---")
    
    # 使用 with 语句确保数据库连接自动关闭
    with DatabaseConnector(db_config_source) as source_db, \
         DatabaseConnector(db_config_target) as target_db:

        if not source_db.is_connected() or not target_db.is_connected():
            print("数据库连接失败，流程终止。")
            return

        # 4. 初始化元数据查询器
        source_querier = MetaDataQuerier(source_db)
        target_querier = MetaDataQuerier(target_db)

        # 5. 初始化配置服务
        config_service = ConfigService(source_querier, target_querier)

        try:
            # 6. 配置并校验规则
            # 6.1 配置表关系
            config_service.configure_table_relations(
                source_main='t_kl_service_instance',
                source_child='t_kl_service_instance_property',
                target_main='t_kl_service_instance_dest',
                target_child='t_kl_service_instance_property_dest'
            )
            
            # 6.2 配置同步键
            config_service.configure_sync_keys(
                main_table_unique_key='service_name',
                master_child_foreign_key='service_id',
                child_table_unique_key='param'
            )

            # 6.3 配置同步范围
            config_service.configure_scope(
                source_filter_condition="is_del = 0 AND service_name like '%南向%'",
                exclude_fields_main=['create_time'],
                exclude_fields_child=['create_time']
            )

            # 7. 获取最终的、经过完整校验的配置对象
            final_config = config_service.get_current_config()
            print("\n--- 配置完成并通过校验 ---")
            print(final_config)

            # 8. 初始化脚本生成器
            generator = SqlGenerator(final_config, source_querier, target_querier)
            
            # 9. 生成SQL脚本的各个部分
            sql_parts = generator.generate_script()
            print("\n--- SQL脚本生成成功 ---")
            print("-- [DEFINITION] --\n" + sql_parts['definition'])
            print("\n-- [CALL] --\n" + sql_parts['call'])
            print("\n-- [DROP] --\n" + sql_parts['drop'])

            # 10. 导出脚本到文件 (此处只导出定义部分)
            FileExporter.export_sql_script(sql_parts['definition'], final_config)
            
            # 11. 分步执行脚本
            print("\n--- 准备在目标数据库分步执行脚本 ---")
            try:
                print("步骤 1/3: 定义存储过程...")
                if not target_db.execute_script(sql_parts['definition']):
                    raise RuntimeError("定义存储过程失败")
                print("步骤 2/3: 调用存储过程...")
                if not target_db.execute_script(sql_parts['call']):
                    raise RuntimeError("调用存储过程失败")
                print("步骤 3/3: 删除存储过程...")
                if not target_db.execute_script(sql_parts['drop']):
                    raise RuntimeError("删除存储过程失败")
                print("脚本分步执行成功！")
            except Exception as e:
                print(f"脚本执行过程中发生错误: {e}")

        except ValueError as e:
            print(f"\n配置校验失败: {e}")
        
    print("\n--- 流程结束 ---")

if __name__ == "__main__":
    main()
