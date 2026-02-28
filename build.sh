#!/usr/bin/env bash

set -o errexit

# install tesseract
apt-get update -y
apt-get install -y tesseract-ocr

#install python packages
pip install -r requirements.txt