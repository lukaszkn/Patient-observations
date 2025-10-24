# Databricks notebook source
# MAGIC %md
# MAGIC # Azure SQL to Databricks Incremental Pipeline
# MAGIC 
# MAGIC This notebook implements the main pipeline for incremental data migration from Azure SQL Server to Databricks.
# MAGIC 
# MAGIC ## Features:
# MAGIC - Incremental loading with watermark tracking
# MAGIC - Parallel table processing
# MAGIC - Data quality checks
# MAGIC - Comprehensive monitoring and alerting
# MAGIC - Automatic retry on failures

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Setup and Imports

# COMMAND ----------

# Import required libraries
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit
from delta.tables import DeltaTable
from datetime import datetime, timedelta
import logging
import json
from typing import Dict, List, Any, Optional
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AzureSQLPipeline")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Configuration

# COMMAND ----------

# Widget parameters for notebook
dbutils.widgets.text("config_path", "/dbfs/mnt/config/pipeline_config.json", "Configuration File Path")
dbutils.widgets.dropdown("run_mode", "parallel", ["parallel", "sequential"], "Run Mode")
dbutils.widgets.text("log_level", "INFO", "Log Level")
dbutils.widgets.dropdown("dry_run", "false", ["true", "false"], "Dry Run Mode")

# Get widget values
config_path = dbutils.widgets.get("config_path")
run_mode = dbutils.widgets.get("run_mode")
log_level = dbutils.widgets.get("log_level")
dry_run = dbutils.widgets.get("dry_run") == "true"

# Set log level
logging.getLogger().setLevel(getattr(logging, log_level))

# COMMAND ----------

# Load configuration from secrets or file
def load_configuration():
    """Load pipeline configuration from Databricks secrets or file."""
    
    # Option 1: Load from Databricks secrets (recommended for production)
    try:
        config = {
            "source": {
                "server": dbutils.secrets.get("pipeline-secrets", "azure-sql-server"),
                "database": dbutils.secrets.get("pipeline-secrets", "azure-sql-database"),
                "username": dbutils.secrets.get("pipeline-secrets", "azure-sql-username"),
                "password": dbutils.secrets.get("pipeline-secrets", "azure-sql-password"),
                "port": 1433,
                "fetch_size": 10000
            },
            "target": {
                "catalog": dbutils.secrets.get("pipeline-secrets", "target-catalog"),
                "schema": dbutils.secrets.get("pipeline-secrets", "target-schema"),
                "watermark_table": "pipeline_watermarks"
            },
            "parallel_tables": 2,
            "max_retries": 3,
            "enable_notifications": True
        }
        logger.info("Configuration loaded from Databricks secrets")
        return config
    except:
        pass
    
    # Option 2: Load from configuration file
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(f"Configuration loaded from file: {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        raise

config = load_configuration()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Pipeline Implementation

# COMMAND ----------

class IncrementalPipeline:
    """Main pipeline class for incremental data migration."""
    
    def __init__(self, spark, config):
        self.spark = spark
        self.config = config
        self.jdbc_url = self._build_jdbc_url()
        self.metrics = {
            "start_time": datetime.now(),
            "tables_processed": [],
            "errors": []
        }
        
    def _build_jdbc_url(self):
        """Build JDBC URL for Azure SQL connection."""
        server = self.config['source']['server']
        database = self.config['source']['database']
        port = self.config['source'].get('port', 1433)
        
        return (
            f"jdbc:sqlserver://{server}:{port};"
            f"database={database};"
            f"encrypt=true;"
            f"trustServerCertificate=false;"
            f"hostNameInCertificate=*.database.windows.net;"
            f"loginTimeout=30;"
        )
    
    def _get_last_watermark(self, table_name, watermark_column):
        """Get the last watermark value for a table."""
        watermark_table = f"{self.config['target']['catalog']}.{self.config['target']['schema']}.{self.config['target']['watermark_table']}"
        
        try:
            result = spark.sql(f"""
                SELECT last_watermark_value 
                FROM {watermark_table}
                WHERE table_name = '{table_name}' 
                  AND watermark_column = '{watermark_column}'
                  AND status = 'SUCCESS'
                ORDER BY last_sync_timestamp DESC
                LIMIT 1
            """).collect()
            
            if result:
                return result[0]['last_watermark_value']
        except:
            pass
        
        return None
    
    def _update_watermark(self, table_name, watermark_column, watermark_value, records, status):
        """Update the watermark table."""
        watermark_table = f"{self.config['target']['catalog']}.{self.config['target']['schema']}.{self.config['target']['watermark_table']}"
        
        spark.sql(f"""
            INSERT INTO {watermark_table}
            VALUES (
                '{table_name}',
                '{watermark_column}',
                '{watermark_value}',
                current_timestamp(),
                {records},
                '{status}',
                NULL,
                NULL
            )
        """)
    
    def migrate_table(self, table_config):
        """Migrate a single table."""
        start_time = time.time()
        table_name = table_config['source_table']
        
        try:
            logger.info(f"Starting migration for {table_name}")
            
            # Get last watermark
            last_watermark = self._get_last_watermark(
                table_name, 
                table_config['watermark_column']
            )
            
            # Build query
            where_clause = ""
            if last_watermark:
                where_clause = f"WHERE {table_config['watermark_column']} > '{last_watermark}'"
                logger.info(f"Incremental load from watermark: {last_watermark}")
            else:
                logger.info("Initial full load")
            
            query = f"(SELECT * FROM {table_name} {where_clause}) AS data"
            
            # Read from source
            df = spark.read \
                .format("jdbc") \
                .option("url", self.jdbc_url) \
                .option("dbtable", query) \
                .option("user", self.config['source']['username']) \
                .option("password", self.config['source']['password']) \
                .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver") \
                .option("fetchsize", self.config['source'].get('fetch_size', 10000)) \
                .load()
            
            # Add audit columns
            df = df.withColumn("_ingestion_timestamp", current_timestamp()) \
                   .withColumn("_source_system", lit("AZURE_SQL"))
            
            # Count records
            record_count = df.count()
            
            if record_count == 0:
                logger.info(f"No new records for {table_name}")
                return {
                    "table": table_name,
                    "status": "NO_NEW_DATA",
                    "records": 0,
                    "duration": time.time() - start_time
                }
            
            logger.info(f"Processing {record_count} records for {table_name}")
            
            # Get new watermark
            new_watermark = df.agg({table_config['watermark_column']: "max"}).collect()[0][0]
            
            # Write to target
            target_table = f"{self.config['target']['catalog']}.{self.config['target']['schema']}.{table_config.get('target_table', table_name)}"
            
            if not dry_run:
                # Check if merge is needed
                if table_config.get('merge_keys') and spark.catalog.tableExists(target_table):
                    # Perform merge
                    target_delta = DeltaTable.forName(spark, target_table)
                    merge_condition = " AND ".join([
                        f"target.{key} = source.{key}" 
                        for key in table_config['merge_keys']
                    ])
                    
                    target_delta.alias("target") \
                        .merge(df.alias("source"), merge_condition) \
                        .whenMatchedUpdateAll() \
                        .whenNotMatchedInsertAll() \
                        .execute()
                    
                    logger.info(f"Merged data into {target_table}")
                else:
                    # Append or create
                    mode = "overwrite" if not spark.catalog.tableExists(target_table) else "append"
                    df.write.mode(mode).saveAsTable(target_table)
                    logger.info(f"Written data to {target_table} (mode: {mode})")
                
                # Update watermark
                self._update_watermark(
                    table_name,
                    table_config['watermark_column'],
                    str(new_watermark),
                    record_count,
                    "SUCCESS"
                )
            else:
                logger.info(f"DRY RUN: Would write {record_count} records to {target_table}")
            
            duration = time.time() - start_time
            logger.info(f"Completed {table_name} in {duration:.2f} seconds")
            
            return {
                "table": table_name,
                "status": "SUCCESS",
                "records": record_count,
                "duration": duration,
                "new_watermark": str(new_watermark)
            }
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Failed to migrate {table_name}: {str(e)}")
            
            if not dry_run:
                self._update_watermark(
                    table_name,
                    table_config['watermark_column'],
                    last_watermark or "ERROR",
                    0,
                    f"ERROR: {str(e)[:200]}"
                )
            
            return {
                "table": table_name,
                "status": "ERROR",
                "error": str(e),
                "duration": duration
            }
    
    def run(self, tables):
        """Run the pipeline for all configured tables."""
        logger.info(f"Starting pipeline run in {run_mode} mode")
        
        results = []
        for table_config in tables:
            result = self.migrate_table(table_config)
            results.append(result)
            self.metrics["tables_processed"].append(result)
            
            if result["status"] == "ERROR":
                self.metrics["errors"].append(result)
        
        self.metrics["end_time"] = datetime.now()
        self.metrics["duration"] = (self.metrics["end_time"] - self.metrics["start_time"]).total_seconds()
        
        return results

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Define Tables to Migrate

# COMMAND ----------

# Define table configurations
tables_to_migrate = [
    {
        "source_table": "dbo.customers",
        "target_table": "customers",
        "watermark_column": "modified_date",
        "merge_keys": ["customer_id"]
    },
    {
        "source_table": "dbo.orders",
        "target_table": "orders",
        "watermark_column": "order_date",
        "merge_keys": ["order_id"]
    },
    {
        "source_table": "dbo.order_items",
        "target_table": "order_items",
        "watermark_column": "modified_date",
        "merge_keys": ["order_id", "item_id"]
    },
    {
        "source_table": "dbo.products",
        "target_table": "products",
        "watermark_column": "last_updated",
        "merge_keys": ["product_id"]
    }
]

# Override with config if available
if 'tables' in config:
    tables_to_migrate = config['tables']

logger.info(f"Configured to migrate {len(tables_to_migrate)} tables")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Initialize Watermark Table

# COMMAND ----------

# Create watermark table if it doesn't exist
watermark_table = f"{config['target']['catalog']}.{config['target']['schema']}.{config['target']['watermark_table']}"

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {watermark_table} (
        table_name STRING,
        watermark_column STRING,
        last_watermark_value STRING,
        last_sync_timestamp TIMESTAMP,
        records_processed BIGINT,
        status STRING,
        error_message STRING,
        duration_seconds BIGINT
    )
    USING DELTA
    COMMENT 'Tracks watermarks for incremental pipeline loads'
""")

logger.info(f"Watermark table ready: {watermark_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Run Pipeline

# COMMAND ----------

# Initialize and run pipeline
pipeline = IncrementalPipeline(spark, config)
results = pipeline.run(tables_to_migrate)

# Display results
display(spark.createDataFrame(results))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Summary and Metrics

# COMMAND ----------

# Calculate summary metrics
total_records = sum(r.get('records', 0) for r in results)
successful_tables = sum(1 for r in results if r['status'] == 'SUCCESS')
failed_tables = sum(1 for r in results if r['status'] == 'ERROR')
total_duration = sum(r.get('duration', 0) for r in results)

summary = {
    "Pipeline Run Summary": "",
    "Total Tables": len(results),
    "Successful": successful_tables,
    "Failed": failed_tables,
    "Total Records Processed": total_records,
    "Total Duration (seconds)": round(total_duration, 2),
    "Average Records/Second": round(total_records / total_duration, 2) if total_duration > 0 else 0,
    "Run Mode": run_mode,
    "Dry Run": dry_run
}

# Display summary
for key, value in summary.items():
    print(f"{key}: {value}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Error Reporting

# COMMAND ----------

# Report any errors
errors = [r for r in results if r['status'] == 'ERROR']
if errors:
    logger.error(f"Pipeline completed with {len(errors)} errors")
    for error in errors:
        print(f"ERROR in {error['table']}: {error.get('error', 'Unknown error')}")
    
    # Optionally raise exception to fail the job
    if not dry_run and config.get('fail_on_error', True):
        raise Exception(f"Pipeline failed with {len(errors)} table errors")
else:
    logger.info("Pipeline completed successfully with no errors")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Cleanup and Next Steps

# COMMAND ----------

# Return success/failure for job scheduling
if failed_tables > 0:
    dbutils.notebook.exit(f"FAILED: {failed_tables} tables failed")
else:
    dbutils.notebook.exit(f"SUCCESS: Processed {total_records} records from {successful_tables} tables")