import unittest
from unittest.mock import Mock

# Import the classes to be tested
from src.services import ConfigService
from src.core import MetaDataQuerier

class TestConfigService(unittest.TestCase):
    """
    针对 ConfigService 的单元测试套件。
    """

    def setUp(self):
        """
        在每个测试方法运行前执行，用于设置模拟对象。
        """
        # 1. 创建模拟的 MetaDataQuerier
        self.mock_source_querier = Mock(spec=MetaDataQuerier)
        self.mock_target_querier = Mock(spec=MetaDataQuerier)

        # 2. 预设模拟对象的返回值
        # 模拟源数据库中有 't_main_src', 't_child_src' 两张表
        self.mock_source_querier.get_all_tables.return_value = ['t_main_src', 't_child_src']
        # 模拟目标数据库中有 't_main_tgt', 't_child_tgt' 两张表
        self.mock_target_querier.get_all_tables.return_value = ['t_main_tgt', 't_child_tgt']
        
        # 模拟表结构 - 假设源表和目标表结构兼容
        compatible_schema = [
            {'字段名': 'id', '字段类型': 'int', '是否主键': 1, '是否自增': 1},
            {'字段名': 'name', '字段类型': 'varchar', '是否主键': 0, '是否自增': 0},
            {'字段名': 'service_id', '字段类型': 'int', '是否主键': 0, '是否自增': 0},
        ]
        self.mock_source_querier.get_table_columns.return_value = compatible_schema
        self.mock_target_querier.get_table_columns.return_value = compatible_schema

        # 3. 创建被测试的 ConfigService 实例，注入模拟对象
        self.config_service = ConfigService(
            source_querier=self.mock_source_querier,
            target_querier=self.mock_target_querier
        )

    def test_configure_table_relations_success(self):
        """
        测试：当所有表都存在且结构兼容时，表关系配置应成功。
        """
        # 调用被测试的方法
        self.config_service.configure_table_relations(
            source_main='t_main_src',
            source_child='t_child_src',
            target_main='t_main_tgt',
            target_child='t_child_tgt'
        )
        
        # 断言：检查配置是否已正确存储
        config = self.config_service.get_current_config()
        self.assertEqual(config.table_relations.source_main_table, 't_main_src')
        self.assertEqual(config.table_relations.target_main_table, 't_main_tgt')

    def test_configure_table_relations_table_not_found(self):
        """
        测试：当源主表不存在时，应抛出 ValueError。
        """
        # 使用 assertRaises 上下文管理器来断言特定的异常被抛出
        with self.assertRaises(ValueError) as context:
            self.config_service.configure_table_relations(
                source_main='non_existent_table', # 一个不存在的表
                source_child='t_child_src',
                target_main='t_main_tgt',
                target_child='t_child_tgt'
            )
        
        # 断言：检查异常信息是否符合预期
        self.assertIn("源数据库中未找到主表: non_existent_table", str(context.exception))

    def test_configure_table_relations_schema_incompatible(self):
        """
        测试：当主表结构不兼容时（缺少字段），应抛出 ValueError。
        """
        # 覆盖 setUp 中的模拟设置，让目标表缺少一个字段
        incompatible_schema_target = [
            {'字段名': 'id', '字段类型': 'int', '是否主键': 1, '是否自增': 1},
            # 缺少 'name' 字段
        ]
        self.mock_target_querier.get_table_columns.return_value = incompatible_schema_target

        with self.assertRaises(ValueError) as context:
            self.config_service.configure_table_relations(
                source_main='t_main_src',
                source_child='t_child_src',
                target_main='t_main_tgt',
                target_child='t_child_tgt'
            )
            
        self.assertIn("结构不兼容: 目标主表 't_main_tgt' 缺少字段 'name'", str(context.exception))

if __name__ == '__main__':
    unittest.main()
