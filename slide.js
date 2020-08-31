define([
    'app',
    'app/devices/Devices.js',
    '../templates/slide-devices',
],
function(app) {

    app.component('slidePlugin', {
        templateUrl: 'app/slide/index.html',
        controller: SlidePluginController
    });

    function SlidePluginController($element, $scope, $http, Device, domoticzApi, dzNotification) {
        var $ctrl = this;

        $ctrl.refreshDomoticzDevices = refreshDomoticzDevices;

        $ctrl.$onInit = function() {
            $ctrl.devices = [];
            $ctrl.config = {};
            $ctrl.cmdDevice = null;
            $ctrl.statusDevice = null;
            $ctrl.calibrateSlide = calibrateSlide;

            refreshDomoticzDevices().then(function() {
/*                console.log('Devices: ', $ctrl.devices);
                console.log('cmd device', $ctrl.cmdDevice);
                console.log('status device', $ctrl.statusDevice);*/
            });

            $scope.$on('device_update', function(event, deviceData) {
//                console.log('device_update');
                var device = $ctrl.devices.find(function(device) {
                    return device.idx === deviceData.idx && device.Type === deviceData.Type;
                });

                if (device) {
                    Object.assign(device, deviceData);
                }
            });
        };

        function calibrateSlide(device) {
            if(device) {
                return domoticzApi.sendRequest({
                    type: 'command',
                    param: 'switchlight',
                    idx: $ctrl.cmdDevice.idx,
                    switchcmd: 'On calibrate '+device.ID
                })
                .then(domoticzApi.errorHandler)
                .then(function(response) {
//                    console.log(response);
                })
            }
        }

        function refreshDomoticzDevices() {
            return domoticzApi.sendRequest({
                type: 'devices',
                displayhidden: 1,
                filter: 'all',
                used: 'all'
            })
                .then(domoticzApi.errorHandler)
                .then(function(response) {
                    if (response.result !== undefined) {
                        $ctrl.devices = response.result
                            .filter(function(device) {
                                return device.HardwareType === 'Slide by Innovation in Motion - Local' && device.Unit<200
                            })
                            .map(function(device) {
                                dev = new Device(device);
                                dev.ip='';
                                dev.code='';
                                return dev;
                            })
                        $ctrl.statusDevice = response.result.find(function(device) {
                            return device.Unit === 255
                        });
                        $ctrl.cmdDevice = response.result.find(function(device) {
                            return device.Unit === 254
                        });

                        if($ctrl.statusDevice && $ctrl.statusDevice.Description) {
                            devices = JSON.parse($ctrl.statusDevice.Description)
                            devices.forEach(function(dev) {
                                domoticzDevice = $ctrl.devices.find(function(el) {
                                    return el.ID == dev.slide_id
                                });
                                domoticzDevice.ip=dev.ip
                                domoticzDevice.code=dev.code
                            })
                        }
                    } else {
                        $ctrl.devices = [];
                    }

                });
        }
    }
});