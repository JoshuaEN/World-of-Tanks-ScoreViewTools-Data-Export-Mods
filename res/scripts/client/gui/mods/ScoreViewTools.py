import json
import time
import copy
import os
import glob
import inspect
import traceback
import ArenaType
import BigWorld
import ArenaType
import Math
from Math import Vector3
from AvatarInputHandler import gun_marker_ctrl
from items.tankmen import getSkillsConfig
from items.components import skills_constants, shared_components
from gui.Scaleform.daapi.view.lobby.techtree.techtree_dp import g_techTreeDP
from helpers import i18n, getFullClientVersion, getClientVersion, getClientLanguage, getLanguageCode
from gui.Scaleform.daapi.view.lobby.trainings import formatters
from gui.Scaleform.locale.MENU import MENU
from gui.shared.gui_items.Vehicle import Vehicle
from gui.shared.gui_items import KPI
from items import vehicles, artefacts
from items.stun import g_cfg as stunConfig
import nations
from constants import VEHICLE_CLASSES, VEHICLE_MODE
from gui.shared.items_parameters.params_cache import g_paramsCache
from helpers import dependency
from skeletons.gui.lobby_context import ILobbyContext
from skeletons.gui.shared.gui_items import IGuiItemsFactory


from gui.shared.gui_items import GUI_ITEM_TYPE

g_svt_shell_costs = {}

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set) or isinstance(obj, frozenset) or isinstance(obj, tuple):
            return list(obj)

        elif isinstance(obj, Vector3):
            return [obj.x, obj.y, obj.z]

        elif isinstance(obj, artefacts.VehicleFilter):
            return {
                "include": list(obj._include),
                "exclude": list(obj._exclude)
            }

        elif isinstance(obj, artefacts._ArtefactFilter):
            return {
                "installed": list(obj._ArtefactFilter__installed),
                "active": list(obj._ArtefactFilter__active)
            }                    

        elif isinstance(obj, artefacts._OptionalDeviceFilter):
            return {
                "requiredTags": list(obj._OptionalDeviceFilter__requiredTags),
                "incompatibleTags": list(obj._OptionalDeviceFilter__incompatibleTags)
            }

        elif isinstance(obj, artefacts.MineParams):
            return {
                "triggerRadius": obj.triggerRadius,
                "triggerHeight": obj.triggerHeight,
                "triggerDepth": obj.triggerDepth,
                "influenceType": obj.influenceType,
                "lifetime": obj.lifetime,
                "damage": obj.damage,
                "shell": obj.shell,
            }

        elif isinstance(obj, shared_components.I18nComponent):
            return {
                "userString": obj.userString,
                "shortString": obj.shortString,
                "description": obj.description
            }

        elif isinstance(obj, KPI):
            return {
                "name": obj.name,
                "value": obj.value,
                "type": obj.type
            }

        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError as e:
            if (e.message.endswith("is not JSON serializable")):
                return "Conversion failed: {0}".format(e)
            raise

class Export:

    __rosterExportInternalCounter = 0
    __settingExportInternalCounter = 0

    @staticmethod
    def __checkVersion():
        return True

    @staticmethod
    def __makeDir(path):
        try: 
            os.makedirs(path)
        except OSError:
            if not os.path.isdir(path):
                raise

    @staticmethod
    def init():
        try:
            Export.__makeDir('res_mods/ScoreViewTools/TrainingRoom')
            Export.__makeDir('res_mods/ScoreViewTools/Export')
        except Exception as e:
            print "SVT - Training Room Export - Error during Initialization"
            traceback.print_exc()

    @staticmethod
    def cleanup():
        try:
            files = glob.glob('*res_mods/ScoreViewTools/TrainingRoom/*.json')
            for f in files:
                os.remove(f)
        except Exception as e:
            print "SVT - Training Room Export - Error during Clean up"
            traceback.print_exc()

    @staticmethod
    def recordShellCost(nationID, id, cost):
        if(g_svt_shell_costs.has_key(nationID) is False):
            g_svt_shell_costs[nationID] = {}
        g_svt_shell_costs[nationID][id] = cost
    
    @staticmethod
    def _vehicleForExport(vehicle):
        return {
            "tag": vehicle.name,
            "short_name": vehicle.shortUserName,
            "name": vehicle.userName,
            "level": vehicle.level,
            "type_tag": vehicle.type,
            "type_name": i18n.makeString("#menu:header/vehicleType/" + str(vehicle.type)),
            "id": vehicle.intCD,
            "nation_id": vehicle.nationID,
            "nation_tag": nations.NAMES[vehicle.nationID],
            "nation_name": i18n.makeString(MENU.nations(nations.NAMES[vehicle.nationID]))
        }

    @staticmethod
    def _getResearchCost(intCD, vehIntCD):
        unlockPrices = g_techTreeDP.getUnlockPrices(intCD)
        if unlockPrices:
            if vehIntCD in unlockPrices:
                return unlockPrices[vehIntCD]

    @staticmethod
    def _installableItemForExport(item, vehIntCD):
        return {
            # "typeID": item.typeID,
            #"id": item.id,
            "name": item.name,
            "compactDescr": item.compactDescr,
            "tags": list(item.tags),
            "i18n": {
                "userString": item.i18n.userString,
                "shortString": item.i18n.shortString,
                "description": item.i18n.description
            },
            "itemTypeName": item.itemTypeName,
            "level": item.level,
            #"status": item.status,
            "weight": item.weight,
            "unlocks": item.unlocks,
            "maxHealth": item.maxHealth,
            "repairCost": item.repairCost,
            "maxRegenHealth": item.maxRegenHealth,
            "maxRepairCost": item.maxRepairCost,
            "researchCost": Export._getResearchCost(item.compactDescr, vehIntCD)
        }


    @staticmethod
    def _check_for_json(key, value):
        import collections

        #print "checking key " + str(key) + " with value of " + str(value)
        if isinstance(value, dict):
            for k, v in value.iteritems():
                Export._check_for_json(str(key) + '.' + str(k), v)
            return
        if not isinstance(value, str) and isinstance(value, collections.Iterable):
            for v in value:
                Export._check_for_json(key + '[]', v)

            try:
                json.dumps(value, cls=CustomEncoder)
            except Exception as e:
                print str(key) + " of type " + value.__class__.__name__ + " failed to be converted to JSON"
                traceback.print_exc()

            return
        
        try:
            json.dumps(value, cls=CustomEncoder)
        except Exception as e:
            print str(key) + " of type " + value.__class__.__name__ + " failed to be converted to JSON"
            traceback.print_exc()

    @staticmethod
    def _artefactForExport(equipment):
        obj = {
            "__class__": equipment.__class__.__name__,
            "__mro__": map(lambda c: c.__name__, inspect.getmro(equipment.__class__))
        }

        for name in dir(equipment):

            if callable(name) == False:

                value = getattr(equipment, name, None)

                if  name == "__module__" or name == "__doc__" or name == "__slots__":
                    continue

                elif name in ('status', 'id', 'typeID', 'tooltipInformation'):
                    continue

                elif name == "icon":
                    obj[name] = value[0]

                # elif isinstance(value, artefacts._VehicleFilter):
                #     obj[name] = {
                #         "include": list(value._VehicleFilter__include),
                #         "exclude": list(value._VehicleFilter__exclude)
                #     }

                # elif isinstance(value, artefacts._ArtefactFilter):
                #     obj[name] = {
                #         "installed": list(value._ArtefactFilter__installed),
                #         "active": list(value._ArtefactFilter__active)
                #     }                    

                # elif isinstance(value, artefacts._OptionalDeviceFilter):
                #     obj[name] = {
                #         "requiredTags": list(value._OptionalDeviceFilter__requiredTags),
                #         "incompatibleTags": list(value._OptionalDeviceFilter__incompatibleTags)
                #     }

                # elif isinstance(value, shared_components.I18nComponent):
                #     obj[name] = {
                #         "userString": value.userString,
                #         "shortString": value.shortString,
                #         "description": value.description
                #     }
                else:
                    if callable(value) == False and value != None:
                        Export._check_for_json(name, value)
                        obj[name] = value

        return obj

    @staticmethod
    def _consumablesForExport():
        equipmentForExport = []
        for eKey, equipment in vehicles.g_cache.equipments().iteritems():
            equipmentForExport.append(Export._artefactForExport(equipment))
            continue
            # icon_str = equipment.icon[0]
            # equipmentForExport.append(
            #     {
            #         "name": equipment.name,
            #         "display_name": equipment.userString,
            #         "icon_key": icon_str,
            #         "compact_descr": equipment.compactDescr
            #     }
            # )

        return equipmentForExport

    @staticmethod
    def _exportVehicle(v, vehicle, type):
        if type.hasSiegeMode:
            v['_siegeDataMarker'] = True
        v['mode'] = type.mode
        v['hasSiegeMode'] = type.hasSiegeMode
        v['isMultiTurret'] = len(type.turrets) > 1
        v['speedLimits'] = type.speedLimits
        v['repairCost'] = type.repairCost
        v['crewXpFactor'] = type.crewXpFactor
        v['premiumVehicleXPFactor'] = type.premiumVehicleXPFactor
        # v['xpFactor'] = type.xpFactor
        # v['creditsFactor'] = type.creditsFactor
        # v['freeXpFactor'] = type.freeXpFactor
        #v['healthBurnPerSec'] = type.healthBurnPerSec
        #v['healthBurnPerSecLossFraction'] = type.healthBurnPerSecLossFraction
        v['invisibility'] = type.invisibility
        v['invisibilityDeltas'] = type.invisibilityDeltas
        v['crewRoles'] = type.crewRoles
        #v['extras'] = type.extras


        #v['devices'] = type.devices
        #v['tankmen'] = type.tankmen
        v['isRotationStill'] = type.isRotationStill
        v['siegeModeParams'] = type.siegeModeParams
        v['hullAimingParams'] = type.hullAimingParams
        v['unlocks'] = type.unlocks
        v['unlocksDescrs'] = type.unlocksDescrs
        v['autounlockedItems'] = type.autounlockedItems

                              
                              # vehicle.intCD
        withRareCamouflage = type.compactDescr in g_paramsCache.getVehiclesWithoutCamouflage()

        v['canHaveCamouflage'] = not withRareCamouflage
        v['hasCustomDefaultCamouflage'] = type.hasCustomDefaultCamouflage

        v['clientAdjustmentFactors'] = type.clientAdjustmentFactors
        v['xphysics'] = type.xphysics

        v['hulls'] = []
        v['chassis'] = []
        v['engines'] = []
        v['fuelTanks'] = []
        v['radios'] = []

        for hull in type.hulls:
            i = {}
            if type.hasSiegeMode:
                i['_siegeDataMarker'] = True
            i['weight'] = hull.weight
            i['primaryArmor'] = hull.primaryArmor
            i['maxHealth'] = hull.maxHealth
            i['variantName'] = hull.variantName
            i['fakeTurrets'] = hull.fakeTurrets
            i['ammoBayHealth'] = { 
                'maxHealth': hull.ammoBayHealth.maxHealth,
                'repairCost': hull.ammoBayHealth.repairCost,
                'maxRegenHealth': hull.ammoBayHealth.maxRegenHealth
            }
            i['variantMatch'] = hull.variantMatch
            i['armorHomogenization'] = hull.armorHomogenization
            i['turretPositions'] = hull.turretPositions
            i['turrets'] = []

            turretIndex = 0
            for turretList in type.turrets:

                for turret in turretList:
                    t = Export._installableItemForExport(turret, type.compactDescr)
                    if type.hasSiegeMode:
                        t['_siegeDataMarker'] = True
                    t['mountIndex'] = turretIndex
                    t['rotationSpeed'] = turret.rotationSpeed
                    t['turretRotatorHealth'] = { 
                        'maxHealth': turret.turretRotatorHealth.maxHealth,
                        'repairCost': turret.turretRotatorHealth.repairCost,
                        'maxRegenHealth': turret.turretRotatorHealth.maxRegenHealth
                    }
                    t['surveyingDeviceHealth'] = { 
                        'maxHealth': turret.surveyingDeviceHealth.maxHealth,
                        'repairCost': turret.surveyingDeviceHealth.repairCost,
                        'maxRegenHealth': turret.surveyingDeviceHealth.maxRegenHealth
                    }
                    t['invisibilityFactor'] = turret.invisibilityFactor
                    t['circularVisionRadius'] = turret.circularVisionRadius
                    t['primaryArmor'] = turret.primaryArmor
                    t['guns'] = []

                    for gun in turret.guns:
                        g = Export._installableItemForExport(gun, type.compactDescr)
                        if type.hasSiegeMode:
                            g['_siegeDataMarker'] = True
                        g['rotationSpeed'] = gun.rotationSpeed
                        g['reloadTime'] = gun.reloadTime
                        g['aimingTime'] = gun.aimingTime
                        g['maxAmmo'] = gun.maxAmmo
                        g['invisibilityFactorAtShot'] = gun.invisibilityFactorAtShot
                        g['turretYawLimits'] = gun.turretYawLimits
                        g['pitchLimits'] = gun.pitchLimits
                        g['staticTurretYaw'] = gun.staticTurretYaw
                        g['staticPitch'] = gun.staticPitch
                        g['shotDispersionAngle'] = gun.shotDispersionAngle
                        g['shotDispersionFactors'] = gun.shotDispersionFactors
                        g['burst'] = gun.burst
                        g['clip'] = gun.clip
                        g['clipSize'] = gun.clip[0] / (gun.burst[0] if gun.clip[0] > 1 else 1)
                        g['innerClipReloadTime'] = gun.clip[1]
                        g['autoreload'] = gun.autoreload
                        g['burstSize'] = gun.burst[0]
                        g['burstFireTime'] = gun.burst[1]
                        g['combinedPitchLimits'] = gun.combinedPitchLimits
                        g['shots'] = []

                        for shot in gun.shots:
                            s = {
                                'typeID': shot.shell.typeID,
                                'id': shot.shell.id,
                                'name': shot.shell.name,
                                'compactDescr': shot.shell.compactDescr,
                                'tags': list(shot.shell.tags),
                                'i18n': {
                                    "userString": shot.shell.i18n.userString,
                                    "shortString": shot.shell.i18n.shortString,
                                    "description": shot.shell.i18n.description
                                }
                            }
                            if type.hasSiegeMode:
                                s['_siegeDataMarker'] = True
                            s['shell'] = {
                                'caliber': shot.shell.caliber,
                                'isTracer': shot.shell.isTracer,
                                'damage': shot.shell.damage,
                                "avgDamage": shot.shell.damage[0],
                                'damageRandomization': shot.shell.damageRandomization,
                                'piercingPowerRandomization': shot.shell.piercingPowerRandomization,
                                'stun': None,
                                'type': {
                                    'name': shot.shell.type.name,
                                    'normalizationAngle': getattr(shot.shell.type, 'normalizationAngle', None),
                                    'ricochetAngleCos': getattr(shot.shell.type, 'ricochetAngleCos', None),
                                    'piercingPowerLossFactorByDistance': getattr(shot.shell.type, 'piercingPowerLossFactorByDistance', None),
                                    'ricochetAngleCos': getattr(shot.shell.type, 'ricochetAngleCos', None),
                                    'explosionRadius': getattr(shot.shell.type, 'explosionRadius', None),
                                    'explosionDamageFactor': getattr(shot.shell.type, 'explosionDamageFactor', None),
                                    'explosionDamageAbsorptionFactor': getattr(shot.shell.type, 'explosionDamageAbsorptionFactor', None),
                                    'explosionEdgeDamageFactor': getattr(shot.shell.type, 'explosionEdgeDamageFactor', None),
                                    'stunRadius': getattr(shot.shell.type, 'stunRadius', None),
                                    'stunDuration': getattr(shot.shell.type, 'stunDuration', None),
                                    'stunFactor': getattr(shot.shell.type, 'stunFactor', None),
                                    'guaranteedStunDuration': getattr(shot.shell.type, 'guaranteedStunDuration', None),
                                    'damageDurationCoeff': getattr(shot.shell.type, 'damageDurationCoeff', None),
                                    'guaranteedStunEffect': getattr(shot.shell.type, 'guaranteedStunEffect', None),
                                    'damageEffectCoeff': getattr(shot.shell.type, 'damageEffectCoeff', None)
                                },
                                'isGold': shot.shell.isGold,
                                'price': g_svt_shell_costs.get(vehicle.nationID, {}).get(shot.shell.id[1], None)
                            }
                            if shot.shell.stun != None:
                                s['shell']['stun'] = {
                                    'stunRadius': shot.shell.stun.stunRadius,
                                    'stunDuration': shot.shell.stun.stunDuration,
                                    'stunFactor': shot.shell.stun.stunFactor,
                                    'guaranteedStunDuration': shot.shell.stun.guaranteedStunDuration,
                                    'damageDurationCoeff': shot.shell.stun.damageDurationCoeff,
                                    'guaranteedStunEffect': shot.shell.stun.guaranteedStunEffect,
                                    'damageEffectCoeff': shot.shell.stun.damageEffectCoeff
                                }

                            s['defaultPortion'] = shot.defaultPortion
                            s['piercingPower'] = [
                                shot.piercingPower[0], 
                                shot.piercingPower[1]
                            ],
                            s['avgPiercingPower'] = shot.piercingPower[0]
                            s['speed'] = shot.speed
                            s['gravity'] = shot.gravity
                            s['maxDistance'] = shot.maxDistance
                            s['maxHeight'] = shot.maxHeight
                            g['shots'].append(s)

                        clipCount = gun.clip[0] / (gun.burst[0] if gun.clip[0] > 1 else 1)
                        g['clipCount'] = clipCount
                        # Who knows where this is coming from

                        # Correct:
                        # reloadTime = gun.reloadTime * 0.9587727708533078


                        # g['clipSize'] = gun.clip[0] / (gun.burst[0] if gun.clip[0] > 1 else 1)
                        # g['innerClipReloadTime'] = gun.clip[1]

                        # Corret:
                        # g['trueReloadTime'] = reloadTime
                        # g['fullReloadTime'] = (reloadTime + (gun.burst[0] - 1) * gun.burst[1] * clipCount + (clipCount - 1) * gun.clip[1])
                        # g['shotsPerMinute'] = gun.burst[0] * clipCount * 60 / (reloadTime + (gun.burst[0] - 1) * gun.burst[1] * clipCount + (clipCount - 1) * gun.clip[1])
                        g['avgDamage'] = g['shots'][0]['shell']['avgDamage']
                        # g['avgBurstDamage'] = gun.clip[0] * g['avgDamage']
                        # g['avgDamagePerMinute'] = g['shotsPerMinute'] * g['avgDamage']

                        # g['trueAimingTime'] = g['aimingTime'] * 0.9587727708533078
                        # g['trueShotDispersionAngle'] = round(g['shotDispersionAngle'] * 0.9587727708533078 * 100, 2)

                        t['guns'].append(g)

                    while turretIndex >= len(i['turrets']):
                        i['turrets'].append([])

                    i['turrets'][turretIndex].append(t)
                
                turretIndex += 1

            v['hulls'].append(i)

        for chassis in type.chassis:
            i = Export._installableItemForExport(chassis, type.compactDescr)
            if type.hasSiegeMode:
                i['_siegeDataMarker'] = True
            i['specificFriction'] = chassis.specificFriction
            i['maxLoad'] = chassis.maxLoad
            i['rotationSpeed'] = chassis.rotationSpeed
            i['rotationSpeedLimit'] = chassis.rotationSpeedLimit
            i['rotationIsAroundCenter'] = chassis.rotationIsAroundCenter
            i['shotDispersionFactors'] = chassis.shotDispersionFactors
            i['brakeForce'] = chassis.brakeForce
            i['terrainResistance'] = chassis.terrainResistance
            i['bulkHealthFactor'] = chassis.bulkHealthFactor
            i['topRightCarryingPoint'] = [chassis.topRightCarryingPoint[0], chassis.topRightCarryingPoint[1]]
            i['minPlaneNormalY'] = chassis.minPlaneNormalY
            v['chassis'].append(i)

        for engine in type.engines:
            i = Export._installableItemForExport(engine, type.compactDescr)
            if type.hasSiegeMode:
                i['_siegeDataMarker'] = True
            i['power'] = engine.power
            i['fireStartingChance'] = engine.fireStartingChance
            i['minFireStartingDamage'] = engine.minFireStartingDamage
            i['rpm_min'] = engine.rpm_min
            i['rpm_max'] = engine.rpm_max
            v['engines'].append(i)

        for fuelTank in type.fuelTanks:
            i = Export._installableItemForExport(fuelTank, type.compactDescr)
            if type.hasSiegeMode:
                i['_siegeDataMarker'] = True
            v['fuelTanks'].append(i)

        for radio in type.radios:
            i = Export._installableItemForExport(radio, type.compactDescr)
            if type.hasSiegeMode:
                i['_siegeDataMarker'] = True
            i['distance'] = radio.distance
            v['radios'].append(i)

        v['tags'] = []

        for tag in type.tags:
            v['tags'].append(tag)


    @staticmethod
    def _clearSameParams(v, otherV, modeKey):
        #v = json.loads(json.dumps(v, cls=CustomEncoder))
        #otherV = json.loads(json.dumps(otherV, cls=CustomEncoder))
        otherV = copy.deepcopy(otherV)

        if v is None or otherV is None:
            return (v, otherV)

        if isinstance(v, dict):
            retainAllValues = '_siegeDataMarker' in v

            for key in v.keys():
                if key == '_siegeDataMarker' or key == 'modePropertyOverrides':
                    next

                valueFromV, valueFromOtherV = Export._clearSameParams(v.get(key, None), otherV.get(key, None), modeKey)

                if valueFromV is None:
                    v.pop(key, None)
                else:
                    v[key] = valueFromV

                if valueFromOtherV is None:
                    otherV.pop(key, None)
                elif not retainAllValues:
                    otherV[key] = valueFromOtherV

            if '_siegeDataMarker' in v:
                del v['_siegeDataMarker']

                if len(otherV) > 0:
                    if 'modePropertyOverrides' not in v:
                        v['modePropertyOverrides'] = {}


                    v['modePropertyOverrides'][modeKey] = otherV

                # Since we've set the values to the siegeModeDifferentPrams, we clear the source data so it isn't included elsewhere
                return (v, None)

            if(len(otherV) == 0):
                otherV = None

            return (v, otherV)

        if isinstance(v, tuple) or isinstance(v, set) or isinstance(v, frozenset):
            v = list(v)
            otherV = list(otherV)


        if isinstance(v, list):
            if(len(v) != len(otherV)):
                if len(v) == 0:
                    v = None
                if len(otherV) == 0:
                    otherV = None

                return v, otherV

            # Go backwards so we can delete array elements without any issues
            idx = len(v) - 1
            while idx > -1:
                valueFromV, valueFromOtherV = Export._clearSameParams(v[idx], otherV[idx], modeKey)


                if valueFromV is None:
                    del v[idx]
                else:
                    v[idx] = valueFromV

                if valueFromOtherV is None:
                    del otherV[idx]
                else:
                    otherV[idx] = valueFromOtherV
                
                idx -= 1

            if len(v) == 0:
                v = None
            if len(otherV) == 0:
                otherV = None

            return (v, otherV)

        if v == otherV:
            return v, None

        return v, otherV

    @staticmethod
    def serverSettings():
        try:

            lobbyContext = dependency.descriptor(ILobbyContext)
            #serverSettings = lobbyContext.getServerSettings()
            from Account import PlayerAccount
            import BigWorld
            serverSettings = BigWorld.player().serverSettings

            Export._check_for_json('root', serverSettings)

            path = 'res_mods/ScoreViewTools/Export/serverSettings.json'
            abs_path = os.path.abspath(path)

            with open(abs_path, 'w+') as outfile:
                outfile.write(json.dumps({
                    "serverSettings": serverSettings
                }, cls=CustomEncoder))

        except Exception as e:
            print "SVT - Data Export (Server Settings) - Error"
            traceback.print_exc()


    @staticmethod
    def _vehicleDetailsForExport():
        def check_for_json(key, value):
            return Export._check_for_json(key, value)

        try:
            g_techTreeDP.load()
            vehs = vehicles.g_list
            vehsForExport = []
            modulesForExport = {}

            for nationID in xrange(len(nations.NAMES)):
                # Force reload of nation data so our shell loader hook (in ScoreViewTools_Init.py) can grab additional data
                vehicles.g_cache._Cache__readNation(nationID)
                for key, value in vehs.getList(nationID).iteritems():
                    vehicle = Vehicle(typeCompDescr=value.compactDescr)

                    v = Export._vehicleForExport(vehicle)
                    type = vehicle.descriptor.type
                    #v['price'] = type.price

                    vSiege = {}
                    typeSiege = None

                    if type.hasSiegeMode:
                        typeSiege = getattr(vehicle.descriptor, '_CompositeVehicleDescriptor__siegeDescr', None)

                    Export._exportVehicle(v, vehicle, type)

                    if typeSiege is not None:
                        Export._exportVehicle(vSiege, vehicle, typeSiege.type)
                        Export._clearSameParams(v, vSiege, 'siege')

                    

                    

                    vehsForExport.append(v)

            check_for_json('root', vehsForExport)

            skill_factors = {}

            for role in skills_constants.SKILLS_BY_ROLES:
                skill_names = skills_constants.SKILLS_BY_ROLES[role]

                for skill_name in skill_names:
                    skill = getSkillsConfig().getSkill(skill_name)

                    # skill_info = {
                    #     "name": getattr(skill, "name", None),
                    #     "userString": getattr(skill, "userString", None),
                    #     "description": getattr(skill, "description", None),
                    #     "crewLevelIncrease": getattr(skill, "crewLevelIncrease", None),
                    #     "xpBonusFactorPerLevel": getattr(skill, "xpBonusFactorPerLevel", None),
                    #     "efficiency": getattr(skill, "efficiency", None),
                    #     "delay": getattr(skill, "delay", None),
                    #     "distanceFactorPerLevelWhenDeviceWorking": getattr(skill, "distanceFactorPerLevelWhenDeviceWorking", None),
                    #     "distanceFactorPerLevelWhenDeviceDestroyed": getattr(skill, "distanceFactorPerLevelWhenDeviceDestroyed", None),
                    #     "fireStartingChanceFactor": getattr(skill, "fireStartingChanceFactor", None),
                    #     "shotDispersionFactorPerLevel": getattr(skill, "shotDispersionFactorPerLevel", None),
                    #     "rotationSpeedFactorPerLevel": getattr(skill, "rotationSpeedFactorPerLevel", None),
                    #     "rammingBonusFactorPerLevel": getattr(skill, "rammingBonusFactorPerLevel", None),
                    #     "softGroundResistanceFactorPerLevel": getattr(skill, "softGroundResistanceFactorPerLevel", None),
                    #     "mediumGroundResistanceFactorPerLevel": getattr(skill, "mediumGroundResistanceFactorPerLevel", None),
                    #     "shotDispersionFactorPerLevel": getattr(skill, "shotDispersionFactorPerLevel", None),
                    #     "shotDispersionFactorPerLevel": getattr(skill, "shotDispersionFactorPerLevel", None),
                    #     "deviceChanceToHitBoost": getattr(skill, "deviceChanceToHitBoost", None),
                    #     "duration": getattr(skill, "duration", None),
                    #     "sectorHalfAngle": getattr(skill, "sectorHalfAngle", None),
                    #     "ammoBayHealthFactor": getattr(skill, "ammoBayHealthFactor", None),
                    #     "chance": getattr(skill, "chance", None),
                    #     "vehicleHealthFraction": getattr(skill, "vehicleHealthFraction", None),
                    #     "gunReloadTimeFactor": getattr(skill, "gunReloadTimeFactor", None),
                    #     "visionRadiusFactorPerLevel": getattr(skill, "visionRadiusFactorPerLevel", None),
                    #     "radioDistanceFactorPerLevel": getattr(skill, "radioDistanceFactorPerLevel", None),
                    #     "distanceFactorPerLevel": getattr(skill, "distanceFactorPerLevel", None)
                    # }

                    # for key in skill_info.keys():
                    #     if skill_info[key] == None:
                    #         skill_info.pop(key, None)

                    skill_factors[skill_name] = Export._artefactForExport(skill)
                    roles = []
                    for role_name in skills_constants.SKILLS_BY_ROLES:
                            skills = skills_constants.SKILLS_BY_ROLES[role_name]
                            if skill_name in skills:
                                roles.append(role_name)

                    skill_factors[skill_name]["roles"] = roles
                    skill_factors[skill_name]["isPerk"] = skill_name in skills_constants.PERKS
                    skill_factors[skill_name]["isCommon"] = skill_name in skills_constants.COMMON_SKILLS


            shell_data = {}

            for shell_name in gun_marker_ctrl._CrosshairShotResults._SHELL_EXTRA_DATA:
                shell_info = gun_marker_ctrl._CrosshairShotResults._SHELL_EXTRA_DATA[shell_name]

                shell_data[shell_name] = shell_info._asdict()


            return {
                "skills": [ v for v in skill_factors.values() ],
                "coefficients": g_paramsCache.getSimplifiedCoefficients(),
                "shell_data": shell_data,
                "vehicles": vehsForExport
            }
        except Exception as e:
            print "SVT - Data Export (Vehicles Full Details) - Error"
            traceback.print_exc()

    @staticmethod
    def _equipmentForExport():
        optionalForExport = []
        for eKey, equipment in vehicles.g_cache.optionalDevices().iteritems():

            optionalForExport.append(Export._artefactForExport(equipment))
            continue

            # tags = []

            # for tag in equipment.tags:
            #     tags.append(tag)

            # def get_private_attr(name, default = None):
            #     return getattr(equipment, "_" + equipment.__class__.__name__ + name, default)

            # optionalForExport.append(
            #     {
            #         "name": equipment.name,
            #         "extraName": equipment.extraName,
            #         "id": equipment.id,
            #         "compactDescr": equipment.compactDescr,
            #         "tags": tags,
            #         "i18n": equipment.i18n,
            #         "icon": equipment.icon,
            #         "vehicleWeightFraction": equipment._vehWeightFraction,
            #         "weight": equipment._weight,
            #         "maxWeightChange": equipment.maxWeightChange,
            #         "removable": equipment.removable,
            #         "price": equipment.price,
            #         "showInShop": equipment.showInShop,
            #         "stunResistanceEffect": equipment.stunResistanceEffect,
            #         "stunResistanceDuration": equipment.stunResistanceDuration,
            #         "vehicleFilter": equipment._Artefact__vehicleFilter,
            #         "artefactFilter": equipment._Artefact__artefactFilter,

            #         "equipmentType": getattr(equipment, "equipmentType", None),
            #         "reuseCount": getattr(equipment, "reuseCount", None),
            #         "cooldownSeconds": getattr(equipment, "cooldownSeconds", None),
            #         "durationSeconds": getattr(equipment, "durationSeconds", None),


            #         "staticFactorDevice_Factor": get_private_attr("__factor", None),
            #         "staticAdditiveDevice_Value": get_private_attr("__value", None),
            #         "staticFactor_Attr": get_private_attr("__attr", None),

            #         "activateWhenStillSec": getattr(equipment, "activateWhenStillSec", None),

            #         "circularVisionRadiusFactor": getattr(equipment, "circularVisionRadiusFactor", None),

            #         "chassisMaxLoadFactor": get_private_attr("__chassisMaxLoadFactor", None),
            #         "chassisHealthFactor": get_private_attr("__chassisHealthFactor", None),
            #         "vehicleByChassisDamageFactor": get_private_attr("__vehicleByChassisDamageFactor", None),

            #         "terrainResistance_factorSoft": get_private_attr("__factorSoft", None),
            #         "terrainResistance_factorMedium": get_private_attr("__factorMedium", None),

            #         "antifragmentationLiningFactor": get_private_attr("__antifragmentationLiningFactor", None),
            #         "increaseCrewChanceToEvadeHit": get_private_attr("__increaseCrewChanceToEvadeHit", None),

            #         "fireStartingChanceFactor": getattr(equipment, "fireStartingChanceFactor", None),
            #         "autoactivate": getattr(equipment, "autoactivate", None),

            #         "enginePowerFactor": getattr(equipment, "enginePowerFactor", None),
            #         "turretRotationSpeedFactor": getattr(equipment, "turretRotationSpeedFactor", None),
            #         "engineHpLossPerSecond": getattr(equipment, "engineHpLossPerSecond", None),

            #         "crewLevelIncrease": getattr(equipment, "crewLevelIncrease", None),

            #         "repairAll": getattr(equipment, "repairAll", None),
            #         "bonusValue": getattr(equipment, "bonusValue", None),

            #         "_config": getattr(equipment, "_config", None),

            #     }
                # {
                #     "name": equipment.name,
                #     "display_name": equipment.userString,
                #     "icon_key": equipment.icon[0].split("/")[-1].split(".")[0],
                #     "compact_descr": equipment.compactDescr,
                # }
            # )

        return optionalForExport

    @staticmethod
    def _gameInfoForExport():
        import urlparse
        import Settings
        from predefined_hosts import g_preDefinedHosts
        s = Settings.g_instance
        g_preDefinedHosts.readScriptConfig(s.scriptConfig, s.userPrefs)

        netloc = urlparse.urlsplit(g_preDefinedHosts._PreDefinedHostList__csisUrl).netloc.split(".")[-1]
        region = "?"

        if netloc == "com":
            region = "NA"
        elif netloc == "ru":
            region = "RU"
        elif netloc == "asia":
            region = "ASIA"
        elif netloc == "eu":
            region = "EU"
        else:
            region = "UNKNOWN"

        return {
            "xml_version": getFullClientVersion(),
            "exe_version": BigWorld.wg_getProductVersion(),
            "client_version": getClientVersion(),
            "client_language": getClientLanguage(),
            "language_code": getLanguageCode(),
            "csis_url": g_preDefinedHosts._PreDefinedHostList__csisUrl,
            "detected_region": region
        }

    @staticmethod
    def maps():
        try:
            arenasForExport = {}
            for arenaTypeID, arenaType in ArenaType.g_cache.iteritems():
                arenaName = arenaType.geometry
                i = arenaName.find('/')
                if i != -1:
                    arenaName = arenaName[i + 1:]

                arenasForExport[arenaName] = {
                    'id': int(arenaName.split('_', 1)[0]),
                    'arenaTypeID': arenaTypeID,
                    'name': arenaName,
                    'displayName': arenaType.name
                }

            path = 'res_mods/ScoreViewTools/Export/maps.json'
            abs_path = os.path.abspath(path)

            with open(abs_path, 'w+') as outfile:
                outfile.write(json.dumps({
                    "maps": arenasForExport.values()
                }, cls=CustomEncoder))

        except Exception as e:
            print "SVT - Data Export (Maps) - Error"
            traceback.print_exc()

    @staticmethod
    def vehicles():
        try:
            itemsFactory = dependency.descriptor(IGuiItemsFactory)
            vehs = vehicles.g_list
            vehsForExport = []
            for nationID in xrange(len(nations.NAMES)):
                for key, value in vehs.getList(nationID).iteritems():
                    vehicle = Vehicle(typeCompDescr=value.compactDescr)
                    #vehicle = itemsFactory.createVehicle(typeCompDescr=value.compactDescr) 
                    # vehicle = itemsFactory.createVehicle(typeCompDescr=value.compactDescr)
                    v = Export._vehicleForExport(vehicle)
                    v['maxHealths'] = []

                    for hull in vehicle.descriptor.type.hulls:
                        for turretList in vehicle.descriptor.type.turrets:
                            for turret in turretList:
                                v['maxHealths'].append(hull.maxHealth + turret.maxHealth)

                    vehsForExport.append(v)

            path = 'res_mods/ScoreViewTools/Export/vehicles.json'
            abs_path = os.path.abspath(path)

            with open(abs_path, 'w+') as outfile:
                outfile.write(json.dumps({
                    "vehicles": vehsForExport
                }, cls=CustomEncoder))
        except Exception as e:
            print "SVT - Data Export (Vehicles) - Error"
            traceback.print_exc()

    @staticmethod
    def vehicle_details():
        def check_for_json(key, value):
            import collections

            #print "checking key " + str(key) + " with value of " + str(value)
            if isinstance(value, dict):
                for k, v in value.iteritems():
                    check_for_json(str(key) + '.' + str(k), v)
                return
            if not isinstance(value, str) and isinstance(value, collections.Iterable):
                for v in value:
                    check_for_json(key + '[]', v)

                try:
                    json.dumps(value, cls=CustomEncoder)
                except Exception as e:
                    print str(key) + " failed to be converted to JSON"
                    traceback.print_exc()

                return
            
            try:
                json.dumps(value, cls=CustomEncoder)
            except Exception as e:
                print str(key) + " failed to be converted to JSON"
                traceback.print_exc()


        try:
            g_techTreeDP.load()
            vehs = vehicles.g_list
            vehsForExport = []
            modulesForExport = {}

            for nationID in xrange(len(nations.NAMES)):
                # if not nationID == 8:
                #     continue

                for key, value in vehs.getList(nationID).iteritems():

                    vehicle = Vehicle(typeCompDescr=value.compactDescr)
                    
                    # if not vehicle.level == 5:
                    #     continue

                    v = Export._vehicleForExport(vehicle)
                    type = vehicle.descriptor.type

                    
                    #v['price'] = type.price

                    v['mode'] = type.mode
                    v['hasSiegeMode'] = type.hasSiegeMode
                    v['speedLimits'] = type.speedLimits
                    v['repairCost'] = type.repairCost
                    v['crewXpFactor'] = type.crewXpFactor
                    v['premiumVehicleXPFactor'] = type.premiumVehicleXPFactor
                    # v['xpFactor'] = type.xpFactor
                    # v['creditsFactor'] = type.creditsFactor
                    # v['freeXpFactor'] = type.freeXpFactor
                    # v['healthBurnPerSec'] = type.healthBurnPerSec
                    # v['healthBurnPerSecLossFraction'] = type.healthBurnPerSecLossFraction
                    v['invisibility'] = type.invisibility
                    v['invisibilityDeltas'] = type.invisibilityDeltas
                    v['crewRoles'] = type.crewRoles
                    #v['extras'] = type.extras


                    #v['devices'] = type.devices
                    #v['tankmen'] = type.tankmen
                    v['isRotationStill'] = type.isRotationStill
                    v['siegeModeParams'] = type.siegeModeParams
                    v['hullAimingParams'] = type.hullAimingParams
                    v['unlocks'] = type.unlocks
                    v['unlocksDescrs'] = type.unlocksDescrs
                    v['autounlockedItems'] = type.autounlockedItems

                    v['hulls'] = []
                    v['chassis'] = []
                    v['engines'] = []
                    v['fuelTanks'] = []
                    v['radios'] = []

                    for hull in type.hulls:
                        i = {}
                        i['primaryArmor'] = hull.primaryArmor
                        i['maxHealth'] = hull.maxHealth
                        i['variantName'] = hull.variantName
                        i['turrets'] = []
                        for turretList in vehicle.descriptor.type.turrets:
                            for turret in turretList:
                                t = Export._installableItemForExport(turret, value.compactDescr)
                                t['rotationSpeed'] = turret.rotationSpeed
                                t['turretRotatorHealth'] = { 
                                    'maxHealth': turret.turretRotatorHealth.maxHealth,
                                    'repairCost': turret.turretRotatorHealth.repairCost,
                                    'maxRegenHealth': turret.turretRotatorHealth.maxRegenHealth
                                }
                                t['surveyingDeviceHealth'] = { 
                                    'maxHealth': turret.surveyingDeviceHealth.maxHealth,
                                    'repairCost': turret.surveyingDeviceHealth.repairCost,
                                    'maxRegenHealth': turret.surveyingDeviceHealth.maxRegenHealth
                                }
                                t['invisibilityFactor'] = turret.invisibilityFactor
                                t['circularVisionRadius'] = turret.circularVisionRadius
                                t['primaryArmor'] = turret.primaryArmor
                                t['guns'] = []

                                for gun in turret.guns:
                                    g = Export._installableItemForExport(gun, value.compactDescr)
                                    g['rotationSpeed'] = gun.rotationSpeed
                                    g['reloadTime'] = gun.reloadTime
                                    g['aimingTime'] = gun.aimingTime
                                    g['maxAmmo'] = gun.maxAmmo
                                    g['invisibilityFactorAtShot'] = gun.invisibilityFactorAtShot
                                    g['turretYawLimits'] = gun.turretYawLimits
                                    g['pitchLimits'] = gun.pitchLimits
                                    g['staticTurretYaw'] = gun.staticTurretYaw
                                    g['staticPitch'] = gun.staticPitch
                                    g['shotDispersionAngle'] = gun.shotDispersionAngle
                                    g['shotDispersionFactors'] = gun.shotDispersionFactors
                                    g['burst'] = gun.burst
                                    g['clip'] = gun.clip
                                    g['clipSize'] = gun.clip[0] / (gun.burst[0] if gun.clip[0] > 1 else 1)
                                    g['innerClipReloadTime'] = gun.clip[1]
                                    g['burstSize'] = gun.burst[0]
                                    g['burstFireTime'] = gun.burst[1]
                                    g['combinedPitchLimits'] = gun.combinedPitchLimits
                                    g['shots'] = []

                                    for shot in gun.shots:
                                        s = {}
                                        s['shell'] = {
                                            'caliber': shot.shell.caliber,
                                            'isTracer': shot.shell.isTracer,
                                            'damage': shot.shell.damage,
                                            "avgDamage": shot.shell.damage[0],
                                            'damageRandomization': shot.shell.damageRandomization,
                                            'piercingPowerRandomization': shot.shell.piercingPowerRandomization,
                                            'stun': None,
                                            'type': {
                                                'name': shot.shell.type.name,
                                                'normalizationAngle': getattr(shot.shell.type, 'normalizationAngle', None),
                                                'ricochetAngleCos': getattr(shot.shell.type, 'ricochetAngleCos', None),
                                                'piercingPowerLossFactorByDistance': getattr(shot.shell.type, 'piercingPowerLossFactorByDistance', None),
                                                'ricochetAngleCos': getattr(shot.shell.type, 'ricochetAngleCos', None),
                                                'explosionRadius': getattr(shot.shell.type, 'explosionRadius', None),
                                                'explosionDamageFactor': getattr(shot.shell.type, 'explosionDamageFactor', None),
                                                'explosionDamageAbsorptionFactor': getattr(shot.shell.type, 'explosionDamageAbsorptionFactor', None),
                                                'explosionEdgeDamageFactor': getattr(shot.shell.type, 'explosionEdgeDamageFactor', None),
                                                'stunRadius': getattr(shot.shell.type, 'stunRadius', None),
                                                'stunDuration': getattr(shot.shell.type, 'stunDuration', None),
                                                'stunFactor': getattr(shot.shell.type, 'stunFactor', None),
                                                'guaranteedStunDuration': getattr(shot.shell.type, 'guaranteedStunDuration', None),
                                                'damageDurationCoeff': getattr(shot.shell.type, 'damageDurationCoeff', None),
                                                'guaranteedStunEffect': getattr(shot.shell.type, 'guaranteedStunEffect', None),
                                                'damageEffectCoeff': getattr(shot.shell.type, 'damageEffectCoeff', None)
                                            },
                                            'isGold': shot.shell.isGold
                                        }
                                        if shot.shell.stun != None:
                                            s['shell']['stun'] = {
                                                'stunRadius': shot.shell.stun.stunRadius,
                                                'stunDuration': shot.shell.stun.stunDuration,
                                                'stunFactor': shot.shell.stun.stunFactor,
                                                'guaranteedStunDuration': shot.shell.stun.guaranteedStunDuration,
                                                'damageDurationCoeff': shot.shell.stun.damageDurationCoeff,
                                                'guaranteedStunEffect': shot.shell.stun.guaranteedStunEffect,
                                                'damageEffectCoeff': shot.shell.stun.damageEffectCoeff
                                            }

                                        s['defaultPortion'] = shot.defaultPortion
                                        s['piercingPower'] = [
                                            shot.piercingPower[0], 
                                            shot.piercingPower[1]
                                        ],
                                        s['avgPiercingPower'] = shot.piercingPower[0]
                                        s['speed'] = shot.speed
                                        s['gravity'] = shot.gravity
                                        s['maxDistance'] = shot.maxDistance
                                        s['maxHeight'] = shot.maxHeight
                                        g['shots'].append(s)

                                    clipCount = gun.clip[0] / (gun.burst[0] if gun.clip[0] > 1 else 1)
                                    # Who knows where this is coming from
                                    reloadTime = gun.reloadTime * 0.9587727708533078
                                    # g['clipSize'] = gun.clip[0] / (gun.burst[0] if gun.clip[0] > 1 else 1)
                                    # g['innerClipReloadTime'] = gun.clip[1]
                                    g['trueReloadTime'] = reloadTime
                                    g['fullReloadTime'] = (reloadTime + (gun.burst[0] - 1) * gun.burst[1] * clipCount + (clipCount - 1) * gun.clip[1])
                                    g['shotsPerMinute'] = gun.burst[0] * clipCount * 60 / (reloadTime + (gun.burst[0] - 1) * gun.burst[1] * clipCount + (clipCount - 1) * gun.clip[1])
                                    g['avgDamage'] = g['shots'][0]['shell']['avgDamage']
                                    g['avgBurstDamage'] = gun.clip[0] * g['avgDamage']
                                    g['avgDamagePerMinute'] = g['shotsPerMinute'] * g['avgDamage']

                                    g['trueAimingTime'] = g['aimingTime'] * 0.9587727708533078
                                    g['trueShotDispersionAngle'] = round(g['shotDispersionAngle'] * 0.9587727708533078 * 100, 2)

                                    t['guns'].append(g)

                                i['turrets'].append(t)

                        v['hulls'].append(i)

                    for chassis in type.chassis:
                        i = Export._installableItemForExport(chassis, value.compactDescr)
                        i['specificFriction'] = chassis.specificFriction
                        i['maxLoad'] = chassis.maxLoad
                        i['rotationSpeed'] = chassis.rotationSpeed
                        i['rotationSpeedLimit'] = chassis.rotationSpeedLimit
                        i['rotationIsAroundCenter'] = chassis.rotationIsAroundCenter
                        i['shotDispersionFactors'] = chassis.shotDispersionFactors
                        i['brakeForce'] = chassis.brakeForce
                        i['terrainResistance'] = chassis.terrainResistance
                        i['bulkHealthFactor'] = chassis.bulkHealthFactor
                        v['chassis'].append(i)

                    for engine in type.engines:
                        i = Export._installableItemForExport(engine, value.compactDescr)
                        i['power'] = engine.power
                        i['fireStartingChance'] = engine.fireStartingChance
                        i['minFireStartingDamage'] = engine.minFireStartingDamage
                        i['rpm_min'] = engine.rpm_min
                        i['rpm_max'] = engine.rpm_max
                        v['engines'].append(i)

                    for fuelTank in type.fuelTanks:
                        i = Export._installableItemForExport(fuelTank, value.compactDescr)
                        v['fuelTanks'].append(i)

                    for radio in type.radios:
                        i = Export._installableItemForExport(radio, value.compactDescr)
                        i['distance'] = radio.distance
                        v['radios'].append(i)

                    v['tags'] = []

                    for tag in vehicle.tags:
                        v['tags'].append(tag)

                    vehsForExport.append(v)
                #     break
                # break

            check_for_json('root', vehsForExport)

            topcfgs = [
                [
                    'id',
                    'name',
                    'type',
                    'level',
                    'maxHealth',
                    'avgDamage',
                    'avgDamagePerMinute',
                    'shotsPerMinute',
                    'reloadTime',
                    'shotDispersionAngle',
                    # 'avgDamagePerSecond',
                    # 'avgTimeToKillSelfStartingLoaded',
                    # 'avgTimeToKillSelfStartingUnloaded'
                    # 'maxHealth',
                    # 'vehicleWeight',
                    # 'enginePower',
                    # 'enginePowerPerTon',
                    # 'speedLimits',
                    # 'chassisRotationSpeed',
                    # 'hullArmor',
                    # 'damage',
                    # 'avgDamage',
                    # 'avgDamagePerMinute',
                    # 'avgPiercingPower',
                    # 'piercingPower',
                    # 'reloadTime',
                    # 'turretRotationSpeed',
                    # 'gunRotationSpeed',
                    # 'circularVisionRadius',
                    # 'radioDistance',
                    # 'turretArmor',
                    # 'explosionRadius',
                    # 'aimingTime',
                    # 'shotDispersionAngle',
                    # 'reloadTimeSecs',
                    # 'relativePower',
                    # 'relativeArmor',
                    # 'relativeMobility',
                    # 'relativeVisibility',
                    # 'relativeCamouflage',
                    # 'turretYawLimits',
                    # 'gunYawLimits',
                    # 'pitchLimits',
                    # 'invisibilityStillFactor',
                    # 'invisibilityMovingFactor',
                    # 'invisibilityFactorAtShot',
                    # 'clipFireRate',
                    # 'switchOnTime',
                    # 'switchOffTime',
                    # 'stunMaxDuration',
                    # 'stunMinDuration'
                ]
            ]

            # def compare_modules(a, b, mostValuableParam):
            #     if a == None:
            #         return b
            #     if a['level'] < b['level'] or a['researchCost'] < b['researchCost'] or a[mostValuableParam] < b[mostValuableParam]:
            #         return b

            #     return a

            # def calculate_time_to_deal_damage(veh, damageTarget, startLoaded = True):
            #     time = 0
            #     avgDamage = veh['gun']['avgDamage']
            #     fullReloadTime = veh['gun']['trueReloadTime']
            #     clipSize = veh['gun']['clipSize']
            #     innerClipReloadTime = veh['gun']['innerClipReloadTime']
            #     burstSize = veh['gun']['burstSize']
            #     burstFireTime = veh['gun']['burstFireTime']

            #     if startLoaded == True:
            #         time -= fullReloadTime

            #     healthRemaining = damageTarget
            #     while healthRemaining > 0:
            #         time += fullReloadTime
                    
            #         currentClip = clipSize

            #         time -= innerClipReloadTime
            #         while currentClip > 0:
            #             time += innerClipReloadTime

            #             currentBurst = burstSize

            #             time -= burstFireTime
            #             while currentBurst > 0:
            #                 time += burstFireTime

            #                 healthRemaining -= avgDamage

            #                 if healthRemaining <= 0:
            #                     return time

            #                 currentBurst -= 1

            #             currentClip -= 1


            #     return time



            # Note: scripts/common/items/utils.py
            # Note: scripts/client/gui/shared/items_parameters/params.py
            # Note: scripts/client/gui/shared/items_paramaters/__init__.py
            # Note: /scripts/common/items/VehicleDescrCrew.py

            # for veh in vehsForExport:

            #     if "premiumIGR" in veh['tags'] or "secret" in veh['tags']:
            #         continue


            #     modules = {
            #         'hull': veh['hulls'][0],
            #         'chassis': None,
            #         'turret': None,
            #         'gun': None,
            #         'engine': None,
            #         'radio': None
            #     }

            #     for chassis in veh['chassis']:
            #         modules['chassis'] = compare_modules(modules['chassis'], chassis, 'maxLoad')

            #     for turret in modules['hull']['turrets']:
            #         modules['turret'] = compare_modules(modules['turret'], turret, 'primaryArmor')

            #     for gun in modules['turret']['guns']:
            #         modules['gun'] = compare_modules(modules['gun'], gun, 'avgDamagePerMinute')

            #     for engine in veh['engines']:
            #         modules['engine'] = compare_modules(modules['engine'], engine, 'power')

            #     for radio in veh['radios']:
            #         modules['radio'] = compare_modules(modules['radio'], radio, 'distance')
                    
            #     maxHealth = modules['hull']['maxHealth'] + modules['turret']['maxHealth']

            #     # ttks_startingLoaded = 0
            #     # remainingHealth = maxHealth - modules['gun']['avgBurstDamage']

            #     # while remainingHealth > 0:
            #     #     remainingHealth = remainingHealth - modules['gun']['avgBurstDamage']
            #     #     ttks_startingLoaded = ttks_startingLoaded + modules['gun']['fullReloadTime']


            #     # remainingHealth = maxHealth
            #     # ttks_startingUnloaded = 0
            #     # while remainingHealth > 0:
            #     #     remainingHealth = remainingHealth - modules['gun']['avgBurstDamage']
            #     #     ttks_startingUnloaded = ttks_startingUnloaded + modules['gun']['fullReloadTime']


            #     topcfgs.append([
            #         veh['id'],
            #         veh['name'],
            #         veh['type_tag'],
            #         veh['level'],
            #         maxHealth,
            #         modules['gun']['avgDamage'],
            #         modules['gun']['avgDamagePerMinute'],
            #         modules['gun']['shotsPerMinute'],
            #         modules['gun']['trueReloadTime'],
            #         modules['gun']['trueShotDispersionAngle'],
            #         modules['gun']['avgDamagePerMinute'] / 60,
            #         calculate_time_to_deal_damage(modules, maxHealth),
            #         calculate_time_to_deal_damage(modules, maxHealth, False)
            #     ])

            # path = 'res_mods/ScoreViewTools/Export/vehicle_details.csv'            
            # abs_path = os.path.abspath(path)

            # import csv
            # with open(path, 'wb') as f:
            #     writer = csv.writer(f)
            #     writer.writerows(topcfgs)

            skill_factors = {}

            for role in skills_constants.SKILLS_BY_ROLES:
                skill_names = skills_constants.SKILLS_BY_ROLES[role]

                for skill_name in skill_names:
                    skill = getSkillsConfig().getSkill(skill_name)

                    skill_info = {
                        "name": getattr(skill, "name", None),
                        "userString": getattr(skill, "userString", None),
                        "description": getattr(skill, "description", None),
                        "crewLevelIncrease": getattr(skill, "crewLevelIncrease", None),
                        "xpBonusFactorPerLevel": getattr(skill, "xpBonusFactorPerLevel", None),
                        "efficiency": getattr(skill, "efficiency", None),
                        "delay": getattr(skill, "delay", None),
                        "distanceFactorPerLevelWhenDeviceWorking": getattr(skill, "distanceFactorPerLevelWhenDeviceWorking", None),
                        "distanceFactorPerLevelWhenDeviceDestroyed": getattr(skill, "distanceFactorPerLevelWhenDeviceDestroyed", None),
                        "fireStartingChanceFactor": getattr(skill, "fireStartingChanceFactor", None),
                        "shotDispersionFactorPerLevel": getattr(skill, "shotDispersionFactorPerLevel", None),
                        "rotationSpeedFactorPerLevel": getattr(skill, "rotationSpeedFactorPerLevel", None),
                        "rammingBonusFactorPerLevel": getattr(skill, "rammingBonusFactorPerLevel", None),
                        "softGroundResistanceFactorPerLevel": getattr(skill, "softGroundResistanceFactorPerLevel", None),
                        "mediumGroundResistanceFactorPerLevel": getattr(skill, "mediumGroundResistanceFactorPerLevel", None),
                        "shotDispersionFactorPerLevel": getattr(skill, "shotDispersionFactorPerLevel", None),
                        "shotDispersionFactorPerLevel": getattr(skill, "shotDispersionFactorPerLevel", None),
                        "deviceChanceToHitBoost": getattr(skill, "deviceChanceToHitBoost", None),
                        "duration": getattr(skill, "duration", None),
                        "sectorHalfAngle": getattr(skill, "sectorHalfAngle", None),
                        "ammoBayHealthFactor": getattr(skill, "ammoBayHealthFactor", None),
                        "chance": getattr(skill, "chance", None),
                        "vehicleHealthFraction": getattr(skill, "vehicleHealthFraction", None),
                        "gunReloadTimeFactor": getattr(skill, "gunReloadTimeFactor", None),
                        "visionRadiusFactorPerLevel": getattr(skill, "visionRadiusFactorPerLevel", None),
                        "radioDistanceFactorPerLevel": getattr(skill, "radioDistanceFactorPerLevel", None),
                        "distanceFactorPerLevel": getattr(skill, "distanceFactorPerLevel", None)
                    }

                    for key in skill_info.keys():
                        if skill_info[key] == None:
                            skill_info.pop(key, None)

                    skill_factors[skill_name] = skill_info



            path = 'res_mods/ScoreViewTools/Export/vehicle_details.json'
            abs_path = os.path.abspath(path)

            with open(abs_path, 'w+') as outfile:
                outfile.write(json.dumps({
                    "skills": skill_factors,
                    "vehicle_factors": VEHICLE_ATTRIBUTE_FACTORS,
                    "vehicles": vehsForExport
                }, cls=CustomEncoder))
        except Exception as e:
            print "SVT - Data Export (Vehicle Details) - Error"
            traceback.print_exc()

    @staticmethod
    def consumables():
        try:
            path = 'res_mods/ScoreViewTools/Export/consumables.json'
            abs_path = os.path.abspath(path)

            equipmentForExport = Export._consumablesForExport()

            Export._check_for_json('root', equipmentForExport)

            with open(abs_path, 'w+') as outfile:
                outfile.write(json.dumps({
                    "consumables": equipmentForExport
                }, cls=CustomEncoder))
        except Exception as e:
            print "SVT - Data Export (Consumables) - Error"
            traceback.print_exc()

    @staticmethod
    def equipment():
        try:
            path = 'res_mods/ScoreViewTools/Export/equipment.json'
            abs_path = os.path.abspath(path)


            optionalForExport = Export._equipmentForExport()

            Export._check_for_json('root', optionalForExport)

            with open(abs_path, 'w+') as outfile:
                outfile.write(json.dumps({
                    "equipment": optionalForExport
                }, cls=CustomEncoder))
        except Exception as e:
            print "SVT - Data Export (Equipment) - Error"
            traceback.print_exc()

    @staticmethod
    def gameInfo():
        try:
            path = 'res_mods/ScoreViewTools/Export/gameInfo.json'
            with open(path, 'w+') as outfile:
                outfile.write(json.dumps(Export._gameInfoForExport(), cls=CustomEncoder))
        except Exception as e:
            print "SVT - Data Export (Game Info) - Error"
            traceback.print_exc()

    @staticmethod
    def gameData():
        try:
            vehData = Export._vehicleDetailsForExport()
            data = {
                    "exported_data_format_version": 1,
                    "game": Export._gameInfoForExport(),
                    "consumables": Export._consumablesForExport(),
                    "equipment": Export._equipmentForExport(),
                    "skills": vehData["skills"],
                    "vehicle_factors": vehData["vehicle_factors"],
                    "vehicle_coefficients": vehData["coefficients"],
                    "vehicles": vehData["vehicles"],
                    "shell_data": vehData["shell_data"],
                    "stun_data": stunConfig
                }

            Export._check_for_json('root', data)


            path = 'res_mods/ScoreViewTools/Export/gameData.json'
            with open(path, 'w+') as outfile:
                outfile.write(json.dumps(data, cls=CustomEncoder))

        except Exception as e:
            print "SVT - Data Export (Game Data) - Error"
            traceback.print_exc()

    @staticmethod
    def trainingRoom(functional):
        if(Export.__checkVersion() != True):
            print "SVT - Version Unsupported"
            return

        try:

            settings = functional.getSettings()
            mapData = None
            if settings is not None:
                arenaTypeID = settings['arenaTypeID']
                arenaType = ArenaType.g_cache.get(arenaTypeID)

                arenaName = arenaType.geometry
                i = arenaName.find('/')
                if i != -1:
                    arenaName = arenaName[i + 1:]

                mapData = {
                    "arenaTypeID": arenaTypeID,
                    "maxPlayersCount": arenaType.maxPlayersInTeam * 2,
                    "arenaDisplayName": arenaType.name,
                    "arenaName": arenaName,
                    "arenaSubType": formatters.getArenaSubTypeString(arenaTypeID),
                    "gameplayName": arenaType.gameplayName,
                    "descriptionStr": arenaType.description,
                    "roundLength": settings['roundLength'],
                    'roundLenString': formatters.getRoundLenString(settings['roundLength'])
                }

            rosters = functional.getRosters()

            roster_list = []
            for key in rosters:
                for player in rosters[key]:

                    dataDic = {}

                    if player.isVehicleSpecified():
                        vehicle = player.getVehicle()
                        dataDic = Export._vehicleForExport(vehicle)

                        dataDic["maxHealth"] = vehicle.descriptor.maxHealth

                        gun = vehicle.descriptor.turrets[0][1];
                        dataDic["clipSize"] = gun.clip[0] / (gun.burst[0] if gun.clip[0] > 1 else 1)

                        dataDic["equipment"] = []
                        for equipment in vehicle.descriptor.optionalDevices:
                            equipment_descr = None
                            if equipment is not None:
                                equipment_descr = equipment.compactDescr

                            dataDic["equipment"].append(equipment_descr)

                        dataDic["consumables"] = []
                        for consumable in vehicle._equipment.consumables.installed:
                            consumable_descr = None
                            if consumable is not None:
                                consumable_descr = consumable.compactDescr

                            dataDic["consumables"].append(consumable_descr)


                    dataDic["name"] = player.name
                    dataDic["dbID"] = player.dbID
                    dataDic["team"] = int(key)
                    dataDic["clanDBID"] = player.clanDBID
                    dataDic["clanAbbrev"] = player.clanAbbrev
                    roster_list.append(dataDic);

            timestamp = int(time.time())
            Export.__settingExportInternalCounter += 1
            counter = Export.__settingExportInternalCounter
            path = 'res_mods/ScoreViewTools/TrainingRoom/export_' + str(timestamp) + '_' + str(counter) + '.json'
            abs_path = os.path.abspath(path)

            with open(abs_path, 'w+') as outfile:
                outfile.write(json.dumps({
                    "timestamp": timestamp,
                    "counter": counter,
                    "rosters": roster_list,
                    "map": mapData
                }, cls=CustomEncoder))

        except Exception as e:
            print "SVT - Training Room Export - Error"
            traceback.print_exc()

    @staticmethod
    def trainingRoomSettings(functional):
        Export.trainingRoom(functional)
        return

    @staticmethod
    def trainingRoomRoster(functional):
        Export.trainingRoom(functional)
        return