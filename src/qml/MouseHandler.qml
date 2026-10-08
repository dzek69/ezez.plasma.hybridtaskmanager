/*
    SPDX-FileCopyrightText: 2012-2016 Eike Hein <hein@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick

import org.kde.taskmanager as TaskManager
import org.kde.plasma.plasmoid
import plasma.applet.org.ezez.plasma.hybridtaskmanager as TaskManagerApplet

DropArea {
    id: dropArea
    signal urlsDropped(var urls)

    property Item target
    property Item ignoredItem
    property point reorderDirection: Qt.point(0, 0)
    property real furthestDragPosition: 0
    property Item hoveredItem
    property bool isGroupDialog: false
    property bool moved: false

    property alias handleWheelEvents: wheelHandler.handleWheelEvents

    //ignore anything that is neither internal to TaskManager or a URL list
    onEntered: event => {
        ignoredItem = null;
        if (event.formats.indexOf("text/x-plasmoidservicename") >= 0) {
            event.accepted = false;
        }
        if (target.animating) { // Not all targets have an animating property
            target.animating = false;
        }
    }

    onPositionChanged: event => {
        if (target.animating) {
            return;
        }

        // RtL horizontal TaskLists do not include the spacer (which are initial in this
        // configuration), if any, but the mouse event coordinates do. We need to subtract
        // them, or we end thinking we're dragging way right of where we actually are.
        const rtlSpacerAdjustment = target.LayoutMirroring.enabled ? tasks.width - target.width : 0;
        let above;
        if (isGroupDialog) {
            above = target.itemAt(event.x - rtlSpacerAdjustment, event.y);
        } else {
            above = target.childAt(event.x - rtlSpacerAdjustment, event.y);
        }

        if (!above) {
            hoveredItem = null;
            activationTimer.stop();

            return;
        }

        if (tasksModel.sortMode === TaskManager.TasksModel.SortManual && tasks.dragSource) {
            // Reject drags between different TaskList instances.
            if (tasks.dragSource.parent !== above.parent) {
                return;
            }

            const insertAt = above.index;

            if (tasks.dragSource !== above && tasks.dragSource.index !== insertAt) {
                // A wider neighbour can remain under the cursor after a swap.
                // Do not swap it back while continuing in the same direction,
                // even during a slow drag. Allow reversing after a deliberate
                // movement back from the furthest pointer position.
                if (above === ignoredItem) {
                    const position = event.x * reorderDirection.x + event.y * reorderDirection.y;
                    furthestDragPosition = Math.max(furthestDragPosition, position);
                    if (furthestDragPosition - position < Application.styleHints.startDragDistance) {
                        return;
                    }
                }

                const sourceCenter = tasks.dragSource.mapToItem(dropArea, tasks.dragSource.width / 2, tasks.dragSource.height / 2);
                const targetCenter = above.mapToItem(dropArea, above.width / 2, above.height / 2);
                // Follow the row/column being crossed, including mirrored
                // layouts and wrapping onto another row or column.
                const vertical = isGroupDialog || (tasks.vertical
                    ? Math.abs(targetCenter.x - sourceCenter.x) < (tasks.dragSource.width + above.width) / 2
                    : Math.abs(targetCenter.y - sourceCenter.y) >= (tasks.dragSource.height + above.height) / 2);
                reorderDirection = vertical
                    ? Qt.point(0, Math.sign(targetCenter.y - sourceCenter.y))
                    : Qt.point(Math.sign(targetCenter.x - sourceCenter.x), 0);
                furthestDragPosition = event.x * reorderDirection.x + event.y * reorderDirection.y;
                ignoredItem = above;

                if (tasks.groupDialog) {
                    tasksModel.move(tasks.dragSource.index, insertAt,
                        tasksModel.makeModelIndex(tasks.groupDialog.visualParent.index));
                } else {
                    tasksModel.move(tasks.dragSource.index, insertAt);
                }

            } else {
                // Once the cursor reaches its own delegate there is no
                // displaced neighbour left underneath it to suppress.
                ignoredItem = null;
            }
        } else if (!tasks.dragSource && hoveredItem !== above) {
            hoveredItem = above;
            activationTimer.restart();
        }
    }

    onExited: {
        ignoredItem = null;
        hoveredItem = null;
        activationTimer.stop();
    }

    onDropped: event => {
        // Reject internal drops.
        if (event.formats.indexOf("application/x-orgkdeplasmataskmanager_taskbuttonitem") >= 0) {
            event.accepted = false;
            return;
        }

        // Reject plasmoid drops.
        if (event.formats.indexOf("text/x-plasmoidservicename") >= 0) {
            event.accepted = false;
            return;
        }

        if (event.hasUrls) {
            urlsDropped(event.urls);
            return;
        }
    }

    Connections {
        target: tasks

        function onDragSourceChanged(): void {
            dropArea.ignoredItem = null;
        }
    }

    Timer {
        id: activationTimer

        interval: 250
        repeat: false

        onTriggered: {
            if (parent.hoveredItem.model.IsGroupParent) {
                TaskManagerApplet.TaskTools.createGroupDialog(parent.hoveredItem, tasks);
            } else if (!parent.hoveredItem.model.IsLauncher) {
                tasksModel.requestActivate(parent.hoveredItem.modelIndex());
            }
        }
    }

    WheelHandler {
        id: wheelHandler

        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad

        property bool handleWheelEvents: true

        enabled: handleWheelEvents && Plasmoid.configuration.wheelEnabled !== 0

        onWheel: event => {
            // magic number 15 for common "one scroll"
            // See https://doc.qt.io/qt-6/qml-qtquick-wheelhandler.html#rotation-prop
            let increment = 0;
            while (rotation >= 15) {
                rotation -= 15;
                increment++;
            }
            while (rotation <= -15) {
                rotation += 15;
                increment--;
            }
            const anchor = dropArea.target.childAt(event.x, event.y);
            if (Plasmoid.configuration.wheelEnabled === 3) {
                const loudest = anchor?.audioStreams?.reduce((loudest, stream) => Math.max(loudest, stream.volume), 0)
                const step = (pulseAudio.item.normalVolume - pulseAudio.item.minimalVolume) * pulseAudio.item.globalConfig.volumeStep / 100;
                anchor?.audioStreams?.forEach((stream) => {
                    let delta = step * increment;
                    if (loudest > 0) {
                        delta *= stream.volume / loudest;
                    }
                    const volume = stream.volume + delta;
                    console.log(volume, Math.max(pulseAudio.item.minimalVolume, Math.min(volume, pulseAudio.item.normalVolume)));
                    stream.model.Volume = Math.max(pulseAudio.item.minimalVolume, Math.min(volume, pulseAudio.item.normalVolume));
                    stream.model.Muted = volume === 0
                })
            return;
            }
            while (increment !== 0) {
                TaskManagerApplet.TaskTools.activateNextPrevTask(anchor, increment < 0, Plasmoid.configuration.wheelSkipMinimized, Plasmoid.configuration.wheelEnabled, tasks);
                increment += (increment < 0) ? 1 : -1;
            }
        }
    }
}
