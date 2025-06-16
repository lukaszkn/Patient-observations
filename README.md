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
