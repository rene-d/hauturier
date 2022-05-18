#!/usr/bin/env bash

python3 -m venv venv
source venv/bin/activate

python -m pip install --upgrade pip
python -m pip install --pre toga
python -m pip install briefcase

briefcase build android
# python -mhttp.server --directory android/gradle/NMEA\ Logger/app/build/outputs/apk/debug/
