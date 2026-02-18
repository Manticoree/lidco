# Установка плагина LIDCO в Android Studio

## Требования

| Компонент | Минимальная версия |
|-----------|-------------------|
| Android Studio | Koala (2024.1) или новее |
| IntelliJ IDEA | 2024.1 или новее |
| JDK | 17+ |
| Gradle | 8.5+ (или используйте wrapper) |
| LIDCO сервер | Запущен (`lidco serve`) |

---

## Способ 1: Установка из собранного ZIP (рекомендуется)

### Шаг 1. Склонируйте проект (если ещё нет)

```bash
git clone https://github.com/lidco/lidco.git
cd lidco
```

### Шаг 2. Перейдите в папку плагина

```bash
cd ide/android-studio-plugin
```

### Шаг 3. Создайте Gradle Wrapper (один раз)

Если файла `gradlew` ещё нет:

```bash
gradle wrapper --gradle-version 8.5
```

> Если Gradle не установлен глобально, скачайте с https://gradle.org/install/
> или установите через пакетный менеджер:
> - **Windows (scoop):** `scoop install gradle`
> - **macOS:** `brew install gradle`
> - **Linux:** `sdk install gradle 8.5.0`

### Шаг 4. Соберите плагин

**Linux / macOS:**
```bash
./gradlew buildPlugin
```

**Windows:**
```cmd
gradlew.bat buildPlugin
```

Если сборка прошла успешно, ZIP-архив появится здесь:

```
build/distributions/lidco-intellij-plugin-0.1.0.zip
```

### Шаг 5. Установите в Android Studio

1. Откройте Android Studio
2. Перейдите в **File → Settings** (Windows/Linux) или **Android Studio → Settings** (macOS)
3. В левом меню выберите **Plugins**
4. Нажмите на **значок шестерёнки** (⚙) в правом верхнем углу панели Plugins
5. Выберите **Install Plugin from Disk...**
6. В открывшемся окне найдите и выберите файл:
   ```
   ide/android-studio-plugin/build/distributions/lidco-intellij-plugin-0.1.0.zip
   ```
7. Нажмите **OK**
8. Нажмите **Restart IDE** для перезагрузки

### Шаг 6. Проверьте установку

После перезагрузки:
- На правой боковой панели появится вкладка **LIDCO** (иконка с буквой "L")
- В правом нижнем углу статусной строки появится **LIDCO: offline** (или имя модели, если сервер запущен)
- В контекстном меню редактора (ПКМ) появится подменю **LIDCO**

---

## Способ 2: Запуск в режиме разработки

Этот способ запускает отдельную изолированную копию IDE с уже установленным плагином. Удобно для тестирования и отладки.

```bash
cd ide/android-studio-plugin

# Linux / macOS
./gradlew runIde

# Windows
gradlew.bat runIde
```

Откроется новое окно IntelliJ IDEA с предустановленным плагином LIDCO. Ваш основной Android Studio не затрагивается.

---

## Настройка плагина

### Подключение к серверу

1. Убедитесь, что LIDCO сервер запущен:
   ```bash
   lidco serve
   ```
2. В Android Studio: **File → Settings → Tools → LIDCO**
3. Проверьте настройки:

| Параметр | Значение | Описание |
|----------|----------|----------|
| **Server URL** | `http://127.0.0.1:8321` | Адрес LIDCO сервера |
| **API Token** | _(пусто)_ | Оставьте пустым для локальной разработки |
| **Default Agent** | _(пусто)_ | Пусто = автоматический выбор агента |
| **Enable SSE streaming** | ✅ | Потоковая передача ответов |

4. Нажмите **Apply** → **OK**

### Проверка подключения

- Виджет в статусной строке должен показать: **LIDCO: gpt-4o-mini** (или имя вашей модели)
- Если показывает **LIDCO: offline** — сервер не запущен или URL неверный

---

## Использование

### Чат

1. Нажмите на вкладку **LIDCO** на правой боковой панели
2. Введите сообщение в текстовое поле внизу
3. Нажмите **Enter** для отправки
4. Выберите агента из выпадающего списка (или оставьте "auto")

### Контекстное меню

1. Выделите код в редакторе
2. Нажмите правую кнопку мыши
3. В меню найдите подменю **LIDCO**:
   - **Review Code** — ревью выделенного кода
   - **Explain Code** — объяснение кода
   - **Refactor** — предложения по рефакторингу
   - **Send to Chat** — отправить код в чат

### Инлайн-дополнение

Нажмите **Alt+L** в любом месте редактора — AI вставит дополнение в позицию курсора.

---

## Решение проблем при сборке

### `gradle: command not found`

Gradle не установлен. Варианты:

```bash
# Через SDKMAN (Linux/macOS)
curl -s "https://get.sdkman.io" | bash
sdk install gradle 8.5.0

# Через Homebrew (macOS)
brew install gradle

# Через Scoop (Windows)
scoop install gradle

# Или скачайте вручную: https://gradle.org/releases/
```

### `Unsupported class file major version 65`

Нужен JDK 17+. Проверьте:

```bash
java -version
```

Установка JDK 17:

```bash
# SDKMAN
sdk install java 17.0.11-tem

# Homebrew
brew install openjdk@17

# Windows — скачайте с https://adoptium.net/
```

### `Could not resolve com.jetbrains.intellij.idea`

Проблема с сетью или прокси. Попробуйте:

```bash
# Очистить кэш
./gradlew clean --refresh-dependencies

# Если за прокси, добавьте в gradle.properties:
# systemProp.http.proxyHost=proxy.example.com
# systemProp.http.proxyPort=8080
```

### Плагин не появляется после установки

1. Перезагрузите IDE (**File → Restart**)
2. Проверьте **Settings → Plugins → Installed** — найдите "LIDCO"
3. Если плагин неактивен, нажмите **Enable** и перезагрузите
4. Проверьте совместимость версии IDE (нужна 2024.1+)

---

## Обновление плагина

1. Пересоберите: `./gradlew clean buildPlugin`
2. В Android Studio: **Settings → Plugins → ⚙ → Install Plugin from Disk**
3. Выберите новый ZIP
4. Перезагрузите IDE

---

## Удаление плагина

1. **Settings → Plugins → Installed**
2. Найдите **LIDCO**
3. Нажмите **▼ → Uninstall**
4. Перезагрузите IDE
