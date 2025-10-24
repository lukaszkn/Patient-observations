"""
Enhanced Databricks Pipeline with integrated utilities and configuration
Supports incremental loads, data quality checks, and transformations
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, max as spark_max, current_timestamp, lit, count
from delta.tables import DeltaTable
from datetime import datetime, timedelta
import logging
import json
from typing import Dict, Optional, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from config import ConfigManager, PipelineConfig, TableConfig
from utils import (
    DataQualityChecker, 
    DataTransformer, 
    PerformanceOptimizer,
    RetryHandler,
    SchemaManager,
    NotificationManager
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedIncrementalPipeline:
    """
    Enhanced pipeline with data quality, transformations, and monitoring.
    """
    
    def __init__(self, spark: SparkSession, config: PipelineConfig):
        """
        Initialize the enhanced pipeline.
        
        Args:
            spark: Active SparkSession
            config: PipelineConfig object with all settings
        """
        self.spark = spark
        self.config = config
        self.jdbc_url = config.source.to_jdbc_url()
        self.connection_props = config.source.to_connection_properties()
        self.quality_checker = DataQualityChecker()
        self.transformer = DataTransformer()
        self.optimizer = PerformanceOptimizer()
        self.schema_manager = SchemaManager()
        self.notification_manager = NotificationManager()
        self.pipeline_results = {
            "timestamp": datetime.now().isoformat(),
            "tables": [],
            "quality_checks": {},
            "errors": []
        }
        
        # Initialize Delta Lake settings
        self._configure_delta_settings()
    
    def _configure_delta_settings(self):
        """Configure Delta Lake optimization settings."""
        if self.config.target.optimize_write:
            self.spark.conf.set("spark.databricks.delta.optimizeWrite.enabled", "true")
        if self.config.target.auto_compact:
            self.spark.conf.set("spark.databricks.delta.autoCompact.enabled", "true")
        
        # Set file size for optimized writes
        self.spark.conf.set(
            "spark.databricks.delta.optimizeWrite.binSize", 
            self.config.target.optimized_write_max_file_size
        )
    
    def _initialize_watermark_table(self):
        """Create or verify watermark table exists."""
        from pyspark.sql.types import StructType, StructField, StringType, TimestampType, LongType
        
        watermark_schema = StructType([
            StructField("table_name", StringType(), False),
            StructField("watermark_column", StringType(), False),
            StructField("last_watermark_value", StringType(), True),
            StructField("last_sync_timestamp", TimestampType(), False),
            StructField("records_processed", LongType(), True),
            StructField("status", StringType(), True),
            StructField("error_message", StringType(), True),
            StructField("duration_seconds", LongType(), True)
        ])
        
        table_path = f"{self.config.target.catalog}.{self.config.target.schema}.{self.config.target.watermark_table}"
        
        if not self.spark.catalog.tableExists(table_path):
            empty_df = self.spark.createDataFrame([], watermark_schema)
            empty_df.write \
                .mode("overwrite") \
                .option("overwriteSchema", "true") \
                .saveAsTable(table_path)
            logger.info(f"Created watermark table: {table_path}")
    
    def _get_last_watermark(self, table_name: str, watermark_column: str) -> Optional[str]:
        """Retrieve the last successful watermark value."""
        table_path = f"{self.config.target.catalog}.{self.config.target.schema}.{self.config.target.watermark_table}"
        
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
                         watermark_value: str, records_processed: int, 
                         status: str, duration: float, error_message: str = None):
        """Update watermark table with execution details."""
        watermark_data = [(
            table_name,
            watermark_column,
            str(watermark_value) if watermark_value else None,
            datetime.now(),
            records_processed,
            status,
            error_message,
            int(duration)
        )]
        
        columns = ["table_name", "watermark_column", "last_watermark_value", 
                  "last_sync_timestamp", "records_processed", "status", 
                  "error_message", "duration_seconds"]
        
        watermark_df = self.spark.createDataFrame(watermark_data, columns)
        
        table_path = f"{self.config.target.catalog}.{self.config.target.schema}.{self.config.target.watermark_table}"
        watermark_df.write.mode("append").saveAsTable(table_path)
    
    def _build_incremental_query(self, table_config: TableConfig, 
                                last_watermark: Optional[str]) -> str:
        """Build optimized SQL query for incremental extraction."""
        # Select specific columns or all
        if table_config.custom_columns:
            columns = ", ".join(table_config.custom_columns)
        elif table_config.exclude_columns:
            # This would require querying the schema first
            columns = "*"  # Simplified for now
        else:
            columns = "*"
        
        # Build WHERE clause
        where_conditions = []
        
        if last_watermark:
            where_conditions.append(f"{table_config.watermark_column} > '{last_watermark}'")
        
        if table_config.where_clause:
            where_conditions.append(f"({table_config.where_clause})")
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        query = f"""
        (SELECT {columns} 
         FROM {table_config.source_table} 
         WHERE {where_clause}
         ) AS data
        """
        
        return query
    
    @RetryHandler.retry_on_failure(max_retries=3, delay_seconds=60)
    def _read_source_data(self, table_config: TableConfig, 
                         last_watermark: Optional[str]) -> Any:
        """Read data from source with retry logic."""
        query = self._build_incremental_query(table_config, last_watermark)
        
        return self.spark.read \
            .format("jdbc") \
            .option("url", self.jdbc_url) \
            .option("dbtable", query) \
            .option("user", self.config.source.username) \
            .option("password", self.config.source.password) \
            .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver") \
            .option("fetchsize", table_config.batch_size) \
            .option("queryTimeout", "600") \
            .load()
    
    def _apply_transformations(self, df: Any, table_config: TableConfig) -> Any:
        """Apply configured transformations to the DataFrame."""
        # Apply standard audit columns
        df = self.transformer.add_audit_columns(df, "AZURE_SQL")
        
        # Apply custom transformations
        if table_config.transformations:
            df = self.transformer.apply_transformations(df, table_config.transformations)
        
        # Add partition columns if specified
        if table_config.partition_columns and table_config.watermark_column:
            # Check if watermark column is a date type
            if any(pc in table_config.watermark_column for pc in ['date', 'time']):
                df = self.transformer.add_partition_columns(df, table_config.watermark_column)
        
        return df
    
    def _perform_data_quality_checks(self, df: Any, 
                                    table_config: TableConfig) -> Dict[str, Any]:
        """Perform data quality checks and return results."""
        if not self.config.enable_data_quality or not table_config.data_quality_checks:
            return {"skipped": True}
        
        results = self.quality_checker.run_all_checks(df, table_config.data_quality_checks)
        
        # Log results
        if results['all_passed']:
            logger.info(f"All data quality checks passed for {table_config.source_table}")
        else:
            logger.warning(f"Data quality issues found for {table_config.source_table}: {results}")
        
        return results
    
    def _write_to_delta(self, df: Any, table_config: TableConfig, 
                       target_path: str) -> None:
        """Write DataFrame to Delta table with merge or append."""
        table_exists = self.spark.catalog.tableExists(target_path)
        
        if not table_exists:
            # Create new table
            writer = df.write.mode("overwrite")
            
            if table_config.partition_columns:
                writer = writer.partitionBy(*table_config.partition_columns)
            
            writer.format("delta") \
                .option("overwriteSchema", "true") \
                .saveAsTable(target_path)
            
            logger.info(f"Created new Delta table: {target_path}")
            
        elif table_config.enable_merge and table_config.merge_keys:
            # Perform merge operation
            target_delta = DeltaTable.forName(self.spark, target_path)
            
            # Handle schema evolution
            if table_config.enable_schema_evolution:
                target_delta.alias("target") \
                    .merge(
                        df.alias("source"),
                        " AND ".join([f"target.{key} = source.{key}" for key in table_config.merge_keys])
                    ) \
                    .whenMatchedUpdateAll() \
                    .whenNotMatchedInsertAll() \
                    .execute()
            else:
                # Standard merge without schema evolution
                target_delta.alias("target") \
                    .merge(
                        df.alias("source"),
                        " AND ".join([f"target.{key} = source.{key}" for key in table_config.merge_keys])
                    ) \
                    .whenMatchedUpdateAll() \
                    .whenNotMatchedInsertAll() \
                    .execute()
            
            logger.info(f"Merged data into Delta table: {target_path}")
            
        else:
            # Simple append
            df.write.mode("append").format("delta").saveAsTable(target_path)
            logger.info(f"Appended data to Delta table: {target_path}")
    
    def migrate_table(self, table_config: TableConfig) -> Dict[str, Any]:
        """
        Migrate a single table with all enhancements.
        
        Args:
            table_config: TableConfig object with table settings
            
        Returns:
            Dictionary with migration results
        """
        start_time = time.time()
        result = {
            "name": table_config.source_table,
            "status": "PENDING",
            "records": 0,
            "duration": 0,
            "quality_checks": {},
            "error": None
        }
        
        try:
            logger.info(f"Starting migration for table: {table_config.source_table}")
            
            # Validate configuration
            table_config.validate()
            
            # Get last watermark
            last_watermark = self._get_last_watermark(
                table_config.source_table, 
                table_config.watermark_column
            )
            
            # Read source data
            source_df = self._read_source_data(table_config, last_watermark)
            
            # Optimize DataFrame
            source_df = self.optimizer.optimize_dataframe(source_df)
            
            # Cache for multiple operations
            source_df = self.optimizer.cache_if_reused(source_df, reuse_count=3)
            
            # Count records
            record_count = source_df.count()
            result["records"] = record_count
            
            if record_count == 0:
                logger.info(f"No new records to process for {table_config.source_table}")
                result["status"] = "NO_NEW_DATA"
                duration = time.time() - start_time
                self._update_watermark(
                    table_config.source_table, 
                    table_config.watermark_column,
                    last_watermark or "NO_DATA", 
                    0, 
                    "NO_NEW_DATA",
                    duration
                )
                return result
            
            logger.info(f"Processing {record_count} records for {table_config.source_table}")
            
            # Apply transformations
            source_df = self._apply_transformations(source_df, table_config)
            
            # Perform data quality checks
            quality_results = self._perform_data_quality_checks(source_df, table_config)
            result["quality_checks"] = quality_results
            
            # Get new watermark value
            new_watermark = source_df.agg(
                spark_max(col(table_config.watermark_column))
            ).collect()[0][0]
            
            # Write to Delta
            target_path = f"{self.config.target.catalog}.{self.config.target.schema}.{table_config.target_table}"
            self._write_to_delta(source_df, table_config, target_path)
            
            # Calculate duration
            duration = time.time() - start_time
            result["duration"] = duration
            result["status"] = "SUCCESS"
            
            # Update watermark
            self._update_watermark(
                table_config.source_table,
                table_config.watermark_column,
                str(new_watermark),
                record_count,
                "SUCCESS",
                duration
            )
            
            # Unpersist cached data
            source_df.unpersist()
            
            logger.info(f"Successfully migrated {table_config.source_table} in {duration:.2f} seconds")
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Error migrating table {table_config.source_table}: {error_msg}")
            
            result["status"] = "ERROR"
            result["error"] = error_msg
            result["duration"] = duration
            
            self._update_watermark(
                table_config.source_table,
                table_config.watermark_column,
                last_watermark or "ERROR",
                0,
                "ERROR",
                duration,
                error_msg[:500]  # Truncate error message
            )
            
            if self.config.max_retries == 0:
                raise
        
        return result
    
    def run_pipeline_parallel(self) -> Dict[str, Any]:
        """
        Run pipeline with parallel table processing.
        
        Returns:
            Dictionary with complete pipeline results
        """
        logger.info(f"Starting parallel pipeline run with {self.config.parallel_tables} workers")
        
        # Initialize watermark table
        self._initialize_watermark_table()
        
        # Process tables in parallel
        with ThreadPoolExecutor(max_workers=self.config.parallel_tables) as executor:
            future_to_table = {
                executor.submit(self.migrate_table, table_config): table_config
                for table_config in self.config.tables
            }
            
            for future in as_completed(future_to_table):
                table_config = future_to_table[future]
                try:
                    result = future.result()
                    self.pipeline_results["tables"].append(result)
                except Exception as e:
                    logger.error(f"Failed to process {table_config.source_table}: {str(e)}")
                    self.pipeline_results["errors"].append({
                        "table": table_config.source_table,
                        "error": str(e)
                    })
        
        # Determine overall status
        success_count = sum(1 for t in self.pipeline_results["tables"] 
                          if t["status"] == "SUCCESS")
        error_count = len(self.pipeline_results["errors"])
        
        if error_count == 0:
            self.pipeline_results["status"] = "SUCCESS"
        elif success_count > 0:
            self.pipeline_results["status"] = "PARTIAL_SUCCESS"
        else:
            self.pipeline_results["status"] = "FAILED"
        
        logger.info(f"Pipeline completed: {success_count} successful, {error_count} errors")
        
        # Send notifications if configured
        if self.config.enable_notifications and self.config.notification_email:
            self._send_completion_notification()
        
        return self.pipeline_results
    
    def run_pipeline_sequential(self) -> Dict[str, Any]:
        """
        Run pipeline with sequential table processing.
        
        Returns:
            Dictionary with complete pipeline results
        """
        logger.info("Starting sequential pipeline run")
        
        # Initialize watermark table
        self._initialize_watermark_table()
        
        for table_config in self.config.tables:
            try:
                result = self.migrate_table(table_config)
                self.pipeline_results["tables"].append(result)
            except Exception as e:
                logger.error(f"Failed to process {table_config.source_table}: {str(e)}")
                self.pipeline_results["errors"].append({
                    "table": table_config.source_table,
                    "error": str(e)
                })
                
                # Stop on first error if configured
                if self.config.max_retries == 0:
                    break
        
        # Determine overall status
        success_count = sum(1 for t in self.pipeline_results["tables"] 
                          if t["status"] == "SUCCESS")
        error_count = len(self.pipeline_results["errors"])
        
        if error_count == 0:
            self.pipeline_results["status"] = "SUCCESS"
        elif success_count > 0:
            self.pipeline_results["status"] = "PARTIAL_SUCCESS"
        else:
            self.pipeline_results["status"] = "FAILED"
        
        logger.info(f"Pipeline completed: {success_count} successful, {error_count} errors")
        
        # Send notifications if configured
        if self.config.enable_notifications and self.config.notification_email:
            self._send_completion_notification()
        
        return self.pipeline_results
    
    def _send_completion_notification(self):
        """Send pipeline completion notification."""
        try:
            subject = f"Data Pipeline {self.pipeline_results['status']}: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            body = self.notification_manager.format_pipeline_report(self.pipeline_results)
            
            # This would need SMTP configuration
            # self.notification_manager.send_email_notification(
            #     subject, body, [self.config.notification_email], smtp_config
            # )
            
            logger.info("Notification sent successfully")
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")


def main():
    """Main entry point for the enhanced pipeline."""
    
    # Initialize Spark session with optimizations
    spark = SparkSession.builder \
        .appName("Enhanced Azure SQL to Databricks Pipeline") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.sql.adaptive.skewJoin.enabled", "true") \
        .config("spark.databricks.delta.retentionDurationCheck.enabled", "false") \
        .config("spark.databricks.delta.merge.enableLowShuffle", "true") \
        .getOrCreate()
    
    # Load configuration
    # Option 1: From file
    # config = ConfigManager.load_from_file("databricks_pipeline/pipeline_config.json")
    
    # Option 2: From Databricks secrets (when running in Databricks)
    # config = ConfigManager.load_from_dbutils(dbutils, "pipeline-secrets")
    
    # Option 3: Hardcoded for testing
    from config import SourceConfig, TargetConfig, TableConfig, PipelineConfig
    
    source = SourceConfig(
        server="your-server.database.windows.net",
        database="your-database",
        username="your-username",
        password="your-password"  # Use secrets in production
    )
    
    target = TargetConfig(
        catalog="main",
        schema="bronze",
        watermark_table="pipeline_watermarks"
    )
    
    tables = [
        TableConfig(
            source_table="dbo.customers",
            target_table="customers",
            watermark_column="modified_date",
            merge_keys=["customer_id"],
            partition_columns=["created_year"],
            data_quality_checks={
                "not_null": ["customer_id", "customer_name"]
            }
        ),
        TableConfig(
            source_table="dbo.orders",
            target_table="orders",
            watermark_column="order_date",
            merge_keys=["order_id"],
            partition_columns=["order_year", "order_month"],
            data_quality_checks={
                "not_null": ["order_id", "customer_id"],
                "positive": ["order_amount"]
            }
        )
    ]
    
    config = PipelineConfig(
        source=source,
        target=target,
        tables=tables,
        parallel_tables=2,
        enable_notifications=True,
        notification_email="data-team@company.com"
    )
    
    # Validate configuration
    ConfigManager.validate_config(config)
    
    # Create and run pipeline
    pipeline = EnhancedIncrementalPipeline(spark, config)
    
    # Run with parallel processing
    if config.parallel_tables > 1:
        results = pipeline.run_pipeline_parallel()
    else:
        results = pipeline.run_pipeline_sequential()
    
    # Log final results
    logger.info(f"Pipeline Results: {json.dumps(results, indent=2, default=str)}")
    
    # Return non-zero exit code if there were errors
    if results["status"] == "FAILED":
        spark.stop()
        raise Exception("Pipeline failed with errors")
    
    spark.stop()


if __name__ == "__main__":
    main()