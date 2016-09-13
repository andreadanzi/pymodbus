#!/bin/bash
# MongoDB
export MONGO_HOST="localhost"
export MONGO_PORT=27017
# Destination - insert yout database, newly created stage ID and step ID
export MAIN_DATABASE="tgrout-dev"

export STEP_NO=2
export MINUTES=20
# Borehole: 015G-U-L-06.75
export STAGE_ID="57d2bb740f46b58b20371420"
export STEP_ID="57d2bb740f46b58b20371421"
python pytgrout_steps.py -m $MONGO_HOST -p $MONGO_PORT -d $MAIN_DATABASE -t $MINUTES -s $STAGE_ID:$STEP_ID -n $STEP_NO
echo "### pytgrout_steps terminated"

export STEP_NO=1
export MINUTES=30
# Borehole: 015G-U-L-06.75
export STAGE_ID="57d2bbc60f46b58b20371434"
export STEP_ID="57d2bbc60f46b58b20371435"
python pytgrout_steps.py -m $MONGO_HOST -p $MONGO_PORT -d $MAIN_DATABASE -t $MINUTES -s $STAGE_ID:$STEP_ID -n $STEP_NO
echo "### pytgrout_steps terminated"


export STEP_NO=3
export MINUTES=25
# Borehole: 013G-D-E-00.00
export STAGE_ID="57c6d367ea71da9c2513d624"
export STEP_ID="57c6d367ea71da9c2513d625"
python pytgrout_steps.py -m $MONGO_HOST -p $MONGO_PORT -d $MAIN_DATABASE -t $MINUTES -s $STAGE_ID:$STEP_ID -n $STEP_NO
echo "### pytgrout_steps terminated"


export STEP_NO=3
export MINUTES=25
# Borehole: 014G-D-Q-03.00
export STAGE_ID="57d2bbdc0f46b58b2037143a"
export STEP_ID="57d2bbdc0f46b58b2037143b"
python pytgrout_steps.py -m $MONGO_HOST -p $MONGO_PORT -d $MAIN_DATABASE -t $MINUTES -s $STAGE_ID:$STEP_ID -n $STEP_NO
echo "### pytgrout_steps terminated"
