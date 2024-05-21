# Dashticz plugin for Innovation in Motion Slide
#
# Author: lokonli
#
"""
<plugin key="iim-slide-local" name="Slide by Innovation in Motion - Local" author="lokonli" version="0.3.0" wikilink="https://github.com/lokonli/slide-domoticz-local" externallink="https://slide.store/">
    <description>
        <h2>Slide by Innovation in Motion</h2><br/>
        Plugin for Slide by Innovation in Motion.<br/>
        <br/>
        It uses the Innovation in Motion local API.<br/>
        <br/>
        This is beta release 0.3.0. <br/>
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
import Domoticz # type: ignore
import json
from datetime import datetime, timezone
import time
import _strptime
from hashlib import md5
from shutil import copy2
import os
import os.path
import re

if False==True:
    Domoticz = {}
    Parameters = {}
    Devices = {}

class IimSlideLocal:

    def __init__(self):
        # 0: Date including timezone info; 1: No timezone info. Workaround for strptime bug
        self._dateType = 0

    def onStart(self):
        Domoticz.Debug("onStart called")
        strVersion = Parameters['DomoticzVersion']
        Domoticz.Log('Version ' + strVersion)
        mainVersion = strVersion.split()[0]
        if mainVersion>="2024.1":
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
        self.messageQueue = []
        self.connections = {}
        self.msgCount = 0
        self.messageActive = False
        self._tick = 0
        self._dateType = 0
        if Parameters["Mode6"] != "0":
            Domoticz.Debugging(int(Parameters["Mode6"]))
            DumpConfigToLog()
        Domoticz.Debug("Homefolder: {}".format(Parameters["HomeFolder"]))
        Domoticz.Debug("Length {}".format(len(self.messageQueue)))
        Domoticz.Heartbeat(60)
        self.initialize()

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
        
        self.hbCycles = max(int(Parameters['Mode4']),1)

        self.devices = [{'ip': ip, 'code': code, 'nonce': '', 'nc': 0,
                         'checkMovement': 0, 'Conn': None} for ip, code in zip(ipList, codeList)]

        Domoticz.Debug(json.dumps(self.devices, indent=4))
        self.getAllSlidesInfo()

    def onStop(self):
        Domoticz.Debug("onStop called")

    def addMessageToQueue(self, cmd):
        Domoticz.Debug("addMessageToQueue: " +str(cmd))
        cmd['authorizationError'] = False
        self.messageQueue.append(cmd)
        if not self.messageActive:
            self.sendMessageFromQueue()
        else:
            Domoticz.Debug("Sending postponed, queue len: " + str(len(self.messageQueue)))


    def sendMessageFromQueue(self):
        if len(self.messageQueue) == 0:
            return
        self.connect(self.messageQueue.pop(0))

    def connect(self, msg):
        Domoticz.Debug("connect called" + str(msg))
        self.messageActive = True
        address = msg["device"]["ip"]
        self.msgCount = self.msgCount + 1 if self.msgCount < 9999 else 0
        
        connectionName = 'Slide_'+address+'_'+str(self.msgCount)
#        if connectionName not in self.connections:
#            self.connections[connectionName] = []	# initialise the connections list that holds the commands
#        self.connections[connectionName].append(msg)	# add the message to the list
        self.connections[connectionName] = msg
        self.connection = Domoticz.Connection(
            Name=connectionName, Transport="TCP/IP", Protocol="HTTP", Address=address, Port="80")
        self.connection.Connect(Timeout=1000)
        return

        for dev in self.devices:
            if dev['ip'] == address:
                if dev['Conn'] == None:
                    Domoticz.Debug("Creating connection for address " + address)
                    dev['Conn'] = Domoticz.Connection(
                        Name=connectionName, Transport="TCP/IP", Protocol="HTTP", Address=address, Port="80")
                    dev['Conn'].Connect()
                    return
                else:
                    if dev['Conn'].Connected() or dev['Conn'].Connecting():
                        Domoticz.Debug("Connection (being) created " + address)
                        return
                    else:
                        Domoticz.Debug("Connecting address " + address)
                        dev['Conn'].Connect()
                        return

        Domoticz.Error("Error: connection for IP not found " + address)

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect called: " + Connection.Address + " " + Connection.Name + " connected: " + str(Connection.Connected()) + " connecting: " + str(Connection.Connecting()))

        currentMessage = self.connections[Connection.Name] if Connection.Name in self.connections else None
        Domoticz.Debug("onConnect message is: " + str(currentMessage))

        if (Status == 0):
            Domoticz.Debug("Slide connected successfully: "+Connection.Address+" "+Connection.Name)
        else:
            Domoticz.Error("Failed to connect ("+str(Status)+") to: " +
                           currentMessage["device"]["ip"]+" with error: "+Description)
            return

        if Connection.Name in self.connections:
            self.sendMessage(Connection)
        else:
            Domoticz.Error('Connection without info')
    
    def onTimeout(self, Connection):
        Domoticz.Debug("Timeout for: "+Connection.Name)
        self.messageActive = False
        self.connections.pop(Connection.Name, None)
        self.sendMessageFromQueue()


    def sendMessage(self, connection):
        Domoticz.Debug("sendMessage called")
        currentMessage = self.connections[connection.Name]
        Domoticz.Debug("sendMessage currentMessage: " + str(currentMessage))
        _device = currentMessage["device"]
        username = 'user'
        realm = 'iim'
        password = _device["code"]

        part1 = md5((username + ':' + realm + ':' +
                     password).encode("utf-8")).hexdigest()
        Domoticz.Debug('Part 1: '+part1)

        cmd = 'POST'
        uri = currentMessage["uri"]
        part2 = md5((cmd + ':' + uri).encode("utf-8")).hexdigest()
        Domoticz.Debug('Part 2: '+part2)

        nonce = _device["nonce"]
        nc = format(_device["nc"], '08')
        _device["nc"] += 1
        cnonce = 'abcdef0123456789'
        qop = 'auth'

        response = md5((part1 + ':' + nonce + ':' + nc + ':' + cnonce +
                        ':' + qop + ':' + part2).encode("utf-8")).hexdigest()

# 'Authorization: Digest username="user",
# realm="iim", nonce="5f4031e1",
# uri="/rpc/Slide.GetInfo",
# algorithm="MD5",
# qop=auth, nc=00000001,
# cnonce="abcdef0123456789",
# response="258bc1b41e0b9d70bea4f0a204d85593"'
        sendData = {
            'Verb': 'POST',
            'Headers': {'Content-Type': 'application/json',
                        #                        'Host': 'api.goslide.io',
                        'Accept': 'application/json',
                        #                        'X-Requested-With': 'XMLHttpRequest',
                        'Authorization': 'Digest username="' + username + '", ' +
                        'realm="'+realm+'", ' +
                        'nonce="'+nonce + '", ' +
                        'uri="' + uri + '", ' +
                        'algorithm="MD5", qop=' + qop + ', ' +
                        'nc='+nc+', ' +
                        'cnonce="' + cnonce + '", ' +
                        'response="' + response + '"'
                        },
            'URL': uri,
            'Data': currentMessage["data"]  # json.dumps({"pos": str(level)})
        }
        delay = currentMessage["delay"] if 'delay' in currentMessage else 0

        Domoticz.Debug("Sending: "+json.dumps(sendData))
        connection.Send(sendData, delay)

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage called: "+Connection.Address+" "+Connection.Name)
        # self.messageActive = False # not here, but in disconnect or timeout
        # DumpHTTPResponseToLog(Data)
        Response = {}
        currentMessage = self.connections.pop(Connection.Name)
        if "Data" in Data:
            strData = Data["Data"].decode("utf-8", "ignore")
            try:
                Response = json.loads(strData)
            except:
                Domoticz.Debug("Invalid response data: "+vars(Data))
                return

        Status = int(Data["Status"])
        retry = False

        Domoticz.Debug(json.dumps(Response))

        if (Status == 200):
            Domoticz.Debug("Good Response received from IIM: "+Connection.Address+" "+Connection.Name)
            currentMessage['authorizationError'] = False
        elif (Status == 401):
            Domoticz.Debug("Authorization error: "+Connection.Address+" "+Connection.Name)
            if currentMessage['authorizationError']:
                Domoticz.Error("Digest Authorization error.")
                currentMessage['authorizationError'] = False
            else:
                currentMessage['authorizationError'] = True
                Domoticz.Debug(Connection.Address+": "+json.dumps(Data))
                Domoticz.Debug('Header: '+Data['Headers']['WWW-Authenticate'])
                # after an Authorization Error we set nc to 0 to restart counting
                currentMessage["device"]["nc"] = 0
                auth = Data['Headers']['WWW-Authenticate']
                import re

                reg = re.compile('(\w+)[=] ?"?(\w+)"?')

                authDict = dict(reg.findall(auth))
                Domoticz.Debug(Connection.Address+": "+json.dumps(authDict))

#                self.currentMessage["device"]["nonce"]=authDict["nonce"]
                currentMessage["device"]['nonce'] = authDict["nonce"]
                self.messageActive = True
                self.connect(currentMessage)  # resend, by reconnect
                retry = True
        else:
            Domoticz.Debug("IIM returned a status: "+str(Status))

        if retry:  # We have resend the connect, so let's return
            return

        updated = False

        if "pos" in Response:
            id = Response["slide_id"]
            pos = Response["pos"]
            currentMessage['device']['slide_id'] = id
#            self.updateStatusDeviceDescription()
            self.deviceMap[id] = currentMessage['device']

            Domoticz.Debug('Searching for device {}'.format(id))

            found = False
            for idx in Devices:
                device = Devices[idx]
                if device.DeviceID == id:
                    Domoticz.Debug('Device exists')
                    found = True
                    if self.setStatus(device, pos):
                        updated = True
                    break
            if not found:
                # During installation of Slide the name is null
                name = Response["slide_id"]
                if Response["device_name"] != None and Response["device_name"] != "":
                    name = Response["device_name"]
                Domoticz.Log(
                    'New slide found: {}, device ID {}'.format(name, str(id)))

                unit = findFirstFreeUnit()

                switchType = 21 if self.nVersion>=1 else 13
                myDev = Domoticz.Device(Name=name, Unit=unit, DeviceID='{}'.format(
                    id), Type=244, Subtype=73, Switchtype=switchType, Used=1)
                myDev.Create()
                self.setStatus(myDev, pos)

                self.createCalibrationSwitch(id)

            _device = currentMessage['device']
            _device["checkMovement"] = max(_device["checkMovement"]-1, 0)
            if updated or (_device["checkMovement"] > 0):
                Domoticz.Debug('Check movement for slide {}'.format(id))
                self.getSlideInfo(_device, 1)

        self.sendMessageFromQueue()
    
    def createCalibrationSwitch(self, id):
        Domoticz.Debug('Check calibration switch for {}'.format(id))
        calibrationID = id + '_cal'
        found = False
        for idx in Devices: 
            device = Devices[idx]
            if device.DeviceID ==calibrationID:
                Domoticz.Debug('Calibration switch exists')
                found = True
                break
        if not found:
            Domoticz.Debug('Create calibration switch')
            unit = findFirstFreeUnit()
            name = 'Calibrate ' + id
            Domoticz.Device(Name=name, Unit=unit, DeviceID=calibrationID, Type=244, Subtype=73, Switchtype=9, Used=1).Create()



    def getAllSlidesInfo(self, delay=0):
        for device in self.devices:
            self.getSlideInfo(device, delay)

    def getSlideInfo(self, device, delay=0):
        Domoticz.Debug('Get Slide info: ')
#        Domoticz.Debug(json.dumps(device))
        Domoticz.Debug("getSLideInfo: "+str(device))
        cmd = {
            'device': device,
            'uri': '/rpc/Slide.GetInfo',
            'data': '',
            'delay': delay
        }
        self.addMessageToQueue(cmd)

    def calibrate(self, device):
        Domoticz.Debug('Calibrate ' + device['slide_id'])
        cmd = {
            'device': device,
            'uri': '/rpc/Slide.Calibrate',
            'data': ''
        }
        self.addMessageToQueue(cmd)

    def setStatus(self, device, pos):
        Domoticz.Debug("setStatus called with pos:" + str(pos))
        sValue = str(int(pos*100))
        nValue = 2
#        if pos < 0.13:
        nPos = 1- pos if self.nVersion >= 1 else pos
        sValue = str(int(nPos*100))
        if nPos < 0.13:
            nValue = 0
            sValue = '0'
        if nPos > 0.87:
            nValue = 1
            sValue = '100'
        if(device.sValue != sValue):
            Domoticz.Debug('Update position from {} to {}'.format(
                device.sValue, sValue))
            device.Update(nValue=nValue, sValue=sValue)
            return True
        else:
            return False
# New Domoticz versions
#- 0 = Blind Close in GUI/dzvents
#- 100 = Blind Open in GUI/dzvents
#- 90 = Show 90 in the GUI/dzvents, Send 90 to the device (Blind almost fully Open)
#- 10 = Show 10 in the GUI/dzvents, Send 10 to the device (Blind almost fully Closed)

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand called for Unit " + str(Unit) +
                       ": Parameter '" + str(Command) + "', Level: " + str(Level))
        if Unit>200:
            cmdArray = Command.split()
            if len(cmdArray) != 3:  #Command should contain three words: On calibrate <slide_id>
                Domoticz.Error('Incorrect command')
                return
            cmd = cmdArray[1]
            device = cmdArray[2]
            Domoticz.Debug('Special command: ' + cmd + ' unit ' + device)
            if cmd=='calibrate':
                self.calibrate(self.getDevice(device))
            else:
                Domoticz.Error('Unsupported command: ' + cmd)
                return
            return
        if (Command == 'Off' or Command == 'Close'):
            self.setPosition(Devices[Unit].DeviceID, 0)
        if (Command == 'On'):
            if right(Devices[Unit].DeviceID,3)=='cal':
                deviceID = Devices[Unit].DeviceID[:len(Devices[Unit].DeviceID)-4]
                self.calibrate(self.getDevice(deviceID))
                return
            self.setPosition(Devices[Unit].DeviceID, 1)
        if (Command == 'Open'):
            self.setPosition(Devices[Unit].DeviceID, 1)
        if (Command == 'Set Level'):
            self.setPosition(Devices[Unit].DeviceID, Level/100)
        if (Command == 'Stop'):
            self.slideStop(Devices[Unit].DeviceID, Level/100)

    def setPosition(self, id, level):
        Domoticz.Debug("setPosition called")
        Domoticz.Debug("Nversion "+ str(self.nVersion))
        nLevel = 1-level if self.nVersion >= 1 else level
        Domoticz.Debug("nLevel " + str(nLevel))
        device = self.getDevice(id)
        if device == None:
            return
        sendData = {'uri': '/rpc/Slide.SetPos',
                    'data': json.dumps({"pos": str(nLevel)}),
                    'device': device
                    }
        device["checkMovement"] = min(device["checkMovement"]+1, 2)
        self.addMessageToQueue(sendData)
        if device["checkMovement"] == 1:
            self.getSlideInfo(device, 2)

    def getDevice(self, id):
        Domoticz.Debug('getDevice called for ' + id)
        if id in self.deviceMap:
            return self.deviceMap[id]
        else:
            Domoticz.Error('Slide id {}  not found.'.format(id))
            Domoticz.Debug(json.dumps(self.deviceMap))
            return None

    def slideStop(self, id, level):
        Domoticz.Debug("slideStop called")
        device = self.getDevice(id)
        if device == None:
            return
        cmd = {
            'device': device,
            'uri': '/rpc/Slide.Stop',
            'data': ''
        }
        self.addMessageToQueue(cmd)

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Debug("Notification: " + Name + "," + Subject + "," + Text +
                       "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called: "+Connection.Name + ' messageActive: ' + str(self.messageActive))
#        self.connections.pop(Connection.Name, None)
        self.messageActive = False

    def onHeartbeat(self):
        Domoticz.Debug("Connections#: {}".format(len(self.connections.keys())))
        if self.hb >= self.hbCycles:
            Domoticz.Debug("onHeartbeat called")
            self.hb = 1
            self.getAllSlidesInfo()
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


def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onTimeout(Connection):
    global _plugin
    _plugin.onTimeout(Connection)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)


def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status,
                           Priority, Sound, ImageFile)


def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)


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


def DumpHTTPResponseToLog(httpResp, level=0):
    if (level == 0):
        Domoticz.Debug("HTTP Details ("+str(len(httpResp))+"):")
    indentStr = ""
    for x in range(level):
        indentStr += "----"
    if isinstance(httpResp, dict):
        for x in httpResp:
            if not isinstance(httpResp[x], dict) and not isinstance(httpResp[x], list):
                Domoticz.Debug(indentStr + ">'" + x +
                               "':'" + str(httpResp[x]) + "'")
            else:
                Domoticz.Debug(indentStr + ">'" + x + "':")
                DumpHTTPResponseToLog(httpResp[x], level+1)
    elif isinstance(httpResp, list):
        for x in httpResp:
            Domoticz.Debug(indentStr + "['" + x + "']")
    else:
        Domoticz.Debug(indentStr + ">'" + x + "':'" + str(httpResp[x]) + "'")

def findFirstFreeUnit():
    # find first free unit
    units = list(range(1, len(Devices)+2))
    for device in Devices:
        if device in units:
            units.remove(device)
    return min(units)

def right(s, amount):
    return s[-amount:]