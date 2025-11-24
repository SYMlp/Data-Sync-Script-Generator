from dataclasses import dataclass, field


@dataclass
class TableRelationConfig:
    """
    存储主从表关系配置。
    
    Attributes:
        source_main_table (str): 源主表全名 (e.g., 'db_source.t_main')。
        source_child_table (str): 源从表全名。
        target_main_table (str): 目标主表全名。
        target_child_table (str): 目标从表全名。
    """
    source_main_table: str = ""
    source_child_table: str = ""
    target_main_table: str = ""
    target_child_table: str = ""


@dataclass
class SyncKeysConfig:
    """
    存储同步依据的关键字段配置。
    
    Attributes:
        main_table_unique_key (str): 用于匹配主表记录的唯一标识字段名。
        master_child_foreign_key (str): 从表中关联主表主键的外键字段名。
        child_table_unique_key (str): 在同一主表记录下，用于匹配从表记录的唯一标识字段名。
    """
    main_table_unique_key: str = ""
    master_child_foreign_key: str = ""
    child_table_unique_key: str = ""


@dataclass
class SyncScopeConfig:
    """
    存储同步范围与例外规则。
    
    Attributes:
        source_filter_condition (str): 源主表的过滤条件 (WHERE子句内容)。
        exclude_fields_main (list[str]): 目标主表中需要排除、不同步的字段列表。
        exclude_fields_child (list[str]): 目标从表中需要排除、不同步的字段列表。
    """
    source_filter_condition: str = ""
    exclude_fields_main: list[str] = field(default_factory=list)
    exclude_fields_child: list[str] = field(default_factory=list)


@dataclass
class SyncConfig:
    """
    总配置模型，聚合所有同步规则配置。
    
    这是一个顶层容器，整合了表关系、同步键和同步范围等所有配置信息，
    将作为最终生成SQL脚本的核心数据依据。
    """
    table_relations: TableRelationConfig = field(default_factory=TableRelationConfig)
    sync_keys: SyncKeysConfig = field(default_factory=SyncKeysConfig)
    scope: SyncScopeConfig = field(default_factory=SyncScopeConfig)
