# Используем более свежий официальный образ Python на базе Debian Bullseye (Debian 11)
FROM python:3.9-slim-bullseye

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Устанавливаем git для клонирования репозитория
# Важно: apt-get update должен быть выполнен перед apt-get install
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Клонируем ваш репозиторий GitHub
# Замените <your_github_username> и <your_repository_name> на актуальные данные
RUN git clone https://github.com/AikyMoon/baltic_bot .

# Устанавливаем зависимости из requirements.txt
# Предполагается, что requirements.txt находится в корне вашего репозитория
# После клонирования репозитория, requirements.txt уже будет в WORKDIR /app
# Нет необходимости в отдельном COPY requirements.txt, если он уже в репозитории.
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт, если бот будет взаимодействовать с внешними сервисами через вебхуки
# EXPOSE 8080 

# Запускаем бота при запуске контейнера
# Убедитесь, что `main.py` - это файл, который запускает вашего бота
CMD ["python", "main.py"]