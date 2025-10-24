"""
Databricks Pipeline for Incremental Data Migration from Azure SQL Server
This pipeline supports incremental loads and is designed to run hourly.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, max as spark_max, current_timestamp, lit
from pyspark.sql.types import StructType, StructField, StringType, TimestampType
from datetime import datetime, timedelta
import logging
import json
from typing import Dict, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IncrementalDataPipeline:
    """
    Main class for handling incremental data migration from Azure SQL Server to Databricks.
    """
    
    def __init__(self, spark: SparkSession, config: Dict):
        """
        Initialize the pipeline with Spark session and configuration.
        
        Args:
            spark: Active SparkSession
            config: Configuration dictionary containing connection details
        """
        self.spark = spark
        self.config = config
        self.jdbc_url = self._build_jdbc_url()
        self.watermark_table = config.get('watermark_table', 'pipeline_watermarks')
        self.target_catalog = config.get('target_catalog', 'main')
        self.target_schema = config.get('target_schema', 'bronze')
        
    def _build_jdbc_url(self) -> str:
        """Build JDBC URL for Azure SQL Server connection."""
        server = self.config['source_server']
        database = self.config['source_database']
        port = self.config.get('source_port', 1433)
        
        jdbc_url = (
            f"jdbc:sqlserver://{server}:{port};"
            f"database={database};"
            f"encrypt=true;"
            f"trustServerCertificate=false;"
            f"hostNameInCertificate=*.database.windows.net;"
            f"loginTimeout=30;"
        )
        return jdbc_url
    
    def _get_connection_properties(self) -> Dict:
        """Get JDBC connection properties."""
        return {
            "user": self.config['source_username'],
            "password": self.config['source_password'],
            "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver"
        }
    
    def _initialize_watermark_table(self):
        """Create watermark table if it doesn't exist."""
        watermark_schema = StructType([
            StructField("table_name", StringType(), False),
            StructField("watermark_column", StringType(), False),
            StructField("last_watermark_value", StringType(), True),
            StructField("last_sync_timestamp", TimestampType(), False),
            StructField("records_processed", StringType(), True),
            StructField("status", StringType(), True)
        ])
        
        # Create empty DataFrame with schema
        empty_df = self.spark.createDataFrame([], watermark_schema)
        
        # Write as Delta table if it doesn't exist
        table_path = f"{self.target_catalog}.{self.target_schema}.{self.watermark_table}"
        
        if not self.spark.catalog.tableExists(table_path):
            empty_df.write \
                .mode("overwrite") \
                .option("overwriteSchema", "true") \
                .saveAsTable(table_path)
            logger.info(f"Created watermark table: {table_path}")
    
    def _get_last_watermark(self, table_name: str, watermark_column: str) -> Optional[str]:
        """
        Retrieve the last watermark value for a given table.
        
        Args:
            table_name: Name of the source table
            watermark_column: Column used for watermarking
            
        Returns:
            Last watermark value or None if not found
        """
        table_path = f"{self.target_catalog}.{self.target_schema}.{self.watermark_table}"
        
        try:
            watermark_df = self.spark.table(table_path) \
                .filter(
                    (col("table_name") == table_name) & 
                    (col("watermark_column") == watermark_column) &
                    (col("status") == "SUCCESS")
                ) \
                .orderBy(col("last_sync_timestamp").desc()) \
                .limit(1) \
                .select("last_watermark_value")
            
            if watermark_df.count() > 0:
                return watermark_df.collect()[0]["last_watermark_value"]
        except Exception as e:
            logger.warning(f"Could not retrieve watermark for {table_name}: {str(e)}")
        
        return None
    
    def _update_watermark(self, table_name: str, watermark_column: str, 
                         watermark_value: str, records_processed: int, status: str = "SUCCESS"):
        """
        Update the watermark table with the latest sync information.
        
        Args:
            table_name: Name of the source table
            watermark_column: Column used for watermarking
            watermark_value: New watermark value
            records_processed: Number of records processed
            status: Status of the sync operation
        """
        watermark_data = [(
            table_name,
            watermark_column,
            str(watermark_value),
            datetime.now(),
            str(records_processed),
            status
        )]
        
        columns = ["table_name", "watermark_column", "last_watermark_value", 
                  "last_sync_timestamp", "records_processed", "status"]
        
        watermark_df = self.spark.createDataFrame(watermark_data, columns)
        
        table_path = f"{self.target_catalog}.{self.target_schema}.{self.watermark_table}"
        watermark_df.write.mode("append").saveAsTable(table_path)
        
        logger.info(f"Updated watermark for {table_name}: {watermark_value}, Records: {records_processed}")
    
    def _build_incremental_query(self, table_name: str, watermark_column: str, 
                                last_watermark: Optional[str], 
                                custom_columns: Optional[List[str]] = None) -> str:
        """
        Build SQL query for incremental data extraction.
        
        Args:
            table_name: Source table name
            watermark_column: Column to use for incremental logic
            last_watermark: Last watermark value
            custom_columns: Specific columns to select (if None, selects all)
            
        Returns:
            SQL query string
        """
        columns = "*" if not custom_columns else ", ".join(custom_columns)
        
        if last_watermark:
            # For incremental load
            query = f"""
            (SELECT {columns} 
             FROM {table_name} 
             WHERE {watermark_column} > '{last_watermark}'
             ) AS incremental_data
            """
        else:
            # For initial full load
            query = f"""
            (SELECT {columns} 
             FROM {table_name}
             ) AS full_data
            """
        
        return query
    
    def migrate_table(self, source_table: str, target_table: str, 
                     watermark_column: str, 
                     custom_columns: Optional[List[str]] = None,
                     partition_columns: Optional[List[str]] = None,
                     merge_keys: Optional[List[str]] = None):
        """
        Migrate a single table with incremental load support.
        
        Args:
            source_table: Source table name in Azure SQL
            target_table: Target table name in Databricks
            watermark_column: Column to use for incremental tracking
            custom_columns: Specific columns to migrate
            partition_columns: Columns to use for partitioning in Delta
            merge_keys: Keys to use for merge operation (for upsert logic)
        """
        try:
            logger.info(f"Starting migration for table: {source_table}")
            
            # Get last watermark
            last_watermark = self._get_last_watermark(source_table, watermark_column)
            
            if last_watermark:
                logger.info(f"Incremental load from watermark: {last_watermark}")
            else:
                logger.info("Initial full load - no previous watermark found")
            
            # Build query
            query = self._build_incremental_query(
                source_table, watermark_column, last_watermark, custom_columns
            )
            
            # Read data from Azure SQL
            source_df = self.spark.read \
                .format("jdbc") \
                .option("url", self.jdbc_url) \
                .option("dbtable", query) \
                .option("user", self.config['source_username']) \
                .option("password", self.config['source_password']) \
                .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver") \
                .option("fetchsize", self.config.get('fetch_size', 10000)) \
                .load()
            
            # Add metadata columns
            source_df = source_df \
                .withColumn("_ingestion_timestamp", current_timestamp()) \
                .withColumn("_source_system", lit("AZURE_SQL"))
            
            # Cache for performance
            source_df.cache()
            record_count = source_df.count()
            
            if record_count == 0:
                logger.info(f"No new records to process for {source_table}")
                self._update_watermark(source_table, watermark_column, 
                                      last_watermark or "NO_DATA", 0, "NO_NEW_DATA")
                return
            
            logger.info(f"Processing {record_count} records")
            
            # Get new watermark value
            new_watermark = source_df.agg(spark_max(col(watermark_column))).collect()[0][0]
            
            # Define target table path
            target_path = f"{self.target_catalog}.{self.target_schema}.{target_table}"
            
            # Check if target table exists
            table_exists = self.spark.catalog.tableExists(target_path)
            
            if not table_exists or not merge_keys:
                # Simple append or overwrite
                write_mode = "overwrite" if not table_exists else "append"
                
                writer = source_df.write.mode(write_mode)
                
                if partition_columns:
                    writer = writer.partitionBy(*partition_columns)
                
                writer.format("delta").saveAsTable(target_path)
                
                logger.info(f"Data written to {target_path} using {write_mode} mode")
            else:
                # Merge operation for upsert
                from delta.tables import DeltaTable
                
                target_delta = DeltaTable.forName(self.spark, target_path)
                
                # Build merge condition
                merge_condition = " AND ".join([
                    f"target.{key} = source.{key}" for key in merge_keys
                ])
                
                # Perform merge
                target_delta.alias("target") \
                    .merge(source_df.alias("source"), merge_condition) \
                    .whenMatchedUpdateAll() \
                    .whenNotMatchedInsertAll() \
                    .execute()
                
                logger.info(f"Data merged into {target_path}")
            
            # Update watermark
            self._update_watermark(source_table, watermark_column, 
                                  str(new_watermark), record_count)
            
            # Unpersist cached data
            source_df.unpersist()
            
            logger.info(f"Successfully migrated {source_table} to {target_table}")
            
        except Exception as e:
            logger.error(f"Error migrating table {source_table}: {str(e)}")
            self._update_watermark(source_table, watermark_column, 
                                  last_watermark or "ERROR", 0, f"ERROR: {str(e)}")
            raise
    
    def run_pipeline(self, table_configs: List[Dict]):
        """
        Run the complete pipeline for multiple tables.
        
        Args:
            table_configs: List of table configuration dictionaries
        """
        logger.info(f"Starting pipeline run at {datetime.now()}")
        
        # Initialize watermark table
        self._initialize_watermark_table()
        
        success_count = 0
        error_count = 0
        
        for config in table_configs:
            try:
                self.migrate_table(
                    source_table=config['source_table'],
                    target_table=config.get('target_table', config['source_table']),
                    watermark_column=config['watermark_column'],
                    custom_columns=config.get('custom_columns'),
                    partition_columns=config.get('partition_columns'),
                    merge_keys=config.get('merge_keys')
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to migrate {config['source_table']}: {str(e)}")
                error_count += 1
        
        logger.info(f"Pipeline completed. Success: {success_count}, Errors: {error_count}")
        
        if error_count > 0:
            raise Exception(f"Pipeline completed with {error_count} errors")


def main():
    """Main entry point for the pipeline."""
    
    # Initialize Spark session
    spark = SparkSession.builder \
        .appName("Azure SQL to Databricks Incremental Pipeline") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()
    
    # Load configuration (this would typically come from a config file or Databricks secrets)
    config = {
        "source_server": "your-server.database.windows.net",
        "source_database": "your-database",
        "source_username": "your-username",
        "source_password": "your-password",  # Use Databricks secrets in production
        "target_catalog": "main",
        "target_schema": "bronze",
        "watermark_table": "pipeline_watermarks",
        "fetch_size": 10000
    }
    
    # Define tables to migrate
    table_configs = [
        {
            "source_table": "dbo.customers",
            "target_table": "customers",
            "watermark_column": "modified_date",
            "merge_keys": ["customer_id"],
            "partition_columns": ["created_year", "created_month"]
        },
        {
            "source_table": "dbo.orders",
            "target_table": "orders",
            "watermark_column": "order_date",
            "merge_keys": ["order_id"],
            "partition_columns": ["order_year", "order_month"]
        },
        {
            "source_table": "dbo.products",
            "target_table": "products",
            "watermark_column": "last_updated",
            "merge_keys": ["product_id"]
        }
    ]
    
    # Create and run pipeline
    pipeline = IncrementalDataPipeline(spark, config)
    pipeline.run_pipeline(table_configs)
    
    spark.stop()


if __name__ == "__main__":
    main()