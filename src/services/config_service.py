from __future__ import annotations

from src.config import SyncConfig, TableRelationConfig, SyncKeysConfig, SyncScopeConfig
from src.core import MetaDataQuerier


class ConfigService:
    """
    配置服务，负责处理和校验所有与同步相关的用户配置。
    
    该服务是业务逻辑的核心，它接收用户输入，使用元数据查询器进行校验，
    并最终构建出完整、有效的 SyncConfig 配置对象。
    """

    def __init__(
        self,
        source_querier: MetaDataQuerier,
        target_querier: MetaDataQuerier
    ) -> None:
        """
        初始化配置服务。

        Args:
            source_querier (MetaDataQuerier): 已连接到源数据库的元数据查询器。
            target_querier (MetaDataQuerier): 已连接到目标数据库的元数据查询器。
        """
        self._source_querier: MetaDataQuerier = source_querier
        self._target_querier: MetaDataQuerier = target_querier
        self._config: SyncConfig = SyncConfig()

    def configure_table_relations(
        self,
        source_main: str,
        source_child: str,
        target_main: str,
        target_child: str
    ) -> None:
        """
        配置并校验主从表的对应关系。

        此方法会执行需求文档中要求的各项校验：
        1. 检查所有指定的表是否存在于各自的数据库中。
        2. 校验源主/从表与目标主/从表的结构是否兼容。

        Args:
            source_main (str): 源主表名。
            source_child (str): 源从表名。
            target_main (str): 目标主表名。
            target_child (str): 目标从表名。
            
        Raises:
            ValueError: 当任何校验失败时，抛出此异常并附带详细错误信息。
        """
        print("开始校验表关系配置...")
        # 1. 校验表存在性
        self._validate_table_existence(source_main, source_child, target_main, target_child)

        # 2. 校验表结构兼容性
        self._validate_schema_compatibility(source_main, target_main, "主表")
        self._validate_schema_compatibility(source_child, target_child, "从表")

        # 3. 更新配置对象
        self._config.table_relations = TableRelationConfig(
            source_main_table=source_main,
            source_child_table=source_child,
            target_main_table=target_main,
            target_child_table=target_child
        )
        print("表关系配置成功并通过校验。")

    def configure_sync_keys(
        self,
        main_table_unique_key: str,
        master_child_foreign_key: str,
        child_table_unique_key: str
    ) -> None:
        """
        配置并校验用于同步的各类关键字段。

        Args:
            main_table_unique_key (str): 用于匹配主表的唯一标识字段。
            master_child_foreign_key (str): 从表中关联主表的外键字段。
            child_table_unique_key (str): 用于在从表中唯一识别记录的字段。

        Raises:
            ValueError: 如果配置的表关系不存在或字段校验失败。
        """
        print("开始校验同步关键字段配置...")
        if not self._config.table_relations.source_main_table:
            raise ValueError("请先配置并校验主从表关系。")

        # 校验主表唯一键是否存在于源主表和目标主表
        self._validate_key_existence(main_table_unique_key, self._config.table_relations.source_main_table, self._source_querier, "源主表唯一键")
        self._validate_key_existence(main_table_unique_key, self._config.table_relations.target_main_table, self._target_querier, "目标主表唯一键")

        # 校验主从外键是否存在于源从表和目标从表
        self._validate_key_existence(master_child_foreign_key, self._config.table_relations.source_child_table, self._source_querier, "源从表外键")
        self._validate_key_existence(master_child_foreign_key, self._config.table_relations.target_child_table, self._target_querier, "目标从表外键")

        # 校验从表唯一键是否存在于源从表和目标从表
        self._validate_key_existence(child_table_unique_key, self._config.table_relations.source_child_table, self._source_querier, "源从表唯一键")
        self._validate_key_existence(child_table_unique_key, self._config.table_relations.target_child_table, self._target_querier, "目标从表唯一键")

        self._config.sync_keys = SyncKeysConfig(
            main_table_unique_key=main_table_unique_key,
            master_child_foreign_key=master_child_foreign_key,
            child_table_unique_key=child_table_unique_key
        )
        print("同步关键字段配置成功并通过校验。")

    def configure_scope(
        self,
        source_filter_condition: str,
        exclude_fields_main: list[str],
        exclude_fields_child: list[str]
    ) -> None:
        """
        配置同步的范围，包括过滤条件和需要排除的字段。

        Args:
            source_filter_condition (str): 应用于源主表的WHERE过滤子句。
            exclude_fields_main (list[str]): 主表中需要排除同步的字段列表。
            exclude_fields_child (list[str]): 从表中需要排除同步的字段列表。
        """
        print("开始校验同步范围配置...")
        if not self._config.table_relations.source_main_table:
            raise ValueError("请先配置并校验主从表关系。")
            
        # 校验排除字段的有效性
        self._validate_key_existence(exclude_fields_main, self._config.table_relations.target_main_table, self._target_querier, "主表排除字段")
        self._validate_key_existence(exclude_fields_child, self._config.table_relations.target_child_table, self._target_querier, "从表排除字段")

        self._config.scope = SyncScopeConfig(
            source_filter_condition=source_filter_condition,
            exclude_fields_main=exclude_fields_main,
            exclude_fields_child=exclude_fields_child
        )
        print("同步范围配置成功。")


    def _validate_table_existence(
        self, source_main: str, source_child: str, target_main: str, target_child: str
    ) -> None:
        """检查所有指定的表是否存在。"""
        source_tables = self._source_querier.get_all_tables()
        if source_main not in source_tables:
            raise ValueError(f"源数据库中未找到主表: {source_main}")
        if source_child not in source_tables:
            raise ValueError(f"源数据库中未找到从表: {source_child}")

        target_tables = self._target_querier.get_all_tables()
        if target_main not in target_tables:
            raise ValueError(f"目标数据库中未找到主表: {target_main}")
        if target_child not in target_tables:
            raise ValueError(f"目标数据库中未找到从表: {target_child}")
        print("所有表均已在数据库中找到。")

    def _validate_schema_compatibility(self, source_table: str, target_table: str, table_type: str) -> None:
        """校验源表和目标表的结构是否兼容。"""
        source_columns = self._source_querier.get_table_columns(source_table)
        target_columns_map = {
            col['字段名']: col for col in self._target_querier.get_table_columns(target_table)
        }

        for src_col in source_columns:
            col_name = src_col['字段名']
            if col_name not in target_columns_map:
                raise ValueError(f"结构不兼容: 目标{table_type} '{target_table}' 缺少字段 '{col_name}'")
            
            tgt_col = target_columns_map[col_name]
            if src_col['字段类型'] != tgt_col['字段类型']:
                raise ValueError(
                    f"结构不兼容: {table_type} '{target_table}' 字段 '{col_name}' 类型不匹配"
                    f" (源: {src_col['字段类型']}, 目标: {tgt_col['字段类型']})"
                )
        print(f"{table_type} '{source_table}' 与 '{target_table}' 结构兼容性校验通过。")

    def _validate_key_existence(self, keys: str | list[str], table_name: str, querier: MetaDataQuerier, key_type: str) -> None:
        """检查单个或多个关键字段是否存在于指定表中。"""
        columns = querier.get_table_columns(table_name)
        column_names = {col['字段名'] for col in columns}

        keys_to_check = [keys] if isinstance(keys, str) else keys

        for key in keys_to_check:
            if key not in column_names:
                raise ValueError(f"校验失败: {key_type} '{key}' 在表 '{table_name}' 中不存在。")
        
        print(f"校验通过: {key_type} 在表 '{table_name}' 中均存在。")

    def get_current_config(self) -> SyncConfig:
        """
        获取当前已配置和校验通过的同步配置对象。
        """
        return self._config
