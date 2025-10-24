"""
Configuration module for Databricks Pipeline
Manages connection settings, table configurations, and pipeline parameters
"""

import os
from typing import Dict, List, Any
from dataclasses import dataclass, field
import json


@dataclass
class SourceConfig:
    """Configuration for Azure SQL Server source."""
    server: str
    database: str
    username: str
    password: str
    port: int = 1433
    encrypt: bool = True
    trust_server_certificate: bool = False
    connection_timeout: int = 30
    fetch_size: int = 10000
    
    def to_jdbc_url(self) -> str:
        """Convert configuration to JDBC URL."""
        jdbc_url = (
            f"jdbc:sqlserver://{self.server}:{self.port};"
            f"database={self.database};"
            f"encrypt={'true' if self.encrypt else 'false'};"
            f"trustServerCertificate={'true' if self.trust_server_certificate else 'false'};"
            f"hostNameInCertificate=*.database.windows.net;"
            f"loginTimeout={self.connection_timeout};"
        )
        return jdbc_url
    
    def to_connection_properties(self) -> Dict[str, str]:
        """Get JDBC connection properties."""
        return {
            "user": self.username,
            "password": self.password,
            "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver"
        }


@dataclass
class TargetConfig:
    """Configuration for Databricks target."""
    catalog: str = "main"
    schema: str = "bronze"
    watermark_table: str = "pipeline_watermarks"
    checkpoint_location: str = "/mnt/delta/checkpoints"
    optimize_write: bool = True
    auto_compact: bool = True
    optimized_write_max_file_size: str = "128MB"


@dataclass
class TableConfig:
    """Configuration for individual table migration."""
    source_table: str
    target_table: str
    watermark_column: str
    merge_keys: List[str] = field(default_factory=list)
    partition_columns: List[str] = field(default_factory=list)
    custom_columns: List[str] = field(default_factory=list)
    exclude_columns: List[str] = field(default_factory=list)
    where_clause: str = ""
    batch_size: int = 10000
    enable_merge: bool = True
    enable_schema_evolution: bool = True
    data_quality_checks: Dict[str, Any] = field(default_factory=dict)
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    
    def validate(self) -> bool:
        """Validate table configuration."""
        if not self.source_table:
            raise ValueError("source_table is required")
        if not self.watermark_column:
            raise ValueError("watermark_column is required")
        if self.enable_merge and not self.merge_keys:
            raise ValueError("merge_keys are required when enable_merge is True")
        return True


@dataclass
class PipelineConfig:
    """Main pipeline configuration."""
    source: SourceConfig
    target: TargetConfig
    tables: List[TableConfig]
    parallel_tables: int = 1
    max_retries: int = 3
    retry_delay_seconds: int = 60
    enable_notifications: bool = True
    notification_email: str = ""
    enable_data_quality: bool = True
    enable_lineage_tracking: bool = True
    tags: Dict[str, str] = field(default_factory=dict)


class ConfigManager:
    """Manages loading and validation of pipeline configurations."""
    
    @staticmethod
    def load_from_file(config_path: str) -> PipelineConfig:
        """Load configuration from JSON file."""
        with open(config_path, 'r') as f:
            config_dict = json.load(f)
        return ConfigManager.from_dict(config_dict)
    
    @staticmethod
    def load_from_dbutils(dbutils, scope: str) -> PipelineConfig:
        """Load configuration from Databricks secrets."""
        source_config = SourceConfig(
            server=dbutils.secrets.get(scope, "azure-sql-server"),
            database=dbutils.secrets.get(scope, "azure-sql-database"),
            username=dbutils.secrets.get(scope, "azure-sql-username"),
            password=dbutils.secrets.get(scope, "azure-sql-password"),
            port=int(dbutils.secrets.get(scope, "azure-sql-port", "1433"))
        )
        
        target_config = TargetConfig(
            catalog=dbutils.secrets.get(scope, "target-catalog", "main"),
            schema=dbutils.secrets.get(scope, "target-schema", "bronze")
        )
        
        # Load table configurations from a config file or define them here
        tables = ConfigManager._get_default_table_configs()
        
        return PipelineConfig(
            source=source_config,
            target=target_config,
            tables=tables
        )
    
    @staticmethod
    def from_dict(config_dict: Dict) -> PipelineConfig:
        """Create PipelineConfig from dictionary."""
        source = SourceConfig(**config_dict['source'])
        target = TargetConfig(**config_dict['target'])
        tables = [TableConfig(**table) for table in config_dict['tables']]
        
        return PipelineConfig(
            source=source,
            target=target,
            tables=tables,
            **{k: v for k, v in config_dict.items() 
               if k not in ['source', 'target', 'tables']}
        )
    
    @staticmethod
    def _get_default_table_configs() -> List[TableConfig]:
        """Get default table configurations."""
        return [
            TableConfig(
                source_table="dbo.customers",
                target_table="customers",
                watermark_column="modified_date",
                merge_keys=["customer_id"],
                partition_columns=["created_year", "created_month"],
                data_quality_checks={
                    "not_null": ["customer_id", "customer_name"],
                    "unique": ["customer_id"],
                    "valid_email": ["email"]
                }
            ),
            TableConfig(
                source_table="dbo.orders",
                target_table="orders",
                watermark_column="order_date",
                merge_keys=["order_id"],
                partition_columns=["order_year", "order_month"],
                data_quality_checks={
                    "not_null": ["order_id", "customer_id", "order_date"],
                    "positive": ["order_amount"],
                    "valid_status": ["order_status"]
                }
            ),
            TableConfig(
                source_table="dbo.order_items",
                target_table="order_items",
                watermark_column="modified_date",
                merge_keys=["order_id", "item_id"],
                data_quality_checks={
                    "not_null": ["order_id", "item_id", "product_id"],
                    "positive": ["quantity", "unit_price"]
                }
            ),
            TableConfig(
                source_table="dbo.products",
                target_table="products",
                watermark_column="last_updated",
                merge_keys=["product_id"],
                data_quality_checks={
                    "not_null": ["product_id", "product_name"],
                    "positive": ["price"],
                    "valid_category": ["category"]
                }
            ),
            TableConfig(
                source_table="dbo.inventory",
                target_table="inventory",
                watermark_column="last_updated",
                merge_keys=["product_id", "warehouse_id"],
                partition_columns=["warehouse_id"],
                data_quality_checks={
                    "not_null": ["product_id", "warehouse_id"],
                    "non_negative": ["quantity_on_hand", "quantity_reserved"]
                }
            )
        ]
    
    @staticmethod
    def validate_config(config: PipelineConfig) -> bool:
        """Validate the entire pipeline configuration."""
        # Validate source
        if not config.source.server or not config.source.database:
            raise ValueError("Source server and database are required")
        
        # Validate target
        if not config.target.catalog or not config.target.schema:
            raise ValueError("Target catalog and schema are required")
        
        # Validate tables
        if not config.tables:
            raise ValueError("At least one table configuration is required")
        
        for table in config.tables:
            table.validate()
        
        # Validate pipeline settings
        if config.parallel_tables < 1:
            raise ValueError("parallel_tables must be at least 1")
        
        if config.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        
        return True


# Sample configuration file content
SAMPLE_CONFIG = {
    "source": {
        "server": "your-server.database.windows.net",
        "database": "your-database",
        "username": "your-username",
        "password": "your-password",
        "port": 1433,
        "fetch_size": 10000
    },
    "target": {
        "catalog": "main",
        "schema": "bronze",
        "watermark_table": "pipeline_watermarks",
        "checkpoint_location": "/mnt/delta/checkpoints"
    },
    "tables": [
        {
            "source_table": "dbo.customers",
            "target_table": "customers",
            "watermark_column": "modified_date",
            "merge_keys": ["customer_id"],
            "partition_columns": ["created_year", "created_month"],
            "enable_merge": True,
            "data_quality_checks": {
                "not_null": ["customer_id", "customer_name"],
                "unique": ["customer_id"]
            }
        },
        {
            "source_table": "dbo.orders",
            "target_table": "orders",
            "watermark_column": "order_date",
            "merge_keys": ["order_id"],
            "partition_columns": ["order_year", "order_month"],
            "enable_merge": True,
            "data_quality_checks": {
                "not_null": ["order_id", "customer_id"],
                "positive": ["order_amount"]
            }
        }
    ],
    "parallel_tables": 2,
    "max_retries": 3,
    "retry_delay_seconds": 60,
    "enable_notifications": True,
    "notification_email": "data-team@company.com",
    "enable_data_quality": True,
    "tags": {
        "environment": "production",
        "team": "data-engineering",
        "project": "azure-migration"
    }
}


def create_sample_config_file(file_path: str = "pipeline_config.json"):
    """Create a sample configuration file."""
    with open(file_path, 'w') as f:
        json.dump(SAMPLE_CONFIG, f, indent=2)
    print(f"Sample configuration file created: {file_path}")


if __name__ == "__main__":
    # Example usage
    create_sample_config_file("databricks_pipeline/pipeline_config.json")