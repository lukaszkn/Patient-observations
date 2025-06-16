import org.apache.spark.sql.SparkSession

object JoinData {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder
      .appName("Join Patient Data")
      .getOrCreate()

    val observationsPath = if (args.length > 0) args(0) else "data/observations_micro.json"
    val patientsPath = if (args.length > 1) args(1) else "data/patients_micro.json"

    val observationsDF = spark.read.json(observationsPath)
    val patientsDF = spark.read.json(patientsPath)

    val joinedDF = observationsDF.join(patientsDF, "pat_no")

    joinedDF.show()

    spark.stop()
  }
}
