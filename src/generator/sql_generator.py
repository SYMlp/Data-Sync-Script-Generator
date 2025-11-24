from __future__ import annotations
import datetime

from src.config import SyncConfig
from src.core import MetaDataQuerier


class SqlGenerator:
    """
    SQL脚本生成器。

    根据传入的同步配置对象和元数据查询器，生成完整的、可执行的
    MySQL主从表数据同步存储过程脚本。
    """

    def __init__(
        self,
        config: SyncConfig,
        source_querier: MetaDataQuerier,
        target_querier: MetaDataQuerier
    ) -> None:
        """
        初始化SQL脚本生成器。

        Args:
            config (SyncConfig): 经过完整校验的同步配置对象。
            source_querier (MetaDataQuerier): 源数据库的元数据查询器。
            target_querier (MetaDataQuerier): 目标数据库的元数据查询器。
        """
        self._config: SyncConfig = config
        self._source_querier: MetaDataQuerier = source_querier
        self._target_querier: MetaDataQuerier = target_querier
        self._source_db_name: str = self._source_querier.get_db_name()
        self._target_db_name: str = self._target_querier.get_db_name()
        self._procedure_name: str = self._generate_procedure_name()
        self._source_main_pk: str = self._get_table_primary_key(self._config.table_relations.source_main_table, self._source_querier)
        self._target_main_pk: str = self._get_table_primary_key(self._config.table_relations.target_main_table, self._target_querier)
        self._target_child_pk: str = self._get_table_primary_key(self._config.table_relations.target_child_table, self._target_querier)

    def _generate_procedure_name(self) -> str:
        """根据表名和时间戳生成一个唯一的存储过程名。"""
        main_table = self._config.table_relations.source_main_table.split('.')[-1]
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        return f"Sync_{main_table}_{timestamp}"

    def _get_table_primary_key(self, table_name: str, querier: MetaDataQuerier) -> str:
        """获取指定表的第一个主键字段名。"""
        columns = querier.get_table_columns(table_name)
        for col in columns:
            if col['是否主键'] == 1:
                return col['字段名']
        raise ValueError(f"表 '{table_name}' 中未找到主键，无法生成脚本。")

    def _get_column_sql_type(self, table_name: str, column_name: str, querier: MetaDataQuerier) -> str:
        """获取指定表中指定字段的完整SQL数据类型字符串。"""
        columns = querier.get_table_columns(table_name)
        for col in columns:
            if col['字段名'] == column_name:
                col_type = col['字段类型']
                # 处理常见的带长度的类型
                if col_type.upper() in ['VARCHAR', 'CHAR', 'VARBINARY', 'BINARY']:
                    length = col.get('字符最大长度') or 255 # 提供默认长度
                    return f"{col_type}({length})"
                # 处理带精度和小数位的类型
                if col_type.upper() in ['DECIMAL', 'NUMERIC'] and '数字精度' in col and col['数字精度']:
                    return f"{col_type}({col['数字精度']}, {col['数字小数位数']})"
                return col_type
        raise ValueError(f"在表 '{table_name}' 中未找到字段 '{column_name}'。")

    def _get_source_table_ref(self, table_name: str) -> str:
        """
        获取带数据库前缀的源表名引用 (例如: `db_name`.`table_name`)。
        用于在目标库执行的SQL中正确引用源库的表。
        """
        if self._source_db_name and '.' not in table_name:
            return f"`{self._source_db_name}`.`{table_name}`"
        return f"`{table_name}`"

    def _get_target_table_ref(self, table_name: str) -> str:
        """
        获取带数据库前缀的目标表名引用 (例如: `db_name`.`table_name`)。
        确保在任何库执行脚本时都能定位到目标表。
        """
        if self._target_db_name and '.' not in table_name:
            return f"`{self._target_db_name}`.`{table_name}`"
        return f"`{table_name}`"

    def generate_script(self) -> dict[str, str]:
        """
        生成最终的SQL脚本的三个独立部分。

        Returns:
            dict[str, str]: 一个包含 'definition', 'call', 'drop' 三个部分的字典。
        """
        header = self._generate_header()
        variable_declarations = self._generate_variable_declarations()
        cursor_definition = self._generate_cursor_definition()
        main_loop_body = self._generate_main_loop_body()
        footer = self._generate_footer()

        procedure_definition = f"""
{header}
CREATE PROCEDURE {self._procedure_name}()
BEGIN
    -- 1. 声明变量
{variable_declarations}
    
    -- 2. 定义游标
{cursor_definition}
    
    -- 3. 定义事务异常处理
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        -- 直接使用用户变量避免 DECLARE 干扰诊断区域
        GET DIAGNOSTICS CONDITION 1
            @p_err_code = RETURNED_SQLSTATE, @p_err_msg = MESSAGE_TEXT;
            
        ROLLBACK;
        SELECT 
            '同步中断' AS status,
            step_info AS error_step,
            src_unique_key AS error_source_key,
            COALESCE(@p_err_code, 'UNKNOWN') AS sql_state,
            COALESCE(@p_err_msg, '无法获取详细错误信息，请参考 error_step 定位问题') AS error_detail;
    END;

    -- 4. (已改为循环内微事务)

    -- 5. 打开游标并开始循环
    OPEN main_cursor;
    main_loop: LOOP
        -- 从游标获取一行源主表数据
        FETCH main_cursor INTO src_main_id, src_unique_key;
        
        IF done = 1 THEN
            LEAVE main_loop;
        END IF;

        -- 开启单条记录的微事务
        START TRANSACTION;

        -- 核心同步逻辑
{main_loop_body}
        
        -- 提交单条记录的微事务
        COMMIT;

    END LOOP main_loop;
    CLOSE main_cursor;

    -- 6. 同步完成
    SELECT '同步成功' AS result;

END;
"""
        procedure_call, procedure_drop = footer.splitlines()

        return {
            "definition": procedure_definition.strip(),
            "call": procedure_call,
            "drop": procedure_drop
        }

    def generate_full_executable_script(self) -> str:
        """
        生成包含 前置清理 -> 定义 -> 调用 -> 后置清理 完整流程的单一脚本字符串。
        
        适用于：
        1. Streamlit 前端页面展示
        2. SQL 脚本文件下载
        3. 数据库工具直接运行
        
        Returns:
            str: 完整的可执行 SQL 脚本内容。
        """
        parts = self.generate_script()
        
        return f"""{parts['drop']}

DELIMITER $$

{parts['definition']}
$$

DELIMITER ;

-- ====================================================================
-- 执行同步过程
-- ====================================================================
{parts['call']}

-- ====================================================================
-- 清理环境 (删除临时存储过程)
-- ====================================================================
{parts['drop']}
"""

    def _get_sync_columns(self, table_name: str, querier: MetaDataQuerier, exclude_keys: list[str]) -> list[str]:
        """获取用于同步的字段列表，排除主键、自增键和用户指定的字段。"""
        columns = querier.get_table_columns(table_name)
        exclude_set = set(exclude_keys)
        sync_columns = []
        for col in columns:
            col_name = col['字段名']
            # 排除主键、自增字段
            if col['是否主键'] == 1 or col['是否自增'] == 1:
                continue
            # 排除用户指定的字段
            if col_name in exclude_set:
                continue
            sync_columns.append(col_name)
        return sync_columns

    def _generate_header(self) -> str:
        """生成脚本头部的注释说明。"""
        cfg = self._config
        return f"""
-- ====================================================================
-- 主从表数据同步脚本
-- 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- --------------------------------------------------------------------
-- 同步规则:
--   源主表: {cfg.table_relations.source_main_table}
--   源从表: {cfg.table_relations.source_child_table}
--   目标主表: {cfg.table_relations.target_main_table}
--   目标从表: {cfg.table_relations.target_child_table}
--   主表唯一标识: {cfg.sync_keys.main_table_unique_key}
--   主从关联字段: {cfg.sync_keys.master_child_foreign_key}
--   从表唯一标识: {cfg.sync_keys.child_table_unique_key}
--   过滤条件: {cfg.scope.source_filter_condition or '无'}
-- ====================================================================
"""

    def _generate_variable_declarations(self) -> str:
        """生成存储过程中所需的变量声明语句。"""
        cfg = self._config
        
        src_main_id_type = self._get_column_sql_type(
            cfg.table_relations.source_main_table, self._source_main_pk, self._source_querier
        )
        src_unique_key_type = self._get_column_sql_type(
            cfg.table_relations.source_main_table, cfg.sync_keys.main_table_unique_key, self._source_querier
        )
        dest_main_id_type = self._get_column_sql_type(
            cfg.table_relations.target_main_table, self._target_main_pk, self._target_querier
        )
        
        declarations = [
            "    DECLARE done INT DEFAULT 0;",
            "    DECLARE step_info VARCHAR(255) DEFAULT ''; -- 记录执行步骤用于排错",
            f"    DECLARE src_main_id {src_main_id_type}; -- 源主表主键",
            f"    DECLARE src_unique_key {src_unique_key_type}; -- 源主表唯一标识键",
            f"    DECLARE dest_main_id {dest_main_id_type}; -- 目标主表主键"
        ]
        
        return "\n".join(declarations)

    def _generate_cursor_definition(self) -> str:
        """生成游标定义语句。"""
        filter_clause = self._config.scope.source_filter_condition
        where_clause = f"WHERE {filter_clause}" if filter_clause else ""
        
        source_table_ref = self._get_source_table_ref(self._config.table_relations.source_main_table)

        return f"""
    DECLARE main_cursor CURSOR FOR
        SELECT `{self._source_main_pk}`, `{self._config.sync_keys.main_table_unique_key}` 
        FROM {source_table_ref}
        {where_clause};
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;
"""

    def _generate_main_loop_body(self) -> str:
        """生成主循环体内的核心同步逻辑。"""
        main_table_logic = self._generate_main_table_sync_logic()
        child_table_logic = self._generate_child_table_sync_logic()
        return f"""
{main_table_logic}
{child_table_logic}
"""

    def _generate_main_table_sync_logic(self) -> str:
        """生成主表同步的UPDATE和INSERT逻辑。"""
        cfg = self._config
        relations = cfg.table_relations
        keys = cfg.sync_keys
        
        # UPDATE时：应用排除列表（例如排除 create_user, create_time）
        update_sync_columns = self._get_sync_columns(
            relations.source_main_table, 
            self._source_querier, 
            cfg.scope.exclude_fields_main
        )
        
        # INSERT时：不应用排除列表，确保所有非空字段（如 create_user）都能被插入
        # 除非该字段在源表中也不存在
        insert_sync_columns = self._get_sync_columns(
            relations.source_main_table, 
            self._source_querier, 
            [] # 不排除任何字段
        )

        source_table_ref = self._get_source_table_ref(relations.source_main_table)
        target_table_ref = self._get_target_table_ref(relations.target_main_table)

        update_set_clause = ",\n".join([f"            dest.`{col}` = src.`{col}`" for col in update_sync_columns])
        insert_columns_str = ",\n".join([f"            `{col}`" for col in insert_sync_columns])
        insert_values_str = ",\n".join([f"            src.`{col}`" for col in insert_sync_columns])

        return f"""
        -- 5.1. 同步主表
        SET step_info = '5.1 Sync Main Table Check';
        SET dest_main_id = NULL;
        
        -- 使用独立的BEGIN-END块来隔离NOT FOUND处理，防止误触发外层循环的done标记
        BEGIN
            DECLARE CONTINUE HANDLER FOR NOT FOUND SET dest_main_id = NULL;
            SELECT `{self._source_main_pk}` INTO dest_main_id
            FROM {target_table_ref}
            WHERE `{keys.main_table_unique_key}` = src_unique_key;
        END;

        SET step_info = '5.1 Sync Main Table Write';
        IF dest_main_id IS NOT NULL THEN
            UPDATE {target_table_ref} dest
            INNER JOIN {source_table_ref} src ON src.`{self._source_main_pk}` = src_main_id
            SET 
{update_set_clause}
            WHERE dest.`{self._source_main_pk}` = dest_main_id;
        ELSE
            INSERT INTO {target_table_ref} (
{insert_columns_str}
            )
            SELECT 
{insert_values_str}
            FROM {source_table_ref} src
            WHERE src.`{self._source_main_pk}` = src_main_id;
            
            SET dest_main_id = LAST_INSERT_ID();
        END IF;
"""

    def _generate_child_table_sync_logic(self) -> str:
        """生成从表同步的DELETE, UPDATE, INSERT逻辑。"""
        cfg = self._config
        relations = cfg.table_relations
        keys = cfg.sync_keys

        # 用于UPDATE的字段列表，需要排除外键，避免错误更新
        update_columns = self._get_sync_columns(
            relations.source_child_table,
            self._source_querier,
            cfg.scope.exclude_fields_child + [keys.master_child_foreign_key]
        )
        
        # 用于INSERT的字段列表，仅排除外键，不应用exclude_fields_child
        # 确保插入完整数据
        insert_columns = self._get_sync_columns(
            relations.source_child_table,
            self._source_querier,
            [keys.master_child_foreign_key] 
        )

        source_child_ref = self._get_source_table_ref(relations.source_child_table)
        target_child_ref = self._get_target_table_ref(relations.target_child_table)

        update_set_clause = ",\n".join([f"            dest.`{col}` = src.`{col}`" for col in update_columns])
        
        insert_columns_str = ",\n".join([f"            `{col}`" for col in insert_columns])
        select_values_str = ",\n".join([f"            src.`{col}`" for col in insert_columns])


        return f"""
        -- 5.2. 同步从表
        SET step_info = '5.2 Sync Child Table Delete';
        --   a. 删除目标从表中不再存在的记录
        DELETE FROM {target_child_ref}
        WHERE `{keys.master_child_foreign_key}` = dest_main_id
          AND `{keys.child_table_unique_key}` NOT IN (
            SELECT `{keys.child_table_unique_key}`
            FROM {source_child_ref}
            WHERE `{keys.master_child_foreign_key}` = src_main_id
          );

        SET step_info = '5.2 Sync Child Table Update';
        --   b. 更新目标从表中已存在的记录
        UPDATE {target_child_ref} dest
        INNER JOIN {source_child_ref} src 
            ON dest.`{keys.master_child_foreign_key}` = dest_main_id 
           AND dest.`{keys.child_table_unique_key}` = src.`{keys.child_table_unique_key}`
        SET
{update_set_clause}
        WHERE src.`{keys.master_child_foreign_key}` = src_main_id;

        SET step_info = '5.2 Sync Child Table Insert';
        --   c. 插入源从表中新增的记录
        INSERT INTO {target_child_ref} (
            `{keys.master_child_foreign_key}`,
{insert_columns_str}
        )
        SELECT
            dest_main_id,
{select_values_str}
        FROM {source_child_ref} src
        LEFT JOIN {target_child_ref} dest
            ON dest.`{keys.master_child_foreign_key}` = dest_main_id
           AND dest.`{keys.child_table_unique_key}` = src.`{keys.child_table_unique_key}`
        WHERE src.`{keys.master_child_foreign_key}` = src_main_id
          AND dest.`{self._target_child_pk}` IS NULL;
"""

    def _generate_footer(self) -> str:
        """生成脚本的调用和删除语句。"""
        return f"CALL {self._procedure_name}();\nDROP PROCEDURE IF EXISTS {self._procedure_name};"