import os
from pathlib import Path

class Files:

    def getSettingsFilenameWithPath() -> str:
        settingsFilename = "settings.json"
        return os.getcwd()+"/"+settingsFilename

    def getDatabaseFilenameWithPath() -> str:
        filename = "database.json"
        return os.getcwd()+"/"+filename

    def getLoggingFilenameWithPath() -> str:
        filename = "logging.log"
        return os.getcwd()+"/"+filename

    def settingsExists() -> bool:
        return Path(Files.getSettingsFilenameWithPath()).is_file()

    def databaseExists() -> bool:
        return Path(Files.getDatabaseFilenameWithPath()).is_file()