import os
import datetime
import asyncio
from typing import List
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, ForeignKey, Table, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
# ==================== ЗАГРУЗКА НАСТРОЕК ====================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///attendance_bot.db")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в файле .env")
# ==================== БАЗА ДАННЫХ ====================
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)
# Связующая таблица
discipline_group = Table(
    "discipline_group",
    Base.metadata,
    Column("discipline_id", Integer, ForeignKey("disciplines.id")),
    Column("group_id", Integer, ForeignKey("groups.id")),
)
class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    students = relationship("Student", back_populates="group")
    disciplines = relationship("Discipline", secondary=discipline_group, back_populates="groups")
class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    full_name = Column(String(200), nullable=False)
    telegram_id = Column(Integer, unique=True, nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"))
    group = relationship("Group", back_populates="students")
    missed = relationship("MissedClass", back_populates="student")
    grades = relationship("Grade", back_populates="student")
class Discipline(Base):
    __tablename__ = "disciplines"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    groups = relationship("Group", secondary=discipline_group, back_populates="disciplines")
    grades = relationship("Grade", back_populates="discipline")
class MissedClass(Base):
    __tablename__ = "missed_classes"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    discipline_id = Column(Integer, ForeignKey("disciplines.id"))
    date = Column(Date, default=datetime.date.today)
    is_missed = Column(Boolean, default=True)
    student = relationship("Student", back_populates="missed")
class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    discipline_id = Column(Integer, ForeignKey("disciplines.id"))
    value = Column(Integer, nullable=False)
    comment = Column(String(200), nullable=True)
    date = Column(Date, default=datetime.date.today)
    student = relationship("Student", back_populates="grades")
    discipline = relationship("Discipline", back_populates="grades")
def init_db():
    Base.metadata.create_all(engine)
    with Session() as session:
        for admin_id in ADMIN_IDS:
            if not session.query(Admin).filter(Admin.telegram_id == admin_id).first():
                session.add(Admin(telegram_id=admin_id))
        session.commit()
    print("✅ База данных инициализирована")
def is_admin(telegram_id: int) -> bool:
    with Session() as session:
        return session.query(Admin).filter(Admin.telegram_id == telegram_id).first() is not None
def get_groups():
    with Session() as session:
        return session.query(Group).all()
def add_group(name: str):
    with Session() as session:
        if not session.query(Group).filter(Group.name == name).first():
            session.add(Group(name=name))
            session.commit()
            return True
        return False
def get_disciplines():
    with Session() as session:
        return session.query(Discipline).all()
def add_discipline(name: str):
    with Session() as session:
        if not session.query(Discipline).filter(Discipline.name == name).first():
            session.add(Discipline(name=name))
            session.commit()
            return True
        return False
def assign_discipline_to_group(discipline_id: int, group_id: int):
    with Session() as session:
        discipline = session.get(Discipline, discipline_id)
        group = session.get(Group, group_id)
        if discipline and group and discipline not in group.disciplines:
            group.disciplines.append(discipline)
            session.commit()
            return True
        return False
def get_assigned_groups(discipline_id: int):
    with Session() as session:
        discipline = session.get(Discipline, discipline_id)
        return discipline.groups if discipline else []
def get_students(group_id: int):
    with Session() as session:
        return session.query(Student).filter(Student.group_id == group_id).all()
def add_student(group_id: int, full_name: str):
    with Session() as session:
        session.add(Student(full_name=full_name, group_id=group_id))
        session.commit()
def save_attendance(missed_student_ids: List[int], discipline_id: int, group_id: int):
    with Session() as session:
        today = datetime.date.today()
        students = get_students(group_id)
        for student in students:
            is_missed = student.id in missed_student_ids
            existing = session.query(MissedClass).filter(
                MissedClass.student_id == student.id,
                MissedClass.discipline_id == discipline_id,
                MissedClass.date == today
            ).first()
            if existing:
                existing.is_missed = is_missed
            else:
                session.add(MissedClass(
                    student_id=student.id,
                    discipline_id=discipline_id,
                    date=today,
                    is_missed=is_missed
                ))
        session.commit()
# ==================== ФУНКЦИИ ДЛЯ ОЦЕНОК ====================
def add_grade(student_id: int, discipline_id: int, value: int, comment: str = None):
    with Session() as session:
        grade = Grade(
            student_id=student_id,
            discipline_id=discipline_id,
            value=value,
            comment=comment,
            date=datetime.date.today()
        )
        session.add(grade)
        session.commit()
def get_student_grades(student_id: int):
    with Session() as session:
        return session.query(Grade).filter(Grade.student_id == student_id).order_by(Grade.date.desc()).all()
def get_student_average(student_id: int, discipline_id: int = None):
    with Session() as session:
        query = session.query(func.avg(Grade.value)).filter(Grade.student_id == student_id)
        if discipline_id:
            query = query.filter(Grade.discipline_id == discipline_id)
        result = query.scalar()
        return round(result, 2) if result else 0


def get_student_by_telegram(telegram_id: int):
    with Session() as session:
        return session.query(Student).filter(Student.telegram_id == telegram_id).first()
# ==================== БОТ ====================
bot = AsyncTeleBot(BOT_TOKEN, parse_mode="HTML")
# Временное хранилище
user_data = {}
attendance_data = {}
grade_data = {}
# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📚 Добавить группу", callback_data="add_group"),
        InlineKeyboardButton("📖 Добавить дисциплину", callback_data="add_discipline"),
        InlineKeyboardButton("🔗 Назначить дисциплину группе", callback_data="assign_discipline"),
        InlineKeyboardButton("👨‍🎓 Добавить студента", callback_data="add_student"),
        InlineKeyboardButton("✅ Отметить посещаемость", callback_data="attendance"),
        InlineKeyboardButton("📝 Выставить оценку", callback_data="add_grade"),
        InlineKeyboardButton("📊 Посмотреть оценки студента", callback_data="view_grades"),
    )
    return markup
def get_groups_keyboard(prefix: str):
    groups = get_groups()
    if not groups:
        return None
    markup = InlineKeyboardMarkup(row_width=1)
    for g in groups:
        markup.add(InlineKeyboardButton(g.name, callback_data=f"{prefix}_{g.id}"))
    return markup
def get_disciplines_keyboard(prefix: str):
    disciplines = get_disciplines()
    if not disciplines:
        return None
    markup = InlineKeyboardMarkup(row_width=1)
    for d in disciplines:
        markup.add(InlineKeyboardButton(d.name, callback_data=f"{prefix}_{d.id}"))
    return markup
def get_grades_keyboard():
    markup = InlineKeyboardMarkup(row_width=5)
    for grade in [5, 4, 3, 2]:
        markup.add(InlineKeyboardButton(str(grade), callback_data=f"grade_value_{grade}"))
    return markup
# ==================== ОБРАБОТЧИКИ ====================
@bot.message_handler(commands=["start"])
async def start_command(message: Message):
    if is_admin(message.from_user.id):
        await bot.send_message(
            message.chat.id,
            "🎓 Добро пожаловать в систему контроля посещаемости и успеваемости!\n\nВыберите действие:",
            reply_markup=get_main_keyboard()
        )
    else:
        student = get_student_by_telegram(message.from_user.id)
        if student:
            await bot.send_message(
                message.chat.id,
                f"👋 Здравствуйте, {student.full_name}!\n\nИспользуйте /mygrades для просмотра своих оценок."
            )
        else:
            await bot.send_message(message.chat.id, "⛔ У вас нет доступа к этому боту")
@bot.message_handler(commands=["mygrades"])
async def my_grades_command(message: Message):
    student = get_student_by_telegram(message.from_user.id)
    if not student:
        await bot.send_message(message.chat.id, "❌ Вы не зарегистрированы в системе как студент")
        return   
    grades = get_student_grades(student.id)
    if not grades:
        await bot.send_message(message.chat.id, "📋 У вас пока нет оценок")
        return   
    text = "📊 ВАШИ ОЦЕНКИ:\n\n"
    for g in grades:
        discipline = next((d for d in get_disciplines() if d.id == g.discipline_id), None)
        disc_name = discipline.name if discipline else "?"
        text += f"📚 {disc_name}: {g.value}"
        if g.comment:
            text += f" ({g.comment})"
        text += f"\n   📅 {g.date}\n\n"
    
    avg = get_student_average(student.id)
    text += f"📈 Общий средний балл: {avg}"
    await bot.send_message(message.chat.id, text)
@bot.callback_query_handler(func=lambda call: True)
async def handle_all_callbacks(call: CallbackQuery):
    await bot.answer_callback_query(call.id)
    
    data = call.data
    user_id = call.from_user.id
    
    if not is_admin(user_id):
        await bot.edit_message_text("⛔ Нет доступа", call.message.chat.id, call.message.id)
        return   
    # === ДОБАВЛЕНИЕ ГРУППЫ ===
    if data == "add_group":
        user_data[user_id] = {"action": "add_group"}
        await bot.edit_message_text(
            "📝 Введите название группы:",
            call.message.chat.id,
            call.message.id
        )    
    # === ДОБАВЛЕНИЕ ДИСЦИПЛИНЫ ===
    elif data == "add_discipline":
        user_data[user_id] = {"action": "add_discipline"}
        await bot.edit_message_text(
            "📝 Введите название дисциплины:",
            call.message.chat.id,
            call.message.id
        )   
    # === НАЗНАЧЕНИЕ ДИСЦИПЛИНЫ ГРУППЕ ===
    elif data == "assign_discipline":
        markup = get_disciplines_keyboard("assign_choose_dis")
        if markup:
            await bot.edit_message_text(
                "📚 Выберите дисциплину:",
                call.message.chat.id,
                call.message.id,
                reply_markup=markup
            )
        else:
            await bot.edit_message_text(
                "❌ Сначала добавьте дисциплину!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )   
    elif data.startswith("assign_choose_dis_"):
        discipline_id = int(data.split("_")[3])
        user_data[user_id] = {"action": "assign_discipline", "discipline_id": discipline_id}
        markup = get_groups_keyboard(f"assign_choose_group_{discipline_id}")
        if markup:
            await bot.edit_message_text(
                "👥 Выберите группу:",
                call.message.chat.id,
                call.message.id,
                reply_markup=markup
            )
        else:
            await bot.edit_message_text(
                "❌ Сначала добавьте группу!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )   
    elif data.startswith("assign_choose_group_"):
        parts = data.split("_")
        discipline_id = int(parts[3])
        group_id = int(parts[4])
        if assign_discipline_to_group(discipline_id, group_id):
            await bot.edit_message_text(
                "✅ Дисциплина назначена группе!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )
        else:
            await bot.edit_message_text(
                "❌ Дисциплина уже назначена этой группе",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )   
    # === ДОБАВЛЕНИЕ СТУДЕНТА ===
    elif data == "add_student":
        markup = get_groups_keyboard("add_student_choose_group")
        if markup:
            await bot.edit_message_text(
                "👥 Выберите группу:",
                call.message.chat.id,
                call.message.id,
                reply_markup=markup
            )
        else:
            await bot.edit_message_text(
                "❌ Сначала добавьте группу!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )    
    elif data.startswith("add_student_choose_group_"):
        group_id = int(data.split("_")[4])
        user_data[user_id] = {"action": "add_student", "group_id": group_id}
        await bot.edit_message_text(
            "📝 Введите ФИО студента (например: Иванов Иван Иванович):",
            call.message.chat.id,
            call.message.id
        )   
    # === ОТМЕТКА ПОСЕЩАЕМОСТИ ===
    elif data == "attendance":
        markup = get_disciplines_keyboard("attendance_choose_dis")
        if markup:
            await bot.edit_message_text(
                "📚 Выберите дисциплину:",
                call.message.chat.id,
                call.message.id,
                reply_markup=markup
            )
        else:
            await bot.edit_message_text(
                "❌ Сначала добавьте дисциплину!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )    
    elif data.startswith("attendance_choose_dis_"):
        discipline_id = int(data.split("_")[3])
        groups = get_assigned_groups(discipline_id)
        if not groups:
            await bot.edit_message_text(
                "❌ Дисциплина не назначена группам!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )
            return
        markup = InlineKeyboardMarkup(row_width=1)
        for g in groups:
            markup.add(InlineKeyboardButton(g.name, callback_data=f"attendance_choose_group_{discipline_id}_{g.id}"))
        await bot.edit_message_text(
            "👥 Выберите группу:",
            call.message.chat.id,
            call.message.id,
            reply_markup=markup
        )  
    elif data.startswith("attendance_choose_group_"):
        parts = data.split("_")
        discipline_id = int(parts[3])
        group_id = int(parts[4])
        students = get_students(group_id)
        if not students:
            await bot.edit_message_text(
                "❌ Нет студентов в этой группе!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )
            return        
        attendance_data[user_id] = {
            "discipline_id": discipline_id,
            "group_id": group_id,
            "missed_students": []
        }
        await show_attendance_list(call.message.chat.id, call.message.id, user_id)   
    elif data.startswith("attendance_toggle_"):
        parts = data.split("_")
        student_id = int(parts[2])
        
        if user_id not in attendance_data:
            await bot.edit_message_text(
                "❌ Сессия истекла. Начните заново.",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )
            return       
        if student_id in attendance_data[user_id]["missed_students"]:
            attendance_data[user_id]["missed_students"].remove(student_id)
        else:
            attendance_data[user_id]["missed_students"].append(student_id)
        
        await show_attendance_list(call.message.chat.id, call.message.id, user_id)    
    elif data == "attendance_save":
        if user_id not in attendance_data:
            await bot.edit_message_text(
                "❌ Нет данных для сохранения",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )
            return        
        missed = attendance_data[user_id]["missed_students"]
        discipline_id = attendance_data[user_id]["discipline_id"]
        group_id = attendance_data[user_id]["group_id"]
        
        save_attendance(missed, discipline_id, group_id)
        del attendance_data[user_id]
        
        await bot.edit_message_text(
            f"✅ Посещаемость сохранена!\n\nОтсутствовало студентов: {len(missed)}",
            call.message.chat.id,
            call.message.id,
            reply_markup=get_main_keyboard()
        )   
    elif data == "attendance_all_present":
        if user_id not in attendance_data:
            await bot.edit_message_text(
                "❌ Сессия истекла",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )
            return      
        attendance_data[user_id]["missed_students"] = []
        missed = attendance_data[user_id]["missed_students"]
        discipline_id = attendance_data[user_id]["discipline_id"]
        group_id = attendance_data[user_id]["group_id"]
        
        save_attendance(missed, discipline_id, group_id)
        del attendance_data[user_id]
        
        await bot.edit_message_text(
            "✅ Все студенты присутствуют! Посещаемость сохранена.",
            call.message.chat.id,
            call.message.id,
            reply_markup=get_main_keyboard()
        )  
    # === ВЫСТАВЛЕНИЕ ОЦЕНКИ ===
    elif data == "add_grade":
        markup = get_disciplines_keyboard("grade_choose_dis")
        if markup:
            await bot.edit_message_text(
                "📚 Выберите дисциплину:",
                call.message.chat.id,
                call.message.id,
                reply_markup=markup
            )
        else:
            await bot.edit_message_text(
                "❌ Сначала добавьте дисциплину!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )  
    elif data.startswith("grade_choose_dis_"):
        discipline_id = int(data.split("_")[3])
        groups = get_assigned_groups(discipline_id)
        if not groups:
            await bot.edit_message_text(
                "❌ Дисциплина не назначена группам!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )
            return       
        grade_data[user_id] = {"discipline_id": discipline_id}
        markup = InlineKeyboardMarkup(row_width=1)
        for g in groups:
            students = get_students(g.id)
            if students:
                markup.add(InlineKeyboardButton(g.name, callback_data=f"grade_choose_group_{discipline_id}_{g.id}"))
        
        if markup.keyboard:
            await bot.edit_message_text(
                "👥 Выберите группу:",
                call.message.chat.id,
                call.message.id,
                reply_markup=markup
            )
        else:
            await bot.edit_message_text(
                "❌ В группах нет студентов!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            ) 
    elif data.startswith("grade_choose_group_"):
        parts = data.split("_")
        discipline_id = int(parts[3])
        group_id = int(parts[4])
        students = get_students(group_id)       
        if not students:
            await bot.edit_message_text(
                "❌ Нет студентов в группе!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )
            return        
        grade_data[user_id]["group_id"] = group_id
        markup = InlineKeyboardMarkup(row_width=1)
        for s in students:
            markup.add(InlineKeyboardButton(s.full_name, callback_data=f"grade_choose_student_{s.id}"))
        
        await bot.edit_message_text(
            "🎓 Выберите студента:",
            call.message.chat.id,
            call.message.id,
            reply_markup=markup
        )    
    elif data.startswith("grade_choose_student_"):
        student_id = int(data.split("_")[3])
        grade_data[user_id]["student_id"] = student_id
        
        markup = get_grades_keyboard()
        await bot.edit_message_text(
            "📝 Выберите оценку (2-5):",
            call.message.chat.id,
            call.message.id,
            reply_markup=markup
        )    
    elif data.startswith("grade_value_"):
        value = int(data.split("_")[2])
        grade_data[user_id]["value"] = value
        grade_data[user_id]["awaiting_comment"] = True        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("⏭ Пропустить комментарий", callback_data="grade_skip_comment"))       
        await bot.edit_message_text(
            "💬 Введите комментарий к оценке (или нажмите 'Пропустить'):",
            call.message.chat.id,
            call.message.id,
            reply_markup=markup
        )   
    elif data == "grade_skip_comment":
        await save_grade_from_callback(call, None)   
    # === ПРОСМОТР ОЦЕНОК СТУДЕНТА===
    elif data == "view_grades":
        markup = get_groups_keyboard("view_grades_group")
        if markup:
            await bot.edit_message_text(
                "👥 Выберите группу для просмотра оценок:",
                call.message.chat.id,
                call.message.id,
                reply_markup=markup
            )
        else:
            await bot.edit_message_text(
                "❌ Нет групп!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )   
    elif data.startswith("view_grades_group_"):
        group_id = int(data.split("_")[3])
        students = get_students(group_id)
        if not students:
            await bot.edit_message_text(
                "❌ Нет студентов в группе!",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )
            return     
        markup = InlineKeyboardMarkup(row_width=1)
        for s in students:
            markup.add(InlineKeyboardButton(s.full_name, callback_data=f"view_grades_student_{s.id}"))      
        await bot.edit_message_text(
            "🎓 Выберите студента для просмотра оценок:",
            call.message.chat.id,
            call.message.id,
            reply_markup=markup
        )    
    elif data.startswith("view_grades_student_"):
        student_id = int(data.split("_")[3])
        grades = get_student_grades(student_id)
        
        with Session() as session:
            student = session.get(Student, student_id)
            student_name = student.full_name if student else "?"      
        if not grades:
            await bot.edit_message_text(
                f"📋 У студента {student_name} пока нет оценок",
                call.message.chat.id,
                call.message.id,
                reply_markup=get_main_keyboard()
            )
            return      
        text = f"📊 ОЦЕНКИ СТУДЕНТА\n"
        text += f"👨‍🎓 {student_name}\n\n"        
        for g in grades:
            discipline = next((d for d in get_disciplines() if d.id == g.discipline_id), None)
            disc_name = discipline.name if discipline else "?"
            text += f"📚 {disc_name}: {g.value}"
            if g.comment:
                text += f" ({g.comment})"
            text += f"\n   📅 {g.date}\n\n"       
        avg = get_student_average(student_id)
        text += f"📈 Средний балл: {avg}"        
        await bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.id,
            reply_markup=get_main_keyboard()
        )    
    elif data == "main_menu":
        await bot.edit_message_text(
            "🎓 Главное меню:",
            call.message.chat.id,
            call.message.id,
            reply_markup=get_main_keyboard()
        )
async def show_attendance_list(chat_id: int, message_id: int, user_id: int):
    discipline_id = attendance_data[user_id]["discipline_id"]
    group_id = attendance_data[user_id]["group_id"]
    missed_students = attendance_data[user_id]["missed_students"]    
    students = get_students(group_id)
    discipline = next((d for d in get_disciplines() if d.id == discipline_id), None)
    group = next((g for g in get_groups() if g.id == group_id), None)
    
    if not students:
        await bot.edit_message_text(
            "❌ Нет студентов в группе",
            chat_id,
            message_id,
            reply_markup=get_main_keyboard()
        )
        return   
    markup = InlineKeyboardMarkup(row_width=1)
    
    for s in students:
        status = "❌" if s.id in missed_students else "✅"
        markup.add(InlineKeyboardButton(
            f"{status} {s.full_name}",
            callback_data=f"attendance_toggle_{s.id}"
        ))   
    markup.add(InlineKeyboardButton("✅ Все присутствуют", callback_data="attendance_all_present"))
    markup.add(InlineKeyboardButton("💾 Сохранить посещаемость", callback_data="attendance_save"))
    markup.add(InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))   
    discipline_name = discipline.name if discipline else "?"
    group_name = group.name if group else "?"   
    await bot.edit_message_text(
        f"📊 Отметка посещаемости\n"
        f"📚 Дисциплина: {discipline_name}\n"
        f"👥 Группа: {group_name}\n\n"
        f"🎓 Нажмите на студента, чтобы отметить его отсутствующим (❌)\n"
        f"✅ - присутствует, ❌ - отсутствует\n\n"
        f"⚠️ Отмечено отсутствующих: {len(missed_students)}",
        chat_id,
        message_id,
        reply_markup=markup
    )
async def save_grade_from_callback(call, comment):
    user_id = call.from_user.id
    
    if user_id not in grade_data:
        await bot.edit_message_text(
            "❌ Ошибка: данные сессии потеряны",
            call.message.chat.id,
            call.message.id,
            reply_markup=get_main_keyboard()
        )
        return   
    discipline_id = grade_data[user_id].get("discipline_id")
    student_id = grade_data[user_id].get("student_id")
    value = grade_data[user_id].get("value")   
    if discipline_id and student_id and value:
        add_grade(student_id, discipline_id, value, comment)       
        with Session() as session:
            student = session.get(Student, student_id)
            student_name = student.full_name if student else "?"       
        await bot.edit_message_text(
            f"✅ Оценка **{value}** выставлена студенту {student_name}!",
            call.message.chat.id,
            call.message.id,
            reply_markup=get_main_keyboard()
        )
    else:
        await bot.edit_message_text(
            "❌ Ошибка: не все данные заполнены",
            call.message.chat.id,
            call.message.id,
            reply_markup=get_main_keyboard()
        )   
    if user_id in grade_data:
        del grade_data[user_id]
# ==================== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ====================
@bot.message_handler(func=lambda message: True)
async def handle_text(message: Message):
    user_id = message.from_user.id  
    # Проверка на ожидание комментария к оценке
    if user_id in grade_data and grade_data[user_id].get("awaiting_comment"):
        await save_grade_from_text(message, message.text)
        return   
    if not is_admin(user_id):
        await bot.send_message(message.chat.id, "⛔ Нет доступа")
        return  
    action_data = user_data.get(user_id)
    if not action_data:
        await bot.send_message(message.chat.id, "❌ Действие не выбрано. Нажмите /start")
        return   
    action = action_data.get("action")  
    if action == "add_group":
        if add_group(message.text.strip()):
            await bot.send_message(message.chat.id, f"✅ Группа '{message.text}' добавлена!", reply_markup=get_main_keyboard())
        else:
            await bot.send_message(message.chat.id, f"❌ Группа '{message.text}' уже существует!", reply_markup=get_main_keyboard())
        del user_data[user_id]  
    elif action == "add_discipline":
        if add_discipline(message.text.strip()):
            await bot.send_message(message.chat.id, f"✅ Дисциплина '{message.text}' добавлена!", reply_markup=get_main_keyboard())
        else:
            await bot.send_message(message.chat.id, f"❌ Дисциплина '{message.text}' уже существует!", reply_markup=get_main_keyboard())
        del user_data[user_id]   
    elif action == "add_student":
        group_id = action_data.get("group_id")
        add_student(group_id, message.text.strip())
        await bot.send_message(message.chat.id, f"✅ Студент '{message.text}' добавлен!", reply_markup=get_main_keyboard())
        del user_data[user_id]  
    else:
        await bot.send_message(message.chat.id, "❌ Неизвестное действие. Нажмите /start", reply_markup=get_main_keyboard())
async def save_grade_from_text(message, comment):
    user_id = message.from_user.id   
    if user_id not in grade_data:
        await bot.send_message(
            message.chat.id, 
            "❌ Ошибка: данные сессии потеряны", 
            reply_markup=get_main_keyboard()
        )
        return 
    discipline_id = grade_data[user_id].get("discipline_id")
    student_id = grade_data[user_id].get("student_id")
    value = grade_data[user_id].get("value")   
    if discipline_id and student_id and value:
        add_grade(student_id, discipline_id, value, comment)      
        with Session() as session:
            student = session.get(Student, student_id)
            student_name = student.full_name if student else "?"       
        await bot.send_message(
            message.chat.id,
            f"✅ Оценка **{value}** выставлена студенту {student_name}!",
            reply_markup=get_main_keyboard()
        )
    else:
        await bot.send_message(
            message.chat.id, 
            "❌ Ошибка: не все данные заполнены", 
            reply_markup=get_main_keyboard()
        ) 
    if user_id in grade_data:
        del grade_data[user_id]
# ==================== ЗАПУСК ====================
async def main():
    init_db()   
    # Добавляем тестовые данные, если их нет
    with Session() as session:
        if session.query(Group).count() == 0:
            add_group("А-01")
            add_group("Б-01")
        if session.query(Discipline).count() == 0:
            add_discipline("Программирование")
            add_discipline("Базы данных")    
    print("🤖 Бот запущен...")
    await bot.infinity_polling(request_timeout=90)
if __name__ == "__main__":
    asyncio.run(main())