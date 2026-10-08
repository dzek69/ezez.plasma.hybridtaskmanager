// SPDX-License-Identifier: GPL-2.0-or-later
#include <QApplication>
#include <QAction>
#include <QDir>
#include <QProcess>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQmlExpression>
#include <QQuickItem>
#include <QQuickWindow>
#include <QTest>
#include <QTemporaryDir>
#include <KConfigGroup>
#include <KConfigLoader>
#include <KConfigPropertyMap>
#include <KLocalizedString>
#include <Plasma/Corona>
#include <Plasma/Containment>
#include <PlasmaQuick/AppletQuickItem>
#include <X11/Xlib.h>
#include <X11/Xatom.h>

class TestCorona : public Plasma::Corona
{
public:
    using Plasma::Corona::Corona;
    QRect screenGeometry(int) const override { return QRect(0, 0, 1280, 800); }
};

class AppletTest : public QObject
{
    Q_OBJECT
    Plasma::Corona *corona = nullptr;
    Plasma::Containment *panel = nullptr;
    Plasma::Applet *applet = nullptr;
    PlasmaQuick::AppletQuickItem *root = nullptr;
    QQuickWindow view;
    QProcess first, second, third;
    Display *display = nullptr;
    QList<unsigned long> windows;

    void publishWindows()
    {
        XChangeProperty(display, DefaultRootWindow(display), XInternAtom(display, "_NET_CLIENT_LIST", false),
                        XA_WINDOW, 32, PropModeReplace, reinterpret_cast<const unsigned char *>(windows.constData()), windows.size());
        XFlush(display);
    }
    void registerWindow(QProcess &process)
    {
        QVERIFY(process.waitForStarted());
        QVERIFY(process.waitForReadyRead());
        const auto id = process.readLine().trimmed().toULong();
        QVERIFY(id);
        windows.append(id);
        publishWindows();
    }

    QVariant eval(const QString &code, QObject *scope = nullptr)
    {
        QQmlExpression expression(qmlContext(root), scope ? scope : root, code);
        auto result = expression.evaluate();
        if (expression.hasError()) {
            qWarning() << expression.error();
        }
        return result;
    }
    QQuickItem *task(const QString &name)
    {
        return eval("taskList.children.find(t => t.model && t.model.display === '" + name + "')").value<QQuickItem *>();
    }
    bool labelVisible(QQuickItem *item)
    {
        return eval("children.some(c => c.text !== undefined && c.visible && c.text === model.display)", item).toBool();
    }
    void screenshot(const QString &name)
    {
        QTest::qWait(350); // Let task motion and asynchronous icons finish rendering.
        const QString directory = qEnvironmentVariable("HYBRID_TEST_ARTIFACTS");
        if (!directory.isEmpty()) {
            view.grabWindow().save(directory + '/' + name + ".png");
        }
    }
    void toggleMenu(QQuickItem *item, bool expectedChecked)
    {
        eval("showContextMenu({})", item);
        QTRY_VERIFY_WITH_TIMEOUT(item->property("contextMenu").value<QObject *>(), 5000);
        auto menu = item->property("contextMenu").value<QObject *>();
        auto actionItem = menu->findChild<QObject *>("iconOnlyAction");
        QVERIFY(actionItem);
        QVERIFY(actionItem->property("enabled").toBool());
        QCOMPARE(actionItem->property("checked").toBool(), expectedChecked);
        auto action = actionItem->property("action").value<QAction *>();
        QVERIFY(action);
        action->trigger();
        QMetaObject::invokeMethod(menu, "close");
    }
private Q_SLOTS:
    void initTestCase()
    {
        display = XOpenDisplay(nullptr);
        QVERIFY(display);
        corona = new TestCorona(this);
        panel = corona->createContainment("null");
        QVERIFY(panel);
        panel->setFormFactor(Plasma::Types::Horizontal);
        panel->setLocation(Plasma::Types::BottomEdge);
        applet = panel->createApplet("org.ezez.plasma.hybridtaskmanager");
        QVERIFY(applet);
        QVERIFY2(!applet->failedToLaunch(), qPrintable(applet->launchErrorMessage()));
        auto config = applet->config().group("General");
        config.writeEntry("launchers", QStringList());
        config.writeEntry("groupingStrategy", 0);
        config.writeEntry("showOnlyCurrentScreen", false);
        config.writeEntry("showOnlyCurrentDesktop", false);
        config.writeEntry("showOnlyCurrentActivity", false);
        config.writeEntry("maxStripes", 1);
        applet->configScheme()->load();
        root = PlasmaQuick::AppletQuickItem::itemForApplet(applet);
        QVERIFY2(root, qPrintable(applet->launchErrorMessage()));
        root->setParentItem(view.contentItem());
        root->setSize(QSizeF(1000, 44));
        view.resize(1000, 44);
        view.setTitle("Hybrid Task Manager Test");
        view.setColor(QColor("#eff0f1"));
        view.show();
        first.start(QCoreApplication::applicationFilePath(), {"--fixture", "org.kde.konsole", "Terminal test"});
        second.start(QCoreApplication::applicationFilePath(), {"--fixture", "org.kde.dolphin", "Files test"});
        registerWindow(first);
        registerWindow(second);
        QTRY_VERIFY_WITH_TIMEOUT(task("Terminal test"), 15000);
        QTRY_VERIFY_WITH_TIMEOUT(task("Files test"), 15000);
    }
    void menuChangesWidthAndRestoresText()
    {
        auto terminal = task("Terminal test");
        auto files = task("Files test");
        QTRY_VERIFY(labelVisible(terminal));
        QTRY_VERIFY(labelVisible(files));
        QVERIFY(terminal->width() > 100);
        const qreal textWidth = terminal->width();
        screenshot("before");
        toggleMenu(terminal, false);
        QTRY_VERIFY(terminal->property("iconOnlyApplication").toBool());
        QTRY_VERIFY(!labelVisible(terminal));
        QTRY_VERIFY(terminal->width() <= 44);
        QVERIFY(labelVisible(files));
        QVERIFY(files->width() > 100);
        screenshot("icon-only");
        toggleMenu(terminal, true);
        QTRY_VERIFY(!terminal->property("iconOnlyApplication").toBool());
        QTRY_VERIFY(labelVisible(terminal));
        QTRY_COMPARE(terminal->width(), textWidth);
    }
    void survivesWindowRestartAndPreservesPopupLabels()
    {
        toggleMenu(task("Terminal test"), false);
        first.terminate();
        QVERIFY(first.waitForFinished());
        windows.removeFirst();
        publishWindows();
        QTRY_VERIFY(!task("Terminal test"));
        first.start(QCoreApplication::applicationFilePath(), {"--fixture", "org.kde.konsole", "Terminal reopened"});
        registerWindow(first);
        QTRY_VERIFY_WITH_TIMEOUT(task("Terminal reopened"), 10000);
        auto terminal = task("Terminal reopened");
        QTRY_VERIFY(terminal->property("iconOnlyApplication").toBool());
        QTRY_VERIFY(!labelVisible(terminal));
        QTRY_VERIFY(terminal->width() <= 44);
        terminal->setProperty("inPopup", true);
        QTRY_VERIFY(labelVisible(terminal));
        terminal->setProperty("inPopup", false);
        QTRY_VERIFY(!labelVisible(terminal));
        toggleMenu(terminal, true);
    }
    void verticalAndMultipleRows()
    {
        auto terminal = task("Terminal reopened");
        toggleMenu(terminal, false);
        panel->setFormFactor(Plasma::Types::Vertical);
        root->setSize(QSizeF(240, 700));
        view.resize(240, 700);
        QTRY_VERIFY(root->property("vertical").toBool());
        QTRY_VERIFY(!labelVisible(terminal));
        QTRY_VERIFY(labelVisible(task("Files test")));
        panel->setFormFactor(Plasma::Types::Horizontal);
        applet->configuration()->insert("maxStripes", 2);
        applet->configuration()->insert("forceStripes", true);
        root->setSize(QSizeF(1000, 88));
        view.resize(1000, 88);
        QTRY_VERIFY(!root->property("vertical").toBool());
        QTRY_VERIFY(terminal->width() <= 44);
        QVERIFY(!labelVisible(terminal));
        screenshot("two-rows");
        toggleMenu(terminal, true);
    }
    void groupedWindowsAndSecondPanel()
    {
        applet->configuration()->insert("maxStripes", 1);
        applet->configuration()->insert("forceStripes", false);
        root->setSize(QSizeF(1000, 44));
        view.resize(1000, 44);
        third.start(QCoreApplication::applicationFilePath(), {"--fixture", "org.kde.konsole", "Terminal second window"});
        registerWindow(third);
        QTRY_VERIFY(task("Terminal second window"));
        toggleMenu(task("Terminal reopened"), false);
        QTRY_VERIFY(task("Terminal second window")->property("iconOnlyApplication").toBool());
        QTRY_VERIFY(task("Terminal second window")->width() <= 44);

        auto otherApplet = panel->createApplet("org.ezez.plasma.hybridtaskmanager");
        auto otherConfig = otherApplet->config().group("General");
        otherConfig.writeEntry("launchers", QStringList());
        otherConfig.writeEntry("groupingStrategy", 0);
        otherConfig.writeEntry("showOnlyCurrentDesktop", false);
        otherConfig.writeEntry("showOnlyCurrentActivity", false);
        otherApplet->configScheme()->load();
        auto otherRoot = PlasmaQuick::AppletQuickItem::itemForApplet(otherApplet);
        QVERIFY(otherRoot);
        otherRoot->setParentItem(view.contentItem());
        otherRoot->setSize(QSizeF(1000, 44));
        otherRoot->setY(44);
        auto otherTask = [&]() {
            QQmlExpression expression(qmlContext(otherRoot), otherRoot,
                "taskList.children.find(t => t.model && t.model.display === 'Terminal reopened')");
            return expression.evaluate().value<QQuickItem *>();
        };
        QTRY_VERIFY(otherTask());
        QTRY_VERIFY(otherTask()->property("iconOnlyApplication").toBool());
        toggleMenu(task("Terminal reopened"), true);
        QTRY_VERIFY(!otherTask()->property("iconOnlyApplication").toBool());
        toggleMenu(task("Terminal reopened"), false);

        applet->configuration()->insert("onlyGroupWhenFull", false);
        applet->configuration()->insert("groupingStrategy", 1);
        auto group = [&]() {
            return eval("taskList.children.find(t => t.model && t.model.IsGroupParent)").value<QQuickItem *>();
        };
        QTRY_VERIFY(group());
        QTRY_VERIFY(group()->property("iconOnlyApplication").toBool());
        QTRY_VERIFY(group()->width() <= 44);
        QVERIFY(!labelVisible(group()));
        toggleMenu(group(), true);
        QTRY_VERIFY(labelVisible(group()));
        delete otherApplet;
        third.terminate();
        QVERIFY(third.waitForFinished());
        windows.removeLast();
        publishWindows();
    }
    void cleanupTestCase()
    {
        first.terminate();
        second.terminate();
        if (third.state() != QProcess::NotRunning) {
            third.terminate();
            third.waitForFinished();
        }
        first.waitForFinished();
        second.waitForFinished();
        view.hide();
        delete corona;
        corona = nullptr;
        XCloseDisplay(display);
    }
};

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    KLocalizedString::setApplicationDomain("plasma_applet_org.kde.plasma.taskmanager");
    if (app.arguments().value(1) == "--fixture") {
        QGuiApplication::setDesktopFileName(app.arguments().value(2));
        QQuickWindow window;
        window.setTitle(app.arguments().value(3));
        window.resize(320, 200);
        window.show();
        auto display = XOpenDisplay(nullptr);
        const QByteArray desktopFile = app.arguments().value(2).toUtf8();
        XChangeProperty(display, window.winId(), XInternAtom(display, "_KDE_NET_WM_DESKTOP_FILE", false),
                        XInternAtom(display, "UTF8_STRING", false), 8, PropModeReplace,
                        reinterpret_cast<const unsigned char *>(desktopFile.constData()), desktopFile.size());
        XFlush(display);
        printf("%lu\n", static_cast<unsigned long>(window.winId()));
        fflush(stdout);
        return app.exec();
    }
    AppletTest test;
    return QTest::qExec(&test, argc, argv);
}
#include "test_applet.moc"
