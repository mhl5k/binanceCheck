# reads settings json file
# if not available it creates a default file
# License: MIT
# Author: mhl5k

import json
from .files import Files

__version__ = "0.8"


class Settings:

    # DO NOT CHANGE SETTINGS HERE!
    defaults = {
        "version": "1",
        "apiKey": "insert-your-api-key",
        "apiSecret": "insert-your-secret-key"
    }

    def initializeNewSettingsJSONFile(self):
        print("Creating default config file.")
        print("Please edit "+Files.getSettingsFilenameWithPath()+" then rerun.")
        with open(Files.getSettingsFilenameWithPath(), "w") as outfile:
            json.dump(self.defaults, outfile, indent=4, sort_keys=False)
            outfile.close()


    def load(self):
        print("Loading settings")
        with open(Files.getSettingsFilenameWithPath(), "r") as infile:
            self.current=json.load(infile)
            infile.close()


    def __init__(self):
        self.current:dict = {}
        if not Files.settingsExists():
            self.initializeNewSettingsJSONFile()
            exit(1)
        else:
            self.load()


# Test function for module  
def _test():
    # tests

    # end
    print(__file__+" "+__version__+": All module tests did run fine.")

# when file ist started directlx
if __name__ == '__main__':
    _test()
