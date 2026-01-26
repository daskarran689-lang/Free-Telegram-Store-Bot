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
            # Get actual Canva account count from database
            from InDMDevDB import CanvaAccountDB
            canva_stock = CanvaAccountDB.get_account_count()
            
            # ========== SẢN PHẨM 1: CANVA EDU ADMIN (MUA MỚI) ==========
            inline_kb_canva = types.InlineKeyboardMarkup(row_width=2)
            inline_kb_canva.row(
                types.InlineKeyboardButton(text="🛡 BH 3 tháng", callback_data="warranty_bh3"),
                types.InlineKeyboardButton(text="⚡ KBH", callback_data="warranty_kbh")
            )
            
            # Bảng giá Canva Edu Admin
            price_tiers_canva = "💰 <b>Bảng giá:</b>\n"
            price_tiers_canva += "━━━━━━━━━━━━━━\n"
            price_tiers_canva += "🛡 <b>BH 3 tháng:</b>\n"
            price_tiers_canva += "• 1-9 acc: 100K/acc\n"
            price_tiers_canva += "• ≥10 acc: 50K/acc\n"
            price_tiers_canva += "• ≥50 acc: 25K/acc\n\n"
            price_tiers_canva += "⚡ <b>KBH (Không bảo hành):</b>\n"
            price_tiers_canva += "• 1-9 acc: 40K/acc\n"
            price_tiers_canva += "• ≥10 acc: 20K/acc\n"
            price_tiers_canva += "• ≥50 acc: 10K/acc"
            
            # Show product 1 from database
            for productnumber, productname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory in products_list:
                caption_canva = f"🛍 <b>{productname}</b>\n\n📦 Còn: {canva_stock} tài khoản\n\n{price_tiers_canva}\n\n📝 {productdescription}"
                caption_canva += "\n\n👇 Chọn loại bảo hành:"
                try:
                    bot.send_photo(id, photo=f"{productimagelink}", caption=caption_canva, reply_markup=inline_kb_canva, parse_mode='HTML')
                except:
                    bot.send_message(id, caption_canva, reply_markup=inline_kb_canva, parse_mode='HTML')
                break  # Chỉ lấy sản phẩm đầu tiên
            
            # ========== SẢN PHẨM 2: UP LẠI CANVA EDU ==========
            inline_kb_upgrade = types.InlineKeyboardMarkup(row_width=1)
            inline_kb_upgrade.row(
                types.InlineKeyboardButton(text="🛡 BH 3 tháng - 120K", callback_data="upgrade_bh3")
            )
            inline_kb_upgrade.row(
                types.InlineKeyboardButton(text="⚡ KBH - 50K", callback_data="upgrade_kbh")
            )
            
            # Bảng giá Up lại Canva Edu
            caption_upgrade = "♻️ <b>UP LẠI CANVA EDU ADMIN</b>\n"
            caption_upgrade += "━━━━━━━━━━━━━━\n"
            caption_upgrade += "<i>Dành cho tài khoản bị mất gói - giữ nguyên team/design</i>\n\n"
            caption_upgrade += "💰 <b>Bảng giá:</b>\n"
            caption_upgrade += "• KBH: <b>50K</b>\n"
            caption_upgrade += "• BH 3 tháng: <b>120K</b>\n\n"
            caption_upgrade += "📝 <b>Lưu ý:</b> Sau khi thanh toán thành công:\n"
            caption_upgrade += "📩 Inbox Admin kèm:\n"
            caption_upgrade += "• Mã đơn hàng\n"
            caption_upgrade += "• Tài khoản Canva\n"
            caption_upgrade += "• Mật khẩu (nếu có)\n"
            caption_upgrade += "• Cung cấp mã xác thực khi Admin yêu cầu"
            caption_upgrade += "\n\n👇 Chọn loại bảo hành:"
            
            bot.send_message(id, caption_upgrade, reply_markup=inline_kb_upgrade, parse_mode='HTML')
            
            # Reply keyboard for navigation
            nav_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            nav_keyboard.row(
                types.KeyboardButton(text="🛡 Mua BH 3 tháng"),
                types.KeyboardButton(text="⚡ Mua KBH")
            )
            nav_keyboard.row(
                types.KeyboardButton(text="♻️ Up lại Canva Edu")
            )
            nav_keyboard.add(types.KeyboardButton(text="🏠 Trang chủ"))
            
            # Set reply keyboard
            bot.send_message(id, "Hoặc bấm chọn ở menu bàn phím 👇", reply_markup=nav_keyboard)

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
