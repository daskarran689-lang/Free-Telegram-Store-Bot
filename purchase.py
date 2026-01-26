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


# M""M M"""""""`YM M""""""'YMM M"""""`'"""`YM M""""""'YMM MM""""""""`M M""MMMMM""M 
# M  M M  mmmm.  M M  mmmm. `M M  mm.  mm.  M M  mmmm. `M MM  mmmmmmmM M  MMMMM  M 
# M  M M  MMMMM  M M  MMMMM  M M  MMM  MMM  M M  MMMMM  M M`      MMMM M  MMMMP  M 
# M  M M  MMMMM  M M  MMMMM  M M  MMM  MMM  M M  MMMMM  M MM  MMMMMMMM M  MMMM' .M 
# M  M M  MMMMM  M M  MMMM' .M M  MMM  MMM  M M  MMMM' .M MM  MMMMMMMM M  MMP' .MM 
# M  M M  MMMMM  M M       .MM M  MMM  MMM  M M       .MM MM        .M M     .dMMM 
# MMMM MMMMMMMMMMM MMMMMMMMMMM MMMMMMMMMMMMMM MMMMMMMMMMM MMMMMMMMMMMM MMMMMMMMMMM 

# Bot connection
bot = telebot.TeleBot(f"{os.getenv('TELEGRAM_BOT_TOKEN')}", threaded=False)
StoreCurrency = f"{os.getenv('STORE_CURRENCY')}"

class UserOperations:
    def shop_items(message):
        id = message.from_user.id
        lang = get_user_lang(id)
        usname = message.chat.username
        products_list = GetDataFromDB.GetProductInfo()
        
        if products_list == [] or products_list is None:
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
            bot.send_message(id, get_text("no_product_store", lang), reply_markup=keyboard)
        else:
            # Inline keyboard với 2 nút sản phẩm
            inline_kb = types.InlineKeyboardMarkup(row_width=1)
            inline_kb.row(
                types.InlineKeyboardButton(text="🛍 Canva Edu Admin", callback_data="product_canva")
            )
            inline_kb.row(
                types.InlineKeyboardButton(text="♻️ Up lại Canva Edu", callback_data="product_upgrade")
            )
            
            # Reply keyboard với 2 nút sản phẩm
            nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            nav_keyboard.row(
                types.KeyboardButton(text="🛍 Canva Edu Admin"),
                types.KeyboardButton(text="♻️ Up lại Canva Edu")
            )
            nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
            
            # Gửi message với inline keyboard
            bot.send_message(id, "👇 Chọn sản phẩm:", reply_markup=inline_kb)
            # Gửi message với reply keyboard và lưu message_id
            reply_msg = bot.send_message(id, "⌨️", reply_markup=nav_keyboard)
            # Lưu message_id để sau xóa và gửi lại
            from store_main import pending_reply_keyboard_messages
            pending_reply_keyboard_messages[id] = {"chat_id": id, "message_id": reply_msg.message_id}

    #@bot.callback_query_handler(func=lambda call: True)
    def callback_query(call):
        if call.data == "check":
            check_command(call.message)
        else:
            print("Ok")

    def purchase_a_products(message, input_cate):
        id = message.from_user.id
        lang = get_user_lang(id)
        
        def checkint():
            try:
                input_cat = int(input_cate)
                return input_cat
            except:
                return input_cate

        input_product_id = checkint() 
        if isinstance(input_product_id, int) == True:
            product_list = GetDataFromDB.GetProductInfoByPName(input_product_id)
            print(f"DEBUG: product_list = {product_list}")
            
            # Check if product exists (product_list is not empty)
            if product_list and len(product_list) > 0:
                for productnumber, productname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory in product_list:
                    list_m = [productnumber, productname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory]
                
                global order_info
                order_info = list_m
                
                # Return order info to trigger bank transfer directly
                return list_m
            else:
                print(f"Wrong command !!! Product ID {input_product_id} not found")
                return None
        return None
    def orderdata():
        try:
            1==1
            print(order_info)
            return order_info
        except:
            return None
