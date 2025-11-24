import datetime
import os
from src.config import SyncConfig

class FileExporter:
    """
    负责将生成的SQL脚本导出到文件。
    """

    @staticmethod
    def export_sql_script(
        sql_content: str,
        config: SyncConfig,
        output_dir: str = "data"
    ) -> str:
        """
        将SQL脚本内容保存到.sql文件中。

        文件名将根据需求文档自动生成。

        Args:
            sql_content (str): 由SqlGenerator生成的完整SQL脚本。
            config (SyncConfig): 用于生成文件名的同步配置对象。
            output_dir (str, optional): 导出的目标目录。默认为 "data"。

        Returns:
            str: 成功保存的文件路径。
            
        Raises:
            IOError: 如果文件写入失败。
        """
        # 提取不带数据库名的表名
        source_main_table = config.table_relations.source_main_table.split('.')[-1]
        target_main_table = config.table_relations.target_main_table.split('.')[-1]
        timestamp = datetime.datetime.now().strftime('%Y%m%d')

        filename = f"同步_{source_main_table}_{target_main_table}_{timestamp}.sql"
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        file_path = os.path.join(output_dir, filename)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(sql_content)
            print(f"脚本已成功导出到: {file_path}")
            return file_path
        except IOError as e:
            print(f"错误：无法将脚本写入文件 {file_path}。原因: {e}")
            raise
