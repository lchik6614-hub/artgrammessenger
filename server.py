#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARTgram Server v2.4
Полнофункциональный бэкенд для мессенджера с поддержкой:
- Регистрации/авторизации
- Чатов и сообщений с сортировкой
- Подарков и NFT (👑 Корона + 🎈 Шар + 🪐 Планета)
- Верификации пользователей
- Надёжных бэкапов (каждые 30 мин, БЕЗ удаления)
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import shutil
import tempfile
import logging
import threading
import time
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import OrderedDict

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log', encoding='utf-8', mode='a', delay=True),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# === КОНФИГУРАЦИЯ ===
DB_FILE = 'database.json'
BALANCE_FILE = 'balance.txt'
STAR_FILE = 'star.txt'
PAYMENT_FILE = 'payment.txt'
CROWN_SOLD_FILE = 'crowns_sold.txt'
BALLOON_SOLD_FILE = 'balloons_sold.txt'
PLANET_SOLD_FILE = 'planets_sold.txt'
NFT_FILE = 'nft_registry.json'
VERIF_FILE = 'verif.txt'
BACKUP_DIR = 'backups'

# 🔐 НАСТРОЙКИ БЕЗОПАСНОСТИ И ХРАНЕНИЯ
MAX_DB_SIZE_BYTES = 1 * 1024 * 1024 * 1024  # ✅ 1 ГБ лимит
MAX_BACKUPS_TO_KEEP = 10
AUTO_DELETE_OLD_DATA = False
# ⏰ Бэкапы каждые 30 минут (было 3 часа)
BACKUP_INTERVAL_MINUTES = 30
BACKUP_INTERVAL_SECONDS = BACKUP_INTERVAL_MINUTES * 60

os.makedirs(BACKUP_DIR, exist_ok=True)

PREMIUM_USERS = ['artem', 'chap1a', 'kaktak', 'fiman', 'h', "support", "artgrambank", "LEVCHIK"]
ADMINS = ['artem', 'admin']
CROWN_LIMIT = 25
BALLOON_LIMIT = 20
PLANET_LIMIT = 15

# 👑 NFT конфигурация - Корона
NFT_MODEL_CROWN = {'id': 'crown', 'name': 'Корона', 'value': 500, 'rarity': 'legendary', 'icon': '👑'}
NFT_BACKGROUNDS_CROWN = [
    {'id': 'bg_1', 'name': 'Рассвет', 'color': 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'},
    {'id': 'bg_2', 'name': 'Океан', 'color': 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'},
    {'id': 'bg_3', 'name': 'Лес', 'color': 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)'},
    {'id': 'bg_4', 'name': 'Космос', 'color': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'},
    {'id': 'bg_5', 'name': 'Огонь', 'color': 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)'}
]
NFT_PATTERNS_CROWN = [
    {'id': 'pattern_1', 'name': 'Галочка', 'symbol': '✓', 'class': 'pattern-checkmark'},
    {'id': 'pattern_2', 'name': 'Буква A', 'symbol': 'A', 'class': 'pattern-letter-a'},
    {'id': 'pattern_3', 'name': 'Птица', 'symbol': '🕊', 'class': 'pattern-bird'},
    {'id': 'pattern_4', 'name': 'Кисточка', 'symbol': '🎨', 'class': 'pattern-brush'},
    {'id': 'pattern_5', 'name': 'Круг', 'symbol': '●', 'class': 'pattern-circle'}
]

# 🎈 NFT конфигурация - Воздушный шар
NFT_MODEL_BALLOON = {'id': 'balloon', 'name': 'Шар', 'value': 1000, 'rarity': 'legendary', 'icon': '🎈'}
NFT_BACKGROUNDS_BALLOON = [
    {'id': 'balloon_bg_1', 'name': 'Закат', 'color': 'linear-gradient(135deg, #ff9a56 0%, #ffc470 100%)', 'rarity': 'common'},
    {'id': 'balloon_bg_2', 'name': 'Мята', 'color': 'linear-gradient(135deg, #56ccf2 0%, #7ef9d4 100%)', 'rarity': 'rare'},
    {'id': 'balloon_bg_3', 'name': 'Радуга', 'color': 'linear-gradient(135deg, #ff00cc 0%, #3333ff 25%, #00ccff 50%, #33ff99 75%, #ffcc00 100%)', 'rarity': 'mythic'}
]
NFT_PATTERNS_BALLOON = [
    {'id': 'balloon_pattern_1', 'name': 'Звёзды', 'symbol': '✦', 'class': 'pattern-stars'},
    {'id': 'balloon_pattern_2', 'name': 'Волны', 'symbol': '〰', 'class': 'pattern-waves'},
    {'id': 'balloon_pattern_3', 'name': 'Искры', 'symbol': '✧', 'class': 'pattern-sparkles'}
]

# 🪐 NFT конфигурация - Планета
NFT_MODEL_PLANET = {'id': 'planet', 'name': 'Планета', 'value': 2500, 'rarity': 'ultra-legendary', 'icon': '🪐'}
NFT_BACKGROUNDS_PLANET = [
    {'id': 'planet_bg_1', 'name': 'Ледяной океан', 'color': 'linear-gradient(135deg, #4facfe 0%, #00a8ff 50%, #00d2ff 100%)', 'rarity': 'common'},
    {'id': 'planet_bg_2', 'name': 'Огненная буря', 'color': 'linear-gradient(135deg, #ff416c 0%, #ff4b2b 50%, #ffb347 100%)', 'rarity': 'rare'},
    {'id': 'planet_bg_3', 'name': 'Космическая аура', 'color': 'linear-gradient(135deg, #667eea 0%, #b721ff 25%, #764ba2 50%, #4facfe 75%, #00f2fe 100%)', 'rarity': 'ultra-rare', 'animated': True}
]
NFT_PATTERNS_PLANET = [
    {'id': 'planet_pattern_1', 'name': 'Кольца', 'symbol': '◌', 'class': 'pattern-rings'},
    {'id': 'planet_pattern_2', 'name': 'Орбита', 'symbol': '◎', 'class': 'pattern-orbit'},
    {'id': 'planet_pattern_3', 'name': 'Туманность', 'symbol': '✦✧', 'class': 'pattern-nebula'}
]

INITIAL_BALANCES = {'artem': 1000, 'admin': 500}

# === КЭШ ДЛЯ БЫСТРОГО ДОСТУПА ===
_contacts_cache = {}
_users_cache = {}
_cache_timestamp = {}
CACHE_TTL_SECONDS = 30


# === ФУНКЦИИ ВЕРИФИКАЦИИ ===
def load_verified_users():
    if not os.path.exists(VERIF_FILE):
        return []
    try:
        with open(VERIF_FILE, 'r', encoding='utf-8') as f:
            return [line.strip().lower() for line in f.readlines() if line.strip()]
    except Exception as e:
        logger.error(f"Ошибка загрузки verif.txt: {e}")
        return []


def save_verified_user(username):
    try:
        verified = load_verified_users()
        username = username.lower()
        if username not in verified:
            verified.append(username)
            with open(VERIF_FILE, 'w', encoding='utf-8') as f:
                for user in verified:
                    f.write(user + '\n')
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения верификации: {e}")
        return False


def remove_verified_user(username):
    try:
        verified = load_verified_users()
        username = username.lower()
        if username in verified:
            verified.remove(username)
            with open(VERIF_FILE, 'w', encoding='utf-8') as f:
                for user in verified:
                    f.write(user + '\n')
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления верификации: {e}")
        return False


def is_verified(username):
    return username.lower() in load_verified_users()


# === ФУНКЦИИ NFT ===
def load_nft_registry():
    if not os.path.exists(NFT_FILE):
        return {'nfts': [], 'next_id': 1}
    try:
        with open(NFT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки NFT реестра: {e}")
        return {'nfts': [], 'next_id': 1}


def save_nft_registry(data):
    try:
        with open(NFT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения NFT: {e}")
        return False


# === ФУНКЦИИ БЭКАПА ===
# ✅✅✅ ФУНКЦИЯ cleanup_old_backups() УДАЛЕНА — бэкапы теперь НИКОГДА не удаляются

def create_backup(filepath):
    if not os.path.exists(filepath):
        return False
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(BACKUP_DIR, f"{os.path.basename(filepath)}.{timestamp}.bak")
        shutil.copy2(filepath, backup_path)
        # ❌ cleanup_old_backups(filepath) — УДАЛЕНО, бэкапы копятся вечно
        logger.info(f"✅ Бэкап создан: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания бэкапа {filepath}: {e}")
        return False


def atomic_save(filepath, data, is_json=True):
    """Атомарная запись с проверкой размера и целостности"""
    try:
        if is_json:
            test_data = json.dumps(data, ensure_ascii=False, indent=2)
            if len(test_data.encode('utf-8')) > MAX_DB_SIZE_BYTES:
                logger.error(f"❌ Превышен лимит БД: {len(test_data.encode('utf-8')) / 1024 / 1024:.2f} МБ > 1 ГБ")
                return False

        dir_path = os.path.dirname(filepath) or '.'
        fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                if is_json:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                else:
                    f.write(data)
            if is_json:
                with open(temp_path, 'r', encoding='utf-8') as test_f:
                    json.load(test_f)
            shutil.move(temp_path, filepath)
            return True
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"❌ Ошибка атомарной записи: {e}")
            raise
    except Exception as e:
        logger.error(f"❌ Критическая ошибка сохранения {filepath}: {e}")
        return False


def get_latest_backup(original_path):
    basename = os.path.basename(original_path)
    backups = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith(basename + '.')]
    if not backups:
        return None
    backups.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return backups[0]


def load_db_from_path(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Не удалось загрузить бэкап {path}: {e}")
        return None


def validate_db_structure(data):
    """Проверка целостности структуры БД"""
    required_keys = ['users', 'chats', 'contacts', 'blocked']
    for key in required_keys:
        if key not in data:
            data[key] = {} if key in ['users', 'contacts', 'blocked'] else []
    if not isinstance(data['users'], dict):
        data['users'] = {}
    if not isinstance(data['chats'], list):
        data['chats'] = []
    if not isinstance(data['contacts'], dict):
        data['contacts'] = {}
    if not isinstance(data['blocked'], dict):
        data['blocked'] = {}
    return data


def load_db():
    """Загрузка БД с многоуровневым восстановлением при ошибках"""
    if os.path.exists(DB_FILE):
        try:
            file_size = os.path.getsize(DB_FILE)
            if file_size > MAX_DB_SIZE_BYTES:
                logger.warning(f"⚠️ Размер БД {file_size / 1024 / 1024:.2f} МБ превышает лимит 1 ГБ, но НЕ удаляется!")
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    logger.warning("⚠️ Файл БД пустой!")
                    return {"users": {}, "chats": [], "contacts": {}, "blocked": {}}
                data = json.loads(content)
                return validate_db_structure(data)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Повреждён JSON в {DB_FILE}: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки БД: {type(e).__name__}: {e}")

    backup = get_latest_backup(DB_FILE)
    if backup:
        logger.info(f"🔄 Восстановление из бэкапа: {backup}")
        restored = load_db_from_path(backup)
        if restored:
            if atomic_save(DB_FILE, restored, is_json=True):
                logger.info("✅ БД успешно восстановлена из бэкапа")
                return validate_db_structure(restored)

    logger.warning("⚠️ Создаём новую пустую базу данных")
    new_db = {"users": {}, "chats": [], "contacts": {}, "blocked": {}}
    if atomic_save(DB_FILE, new_db, is_json=True):
        return new_db
    return {"users": {}, "chats": [], "contacts": {}, "blocked": {}}


def save_db(data):
    """Сохранение БД с бэкапом и проверками"""
    try:
        create_backup(DB_FILE)
        if not atomic_save(DB_FILE, data, is_json=True):
            logger.error("❌ Не удалось сохранить БД, пробуем фоллбэк...")
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"🚨 Критическая ошибка сохранения БД: {e}")
        return False


# === ФУНКЦИИ БАЛАНСА ===
def load_balances():
    if not os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, 'w', encoding='utf-8') as f:
            for username, balance in INITIAL_BALANCES.items():
                f.write(f"{username}:{balance}\n")
        return INITIAL_BALANCES.copy()
    balances = {}
    try:
        with open(BALANCE_FILE, 'r', encoding='utf-8') as f:
            for line in f.readlines():
                line = line.strip()
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        try:
                            balances[parts[0].lower()] = int(parts[1])
                        except ValueError:
                            pass
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки балансов: {e}")
        return INITIAL_BALANCES.copy()
    return balances


def save_balances(balances):
    content = '\n'.join(f"{u}:{b}" for u, b in balances.items()) + '\n'
    atomic_save(BALANCE_FILE, content, is_json=False)


def get_user_balance(username):
    balances = load_balances()
    if username not in balances:
        balances[username] = INITIAL_BALANCES.get(username, 0)
        save_balances(balances)
    return balances[username]


def update_user_balance(username, amount):
    balances = load_balances()
    balances[username] = balances.get(username, 0) + amount
    save_balances(balances)
    return balances[username]


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def check_premium(username):
    return username.lower() in [u.lower() for u in PREMIUM_USERS]


def load_crowns_sold():
    if not os.path.exists(CROWN_SOLD_FILE):
        return 0
    try:
        with open(CROWN_SOLD_FILE, 'r', encoding='utf-8') as f:
            return int(f.read().strip())
    except:
        return 0


def save_crowns_sold(count):
    atomic_save(CROWN_SOLD_FILE, str(count), is_json=False)


def get_crowns_available():
    return max(0, CROWN_LIMIT - load_crowns_sold())


def load_balloons_sold():
    if not os.path.exists(BALLOON_SOLD_FILE):
        return 0
    try:
        with open(BALLOON_SOLD_FILE, 'r', encoding='utf-8') as f:
            return int(f.read().strip())
    except:
        return 0


def save_balloons_sold(count):
    atomic_save(BALLOON_SOLD_FILE, str(count), is_json=False)


def get_balloons_available():
    return max(0, BALLOON_LIMIT - load_balloons_sold())


def load_planets_sold():
    if not os.path.exists(PLANET_SOLD_FILE):
        return 0
    try:
        with open(PLANET_SOLD_FILE, 'r', encoding='utf-8') as f:
            return int(f.read().strip())
    except:
        return 0


def save_planets_sold(count):
    atomic_save(PLANET_SOLD_FILE, str(count), is_json=False)


def get_planets_available():
    return max(0, PLANET_LIMIT - load_planets_sold())


def save_star_purchase(username, rockets, price):
    try:
        with open(STAR_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{username}|{rockets}|{price}|{datetime.now().isoformat()}|pending\n")
    except Exception as e:
        logger.error(f"❌ Ошибка записи покупки: {e}")


def load_payments():
    if not os.path.exists(PAYMENT_FILE):
        return []
    try:
        with open(PAYMENT_FILE, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except:
        return []


def save_payment(username):
    payments = load_payments()
    if username not in payments:
        try:
            with open(PAYMENT_FILE, 'a', encoding='utf-8') as f:
                f.write(username + '\n')
        except:
            pass


# === КЭШИРОВАНИЕ КОНТАКТОВ ===
def get_contacts_cached(username):
    """Получение контактов с кэшированием для быстрой загрузки"""
    current_time = time.time()
    if username in _contacts_cache and (current_time - _cache_timestamp.get(username, 0)) < CACHE_TTL_SECONDS:
        return _contacts_cache[username]
    db = load_db()
    contacts_list = []
    for cu in db.get('contacts', {}).get(username, []):
        if cu in db['users']:
            u = db['users'][cu]
            contacts_list.append({
                "username": u['username'],
                "avatar": u.get('avatar'),
                "bio": u.get('bio', ''),
                "status": u.get('status', ''),
                "premium": u.get('premium', False),
                "verified": u.get('verified', False) or is_verified(cu)
            })
    _contacts_cache[username] = contacts_list
    _cache_timestamp[username] = current_time
    return contacts_list


def invalidate_contacts_cache(username=None):
    """Очистка кэша контактов"""
    if username:
        _contacts_cache.pop(username, None)
        _cache_timestamp.pop(username, None)
    else:
        _contacts_cache.clear()
        _cache_timestamp.clear()


# === ПЛАНИРОВЩИК БЭКАПОВ ===
def scheduled_backup_task():
    while True:
        try:
            time.sleep(BACKUP_INTERVAL_SECONDS)
            logger.info(f"🕐 Плановый бэкап (каждые {BACKUP_INTERVAL_MINUTES} мин.)")
            for filepath in [DB_FILE, BALANCE_FILE, CROWN_SOLD_FILE, BALLOON_SOLD_FILE, PLANET_SOLD_FILE, NFT_FILE]:
                if os.path.exists(filepath):
                    create_backup(filepath)
            logger.info("✅ Плановый бэкап завершён")
        except Exception as e:
            logger.error(f"❌ Ошибка планового бэкапа: {e}")


def start_backup_scheduler():
    thread = threading.Thread(target=scheduled_backup_task, daemon=True)
    thread.start()
    logger.info(
        f"🔄 Планировщик бэкапов запущен (интервал: {BACKUP_INTERVAL_MINUTES} мин, бэкапы НЕ УДАЛЯЮТСЯ)")


# === API ENDPOINTS ===

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "message": "Неверные данные"}), 400

        db = load_db()
        username = data.get('username', '').replace('@', '').lower()

        if not username or len(username) < 3:
            return jsonify({"success": False, "message": "Юзернейм слишком короткий"}), 400
        if username in db['users']:
            return jsonify({"success": False, "message": "Юзернейм уже занят!"}), 400

        db['users'][username] = {
            "username": username,
            "email": data.get('email', ''),
            "password": data.get('password', ''),
            "bio": data.get('bio', ''),
            "avatar": data.get('avatar'),
            "status": "",
            "premium": check_premium(username),
            "verified": is_verified(username),
            "premium_until": datetime.now().isoformat() if check_premium(username) else None,
            "payment_pending": False,
            "created_at": datetime.now().isoformat(),
            "gifts": [],
            "nfts": [],
            "show_gifts": True
        }

        db.setdefault('contacts', {})[username] = []
        db.setdefault('blocked', {})[username] = []

        balances = load_balances()
        if username not in balances:
            balances[username] = INITIAL_BALANCES.get(username, 0)
            save_balances(balances)

        save_db(db)
        invalidate_contacts_cache()
        logger.info(f"✅ Регистрация: @{username}")
        return jsonify({"success": True, "message": "Регистрация успешна!"})
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации: {e}")
        return jsonify({"success": False, "message": "Ошибка сервера"}), 500


@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "message": "Неверные данные"}), 400

        db = load_db()
        username = data.get('username', '').replace('@', '').lower()
        password = data.get('password')

        if username not in db['users']:
            return jsonify({"success": False, "message": "Пользователь не найден"}), 404
        if db['users'][username]['password'] != password:
            return jsonify({"success": False, "message": "Неверный пароль"}), 401

        user = db['users'][username].copy()
        user['balance'] = get_user_balance(username)
        user['is_admin'] = username in ADMINS

        if check_premium(username):
            user['premium'] = True
            user['premium_until'] = datetime.now().isoformat()
        if is_verified(username):
            user['verified'] = True

        user.pop('password', None)
        logger.info(f"✅ Вход: @{username}")
        return jsonify({"success": True, "user": user})
    except Exception as e:
        logger.error(f"❌ Ошибка входа: {e}")
        return jsonify({"success": False, "message": "Ошибка сервера"}), 500


@app.route('/api/get_balance', methods=['POST'])
def get_balance():
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').lower()
        return jsonify({"success": True, "balance": get_user_balance(username)})
    except Exception as e:
        logger.error(f"❌ Ошибка get_balance: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/purchase_rockets', methods=['POST'])
def purchase_rockets():
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').lower()
        package = data.get('package')

        packages = {'50': {'rockets': 50, 'price': 49}, '100': {'rockets': 100, 'price': 89}}
        if package not in packages:
            return jsonify({"success": False, "message": "Неверный пакет"}), 400

        pkg = packages[package]
        save_star_purchase(username, pkg['rockets'], pkg['price'])

        return jsonify({
            "success": True,
            "rockets": pkg['rockets'],
            "price": pkg['price'],
            "payment_phone": "+7 (951) 305-75-61",
            "payment_bank": "Сбербанк",
            "message": "Укажите юзернейм в комментарии перевода!"
        })
    except Exception as e:
        logger.error(f"❌ Ошибка purchase_rockets: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/admin_add_balance', methods=['POST'])
def admin_add_balance():
    try:
        data = request.get_json(force=True)
        admin = data.get('admin', '').lower()
        username = data.get('username', '').lower()
        amount = data.get('amount', 0)

        if admin not in ADMINS:
            return jsonify({"success": False, "message": "Только админ"}), 403

        new_balance = update_user_balance(username, amount)
        logger.info(f"💰 {admin} изменил баланс {username}: +{amount} → {new_balance}")
        invalidate_contacts_cache(username)
        return jsonify({"success": True, "new_balance": new_balance})
    except Exception as e:
        logger.error(f"❌ Ошибка admin_add_balance: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/admin_toggle_verify', methods=['POST'])
def admin_toggle_verify():
    try:
        data = request.get_json(force=True)
        admin = data.get('admin', '').lower()
        target_id = data.get('target_id', '').lower()
        action = data.get('action', 'toggle')

        if admin != 'artem':
            return jsonify({"success": False, "message": "Только @artem может верифицировать!"}), 403

        if action == 'add':
            if save_verified_user(target_id):
                invalidate_contacts_cache()
                return jsonify({"success": True, "message": f"@{target_id} верифицирован!"})
        elif action == 'remove':
            if remove_verified_user(target_id):
                invalidate_contacts_cache()
                return jsonify({"success": True, "message": f"@{target_id} снят с верификации"})

        return jsonify({"success": False, "message": "Ошибка"}), 500
    except Exception as e:
        logger.error(f"❌ Ошибка admin_toggle_verify: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/send_gift', methods=['POST'])
def send_gift():
    try:
        data = request.get_json(force=True)
        sender = data.get('sender', '').lower()
        receiver = data.get('receiver', '').lower()
        gift_type = data.get('gift_type')

        gift_prices = {
            'teddy': 50, 'heart': 50, 'cup': 100,
            'crown': 500, 'balloon': 1000, 'planet': 2500
        }

        if gift_type not in gift_prices:
            return jsonify({"success": False, "message": "Неверный подарок"}), 400

        if gift_type == 'crown' and get_crowns_available() <= 0:
            return jsonify({"success": False, "message": "👑 Корона распродана!"}), 400
        if gift_type == 'balloon' and get_balloons_available() <= 0:
            return jsonify({"success": False, "message": "🎈 Шары распроданы!"}), 400
        if gift_type == 'planet' and get_planets_available() <= 0:
            return jsonify({"success": False, "message": "🪐 Планеты распроданы!"}), 400

        price = gift_prices[gift_type]
        if get_user_balance(sender) < price:
            return jsonify({"success": False, "message": "Недостаточно ракет 🚀"}), 400

        update_user_balance(sender, -price)

        if gift_type == 'crown':
            save_crowns_sold(load_crowns_sold() + 1)
        elif gift_type == 'balloon':
            save_balloons_sold(load_balloons_sold() + 1)
        elif gift_type == 'planet':
            save_planets_sold(load_planets_sold() + 1)

        db = load_db()
        gift = {
            "id": str(datetime.now().timestamp()),
            "type": gift_type,
            "from": sender,
            "date": datetime.now().isoformat(),
            "price": price,
            "rare": gift_type in ['crown', 'balloon', 'planet'],
            "nft": None,
            "model_type": "crown" if gift_type == 'crown' else "balloon" if gift_type == 'balloon' else "planet" if gift_type == 'planet' else None
        }

        if receiver in db['users']:
            db['users'].setdefault(receiver, {}).setdefault('gifts', []).append(gift)
            db['users'][receiver].setdefault('nfts', [])
            save_db(db)
            invalidate_contacts_cache(receiver)

        response = {"success": True, "gift": gift, "sender_new_balance": get_user_balance(sender)}
        if gift_type == 'crown':
            response['crowns_left'] = get_crowns_available()
        elif gift_type == 'balloon':
            response['balloons_left'] = get_balloons_available()
        elif gift_type == 'planet':
            response['planets_left'] = get_planets_available()

        return jsonify(response)
    except Exception as e:
        logger.error(f"❌ Ошибка send_gift: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/transfer_nft_gift', methods=['POST'])
def transfer_nft_gift():
    try:
        data = request.get_json(force=True)
        sender = data.get('sender', '').lower()
        receiver = data.get('receiver', '').lower()
        gift_id = data.get('gift_id')

        if not sender or not receiver or not gift_id:
            return jsonify({"success": False, "message": "Неверные параметры"}), 400

        db = load_db()
        nft_registry = load_nft_registry()

        if sender not in db['users'] or receiver not in db['users']:
            return jsonify({"success": False, "message": "Пользователь не найден"}), 404

        sender_gifts = db['users'][sender].get('gifts', [])
        gift_index = next((i for i, g in enumerate(sender_gifts) if g['id'] == gift_id), None)

        if gift_index is None:
            return jsonify({"success": False, "message": "Подарок не найден"}), 404

        gift = sender_gifts[gift_index]
        if not gift.get('nft'):
            return jsonify({"success": False, "message": "Это не NFT"}), 400

        for nft in nft_registry['nfts']:
            if nft['id'] == gift['nft']['id']:
                nft['owner'] = receiver
                nft.setdefault('transfer_history', []).append({
                    'from': sender, 'to': receiver, 'date': datetime.now().isoformat()
                })
                break
        save_nft_registry(nft_registry)

        sender_gifts.pop(gift_index)
        db['users'][sender]['gifts'] = sender_gifts
        db['users'].setdefault(receiver, {}).setdefault('gifts', []).append(gift)
        db['users'][receiver].setdefault('nfts', []).append(gift['nft']['id'])

        save_db(db)
        invalidate_contacts_cache(sender)
        invalidate_contacts_cache(receiver)

        logger.info(f"🎁 NFT #{gift['nft']['id']} передан: @{sender} → @{receiver}")

        return jsonify({
            "success": True,
            "message": f"NFT #{gift['nft']['id']} передан @{receiver}",
            "gift": gift,
            "nft_id": gift['nft']['id'],
            "contacts": get_contacts_cached(sender)
        })
    except Exception as e:
        logger.error(f"❌ Ошибка transfer_nft_gift: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/upgrade_nft', methods=['POST'])
def upgrade_nft():
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').lower()
        gift_id = data.get('gift_id')
        upgrade_cost = data.get('upgrade_cost', 250)

        db = load_db()
        nft_registry = load_nft_registry()

        if username not in db['users']:
            return jsonify({"success": False, "message": "Пользователь не найден"}), 404

        gifts = db['users'][username].get('gifts', [])
        gift_index = next((i for i, g in enumerate(gifts) if g['id'] == gift_id), None)

        if gift_index is None:
            return jsonify({"success": False, "message": "Подарок не найден"}), 404

        gift = gifts[gift_index]

        if gift['type'] not in ['crown', 'balloon', 'planet'] or gift.get('nft'):
            return jsonify({"success": False, "message": "Нельзя улучшить"}), 400

        if get_user_balance(username) < upgrade_cost:
            return jsonify({"success": False, "message": "Недостаточно ракет для улучшения 🚀"}), 400

        update_user_balance(username, -upgrade_cost)

        if gift['type'] == 'crown':
            model = NFT_MODEL_CROWN.copy()
            backgrounds = NFT_BACKGROUNDS_CROWN
            patterns = NFT_PATTERNS_CROWN
        elif gift['type'] == 'balloon':
            model = NFT_MODEL_BALLOON.copy()
            backgrounds = NFT_BACKGROUNDS_BALLOON
            patterns = NFT_PATTERNS_BALLOON
        else:
            model = NFT_MODEL_PLANET.copy()
            backgrounds = NFT_BACKGROUNDS_PLANET
            patterns = NFT_PATTERNS_PLANET

        nft_id = nft_registry['next_id']

        if gift['type'] == 'planet':
            bg_weights = [0.5, 0.35, 0.15]
            background = random.choices(backgrounds, weights=bg_weights)[0]
        elif gift['type'] == 'balloon':
            bg_weights = [0.5, 0.35, 0.15]
            background = random.choices(backgrounds, weights=bg_weights)[0]
        else:
            background = random.choice(backgrounds)

        nft_data = {
            "id": nft_id,
            "owner": username,
            "gift_id": gift_id,
            "model": model,
            "background": background,
            "pattern": random.choice(patterns),
            "activated_at": datetime.now().isoformat(),
            "rarity_scores": {
                "model": model['rarity'],
                "background": background.get('rarity', random.choice(['common', 'rare', 'legendary'])),
                "pattern": random.choice(['common', 'rare', 'legendary'])
            }
        }

        nft_registry['nfts'].append(nft_data)
        nft_registry['next_id'] += 1
        save_nft_registry(nft_registry)

        gift['nft'] = nft_data
        db['users'][username].setdefault('nfts', []).append(nft_id)
        save_db(db)
        invalidate_contacts_cache(username)

        return jsonify({
            "success": True,
            "nft": nft_data,
            "message": f"🎉 {model['icon']} NFT #{nft_id} активирован!",
            "new_balance": get_user_balance(username)
        })
    except Exception as e:
        logger.error(f"❌ Ошибка upgrade_nft: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/get_nft_info', methods=['POST'])
def get_nft_info():
    try:
        data = request.get_json(force=True)
        nft_id = data.get('nft_id')
        nft_registry = load_nft_registry()

        nft = next((n for n in nft_registry['nfts'] if n['id'] == nft_id), None)
        if not nft:
            return jsonify({"success": False, "message": "NFT не найден"}), 404

        model_id = nft['model']['id']
        if model_id == 'balloon':
            bg_count = len(NFT_BACKGROUNDS_BALLOON)
            pattern_count = len(NFT_BALLOON_PATTERNS)
        elif model_id == 'planet':
            bg_count = len(NFT_BACKGROUNDS_PLANET)
            pattern_count = len(NFT_PATTERNS_PLANET)
        else:
            bg_count = len(NFT_BACKGROUNDS_CROWN)
            pattern_count = len(NFT_PATTERNS_CROWN)

        return jsonify({
            "success": True,
            "nft": nft,
            "odds": {"background": f"1/{bg_count}", "pattern": f"1/{pattern_count}"}
        })
    except Exception as e:
        logger.error(f"❌ Ошибка get_nft_info: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/sell_gift', methods=['POST'])
def sell_gift():
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').lower()
        gift_id = data.get('gift_id')

        db = load_db()
        gifts = db['users'].get(username, {}).get('gifts', [])
        gift_index = next((i for i, g in enumerate(gifts) if g['id'] == gift_id), None)

        if gift_index is None:
            return jsonify({"success": False, "message": "Подарок не найден"}), 404

        gift = gifts[gift_index]

        if gift.get('nft'):
            sell_price = gift['nft']['model']['value']
        elif gift['type'] == 'crown':
            sell_price = 450
        elif gift['type'] == 'balloon':
            sell_price = 900
        elif gift['type'] == 'planet':
            sell_price = 2250
        else:
            sell_price = 45

        gifts.pop(gift_index)
        db['users'][username]['gifts'] = gifts
        new_balance = update_user_balance(username, sell_price)
        save_db(db)
        invalidate_contacts_cache(username)

        return jsonify({"success": True, "new_balance": new_balance, "earned": sell_price})
    except Exception as e:
        logger.error(f"❌ Ошибка sell_gift: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/toggle_gifts', methods=['POST'])
def toggle_gifts():
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').lower()
        show = data.get('show', True)

        db = load_db()
        if username in db['users']:
            db['users'][username]['show_gifts'] = show
            save_db(db)
            invalidate_contacts_cache(username)
            return jsonify({"success": True, "show_gifts": show})
        return jsonify({"success": False}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка toggle_gifts: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/get_user_gifts', methods=['POST'])
def get_user_gifts():
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').lower()
        db = load_db()

        if username in db['users']:
            return jsonify({
                "success": True,
                "gifts": db['users'][username].get('gifts', []),
                "show_gifts": db['users'][username].get('show_gifts', True)
            })
        return jsonify({"success": False, "gifts": []}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка get_user_gifts: {e}")
        return jsonify({"success": False, "gifts": []}), 500


@app.route('/api/get_user_nfts', methods=['POST'])
def get_user_nfts():
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').lower()
        nft_registry = load_nft_registry()
        user_nfts = [nft for nft in nft_registry['nfts'] if nft['owner'] == username]
        return jsonify({"success": True, "nfts": user_nfts, "count": len(user_nfts)})
    except Exception as e:
        logger.error(f"❌ Ошибка get_user_nfts: {e}")
        return jsonify({"success": False, "nfts": []}), 500


@app.route('/api/add_reaction', methods=['POST'])
def add_reaction():
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').lower()
        chat_id = data.get('chat_id')
        message_id = data.get('message_id')
        reaction = data.get('reaction')

        db = load_db()
        chat = next((c for c in db['chats'] if c['id'] == chat_id), None)
        if chat:
            message = next((m for m in chat['messages'] if m['id'] == message_id), None)
            if message:
                message.setdefault('reactions', [])
                existing = next((r for r in message['reactions'] if r['user'] == username), None)
                if existing:
                    if existing['type'] == reaction:
                        message['reactions'].remove(existing)
                    else:
                        existing['type'] = reaction
                else:
                    message['reactions'].append(
                        {"user": username, "type": reaction, "timestamp": datetime.now().isoformat()})
                save_db(db)
                return jsonify({"success": True, "reactions": message['reactions']})
        return jsonify({"success": False}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка add_reaction: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/get_reactions', methods=['POST'])
def get_reactions():
    try:
        data = request.get_json(force=True)
        chat_id = data.get('chat_id')
        message_id = data.get('message_id')
        db = load_db()
        chat = next((c for c in db['chats'] if c['id'] == chat_id), None)
        if chat:
            message = next((m for m in chat['messages'] if m['id'] == message_id), None)
            if message:
                return jsonify({"success": True, "reactions": message.get('reactions', [])})
        return jsonify({"success": False, "reactions": []}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка get_reactions: {e}")
        return jsonify({"success": False, "reactions": []}), 500


@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    try:
        data = request.get_json(force=True)
        db = load_db()
        username = data.get('username', '').lower()

        if username in db['users']:
            if data.get('new_username'):
                new_username = data.get('new_username').replace('@', '').lower()
                if new_username != username and new_username in db['users']:
                    return jsonify({"success": False, "message": "Юзернейм занят"}), 400
                db['users'][new_username] = db['users'].pop(username)
                db['users'][new_username]['username'] = new_username
                for u in db['users']:
                    if username in db['contacts'].get(u, []):
                        db['contacts'][u].remove(username)
                        db['contacts'][u].append(new_username)
                username = new_username

            for field in ['avatar', 'bio', 'status']:
                if data.get(field) is not None:
                    db['users'][username][field] = data.get(field)

            save_db(db)
            invalidate_contacts_cache()
            user_copy = db['users'][username].copy()
            user_copy['balance'] = get_user_balance(username)
            user_copy.pop('password', None)
            return jsonify({"success": True, "user": user_copy})
        return jsonify({"success": False}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка update_profile: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/update_channel', methods=['POST'])
def update_channel():
    try:
        data = request.get_json(force=True)
        db = load_db()
        username = data.get('username', '').lower()
        chat_id = data.get('chat_id')

        chat = next((c for c in db['chats'] if c['id'] == chat_id), None)
        if not chat or chat.get('owner') != username or chat.get('type') not in ['channel', 'group']:
            return jsonify({"success": False, "message": "Ошибка"}), 400

        for field in ['name', 'description', 'avatar', 'username']:
            if data.get(field) is not None:
                chat[field] = data.get(field).replace('@', '').lower() if field == 'username' else data.get(field)

        save_db(db)
        return jsonify({"success": True, "chat": chat})
    except Exception as e:
        logger.error(f"❌ Ошибка update_channel: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/get_channel_subscribers', methods=['POST'])
def get_channel_subscribers():
    try:
        data = request.get_json(force=True)
        db = load_db()
        username = data.get('username', '').lower()
        chat_id = data.get('chat_id')

        chat = next((c for c in db['chats'] if c['id'] == chat_id), None)
        if not chat or chat.get('owner') != username:
            return jsonify({"success": False, "message": "Ошибка"}), 400

        subscribers = []
        for p in chat.get('participants', []):
            if p in db['users']:
                u = db['users'][p]
                subscribers.append({"username": u['username'], "avatar": u.get('avatar'), "bio": u.get('bio', '')})

        return jsonify({"success": True, "subscribers": subscribers, "count": len(subscribers)})
    except Exception as e:
        logger.error(f"❌ Ошибка get_channel_subscribers: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/get_contacts', methods=['POST'])
def get_contacts():
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').lower()
        contacts = get_contacts_cached(username)
        return jsonify({"contacts": contacts})
    except Exception as e:
        logger.error(f"❌ Ошибка get_contacts: {e}")
        return jsonify({"contacts": []}), 500


@app.route('/api/add_contact', methods=['POST'])
def add_contact():
    try:
        data = request.get_json(force=True)
        db = load_db()
        username = data.get('username', '').lower()
        contact = data.get('contact', '').lower()

        db.setdefault('contacts', {}).setdefault(username, [])
        db.setdefault('blocked', {}).setdefault(username, [])

        if contact in db['blocked'][username]:
            return jsonify({"success": False, "message": "Заблокирован"}), 400
        if contact not in db['contacts'][username]:
            db['contacts'][username].append(contact)
            save_db(db)
            invalidate_contacts_cache(username)
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Уже в контактах"}), 400
    except Exception as e:
        logger.error(f"❌ Ошибка add_contact: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/remove_contact', methods=['POST'])
def remove_contact():
    try:
        data = request.get_json(force=True)
        db = load_db()
        username = data.get('username', '').lower()
        contact = data.get('contact', '').lower()

        if contact in db.get('contacts', {}).get(username, []):
            db['contacts'][username].remove(contact)
            save_db(db)
            invalidate_contacts_cache(username)
            return jsonify({"success": True})
        return jsonify({"success": False}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка remove_contact: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/block_user', methods=['POST'])
def block_user():
    try:
        data = request.get_json(force=True)
        db = load_db()
        username = data.get('username', '').lower()
        block = data.get('block', '').lower()

        db.setdefault('blocked', {}).setdefault(username, [])
        if block not in db['blocked'][username]:
            db['blocked'][username].append(block)
            if block in db.get('contacts', {}).get(username, []):
                db['contacts'][username].remove(block)
            save_db(db)
            invalidate_contacts_cache(username)
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Уже заблокирован"}), 400
    except Exception as e:
        logger.error(f"❌ Ошибка block_user: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/unblock_user', methods=['POST'])
def unblock_user():
    try:
        data = request.get_json(force=True)
        db = load_db()
        username = data.get('username', '').lower()
        unblock = data.get('unblock', '').lower()

        if unblock in db.get('blocked', {}).get(username, []):
            db['blocked'][username].remove(unblock)
            save_db(db)
            invalidate_contacts_cache(username)
            return jsonify({"success": True})
        return jsonify({"success": False}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка unblock_user: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/get_blocked', methods=['POST'])
def get_blocked():
    try:
        data = request.get_json(force=True)
        db = load_db()
        username = data.get('username', '').lower()
        blocked = []
        for bu in db.get('blocked', {}).get(username, []):
            if bu in db['users']:
                u = db['users'][bu]
                blocked.append({"username": u['username'], "avatar": u.get('avatar'), "bio": u.get('bio', '')})
        return jsonify({"blocked": blocked})
    except Exception as e:
        logger.error(f"❌ Ошибка get_blocked: {e}")
        return jsonify({"blocked": []}), 500


@app.route('/api/search_user', methods=['POST'])
def search_user():
    try:
        data = request.get_json(force=True)
        db = load_db()
        query = data.get('query', '').replace('@', '').lower()
        current = data.get('current_user', '').lower()
        found = []
        for uname, udata in db['users'].items():
            if query in uname and uname != current:
                found.append({
                    "username": udata['username'], "bio": udata.get('bio', ''), "avatar": udata.get('avatar'),
                    "status": udata.get('status', ''), "premium": udata.get('premium', False) or check_premium(uname),
                    "verified": udata.get('verified', False) or is_verified(uname), "is_user": True,
                    "is_contact": uname in db.get('contacts', {}).get(current, []),
                    "is_blocked": uname in db.get('blocked', {}).get(current, [])
                })
        for chat in db['chats']:
            if query in chat.get('name', '').lower() or query in chat.get('username', '').lower():
                if chat.get('type') in ['group', 'channel']:
                    found.append({
                        "username": chat.get('username') or chat['name'], "bio": chat.get('description', 'Чат'),
                        "avatar": chat.get('avatar'), "is_chat": True, "chat_id": chat['id'],
                        "type": chat['type'], "verified": chat.get('verified', False)
                    })
        return jsonify(found)
    except Exception as e:
        logger.error(f"❌ Ошибка search_user: {e}")
        return jsonify([]), 500


@app.route('/api/get_chats', methods=['POST'])
def get_chats():
    try:
        data = request.get_json(force=True)
        db = load_db()
        username = data.get('username', '').lower()
        user_chats = []
        saved_id = f"saved_{username}"
        saved_chat = {"id": saved_id, "name": "Избранное", "type": "saved", "is_saved": True, "messages": []}
        if not any(c['id'] == saved_id for c in db['chats']):
            db['chats'].insert(0, saved_chat)
            save_db(db)
        for chat in db['chats']:
            if chat['id'] == saved_id:
                user_chats.append(chat)
            elif chat.get('type') == 'private' and username in chat.get('participants', []):
                other = next((p for p in chat['participants'] if p.lower() != username.lower()), None)
                if other and other in db['users']:
                    u = db['users'][other]
                    chat['display_name'] = u['username']
                    chat['display_avatar'] = u.get('avatar')
                    chat['display_status'] = u.get('status', '')
                    chat['display_premium'] = u.get('premium', False) or check_premium(other)
                    chat['display_verified'] = u.get('verified', False) or is_verified(other)
                    chat['blocked_by_me'] = other in db.get('blocked', {}).get(username, [])
                    # ❌ Убран подсчёт непрочитанных (галочки прочтения удалены)
                user_chats.append(chat)
            elif chat['id'] != saved_id and (username in chat.get('participants', []) or chat.get('owner') == username):
                chat['subscribers'] = len(chat.get('participants', [chat.get('owner')]))
                chat['is_owner'] = chat.get('owner') == username
                user_chats.append(chat)
        user_chats.sort(key=lambda c: (
            c.get('messages', [])[-1].get('timestamp', c.get('created_at', '0')) if c.get('messages') else '0'),
                        reverse=True)
        return jsonify(user_chats)
    except Exception as e:
        logger.error(f"❌ Ошибка get_chats: {e}")
        return jsonify([]), 500


@app.route('/api/start_chat', methods=['POST'])
def start_chat():
    try:
        data = request.get_json(force=True)
        db = load_db()
        user1 = data.get('user1', '').lower()
        user2 = data.get('user2', '').lower()
        db.setdefault('blocked', {})
        if user2 in db['blocked'].get(user1, []) or user1 in db['blocked'].get(user2, []):
            return jsonify({"success": False, "message": "Заблокирован"}), 400
        for chat in db['chats']:
            if chat.get('type') == 'private' and user1 in chat.get('participants', []) and user2 in chat.get(
                    'participants', []):
                return jsonify({"success": True, "chat_id": chat['id']})
        new_chat = {
            "id": str(datetime.now().timestamp()), "name": user2, "type": "private",
            "participants": [user1, user2], "messages": [], "avatar": None,
            "created_at": datetime.now().isoformat()
        }
        db['chats'].insert(0, new_chat)
        save_db(db)
        invalidate_contacts_cache(user1)
        invalidate_contacts_cache(user2)
        return jsonify({"success": True, "chat_id": new_chat['id']})
    except Exception as e:
        logger.error(f"❌ Ошибка start_chat: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/send_message', methods=['POST'])
def send_message():
    try:
        data = request.get_json(force=True)
        db = load_db()
        sender = data.get('from_user', '').lower()
        chat_id = data.get('chat_id')
        chat = next((c for c in db['chats'] if c['id'] == chat_id), None)
        if chat:
            if chat.get('type') == 'private':
                for p in chat.get('participants', []):
                    if p != sender and sender in db.get('blocked', {}).get(p, []):
                        return jsonify({"success": False, "message": "Вас заблокировали", "blocked": True}), 400
            # ❌ Убраны поля read_by и status (галочки прочтения)
            new_msg = {
                "id": str(datetime.now().timestamp()), "text": data.get('text'), "from": sender,
                "time": datetime.now().strftime("%H:%M"), "timestamp": datetime.now().isoformat(),
                "type": data.get('type', 'text'), "data": data.get('data'), "fileName": data.get('fileName'),
                "reactions": [], "duration": data.get('duration'), "nft_id": data.get('nft_id')
            }
            chat['messages'].append(new_msg)
            save_db(db)
            return jsonify({"success": True, "message_count": len(chat['messages']), "message": new_msg})
        return jsonify({"success": False}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка send_message: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/get_messages', methods=['POST'])
def get_messages():
    try:
        data = request.get_json(force=True)
        db = load_db()
        chat_id = data.get('chat_id')
        username = data.get('username', '').lower()
        chat = next((c for c in db['chats'] if c['id'] == chat_id), None)
        if chat:
            is_blocked = False
            if chat.get('type') == 'private':
                for p in chat.get('participants', []):
                    if p != username and username in db.get('blocked', {}).get(p, []):
                        is_blocked = True
                        break
            # ❌ Убрано авто-прочтение сообщений (галочки удалены)
            return jsonify({"success": True, "messages": chat['messages'], "count": len(chat['messages']),
                            "is_blocked": is_blocked})
        return jsonify({"success": False, "messages": [], "count": 0}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка get_messages: {e}")
        return jsonify({"success": False, "messages": [], "count": 0}), 500


@app.route('/api/create_chat', methods=['POST'])
def create_chat():
    try:
        data = request.get_json(force=True)
        db = load_db()
        new_chat = {
            "id": str(datetime.now().timestamp()), "name": data.get('name'), "username": data.get('username'),
            "type": data.get('type'), "owner": data.get('owner', '').lower(),
            "participants": [data.get('owner', '').lower()], "avatar": data.get('avatar'),
            "description": data.get('description'), "subscribers": 1, "messages": [],
            "verified": False, "created_at": datetime.now().isoformat()
        }
        db['chats'].insert(0, new_chat)
        save_db(db)
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"❌ Ошибка create_chat: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/buy_premium', methods=['POST'])
def buy_premium():
    try:
        data = request.get_json(force=True)
        db = load_db()
        username = data.get('username', '').lower()
        if username in db['users']:
            save_payment(username)
            db['users'][username]['payment_pending'] = True
            save_db(db)
            return jsonify({"success": True, "message": "Заявка отправлена!"})
        return jsonify({"success": False}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка buy_premium: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/get_user_profile', methods=['POST'])
def get_user_profile():
    try:
        data = request.get_json(force=True)
        db = load_db()
        target = data.get('username', '').lower()
        current = data.get('current_user', '').lower()
        if target in db['users']:
            user = db['users'][target]
            return jsonify({
                "success": True,
                "user": {
                    "username": user['username'], "avatar": user.get('avatar'), "bio": user.get('bio', ''),
                    "status": user.get('status', ''), "premium": user.get('premium', False) or check_premium(target),
                    "verified": user.get('verified', False) or is_verified(target),
                    "is_contact": target in db.get('contacts', {}).get(current, []),
                    "is_blocked": target in db.get('blocked', {}).get(current, []),
                    "blocked_me": current in db.get('blocked', {}).get(target, []),
                    "gifts": user.get('gifts', []), "show_gifts": user.get('show_gifts', True)
                }
            })
        return jsonify({"success": False}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка get_user_profile: {e}")
        return jsonify({"success": False}), 500


@app.route('/api/get_crowns_info', methods=['GET'])
def get_crowns_info():
    return jsonify({"total": CROWN_LIMIT, "sold": load_crowns_sold(), "available": get_crowns_available()})


@app.route('/api/get_balloons_info', methods=['GET'])
def get_balloons_info():
    return jsonify({
        "total": BALLOON_LIMIT, "sold": load_balloons_sold(), "available": get_balloons_available(),
        "upgrade_cost": 250, "backgrounds": NFT_BACKGROUNDS_BALLOON, "patterns": NFT_PATTERNS_BALLOON
    })


@app.route('/api/get_planets_info', methods=['GET'])
def get_planets_info():
    return jsonify({
        "total": PLANET_LIMIT, "sold": load_planets_sold(), "available": get_planets_available(),
        "upgrade_cost": 250, "backgrounds": NFT_BACKGROUNDS_PLANET, "patterns": NFT_PATTERNS_PLANET,
        "model": NFT_MODEL_PLANET
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    db_size = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
    backup_count = len(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith(os.path.basename(DB_FILE) + '.')]) if os.path.exists(
        BACKUP_DIR) else 0
    last_backup = None
    if backup_count > 0:
        backups = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if
                          f.startswith(os.path.basename(DB_FILE) + '.')],
                         key=lambda x: os.path.getmtime(x), reverse=True)
        if backups:
            last_backup = datetime.fromtimestamp(os.path.getmtime(backups[0])).isoformat()
    return jsonify({
        "status": "ok",
        "db_exists": os.path.exists(DB_FILE),
        "db_size_mb": round(db_size / 1024 / 1024, 2),
        "db_limit_mb": MAX_DB_SIZE_BYTES // 1024 // 1024,
        "backup_count": backup_count,
        "max_backups": MAX_BACKUPS_TO_KEEP,
        "last_backup": last_backup,
        "next_backup_in_minutes": BACKUP_INTERVAL_MINUTES,
        "auto_delete_disabled": not AUTO_DELETE_OLD_DATA,
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/backup_now', methods=['POST'])
def backup_now():
    try:
        data = request.get_json(force=True) or {}
        admin = data.get('admin', '').lower()
        if admin not in ADMINS:
            return jsonify({"success": False, "message": "Только админ"}), 403
        backed_up = []
        for filepath in [DB_FILE, BALANCE_FILE, CROWN_SOLD_FILE, BALLOON_SOLD_FILE, PLANET_SOLD_FILE, NFT_FILE]:
            if os.path.exists(filepath) and create_backup(filepath):
                backed_up.append(filepath)
        return jsonify({"success": True, "message": f"Бэкап: {len(backed_up)} файлов", "files": backed_up})
    except Exception as e:
        logger.error(f"❌ Ошибка backup_now: {e}")
        return jsonify({"success": False, "message": "Ошибка"}), 500


# === ЗАПУСК СЕРВЕРА ===
if __name__ == '__main__':
    HOST_IP = '192.168.4.238'
    PORT = 5000

    print("\n" + "=" * 70)
    print("🚀 ARTgram Server v2.4 запущен!")
    print(f"📱 Доступен: http://{HOST_IP}:{PORT}")
    print(f"💰 Балансы: {BALANCE_FILE}")
    print(f"🎁 NFT: {NFT_FILE}")
    print(
        f"👑 Корон: {load_crowns_sold()}/{CROWN_LIMIT} | 🎈 Шаров: {load_balloons_sold()}/{BALLOON_LIMIT} | 🪐 Планет: {load_planets_sold()}/{PLANET_LIMIT}")
    print(f"✅ Верификация: {VERIF_FILE}")
    print(f"⏰ Бэкапы: каждые {BACKUP_INTERVAL_MINUTES} минут — ❌ НИКОГДА НЕ УДАЛЯЮТСЯ")
    print(f"❌ Галочки прочтения: ОТКЛЮЧЕНЫ")
    print(f"🔍 Health: http://{HOST_IP}:{PORT}/api/health")
    print("=" * 70 + "\n")

    start_backup_scheduler()

    import sys
    from werkzeug.serving import run_simple

    try:
        run_simple(HOST_IP, PORT, app, use_reloader=False, use_debugger=False, threaded=True)
    except OSError as e:
        if e.errno == 98:
            logger.critical(f"🚨 Порт {PORT} занят! Остановите другой процесс или измените порт.")
        else:
            logger.critical(f"🚨 Ошибка запуска: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("👋 Сервер остановлен пользователем")
    except Exception as e:
        logger.critical(f"🚨 Критическая ошибка: {e}")