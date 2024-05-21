# Slide by Innovation in Motion

Plugin for Slide by Innovation in Motion.

This plugin uses the local API (beta).  

For a Domoticz plugin that uses the cloud API see:  
http://github.com/lokonli/slide-domoticz

:warning: **Note:**  
You can't use local API and cloud API simultaneously!  
If you activate the local API on your slide the Slide App won't work anymore.

## Version
This is beta release 0.3.0. <br/>

## Slide setup
First configure your slide using the Slide app for your own WiFi network.

Switch to local API on your slide by pressing the reset button twice within 0.5 sec.<br/>


The reset button is in the hole left of the power connector, when you have the orange slide label on top.<br/>
The LED, right of the power connector, will flash a few time to indicate your slide switched to local API mode<br/>
<br/>

Write down your device code. You need it during plugin configuration. The Device code are the 8 characters printed on top of your Slide.<br/>

## Installation

Go to the Domoticz plugin folder.

    cd domoticz
    cd plugins

Clone the plugin repository:

    git clone https://github.com/lokonli/slide-domoticz-local

Restart Domoticz:

    sudo service domoticz restart

## Plugin configuration

First activate 'Allow new devices' in Domoticz.

Then add the slide-local hardware in Domoticz.

The plugin uses the following configuration fields:

Slide IP addresses: 1 or more IP addresses, semicolon separated.<br/>
Device codes: List of device codes, semicolon seperated. Number of codes must match number of IP addresses. Device code is printed on top of your Slide.<br/>
Refresh time (minutes): Polling time to update slide positions.<br/>

## Usage

Slide devices and a calibration device for each slide (push on switch) will be created automatically.

For some more information see the Wiki:

https://github.com/lokonli/slide-domoticz-local/wiki

## Todo

* Wifi configuration for new slides.  
* Auto slide discovery.

## Links

[Domoticz forum](https://www.domoticz.com/forum/viewtopic.php?f=65&t=30449)

https://slide.store/
