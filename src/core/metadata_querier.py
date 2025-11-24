from __future__ import annotations

from typing import Any

from .db_connector import DatabaseConnector


class MetaDataQuerier:
    """
    元数据查询器，负责从数据库中获取表结构、字段属性等信息。
    """

    def __init__(self, db_connector: DatabaseConnector) -> None:
        """
        初始化元数据查询器。

        Args:
            db_connector (DatabaseConnector): 一个有效的数据库连接器实例。
        """
        self._db_connector: DatabaseConnector = db_connector

    def get_db_name(self) -> str | None:
        """获取查询器关联的数据库名称"""
        return self._db_connector.get_db_name()

    def get_all_tables(self) -> list[str] | None:
        """
        获取当前数据库中的所有表名。

        Returns:
            list[str] | None: 如果成功，返回一个包含所有表名的列表；
                              如果数据库未连接或发生错误，则返回 None。
        """
        cursor = self._db_connector.get_cursor()
        if not cursor:
            return None

        try:
            cursor.execute("SHOW TABLES;")
            tables = [table[0] for table in cursor.fetchall()]
            return tables
        except Exception as e:
            print(f"查询所有表失败: {e}")
            return None
        finally:
            cursor.close()

    def get_table_comment(self, table_name: str) -> str | None:
        """
        获取指定表的注释。

        Args:
            table_name (str): 要查询的表名。

        Returns:
            str | None: 表的注释信息，或在发生错误时返回 None。
        """
        cursor = self._db_connector.get_cursor()
        if not cursor:
            return None
        
        query = """
            SELECT table_comment 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() AND table_name = %s;
        """
        try:
            cursor.execute(query, (table_name,))
            result = cursor.fetchone()
            return result[0] if result else ""
        except Exception as e:
            print(f"查询表注释失败: {e}")
            return None
        finally:
            cursor.close()

    def get_table_columns(self, table_name: str) -> list[dict[str, Any]] | None:
        """
        获取指定表的字段详细信息。

        查询结果将遵循需求文档中的格式，包含字段名、类型、是否主键等。

        Args:
            table_name (str): 要查询的表名。

        Returns:
            list[dict[str, Any]] | None: 包含字段信息的字典列表，或在发生错误时返回 None。
        """
        cursor = self._db_connector.get_cursor()
        if not cursor:
            return None

        query = """
            SELECT 
                column_name AS 字段名,
                data_type AS 字段类型,
                CASE WHEN column_key = 'PRI' THEN 1 ELSE 0 END AS 是否主键,
                column_key AS 键类型,
                CASE WHEN extra LIKE '%%auto_increment%%' THEN 1 ELSE 0 END AS 是否自增,
                column_comment AS 字段注释
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() AND table_name = %s;
        """
        try:
            cursor.execute(query, (table_name,))
            columns = [
                dict(zip([i[0] for i in cursor.description], row))
                for row in cursor.fetchall()
            ]
            return columns
        except Exception as e:
            print(f"查询表字段信息失败: {e}")
            return None
        finally:
            cursor.close()
