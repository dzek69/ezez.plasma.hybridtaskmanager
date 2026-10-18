find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)
add_test(NAME panel_script COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_panel.py)

add_executable(test_icononlyapps test_icononlyapps.cpp ../src/icononlyapps.cpp)
target_include_directories(test_icononlyapps PRIVATE ../src)
target_link_libraries(test_icononlyapps PRIVATE Qt::Test Qt::Qml KF6::ConfigCore KF6::Service)
add_test(NAME icononlyapps COMMAND test_icononlyapps)
set_tests_properties(icononlyapps PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")

add_executable(test_applet test_applet.cpp)
find_package(LayerShellQt REQUIRED)
target_link_libraries(test_applet PRIVATE Qt::Test Qt::Quick Qt::Widgets Plasma::Plasma Plasma::PlasmaQuick KF6::ConfigQml KF6::I18n LayerShellQt::Interface)
target_compile_options(test_applet PRIVATE -UQT_NO_CAST_FROM_ASCII -UQT_NO_CAST_TO_ASCII)
add_dependencies(test_applet org.ezez.plasma.hybridtaskmanager)
