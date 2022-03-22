# shows all Binance trading pairs with progress over 5min, 1h, 24h, ... 
# 
# License: MIT
# Author: mhl5k

import sys
import logging
from binance.lib.utils import config_logging
from mhl5k.binance.dataset import BinanceDataSet
from settings import Settings
from mhl5k.files import Files

VERSION = "0.8"

# Functions and constants
# ------------------------

APIURL="https://api.binance.com"

def printAppName():
    print("binanceTradeTimeProgress %s by mhl5k, MIT license" % (VERSION))


# Main start up
# -------------
printAppName()

# limit to command line parameter
commandlineLimit=""
if len(sys.argv) == 2:
    commandlineLimit=sys.argv[1]

# load settings
settings=Settings()

config_logging(logging, logging.DEBUG, Files.getLoggingFilenameWithPath())

try:
    # Binance Account Data Set
    binanceAccountDataSet=BinanceDataSet(settings)
    binanceAccountDataSet.showTradeTimeProgress(limit=commandlineLimit)

except Exception as E:
    print("Error: %s" % E)
    exit(1)

# exit
exit(0)
