// SPDX-License-Identifier: GPL-2.0-or-later
#include "icononlyapps.h"
#include <KConfigGroup>
#include <KService>

IconOnlyApps::IconOnlyApps(QObject *parent)
    : QObject(parent)
    , m_config(KSharedConfig::openConfig(QStringLiteral("hybridtaskmanagerrc"), KConfig::NoGlobals))
    , m_watcher(KConfigWatcher::create(m_config))
{
    connect(m_watcher.data(), &KConfigWatcher::configChanged, this,
            [this](const KConfigGroup &group, const QByteArrayList &) {
                if (group.name() == QLatin1String("Appearance")) {
                    Q_EMIT applicationsChanged();
                }
            });
}

QStringList IconOnlyApps::applications() const
{
    return m_config->group(QStringLiteral("Appearance")).readEntry("IconOnlyApplications", QStringList());
}

QString IconOnlyApps::applicationKey(const QString &appId, const QUrl &launcherUrl) const
{
    // Resolve the same .desktop entry for native apps, Flatpaks and pinned launchers.
    if (launcherUrl.scheme() == QLatin1String("applications")) {
        const QString id = launcherUrl.path();
        if (!id.isEmpty()) {
            return QStringLiteral("desktop:") + id;
        }
    } else if (launcherUrl.isLocalFile() && launcherUrl.path().endsWith(QLatin1String(".desktop"))) {
        const auto service = KService::serviceByDesktopPath(launcherUrl.toLocalFile());
        if (service) {
            return QStringLiteral("desktop:") + service->storageId();
        }
        return QStringLiteral("file:") + launcherUrl.toLocalFile();
    }

    // Unregistered Wayland/X11 apps still have an app ID (WM_CLASS on X11).
    // Never use the window title or PID: neither survives a restart reliably.
    if (!appId.isEmpty()) {
        QString id = appId;
        if (id.endsWith(QLatin1String(".desktop"))) {
            id.chop(8);
        }
        if (const auto service = KService::serviceByDesktopName(id)) {
            return QStringLiteral("desktop:") + service->storageId();
        }
        return id.isEmpty() ? QString() : QStringLiteral("app:") + id;
    }
    return {};
}

void IconOnlyApps::setIconOnly(const QString &key, bool enabled)
{
    if (key.isEmpty()) {
        return;
    }
    QStringList entries = applications();
    if (entries.contains(key) == enabled) {
        return;
    }
    entries.removeAll(key);
    if (enabled) {
        entries.append(key);
    }
    auto group = m_config->group(QStringLiteral("Appearance"));
    group.writeEntry("IconOnlyApplications", entries, KConfig::Notify);
    m_config->sync();
    Q_EMIT applicationsChanged();
}
