# -*- coding: utf-8 -*-
#!/usr/bin/env python
import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId
import logging
import logging.handlers
import os
import sys
import getopt
import datetime
import collections
from scipy.stats import randint
"""
	3	2	1	k
Q	0.0001447	-0.024499	0.86506	15.4763
P	0.000021167	-0.00403	0.30249	-0.8024
"""

def pOut(t):
    retV=0.000021167*t**3-0.00403*t**2+0.30249*t-0.8024
    if retV < 0.0:
        retV = 0.0
    return retV

def qOut(t):
    retV = 0.0001447*t**3-0.024499*t**2+0.86506*t+15.4763
    return retV

# client = MongoClient('localhost', 27017)
log = logging.getLogger()
log.setLevel(logging.DEBUG)
file_handler = logging.handlers.RotatingFileHandler("{0}.log".format(os.path.basename(__file__).split(".")[0]), maxBytes=5000000,backupCount=5)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

delta_rand = randint(-2, 2)
# dati di partenza
# da caricare con
# >mongoimport --db import --collection timeseries --host srv3.sws-digital.com --file import_series.json
# generati con
# >mongoexport --db tgrout-development --collection timeseries --host srv3.sws-digital.com --out import_series.json --query "{'stage':ObjectId('57c6cbb9ea71da9c2513d5b2'),'step':ObjectId('57c6cbb9ea71da9c2513d5b3')}"
# 57cd5367deeb0e074430c8f7
# 57cd5367deeb0e074430c8f8
import_refusalPressure = 10.
base_stageId = "57c6cbb9ea71da9c2513d5b2"
base_stepId = "57c6cbb9ea71da9c2513d5b3"


def main(argv):
    syntax = os.path.basename(__file__) + " -m <mongo host> -p <mongo port> -d <main database> -t <time in minutes> -s <stageId:stepId> -n <number of steps>"
    mongo_host = "localhost"
    mongo_port = 27017
    mongo_database = "tgrout-development"
    time_minutes = 10
    stage_step = None
    numsteps = 1
    try:
        opts = getopt.getopt(argv, "hm:p:d:t:s:n:", ["mongohost=","port=","database=","time=","stage=","numsteps="])[0]
    except getopt.GetoptError:
        print syntax
        sys.exit(1)
    if len(opts) < 1:
        print syntax
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print syntax
            sys.exit()
        elif opt in ("-p", "--port"):
            mongo_port = int(arg)
        elif opt in ("-m", "--mongohost"):
            mongo_host = arg
        elif opt in ("-n", "--numsteps"):
            numsteps = int(arg)
            if numsteps > 4 or numsteps < 1:
                print syntax
                print "-n deve essere un numero intero compreso tr 1 e 4, hai fornito {}".format(numsteps)
                sys.exit()
        elif opt in ("-d", "--database"):
            mongo_database = arg
        elif opt in ("-t", "--time"):
            time_minutes = int(arg)
        elif opt in ("-s", "--stage"):
            stage_step = arg
    if stage_step:
        s_splitted = stage_step.split(":")
        if len(s_splitted) > 1:
            stageId = s_splitted[0]
            stepId = s_splitted[1]
            log.info("Trying connecting to {0}:{1}, database {2}".format(mongo_host,mongo_port,mongo_database))
            mClient = MongoClient(mongo_host, mongo_port)
            db = mClient[mongo_database]
            main_stage = db.stages.find_one({"_id":ObjectId(stageId)})
            if main_stage:
                log.info("Found stage with Id {0}! stageStatus = {1}, bottomLength={2}, topLength={3} and R={4}".format(stageId,main_stage["stageStatus"],main_stage["bottomLength"],main_stage["topLength"],main_stage["refusalPressure"]))
                if main_stage["stageStatus"] == "OPEN" or main_stage["stageStatus"] == "CLOSED":
                    refusalPressure = main_stage["refusalPressure"]
                    main_steps = [step  for step in main_stage["steps"] if step["_id"]== ObjectId(stepId)]
                    scaleR = refusalPressure / import_refusalPressure
                    timestampMinute = datetime.datetime.utcnow()
                    main_stage["startDateTime"] = timestampMinute
                    rCheckDuration = main_stage["rCheckDuration"]
                    for istep, step in enumerate(main_steps):
                        log.info("Found step with Id {0}!".format(stepId))
                        timestampMinute = datetime.datetime.utcnow()
                        new_new_ts_items = []
                        maxGaugePressure = 0
                        maxPressure = 0
                        flowRateAtMaxGaugePressure = 0
                        flowRateAtMaxPressure = 0
                        groutTake = 0
                        lastP = 0
                        lastPeff = 0
                        cStepId = None
                        lastQ = 0
                        ti = 0
                        # print "time_minutes {0}".format(time_minutes)
                        time_step = time_minutes/numsteps
                        timemin = time_step*numsteps
                        main_stage_steps = []
                        for step in range(numsteps):
                            print "step {0}".format(step+1)
                            # a partire dal secondo step in poi
                            if step > 0:
                                cStepId = ObjectId()
                                if step == 1:
                                    mixType = "B"
                                if step == 2:
                                    mixType = "C"
                                if step == 3:
                                    mixType = "D"
                                bFound = False
                                mrets = db.mixtypes.find({"type":mixType})
                                for mt in list(mrets):
                                    hrets = db.headlossfactors.find({"mixType":mt["_id"]})
                                    for ht in list(hrets):
                                        headLossFactor = ht
                                        bFound = True
                                if not bFound:
                                    log.error("Non è stato trovato un HEAD Loss factor per MixType {}".format(mixType))
                                    print "ERRORE: Non è stato trovato un HEAD Loss factor per MixType {}".format(mixType)
                                    print "\t=> Bisogna censire sia un elemento in Mix Types che il successivo in Head Loss Factors"
                                    sys.exit(-1)
                                main_stage_steps.append({"_id":cStepId,"stepType" : "GroutStep","sgsConfirm" : True,
                                                            "waterPresence" : main_stage["steps"][istep]["waterPresence"],
                                                            "initPumpFlowRate":main_stage["steps"][istep]["initPumpFlowRate"],
                                                            "initPumpPressure":main_stage["steps"][istep]["initPumpPressure"],
                                                            "mixTypeType":mixType,
                                                            "bgu":main_stage["steps"][istep]["bgu"],
                                                            "gaugeHeight":main_stage["steps"][istep]["gaugeHeight"],
                                                            "headLossFactor":headLossFactor["_id"],
                                                            "pipeLineLength":main_stage["steps"][istep]["pipeLineLength"],
                                                            "waterDistance":main_stage["steps"][istep]["waterDistance"]
                                                            # , "waterPressure":main_stage["steps"][istep]["waterPressure"],
                                                            # "srsUser":main_stage["steps"][istep]["srsUser"],
                                                            # "stepStatusMessage":main_stage["steps"][istep]["stepStatusMessage"]
                                                             })
                            else:
                                cStepId = main_stage["steps"][istep]["_id"]
                                main_stage_steps.append(main_stage["steps"][istep])
                            #
                            for tm in range(time_step):
                                new_ts_item = {'stage':ObjectId(stageId),'step':cStepId,'timestampMinute':timestampMinute, "__v" : 0, "values":{}}
                                timestampMinute = timestampMinute + datetime.timedelta(0,60)
                                # print "## tm {0}".format(tm)
                                for ts in range(60):
                                    ti += 1 # step*tm*60 + (ts+1)
                                    # print "\tti {0}".format(ti)
                                    tx = (float(ti)*100.)/(float(timemin)*60.)
                                    # print "\ttx {0}".format(tx)
                                    pV = pOut(tx)*scaleR
                                    qV = qOut(tx)
                                    # print "\t\tqV {0} - pV {1}".format(qV,pV)
                                    newPressureGaugeManifold = pV*1.2
                                    newPressureEffective = pV
                                    groutTake = groutTake + qV/60.
                                    new_ts_item["values"][str(ts)] = { "_id": ObjectId(),
                                                                        "pressureGaugeManifold" : newPressureGaugeManifold,
                                                                        "flowRateGaugeManifold" : qV,
                                                                        "pressureEffective" : newPressureEffective,
                                                                        "injectedGroutTakeVolume" : groutTake,
                                                                        "elapsedTime" : ti*1000}
                                    lastP = newPressureGaugeManifold
                                    lastPeff = newPressureEffective
                                    lastQ = qV
                                    if maxGaugePressure <= newPressureGaugeManifold:
                                        maxGaugePressure = newPressureGaugeManifold
                                        flowRateAtMaxGaugePressure =  qV
                                    if maxPressure <= newPressureEffective:
                                        maxPressure = newPressureEffective
                                        flowRateAtMaxPressure =  qV
                                new_new_ts_items.append(new_ts_item)
                            # solo per ultimo step
                            if step == numsteps-1:
                                # ultimi 2 minuti
                                print "# ultimi 2 minuti; lastP={} +-2".format(lastPeff)
                                for tm in range(rCheckDuration):
                                    new_ts_item = {'stage':ObjectId(stageId),'step':cStepId,'timestampMinute':timestampMinute, "__v" : 0, "values":{}}
                                    timestampMinute = timestampMinute + datetime.timedelta(0,60)
                                    for ts in range(60):
                                        ti += 1
                                        # print "\tti {0}".format(ti)
                                        pV = lastPeff + delta_rand.rvs()
                                        qV = lastQ
                                        # print "\t\tqV {0} - pV {1}".format(qV,pV)
                                        newPressureGaugeManifold = pV*1.2
                                        newPressureEffective = pV
                                        groutTake = groutTake + qV/60.
                                        new_ts_item["values"][str(ts)] = { "_id": ObjectId(),
                                                                            "pressureGaugeManifold" : newPressureGaugeManifold,
                                                                            "flowRateGaugeManifold" : qV,
                                                                            "pressureEffective" : newPressureEffective,
                                                                            "injectedGroutTakeVolume" : groutTake,
                                                                            "elapsedTime" : ti*1000}
                                        if maxGaugePressure <= newPressureGaugeManifold:
                                            maxGaugePressure = newPressureGaugeManifold
                                            flowRateAtMaxGaugePressure =  qV
                                        if maxPressure <= newPressureEffective:
                                            maxPressure = newPressureEffective
                                            flowRateAtMaxPressure =  qV
                                    new_new_ts_items.append(new_ts_item)
                                main_stage_steps[step]["stepStatus"] = "COMPLETED"
                            else:
                                main_stage_steps[step]["stepStatus"] = "STOPPED_FOR_CHANGE_MIX"
                            main_stage_steps[step]["maxGaugePressure"] = maxGaugePressure
                            main_stage_steps[step]["flowRateAtMaxGaugePressure"] = flowRateAtMaxGaugePressure
                            main_stage_steps[step]["maxPressure"] = maxPressure
                            main_stage_steps[step]["flowRateAtMaxPressure"] = flowRateAtMaxPressure
                            main_stage_steps[step]["groutTake"] = groutTake
                        db.timeseries.delete_many({'stage':ObjectId(stageId),'step':ObjectId(stepId)})
                        result = db.timeseries.insert_many(new_new_ts_items)
                        log.info("Inserted {0} items for stage {1}".format(len(result.inserted_ids),stageId))
                        # print "Inserted {0} items for stage {1}".format(len(result.inserted_ids),stageId)
                    main_stage["stageStatus"] = "CLOSED"
                    main_stage["stopDateTime"] = timestampMinute
                    main_stage["steps"] = main_stage_steps
                    db.stages.update({"_id":main_stage["_id"]},main_stage)
                else:
                    log.error("Stage {0} with wrong status ({1})!".format(stageId,  main_stage["stageStatus"]))
                    print "ERROR: Stage {0} with wrong status ({1})!".format(stageId,  main_stage["stageStatus"])
            else:
                log.error("Stage with Id {0} not found!".format(stageId))
                print "ERROR: Stage with Id {0} not found!".format(stageId)
        else:
            log.error("Wrong stage and step format: {0}".format(stage_step))
            print "ERROR: Wrong stage and step format: {0}".format(stage_step)
    else:
        log.error("Stage and step not available")
        print "ERROR: Stage and step not available"



if __name__ == "__main__":
    main(sys.argv[1:])
