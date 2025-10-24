"""
Databricks Job Configuration for Hourly Pipeline Execution
This module creates and manages Databricks jobs for scheduled pipeline runs
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


class DatabricksJobConfig:
    """Configuration for Databricks scheduled jobs."""
    
    @staticmethod
    def create_job_config(
        job_name: str,
        notebook_path: str,
        cluster_config: Dict[str, Any],
        schedule: Dict[str, Any],
        parameters: Optional[Dict[str, str]] = None,
        email_notifications: Optional[Dict[str, List[str]]] = None,
        max_retries: int = 2,
        timeout_seconds: int = 7200,
        tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create a Databricks job configuration.
        
        Args:
            job_name: Name of the job
            notebook_path: Path to the notebook in Databricks workspace
            cluster_config: Cluster configuration
            schedule: Schedule configuration (cron expression)
            parameters: Notebook parameters
            email_notifications: Email notification settings
            max_retries: Maximum number of retries
            timeout_seconds: Job timeout in seconds
            tags: Job tags for organization
            
        Returns:
            Job configuration dictionary
        """
        job_config = {
            "name": job_name,
            "tasks": [
                {
                    "task_key": "incremental_pipeline_task",
                    "description": "Run incremental data pipeline from Azure SQL to Databricks",
                    "notebook_task": {
                        "notebook_path": notebook_path,
                        "base_parameters": parameters or {}
                    },
                    "new_cluster": cluster_config,
                    "max_retries": max_retries,
                    "timeout_seconds": timeout_seconds,
                    "retry_on_timeout": True
                }
            ],
            "schedule": schedule,
            "max_concurrent_runs": 1,
            "tags": tags or {},
            "format": "MULTI_TASK"
        }
        
        if email_notifications:
            job_config["email_notifications"] = email_notifications
        
        return job_config
    
    @staticmethod
    def get_hourly_schedule() -> Dict[str, Any]:
        """Get configuration for hourly schedule."""
        return {
            "quartz_cron_expression": "0 0 * ? * * *",  # Every hour at minute 0
            "timezone_id": "UTC",
            "pause_status": "UNPAUSED"
        }
    
    @staticmethod
    def get_cluster_config(
        node_type: str = "Standard_DS3_v2",
        min_workers: int = 1,
        max_workers: int = 4,
        spark_version: str = "13.3.x-scala2.12",
        auto_termination_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        Get cluster configuration for the job.
        
        Args:
            node_type: Azure VM type for cluster nodes
            min_workers: Minimum number of workers
            max_workers: Maximum number of workers
            spark_version: Spark runtime version
            auto_termination_minutes: Auto-termination timeout
            
        Returns:
            Cluster configuration dictionary
        """
        return {
            "spark_version": spark_version,
            "node_type_id": node_type,
            "num_workers": min_workers,
            "autoscale": {
                "min_workers": min_workers,
                "max_workers": max_workers
            },
            "auto_termination_minutes": auto_termination_minutes,
            "spark_conf": {
                "spark.sql.adaptive.enabled": "true",
                "spark.sql.adaptive.coalescePartitions.enabled": "true",
                "spark.databricks.delta.optimizeWrite.enabled": "true",
                "spark.databricks.delta.autoCompact.enabled": "true",
                "spark.sql.shuffle.partitions": "auto"
            },
            "spark_env_vars": {
                "PYSPARK_PYTHON": "/databricks/python3/bin/python3"
            },
            "init_scripts": [],
            "custom_tags": {
                "Project": "DataPipeline",
                "Environment": "Production",
                "Team": "DataEngineering"
            }
        }
    
    @staticmethod
    def get_email_notifications(
        on_success: List[str] = None,
        on_failure: List[str] = None,
        on_start: List[str] = None,
        no_alert_for_skipped_runs: bool = True
    ) -> Dict[str, Any]:
        """
        Configure email notifications for the job.
        
        Args:
            on_success: Email addresses to notify on success
            on_failure: Email addresses to notify on failure
            on_start: Email addresses to notify on start
            no_alert_for_skipped_runs: Skip alerts for skipped runs
            
        Returns:
            Email notification configuration
        """
        notifications = {
            "no_alert_for_skipped_runs": no_alert_for_skipped_runs
        }
        
        if on_success:
            notifications["on_success"] = on_success
        if on_failure:
            notifications["on_failure"] = on_failure
        if on_start:
            notifications["on_start"] = on_start
        
        return notifications


def create_hourly_pipeline_job() -> Dict[str, Any]:
    """
    Create the complete job configuration for hourly pipeline execution.
    
    Returns:
        Complete job configuration dictionary
    """
    # Define cluster configuration
    cluster_config = DatabricksJobConfig.get_cluster_config(
        node_type="Standard_DS3_v2",  # Adjust based on workload
        min_workers=1,
        max_workers=4,
        spark_version="13.3.x-scala2.12",
        auto_termination_minutes=30
    )
    
    # Define schedule (hourly)
    schedule = DatabricksJobConfig.get_hourly_schedule()
    
    # Define parameters
    parameters = {
        "config_path": "/dbfs/mnt/config/pipeline_config.json",
        "log_level": "INFO",
        "parallel_tables": "2",
        "enable_notifications": "true"
    }
    
    # Define email notifications
    email_notifications = DatabricksJobConfig.get_email_notifications(
        on_failure=["data-team@company.com", "ops-team@company.com"],
        on_success=["data-team@company.com"]
    )
    
    # Create job configuration
    job_config = DatabricksJobConfig.create_job_config(
        job_name="Azure_SQL_to_Databricks_Incremental_Pipeline",
        notebook_path="/Workspace/pipelines/enhanced_pipeline",
        cluster_config=cluster_config,
        schedule=schedule,
        parameters=parameters,
        email_notifications=email_notifications,
        max_retries=2,
        timeout_seconds=7200,  # 2 hours
        tags={
            "Project": "DataMigration",
            "Source": "AzureSQL",
            "Target": "Databricks",
            "Type": "Incremental",
            "Schedule": "Hourly"
        }
    )
    
    return job_config


def create_job_via_api(job_config: Dict[str, Any], 
                       databricks_host: str,
                       databricks_token: str) -> Dict[str, Any]:
    """
    Create a job using Databricks REST API.
    
    Args:
        job_config: Job configuration dictionary
        databricks_host: Databricks workspace URL
        databricks_token: Databricks access token
        
    Returns:
        API response with job details
    """
    import requests
    
    url = f"{databricks_host}/api/2.1/jobs/create"
    headers = {
        "Authorization": f"Bearer {databricks_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json=job_config)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to create job: {response.text}")


def update_job_via_api(job_id: int,
                       job_config: Dict[str, Any],
                       databricks_host: str,
                       databricks_token: str) -> Dict[str, Any]:
    """
    Update an existing job using Databricks REST API.
    
    Args:
        job_id: ID of the job to update
        job_config: Updated job configuration
        databricks_host: Databricks workspace URL
        databricks_token: Databricks access token
        
    Returns:
        API response
    """
    import requests
    
    url = f"{databricks_host}/api/2.1/jobs/update"
    headers = {
        "Authorization": f"Bearer {databricks_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "job_id": job_id,
        "new_settings": job_config
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to update job: {response.text}")


def get_job_runs(job_id: int,
                databricks_host: str,
                databricks_token: str,
                limit: int = 10) -> Dict[str, Any]:
    """
    Get recent runs for a job.
    
    Args:
        job_id: ID of the job
        databricks_host: Databricks workspace URL
        databricks_token: Databricks access token
        limit: Maximum number of runs to retrieve
        
    Returns:
        Job runs information
    """
    import requests
    
    url = f"{databricks_host}/api/2.1/jobs/runs/list"
    headers = {
        "Authorization": f"Bearer {databricks_token}",
        "Content-Type": "application/json"
    }
    
    params = {
        "job_id": job_id,
        "limit": limit
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get job runs: {response.text}")


# Alternative: Job configuration as a notebook cell
NOTEBOOK_JOB_CONFIG = """
# Databricks notebook source
# MAGIC %md
# MAGIC # Hourly Pipeline Job Configuration
# MAGIC This notebook sets up the hourly job for the incremental pipeline

# COMMAND ----------

# Import required libraries
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import jobs
import json

# COMMAND ----------

# Initialize Databricks client
w = WorkspaceClient()

# COMMAND ----------

# Define job configuration
job_name = "Azure_SQL_to_Databricks_Incremental_Pipeline"
notebook_path = "/Workspace/pipelines/enhanced_pipeline"

# Cluster configuration
cluster_spec = jobs.ClusterSpec(
    spark_version="13.3.x-scala2.12",
    node_type_id="Standard_DS3_v2",
    autoscale=jobs.AutoScale(min_workers=1, max_workers=4),
    spark_conf={
        "spark.sql.adaptive.enabled": "true",
        "spark.sql.adaptive.coalescePartitions.enabled": "true",
        "spark.databricks.delta.optimizeWrite.enabled": "true",
        "spark.databricks.delta.autoCompact.enabled": "true"
    }
)

# Task configuration
task = jobs.Task(
    task_key="incremental_pipeline_task",
    description="Run incremental data pipeline",
    notebook_task=jobs.NotebookTask(
        notebook_path=notebook_path,
        base_parameters={
            "config_path": "/dbfs/mnt/config/pipeline_config.json",
            "log_level": "INFO"
        }
    ),
    new_cluster=cluster_spec,
    max_retries=2,
    timeout_seconds=7200
)

# Schedule configuration (hourly)
schedule = jobs.CronSchedule(
    quartz_cron_expression="0 0 * ? * * *",  # Every hour
    timezone_id="UTC",
    pause_status=jobs.PauseStatus.UNPAUSED
)

# Email notifications
email_notifications = jobs.JobEmailNotifications(
    on_failure=["data-team@company.com"],
    on_success=["data-team@company.com"],
    no_alert_for_skipped_runs=True
)

# COMMAND ----------

# Create or update the job
try:
    # Check if job exists
    existing_jobs = w.jobs.list(name=job_name)
    job_exists = False
    job_id = None
    
    for job in existing_jobs:
        if job.settings.name == job_name:
            job_exists = True
            job_id = job.job_id
            break
    
    if job_exists:
        # Update existing job
        print(f"Updating existing job with ID: {job_id}")
        w.jobs.update(
            job_id=job_id,
            new_settings=jobs.JobSettings(
                name=job_name,
                tasks=[task],
                schedule=schedule,
                email_notifications=email_notifications,
                max_concurrent_runs=1,
                tags={
                    "Project": "DataMigration",
                    "Schedule": "Hourly"
                }
            )
        )
        print("Job updated successfully")
    else:
        # Create new job
        print("Creating new job")
        response = w.jobs.create(
            name=job_name,
            tasks=[task],
            schedule=schedule,
            email_notifications=email_notifications,
            max_concurrent_runs=1,
            tags={
                "Project": "DataMigration",
                "Schedule": "Hourly"
            }
        )
        print(f"Job created successfully with ID: {response.job_id}")
        
except Exception as e:
    print(f"Error managing job: {str(e)}")
    raise

# COMMAND ----------

# Display job information
if job_id:
    job_info = w.jobs.get(job_id=job_id)
    print(f"Job Name: {job_info.settings.name}")
    print(f"Job ID: {job_id}")
    print(f"Schedule: {job_info.settings.schedule.quartz_cron_expression}")
    print(f"Status: Active")
"""


if __name__ == "__main__":
    # Create job configuration
    job_config = create_hourly_pipeline_job()
    
    # Save to file
    with open("databricks_pipeline/job_config.json", "w") as f:
        json.dump(job_config, f, indent=2)
    
    print("Job configuration created successfully")
    print(json.dumps(job_config, indent=2))