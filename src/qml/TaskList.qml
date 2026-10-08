/*
    SPDX-FileCopyrightText: 2012-2013 Eike Hein <hein@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import QtQuick.Layouts

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import plasma.applet.org.ezez.plasma.hybridtaskmanager as TaskManagerApplet

GridLayout {
    property bool animating: false

    rowSpacing: 0
    columnSpacing: 0

    property int animationsRunning: 0
    onAnimationsRunningChanged: {
        animating = animationsRunning > 0;
    }

    required property int count
    required property real availableWidth
    required property real availableHeight

    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical

    readonly property real minimumWidth: children
        .filter(item => item.visible && item.width > 0)
        .reduce((minimumWidth, item) => Math.min(minimumWidth, item.width), Infinity)

    readonly property int stripeCount: {
        if (Plasmoid.configuration.maxStripes === 1 || count === 0) {
            return 1;
        }
        if (Plasmoid.configuration.forceStripes) {
            return Plasmoid.configuration.maxStripes;
        }

        // The maximum number of stripes allowed by the applet's size
        // The parent follows this layout's size, so measuring it here creates
        // a cycle through stripeCount -> columns -> width -> parent.width.
        const stripeSizeLimit = vertical
            ? Math.floor(availableWidth / Math.max(1, children[0].implicitWidth))
            : Math.floor(availableHeight / Math.max(1, children[0].implicitHeight))
        const maxStripes = Math.max(1, Math.min(Plasmoid.configuration.maxStripes, stripeSizeLimit))


        // The number of tasks that will fill a "stripe" before starting the next one
        const maxTasksPerStripe = vertical
            ? Math.max(1, Math.ceil(availableHeight / TaskManagerApplet.LayoutMetrics.preferredMinHeight()))
            : Math.max(1, Math.ceil(availableWidth / TaskManagerApplet.LayoutMetrics.preferredMinWidth()))

        return Math.min(Math.ceil(count / maxTasksPerStripe), maxStripes)
    }

    readonly property int orthogonalCount: {
        return Math.ceil(count / stripeCount);
    }

    rows: vertical ? orthogonalCount : stripeCount
    columns: vertical ? stripeCount : orthogonalCount
}
