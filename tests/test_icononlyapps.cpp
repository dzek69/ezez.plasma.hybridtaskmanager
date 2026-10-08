// SPDX-License-Identifier: GPL-2.0-or-later
#include "icononlyapps.h"
#include <KConfigGroup>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

class RulesTest : public QObject
{
    Q_OBJECT
private Q_SLOTS:
    void identity_data()
    {
        QTest::addColumn<QString>("appId");
        QTest::addColumn<QUrl>("url");
        QTest::addColumn<QString>("expected");
        QTest::newRow("native") << QStringLiteral("org.kde.konsole") << QUrl(QStringLiteral("applications:org.kde.konsole.desktop")) << QStringLiteral("desktop:org.kde.konsole.desktop");
        QTest::newRow("flatpak") << QStringLiteral("discord") << QUrl(QStringLiteral("applications:com.discordapp.Discord.desktop")) << QStringLiteral("desktop:com.discordapp.Discord.desktop");
        QTest::newRow("query") << QStringLiteral("discord") << QUrl(QStringLiteral("applications:com.discordapp.Discord.desktop?iconData=abc")) << QStringLiteral("desktop:com.discordapp.Discord.desktop");
        QTest::newRow("wayland") << QStringLiteral("my-app") << QUrl() << QStringLiteral("app:my-app");
        QTest::newRow("x11") << QStringLiteral("MyApp.desktop") << QUrl() << QStringLiteral("app:MyApp");
        QTest::newRow("suffix-only") << QStringLiteral("a.desktop.profile") << QUrl() << QStringLiteral("app:a.desktop.profile");
        QTest::newRow("unknown") << QStringLiteral("") << QUrl() << QStringLiteral("");
        QTest::newRow("empty-id") << QStringLiteral(".desktop") << QUrl() << QStringLiteral("");
        QTest::newRow("no-binary-match") << QStringLiteral("") << QUrl(QStringLiteral("file:///usr/bin/sh")) << QStringLiteral("");
        QTest::newRow("unregistered-desktop") << QStringLiteral("CustomApp") << QUrl(QStringLiteral("file:///not-installed/my-app.desktop")) << QStringLiteral("file:/not-installed/my-app.desktop");
    }
    void identity()
    {
        QFETCH(QString, appId);
        QFETCH(QUrl, url);
        QFETCH(QString, expected);
        IconOnlyApps rules;
        QCOMPARE(rules.applicationKey(appId, url), expected);
    }
    void togglePersistsAndPreservesOtherApps()
    {
        IconOnlyApps rules;
        QSignalSpy changed(&rules, &IconOnlyApps::applicationsChanged);
        rules.setIconOnly(QStringLiteral("desktop:first.desktop"), true);
        rules.setIconOnly(QStringLiteral("app:second"), true);
        rules.setIconOnly(QStringLiteral("desktop:first.desktop"), true);
        rules.setIconOnly(QStringLiteral(""), true);
        QCOMPARE(changed.count(), 2);
        QCOMPARE(rules.applications(), QStringList({QStringLiteral("desktop:first.desktop"), QStringLiteral("app:second")}));
        auto disk = KSharedConfig::openConfig(QStringLiteral("hybridtaskmanagerrc"), KConfig::NoGlobals);
        disk->reparseConfiguration();
        QCOMPARE(disk->group(QStringLiteral("Appearance")).readEntry("IconOnlyApplications", QStringList()), rules.applications());
        IconOnlyApps otherPanel;
        QCOMPARE(otherPanel.applications(), rules.applications());
        rules.setIconOnly(QStringLiteral("desktop:first.desktop"), false);
        QCOMPARE(otherPanel.applications(), QStringList({QStringLiteral("app:second")}));
        rules.setIconOnly(QStringLiteral("app:second"), false);
        QVERIFY(rules.applications().isEmpty());
    }
};

int main(int argc, char **argv)
{
    QTemporaryDir config;
    qputenv("XDG_CONFIG_HOME", config.path().toUtf8());
    QCoreApplication app(argc, argv);
    RulesTest test;
    return QTest::qExec(&test, argc, argv);
}
#include "test_icononlyapps.moc"
