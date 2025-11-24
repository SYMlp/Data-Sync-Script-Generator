from __future__ import annotations

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import Cursor
from pymysql.err import Error


class DatabaseConnector:
    """
    数据库连接器，负责管理与MySQL数据库的连接（使用PyMySQL）。
    """

    def __init__(self, db_config: dict[str, str]) -> None:
        """
        初始化数据库连接器。
        Args:
            db_config (dict[str, str]): 数据库连接配置。
        """
        self._connection_config: dict[str, str] = db_config
        self._connection: Connection | None = None

    def connect(self) -> bool:
        """
        建立与数据库的连接。
        """
        if self.is_connected():
            self.disconnect()
        
        try:
            # PyMySQL 的 connect 函数参数名与 mysql-connector 略有不同
            config = self._connection_config.copy()
            config['port'] = int(config.get('port', 3306)) # port 需要是整数
            self._connection = pymysql.connect(**config)
            print("数据库连接成功 (使用 PyMySQL)。")
            return True
        except Error as e:
            print(f"数据库连接失败: {e}")
            self._connection = None
            return False

    def disconnect(self) -> None:
        """
        关闭数据库连接。
        """
        if self._connection:
            self._connection.close()
            print("数据库连接已关闭。")
        self._connection = None

    def is_connected(self) -> bool:
        """
        检查当前是否存在有效的数据库连接。
        """
        return self._connection is not None and self._connection.open

    def get_cursor(self) -> Cursor | None:
        """
        获取一个用于执行SQL语句的游标对象。
        """
        if not self.is_connected():
            print("错误：数据库未连接，无法获取游标。")
            return None
        return self._connection.cursor()

    def get_db_name(self) -> str | None:
        """
        获取当前连接的数据库名称。
        """
        return self._connection_config.get('database')

    def execute_script(self, script_content: str) -> bool:
        """
        在当前数据库连接上执行一个包含多条语句的SQL脚本。
        PyMySQL 的 cursor.execute() 默认就能处理以分号分隔的多语句脚本。
        """
        cursor = self.get_cursor()
        if not cursor:
            return False

        try:
            cursor.execute(script_content)
            self._connection.commit()
            print("脚本单步执行成功。")
            return True
        except Error as e:
            print(f"脚本执行失败: {e}")
            self._connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def __enter__(self) -> DatabaseConnector:
        """
        实现上下文管理器协议的 __enter__ 方法。
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        实现上下文管理器协议的 __exit__ 方法。
        """
        self.disconnect()
