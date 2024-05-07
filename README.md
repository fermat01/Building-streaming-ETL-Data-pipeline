# Building-streaming-Data-pipeline


![GitHub](https://img.shields.io/github/license/fermat01/Building-streaming-Data-pipeline?style=flat)
![GitHub top language](https://img.shields.io/github/languages/top/fermat01/Building-streaming-Data-pipeline?style=flat)
![GitHub language count](https://img.shields.io/github/languages/count/fermat01/Building-streaming-Data-pipeline?style=flat)
![GitHub last commit](https://img.shields.io/github/last-commit/fermat01/Building-streaming-Data-pipeline?style=flat)
![ViewCount](https://views.whatilearened.today/views/github/fermat01/Building-streaming-Data-pipeline.svg?cache=remove)




Building streaming Data pipeline using apache airflow, kafka ,...



## 1. Architecture

<img src="images/streaming-architect.gif" > 

 <br />


To be continued ...

1. Create network using

```
docker network create streaming_network
```



2. Access the Kafka UI at http://localhost:8888/ and  create topic naming 'streaming_topic'
   
3.  Create Minio docker container
   
docker run \
   -p 9090:9000 \
   -p 9001:9001 \
   --name minio \
   -v ~/minio/data:/data \
   -e "MINIO_ROOT_USER=MINIOAIRFLOW01" \
   -e "MINIO_ROOT_PASSWORD=AIRFLOW123" \
   quay.io/minio/minio server /data --console-address ":9001"

 and acess minio  UI using ``` http://127.0.0.1:9001 ``` and credentials uername: MINIOAIRFLOW01 and password:AIRFLOW123
4. Copy your Spark script into the Docker container:
```
docker cp data_processing_spark.py spark_master:/opt/bitnami/spark/
```

and go inside spark container
```
docker exec -it spark_master /bin/bash
```

and to list all jar files in jars directory
```
cd jars
```
and ls -ll
5.  Download required jar files ???? 
   
   ```

curl -O https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/2.8.1/kafka-clients-2.8.1.jar
curl -O https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.13/3.3.0/spark-sql-kafka-0-10_2.13-3.3.0.jar
curl -O https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.2.0/hadoop-aws-3.2.0.jar
curl -O https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-s3/1.11.375/aws-java-sdk-s3-1.11.375.jar
curl -O https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.8.0/commons-pool2-2.8.0.jar



### new package added
curl -O https://repo1.maven.org/maven2/org/apache/spark/spark-streaming-kafka-0-10-assembly_2.12/3.0.2/spark-streaming-kafka-0-10-assembly_2.12-3.0.2.jar

   ```
NB: Minio is S3 API compatible ?? => to connect to our minio bucket we can use aws s3 api which is included in airflow as amazon airflow provider packages






spark-submit \\
--master local[2] \\
--jars /opt/bitnami/spark/jars/kafka-clients-2.8.1.jar,\\
/opt/bitnami/spark/jars/spark-sql-kafka-0-10_2.13-3.3.0.jar,\\
/opt/bitnami/spark/jars/hadoop-aws-3.2.0.jar,\\
/opt/bitnami/spark/jars/spark-streaming-kafka-0-10-assembly_2.12-3.0.2.jar,\\
/opt/bitnami/spark/jars/aws-java-sdk-s3-1.11.375.jar,\\
/opt/bitnami/spark/jars/commons-pool2-2.8.0.jar \\

spark_processing.py