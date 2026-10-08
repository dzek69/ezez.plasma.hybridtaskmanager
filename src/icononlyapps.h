// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <KConfigWatcher>
#include <QObject>
#include <QStringList>
#include <QUrl>
#include <qqmlregistration.h>

// Shared across panels, with KConfig notifications for other Plasma processes.
class IconOnlyApps : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QStringList applications READ applications NOTIFY applicationsChanged)
public:
    explicit IconOnlyApps(QObject *parent = nullptr);
    QStringList applications() const;
    Q_INVOKABLE QString applicationKey(const QString &appId, const QUrl &launcherUrl) const;
    Q_INVOKABLE void setIconOnly(const QString &key, bool enabled);
Q_SIGNALS:
    void applicationsChanged();
private:
    KSharedConfig::Ptr m_config;
    KConfigWatcher::Ptr m_watcher;
};
