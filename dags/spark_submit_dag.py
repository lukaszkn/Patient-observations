from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from datetime import datetime

with DAG(
    dag_id='spark_patient_data_join',
    start_date=datetime(2025, 6, 16),
    schedule_interval=None,
    catchup=False,
    tags=['spark', 'example'],
) as dag:
    submit_spark_job = SparkSubmitOperator(
        task_id='submit_pyspark_join_job',
        application='/opt/airflow/dags/pyspark_join_data.py',  # Path inside the Airflow container
        conn_id='spark_default',  # This should be configured in the Airflow UI
        conf={'spark.master': 'spark://spark-master:7077'},
        verbose=True
    )
