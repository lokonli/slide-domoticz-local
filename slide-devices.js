define(['app',  'app/devices/Devices.js'], function(app) {

    /* we could add here the controllers for slide api */
    app.component('slideDevices', {
        bindings: {
            devices: '<',
            onUpdate: '&',
            onCalibrate: '&'
        },
        template: '<table id="slide-devices" class="display" width="100%"></table>',
        controller: SlideDevicesController
    });

    function SlideDevicesController($element, $scope, $timeout, $uibModal, bootbox, dzSettings, dataTableDefaultSettings) {
        var $ctrl = this;
        var table;

        $ctrl.$onInit = function() {
            table = $element.find('table').dataTable(Object.assign({}, dataTableDefaultSettings, {
                order: [[0, 'asc']],
                columns: [
                    { title: 'Name', data: 'Name' },
                    { title: 'Slide ID', data: 'ID' },
                    { title: 'IP', data: 'ip' },
                    { title: 'Code', data: 'code' },
                    { title: 'Last Seen', data: 'LastUpdate', width: '150px', render: dateRenderer },
                    {
                        title: '',
                        className: 'actions-column',
                        width: '80px',
                        data: 'ID',
                        orderable: false,
                        render: actionsRenderer
                    },
                ],
            }));

            table.on('click', '.js-rename-device', function() {
                var row = table.api().row($(this).closest('tr')).data();
                var scope = $scope.$new(true);
//                scope.device = row.friendly_name;

                $uibModal
                    .open(Object.assign({ scope: scope }, renameDeviceModal)).result
                    .then($ctrl.onUpdate);

                $scope.$apply();
                return false;
            });


            table.on('click', '.js-calibrate', function() {
                var row = table.api().row($(this).closest('tr')).data();
/*
                var scope = $scope.$new(true);
//                scope.device = row.friendly_name;

//                $uibModal.open(Object.assign({ scope: scope }, setDeviceStateModal));*/
                $ctrl.onCalibrate({ device: row });

                /*$scope.$apply();*/
                return false;
            });

            table.on('click', '.js-remove-device', function() {
                var row = table.api().row($(this).closest('tr')).data();
                var scope = $scope.$new(true);
  //              scope.device = row.friendly_name;
                scope.removeDomoticzDevices = true;

                $uibModal
                    .open(Object.assign({ scope: scope }, deviceRemoveModal)).result
                    .then($ctrl.onUpdate);

                $scope.$apply();
                return false;
            })

            table.on('select.dt', function(event, row) {
                $ctrl.onSelect({ device: row.data() });
                $scope.$apply();
            });

            table.on('deselect.dt', function() {
                //Timeout to prevent flickering when we select another item in the table
                $timeout(function() {
                    if (table.api().rows({ selected: true }).count() > 0) {
                        return;
                    }

                    $ctrl.onSelect({ device: null });
                });

                $scope.$apply();
            });

            render($ctrl.devices);
        };

        $ctrl.$onChanges = function(changes) {
            if (changes.devices) {
                render($ctrl.devices);
            }
        };

        function render(items) {
            if (!table || !items) {
                return;
            }

            table.api().clear();
            table.api().rows
                .add(items)
                .draw();
        }

        function dateRenderer(data, type, row) {
            if (type === 'sort' || type === 'type' || !Number.isInteger(data)) {
                return data;
            }

            return DateTime.fromMillis(data).toFormat(dzSettings.serverDateFormat);
        }

        function actionsRenderer(data, type, row) {
            var actions = [];
            var placeholder = '<img src="../../images/empty16.png" width="16" height="16" />';

            actions.push('<button class="btn btn-icon js-calibrate" title="' + $.t('Calibrate Slide') + '"><img src="images/adjust48.png" /></button>');

/*            actions.push(placeholder)
            actions.push('<button class="btn btn-icon js-set-state" title="' + $.t('Set State') + '"><img src="images/events.png" /></button>');
            actions.push('<button class="btn btn-icon js-rename-device" title="' + $.t('Rename Device') + '"><img src="images/rename.png" /></button>');

            if (row['type'] !== 'Coordinator') {
                actions.push('<button class="btn btn-icon js-remove-device" title="' + $.t('Remove') + '"><img src="images/delete.png" /></button>');
            } else {
                actions.push(placeholder)
            }
*/

            return actions.join('&nbsp;');
        }
    }
});