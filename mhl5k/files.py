# V0.10

import os
import sys
from pathlib import Path

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