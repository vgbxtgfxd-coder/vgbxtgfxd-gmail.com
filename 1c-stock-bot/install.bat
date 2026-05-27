@echo off
echo === Установка бота складских остатков 1С ===
echo.

:: Проверяем Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ОШИБКА] Python не найден. Установи Python 3.11+ с python.org
    pause
    exit /b 1
)

:: Создаём виртуальное окружение
echo [1/4] Создаю виртуальное окружение...
python -m venv venv

:: Активируем
echo [2/4] Активирую venv...
call venv\Scripts\activate.bat

:: Устанавливаем зависимости
echo [3/4] Устанавливаю зависимости...
pip install -r requirements.txt

:: Копируем .env
echo [4/4] Настройка конфигурации...
if not exist .env (
    copy .env.example .env
    echo [!] Создан файл .env — заполни BOT_TOKEN!
) else (
    echo [OK] Файл .env уже существует
)

echo.
echo === Установка завершена ===
echo.
echo Следующие шаги:
echo 1. Заполни .env (BOT_TOKEN)
echo 2. Открой 1С в RDP-сессии на отчёте "ОСВ по номенклатуре и заказам"
echo 3. Запусти калибровку: python automation.py
echo 4. Запусти бот: python bot.py
echo.
pause
