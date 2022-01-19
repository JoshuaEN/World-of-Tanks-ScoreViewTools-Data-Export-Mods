from items import vehicles, _xml
from gui.Scaleform.daapi.view.lobby.trainings.training_room import TrainingRoom;
from helpers.statistics import StatisticsCollector;
from game import init
import ScoreViewTools

def exportAll():
        ScoreViewTools.Export.init()
        ScoreViewTools.Export.cleanup()
        ScoreViewTools.Export.gameInfo()
        ScoreViewTools.Export.vehicles()
        #ScoreViewTools.Export.gameData()
        #ScoreViewTools.Export.equipment()
        #ScoreViewTools.Export.consumables()
        ScoreViewTools.Export.maps()
        #ScoreViewTools.Export.serverSettings()

old_noteHangarLoadingState = StatisticsCollector.noteHangarLoadingState

def new_noteHangarLoadingState(self, state, initialState=False, showSummaryNow=False):
        old_noteHangarLoadingState(self, state, initialState, showSummaryNow)

StatisticsCollector.noteHangarLoadingState = new_noteHangarLoadingState

print dir(TrainingRoom)

old_onSettingUpdated = TrainingRoom.onSettingUpdated
old_onRostersChanged = TrainingRoom.onRostersChanged
old_onPlayerStateChanged = TrainingRoom.onPlayerStateChanged
old__TrainingRoomBase__showSettings = TrainingRoom._TrainingRoomBase__showSettings
old_showRosters = TrainingRoom._showRosters

first = True

def new_onSettingUpdated(self, functional, settingName, settingValue):
        ScoreViewTools.Export.trainingRoomSettings(functional)
        old_onSettingUpdated(self, functional, settingName, settingValue)

def new_onRostersChanged(self, functional, rosters, full):
        ScoreViewTools.Export.trainingRoomRoster(functional)
        old_onRostersChanged(self, functional, rosters, full)

def new_onPlayerStateChanged(self, functional, roster, accountInfo):
        ScoreViewTools.Export.trainingRoomRoster(functional)
        old_onPlayerStateChanged(self, functional, roster, accountInfo)

def new__TrainingRoomBase__showSettings(self, functional):
        ScoreViewTools.Export.trainingRoomSettings(functional)
        old__TrainingRoomBase__showSettings(self, functional)

def new_showRosters(self, functional, rosters):
        global first
        if first:
                first = False
                exportAll()
        ScoreViewTools.Export.trainingRoomRoster(functional)
        old_showRosters(self, functional, rosters)

TrainingRoom.onSettingUpdated = new_onSettingUpdated
TrainingRoom.onRostersChanged = new_onRostersChanged
TrainingRoom.onPlayerStateChanged = new_onPlayerStateChanged
TrainingRoom._TrainingRoomBase__showSettings = new__TrainingRoomBase__showSettings
TrainingRoom._showRosters = new_showRosters
