from alembic import command
from alembic.config import Config
from pathlib import Path
import subprocess

ALEMBIC_INI = Path(__file__).with_name("alembic.ini")

def run_auto_migrations(msg: str = "autogenerate"):
    cfg = Config(str(ALEMBIC_INI))

    try:
        print("Проверяем изменения в моделях...")

        # Генерируем миграцию (если есть изменения)
        try:
            subprocess.check_call(["alembic", "revision", "--autogenerate", "-m", msg])
        except subprocess.CalledProcessError as e:
            if "No changes detected" in str(e):
                print("Схема БД уже актуальна — новых миграций нет.")
            else:
                raise e

        print("Проверяем текущее состояние базы...")
        # Получаем текущую версию базы
        current_rev = command.current(cfg)
        # Получаем последнюю ревизию
        head_rev = command.heads(cfg)

        if current_rev != head_rev:
            print(f"База не актуальна (current: {current_rev}, head: {head_rev}). Применяем миграции...")
            command.upgrade(cfg, "head")
            print("Миграции успешно применены.")
        else:
            print("База данных уже на последней версии.")

    except subprocess.CalledProcessError as e:
        print(f"Ошибка при генерации миграции: {e}")
    except Exception as e:
        print(f"Ошибка при применении миграций: {e}")
