# Azure SQL to Databricks Incremental Data Pipeline

A production-ready, scalable data pipeline for migrating data from Azure SQL Server to Databricks with incremental load support, designed to run hourly.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Performance Optimization](#performance-optimization)
- [Security](#security)
- [API Reference](#api-reference)

## 🎯 Overview

This pipeline provides a robust solution for incrementally migrating data from Azure SQL Server to Databricks Delta Lake. It supports hourly scheduled runs, data quality checks, transformations, and comprehensive monitoring.

### Key Components

1. **Incremental Pipeline** - Core migration logic with watermark-based incremental loading
2. **Enhanced Pipeline** - Advanced features including parallel processing and data quality
3. **Configuration Management** - Flexible configuration system for different environments
4. **Utilities** - Data quality checks, transformations, and performance optimization
5. **Job Scheduling** - Databricks job configuration for hourly execution
6. **Monitoring** - Comprehensive metrics, logging, and alerting

## ✨ Features

- **Incremental Loading**: Watermark-based incremental data synchronization
- **Parallel Processing**: Support for parallel table migration
- **Data Quality Checks**: Built-in validation including null checks, uniqueness, and custom rules
- **Schema Evolution**: Automatic handling of schema changes
- **Delta Lake Integration**: Full support for Delta Lake features (merge, optimize, etc.)
- **Retry Logic**: Configurable retry mechanism for transient failures
- **Monitoring & Alerting**: Comprehensive metrics and email notifications
- **Performance Optimization**: Automatic DataFrame optimization and caching
- **Audit Trail**: Complete audit logging with watermark tracking

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Azure SQL      │────▶│  Databricks      │────▶│  Delta Lake     │
│  Server         │     │  Pipeline        │     │  Tables         │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │  Watermark       │
                    │  Table           │
                    └──────────────────┘
```

### Data Flow

1. **Source Extraction**: Read data from Azure SQL Server using JDBC
2. **Incremental Filter**: Apply watermark-based filtering for changed records
3. **Transformation**: Apply configured transformations and add audit columns
4. **Data Quality**: Perform validation checks
5. **Target Loading**: Write to Delta Lake using merge or append
6. **Watermark Update**: Update watermark for next run

## 📦 Prerequisites

- Databricks Runtime 13.3 LTS or higher
- Azure SQL Server with JDBC access
- Python 3.9+
- Required Python packages:
  - pyspark
  - delta-spark
  - databricks-sdk (for job management)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd databricks_pipeline
```

### 2. Upload to Databricks Workspace

```bash
# Using Databricks CLI
databricks workspace import_dir ./databricks_pipeline /Workspace/pipelines --overwrite
```

### 3. Install Dependencies

Create a cluster init script:

```bash
#!/bin/bash
pip install databricks-sdk
```

### 4. Configure Secrets

```python
# Create secret scope
databricks secrets create-scope --scope pipeline-secrets

# Add secrets
databricks secrets put --scope pipeline-secrets --key azure-sql-server
databricks secrets put --scope pipeline-secrets --key azure-sql-database
databricks secrets put --scope pipeline-secrets --key azure-sql-username
databricks secrets put --scope pipeline-secrets --key azure-sql-password
```

## ⚙️ Configuration

### Pipeline Configuration

Create a `pipeline_config.json` file:

```json
{
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
      "partition_columns": ["created_year"],
      "data_quality_checks": {
        "not_null": ["customer_id", "customer_name"],
        "unique": ["customer_id"]
      }
    }
  ],
  "parallel_tables": 2,
  "max_retries": 3,
  "enable_notifications": true,
  "notification_email": "data-team@company.com"
}
```

### Table Configuration Options

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `source_table` | Source table name in Azure SQL | Yes | - |
| `target_table` | Target table name in Databricks | Yes | - |
| `watermark_column` | Column for incremental tracking | Yes | - |
| `merge_keys` | Keys for merge operation | No | [] |
| `partition_columns` | Columns for Delta partitioning | No | [] |
| `custom_columns` | Specific columns to migrate | No | All |
| `where_clause` | Additional filter condition | No | - |
| `enable_merge` | Use merge instead of append | No | true |
| `data_quality_checks` | Quality validation rules | No | {} |

## 📖 Usage

### Running the Pipeline Manually

```python
# Databricks notebook
from enhanced_pipeline import EnhancedIncrementalPipeline
from config import ConfigManager

# Load configuration
config = ConfigManager.load_from_file("/dbfs/mnt/config/pipeline_config.json")

# Create pipeline
pipeline = EnhancedIncrementalPipeline(spark, config)

# Run pipeline
results = pipeline.run_pipeline_parallel()
print(results)
```

### Scheduling Hourly Runs

```python
# Create Databricks job
from job_config import create_hourly_pipeline_job

job_config = create_hourly_pipeline_job()

# Submit via API or UI
```

### Using Different Modes

#### Sequential Processing
```python
results = pipeline.run_pipeline_sequential()
```

#### Parallel Processing
```python
results = pipeline.run_pipeline_parallel()
```

## 📊 Monitoring

### Metrics Collection

The pipeline automatically collects:
- Execution duration
- Records processed per table
- Success/failure rates
- Data quality check results
- Error messages and stack traces

### Viewing Metrics

```sql
-- Recent pipeline runs
SELECT * FROM pipeline_metrics 
WHERE start_time >= current_timestamp() - INTERVAL 7 DAYS
ORDER BY start_time DESC;

-- Performance summary
SELECT 
    DATE(start_time) as run_date,
    COUNT(*) as total_runs,
    AVG(duration_seconds) as avg_duration,
    SUM(total_records) as total_records,
    AVG(average_records_per_second) as avg_throughput
FROM pipeline_metrics
GROUP BY DATE(start_time)
ORDER BY run_date DESC;
```

### Setting Up Alerts

```python
from monitoring import AlertManager

# Configure thresholds
thresholds = {
    "max_duration_seconds": 3600,
    "max_error_rate_percent": 10,
    "max_quality_failure_rate_percent": 5
}

alert_manager = AlertManager(thresholds)
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Connection Errors

**Error**: `java.sql.SQLException: The TCP/IP connection to the host failed`

**Solution**:
- Verify Azure SQL firewall rules
- Check network connectivity from Databricks
- Ensure correct server name and port

#### 2. Memory Issues

**Error**: `java.lang.OutOfMemoryError`

**Solution**:
- Increase cluster size
- Reduce fetch_size in configuration
- Enable adaptive query execution

#### 3. Schema Mismatch

**Error**: `AnalysisException: cannot resolve column`

**Solution**:
- Enable schema evolution in table config
- Verify column names match between source and target
- Check for case sensitivity issues

#### 4. Slow Performance

**Symptoms**: Pipeline takes longer than expected

**Solutions**:
- Increase parallel_tables setting
- Optimize partition strategy
- Add indexes on watermark columns in source
- Use cluster with more workers

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## ⚡ Performance Optimization

### Best Practices

1. **Partitioning Strategy**
   - Partition by date columns for time-series data
   - Avoid over-partitioning (aim for 1GB+ per partition)

2. **Cluster Configuration**
   - Use autoscaling for variable workloads
   - Enable adaptive query execution
   - Configure appropriate driver and executor memory

3. **Source Optimization**
   - Create indexes on watermark columns
   - Use column pruning (custom_columns)
   - Apply filters at source (where_clause)

4. **Delta Optimization**
   - Enable auto-optimize and auto-compact
   - Run OPTIMIZE periodically for small files
   - Use Z-ORDER for frequently queried columns

### Performance Tuning Parameters

```python
# Spark configurations
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.databricks.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.databricks.delta.autoCompact.enabled", "true")
```

## 🔒 Security

### Best Practices

1. **Credential Management**
   - Use Databricks secrets for sensitive data
   - Never hardcode passwords
   - Rotate credentials regularly

2. **Network Security**
   - Use private endpoints when possible
   - Implement IP whitelisting
   - Enable SSL/TLS encryption

3. **Access Control**
   - Use Unity Catalog for table permissions
   - Implement row-level security where needed
   - Audit data access

### Example Secret Configuration

```python
# Using Databricks secrets
dbutils.secrets.get(scope="pipeline-secrets", key="azure-sql-password")
```

## 📚 API Reference

### Main Classes

#### EnhancedIncrementalPipeline

```python
class EnhancedIncrementalPipeline:
    def __init__(self, spark: SparkSession, config: PipelineConfig)
    def migrate_table(self, table_config: TableConfig) -> Dict
    def run_pipeline_parallel() -> Dict
    def run_pipeline_sequential() -> Dict
```

#### TableConfig

```python
@dataclass
class TableConfig:
    source_table: str
    target_table: str
    watermark_column: str
    merge_keys: List[str]
    partition_columns: List[str]
    data_quality_checks: Dict[str, Any]
```

#### PipelineMonitor

```python
class PipelineMonitor:
    def start_monitoring(pipeline_id: str) -> PipelineMetrics
    def update_table_metrics(table_name: str, records: int, status: str, duration: float)
    def stop_monitoring(status: str) -> PipelineMetrics
    def get_performance_summary(days: int) -> Dict
```

## 🤝 Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For issues and questions:
- Create an issue in the repository
- Contact the data engineering team
- Check the [FAQ](FAQ.md) document

## 🔄 Version History

- **v1.0.0** (2024-10-24): Initial release with core functionality
- **v1.1.0** (Planned): Add support for CDC (Change Data Capture)
- **v1.2.0** (Planned): Add support for streaming ingestion

---

**Last Updated**: October 24, 2024
**Maintained By**: Data Engineering Team