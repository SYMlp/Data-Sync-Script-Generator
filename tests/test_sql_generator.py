import unittest
from unittest.mock import Mock

from src.generator import SqlGenerator
from src.config import SyncConfig, TableRelationConfig, SyncKeysConfig, SyncScopeConfig
from src.core import MetaDataQuerier

class TestSqlGenerator(unittest.TestCase):
    """
    针对 SqlGenerator 的单元测试套件。
    """

    def setUp(self):
        """
        设置一个完整、固定的 SyncConfig 和模拟的 Querier，
        作为 SqlGenerator 的输入。
        """
        # 1. 创建一个固定的、完整的配置对象
        self.config = SyncConfig(
            table_relations=TableRelationConfig(
                source_main_table='db_source.t_users',
                source_child_table='db_source.t_user_profiles',
                target_main_table='db_target.t_users',
                target_child_table='db_target.t_user_profiles'
            ),
            sync_keys=SyncKeysConfig(
                main_table_unique_key='username',
                master_child_foreign_key='user_id',
                child_table_unique_key='profile_key'
            ),
            scope=SyncScopeConfig(
                source_filter_condition="is_active = 1",
                exclude_fields_main=['last_login'],
                exclude_fields_child=['last_updated']
            )
        )

        # 2. 创建模拟的 Querier
        self.mock_source_querier = Mock(spec=MetaDataQuerier)
        self.mock_target_querier = Mock(spec=MetaDataQuerier)

        # 3. 预设模拟 Querier 的返回值
        main_schema = [
            {'字段名': 'id', '字段类型': 'int', '是否主键': 1, '是否自增': 1},
            {'字段名': 'username', '字段类型': 'varchar', '是否主键': 0, '是否自增': 0},
            {'字段名': 'email', '字段类型': 'varchar', '是否主键': 0, '是否自增': 0},
            {'字段名': 'last_login', '字段类型': 'timestamp', '是否主键': 0, '是否自增': 0},
        ]
        child_schema = [
            {'字段名': 'profile_id', '字段类型': 'int', '是否主键': 1, '是否自增': 1},
            {'字段名': 'user_id', '字段类型': 'int', '是否主键': 0, '是否自增': 0},
            {'字段名': 'profile_key', '字段类型': 'varchar', '是否主键': 0, '是否自增': 0},
            {'字段名': 'profile_value', '字段类型': 'varchar', '是否主键': 0, '是否自增': 0},
            {'字段名': 'last_updated', '字段类型': 'timestamp', '是否主键': 0, '是否自增': 0},
        ]
        self.mock_source_querier.get_table_columns.side_effect = lambda table_name: main_schema if 'users' in table_name else child_schema
        self.mock_target_querier.get_table_columns.side_effect = lambda table_name: main_schema if 'users' in table_name else child_schema

        # 4. 初始化被测试的 SqlGenerator
        self.generator = SqlGenerator(
            config=self.config,
            source_querier=self.mock_source_querier,
            target_querier=self.mock_target_querier
        )

    def test_generate_script_header(self):
        """
        测试：生成的脚本头部注释是否正确包含了所有配置信息。
        """
        script = self.generator.generate_script()
        self.assertIn("--   源主表: db_source.t_users", script)
        self.assertIn("--   主表唯一标识: username", script)
        self.assertIn("--   过滤条件: is_active = 1", script)

    def test_main_table_update_logic(self):
        """
        测试：主表UPDATE语句是否正确生成，并排除了例外字段。
        """
        script = self.generator.generate_script()
        # 断言 UPDATE 语句中包含了需要同步的 'email' 字段
        self.assertIn("dest.`email` = src.`email`", script)
        # 断言 UPDATE 语句中不包含被排除的 'last_login' 字段
        self.assertNotIn("dest.`last_login` = src.`last_login`", script)

    def test_child_table_insert_logic(self):
        """
        测试：从表INSERT语句的字段列表是否正确。
        """
        script = self.generator.generate_script()
        
        # 预期的INSERT字段列表，包含了外键和需要同步的字段
        expected_insert_columns = "INSERT INTO db_target.t_user_profiles (\n            `user_id`,\n            `profile_key`,\n            `profile_value`\n        )"
        
        # 使用 replace 来忽略SQL格式化中的空白差异
        self.assertIn(
            expected_insert_columns.replace(" ", "").replace("\n", ""),
            script.replace(" ", "").replace("\n", "")
        )
        self.assertNotIn("last_updated", script) # 确认例外字段被排除
        
    def test_child_table_delete_logic(self):
        """
        测试：从表DELETE语句的逻辑是否正确使用了配置的键。
        """
        script = self.generator.generate_script()
        
        # 将断言分解为多个更小、更稳定的部分
        self.assertIn("DELETE FROM db_target.t_user_profiles", script)
        self.assertIn("WHERE `user_id` = dest_main_id", script)
        self.assertIn("AND `profile_key` NOT IN", script)
        self.assertIn("SELECT `profile_key`", script)
        self.assertIn("FROM db_source.t_user_profiles", script)
        self.assertIn("WHERE `user_id` = src_main_id", script)

if __name__ == '__main__':
    unittest.main()
