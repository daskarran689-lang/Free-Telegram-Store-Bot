import flask
from datetime import datetime, timedelta, timezone
import requests

# Vietnam timezone (UTC+7)
VN_TIMEZONE = timezone(timedelta(hours=7))
import time
import logging
from flask_session import Session
import telebot
from flask import Flask, request, jsonify
from telebot import types
import random
import os
import os.path
import re
import threading
from InDMDevDB import *
from purchase import *
from InDMCategories import *
import time
from tempmail_client import TempMailClient
from telebot.types import LabeledPrice, PreCheckoutQuery, SuccessfulPayment, ShippingOption
import json
from dotenv import load_dotenv
from languages import get_text, get_user_lang, set_user_lang, LANGUAGES, get_button_text

# Import performance optimizations
from performance import (
    is_admin_cached, check_rate_limit, background,
    notify_admin_async, add_user_async, has_purchased_cached,
    get_products_cached, get_promotion_cached, invalidate_user_purchase_cache,
    invalidate_promotion_cache, warm_caches, get_all_cache_stats,
    user_cache, admin_cache
)

# Load environment variables
load_dotenv('config.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# M""M M"""""""`YM M""""""'YMM M"""""`'"""`YM M""""""'YMM MM""""""""`M M""MMMMM""M 
# M  M M  mmmm.  M M  mmmm. `M M  mm.  mm.  M M  mmmm. `M MM  mmmmmmmM M  MMMMM  M 
# M  M M  MMMMM  M M  MMMMM  M M  MMM  MMM  M M  MMMMM  M M`      MMMM M  MMMMP  M 
# M  M M  MMMMM  M M  MMMMM  M M  MMM  MMM  M M  MMMMM  M MM  MMMMMMMM M  MMMM' .M 
# M  M M  MMMMM  M M  MMMM' .M M  MMM  MMM  M M  MMMM' .M MM  MMMMMMMM M  MMP' .MM 
# M  M M  MMMMM  M M       .MM M  MMM  MMM  M M       .MM MM        .M M     .dMMM 
# MMMM MMMMMMMMMMM MMMMMMMMMMM MMMMMMMMMMMMMM MMMMMMMMMMM MMMMMMMMMMMM MMMMMMMMMMM 

# Flask connection 
flask_app = Flask(__name__)
flask_app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Bot connection
# Support both RENDER_EXTERNAL_URL (Render) and NGROK_HTTPS_URL (local dev)
webhook_url = os.getenv('RENDER_EXTERNAL_URL') or os.getenv('NGROK_HTTPS_URL')
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
store_currency = os.getenv('STORE_CURRENCY', 'USD')
default_admin_id = os.getenv('ADMIN_ID', '')

# TempMail.fish Premium credentials
TEMPMAIL_EMAIL = os.getenv('TEMPMAIL_EMAIL', '')
TEMPMAIL_PASSWORD = os.getenv('TEMPMAIL_PASSWORD', '')

# PayOS credentials
PAYOS_CLIENT_ID = os.getenv('PAYOS_CLIENT_ID', '')
PAYOS_API_KEY = os.getenv('PAYOS_API_KEY', '')
PAYOS_CHECKSUM_KEY = os.getenv('PAYOS_CHECKSUM_KEY', '')

if not webhook_url or not bot_token:
    logger.error("Missing required environment variables: RENDER_EXTERNAL_URL/NGROK_HTTPS_URL or TELEGRAM_BOT_TOKEN")
    exit(1)

# PERFORMANCE: Enable threaded mode for concurrent request handling
bot = telebot.TeleBot(bot_token, threaded=True, num_threads=4)

# IMPORTANT: Setup webhook in background to not block Flask startup
# Render requires port to be open within 60 seconds
def setup_webhook_background():
    """Setup webhook and bot commands in background"""
    try:
        bot.remove_webhook()
        
        base_url = (webhook_url or "").rstrip("/")
        public_webhook = f"{base_url}/webhook"
        
        bot.set_webhook(url=public_webhook)
        logger.info(f"Webhook set successfully to {public_webhook}")
        
        # Set bot commands menu
        commands = [
            types.BotCommand("start", "Khởi động bot"),
            types.BotCommand("menu", "Về trang chủ"),
            types.BotCommand("buy", "Mua hàng"),
            types.BotCommand("orders", "Xem đơn hàng"),
            types.BotCommand("support", "Hỗ trợ"),
            types.BotCommand("help", "Xem hướng dẫn")
        ]
        bot.set_my_commands(commands)
        logger.info("Bot commands menu set successfully")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# Start webhook setup in background thread
webhook_thread = threading.Thread(target=setup_webhook_background, daemon=True)
webhook_thread.start()
logger.info("Webhook setup started in background")

# Helper function to check if user is admin (CACHED for performance)
def is_admin(user_id):
    """Check if user_id is an admin - uses cache for speed"""
    return is_admin_cached(user_id, default_admin_id)

# Maintenance mode - when True, only admins can use the bot
maintenance_mode = False

# Upgrade product mode - when False, "Up lại Canva Edu" product is hidden
upgrade_product_enabled = True

# Individual product toggles
canva_product_enabled = True
slot_product_enabled = True
new_product_enabled = True

# Global sales mode - when False, all products are temporarily not for sale
sales_enabled = True

def is_maintenance_mode():
    """Check if bot is in maintenance mode"""
    return maintenance_mode

def set_maintenance_mode(enabled: bool):
    """Enable/disable maintenance mode"""
    global maintenance_mode
    maintenance_mode = enabled
    return maintenance_mode

def is_upgrade_product_enabled():
    """Check if upgrade product is enabled"""
    return upgrade_product_enabled

def set_upgrade_product_enabled(enabled: bool):
    """Enable/disable upgrade product"""
    global upgrade_product_enabled
    upgrade_product_enabled = enabled
    return upgrade_product_enabled

def set_canva_product_enabled(enabled: bool):
    global canva_product_enabled
    canva_product_enabled = enabled
    return canva_product_enabled

def set_slot_product_enabled(enabled: bool):
    global slot_product_enabled
    slot_product_enabled = enabled
    return slot_product_enabled

def set_new_product_enabled(enabled: bool):
    global new_product_enabled
    new_product_enabled = enabled
    return new_product_enabled

def is_sales_enabled():
    """Check if selling is enabled for all products"""
    return sales_enabled

def set_sales_enabled(enabled: bool):
    """Enable/disable selling for all products"""
    global sales_enabled
    sales_enabled = enabled
    return sales_enabled

# ============== DYNAMIC PRICE CONFIGURATION ==============
PRICE_CONFIG_FILE = "price_config.json"

# Default prices
DEFAULT_PRICE_CONFIG = {
    "canva_bh3": {"tier1": 199000, "tier10": 159000, "tier50": 109000},
    "canva_kbh": {"tier1": 40000, "tier10": 20000, "tier50": 10000},
    "upgrade_bh3": 250000,
    "upgrade_kbh": 100000,
    "slot_price": 15000,
    "new_product_price": 35000,
    "new_product_name": "Slot Youtube Premium",
    "new_product_packages": {
        "1m": {"name": "1 Tháng", "price": 35000},
        "3m": {"name": "3 Tháng", "price": 99000},
        "6m": {"name": "6 Tháng", "price": 179000},
        "1y": {"name": "1 Năm", "price": 249000}
    }
}

def load_price_config():
    """Load price config from JSON file, fallback to defaults"""
    try:
        if os.path.exists(PRICE_CONFIG_FILE):
            with open(PRICE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # Merge with defaults to ensure all keys exist
            merged = DEFAULT_PRICE_CONFIG.copy()
            for key in merged:
                if key in config:
                    merged[key] = config[key]
            return merged
    except Exception as e:
        logger.error(f"Failed to load price config: {e}")
    return DEFAULT_PRICE_CONFIG.copy()

def save_price_config(config):
    """Save price config to JSON file"""
    try:
        with open(PRICE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("Price config saved successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to save price config: {e}")
        return False

# Load prices at startup
price_config = load_price_config()

def get_price_config():
    """Get current price config"""
    return price_config

def update_price_config(key, value):
    """Update a price config value and save"""
    global price_config
    price_config[key] = value
    save_price_config(price_config)
    return price_config

def get_new_product_name():
    """Get the configured name for the new product"""
    return price_config.get("new_product_name", "Sản phẩm mới")

def get_new_product_packages():
    """Get the package options for new product (YouTube Premium)"""
    default_packages = {
        "1m": {"name": "1 Tháng", "price": 35000},
        "3m": {"name": "3 Tháng", "price": 90000},
        "6m": {"name": "6 Tháng", "price": 160000},
        "1y": {"name": "1 Năm", "price": 290000}
    }
    return price_config.get("new_product_packages", default_packages)

def get_package_label(package_type):
    """Get display label for a package type"""
    packages = get_new_product_packages()
    pkg = packages.get(package_type, {})
    return pkg.get("name", package_type)

# State for price editing flow
pending_price_edit = {}

# State for product renaming flow
pending_product_rename = {}

def check_maintenance(user_id):
    """Check if user can access bot (returns True if allowed)"""
    if not maintenance_mode:
        return True
    return is_admin(user_id)

def send_maintenance_message(message):
    """Send maintenance mode message to user"""
    bot.send_message(message.chat.id, "🔧 *BOT ĐANG BẢO TRÌ*\n\nVui lòng quay lại sau!\nXin lỗi vì sự bất tiện này.", parse_mode='Markdown')

def maintenance_check(func):
    """Decorator to check maintenance mode before executing handler"""
    def wrapper(message):
        user_id = message.from_user.id
        if maintenance_mode and not is_admin(user_id):
            send_maintenance_message(message)
            return
        return func(message)
    wrapper.__name__ = func.__name__
    return wrapper

# Hàm lấy display name cho user
def get_user_display_name(message):
    """Lấy tên hiển thị: @username nếu có, hoặc first_name - user_id"""
    if message.from_user.username:
        return f"@{message.from_user.username}"
    else:
        first_name = message.from_user.first_name or "User"
        return f"{first_name} - {message.from_user.id}"

def get_user_display_name_from_data(username, user_id):
    """Lấy tên hiển thị từ data: @username nếu có, hoặc user_id"""
    if username and username != "user" and username != "None":
        return f"@{username}"
    else:
        return f"ID: {user_id}"

# Helper: Check if user wants to cancel
def is_cancel_action(text):
    """Check if user wants to cancel the current action"""
    cancel_keywords = ["❌ Hủy", "🏠 Trang chủ", "/start", "Hủy", "Cancel"]
    return any(kw in text for kw in cancel_keywords) if text else False

# Helper: Create keyboard with Cancel button
def create_cancel_keyboard():
    """Create a simple keyboard with Cancel button"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="❌ Hủy"))
    return keyboard

# Handler for Cancel button
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "❌ Hủy")
def handle_cancel(message):
    """Handle cancel action - return to home"""
    # Clear slot email state if exists
    if message.from_user.id in pending_slot_email_state:
        del pending_slot_email_state[message.from_user.id]
    send_welcome(message)

# Handler for Cancel slot button
@bot.message_handler(content_types=["text"], func=lambda message: "Hủy mua slot" in message.text)
def handle_cancel_slot(message):
    """Handle cancel slot purchase"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Delete the slot product message if exists
    if id in pending_slot_email_state:
        msg_id = pending_slot_email_state[id].get("message_id")
        if msg_id:
            try:
                bot.delete_message(id, msg_id)
            except:
                pass
        del pending_slot_email_state[id]
    
    bot.send_message(id, "❌ Đã hủy mua slot!", reply_markup=create_main_keyboard(lang, id))

# Hàm thông báo cho admin (NON-BLOCKING)
def notify_admin(action, display_name, user_id=None, extra=""):
    """Gửi thông báo ngắn gọn cho admin - chạy background không block"""
    if default_admin_id:
        msg = f"📌 {display_name}: {action}"
        if extra:
            msg += f" - {extra}"
        notify_admin_async(bot, default_admin_id, msg)

# Add default admin from env in background (non-blocking)
def add_default_admin_background():
    """Add default admin in background thread"""
    if default_admin_id:
        try:
            # Wait a bit for DB to be ready
            time.sleep(5)
            existing_admins = GetDataFromDB.GetAdminIDsInDB() or []
            admin_ids = [str(admin[0]) for admin in existing_admins]
            if str(default_admin_id) not in admin_ids:
                CreateDatas.AddAdmin(int(default_admin_id), "env_admin")
                logger.info(f"Default admin {default_admin_id} added from environment variable")
            else:
                logger.info(f"Admin {default_admin_id} already exists")
        except Exception as e:
            logger.error(f"Error adding default admin: {e}")

# Start in background
admin_thread = threading.Thread(target=add_default_admin_background, daemon=True)
admin_thread.start()

# Process webhook calls
logger.info("Shop Starting... Flask will be ready shortly")

@flask_app.route("/", methods=["GET", "HEAD"])
def health():
    # Render health check hits this route (HEAD /)
    return "ok", 200


@flask_app.route("/", methods=["POST"])
@flask_app.route("/webhook", methods=["POST"])
def telegram_webhook():
    """Handle incoming webhook requests from Telegram - OPTIMIZED for speed"""
    try:
        ctype = (request.headers.get("content-type") or "").lower()

        if ctype.startswith("application/json"):
            json_string = request.get_data(as_text=True)
            
            # PERFORMANCE: Process update in background thread
            # This allows webhook to respond immediately to Telegram
            def process_update():
                try:
                    update = telebot.types.Update.de_json(json_string)
                    bot.process_new_updates([update])
                except Exception as e:
                    logger.error(f"Error processing update: {e}")
            
            # Submit to background processor
            background.submit(process_update)
            
            # Return immediately - don't wait for processing
            return "ok", 200

        logger.warning(f"Invalid content type in webhook request: {ctype}")
        return "forbidden", 403

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return "ok", 200  # Always return 200 to prevent Telegram retries


# PayOS helper functions
import hashlib
import hmac

def create_payos_signature(data, checksum_key):
    """Create signature for PayOS webhook verification"""
    sorted_data = sorted(data.items())
    data_str = "&".join([f"{k}={v}" for k, v in sorted_data if k != "signature"])
    signature = hmac.new(checksum_key.encode(), data_str.encode(), hashlib.sha256).hexdigest()
    return signature

def verify_payos_webhook(data, signature, checksum_key):
    """Verify PayOS webhook signature"""
    calculated_sig = create_payos_signature(data, checksum_key)
    return calculated_sig == signature

@flask_app.route("/payos-webhook", methods=["POST", "GET"])
def payos_webhook():
    """Handle incoming webhook from PayOS for payment confirmation"""
    if request.method == "GET":
        return "ok", 200
    
    try:
        data = request.json
        logger.info(f"PayOS webhook received: {data}")
        
        if not data:
            return "ok", 200
        
        # PayOS webhook format
        webhook_data = data.get("data", {})
        code = data.get("code")
        
        # code = "00" means success
        if code != "00":
            logger.info(f"PayOS webhook code not success: {code}")
            return "ok", 200
        
        order_code = webhook_data.get("orderCode")
        amount = webhook_data.get("amount", 0)
        description = webhook_data.get("description", "")
        
        if not order_code:
            return "ok", 200
        
        # order_code is our ordernumber
        ordernumber = int(order_code)
        
        # Check if order exists in pending_orders_info
        if ordernumber not in pending_orders_info:
            logger.warning(f"PayOS: Order {ordernumber} not found in pending orders")
            return "ok", 200
        
        order_info = pending_orders_info[ordernumber]
        user_id = order_info["user_id"]
        username = order_info["username"]
        product_name = order_info["product_name"]
        price = order_info["price"]
        quantity = order_info["quantity"]
        product_number = order_info["product_number"]
        orderdate = order_info["orderdate"]
        is_upgrade = order_info.get("is_upgrade", False)  # Check if this is an upgrade order
        is_slot = order_info.get("is_slot", False)  # Check if this is a slot order
        
        # Get user language
        lang = get_user_lang(user_id)
        
        # Delete QR message first
        if ordernumber in pending_qr_messages:
            try:
                msg_info = pending_qr_messages[ordernumber]
                bot.delete_message(msg_info["chat_id"], msg_info["message_id"])
            except:
                pass
            del pending_qr_messages[ordernumber]
        
        # Handle UPGRADE orders differently - don't assign new accounts
        if is_upgrade:
            # Save order to database (no product keys for upgrade)
            CreateDatas.AddOrder(
                ordernumber, user_id, username, product_name, price, product_number, 
                payment_id=str(webhook_data.get("paymentLinkId", "")),
                paidmethod='PayOS'
            )
            
            # Send success message for UPGRADE order
            warranty_type = order_info.get("warranty_type", "kbh")
            warranty_label = "BH 3 tháng" if warranty_type == "bh3" else "KBH"
            
            try:
                price_num = int(float(str(price).replace(',', '')))
            except:
                price_num = price
            
            buyer_msg = f"✅ *THANH TOÁN THÀNH CÔNG!*\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"🆔 Mã đơn hàng: `{ordernumber}`\n"
            buyer_msg += f"📅 Ngày mua: _{orderdate}_\n"
            buyer_msg += f"📦 Gói: *{product_name}*\n"
            buyer_msg += f"💰 Giá: *{price_num:,} {store_currency}*\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"📌 *BƯỚC TIẾP THEO:*\n"
            buyer_msg += f"Vui lòng inbox Admin kèm:\n"
            buyer_msg += f"• Mã đơn hàng: `{ordernumber}`\n"
            buyer_msg += f"• Tài khoản Canva của bạn\n"
            buyer_msg += f"• Mật khẩu (nếu có)\n"
            buyer_msg += f"• Cung cấp mã xác thực khi Admin yêu cầu\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"⏳ Admin sẽ xử lý trong vòng 24h!"
            
            try:
                bot.send_message(user_id, buyer_msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"PayOS: Error sending upgrade buyer message: {e}")
                bot.send_message(user_id, buyer_msg.replace("*", "").replace("_", "").replace("`", ""))
            
            # Update reply keyboard (no success photo for upgrade - customer already has account)
            nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            nav_keyboard.row(types.KeyboardButton(text="🛍 Đơn hàng"), types.KeyboardButton(text="📞 Hỗ trợ"))
            nav_keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
            bot.send_message(user_id, "👆 Vui lòng inbox Admin theo hướng dẫn trên.", reply_markup=nav_keyboard)
            
            # Edit admin notification for UPGRADE
            admin_msg = f"✅ *Đơn UP LẠI CANVA đã thanh toán!*\n"
            admin_msg += f"━━━━━━━━━━━━━━\n"
            admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
            admin_msg += f"👤 Khách: @{username}\n"
            admin_msg += f"📦 Sản phẩm: {product_name}\n"
            admin_msg += f"💰 Số tiền: {amount:,} VND\n"
            admin_msg += f"━━━━━━━━━━━━━━\n"
            admin_msg += f"⏳ *Chờ khách inbox thông tin tài khoản Canva*"
            
            if ordernumber in pending_admin_messages:
                for msg_info in pending_admin_messages[ordernumber]:
                    try:
                        bot.edit_message_text(admin_msg, msg_info["chat_id"], msg_info["message_id"], parse_mode="Markdown")
                    except:
                        pass
                del pending_admin_messages[ordernumber]
            else:
                admins = GetDataFromDB.GetAdminIDsInDB() or []
                for admin in admins:
                    try:
                        bot.send_message(admin[0], admin_msg, parse_mode="Markdown")
                    except:
                        pass
            
            # Cleanup
            if ordernumber in pending_orders_info:
                del pending_orders_info[ordernumber]
            if ordernumber in pending_order_quantities:
                del pending_order_quantities[ordernumber]
            
            logger.info(f"PayOS: Upgrade order {ordernumber} confirmed!")
            return "ok", 200
        
        # === SLOT ORDER - notify admin with email, wait for manual processing ===
        if is_slot:
            canva_email = order_info.get("canva_email", "")
            
            # Save order to database (no product keys for slot)
            CreateDatas.AddOrder(
                ordernumber, user_id, username, product_name, price, product_number, 
                payment_id=str(webhook_data.get("paymentLinkId", "")),
                paidmethod='PayOS'
            )
            
            try:
                price_num = int(float(str(price).replace(',', '')))
            except:
                price_num = price
            
            # Send success message for SLOT order
            buyer_msg = f"✅ *THANH TOÁN THÀNH CÔNG!*\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"🆔 Mã đơn hàng: `{ordernumber}`\n"
            buyer_msg += f"📅 Ngày mua: _{orderdate}_\n"
            buyer_msg += f"📦 Gói: *{product_name}*\n"
            buyer_msg += f"📧 Email Canva: `{canva_email}`\n"
            buyer_msg += f"💰 Giá: *{price_num:,} {store_currency}*\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"📤 *Đã gửi yêu cầu đến Admin!*\n"
            buyer_msg += f"⏳ Vui lòng đợi xử lý, khi Admin xử lý xong bot sẽ thông báo ngay cho bạn."
            
            try:
                bot.send_message(user_id, buyer_msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"PayOS: Error sending slot buyer message: {e}")
                bot.send_message(user_id, buyer_msg.replace("*", "").replace("_", "").replace("`", ""))
            
            # Update reply keyboard (no success photo for slot - customer already has account)
            nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            nav_keyboard.row(types.KeyboardButton(text="🛍 Đơn hàng"), types.KeyboardButton(text="📞 Hỗ trợ"))
            nav_keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
            update_reply_keyboard(user_id, nav_keyboard)
            
            # Edit admin notification for SLOT with button
            admin_msg = f"✅ *Đơn SLOT CANVA đã thanh toán!*\n"
            admin_msg += f"━━━━━━━━━━━━━━\n"
            admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
            admin_msg += f"👤 Khách: @{username} (ID: `{user_id}`)\n"
            admin_msg += f"📦 Sản phẩm: {product_name}\n"
            admin_msg += f"📧 Email Canva: `{canva_email}`\n"
            admin_msg += f"💰 Số tiền: {amount:,} VND\n"
            admin_msg += f"━━━━━━━━━━━━━━\n"
            admin_msg += f"⏳ *Chờ xử lý thêm slot cho khách*"
            
            # Save email for later use when admin clicks done
            slot_order_emails[ordernumber] = canva_email
            
            # Create button for admin to mark as done
            admin_inline_kb = types.InlineKeyboardMarkup()
            admin_inline_kb.add(types.InlineKeyboardButton(
                text="✅ Đã xử lý xong",
                callback_data=f"slot_done_{ordernumber}_{user_id}"
            ))
            
            if ordernumber in pending_admin_messages:
                for msg_info in pending_admin_messages[ordernumber]:
                    try:
                        bot.edit_message_text(admin_msg, msg_info["chat_id"], msg_info["message_id"], parse_mode="Markdown", reply_markup=admin_inline_kb)
                    except:
                        pass
                del pending_admin_messages[ordernumber]
            else:
                admins = GetDataFromDB.GetAdminIDsInDB() or []
                for admin in admins:
                    try:
                        bot.send_message(admin[0], admin_msg, parse_mode="Markdown", reply_markup=admin_inline_kb)
                    except:
                        pass
            
            # Cleanup
            if ordernumber in pending_orders_info:
                del pending_orders_info[ordernumber]
            if ordernumber in pending_order_quantities:
                del pending_order_quantities[ordernumber]
            
            logger.info(f"PayOS: Slot order {ordernumber} confirmed!")
            return "ok", 200

        # === CUSTOM ORDER (new product / YouTube Premium) - manual fulfillment ===
        is_custom = order_info.get("is_custom", False)
        if is_custom:
            # Get extra info from pending order
            google_email = order_info.get("google_email", "")
            package_label = order_info.get("package_label", "")
            
            # Save order to database
            CreateDatas.AddOrder(
                ordernumber, user_id, username, product_name, price, product_number,
                payment_id=str(webhook_data.get("paymentLinkId", "")),
                paidmethod='PayOS'
            )

            try:
                price_num = int(float(str(price).replace(',', '')))
            except:
                price_num = price

            buyer_msg = f"✅ *THANH TOÁN THÀNH CÔNG!*\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"🆔 Mã đơn hàng: `{ordernumber}`\n"
            buyer_msg += f"📅 Ngày mua: _{orderdate}_\n"
            buyer_msg += f"📦 Sản phẩm: *{product_name}*\n"
            if package_label:
                buyer_msg += f"📋 Gói: *{package_label}*\n"
            if google_email:
                buyer_msg += f"📧 Email: `{google_email}`\n"
            buyer_msg += f"💰 Giá: *{price_num:,} {store_currency}*\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"📤 *Đã gửi yêu cầu đến Admin!*\n"
            buyer_msg += f"⏳ Vui lòng đợi xử lý, khi Admin xử lý xong bot sẽ thông báo ngay cho bạn."

            try:
                bot.send_message(user_id, buyer_msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"PayOS: Error sending custom buyer message: {e}")
                bot.send_message(user_id, buyer_msg.replace("*", "").replace("_", "").replace("`", ""))

            # Update reply keyboard
            nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            nav_keyboard.row(types.KeyboardButton(text="🛍 Đơn hàng"), types.KeyboardButton(text="📞 Hỗ trợ"))
            nav_keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
            try:
                update_reply_keyboard(user_id, nav_keyboard)
            except:
                pass

            # Edit admin notification with "Done" button
            base_product_name = get_new_product_name()
            admin_msg = f"✅ *Đơn {base_product_name} đã thanh toán!*\n"
            admin_msg += f"━━━━━━━━━━━━━━\n"
            admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
            admin_msg += f"👤 Khách: @{username} (ID: `{user_id}`)\n"
            admin_msg += f"📦 Sản phẩm: {product_name}\n"
            if package_label:
                admin_msg += f"📋 Gói: *{package_label}*\n"
            if google_email:
                admin_msg += f"📧 Email khách: `{google_email}`\n"
            admin_msg += f"💰 Số tiền: {amount:,} VND\n"
            admin_msg += f"━━━━━━━━━━━━━━\n"
            admin_msg += f"⏳ *Chờ admin giao hàng cho khách*"

            # Save order info for delivery later
            pending_newprod_orders[str(ordernumber)] = {
                "google_email": google_email,
                "package_label": package_label,
                "product_name": product_name
            }

            # Create button for admin to mark as done
            admin_inline_kb = types.InlineKeyboardMarkup()
            admin_inline_kb.add(types.InlineKeyboardButton(
                text="📦 Giao hàng thủ công",
                callback_data=f"newprod_done_{ordernumber}_{user_id}"
            ))

            if ordernumber in pending_admin_messages:
                for msg_info in pending_admin_messages[ordernumber]:
                    try:
                        bot.edit_message_text(admin_msg, msg_info["chat_id"], msg_info["message_id"], parse_mode="Markdown", reply_markup=admin_inline_kb)
                    except:
                        pass
                del pending_admin_messages[ordernumber]
            else:
                admins = GetDataFromDB.GetAdminIDsInDB() or []
                for admin in admins:
                    try:
                        bot.send_message(admin[0], admin_msg, parse_mode="Markdown", reply_markup=admin_inline_kb)
                    except:
                        pass

            # Cleanup
            if ordernumber in pending_orders_info:
                del pending_orders_info[ordernumber]
            if ordernumber in pending_order_quantities:
                del pending_order_quantities[ordernumber]

            logger.info(f"PayOS: Custom order {ordernumber} confirmed!")
            return "ok", 200
        
        # === NORMAL ORDER (Canva Edu Admin) - auto or manual fulfillment ===
        warranty_type = order_info.get("warranty_type", "kbh")
        warranty_label = "BH 3 tháng" if warranty_type == "bh3" else "KBH"
        
        # Save order to database
        CreateDatas.AddOrder(
            ordernumber, user_id, username, product_name, price, product_number, 
            payment_id=str(webhook_data.get("paymentLinkId", "")),
            paidmethod='PayOS'
        )
        
        # Check promotion
        promo_msg = ""
        promo_info = PromotionDB.get_promotion_info()
        if promo_info and promo_info["is_active"]:
            sold_before = promo_info["sold_count"]
            max_promo = promo_info["max_count"]
            if sold_before < max_promo:
                remaining_slots = max_promo - sold_before
                promo_bonus = min(quantity, remaining_slots)
                promo_slot_start = sold_before + 1
                promo_slot_end = min(sold_before + quantity, max_promo)
                
                PromotionDB.increment_sold_count(quantity)
                
                if promo_bonus == 1:
                    slot_display = f"{promo_slot_start}"
                else:
                    slot_display = f"{promo_slot_start}-{promo_slot_end}"
                
                promo_msg = f"\n\n🎉 *CHÚC MỪNG! BẠN ĐƯỢC KHUYẾN MÃI MUA 1 TẶNG 1!*\n"
                promo_msg += f"━━━━━━━━━━━━━━\n"
                promo_msg += f"🎯 Suất khuyến mãi: slot {slot_display}\n"
                promo_msg += f"📩 Inbox Admin kèm mã đơn `{ordernumber}` để được tặng thêm {promo_bonus} tài khoản!"
        
        # Check if we have available accounts in stock for AUTO delivery
        available_accounts = CanvaAccountDB.get_available_accounts(quantity)
        
        try:
            price_num = int(float(str(price).replace(',', '')))
        except:
            price_num = price
        
        if available_accounts and len(available_accounts) >= quantity:
            # === AUTO DELIVERY - We have stock ===
            logger.info(f"PayOS: Auto-delivering {quantity} accounts for order {ordernumber}")
            
            # Assign accounts to buyer
            assigned_accounts = []
            for account in available_accounts[:quantity]:
                account_id = account[0]
                email = account[1]
                authkey = account[2]
                
                # Assign to buyer
                CanvaAccountDB.assign_account_to_buyer(account_id, user_id, ordernumber)
                assigned_accounts.append({"email": email, "authkey": authkey})
            
            # Build account details message
            accounts_text = ""
            otp_buttons = []
            for i, acc in enumerate(assigned_accounts, 1):
                accounts_text += f"\n🔑 *Tài khoản Canva:*\n"
                accounts_text += f"{acc['email']}\n"
                if acc.get('authkey'):
                    accounts_text += f"🔐 Mật khẩu: `{acc['authkey']}`\n"
                
                # Add OTP button for each account
                otp_buttons.append(types.InlineKeyboardButton(
                    text=f"🔑 Lấy OTP: {acc['email'][:20]}...",
                    callback_data=f"otp_{acc['email']}"
                ))
            
            # Send success message with accounts
            buyer_msg = f"✅ *THANH TOÁN THÀNH CÔNG!*\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"🆔 Mã đơn hàng: `{ordernumber}`\n"
            buyer_msg += f"📅 Ngày mua: _{orderdate}_\n"
            buyer_msg += f"📦 Gói: *{product_name}*\n"
            buyer_msg += f"🛡 Loại: *{warranty_label}*\n"
            buyer_msg += f"💰 Giá: *{price_num:,} {store_currency}*\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━"
            buyer_msg += accounts_text
            buyer_msg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"👇 _Bấm nút bên dưới để lấy mã xác thực cho email (dùng cho việc đăng nhập, đổi mail, v.v...)_"
            buyer_msg += promo_msg
            
            # Create inline keyboard with OTP buttons
            inline_kb = types.InlineKeyboardMarkup(row_width=1)
            for btn in otp_buttons:
                inline_kb.add(btn)
            
            # Send with photo (Canva Edu guide)
            canva_guide_photo = "AgACAgUAAxkBAAI6TGmfKrHzbmZvjWhQN7pWcxe8fhozAAIwDWsb-0IAAVWVJ0OvdBs9pgEAAwIAA3kAAzoE"
            
            try:
                bot.send_photo(user_id, photo=canva_guide_photo, caption=buyer_msg, reply_markup=inline_kb, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"PayOS: Error sending auto-delivery photo: {e}")
                # Fallback without photo
                try:
                    bot.send_message(user_id, buyer_msg, reply_markup=inline_kb, parse_mode="Markdown")
                except Exception as e2:
                    logger.error(f"PayOS: Error sending auto-delivery message: {e2}")
                    bot.send_message(user_id, buyer_msg.replace("*", "").replace("_", "").replace("`", ""), reply_markup=inline_kb)
            
            # Update reply keyboard
            nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            nav_keyboard.row(types.KeyboardButton(text="🛍 Đơn hàng"), types.KeyboardButton(text="📞 Hỗ trợ"))
            nav_keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
            update_reply_keyboard(user_id, nav_keyboard)
            
            # Notify admin about auto-delivery
            # Build account list for admin
            accounts_list = ""
            for i, acc in enumerate(assigned_accounts, 1):
                accounts_list += f"\n📧 {acc['email']}"
            
            admin_msg = f"✅ *Đơn CANVA EDU ADMIN đã giao tự động!*\n"
            admin_msg += f"━━━━━━━━━━━━━━\n"
            admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
            admin_msg += f"👤 Khách: @{username} (ID: `{user_id}`)\n"
            admin_msg += f"📦 Sản phẩm: {product_name}\n"
            admin_msg += f"🛡 Loại: {warranty_label}\n"
            admin_msg += f"📦 Số lượng: {quantity}\n"
            admin_msg += f"💰 Số tiền: {amount:,} VND\n"
            admin_msg += f"━━━━━━━━━━━━━━\n"
            admin_msg += f"🤖 *Đã giao tự động từ kho:*"
            admin_msg += accounts_list
            
            if ordernumber in pending_admin_messages:
                for msg_info in pending_admin_messages[ordernumber]:
                    try:
                        bot.edit_message_text(admin_msg, msg_info["chat_id"], msg_info["message_id"], parse_mode="Markdown")
                    except:
                        pass
                del pending_admin_messages[ordernumber]
            else:
                admins = GetDataFromDB.GetAdminIDsInDB() or []
                for admin in admins:
                    try:
                        bot.send_message(admin[0], admin_msg, parse_mode="Markdown")
                    except:
                        pass
            
            logger.info(f"PayOS: Order {ordernumber} auto-delivered successfully!")
            
        else:
            # === MANUAL DELIVERY - No stock available ===
            logger.info(f"PayOS: Manual delivery needed for order {ordernumber} (stock: {len(available_accounts) if available_accounts else 0}/{quantity})")
            
            buyer_msg = f"✅ *THANH TOÁN THÀNH CÔNG!*\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"🆔 Mã đơn hàng: `{ordernumber}`\n"
            buyer_msg += f"📅 Ngày mua: _{orderdate}_\n"
            buyer_msg += f"📦 Sản phẩm: *{product_name}*\n"
            buyer_msg += f"🛡 Loại: *{warranty_label}*\n"
            buyer_msg += f"💰 Giá: *{price_num:,} {store_currency}*\n"
            buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            buyer_msg += f"📤 *Đã gửi yêu cầu đến Admin!*\n"
            buyer_msg += f"⏳ Vui lòng đợi xử lý, khi Admin xử lý xong bot sẽ thông báo ngay cho bạn."
            buyer_msg += promo_msg
            
            try:
                bot.send_message(user_id, buyer_msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"PayOS: Error sending buyer message: {e}")
                bot.send_message(user_id, buyer_msg.replace("*", "").replace("_", "").replace("`", ""))
            
            # Update reply keyboard
            nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            nav_keyboard.row(types.KeyboardButton(text="🛍 Đơn hàng"), types.KeyboardButton(text="📞 Hỗ trợ"))
            nav_keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
            update_reply_keyboard(user_id, nav_keyboard)
            
            # Edit admin notification with "Done" button
            admin_msg = f"✅ *Đơn CANVA EDU ADMIN đã thanh toán!*\n"
            admin_msg += f"━━━━━━━━━━━━━━\n"
            admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
            admin_msg += f"👤 Khách: @{username} (ID: `{user_id}`)\n"
            admin_msg += f"📦 Sản phẩm: {product_name}\n"
            admin_msg += f"🛡 Loại: {warranty_label}\n"
            admin_msg += f"📦 Số lượng: {quantity}\n"
            admin_msg += f"💰 Số tiền: {amount:,} VND\n"
            admin_msg += f"━━━━━━━━━━━━━━\n"
            admin_msg += f"⚠️ *Hết hàng trong kho - cần giao thủ công!*"
            
            # Create button for admin to mark as done
            admin_inline_kb = types.InlineKeyboardMarkup()
            admin_inline_kb.add(types.InlineKeyboardButton(
                text="📦 Giao hàng thủ công",
                callback_data=f"canva_done_{ordernumber}_{user_id}_{warranty_type}"
            ))
            
            if ordernumber in pending_admin_messages:
                for msg_info in pending_admin_messages[ordernumber]:
                    try:
                        bot.edit_message_text(admin_msg, msg_info["chat_id"], msg_info["message_id"], parse_mode="Markdown", reply_markup=admin_inline_kb)
                    except:
                        pass
                del pending_admin_messages[ordernumber]
            else:
                admins = GetDataFromDB.GetAdminIDsInDB() or []
                for admin in admins:
                    try:
                        bot.send_message(admin[0], admin_msg, parse_mode="Markdown", reply_markup=admin_inline_kb)
                    except:
                        pass
        
        # Cleanup
        if ordernumber in pending_orders_info:
            del pending_orders_info[ordernumber]
        if ordernumber in pending_order_quantities:
            del pending_order_quantities[ordernumber]
        
        logger.info(f"PayOS: Order {ordernumber} confirmed!")
        return "ok", 200
        
    except Exception as e:
        logger.error(f"Error processing PayOS webhook: {e}")
        return "ok", 200

# Initialize payment settings
def get_payment_api_key():
    """Get payment API key from database"""
    try:
        api_key = GetDataFromDB.GetPaymentMethodTokenKeysCleintID("Bitcoin")
        return api_key
    except Exception as e:
        logger.error(f"Error getting payment API key: {e}")
        return None

BASE_CURRENCY = store_currency

# PERFORMANCE: Warm caches on startup
warm_caches()

# Create main reply keyboard (buttons at bottom - always visible)
def create_main_keyboard(lang="vi", user_id=None, skip_db_check=False):
    """Create the main user keyboard. If user has purchased, show OTP button.
    OPTIMIZED: Uses performance cache for fast lookup"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="🛒 Mua ngay"))
    
    # Check if user has purchased (FAST - using performance cache)
    has_purchased = False
    if user_id and not skip_db_check:
        has_purchased = has_purchased_cached(user_id)
    
    if has_purchased:
        keyboard.row(types.KeyboardButton(text="🔑 Lấy mã xác thực"))
    
    keyboard.row(
        types.KeyboardButton(text="🛍 Đơn hàng"),
        types.KeyboardButton(text="📞 Hỗ trợ")
    )
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    return keyboard

keyboard = create_main_keyboard()
##################WELCOME MESSAGE + BUTTONS START#########################
#Function to list Products and Categories
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    """Handle callback queries from inline keyboards"""
    try:
        user_id = call.from_user.id
        lang = get_user_lang(user_id)
        
        # Check maintenance mode - only allow admins
        if maintenance_mode and not is_admin(user_id):
            bot.answer_callback_query(call.id, "🔧 Bot đang bảo trì, vui lòng quay lại sau!")
            return
        
        # Check rate limit (anti-spam)
        if not check_rate_limit(user_id):
            bot.answer_callback_query(call.id, "⏳ Thao tác quá nhanh, vui lòng chờ...")
            return
        
        # Handle admin confirm payment - FINAL confirmation (step 2)
        if call.data.startswith("confirm_payment_final_"):
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Chỉ admin mới có quyền!", show_alert=True)
                return
            
            ordernumber = int(call.data.replace("confirm_payment_final_", ""))
            bot.answer_callback_query(call.id, "Đang xử lý giao hàng...")
            
            # Get order info from pending_orders_info
            if ordernumber not in pending_orders_info:
                bot.answer_callback_query(call.id, "❌ Không tìm thấy đơn hàng!", show_alert=True)
                return
            
            order_info = pending_orders_info[ordernumber]
            buyer_id = order_info["user_id"]
            username = order_info["username"]
            product_name = order_info["product_name"]
            price = order_info["price"]
            quantity = order_info["quantity"]
            product_number = order_info["product_number"]
            orderdate = order_info["orderdate"]
            warranty_type = order_info.get("warranty_type", "kbh")
            warranty_label = "BH 3 tháng" if warranty_type == "bh3" else "KBH"
            
            # Save order to database
            CreateDatas.AddOrder(
                ordernumber, buyer_id, username, product_name, price, product_number,
                payment_id="MANUAL_CONFIRM",
                paidmethod='VietQR'
            )
            
            # Check if we have stock for auto delivery
            available_accounts = CanvaAccountDB.get_available_accounts(quantity)
            
            try:
                price_num = int(float(str(price).replace(',', '')))
            except:
                price_num = price
            
            if available_accounts and len(available_accounts) >= quantity:
                # AUTO DELIVERY
                assigned_accounts = []
                for account in available_accounts[:quantity]:
                    account_id = account[0]
                    email = account[1]
                    authkey = account[2]
                    CanvaAccountDB.assign_account_to_buyer(account_id, buyer_id, ordernumber)
                    assigned_accounts.append({"email": email, "authkey": authkey})
                
                # Build message
                accounts_text = ""
                otp_buttons = []
                for i, acc in enumerate(assigned_accounts, 1):
                    accounts_text += f"\n🔑 *Tài khoản Canva:*\n"
                    accounts_text += f"{acc['email']}\n"
                    if acc.get('authkey'):
                        accounts_text += f"🔐 Mật khẩu: `{acc['authkey']}`\n"
                    otp_buttons.append(types.InlineKeyboardButton(
                        text=f"🔑 Lấy OTP: {acc['email'][:20]}...",
                        callback_data=f"otp_{acc['email']}"
                    ))
                
                buyer_msg = f"✅ *THANH TOÁN THÀNH CÔNG!*\n"
                buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                buyer_msg += f"🆔 Mã đơn hàng: `{ordernumber}`\n"
                buyer_msg += f"📅 Ngày mua: _{orderdate}_\n"
                buyer_msg += f"📦 Gói: *{product_name}*\n"
                buyer_msg += f"🛡 Loại: *{warranty_label}*\n"
                buyer_msg += f"💰 Giá: *{price_num:,} {store_currency}*\n"
                buyer_msg += f"━━━━━━━━━━━━━━━━━━━━"
                buyer_msg += accounts_text
                buyer_msg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                buyer_msg += f"👇 _Bấm nút bên dưới để lấy mã xác thực cho email (dùng cho việc đăng nhập, đổi mail, v.v...)_"
                
                inline_kb = types.InlineKeyboardMarkup(row_width=1)
                for btn in otp_buttons:
                    inline_kb.add(btn)
                
                canva_guide_photo = "AgACAgUAAxkBAAI6TGmfKrHzbmZvjWhQN7pWcxe8fhozAAIwDWsb-0IAAVWVJ0OvdBs9pgEAAwIAA3kAAzoE"
                
                try:
                    bot.send_photo(buyer_id, photo=canva_guide_photo, caption=buyer_msg, reply_markup=inline_kb, parse_mode="Markdown")
                except:
                    try:
                        bot.send_message(buyer_id, buyer_msg, reply_markup=inline_kb, parse_mode="Markdown")
                    except:
                        bot.send_message(buyer_id, buyer_msg.replace("*", "").replace("_", "").replace("`", ""), reply_markup=inline_kb)
                
                # Update admin message
                accounts_list = ""
                for i, acc in enumerate(assigned_accounts, 1):
                    accounts_list += f"\n📧 {acc['email']}"
                
                admin_msg = f"✅ *Đơn đã giao tự động!*\n"
                admin_msg += f"━━━━━━━━━━━━━━\n"
                admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
                admin_msg += f"👤 Khách: @{username} (ID: `{buyer_id}`)\n"
                admin_msg += f"📦 Sản phẩm: {product_name}\n"
                admin_msg += f"💰 Số tiền: {price_num:,} VND\n"
                admin_msg += f"━━━━━━━━━━━━━━\n"
                admin_msg += f"🤖 *Đã giao tự động từ kho:*"
                admin_msg += accounts_list
                
                bot.edit_message_text(admin_msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
                
            else:
                # MANUAL DELIVERY
                buyer_msg = f"✅ *THANH TOÁN THÀNH CÔNG!*\n"
                buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                buyer_msg += f"🆔 Mã đơn hàng: `{ordernumber}`\n"
                buyer_msg += f"📅 Ngày mua: _{orderdate}_\n"
                buyer_msg += f"📦 Gói: *{product_name}*\n"
                buyer_msg += f"🛡 Loại: *{warranty_label}*\n"
                buyer_msg += f"💰 Giá: *{price_num:,} {store_currency}*\n"
                buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                buyer_msg += f"📤 *Đã gửi yêu cầu đến Admin!*\n"
                buyer_msg += f"⏳ Vui lòng đợi xử lý, khi Admin xử lý xong bot sẽ thông báo ngay cho bạn."
                
                try:
                    bot.send_message(buyer_id, buyer_msg, parse_mode="Markdown")
                except:
                    bot.send_message(buyer_id, buyer_msg.replace("*", "").replace("_", "").replace("`", ""))
                
                admin_msg = f"✅ *Đã xác nhận thanh toán!*\n"
                admin_msg += f"━━━━━━━━━━━━━━\n"
                admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
                admin_msg += f"👤 Khách: @{username} (ID: `{buyer_id}`)\n"
                admin_msg += f"📦 Sản phẩm: {product_name}\n"
                admin_msg += f"💰 Số tiền: {price_num:,} VND\n"
                admin_msg += f"━━━━━━━━━━━━━━\n"
                admin_msg += f"⚠️ *Hết hàng - cần giao thủ công!*"
                
                manual_kb = types.InlineKeyboardMarkup()
                manual_kb.add(types.InlineKeyboardButton(
                    text="📦 Giao hàng thủ công",
                    callback_data=f"canva_done_{ordernumber}_{buyer_id}_{warranty_type}"
                ))
                
                bot.edit_message_text(admin_msg, call.message.chat.id, call.message.message_id, reply_markup=manual_kb, parse_mode="Markdown")
            
            # Delete QR message
            if ordernumber in pending_qr_messages:
                try:
                    msg_info = pending_qr_messages[ordernumber]
                    bot.delete_message(msg_info["chat_id"], msg_info["message_id"])
                except:
                    pass
                del pending_qr_messages[ordernumber]
            
            # Cleanup
            if ordernumber in pending_orders_info:
                del pending_orders_info[ordernumber]
            if ordernumber in pending_order_quantities:
                del pending_order_quantities[ordernumber]
            
            return
        
        # Handle admin confirm payment - FIRST confirmation (step 1)
        if call.data.startswith("confirm_payment_"):
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Chỉ admin mới có quyền!", show_alert=True)
                return
            
            ordernumber = int(call.data.replace("confirm_payment_", ""))
            bot.answer_callback_query(call.id, "⚠️ Vui lòng xác nhận lại!")
            
            confirm_msg = f"⚠️ *XÁC NHẬN GIAO HÀNG*\n\n"
            confirm_msg += f"━━━━━━━━━━━━━━\n"
            confirm_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
            confirm_msg += f"━━━━━━━━━━━━━━\n\n"
            confirm_msg += f"Bạn có chắc đã nhận được tiền và muốn giao hàng cho đơn này không?"
            
            confirm_kb = types.InlineKeyboardMarkup()
            confirm_kb.add(types.InlineKeyboardButton(text="✅ Chắc chắn - Giao hàng", callback_data=f"confirm_payment_final_{ordernumber}"))
            confirm_kb.add(types.InlineKeyboardButton(text="❌ Hủy", callback_data=f"cancel_confirm_{ordernumber}"))
            
            bot.edit_message_text(confirm_msg, call.message.chat.id, call.message.message_id, reply_markup=confirm_kb, parse_mode="Markdown")
            return
        
        # Handle cancel confirmation
        if call.data.startswith("cancel_confirm_"):
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Chỉ admin mới có quyền!", show_alert=True)
                return
            
            ordernumber = int(call.data.replace("cancel_confirm_", ""))
            bot.answer_callback_query(call.id, "Đã hủy xác nhận")
            
            # Get order info to restore original message
            if ordernumber in pending_orders_info:
                order_info = pending_orders_info[ordernumber]
                username = order_info["username"]
                buyer_id = order_info["user_id"]
                product_name = order_info["product_name"]
                price = order_info["price"]
                warranty_type = order_info.get("warranty_type", "kbh")
                
                # Restore original admin message
                admin_msg = f"🛒 *Đơn hàng mới đang chờ thanh toán*\n"
                admin_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
                admin_msg += f"👤 Khách: @{username} (ID: `{buyer_id}`)\n"
                admin_msg += f"📦 Sản phẩm: {product_name}\n"
                admin_msg += f"🛡 Loại: {'BH 3 tháng' if warranty_type == 'bh3' else 'Không bảo hành'}\n"
                admin_msg += f"💰 Số tiền: {price:,} VND\n"
                admin_msg += f"⏳ Trạng thái: _Chờ chuyển khoản_"
                
                admin_inline_kb = types.InlineKeyboardMarkup()
                admin_inline_kb.add(types.InlineKeyboardButton(
                    text="✅ Đã nhận tiền - Giao hàng",
                    callback_data=f"confirm_payment_{ordernumber}"
                ))
                
                bot.edit_message_text(admin_msg, call.message.chat.id, call.message.message_id, reply_markup=admin_inline_kb, parse_mode="Markdown")
            else:
                bot.edit_message_text("❌ Không tìm thấy thông tin đơn hàng", call.message.chat.id, call.message.message_id)
            
            return
        
        if call.data.startswith("otp_"):
            # Handle inline OTP button with specific email
            email = call.data.replace("otp_", "")
            bot.answer_callback_query(call.id, f"Đang lấy mã cho {email}...")
            get_otp_for_email(user_id, email, lang)
            return
        elif call.data == "get_otp_inline":
            # Handle inline OTP button - redirect to OTP handler
            bot.answer_callback_query(call.id, "Đang lấy mã xác thực...")
            # Get user's Canva accounts - returns (email, order_number, created_at)
            accounts = CanvaAccountDB.get_buyer_accounts(user_id)
            if accounts:
                if len(accounts) == 1:
                    # Only one account, get OTP directly
                    email = accounts[0][0]  # index 0 is email
                    get_otp_for_email(user_id, email, lang)
                else:
                    # Multiple accounts, show selection
                    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
                    for acc in accounts:
                        keyboard.row(types.KeyboardButton(text=f"📧 {acc[0]}"))  # index 0 is email
                    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
                    bot.send_message(user_id, "Chọn email để lấy mã xác thực:", reply_markup=keyboard)
            else:
                bot.send_message(user_id, "❌ *Không tìm thấy tài khoản*\n_Bạn chưa mua tài khoản Canva nào_", reply_markup=create_main_keyboard(lang, user_id), parse_mode='Markdown')
            return
        elif call.data == "product_canva":
            # Handle Canva Edu Admin product selection - edit message to show warranty options
            if (not sales_enabled or not canva_product_enabled) and not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Sản phẩm này tạm thời không khả dụng!", show_alert=True)
                return
            bot.answer_callback_query(call.id, "Đang xử lý...")
            show_canva_product_details(user_id, lang, call.message.chat.id, call.message.message_id)
            return
        elif call.data == "product_upgrade":
            # Handle Up lại Canva Edu product selection - check if enabled
            if not sales_enabled and not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Hiện đang tạm ngưng bán!", show_alert=True)
                return
            if not upgrade_product_enabled:
                bot.answer_callback_query(call.id, "❌ Sản phẩm này tạm thời không khả dụng!", show_alert=True)
                return
            bot.answer_callback_query(call.id, "Đang xử lý...")
            show_upgrade_product_details(user_id, lang, call.message.chat.id, call.message.message_id)
            return
        elif call.data == "product_slot":
            # Handle Slot Canva Edu product selection - ask email directly
            if (not sales_enabled or not slot_product_enabled) and not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Sản phẩm này tạm thời không khả dụng!", show_alert=True)
                return
            bot.answer_callback_query(call.id, "Vui lòng nhập email Canva...")
            # Set username in state before calling show_slot_product_details
            pending_slot_email_state[user_id] = {
                "quantity": 1,
                "username": call.from_user.username or "user"
            }
            show_slot_product_details(user_id, lang, call.message.chat.id, call.message.message_id)
            return
        elif call.data == "product_new":
            # Handle new product selection
            if (not sales_enabled or not new_product_enabled) and not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Sản phẩm này tạm thời không khả dụng!", show_alert=True)
                return
            bot.answer_callback_query(call.id, "Đang xử lý...")
            show_new_product_details(user_id, lang, call.message.chat.id, call.message.message_id)
            return
        elif call.data == "cancel_slot_email":
            # Cancel slot email input
            if user_id in pending_slot_email_state:
                del pending_slot_email_state[user_id]
            bot.answer_callback_query(call.id, "Đã hủy!")
            # Go back to products menu
            inline_kb = types.InlineKeyboardMarkup(row_width=1)
            inline_kb.row(types.InlineKeyboardButton(text="🛍 Canva Edu Admin", callback_data="product_canva"))
            inline_kb.row(types.InlineKeyboardButton(text="🎫 Slot Canva Edu", callback_data="product_slot"))
            inline_kb.row(types.InlineKeyboardButton(text=f"🆕 {get_new_product_name()}", callback_data="product_new"))
            if upgrade_product_enabled:
                inline_kb.row(types.InlineKeyboardButton(text="♻️ Up lại Canva Edu", callback_data="product_upgrade"))
            try:
                bot.edit_message_text("👇 Chọn sản phẩm:", call.message.chat.id, call.message.message_id, reply_markup=inline_kb)
            except:
                bot.send_message(user_id, "👇 Chọn sản phẩm:", reply_markup=inline_kb)
            
            # Update reply keyboard
            nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            nav_keyboard.row(
                types.KeyboardButton(text="🛍 Canva Edu Admin"),
                types.KeyboardButton(text="🎫 Slot Canva Edu")
            )
            nav_keyboard.row(types.KeyboardButton(text=f"🆕 {get_new_product_name()}"))
            if upgrade_product_enabled:
                nav_keyboard.row(types.KeyboardButton(text="♻️ Up lại Canva Edu"))
            nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
            update_reply_keyboard(user_id, nav_keyboard)
            return
        elif call.data.startswith("slot_done_"):
            # Admin marks slot order as done
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Chỉ admin mới có quyền!", show_alert=True)
                return
            
            # Parse: slot_done_{ordernumber}_{buyer_user_id}
            parts = call.data.replace("slot_done_", "").split("_")
            if len(parts) >= 2:
                ordernumber = parts[0]
                buyer_user_id = int(parts[1])
                
                bot.answer_callback_query(call.id, "✅ Đã đánh dấu hoàn thành!")
                
                # Get email from saved dict
                canva_email = slot_order_emails.get(int(ordernumber), "") or slot_order_emails.get(ordernumber, "")
                
                # Cleanup email from dict
                if int(ordernumber) in slot_order_emails:
                    del slot_order_emails[int(ordernumber)]
                if ordernumber in slot_order_emails:
                    del slot_order_emails[ordernumber]
                
                # Edit admin message
                try:
                    new_msg = call.message.text.replace("⏳ Chờ xử lý thêm slot cho khách", "✅ ĐÃ XỬ LÝ XONG")
                    bot.edit_message_text(new_msg, call.message.chat.id, call.message.message_id)
                except:
                    pass
                
                # Notify buyer with email
                buyer_msg = f"🎉 *THÔNG BÁO TỪ ADMIN*\n"
                buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                buyer_msg += f"✅ Đơn hàng `{ordernumber}` đã được xử lý xong!\n\n"
                buyer_msg += f"🎫 Slot email: `{canva_email}` đã được gửi lời mời vào đội.\n"
                buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                buyer_msg += f"Cảm ơn bạn đã sử dụng dịch vụ! 💚"
                
                try:
                    bot.send_message(buyer_user_id, buyer_msg, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Error notifying buyer about slot done: {e}")
            return
        elif call.data.startswith("canva_done_"):
            # Admin starts Canva Edu Admin delivery flow
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Chỉ admin mới có quyền!", show_alert=True)
                return
            
            # Parse: canva_done_{ordernumber}_{buyer_user_id}_{warranty_type}
            parts = call.data.replace("canva_done_", "").split("_")
            if len(parts) >= 2:
                ordernumber = parts[0]
                buyer_user_id = int(parts[1])
                warranty_type = parts[2] if len(parts) > 2 else "kbh"
                
                bot.answer_callback_query(call.id, "Nhập thông tin tài khoản để giao cho khách...")
                
                # Save state - waiting for admin to input account details
                pending_canva_delivery[user_id] = {
                    "ordernumber": ordernumber,
                    "buyer_user_id": buyer_user_id,
                    "admin_msg_chat_id": call.message.chat.id,
                    "admin_msg_id": call.message.message_id,
                    "step": "account",
                    "account_details": "",
                    "warranty_type": warranty_type
                }
                
                # Prompt admin to input account details
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
                keyboard.row(types.KeyboardButton(text="❌ Hủy giao hàng"))
                
                prompt_msg = f"📝 *GIAO TÀI KHOẢN CHO KHÁCH*\n"
                prompt_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                prompt_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
                prompt_msg += f"👤 Khách: ID `{buyer_user_id}`\n"
                prompt_msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
                prompt_msg += f"📧 Nhập thông tin tài khoản gửi cho khách:\n"
                prompt_msg += f"_(email, mật khẩu, hoặc bất kỳ thông tin nào)_\n\n"
                prompt_msg += f"💡 Ví dụ:\n"
                prompt_msg += f"`email@edu.com\n"
                prompt_msg += f"Pass: 123456`\n\n"
                prompt_msg += f"Hoặc bấm ❌ Hủy giao hàng để quay lại."
                
                bot.send_message(user_id, prompt_msg, reply_markup=keyboard, parse_mode="Markdown")
            return
        elif call.data.startswith("newprod_done_"):
            # Admin confirms new product (YouTube Premium) delivery - auto send to buyer
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Chỉ admin mới có quyền!", show_alert=True)
                return
            
            # Parse: newprod_done_{ordernumber}_{buyer_user_id}
            parts = call.data.replace("newprod_done_", "").split("_")
            if len(parts) >= 2:
                ordernumber = parts[0]
                buyer_user_id = int(parts[1])
                
                bot.answer_callback_query(call.id, "Đang gửi thông báo cho khách...")
                
                # Get stored order info
                order_data = pending_newprod_orders.get(ordernumber, {})
                google_email = order_data.get("google_email", "")
                package_label = order_data.get("package_label", "")
                product_name = get_new_product_name()
                
                # Build buyer notification
                buyer_msg = f"🎉 *THÔNG BÁO TỪ ADMIN*\n"
                buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                buyer_msg += f"✅ Đơn hàng `{ordernumber}` đã được xử lý xong!\n\n"
                buyer_msg += f"📺 *{product_name.upper()}*"
                if package_label:
                    buyer_msg += f" - *{package_label}*"
                buyer_msg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                if google_email:
                    buyer_msg += f"📧 Email: `{google_email}`\n\n"
                buyer_msg += f"✉️ Vui lòng check email và bấm *chấp nhận* để tham gia Family.\n\n"
                buyer_msg += f"📌 *Hướng dẫn:*\n"
                buyer_msg += f"1️⃣ Mở Gmail → Tìm thư mời từ YouTube/Google\n"
                buyer_msg += f"2️⃣ Bấm *Chấp nhận lời mời*\n"
                buyer_msg += f"3️⃣ Mở YouTube → Kiểm tra Premium đã kích hoạt\n"
                buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                buyer_msg += f"Cảm ơn bạn đã sử dụng dịch vụ! 💚"
                
                delivery_success = False
                try:
                    bot.send_message(buyer_user_id, buyer_msg, parse_mode="Markdown")
                    
                    # Send reply keyboard
                    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
                    kb.row(types.KeyboardButton(text="🛍 Đơn hàng"), types.KeyboardButton(text="📞 Hỗ trợ"))
                    kb.row(types.KeyboardButton(text="🏠 Trang chủ"))
                    bot.send_message(buyer_user_id, "👆 Thông tin đơn hàng của bạn ở trên.", reply_markup=kb)
                    delivery_success = True
                except Exception as e:
                    logger.error(f"Error sending newprod delivery to buyer {buyer_user_id}: {e}")
                    bot.send_message(user_id, f"⚠️ Không thể gửi tin nhắn cho khách (ID: {buyer_user_id}). Khách có thể đã block bot.")
                
                # Edit admin message to mark as done
                try:
                    done_msg = f"✅ *ĐÃ GIAO HÀNG XONG*\n━━━━━━━━━━━━━━\n🆔 Mã đơn: `{ordernumber}`\n👤 Khách: ID `{buyer_user_id}`"
                    if google_email:
                        done_msg += f"\n📧 Email: `{google_email}`"
                    if package_label:
                        done_msg += f"\n📋 Gói: {package_label}"
                    bot.edit_message_text(done_msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
                except:
                    pass
                
                # Confirm to admin
                if delivery_success:
                    confirm = f"✅ Đã gửi thông báo giao hàng cho khách (Đơn `{ordernumber}`)!"
                    if google_email:
                        confirm += f"\n📧 Email: `{google_email}`"
                    bot.send_message(user_id, confirm, parse_mode="Markdown")
                else:
                    bot.send_message(user_id, f"⚠️ Đơn `{ordernumber}` - Không gửi được cho khách. Hãy liên hệ trực tiếp.", parse_mode="Markdown")
                
                # Cleanup
                if ordernumber in pending_newprod_orders:
                    del pending_newprod_orders[ordernumber]
            return
        elif call.data.startswith("buy_qty_"):
            # Handle inline buy quantity button (with warranty type)
            if not sales_enabled and not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Hiện đang tạm ngưng bán!", show_alert=True)
                return
            parts = call.data.replace('buy_qty_', '').split('_')
            quantity = int(parts[0])
            warranty_type = parts[1] if len(parts) > 1 else "kbh"
            bot.answer_callback_query(call.id, f"Đang xử lý mua {quantity} tài khoản...")
            # Simulate clicking the buy button
            fake_message = type('obj', (object,), {
                'from_user': call.from_user,
                'chat': call.message.chat,
                'text': f"🛒 Mua ({quantity})"
            })()
            handle_buy_with_quantity(fake_message, warranty_type)
            return
        elif call.data.startswith("warranty_"):
            # Handle warranty type selection - edit message
            if not sales_enabled and not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Hiện đang tạm ngưng bán!", show_alert=True)
                return
            warranty_type = call.data.replace('warranty_', '')
            bot.answer_callback_query(call.id, f"Đã chọn {'BH 3 tháng' if warranty_type == 'bh3' else 'Không bảo hành'}")
            # Show quantity selection for this warranty type - edit current message
            show_quantity_selection(user_id, warranty_type, lang, call.message.chat.id, call.message.message_id)
            return
        elif call.data == "upgrade_canva":
            # Handle "Up lại Canva Edu" selection
            if not sales_enabled and not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Hiện đang tạm ngưng bán!", show_alert=True)
                return
            bot.answer_callback_query(call.id, "Đang xử lý...")
            show_upgrade_canva_options(user_id, lang)
            return
        elif call.data.startswith("upgrade_"):
            # Handle upgrade warranty type selection
            if not sales_enabled and not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Hiện đang tạm ngưng bán!", show_alert=True)
                return
            warranty_type = call.data.replace('upgrade_', '')
            bot.answer_callback_query(call.id, f"Đang xử lý Up lại Canva Edu...")
            process_upgrade_canva_order(user_id, call.from_user.username or "user", warranty_type, lang)
            return
        elif call.data.startswith("new_product_pkg_"):
            # Handle YouTube Premium package selection -> ask for Google email
            if not sales_enabled and not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Hiện đang tạm ngưng bán!", show_alert=True)
                return
            package_type = call.data.replace("new_product_pkg_", "")  # 1m, 3m, 6m, 1y
            packages = get_new_product_packages()
            if package_type not in packages:
                bot.answer_callback_query(call.id, "❌ Gói không hợp lệ!", show_alert=True)
                return
            pkg = packages[package_type]
            bot.answer_callback_query(call.id, f"Đã chọn gói {pkg['name']}...")

            # Save state - waiting for email input
            pending_new_product_email[user_id] = {
                "package_type": package_type,
                "username": call.from_user.username or "user"
            }

            # Ask for Google email
            product_name = get_new_product_name()
            prompt_msg = f"📧 <b>NHẬP EMAIL GOOGLE</b>\n"
            prompt_msg += "━━━━━━━━━━━━━━━━━━━━\n"
            prompt_msg += f"📦 Sản phẩm: <b>{product_name}</b>\n"
            prompt_msg += f"📋 Gói: <b>{pkg['name']}</b>\n"
            prompt_msg += f"💰 Giá: <b>{format_price_vnd(pkg['price'])}</b>\n"
            prompt_msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
            prompt_msg += "📩 Vui lòng nhập email Google (Gmail) của bạn:\n\n"
            prompt_msg += "<i>💡 Ví dụ: example@gmail.com</i>\n\n"
            prompt_msg += "⚠️ Email này sẽ được dùng để thêm vào nhóm gia đình YouTube Premium."

            # Update reply keyboard
            nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            nav_keyboard.row(types.KeyboardButton(text=f"❌ Hủy mua {get_new_product_name()}"))
            nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
            update_reply_keyboard(user_id, nav_keyboard)

            try:
                bot.edit_message_text(prompt_msg, call.message.chat.id, call.message.message_id, parse_mode='HTML')
            except:
                bot.send_message(user_id, prompt_msg, parse_mode='HTML')
            return
        elif call.data.startswith("cancel_order_"):
            # User cancels their pending order (not yet in database)
            ordernumber = int(call.data.replace('cancel_order_', ''))
            try:
                # Get order info before deleting
                cancelled_order = pending_orders_info.get(ordernumber, {})
                cancelled_username = cancelled_order.get("username", call.from_user.username or "user")
                cancelled_product = cancelled_order.get("product_name", "N/A")
                cancelled_amount = cancelled_order.get("price", 0)
                
                # Cancel PayOS payment link
                cancel_payos_payment(ordernumber, "Khách hủy đơn")
                
                # Remove from pending orders (memory only, not in DB)
                if ordernumber in pending_orders_info:
                    del pending_orders_info[ordernumber]
                if ordernumber in pending_order_quantities:
                    del pending_order_quantities[ordernumber]
                if ordernumber in pending_qr_messages:
                    del pending_qr_messages[ordernumber]
                
                # Edit admin notification message (instead of sending new)
                admin_msg = f"❌ *Đơn hàng đã bị hủy*\n"
                admin_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
                admin_msg += f"👤 Khách: @{cancelled_username}\n"
                admin_msg += f"📦 Sản phẩm: {cancelled_product}\n"
                admin_msg += f"💰 Số tiền: {cancelled_amount:,} VND"
                
                # Try to edit existing admin messages
                if ordernumber in pending_admin_messages:
                    for msg_info in pending_admin_messages[ordernumber]:
                        try:
                            bot.edit_message_text(admin_msg, msg_info["chat_id"], msg_info["message_id"], parse_mode="Markdown")
                        except:
                            pass
                    del pending_admin_messages[ordernumber]
                else:
                    # Fallback: send new message if no saved message
                    admins = GetDataFromDB.GetAdminIDsInDB() or []
                    for admin in admins:
                        try:
                            bot.send_message(admin[0], admin_msg, parse_mode="Markdown")
                        except:
                            pass
                
                bot.answer_callback_query(call.id, get_text("order_cancelled", lang, ordernumber))
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(call.message.chat.id, get_text("order_cancelled", lang, ordernumber), reply_markup=create_main_keyboard(lang, user_id), parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Cancel order error: {e}")
                bot.answer_callback_query(call.id, f"Error: {e}")
            return
        elif call.data == "back_to_warranty" or call.data == "back_to_products":
            # Go back to product selection menu - edit inline + update reply keyboard
            bot.answer_callback_query(call.id, "Quay lại...")
            # Edit inline message
            inline_kb = types.InlineKeyboardMarkup(row_width=1)
            inline_kb.row(
                types.InlineKeyboardButton(text="🛍 Canva Edu Admin", callback_data="product_canva")
            )
            inline_kb.row(
                types.InlineKeyboardButton(text="🎫 Slot Canva Edu", callback_data="product_slot")
            )
            inline_kb.row(
                types.InlineKeyboardButton(text=f"🆕 {get_new_product_name()}", callback_data="product_new")
            )
            # Only show upgrade product if enabled
            if upgrade_product_enabled:
                inline_kb.row(
                    types.InlineKeyboardButton(text="♻️ Up lại Canva Edu", callback_data="product_upgrade")
                )
            try:
                bot.edit_message_text("👇 Chọn sản phẩm:", call.message.chat.id, call.message.message_id, reply_markup=inline_kb)
            except:
                bot.send_message(user_id, "👇 Chọn sản phẩm:", reply_markup=inline_kb)
            # Update reply keyboard
            nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            nav_keyboard.row(
                types.KeyboardButton(text="🛍 Canva Edu Admin"),
                types.KeyboardButton(text="🎫 Slot Canva Edu")
            )
            nav_keyboard.row(types.KeyboardButton(text=f"🆕 {get_new_product_name()}"))
            if upgrade_product_enabled:
                nav_keyboard.row(types.KeyboardButton(text="♻️ Up lại Canva Edu"))
            nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
            update_reply_keyboard(user_id, nav_keyboard)
            return
        elif call.data == "back_to_canva":
            # Go back to Canva Edu Admin warranty selection - edit inline message
            bot.answer_callback_query(call.id, "Quay lại...")
            show_canva_product_details(user_id, lang, call.message.chat.id, call.message.message_id)
            return
        elif call.data.startswith("assign_"):
            # Handle assign account callbacks (Admin only)
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Chỉ admin mới có quyền!", show_alert=True)
                return
            
            if call.data == "assign_cancel":
                bot.answer_callback_query(call.id, "Đã hủy")
                bot.edit_message_text("❌ Đã hủy gán tài khoản", call.message.chat.id, call.message.message_id)
                if user_id in assign_account_state:
                    del assign_account_state[user_id]
                return
            
            if call.data == "assign_more":
                # Restart assign flow
                bot.answer_callback_query(call.id, "Đang tải...")
                admin_assign_account_start_inline(user_id, call.message.chat.id)
                return
            
            if call.data == "assign_skip_pw":
                # Handle skip password - assign without password, get data from state
                if user_id not in assign_account_state:
                    bot.answer_callback_query(call.id, "❌ Phiên đã hết hạn, vui lòng thử lại!", show_alert=True)
                    return
                
                target_user_id = assign_account_state[user_id].get('target_user_id')
                canva_email = assign_account_state[user_id].get('canva_email')
                
                if not target_user_id or not canva_email:
                    bot.answer_callback_query(call.id, "❌ Thiếu thông tin!", show_alert=True)
                    return
                
                bot.answer_callback_query(call.id, "Đang gán tài khoản...")
                
                order_num = f"ADMIN_{int(time.time())}"
                
                # Check if account exists
                existing = CanvaAccountDB.get_account_by_email(canva_email)
                if existing:
                    # Account exists - just assign
                    result = CanvaAccountDB.assign_account_to_buyer(existing['id'], target_user_id, order_num)
                else:
                    # Account doesn't exist - add and assign in one step (status = sold)
                    result = CanvaAccountDB.add_and_assign_account(canva_email, target_user_id, order_num)
                
                if result:
                    # Success - create inline buttons
                    inline_kb = types.InlineKeyboardMarkup(row_width=1)
                    inline_kb.add(types.InlineKeyboardButton(text=f"🔑 Lấy OTP: {canva_email}", callback_data=f"otp_{canva_email}"))
                    inline_kb.add(types.InlineKeyboardButton(text="📋 Gán thêm tài khoản", callback_data="assign_more"))
                    
                    success_msg = f"✅ *GÁN TÀI KHOẢN THÀNH CÔNG!*\n"
                    success_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                    success_msg += f"👤 User ID: `{target_user_id}`\n"
                    success_msg += f"📧 Email: `{canva_email}`\n"
                    success_msg += f"🆔 Mã đơn: `{order_num}`\n"
                    success_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                    success_msg += f"_Nhấn nút bên dưới để lấy OTP hoặc gán thêm_"
                    
                    bot.edit_message_text(success_msg, call.message.chat.id, call.message.message_id, reply_markup=inline_kb, parse_mode="Markdown")
                    
                    # Notify the target user (no password)
                    try:
                        user_msg = f"✅ *ADMIN ĐÃ GÁN TÀI KHOẢN CHO BẠN!*\n"
                        user_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                        user_msg += f"📧 Email: `{canva_email}`\n"
                        user_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                        user_msg += f"_Nhấn nút bên dưới để lấy mã xác thực_"
                        
                        user_inline_kb = types.InlineKeyboardMarkup()
                        user_inline_kb.add(types.InlineKeyboardButton(text=f"🔑 Lấy OTP", callback_data=f"otp_{canva_email}"))
                        
                        bot.send_message(target_user_id, user_msg, reply_markup=user_inline_kb, parse_mode="Markdown")
                    except Exception as e:
                        logger.warning(f"Could not notify user {target_user_id}: {e}")
                else:
                    bot.edit_message_text(f"❌ Lỗi khi gán tài khoản!", call.message.chat.id, call.message.message_id)
                
                # Cleanup state
                if user_id in assign_account_state:
                    del assign_account_state[user_id]
                return
            
            # Parse callback data: assign_{account_id}_{target_user_id}
            parts = call.data.split("_")
            if len(parts) < 3:
                bot.answer_callback_query(call.id, "❌ Lỗi dữ liệu!", show_alert=True)
                return
            
            try:
                account_id = int(parts[1])
                target_user_id = int(parts[2])
            except ValueError:
                bot.answer_callback_query(call.id, "❌ Lỗi dữ liệu!", show_alert=True)
                return
            
            bot.answer_callback_query(call.id, "Đang gán tài khoản...")
            
            # Get account info before assigning
            all_accounts = CanvaAccountDB.get_all_accounts()
            account_info = None
            for acc in all_accounts:
                if acc[0] == account_id:
                    account_info = acc
                    break
            
            if not account_info:
                bot.edit_message_text("❌ Tài khoản không tồn tại!", call.message.chat.id, call.message.message_id)
                return
            
            acc_id, email, authkey, buyer_id, order_number, status = account_info
            
            if status == 'sold':
                bot.edit_message_text(f"❌ Tài khoản `{email}` đã được gán cho user khác!", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
                return
            
            # Assign account
            order_num = f"ADMIN_{int(time.time())}"
            result = CanvaAccountDB.assign_account_to_buyer(account_id, target_user_id, order_num)
            
            if result:
                # Success - create inline buttons for the assigned account
                inline_kb = types.InlineKeyboardMarkup(row_width=1)
                inline_kb.add(types.InlineKeyboardButton(text=f"🔑 Lấy OTP: {email}", callback_data=f"otp_{email}"))
                inline_kb.add(types.InlineKeyboardButton(text="📋 Gán thêm tài khoản", callback_data="assign_more"))
                
                success_msg = f"✅ *GÁN TÀI KHOẢN THÀNH CÔNG!*\n"
                success_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                success_msg += f"👤 User ID: `{target_user_id}`\n"
                success_msg += f"📧 Email: `{email}`\n"
                success_msg += f"🆔 Mã đơn: `{order_num}`\n"
                success_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                success_msg += f"_Nhấn nút bên dưới để lấy OTP hoặc gán thêm_"
                
                bot.edit_message_text(success_msg, call.message.chat.id, call.message.message_id, reply_markup=inline_kb, parse_mode="Markdown")
                
                # Notify the target user
                try:
                    user_msg = f"✅ *ADMIN ĐÃ GÁN TÀI KHOẢN CHO BẠN!*\n"
                    user_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                    user_msg += f"📧 Email: `{email}`\n"
                    user_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                    user_msg += f"_Nhấn nút bên dưới để lấy mã xác thực_"
                    
                    user_inline_kb = types.InlineKeyboardMarkup()
                    user_inline_kb.add(types.InlineKeyboardButton(text=f"🔑 Lấy OTP", callback_data=f"otp_{email}"))
                    
                    bot.send_message(target_user_id, user_msg, reply_markup=user_inline_kb, parse_mode="Markdown")
                except Exception as e:
                    logger.warning(f"Could not notify user {target_user_id}: {e}")
            else:
                bot.edit_message_text(f"❌ Lỗi khi gán tài khoản!", call.message.chat.id, call.message.message_id)
            return
        elif call.data.startswith("reassign_"):
            # Handle reassign account callbacks (Admin only)
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Chỉ admin mới có quyền!", show_alert=True)
                return
            
            # Parse callback data: reassign_{email}_{target_user_id}
            parts = call.data.split("_", 2)  # Split max 2 times to preserve email with underscores
            if len(parts) < 3:
                bot.answer_callback_query(call.id, "❌ Lỗi dữ liệu!", show_alert=True)
                return
            
            # parts[1] contains email_targetuserid, need to split by last _
            remaining = parts[1] + "_" + parts[2]
            last_underscore = remaining.rfind("_")
            if last_underscore == -1:
                bot.answer_callback_query(call.id, "❌ Lỗi dữ liệu!", show_alert=True)
                return
            
            canva_email = remaining[:last_underscore]
            try:
                target_user_id = int(remaining[last_underscore + 1:])
            except ValueError:
                bot.answer_callback_query(call.id, "❌ Lỗi dữ liệu!", show_alert=True)
                return
            
            bot.answer_callback_query(call.id, "Đang gán đè tài khoản...")
            
            # Get account info
            acc_info = CanvaAccountDB.get_account_by_email(canva_email)
            if not acc_info:
                bot.edit_message_text("❌ Tài khoản không tồn tại!", call.message.chat.id, call.message.message_id)
                return
            
            # Reassign account
            order_num = f"ADMIN_{int(time.time())}"
            result = CanvaAccountDB.assign_account_to_buyer(acc_info['id'], target_user_id, order_num)
            
            if result:
                # Success - create inline buttons
                inline_kb = types.InlineKeyboardMarkup(row_width=1)
                inline_kb.add(types.InlineKeyboardButton(text=f"🔑 Lấy OTP: {canva_email}", callback_data=f"otp_{canva_email}"))
                inline_kb.add(types.InlineKeyboardButton(text="📋 Gán thêm tài khoản", callback_data="assign_more"))
                
                success_msg = f"✅ *GÁN ĐÈ TÀI KHOẢN THÀNH CÔNG!*\n"
                success_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                success_msg += f"👤 User ID: `{target_user_id}`\n"
                success_msg += f"📧 Email: `{canva_email}`\n"
                success_msg += f"🆔 Mã đơn: `{order_num}`\n"
                success_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                success_msg += f"_Nhấn nút bên dưới để lấy OTP hoặc gán thêm_"
                
                bot.edit_message_text(success_msg, call.message.chat.id, call.message.message_id, reply_markup=inline_kb, parse_mode="Markdown")
                
                # Notify the target user
                try:
                    user_msg = f"✅ *ADMIN ĐÃ GÁN TÀI KHOẢN CHO BẠN!*\n"
                    user_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                    user_msg += f"📧 Email: `{canva_email}`\n"
                    user_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                    user_msg += f"_Nhấn nút bên dưới để lấy mã xác thực_"
                    
                    user_inline_kb = types.InlineKeyboardMarkup()
                    user_inline_kb.add(types.InlineKeyboardButton(text=f"🔑 Lấy OTP", callback_data=f"otp_{canva_email}"))
                    
                    bot.send_message(target_user_id, user_msg, reply_markup=user_inline_kb, parse_mode="Markdown")
                except Exception as e:
                    logger.warning(f"Could not notify user {target_user_id}: {e}")
            else:
                bot.edit_message_text(f"❌ Lỗi khi gán đè tài khoản!", call.message.chat.id, call.message.message_id)
            return
        elif call.data.startswith("quick_assign_"):
            # Handle quick assign from /myid command
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Chỉ admin mới có quyền!", show_alert=True)
                return
            
            # Parse: quick_assign_{target_user_id}
            try:
                target_user_id = int(call.data.replace("quick_assign_", ""))
            except ValueError:
                bot.answer_callback_query(call.id, "❌ Lỗi dữ liệu!", show_alert=True)
                return
            
            bot.answer_callback_query(call.id, "Đang mở form gán tài khoản...")
            
            # Store target user ID and start email input
            assign_account_state[user_id] = {'target_user_id': target_user_id}
            
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.row(types.KeyboardButton(text="❌ Hủy"))
            
            msg = f"🎁 *GÁN TÀI KHOẢN CHO USER*\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"👤 User ID: `{target_user_id}`\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            msg += f"📝 Nhập email Canva cần gán:\n"
            msg += f"_(Ví dụ: example@domain.com)_"
            
            sent_msg = bot.send_message(call.message.chat.id, msg, reply_markup=keyboard, parse_mode="Markdown")
            bot.register_next_step_handler(sent_msg, admin_assign_account_get_email)
            return
        else:
            logger.warning(f"Unknown callback data: {call.data}")
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        bot.send_message(call.message.chat.id, get_text("error_404", get_user_lang(call.from_user.id)), parse_mode='Markdown')


#Function to list Products
def is_product_command(message):
    """Check if message is a product command"""
    try:
        pattern = r'/\d{8}$'
        return bool(re.match(pattern, message))
    except Exception as e:
        logger.error(f"Error checking product command: {e}")
        return False
@bot.message_handler(content_types=["text"], func=lambda message: is_product_command(message.text))
def products_get(message):
    """Handle product selection"""
    try:
        UserOperations.purchase_a_products(message)
    except Exception as e:
        logger.error(f"Error processing product selection: {e}")
        bot.send_message(message.chat.id, "Error processing your request. Please try again.")
# Check if message matches any button text in any language
def is_home_button(text):
    return text in [get_text("home", "en"), get_text("home", "vi"), "Home 🏘", "Trang chủ 🏘", "🏠 Trang chủ"]

# Handler to get file_id when admin sends photo
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if is_admin(message.from_user.id):
        file_id = message.photo[-1].file_id  # Largest size
        logger.info(f"PHOTO FILE_ID: {file_id}")
        bot.reply_to(message, f"File ID:\n`{file_id}`", parse_mode="Markdown")

#Start command handler and function
@bot.message_handler(content_types=["text"], func=lambda message: is_home_button(message.text))
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        # Lấy username hoặc first_name - user_id
        if message.from_user.username:
            usname = message.from_user.username
            display_name = f"@{usname}"
        else:
            first_name = message.from_user.first_name or "User"
            usname = f"{first_name}_{id}"  # Lưu vào DB
            display_name = f"{first_name} - {id}"
        
        # Check admin first (fast - uses cached env var)
        user_is_admin = is_admin(id)
        
        if user_is_admin:
            # Admin panel - load stats only for admin
            try:
                user_s = GetDataFromDB.AllUsers() or []
                all_user_s = user_s[0][0] if user_s and user_s[0] else 0
                admin_s = GetDataFromDB.AllAdmins() or []
                all_admin_s = admin_s[0][0] if admin_s and admin_s[0] else 0
                product_s = GetDataFromDB.AllProducts() or []
                all_product_s = product_s[0][0] if product_s and product_s[0] else 0
                orders_s = GetDataFromDB.AllOrders() or []
                all_orders_s = orders_s[0][0] if orders_s and orders_s[0] else 0
            except:
                all_user_s = all_admin_s = all_product_s = all_orders_s = 0
            
            # Ensure admin is in database
            CreateDatas.AddAuser(id, usname)
            CreateDatas.AddAdmin(id, usname)
            
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
            keyboardadmin.row_width = 2
            key0 = types.KeyboardButton(text="📧 Quản lý tài khoản Canva")
            key2 = types.KeyboardButton(text=get_text("manage_orders", lang))
            key4 = types.KeyboardButton(text=get_text("news_to_users", lang))
            key5 = types.KeyboardButton(text=get_text("switch_to_user", lang))
            key6 = types.KeyboardButton(text="🎁 Quản lý khuyến mãi")
            # Maintenance mode button
            if maintenance_mode:
                key7 = types.KeyboardButton(text="🟢 BẬT Bot (đang tắt)")
            else:
                key7 = types.KeyboardButton(text="🔴 TẮT Bot (bảo trì)")
            # Sales toggle button
            if sales_enabled:
                key8 = types.KeyboardButton(text="🔴 TẮT bán tất cả (đang bật)")
            else:
                key8 = types.KeyboardButton(text="🟢 BẬT bán tất cả (đang tắt)")
            keyboardadmin.add(key0, key2)
            keyboardadmin.add(key4, key5)
            keyboardadmin.add(key6, key7)
            keyboardadmin.add(key8)

            # Get promotion status
            promo_info = PromotionDB.get_promotion_info()
            promo_status = ""
            if promo_info:
                if promo_info["is_active"]:
                    promo_status = f"\n\n🎁 *Khuyến mãi:* ĐÃ BẬT ({promo_info['sold_count']}/{promo_info['max_count']} slot)"
                else:
                    promo_status = f"\n\n🎁 *Khuyến mãi:* TẮT"

            store_statistics = f"{get_text('store_statistics', lang)}\n\n{get_text('total_users', lang)}: {all_user_s}\n{get_text('total_admins', lang)}: {all_admin_s}\n{get_text('total_products', lang)}: {all_product_s}\n{get_text('total_orders', lang)}: {all_orders_s}{promo_status}"
            bot.send_message(message.chat.id, f"{get_text('welcome_admin', lang)}\n\n{store_statistics}", reply_markup=keyboardadmin, parse_mode='Markdown')
        else:
            # Customer - check maintenance mode first
            if maintenance_mode:
                bot.send_message(id, "🔧 *BOT ĐANG BẢO TRÌ*\n\nVui lòng quay lại sau!\nXin lỗi vì sự bất tiện này.", parse_mode='Markdown')
                return
                
            # Customer - minimal DB calls
            # Check if new user
            existing_users = GetDataFromDB.GetUserIDsInDB() or []
            is_new_user = str(id) not in str(existing_users)
            
            CreateDatas.AddAuser(id, usname)
            
            # Notify admin if new user
            if is_new_user:
                notify_admin("🆕 User mới", display_name)
            
            # Check promotion and add banner if active
            promo_banner = ""
            promo_info = PromotionDB.get_promotion_info()
            if promo_info and promo_info["is_active"]:
                remaining = promo_info["max_count"] - promo_info["sold_count"]
                if remaining > 0:
                    promo_banner = f"🎉 *ĐANG CÓ KHUYẾN MÃI MUA 1 TẶNG 1!*\n🎁 Còn lại {remaining} slot\n━━━━━━━━━━━━━━\n\n"
            
            # Escape username để tránh lỗi Markdown
            safe_display = display_name.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
            welcome_msg = promo_banner + get_text("welcome_customer", lang).replace("{username}", safe_display)
            # Send welcome with photo (using Telegram file_id for speed)
            welcome_photo = "AgACAgUAAxkBAAI5FWmfIdRcVGHee4LazuOplHyEBFpEAAIVDWsb-0IAAVV3t9lc4ydhRAEAAwIAA3gAAzoE"
            try:
                bot.send_photo(message.chat.id, photo=welcome_photo, caption=welcome_msg, reply_markup=create_main_keyboard(lang, id), parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Failed to send welcome photo with Markdown: {e}")
                # Fallback: gửi không có Markdown
                try:
                    welcome_msg_plain = promo_banner.replace("*", "") + get_text("welcome_customer", lang).replace("{username}", display_name).replace("*", "")
                    bot.send_photo(message.chat.id, photo=welcome_photo, caption=welcome_msg_plain, reply_markup=create_main_keyboard(lang, id))
                except:
                    bot.send_message(message.chat.id, welcome_msg_plain, reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        logger.error(f"Error in send_welcome: {e}")
        
# Check if message matches switch to user button
def is_manage_users_button(text):
    keywords = ["Quản lý người dùng", "quản lý người dùng", "Manage Users"]
    return any(kw in text for kw in keywords)

# Handler for maintenance mode toggle
def is_maintenance_toggle_button(text):
    return "TẮT Bot (bảo trì)" in text or "BẬT Bot (đang tắt)" in text

@bot.message_handler(content_types=["text"], func=lambda message: is_maintenance_toggle_button(message.text))
def toggle_maintenance_mode(message):
    global maintenance_mode
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, "❌ Chỉ admin mới có quyền truy cập!", reply_markup=create_main_keyboard(lang, id))
        return
    
    if "TẮT Bot" in message.text:
        # Turn ON maintenance mode (bot is OFF for users)
        set_maintenance_mode(True)
        bot.send_message(id, "🔴 *ĐÃ TẮT BOT*\n\n⚠️ Bot đang ở chế độ bảo trì.\nChỉ admin mới có thể sử dụng.\n\nNhấn 🏠 để cập nhật menu.", parse_mode='Markdown')
    else:
        # Turn OFF maintenance mode (bot is ON for users)
        set_maintenance_mode(False)
        bot.send_message(id, "🟢 *ĐÃ BẬT BOT*\n\n✅ Bot hoạt động bình thường.\nMọi người đều có thể sử dụng.\n\nNhấn 🏠 để cập nhật menu.", parse_mode='Markdown')

# Handler for upgrade product toggle
def is_upgrade_toggle_button(text):
    return "TẮT bán Up lại" in text or "BẬT bán Up lại" in text

@bot.message_handler(content_types=["text"], func=lambda message: is_upgrade_toggle_button(message.text))
def toggle_upgrade_product(message):
    global upgrade_product_enabled
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, "❌ Chỉ admin mới có quyền truy cập!", reply_markup=create_main_keyboard(lang, id))
        return
    
    if "TẮT bán Up lại" in message.text:
        # Turn OFF upgrade product (hide from menu)
        set_upgrade_product_enabled(False)
        bot.send_message(id, "🔴 *ĐÃ TẮT BÁN SẢN PHẨM UP LẠI*\n\n⚠️ Sản phẩm 'Up lại Canva Edu' đã bị ẩn.\nKhách hàng sẽ không thấy sản phẩm này.", parse_mode='Markdown')
    else:
        # Turn ON upgrade product (show in menu)
        set_upgrade_product_enabled(True)
        bot.send_message(id, "🟢 *ĐÃ BẬT BÁN SẢN PHẨM UP LẠI*\n\n✅ Sản phẩm 'Up lại Canva Edu' đã hiển thị.\nKhách hàng có thể mua sản phẩm này.", parse_mode='Markdown')
    
    # Refresh Canva management menu
    manage_canva_accounts(message)

# Handler for canva product toggle
def is_canva_toggle_button(text):
    return "TẮT bán Canva" in text or "BẬT bán Canva" in text

@bot.message_handler(content_types=["text"], func=lambda message: is_canva_toggle_button(message.text))
def toggle_canva_product(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    if not is_admin(id):
        bot.send_message(id, "❌ Chỉ admin mới có quyền truy cập!", reply_markup=create_main_keyboard(lang, id))
        return
    if "TẮT bán Canva" in message.text:
        set_canva_product_enabled(False)
        bot.send_message(id, "🔴 *ĐÃ TẮT BÁN CANVA EDU ADMIN*\n\n⚠️ Khách hàng sẽ không thấy sản phẩm này.", parse_mode='Markdown')
    else:
        set_canva_product_enabled(True)
        bot.send_message(id, "🟢 *ĐÃ BẬT BÁN CANVA EDU ADMIN*\n\n✅ Khách hàng có thể mua sản phẩm này.", parse_mode='Markdown')
    manage_canva_accounts(message)

# Handler for slot product toggle
def is_slot_toggle_button(text):
    return "TẮT bán Slot" in text or "BẬT bán Slot" in text

@bot.message_handler(content_types=["text"], func=lambda message: is_slot_toggle_button(message.text))
def toggle_slot_product(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    if not is_admin(id):
        bot.send_message(id, "❌ Chỉ admin mới có quyền truy cập!", reply_markup=create_main_keyboard(lang, id))
        return
    if "TẮT bán Slot" in message.text:
        set_slot_product_enabled(False)
        bot.send_message(id, "🔴 *ĐÃ TẮT BÁN SLOT CANVA EDU*\n\n⚠️ Khách hàng sẽ không thấy sản phẩm này.", parse_mode='Markdown')
    else:
        set_slot_product_enabled(True)
        bot.send_message(id, "🟢 *ĐÃ BẬT BÁN SLOT CANVA EDU*\n\n✅ Khách hàng có thể mua sản phẩm này.", parse_mode='Markdown')
    manage_canva_accounts(message)

# Handler for new product toggle
def is_new_product_toggle_button(text):
    return ("TẮT bán" in text or "BẬT bán" in text) and get_new_product_name() in text

@bot.message_handler(content_types=["text"], func=lambda message: is_new_product_toggle_button(message.text))
def toggle_new_product(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    if not is_admin(id):
        bot.send_message(id, "❌ Chỉ admin mới có quyền truy cập!", reply_markup=create_main_keyboard(lang, id))
        return
    pname = get_new_product_name()
    if "TẮT bán" in message.text:
        set_new_product_enabled(False)
        bot.send_message(id, f"🔴 *ĐÃ TẮT BÁN {pname.upper()}*\n\n⚠️ Khách hàng sẽ không thấy sản phẩm này.", parse_mode='Markdown')
    else:
        set_new_product_enabled(True)
        bot.send_message(id, f"🟢 *ĐÃ BẬT BÁN {pname.upper()}*\n\n✅ Khách hàng có thể mua sản phẩm này.", parse_mode='Markdown')
    manage_canva_accounts(message)

# Handler for global sales toggle
def is_sales_toggle_button(text):
    return "TẮT bán tất cả" in text or "BẬT bán tất cả" in text

@bot.message_handler(content_types=["text"], func=lambda message: is_sales_toggle_button(message.text))
def toggle_sales_mode(message):
    id = message.from_user.id
    lang = get_user_lang(id)

    if not is_admin(id):
        bot.send_message(id, "❌ Chỉ admin mới có quyền truy cập!", reply_markup=create_main_keyboard(lang, id))
        return

    if "TẮT bán tất cả" in message.text:
        set_sales_enabled(False)
        bot.send_message(id, "🔴 *ĐÃ TẮT BÁN TẤT CẢ SẢN PHẨM*\n\n⚠️ Tạm ngưng bán cho khách hàng.\nAdmin vẫn có thể thao tác bình thường.", parse_mode='Markdown')
    else:
        set_sales_enabled(True)
        bot.send_message(id, "🟢 *ĐÃ BẬT BÁN TẤT CẢ SẢN PHẨM*\n\n✅ Khách hàng có thể mua bình thường.", parse_mode='Markdown')

    # Refresh admin menu
    send_welcome(message)

# ============== ADMIN: ĐIỀU CHỈNH GIÁ ==============

def format_price_vnd(price):
    """Format price with K suffix"""
    if price >= 1000:
        if price % 1000 == 0:
            return f"{price // 1000}K"
        return f"{price:,}đ"
    return f"{price:,}đ"

@bot.message_handler(content_types=["text"], func=lambda message: message.text == "💰 Điều chỉnh giá")
def show_price_management(message):
    """Admin: Show price management menu"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    cfg = get_price_config()
    
    msg = "💰 <b>ĐIỀU CHỈNH GIÁ SẢN PHẨM CANVA</b>\n"
    msg += "━━━━━━━━━━━━━━\n\n"
    msg += "⚡ <b>1. Canva Edu Admin - BH 3 tháng:</b>\n"
    msg += f"   • 1-9 acc: {format_price_vnd(cfg['canva_bh3']['tier1'])}\n"
    msg += f"   • ≥10 acc: {format_price_vnd(cfg['canva_bh3']['tier10'])}\n"
    msg += f"   • ≥50 acc: {format_price_vnd(cfg['canva_bh3']['tier50'])}\n\n"
    msg += "⚡ <b>2. Canva Edu Admin - KBH:</b>\n"
    msg += f"   • 1-9 acc: {format_price_vnd(cfg['canva_kbh']['tier1'])}\n"
    msg += f"   • ≥10 acc: {format_price_vnd(cfg['canva_kbh']['tier10'])}\n"
    msg += f"   • ≥50 acc: {format_price_vnd(cfg['canva_kbh']['tier50'])}\n\n"
    msg += "♻️ <b>3. Up lại Canva Edu:</b>\n"
    msg += f"   • KBH: {format_price_vnd(cfg['upgrade_kbh'])}\n"
    msg += f"   • BH 3 tháng: {format_price_vnd(cfg['upgrade_bh3'])}\n\n"
    msg += "🎫 <b>4. Slot Canva Edu:</b>\n"
    msg += f"   • Giá/slot: {format_price_vnd(cfg['slot_price'])}\n\n"
    msg += "🆕 <b>5. " + get_new_product_name() + ":</b>\n"
    packages = get_new_product_packages()
    for key in ["1m", "3m", "6m", "1y"]:
        pkg = packages[key]
        msg += f"   • {pkg['name']}: {format_price_vnd(pkg['price'])}\n"
    msg += "\n"
    msg += "👇 Chọn sản phẩm cần điều chỉnh giá:"
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="📝 Sửa giá Canva BH3"))
    keyboard.row(types.KeyboardButton(text="📝 Sửa giá Canva KBH"))
    keyboard.row(types.KeyboardButton(text="📝 Sửa giá Up lại"))
    keyboard.row(types.KeyboardButton(text="📝 Sửa giá Slot"))
    keyboard.row(types.KeyboardButton(text=f"📝 Sửa giá {get_new_product_name()}"))
    keyboard.row(types.KeyboardButton(text=f"✏️ Đổi tên {get_new_product_name()}"))
    keyboard.row(types.KeyboardButton(text="🔄 Khôi phục giá mặc định"))
    keyboard.row(types.KeyboardButton(text="⬅️ Quay lại quản lý Canva"))
    
    bot.send_message(id, msg, reply_markup=keyboard, parse_mode='HTML')

@bot.message_handler(content_types=["text"], func=lambda message: message.text == "⬅️ Quay lại quản lý Canva")
def back_to_canva_management(message):
    """Return to Canva management menu"""
    manage_canva_accounts(message)

@bot.message_handler(content_types=["text"], func=lambda message: message.text == "🔄 Khôi phục giá mặc định")
def reset_default_prices(message):
    """Admin: Reset all prices to default"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    global price_config
    price_config = DEFAULT_PRICE_CONFIG.copy()
    save_price_config(price_config)
    bot.send_message(id, "✅ Đã khôi phục tất cả giá về mặc định!", parse_mode='HTML')
    show_price_management(message)

@bot.message_handler(content_types=["text"], func=lambda message: message.text == "📝 Sửa giá Canva BH3")
def edit_price_canva_bh3(message):
    """Admin: Edit Canva BH3 prices"""
    id = message.from_user.id
    lang = get_user_lang(id)
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    cfg = get_price_config()
    keyboard = create_cancel_keyboard()
    msg = f"📝 <b>Sửa giá Canva Edu Admin - BH 3 tháng</b>\n\n"
    msg += f"Giá hiện tại:\n"
    msg += f"• 1-9 acc: {format_price_vnd(cfg['canva_bh3']['tier1'])}\n"
    msg += f"• ≥10 acc: {format_price_vnd(cfg['canva_bh3']['tier10'])}\n"
    msg += f"• ≥50 acc: {format_price_vnd(cfg['canva_bh3']['tier50'])}\n\n"
    msg += "Nhập giá mới theo định dạng:\n<code>giá_1-9 giá_10+ giá_50+</code>\n\n"
    msg += "Ví dụ: <code>100000 50000 25000</code>\n"
    msg += "(đơn vị VND, cách nhau bởi dấu cách)"
    sent = bot.send_message(id, msg, reply_markup=keyboard, parse_mode='HTML')
    pending_price_edit[id] = "canva_bh3"
    bot.register_next_step_handler(sent, process_price_edit)

@bot.message_handler(content_types=["text"], func=lambda message: message.text == "📝 Sửa giá Canva KBH")
def edit_price_canva_kbh(message):
    """Admin: Edit Canva KBH prices"""
    id = message.from_user.id
    lang = get_user_lang(id)
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    cfg = get_price_config()
    keyboard = create_cancel_keyboard()
    msg = f"📝 <b>Sửa giá Canva Edu Admin - KBH</b>\n\n"
    msg += f"Giá hiện tại:\n"
    msg += f"• 1-9 acc: {format_price_vnd(cfg['canva_kbh']['tier1'])}\n"
    msg += f"• ≥10 acc: {format_price_vnd(cfg['canva_kbh']['tier10'])}\n"
    msg += f"• ≥50 acc: {format_price_vnd(cfg['canva_kbh']['tier50'])}\n\n"
    msg += "Nhập giá mới theo định dạng:\n<code>giá_1-9 giá_10+ giá_50+</code>\n\n"
    msg += "Ví dụ: <code>40000 20000 10000</code>\n"
    msg += "(đơn vị VND, cách nhau bởi dấu cách)"
    sent = bot.send_message(id, msg, reply_markup=keyboard, parse_mode='HTML')
    pending_price_edit[id] = "canva_kbh"
    bot.register_next_step_handler(sent, process_price_edit)

@bot.message_handler(content_types=["text"], func=lambda message: message.text == "📝 Sửa giá Up lại")
def edit_price_upgrade(message):
    """Admin: Edit upgrade prices"""
    id = message.from_user.id
    lang = get_user_lang(id)
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    cfg = get_price_config()
    keyboard = create_cancel_keyboard()
    msg = f"📝 <b>Sửa giá Up lại Canva Edu</b>\n\n"
    msg += f"Giá hiện tại:\n"
    msg += f"• KBH: {format_price_vnd(cfg['upgrade_kbh'])}\n"
    msg += f"• BH 3 tháng: {format_price_vnd(cfg['upgrade_bh3'])}\n\n"
    msg += "Nhập giá mới theo định dạng:\n<code>giá_KBH giá_BH3</code>\n\n"
    msg += "Ví dụ: <code>100000 250000</code>\n"
    msg += "(đơn vị VND, cách nhau bởi dấu cách)"
    sent = bot.send_message(id, msg, reply_markup=keyboard, parse_mode='HTML')
    pending_price_edit[id] = "upgrade"
    bot.register_next_step_handler(sent, process_price_edit)

@bot.message_handler(content_types=["text"], func=lambda message: message.text == "📝 Sửa giá Slot")
def edit_price_slot(message):
    """Admin: Edit slot price"""
    id = message.from_user.id
    lang = get_user_lang(id)
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    cfg = get_price_config()
    keyboard = create_cancel_keyboard()
    msg = f"📝 <b>Sửa giá Slot Canva Edu</b>\n\n"
    msg += f"Giá hiện tại: {format_price_vnd(cfg['slot_price'])}/slot\n\n"
    msg += "Nhập giá mới cho 1 slot:\n"
    msg += "Ví dụ: <code>5000</code>\n"
    msg += "(đơn vị VND)"
    sent = bot.send_message(id, msg, reply_markup=keyboard, parse_mode='HTML')
    pending_price_edit[id] = "slot"
    bot.register_next_step_handler(sent, process_price_edit)

@bot.message_handler(content_types=["text"], func=lambda message: message.text.startswith("📝 Sửa giá") and message.text == f"📝 Sửa giá {get_new_product_name()}")
def edit_price_new_product(message):
    """Admin: Edit new product package prices"""
    id = message.from_user.id
    lang = get_user_lang(id)
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    packages = get_new_product_packages()
    keyboard = create_cancel_keyboard()
    msg = f"📝 <b>Sửa giá {get_new_product_name()}</b>\n\n"
    msg += "Giá hiện tại:\n"
    for key in ["1m", "3m", "6m", "1y"]:
        pkg = packages[key]
        msg += f"  • {pkg['name']}: {format_price_vnd(pkg['price'])}\n"
    msg += "\nNhập 4 giá mới (cách nhau bởi dấu cách):\n"
    msg += "<code>1thang 3thang 6thang 1nam</code>\n"
    msg += "Ví dụ: <code>35000 90000 160000 290000</code>\n"
    msg += "(đơn vị VND)"
    sent = bot.send_message(id, msg, reply_markup=keyboard, parse_mode='HTML')
    pending_price_edit[id] = "new_product"
    bot.register_next_step_handler(sent, process_price_edit)

@bot.message_handler(content_types=["text"], func=lambda message: message.text.startswith("✏️ Đổi tên") and message.text == f"✏️ Đổi tên {get_new_product_name()}")
def rename_new_product(message):
    """Admin: Rename the new product"""
    id = message.from_user.id
    lang = get_user_lang(id)
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    keyboard = create_cancel_keyboard()
    current_name = get_new_product_name()
    msg = f"✏️ <b>Đổi tên sản phẩm</b>\n\n"
    msg += f"Tên hiện tại: <b>{current_name}</b>\n\n"
    msg += "Nhập tên mới cho sản phẩm:\n"
    msg += "(Tối đa 50 ký tự)"
    sent = bot.send_message(id, msg, reply_markup=keyboard, parse_mode='HTML')
    pending_product_rename[id] = True
    bot.register_next_step_handler(sent, process_product_rename)

def process_product_rename(message):
    """Process product rename input from admin"""
    id = message.from_user.id
    lang = get_user_lang(id)

    if not is_admin(id):
        return

    # Check cancel
    if is_cancel_action(message.text):
        if id in pending_product_rename:
            del pending_product_rename[id]
        show_price_management(message)
        return

    if id not in pending_product_rename:
        bot.send_message(id, "❌ Phiên đổi tên đã hết hạn.", reply_markup=create_main_keyboard(lang, id))
        return

    new_name = message.text.strip()
    if not new_name or len(new_name) > 50:
        bot.send_message(id, "❌ Tên không hợp lệ! Tên phải từ 1-50 ký tự.", parse_mode='HTML')
        if id in pending_product_rename:
            del pending_product_rename[id]
        show_price_management(message)
        return

    old_name = get_new_product_name()
    update_price_config("new_product_name", new_name)
    bot.send_message(id, f"✅ Đã đổi tên sản phẩm!\n\n<b>{old_name}</b> → <b>{new_name}</b>", parse_mode='HTML')

    if id in pending_product_rename:
        del pending_product_rename[id]
    show_price_management(message)

def process_price_edit(message):
    """Process price edit input from admin"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    # Check cancel
    if is_cancel_action(message.text):
        if id in pending_price_edit:
            del pending_price_edit[id]
        show_price_management(message)
        return
    
    edit_type = pending_price_edit.get(id)
    if not edit_type:
        bot.send_message(id, "❌ Phiên chỉnh sửa đã hết hạn.", reply_markup=create_main_keyboard(lang, id))
        return
    
    try:
        parts = message.text.strip().split()
        cfg = get_price_config()
        
        if edit_type in ["canva_bh3", "canva_kbh"]:
            if len(parts) != 3:
                bot.send_message(id, "❌ Sai định dạng! Cần nhập 3 số cách nhau bởi dấu cách.\nVí dụ: <code>100000 50000 25000</code>", parse_mode='HTML')
                if id in pending_price_edit:
                    del pending_price_edit[id]
                show_price_management(message)
                return
            tier1, tier10, tier50 = int(parts[0]), int(parts[1]), int(parts[2])
            if tier1 <= 0 or tier10 <= 0 or tier50 <= 0:
                raise ValueError("Giá phải lớn hơn 0")
            update_price_config(edit_type, {"tier1": tier1, "tier10": tier10, "tier50": tier50})
            label = "BH 3 tháng" if edit_type == "canva_bh3" else "KBH"
            bot.send_message(id, f"✅ Đã cập nhật giá <b>Canva Edu Admin - {label}</b>:\n• 1-9 acc: {format_price_vnd(tier1)}\n• ≥10 acc: {format_price_vnd(tier10)}\n• ≥50 acc: {format_price_vnd(tier50)}", parse_mode='HTML')
        
        elif edit_type == "upgrade":
            if len(parts) != 2:
                bot.send_message(id, "❌ Sai định dạng! Cần nhập 2 số cách nhau bởi dấu cách.\nVí dụ: <code>100000 250000</code>", parse_mode='HTML')
                if id in pending_price_edit:
                    del pending_price_edit[id]
                show_price_management(message)
                return
            kbh_price, bh3_price = int(parts[0]), int(parts[1])
            if kbh_price <= 0 or bh3_price <= 0:
                raise ValueError("Giá phải lớn hơn 0")
            update_price_config("upgrade_kbh", kbh_price)
            update_price_config("upgrade_bh3", bh3_price)
            bot.send_message(id, f"✅ Đã cập nhật giá <b>Up lại Canva Edu</b>:\n• KBH: {format_price_vnd(kbh_price)}\n• BH 3 tháng: {format_price_vnd(bh3_price)}", parse_mode='HTML')
        
        elif edit_type == "slot":
            if len(parts) != 1:
                bot.send_message(id, "❌ Sai định dạng! Cần nhập 1 số.\nVí dụ: <code>5000</code>", parse_mode='HTML')
                if id in pending_price_edit:
                    del pending_price_edit[id]
                show_price_management(message)
                return
            slot_price = int(parts[0])
            if slot_price <= 0:
                raise ValueError("Giá phải lớn hơn 0")
            update_price_config("slot_price", slot_price)
            bot.send_message(id, f"✅ Đã cập nhật giá <b>Slot Canva Edu</b>: {format_price_vnd(slot_price)}/slot", parse_mode='HTML')

        elif edit_type == "new_product":
            if len(parts) != 4:
                bot.send_message(id, "❌ Sai định dạng! Cần nhập 4 số (1 tháng, 3 tháng, 6 tháng, 1 năm).\nVí dụ: <code>35000 90000 160000 290000</code>", parse_mode='HTML')
                if id in pending_price_edit:
                    del pending_price_edit[id]
                show_price_management(message)
                return
            prices = [int(p) for p in parts]
            for p in prices:
                if p <= 0:
                    raise ValueError("Giá phải lớn hơn 0")
            packages = get_new_product_packages()
            pkg_keys = ["1m", "3m", "6m", "1y"]
            for i, key in enumerate(pkg_keys):
                packages[key]["price"] = prices[i]
            update_price_config("new_product_packages", packages)
            result_msg = f"✅ Đã cập nhật giá <b>{get_new_product_name()}</b>:\n"
            for key in pkg_keys:
                result_msg += f"  • {packages[key]['name']}: {format_price_vnd(packages[key]['price'])}\n"
            bot.send_message(id, result_msg, parse_mode='HTML')
        
    except ValueError as e:
        bot.send_message(id, f"❌ Giá không hợp lệ: {str(e)}\nVui lòng nhập số nguyên dương.", parse_mode='HTML')
    except Exception as e:
        bot.send_message(id, f"❌ Lỗi: {str(e)}", parse_mode='HTML')
    
    if id in pending_price_edit:
        del pending_price_edit[id]
    show_price_management(message)

# ============== ADMIN: GÁN TÀI KHOẢN CHO USER ==============

# State storage for assign account flow
assign_account_state = {}

# State storage for slot order flow (waiting for email input)
# Format: {user_id: {"quantity": int, "username": str}}
pending_slot_email_state = {}

# Store slot order emails for admin callback (ordernumber -> canva_email)
slot_order_emails = {}

# State storage for admin manual Canva delivery (admin entering account details)
# Format: {admin_id: {"ordernumber": str, "buyer_user_id": int, "admin_msg_chat_id": int, "admin_msg_id": int, "step": "account"|"otp_link", "account_details": str}}
pending_canva_delivery = {}

# State storage for new product email input flow (user entering Google email)
# Format: {user_id: {"package_type": str, "username": str}}
pending_new_product_email = {}

# Store new product order info for delivery (ordernumber -> {google_email, package_label, product_name})
# Persists after webhook so admin can click "Done" later
pending_newprod_orders = {}

# Check if message matches assign account button
def is_assign_account_button(text):
    keywords = ["🎁 Gán tài khoản cho user", "Gán tài khoản"]
    return any(kw in text for kw in keywords)

# Handler for assign account to user (Admin only)
@bot.message_handler(content_types=["text"], func=lambda message: is_assign_account_button(message.text))
def admin_assign_account_start(message):
    """Admin: Start assign account to user flow"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, "❌ Chỉ admin mới có quyền truy cập!", reply_markup=create_main_keyboard(lang, id))
        return
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="❌ Hủy"))
    
    msg = f"🎁 *GÁN TÀI KHOẢN CHO USER*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"📝 *Bước 1:* Nhập User ID của người dùng cần gán tài khoản:\n"
    msg += f"_(Ví dụ: 123456789)_"
    
    sent_msg = bot.send_message(id, msg, reply_markup=keyboard, parse_mode="Markdown")
    bot.register_next_step_handler(sent_msg, admin_assign_account_get_user_id)

def admin_assign_account_get_user_id(message):
    """Step 2: Get user ID to assign account"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    if is_cancel_action(message.text):
        bot.send_message(id, "❌ Đã hủy", reply_markup=create_main_keyboard(lang, id))
        return
    
    try:
        target_user_id = int(message.text.strip())
    except ValueError:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row(types.KeyboardButton(text="❌ Hủy"))
        msg = bot.send_message(id, "❌ User ID không hợp lệ! Vui lòng nhập số.\n\n📝 Nhập lại User ID:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, admin_assign_account_get_user_id)
        return
    
    # Store state
    assign_account_state[id] = {'target_user_id': target_user_id}
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="❌ Hủy"))
    
    msg = f"🎁 *GÁN TÀI KHOẢN CHO USER*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"👤 User ID: `{target_user_id}`\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"📝 *Bước 2:* Nhập email Canva cần gán:\n"
    msg += f"_(Ví dụ: example@domain.com)_"
    
    sent_msg = bot.send_message(id, msg, reply_markup=keyboard, parse_mode="Markdown")
    bot.register_next_step_handler(sent_msg, admin_assign_account_get_email)

def admin_assign_account_get_email(message):
    """Step 3: Get Canva email to assign"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    if is_cancel_action(message.text):
        bot.send_message(id, "❌ Đã hủy", reply_markup=create_main_keyboard(lang, id))
        if id in assign_account_state:
            del assign_account_state[id]
        return
    
    canva_email = message.text.strip().lower()
    
    # Validate email format
    if '@' not in canva_email or '.' not in canva_email:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row(types.KeyboardButton(text="❌ Hủy"))
        msg = bot.send_message(id, "❌ Email không hợp lệ!\n\n📝 Nhập lại email Canva:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, admin_assign_account_get_email)
        return
    
    if id not in assign_account_state:
        bot.send_message(id, "❌ Lỗi! Vui lòng thử lại.", reply_markup=create_main_keyboard(lang, id))
        return
    
    # Store email in state
    assign_account_state[id]['canva_email'] = canva_email
    target_user_id = assign_account_state[id]['target_user_id']
    
    # Check if account already assigned
    existing = CanvaAccountDB.get_account_by_email(canva_email)
    if existing and existing['status'] == 'sold' and existing.get('buyer_id'):
        # Account already assigned to someone
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        inline_kb.add(types.InlineKeyboardButton(text="✅ Gán đè (reassign)", callback_data=f"reassign_{canva_email}_{target_user_id}"))
        inline_kb.add(types.InlineKeyboardButton(text="❌ Hủy", callback_data="assign_cancel"))
        
        msg = f"⚠️ *TÀI KHOẢN ĐÃ ĐƯỢC GÁN*\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"📧 Email: `{canva_email}`\n"
        msg += f"👤 Đang thuộc về: `{existing['buyer_id']}`\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"Bạn có muốn gán đè cho user `{target_user_id}` không?"
        
        bot.send_message(id, msg, reply_markup=inline_kb, parse_mode="Markdown")
        return
    
    # Ask for password (optional) - with inline button to skip
    # Store email in state for callback to use
    inline_kb = types.InlineKeyboardMarkup(row_width=1)
    inline_kb.add(types.InlineKeyboardButton(text="⏭ Bỏ qua (không có mật khẩu)", callback_data=f"assign_skip_pw"))
    inline_kb.add(types.InlineKeyboardButton(text="❌ Hủy", callback_data="assign_cancel"))
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="❌ Hủy"))
    
    msg = f"🎁 *GÁN TÀI KHOẢN CHO USER*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"👤 User ID: `{target_user_id}`\n"
    msg += f"📧 Email: `{canva_email}`\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"📝 *Bước 3:* Nhập mật khẩu hoặc nhấn Bỏ qua:"
    
    bot.send_message(id, msg, reply_markup=inline_kb, parse_mode="Markdown")
    bot.register_next_step_handler(message, admin_assign_account_get_password)

def admin_assign_account_get_password(message):
    """Step 4: Get password (optional) and complete assignment"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    if is_cancel_action(message.text):
        bot.send_message(id, "❌ Đã hủy", reply_markup=create_main_keyboard(lang, id))
        if id in assign_account_state:
            del assign_account_state[id]
        return
    
    if id not in assign_account_state:
        bot.send_message(id, "❌ Lỗi! Vui lòng thử lại.", reply_markup=create_main_keyboard(lang, id))
        return
    
    # Get password (or None if skipped)
    password = None
    if "Bỏ qua" not in message.text:
        password = message.text.strip()
    
    target_user_id = assign_account_state[id]['target_user_id']
    canva_email = assign_account_state[id]['canva_email']
    
    order_num = f"ADMIN_{int(time.time())}"
    
    # Check if account exists
    existing = CanvaAccountDB.get_account_by_email(canva_email)
    if existing:
        # Account exists - just assign
        result = CanvaAccountDB.assign_account_to_buyer(existing['id'], target_user_id, order_num)
    else:
        # Account doesn't exist - add and assign in one step (status = sold)
        result = CanvaAccountDB.add_and_assign_account(canva_email, target_user_id, order_num)
    
    if result:
        # Success - create inline buttons
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        inline_kb.add(types.InlineKeyboardButton(text=f"🔑 Lấy OTP: {canva_email}", callback_data=f"otp_{canva_email}"))
        inline_kb.add(types.InlineKeyboardButton(text="📋 Gán thêm tài khoản", callback_data="assign_more"))
        
        success_msg = f"✅ *GÁN TÀI KHOẢN THÀNH CÔNG!*\n"
        success_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        success_msg += f"👤 User ID: `{target_user_id}`\n"
        success_msg += f"📧 Email: `{canva_email}`\n"
        if password:
            success_msg += f"🔐 Mật khẩu: `{password}`\n"
        success_msg += f"🆔 Mã đơn: `{order_num}`\n"
        success_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        success_msg += f"_Nhấn nút bên dưới để lấy OTP hoặc gán thêm_"
        
        bot.send_message(id, success_msg, reply_markup=inline_kb, parse_mode="Markdown")
        
        # Notify the target user
        try:
            user_msg = f"✅ *ADMIN ĐÃ GÁN TÀI KHOẢN CHO BẠN!*\n"
            user_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            user_msg += f"📧 Email: `{canva_email}`\n"
            if password:
                user_msg += f"🔐 Mật khẩu: `{password}`\n"
            user_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            user_msg += f"_Nhấn nút bên dưới để lấy mã xác thực_"
            
            user_inline_kb = types.InlineKeyboardMarkup()
            user_inline_kb.add(types.InlineKeyboardButton(text=f"🔑 Lấy OTP", callback_data=f"otp_{canva_email}"))
            
            bot.send_message(target_user_id, user_msg, reply_markup=user_inline_kb, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Could not notify user {target_user_id}: {e}")
    else:
        bot.send_message(id, "❌ Lỗi khi gán tài khoản!", reply_markup=create_main_keyboard(lang, id))
    
    # Cleanup state
    if id in assign_account_state:
        del assign_account_state[id]

def admin_assign_account_start_inline(user_id, chat_id):
    """Helper function to start assign flow from inline button"""
    lang = get_user_lang(user_id)
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="❌ Hủy"))
    
    msg = f"🎁 *GÁN TÀI KHOẢN CHO USER*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"📝 *Bước 1:* Nhập User ID của người dùng cần gán tài khoản:\n"
    msg += f"_(Ví dụ: 123456789)_"
    
    sent_msg = bot.send_message(chat_id, msg, reply_markup=keyboard, parse_mode="Markdown")
    bot.register_next_step_handler(sent_msg, admin_assign_account_get_user_id)

# Manage users handler
@bot.message_handler(content_types=["text"], func=lambda message: is_manage_users_button(message.text))
def manage_users(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, "❌ Chỉ admin mới có quyền truy cập!", reply_markup=create_main_keyboard(lang, id))
        return
    
    # Get all users with created_at
    all_users = GetDataFromDB.GetUsersInfoWithDate()
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="🎁 Gán tài khoản cho user"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    if not all_users:
        bot.send_message(id, "📭 Chưa có người dùng nào!", reply_markup=keyboard)
        return
    
    msg = f"👥 *QUẢN LÝ NGƯỜI DÙNG*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 Tổng: {len(all_users)} người dùng\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"Nhấn nút bên dưới để gán tài khoản cho user"
    
    try:
        bot.send_message(id, msg, reply_markup=keyboard, parse_mode="Markdown")
    except:
        # Fallback không dùng Markdown
        msg_plain = msg.replace("*", "")
        bot.send_message(id, msg_plain, reply_markup=keyboard)

# Check if message matches manage promotion button
def is_manage_promotion_button(text):
    keywords = ["Quản lý khuyến mãi", "quản lý khuyến mãi", "Manage Promotion"]
    return any(kw in text for kw in keywords)

# Handler for promotion management
@bot.message_handler(content_types=["text"], func=lambda message: is_manage_promotion_button(message.text))
def manage_promotion(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, "❌ Chỉ admin mới có quyền truy cập!", reply_markup=create_main_keyboard(lang, id))
        return
    
    promo_info = PromotionDB.get_promotion_info()
    
    max_slots = promo_info['max_count'] if promo_info else 10
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if promo_info and promo_info["is_active"]:
        keyboard.row(types.KeyboardButton(text="🔴 TẮT khuyến mãi"))
    else:
        keyboard.row(types.KeyboardButton(text="🟢 BẬT khuyến mãi"))
    keyboard.row(types.KeyboardButton(text="⚙️ Đặt số slot khuyến mãi"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    status_text = "🎁 *QUẢN LÝ KHUYẾN MÃI MUA 1 TẶNG 1*\n"
    status_text += "━━━━━━━━━━━━━━━━━━━━\n"
    if promo_info:
        if promo_info["is_active"]:
            status_text += f"📊 *Trạng thái:* ✅ ĐANG BẬT\n"
            status_text += f"🎫 *Tổng slot:* {promo_info['max_count']}\n"
            status_text += f"📈 *Đã bán:* {promo_info['sold_count']} slot\n"
            remaining = promo_info['max_count'] - promo_info['sold_count']
            status_text += f"🎯 *Còn lại:* {remaining} slot khuyến mãi\n"
            if promo_info['started_at']:
                status_text += f"⏰ *Bắt đầu:* {promo_info['started_at']}\n"
        else:
            status_text += f"📊 *Trạng thái:* ❌ TẮT\n"
            status_text += f"🎫 *Tổng slot:* {promo_info['max_count']}\n"
    else:
        status_text += f"📊 *Trạng thái:* ❌ TẮT\n"
    
    status_text += "━━━━━━━━━━━━━━━━━━━━\n"
    status_text += f"_Khi BẬT: {max_slots} tài khoản đầu tiên sẽ được tặng thêm_\n"
    status_text += "_Khi TẮT: Hủy khuyến mãi, bật lại sẽ đếm từ đầu_"
    
    bot.send_message(id, status_text, reply_markup=keyboard, parse_mode="Markdown")

# Handler for enable promotion
@bot.message_handler(content_types=["text"], func=lambda message: "BẬT khuyến mãi" in message.text)
def enable_promotion(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    promo_info = PromotionDB.get_promotion_info()
    max_slots = promo_info['max_count'] if promo_info else 10
    PromotionDB.enable_promotion()
    bot.send_message(id, f"✅ *Đã BẬT khuyến mãi!*\n\n🎁 {max_slots} tài khoản tiếp theo sẽ được tặng thêm.\nĐếm bắt đầu từ 0.", reply_markup=create_main_keyboard(lang, id), parse_mode="Markdown")

# Handler for disable promotion
@bot.message_handler(content_types=["text"], func=lambda message: "TẮT khuyến mãi" in message.text)
def disable_promotion(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    PromotionDB.disable_promotion()
    bot.send_message(id, "❌ *Đã TẮT khuyến mãi!*\n\n_Khuyến mãi đã bị hủy. Bật lại sẽ đếm từ đầu._", reply_markup=create_main_keyboard(lang, id), parse_mode="Markdown")

# Handler for set promotion slots
@bot.message_handler(content_types=["text"], func=lambda message: "Đặt số slot khuyến mãi" in message.text)
def set_promo_slots(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    promo_info = PromotionDB.get_promotion_info()
    current_slots = promo_info['max_count'] if promo_info else 10
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="5"), types.KeyboardButton(text="10"), types.KeyboardButton(text="15"))
    keyboard.row(types.KeyboardButton(text="20"), types.KeyboardButton(text="30"), types.KeyboardButton(text="50"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    msg = bot.send_message(id, f"⚙️ *Đặt số slot khuyến mãi*\n\n📊 Hiện tại: {current_slots} slot\n\n_Chọn số slot hoặc nhập số tùy ý:_", reply_markup=keyboard, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_set_slots)

def process_set_slots(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if message.text == "🏠 Trang chủ":
        send_welcome(message)
        return
    
    try:
        new_slots = int(message.text)
        if new_slots < 1:
            bot.send_message(id, "❌ Số slot phải lớn hơn 0!", reply_markup=create_main_keyboard(lang, id))
            return
        
        PromotionDB.set_max_count(new_slots)
        bot.send_message(id, f"✅ *Đã đặt số slot khuyến mãi: {new_slots}*", reply_markup=create_main_keyboard(lang, id), parse_mode="Markdown")
    except ValueError:
        bot.send_message(id, "❌ Vui lòng nhập số hợp lệ!", reply_markup=create_main_keyboard(lang, id))

# Check if message matches manage canva accounts button
def is_manage_canva_button(text):
    return "Quản lý tài khoản Canva" in text or "📧 Quản lý tài khoản Canva" in text

# Handler for manage Canva accounts
@bot.message_handler(content_types=["text"], func=lambda message: is_manage_canva_button(message.text))
def manage_canva_accounts(message):
    """Admin: Manage Canva accounts"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    # Show Canva account management menu
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="➕ Thêm tài khoản Canva"))
    keyboard.row(types.KeyboardButton(text="📋 Danh sách tài khoản"))
    keyboard.row(types.KeyboardButton(text="🗑 Xóa tài khoản Canva"))
    keyboard.row(types.KeyboardButton(text="📊 Thống kê tài khoản"))
    keyboard.row(types.KeyboardButton(text="💰 Điều chỉnh giá"))
    # Product toggle buttons
    canva_btn = "🔴 TẮT bán Canva (đang bật)" if canva_product_enabled else "🟢 BẬT bán Canva (đang tắt)"
    slot_btn = "🔴 TẮT bán Slot (đang bật)" if slot_product_enabled else "🟢 BẬT bán Slot (đang tắt)"
    keyboard.row(types.KeyboardButton(text=canva_btn))
    keyboard.row(types.KeyboardButton(text=slot_btn))
    newp_btn = f"🔴 TẮT bán {get_new_product_name()} (đang bật)" if new_product_enabled else f"🟢 BẬT bán {get_new_product_name()} (đang tắt)"
    keyboard.row(types.KeyboardButton(text=newp_btn))
    if upgrade_product_enabled:
        keyboard.row(types.KeyboardButton(text="🔴 TẮT bán Up lại (đang bật)"))
    else:
        keyboard.row(types.KeyboardButton(text="🟢 BẬT bán Up lại (đang tắt)"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    count = CanvaAccountDB.get_account_count()
    canva_s = "✅" if canva_product_enabled else "❌"
    slot_s = "✅" if slot_product_enabled else "❌"
    newp_s = "✅" if new_product_enabled else "❌"
    upgrade_s = "✅" if upgrade_product_enabled else "❌"
    status_msg = f"📧 Quản lý tài khoản Canva\n\n📊 Còn {count} tài khoản khả dụng\n"
    status_msg += f"\n📦 *Trạng thái sản phẩm:*\n"
    status_msg += f"🛍 Canva Edu Admin: {canva_s}\n"
    status_msg += f"🎫 Slot Canva Edu: {slot_s}\n"
    status_msg += f"🆕 {get_new_product_name()}: {newp_s}\n"
    status_msg += f"♻️ Up lại Canva Edu: {upgrade_s}"
    bot.send_message(id, status_msg, reply_markup=keyboard, parse_mode='Markdown')

# Handler for add Canva account
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "➕ Thêm tài khoản Canva")
def add_canva_account_prompt(message):
    """Admin: Prompt to add Canva account"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    # With Premium, only need email (no authkey required)
    keyboard = create_cancel_keyboard()
    msg = bot.send_message(id, "📧 Gửi danh sách email tài khoản Canva\n\n✅ Đã dùng Premium - không cần authkey!\n\nĐịnh dạng:\nemail1@domain.xyz\nemail2@domain.xyz\nemail3@domain.xyz\n\n(Mỗi email 1 dòng)", reply_markup=keyboard)
    bot.register_next_step_handler(msg, process_canva_accounts_file)

def process_canva_accounts_file(message):
    """Process uploaded Canva accounts file"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    # Check cancel
    if is_cancel_action(message.text):
        send_welcome(message)
        return
    
    if message.document:
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            content = downloaded_file.decode('utf-8')
            
            count = CanvaAccountDB.import_emails_only(content)
            
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.row(types.KeyboardButton(text="➕ Thêm tài khoản Canva"))
            keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
            
            bot.send_message(id, f"✅ Đã thêm {count} tài khoản Canva!", reply_markup=keyboard)
        except Exception as e:
            bot.send_message(id, f"❌ Lỗi: {str(e)}", reply_markup=create_main_keyboard(lang, id))
    elif message.text:
        # Try to parse text directly
        try:
            count = CanvaAccountDB.import_emails_only(message.text)
            if count > 0:
                bot.send_message(id, f"✅ Đã thêm {count} tài khoản Canva!", reply_markup=create_main_keyboard(lang, id))
            else:
                bot.send_message(id, "❌ Không tìm thấy email hợp lệ. Mỗi email 1 dòng.", reply_markup=create_main_keyboard(lang, id))
        except Exception as e:
            bot.send_message(id, f"❌ Lỗi: {str(e)}", reply_markup=create_main_keyboard(lang, id))
    else:
        bot.send_message(id, "❌ Vui lòng gửi file .txt hoặc text", reply_markup=create_main_keyboard(lang, id))

# Handler for list Canva accounts
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "📋 Danh sách tài khoản")
def list_canva_accounts(message):
    """Admin: List all Canva accounts"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    accounts = CanvaAccountDB.get_all_accounts()
    
    if not accounts:
        bot.send_message(id, "📭 Chưa có tài khoản nào", reply_markup=create_main_keyboard(lang, id))
        return
    
    # Group by status
    available = [a for a in accounts if a[5] == 'available']
    sold = [a for a in accounts if a[5] == 'sold']
    
    msg = f"📧 Danh sách tài khoản Canva\n\n"
    msg += f"✅ Khả dụng: {len(available)}\n"
    msg += f"🛒 Đã bán: {len(sold)}\n\n"
    
    if available[:10]:
        msg += "📋 10 tài khoản khả dụng gần nhất:\n"
        for acc in available[:10]:
            msg += f"• {acc[1]}\n"
    
    bot.send_message(id, msg, reply_markup=create_main_keyboard(lang, id))

# Handler for delete Canva account
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "🗑 Xóa tài khoản Canva")
def delete_canva_account_prompt(message):
    """Admin: Prompt to delete Canva account"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    # Show available accounts to delete
    accounts = CanvaAccountDB.get_all_accounts()
    available = [a for a in accounts if a[5] == 'available']
    
    if not available:
        bot.send_message(id, "📭 Không có tài khoản nào để xóa", reply_markup=create_main_keyboard(lang, id))
        return
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="🗑 Xóa tất cả tài khoản"))
    for acc in available[:10]:  # Show max 10
        keyboard.add(types.KeyboardButton(text=f"❌ {acc[1]}"))
    keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
    
    bot.send_message(id, f"Chọn tài khoản cần xóa:\n\n(Hiển thị {min(10, len(available))}/{len(available)} tài khoản)", reply_markup=keyboard)

# Check if message is admin delete button (not user delete)
def is_admin_delete_button(text):
    # Admin format: "❌ email@domain.xyz" (no "Xóa:")
    # User format: "❌ Xóa: email@domain.xyz"
    return text.startswith("❌ ") and "Xóa:" not in text

# Handler for delete specific account (Admin only)
@bot.message_handler(content_types=["text"], func=lambda message: is_admin_delete_button(message.text))
def delete_specific_canva_account(message):
    """Admin: Delete specific Canva account"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    email = message.text.replace("❌ ", "")
    
    # Find and delete account
    accounts = CanvaAccountDB.get_all_accounts()
    for acc in accounts:
        if acc[1] == email:
            CanvaAccountDB.delete_account(acc[0])
            bot.send_message(id, f"✅ Đã xóa tài khoản: {email}", reply_markup=create_main_keyboard(lang, id))
            return
    
    bot.send_message(id, f"❌ Không tìm thấy tài khoản: {email}", reply_markup=create_main_keyboard(lang, id))

# Handler for delete all accounts
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "🗑 Xóa tất cả tài khoản")
def delete_all_canva_accounts(message):
    """Admin: Delete all available Canva accounts"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="✅ Xác nhận xóa tất cả"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    bot.send_message(id, "⚠️ Bạn có chắc muốn xóa TẤT CẢ tài khoản Canva chưa bán?", reply_markup=keyboard)

# Handler for confirm delete all
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "✅ Xác nhận xóa tất cả")
def confirm_delete_all_canva(message):
    """Admin: Confirm delete all accounts"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    accounts = CanvaAccountDB.get_all_accounts()
    available = [a for a in accounts if a[5] == 'available']
    
    count = 0
    for acc in available:
        if CanvaAccountDB.delete_account(acc[0]):
            count += 1
    
    bot.send_message(id, f"✅ Đã xóa {count} tài khoản Canva!", reply_markup=create_main_keyboard(lang, id))

# Handler for Canva account stats
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "📊 Thống kê tài khoản")
def canva_account_stats(message):
    """Admin: Show Canva account statistics"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    accounts = CanvaAccountDB.get_all_accounts()
    available = len([a for a in accounts if a[5] == 'available'])
    sold = len([a for a in accounts if a[5] == 'sold'])
    
    msg = f"📊 Thống kê tài khoản Canva\n\n"
    msg += f"📧 Tổng số: {len(accounts)}\n"
    msg += f"✅ Khả dụng: {available}\n"
    msg += f"🛒 Đã bán: {sold}\n"
    
    bot.send_message(id, msg, reply_markup=create_main_keyboard(lang, id))

# Check if message matches shop items button
def is_shop_items_button(text):
    keywords = ["Shop Items", "Cửa hàng", "shop items", "cửa hàng", "Mua Canva", "mua canva", "🎨 Mua Canva", "🛒 Mua ngay", "Mua ngay"]
    return any(kw in text for kw in keywords)

# Check if message is get OTP button
def is_get_otp_button(text):
    return "Lấy mã xác thực" in text or "🔑 Lấy mã xác thực" in text or "Lấy mã đăng nhập" in text

# Handler for get OTP button
@bot.message_handler(content_types=["text"], func=lambda message: is_get_otp_button(message.text))
def handle_get_otp(message):
    """Handle get OTP button - retrieve login code from TempMail"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(user_id):
        send_maintenance_message(message)
        return
    
    display_name = get_user_display_name(message)
    
    if not is_admin(user_id):
        notify_admin("🔑 Lấy OTP", display_name)
    
    # Get user's Canva accounts
    accounts = CanvaAccountDB.get_buyer_accounts(user_id)
    
    if not accounts:
        bot.send_message(user_id, "❌ Bạn chưa có tài khoản Canva nào. Vui lòng mua hàng trước.", reply_markup=create_main_keyboard(lang, user_id))
        return
    
    # Create keyboard to select which account to get OTP
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for acc in accounts:
        email = acc[0]
        keyboard.row(types.KeyboardButton(text=f"📧 {email}"))
    keyboard.row(types.KeyboardButton(text="🗑 Xóa tài khoản"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    if len(accounts) == 1:
        bot.send_message(user_id, f"📧 Tài khoản của bạn: {accounts[0][0]}\n\nBấm vào email để lấy mã xác thực:", reply_markup=keyboard)
    else:
        bot.send_message(user_id, f"📧 Bạn có {len(accounts)} tài khoản.\n\nChọn tài khoản cần lấy mã xác thực:", reply_markup=keyboard)

# Handler for delete account button
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "🗑 Xóa tài khoản")
def handle_delete_account_menu(message):
    """Show menu to delete Canva account from user's list"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(user_id):
        send_maintenance_message(message)
        return
    
    accounts = CanvaAccountDB.get_buyer_accounts(user_id)
    
    if not accounts:
        bot.send_message(user_id, "❌ Bạn không có tài khoản nào để xóa.", reply_markup=create_main_keyboard(lang, user_id))
        return
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for acc in accounts:
        email = acc[0]
        keyboard.row(types.KeyboardButton(text=f"❌ Xóa: {email}"))
    keyboard.row(types.KeyboardButton(text="🔙 Quay lại"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    bot.send_message(user_id, "⚠️ Chọn tài khoản muốn xóa:\n\n(Sau khi xóa, bạn sẽ không thể lấy mã xác thực cho tài khoản này nữa)", reply_markup=keyboard)

# Handler for confirm delete account
# Check if message is delete account button
def is_delete_account_button(text):
    return "Xóa:" in text and text.startswith("❌")

@bot.message_handler(content_types=["text"], func=lambda message: is_delete_account_button(message.text))
def handle_delete_account_confirm(message):
    """Delete Canva account from user's list"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(user_id):
        send_maintenance_message(message)
        return
    
    logger.info(f"Delete account request: {message.text}")
    
    # Extract email - handle different formats
    email = message.text
    if "Xóa: " in email:
        email = email.split("Xóa: ", 1)[1].strip()
    elif "Xóa:" in email:
        email = email.split("Xóa:", 1)[1].strip()
    
    logger.info(f"Deleting account: {email} for user {user_id}")
    
    # Remove buyer_id from account (set back to available or delete)
    success = CanvaAccountDB.remove_buyer_from_account(email, user_id)
    
    if success:
        bot.send_message(user_id, f"✅ Đã xóa tài khoản {email} khỏi danh sách của bạn.", reply_markup=create_main_keyboard(lang, user_id))
    else:
        bot.send_message(user_id, f"❌ Không thể xóa tài khoản {email}.", reply_markup=create_main_keyboard(lang, user_id))

# Handler for back button
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "🔙 Quay lại")
def handle_back_to_otp(message):
    """Go back to OTP menu"""
    handle_get_otp(message)

# Handler for email selection (for OTP)
@bot.message_handler(content_types=["text"], func=lambda message: message.text.startswith("📧 "))
def handle_email_selection(message):
    """Handle email selection for OTP retrieval"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(user_id):
        send_maintenance_message(message)
        return
    
    email = message.text.replace("📧 ", "")
    get_otp_for_email(user_id, email, lang)

def detect_otp_type(subject, text_body):
    """Detect the type of OTP/verification code from email content"""
    subject_lower = subject.lower()
    text_lower = text_body.lower()
    
    # Check for login/sign-in
    if any(kw in subject_lower or kw in text_lower for kw in ['sign in', 'log in', 'login', 'đăng nhập']):
        return "🔐 Mã xác thực ĐĂNG NHẬP"
    
    # Check for email change/update
    if any(kw in subject_lower or kw in text_lower for kw in ['change email', 'update email', 'thay đổi email', 'new email']):
        return "📧 Mã xác thực THAY ĐỔI EMAIL"
    
    # Check for password reset
    if any(kw in subject_lower or kw in text_lower for kw in ['reset password', 'password reset', 'đặt lại mật khẩu', 'forgot password']):
        return "🔒 Mã xác thực ĐẶT LẠI MẬT KHẨU"
    
    # Check for account verification
    if any(kw in subject_lower or kw in text_lower for kw in ['verify', 'verification', 'xác minh', 'confirm']):
        return "✅ Mã xác thực XÁC MINH TÀI KHOẢN"
    
    # Check for security/2FA
    if any(kw in subject_lower or kw in text_lower for kw in ['security', 'two-factor', '2fa', 'bảo mật']):
        return "🛡 Mã xác thực BẢO MẬT"
    
    # Default
    return "🔑 Mã xác thực Canva"

def get_otp_for_email(user_id, email, lang):
    """Get OTP from TempMail or EmailWorker for a specific email"""
    from tempmail_client import EmailWorkerClient
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="🔑 Lấy mã xác thực"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    # Check if user is rate limited
    if user_id in otp_rate_limit:
        remaining = otp_rate_limit[user_id] - time.time()
        if remaining > 0:
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            bot.send_message(user_id, f"⚠️ Bạn đã lấy mã quá {OTP_MAX_REQUESTS} lần.\n⏳ Vui lòng đợi {minutes} phút {seconds} giây.", reply_markup=keyboard)
            return
        else:
            # Rate limit expired, reset
            del otp_rate_limit[user_id]
            otp_request_count[user_id] = 0
    
    # Increment request count
    otp_request_count[user_id] = otp_request_count.get(user_id, 0) + 1
    current_count = otp_request_count[user_id]
    
    # Check if reached limit
    if current_count > OTP_MAX_REQUESTS:
        otp_rate_limit[user_id] = time.time() + OTP_LIMIT_DURATION
        bot.send_message(user_id, f"⚠️ Bạn đã lấy mã quá {OTP_MAX_REQUESTS} lần.\n⏳ Vui lòng đợi 15 phút.", reply_markup=keyboard)
        return
    
    logger.info(f"Getting OTP for email: {email} (request {current_count}/{OTP_MAX_REQUESTS})")
    loading_msg = bot.send_message(user_id, f"⏳ Đang kiểm tra hộp thư {email}...")
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="🔑 Lấy mã xác thực"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    try:
        # Check if email is from EmailWorker domain
        if EmailWorkerClient.is_worker_email(email):
            # Use EmailWorkerClient for dlndaiiii.indevs.in domain
            logger.info(f"Using EmailWorkerClient for {email}")
            worker_client = EmailWorkerClient()
            
            # Get all emails
            emails_raw = worker_client.get_all_emails(email)
            
            if emails_raw:
                # Find OTP in emails (newest first - already sorted by API)
                otp_found = False
                for mail_data in emails_raw:
                    otp_code = worker_client.find_otp(mail_data)
                    if otp_code:
                        subject = mail_data.get('s', 'No Subject')
                        # Escape Markdown characters
                        subject_safe = subject.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")[:50]
                        timestamp = mail_data.get('t', 0)
                        from datetime import datetime
                        # Convert to UTC+7
                        if timestamp:
                            mail_time = datetime.fromtimestamp(timestamp / 1000, tz=VN_TIMEZONE).strftime('%H:%M:%S %d/%m/%Y')
                        else:
                            mail_time = "N/A"
                        
                        msg = f"✅ 🔑 Mã xác thực Canva:\n\n"
                        msg += f"🔢 *{otp_code}*\n\n"
                        msg += f"📧 Email: {email}\n"
                        msg += f"📋 Tiêu đề: {subject_safe}{'...' if len(subject) > 50 else ''}\n"
                        msg += f"🕐 Nhận lúc: {mail_time}\n"
                        msg += f"⏰ Mã có hiệu lực trong vài phút"
                        
                        try:
                            bot.delete_message(user_id, loading_msg.message_id)
                        except:
                            pass
                        try:
                            bot.send_message(user_id, msg, reply_markup=keyboard, parse_mode="Markdown")
                        except:
                            # Fallback without parse_mode
                            bot.send_message(user_id, msg.replace("*", ""), reply_markup=keyboard)
                        otp_found = True
                        break
                
                if not otp_found:
                    # Show latest email
                    latest = emails_raw[0]
                    subject = latest.get('s', 'No Subject')
                    sender = latest.get('f', 'Unknown')
                    timestamp = latest.get('t', 0)
                    from datetime import datetime
                    # Convert to UTC+7
                    if timestamp:
                        mail_time = datetime.fromtimestamp(timestamp / 1000, tz=VN_TIMEZONE).strftime('%H:%M:%S %d/%m/%Y')
                    else:
                        mail_time = "N/A"
                    
                    msg = f"📬 Email mới nhất ({mail_time}):\n\nTừ: {sender}\nTiêu đề: {subject}\n\n❌ Không tìm thấy mã OTP trong email này."
                    try:
                        bot.delete_message(user_id, loading_msg.message_id)
                    except:
                        pass
                    bot.send_message(user_id, msg, reply_markup=keyboard)
            else:
                try:
                    bot.delete_message(user_id, loading_msg.message_id)
                except:
                    pass
                bot.send_message(user_id, "📭 Chưa có email mới. Vui lòng yêu cầu mã xác thực trên Canva rồi bấm lại nút.", reply_markup=keyboard)
            return
        
        # Use TempMail.fish for other domains
        # Use Premium login if credentials available, otherwise fallback to authkey
        if TEMPMAIL_EMAIL and TEMPMAIL_PASSWORD:
            client = TempMailClient(email=TEMPMAIL_EMAIL, password=TEMPMAIL_PASSWORD)
            logger.info("Using TempMail Premium login")
        else:
            # Fallback to authkey from database
            authkey = CanvaAccountDB.get_authkey_by_email(email)
            if not authkey:
                bot.send_message(user_id, f"❌ Không tìm thấy thông tin xác thực cho {email}", reply_markup=create_main_keyboard(lang, user_id))
                return
            client = TempMailClient(auth_key=authkey)
            logger.info(f"Using authkey: {authkey[:10]}...")
        
        # get_emails will auto-create custom alias for Premium accounts
        emails = client.get_emails(email)
        logger.info(f"get_emails response: {len(emails) if emails else 0} emails")
        
        # Check for error response
        if isinstance(emails, list) and len(emails) > 0 and "error" in emails[0]:
            error_msg = emails[0]['error']
            # Delete loading message
            try:
                bot.delete_message(user_id, loading_msg.message_id)
            except:
                pass
            # Handle 404 - email not found or expired
            if "404" in error_msg or "Not Found" in error_msg:
                msg = f"⚠️ Hộp thư *{email}* đã hết hạn hoặc không tồn tại trên TempMail.\n\n"
                msg += "📌 Email tạm thời thường hết hạn sau 24-48 giờ.\n"
                msg += "💬 Vui lòng liên hệ @dlndai để được hỗ trợ cấp tài khoản mới."
                bot.send_message(user_id, msg, reply_markup=keyboard, parse_mode="Markdown")
            else:
                bot.send_message(user_id, f"❌ Lỗi: {error_msg}", reply_markup=keyboard)
            return
        
        if isinstance(emails, list) and len(emails) > 0:
            # Sort emails by timestamp (newest first)
            sorted_emails = sorted(emails, key=lambda x: x.get('timestamp', 0), reverse=True)
            
            # Find Canva OTP email (check newest first)
            otp_found = False
            for mail in sorted_emails:
                subject = mail.get('subject', '')
                text_body = mail.get('textBody', '') or ''
                html_body = mail.get('htmlBody', '') or mail.get('body', '') or ''
                from_addr = mail.get('from', '').lower()
                timestamp = mail.get('timestamp', 0)
                
                # Check if it's from Canva
                if 'canva' in subject.lower() or 'canva' in from_addr:
                    # Extract OTP code (6 digits)
                    # PRIORITY 1: Check subject first (Canva often puts code in subject like "Mã đăng nhập của bạn là 301927")
                    otp_match = re.search(r'\b(\d{6})\b', subject)
                    
                    # PRIORITY 2: Try text body - look for pattern "Nhập XXXXXX" first
                    if not otp_match:
                        otp_match = re.search(r'Nhập\s*(\d{6})', text_body)
                    
                    # PRIORITY 3: Clean HTML from textBody and search
                    if not otp_match:
                        # Remove HTML tags and invisible characters
                        clean_text = re.sub(r'<[^>]+>', ' ', text_body)
                        clean_text = re.sub(r'[͏­\xa0\u200B-\u200D\uFEFF]+', '', clean_text)
                        otp_match = re.search(r'\b(\d{6})\b', clean_text)
                    
                    # Skip if found code is likely not OTP (like 000000 from CSS)
                    if otp_match and otp_match.group(1) == '000000':
                        otp_match = None
                    
                    if otp_match:
                        otp_code = otp_match.group(1)
                        # Detect OTP type
                        otp_type = detect_otp_type(subject, text_body)
                        # Format timestamp
                        from datetime import datetime
                        mail_time = datetime.fromtimestamp(timestamp / 1000).strftime('%H:%M:%S %d/%m/%Y') if timestamp else "N/A"
                        
                        msg = f"✅ {otp_type}:\n\n"
                        msg += f"🔢 *{otp_code}*\n\n"
                        msg += f"📧 Email: {email}\n"
                        msg += f"📋 Tiêu đề: {subject[:50]}{'...' if len(subject) > 50 else ''}\n"
                        msg += f"🕐 Nhận lúc: {mail_time}\n"
                        msg += f"⏰ Mã có hiệu lực trong vài phút"
                        
                        # Delete loading message and send result
                        try:
                            bot.delete_message(user_id, loading_msg.message_id)
                        except:
                            pass
                        bot.send_message(user_id, msg, reply_markup=keyboard, parse_mode="Markdown")
                        otp_found = True
                        break
            
            if not otp_found:
                # Show latest email content (by timestamp)
                latest = sorted_emails[0]
                timestamp = latest.get('timestamp', 0)
                from datetime import datetime
                mail_time = datetime.fromtimestamp(timestamp / 1000).strftime('%H:%M:%S %d/%m/%Y') if timestamp else "N/A"
                msg = f"📬 Email mới nhất ({mail_time}):\n\nTừ: {latest.get('from', 'Unknown')}\nTiêu đề: {latest.get('subject', 'No Subject')}\n\n{TempMailClient.clean_html(latest.get('textBody', ''))[:500]}"
                # Delete loading message
                try:
                    bot.delete_message(user_id, loading_msg.message_id)
                except:
                    pass
                bot.send_message(user_id, msg, reply_markup=keyboard)
        else:
            # Delete loading message
            try:
                bot.delete_message(user_id, loading_msg.message_id)
            except:
                pass
            bot.send_message(user_id, "📭 Chưa có email mới. Vui lòng yêu cầu mã xác thực trên Canva rồi bấm lại nút.", reply_markup=keyboard)
            
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error getting OTP: {e}")
        try:
            bot.delete_message(user_id, loading_msg.message_id)
        except:
            pass
        if e.response and e.response.status_code == 404:
            msg = f"⚠️ Hộp thư *{email}* đã hết hạn hoặc không tồn tại trên TempMail.\n\n"
            msg += "📌 Email tạm thời thường hết hạn sau 24-48 giờ.\n"
            msg += "💬 Vui lòng liên hệ @dlndai để được hỗ trợ cấp tài khoản mới."
            bot.send_message(user_id, msg, reply_markup=keyboard, parse_mode="Markdown")
        else:
            bot.send_message(user_id, f"❌ Lỗi kết nối: {str(e)}", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error getting OTP: {e}")
        try:
            bot.delete_message(user_id, loading_msg.message_id)
        except:
            pass
        error_str = str(e)
        if "404" in error_str or "Not Found" in error_str:
            msg = f"⚠️ Hộp thư *{email}* đã hết hạn hoặc không tồn tại trên TempMail.\n\n"
            msg += "📌 Email tạm thời thường hết hạn sau 24-48 giờ.\n"
            msg += "💬 Vui lòng liên hệ @dlndai để được hỗ trợ cấp tài khoản mới."
            bot.send_message(user_id, msg, reply_markup=keyboard, parse_mode="Markdown")
        else:
            bot.send_message(user_id, f"❌ Lỗi khi lấy mã: {error_str}", reply_markup=keyboard)

# Check if message is a category button (📁 CategoryName)
def is_category_button(text):
    return text.startswith("📁 ")

# Check if message is a buy button (🛒 Mua (quantity))
def is_buy_button(text):
    return text.startswith("🛒 Mua (") and text.endswith(")")

# Check if message is warranty type button
def is_warranty_button(text):
    return text in ["🛡 Mua BH 3 tháng", "⚡ Mua KBH", "🛡 BH 3 tháng", "⚡ KBH"]

# Check if message is upgrade canva button
def is_upgrade_button(text):
    return text == "♻️ Up lại Canva Edu"

# Check if message is slot canva button
def is_slot_button(text):
    return text == "🎫 Slot Canva Edu"

# Check if message is upgrade warranty button (for Up lại Canva Edu)
def is_upgrade_warranty_button(text):
    return text in ["🛡 BH 3 tháng - 250K", "⚡ KBH - 100K"]

# Check if message is product selection button (from /buy menu)
def is_product_selection_button(text):
    return text in ["🛍 Canva Edu Admin", "♻️ Up lại Canva Edu", "🎫 Slot Canva Edu", f"🆕 {get_new_product_name()}"]

# Store reply keyboard message_id for each user to delete and resend
# Format: {user_id: {"chat_id": chat_id, "message_id": message_id}}
pending_reply_keyboard_messages = {}

# Rate limit for user actions (anti-spam)
# Format: {user_id: last_action_timestamp}
user_action_timestamps = {}
ACTION_COOLDOWN = 1.0  # Minimum seconds between actions

def check_rate_limit(user_id):
    """Check if user is rate limited. Returns True if allowed, False if spam."""
    current_time = time.time()
    last_action = user_action_timestamps.get(user_id, 0)
    
    if current_time - last_action < ACTION_COOLDOWN:
        return False  # Too fast, rate limited
    
    user_action_timestamps[user_id] = current_time
    return True  # Allowed

# Helper function to initialize reply keyboard message (first time, no delete)
def init_reply_keyboard(user_id, reply_markup):
    """Send reply keyboard message and save message_id (for first time)"""
    reply_msg = bot.send_message(user_id, "Hoặc bấm chọn ở menu bàn phím 👇", reply_markup=reply_markup)
    pending_reply_keyboard_messages[user_id] = {"chat_id": user_id, "message_id": reply_msg.message_id}
    logger.info(f"Init reply keyboard message: user_id={user_id}, message_id={reply_msg.message_id}")

# Helper function to update reply keyboard message
def update_reply_keyboard(user_id, reply_markup):
    """Delete old reply keyboard message and send new one"""
    # Delete old message if exists
    if user_id in pending_reply_keyboard_messages:
        try:
            msg_info = pending_reply_keyboard_messages[user_id]
            logger.info(f"Deleting reply keyboard message: chat_id={msg_info['chat_id']}, message_id={msg_info['message_id']}")
            bot.delete_message(msg_info["chat_id"], msg_info["message_id"])
            logger.info(f"Deleted successfully")
        except Exception as e:
            logger.error(f"Failed to delete reply keyboard message: {e}")
    else:
        logger.info(f"No pending reply keyboard message for user {user_id}")
    # Send new message with reply keyboard
    reply_msg = bot.send_message(user_id, "Hoặc bấm chọn ở menu bàn phím 👇", reply_markup=reply_markup)
    pending_reply_keyboard_messages[user_id] = {"chat_id": user_id, "message_id": reply_msg.message_id}
    logger.info(f"Saved new reply keyboard message: user_id={user_id}, message_id={reply_msg.message_id}")

# Show Canva Edu Admin product details
def show_canva_product_details(user_id, lang, chat_id=None, message_id=None):
    """Show Canva Edu Admin product with warranty options"""
    
    inline_kb = types.InlineKeyboardMarkup(row_width=2)
    inline_kb.row(
        types.InlineKeyboardButton(text="🛡 BH 3 tháng", callback_data="warranty_bh3"),
        types.InlineKeyboardButton(text="⚡ KBH", callback_data="warranty_kbh")
    )
    inline_kb.row(
        types.InlineKeyboardButton(text="⬅️ Quay lại", callback_data="back_to_products")
    )
    
    cfg = get_price_config()
    bh3 = cfg["canva_bh3"]
    kbh = cfg["canva_kbh"]
    price_tiers = "💰 <b>Bảng giá:</b>\n"
    price_tiers += f"• KBH: {format_price_vnd(kbh['tier1'])}/1 | ≥10: {format_price_vnd(kbh['tier10'])} | ≥50: {format_price_vnd(kbh['tier50'])}\n"
    price_tiers += f"• BH 3 tháng: {format_price_vnd(bh3['tier1'])}/1 | ≥10: {format_price_vnd(bh3['tier10'])} | ≥50: {format_price_vnd(bh3['tier50'])}"
    
    msg = f"🛍 <b>CANVA EDU ADMIN</b>\n\n🎓 Full quyền 500 slot – hạn 3 năm\n\n{price_tiers}\n\n👇 Chọn loại bảo hành:"
    
    # Edit inline message
    if chat_id and message_id:
        try:
            bot.edit_message_text(msg, chat_id, message_id, reply_markup=inline_kb, parse_mode='HTML')
        except:
            bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
    else:
        bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
    
    # Update reply keyboard
    nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    nav_keyboard.row(
        types.KeyboardButton(text="🛡 BH 3 tháng"),
        types.KeyboardButton(text="⚡ KBH")
    )
    nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
    update_reply_keyboard(user_id, nav_keyboard)

# Show Up lại Canva Edu product details
def show_upgrade_product_details(user_id, lang, chat_id=None, message_id=None):
    """Show Up lại Canva Edu product with warranty options"""
    cfg = get_price_config()
    upgrade_kbh_price = format_price_vnd(cfg['upgrade_kbh'])
    upgrade_bh3_price = format_price_vnd(cfg['upgrade_bh3'])
    
    inline_kb = types.InlineKeyboardMarkup(row_width=1)
    inline_kb.row(
        types.InlineKeyboardButton(text=f"🛡 BH 3 tháng - {upgrade_bh3_price}", callback_data="upgrade_bh3")
    )
    inline_kb.row(
        types.InlineKeyboardButton(text=f"⚡ KBH - {upgrade_kbh_price}", callback_data="upgrade_kbh")
    )
    inline_kb.row(
        types.InlineKeyboardButton(text="⬅️ Quay lại", callback_data="back_to_products")
    )
    
    msg = "♻️ <b>UP LẠI CANVA EDU ADMIN</b>\n"
    msg += "━━━━━━━━━━━━━━\n"
    msg += "<i>Dành cho tài khoản bị mất gói - giữ nguyên đội nhóm/team</i>\n\n"
    msg += "💰 <b>Bảng giá:</b>\n"
    msg += f"• KBH: {upgrade_kbh_price}\n"
    msg += f"• BH 3 tháng: {upgrade_bh3_price}\n\n"
    msg += "📝 <b>Lưu ý:</b> Sau khi thanh toán thành công, vui lòng inbox Admin:\n"
    msg += "• Mã đơn hàng\n"
    msg += "• Tài khoản Canva\n"
    msg += "• Mật khẩu (nếu có)\n"
    msg += "• Cung cấp mã xác thực khi Admin yêu cầu\n\n"
    msg += "👇 Chọn loại bảo hành:"
    
    # Edit inline message
    if chat_id and message_id:
        try:
            bot.edit_message_text(msg, chat_id, message_id, reply_markup=inline_kb, parse_mode='HTML')
        except:
            bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
    else:
        bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
    
    # Update reply keyboard
    nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    nav_keyboard.row(
        types.KeyboardButton(text=f"🛡 BH 3 tháng - {upgrade_bh3_price}"),
        types.KeyboardButton(text=f"⚡ KBH - {upgrade_kbh_price}")
    )
    nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
    update_reply_keyboard(user_id, nav_keyboard)

# Show Slot Canva Edu product details - ask for email directly
def show_slot_product_details(user_id, lang, chat_id=None, message_id=None):
    """Show Slot Canva Edu product and ask for email (1 slot = 5K)"""
    inline_kb = types.InlineKeyboardMarkup()
    inline_kb.add(types.InlineKeyboardButton(text="❌ Hủy", callback_data="cancel_slot_email"))
    
    cfg = get_price_config()
    slot_p = format_price_vnd(cfg['slot_price'])
    msg = "🎫 <b>SLOT CANVA EDU</b>\n"
    msg += "━━━━━━━━━━━━━━\n"
    msg += "<i>Thêm thành viên vào team Canva Edu</i>\n\n"
    msg += f"💰 <b>Giá:</b> {slot_p} (KBH)\n\n"
    msg += "📧 <b>Vui lòng gửi email tài khoản Canva cần thêm slot:</b>"
    
    # Edit inline message or send new one
    sent_msg = None
    if chat_id and message_id:
        try:
            bot.edit_message_text(msg, chat_id, message_id, reply_markup=inline_kb, parse_mode='HTML')
            sent_msg = message_id
        except:
            result = bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
            sent_msg = result.message_id
    else:
        result = bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
        sent_msg = result.message_id
    
    # Save state waiting for email (default 1 slot) with message_id to delete later
    pending_slot_email_state[user_id] = {
        "quantity": 1,
        "username": "",  # Will be filled when processing
        "message_id": sent_msg
    }
    
    # Update reply keyboard
    nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    nav_keyboard.add(types.KeyboardButton(text="❌ Hủy mua slot"))
    nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
    update_reply_keyboard(user_id, nav_keyboard)

# Show New Product details (YouTube Premium with package selection)
def show_new_product_details(user_id, lang, chat_id=None, message_id=None):
    """Show new product details with package options for YouTube Premium"""
    product_name = get_new_product_name()
    packages = get_new_product_packages()

    inline_kb = types.InlineKeyboardMarkup(row_width=2)
    # Package selection buttons in 2 columns
    inline_kb.row(
        types.InlineKeyboardButton(text=f"📦 {packages['1m']['name']} - {format_price_vnd(packages['1m']['price'])}", callback_data="new_product_pkg_1m"),
        types.InlineKeyboardButton(text=f"📦 {packages['3m']['name']} - {format_price_vnd(packages['3m']['price'])}", callback_data="new_product_pkg_3m")
    )
    inline_kb.row(
        types.InlineKeyboardButton(text=f"📦 {packages['6m']['name']} - {format_price_vnd(packages['6m']['price'])}", callback_data="new_product_pkg_6m"),
        types.InlineKeyboardButton(text=f"📦 {packages['1y']['name']} - {format_price_vnd(packages['1y']['price'])}", callback_data="new_product_pkg_1y")
    )
    inline_kb.row(types.InlineKeyboardButton(text="⬅️ Quay lại", callback_data="back_to_products"))

    msg = f"🆕 <b>{product_name.upper()}</b>\n"
    msg += "━━━━━━━━━━━━━━\n"
    msg += f"📺 <i>Slot {product_name} - Dùng chung gia đình (Family)</i>\n\n"
    msg += f"📋 <b>Các gói hiện có:</b>\n"
    for key in ["1m", "3m", "6m", "1y"]:
        pkg = packages[key]
        msg += f"  • <b>{pkg['name']}</b>: {format_price_vnd(pkg['price'])}\n"
    msg += f"\n⚠️ Yêu cầu: Email Google (Gmail)\n"
    msg += "👇 Chọn gói bạn muốn mua:" 

    if chat_id and message_id:
        try:
            bot.edit_message_text(msg, chat_id, message_id, reply_markup=inline_kb, parse_mode='HTML')
        except:
            bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
    else:
        bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')

    nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
    update_reply_keyboard(user_id, nav_keyboard)

# Show quantity selection for warranty type
def show_quantity_selection(user_id, warranty_type, lang, chat_id=None, message_id=None):
    """Show quantity selection buttons for selected warranty type"""
    warranty_label = "BH 3 tháng" if warranty_type == "bh3" else "KBH"
    
    inline_kb = types.InlineKeyboardMarkup(row_width=2)
    inline_kb.row(
        types.InlineKeyboardButton(text="🛒 Mua (1)", callback_data=f"buy_qty_1_{warranty_type}"),
        types.InlineKeyboardButton(text="🛒 Mua (2)", callback_data=f"buy_qty_2_{warranty_type}")
    )
    inline_kb.row(
        types.InlineKeyboardButton(text="🛒 Mua (3)", callback_data=f"buy_qty_3_{warranty_type}"),
        types.InlineKeyboardButton(text="🛒 Mua (5)", callback_data=f"buy_qty_5_{warranty_type}")
    )
    inline_kb.row(
        types.InlineKeyboardButton(text="🛒 Mua (10)", callback_data=f"buy_qty_10_{warranty_type}"),
        types.InlineKeyboardButton(text="🛒 Mua (20)", callback_data=f"buy_qty_20_{warranty_type}")
    )
    inline_kb.row(
        types.InlineKeyboardButton(text="🛒 Mua (50)", callback_data=f"buy_qty_50_{warranty_type}"),
        types.InlineKeyboardButton(text="🛒 Mua (100)", callback_data=f"buy_qty_100_{warranty_type}")
    )
    inline_kb.row(
        types.InlineKeyboardButton(text="⬅️ Quay lại", callback_data="back_to_canva")
    )
    
    # Get price info for this warranty type (dynamic)
    cfg = get_price_config()
    if warranty_type == "bh3":
        t = cfg["canva_bh3"]
        price_info = f"💰 Bảng giá BH 3 tháng:\n• 1-9 acc: {format_price_vnd(t['tier1'])}/acc\n• ≥10 acc: {format_price_vnd(t['tier10'])}/acc\n• ≥50 acc: {format_price_vnd(t['tier50'])}/acc"
    else:
        t = cfg["canva_kbh"]
        price_info = f"💰 Bảng giá KBH:\n• 1-9 acc: {format_price_vnd(t['tier1'])}/acc\n• ≥10 acc: {format_price_vnd(t['tier10'])}/acc\n• ≥50 acc: {format_price_vnd(t['tier50'])}/acc"
    
    msg = f"🛡 <b>Đã chọn: {warranty_label}</b>\n\n{price_info}\n\n👇 Chọn số lượng muốn mua:"
    
    # Edit inline message
    if chat_id and message_id:
        try:
            bot.edit_message_text(msg, chat_id, message_id, reply_markup=inline_kb, parse_mode='HTML')
        except:
            bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
    else:
        bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
    
    # Update reply keyboard - show quantity buttons
    nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    nav_keyboard.row(
        types.KeyboardButton(text="🛒 Mua (1)"),
        types.KeyboardButton(text="🛒 Mua (5)")
    )
    nav_keyboard.row(
        types.KeyboardButton(text="🛒 Mua (10)"),
        types.KeyboardButton(text="🛒 Mua (50)")
    )
    nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
    update_reply_keyboard(user_id, nav_keyboard)

# Show upgrade canva options
def show_upgrade_canva_options(user_id, lang):
    """Show warranty options for 'Up lại Canva Edu' service"""
    cfg = get_price_config()
    upgrade_kbh_price = format_price_vnd(cfg['upgrade_kbh'])
    upgrade_bh3_price = format_price_vnd(cfg['upgrade_bh3'])
    
    inline_kb = types.InlineKeyboardMarkup(row_width=1)
    inline_kb.row(
        types.InlineKeyboardButton(text=f"🛡 BH 3 tháng - {upgrade_bh3_price}", callback_data="upgrade_bh3")
    )
    inline_kb.row(
        types.InlineKeyboardButton(text=f"⚡ KBH - {upgrade_kbh_price}", callback_data="upgrade_kbh")
    )
    inline_kb.row(
        types.InlineKeyboardButton(text="⬅️ Quay lại", callback_data="back_to_warranty")
    )
    
    msg = "♻️ <b>UP LẠI CANVA EDU ADMIN</b>\n"
    msg += "━━━━━━━━━━━━━━\n"
    msg += "<i>Dành cho tài khoản bị mất gói - giữ nguyên đội nhóm/team</i>\n\n"
    msg += "💰 <b>Bảng giá:</b>\n"
    msg += f"• KBH: {upgrade_kbh_price}\n"
    msg += f"• BH 3 tháng: {upgrade_bh3_price}\n\n"
    msg += "📝 <b>Lưu ý:</b> Sau khi thanh toán thành công, vui lòng inbox Admin:\n"
    msg += "• Mã đơn hàng\n"
    msg += "• Tài khoản Canva\n"
    msg += "• Mật khẩu (nếu có)\n"
    msg += "• Cung cấp mã xác thực khi Admin yêu cầu\n\n"
    msg += "👇 Chọn loại bảo hành:"
    bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')

# Process upgrade canva order
def process_upgrade_canva_order(user_id, username, warranty_type, lang):
    """Process 'Up lại Canva Edu' order"""
    price = calculate_upgrade_price(warranty_type)
    warranty_label = "BH 3 tháng" if warranty_type == "bh3" else "KBH"
    product_name = f"Up lại Canva Edu ({warranty_label})"
    
    # Get bank config
    bank_cfg = get_bank_config()
    if not bank_cfg["bank_code"] or not bank_cfg["account_number"]:
        bot.send_message(user_id, get_text("bank_not_setup", lang), reply_markup=create_main_keyboard(lang, user_id))
        return
    
    # Send loading photo first
    loading_img = "https://files.catbox.moe/yicj8r.jpg"
    try:
        loading_msg = bot.send_photo(user_id, loading_img, caption="⏳ Đang xử lý...")
    except Exception as e:
        logger.warning(f"Failed to send loading photo: {e}")
        loading_msg = bot.send_message(user_id, "⏳ Đang xử lý...")
    
    try:
        ordernumber = random.randint(10000, 99999)
        transfer_content = f"UP{ordernumber}"
        
        now = datetime.now(VN_TIMEZONE)
        orderdate = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # Save to pending_orders_info
        pending_orders_info[ordernumber] = {
            "user_id": user_id,
            "username": username,
            "product_name": product_name,
            "price": price,
            "quantity": 1,
            "product_number": 0,  # 0 = UPGRADE product
            "orderdate": orderdate,
            "download_link": "",
            "transfer_content": transfer_content,
            "is_upgrade": True,
            "warranty_type": warranty_type
        }
        
        # Notify admin about new pending order
        admins = GetDataFromDB.GetAdminIDsInDB() or []
        admin_msg_ids = []
        for admin in admins:
            try:
                admin_msg = f"♻️ *Đơn UP LẠI CANVA đang chờ thanh toán*\n"
                admin_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
                admin_msg += f"👤 Khách: @{username}\n"
                admin_msg += f"📦 Sản phẩm: {product_name}\n"
                admin_msg += f"💰 Số tiền: {price:,} VND\n"
                admin_msg += f"⏳ Trạng thái: _Chờ chuyển khoản_\n"
                admin_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                admin_msg += f"📝 _Sau khi thanh toán, khách sẽ inbox thông tin tài khoản Canva_"
                sent = bot.send_message(admin[0], admin_msg, parse_mode="Markdown")
                admin_msg_ids.append({"chat_id": admin[0], "message_id": sent.message_id})
            except:
                pass
        pending_admin_messages[ordernumber] = admin_msg_ids
        
        # Try PayOS first
        payos_result = create_payos_payment_link(ordernumber, price, transfer_content, username)
        
        if payos_result and payos_result.get("accountNumber"):
            checkout_url = payos_result.get("checkoutUrl", "")
            payos_account = payos_result.get("accountNumber", "")
            payos_name = payos_result.get("accountName", "")
            payos_bin = payos_result.get("bin", "")
            
            import urllib.parse
            qr_url = f"https://img.vietqr.io/image/{payos_bin}-{payos_account}-compact2.png"
            params = {
                "amount": int(price),
                "addInfo": transfer_content,
                "accountName": payos_name
            }
            qr_url = f"{qr_url}?{urllib.parse.urlencode(params)}"
            
            msg = f"📱 <b>QUÉT MÃ QR ĐỂ THANH TOÁN</b>\n\n"
            msg += f"🏦 Ngân hàng: <b>MB Bank</b>\n"
            msg += f"💳 Số TK: <code>{payos_account}</code>\n"
            msg += f"👤 Chủ TK: <b>{payos_name}</b>\n"
            msg += f"💰 Số tiền: <b>{price:,} VND</b>\n"
            msg += f"📝 Nội dung: <code>{transfer_content}</code>\n\n"
            msg += f"⏳ Mã đơn hàng: <code>{ordernumber}</code>\n\n"
            msg += f"━━━━━━━━━━━━━━\n"
            msg += f"📌 <b>SAU KHI THANH TOÁN THÀNH CÔNG:</b>\n"
            msg += f"Vui lòng inbox Admin kèm:\n"
            msg += f"• Mã đơn hàng: <code>{ordernumber}</code>\n"
            msg += f"• Tài khoản Canva của bạn\n"
            msg += f"• Mật khẩu (nếu có)\n"
            msg += f"• Cung cấp mã xác thực khi Admin yêu cầu"
        else:
            qr_url = generate_vietqr_url(
                bank_cfg["bank_code"],
                bank_cfg["account_number"],
                bank_cfg["account_name"],
                price,
                transfer_content
            )
            msg = f"📱 <b>QUÉT MÃ QR ĐỂ THANH TOÁN</b>\n\n"
            msg += f"🏦 Ngân hàng: <b>{bank_cfg['bank_code']}</b>\n"
            msg += f"💳 Số TK: <code>{bank_cfg['account_number']}</code>\n"
            msg += f"👤 Chủ TK: <b>{bank_cfg['account_name']}</b>\n"
            msg += f"💰 Số tiền: <b>{price:,} VND</b>\n"
            msg += f"📝 Nội dung: <code>{transfer_content}</code>\n\n"
            msg += f"⏳ Mã đơn hàng: <code>{ordernumber}</code>\n\n"
            msg += f"━━━━━━━━━━━━━━\n"
            msg += f"📌 <b>SAU KHI THANH TOÁN THÀNH CÔNG:</b>\n"
            msg += f"Vui lòng inbox Admin kèm:\n"
            msg += f"• Mã đơn hàng: <code>{ordernumber}</code>\n"
            msg += f"• Tài khoản Canva của bạn\n"
            msg += f"• Mật khẩu (nếu có)\n"
            msg += f"• Cung cấp mã xác thực khi Admin yêu cầu"
        
        inline_kb = types.InlineKeyboardMarkup()
        inline_kb.add(types.InlineKeyboardButton(
            text=get_text("cancel_order", lang),
            callback_data=f"cancel_order_{ordernumber}"
        ))
        
        try:
            media = types.InputMediaPhoto(qr_url, caption=msg, parse_mode='HTML')
            bot.edit_message_media(media, chat_id=user_id, message_id=loading_msg.message_id, reply_markup=inline_kb)
            pending_qr_messages[ordernumber] = {"chat_id": user_id, "message_id": loading_msg.message_id}
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            bot.send_photo(user_id, qr_url, caption=msg, reply_markup=inline_kb, parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"Error processing upgrade order: {e}")
        bot.send_message(user_id, f"❌ Lỗi: {e}", reply_markup=create_main_keyboard(lang, user_id))

# Process slot order
def process_slot_order(user_id, username, quantity, lang, canva_email):
    """Process 'Slot Canva Edu' order with customer's Canva email"""
    unit_price, total_price = calculate_slot_price(quantity)
    product_name = f"Slot Canva Edu x{quantity}"
    
    # Get bank config
    bank_cfg = get_bank_config()
    if not bank_cfg["bank_code"] or not bank_cfg["account_number"]:
        bot.send_message(user_id, get_text("bank_not_setup", lang), reply_markup=create_main_keyboard(lang, user_id))
        return
    
    # Send loading photo first
    loading_img = "https://files.catbox.moe/yicj8r.jpg"
    try:
        loading_msg = bot.send_photo(user_id, loading_img, caption="⏳ Đang xử lý...")
    except Exception as e:
        logger.warning(f"Failed to send loading photo: {e}")
        loading_msg = bot.send_message(user_id, "⏳ Đang xử lý...")
    
    try:
        ordernumber = random.randint(10000, 99999)
        transfer_content = f"SLOT{ordernumber}"
        
        now = datetime.now(VN_TIMEZONE)
        orderdate = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # Save to pending_orders_info with canva_email
        pending_orders_info[ordernumber] = {
            "user_id": user_id,
            "username": username,
            "product_name": product_name,
            "price": total_price,
            "quantity": quantity,
            "product_number": -1,  # -1 = SLOT product
            "orderdate": orderdate,
            "download_link": "",
            "transfer_content": transfer_content,
            "is_slot": True,
            "canva_email": canva_email
        }
        
        # Notify admin about new pending order with email info
        admins = GetDataFromDB.GetAdminIDsInDB() or []
        admin_msg_ids = []
        for admin in admins:
            try:
                admin_msg = f"🎫 *Đơn SLOT CANVA đang chờ thanh toán*\n"
                admin_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
                admin_msg += f"👤 Khách: @{username}\n"
                admin_msg += f"📦 Sản phẩm: {product_name}\n"
                admin_msg += f"📧 Email Canva: `{canva_email}`\n"
                admin_msg += f"💰 Số tiền: {total_price:,} VND\n"
                admin_msg += f"⏳ Trạng thái: _Chờ chuyển khoản_"
                sent = bot.send_message(admin[0], admin_msg, parse_mode="Markdown")
                admin_msg_ids.append({"chat_id": admin[0], "message_id": sent.message_id})
            except:
                pass
        pending_admin_messages[ordernumber] = admin_msg_ids
        
        # Try PayOS first
        payos_result = create_payos_payment_link(ordernumber, total_price, transfer_content, username)
        
        if payos_result and payos_result.get("accountNumber"):
            checkout_url = payos_result.get("checkoutUrl", "")
            payos_account = payos_result.get("accountNumber", "")
            payos_name = payos_result.get("accountName", "")
            payos_bin = payos_result.get("bin", "")
            
            import urllib.parse
            qr_url = f"https://img.vietqr.io/image/{payos_bin}-{payos_account}-compact2.png"
            params = {
                "amount": int(total_price),
                "addInfo": transfer_content,
                "accountName": payos_name
            }
            qr_url = f"{qr_url}?{urllib.parse.urlencode(params)}"
            
            msg = f"📱 <b>QUÉT MÃ QR ĐỂ THANH TOÁN</b>\n\n"
            msg += f"🏦 Ngân hàng: <b>MB Bank</b>\n"
            msg += f"💳 Số TK: <code>{payos_account}</code>\n"
            msg += f"👤 Chủ TK: <b>{payos_name}</b>\n"
            msg += f"💰 Số tiền: <b>{total_price:,} VND</b>\n"
            msg += f"📝 Nội dung: <code>{transfer_content}</code>\n\n"
            msg += f"⏳ Mã đơn hàng: <code>{ordernumber}</code>\n"
            msg += f"📧 Email Canva: <code>{canva_email}</code>"
        else:
            qr_url = generate_vietqr_url(
                bank_cfg["bank_code"],
                bank_cfg["account_number"],
                bank_cfg["account_name"],
                total_price,
                transfer_content
            )
            msg = f"📱 <b>QUÉT MÃ QR ĐỂ THANH TOÁN</b>\n\n"
            msg += f"🏦 Ngân hàng: <b>{bank_cfg['bank_code']}</b>\n"
            msg += f"💳 Số TK: <code>{bank_cfg['account_number']}</code>\n"
            msg += f"👤 Chủ TK: <b>{bank_cfg['account_name']}</b>\n"
            msg += f"💰 Số tiền: <b>{total_price:,} VND</b>\n"
            msg += f"📝 Nội dung: <code>{transfer_content}</code>\n\n"
            msg += f"⏳ Mã đơn hàng: <code>{ordernumber}</code>\n"
            msg += f"📧 Email Canva: <code>{canva_email}</code>"
        
        inline_kb = types.InlineKeyboardMarkup()
        inline_kb.add(types.InlineKeyboardButton(
            text=get_text("cancel_order", lang),
            callback_data=f"cancel_order_{ordernumber}"
        ))
        
        try:
            media = types.InputMediaPhoto(qr_url, caption=msg, parse_mode='HTML')
            bot.edit_message_media(media, chat_id=user_id, message_id=loading_msg.message_id, reply_markup=inline_kb)
            pending_qr_messages[ordernumber] = {"chat_id": user_id, "message_id": loading_msg.message_id}
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            bot.send_photo(user_id, qr_url, caption=msg, reply_markup=inline_kb, parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"Error processing slot order: {e}")
        bot.send_message(user_id, f"❌ Lỗi: {e}", reply_markup=create_main_keyboard(lang, user_id))

# Process new product order (YouTube Premium - manual fulfillment)
def process_new_product_order(user_id, username, lang, package_type="1m", google_email=""):
    """Process new product order with package-based pricing"""
    packages = get_new_product_packages()
    pkg = packages.get(package_type)
    if not pkg:
        bot.send_message(user_id, "❌ Gói không hợp lệ!", reply_markup=create_main_keyboard(lang, user_id))
        return
    
    price = pkg["price"]
    package_label = pkg["name"]
    product_name = get_new_product_name()
    display_name = f"{product_name} ({package_label})"

    # Get bank config
    bank_cfg = get_bank_config()
    if not bank_cfg["bank_code"] or not bank_cfg["account_number"]:
        bot.send_message(user_id, get_text("bank_not_setup", lang), reply_markup=create_main_keyboard(lang, user_id))
        return

    # Send loading photo first
    loading_img = "https://files.catbox.moe/yicj8r.jpg"
    try:
        loading_msg = bot.send_photo(user_id, loading_img, caption="⏳ Đang xử lý...")
    except Exception as e:
        logger.warning(f"Failed to send loading photo: {e}")
        loading_msg = bot.send_message(user_id, "⏳ Đang xử lý...")

    try:
        ordernumber = random.randint(10000, 99999)
        transfer_content = f"YTP{ordernumber}"

        now = datetime.now(VN_TIMEZONE)
        orderdate = now.strftime("%Y-%m-%d %H:%M:%S")

        pending_orders_info[ordernumber] = {
            "user_id": user_id,
            "username": username,
            "product_name": display_name,
            "price": price,
            "quantity": 1,
            "product_number": -2,
            "orderdate": orderdate,
            "download_link": "",
            "transfer_content": transfer_content,
            "is_custom": True,
            "custom_type": "new_product",
            "package_type": package_type,
            "package_label": package_label,
            "google_email": google_email
        }

        admins = GetDataFromDB.GetAdminIDsInDB() or []
        admin_msg_ids = []
        for admin in admins:
            try:
                admin_msg = f"🆕 *Đơn {product_name} đang chờ thanh toán*\n"
                admin_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
                admin_msg += f"👤 Khách: @{username}\n"
                admin_msg += f"📦 Sản phẩm: {product_name}\n"
                admin_msg += f"📋 Gói: *{package_label}*\n"
                admin_msg += f"📧 Email: `{google_email}`\n"
                admin_msg += f"💰 Số tiền: {price:,} VND\n"
                admin_msg += f"⏳ Trạng thái: _Chờ chuyển khoản_"
                sent = bot.send_message(admin[0], admin_msg, parse_mode="Markdown")
                admin_msg_ids.append({"chat_id": admin[0], "message_id": sent.message_id})
            except:
                pass
        pending_admin_messages[ordernumber] = admin_msg_ids

        payos_result = create_payos_payment_link(ordernumber, price, transfer_content, username)

        if payos_result and payos_result.get("accountNumber"):
            payos_account = payos_result.get("accountNumber", "")
            payos_name = payos_result.get("accountName", "")
            payos_bin = payos_result.get("bin", "")

            import urllib.parse
            qr_url = f"https://img.vietqr.io/image/{payos_bin}-{payos_account}-compact2.png"
            params = {
                "amount": int(price),
                "addInfo": transfer_content,
                "accountName": payos_name
            }
            qr_url = f"{qr_url}?{urllib.parse.urlencode(params)}"

            msg = f"📱 <b>QUÉT MÃ QR ĐỂ THANH TOÁN</b>\n\n"
            msg += f"📦 Sản phẩm: <b>{product_name} - {package_label}</b>\n"
            msg += f"📧 Email: <code>{google_email}</code>\n"
            msg += f"🏦 Ngân hàng: <b>MB Bank</b>\n"
            msg += f"💳 Số TK: <code>{payos_account}</code>\n"
            msg += f"👤 Chủ TK: <b>{payos_name}</b>\n"
            msg += f"💰 Số tiền: <b>{price:,} VND</b>\n"
            msg += f"📝 Nội dung: <code>{transfer_content}</code>\n\n"
            msg += f"⏳ Mã đơn hàng: <code>{ordernumber}</code>\n"
            msg += f"<i>Sau khi chuyển, hệ thống sẽ tự xác nhận</i>"
        else:
            qr_url = generate_vietqr_url(
                bank_cfg["bank_code"],
                bank_cfg["account_number"],
                bank_cfg["account_name"],
                price,
                transfer_content
            )
            msg = get_text("scan_qr_transfer", lang,
                bank_cfg["bank_code"],
                bank_cfg["account_number"],
                bank_cfg["account_name"],
                price,
                transfer_content,
                ordernumber
            )

        inline_kb = types.InlineKeyboardMarkup()
        inline_kb.add(types.InlineKeyboardButton(
            text=get_text("cancel_order", lang),
            callback_data=f"cancel_order_{ordernumber}"
        ))

        try:
            media = types.InputMediaPhoto(qr_url, caption=msg, parse_mode='HTML')
            bot.edit_message_media(media, chat_id=user_id, message_id=loading_msg.message_id, reply_markup=inline_kb)
            pending_qr_messages[ordernumber] = {"chat_id": user_id, "message_id": loading_msg.message_id}
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            bot.send_photo(user_id, qr_url, caption=msg, reply_markup=inline_kb, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error processing new product order: {e}")
        bot.send_message(user_id, f"❌ Lỗi: {e}", reply_markup=create_main_keyboard(lang, user_id))

# Handler for buy button with quantity
@bot.message_handler(content_types=["text"], func=lambda message: is_buy_button(message.text))
def handle_buy_with_quantity(message, warranty_type="kbh"):
    """Handle buy button press with quantity"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return

    if not sales_enabled and not is_admin(id):
        bot.send_message(id, "❌ *Hiện đang tạm ngưng bán tất cả sản phẩm!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
        return
    
    username = message.from_user.username or "user"
    
    # Extract quantity from button text: "🛒 Mua (5)" -> 5
    try:
        qty_str = message.text.replace("🛒 Mua (", "").replace(")", "")
        quantity = int(qty_str)
    except:
        quantity = 1
    
    # Get first product (Canva Edu Admin)
    products_list = GetDataFromDB.GetProductInfo()
    if products_list:
        productnumber, pname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory = products_list[0]
        
        # Create order data with quantity (manual fulfillment - no stock check needed)
        order_data = [productnumber, pname, productprice, productdescription, productimagelink, productdownloadlink, 9999, productcategory]
        # Process bank transfer with quantity and warranty type
        process_bank_transfer_order(id, username, order_data, lang, quantity, warranty_type)
    else:
        bot.send_message(id, "Không có sản phẩm!", reply_markup=create_main_keyboard(lang, id))

# Handler for warranty type button
@bot.message_handler(content_types=["text"], func=lambda message: is_warranty_button(message.text))
def handle_warranty_button(message):
    """Handle warranty type button press"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return

    if not sales_enabled and not is_admin(id):
        bot.send_message(id, "❌ *Hiện đang tạm ngưng bán tất cả sản phẩm!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
        return
    
    # Check rate limit
    if not check_rate_limit(id):
        return
    
    if message.text in ["🛡 Mua BH 3 tháng", "🛡 BH 3 tháng"]:
        show_quantity_selection(id, "bh3", lang)
    else:  # "⚡ Mua KBH" or "⚡ KBH"
        show_quantity_selection(id, "kbh", lang)

# Handler for upgrade canva button
@bot.message_handler(content_types=["text"], func=lambda message: is_upgrade_button(message.text))
def handle_upgrade_button(message):
    """Handle upgrade canva button press"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return

    if not sales_enabled and not is_admin(id):
        bot.send_message(id, "❌ *Hiện đang tạm ngưng bán tất cả sản phẩm!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
        return
    
    # Check rate limit
    if not check_rate_limit(id):
        return
    
    # Check if upgrade product is enabled
    if not upgrade_product_enabled:
        bot.send_message(id, "❌ *Sản phẩm này tạm thời không khả dụng!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
        return
    
    show_upgrade_canva_options(id, lang)

# Handler for slot canva button
@bot.message_handler(content_types=["text"], func=lambda message: is_slot_button(message.text))
def handle_slot_button(message):
    """Handle slot canva button press - ask for email directly"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return

    if not sales_enabled and not is_admin(id):
        bot.send_message(id, "❌ *Hiện đang tạm ngưng bán tất cả sản phẩm!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
        return
    
    # Check rate limit
    if not check_rate_limit(id):
        return
    
    # Set username in state
    pending_slot_email_state[id] = {
        "quantity": 1,
        "username": message.from_user.username or "user"
    }
    
    show_slot_product_details(id, lang)

# Check if user is in new product email input state
def is_waiting_new_product_email(user_id, text=""):
    if user_id not in pending_new_product_email:
        return False
    # Allow special buttons to pass through
    pass_through_buttons = ["🏠 Trang chủ", "🛍 Đơn hàng", "📞 Hỗ trợ"]
    if text in pass_through_buttons or text.startswith("/"):
        del pending_new_product_email[user_id]
        return False
    # Allow cancel
    if "Hủy" in text:
        return True
    return True

# Handler for new product email input (YouTube Premium)
@bot.message_handler(content_types=["text"], func=lambda message: is_waiting_new_product_email(message.from_user.id, message.text))
def handle_new_product_email_input(message):
    """Handle Google email input for YouTube Premium purchase"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    state = pending_new_product_email.get(user_id)
    if not state:
        return
    
    # Check cancel
    if "Hủy" in message.text:
        del pending_new_product_email[user_id]
        bot.send_message(user_id, f"❌ Đã hủy mua {get_new_product_name()}.", reply_markup=create_main_keyboard(lang, user_id))
        return
    
    # Validate email
    import re
    email = message.text.strip().lower()
    email_pattern = r'^[\w.+-]+@[\w-]+\.[\w.-]+$'
    
    if not re.match(email_pattern, email):
        bot.send_message(user_id, "❌ Email không hợp lệ!\n\n📩 Vui lòng nhập đúng định dạng email:\n💡 Ví dụ: `example@gmail.com`", parse_mode="Markdown")
        return
    
    # Email valid - proceed to payment
    package_type = state["package_type"]
    username = state["username"]
    del pending_new_product_email[user_id]
    
    process_new_product_order(user_id, username, lang, package_type, email)

# Check if admin is in canva delivery input state
def is_waiting_canva_delivery(user_id, text=""):
    if user_id not in pending_canva_delivery:
        return False
    # Allow special buttons to pass through
    if text.startswith("/") or text == "🏠 Trang chủ":
        del pending_canva_delivery[user_id]
        return False
    return True

# Handler for admin canva delivery input
@bot.message_handler(content_types=["text"], func=lambda message: is_waiting_canva_delivery(message.from_user.id, message.text))
def handle_canva_delivery_input(message):
    """Handle admin input for Canva Edu delivery (2-step: account details -> OTP link)"""
    admin_id = message.from_user.id
    lang = get_user_lang(admin_id)
    
    if not is_admin(admin_id):
        return
    
    delivery_info = pending_canva_delivery.get(admin_id)
    if not delivery_info:
        return
    
    # Check cancel
    if "Hủy" in message.text:
        del pending_canva_delivery[admin_id]
        bot.send_message(admin_id, "❌ Đã hủy giao hàng.", reply_markup=create_main_keyboard(lang, admin_id))
        return
    
    current_step = delivery_info.get("step", "account")
    ordernumber = delivery_info["ordernumber"]
    buyer_user_id = delivery_info["buyer_user_id"]
    admin_msg_chat_id = delivery_info["admin_msg_chat_id"]
    admin_msg_id = delivery_info["admin_msg_id"]
    
    # ===== STEP 1: Admin enters account details (emails only) =====
    if current_step == "account":
        account_details = message.text.strip()
        delivery_info["account_details"] = account_details
        
        # Extract ALL emails from account details
        import re
        email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'
        emails_found = re.findall(email_pattern, account_details)
        
        if not emails_found:
            bot.send_message(admin_id, "❌ Không tìm thấy email nào! Vui lòng nhập lại.", reply_markup=types.ReplyKeyboardRemove())
            return
        
        # Check which emails support auto OTP
        from tempmail_client import EmailWorkerClient
        supported_emails = []
        unsupported_emails = []
        
        for email in emails_found:
            if EmailWorkerClient.is_worker_email(email):
                supported_emails.append(email)
            else:
                unsupported_emails.append(email)
        
        delivery_info["supported_emails"] = supported_emails
        delivery_info["unsupported_emails"] = unsupported_emails
        delivery_info["emails_found"] = emails_found
        
        # Move to password step
        delivery_info["step"] = "password"
        pending_canva_delivery[admin_id] = delivery_info
        
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row(types.KeyboardButton(text="🔑 Mật khẩu mặc định"))
        keyboard.row(types.KeyboardButton(text="⏩ Không có mật khẩu"))
        keyboard.row(types.KeyboardButton(text="❌ Hủy giao hàng"))
        
        prompt_msg = f"🔐 *NHẬP MẬT KHẨU*\n"
        prompt_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        prompt_msg += f"Đã tìm thấy {len(emails_found)} email:\n"
        for email in emails_found:
            prompt_msg += f"• `{email}`\n"
        prompt_msg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        prompt_msg += f"Chọn hoặc nhập mật khẩu:\n\n"
        prompt_msg += f"🔑 *Mật khẩu mặc định:* `dlndaicanvaedu`\n"
        prompt_msg += f"⏩ *Không có mật khẩu*\n"
        prompt_msg += f"✍️ *Hoặc nhập mật khẩu tùy chỉnh*"
        
        bot.send_message(admin_id, prompt_msg, reply_markup=keyboard, parse_mode="Markdown")
        return
    
    # ===== STEP 2: Admin enters password =====
    if current_step == "password":
        if message.text == "🔑 Mật khẩu mặc định":
            delivery_info["password"] = "dlndaicanvaedu"
        elif message.text == "⏩ Không có mật khẩu":
            delivery_info["password"] = None
        else:
            delivery_info["password"] = message.text.strip()
        
        # Check if has unsupported emails -> ask for OTP link
        unsupported_emails = delivery_info.get("unsupported_emails", [])
        
        if unsupported_emails:
            # Has unsupported emails -> ask admin for OTP website
            delivery_info["step"] = "otp_link"
            pending_canva_delivery[admin_id] = delivery_info
            
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.row(types.KeyboardButton(text="⏩ Bỏ qua"))
            keyboard.row(types.KeyboardButton(text="❌ Hủy giao hàng"))
            
            warn_msg = f"⚠️ Các email sau không hỗ trợ lấy OTP tự động:\n"
            for email in unsupported_emails:
                warn_msg += f"• `{email}`\n"
            warn_msg += "\n"
            
            prompt_msg = f"🔗 *NHẬP LINK LẤY MÃ XÁC THỰC*\n"
            prompt_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            prompt_msg += warn_msg
            prompt_msg += f"Nhập link trang web để khách tự lấy mã xác thực (OTP):\n\n"
            prompt_msg += f"💡 Ví dụ:\n"
            prompt_msg += f"`https://mail.google.com`\n"
            prompt_msg += f"`https://outlook.live.com`\n\n"
            prompt_msg += f"Hoặc bấm ⏩ Bỏ qua nếu không cần."
            
            bot.send_message(admin_id, prompt_msg, reply_markup=keyboard, parse_mode="Markdown")
        else:
            # All emails support auto OTP -> deliver immediately
            delivery_info["otp_link"] = None
            _complete_canva_delivery(admin_id, delivery_info)
        return
    
    # ===== STEP 3: Admin enters OTP link =====
    if current_step == "otp_link":
        if message.text.strip() == "⏩ Bỏ qua":
            delivery_info["otp_link"] = None
        else:
            delivery_info["otp_link"] = message.text.strip()
        
        _complete_canva_delivery(admin_id, delivery_info)
        return


def _complete_canva_delivery(admin_id, delivery_info):
    """Complete the Canva Edu delivery: send account info to buyer, update admin message."""
    lang = get_user_lang(admin_id)
    ordernumber = delivery_info["ordernumber"]
    buyer_user_id = delivery_info["buyer_user_id"]
    admin_msg_chat_id = delivery_info["admin_msg_chat_id"]
    admin_msg_id = delivery_info["admin_msg_id"]
    account_details = delivery_info["account_details"]
    password = delivery_info.get("password")
    otp_link = delivery_info.get("otp_link")
    emails_found = delivery_info.get("emails_found", [])
    warranty_type = delivery_info.get("warranty_type", "kbh")
    
    # Build buyer message with emails and password
    buyer_msg = f"🎉 *THÔNG BÁO TỪ ADMIN*\n"
    buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    buyer_msg += f"✅ Đơn hàng `{ordernumber}` đã được xử lý xong!\n\n"
    buyer_msg += f"📦 *THÔNG TIN TÀI KHOẢN:*\n"
    buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    
    # Display each email with password
    for i, email in enumerate(emails_found, 1):
        buyer_msg += f"\n🔑 *Tài khoản {i if len(emails_found) > 1 else ''}:*\n"
        buyer_msg += f"{email}\n"
        if password:
            buyer_msg += f"🔐 Mật khẩu: `{password}`\n"
    
    buyer_msg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    
    # Add OTP instructions based on email type
    from tempmail_client import EmailWorkerClient
    supported_emails = delivery_info.get("supported_emails", [])
    
    if supported_emails:
        buyer_msg += f"🔑 Lấy mã xác thực: Bấm nút *🔑 Lấy OTP* bên dưới\n"
    if otp_link:
        buyer_msg += f"🔑 Lấy mã xác thực tại: {otp_link}\n"
    
    buyer_msg += f"Cảm ơn bạn đã sử dụng dịch vụ! 💚"
    buyer_msg += f"✅ Đơn hàng `{ordernumber}` đã được xử lý xong!\n\n"
    buyer_msg += f"📦 *THÔNG TIN TÀI KHOẢN:*\n"
    buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    buyer_msg += f"`{account_details}`\n"
    buyer_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    
    # Add OTP instructions based on email type
    from tempmail_client import EmailWorkerClient
    if otp_email and EmailWorkerClient.is_worker_email(otp_email):
        buyer_msg += f"🔑 Lấy mã xác thực: Bấm nút *🔑 Lấy mã xác thực* bên dưới\n"
    elif otp_link:
        buyer_msg += f"🔑 Lấy mã xác thực tại: {otp_link}\n"
    
    # KBH: yêu cầu đổi mật khẩu VÀ thay đổi email tài khoản
    # BH3T: chỉ yêu cầu đổi mật khẩu
    if warranty_type == "kbh":
        buyer_msg += f"⚠️ Vui lòng đổi mật khẩu và thay đổi email tài khoản ngay sau khi nhận!\n"
    else:
        buyer_msg += f"⚠️ Vui lòng đổi mật khẩu ngay sau khi nhận!\n"
    buyer_msg += f"Cảm ơn bạn đã sử dụng dịch vụ! 💚"
    
    try:
        # Get supported and unsupported emails
        supported_emails = delivery_info.get("supported_emails", [])
        unsupported_emails = delivery_info.get("unsupported_emails", [])
        
        # Send with inline OTP buttons for supported emails
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        has_otp_buttons = False
        
        for email in supported_emails:
            btn_text = f"🔑 Lấy OTP: {email[:20]}..." if len(email) > 20 else f"🔑 Lấy OTP: {email}"
            inline_kb.add(types.InlineKeyboardButton(text=btn_text, callback_data=f"otp_{email}"))
            has_otp_buttons = True
        
        if has_otp_buttons:
            bot.send_message(buyer_user_id, buyer_msg, reply_markup=inline_kb, parse_mode="Markdown")
        else:
            bot.send_message(buyer_user_id, buyer_msg, parse_mode="Markdown")
        
        # Send reply keyboard to buyer
        otp_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        if has_otp_buttons:
            otp_keyboard.row(types.KeyboardButton(text="🔑 Lấy mã xác thực"))
        otp_keyboard.row(types.KeyboardButton(text="🛍 Đơn hàng"), types.KeyboardButton(text="📞 Hỗ trợ"))
        otp_keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
        bot.send_message(buyer_user_id, "👆 Thông tin tài khoản của bạn ở trên.", reply_markup=otp_keyboard)
        
        delivery_success = True
    except Exception as e:
        logger.error(f"Error sending delivery to buyer {buyer_user_id}: {e}")
        bot.send_message(admin_id, f"⚠️ Không thể gửi tin nhắn cho khách (ID: {buyer_user_id}). Khách có thể đã block bot.")
        delivery_success = False
    
    # Edit admin order message to mark as done
    try:
        done_msg = f"✅ *ĐÃ GIAO HÀNG XONG*\n━━━━━━━━━━━━━━\n🆔 Mã đơn: `{ordernumber}`\n👤 Khách: ID `{buyer_user_id}`\n📦 Đã gửi:\n`{account_details}`"
        if otp_link:
            done_msg += f"\n🔗 Link OTP: {otp_link}"
        bot.edit_message_text(done_msg, admin_msg_chat_id, admin_msg_id, parse_mode="Markdown")
    except:
        pass
    
    # Confirm to admin
    if delivery_success:
        confirm_msg = f"✅ Đã giao hàng cho khách (Đơn `{ordernumber}`)!\n\nThông tin đã gửi:\n`{account_details}`"
        if otp_link:
            confirm_msg += f"\n🔗 Link OTP: {otp_link}"
        bot.send_message(admin_id, confirm_msg, reply_markup=create_main_keyboard(lang, admin_id), parse_mode="Markdown")
    else:
        bot.send_message(admin_id, f"⚠️ Đơn `{ordernumber}` - Không gửi được cho khách. Hãy liên hệ trực tiếp.", reply_markup=create_main_keyboard(lang, admin_id), parse_mode="Markdown")
    
    # Cleanup
    if admin_id in pending_canva_delivery:
        del pending_canva_delivery[admin_id]

# Check if user is in slot email input state (exclude special buttons)
def is_waiting_slot_email(user_id, text=""):
    if user_id not in pending_slot_email_state:
        return False
    # Allow special buttons to pass through to other handlers
    pass_through_buttons = ["🏠 Trang chủ", "🛍 Đơn hàng", "📞 Hỗ trợ"]
    # Also allow cancel button
    if text in pass_through_buttons or text.startswith("/") or "Hủy" in text:
        # Clear state so user can use other features
        del pending_slot_email_state[user_id]
        return False
    return True

# Handler for slot email input
@bot.message_handler(content_types=["text"], func=lambda message: is_waiting_slot_email(message.from_user.id, message.text))
def handle_slot_email_input(message):
    """Handle email input for slot order"""
    id = message.from_user.id
    lang = get_user_lang(id)

    if not sales_enabled and not is_admin(id):
        bot.send_message(id, "❌ *Hiện đang tạm ngưng bán tất cả sản phẩm!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
        return
    
    # Check if user wants to cancel (button text contains "Hủy")
    if "Hủy" in message.text or "hủy" in message.text:
        if id in pending_slot_email_state:
            del pending_slot_email_state[id]
        bot.send_message(id, "❌ Đã hủy mua slot!", reply_markup=create_main_keyboard(lang, id))
        return
    
    email = message.text.strip().lower()
    
    # Validate email
    if '@' not in email or '.' not in email:
        bot.send_message(id, "❌ Email không hợp lệ!\n\n📧 Vui lòng nhập lại email Canva:")
        return
    
    # Get saved state
    state = pending_slot_email_state.get(id)
    if not state:
        bot.send_message(id, "❌ Phiên đã hết hạn. Vui lòng thử lại!", reply_markup=create_main_keyboard(lang, id))
        return
    
    quantity = state["quantity"]
    username = state["username"]
    
    # Clear state
    del pending_slot_email_state[id]
    
    # Process order with email
    process_slot_order(id, username, quantity, lang, email)

# Handler for upgrade warranty button (BH 3 tháng - 250K / KBH - 100K)
@bot.message_handler(content_types=["text"], func=lambda message: is_upgrade_warranty_button(message.text))
def handle_upgrade_warranty_button(message):
    """Handle upgrade warranty button press from reply keyboard"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return

    if not sales_enabled and not is_admin(id):
        bot.send_message(id, "❌ *Hiện đang tạm ngưng bán tất cả sản phẩm!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
        return
    
    username = message.from_user.username or "user"
    
    # Check if upgrade product is enabled
    if not upgrade_product_enabled:
        bot.send_message(id, "❌ *Sản phẩm này tạm thời không khả dụng!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
        return
    
    if message.text == "🛡 BH 3 tháng - 250K":
        process_upgrade_canva_order(id, username, "bh3", lang)
    else:  # "⚡ KBH - 100K"
        process_upgrade_canva_order(id, username, "kbh", lang)

# Handler for product selection button (from /buy menu)
@bot.message_handler(content_types=["text"], func=lambda message: is_product_selection_button(message.text))
def handle_product_selection_button(message):
    """Handle product selection button press from /buy menu"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return

    if not sales_enabled and not is_admin(id):
        bot.send_message(id, "❌ *Hiện đang tạm ngưng bán tất cả sản phẩm!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
        return
    
    # Check rate limit
    if not check_rate_limit(id):
        return
    
    if message.text == "🛍 Canva Edu Admin":
        if not canva_product_enabled and not is_admin(id):
            bot.send_message(id, "❌ *Sản phẩm này tạm thời không khả dụng!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
            return
        show_canva_product_details(id, lang)
    elif message.text == "🎫 Slot Canva Edu":
        if not slot_product_enabled and not is_admin(id):
            bot.send_message(id, "❌ *Sản phẩm này tạm thời không khả dụng!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
            return
        show_slot_product_details(id, lang)
    elif message.text == f"🆕 {get_new_product_name()}":
        if not new_product_enabled and not is_admin(id):
            bot.send_message(id, "❌ *Sản phẩm này tạm thời không khả dụng!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
            return
        show_new_product_details(id, lang)
    else:  # "♻️ Up lại Canva Edu"
        # Check if upgrade product is enabled
        if not upgrade_product_enabled and not is_admin(id):
            bot.send_message(id, "❌ *Sản phẩm này tạm thời không khả dụng!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
            return
        show_upgrade_product_details(id, lang)

@bot.message_handler(content_types=["text"], func=lambda message: message.text == f"❌ Hủy mua {get_new_product_name()}")
def handle_cancel_new_product(message):
    """Handle cancel for new product email input"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if id in pending_new_product_email:
        del pending_new_product_email[id]
    
    bot.send_message(id, f"❌ Đã hủy mua {get_new_product_name()}.", reply_markup=create_main_keyboard(lang, id))

#Command handler and fucntion to shop Items
@bot.message_handler(commands=['buy'])
@bot.message_handler(content_types=["text"], func=lambda message: is_shop_items_button(message.text))
def shop_items_handler(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(user_id):
        bot.send_message(user_id, "🔧 *BOT ĐANG BẢO TRÌ*\n\nVui lòng quay lại sau!", parse_mode='Markdown')
        return

    if not sales_enabled and not is_admin(user_id):
        bot.send_message(user_id, "❌ *Hiện đang tạm ngưng bán tất cả sản phẩm!*\n\nVui lòng quay lại sau.", reply_markup=create_main_keyboard(lang, user_id), parse_mode='Markdown')
        return
    
    # Check rate limit
    if not check_rate_limit(user_id):
        return
    
    display_name = get_user_display_name(message)
    if not is_admin(user_id):
        notify_admin("🛒 Xem sản phẩm", display_name)
    
    lang = get_user_lang(user_id)
    products_list = GetDataFromDB.GetProductInfo()
    
    if products_list == [] or products_list is None:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
        bot.send_message(user_id, get_text("no_product_store", lang), reply_markup=keyboard)
    else:
        cfg = get_price_config()
        packages = get_new_product_packages()
        product_name = get_new_product_name()
        is_adm = is_admin(user_id)
        
        # Build compact price list (only show enabled products)
        msg = "🛒 <b>BẢNG GIÁ SẢN PHẨM</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        
        has_products = False
        
        if canva_product_enabled or is_adm:
            msg += "🛍 <b>Canva Edu Admin</b>\n"
            msg += f"   BH3: {format_price_vnd(cfg['canva_bh3']['tier1'])} • KBH: {format_price_vnd(cfg['canva_kbh']['tier1'])}\n\n"
            has_products = True
        
        if slot_product_enabled or is_adm:
            msg += "🎫 <b>Slot Canva Edu</b>\n"
            msg += f"   {format_price_vnd(cfg['slot_price'])}/slot\n\n"
            has_products = True
        
        if new_product_enabled or is_adm:
            msg += f"🆕 <b>{product_name}</b>\n"
            pkg_prices = " • ".join([f"{packages[k]['name']}: {format_price_vnd(packages[k]['price'])}" for k in ["1m", "3m", "6m", "1y"]])
            msg += f"   {pkg_prices}\n"
            has_products = True
        
        if upgrade_product_enabled or is_adm:
            if has_products and not msg.endswith("\n\n"):
                msg += "\n"
            msg += "♻️ <b>Up lại Canva Edu</b>\n"
            msg += f"   BH3: {format_price_vnd(cfg['upgrade_bh3'])} • KBH: {format_price_vnd(cfg['upgrade_kbh'])}\n"
            has_products = True
        
        if not has_products:
            bot.send_message(user_id, "❌ Hiện không có sản phẩm nào đang bán.\nVui lòng quay lại sau!", reply_markup=create_main_keyboard(lang, user_id))
            return
        
        msg += "\n━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>👇 Chọn sản phẩm:</b>"
        
        # Inline keyboard (only show enabled products)
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        if canva_product_enabled or is_adm:
            inline_kb.row(types.InlineKeyboardButton(text="🛍 Canva Edu Admin", callback_data="product_canva"))
        if slot_product_enabled or is_adm:
            inline_kb.row(types.InlineKeyboardButton(text="🎫 Slot Canva Edu", callback_data="product_slot"))
        if new_product_enabled or is_adm:
            inline_kb.row(types.InlineKeyboardButton(text=f"🆕 {get_new_product_name()}", callback_data="product_new"))
        if upgrade_product_enabled or is_adm:
            inline_kb.row(types.InlineKeyboardButton(text="♻️ Up lại Canva Edu", callback_data="product_upgrade"))
        
        # Reply keyboard (only show enabled products)
        nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        row1 = []
        if canva_product_enabled or is_adm:
            row1.append(types.KeyboardButton(text="🛍 Canva Edu Admin"))
        if slot_product_enabled or is_adm:
            row1.append(types.KeyboardButton(text="🎫 Slot Canva Edu"))
        if row1:
            nav_keyboard.row(*row1)
        if new_product_enabled or is_adm:
            nav_keyboard.row(types.KeyboardButton(text=f"🆕 {get_new_product_name()}"))
        if upgrade_product_enabled or is_adm:
            nav_keyboard.row(types.KeyboardButton(text="♻️ Up lại Canva Edu"))
        nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
        
        # Gửi message với inline keyboard
        bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
        # Gửi message với reply keyboard và lưu message_id
        init_reply_keyboard(user_id, nav_keyboard)

# Command shortcuts
@bot.message_handler(commands=['menu'])
def menu_command(message):
    """Redirect to start/home"""
    send_welcome(message)

@bot.message_handler(commands=['orders'])
def orders_command(message):
    """Show user orders"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return
    
    # Trigger the orders handler
    message.text = get_text("my_orders", lang)
    MyOrdersList(message)

@bot.message_handler(commands=['support'])
def support_command(message):
    """Show support info"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return
    
    support_msg = "💬 *Hỗ trợ*\n━━━━━━━━━━━━━━━━━━━━\n"
    support_msg += "📞 Liên hệ: @dlndai\n"
    support_msg += "⏰ Hỗ trợ 24/7\n"
    support_msg += "━━━━━━━━━━━━━━━━━━━━\n"
    support_msg += "_Gửi tin nhắn trực tiếp để được hỗ trợ_"
    bot.send_message(id, support_msg, parse_mode="Markdown", reply_markup=create_main_keyboard(lang, id))

@bot.message_handler(commands=['help'])
def help_command(message):
    """Show help/commands info"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return
    
    help_msg = "📖 *HƯỚNG DẪN SỬ DỤNG BOT*\n"
    help_msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    help_msg += "📌 *Các lệnh có sẵn:*\n"
    help_msg += "/start - Khởi động bot\n"
    help_msg += "/menu - Về trang chủ\n"
    help_msg += "/buy - Mua hàng\n"
    help_msg += "/orders - Xem đơn hàng\n"
    help_msg += "/support - Liên hệ hỗ trợ\n"
    help_msg += "/help - Xem hướng dẫn này\n\n"
    help_msg += "━━━━━━━━━━━━━━━━━━━━\n"
    help_msg += "👇 Hoặc bấm nút bên dưới để thao tác"
    bot.send_message(id, help_msg, parse_mode="Markdown", reply_markup=create_main_keyboard(lang, id))


@bot.message_handler(commands=['myid'])
def myid_command(message):
    """Show user's ID and send to admin for assignment"""
    id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name or "User"
    lang = get_user_lang(id)
    
    # Send confirmation to user
    user_msg = f"✅ *ĐÃ GỬI THÔNG TIN CHO ADMIN!*\n"
    user_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    user_msg += f"🔢 User ID của bạn: `{id}`\n"
    user_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    user_msg += f"_Admin sẽ liên hệ bạn sớm nhất_"
    
    bot.send_message(id, user_msg, parse_mode="Markdown", reply_markup=create_main_keyboard(lang, id))
    
    # Send to admin with inline button to assign directly
    admin_msg = f"📩 *YÊU CẦU GÁN TÀI KHOẢN*\n"
    admin_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    admin_msg += f"👤 Tên: {first_name}\n"
    if username:
        admin_msg += f"📛 Username: @{username}\n"
    admin_msg += f"🔢 User ID: `{id}`\n"
    admin_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    admin_msg += f"_Nhấn nút bên dưới để gán tài khoản_"
    
    inline_kb = types.InlineKeyboardMarkup(row_width=1)
    inline_kb.add(types.InlineKeyboardButton(text=f"🎁 Gán tài khoản cho {id}", callback_data=f"quick_assign_{id}"))
    
    # Send to all admins
    admins = GetDataFromDB.GetAdminIDsInDB() or []
    for admin in admins:
        try:
            bot.send_message(admin[0], admin_msg, parse_mode="Markdown", reply_markup=inline_kb)
        except:
            pass


# Store pending QR message IDs to delete after payment confirmed
pending_qr_messages = {}
# Store pending order quantities
pending_order_quantities = {}
# Store admin notification message IDs to edit later
pending_admin_messages = {}
# Store pending order info (not saved to DB until payment confirmed)
# Format: {ordernumber: {user_id, username, product_name, price, quantity, product_number, orderdate}}
pending_orders_info = {}
# Rate limit for OTP requests
# otp_request_count: user_id -> number of requests
# otp_rate_limit: user_id -> timestamp when limit expires
OTP_MAX_REQUESTS = 5  # Max requests before rate limit
OTP_LIMIT_DURATION = 900  # 15 minutes in seconds
otp_request_count = {}
otp_rate_limit = {}

# Bank account settings (loaded from database or env)
BANK_CONFIG = {
    "bank_code": os.getenv("BANK_CODE", "MB"),
    "account_number": os.getenv("BANK_ACCOUNT", "11116666008888"),
    "account_name": os.getenv("BANK_ACCOUNT_NAME", os.getenv("BANK_NAME", "DINH LE NGOC DAI"))
}

def get_bank_config():
    """Get bank config from database or env"""
    try:
        bank_data = GetDataFromDB.GetPaymentMethodsAll("BankTransfer")
        if bank_data:
            for method_name, token_keys, secret_keys in bank_data:
                if token_keys and secret_keys:
                    parts = token_keys.split("|")
                    if len(parts) >= 2:
                        return {
                            "bank_code": parts[0],
                            "account_number": parts[1],
                            "account_name": secret_keys
                        }
    except:
        pass
    return BANK_CONFIG

def generate_vietqr_url(bank_code, account_number, account_name, amount, content):
    """Generate VietQR image URL"""
    # Using VietQR API (free)
    # Format: https://img.vietqr.io/image/{bank_code}-{account_number}-compact2.png?amount={amount}&addInfo={content}&accountName={name}
    import urllib.parse
    base_url = f"https://img.vietqr.io/image/{bank_code}-{account_number}-compact2.png"
    params = {
        "amount": int(amount),
        "addInfo": content,
        "accountName": account_name
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"

def create_payos_payment_link(ordernumber, amount, description, buyer_name, cancel_url=None, return_url=None):
    """Create PayOS payment link via API"""
    if not PAYOS_CLIENT_ID or not PAYOS_API_KEY or not PAYOS_CHECKSUM_KEY:
        logger.warning("PayOS credentials not configured")
        return None
    
    try:
        import hashlib
        import hmac
        
        # PayOS API endpoint
        api_url = "https://api-merchant.payos.vn/v2/payment-requests"
        
        # Prepare data
        data = {
            "orderCode": int(ordernumber),
            "amount": int(amount),
            "description": description[:25],  # Max 25 chars
            "cancelUrl": cancel_url or webhook_url,
            "returnUrl": return_url or webhook_url,
            "buyerName": buyer_name[:50] if buyer_name else "Khách hàng"
        }
        
        # Create signature: amount + cancelUrl + description + orderCode + returnUrl
        signature_data = f"amount={data['amount']}&cancelUrl={data['cancelUrl']}&description={data['description']}&orderCode={data['orderCode']}&returnUrl={data['returnUrl']}"
        signature = hmac.new(PAYOS_CHECKSUM_KEY.encode(), signature_data.encode(), hashlib.sha256).hexdigest()
        data["signature"] = signature
        
        headers = {
            "Content-Type": "application/json",
            "x-client-id": PAYOS_CLIENT_ID,
            "x-api-key": PAYOS_API_KEY
        }
        
        logger.info(f"PayOS request: {data}")
        response = requests.post(api_url, json=data, headers=headers, timeout=30)
        result = response.json()
        logger.info(f"PayOS response: {result}")
        
        if result.get("code") == "00":
            payment_data = result.get("data", {})
            return {
                "checkoutUrl": payment_data.get("checkoutUrl"),
                "qrCode": payment_data.get("qrCode"),
                "paymentLinkId": payment_data.get("paymentLinkId"),
                "accountNumber": payment_data.get("accountNumber"),
                "accountName": payment_data.get("accountName"),
                "bin": payment_data.get("bin")
            }
        else:
            logger.error(f"PayOS API error: {result}")
            return None
            
    except Exception as e:
        logger.error(f"PayOS create payment error: {e}")
        return None

def cancel_payos_payment(ordernumber, reason="User cancelled"):
    """Cancel PayOS payment link via API"""
    if not PAYOS_CLIENT_ID or not PAYOS_API_KEY:
        return False
    
    try:
        api_url = f"https://api-merchant.payos.vn/v2/payment-requests/{ordernumber}/cancel"
        
        headers = {
            "Content-Type": "application/json",
            "x-client-id": PAYOS_CLIENT_ID,
            "x-api-key": PAYOS_API_KEY
        }
        
        data = {"cancellationReason": reason[:50]}
        
        response = requests.post(api_url, json=data, headers=headers, timeout=10)
        result = response.json()
        
        if result.get("code") == "00":
            logger.info(f"PayOS: Cancelled order {ordernumber}")
            return True
        else:
            logger.warning(f"PayOS cancel failed: {result}")
            return False
            
    except Exception as e:
        logger.error(f"PayOS cancel error: {e}")
        return False

# Helper function to parse price (handles "40k", "100k", "1.5m", etc.)
def parse_price(price_str):
    """Parse price string like '40k', '100k', '1.5m' to integer"""
    price_str = str(price_str).lower().strip().replace(',', '').replace('.', '')
    
    multiplier = 1
    if price_str.endswith('k'):
        multiplier = 1000
        price_str = price_str[:-1]
    elif price_str.endswith('m'):
        multiplier = 1000000
        price_str = price_str[:-1]
    
    try:
        return int(float(price_str) * multiplier)
    except:
        return 0


# Pricing tiers - uses dynamic price config from price_config.json
# Admin can adjust prices via "💰 Điều chỉnh giá" menu

def calculate_price_by_quantity(quantity, warranty_type="kbh"):
    """Calculate unit price based on quantity tiers and warranty type
    warranty_type: "bh3" (bảo hành 3 tháng) or "kbh" (không bảo hành)
    Uses dynamic price config.
    
    Returns: (unit_price, total_price)
    """
    cfg = get_price_config()
    tier_key = "canva_bh3" if warranty_type == "bh3" else "canva_kbh"
    tiers = cfg[tier_key]
    
    if quantity >= 50:
        unit_price = tiers["tier50"]
    elif quantity >= 10:
        unit_price = tiers["tier10"]
    else:
        unit_price = tiers["tier1"]
    
    total_price = unit_price * quantity
    return unit_price, total_price


def calculate_upgrade_price(warranty_type="kbh"):
    """Calculate price for 'Up lại Canva Edu Admin' service
    Uses dynamic price config.
    
    Returns: price
    """
    cfg = get_price_config()
    if warranty_type == "bh3":
        return cfg["upgrade_bh3"]
    else:  # kbh
        return cfg["upgrade_kbh"]


def calculate_slot_price(quantity):
    """Calculate price for 'Slot Canva Edu' service
    Uses dynamic price config.
    
    Returns: (unit_price, total_price)
    """
    cfg = get_price_config()
    unit_price = cfg["slot_price"]
    total_price = unit_price * quantity
    return unit_price, total_price


def get_price_tier_text():
    """Get price tier description for display - uses dynamic prices"""
    cfg = get_price_config()
    bh3 = cfg["canva_bh3"]
    kbh = cfg["canva_kbh"]
    text = "⚡ <b>CANVA EDU ADMIN</b> ⚡\n"
    text += "🎓 Full quyền 500 slot – hạn 3 năm\n\n"
    text += "💰 <b>Bảng giá:</b>\n"
    text += "━━━━━━━━━━━━━━\n"
    text += "🛡 <b>BH 3 tháng:</b>\n"
    text += f"• 1-9 acc: {format_price_vnd(bh3['tier1'])}/acc\n"
    text += f"• ≥10 acc: {format_price_vnd(bh3['tier10'])}/acc\n"
    text += f"• ≥50 acc: {format_price_vnd(bh3['tier50'])}/acc\n\n"
    text += "⚡ <b>KBH (Không bảo hành):</b>\n"
    text += f"• 1-9 acc: {format_price_vnd(kbh['tier1'])}/acc\n"
    text += f"• ≥10 acc: {format_price_vnd(kbh['tier10'])}/acc\n"
    text += f"• ≥50 acc: {format_price_vnd(kbh['tier50'])}/acc\n"
    text += "━━━━━━━━━━━━━━\n"
    text += "♻️ <b>UP LẠI CANVA EDU</b>\n"
    text += "<i>(bị mất gói - giữ nguyên đội nhóm/team)</i>\n"
    text += f"• KBH: {format_price_vnd(cfg['upgrade_kbh'])}\n"
    text += f"• BH 3 tháng: {format_price_vnd(cfg['upgrade_bh3'])}"
    return text


# Process bank transfer order (reusable function)
def process_bank_transfer_order(user_id, username, order_info, lang, quantity=1, warranty_type="kbh"):
    """Process bank transfer and show QR code (manual fulfillment by admin)"""
    
    # Get bank config
    bank_cfg = get_bank_config()
    if not bank_cfg["bank_code"] or not bank_cfg["account_number"]:
        bot.send_message(user_id, get_text("bank_not_setup", lang), reply_markup=create_main_keyboard(lang, user_id))
        return
    
    # Send loading photo first (so we can edit_message_media later)
    loading_img = "https://files.catbox.moe/yicj8r.jpg"
    try:
        loading_msg = bot.send_photo(user_id, loading_img, caption="⏳ Đang xử lý...")
    except Exception as e:
        logger.warning(f"Failed to send loading photo: {e}")
        loading_msg = bot.send_message(user_id, "⏳ Đang xử lý...")
    
    try:
        # Calculate price based on quantity tiers and warranty type
        unit_price, amount = calculate_price_by_quantity(quantity, warranty_type)
        ordernumber = random.randint(10000, 99999)
        transfer_content = f"DH{ordernumber}"
        
        # Store order info in memory (NOT in database yet - only save after payment confirmed)
        now = datetime.now(VN_TIMEZONE)
        orderdate = now.strftime("%Y-%m-%d %H:%M:%S")
        warranty_label = "BH3" if warranty_type == "bh3" else "KBH"
        product_name_with_qty = f"{order_info[1]} ({warranty_label}) x{quantity}" if quantity > 1 else f"{order_info[1]} ({warranty_label})"
        productdownloadlink = GetDataFromDB.GetProductDownloadLink(order_info[0])
        
        # Save to pending_orders_info instead of database
        pending_orders_info[ordernumber] = {
            "user_id": user_id,
            "username": username,
            "product_name": product_name_with_qty,
            "price": amount,
            "quantity": quantity,
            "product_number": order_info[0],
            "orderdate": orderdate,
            "download_link": productdownloadlink,
            "transfer_content": transfer_content,
            "warranty_type": warranty_type
        }
        
        # Store quantity for later use when confirming order
        pending_order_quantities[ordernumber] = quantity
        
        # Notify admin about new pending order
        admins = GetDataFromDB.GetAdminIDsInDB() or []
        admin_msg_ids = []
        for admin in admins:
            try:
                admin_msg = f"🛒 *Đơn hàng mới đang chờ thanh toán*\n"
                admin_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
                admin_msg += f"👤 Khách: @{username} (ID: `{user_id}`)\n"
                admin_msg += f"📦 Sản phẩm: {product_name_with_qty}\n"
                admin_msg += f"🛡 Loại: {'BH 3 tháng' if warranty_type == 'bh3' else 'Không bảo hành'}\n"
                admin_msg += f"💰 Số tiền: {amount:,} VND\n"
                admin_msg += f"⏳ Trạng thái: _Chờ chuyển khoản_"
                
                # Add button for admin to confirm payment manually (for VietQR)
                admin_inline_kb = types.InlineKeyboardMarkup()
                admin_inline_kb.add(types.InlineKeyboardButton(
                    text="✅ Đã nhận tiền - Giao hàng",
                    callback_data=f"confirm_payment_{ordernumber}"
                ))
                
                sent = bot.send_message(admin[0], admin_msg, reply_markup=admin_inline_kb, parse_mode="Markdown")
                admin_msg_ids.append({"chat_id": admin[0], "message_id": sent.message_id})
            except:
                pass
        # Save admin message IDs to edit later
        pending_admin_messages[ordernumber] = admin_msg_ids
        
        # Try PayOS first
        payos_result = create_payos_payment_link(ordernumber, amount, transfer_content, username)
        
        if payos_result and payos_result.get("accountNumber"):
            # PayOS trả về thông tin tài khoản ảo - dùng VietQR để tạo QR
            checkout_url = payos_result.get("checkoutUrl", "")
            payos_account = payos_result.get("accountNumber", "")
            payos_name = payos_result.get("accountName", "")
            payos_bin = payos_result.get("bin", "")  # Mã ngân hàng
            
            # Tạo QR từ VietQR API với thông tin PayOS
            import urllib.parse
            qr_url = f"https://img.vietqr.io/image/{payos_bin}-{payos_account}-compact2.png"
            params = {
                "amount": int(amount),
                "addInfo": transfer_content,
                "accountName": payos_name
            }
            qr_url = f"{qr_url}?{urllib.parse.urlencode(params)}"
            
            # Build message
            msg = f"📱 <b>QUÉT MÃ QR ĐỂ THANH TOÁN</b>\n\n"
            msg += f"🏦 Ngân hàng: <b>MB Bank</b>\n"
            msg += f"💳 Số TK: <code>{payos_account}</code>\n"
            msg += f"👤 Chủ TK: <b>{payos_name}</b>\n"
            msg += f"💰 Số tiền: <b>{amount:,} VND</b>\n"
            msg += f"📝 Nội dung: <code>{transfer_content}</code>\n\n"
            msg += f"⏳ Mã đơn hàng: <code>{ordernumber}</code>\n"
            msg += f"<i>Sau khi chuyển, hệ thống sẽ tự xác nhận</i>"
            
            logger.info(f"PayOS payment created for order {ordernumber}")
        else:
            # Fallback to VietQR với tài khoản cá nhân
            qr_url = generate_vietqr_url(
                bank_cfg["bank_code"],
                bank_cfg["account_number"],
                bank_cfg["account_name"],
                amount,
                transfer_content
            )
            checkout_url = ""
            msg = get_text("scan_qr_transfer", lang, 
                bank_cfg["bank_code"], 
                bank_cfg["account_number"], 
                bank_cfg["account_name"],
                amount, 
                transfer_content,
                ordernumber
            )
            logger.info(f"Using VietQR fallback for order {ordernumber}")
        
        # Inline keyboard with cancel button
        inline_kb = types.InlineKeyboardMarkup()
        inline_kb.add(types.InlineKeyboardButton(
            text=get_text("cancel_order", lang),
            callback_data=f"cancel_order_{ordernumber}"
        ))
        
        # Edit loading message to QR photo
        try:
            media = types.InputMediaPhoto(qr_url, caption=msg, parse_mode='HTML')
            bot.edit_message_media(media, chat_id=user_id, message_id=loading_msg.message_id, reply_markup=inline_kb)
            pending_qr_messages[ordernumber] = {"chat_id": user_id, "message_id": loading_msg.message_id}
        except Exception as edit_err:
            logger.warning(f"Edit media failed: {edit_err}, using fallback")
            try:
                bot.delete_message(user_id, loading_msg.message_id)
            except:
                pass
            try:
                sent_msg = bot.send_photo(user_id, qr_url, caption=msg, reply_markup=inline_kb, parse_mode='HTML')
                pending_qr_messages[ordernumber] = {"chat_id": user_id, "message_id": sent_msg.message_id}
            except:
                sent_msg = bot.send_message(user_id, msg, reply_markup=inline_kb, parse_mode='HTML')
                pending_qr_messages[ordernumber] = {"chat_id": user_id, "message_id": sent_msg.message_id}
                
    except Exception as e:
        logger.error(f"Bank transfer error: {e}")
        bot.send_message(user_id, get_text("error_404", lang), reply_markup=create_main_keyboard(lang, user_id))


# Check if message matches my orders button
def is_my_orders_button(text):
    # Exclude admin buttons
    admin_keywords = ["Quản lý", "Manage", "Danh sách", "List", "Delete", "Xóa"]
    if any(kw in text for kw in admin_keywords):
        return False
    keywords = ["My Orders", "Đơn hàng của tôi", "my orders", "đơn hàng của tôi", "Đơn hàng", "đơn hàng", "🛍 Đơn hàng"]
    return any(kw in text for kw in keywords)

#Command handler and function to List My Orders 🛍
@bot.message_handler(content_types=["text"], func=lambda message: is_my_orders_button(message.text))
def MyOrdersList(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return
    
    display_name = get_user_display_name(message)
    
    if not is_admin(id):
        notify_admin("📋 Xem đơn hàng", display_name)
    
    my_orders = GetDataFromDB.GetOrderIDs_Buyer(id)
    if my_orders is None or my_orders == [] or my_orders == "None":
        bot.send_message(id, get_text("no_order_completed", lang), reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
    else:
        for my_order in my_orders:
            order_details = GetDataFromDB.GetOrderDetails(my_order[0])
            if order_details is None:
                continue
            for buyerid, buyerusername, productname, productprice, orderdate, paidmethod, productdownloadlink, productkeys, buyercomment, ordernumber, productnumber in order_details:
                # Determine payment status
                if paidmethod == "PENDING":
                    status = "⏳ Trạng thái: Chưa thanh toán" if lang == "vi" else "⏳ Status: Pending"
                else:
                    status = "✅ Trạng thái: Đã thanh toán" if lang == "vi" else "✅ Status: Paid"
                # Format price as number for {:,} formatting
                try:
                    price_num = int(float(str(productprice).replace(',', '').replace('k', '000').replace('K', '000')))
                except:
                    price_num = productprice
                msg = get_text("order_info", lang, productname, ordernumber, orderdate, price_num, store_currency, status, productkeys)
                
                # Create inline buttons for each email in productkeys
                inline_kb = types.InlineKeyboardMarkup()
                if productkeys and productkeys != "NIL":
                    emails = [e.strip() for e in productkeys.replace('\n', ',').split(',') if '@' in e.strip()]
                    for email in emails:
                        inline_kb.add(types.InlineKeyboardButton(
                            text=f"🔑 Lấy OTP: {email[:20]}..." if len(email) > 20 else f"🔑 Lấy OTP: {email}",
                            callback_data=f"otp_{email}"
                        ))
                
                if inline_kb.keyboard:
                    bot.send_message(id, text=f"{msg}", reply_markup=inline_kb, parse_mode="Markdown")
                else:
                    bot.send_message(id, text=f"{msg}", parse_mode="Markdown")
        bot.send_message(id, get_text("list_completed", lang), reply_markup=create_main_keyboard(lang, id))

# Check if message matches support button
def is_support_button(text):
    keywords = ["Support", "Hỗ trợ", "support", "hỗ trợ", "📞 Hỗ trợ"]
    return any(kw in text for kw in keywords)

#Command handler and function to list Store Supports 📞
@bot.message_handler(content_types=["text"], func=lambda message: is_support_button(message.text))
def ContactSupport(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    # Check maintenance mode
    if maintenance_mode and not is_admin(id):
        send_maintenance_message(message)
        return
    
    display_name = get_user_display_name(message)
    support_username = os.getenv("SUPPORT_USERNAME", "dlndai")
    
    if not is_admin(id):
        notify_admin("📞 Xem hỗ trợ", display_name)
    
    # Create inline button to open chat with admin
    inline_kb = types.InlineKeyboardMarkup()
    inline_kb.add(types.InlineKeyboardButton(
        text="💬 Chat với Admin",
        url=f"https://t.me/{support_username}"
    ))
    
    bot.send_message(id, get_text("contact_us", lang, support_username), reply_markup=inline_kb, parse_mode='Markdown')

# Check if message matches news to users button
def is_news_to_users_button(text):
    keywords = ["News To Users", "Thông báo người dùng", "news to users", "thông báo người dùng"]
    return any(kw in text for kw in keywords)

#Command handler and functions to  Message All Store Users
@bot.message_handler(content_types=["text"], func=lambda message: is_news_to_users_button(message.text))
def MessageAllUsers(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        # Tạo keyboard với nút hủy
        cancel_kb = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        cancel_kb.add(types.KeyboardButton(text="❌ Hủy"))
        msg = bot.send_message(id, get_text("broadcast_message", lang), reply_markup=cancel_kb)
        bot.register_next_step_handler(msg, message_all_users)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
def message_all_users(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    
    if is_admin(id):
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboardadmin.row_width = 2
        try:
            key1 = types.KeyboardButton(text="Quản lý sản phẩm 💼")
            key2 = types.KeyboardButton(text="Quản lý đơn hàng 🛍")
            key4 = types.KeyboardButton(text="Gửi thông báo 📣")
            key5 = types.KeyboardButton(text="Quản lý người dùng 👥")
            keyboardadmin.add(key1, key2)
            keyboardadmin.add(key4, key5)
            
            input_message = message.text
            
            # Kiểm tra nếu admin bấm hủy
            if input_message == "❌ Hủy":
                bot.send_message(id, "❌ Đã hủy gửi thông báo", reply_markup=keyboardadmin)
                return
            
            all_users = GetDataFromDB.GetUsersInfo()
            if all_users ==  []:
                msg = bot.send_message(id, "Chưa có người dùng nào trong cửa hàng, /start", reply_markup=keyboardadmin)
            else:
                bot.send_message(id, "📢 Đang gửi thông báo đến tất cả người dùng...")
                success_list = []
                blocked_list = []
                other_fail_list = []
                for uid, uname, uwallet in all_users:
                    try:
                        bot.send_message(uid, f"{input_message}")
                        success_list.append(f"@{uname}")
                        time.sleep(0.3)
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "blocked" in error_msg or "deactivated" in error_msg or "bot was blocked" in error_msg:
                            blocked_list.append(f"@{uname}")
                        else:
                            other_fail_list.append(f"@{uname}")
                
                result_msg = f"✅ Hoàn tất!\n\n📊 Đã gửi: {len(success_list)}/{len(all_users)} người dùng"
                if success_list:
                    result_msg += f"\n\n✅ Thành công:\n" + ", ".join(success_list)
                if blocked_list:
                    result_msg += f"\n\n🚫 Đã chặn bot ({len(blocked_list)}):\n" + ", ".join(blocked_list)
                if other_fail_list:
                    result_msg += f"\n\n⚠️ Lỗi khác ({len(other_fail_list)}):\n" + ", ".join(other_fail_list)
                bot.send_message(id, result_msg, reply_markup=keyboardadmin)
        except Exception as e:
            print(e)
            bot.send_message(id, "❌ Lỗi, vui lòng thử lại!")
    else:
        bot.send_message(id, "⚠️ Chỉ admin mới có quyền sử dụng!", reply_markup=keyboard)


# Check if message matches manage orders button
def is_manage_orders_button(text):
    keywords = ["Manage Orders", "Quản lý đơn hàng", "manage orders", "quản lý đơn hàng"]
    return any(kw in text for kw in keywords)

#Command handler and function to Manage Orders
@bot.message_handler(content_types=["text"], func=lambda message: is_manage_orders_button(message.text))
def ManageOrders(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboardadmin.row_width = 2
        key1 = types.KeyboardButton(text=get_text("list_orders", lang))
        key2 = types.KeyboardButton(text=get_text("delete_order", lang))
        key3 = types.KeyboardButton(text="🗑️ Xóa tất cả đơn hàng")
        key4 = types.KeyboardButton(text=get_text("home", lang))
        keyboardadmin.add(key1)
        keyboardadmin.add(key2, key3)
        keyboardadmin.add(key4)
        bot.send_message(id, get_text("choose_action", lang), reply_markup=keyboardadmin)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

# Handler for reset all orders
@bot.message_handler(content_types=["text"], func=lambda message: "Xóa tất cả đơn hàng" in message.text)
def reset_all_orders(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="✅ Xác nhận xóa tất cả"))
    keyboard.row(types.KeyboardButton(text="❌ Hủy"))
    
    bot.send_message(id, "⚠️ *CẢNH BÁO*\n\nBạn có chắc muốn xóa TẤT CẢ đơn hàng?\n_Hành động này không thể hoàn tác!_", reply_markup=keyboard, parse_mode="Markdown")

@bot.message_handler(content_types=["text"], func=lambda message: "Xác nhận xóa tất cả" in message.text)
def confirm_reset_orders(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    CleanData.delete_all_orders()
    bot.send_message(id, "✅ *Đã xóa tất cả đơn hàng!*\n\nTổng đơn hàng đã được reset về 0.", reply_markup=create_main_keyboard(lang, id), parse_mode="Markdown")

# Check if message matches list orders button
def is_list_orders_button(text):
    return text in [get_text("list_orders", "en"), get_text("list_orders", "vi"), "List Orders 🛍", "Danh sách đơn hàng 🛍"]

#Command handler and function to List All Orders
@bot.message_handler(content_types=["text"], func=lambda message: is_list_orders_button(message.text))
def ListOrders(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        
        all_orders = GetDataFromDB.GetOrderInfo()
        if is_admin(id):
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
            keyboardadmin.row_width = 2
            if all_orders == [] or all_orders is None:
                bot.send_message(id, "📭 Chưa có đơn hàng nào trong cửa hàng")
            else:
                bot.send_message(id, "📋 *DANH SÁCH ĐƠN HÀNG*", parse_mode="Markdown")
                bot.send_message(id, "👇 Mã đơn hàng - Tên sản phẩm - Khách - Ngày mua 👇")
                for ordernumber, productname, buyerusername, orderdate in all_orders:
                    time.sleep(0.3)
                    # Escape username để tránh lỗi Markdown
                    safe_username = str(buyerusername).replace("_", "\\_") if buyerusername else "N/A"
                    safe_productname = str(productname).replace("_", "\\_") if productname else "N/A"
                    bot.send_message(id, f"`{ordernumber}` - {safe_productname} - @{safe_username} - {orderdate}", parse_mode="Markdown")
            key1 = types.KeyboardButton(text=get_text("list_orders", lang))
            key2 = types.KeyboardButton(text=get_text("delete_order", lang))
            key3 = types.KeyboardButton(text=get_text("home", lang))
            keyboardadmin.add(key1)
            keyboardadmin.add(key2, key3)
            bot.send_message(id, "✅ Hoàn tất!", reply_markup=keyboardadmin)
        else:
            bot.send_message(id, "⚠️ Chỉ Admin mới có quyền sử dụng!", reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        bot.send_message(id, "❌ Lỗi, vui lòng thử lại!")


# Check if message matches delete order button
def is_delete_order_button(text):
    return text in [get_text("delete_order", "en"), get_text("delete_order", "vi"), "Delete Order 🗑️", "Xóa đơn hàng 🗑️"]

#Command handler and functions to Delete Order
@bot.message_handler(content_types=["text"], func=lambda message: is_delete_order_button(message.text))
def DeleteOrderMNG(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        
        all_orders = GetDataFromDB.GetOrderInfo()
        if is_admin(id):
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
            keyboardadmin.row_width = 2
            if all_orders == [] or all_orders is None:
                key1 = types.KeyboardButton(text=get_text("list_orders", lang))
                key2 = types.KeyboardButton(text=get_text("home", lang))
                keyboardadmin.add(key1)
                keyboardadmin.add(key2)
                bot.send_message(id, "📭 Chưa có đơn hàng nào trong cửa hàng", reply_markup=keyboardadmin)
            else:
                bot.send_message(id, "👇 Mã đơn hàng - Tên sản phẩm - Khách - Ngày mua 👇")
                for ordernumber, productname, buyerusername, orderdate in all_orders:
                    # Escape username để tránh lỗi Markdown
                    safe_username = str(buyerusername).replace("_", "\\_") if buyerusername else "N/A"
                    safe_productname = str(productname).replace("_", "\\_") if productname else "N/A"
                    bot.send_message(id, f"/{ordernumber} - {safe_productname} - @{safe_username} - {orderdate}", parse_mode="Markdown")
                msg = bot.send_message(id, "👆 Nhấn vào mã đơn hàng bạn muốn xóa", parse_mode="Markdown")
                bot.register_next_step_handler(msg, delete_an_order)
        else:
            bot.send_message(id, "⚠️ Chỉ Admin mới có quyền sử dụng!", reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        msg = bot.send_message(id, "❌ Lỗi, vui lòng thử lại!")
        bot.register_next_step_handler(msg, DeleteOrderMNG)
def delete_an_order(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        ordernu = message.text
        ordernumber = ordernu[1:99]
        ordernum = GetDataFromDB.GetOrderIDs()
        ordernumbers = []
        for ordern in ordernum:
            ordernumbers.append(ordern[0])
        if f"{ordernumber}" in f"{ordernumbers}":
            try:
                global ordernums
                ordernums = ordernumber
            except Exception as e:
                print(e)
            
            if is_admin(id):
                keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
                keyboardadmin.row_width = 2
                key1 = types.KeyboardButton(text=get_text("list_orders", lang))
                key2 = types.KeyboardButton(text=get_text("home", lang))
                keyboardadmin.add(key1)
                keyboardadmin.add(key2)
                CleanData.delete_an_order(ordernumber)
                msg = bot.send_message(id, f"✅ Đã xóa đơn hàng `{ordernumber}` thành công!", reply_markup=keyboardadmin, parse_mode="Markdown")
            else:
                bot.send_message(id, "⚠️ Chỉ Admin mới có quyền sử dụng!", reply_markup=create_main_keyboard(lang, id))
        else:
            msg = bot.send_message(id, "❌ Mã đơn hàng không hợp lệ, vui lòng thử lại!")
            bot.register_next_step_handler(msg, delete_an_order)
    except Exception as e:
        print(e)
        msg = bot.send_message(id, "❌ Lỗi, vui lòng thử lại!")
        bot.register_next_step_handler(msg, delete_an_order)


# Bitcoin payment methods removed - using bank transfer only

# Keep-alive mechanism to prevent Render from sleeping
import threading

def keep_alive():
    """Ping self every 10 minutes to prevent Render free tier from sleeping"""
    render_url = os.getenv('RENDER_EXTERNAL_URL', '')
    if not render_url:
        logger.info("RENDER_EXTERNAL_URL not set, skip keep-alive")
        return
    
    while True:
        try:
            time.sleep(600)  # 10 minutes
            response = requests.get(f"{render_url}/health", timeout=30)
            logger.info(f"Keep-alive ping: {response.status_code}")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")

@flask_app.route("/health")
def health_check():
    """Health check endpoint for keep-alive"""
    return "OK", 200

if __name__ == "__main__":
    try:
        port = int(os.getenv("PORT", "10000"))  # Render provides PORT
        logger.info(f"Starting Flask application on port {port}...")
        
        # IMPORTANT: Start background tasks AFTER Flask starts listening
        # This ensures Render sees the port open quickly
        def start_background_tasks():
            """Start all background tasks after Flask is ready"""
            time.sleep(1)  # Give Flask a moment to bind port
            
            # Start DB initialization
            from InDMDevDB import start_background_db_init
            start_background_db_init()
            
            # Start keep-alive thread
            if os.getenv('RENDER_EXTERNAL_URL'):
                keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
                keep_alive_thread.start()
                logger.info("Keep-alive thread started")
        
        # Start background tasks in separate thread
        bg_thread = threading.Thread(target=start_background_tasks, daemon=True)
        bg_thread.start()
        
        # Run Flask - this blocks but port opens immediately
        flask_app.run(debug=False, host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Error starting Flask application: {e}")
        exit(1)

