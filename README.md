# Hybrid Task Manager

Wariant KDE **Icons-and-Text Task Manager** z wyborem aplikacji wyświetlanych samą ikoną. Bazuje na kodzie Plasma Desktop **6.7.5** i używa istniejącego modelu zadań KDE.

Kliknij prawym przyciskiem zadanie na pasku i zaznacz **Show Only Icon for This Application** (po polsku: **Pokazuj tylko ikonę tej aplikacji**). Ponowne kliknięcie przywraca tekst. Przycisk bez tekstu zajmuje szerokość ikony. Wybór dotyczy wszystkich okien aplikacji i wszystkich instancji tego widżetu, także po ponownym uruchomieniu aplikacji lub Plasmy. Nazwy w podpowiedziach i listach okien pozostają dostępne.

Aplikację rozpoznaje wpis `.desktop` zwracany przez KDE, a gdy go brakuje — App ID / WM_CLASS. Nie trzeba wpisywać ścieżki programu, nazwy okna ani PID-u. Flatpaki korzystają ze swojego identyfikatora `.desktop`. Dla okien bez rozpoznawalnego identyfikatora opcja jest nieaktywna.

## Instalacja i cofnięcie

Wymagane są narzędzia deweloperskie Qt 6 / KDE Frameworks 6, Plasma, CMake, Ninja, gettext, kompilator C++, Python 3 i Xvfb. Na komputerze, dla którego powstał projekt, wszystkie zależności były już dostępne. Przetestowano Plasma **6.7.5**, KDE Frameworks **6.30**, Qt **6.12**, Garuda Linux.

```bash
bash scripts/install.sh --activate
```

Skrypt buduje i testuje widżet, instaluje go w `~/.local`, robi kopię konfiguracji i zastępuje standardowe tekstowe menedżery zadań, zachowując ich ID, kolejność oraz ustawienia. Wykonuje krótki restart `plasma-plasmashell.service`; nie restartuje KWin ani aplikacji. Ponowne uruchomienie skryptu aktualizuje bibliotekę i przeładowuje widżet. Bez `--activate` tylko instaluje pliki.

```bash
python3 scripts/panel.py status
python3 scripts/panel.py restore
```

`restore` przywraca standardowy menedżer w tych samych miejscach. Nie odtwarza całego starego układu pulpitu, więc późniejsze zmiany w innych widżetach zostają zachowane.

Pliki użytkownika:

- Biblioteka: `~/.local/lib/qt6/plugins/plasma/applets/org.ezez.plasma.hybridtaskmanager.so`.
- Wybór aplikacji: `~/.config/hybridtaskmanagerrc`, grupa `Appearance`, klucz `IconOnlyApplications`.
- Ścieżka do lokalnego pluginu dla Plasmy: `~/.config/systemd/user/plasma-plasmashell.service.d/50-hybrid-taskmanager.conf`.
- Kopie konfiguracji: `~/.local/state/hybrid-taskmanager/`.

Aktualizacja pakietów KDE nie nadpisuje lokalnego widżetu. Po zmianach ABI Plasmy/Qt może być potrzebna ponowna kompilacja. To lokalny fork — nowe funkcje i poprawki przyszłych wersji oryginalnego menedżera nie trafiają do niego automatycznie.

## Testy

```bash
ctest --test-dir build --output-on-failure
bash scripts/test-integration.sh
```

Testy reguł sprawdzają identyfikację aplikacji, brak dopasowania po binarce, zapis na dysku, odznaczanie i zachowanie pozostałych wpisów. Test integracyjny ładuje prawdziwy plugin Plasmy i model okien, otwiera okna testowe i wywołuje rzeczywistą akcję menu. Sprawdza etykiety, szerokości, ponowne otwarcie aplikacji, widok pionowy, dwa rzędy, grupowanie oraz współdzielenie ustawień między instancjami.

Test integracyjny używa Xvfb, renderowania programowego, prywatnego D-Bus bez aktywacji usług oraz tymczasowych katalogów konfiguracji/danych/cache. Nie uruchamia KWin i nie łączy się z ekranem użytkownika. Nieobecne w tej sesji usługi aktywności KDE mogą generować ostrzeżenia o bazie ostatnich dokumentów; nie uczestniczą w testowanej funkcji.

Logi i zrzuty testowe powstają w `artifacts/`. Test wykrywa błędy asercji, QML `TypeError`/`ReferenceError` i pętle bindingów. Podczas testowania poprawiono także istniejącą zależność cykliczną układu przy zmianie orientacji panelu.

## Pochodzenie kodu

`src/` pochodzi z `applets/taskmanager` projektu [KDE plasma-desktop, tag v6.7.5](https://invent.kde.org/plasma/plasma-desktop/-/tree/v6.7.5/applets/taskmanager). Dwa pliki konfiguracji historii aktywności pochodzą z `kcms/recentFiles`. Zachowano nagłówki SPDX i pliki licencji w `LICENSES/`. Tłumaczenia standardowych funkcji są pobierane z oryginalnego katalogu KDE.

Archiwum źródłowe: `plasma-desktop-v6.7.5.tar.gz`, SHA-256 `9c93dd185dbe761130f871e15c68896e4d740b987d779137c30f846e7926754f`.
