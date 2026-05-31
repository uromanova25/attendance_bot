import os
import sys
import tempfile
# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(__file__))
# Импортируем функции из main.py
from main import (
    init_db, get_groups, add_group, get_disciplines, add_discipline,
    get_students, add_student, add_grade, get_student_grades,
    assign_discipline_to_group, get_assigned_groups, Session
)
from main import Group, Discipline, Student, Grade
def setup_test_db():
    """Создание временной базы данных для тестов"""
    # Создаём временный файл
    test_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    test_db_path = test_db.name
    test_db.close()   
    # Сохраняем оригинальный URL
    original_db_url = os.environ.get('DATABASE_URL', 'sqlite:///attendance_bot.db')   
    # Устанавливаем тестовую БД
    os.environ['DATABASE_URL'] = f'sqlite:///{test_db_path}'    
    # Инициализируем БД
    init_db()    
    return test_db_path, original_db_url
def cleanup_test_db(test_db_path, original_db_url):
    """Очистка после тестов"""
    os.environ['DATABASE_URL'] = original_db_url
    if os.path.exists(test_db_path):
        os.unlink(test_db_path)
def clear_db():
    """Очистка всех таблиц"""
    with Session() as session:
        session.query(Grade).delete()
        session.query(Student).delete()
        session.query(Group).delete()
        session.query(Discipline).delete()
        session.commit()
# ==================== ТЕСТ 1: Создание группы ====================
def test_create_group():
    """Тест создания группы"""
    print("\n✅ ТЕСТ 1: Создание группы")    
    clear_db()   
    # Добавляем группу
    result = add_group("ТЕСТ-01")
    assert result == True, "❌ Группа не создана"   
    # Проверяем, что группа появилась в БД
    groups = get_groups()
    assert len(groups) == 1, f"❌ Ожидалась 1 группа, получено {len(groups)}"
    assert groups[0].name == "ТЕСТ-01", f"❌ Имя группы не совпадает: {groups[0].name}"   
    # Попытка добавить дубликат
    result2 = add_group("ТЕСТ-01")
    assert result2 == False, "❌ Дубликат группы не должен добавляться"  
    print(f"   ✅ Группа '{groups[0].name}' успешно создана")
    return True
# ==================== ТЕСТ 2: Создание дисциплины ====================
def test_create_discipline():
    """Тест создания дисциплины"""
    print("\n✅ ТЕСТ 2: Создание дисциплины")  
    clear_db() 
    # Добавляем дисциплину
    result = add_discipline("Тестовая дисциплина")
    assert result == True, "❌ Дисциплина не создана"   
    # Проверяем, что дисциплина появилась в БД
    disciplines = get_disciplines()
    assert len(disciplines) == 1, f"❌ Ожидалась 1 дисциплина, получено {len(disciplines)}"
    assert disciplines[0].name == "Тестовая дисциплина", f"❌ Имя дисциплины не совпадает: {disciplines[0].name}"   
    # Попытка добавить дубликат
    result2 = add_discipline("Тестовая дисциплина")
    assert result2 == False, "❌ Дубликат дисциплины не должен добавляться"   
    print(f"   ✅ Дисциплина '{disciplines[0].name}' успешно создана")
    return True
# ==================== ТЕСТ 3: Добавление студента ====================
def test_add_student():
    """Тест добавления студента"""
    print("\n✅ ТЕСТ 3: Добавление студента")  
    clear_db()  
    # Сначала создаём группу
    add_group("ТЕСТ-ГРУППА")
    group = get_groups()[0]   
    # Добавляем студента
    add_student(group.id, "Иванов Иван Иванович")  
    # Проверяем, что студент появился в БД
    students = get_students(group.id)
    assert len(students) == 1, f"❌ Ожидался 1 студент, получено {len(students)}"
    assert students[0].full_name == "Иванов Иван Иванович", f"❌ ФИО студента не совпадает: {students[0].full_name}"
    assert students[0].group_id == group.id, "❌ student.group_id не соответствует"
    print(f"   ✅ Студент '{students[0].full_name}' добавлен в группу '{group.name}'")
    return True
# ==================== ТЕСТ 4: Назначение дисциплины группе ====================
def test_assign_discipline_to_group():
    """Тест назначения дисциплины группе"""
    print("\n✅ ТЕСТ 4: Назначение дисциплины группе")  
    clear_db()  
    # Создаём группу и дисциплину
    add_group("ТЕСТ-ГРУППА")
    add_discipline("ТЕСТ-ДИСЦИПЛИНА")  
    group = get_groups()[0]
    discipline = get_disciplines()[0] 
    # Назначаем дисциплину группе
    result = assign_discipline_to_group(discipline.id, group.id)
    assert result == True, "❌ Дисциплина не назначена группе"    
    # Проверяем, что дисциплина появилась в списке дисциплин группы
    assigned_groups = get_assigned_groups(discipline.id)
    assert len(assigned_groups) == 1, f"❌ Ожидалась 1 группа, получено {len(assigned_groups)}"
    assert assigned_groups[0].id == group.id, "❌ ID группы не совпадает"   
    # Попытка назначить повторно
    result2 = assign_discipline_to_group(discipline.id, group.id)
    assert result2 == False, "❌ Повторное назначение не должно работать"   
    print(f"   ✅ Дисциплина '{discipline.name}' назначена группе '{group.name}'")
    return True
# ==================== ТЕСТ 5: Выставление оценки ====================
def test_add_grade():
    """Тест выставления оценки студенту"""
    print("\n✅ ТЕСТ 5: Выставление оценки")  
    clear_db()    
    # Создаём необходимые сущности
    add_group("ТЕСТ-ГРУППА")
    add_discipline("ТЕСТ-ДИСЦИПЛИНА")    
    group = get_groups()[0]
    discipline = get_disciplines()[0]   
    # Добавляем студента
    add_student(group.id, "Иванов Иван Иванович")
    student = get_students(group.id)[0]    
    # Выставляем оценку
    add_grade(student.id, discipline.id, 5, "Отлично")  
    # Проверяем, что оценка появилась в БД
    grades = get_student_grades(student.id)
    assert len(grades) == 1, f"❌ Ожидалась 1 оценка, получено {len(grades)}"
    assert grades[0].value == 5, f"❌ Значение оценки не совпадает: {grades[0].value}"
    assert grades[0].comment == "Отлично", f"❌ Комментарий не совпадает: {grades[0].comment}"
    assert grades[0].student_id == student.id, "❌ student_id не совпадает"
    assert grades[0].discipline_id == discipline.id, "❌ discipline_id не совпадает"
    # Выставляем ещё одну оценку
    add_grade(student.id, discipline.id, 4, "Хорошо")
    grades = get_student_grades(student.id)
    assert len(grades) == 2, f"❌ Ожидалось 2 оценки, получено {len(grades)}"  
    print(f"   ✅ Студенту {student.full_name} выставлена оценка {grades[0].value} ({grades[0].comment})")
    return True
# ==================== ТЕСТ 6: Проверка на дубликаты ====================
def test_unique_constraints():
    """Тест проверки уникальности названий групп и дисциплин"""
    print("\n✅ ТЕСТ 6: Проверка уникальности")   
    clear_db()    
    # Добавляем группу с именем
    result1 = add_group("УНИКАЛЬНАЯ")
    assert result1 == True, "❌ Группа не создана"    
    # Пытаемся добавить группу с таким же именем
    result2 = add_group("УНИКАЛЬНАЯ")
    assert result2 == False, "❌ Дубликат группы не должен создаваться"   
    # Аналогично для дисциплины
    result3 = add_discipline("УНИКАЛЬНАЯ_ДИСЦИПЛИНА")
    assert result3 == True, "❌ Дисциплина не создана"  
    result4 = add_discipline("УНИКАЛЬНАЯ_ДИСЦИПЛИНА")
    assert result4 == False, "❌ Дубликат дисциплины не должен создаваться"   
    print("   ✅ Уникальность названий работает корректно")
    return True
# ==================== ТЕСТ 7: Получение студентов группы ====================
def test_get_students():
    """Тест получения списка студентов группы"""
    print("\n✅ ТЕСТ 7: Получение студентов группы")  
    clear_db()  
    # Создаём группу
    add_group("ТЕСТ-ГРУППА")
    group = get_groups()[0]   
    # Добавляем нескольких студентов
    students_names = ["Иванов Иван", "Петров Петр", "Сидоров Сидор"]
    for name in students_names:
        add_student(group.id, name)
    
    # Получаем студентов
    students = get_students(group.id)
    assert len(students) == 3, f"❌ Ожидалось 3 студента, получено {len(students)}"
    
    found_names = [s.full_name for s in students]
    for name in students_names:
        assert name in found_names, f"❌ Студент '{name}' не найден"
    
    print(f"   ✅ В группе '{group.name}' {len(students)} студентов")
    return True
# ==================== ЗАПУСК ТЕСТОВ ====================
def run_tests():
    """Запуск всех тестов"""
    print("\n" + "=" * 60)
    print(" ЗАПУСК ТЕСТОВ (7 тестов)")
    print("=" * 60)   
    # Инициализация временной БД
    test_db_path, original_db_url = setup_test_db()   
    # Список тестов для запуска
    tests = [
        ("Создание группы", test_create_group),
        ("Создание дисциплины", test_create_discipline),
        ("Добавление студента", test_add_student),
        ("Назначение дисциплины группе", test_assign_discipline_to_group),
        ("Выставление оценки", test_add_grade),
        ("Проверка уникальности", test_unique_constraints),
        ("Получение студентов группы", test_get_students),
    ]   
    passed = 0
    failed = 0
    failed_tests = [] 
    for name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
                failed_tests.append(name)
        except AssertionError as e:
            print(f"   ❌ Ошибка: {e}")
            failed += 1
            failed_tests.append(name)
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
            failed += 1
            failed_tests.append(name)    
    # Очистка
    cleanup_test_db(test_db_path, original_db_url)    
    print("\n" + "=" * 60)
    print(f" РЕЗУЛЬТАТ: {passed} пройдено, {failed} не пройдено")
    if failed_tests:
        print(f" Не пройдены: {', '.join(failed_tests)}")
    print("=" * 60 + "\n")
    return failed == 0
if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)