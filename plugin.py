# Dashticz plugin for Innovation in Motion Slide
#
# Author: lokonli
#
"""
<plugin key="iim-slide-local" name="Slide by Innovation in Motion - Local" author="lokonli" version="0.0.1" wikilink="https://github.com/lokonli/slide-domoticz-local" externallink="https://slide.store/">
    <description>
        <h2>Slide by Innovation in Motion</h2><br/>
        Plugin for Slide by Innovation in Motion.<br/>
        <br/>
        It uses the Innovation in Motion local API.<br/>
        <br/>
        This is beta release 0.0.1. <br/>
        <br/>
        <h3>Configuration</h3>
        Enable local API by pressing the reset button twice within 0.5 sec.<br/>
        The reset button is in the hole left of the power connector, when you have the orange slide label on top<br/>
        The LED, right of the power connector, will flash a few time to indicate your slide switched to local API mode<br/>
        <br/>

        Slide IP addresses: 1 or more IP addresses, semicolon separated.<br/>
        Device codes: List of device codes, semicolon seperated. Number of codes must match number of IP addresses. Device code is printed on top of your Slide.<br/>

    </description>
    <params>
           <param field="Mode2" label="Slide IP address(es)" width="200px" required="true" default="192.168.178.47"/>
           <param field="Mode3" label="Device code(s)" width="200px" required="true" default="a1b2c3d4"/>
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
# pylint:disable=undefined-variable
import Domoticz
import json
from datetime import datetime, timezone
import time
import _strptime
from hashlib import md5
from shutil import copy2
import os
import os.path

class IimSlideLocal:

    def __init__(self):
        # 0: Date including timezone info; 1: No timezone info. Workaround for strptime bug
        self._dateType = 0
        self.uifiles = ['slide.html', 'slide.js', 'slide-devices.js']

    def onStart(self):
        self.devices = []
        self.deviceMap = {}
        self.messageQueue = []
        self.connections = {}
        self.connectCount = 0
        self._tick = 0
        self._dateType = 0
        if Parameters["Mode6"] != "0":
            Domoticz.Debugging(int(Parameters["Mode6"]))
            DumpConfigToLog()
        Domoticz.Debug("onStart called")
        Domoticz.Debug("Homefolder: {}".format(Parameters["HomeFolder"]))
        Domoticz.Debug("Length {}".format(len(self.messageQueue)))
        Domoticz.Heartbeat(30)
        for f in self.uifiles:
            copy2(Parameters["HomeFolder"]+f,
                './www/templates/' + f)
        self.initialize()
 
    def initCmdDevice(self):
        if not 255 in Devices:
            Domoticz.Device(Name='$status', Unit=255, TypeName='Switch').Create()
        if not 254 in Devices:
            Domoticz.Device(Name='$cmd', Unit=254, Type=244, Subtype=73, Switchtype=7).Create() 
        Devices[255].Update(nValue=0, sValue='On', Description='')
        Devices[254].Update(nValue=0, sValue='On', Description='')
        self.updateStatusDeviceDescription()
    
    def updateStatusDeviceDescription(self):
        deviceInfoArr = []
        for device in self.devices:
            if 'slide_id' in device:
                deviceInfoArr.append( {
                    'slide_id': device['slide_id'],
                    'ip': device['ip'],
                    'code': device['code']
                })
        Devices[255].Update(nValue=1, sValue='On', Description = json.dumps(deviceInfoArr))

    def initialize(self):
        Domoticz.Debug('initializing')

        self.initCmdDevice()

        ipList = Parameters['Mode2'].split(';')
        if len(ipList) == 0:
            Domoticz.Log('IP address of Slide undefined')
            return
        codeList = Parameters['Mode3'].split(';')
        if len(codeList) != len(ipList):
            Domoticz.Error(
                'Number of Slide IPs and Slide Device codes do not match')
            return

        self.devices = [{'ip': ip, 'code': code, 'nonce': '', 'nc': 0,
                         'checkMovement': 0} for ip, code in zip(ipList, codeList)]

        Domoticz.Debug(json.dumps(self.devices, indent=4))
        self.getAllSlidesInfo()

    def onStop(self):
        Domoticz.Debug("onStop called")
        for f in self.uifiles:
            fname = './www/templates/' + f
            if os.path.exists(fname):
                os.remove(fname)

    def addMessageToQueue(self, cmd):
        cmd['authorizationError'] = False
        self.messageQueue.append(cmd)
        self.sendMessageFromQueue()

    def sendMessageFromQueue(self):
        if len(self.messageQueue) == 0:
            return
        self.connect(self.messageQueue.pop(0))

    def connect(self, msg):
        Domoticz.Debug("connect called")
        Domoticz.Debug(json.dumps(msg))
        address = msg["device"]["ip"]
        connectionName = 'Slide_'+str(self.connectCount)
        self.connectCount += 1
        self.connections[connectionName] = msg
        self.myConn = Domoticz.Connection(
            Name=connectionName, Transport="TCP/IP", Protocol="HTTP", Address=address, Port="80")
        self.myConn.Connect()

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect called")
        currentMessage = self.connections[Connection.Name] if Connection.Name in self.connections else None

        if (Status == 0):
            Domoticz.Debug("Slide connected successfully.")
        else:
            Domoticz.Error("Failed to connect ("+str(Status)+") to: " +
                           currentMessage["device"]["ip"]+" with error: "+Description)
            return
        if Connection.Name in self.connections:
            self.sendMessage(Connection)
        else:
            Domoticz.Error('Connection without info')

    def sendMessage(self, connection):
        Domoticz.Debug("sendMessage called")
        currentMessage = self.connections[connection.Name]
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

        Domoticz.Debug(json.dumps(sendData))
        connection.Send(sendData, delay)

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage called")
        # DumpHTTPResponseToLog(Data)
        Response = {}
        currentMessage = self.connections.pop(Connection.Name)
        if "Data" in Data:
            strData = Data["Data"].decode("utf-8", "ignore")
            try:
                Response = json.loads(strData)
            except:
                Domoticz.Debug("Invalid response data")
                return

        Status = int(Data["Status"])
        retry = False

        if (Status == 200):
            Domoticz.Debug("Good Response received from IIM")
#            Connection.Disconnect()
            currentMessage['authorizationError'] = False
        elif (Status == 401):
            Domoticz.Debug("Authorization error.")
            if currentMessage['authorizationError']:
                Domoticz.Error("Digest Authorization error.")
                currentMessage['authorizationError'] = False
            else:
                currentMessage['authorizationError'] = True
                Domoticz.Debug(json.dumps(Data))
                Domoticz.Debug('Header: '+Data['Headers']['WWW-Authenticate'])
                # after an Authorization Error we set nc to 0 to restart counting
                currentMessage["device"]["nc"] = 0
                auth = Data['Headers']['WWW-Authenticate']
                import re

                reg = re.compile('(\w+)[=] ?"?(\w+)"?')

                authDict = dict(reg.findall(auth))
                Domoticz.Debug(json.dumps(authDict))

#                self.currentMessage["device"]["nonce"]=authDict["nonce"]
                currentMessage["device"]['nonce'] = authDict["nonce"]
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
            self.updateStatusDeviceDescription()
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
                # find first free unit
                units = list(range(1, len(Devices)+2))
                for device in Devices:
                    if device in units:
                        units.remove(device)
                unit = min(units)

                myDev = Domoticz.Device(Name=name, Unit=unit, DeviceID='{}'.format(
                    id), Type=244, Subtype=73, Switchtype=13, Used=1)
                myDev.Create()
                self.setStatus(myDev, pos)

            _device = currentMessage['device']
            _device["checkMovement"] = max(_device["checkMovement"]-1, 0)
            if updated or (_device["checkMovement"] > 0):
                Domoticz.Debug('Check movement for slide {}'.format(id))
                self.getSlideInfo(_device, 1)

        self.sendMessageFromQueue()

    def getAllSlidesInfo(self, delay=0):
        for device in self.devices:
            self.getSlideInfo(device, delay)

    def getSlideInfo(self, device, delay=0):
        Domoticz.Debug('Get Slide info: ')
        Domoticz.Debug(json.dumps(device))
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
        Domoticz.Debug("setStatus called")
        sValue = str(int(pos*100))
        nValue = 2
        if pos < 0.13:
            nValue = 0
            sValue = '0'
        if pos > 0.87:
            nValue = 1
            sValue = '100'
        if(device.sValue != sValue):
            Domoticz.Debug('Update position from {} to {}'.format(
                device.sValue, sValue))
            device.Update(nValue=nValue, sValue=sValue)
            return True
        else:
            return False

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
        if (Command == 'Off'):
            self.setPosition(Devices[Unit].DeviceID, 0)
        if (Command == 'On'):
            self.setPosition(Devices[Unit].DeviceID, 1)
        if (Command == 'Set Level'):
            self.setPosition(Devices[Unit].DeviceID, Level/100)
        if (Command == 'Stop'):
            self.slideStop(Devices[Unit].DeviceID, Level/100)

    def setPosition(self, id, level):
        Domoticz.Debug("setPosition called")
        device = self.getDevice(id)
        if device == None:
            return
        sendData = {'uri': '/rpc/Slide.SetPos',
                    'data': json.dumps({"pos": str(level)}),
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
        Domoticz.Debug("onDisconnect called")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat called")
        self.getAllSlidesInfo()


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
