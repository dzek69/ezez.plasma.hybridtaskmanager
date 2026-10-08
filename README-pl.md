# Hybrid Task Manager

[English](README.md) | Polski

Wariant KDE **Icons-and-Text Task Manager** z wyborem aplikacji wyświetlanych samą ikoną. Bazuje na kodzie Plasma Desktop **6.7.5** i używa istniejącego modelu zadań KDE.

![Hybrid Task Manager z przyciskami aplikacji z samymi ikonami oraz z tekstem na jednym panelu](screenshot.png)

Kliknij prawym przyciskiem zadanie na pasku i zaznacz **Pokazuj tylko ikonę tej aplikacji** (po angielsku: **Show Only Icon for This Application**). Odznaczenie przywraca tekst. Przycisk bez tekstu zajmuje mniej miejsca. Wybór dotyczy wszystkich okien aplikacji i wszystkich instancji tego widżetu, także po ponownym uruchomieniu aplikacji lub Plasmy. Nazwy w podpowiedziach i listach okien pozostają dostępne.

Aplikację rozpoznaje wpis `.desktop` zwracany przez KDE, a gdy go brakuje — App ID / WM_CLASS. Nie trzeba wpisywać ścieżki programu, nazwy okna ani PID-u. Flatpaki korzystają ze swojego identyfikatora `.desktop`. Dla okien bez rozpoznawalnego identyfikatora opcja jest nieaktywna.

## Wymagania

Widżet zawiera plugin C++ i wymaga kompilacji ze źródeł. Potrzebne są:

- Kompilator C++20, CMake 3.22 lub nowszy, Ninja i gettext.
- Qt 6.10 lub nowsze, KDE Frameworks 6 oraz Extra CMake Modules 6.20 lub nowsze.
- Biblioteki deweloperskie Plasmy, w tym PlasmaQuick, PlasmaActivities, PlasmaActivitiesStats, KSysGuard i LibNotificationManager.
- Python 3, biblioteki deweloperskie X11, Xvfb (`xvfb-run`) i D-Bus (`dbus-run-session`) do skryptów instalacji i testów.

Przetestowano z Plasmą **6.7.5**, KDE Frameworks **6.30** i Qt **6.12** na Garuda Linux. Inne wersje mogą wymagać zmian w kodzie lub konfiguracji kompilacji.

## Instalacja

Uruchom poniższe polecenie z katalogu projektu jako zwykły użytkownik:

```bash
bash scripts/install.sh --activate
```

Skrypt buduje i testuje widżet, instaluje go w `~/.local`, robi kopię konfiguracji paneli i zastępuje wszystkie istniejące widżety **Icons-and-Text Task Manager**, zachowując ich ID, pozycje oraz ustawienia. Po zainstalowaniu zależności sama instalacja widżetu nie wymaga uprawnień roota.

Automatyczna aktywacja wymaga istniejącego widżetu Icons-and-Text Task Manager na panelu oraz sesji Plasmy zarządzanej przez usługę użytkownika systemd `plasma-plasmashell.service`. Jeśli panel zawiera tylko menedżer zadań z samymi ikonami, przed aktywacją dodaj standardowy menedżer z ikonami i tekstem.

Aktywacja na krótko restartuje powłokę Plasmy; KWin i uruchomione aplikacje pozostają aktywne. Ponowne wykonanie polecenia aktualizuje bibliotekę i przeładowuje widżet. Pomiń `--activate`, aby zbudować, przetestować i zainstalować widżet bez zmiany konfiguracji paneli i restartu Plasmy.

## Sprawdzanie stanu i cofnięcie zmiany

```bash
python3 scripts/panel.py status
python3 scripts/panel.py restore
```

`restore` przywraca standardowy menedżer w tych samych miejscach. Nie odtwarza całego starego układu pulpitu, więc późniejsze zmiany w innych widżetach zostają zachowane.

## Konfiguracja i aktualizacje

Domyślne lokalizacje plików:

- Biblioteka: `~/.local/lib/qt6/plugins/plasma/applets/org.ezez.plasma.hybridtaskmanager.so`.
- Wybór aplikacji: `~/.config/hybridtaskmanagerrc`, grupa `Appearance`, klucz `IconOnlyApplications`.
- Ścieżka do lokalnego pluginu dla Plasmy: `~/.config/systemd/user/plasma-plasmashell.service.d/50-hybrid-taskmanager.conf`.
- Kopie konfiguracji: `~/.local/state/hybrid-taskmanager/`.

Aktualizacja pakietów KDE nie nadpisuje tego widżetu. Po zmianach ABI Plasmy lub Qt może być potrzebna ponowna kompilacja. Zmiany z przyszłych wersji menedżera zadań KDE nie trafiają do tego forka automatycznie.

## Testy

Aby zbudować i uruchomić testy bez instalowania widżetu:

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build -j 2
ctest --test-dir build --output-on-failure
bash scripts/test-integration.sh
```

Testy obejmują identyfikację aplikacji, trwały zapis ustawień, akcje menu kontekstowego, etykiety, szerokości przycisków, ponowne otwarcie aplikacji, pionowe panele, wiele rzędów, grupowanie i współdzielenie ustawień między instancjami. Testy przeciągania sprawdzają drobne ruchy kursora, zatrzymanie i celową zmianę kierunku w układach LTR i RTL.

Testy integracyjne ładują rzeczywisty plugin Plasmy i model okien w Xvfb z renderowaniem programowym. Prywatna sesja D-Bus oraz tymczasowe katalogi konfiguracji, danych i pamięci podręcznej izolują je od sesji pulpitu. Testy nie uruchamiają KWin ani nie łączą się z ekranem użytkownika.

Logi i zrzuty ekranu powstają w `artifacts/`. Ostrzeżenia o niedostępnych usługach aktywności KDE lub bazie ostatnich dokumentów są spodziewane w izolowanej sesji testowej.

Skrypt testowy zgłasza niepowodzenie przy błędach asercji, komunikatach QML `TypeError`/`ReferenceError` i pętlach powiązań właściwości.

## Pochodzenie kodu i licencje

`src/` pochodzi z `applets/taskmanager` projektu [KDE plasma-desktop, tag v6.7.5](https://invent.kde.org/plasma/plasma-desktop/-/tree/v6.7.5/applets/taskmanager). Pliki konfiguracji historii aktywności pochodzą z `kcms/recentFiles`. Warunki licencyjne określają nagłówki SPDX poszczególnych plików i teksty w [LICENSES/](LICENSES/). Tłumaczenia standardowych funkcji korzystają z oryginalnego katalogu tłumaczeń KDE.
