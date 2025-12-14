import flask
from datetime import datetime
import requests
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
webhook_url = os.getenv('NGROK_HTTPS_URL')
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
store_currency = os.getenv('STORE_CURRENCY', 'USD')
default_admin_id = os.getenv('ADMIN_ID', '')

if not webhook_url or not bot_token:
    logger.error("Missing required environment variables: NGROK_HTTPS_URL or TELEGRAM_BOT_TOKEN")
    exit(1)

bot = telebot.TeleBot(bot_token, threaded=False)

# Set up webhook (Render-safe: use /webhook path)
try:
    bot.remove_webhook()

    base_url = (webhook_url or "").rstrip("/")
    public_webhook = f"{base_url}/webhook"

    bot.set_webhook(url=public_webhook)
    logger.info(f"Webhook set successfully to {public_webhook}")
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

# Initialize payment settings
def get_payment_api_key():
    """Get payment API key from database"""
    try:
        api_key = GetDataFromDB.GetPaymentMethodTokenKeysCleintID("Bitcoin")
        return api_key
    except Exception as e:
        logger.error(f"Error getting payment API key: {e}")
        return None

NOWPAYMENTS_API_KEY = get_payment_api_key()
BASE_CURRENCY = store_currency


# Create main keyboard
def create_main_keyboard(lang="vi"):
    """Create the main user keyboard"""
    keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    keyboard.row_width = 2
    key1 = types.KeyboardButton(text=get_text("shop_items", lang))
    key2 = types.KeyboardButton(text=get_text("my_orders", lang))
    key3 = types.KeyboardButton(text=get_text("support", lang))
    key4 = types.KeyboardButton(text="🌐 Ngôn ngữ/Language")
    keyboard.add(key1)
    keyboard.add(key2, key3)
    keyboard.add(key4)
    return keyboard

keyboard = create_main_keyboard()

# Language selection handler
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "🌐 Ngôn ngữ/Language")
@bot.message_handler(commands=['language', 'lang'])
def select_language(message):
    """Handle language selection"""
    id = message.from_user.id
    keyboard_lang = types.InlineKeyboardMarkup()
    for lang_code, lang_data in LANGUAGES.items():
        keyboard_lang.add(types.InlineKeyboardButton(
            text=lang_data["name"], 
            callback_data=f"setlang_{lang_code}"
        ))
    bot.send_message(id, get_text("select_language", get_user_lang(id)), reply_markup=keyboard_lang)


##################WELCOME MESSAGE + BUTTONS START#########################
#Function to list Products and Categories
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    """Handle callback queries from inline keyboards"""
    try:
        user_id = call.from_user.id
        lang = get_user_lang(user_id)
        
        # Handle language selection
        if call.data.startswith("setlang_"):
            new_lang = call.data.replace('setlang_', '')
            set_user_lang(user_id, new_lang)
            bot.answer_callback_query(call.id, get_text("language_changed", new_lang))
            bot.send_message(call.message.chat.id, get_text("language_changed", new_lang), reply_markup=create_main_keyboard(new_lang))
            return
        elif call.data.startswith("getcats_"):
            input_catees = call.data.replace('getcats_','')
            CategoriesDatas.get_category_products(call, input_catees)
        elif call.data.startswith("getproduct_"):
            input_cate = call.data.replace('getproduct_','')
            UserOperations.purchase_a_products(call, input_cate)
        elif call.data.startswith("managecats_"):
            input_cate = call.data.replace('managecats_','')
            manage_categoriesbutton(call, input_cate)
        else:
            logger.warning(f"Unknown callback data: {call.data}")
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        bot.send_message(call.message.chat.id, get_text("error_404", get_user_lang(call.from_user.id)))


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
    return text in [get_text("home", "en"), get_text("home", "vi"), "Home 🏘", "Trang chủ 🏘"]

#Start command handler and function
@bot.message_handler(content_types=["text"], func=lambda message: is_home_button(message.text))
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        print(NOWPAYMENTS_API_KEY)
        id = message.from_user.id
        lang = get_user_lang(id)
        try:
            usname = message.chat.username
            admins = GetDataFromDB.GetAdminIDsInDB() or []
            user_s = GetDataFromDB.AllUsers() or []
            all_user_s = 0
            for a_user_s in user_s:
                all_user_s = a_user_s[0] if a_user_s else 0
            admin_s = GetDataFromDB.AllAdmins() or []
            all_admin_s = 0
            for a_admin_s in admin_s:
                all_admin_s = a_admin_s[0] if a_admin_s else 0
            product_s = GetDataFromDB.AllProducts() or []
            all_product_s = 0
            for a_product_s in product_s:
                all_product_s = a_product_s[0] if a_product_s else 0
            orders_s = GetDataFromDB.AllOrders() or []
            all_orders_s = 0
            for a_orders_s in orders_s:
                all_orders_s = a_orders_s[0] if a_orders_s else 0
            
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            keyboardadmin.row_width = 2
            
            # Check if user is admin (from env or database)
            user_is_admin = is_admin(id)
            
            # If no admins exist and no env admin, make first user admin
            if admins == [] and not default_admin_id:
                users = GetDataFromDB.GetUserIDsInDB()
                if f"{id}" not in f"{users}":
                    CreateDatas.AddAuser(id, usname)
                CreateDatas.AddAdmin(id, usname)
                user_is_admin = True
            
            if user_is_admin:
                # Add user to database if not exists
                users = GetDataFromDB.GetUserIDsInDB() or []
                user_ids = [str(u[0]) for u in users] if users else []
                if str(id) not in user_ids:
                    CreateDatas.AddAuser(id, usname)
                
                # Add to admin table if not exists (for env admin)
                admin_ids = [str(a[0]) for a in admins] if admins else []
                if str(id) not in admin_ids:
                    CreateDatas.AddAdmin(id, usname)
                
                key0 = types.KeyboardButton(text=get_text("manage_products", lang))
                key1 = types.KeyboardButton(text=get_text("manage_categories", lang))
                key2 = types.KeyboardButton(text=get_text("manage_orders", lang))
                key3 = types.KeyboardButton(text=get_text("payment_methods", lang))
                key4 = types.KeyboardButton(text=get_text("news_to_users", lang))
                key5 = types.KeyboardButton(text=get_text("switch_to_user", lang))
                keyboardadmin.add(key0)
                keyboardadmin.add(key1, key2)
                keyboardadmin.add(key3, key4)
                keyboardadmin.add(key5)

                store_statistics = f"{get_text('store_statistics', lang)}\n\n\n{get_text('total_users', lang)}: {all_user_s}\n\n{get_text('total_admins', lang)}: {all_admin_s}\n\n{get_text('total_products', lang)}: {all_product_s}\n\n{get_text('total_orders', lang)}: {all_orders_s}\n\n\n➖➖➖➖➖➖➖➖➖➖➖➖➖"
                bot.send_photo(chat_id=message.chat.id, photo="https://i.ibb.co/9vctwpJ/IMG-1235.jpg", caption=f"{get_text('welcome_admin', lang)}\n\n{store_statistics}", reply_markup=keyboardadmin)

            else:
                users = GetDataFromDB.GetUserIDsInDB()
                if f"{id}" not in f"{users}":
                    CreateDatas.AddAuser(id,usname)
                user_data = GetDataFromDB.GetUserWalletInDB(id)
                bot.send_photo(chat_id=message.chat.id, photo="https://i.ibb.co/9vctwpJ/IMG-1235.jpg", caption=get_text("welcome_customer", lang), reply_markup=create_main_keyboard(lang))
        except Exception as e:
            print(e)
            admin_switch_user(message)
    except Exception as e:
        print(e)
        
# Check if message matches switch to user button
def is_switch_user_button(text):
    keywords = ["Switch To User", "Chuyển sang người dùng", "switch to user", "chuyển sang người dùng"]
    return any(kw in text for kw in keywords)

#Switch admin to user handler
@bot.message_handler(content_types=["text"], func=lambda message: is_switch_user_button(message.text))
def admin_switch_user(message):
    id = message.from_user.id
    usname = message.chat.username
    lang = get_user_lang(id)
    keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    keyboard.row_width = 2
    
    users = GetDataFromDB.GetUserIDsInDB()
    if f"{id}" not in f"{users}":
        CreateDatas.AddAuser(id,usname)
    user_data = GetDataFromDB.GetUserWalletInDB(id)
    
    key1 = types.KeyboardButton(text=get_text("shop_items", lang))
    key2 = types.KeyboardButton(text=get_text("my_orders", lang))
    key3 = types.KeyboardButton(text=get_text("support", lang))
    key4 = types.KeyboardButton(text=get_text("home", lang))
    keyboard.add(key1)
    keyboard.add(key2, key3)
    keyboard.add(key4)
    
    bot.send_photo(chat_id=message.chat.id, photo="https://i.ibb.co/9vctwpJ/IMG-1235.jpg", caption=f"{get_text('welcome_customer', lang)}\n\n{get_text('wallet_balance', lang)} {user_data} 💰", reply_markup=keyboard)
    bot.send_message(id, get_text("user_mode", lang), reply_markup=keyboard)

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
    
    if f"{id}" in f"{admins}":
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        keyboardadmin.row_width = 2
        key1 = types.KeyboardButton(text=get_text("add_product", lang))
        key2 = types.KeyboardButton(text=get_text("list_product", lang))
        key3 = types.KeyboardButton(text=get_text("delete_product", lang))
        key4 = types.KeyboardButton(text=get_text("home", lang))
        keyboardadmin.add(key1)
        keyboardadmin.add(key2, key3)
        keyboardadmin.add(key4)

        bot.send_message(id, get_text("choose_action", lang), reply_markup=keyboardadmin)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

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
    
    if f"{id}" in f"{admins}":
        msg = bot.send_message(id, get_text("reply_product_name", lang))
        new_product_number = random.randint(10000000,99999999)
        productnumber = f"{new_product_number}"
        CreateDatas.AddProduct(productnumber, id, usname)
        global productnumbers
        productnumbers = productnumber
        bot.register_next_step_handler(msg, add_a_product_name)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

#Function to add product name
def add_a_product_name(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if f"{id}" in f"{admins}":
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
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

#Function to add product describtion
def add_a_product_decription(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if f"{id}" in f"{admins}":
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
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

#Function to add product price
def add_a_product_price(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if f"{id}" in f"{admins}":
        try:
            price = message.text
            msg = bot.send_message(id, get_text("attach_product_photo", lang))
            CreateDatas.UpdateProductPrice(price, productnumbers)
            bot.register_next_step_handler(msg, add_a_product_photo_link)
        except Exception as e:
            print(e)
            msg = bot.send_message(id, get_text("error_404", lang))
            bot.register_next_step_handler(msg, add_a_product_price)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

#Function to add product photo
def add_a_product_photo_link(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if f"{id}" in f"{admins}":
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
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

#Function to add product category
def add_a_product_category(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if f"{id}" in f"{admins}":
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
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

#Function to add product file for keys
def add_a_product_keys_file(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if f"{id}" in f"{admins}":
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
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

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
        
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
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
        bot.send_photo(chat_id=message.chat.id, photo=f"{productimage}", caption=f"{captions}", parse_mode='Markdown')
        bot.send_message(id, get_text("product_added", lang), reply_markup=keyboardadmin)
    except Exception as e:
        print(e)
        msg = bot.send_message(id, get_text("error_404", lang))
        bot.register_next_step_handler(msg, add_a_product_download_link)

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
        if f"{id}" in f"{admins}":
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
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))
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
        if f"{id}" in f"{admins}":
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
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
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))
    else:
        msg = bot.send_message(id, get_text("error_404", lang))
        bot.register_next_step_handler(msg, delete_a_product)

# Check if message matches shop items button
def is_shop_items_button(text):
    keywords = ["Shop Items", "Cửa hàng", "shop items", "cửa hàng"]
    return any(kw in text for kw in keywords)

#Command handler and fucntion to shop Items
@bot.message_handler(commands=['browse'])
@bot.message_handler(content_types=["text"], func=lambda message: is_shop_items_button(message.text))
def shop_items(message):
    UserOperations.shop_items(message)


# Dictionary to store Bitcoint payment data
bitcoin_payment_data = {}

# Function to get BTC amount for the given fiat amount
def get_btc_amount(fiat_amount, currency):
    url = f'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies={currency.lower()}'
    response = requests.get(url)
    if response.status_code == 200:
        price = response.json()['bitcoin'][currency.lower()]
        btc_amount = int(fiat_amount) / int(price)
        return btc_amount
    else:
        print(f"Error fetching BTC price: {response.status_code} - {response.text}")
        return None

# Function to create a new payment
def create_payment_address(btc_amount):
    url = 'https://api.nowpayments.io/v1/payment'
    headers = {
        'x-api-key': NOWPAYMENTS_API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        'price_amount': btc_amount,
        'price_currency': 'btc',
        'pay_currency': 'btc',
        'ipn_callback_url': 'https://api.nowpayments.io/ipn',
        'order_id': '5555555555',
        'order_description': 'Payment for Order'
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        return response.json()['pay_address'], response.json()['payment_id']
    else:
        print(f"Error creating payment address: {response.status_code} - {response.text}")
        return None, None
    
# Function to check the payment status
def check_payment_status(payment_id):
    url = f'https://api.nowpayments.io/v1/payment/{payment_id}'
    headers = {
        'x-api-key': NOWPAYMENTS_API_KEY
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['payment_status']
    else:
        print(f"Error checking payment status: {response.status_code} - {response.text}")
        return None


# Check if message matches bitcoin button
def is_bitcoin_button(text):
    return text in [get_text("bitcoin", "en"), get_text("bitcoin", "vi"), "Bitcoin ฿"]

# Command handler to pay with Bitcoin
@bot.message_handler(content_types=["text"], func=lambda message: is_bitcoin_button(message.text))
def bitcoin_pay_command(message):
    id = message.from_user.id
    username = message.from_user.username
    lang = get_user_lang(id)
    
    order_info = UserOperations.orderdata()
    new_order = order_info
    new_orders = order_info
    if f"{order_info}" == "None":
        bot.send_message(id, get_text("no_order_found", lang), reply_markup=create_main_keyboard(lang), parse_mode="Markdown")
    else:
        if int(f"{order_info[6]}") < int(1):
            bot.send_message(id, get_text("item_soldout", lang), reply_markup=create_main_keyboard(lang), parse_mode="Markdown")
        else:
            try:
                fiat_amount = new_order[2]
                btc_amount = get_btc_amount(fiat_amount, store_currency)
                if btc_amount:
                    payment_address, payment_id = create_payment_address(btc_amount)
                    if payment_address and payment_id:
                        bitcoin_payment_data[message.from_user.id] = {
                            'payment_id': payment_id,
                            'address': payment_address,
                            'status': 'waiting',
                            'fiat_amount': fiat_amount,
                            'btc_amount': btc_amount
                        }
                        try:
                            now = datetime.now()
                            orderdate = now.strftime("%Y-%m-%d %H:%M:%S")
                            ordernumber = random.randint(10000,99999)
                            paidmethod = "NO"
                            add_key = "NIL"
                            productdownloadlink = GetDataFromDB.GetProductDownloadLink(new_orders[0])

                            CreateDatas.AddOrder(id, username,new_orders[1], new_orders[2], orderdate, paidmethod, productdownloadlink, add_key, ordernumber, new_orders[0], payment_id)
                        except Exception as e:
                            print(e)
                            pass
                        keyboard2 = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        keyboard2.row_width = 2
                        key1 = types.KeyboardButton(text=get_text("check_payment", lang))
                        keyboard2.add(key1)
                        bot.send_message(id, get_text("send_btc", lang, f"{btc_amount:.8f}", fiat_amount, store_currency), reply_markup=types.ReplyKeyboardRemove())
                        bot.send_message(message.chat.id, get_text("address", lang, payment_address), reply_markup=keyboard2, parse_mode='Markdown')
                        bot.send_message(message.chat.id, get_text("stay_check_payment", lang), reply_markup=keyboard2, parse_mode='Markdown')

                    else:
                        bot.send_message(message.chat.id, get_text("error_payment_address", lang))
                else:
                    bot.send_message(message.chat.id, get_text("error_btc_convert", lang))
            except (IndexError, ValueError):
                bot.send_message(message.chat.id, get_text("invalid_command", lang))

# Check if message matches check payment button
def is_check_payment_button(text):
    return text in [get_text("check_payment", "en"), get_text("check_payment", "vi"), "Check Payment Status ⌛", "Kiểm tra thanh toán ⌛"]

# Command handler and function to Check bitcoin payment status
@bot.message_handler(content_types=["text"], func=lambda message: is_check_payment_button(message.text))
def bitcoin_check_command(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    orders = GetDataFromDB.GetAllUnfirmedOrdersUser(id)
    if orders == [] or orders == "None":
        bot.send_message(message.chat.id, get_text("no_order_found", lang))
    else:
        for ordernumber, productname, buyerusername, payment_id, productnumber in orders:
            status = check_payment_status(payment_id)
            if status:
                if status == 'finished':
                    try:
                        keys_folder = 'Keys'
                        keys_location = f"{keys_folder}/{productnumber}.txt"
                        all_key = open(f"{keys_location}", 'r').read().splitlines()
                        def keeys():
                            if all_key == []:
                                return "NIL"
                            else:
                                return all_key
                        all_keys = keeys()
                        for a_key in all_keys:
                            1==1
                        productkeys = a_key

                        name_file = keys_location
                        with open(f'{name_file}', 'r') as file:
                            lines = file.readlines()
                        with open(f'{name_file}', 'w') as file:
                            for line in lines:
                                if f"{productkeys}" not in line:
                                    file.write(line)
                            file.truncate()
                    except:
                        pass
                
                    def check_if_keys():
                        try:
                            return productkeys
                        except:
                            return "NIL"

                    add_key = check_if_keys()

                    bot.send_message(message.chat.id, get_text("payment_received", lang))
                    CreateDatas.UpdateOrderPurchasedKeys(add_key, ordernumber)
                    CreateDatas.UpdateOrderPaymentMethod("Bitcoin", ordernumber)
                    product_list = GetDataFromDB.GetProductInfoByPName(productnumber)
                    for productnumber, productname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory in product_list:
                        list_m = [productnumber, productname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory]
                    new_quantity = int(f"{productquantity}") - int(1)
                    CreateDatas.UpdateProductQuantity(int(new_quantity), productnumber)
                    bot.send_message(message.chat.id, get_text("payment_successful", lang))
                    bot.send_message(message.chat.id, get_text("write_note", lang))
                    msg = bot.send_message(message.chat.id, get_text("reply_note", lang))
                    global order_number
                    order_number = ordernumber
                    bot.register_next_step_handler(msg, complete_order)
                else:
                    keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    keyboard.row_width = 2
                    key1 = types.KeyboardButton(text=get_text("check_payment", lang))
                    key2 = types.KeyboardButton(text=get_text("home", lang))
                    keyboard.add(key1)
                    keyboard.add(key2)
                    bot.send_message(message.chat.id, get_text("payment_status", lang, status, ordernumber), reply_markup=keyboard)
                
            else:
                bot.send_message(message.chat.id, get_text("no_pending_payment", lang))
        bot.send_message(message.chat.id, get_text("done", lang))

def complete_order(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    input_commend = message.text
    CreateDatas.UpdateOrderComment(input_commend, order_number)
    order_details = GetDataFromDB.GetOrderDetails(order_number)
    for buyerid, buyerusername, productname, productprice, orderdate, paidmethod, productdownloadlink, productkeys, buyercomment, ordernumber, productnumber in order_details:
        print(f"{order_details}")
    bot.send_message(message.chat.id, get_text("thank_order", lang))
    msg = get_text("your_new_order", lang, ordernumber, orderdate, productname, productnumber, productprice, store_currency, paidmethod, productkeys, productdownloadlink)
    bot.send_message(id, text=f"{msg}", reply_markup=create_main_keyboard(lang))
    admin_id = GetDataFromDB.GetProduct_A_AdminID(productnumber)
    bot.send_message(admin_id, text=f"{msg}", reply_markup=create_main_keyboard(lang))

# Check if message matches my orders button
def is_my_orders_button(text):
    keywords = ["My Orders", "Đơn hàng của tôi", "my orders", "đơn hàng của tôi"]
    return any(kw in text for kw in keywords)

#Command handler and function to List My Orders 🛍
@bot.message_handler(content_types=["text"], func=lambda message: is_my_orders_button(message.text))
def MyOrdersList(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    
    my_orders = GetDataFromDB.GetOrderIDs_Buyer(id)
    if my_orders == [] or my_orders == "None":
        bot.send_message(id, get_text("no_order_completed", lang), reply_markup=create_main_keyboard(lang))
    else:
        for my_order in my_orders:
            order_details = GetDataFromDB.GetOrderDetails(my_order[0])
            for buyerid, buyerusername, productname, productprice, orderdate, paidmethod, productdownloadlink, productkeys, buyercomment, ordernumber, productnumber in order_details:
                msg = get_text("order_info", lang, productname, orderdate, ordernumber, orderdate, productname, productnumber, productprice, store_currency, paidmethod, productkeys, productdownloadlink)
                bot.send_message(id, text=f"{msg}")
        bot.send_message(id, get_text("list_completed", lang), reply_markup=create_main_keyboard(lang))

# Check if message matches support button
def is_support_button(text):
    keywords = ["Support", "Hỗ trợ", "support", "hỗ trợ"]
    return any(kw in text for kw in keywords)

#Command handler and function to list Store Supports 📞
@bot.message_handler(content_types=["text"], func=lambda message: is_support_button(message.text))
def ContactSupport(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admin_usernames = GetDataFromDB.GetAdminUsernamesInDB()
    for usernames in admin_usernames:
        bot.send_message(id, get_text("contact_us", lang, usernames[0]), reply_markup=create_main_keyboard(lang))

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
        if f"{id}" in f"{admins}":
            msg = bot.send_message(id, get_text("reply_new_category", lang))
            bot.register_next_step_handler(msg, manage_categories)
        else:
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))
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
    
    if f"{id}" in f"{admins}":
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
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
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

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
        if f"{id}" in f"{admins}":
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
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
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))
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
        if f"{id}" in f"{admins}":
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
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
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))
    except Exception as e:
        print(e)
        msg = bot.send_message(id, "Error 404 🚫, try again with corrected input.")
        bot.register_next_step_handler(msg, EditCategoryNameMNG)
def edit_a_category_name(message):
    try:
        id = message.from_user.id
        lang = get_user_lang(id)
        admins = GetDataFromDB.GetAdminIDsInDB()
        if f"{id}" in f"{admins}":
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
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
            bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))
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
    
    if f"{id}" in f"{admins}":
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
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
                
                keyboard1 = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
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
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

def manage_categories(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if f"{id}" in f"{admins}":
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
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
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

def manage_categoriesbutton(message, input_c):
    id = message.from_user.id
    lang = get_user_lang(id)
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    if f"{id}" in f"{admins}":
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
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
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

# Check if message matches list product button
def is_list_product_button(text):
    return text in [get_text("list_product", "en"), get_text("list_product", "vi"), "List Product 🏷", "Danh sách sản phẩm 🏷"]

#Command handler and function to List Product
@bot.message_handler(content_types=["text"], func=lambda message: is_list_product_button(message.text))
def LISTProductsMNG(message):
    id = message.from_user.id
    lang = get_user_lang(id)
    keyboarda = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    keyboarda.row_width = 2
    admins = GetDataFromDB.GetAdminIDsInDB()
    productinfos = GetDataFromDB.GetProductInfos()
    if f"{id}" in f"{admins}":
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
    
    if f"{id}" in f"{admins}":
        msg = bot.send_message(id, get_text("broadcast_message", lang))
        bot.register_next_step_handler(msg, message_all_users)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))
def message_all_users(message):
    id = message.from_user.id
    admins = GetDataFromDB.GetAdminIDsInDB()
    
    
    if f"{id}" in f"{admins}":
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        keyboardadmin.row_width = 2
        try:
            key1 = types.KeyboardButton(text="Manage Products 💼")
            key2 = types.KeyboardButton(text="Manage Orders 🛍")
            key3 = types.KeyboardButton(text="Payment Methods 💳")
            key4 = types.KeyboardButton(text="News To Users 📣")
            key5 = types.KeyboardButton(text="Switch To User 🙍‍♂️")
            keyboardadmin.add(key1, key2)
            keyboardadmin.add(key3, key4)
            keyboardadmin.add(key5)
            input_message = message.text
            all_users = GetDataFromDB.GetUsersInfo()
            if all_users ==  []:
                msg = bot.send_message(id, "No user available in your store, /start", reply_markup=keyboardadmin)
            else:
                bot.send_message(id, "Now Broadcasting Message To All Users: ✅")
                for uid, uname, uwallet in all_users:
                    try:
                        bot.send_message(uid, f"{input_message}")
                        bot.send_message(id, f"Message successfully sent ✅ To: @`{uname}`")
                        time.sleep(0.5)
                    except:
                        bot.send_message(id, f"User @{uid} has blocked the bot - {uname} ")
                bot.send_message(id, f"Broadcast Completed ✅", reply_markup=keyboardadmin)
        except Exception as e:
            print(e)
            bot.send_message(id, "Error 404 🚫, try again with corrected input.")
    else:
        bot.send_message(id, "⚠️ Only Admin can use this command !!!", reply_markup=keyboard)


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
    
    if f"{id}" in f"{admins}":
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        keyboardadmin.row_width = 2
        key1 = types.KeyboardButton(text=get_text("list_orders", lang))
        key2 = types.KeyboardButton(text=get_text("delete_order", lang))
        key3 = types.KeyboardButton(text=get_text("home", lang))
        keyboardadmin.add(key1)
        keyboardadmin.add(key2, key3)
        bot.send_message(id, get_text("choose_action", lang), reply_markup=keyboardadmin)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))

#Command handler and function to List All Orders
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "List Orders 🛍")
def ListOrders(message):
    try:
        id = message.from_user.id
        
        
        admins = GetDataFromDB.GetAdminIDsInDB()
        all_orders = GetDataFromDB.GetOrderInfo()
        if f"{id}" in f"{admins}":
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            keyboardadmin.row_width = 2
            if all_orders ==  []:
                bot.send_message(id, "No Order available in your store, /start")
            else:
                bot.send_message(id, "Your Oders List: ✅")
                bot.send_message(id, f"👇 OrderID - ProductName - BuyerUserName👇")
                for ordernumber, productname, buyerusername in all_orders:
                    import time
                    time.sleep(0.5)
                    bot.send_message(id, f"`{ordernumber}` - `{productname}` - @{buyerusername}")
            key1 = types.KeyboardButton(text="List Orders 🛍")
            key2 = types.KeyboardButton(text="Delete Order 🗑️")
            key3 = types.KeyboardButton(text="Home 🏘")
            keyboardadmin.add(key1)
            keyboardadmin.add(key2, key3)
            bot.send_message(id, f"List Completed ✅", reply_markup=keyboardadmin)
        else:
            bot.send_message(id, "⚠️ Only Admin can use this command !!!", reply_markup=keyboard)
    except Exception as e:
        print(e)
        bot.send_message(id, "Error 404 🚫, try again with corrected input.")


#Command handler and functions to Delete Order
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "Delete Order 🗑️")
def DeleteOrderMNG(message):
    try:
        id = message.from_user.id
        
        
        admins = GetDataFromDB.GetAdminIDsInDB()
        all_orders = GetDataFromDB.GetOrderInfo()
        if f"{id}" in f"{admins}":
            keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            keyboardadmin.row_width = 2
            if all_orders ==  []:
                key1 = types.KeyboardButton(text="List Orders 🛍")
                key2 = types.KeyboardButton(text="Home 🏘")
                keyboardadmin.add(key1)
                keyboardadmin.add(key2)
                bot.send_message(id, "No Order available in your store, /start", reply_markup=keyboardadmin)
            else:
                bot.send_message(id, f"👇 OrderID - ProductName - BuyerUserName 👇")
                for ordernumber, productname, buyerusername in all_orders:
                    bot.send_message(id, f"/{ordernumber} - `{productname}` - @{buyerusername}", parse_mode="Markdown")
                msg = bot.send_message(id, "Click on an Order ID of the order you want to delete: ✅", parse_mode="Markdown")
                bot.register_next_step_handler(msg, delete_an_order)
        else:
            bot.send_message(id, "⚠️ Only Admin can use this command !!!", reply_markup=keyboard)
    except Exception as e:
        print(e)
        msg = bot.send_message(id, "Error 404 🚫, try again with corrected input.")
        bot.register_next_step_handler(msg, DeleteOrderMNG)
def delete_an_order(message):
    try:
        id = message.from_user.id
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
            
            
            admins = GetDataFromDB.GetAdminIDsInDB()
            if f"{id}" in f"{admins}":
                keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                keyboardadmin.row_width = 2
                key1 = types.KeyboardButton(text="List Orders 🛍")
                key2 = types.KeyboardButton(text="Home 🏘")
                keyboardadmin.add(key1)
                keyboardadmin.add(key2)
                CleanData.delete_an_order(ordernumber)
                msg = bot.send_message(id, "Deleted successfully 🗑️\n\n\nWhat will you like to do next ?\n\nSelect one of buttons 👇", reply_markup=keyboardadmin, parse_mode="Markdown")
            else:
                bot.send_message(id, "⚠️ Only Admin can use this command !!!", reply_markup=keyboard)
        else:
            msg = bot.send_message(id, "Error 404 🚫, try again with corrected input.")
            bot.register_next_step_handler(msg, delete_an_order)
    except Exception as e:
        print(e)
        msg = bot.send_message(id, "Error 404 🚫, try again with corrected input.")
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
    
    if f"{id}" in f"{admins}":
        keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        keyboardadmin.row_width = 2
        key1 = types.KeyboardButton(text=get_text("add_bitcoin", lang))
        key2 = types.KeyboardButton(text=get_text("home", lang))
        keyboardadmin.add(key1)
        keyboardadmin.add(key2)
        bot.send_message(id, get_text("choose_action", lang), reply_markup=keyboardadmin)
    else:
        bot.send_message(id, get_text("admin_only", lang), reply_markup=create_main_keyboard(lang))


#Command handler and function to Add API Keys for Bitcoin Payment Method
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "Add Bitcoin Method ➕")
def AddBitcoinAPIKey(message):
    id = message.from_user.id
    username = message.from_user.username
    admins = GetDataFromDB.GetAdminIDsInDB()
    keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    keyboardadmin.row_width = 2
    edit_methods = "Bitcoin"
    global edit_method
    edit_method = edit_methods
    all_pay_methods = GetDataFromDB.GetPaymentMethodsAll(edit_method)
    if f"{id}" in f"{admins}":

        if f"{edit_method}" in f"{all_pay_methods}":
            bot.send_message(id, f"{edit_method} Payment method is already added ✅", reply_markup=keyboardadmin)
        else:
            CreateDatas.AddPaymentMethod(id, username, edit_method)

            try:
                for method_name, token_clientid_keys, sectret_keys in all_pay_methods:
                    all = method_name, token_clientid_keys, sectret_keys
                msg = bot.send_message(id, f"Reply With Your {edit_method} API Key for your NowPayments Account (https://account.nowpayments.io/create-account?link_id=3539852335): ✅")
                bot.register_next_step_handler(msg, add_bitcoin_api_key)
            except Exception as e:
                print(e)
                msg = bot.send_message(id, "Error 404 🚫, try again with corrected input.")
                bot.register_next_step_handler(msg, AddBitcoinAPIKey)
    else:
        bot.send_message(id, "⚠️ Only Admin can use this command !!!", reply_markup=keyboard)
def add_bitcoin_api_key(message):
    id = message.from_user.id
    admins = GetDataFromDB.GetAdminIDsInDB()
    keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    keyboardadmin.row_width = 2
    if f"{id}" in f"{admins}":
        try:
            key1 = types.KeyboardButton(text="Home 🏘")
            keyboardadmin.add(key1)
            id = message.from_user.id
            api_key = message.text
            username = message.from_user.username
            CreateDatas.UpdatePaymentMethodToken(id, username, api_key, edit_method)
            bot.send_message(id, "Bitcoin Added successfully ✅", reply_markup=keyboardadmin)
        except Exception as e:
            print(e)
            msg = bot.send_message(id, "Error 404 🚫, try again with corrected input.")
            bot.register_next_step_handler(msg, AddBitcoinAPIKey)
    else:
        bot.send_message(id, "⚠️ Only Admin can use this command !!!", reply_markup=keyboard)

#Command handler and function to Add API Secret Key for Bitcoin Payment Method
@bot.message_handler(content_types=["text"], func=lambda message: message.text == "Add Bitcoin Secret ➕")
def AddBitcoinSecretKey(message):
    id = message.from_user.id
    admins = GetDataFromDB.GetAdminIDsInDB()
    keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    keyboardadmin.row_width = 2
    all_pay_methods = GetDataFromDB.GetPaymentMethodsAll(edit_method)
    if f"{id}" in f"{admins}":
        try:
            for method_name, token_clientid_keys, sectret_keys in all_pay_methods:
                all = method_name, token_clientid_keys, sectret_keys
            msg = bot.send_message(id, f"Reply With Your {edit_method} API Key for your NowPayments Account (https://account.nowpayments.io/create-account?link_id=3539852335): ✅")
            bot.register_next_step_handler(msg, add_bitcoin_secret_key)
        except Exception as e:
            print(e)
            msg = bot.send_message(id, "Error 404 🚫, try again with corrected input.")
            bot.register_next_step_handler(msg, AddBitcoinSecretKey)
    else:
        bot.send_message(id, "⚠️ Only Admin can use this command !!!", reply_markup=keyboardadmin)
def add_bitcoin_secret_key(message):
    id = message.from_user.id
    admins = GetDataFromDB.GetAdminIDsInDB()
    keyboardadmin = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    keyboardadmin.row_width = 2
    if f"{id}" in f"{admins}":
        try:
            key1 = types.KeyboardButton(text="Home 🏘")
            keyboardadmin.add(key1)
            id = message.from_user.id
            api_key = message.text
            username = message.from_user.username
            CreateDatas.UpdatePaymentMethodSecret(id, username, api_key, edit_method)
            bot.send_message(id, "Added successfully ✅", reply_markup=keyboardadmin)
        except Exception as e:
            print(e)
            msg = bot.send_message(id, "Error 404 🚫, try again with corrected input.")
            bot.register_next_step_handler(msg, AddBitcoinSecretKey)
    else:
        bot.send_message(id, "⚠️ Only Admin can use this command !!!", reply_markup=keyboard)

if __name__ == "__main__":
    try:
        logger.info("Starting Flask application...")
        port = int(os.getenv("PORT", "10000"))  # Render provides PORT
        flask_app.run(debug=False, host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Error starting Flask application: {e}")
        exit(1)