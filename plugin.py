# Dashticz plugin for Innovation in Motion Slide
#
# Author: lokonli
#
"""
<plugin key="iim-slide-local" name="Slide by Innovation in Motion - Local" author="lokonli" version="0.4" wikilink="https://github.com/lokonli/slide-domoticz-local" externallink="https://slide.store/">
    <description>
        <h2>Slide by Innovation in Motion</h2><br/>
        Plugin for Slide by Innovation in Motion.<br/>
        <br/>
        It uses the Innovation in Motion local API.<br/>
        <br/>
        This is beta release 0.4 <br/>
        <br/>
        <h3>Configuration</h3>
        Enable local API by pressing the reset button twice within 0.5 sec.<br/>
        The reset button is in the hole left of the power connector, when you have the orange slide label on top<br/>
        The LED, right of the power connector, will flash a few time to indicate your slide switched to local API mode<br/>
        <br/>

        Don't forget to set 'Allow creation of new devices' in Domoticz first before enabling this plugin. <br/>
        <br/>

        For each Slide two Domoticz devices will be created: A Blinds device and a Calibrate push-button
         
        Slide IP addresses: 1 or more IP addresses, semicolon separated.<br/>
        Device codes: List of device codes, semicolon seperated. Number of codes must match number of IP addresses. Device code is printed on top of your Slide.<br/>

    </description>
    <params>
           <param field="Mode2" label="Slide IP address(es)" width="200px" required="true" default="192.168.178.47"/>
           <param field="Mode3" label="Device code(s)" width="200px" required="true" default="a1b2c3d4"/>
           <param field="Mode4" label="Refresh time (minutes)" width="200px" required="true" default="5"/>
           <param field="Mode6" label="Debug" width="150px">
                <options>
                    <option label="None" value="0"  default="true" />
                    <option label="Python Only" value="2"/>
                    <option label="Basic Debugging" value="62"/>
                    <option label="Basic+Messages" value="126"/>
                    <option label="Connections Only" value="16"/>
                    <option label="Connections+Python" value="18"/>
                    <option label="Connections+Queue" value="144"/>
                    <option label="All" value="-1"/>
                </options>
            </param>
    </params>
</plugin>
"""
import DomoticzEx as Domoticz # type: ignore
import json
from datetime import datetime, timezone
import time
import _strptime
from hashlib import md5
from shutil import copy2
import os
import os.path
import re
import timerqueue
import threading
import asyncio
from goslideapi import GoSlideLocal
import logging

if False==True:
    Domoticz = {}
    Parameters = {}
    Devices = {}

def dumpJson(name, msg):
    messageJson = json.dumps(msg,
                skipkeys = True,
                allow_nan = True,
                indent = 6)
    Domoticz.Debug('Message: '+name )
    Domoticz.Debug(messageJson)
class IimSlideLocal:

    DEV_SLIDE = 1
    DEV_CAL = 2
    DEV_TG = 3

    def __init__(self):
        # 0: Date including timezone info; 1: No timezone info. Workaround for strptime bug
        self._dateType = 0
        self.commandQueue = timerqueue.TimerQueue()
        self.tasks=[]

    def onStart(self):
        Domoticz.Debug("onStart called")
        self.debugging=False

        if Parameters["Mode6"] == "-1":
            Domoticz.Debugging(1)
            Domoticz.Log("Debugger started, use '0.0.0.0 5678' to connect")
            import debugpy
            self.debugging=True
            self.debugpy=debugpy
            logging.basicConfig(filename='/var/log/domoticzlog.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
            debugpy.listen(("0.0.0.0", 5678))
##            debugpy.wait_for_client()
            time.sleep(10)
#            debugpy.breakpoint()
        else:
            Domoticz.Log("onStart called")


        strVersion = Parameters['DomoticzVersion']
        Domoticz.Log('Version ' + strVersion)
        mainVersion = strVersion.split()[0]
        if mainVersion>="2023.1":
            self.nVersion = 1
        else:
            x = re.search("(?<=build )\d+(?=\))", strVersion)
            self.nVersion = 0
            domoVersion = 0
            if x:
                domoVersion = int(x[0])
            if domoVersion > 14560:
                self.nVersion = 1
        Domoticz.Debug('Version ' + str(self.nVersion))
        self.hb = 1
        self.hbCycles = 5
        self.devices = []
        self.deviceMap = {}
        self._tick = 0
        self._dateType = 0
        if Parameters["Mode6"] != "0":
            Domoticz.Debugging(int(Parameters["Mode6"]))
#            DumpConfigToLog()
        Domoticz.Debug("Homefolder: {}".format(Parameters["HomeFolder"]))
        Domoticz.Heartbeat(60)
        self.messageThread = threading.Thread(name="QueueThread", target=IimSlideLocal.slideThread, args=(self,))
        self.messageThread.start()
        Domoticz.Debug('Thread started')
    
    def slideThread(self):
        Domoticz.Debug('Start slide thread')
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.goslide = GoSlideLocal()
        if self.debugging:
            self.debugpy.breakpoint()

        self.initialize()

        while True:
            try:
                Message = self.commandQueue.get(block=True)
                if self.debugging:
                    self.debugpy.breakpoint()

                if Message is None:
                    Domoticz.Debug("Exiting message handler")
                    self.commandQueue.task_done()
                    break

                dumpJson('Message', Message)

                if (Message["Type"] == "Command"):
                    deviceID = Message["DeviceID"]
                    device = self.deviceMap[deviceID]
                    Command=Message["Command"]
                    Unit=Message["Unit"]
                    Level=Message["Level"]
                    try: 
                        if Message["Unit"]==IimSlideLocal.DEV_SLIDE:
                            if (Command == 'Off' or Command == 'Close'):
                                self.setPosition(device, 0)
                            if (Command == 'On' or Command == 'Open'):
                                self.setPosition(device, 1)
                            if (Command == 'Set Level'):
                                self.setPosition(device, Level/100)
                            if (Command == 'Stop'):
                                self.slideStop(device, Level/100)
                        elif Unit==IimSlideLocal.DEV_CAL:
                            if Command == 'On':
                                self.calibrate(device)
                        elif Unit==IimSlideLocal.DEV_TG:
                            self.setTouchGo(device, Command)
                    except Exception as err:
                        Domoticz.Error("Command error: "+str(err))
                elif Message["Type"] == "GetInfo":
                    self.handleGetInfo(Message['device'])
                elif Message["Type"] == "GetAllInfo":
                    self.loop.run_until_complete(self.getAllSlidesInfo())
                else:
                    Domoticz.Error('Message not handled.')
                self.commandQueue.task_done()

            except Exception as err:
                Domoticz.Error("handleMessage: "+str(err))


    def initialize(self):
        Domoticz.Debug('initializing')
        ipList = Parameters['Mode2'].split(';')
        if len(ipList) == 0:
            Domoticz.Log('IP address of Slide undefined')
            return
        codeList = Parameters['Mode3'].split(';')
        if len(codeList) != len(ipList):
            Domoticz.Error(
                'Number of Slide IPs and Slide Device codes do not match')
            return
        
        self.hbCycles = 5 if len(Parameters['Mode4'])==0 else max(int(Parameters['Mode4']),1)

        self.devices = [{'ip': ip, 'code': code, 'connectionError': False, 'monitorTime':0} for ip, code in zip(ipList, codeList)]

        Domoticz.Debug(json.dumps(self.devices, indent=4))
        self.addSlides()
        self.loop.run_until_complete(self.getAllSlidesInfo())

    def onStop(self):
        Domoticz.Debug("onStop called")

        self.commandQueue.put(None)
        self.commandQueue.join()

        Domoticz.Debug('Threads still active: {} (should be 1)'.format(threading.active_count()))
        endTime = time.time() + 70
        while (threading.active_count() > 1) and (time.time() < endTime):
            for thread in threading.enumerate():
                if thread.name != threading.current_thread().name:
                    Domoticz.Debug('Thread {} is still running, waiting otherwise Domoticz will abort on plugin exit.'.format(thread.name))
            time.sleep(1.0)

        Domoticz.Debug('Plugin stopped - Threads still active: {} (should be 1)'.format(threading.active_count()))

    def addSlides(self):
        for device in self.devices:
            api = 2 if len(device["code"])==0 else 1
            self.loop.run_until_complete(self.goslide.slide_add(device["ip"],device["code"],api ))

    async def getAllSlidesInfo(self, delay=0):
        await asyncio.gather(*[self.getSlideInfo(device, delay) for device in self.devices])
        return None

    async def getSlideInfo(self, device, delay=0):
        Domoticz.Debug("getSlideInfo: "+str(device))
        try:
            device["slide"] = await self.goslide.slide_info(device["ip"])
            self.deviceMap[device["slide"]["slide_id"]] = device
            Domoticz.Debug(json.dumps(device))
            if device["slide"] != None:
                if device['connectionError']:
                    device['connectionError'] = False
                    Domoticz.Debug(f"Device {device['ip']} reconnected.")
                self.updateSlide(device)
        except:
            if not device['connectionError']:
                device['connectionError'] = True
                Domoticz.Debug(f"Device {device['ip']} not connected.")

        return None

    def updateSlide(self, device):
        id = device["slide"]["slide_id"]

        switchType = 21 if self.nVersion>=1 else 13

        defaultUnits = [
            { #1
                "Unit": self.DEV_SLIDE,
                "Name": "Slide "+id,
                "Type": 244,
                "Subtype": 73,
                "Switchtype": switchType,
            },
            { #2
                "Unit": self.DEV_CAL,
                "Name": "Calibrate "+id,
                "Type": 244,
                "Subtype": 73,
                "Switchtype": 9,
            },
            { #3
                "Unit": self.DEV_TG,
                "Name": "Touch&Go "+id,
                "Type": 244,
                "Subtype": 73,
                "Switchtype": 0,
            },
        ]

        try:
            slide=Devices[id]
            for defaultUnit in defaultUnits:
                unit = defaultUnit["Unit"]
                if unit in slide.Units:
                    myUnit = slide.Units[unit]
                else:
                    myUnit = Domoticz.Unit(DeviceID=id, Used=1, **defaultUnit)
                    myUnit.Create()
        except:
            for defaultUnit in defaultUnits:
                myUnit = Domoticz.Unit(DeviceID=id, Used=1, **defaultUnit)
                myUnit.Create()
        if self.updateSlidePos(device):
            self.monitorPosition(device,1)
        self.updateTouchGo(device)

    def updateSlidePos(self, device):    
        id = device["slide"]["slide_id"]
        pos=device["slide"]["pos"]
        sValue = str(int(pos*100))
        nValue = 2
#        if pos < 0.13:
        unit = Devices[id].Units[self.DEV_SLIDE]
        nPos = 1- pos if self.nVersion >= 1 else pos
        sValue = str(int(nPos*100))
        if nPos < 0.1:
            nValue = 0
            sValue = '0'
        if nPos > 0.9:
            nValue = 1
            sValue = '100'

        if self.debugging:
            self.debugpy.breakpoint()

        if(unit.sValue != sValue):
            Domoticz.Debug('Update position from {} to {}'.format(
                unit.sValue, sValue))
            unit.nValue=nValue
            unit.sValue=sValue
            unit.Update(Log=True)
            return True
        else:
            return False
    
    def updateTouchGo(self, device):
        id = device["slide"]["slide_id"]
        tg = device["slide"]["touch_go"]
        unit = Devices[id].Units[self.DEV_TG]
        unitTG = unit.nValue == 1
        if tg!=unitTG:
            unit.nValue = 1 if tg else 0
            unit.Update(Log=True)
            return True
        else:
            return False

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        Domoticz.Log("onCommand called for Device " + str(DeviceID) + " Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
        self.commandQueue.put(
            {"Type":"Command", 
             "DeviceID": DeviceID,
             "Unit": Unit,
             "Command": Command,
             "Level": Level
            })

    def setPosition(self, device, level):
        if self.debugging:
            self.debugpy.breakpoint()
        hostname = device["ip"]
        Domoticz.Debug("setPosition called")
        Domoticz.Debug("Nversion "+ str(self.nVersion))
        nLevel = 1-level if self.nVersion == 1 else level
        self.loop.run_until_complete(self.goslide.slide_set_position(hostname, nLevel ))
        self.getInfoDelayed(device, 2)

    def getInfoDelayed(self, device, delay):
        Domoticz.Debug('getInfoDelayed called')
        if self.debugging:
            self.debugpy.breakpoint()
        self.commandQueue.put({
            "Type":"GetInfo", 
            "device": device,
           }, delay)

    def monitorPosition(self, device, delay):
        """ Start polling monitor position for next {delay} seconds """

        Domoticz.Debug('monitorPosition called')
        endTime=time.monotonic() + delay
        monitoring = device['monitorTime'] > 0
        if endTime > device['monitorTime']:
            device['monitorTime'] = endTime
        if not monitoring:
            self.getInfoDelayed(device,1)

    def handleGetInfo(self, device):
        Domoticz.Debug('GetInfo called, delayed command')
        self.loop.run_until_complete(self.getSlideInfo(device))
        if device['monitorTime'] > time.monotonic():
            self.getInfoDelayed(device,1)
        else:
            device['monitorTime'] = 0

    def setTouchGo(self, device, command):
        Domoticz.Debug('set_touch_go '+command)
        hostname = device["ip"]
        nLevel = command=='On'
        self.loop.run_until_complete(self.goslide.slide_set_touchgo(hostname, nLevel ))
        self.getInfoDelayed(device,0.1)

    def calibrate(self, device):
        hostname = device["ip"]
        self.loop.run_until_complete(self.goslide.slide_calibrate(hostname))
        self.monitorPosition(device,3)

    def getDevice(self, id):
        Domoticz.Debug('getDevice called for ' + id)
        if id in self.deviceMap:
            return self.deviceMap[id]
        else:
            Domoticz.Error('Slide id {}  not found.'.format(id))
            Domoticz.Debug(json.dumps(self.deviceMap))
            return None

    def slideStop(self, device, level):
        Domoticz.Debug("slideStop called")
        if device == None:
            return
        hostName = device["ip"]
        self.loop.run_until_complete(self.goslide.slide_stop(hostName))
        self.monitorPosition(device,1)

    def onHeartbeat(self):
        if self.hb >= self.hbCycles:
            Domoticz.Debug("onHeartbeat called")
            self.hb = 1
            self.commandQueue.put(
                {"Type":"GetAllInfo", 
                })
        else:
            self.hb = self.hb + 1


global _plugin
_plugin = IimSlideLocal()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions

def LogMessage(Message):
    Domoticz.Debug(Message)

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return