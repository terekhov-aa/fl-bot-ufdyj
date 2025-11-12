#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправлений и нового функционала FL Bot
"""

import requests
import json
import uuid
from datetime import datetime
import sys

# Конфигурация
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api"

# Тестовые данные
TEST_USER_ID = str(uuid.uuid4())
TEST_ORDER_ID = 123456
TEST_PROJECT_DATA = {
    "id": TEST_ORDER_ID,
    "url": f"https://fl.ru/projects/{TEST_ORDER_ID}",
    "title": "Тестовый заказ",
    "summary": "Описание тестового заказа",
    "budget": "10000",
    "deadline": "2024-12-01"
}


def print_test(test_name, success, details=""):
    """Вывод результата теста"""
    status = "✓" if success else "✗"
    color = "\033[92m" if success else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{status}{reset} {test_name}")
    if details:
        print(f"  {details}")


def test_metadata_upload():
    """Тест загрузки метаданных"""
    print("\n=== Тест загрузки метаданных ===")
    
    # JSON запрос
    response = requests.post(
        f"{API_URL}/upload",
        json={"projectData": TEST_PROJECT_DATA},
        headers={"Content-Type": "application/json"}
    )
    
    success = response.status_code == 200
    print_test(
        "Загрузка метаданных через JSON",
        success,
        f"Status: {response.status_code}, Response: {response.text[:100]}"
    )
    
    # Form-data запрос
    response = requests.post(
        f"{API_URL}/upload",
        data={"projectData": json.dumps(TEST_PROJECT_DATA)}
    )
    
    success = response.status_code == 200
    print_test(
        "Загрузка метаданных через form-data",
        success,
        f"Status: {response.status_code}"
    )
    
    return response.status_code == 200


def test_file_upload():
    """Тест загрузки файла"""
    print("\n=== Тест загрузки файла ===")
    
    # Создаем тестовый файл
    test_file_content = b"Test file content for FL Bot"
    files = {
        'file': ('test_document.txt', test_file_content, 'text/plain')
    }
    data = {
        'project_id': str(TEST_ORDER_ID),
        'page_url': f'https://fl.ru/projects/{TEST_ORDER_ID}',
        'filename': 'test_document.txt'
    }
    
    response = requests.post(
        f"{API_URL}/upload",
        files=files,
        data=data
    )
    
    success = response.status_code == 200
    print_test(
        "Загрузка файла",
        success,
        f"Status: {response.status_code}, Response: {response.text[:100]}"
    )
    
    return success


def test_create_user():
    """Тест создания пользователя"""
    print("\n=== Тест создания пользователя ===")
    
    response = requests.post(
        f"{API_URL}/users/",
        json={
            "uid": TEST_USER_ID,
            "competencies_text": "Python, FastAPI, PostgreSQL",
            "categories": ["backend", "api", "database"]
        }
    )
    
    # Пользователь может уже существовать, это нормально
    success = response.status_code in [200, 201, 422]
    print_test(
        "Создание пользователя",
        success,
        f"Status: {response.status_code}, User ID: {TEST_USER_ID}"
    )
    
    return True


def test_create_feedback():
    """Тест создания отклика на заказ"""
    print("\n=== Тест создания отклика ===")
    
    # Сначала создаем пользователя и заказ
    test_create_user()
    test_metadata_upload()
    
    # Создаем отклик
    feedback_data = {
        "order_id": TEST_ORDER_ID,
        "user_id": TEST_USER_ID,
        "feedback_text": "Готов выполнить этот заказ. Имею большой опыт в разработке подобных систем."
    }
    
    response = requests.post(
        f"{API_URL}/feedbacks/",
        json=feedback_data
    )
    
    success = response.status_code == 200
    print_test(
        "Создание отклика",
        success,
        f"Status: {response.status_code}"
    )
    
    if success:
        feedback_id = response.json().get('id')
        print(f"  Created feedback ID: {feedback_id}")
        return feedback_id
    
    return None


def test_duplicate_feedback():
    """Тест защиты от дублирующих откликов"""
    print("\n=== Тест защиты от дублирования ===")
    
    feedback_data = {
        "order_id": TEST_ORDER_ID,
        "user_id": TEST_USER_ID,
        "feedback_text": "Попытка создать второй отклик"
    }
    
    response = requests.post(
        f"{API_URL}/feedbacks/",
        json=feedback_data
    )
    
    # Должна вернуться ошибка 400
    success = response.status_code == 400
    print_test(
        "Защита от дублирующих откликов",
        success,
        f"Status: {response.status_code} (ожидается 400)"
    )
    
    return success


def test_get_order_feedbacks():
    """Тест получения откликов на заказ"""
    print("\n=== Тест получения откликов на заказ ===")
    
    response = requests.get(
        f"{API_URL}/feedbacks/order/{TEST_ORDER_ID}"
    )
    
    success = response.status_code == 200
    print_test(
        "Получение откликов на заказ",
        success,
        f"Status: {response.status_code}"
    )
    
    if success:
        data = response.json()
        print(f"  Найдено откликов: {len(data.get('items', []))}")
    
    return success


def test_get_user_feedbacks():
    """Тест получения откликов пользователя"""
    print("\n=== Тест получения откликов пользователя ===")
    
    response = requests.get(
        f"{API_URL}/feedbacks/user/{TEST_USER_ID}"
    )
    
    success = response.status_code == 200
    print_test(
        "Получение откликов пользователя",
        success,
        f"Status: {response.status_code}"
    )
    
    if success:
        data = response.json()
        print(f"  Найдено откликов: {len(data.get('items', []))}")
    
    return success


def test_update_feedback_status(feedback_id):
    """Тест изменения статуса отклика"""
    print("\n=== Тест изменения статуса отклика ===")
    
    if not feedback_id:
        print_test("Изменение статуса отклика", False, "Нет ID отклика для теста")
        return False
    
    response = requests.patch(
        f"{API_URL}/feedbacks/{feedback_id}/status",
        params={"status": "accepted"}
    )
    
    success = response.status_code == 200
    print_test(
        "Изменение статуса на 'accepted'",
        success,
        f"Status: {response.status_code}"
    )
    
    return success


def test_get_orders():
    """Тест получения списка заказов"""
    print("\n=== Тест получения заказов ===")
    
    response = requests.get(
        f"{API_URL}/orders",
        params={"limit": 10, "offset": 0}
    )
    
    success = response.status_code == 200
    print_test(
        "Получение списка заказов",
        success,
        f"Status: {response.status_code}"
    )
    
    if success:
        data = response.json()
        print(f"  Найдено заказов: {len(data.get('items', []))}")
    
    return success


def main():
    """Основная функция тестирования"""
    print("=" * 50)
    print("FL Bot API - Тестирование исправлений")
    print("=" * 50)
    print(f"API URL: {API_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    print(f"Test Order ID: {TEST_ORDER_ID}")
    
    try:
        # Проверка доступности API
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code != 200:
            print(f"\n❌ API недоступен на {BASE_URL}")
            print("Убедитесь, что приложение запущено")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Не удается подключиться к {BASE_URL}")
        print("Убедитесь, что приложение запущено")
        sys.exit(1)
    
    # Выполнение тестов
    tests_passed = 0
    tests_total = 0
    
    # Тесты загрузки
    if test_metadata_upload():
        tests_passed += 1
    tests_total += 1
    
    if test_file_upload():
        tests_passed += 1
    tests_total += 1
    
    # Тесты откликов
    feedback_id = test_create_feedback()
    if feedback_id:
        tests_passed += 1
    tests_total += 1
    
    if test_duplicate_feedback():
        tests_passed += 1
    tests_total += 1
    
    if test_get_order_feedbacks():
        tests_passed += 1
    tests_total += 1
    
    if test_get_user_feedbacks():
        tests_passed += 1
    tests_total += 1
    
    if test_update_feedback_status(feedback_id):
        tests_passed += 1
    tests_total += 1
    
    # Тест заказов
    if test_get_orders():
        tests_passed += 1
    tests_total += 1
    
    # Итоги
    print("\n" + "=" * 50)
    print(f"Результаты тестирования: {tests_passed}/{tests_total} тестов пройдено")
    
    if tests_passed == tests_total:
        print("✅ Все тесты пройдены успешно!")
    else:
        print(f"⚠️ Некоторые тесты не прошли ({tests_total - tests_passed} из {tests_total})")


if __name__ == "__main__":
    main()
