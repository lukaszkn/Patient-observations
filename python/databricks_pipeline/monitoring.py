"""
Monitoring and Logging utilities for Databricks Pipeline
Provides comprehensive monitoring, alerting, and performance tracking
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import time
from functools import wraps
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as spark_sum, avg, max as spark_max, min as spark_min, count, when


@dataclass
class PipelineMetrics:
    """Container for pipeline execution metrics."""
    pipeline_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    tables_processed: int = 0
    total_records: int = 0
    success_count: int = 0
    error_count: int = 0
    data_quality_passed: int = 0
    data_quality_failed: int = 0
    average_records_per_second: Optional[float] = None
    peak_memory_usage_mb: Optional[float] = None
    total_data_size_mb: Optional[float] = None
    status: str = "RUNNING"
    error_messages: List[str] = None
    
    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = []
    
    def calculate_metrics(self):
        """Calculate derived metrics."""
        if self.end_time and self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
            if self.duration_seconds > 0:
                self.average_records_per_second = self.total_records / self.duration_seconds
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary."""
        data = asdict(self)
        # Convert datetime objects to strings
        if self.start_time:
            data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        return data


class PipelineMonitor:
    """Monitors pipeline execution and collects metrics."""
    
    def __init__(self, spark: SparkSession, pipeline_name: str, 
                 metrics_table: str = "pipeline_metrics"):
        """
        Initialize pipeline monitor.
        
        Args:
            spark: Active SparkSession
            pipeline_name: Name of the pipeline
            metrics_table: Table to store metrics
        """
        self.spark = spark
        self.pipeline_name = pipeline_name
        self.metrics_table = metrics_table
        self.current_metrics = None
        self.logger = logging.getLogger(f"{__name__}.{pipeline_name}")
        
    def start_monitoring(self, pipeline_id: str = None) -> PipelineMetrics:
        """
        Start monitoring a pipeline execution.
        
        Args:
            pipeline_id: Unique identifier for this pipeline run
            
        Returns:
            PipelineMetrics object
        """
        if not pipeline_id:
            pipeline_id = f"{self.pipeline_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.current_metrics = PipelineMetrics(
            pipeline_id=pipeline_id,
            start_time=datetime.now()
        )
        
        self.logger.info(f"Started monitoring pipeline: {pipeline_id}")
        return self.current_metrics
    
    def update_table_metrics(self, table_name: str, records: int, 
                            status: str, duration: float):
        """
        Update metrics for a processed table.
        
        Args:
            table_name: Name of the processed table
            records: Number of records processed
            status: Processing status
            duration: Processing duration in seconds
        """
        if not self.current_metrics:
            return
        
        self.current_metrics.tables_processed += 1
        self.current_metrics.total_records += records
        
        if status == "SUCCESS":
            self.current_metrics.success_count += 1
        else:
            self.current_metrics.error_count += 1
        
        self.logger.info(f"Table {table_name}: {records} records, {status}, {duration:.2f}s")
    
    def update_data_quality_metrics(self, passed: bool):
        """
        Update data quality check metrics.
        
        Args:
            passed: Whether data quality checks passed
        """
        if not self.current_metrics:
            return
        
        if passed:
            self.current_metrics.data_quality_passed += 1
        else:
            self.current_metrics.data_quality_failed += 1
    
    def add_error(self, error_message: str):
        """
        Add an error message to metrics.
        
        Args:
            error_message: Error message to record
        """
        if self.current_metrics:
            self.current_metrics.error_messages.append(error_message)
            self.logger.error(error_message)
    
    def stop_monitoring(self, status: str = "SUCCESS") -> PipelineMetrics:
        """
        Stop monitoring and finalize metrics.
        
        Args:
            status: Final pipeline status
            
        Returns:
            Final PipelineMetrics object
        """
        if not self.current_metrics:
            return None
        
        self.current_metrics.end_time = datetime.now()
        self.current_metrics.status = status
        self.current_metrics.calculate_metrics()
        
        # Save metrics to table
        self._save_metrics()
        
        self.logger.info(f"Pipeline {self.current_metrics.pipeline_id} completed: {status}")
        return self.current_metrics
    
    def _save_metrics(self):
        """Save metrics to Delta table."""
        if not self.current_metrics:
            return
        
        try:
            metrics_dict = self.current_metrics.to_dict()
            metrics_df = self.spark.createDataFrame([metrics_dict])
            
            # Write to Delta table
            metrics_df.write \
                .mode("append") \
                .option("mergeSchema", "true") \
                .saveAsTable(self.metrics_table)
            
            self.logger.info(f"Metrics saved to {self.metrics_table}")
        except Exception as e:
            self.logger.error(f"Failed to save metrics: {str(e)}")
    
    def get_historical_metrics(self, days: int = 7) -> Any:
        """
        Get historical metrics for the pipeline.
        
        Args:
            days: Number of days to look back
            
        Returns:
            DataFrame with historical metrics
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        return self.spark.table(self.metrics_table) \
            .filter(col("start_time") >= cutoff_date) \
            .orderBy(col("start_time").desc())
    
    def get_performance_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get performance summary statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with summary statistics
        """
        metrics_df = self.get_historical_metrics(days)
        
        if metrics_df.count() == 0:
            return {"message": "No metrics available"}
        
        summary = metrics_df.agg(
            count("pipeline_id").alias("total_runs"),
            avg("duration_seconds").alias("avg_duration"),
            spark_max("duration_seconds").alias("max_duration"),
            spark_min("duration_seconds").alias("min_duration"),
            spark_sum("total_records").alias("total_records_processed"),
            avg("average_records_per_second").alias("avg_throughput"),
            spark_sum(when(col("status") == "SUCCESS", 1).otherwise(0)).alias("successful_runs"),
            spark_sum(when(col("status") == "FAILED", 1).otherwise(0)).alias("failed_runs")
        ).collect()[0]
        
        return {
            "period_days": days,
            "total_runs": summary["total_runs"],
            "successful_runs": summary["successful_runs"],
            "failed_runs": summary["failed_runs"],
            "success_rate": (summary["successful_runs"] / summary["total_runs"] * 100) 
                           if summary["total_runs"] > 0 else 0,
            "avg_duration_seconds": summary["avg_duration"],
            "max_duration_seconds": summary["max_duration"],
            "min_duration_seconds": summary["min_duration"],
            "total_records_processed": summary["total_records_processed"],
            "avg_throughput_records_per_second": summary["avg_throughput"]
        }


class PerformanceTracker:
    """Tracks performance metrics for individual operations."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize performance tracker.
        
        Args:
            logger: Logger instance to use
        """
        self.logger = logger or logging.getLogger(__name__)
        self.timings = {}
        self.counters = {}
    
    def track_timing(self, operation_name: str):
        """
        Decorator to track operation timing.
        
        Args:
            operation_name: Name of the operation to track
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    self.record_timing(operation_name, duration, "SUCCESS")
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self.record_timing(operation_name, duration, "FAILED")
                    raise
            return wrapper
        return decorator
    
    def record_timing(self, operation: str, duration: float, status: str = "SUCCESS"):
        """
        Record timing for an operation.
        
        Args:
            operation: Operation name
            duration: Duration in seconds
            status: Operation status
        """
        if operation not in self.timings:
            self.timings[operation] = []
        
        self.timings[operation].append({
            "timestamp": datetime.now().isoformat(),
            "duration": duration,
            "status": status
        })
        
        self.logger.info(f"Operation '{operation}': {duration:.2f}s ({status})")
    
    def increment_counter(self, counter_name: str, value: int = 1):
        """
        Increment a counter.
        
        Args:
            counter_name: Name of the counter
            value: Value to increment by
        """
        if counter_name not in self.counters:
            self.counters[counter_name] = 0
        self.counters[counter_name] += value
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all tracked metrics.
        
        Returns:
            Dictionary with performance summary
        """
        summary = {
            "counters": self.counters,
            "timings": {}
        }
        
        for operation, timings in self.timings.items():
            durations = [t["duration"] for t in timings if t["status"] == "SUCCESS"]
            if durations:
                summary["timings"][operation] = {
                    "count": len(timings),
                    "success_count": len(durations),
                    "avg_duration": sum(durations) / len(durations),
                    "max_duration": max(durations),
                    "min_duration": min(durations),
                    "total_duration": sum(durations)
                }
        
        return summary


class AlertManager:
    """Manages alerts and notifications based on pipeline events."""
    
    def __init__(self, thresholds: Dict[str, Any]):
        """
        Initialize alert manager.
        
        Args:
            thresholds: Dictionary of alert thresholds
        """
        self.thresholds = thresholds
        self.alerts = []
        self.logger = logging.getLogger(__name__)
    
    def check_duration_threshold(self, duration: float, table_name: str = None) -> bool:
        """
        Check if duration exceeds threshold.
        
        Args:
            duration: Duration in seconds
            table_name: Optional table name for context
            
        Returns:
            True if threshold exceeded
        """
        max_duration = self.thresholds.get("max_duration_seconds", 3600)
        if duration > max_duration:
            alert = {
                "type": "DURATION_EXCEEDED",
                "severity": "WARNING",
                "message": f"Duration {duration:.2f}s exceeded threshold {max_duration}s",
                "table": table_name,
                "timestamp": datetime.now().isoformat()
            }
            self.alerts.append(alert)
            self.logger.warning(alert["message"])
            return True
        return False
    
    def check_error_rate(self, error_count: int, total_count: int) -> bool:
        """
        Check if error rate exceeds threshold.
        
        Args:
            error_count: Number of errors
            total_count: Total number of operations
            
        Returns:
            True if threshold exceeded
        """
        if total_count == 0:
            return False
        
        error_rate = (error_count / total_count) * 100
        max_error_rate = self.thresholds.get("max_error_rate_percent", 10)
        
        if error_rate > max_error_rate:
            alert = {
                "type": "ERROR_RATE_HIGH",
                "severity": "CRITICAL",
                "message": f"Error rate {error_rate:.2f}% exceeded threshold {max_error_rate}%",
                "timestamp": datetime.now().isoformat()
            }
            self.alerts.append(alert)
            self.logger.error(alert["message"])
            return True
        return False
    
    def check_data_quality(self, failed_checks: int, total_checks: int) -> bool:
        """
        Check if data quality failure rate exceeds threshold.
        
        Args:
            failed_checks: Number of failed quality checks
            total_checks: Total number of quality checks
            
        Returns:
            True if threshold exceeded
        """
        if total_checks == 0:
            return False
        
        failure_rate = (failed_checks / total_checks) * 100
        max_failure_rate = self.thresholds.get("max_quality_failure_rate_percent", 5)
        
        if failure_rate > max_failure_rate:
            alert = {
                "type": "DATA_QUALITY_ISSUES",
                "severity": "WARNING",
                "message": f"Data quality failure rate {failure_rate:.2f}% exceeded threshold {max_failure_rate}%",
                "timestamp": datetime.now().isoformat()
            }
            self.alerts.append(alert)
            self.logger.warning(alert["message"])
            return True
        return False
    
    def get_alerts(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get alerts, optionally filtered by severity.
        
        Args:
            severity: Optional severity filter (CRITICAL, WARNING, INFO)
            
        Returns:
            List of alerts
        """
        if severity:
            return [a for a in self.alerts if a["severity"] == severity]
        return self.alerts
    
    def clear_alerts(self):
        """Clear all alerts."""
        self.alerts = []


class LogAnalyzer:
    """Analyzes pipeline logs for patterns and issues."""
    
    @staticmethod
    def analyze_error_patterns(log_entries: List[str]) -> Dict[str, Any]:
        """
        Analyze error patterns in log entries.
        
        Args:
            log_entries: List of log entries
            
        Returns:
            Dictionary with error analysis
        """
        error_patterns = {
            "connection_errors": 0,
            "timeout_errors": 0,
            "data_quality_errors": 0,
            "schema_errors": 0,
            "permission_errors": 0,
            "unknown_errors": 0
        }
        
        for entry in log_entries:
            entry_lower = entry.lower()
            if "connection" in entry_lower or "jdbc" in entry_lower:
                error_patterns["connection_errors"] += 1
            elif "timeout" in entry_lower:
                error_patterns["timeout_errors"] += 1
            elif "quality" in entry_lower or "validation" in entry_lower:
                error_patterns["data_quality_errors"] += 1
            elif "schema" in entry_lower or "column" in entry_lower:
                error_patterns["schema_errors"] += 1
            elif "permission" in entry_lower or "access" in entry_lower:
                error_patterns["permission_errors"] += 1
            else:
                error_patterns["unknown_errors"] += 1
        
        return {
            "total_errors": len(log_entries),
            "patterns": error_patterns,
            "most_common": max(error_patterns, key=error_patterns.get) 
                          if any(error_patterns.values()) else None
        }
    
    @staticmethod
    def extract_performance_metrics(log_entries: List[str]) -> Dict[str, List[float]]:
        """
        Extract performance metrics from log entries.
        
        Args:
            log_entries: List of log entries
            
        Returns:
            Dictionary with extracted metrics
        """
        import re
        
        metrics = {
            "durations": [],
            "record_counts": [],
            "throughput": []
        }
        
        for entry in log_entries:
            # Extract duration (assuming format: "duration: X.XX seconds")
            duration_match = re.search(r'duration[:\s]+(\d+\.?\d*)\s*s', entry, re.IGNORECASE)
            if duration_match:
                metrics["durations"].append(float(duration_match.group(1)))
            
            # Extract record counts
            records_match = re.search(r'(\d+)\s+records?', entry, re.IGNORECASE)
            if records_match:
                metrics["record_counts"].append(int(records_match.group(1)))
            
            # Extract throughput
            throughput_match = re.search(r'(\d+\.?\d*)\s+records?/s', entry, re.IGNORECASE)
            if throughput_match:
                metrics["throughput"].append(float(throughput_match.group(1)))
        
        return metrics


def create_monitoring_dashboard_query() -> str:
    """
    Create SQL query for monitoring dashboard.
    
    Returns:
        SQL query string for dashboard
    """
    return """
    WITH recent_runs AS (
        SELECT 
            pipeline_id,
            start_time,
            end_time,
            duration_seconds,
            total_records,
            status,
            success_count,
            error_count,
            average_records_per_second as throughput
        FROM pipeline_metrics
        WHERE start_time >= current_timestamp() - INTERVAL 7 DAYS
    ),
    hourly_stats AS (
        SELECT 
            date_trunc('hour', start_time) as hour,
            COUNT(*) as runs_per_hour,
            AVG(duration_seconds) as avg_duration,
            SUM(total_records) as records_per_hour,
            SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_runs,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_runs
        FROM recent_runs
        GROUP BY date_trunc('hour', start_time)
    ),
    daily_summary AS (
        SELECT 
            date_trunc('day', start_time) as day,
            COUNT(*) as total_runs,
            AVG(duration_seconds) as avg_duration,
            MAX(duration_seconds) as max_duration,
            MIN(duration_seconds) as min_duration,
            SUM(total_records) as total_records,
            AVG(throughput) as avg_throughput,
            (SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as success_rate
        FROM recent_runs
        GROUP BY date_trunc('day', start_time)
    )
    SELECT 
        'hourly_stats' as metric_type,
        hour as timestamp,
        runs_per_hour as value1,
        avg_duration as value2,
        records_per_hour as value3,
        successful_runs as value4,
        failed_runs as value5
    FROM hourly_stats
    UNION ALL
    SELECT 
        'daily_summary' as metric_type,
        day as timestamp,
        total_runs as value1,
        avg_duration as value2,
        total_records as value3,
        avg_throughput as value4,
        success_rate as value5
    FROM daily_summary
    ORDER BY metric_type, timestamp DESC
    """


# Export all monitoring classes
__all__ = [
    'PipelineMetrics',
    'PipelineMonitor',
    'PerformanceTracker',
    'AlertManager',
    'LogAnalyzer',
    'create_monitoring_dashboard_query'
]