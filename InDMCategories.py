
from datetime import *
from flask_session import Session
import telebot
from flask import Flask, request
from telebot import types
import os
import os.path
from InDMDevDB import *
from dotenv import load_dotenv
from languages import get_text, get_user_lang
load_dotenv('config.env')

# Bot connection
bot = telebot.TeleBot(f"{os.getenv('TELEGRAM_BOT_TOKEN')}", threaded=False)
StoreCurrency = f"{os.getenv('STORE_CURRENCY')}"

class CategoriesDatas:
    def get_category_products(message, input_cate):
        id = message.from_user.id
        lang = get_user_lang(id)
        keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
        keyboard.row_width = 2
        buyer_id = message.from_user.id
        buyer_username = message.from_user.username
        all_categories = GetDataFromDB.GetCategoryIDsInDB()
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
            if f"{product_cate}" in f"{categories}":
                product_category = product_cate.upper()
                product_list = GetDataFromDB.GetProductInfoByCTGName(product_category)
                print(product_list)
                if product_list == []:
                    keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
                    keyboard.row_width = 2
                    key1 = types.KeyboardButton(text=get_text("shop_items", lang))
                    key2 = types.KeyboardButton(text=get_text("my_orders", lang))
                    key3 = types.KeyboardButton(text=get_text("support", lang))
                    keyboard.add(key1)
                    keyboard.add(key2, key3)
                    bot.send_message(id, get_text("no_product_store", lang), reply_markup=keyboard)
                else:
                    bot.send_message(id, f"{product_cate} - {get_text('category_products', lang)}")
                    # Create reply keyboard with buy buttons for each product
                    buy_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
                    product_buttons = []
                    for productnumber, productname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory in product_list:
                        bot.send_photo(id, photo=f"{productimagelink}", caption=get_text("product_info", lang, productname, productprice, StoreCurrency, productquantity, productdescription))
                        product_buttons.append(types.KeyboardButton(text=f"🛒 Mua {productname}"))
                    
                    # Add product buy buttons
                    for btn in product_buttons:
                        buy_keyboard.add(btn)
                    buy_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
                    bot.send_message(id, "👆 Chọn sản phẩm muốn mua:", reply_markup=buy_keyboard)
            else:
                print("Wrong commmand !!!")
