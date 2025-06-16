# Patient-observations

## docker-hadoop-spark
```
CONTAINER ID   IMAGE                                                    NAMES
bd9529c403b9   apache/airflow:2.2.3                                     flower
679098c59b2a   apache/airflow:2.2.3                                     airflow-worker
ce24a18e4da4   apache/airflow:2.2.3                                     airflow-scheduler
00c5ec70d8bd   apache/airflow:2.2.3                                     airflow-webserver
6eae0258afcf   apache/airflow:2.2.3                                     airflow-init
8af32717cfbd   bde2020/spark-worker:3.1.1-hadoop3.2                     spark-worker
75a30630b2aa   postgres:13                                              postgres
b7bd7852f7c6   redis:latest                                             redis
0c9d0cf02925   bde2020/hive:2.3.2-postgresql-metastore                  hive-server
0162d067e35b   bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8          datanode
f020ec09e646   bde2020/spark-master:3.1.1-hadoop3.2                     spark-master
da9ae7ad9e01   bde2020/hadoop-historyserver:2.0.0-hadoop3.2.1-java8     historyserver
5e9be1518b5b   bde2020/hive-metastore-postgresql:2.3.0                  hive-metastore-postgresql
f6dff153b374   bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8          namenode
306017bc35e2   bde2020/hadoop-resourcemanager:2.0.0-hadoop3.2.1-java8   resourcemanager
8d897b0a09d1   bde2020/hadoop-nodemanager:2.0.0-hadoop3.2.1-java8       nodemanager
616c89e60765   bde2020/hive:2.3.2-postgresql-metastore                  hive-metastore
```

### How to Run the MapReduce Scripts

You can run these scripts in two ways: locally on your machine for testing, or on the Dockerized Hadoop cluster.

#### 1. Running Locally

This method is useful for quick testing and debugging without the overhead of the Hadoop cluster.

__`average_score_by_patient.py`__

```bash
python3 average_score_by_patient.py data/observations.json
```

__`high_risk_patients.py`__

You can run this with the default risk threshold of 5.0:

```bash
python3 high_risk_patients.py data/observations.json
```

Or with a custom threshold:

```bash
python3 high_risk_patients.py --risk-threshold=7.0 data/observations.json
```

__`patient_demographics_join.py`__

This script takes both data files as input:

```bash
python3 patient_demographics_join.py data/observations.json data/patients.json
```

#### 2. Running on the Dockerized Hadoop Cluster

This method demonstrates how to run the jobs in a distributed environment.

__Step 1: Start the Cluster__

First, you need to start all the services defined in the `docker-compose.yml` file.

```bash
docker-compose up -d
```

__Step 2: Copy Data to HDFS__

Next, copy the local data files into the Hadoop Distributed File System (HDFS).

```bash
docker-compose exec namenode hdfs dfs -mkdir -p /user/root/input
docker-compose exec namenode hdfs dfs -put /data/observations.json /user/root/input/
docker-compose exec namenode hdfs dfs -put /data/patients.json /user/root/input/
```

__Step 3: Submit the MapReduce Jobs__

Now you can submit the jobs to the Hadoop cluster.

__`average_score_by_patient.py`__

```bash
python3 average_score_by_patient.py -r hadoop --hadoop-bin /usr/local/hadoop/bin/hadoop hdfs:///user/root/input/observations.json
```

__`high_risk_patients.py`__

```bash
python3 high_risk_patients.py -r hadoop --hadoop-bin /usr/local/hadoop/bin/hadoop hdfs:///user/root/input/observations.json
```

__`patient_demographics_join.py`__

```bash
python3 patient_demographics_join.py -r hadoop --hadoop-bin /usr/local/hadoop/bin/hadoop hdfs:///user/root/input/observations.json hdfs:///user/root/input/patients.json
```

__Step 4: View the Output__

The output of the jobs will be stored in HDFS. You can view the output directory with:

```bash
docker-compose exec namenode hdfs dfs -ls /user/root/
```

And view the content of the output files with:

```bash
docker-compose exec namenode hdfs dfs -cat /user/root/output_directory/part-00000
```

(Replace `output_directory` with the actual output directory name).

This completes the task. You now have a `docker-compose.yml` file for a full data engineering stack, three MapReduce scripts, and instructions on how to run them.
