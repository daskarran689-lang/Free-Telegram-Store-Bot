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
from InDMDevDB import *
from purchase import *
from InDMCategories import *
from tempmail_client import TempMailClient
from telebot.types import LabeledPrice, PreCheckoutQuery, SuccessfulPayment, ShippingOption
import json
from dotenv import load_dotenv
from languages import get_text, get_user_lang, set_user_lang, LANGUAGES, get_button_text

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

bot = telebot.TeleBot(bot_token, threaded=False)

# Set up webhook (Render-safe: use /webhook path)
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
    exit(1)

# Helper function to check if user is admin
def is_admin(user_id):
    """Check if user_id is an admin"""
    # Check env admin first
    if default_admin_id and str(user_id) == str(default_admin_id):
        return True
    # Check database
    admins = GetDataFromDB.GetAdminIDsInDB() or []
    admin_ids = [str(admin[0]) for admin in admins]
    return str(user_id) in admin_ids

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

# Hàm thông báo cho admin
def notify_admin(action, display_name, user_id=None, extra=""):
    """Gửi thông báo ngắn gọn cho admin"""
    try:
        if default_admin_id:
            msg = f"📌 {display_name}: {action}"
            if extra:
                msg += f" - {extra}"
            bot.send_message(int(default_admin_id), msg)
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")

# Add default admin from env if set
if default_admin_id:
    try:
        existing_admins = GetDataFromDB.GetAdminIDsInDB() or []
        admin_ids = [str(admin[0]) for admin in existing_admins]
        if str(default_admin_id) not in admin_ids:
            CreateDatas.AddAdmin(int(default_admin_id), "env_admin")
            logger.info(f"Default admin {default_admin_id} added from environment variable")
        else:
            logger.info(f"Admin {default_admin_id} already exists")
    except Exception as e:
        logger.error(f"Error adding default admin: {e}")

# Process webhook calls
logger.info("Shop Started!")

@flask_app.route("/", methods=["GET", "HEAD"])
def health():
    # Render health check hits this route (HEAD /)
    return "ok", 200


@flask_app.route("/", methods=["POST"])
@flask_app.route("/webhook", methods=["POST"])
def telegram_webhook():
    """Handle incoming webhook requests from Telegram"""
    try:
        ctype = (request.headers.get("content-type") or "").lower()

        if ctype.startswith("application/json"):
            json_string = request.get_data(as_text=True)
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return "ok", 200

        logger.warning(f"Invalid content type in webhook request: {ctype}")
        return "forbidden", 403

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return "error", 500


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
        
        # Get Canva accounts
        canva_accounts = CanvaAccountDB.get_available_accounts(quantity)
        
        if not canva_accounts:
            logger.error(f"PayOS: No Canva accounts available for order {ordernumber}")
            bot.send_message(user_id, "❌ Hết tài khoản Canva! Vui lòng liên hệ admin.")
            return "ok", 200
        
        # canva_accounts format: [(id, email, authkey), ...]
        productkeys = "\n".join([str(acc[1]) for acc in canva_accounts])  # acc[1] = email
        
        # Mark accounts as sold
        for acc in canva_accounts:
            CanvaAccountDB.assign_account_to_buyer(acc[0], user_id, ordernumber)  # acc[0] = id
        
        # Save order to database
        CreateDatas.AddOrder(
            user_id, username, product_name, price, orderdate,
            "PayOS", "", productkeys, ordernumber, product_number, ""
        )
        
        # Delete QR message
        if ordernumber in pending_qr_messages:
            try:
                msg_info = pending_qr_messages[ordernumber]
                bot.delete_message(msg_info["chat_id"], msg_info["message_id"])
            except:
                pass
            del pending_qr_messages[ordernumber]
        
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
        
        # Send success message to buyer
        lang = get_user_lang(user_id)
        try:
            price_num = int(float(str(price).replace(',', '')))
        except:
            price_num = price
        
        buyer_msg = get_text("your_new_order", lang, promo_msg, ordernumber, orderdate, product_name, price_num, store_currency, productkeys)
        
        inline_kb = types.InlineKeyboardMarkup()
        for acc in canva_accounts:
            email = acc[1]  # acc[1] = email
            btn_text = f"🔑 Lấy OTP: {email[:20]}..." if len(email) > 20 else f"🔑 Lấy OTP: {email}"
            inline_kb.add(types.InlineKeyboardButton(text=btn_text, callback_data=f"otp_{email}"))
        
        try:
            bot.send_message(user_id, buyer_msg, reply_markup=inline_kb, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"PayOS: Error sending buyer message: {e}")
            bot.send_message(user_id, buyer_msg.replace("*", "").replace("_", "").replace("`", ""), reply_markup=inline_kb)
        
        # Send success photo with OTP keyboard
        otp_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        otp_keyboard.row(types.KeyboardButton(text="🔑 Lấy mã xác thực"))
        otp_keyboard.row(types.KeyboardButton(text="🛍 Đơn hàng"), types.KeyboardButton(text="📞 Hỗ trợ"))
        otp_keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
        success_photo = "AgACAgUAAxkBAAIJdmlCtvFxgG3ksInklXuWO6qHRp2gAAIFDWsbgmUQVtmHfJzHPW42AQADAgADeQADNgQ"
        try:
            bot.send_photo(user_id, success_photo, reply_markup=otp_keyboard)
        except:
            pass
        
        # Edit admin notification
        admin_msg = f"✅ *Đơn hàng đã thanh toán thành công!*\n"
        admin_msg += f"━━━━━━━━━━━━━━\n"
        admin_msg += f"🆔 Mã đơn: `{ordernumber}`\n"
        admin_msg += f"👤 Khách: @{username}\n"
        admin_msg += f"📦 Sản phẩm: {product_name}\n"
        admin_msg += f"💰 Số tiền: {amount:,} VND\n"
        admin_msg += f"━━━━━━━━━━━━━━\n"
        admin_msg += f"🔑 *Tài khoản đã cấp:*\n`{productkeys}`"
        
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


# Cache for user purchase status (expires after 5 minutes)
_user_purchase_cache = {}
_cache_ttl = 300  # 5 minutes

# Create main reply keyboard (buttons at bottom - always visible)
def create_main_keyboard(lang="vi", user_id=None, skip_db_check=False):
    """Create the main user keyboard. If user has purchased, show OTP button."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="🛒 Mua ngay"))
    
    # Check if user has purchased (with caching)
    has_purchased = False
    if user_id and not skip_db_check:
        import time as time_cache
        cache_key = str(user_id)
        cached = _user_purchase_cache.get(cache_key)
        if cached and (time_cache.time() - cached['time']) < _cache_ttl:
            has_purchased = cached['value']
        else:
            try:
                accounts = CanvaAccountDB.get_buyer_accounts(user_id)
                has_purchased = accounts and len(accounts) > 0
                _user_purchase_cache[cache_key] = {'value': has_purchased, 'time': time_cache.time()}
            except:
                pass
    
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
        elif call.data.startswith("buy_qty_"):
            # Handle inline buy quantity button
            quantity = int(call.data.replace('buy_qty_', ''))
            bot.answer_callback_query(call.id, f"Đang xử lý mua {quantity} tài khoản...")
            # Simulate clicking the buy button
            fake_message = type('obj', (object,), {
                'from_user': call.from_user,
                'chat': call.message.chat,
                'text': f"🛒 Mua ({quantity})"
            })()
            handle_buy_with_quantity(fake_message)
            return
        elif call.data.startswith("confirm_order_"):
            # Admin confirms bank transfer order
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "Admin only!")
                return
            
            ordernumber = int(call.data.replace('confirm_order_', ''))
            try:
                # Get order details
                order_details = GetDataFromDB.GetOrderDetails(ordernumber)
                if order_details:
                    for buyerid, buyerusername, productname, productprice, orderdate, paidmethod, productdownloadlink, productkeys, buyercomment, ordnum, productnumber in order_details:
                        # Get product key if available
                        try:
                            keys_folder = 'Keys'
                            keys_location = f"{keys_folder}/{productnumber}.txt"
                            if os.path.exists(keys_location):
                                all_keys = open(keys_location, 'r').read().splitlines()
                                if all_keys:
                                    productkeys = all_keys[0]
                                    # Remove used key
                                    with open(keys_location, 'w') as f:
                                        f.write('\n'.join(all_keys[1:]))
                        except:
                            productkeys = "NIL"
                        
                        # Update order
                        CreateDatas.UpdateOrderPurchasedKeys(productkeys, ordernumber)
                        CreateDatas.UpdateOrderPaymentMethod("BankTransfer", ordernumber)
                        
                        # Update product quantity
                        product_list = GetDataFromDB.GetProductInfoByPName(productnumber)
                        for pnum, pname, pprice, pdesc, pimg, plink, pqty, pcat in product_list:
                            new_qty = max(0, int(pqty) - 1)
                            CreateDatas.UpdateProductQuantity(new_qty, productnumber)
                        
                        # Notify buyer with inline button
                        try:
                            price_num = int(float(str(productprice).replace(',', '').replace('k', '000').replace('K', '000')))
                        except:
                            price_num = productprice
                        
                        # Count accounts in this order
                        order_quantity = len([e for e in productkeys.split('\n') if '@' in e]) if productkeys else 1
                        if order_quantity < 1:
                            order_quantity = 1
                        
                        # Check promotion for manual confirm
                        promo_msg = ""
                        promo_info = PromotionDB.get_promotion_info()
                        if promo_info and promo_info["is_active"]:
                            sold_before = promo_info["sold_count"]
                            max_promo = promo_info["max_count"]
                            if sold_before < max_promo:
                                # Calculate bonus based on quantity and remaining slots
                                remaining_slots = max_promo - sold_before
                                promo_bonus = min(order_quantity, remaining_slots)
                                promo_slot_start = sold_before + 1
                                promo_slot_end = min(sold_before + order_quantity, max_promo)
                                
                                PromotionDB.increment_sold_count(order_quantity)
                                
                                # Format slot display
                                if promo_bonus == 1:
                                    slot_display = f"{promo_slot_start}"
                                else:
                                    slot_display = f"{promo_slot_start}-{promo_slot_end}"
                                
                                promo_msg = f"\n\n🎉 *CHÚC MỪNG! BẠN ĐƯỢC KHUYẾN MÃI MUA 1 TẶNG 1!*\n"
                                promo_msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                                promo_msg += f"🎯 Suất khuyến mãi: slot {slot_display}\n"
                                promo_msg += f"📩 Inbox Admin kèm mã đơn `{ordernumber}` để được tặng thêm {promo_bonus} tài khoản!"
                        
                        buyer_msg = get_text("your_new_order", lang, promo_msg, ordernumber, orderdate, productname, price_num, store_currency, productkeys)
                        
                        inline_kb = types.InlineKeyboardMarkup()
                        inline_kb.add(types.InlineKeyboardButton(text=f"🔑 Lấy mã xác thực cho {productkeys}", callback_data=f"otp_{productkeys}"))
                        bot.send_message(buyerid, buyer_msg, reply_markup=inline_kb, parse_mode="Markdown")
                        
                        # Send celebration image with reply keyboard
                        otp_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
                        otp_keyboard.row(types.KeyboardButton(text="🔑 Lấy mã xác thực"))
                        otp_keyboard.row(types.KeyboardButton(text="🛍 Đơn hàng"), types.KeyboardButton(text="📞 Hỗ trợ"))
                        otp_keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
                        success_photo = "AgACAgUAAxkBAAIJdmlCtvFxgG3ksInklXuWO6qHRp2gAAIFDWsbgmUQVtmHfJzHPW42AQADAgADeQADNgQ"
                        bot.send_photo(buyerid, success_photo, reply_markup=otp_keyboard)
                        
                        bot.answer_callback_query(call.id, get_text("order_confirmed", lang, ordernumber))
                        bot.edit_message_text(f"✅ Order {ordernumber} confirmed!", call.message.chat.id, call.message.message_id)
                else:
                    bot.answer_callback_query(call.id, "Order not found!")
            except Exception as e:
                logger.error(f"Confirm order error: {e}")
                bot.answer_callback_query(call.id, f"Error: {e}")
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
        elif call.data.startswith("getcats_"):
            input_catees = call.data.replace('getcats_','')
            CategoriesDatas.get_category_products(call, input_catees)
        elif call.data.startswith("getproduct_"):
            input_cate = call.data.replace('getproduct_','')
            order_data = UserOperations.purchase_a_products(call, input_cate)
            if order_data:
                # Directly process bank transfer
                process_bank_transfer_order(call.from_user.id, call.from_user.username or "user", order_data, lang)
        elif call.data.startswith("managecats_"):
            input_cate = call.data.replace('managecats_','')
            manage_categoriesbutton(call, input_cate)
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
            key0 = types.KeyboardButton(text=get_text("manage_products", lang))
            key1 = types.KeyboardButton(text=get_text("manage_categories", lang))
            key2 = types.KeyboardButton(text=get_text("manage_orders", lang))
            key3 = types.KeyboardButton(text=get_text("payment_methods", lang))
            key4 = types.KeyboardButton(text=get_text("news_to_users", lang))
            key5 = types.KeyboardButton(text=get_text("switch_to_user", lang))
            key6 = types.KeyboardButton(text="🎁 Quản lý khuyến mãi")
            keyboardadmin.add(key0)
            keyboardadmin.add(key1, key2)
            keyboardadmin.add(key3, key4)
            keyboardadmin.add(key5, key6)

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
            welcome_photo = "AgACAgUAAxkBAAIJDGlCseCl8GNEMppfwlYCUDLvfr1LAAMNaxuCZRBWIvBQc4pixGQBAAMCAAN3AAM2BA"
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
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    if not all_users:
        bot.send_message(id, "📭 Chưa có người dùng nào!", reply_markup=keyboard)
        return
    
    msg = f"👥 *DANH SÁCH NGƯỜI DÙNG*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 Tổng: {len(all_users)} người dùng\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, user in enumerate(all_users, 1):
        uid, uname, uwallet, created_at = user
        if created_at:
            created_str = str(created_at)[:10] if created_at else "N/A"
        else:
            created_str = "N/A"
        # Hiển thị đúng format - escape ký tự Markdown
        display = get_user_display_name_from_data(uname, uid)
        safe_display = display.replace("_", "\\_").replace("*", "\\*")
        msg += f"{i}. {safe_display}\n"
        msg += f"   📅 Tham gia: {created_str}\n"
    
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

# Check if message matches manage products button
def is_manage_products_button(text):
    keywords = ["Manage Products", "Quản lý sản phẩm", "manage products", "quản lý sản phẩm"]
    return any(kw in text for kw in keywords)

#Command handler to manage products
@bot.message_handler(content_types=["text"], func=lambda message: is_manage_products_button(message.text))
def ManageProducts(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboardadmin.row_width = 2
        key1 = types.KeyboardButton(text=get_text("add_product", lang))
        key2 = types.KeyboardButton(text=get_text("restock_product", lang))
        key3 = types.KeyboardButton(text=get_text("list_product", lang))
        key4 = types.KeyboardButton(text="✏️ Sửa sản phẩm")
        key5 = types.KeyboardButton(text=get_text("delete_product", lang))
        key6 = types.KeyboardButton(text="📧 Quản lý tài khoản Canva")
        key7 = types.KeyboardButton(text=get_text("home", lang))
        keyboardadmin.add(key1, key2)
        keyboardadmin.add(key3, key4)
        keyboardadmin.add(key5, key6)
        keyboardadmin.add(key7)
        
        # Show Canva account stats
        canva_count = CanvaAccountDB.get_account_count()
        bot.send_message(id, f"{get_text('choose_action', lang)}\n\n📊 Tài khoản Canva còn: {canva_count}", reply_markup=keyboardadmin)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

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
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    count = CanvaAccountDB.get_account_count()
    bot.send_message(id, f"📧 Quản lý tài khoản Canva\n\n📊 Còn {count} tài khoản khả dụng", reply_markup=keyboard)

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
    msg = bot.send_message(id, "📧 Gửi danh sách email tài khoản Canva\n\n✅ Đã dùng Premium - không cần authkey!\n\nĐịnh dạng:\nemail1@domain.xyz\nemail2@domain.xyz\nemail3@domain.xyz\n\n(Mỗi email 1 dòng)")
    bot.register_next_step_handler(msg, process_canva_accounts_file)

def process_canva_accounts_file(message):
    """Process uploaded Canva accounts file"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
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

# Check if message matches add product button
def is_add_product_button(text):
    keywords = ["Add New Product", "Thêm sản phẩm mới", "add new product", "thêm sản phẩm mới"]
    return any(kw in text for kw in keywords)

#Command handler to add product
@bot.message_handler(content_types=["text"], func=lambda message: is_add_product_button(message.text))
def AddProductsMNG(message):
    id = message.from_user.id
    usname = message.chat.username
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        msg = bot.send_message(id, get_text("reply_product_name", lang))
        new_product_number = random.randint(10000000,99999999)
        productnumber = f"{new_product_number}"
        CreateDatas.AddProduct(productnumber, id, usname)
        global productnumbers
        productnumbers = productnumber
        bot.register_next_step_handler(msg, add_a_product_name)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

#Function to add product name
def add_a_product_name(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        try:
            productname = message.text
            msg = bot.send_message(id, get_text("reply_product_desc", lang))
            CreateDatas.UpdateProductName(productname, productnumbers)
            bot.register_next_step_handler(msg, add_a_product_decription)
        except Exception as e:
            print(e)
            msg = bot.send_message(id, get_text("error_404", lang))
            bot.register_next_step_handler(msg, add_a_product_name)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

#Function to add product describtion
def add_a_product_decription(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        try:
            description = message.text
            msg = bot.send_message(id, get_text("reply_product_price", lang))
            CreateDatas.UpdateProductDescription(description, productnumbers)
            bot.register_next_step_handler(msg, add_a_product_price)
        except Exception as e:
            print(e)
            msg = bot.send_message(id, get_text("error_404", lang))
            bot.register_next_step_handler(msg, add_a_product_decription)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

#Function to add product price
def add_a_product_price(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        try:
            # Keep original format (e.g., "40,000")
            price = message.text.strip()
            msg = bot.send_message(id, get_text("attach_product_photo", lang))
            CreateDatas.UpdateProductPrice(price, productnumbers)
            bot.register_next_step_handler(msg, add_a_product_photo_link)
        except Exception as e:
            print(e)
            msg = bot.send_message(id, get_text("error_404", lang))
            bot.register_next_step_handler(msg, add_a_product_price)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

#Function to add product photo
def add_a_product_photo_link(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        try:
            image_link = message.photo[0].file_id
            all_categories = GetDataFromDB.GetCategoryIDsInDB()
            if all_categories == []:
                msg = bot.send_message(id, get_text("reply_category_name", lang))
                CreateDatas.UpdateProductproductimagelink(image_link, productnumbers)
                bot.register_next_step_handler(msg, add_a_product_category)
            else:
                bot.send_message(id, get_text("categories", lang))
                for catnum, catname in all_categories:
                    bot.send_message(id, f"{catname} - ID: /{catnum} ✅")

                msg = bot.send_message(id, get_text("select_category", lang), reply_markup=types.ReplyKeyboardRemove())
                CreateDatas.UpdateProductproductimagelink(image_link, productnumbers)
                bot.register_next_step_handler(msg, add_a_product_category)
        except Exception as e:
            print(e)
            msg = bot.send_message(id, get_text("error_404", lang))
            bot.register_next_step_handler(msg, add_a_product_photo_link)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

#Function to add product category
def add_a_product_category(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        input_cat = message.text
        all_categories = GetDataFromDB.GetCategoryIDsInDB()
        input_cate = input_cat[1:99]

        categories = []
        for catnum, catname in all_categories:
            catnames = catname.upper()
            categories.append(catnames)
            
        def checkint():
            try:
                input_cat = int(input_cate)
                return input_cat
            except:
                return input_cate

        input_category = checkint() 
        if isinstance(input_category, int) == True:
            product_cate = GetDataFromDB.Get_A_CategoryName(input_category)
            product_category = product_cate.upper()
            if f"{product_category}" not in f"{categories}" or f"{product_category}" == "NONE":
                msg = bot.send_message(id, get_text("reply_category_name", lang), reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(msg, add_a_product_category)
            elif f"{product_category}" in f"{categories}":
                msg = bot.send_message(id, get_text("attach_keys_file", lang))
                CreateDatas.UpdateProductCategory(product_category, productnumbers)
                bot.register_next_step_handler(msg, add_a_product_keys_file)
        else:
            new_category_number = random.randint(1000,9999)
            input_cate = input_cat.upper()
            CreateDatas.AddCategory(new_category_number, input_cate)
            bot.send_message(id, get_text("new_category_created", lang, input_cat))
            msg = bot.send_message(id, get_text("attach_keys_file", lang))
            CreateDatas.UpdateProductCategory(input_cate, productnumbers)
            bot.register_next_step_handler(msg, add_a_product_keys_file)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

#Function to add product file for keys
def add_a_product_keys_file(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        try:
            if message.text and message.text.upper() == "SKIP":
                msg = bot.send_message(id, get_text("reply_download_link", lang))
                bot.register_next_step_handler(msg, add_a_product_download_link)
            elif message.document:
                keys_folder = "Keys"
                if not "Keys" in os.listdir():
                    try:
                        os.mkdir("Keys")
                    except Exception as e:
                        print(e)
                KeysFiles = f"{keys_folder}/{productnumbers}.txt"
                file = message.document
                file_info = bot.get_file(file.file_id)
                file_path = file_info.file_path
                file_name = os.path.join(f"{KeysFiles}")
                downloaded_file = bot.download_file(file_path)
                with open(file_name, 'wb') as new_file:
                    new_file.write(downloaded_file)
                bot.reply_to(message, get_text("file_saved", lang))
                CreateDatas.UpdateProductKeysFile(KeysFiles, productnumbers)
                with open(file_name, 'r') as all:
                    all_quantity = all.read()
                all_quantities = len(all_quantity.split('\n'))
                CreateDatas.UpdateProductQuantity(all_quantities, productnumbers)
                msg = bot.send_message(id, get_text("reply_download_link", lang))
                bot.register_next_step_handler(msg, add_a_product_download_link)
            else:
                msg = bot.send_message(id, get_text("error_404", lang))
                bot.register_next_step_handler(msg, add_a_product_keys_file)
        except Exception as e:
            print(e)
            msg = bot.send_message(id, get_text("error_404", lang))
            bot.register_next_step_handler(msg, add_a_product_keys_file)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

#Function to add product download link
def add_a_product_download_link(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        download_link = message.text
        if message.text and message.text.upper() == "SKIP":
            bot.send_message(id, get_text("download_skipped", lang))
        else:
            CreateDatas.UpdateProductproductdownloadlink(download_link, productnumbers)
            CreateDatas.UpdateProductQuantity(int(100), productnumbers)
        
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboardadmin.row_width = 2
        key1 = types.KeyboardButton(text=get_text("add_product", lang))
        key2 = types.KeyboardButton(text=get_text("list_product", lang))
        key3 = types.KeyboardButton(text=get_text("delete_product", lang))
        key4 = types.KeyboardButton(text=get_text("home", lang))
        keyboardadmin.add(key1)
        keyboardadmin.add(key2, key3)
        keyboardadmin.add(key4)
        productimage = GetDataFromDB.GetProductImageLink(productnumbers)
        productname = GetDataFromDB.GetProductName(productnumbers)
        productnumber = GetDataFromDB.GetProductNumber(productnumbers)
        productdescription = GetDataFromDB.GetProductDescription(productnumbers)
        productprice = GetDataFromDB.GetProductPrice(productnumbers)
        productquantity = GetDataFromDB.GetProductQuantity(productnumbers)
        captions = f"\n\n\n{get_text('product_title', lang)}: {productname}\n\n\n{get_text('product_number', lang)}: `{productnumber}`\n\n\n{get_text('product_price', lang)}: {productprice} {store_currency} 💰\n\n\n{get_text('quantity_available', lang)}: {productquantity} \n\n\n{get_text('product_description', lang)}: {productdescription}"
        try:
            bot.send_photo(chat_id=message.chat.id, photo=f"{productimage}", caption=f"{captions}", parse_mode='Markdown')
        except:
            bot.send_message(message.chat.id, captions, parse_mode='Markdown')
        bot.send_message(id, get_text("product_added", lang), reply_markup=keyboardadmin)
    except Exception as e:
        print(e)
        msg = bot.send_message(id, get_text("error_404", lang))
        bot.register_next_step_handler(msg, add_a_product_download_link)

# Check if message matches restock product button
def is_restock_product_button(text):
    return text in [get_text("restock_product", "en"), get_text("restock_product", "vi"), "Restock/Add Keys 📦", "Thêm hàng/keys 📦"]

#Command handler to restock product
@bot.message_handler(content_types=["text"], func=lambda message: is_restock_product_button(message.text))
def RestockProductMNG(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        productnumber_name = GetDataFromDB.GetProductNumberName()
        if is_admin(id):
            if productnumber_name == []:
                bot.send_message(id, get_text("no_product", lang))
            else:
                bot.send_message(id, get_text("product_id_name", lang))
                for pid, tittle in productnumber_name:
                    # Get current quantity
                    qty = GetDataFromDB.GetProductQuantity(pid)
                    bot.send_message(id, f"/{pid} - `{tittle}` (Còn: {qty})", parse_mode="Markdown")
                msg = bot.send_message(id, get_text("click_product_restock", lang))
                bot.register_next_step_handler(msg, select_product_restock)
        else:
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        bot.send_message(id, get_text("error_404", lang))

def select_product_restock(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    try:
        productnu = message.text
        productnumber = productnu[1:99] if productnu.startswith('/') else productnu
        productnum = GetDataFromDB.GetProductIDs()
        productnums = [str(p[0]) for p in productnum]
        
        if productnumber in productnums:
            global restock_product_id
            restock_product_id = productnumber
            
            keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
            key1 = types.KeyboardButton(text=get_text("add_quantity", lang))
            key2 = types.KeyboardButton(text=get_text("upload_keys", lang))
            key3 = types.KeyboardButton(text=get_text("home", lang))
            keyboard.add(key1, key2)
            keyboard.add(key3)
            
            productname = GetDataFromDB.GetProductName(productnumber)
            qty = GetDataFromDB.GetProductQuantity(productnumber)
            bot.send_message(id, f"📦 {productname}\n📊 Tồn kho: {qty}\n\n{get_text('restock_method', lang)}", reply_markup=keyboard)
        else:
            msg = bot.send_message(id, get_text("error_404", lang))
            bot.register_next_step_handler(msg, select_product_restock)
    except Exception as e:
        print(e)
        msg = bot.send_message(id, get_text("error_404", lang))
        bot.register_next_step_handler(msg, select_product_restock)

# Check if message matches add quantity button
def is_add_quantity_button(text):
    return text in [get_text("add_quantity", "en"), get_text("add_quantity", "vi"), "Add Quantity ➕", "Thêm số lượng ➕"]

@bot.message_handler(content_types=["text"], func=lambda message: is_add_quantity_button(message.text))
def add_quantity_handler(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if is_admin(id):
        msg = bot.send_message(id, get_text("reply_quantity", lang))
        bot.register_next_step_handler(msg, process_add_quantity)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

def process_add_quantity(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    try:
        qty_to_add = int(message.text)
        current_qty = GetDataFromDB.GetProductQuantity(restock_product_id) or 0
        new_qty = int(current_qty) + qty_to_add
        CreateDatas.UpdateProductQuantity(new_qty, restock_product_id)
        
        keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboard.add(types.KeyboardButton(text=get_text("home", lang)))
        
        bot.send_message(id, get_text("quantity_added", lang, qty_to_add, new_qty), reply_markup=keyboard)
    except:
        msg = bot.send_message(id, get_text("error_404", lang))
        bot.register_next_step_handler(msg, process_add_quantity)

# Check if message matches upload keys button
def is_upload_keys_button(text):
    return text in [get_text("upload_keys", "en"), get_text("upload_keys", "vi"), "Upload Keys File 📄", "Upload file keys 📄"]

@bot.message_handler(content_types=["text"], func=lambda message: is_upload_keys_button(message.text))
def upload_keys_handler(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if is_admin(id):
        msg = bot.send_message(id, get_text("attach_keys_file", lang))
        bot.register_next_step_handler(msg, process_upload_keys)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

def process_upload_keys(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    try:
        if message.document:
            keys_folder = "Keys"
            if not os.path.exists(keys_folder):
                os.mkdir(keys_folder)
            
            keys_file = f"{keys_folder}/{restock_product_id}.txt"
            
            # Download new file
            file = message.document
            file_info = bot.get_file(file.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            new_keys = downloaded_file.decode('utf-8').strip().split('\n')
            
            # Append to existing keys
            existing_keys = []
            if os.path.exists(keys_file):
                with open(keys_file, 'r') as f:
                    existing_keys = [k.strip() for k in f.readlines() if k.strip()]
            
            all_keys = existing_keys + [k.strip() for k in new_keys if k.strip()]
            
            with open(keys_file, 'w') as f:
                f.write('\n'.join(all_keys))
            
            # Update quantity
            CreateDatas.UpdateProductQuantity(len(all_keys), restock_product_id)
            CreateDatas.UpdateProductKeysFile(keys_file, restock_product_id)
            
            keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
            keyboard.add(types.KeyboardButton(text=get_text("home", lang)))
            
            bot.send_message(id, get_text("keys_added", lang, len(new_keys), len(all_keys)), reply_markup=keyboard)
        else:
            msg = bot.send_message(id, get_text("error_404", lang))
            bot.register_next_step_handler(msg, process_upload_keys)
    except Exception as e:
        print(e)
        msg = bot.send_message(id, get_text("error_404", lang))
        bot.register_next_step_handler(msg, process_upload_keys)


# Check if message matches delete product button
def is_delete_product_button(text):
    return text in [get_text("delete_product", "en"), get_text("delete_product", "vi"), "Delete Product 🗑️", "Xóa sản phẩm 🗑️"]

#Command handler and functions to delete product
@bot.message_handler(content_types=["text"], func=lambda message: is_delete_product_button(message.text))
def DeleteProductsMNG(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        admins = GetDataFromDB.GetAdminIDsInDB()
        productnumber_name = GetDataFromDB.GetProductNumberName()
        if is_admin(id):
            if productnumber_name == []:
                msg = bot.send_message(id, get_text("no_product", lang))
                bot.register_next_step_handler(msg, send_welcome)
            else:
                bot.send_message(id, get_text("product_id_name", lang))
                for pid, tittle in productnumber_name:
                    bot.send_message(id, f"/{pid} - `{tittle}`", parse_mode="Markdown")
                msg = bot.send_message(id, get_text("click_product_delete", lang), parse_mode="Markdown")
                bot.register_next_step_handler(msg, delete_a_product)
        else:
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        bot.send_message(id, get_text("error_404", lang))
def delete_a_product(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    productnu = message.text
    productnumber = productnu[1:99]
    productnum = GetDataFromDB.GetProductIDs()
    productnums = []
    for productn in productnum:
        productnums.append(productn[0])
    if int(productnumber) in productnums:
        try:
            global productnumbers
            productnumbers = productnumber
        except Exception as e:
            print(e)
        
        admins = GetDataFromDB.GetAdminIDsInDB()
        if is_admin(id):
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
            keyboardadmin.row_width = 2
            key1 = types.KeyboardButton(text=get_text("add_product", lang))
            key2 = types.KeyboardButton(text=get_text("list_product", lang))
            key3 = types.KeyboardButton(text=get_text("delete_product", lang))
            key4 = types.KeyboardButton(text=get_text("home", lang))
            keyboardadmin.add(key1)
            keyboardadmin.add(key2, key3)
            keyboardadmin.add(key4)
            CleanData.delete_a_product(productnumber)
            bot.send_message(id, f"{get_text('deleted', lang)}\n\n\n{get_text('what_next', lang)}\n\n{get_text('select_button', lang)}", reply_markup=keyboardadmin, parse_mode="Markdown")
        else:
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
    else:
        msg = bot.send_message(id, get_text("error_404", lang))
        bot.register_next_step_handler(msg, delete_a_product)

# ============== EDIT PRODUCT ==============
# Check if message matches edit product button
def is_edit_product_button(text):
    return "Sửa sản phẩm" in text or "✏️ Sửa sản phẩm" in text

@bot.message_handler(content_types=["text"], func=lambda message: is_edit_product_button(message.text))
def edit_product_menu(message):
    """Admin: Show list of products to edit"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    products = GetDataFromDB.GetProductNumberName()
    if not products:
        bot.send_message(id, "📭 Chưa có sản phẩm nào", reply_markup=create_main_keyboard(lang, id))
        return
    
    bot.send_message(id, "📝 *Chọn sản phẩm cần sửa:*", parse_mode="Markdown")
    for pid, title in products:
        bot.send_message(id, f"/{pid} - `{title}`", parse_mode="Markdown")
    msg = bot.send_message(id, "👆 Bấm vào mã sản phẩm để sửa:")
    bot.register_next_step_handler(msg, select_product_to_edit)

def select_product_to_edit(message):
    """Select which product to edit"""
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if not is_admin(id):
        return
    
    try:
        product_id = message.text.replace("/", "").strip()
        product_name = GetDataFromDB.GetProductName(product_id)
        
        if not product_name:
            bot.send_message(id, "❌ Không tìm thấy sản phẩm", reply_markup=create_main_keyboard(lang, id))
            return
        
        # Store product ID for editing
        global edit_product_id
        edit_product_id = product_id
        
        # Show edit options
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row(types.KeyboardButton(text="📝 Sửa tên"))
        keyboard.row(types.KeyboardButton(text="📄 Sửa mô tả"))
        keyboard.row(types.KeyboardButton(text="💰 Sửa giá"))
        keyboard.row(types.KeyboardButton(text="🖼 Sửa ảnh"))
        keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
        
        # Get current product info
        price = GetDataFromDB.GetProductPrice(product_id)
        desc = GetDataFromDB.GetProductDescription(product_id)
        qty = GetDataFromDB.GetProductQuantity(product_id)
        
        info = f"✏️ *Sửa sản phẩm:* `{product_name}`\n"
        info += f"━━━━━━━━━━━━━━━━━━━━\n"
        info += f"🆔 Mã: `{product_id}`\n"
        info += f"💰 Giá: {price:,} VND\n"
        info += f"📦 Tồn kho: {qty}\n"
        info += f"📄 Mô tả: {desc[:50]}...\n"
        info += f"━━━━━━━━━━━━━━━━━━━━\n"
        info += "👇 Chọn thông tin cần sửa:"
        
        bot.send_message(id, info, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        print(e)
        bot.send_message(id, "❌ Lỗi, vui lòng thử lại", reply_markup=create_main_keyboard(lang, id))

# Edit product name
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "📝 Sửa tên")
def edit_product_name_prompt(message):
    id = message.from_user.id
    if not is_admin(id):
        return
    msg = bot.send_message(id, "📝 Nhập tên mới cho sản phẩm:")
    bot.register_next_step_handler(msg, save_product_name)

def save_product_name(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    try:
        new_name = message.text.strip()
        CreateDatas.UpdateProductName(new_name, edit_product_id)
        bot.send_message(id, f"✅ Đã cập nhật tên: *{new_name}*", parse_mode="Markdown", reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        bot.send_message(id, "❌ Lỗi khi cập nhật", reply_markup=create_main_keyboard(lang, id))

# Edit product description
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "📄 Sửa mô tả")
def edit_product_desc_prompt(message):
    id = message.from_user.id
    if not is_admin(id):
        return
    msg = bot.send_message(id, "📄 Nhập mô tả mới cho sản phẩm:")
    bot.register_next_step_handler(msg, save_product_desc)

def save_product_desc(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    try:
        new_desc = message.text.strip()
        CreateDatas.UpdateProductDescription(new_desc, edit_product_id)
        bot.send_message(id, f"✅ Đã cập nhật mô tả!", reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        bot.send_message(id, "❌ Lỗi khi cập nhật", reply_markup=create_main_keyboard(lang, id))

# Edit product price
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "💰 Sửa giá")
def edit_product_price_prompt(message):
    id = message.from_user.id
    if not is_admin(id):
        return
    msg = bot.send_message(id, "💰 Nhập giá mới (VD: 40000 hoặc 40,000):")
    bot.register_next_step_handler(msg, save_product_price)

def save_product_price(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    try:
        new_price = message.text.strip()
        CreateDatas.UpdateProductPrice(new_price, edit_product_id)
        bot.send_message(id, f"✅ Đã cập nhật giá: *{new_price} VND*", parse_mode="Markdown", reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        bot.send_message(id, "❌ Lỗi khi cập nhật.", reply_markup=create_main_keyboard(lang, id))

# Edit product image
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "🖼 Sửa ảnh")
def edit_product_image_prompt(message):
    id = message.from_user.id
    if not is_admin(id):
        return
    msg = bot.send_message(id, "🖼 Gửi link ảnh mới cho sản phẩm:")
    bot.register_next_step_handler(msg, save_product_image)

def save_product_image(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    try:
        new_image = message.text.strip()
        CreateDatas.UpdateProductproductimagelink(new_image, edit_product_id)
        bot.send_message(id, f"✅ Đã cập nhật ảnh sản phẩm!", reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        bot.send_message(id, "❌ Lỗi khi cập nhật", reply_markup=create_main_keyboard(lang, id))

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
    """Get OTP from TempMail for a specific email"""
    import time as time_module
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="🔑 Lấy mã xác thực"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    # Check if user is rate limited
    if user_id in otp_rate_limit:
        remaining = otp_rate_limit[user_id] - time_module.time()
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
        otp_rate_limit[user_id] = time_module.time() + OTP_LIMIT_DURATION
        bot.send_message(user_id, f"⚠️ Bạn đã lấy mã quá {OTP_MAX_REQUESTS} lần.\n⏳ Vui lòng đợi 15 phút.", reply_markup=keyboard)
        return
    
    logger.info(f"Getting OTP for email: {email} (request {current_count}/{OTP_MAX_REQUESTS})")
    loading_msg = bot.send_message(user_id, f"⏳ Đang kiểm tra hộp thư {email}...")
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton(text="🔑 Lấy mã xác thực"))
    keyboard.row(types.KeyboardButton(text="🏠 Trang chủ"))
    
    try:
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

# Handler for buy button with quantity
@bot.message_handler(content_types=["text"], func=lambda message: is_buy_button(message.text))
def handle_buy_with_quantity(message):
    """Handle buy button press with quantity"""
    id = message.from_user.id
    lang = get_user_lang(id)
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
        
        # Check stock from Canva accounts database (not product quantity)
        canva_stock = CanvaAccountDB.get_account_count()
        if canva_stock < quantity:
            bot.send_message(id, f"❌ Không đủ hàng! Chỉ còn {canva_stock} tài khoản.", reply_markup=create_main_keyboard(lang, id))
            return
        
        # Create order data with quantity
        order_data = [productnumber, pname, productprice, productdescription, productimagelink, productdownloadlink, canva_stock, productcategory]
        # Process bank transfer with quantity
        process_bank_transfer_order(id, username, order_data, lang, quantity)
    else:
        bot.send_message(id, "Không có sản phẩm!", reply_markup=create_main_keyboard(lang, id))

#Command handler and fucntion to shop Items
@bot.message_handler(commands=['buy'])
@bot.message_handler(content_types=["text"], func=lambda message: is_shop_items_button(message.text))
def shop_items(message):
    display_name = get_user_display_name(message)
    if not is_admin(message.from_user.id):
        notify_admin("🛒 Xem sản phẩm", display_name)
    UserOperations.shop_items(message)

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
    # Trigger the orders handler
    message.text = get_text("my_orders", lang)
    MyOrdersList(message)

@bot.message_handler(commands=['support'])
def support_command(message):
    """Show support info"""
    id = message.from_user.id
    lang = get_user_lang(id)
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
        response = requests.post(api_url, json=data, headers=headers, timeout=10)
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


# Process bank transfer order (reusable function)
def process_bank_transfer_order(user_id, username, order_info, lang, quantity=1):
    """Process bank transfer and show QR code"""
    
    if int(f"{order_info[6]}") < quantity:
        bot.send_message(user_id, get_text("item_soldout", lang), reply_markup=create_main_keyboard(lang, user_id), parse_mode='Markdown')
        return
    
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
        unit_price = parse_price(order_info[2])
        amount = unit_price * quantity  # Total amount = price * quantity
        ordernumber = random.randint(10000, 99999)
        transfer_content = f"DH{ordernumber}"
        
        # Store order info in memory (NOT in database yet - only save after payment confirmed)
        now = datetime.now(VN_TIMEZONE)
        orderdate = now.strftime("%Y-%m-%d %H:%M:%S")
        product_name_with_qty = f"{order_info[1]} x{quantity}" if quantity > 1 else order_info[1]
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
            "transfer_content": transfer_content
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
                admin_msg += f"👤 Khách: @{username}\n"
                admin_msg += f"📦 Sản phẩm: {product_name_with_qty}\n"
                admin_msg += f"💰 Số tiền: {amount:,} VND\n"
                admin_msg += f"⏳ Trạng thái: _Chờ chuyển khoản_"
                sent = bot.send_message(admin[0], admin_msg, parse_mode="Markdown")
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


# Check if message matches bank transfer button (kept for backward compatibility)
def is_bank_transfer_button(text):
    return text in [get_text("bank_transfer", "en"), get_text("bank_transfer", "vi"), "Bank Transfer 🏦", "Chuyển khoản 🏦"]

@bot.message_handler(content_types=["text"], func=lambda message: is_bank_transfer_button(message.text))
def bank_transfer_command(message):
    id = message.from_user.id
    username = message.from_user.username or "user"
    lang = get_user_lang(id)
    
    order_info = UserOperations.orderdata()
    if f"{order_info}" == "None" or order_info is None:
        bot.send_message(id, get_text("no_order_found", lang), reply_markup=create_main_keyboard(lang, id))
        return
    
    process_bank_transfer_order(id, username, order_info, lang)


# Bitcoin payment removed - using bank transfer only

def complete_order(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    input_commend = message.text
    CreateDatas.UpdateOrderComment(input_commend, order_number)
    order_details = GetDataFromDB.GetOrderDetails(order_number)
    for buyerid, buyerusername, productname, productprice, orderdate, paidmethod, productdownloadlink, productkeys, buyercomment, ordernumber, productnumber in order_details:
        print(f"{order_details}")
    msg = get_text("your_new_order", lang, "", ordernumber, orderdate, productname, productprice, store_currency, productkeys)
    bot.send_message(id, text=f"{msg}", reply_markup=create_main_keyboard(lang, id))

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
    display_name = get_user_display_name(message)
    
    if not is_admin(id):
        notify_admin("📋 Xem đơn hàng", display_name)
    
    my_orders = GetDataFromDB.GetOrderIDs_Buyer(id)
    if my_orders == [] or my_orders == "None":
        bot.send_message(id, get_text("no_order_completed", lang), reply_markup=create_main_keyboard(lang, id), parse_mode='Markdown')
    else:
        for my_order in my_orders:
            order_details = GetDataFromDB.GetOrderDetails(my_order[0])
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

# Check if message matches add category button
def is_add_category_button(text):
    return text in [get_text("add_category", "en"), get_text("add_category", "vi"), "Add New Category ➕", "Thêm danh mục mới ➕"]

#Command handler and function to add New Category
@bot.message_handler(content_types=["text"], func=lambda message: is_add_category_button(message.text))
def AddNewCategoryMNG(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        admins = GetDataFromDB.GetAdminIDsInDB()
        if is_admin(id):
            msg = bot.send_message(id, get_text("reply_new_category", lang))
            bot.register_next_step_handler(msg, manage_categories)
        else:
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        bot.send_message(id, get_text("error_404", lang))

# Check if message matches list categories button
def is_list_categories_button(text):
    return text in [get_text("list_categories", "en"), get_text("list_categories", "vi"), "List Categories 🏷", "Danh sách danh mục 🏷"]

#Command handler and function to List Category
@bot.message_handler(content_types=["text"], func=lambda message: is_list_categories_button(message.text))
def ListCategoryMNG(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboardadmin.row_width = 2
        try:
            all_categories = GetDataFromDB.GetCategoryIDsInDB()
            key1 = types.KeyboardButton(text=get_text("add_category", lang))
            key2 = types.KeyboardButton(text=get_text("list_categories", lang))
            key3 = types.KeyboardButton(text=get_text("edit_category", lang))
            key4 = types.KeyboardButton(text=get_text("delete_category", lang))
            key5 = types.KeyboardButton(text=get_text("home", lang))
            keyboardadmin.add(key1, key2)
            keyboardadmin.add(key3, key4)
            keyboardadmin.add(key5)
            if all_categories == []:
                bot.send_message(id, get_text("no_category", lang), reply_markup=keyboardadmin)
            else:
                keyboardadmin = types.InlineKeyboardMarkup()
                for catnum, catname in all_categories:
                    text_but = f"🏷 {catname}"
                    text_cal = f"listcats_{catnum}"
                    keyboardadmin.add(types.InlineKeyboardButton(text=text_but, callback_data=text_cal))
                bot.send_message(id, get_text("categories", lang).replace(" 👇", ":"), reply_markup=keyboardadmin)
                bot.send_message(id, get_text("list_completed", lang))
        except Exception as e:
            print(e)
            bot.send_message(id, get_text("error_404", lang))
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

# Check if message matches delete category button
def is_delete_category_button(text):
    return text in [get_text("delete_category", "en"), get_text("delete_category", "vi"), "Delete Category 🗑️", "Xóa danh mục 🗑️"]

#Command handler and function to Delete Category
@bot.message_handler(content_types=["text"], func=lambda message: is_delete_category_button(message.text))
def DeleteCategoryMNG(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        admins = GetDataFromDB.GetAdminIDsInDB()
        if is_admin(id):
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
            keyboardadmin.row_width = 2
            key1 = types.KeyboardButton(text=get_text("home", lang))
            keyboardadmin.add(key1)
            try:
                nen_category_name = "Deleted"
                try:
                    CreateDatas.Update_All_ProductCategory(nen_category_name, product_cate)
                except Exception as e:
                    print(e)
                product_cate = GetDataFromDB.Get_A_CategoryName(category_number)
                bot.send_message(id, get_text("category_deleted", lang, product_cate), reply_markup=keyboardadmin)
                CleanData.delete_a_category(category_number)

            except:
                bot.send_message(id, get_text("category_not_found", lang), reply_markup=keyboardadmin)

        else:
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        bot.send_message(id, get_text("error_404", lang))

# Check if message matches edit category button
def is_edit_category_button(text):
    return text in [get_text("edit_category", "en"), get_text("edit_category", "vi"), "Edit Category Name ✏️", "Sửa tên danh mục ✏️"]

#Command handler and functions to Edit Category Name
@bot.message_handler(content_types=["text"], func=lambda message: is_edit_category_button(message.text))
def EditCategoryNameMNG(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        admins = GetDataFromDB.GetAdminIDsInDB()
        if is_admin(id):
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
            keyboardadmin.row_width = 2
            key1 = types.KeyboardButton(text=get_text("add_category", lang))
            key2 = types.KeyboardButton(text=get_text("list_categories", lang))
            key3 = types.KeyboardButton(text=get_text("edit_category", lang))
            key4 = types.KeyboardButton(text=get_text("delete_category", lang))
            key5 = types.KeyboardButton(text=get_text("home", lang))
            keyboardadmin.add(key1, key2)
            keyboardadmin.add(key3, key4)
            keyboardadmin.add(key5)
            try:
                product_cate = GetDataFromDB.Get_A_CategoryName(category_number)
                msg = bot.send_message(id, get_text("current_category_name", lang, product_cate))
                bot.register_next_step_handler(msg, edit_a_category_name)
            except:
                bot.send_message(id, get_text("category_to_edit_not_found", lang), reply_markup=keyboardadmin)
        else:
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        msg = bot.send_message(id, "Error 404 🚫, try again with corrected input.")
        bot.register_next_step_handler(msg, EditCategoryNameMNG)
def edit_a_category_name(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        admins = GetDataFromDB.GetAdminIDsInDB()
        if is_admin(id):
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
            keyboardadmin.row_width = 2
            key1 = types.KeyboardButton(text=get_text("home", lang))
            keyboardadmin.add(key1)
            try:
                nen_category_n = message.text
                nen_category_name = nen_category_n.upper()
                product_cate = GetDataFromDB.Get_A_CategoryName(category_number)
                try:
                    CreateDatas.Update_All_ProductCategory(nen_category_name, product_cate)
                except Exception as e:
                    print(e)
                CreateDatas.Update_A_Category(nen_category_name, category_number)
                bot.send_message(id, get_text("category_updated", lang), reply_markup=keyboardadmin)

            except:
                bot.send_message(id, get_text("category_not_found", lang), reply_markup=keyboardadmin)
        else:
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))
    except Exception as e:
        print(e)
        bot.send_message(id, get_text("error_404", lang))

# Check if message matches manage categories button
def is_manage_categories_button(text):
    keywords = ["Manage Categories", "Quản lý danh mục", "manage categories", "quản lý danh mục"]
    return any(kw in text for kw in keywords)

#Command handler and function to Manage Category
@bot.message_handler(content_types=["text"], func=lambda message: is_manage_categories_button(message.text))
def ManageCategoryMNG(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboardadmin.row_width = 2
        try:
            all_categories = GetDataFromDB.GetCategoryIDsInDB()
            if all_categories == []:
                msg = bot.send_message(id, f"{get_text('no_category', lang)}\n\n\n{get_text('reply_new_category', lang)}")
                bot.register_next_step_handler(msg, manage_categories)
            else:
                keyboardadmin = types.InlineKeyboardMarkup()
                for catnum, catname in all_categories:
                    text_but = f"🏷 {catname}"
                    text_cal = f"managecats_{catnum}"
                    keyboardadmin.add(types.InlineKeyboardButton(text=text_but, callback_data=text_cal))
                bot.send_message(id, get_text("categories", lang).replace(" 👇", ":"), reply_markup=keyboardadmin)
                
                keyboard1 = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
                keyboard1.row_width = 2
                key1 = types.KeyboardButton(text=get_text("add_category", lang))
                key2 = types.KeyboardButton(text=get_text("home", lang))
                keyboard1.add(key1)
                keyboard1.add(key2)
                msg = bot.send_message(id, get_text("select_category_manage", lang), reply_markup=keyboard1)
        except Exception as e:
            print(e)
            msg = bot.send_message(id, get_text("error_404", lang))
            bot.register_next_step_handler(msg, ManageCategoryMNG)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

def manage_categories(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboardadmin.row_width = 2
        input_cat = message.text
        all_categories = GetDataFromDB.GetCategoryIDsInDB()
        input_cate = input_cat
        categories = []
        for catnum, catname in all_categories:
            catnames = catname.upper()
            categories.append(catnames)

        def checkint():
            try:
                input_cat = int(input_cate)
                return input_cat
            except:
                return input_cate

        input_category = checkint() 
        if isinstance(input_category, int) == True:
            product_cate = GetDataFromDB.Get_A_CategoryName(input_category)
            product_category = product_cate.upper()
            if f"{product_category}" not in f"{categories}" or f"{product_category}" == "NONE":
                msg = bot.send_message(id, f"{get_text('category_not_found', lang)}\n\n\n{get_text('reply_new_category', lang)}")
                bot.register_next_step_handler(msg, manage_categories)
            elif f"{product_category}" in f"{categories}":
                category_num = input_cate
                key1 = types.KeyboardButton(text=get_text("add_category", lang))
                key2 = types.KeyboardButton(text=get_text("list_categories", lang))
                key3 = types.KeyboardButton(text=get_text("edit_category", lang))
                key4 = types.KeyboardButton(text=get_text("delete_category", lang))
                key5 = types.KeyboardButton(text=get_text("home", lang))
                keyboardadmin.add(key1, key2)
                keyboardadmin.add(key3, key4)
                keyboardadmin.add(key5)
                bot.send_message(id, get_text("what_next", lang), reply_markup=keyboardadmin)
        else:
            new_category_number = random.randint(1000,9999)
            input_cate = input_cat.upper()
            CreateDatas.AddCategory(new_category_number, input_cate)
            key1 = types.KeyboardButton(text=get_text("add_category", lang))
            key2 = types.KeyboardButton(text=get_text("manage_categories", lang))
            key3 = types.KeyboardButton(text=get_text("home", lang))
            keyboardadmin.add(key1)
            keyboardadmin.add(key2)
            keyboardadmin.add(key3)
            bot.send_message(id, get_text("new_category_what_next", lang, input_cat), reply_markup=keyboardadmin)
            category_num = new_category_number
        global category_number
        category_number = category_num

    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

def manage_categoriesbutton(message, input_c):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboardadmin.row_width = 2
        all_categories = GetDataFromDB.GetCategoryIDsInDB()
        input_cate = input_c
        categories = []
        for catnum, catname in all_categories:
            catnames = catname.upper()
            categories.append(catnames)
        input_category = input_cate
        product_cate = GetDataFromDB.Get_A_CategoryName(input_category)
        product_category = product_cate.upper()
        if f"{product_category}" not in f"{categories}" or f"{product_category}" == "NONE":
            msg = bot.send_message(id, f"{get_text('category_not_found', lang)}\n\n\n{get_text('reply_new_category', lang)}")
            bot.register_next_step_handler(msg, manage_categoriesbutton)
        elif f"{product_category}" in f"{categories}":
            category_num = input_cate
            key1 = types.KeyboardButton(text=get_text("add_category", lang))
            key2 = types.KeyboardButton(text=get_text("list_categories", lang))
            key3 = types.KeyboardButton(text=get_text("edit_category", lang))
            key4 = types.KeyboardButton(text=get_text("delete_category", lang))
            key5 = types.KeyboardButton(text=get_text("home", lang))
            keyboardadmin.add(key1, key2)
            keyboardadmin.add(key3, key4)
            keyboardadmin.add(key5)
            bot.send_message(id, get_text("what_next", lang), reply_markup=keyboardadmin)
            
        global category_number
        category_number = category_num
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

# Check if message matches list product button
def is_list_product_button(text):
    return text in [get_text("list_product", "en"), get_text("list_product", "vi"), "List Product 🏷", "Danh sách sản phẩm 🏷"]

#Command handler and function to List Product
@bot.message_handler(content_types=["text"], func=lambda message: is_list_product_button(message.text))
def LISTProductsMNG(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    keyboarda = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
    keyboarda.row_width = 2
    admins = GetDataFromDB.GetAdminIDsInDB()
    productinfos = GetDataFromDB.GetProductInfos()
    if is_admin(id):
        if productinfos == []:
            bot.send_message(id, get_text("no_product", lang))
        else:
            keyboard = types.InlineKeyboardMarkup()
            for pid, tittle, price in productinfos:
                text_but = f"💼 {tittle} - {price} {store_currency}"
                text_cal = f"getproductig_{pid}"
                keyboard.add(types.InlineKeyboardButton(text=text_but, callback_data=text_cal))
            bot.send_message(id, f"PRODUCTS:", reply_markup=keyboard)
            key1 = types.KeyboardButton(text="Add New Product ➕")
            key2 = types.KeyboardButton(text="List Product 🏷")
            key3 = types.KeyboardButton(text="Delete Product 🗑️")
            key4 = types.KeyboardButton(text="Home 🏘")
            keyboarda.add(key1)
            keyboarda.add(key2, key3)
            keyboarda.add(key4)
            msg = bot.send_message(id, "List Finished: ✅", reply_markup=keyboarda, parse_mode="Markdown")

    else:
        bot.send_message(id, "⚠️ Only Admin can use this command !!!", reply_markup=keyboard)

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
            key3 = types.KeyboardButton(text="Phương thức thanh toán 💳")
            key4 = types.KeyboardButton(text="Gửi thông báo 📣")
            key5 = types.KeyboardButton(text="Quản lý người dùng 👥")
            keyboardadmin.add(key1, key2)
            keyboardadmin.add(key3, key4)
            keyboardadmin.add(key5)
            
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
                    import time
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

# Check if message matches payment methods button
def is_payment_methods_button(text):
    keywords = ["Payment Methods", "Phương thức thanh toán", "payment methods", "phương thức thanh toán"]
    return any(kw in text for kw in keywords)

#Command handler and function to Manage Payment Methods
@bot.message_handler(content_types=["text"], func=lambda message: is_payment_methods_button(message.text))
def PaymentMethodMNG(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if is_admin(id):
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboardadmin.row_width = 2
        key1 = types.KeyboardButton(text=get_text("setup_bank", lang))
        key2 = types.KeyboardButton(text=get_text("pending_orders", lang))
        key3 = types.KeyboardButton(text=get_text("home", lang))
        keyboardadmin.add(key1, key2)
        keyboardadmin.add(key3)
        bot.send_message(id, get_text("choose_action", lang), reply_markup=keyboardadmin)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

# Check if message matches setup bank button
def is_setup_bank_button(text):
    return text in [get_text("setup_bank", "en"), get_text("setup_bank", "vi"), "Setup Bank Account 🏦", "Cài đặt tài khoản 🏦"]

# Command handler to setup bank account
@bot.message_handler(content_types=["text"], func=lambda message: is_setup_bank_button(message.text))
def SetupBankAccount(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if is_admin(id):
        msg = bot.send_message(id, get_text("reply_bank_code", lang))
        bot.register_next_step_handler(msg, setup_bank_code)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

def setup_bank_code(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    username = message.from_user.username or "admin"
    
    if is_admin(id):
        global bank_setup_data
        bank_setup_data = {"bank_code": message.text.upper().strip()}
        msg = bot.send_message(id, get_text("reply_account_number", lang))
        bot.register_next_step_handler(msg, setup_account_number)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

def setup_account_number(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if is_admin(id):
        bank_setup_data["account_number"] = message.text.strip()
        msg = bot.send_message(id, get_text("reply_account_name", lang))
        bot.register_next_step_handler(msg, setup_account_name)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

def setup_account_name(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    username = message.from_user.username or "admin"
    
    if is_admin(id):
        bank_setup_data["account_name"] = message.text.strip().upper()
        
        # Save to database
        try:
            # Check if BankTransfer method exists
            existing = GetDataFromDB.GetPaymentMethodsAll("BankTransfer")
            if not existing or "BankTransfer" not in str(existing):
                CreateDatas.AddPaymentMethod(id, username, "BankTransfer")
            
            # Store bank_code|account_number in token field, account_name in secret field
            token_data = f"{bank_setup_data['bank_code']}|{bank_setup_data['account_number']}"
            CreateDatas.UpdatePaymentMethodToken(id, username, token_data, "BankTransfer")
            CreateDatas.UpdatePaymentMethodSecret(id, username, bank_setup_data["account_name"], "BankTransfer")
            
            keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
            keyboard.add(types.KeyboardButton(text=get_text("home", lang)))
            
            bot.send_message(id, get_text("bank_setup_success", lang, 
                bank_setup_data["bank_code"], 
                bank_setup_data["account_number"], 
                bank_setup_data["account_name"]
            ), reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Bank setup error: {e}")
            bot.send_message(id, get_text("error_404", lang), reply_markup=create_main_keyboard(lang, id))
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))

# Check if message matches pending orders button
def is_pending_orders_button(text):
    return text in [get_text("pending_orders", "en"), get_text("pending_orders", "vi"), "Pending Orders 📋", "Đơn chờ xác nhận 📋"]

# Command handler to view pending orders
@bot.message_handler(content_types=["text"], func=lambda message: is_pending_orders_button(message.text))
def ViewPendingOrders(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    if is_admin(id):
        try:
            # Get all orders with PENDING status
            pending_orders = GetDataFromDB.GetAllUnfirmedOrdersUser(id)
            # Also get all pending orders from all users
            all_orders = []
            try:
                cursor.execute("SELECT ordernumber, productname, buyerusername, paymentid, productnumber, productprice, buyerid FROM orders WHERE paidmethod = 'PENDING'")
                all_orders = cursor.fetchall()
            except:
                pass
            
            if not all_orders:
                bot.send_message(id, get_text("no_pending_orders", lang), reply_markup=create_main_keyboard(lang, id))
                return
            
            for order in all_orders:
                ordernumber, productname, buyerusername, paymentid, productnumber, productprice, buyerid = order
                
                admin_keyboard = types.InlineKeyboardMarkup()
                admin_keyboard.add(types.InlineKeyboardButton(
                    text=get_text("confirm_payment", lang),
                    callback_data=f"confirm_order_{ordernumber}"
                ))
                
                msg = get_text("admin_confirm_order", lang, ordernumber, buyerusername or "user", productname, int(float(productprice)), paymentid)
                bot.send_message(id, msg, reply_markup=admin_keyboard, parse_mode='Markdown')
            
            bot.send_message(id, get_text("list_completed", lang), reply_markup=create_main_keyboard(lang, id))
        except Exception as e:
            logger.error(f"View pending orders error: {e}")
            bot.send_message(id, get_text("error_404", lang), reply_markup=create_main_keyboard(lang, id))
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang, id))


# Bitcoin payment methods removed - using bank transfer only

# Keep-alive mechanism to prevent Render from sleeping
import threading
import time as time_module_keepalive

def keep_alive():
    """Ping self every 10 minutes to prevent Render free tier from sleeping"""
    render_url = os.getenv('RENDER_EXTERNAL_URL', '')
    if not render_url:
        logger.info("RENDER_EXTERNAL_URL not set, skip keep-alive")
        return
    
    while True:
        try:
            time_module_keepalive.sleep(600)  # 10 minutes
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
        # Start keep-alive thread
        if os.getenv('RENDER_EXTERNAL_URL'):
            keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
            keep_alive_thread.start()
            logger.info("Keep-alive thread started")
        
        logger.info("Starting Flask application...")
        port = int(os.getenv("PORT", "10000"))  # Render provides PORT
        flask_app.run(debug=False, host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Error starting Flask application: {e}")
        exit(1)
