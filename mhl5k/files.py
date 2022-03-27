# Files by mhl5k
# MIT license

import os
import sys
from pathlib import Path

__version__ = "0.11"

class Files:

    def getScriptPath() -> str:
        return os.path.dirname(os.path.realpath(sys.argv[0]))

    def getSettingsFilenameWithPath() -> str:
        filename = "settings.json"
        return Files.getScriptPath()+"/"+filename

    def getDatabaseFilenameWithPath() -> str:
        filename = "database.json"
        return Files.getScriptPath()+"/"+filename

    def getLoggingFilenameWithPath() -> str:
        filename = "logging.log"
        return Files.getScriptPath()+"/"+filename

    def settingsExists() -> bool:
        return Path(Files.getSettingsFilenameWithPath()).is_file()

    def databaseExists() -> bool:
        return Path(Files.getDatabaseFilenameWithPath()).is_file()

# Test function for module  
def _test():
    # tests
    filepath=Files.getScriptPath()
    assert filepath != ""
    
    # end
    print(__file__+" "+__version__+": All module tests did run fine.")

# when file ist started directlx
if __name__ == '__main__':
    _test()
