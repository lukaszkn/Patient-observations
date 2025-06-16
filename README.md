# Patient-observations

[How to Run the MapReduce Scripts](README.md#how-to-run-the-mapreduce-scripts)<br>
[How to Run the PySpark Scripts](README.md#how-to-run-the-pyspark-scripts)<br>
[How to Run the Scala Spark Scripts](README.md#how-to-run-the-pyspark-scripts)

This project is designed as a hands-on playground for anyone looking to learn and experiment with a complete big data ecosystem on their local machine. It removes the complexity of manual setup by providing a single `docker-compose.yml` file to launch a multi-node cluster with essential data engineering tools.

The core of this repository is a set of example data processing jobs written in three popular frameworks, all running on the same sample dataset of patient medical observations. This allows for a direct comparison of different programming paradigms and execution models.

### Key Features

- **One-Command Setup**: Launch a full data stack with `docker-compose up`.
- **Complete Ecosystem**: Includes **Hadoop** (HDFS, YARN), **Spark**, **Hive** (with a PostgreSQL metastore), and **Apache Airflow** for orchestration.
- **Cross-Framework Examples**: Solve the same data problems using:
    - **MapReduce**: Classic Hadoop processing with Python's `mrjob` library.
    - **PySpark**: Modern, DataFrame-based data manipulation in Python.
    - **Scala & Spark**: Statically-typed, high-performance data processing on the JVM.
- **Sample Data**: Includes JSON files with patient demographics and medical readings, ready for analysis.
- **Detailed Instructions**: Clear, step-by-step guides on how to run each job both locally (for quick testing) and on the Dockerized cluster.

### What You Can Learn

- **Environment Setup**: How to configure and run a multi-component data stack using Docker.
- **Comparing Paradigms**: Understand the differences in syntax, performance, and approach between MapReduce, PySpark, and Scala/Spark.
- **Data Processing Logic**: Implement common data analysis patterns like aggregation, filtering, and joining.
- **Interacting with HDFS**: Learn how to manage files in a distributed file system.
- **Submitting Spark Jobs**: See how to submit applications to a Spark cluster from the command line.

### How to Use This Project

1.  **Start the Cluster**: Run `docker-compose up -d` to launch all services.
2.  **Explore the Scripts**:
    - The `mrjob` scripts (`average_score_by_patient.py`, etc.) demonstrate classic MapReduce.
    - The PySpark scripts (`pyspark_average_score.py`, etc.) showcase the Spark DataFrame API in Python.
    - The `scala_spark` directory contains a complete `sbt` project for Scala-based Spark applications.
3.  **Run the Jobs**: Follow the detailed instructions in the provided documentation to run the jobs either locally or on the Docker cluster. For the Scala examples, you will need to install `sbt` to build the project JAR first.


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

### How to Run the PySpark Scripts

You can run these scripts in two ways: locally on your machine for testing, or on the Dockerized Spark cluster.

#### 1. Running Locally

This method is useful for quick testing and debugging. You'll need to have `pyspark` installed (`pip install pyspark`).

__`pyspark_average_score.py`__

```bash
spark-submit pyspark_average_score.py
```

__`pyspark_high_risk.py`__

You can run this with the default risk threshold of 5.0:

```bash
spark-submit pyspark_high_risk.py
```

Or with a custom threshold:

```bash
spark-submit pyspark_high_risk.py --threshold 7.0
```

__`pyspark_join_data.py`__

```bash
spark-submit pyspark_join_data.py
```

#### 2. Running on the Dockerized Spark Cluster

This method demonstrates how to run the jobs on the Spark cluster.

__Step 1: Start the Cluster__

If it's not already running, start all the services:

```bash
docker-compose up -d
```

__Step 2: Submit the PySpark Jobs__

Use `docker-compose exec` to run `spark-submit` on the `spark-master` container.

__`pyspark_average_score.py`__

```bash
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /data/pyspark_average_score.py
```

__`pyspark_high_risk.py`__

```bash
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /data/pyspark_high_risk.py --threshold 7.0
```

__`pyspark_join_data.py`__

```bash
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /data/pyspark_join_data.py
```

### How to Run the Scala Spark Scripts

Once `sbt` is installed, you can proceed with building and running the scripts.

#### 1. Build the JAR

Navigate to the `scala_spark` directory and run the `sbt package` command. This will compile your code and create a JAR file named `scalasparkexamples_2.12-1.0.jar` in the `scala_spark/target/scala-2.12/` directory.

```bash
cd scala_spark
sbt package
```

#### 2. Running Locally

After building the JAR, you can submit the applications to Spark locally. Make sure you are in the `scala_spark` directory.

__`AverageScore.scala`__

```bash
spark-submit --class AverageScore target/scala-2.12/scalasparkexamples_2.12-1.0.jar ../data/observations_micro.json
```

__`HighRiskPatients.scala`__

```bash
# With default threshold (5.0)
spark-submit --class HighRiskPatients target/scala-2.12/scalasparkexamples_2.12-1.0.jar ../data/observations_micro.json

# With custom threshold
spark-submit --class HighRiskPatients target/scala-2.12/scalasparkexamples_2.12-1.0.jar ../data/observations_micro.json 7.0
```

__`JoinData.scala`__

```bash
spark-submit --class JoinData target/scala-2.12/scalasparkexamples_2.12-1.0.jar ../data/observations_micro.json ../data/patients_micro.json
```

#### 3. Running on the Dockerized Spark Cluster

__Step 1: Copy the JAR to the Spark Master Container__

First, copy the JAR file from your local machine into the `spark-master` container.

```bash
docker cp scala_spark/target/scala-2.12/scalasparkexamples_2.12-1.0.jar spark-master:/
```

__Step 2: Submit the Jobs to the Spark Cluster__

Now you can execute the jobs on the cluster.

__`AverageScore.scala`__

```bash
docker-compose exec spark-master spark-submit --class AverageScore --master spark://spark-master:7077 /scalasparkexamples_2.12-1.0.jar /data/observations_micro.json
```

__`HighRiskPatients.scala`__

```bash
docker-compose exec spark-master spark-submit --class HighRiskPatients --master spark://spark-master:7077 /scalasparkexamples_2.12-1.0.jar /data/observations_micro.json 7.0
```

__`JoinData.scala`__

```bash
docker-compose exec spark-master spark-submit --class JoinData --master spark://spark-master:7077 /scalasparkexamples_2.12-1.0.jar /data/observations_micro.json /data/patients_micro.json
```
