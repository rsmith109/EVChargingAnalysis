import configparser
import csv
import pymysql

def readConfig(configFile):

    # Get credentials to connect to database
    config = configparser.ConfigParser()
    try:
        config.read_file(open(configFile)) # point to the correct place where this file is!
        dbConfig = {
            "host" : config['csc']['dbhost'],
            "user" : config['csc']['dbuser'],
            "password" : config['csc']['dbpw']
        }
        return dbConfig
    except FileNotFoundError as e:
        print(f"{configFile} was not found")
        raise

def connectToDatabase(dbName,configFile):

    #read in connection info
    dbConfig = readConfig(configFile)

    #Open database connection
    dbConn = pymysql.connect(host=dbConfig["host"],
                             user=dbConfig["user"],
                             passwd=dbConfig["password"],
                             db=dbName,
                             use_unicode=True,
                             charset='utf8mb4',
                             autocommit=True)

    return dbConn

def disconnectFromDatabase(dbConn):
    dbConn.close()

def addSaticValues(dbConn):
    insertStaticValuesSQL = ["insert into FP_charger_type (charger_type_name) Values ('DC Fast Charger'), ('Level 1'), ('Level 2');",
                            "insert into FP_day_of_week (dow_name) Values ('Monday'), ('Tuesday'), ('Wednesday'), ('Thursday'), ('Friday'), ('Saturday'), ('Sunday');",
                            "insert into FP_time_of_day (time_of_day_name) Values ('Evening'), ('Morning'), ('Afternoon'), ('Night');",
                            "insert into FP_user_type (user_type_name) Values ('Commuter'), ('Casual Driver'), ('Long-Distance Traveler');"]

    cursor = dbConn.cursor()

    for statement in insertStaticValuesSQL:
        cursor.execute(statement)

def processFile(fileName,dbConn):
    batchSize = 500
    with open(fileName) as gameFile:
       gameFileReader = csv.DictReader(gameFile)
       batchCounter = 1
       gameList=[]
       for gameDictionary in gameFileReader:
           gameList.append(processRow(dbConn,gameDictionary))
           if (batchCounter == batchSize):
               saveEvChargerFact(dbConn,gameList)
               gameList = []
               batchCounter = 1
           else:
               batchCounter += 1
    saveEvChargerFact(dbConn,gameList)
def processRow(dbConn,evChargerDictionary):
    evChargerDictionary = cleanDictionary(evChargerDictionary)
    return (
        getStationDemension(dbConn, evChargerDictionary["Charging_Station_ID"]), getLocationDemension(dbConn, evChargerDictionary["Charging_Station_Location"]),
        getTODDemension(dbConn, evChargerDictionary["Time_of_Day"]), getDOWDemension(dbConn, evChargerDictionary["Day_of_Week"]),
        getChargerTypeDemension(dbConn, evChargerDictionary["Charger_Type"]), getUserTypeDemension(dbConn, evChargerDictionary["User_Type"]),
        getVehicleModelDemension(dbConn, evChargerDictionary["Vehicle_Model"]), evChargerDictionary["Battery_Capacity"],
        evChargerDictionary["Charging_Start_Time"], evChargerDictionary["Charging_End_Time"], evChargerDictionary["Energy_Consumed"],
        evChargerDictionary["Charging_Duration"], evChargerDictionary["Charging_Rate"], evChargerDictionary["Charging_Cost"],
        evChargerDictionary["State_of_Charge_Start"], evChargerDictionary["State_of_Charge_End"],
        evChargerDictionary["Distance_Driven_Since_Last_Charge"], evChargerDictionary["Temperature"], evChargerDictionary["Vehicle_Age"]
    )


def cleanDictionary(initialDictionary):
    # Convert empty strings to None in the row dictionary
    # return {key: (value if value != "" else None) for key, value in row.items()}
    cleanDictionary = {}
    for key,value in initialDictionary.items():
        if value == "":
            cleanDictionary[key] = None
        else:
            cleanDictionary[key] = value
    return cleanDictionary


def saveEvChargerFact(dbConn,batchSQLStatementValues):
    gameInsertSQL= 'INSERT INTO FP_charging_fact ' \
                    '(station_id,location_id,tod_id,dow_id,charger_type_id,user_type_id,' \
                    'model_id,battery_capacity,charge_start_time,charge_end_time,energy_consumption,'    \
                    'charging_duration,average_charging_rate,charging_cost,start_charge_pct,'    \
                    'end_charge_pct,distance_driven,temperature,vehicle_age) '    \
                    'VALUES (%s, %s, %s,%s, %s, %s,%s, %s, %s, ' \
                    '%s, %s, %s,%s, %s, %s,%s, %s, %s,%s);'

    cursor = dbConn.cursor()
    cursor.executemany(gameInsertSQL,batchSQLStatementValues)



def getDimensionId(dbConn,dimensionSQL,dimensionLookupValue,dimensionIdColumn):
    print(f"Running {dimensionSQL}")
    print(f"With Value {dimensionLookupValue}")
    cursor = dbConn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(dimensionSQL,dimensionLookupValue)
    result = cursor.fetchone()
    cursor.close()
    if result is None:
        return None
    return result[dimensionIdColumn]

def insertDimension(dbConn,dimensionInsertSQL,dimensionInsertValue):
    print(f"Running {dimensionInsertSQL}")
    print(f"With Value {dimensionInsertValue}")
    cursor = dbConn.cursor()
    cursor.execute(dimensionInsertSQL,dimensionInsertValue)
    # Get the value of the auto-incremented key
    cursor.execute("SELECT LAST_INSERT_ID()")
    # Fetch the result
    auto_incremented_key = cursor.fetchone()[0]
    cursor.close()
    return auto_incremented_key

def mapSlowDimension(dbConn,dimensionLookupSQL,dimensionInsertSQL,dimesionLookupValue,dimensionIdColumn):
    if dimesionLookupValue is None:
        return None
    dimensionId = getDimensionId(dbConn,dimensionLookupSQL,dimesionLookupValue,dimensionIdColumn)
    if dimensionId is None:
        dimensionId = insertDimension(dbConn,dimensionInsertSQL,dimesionLookupValue)
    return dimensionId

def mapStaticDimension(dbConn,dimensionLookupSQL,dimensionLookupValue,dimensionIdColumn):
    if dimensionLookupValue is None:
        return None
    dimensionId = getDimensionId(dbConn,dimensionLookupSQL,dimensionLookupValue,dimensionIdColumn)
    return dimensionId

def getStationDemension(dbConn, stationValue):
    stationLookupSQL = "select station_id from FP_charging_station where station_name = %s"
    stationInsertSQL = "insert into FP_charging_station (station_name) Values (%s)"

    stationId = mapSlowDimension(dbConn,stationLookupSQL, stationInsertSQL, stationValue, "station_id")
    return stationId

def getVehicleModelDemension(dbConn, vehicleModelValue):
    modelLookupSQL = "select model_id from FP_vehicle_model where model_name = %s"
    modelInsertSQL = "insert into FP_vehicle_model (model_name) Values (%s)"

    modelId = mapSlowDimension(dbConn, modelLookupSQL, modelInsertSQL, vehicleModelValue, "model_id")
    return modelId

def getChargerTypeDemension(dbConn, chargerTypeValue):
    chargerLookupSQL = "select charger_type_id from FP_charger_type where charger_type_name = %s"

    chargerTypeId = mapStaticDimension(dbConn, chargerLookupSQL, chargerTypeValue, "charger_type_id")
    return chargerTypeId

def getLocationDemension(dbConn, locationValue):
    locationLookupSQL = "select location_id from FP_charging_station_location where location_name = %s"
    locationInsertSQL = "insert into FP_charging_station_location (location_name) Values (%s)"

    locationId = mapSlowDimension(dbConn, locationLookupSQL, locationInsertSQL, locationValue, "location_id")
    return locationId

def getDOWDemension(dbConn, DOWValue):
    DOWLookupSQL = "select dow_id from FP_day_of_week where dow_name = %s"

    DOWId = mapStaticDimension(dbConn, DOWLookupSQL, DOWValue, "dow_id")
    return DOWId

def getTODDemension(dbConn, TODValue):
    TODLookupSQL = "select tod_id from FP_time_of_day where time_of_day_name = %s"

    TODId = mapStaticDimension(dbConn, TODLookupSQL, TODValue, "tod_id")
    return TODId

def getUserTypeDemension(dbConn, userTypeValue):
    userTypeLookupSQL = "select user_type_id from FP_user_type where user_type_name = %s"

    userTypeId = mapStaticDimension(dbConn, userTypeLookupSQL, userTypeValue, "user_type_id")
    return userTypeId

#Start Main Program
if (__name__ == '__main__'):
    dbSchema = 'rsmith109'
    configFile = 'credentials.txt'
    dataFile = 'ev_final_project.csv'
    try:
        #1. Connect To Database
        dbConn = connectToDatabase(dbSchema,configFile)

        try:
            #2. Add static dimensions
            addSaticValues(dbConn)

        except Exception as e:
            print(e)

        try:
            #3 Process the File
            processFile(dataFile,dbConn)

        except Exception as e:
            print(e)
        finally:
            # 4 Close DB Connection
            disconnectFromDatabase(dbConn)
    except Exception as e:
        print(e)


