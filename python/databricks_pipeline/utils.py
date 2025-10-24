"""
Utility functions for Databricks Pipeline
Includes data quality checks, transformations, and helper functions
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    col, when, isnan, isnull, count, sum as spark_sum, 
    avg, min as spark_min, max as spark_max, stddev,
    current_timestamp, date_format, year, month, dayofmonth,
    regexp_extract, trim, upper, lower, length, lit,
    to_timestamp, datediff, months_between
)
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType
from typing import Dict, List, Any, Optional, Tuple
import logging
import re
from datetime import datetime
from functools import wraps
import time

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """Performs data quality checks on DataFrames."""
    
    @staticmethod
    def check_not_null(df: DataFrame, columns: List[str]) -> Tuple[bool, Dict[str, int]]:
        """
        Check for null values in specified columns.
        
        Args:
            df: Input DataFrame
            columns: List of column names to check
            
        Returns:
            Tuple of (pass/fail, dictionary of null counts per column)
        """
        null_counts = {}
        total_nulls = 0
        
        for column in columns:
            if column in df.columns:
                null_count = df.filter(col(column).isNull() | isnan(col(column))).count()
                null_counts[column] = null_count
                total_nulls += null_count
            else:
                logger.warning(f"Column {column} not found in DataFrame")
        
        passed = total_nulls == 0
        return passed, null_counts
    
    @staticmethod
    def check_unique(df: DataFrame, columns: List[str]) -> Tuple[bool, Dict[str, int]]:
        """
        Check for duplicate values in specified columns.
        
        Args:
            df: Input DataFrame
            columns: List of column names to check for uniqueness
            
        Returns:
            Tuple of (pass/fail, dictionary with duplicate counts)
        """
        total_rows = df.count()
        unique_rows = df.select(columns).distinct().count()
        duplicate_count = total_rows - unique_rows
        
        result = {
            "total_rows": total_rows,
            "unique_rows": unique_rows,
            "duplicate_rows": duplicate_count
        }
        
        passed = duplicate_count == 0
        return passed, result
    
    @staticmethod
    def check_positive(df: DataFrame, columns: List[str]) -> Tuple[bool, Dict[str, int]]:
        """
        Check that numeric columns contain only positive values.
        
        Args:
            df: Input DataFrame
            columns: List of numeric column names to check
            
        Returns:
            Tuple of (pass/fail, dictionary of non-positive counts)
        """
        non_positive_counts = {}
        total_non_positive = 0
        
        for column in columns:
            if column in df.columns:
                non_positive = df.filter(col(column) <= 0).count()
                non_positive_counts[column] = non_positive
                total_non_positive += non_positive
        
        passed = total_non_positive == 0
        return passed, non_positive_counts
    
    @staticmethod
    def check_valid_email(df: DataFrame, columns: List[str]) -> Tuple[bool, Dict[str, int]]:
        """
        Check that email columns contain valid email addresses.
        
        Args:
            df: Input DataFrame
            columns: List of email column names to check
            
        Returns:
            Tuple of (pass/fail, dictionary of invalid email counts)
        """
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        invalid_counts = {}
        total_invalid = 0
        
        for column in columns:
            if column in df.columns:
                invalid = df.filter(
                    ~col(column).rlike(email_pattern) & col(column).isNotNull()
                ).count()
                invalid_counts[column] = invalid
                total_invalid += invalid
        
        passed = total_invalid == 0
        return passed, invalid_counts
    
    @staticmethod
    def check_date_range(df: DataFrame, column: str, 
                        min_date: str, max_date: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check that date values fall within a specified range.
        
        Args:
            df: Input DataFrame
            column: Date column name
            min_date: Minimum allowed date (YYYY-MM-DD format)
            max_date: Maximum allowed date (YYYY-MM-DD format)
            
        Returns:
            Tuple of (pass/fail, dictionary with out-of-range details)
        """
        out_of_range = df.filter(
            (col(column) < lit(min_date)) | (col(column) > lit(max_date))
        )
        
        out_of_range_count = out_of_range.count()
        
        result = {
            "out_of_range_count": out_of_range_count,
            "min_date_found": df.agg(spark_min(col(column))).collect()[0][0],
            "max_date_found": df.agg(spark_max(col(column))).collect()[0][0]
        }
        
        passed = out_of_range_count == 0
        return passed, result
    
    @staticmethod
    def run_all_checks(df: DataFrame, checks: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run all specified data quality checks.
        
        Args:
            df: Input DataFrame
            checks: Dictionary of check types and their parameters
            
        Returns:
            Dictionary with check results
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_records": df.count(),
            "checks": {}
        }
        
        all_passed = True
        
        for check_type, params in checks.items():
            if check_type == "not_null":
                passed, details = DataQualityChecker.check_not_null(df, params)
            elif check_type == "unique":
                passed, details = DataQualityChecker.check_unique(df, params)
            elif check_type == "positive":
                passed, details = DataQualityChecker.check_positive(df, params)
            elif check_type == "valid_email":
                passed, details = DataQualityChecker.check_valid_email(df, params)
            elif check_type == "date_range" and isinstance(params, dict):
                passed, details = DataQualityChecker.check_date_range(
                    df, params['column'], params['min_date'], params['max_date']
                )
            else:
                logger.warning(f"Unknown check type: {check_type}")
                continue
            
            results["checks"][check_type] = {
                "passed": passed,
                "details": details
            }
            
            if not passed:
                all_passed = False
        
        results["all_passed"] = all_passed
        return results


class DataTransformer:
    """Applies transformations to DataFrames."""
    
    @staticmethod
    def add_audit_columns(df: DataFrame, source_system: str = "AZURE_SQL") -> DataFrame:
        """
        Add audit columns to track data lineage.
        
        Args:
            df: Input DataFrame
            source_system: Name of the source system
            
        Returns:
            DataFrame with audit columns added
        """
        return df \
            .withColumn("_ingestion_timestamp", current_timestamp()) \
            .withColumn("_source_system", lit(source_system)) \
            .withColumn("_ingestion_date", date_format(current_timestamp(), "yyyy-MM-dd"))
    
    @staticmethod
    def add_partition_columns(df: DataFrame, date_column: str) -> DataFrame:
        """
        Add year, month, and day partition columns based on a date column.
        
        Args:
            df: Input DataFrame
            date_column: Name of the date column to derive partitions from
            
        Returns:
            DataFrame with partition columns added
        """
        return df \
            .withColumn(f"{date_column}_year", year(col(date_column))) \
            .withColumn(f"{date_column}_month", month(col(date_column))) \
            .withColumn(f"{date_column}_day", dayofmonth(col(date_column)))
    
    @staticmethod
    def clean_string_columns(df: DataFrame, columns: List[str]) -> DataFrame:
        """
        Clean string columns by trimming whitespace and standardizing case.
        
        Args:
            df: Input DataFrame
            columns: List of string column names to clean
            
        Returns:
            DataFrame with cleaned string columns
        """
        for column in columns:
            if column in df.columns:
                df = df.withColumn(column, trim(col(column)))
        return df
    
    @staticmethod
    def standardize_phone_numbers(df: DataFrame, columns: List[str]) -> DataFrame:
        """
        Standardize phone number formats.
        
        Args:
            df: Input DataFrame
            columns: List of phone number column names
            
        Returns:
            DataFrame with standardized phone numbers
        """
        for column in columns:
            if column in df.columns:
                # Remove all non-numeric characters
                df = df.withColumn(
                    column,
                    regexp_extract(col(column), r'(\d+)', 1)
                )
        return df
    
    @staticmethod
    def hash_sensitive_columns(df: DataFrame, columns: List[str], 
                              salt: str = "default_salt") -> DataFrame:
        """
        Hash sensitive columns for privacy protection.
        
        Args:
            df: Input DataFrame
            columns: List of column names to hash
            salt: Salt value for hashing
            
        Returns:
            DataFrame with hashed columns
        """
        from pyspark.sql.functions import sha2, concat
        
        for column in columns:
            if column in df.columns:
                df = df.withColumn(
                    f"{column}_hashed",
                    sha2(concat(col(column), lit(salt)), 256)
                )
                df = df.drop(column)
        return df
    
    @staticmethod
    def apply_transformations(df: DataFrame, 
                            transformations: List[Dict[str, Any]]) -> DataFrame:
        """
        Apply a list of transformations to a DataFrame.
        
        Args:
            df: Input DataFrame
            transformations: List of transformation configurations
            
        Returns:
            Transformed DataFrame
        """
        for transform in transformations:
            transform_type = transform.get('type')
            
            if transform_type == 'add_audit_columns':
                df = DataTransformer.add_audit_columns(
                    df, transform.get('source_system', 'AZURE_SQL')
                )
            elif transform_type == 'add_partition_columns':
                df = DataTransformer.add_partition_columns(
                    df, transform['date_column']
                )
            elif transform_type == 'clean_strings':
                df = DataTransformer.clean_string_columns(
                    df, transform['columns']
                )
            elif transform_type == 'standardize_phones':
                df = DataTransformer.standardize_phone_numbers(
                    df, transform['columns']
                )
            elif transform_type == 'hash_sensitive':
                df = DataTransformer.hash_sensitive_columns(
                    df, transform['columns'], transform.get('salt', 'default_salt')
                )
            else:
                logger.warning(f"Unknown transformation type: {transform_type}")
        
        return df


class PerformanceOptimizer:
    """Utilities for optimizing pipeline performance."""
    
    @staticmethod
    def optimize_dataframe(df: DataFrame, 
                          partition_size_mb: int = 128) -> DataFrame:
        """
        Optimize DataFrame partitioning for better performance.
        
        Args:
            df: Input DataFrame
            partition_size_mb: Target partition size in MB
            
        Returns:
            Optimized DataFrame
        """
        # Estimate DataFrame size
        row_count = df.count()
        column_count = len(df.columns)
        
        # Rough estimate: assume 100 bytes per cell
        estimated_size_mb = (row_count * column_count * 100) / (1024 * 1024)
        
        # Calculate optimal partition count
        optimal_partitions = max(1, int(estimated_size_mb / partition_size_mb))
        
        # Repartition if needed
        current_partitions = df.rdd.getNumPartitions()
        if current_partitions != optimal_partitions:
            logger.info(f"Repartitioning from {current_partitions} to {optimal_partitions}")
            df = df.repartition(optimal_partitions)
        
        return df
    
    @staticmethod
    def cache_if_reused(df: DataFrame, reuse_count: int = 2) -> DataFrame:
        """
        Cache DataFrame if it will be reused multiple times.
        
        Args:
            df: Input DataFrame
            reuse_count: Number of times DataFrame will be reused
            
        Returns:
            Potentially cached DataFrame
        """
        if reuse_count >= 2:
            logger.info("Caching DataFrame for reuse")
            df.cache()
        return df


class RetryHandler:
    """Handles retry logic for pipeline operations."""
    
    @staticmethod
    def retry_on_failure(max_retries: int = 3, 
                        delay_seconds: int = 60,
                        backoff_factor: float = 2.0):
        """
        Decorator for retrying failed operations.
        
        Args:
            max_retries: Maximum number of retry attempts
            delay_seconds: Initial delay between retries
            backoff_factor: Factor to multiply delay by after each retry
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                delay = delay_seconds
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_retries:
                            logger.warning(
                                f"Attempt {attempt + 1} failed: {str(e)}. "
                                f"Retrying in {delay} seconds..."
                            )
                            time.sleep(delay)
                            delay *= backoff_factor
                        else:
                            logger.error(f"All {max_retries + 1} attempts failed")
                
                raise last_exception
            return wrapper
        return decorator


class SchemaManager:
    """Manages schema operations and evolution."""
    
    @staticmethod
    def compare_schemas(source_schema: StructType, 
                       target_schema: StructType) -> Dict[str, List[str]]:
        """
        Compare source and target schemas.
        
        Args:
            source_schema: Source DataFrame schema
            target_schema: Target DataFrame schema
            
        Returns:
            Dictionary with schema differences
        """
        source_fields = {field.name: field.dataType for field in source_schema.fields}
        target_fields = {field.name: field.dataType for field in target_schema.fields}
        
        new_columns = [col for col in source_fields if col not in target_fields]
        removed_columns = [col for col in target_fields if col not in source_fields]
        
        type_changes = []
        for col in source_fields:
            if col in target_fields and source_fields[col] != target_fields[col]:
                type_changes.append({
                    "column": col,
                    "source_type": str(source_fields[col]),
                    "target_type": str(target_fields[col])
                })
        
        return {
            "new_columns": new_columns,
            "removed_columns": removed_columns,
            "type_changes": type_changes
        }
    
    @staticmethod
    def merge_schemas(source_schema: StructType, 
                     target_schema: StructType) -> StructType:
        """
        Merge source and target schemas for schema evolution.
        
        Args:
            source_schema: Source DataFrame schema
            target_schema: Target DataFrame schema
            
        Returns:
            Merged schema
        """
        merged_fields = []
        source_fields_dict = {field.name: field for field in source_schema.fields}
        target_fields_dict = {field.name: field for field in target_schema.fields}
        
        # Add all target fields
        for field_name, field in target_fields_dict.items():
            merged_fields.append(field)
        
        # Add new source fields
        for field_name, field in source_fields_dict.items():
            if field_name not in target_fields_dict:
                merged_fields.append(field)
        
        return StructType(merged_fields)


class NotificationManager:
    """Handles notifications and alerts."""
    
    @staticmethod
    def send_email_notification(subject: str, body: str, 
                               recipients: List[str],
                               smtp_config: Dict[str, Any]):
        """
        Send email notification.
        
        Args:
            subject: Email subject
            body: Email body
            recipients: List of recipient email addresses
            smtp_config: SMTP configuration
        """
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_config['sender']
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html'))
            
            with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
                if smtp_config.get('use_tls', True):
                    server.starttls()
                server.login(smtp_config['username'], smtp_config['password'])
                server.send_message(msg)
            
            logger.info(f"Email notification sent to {recipients}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
    
    @staticmethod
    def format_pipeline_report(results: Dict[str, Any]) -> str:
        """
        Format pipeline results as HTML report.
        
        Args:
            results: Pipeline execution results
            
        Returns:
            HTML formatted report
        """
        html = """
        <html>
        <body>
        <h2>Pipeline Execution Report</h2>
        <p><strong>Execution Time:</strong> {timestamp}</p>
        <p><strong>Status:</strong> {status}</p>
        
        <h3>Table Processing Summary</h3>
        <table border="1">
            <tr>
                <th>Table</th>
                <th>Records Processed</th>
                <th>Status</th>
                <th>Duration (seconds)</th>
            </tr>
            {table_rows}
        </table>
        
        <h3>Data Quality Results</h3>
        {quality_results}
        
        <p>Best regards,<br>Data Pipeline Team</p>
        </body>
        </html>
        """
        
        # Format table rows
        table_rows = ""
        for table in results.get('tables', []):
            table_rows += f"""
            <tr>
                <td>{table['name']}</td>
                <td>{table['records']}</td>
                <td>{table['status']}</td>
                <td>{table['duration']}</td>
            </tr>
            """
        
        # Format quality results
        quality_results = "<ul>"
        for check, result in results.get('quality_checks', {}).items():
            status = "✓" if result['passed'] else "✗"
            quality_results += f"<li>{status} {check}: {result.get('details', '')}</li>"
        quality_results += "</ul>"
        
        return html.format(
            timestamp=results.get('timestamp', ''),
            status=results.get('status', ''),
            table_rows=table_rows,
            quality_results=quality_results
        )


# Export all utility classes
__all__ = [
    'DataQualityChecker',
    'DataTransformer',
    'PerformanceOptimizer',
    'RetryHandler',
    'SchemaManager',
    'NotificationManager'
]