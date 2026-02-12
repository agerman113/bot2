"""
VK бот для мониторинга автомобилей с auto.ru и drom.ru
"""
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
import json
import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List
from parser import CarParser

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния пользователя
STATE_MAIN_MENU = 'main_menu'
STATE_CHOOSING_CITY = 'choosing_city'
STATE_ADDING_URL = 'adding_url'
STATE_SETTING_FILTERS = 'setting_filters'
STATE_PRICE_MIN = 'price_min'
STATE_PRICE_MAX = 'price_max'
STATE_YEAR_MIN = 'year_min'
STATE_YEAR_MAX = 'year_max'
STATE_CONDITION = 'condition'
STATE_DOCUMENTS = 'documents'


class VKAutoMonitorBot:
    def __init__(self, token: str, group_id: int):
        """
        Инициализация VK бота
        
        Args:
            token: Токен доступа VK сообщества
            group_id: ID группы VK
        """
        self.vk_session = vk_api.VkApi(token=token)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkLongPoll(self.vk_session)
        self.group_id = group_id
        self.parser = CarParser()
        
        self.user_data_file = 'vk_user_data.json'
        self.user_states = {}  # Состояния пользователей
        self.load_user_data()
        
    def load_user_data(self):
        """Загрузка данных пользователей"""
        if os.path.exists(self.user_data_file):
            with open(self.user_data_file, 'r', encoding='utf-8') as f:
                self.user_data = json.load(f)
        else:
            self.user_data = {}
    
    def save_user_data(self):
        """Сохранение данных пользователей"""
        with open(self.user_data_file, 'w', encoding='utf-8') as f:
            json.dump(self.user_data, f, ensure_ascii=False, indent=2)
    
    def get_user_data(self, user_id: str) -> Dict:
        """Получение данных пользователя"""
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                'city': None,
                'monitored_cars': {},
                'filters': {
                    'price_min': None,
                    'price_max': None,
                    'year_min': None,
                    'year_max': None,
                    'condition': None,  # 'new', 'used', 'any'
                    'documents': None,  # 'with_docs', 'without_docs', 'any'
                },
                'price_threshold': 5
            }
        return self.user_data[user_id]
    
    def send_message(self, user_id: int, message: str, keyboard=None, attachment=None):
        """Отправка сообщения пользователю"""
        params = {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id()
        }
        
        if keyboard:
            params['keyboard'] = keyboard.get_keyboard()
        
        if attachment:
            params['attachment'] = attachment
        
        self.vk.messages.send(**params)
    
    def create_main_menu_keyboard(self) -> VkKeyboard:
        """Создание главного меню"""
        keyboard = VkKeyboard(one_time=False)
        
        keyboard.add_button('🏙 Выбрать город', VkKeyboardColor.PRIMARY)
        keyboard.add_button('➕ Добавить объявление', VkKeyboardColor.POSITIVE)
        
        keyboard.add_line()
        keyboard.add_button('📋 Мои объявления', VkKeyboardColor.SECONDARY)
        keyboard.add_button('🔍 Фильтры', VkKeyboardColor.SECONDARY)
        
        keyboard.add_line()
        keyboard.add_button('⚙️ Настройки', VkKeyboardColor.SECONDARY)
        keyboard.add_button('❓ Помощь', VkKeyboardColor.SECONDARY)
        
        return keyboard
    
    def create_city_keyboard(self) -> VkKeyboard:
        """Создание клавиатуры выбора города"""
        keyboard = VkKeyboard(one_time=True)
        
        cities = [
            ['Москва', 'Санкт-Петербург'],
            ['Новосибирск', 'Екатеринбург'],
            ['Казань', 'Нижний Новгород'],
            ['Челябинск', 'Самара'],
            ['Омск', 'Ростов-на-Дону'],
            ['Краснодар', 'Воронеж']
        ]
        
        for row in cities:
            for i, city in enumerate(row):
                if i > 0:
                    keyboard.add_button(city, VkKeyboardColor.PRIMARY)
                else:
                    keyboard.add_line()
                    keyboard.add_button(city, VkKeyboardColor.PRIMARY)
        
        keyboard.add_line()
        keyboard.add_button('✏️ Другой город', VkKeyboardColor.SECONDARY)
        keyboard.add_button('« Назад', VkKeyboardColor.NEGATIVE)
        
        return keyboard
    
    def create_filters_keyboard(self) -> VkKeyboard:
        """Создание клавиатуры фильтров"""
        keyboard = VkKeyboard(one_time=False)
        
        keyboard.add_button('💰 Цена', VkKeyboardColor.PRIMARY)
        keyboard.add_button('📅 Год выпуска', VkKeyboardColor.PRIMARY)
        
        keyboard.add_line()
        keyboard.add_button('🚗 Состояние', VkKeyboardColor.SECONDARY)
        keyboard.add_button('📄 Документы', VkKeyboardColor.SECONDARY)
        
        keyboard.add_line()
        keyboard.add_button('🗑 Сбросить фильтры', VkKeyboardColor.NEGATIVE)
        keyboard.add_button('« Назад', VkKeyboardColor.NEGATIVE)
        
        return keyboard
    
    def create_condition_keyboard(self) -> VkKeyboard:
        """Клавиатура выбора состояния"""
        keyboard = VkKeyboard(one_time=True)
        
        keyboard.add_button('🆕 Новый', VkKeyboardColor.POSITIVE)
        keyboard.add_button('🔧 С пробегом', VkKeyboardColor.PRIMARY)
        
        keyboard.add_line()
        keyboard.add_button('🔄 Любое', VkKeyboardColor.SECONDARY)
        keyboard.add_button('« Назад', VkKeyboardColor.NEGATIVE)
        
        return keyboard
    
    def create_documents_keyboard(self) -> VkKeyboard:
        """Клавиатура выбора документов"""
        keyboard = VkKeyboard(one_time=True)
        
        keyboard.add_button('✅ С документами', VkKeyboardColor.POSITIVE)
        keyboard.add_button('❌ Без документов', VkKeyboardColor.PRIMARY)
        
        keyboard.add_line()
        keyboard.add_button('🔄 Любые', VkKeyboardColor.SECONDARY)
        keyboard.add_button('« Назад', VkKeyboardColor.NEGATIVE)
        
        return keyboard
    
    def create_back_keyboard(self) -> VkKeyboard:
        """Клавиатура с кнопкой назад"""
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('« Назад', VkKeyboardColor.NEGATIVE)
        return keyboard
    
    def format_filters(self, user_id: str) -> str:
        """Форматирование фильтров для отображения"""
        user_data = self.get_user_data(user_id)
        filters = user_data['filters']
        
        lines = []
        
        # Цена
        if filters['price_min'] or filters['price_max']:
            price_str = "💰 Цена: "
            if filters['price_min'] and filters['price_max']:
                price_str += f"{filters['price_min']:,} - {filters['price_max']:,} ₽"
            elif filters['price_min']:
                price_str += f"от {filters['price_min']:,} ₽"
            else:
                price_str += f"до {filters['price_max']:,} ₽"
            lines.append(price_str)
        
        # Год
        if filters['year_min'] or filters['year_max']:
            year_str = "📅 Год: "
            if filters['year_min'] and filters['year_max']:
                year_str += f"{filters['year_min']} - {filters['year_max']}"
            elif filters['year_min']:
                year_str += f"от {filters['year_min']}"
            else:
                year_str += f"до {filters['year_max']}"
            lines.append(year_str)
        
        # Состояние
        if filters['condition']:
            condition_map = {
                'new': '🆕 Новый',
                'used': '🔧 С пробегом',
                'any': '🔄 Любое'
            }
            lines.append(f"🚗 Состояние: {condition_map.get(filters['condition'], 'Не указано')}")
        
        # Документы
        if filters['documents']:
            docs_map = {
                'with_docs': '✅ С документами',
                'without_docs': '❌ Без документов',
                'any': '🔄 Любые'
            }
            lines.append(f"📄 Документы: {docs_map.get(filters['documents'], 'Не указано')}")
        
        if not lines:
            return "Фильтры не установлены"
        
        return "\n".join(lines)
    
    def check_filters(self, car_data: Dict, filters: Dict) -> bool:
        """Проверка соответствия авто фильтрам"""
        # Проверка цены
        if filters['price_min'] and car_data['price'] < filters['price_min']:
            return False
        if filters['price_max'] and car_data['price'] > filters['price_max']:
            return False
        
        # Проверка года
        if car_data.get('year'):
            if filters['year_min'] and car_data['year'] < filters['year_min']:
                return False
            if filters['year_max'] and car_data['year'] > filters['year_max']:
                return False
        
        # Проверка состояния
        if filters['condition'] and filters['condition'] != 'any':
            # Здесь можно добавить логику проверки состояния из парсера
            pass
        
        # Проверка документов
        if filters['documents'] and filters['documents'] != 'any':
            # Здесь можно добавить логику проверки документов из парсера
            pass
        
        return True
    
    def handle_start(self, user_id: int):
        """Обработка команды начало"""
        user_data = self.get_user_data(str(user_id))
        
        message = (
            "🚗 Добро пожаловать в Авто Мониторинг Бот!\n\n"
            "Я помогу отслеживать изменения цен на автомобили с:\n"
            "• auto.ru\n"
            "• drom.ru\n\n"
        )
        
        if user_data['city']:
            message += f"📍 Ваш город: {user_data['city']}\n"
            message += f"📊 Отслеживается: {len(user_data['monitored_cars'])} объявлений\n\n"
        else:
            message += "⚠️ Сначала выберите город\n\n"
        
        message += "Выберите действие:"
        
        self.user_states[user_id] = STATE_MAIN_MENU
        self.send_message(user_id, message, self.create_main_menu_keyboard())
    
    def handle_choose_city(self, user_id: int):
        """Выбор города"""
        message = "🏙 Выберите ваш город:\n\nГород будет использоваться для фильтрации объявлений"
        
        self.user_states[user_id] = STATE_CHOOSING_CITY
        self.send_message(user_id, message, self.create_city_keyboard())
    
    def handle_city_selected(self, user_id: int, city: str):
        """Обработка выбранного города"""
        if city == "✏️ Другой город":
            message = "✏️ Введите название вашего города:"
            self.send_message(user_id, message, self.create_back_keyboard())
            return
        
        user_data = self.get_user_data(str(user_id))
        user_data['city'] = city
        self.save_user_data()
        
        message = f"✅ Город установлен: {city}\n\nТеперь вы можете добавлять объявления!"
        
        self.user_states[user_id] = STATE_MAIN_MENU
        self.send_message(user_id, message, self.create_main_menu_keyboard())
    
    def handle_add_url(self, user_id: int):
        """Начало добавления объявления"""
        user_data = self.get_user_data(str(user_id))
        
        if not user_data['city']:
            message = "⚠️ Сначала выберите город!\n\nИспользуйте кнопку '🏙 Выбрать город'"
            self.send_message(user_id, message, self.create_main_menu_keyboard())
            return
        
        message = (
            "📎 Отправьте ссылку на объявление\n\n"
            "Поддерживаются сайты:\n"
            "• auto.ru\n"
            "• drom.ru\n\n"
            "Пример:\n"
            "https://auto.ru/cars/used/sale/kia/rio/1234567890/"
        )
        
        self.user_states[user_id] = STATE_ADDING_URL
        self.send_message(user_id, message, self.create_back_keyboard())
    
    async def handle_url_received(self, user_id: int, url: str):
        """Обработка полученного URL"""
        if not ('auto.ru' in url or 'drom.ru' in url):
            message = "❌ Неверная ссылка!\n\nОтправьте ссылку с auto.ru или drom.ru"
            self.send_message(user_id, message)
            return
        
        user_str_id = str(user_id)
        
        # Проверка дубликата
        if url in self.user_data[user_str_id]['monitored_cars']:
            message = "⚠️ Это объявление уже добавлено!"
            self.user_states[user_id] = STATE_MAIN_MENU
            self.send_message(user_id, message, self.create_main_menu_keyboard())
            return
        
        # Статус загрузки
        self.send_message(user_id, "⏳ Получаю данные об автомобиле...")
        
        # Получение данных
        car_data = await self.parser.fetch_car_data(url)
        
        if not car_data:
            message = "❌ Не удалось получить данные\n\nПроверьте URL и попробуйте снова"
            self.send_message(user_id, message)
            return
        
        # Проверка фильтров
        user_data = self.get_user_data(user_str_id)
        if not self.check_filters(car_data, user_data['filters']):
            message = (
                "⚠️ Автомобиль не соответствует вашим фильтрам!\n\n"
                f"🚗 {car_data['title']}\n"
                f"💰 Цена: {car_data['price']:,} ₽\n"
            )
            
            if car_data.get('year'):
                message += f"📅 Год: {car_data['year']}\n"
            
            message += "\n❓ Всё равно добавить? Отправьте ссылку ещё раз"
            
            # Временно разрешаем добавление
            self.send_message(user_id, message)
            return
        
        # Сохранение
        self.user_data[user_str_id]['monitored_cars'][url] = {
            'title': car_data['title'],
            'price': car_data['price'],
            'initial_price': car_data['price'],
            'site': car_data['site'],
            'year': car_data.get('year'),
            'mileage': car_data.get('mileage'),
            'location': car_data.get('location'),
            'added_date': datetime.now().isoformat(),
            'last_check': datetime.now().isoformat(),
            'price_history': [{
                'price': car_data['price'],
                'date': datetime.now().isoformat()
            }]
        }
        self.save_user_data()
        
        # Сообщение об успехе
        message = (
            f"✅ Объявление добавлено!\n\n"
            f"🚗 {car_data['title']}\n"
            f"💰 Цена: {car_data['price']:,} ₽\n"
            f"🌐 Сайт: {car_data['site']}\n"
        )
        
        if car_data.get('year'):
            message += f"📅 Год: {car_data['year']}\n"
        if car_data.get('mileage'):
            message += f"🛣 Пробег: {car_data['mileage']:,} км\n"
        if car_data.get('location'):
            message += f"📍 Место: {car_data['location']}\n"
        
        message += "\n💡 Я буду отслеживать изменения цены!"
        
        self.user_states[user_id] = STATE_MAIN_MENU
        self.send_message(user_id, message, self.create_main_menu_keyboard())
    
    def handle_list_cars(self, user_id: int):
        """Список отслеживаемых объявлений"""
        user_data = self.get_user_data(str(user_id))
        
        if not user_data['monitored_cars']:
            message = "📋 У вас нет отслеживаемых объявлений\n\nДобавьте первое объявление!"
            self.send_message(user_id, message, self.create_main_menu_keyboard())
            return
        
        message = "📋 Ваши объявления:\n\n"
        
        for i, (url, car) in enumerate(user_data['monitored_cars'].items(), 1):
            price_change = car['price'] - car['initial_price']
            change_emoji = "📉" if price_change < 0 else "📈" if price_change > 0 else "➖"
            
            message += f"{i}. {car['title']}\n"
            message += f"   💰 {car['price']:,} ₽"
            
            if price_change != 0:
                change_percent = (price_change / car['initial_price']) * 100
                message += f" {change_emoji} {price_change:+,} ₽ ({change_percent:+.1f}%)"
            
            message += f"\n   🌐 {car['site']}"
            
            if car.get('location'):
                message += f"\n   📍 {car['location']}"
            
            message += f"\n   🔗 {url}\n\n"
        
        # Если сообщение слишком длинное, разбиваем на части
        if len(message) > 4096:
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for part in parts[:-1]:
                self.send_message(user_id, part)
            self.send_message(user_id, parts[-1], self.create_main_menu_keyboard())
        else:
            self.send_message(user_id, message, self.create_main_menu_keyboard())
    
    def handle_filters_menu(self, user_id: int):
        """Меню фильтров"""
        user_data = self.get_user_data(str(user_id))
        
        message = "🔍 Фильтры поиска\n\n"
        message += self.format_filters(str(user_id))
        message += "\n\nВыберите параметр для настройки:"
        
        self.user_states[user_id] = STATE_SETTING_FILTERS
        self.send_message(user_id, message, self.create_filters_keyboard())
    
    def handle_price_filter(self, user_id: int):
        """Настройка фильтра цены"""
        message = "💰 Установка диапазона цены\n\nВведите минимальную цену в рублях (или 0 для пропуска):"
        
        self.user_states[user_id] = STATE_PRICE_MIN
        self.send_message(user_id, message, self.create_back_keyboard())
    
    def handle_price_min(self, user_id: int, value: str):
        """Обработка минимальной цены"""
        try:
            price = int(value.replace(' ', '').replace(',', ''))
            if price < 0:
                raise ValueError
            
            user_data = self.get_user_data(str(user_id))
            user_data['filters']['price_min'] = price if price > 0 else None
            self.save_user_data()
            
            message = "💰 Введите максимальную цену в рублях (или 0 для пропуска):"
            self.user_states[user_id] = STATE_PRICE_MAX
            self.send_message(user_id, message, self.create_back_keyboard())
            
        except ValueError:
            message = "❌ Неверный формат!\n\nВведите число (например: 500000):"
            self.send_message(user_id, message)
    
    def handle_price_max(self, user_id: int, value: str):
        """Обработка максимальной цены"""
        try:
            price = int(value.replace(' ', '').replace(',', ''))
            if price < 0:
                raise ValueError
            
            user_data = self.get_user_data(str(user_id))
            user_data['filters']['price_max'] = price if price > 0 else None
            self.save_user_data()
            
            message = f"✅ Фильтр цены установлен!\n\n{self.format_filters(str(user_id))}"
            self.user_states[user_id] = STATE_SETTING_FILTERS
            self.send_message(user_id, message, self.create_filters_keyboard())
            
        except ValueError:
            message = "❌ Неверный формат!\n\nВведите число (например: 1500000):"
            self.send_message(user_id, message)
    
    def handle_year_filter(self, user_id: int):
        """Настройка фильтра года"""
        message = "📅 Установка диапазона года выпуска\n\nВведите минимальный год (или 0 для пропуска):"
        
        self.user_states[user_id] = STATE_YEAR_MIN
        self.send_message(user_id, message, self.create_back_keyboard())
    
    def handle_year_min(self, user_id: int, value: str):
        """Обработка минимального года"""
        try:
            year = int(value)
            current_year = datetime.now().year
            
            if year != 0 and (year < 1900 or year > current_year):
                raise ValueError
            
            user_data = self.get_user_data(str(user_id))
            user_data['filters']['year_min'] = year if year > 0 else None
            self.save_user_data()
            
            message = "📅 Введите максимальный год (или 0 для пропуска):"
            self.user_states[user_id] = STATE_YEAR_MAX
            self.send_message(user_id, message, self.create_back_keyboard())
            
        except ValueError:
            message = f"❌ Неверный год!\n\nВведите год от 1900 до {datetime.now().year}:"
            self.send_message(user_id, message)
    
    def handle_year_max(self, user_id: int, value: str):
        """Обработка максимального года"""
        try:
            year = int(value)
            current_year = datetime.now().year
            
            if year != 0 and (year < 1900 or year > current_year):
                raise ValueError
            
            user_data = self.get_user_data(str(user_id))
            user_data['filters']['year_max'] = year if year > 0 else None
            self.save_user_data()
            
            message = f"✅ Фильтр года установлен!\n\n{self.format_filters(str(user_id))}"
            self.user_states[user_id] = STATE_SETTING_FILTERS
            self.send_message(user_id, message, self.create_filters_keyboard())
            
        except ValueError:
            message = f"❌ Неверный год!\n\nВведите год от 1900 до {datetime.now().year}:"
            self.send_message(user_id, message)
    
    def handle_condition_filter(self, user_id: int):
        """Настройка фильтра состояния"""
        message = "🚗 Выберите состояние автомобиля:"
        
        self.user_states[user_id] = STATE_CONDITION
        self.send_message(user_id, message, self.create_condition_keyboard())
    
    def handle_condition_selected(self, user_id: int, condition_text: str):
        """Обработка выбранного состояния"""
        condition_map = {
            '🆕 Новый': 'new',
            '🔧 С пробегом': 'used',
            '🔄 Любое': 'any'
        }
        
        condition = condition_map.get(condition_text)
        if condition:
            user_data = self.get_user_data(str(user_id))
            user_data['filters']['condition'] = condition
            self.save_user_data()
            
            message = f"✅ Фильтр состояния установлен!\n\n{self.format_filters(str(user_id))}"
            self.user_states[user_id] = STATE_SETTING_FILTERS
            self.send_message(user_id, message, self.create_filters_keyboard())
    
    def handle_documents_filter(self, user_id: int):
        """Настройка фильтра документов"""
        message = "📄 Выберите наличие документов:"
        
        self.user_states[user_id] = STATE_DOCUMENTS
        self.send_message(user_id, message, self.create_documents_keyboard())
    
    def handle_documents_selected(self, user_id: int, docs_text: str):
        """Обработка выбранных документов"""
        docs_map = {
            '✅ С документами': 'with_docs',
            '❌ Без документов': 'without_docs',
            '🔄 Любые': 'any'
        }
        
        docs = docs_map.get(docs_text)
        if docs:
            user_data = self.get_user_data(str(user_id))
            user_data['filters']['documents'] = docs
            self.save_user_data()
            
            message = f"✅ Фильтр документов установлен!\n\n{self.format_filters(str(user_id))}"
            self.user_states[user_id] = STATE_SETTING_FILTERS
            self.send_message(user_id, message, self.create_filters_keyboard())
    
    def handle_clear_filters(self, user_id: int):
        """Сброс фильтров"""
        user_data = self.get_user_data(str(user_id))
        user_data['filters'] = {
            'price_min': None,
            'price_max': None,
            'year_min': None,
            'year_max': None,
            'condition': None,
            'documents': None,
        }
        self.save_user_data()
        
        message = "🗑 Все фильтры сброшены!"
        self.user_states[user_id] = STATE_SETTING_FILTERS
        self.send_message(user_id, message, self.create_filters_keyboard())
    
    def handle_settings(self, user_id: int):
        """Настройки"""
        user_data = self.get_user_data(str(user_id))
        
        message = (
            "⚙️ Настройки\n\n"
            f"📍 Город: {user_data['city'] or 'Не выбран'}\n"
            f"📊 Порог уведомлений: {user_data['price_threshold']}%\n"
            f"📋 Объявлений: {len(user_data['monitored_cars'])}\n\n"
            f"🔍 Фильтры:\n{self.format_filters(str(user_id))}"
        )
        
        self.send_message(user_id, message, self.create_main_menu_keyboard())
    
    def handle_help(self, user_id: int):
        """Помощь"""
        message = (
            "❓ Помощь по использованию бота\n\n"
            "🎯 Основные функции:\n"
            "• Отслеживание цен на авто\n"
            "• Уведомления об изменениях\n"
            "• История изменения цен\n"
            "• Гибкие фильтры поиска\n\n"
            
            "📝 Как использовать:\n"
            "1️⃣ Выберите город\n"
            "2️⃣ Настройте фильтры (опционально)\n"
            "3️⃣ Добавьте ссылки на объявления\n"
            "4️⃣ Получайте уведомления\n\n"
            
            "🔍 Доступные фильтры:\n"
            "• Диапазон цены\n"
            "• Год выпуска\n"
            "• Состояние (новый/с пробегом)\n"
            "• Наличие документов\n\n"
            
            "🌐 Поддерживаемые сайты:\n"
            "• auto.ru\n"
            "• drom.ru\n\n"
            
            "🔔 Уведомления приходят при изменении цены более чем на 5%\n\n"
            
            "💡 Совет: Настройте фильтры перед добавлением объявлений!"
        )
        
        self.send_message(user_id, message, self.create_main_menu_keyboard())
    
    def handle_message(self, event):
        """Основной обработчик сообщений"""
        user_id = event.user_id
        message = event.text.strip()
        
        # Получаем состояние пользователя
        state = self.user_states.get(user_id, STATE_MAIN_MENU)
        
        # Обработка кнопки "Назад"
        if message == "« Назад":
            self.handle_start(user_id)
            return
        
        # Главное меню
        if state == STATE_MAIN_MENU or message.lower() in ['начать', 'start', 'меню']:
            if message == '🏙 Выбрать город':
                self.handle_choose_city(user_id)
            elif message == '➕ Добавить объявление':
                self.handle_add_url(user_id)
            elif message == '📋 Мои объявления':
                self.handle_list_cars(user_id)
            elif message == '🔍 Фильтры':
                self.handle_filters_menu(user_id)
            elif message == '⚙️ Настройки':
                self.handle_settings(user_id)
            elif message == '❓ Помощь':
                self.handle_help(user_id)
            else:
                self.handle_start(user_id)
        
        # Выбор города
        elif state == STATE_CHOOSING_CITY:
            self.handle_city_selected(user_id, message)
        
        # Добавление URL
        elif state == STATE_ADDING_URL:
            asyncio.run(self.handle_url_received(user_id, message))
        
        # Меню фильтров
        elif state == STATE_SETTING_FILTERS:
            if message == '💰 Цена':
                self.handle_price_filter(user_id)
            elif message == '📅 Год выпуска':
                self.handle_year_filter(user_id)
            elif message == '🚗 Состояние':
                self.handle_condition_filter(user_id)
            elif message == '📄 Документы':
                self.handle_documents_filter(user_id)
            elif message == '🗑 Сбросить фильтры':
                self.handle_clear_filters(user_id)
        
        # Ввод минимальной цены
        elif state == STATE_PRICE_MIN:
            self.handle_price_min(user_id, message)
        
        # Ввод максимальной цены
        elif state == STATE_PRICE_MAX:
            self.handle_price_max(user_id, message)
        
        # Ввод минимального года
        elif state == STATE_YEAR_MIN:
            self.handle_year_min(user_id, message)
        
        # Ввод максимального года
        elif state == STATE_YEAR_MAX:
            self.handle_year_max(user_id, message)
        
        # Выбор состояния
        elif state == STATE_CONDITION:
            self.handle_condition_selected(user_id, message)
        
        # Выбор документов
        elif state == STATE_DOCUMENTS:
            self.handle_documents_selected(user_id, message)
    
    async def monitor_prices(self):
        """Фоновый мониторинг цен"""
        logger.info("🔄 Запуск мониторинга цен...")
        
        for user_id, data in self.user_data.items():
            if not data['monitored_cars']:
                continue
            
            for url, car in data['monitored_cars'].items():
                try:
                    new_data = await self.parser.fetch_car_data(url)
                    
                    if not new_data:
                        continue
                    
                    old_price = car['price']
                    new_price = new_data['price']
                    
                    car['last_check'] = datetime.now().isoformat()
                    
                    if old_price != new_price:
                        price_change_percent = abs((new_price - old_price) / old_price * 100)
                        
                        if price_change_percent >= data['price_threshold']:
                            car['price'] = new_price
                            car['price_history'].append({
                                'price': new_price,
                                'date': datetime.now().isoformat()
                            })
                            
                            change_emoji = "📉" if new_price < old_price else "📈"
                            change_text = "снизилась" if new_price < old_price else "выросла"
                            alert_type = "🎉 Отличная новость!" if new_price < old_price else "⚠️ Внимание!"
                            
                            message = (
                                f"{alert_type}\n\n"
                                f"{change_emoji} Изменение цены!\n\n"
                                f"🚗 {car['title']}\n"
                                f"💰 Старая цена: {old_price:,} ₽\n"
                                f"💰 Новая цена: {new_price:,} ₽\n"
                                f"📊 Изменение: {new_price - old_price:+,} ₽ "
                                f"({(new_price - old_price) / old_price * 100:+.1f}%)\n\n"
                            )
                            
                            if new_price < old_price:
                                savings = old_price - new_price
                                message += f"💵 Экономия: {savings:,} ₽\n\n"
                            
                            message += f"🔗 {url}"
                            
                            try:
                                self.send_message(int(user_id), message)
                                logger.info(f"✅ Уведомление отправлено {user_id}")
                            except Exception as e:
                                logger.error(f"❌ Ошибка отправки: {e}")
                    
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка мониторинга {url}: {e}")
        
        self.save_user_data()
        logger.info("✅ Мониторинг завершен")
    
    async def run_monitoring_loop(self):
        """Цикл мониторинга"""
        while True:
            await self.monitor_prices()
            await asyncio.sleep(1800)  # 30 минут
    
    def run(self):
        """Запуск бота"""
        logger.info("🚀 VK бот запущен!")
        
        # Запускаем мониторинг в отдельном потоке
        import threading
        monitor_thread = threading.Thread(
            target=lambda: asyncio.run(self.run_monitoring_loop()),
            daemon=True
        )
        monitor_thread.start()
        
        # Основной цикл обработки сообщений
        for event in self.longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                try:
                    self.handle_message(event)
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки: {e}")


if __name__ == '__main__':
    # ВАЖНО: Замените на ваши данные
    VK_TOKEN = "YOUR_VK_GROUP_TOKEN"
    GROUP_ID = 123456789  # ID вашей группы
    
    if VK_TOKEN == "YOUR_VK_GROUP_TOKEN":
        print("❌ ОШИБКА: Укажите токен VK группы!")
        print("📝 Получите токен в настройках группы")
    else:
        bot = VKAutoMonitorBot(VK_TOKEN, GROUP_ID)
        bot.run()
