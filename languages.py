# Multi-language support for Telegram Store Bot
# Hỗ trợ đa ngôn ngữ cho Bot Cửa hàng Telegram

LANGUAGES = {
    "en": {
        "name": "English 🇬🇧",
        # Buttons - User
        "shop_items": "Shop Items 🛒",
        "my_orders": "My Orders 🛍",
        "support": "Support 📞",
        "home": "Home 🏘",
        "check_payment": "Check Payment Status ⌛",
        "bitcoin": "Bitcoin ฿",
        
        # Buttons - Admin
        "manage_products": "Manage Products 💼",
        "manage_categories": "Manage Categories 💼",
        "manage_orders": "Manage Orders 🛍",
        "payment_methods": "Payment Methods 💳",
        "news_to_users": "News To Users 📣",
        "switch_to_user": "Switch To User 🙍‍♂️",
        "add_product": "Add New Product ➕",
        "list_product": "List Product 🏷",
        "delete_product": "Delete Product 🗑️",
        "add_category": "Add New Category ➕",
        "list_categories": "List Categories 🏷",
        "edit_category": "Edit Category Name ✏️",
        "delete_category": "Delete Category 🗑️",
        "list_orders": "List Orders 🛍",
        "delete_order": "Delete Order 🗑️",
        "add_bitcoin": "Add Bitcoin Method ➕",
        "add_bitcoin_secret": "Add Bitcoin Secret ➕",
        
        # Messages - Welcome
        "welcome_admin": "Dear Shop Admin,\n\nWelcome! 🤝",
        "welcome_customer": "Dear Customer,\n\nWelcome! 🤝\n\nBrowse our products, make purchases, and enjoy fast delivery! \nType /browse to start shopping. \n\n💬 Need help? \nContact our support team anytime.",
        "wallet_balance": "Your Wallet Balance: $",
        
        # Statistics
        "store_statistics": "➖➖➖Store's Statistics 📊➖➖➖",
        "total_users": "Total Users 🙍‍♂️",
        "total_admins": "Total Admins 🤴",
        "total_products": "Total Products 🏷",
        "total_orders": "Total Orders 🛍",
        
        # Messages - General
        "choose_action": "Choose an action to perform ✅",
        "admin_only": "⚠️ Only Admin can use this command !!!",
        "error_404": "Error 404 🚫, try again with corrected input.",
        "success": "Successfully ✅",
        "deleted": "Deleted successfully 🗑️",
        "list_completed": "List completed ✅",
        "done": "Done ✅",
        "no_order_found": "No order found !",
        "what_next": "What will you like to do next ?",
        "select_button": "Select one of buttons 👇",
        
        # Messages - User Mode
        "user_mode": "You are on User Mode ✅\nSend /start command or press Home 🏘 button to switch back to Admin Mode",
        
        # Messages - Products
        "reply_product_name": "Reply With Your Product Name or Title: ✅",
        "reply_product_desc": "Reply With Your Product Description: ✅",
        "reply_product_price": "Reply With Your Product Price: ✅",
        "attach_product_photo": "Attach Your Product Photo: ✅",
        "reply_category_name": "Please reply with a new category's name",
        "categories": "CATEGORIES 👇",
        "select_category": "Click on a Category ID to select Category for this Product: ✅\n\n⚠️Or Write A New Category",
        "attach_keys_file": "Attach Your Product Keys In A Text File: ✅\n\n⚠️ Please Arrange Your Product Keys In the Text File, One Product Key Per Line In The File\n\n\n⚠️ Reply With Skip to skip this step if this Product has no Product Keys",
        "reply_download_link": "Reply With Download Link For This Product\n\nThis will be the Link customer will have access to after they have paid: ✅\n\n\n⚠️ Reply With Skip to skip this step if this Product has no Product Download Link",
        "download_skipped": "Download Link Skipped ✅",
        "product_added": "Product Successfully Added ✅\n\nWhat will you like to do next ?",
        "no_product": "No product available, please send /start command to start creating products",
        "product_id_name": "👇Product ID --- Product Name👇",
        "click_product_delete": "Click on a Product ID of the product you want to delete: ✅",
        "no_product_store": "No Product in the store",
        "category_products": "Category's Products",
        "buy_now": "BUY NOW 💰",
        "product_info": "Product ID 🪪: /{}\n\nProduct Name 📦: {}\n\nProduct Price 💰: {} {}\n\nProducts In Stock 🛍: {}\n\nProduct Description 💬: {}",
        "product_title": "Product Title",
        "product_number": "Product Number",
        "product_price": "Product Price",
        "quantity_available": "Quantity Available",
        "product_description": "Product Description",
        "new_category_created": "New Category created successfully - {}",
        "file_saved": "File saved successfully.",
        
        # Messages - Categories
        "no_category": "No Category in your Store !!!",
        "reply_new_category": "Please reply with a new category's name to create Category",
        "select_category_manage": "Select Category you want to manage: ✅\n\nOr Create new Category",
        "category_not_found": "Category not found !!!",
        "category_deleted": "{} successfully deleted 🗑️",
        "current_category_name": "Current Category's Name: {} \n\n\nReply with your new Category's name",
        "category_to_edit_not_found": "Category to edit not found !!!",
        "category_updated": "Category's name successfully updated: ✅",
        "new_category_what_next": "New Category {} created successfully\n\n\nWhat will you like to do next ?",
        
        # Messages - Orders
        "no_order_completed": "You have not completed any order yet, please purchase an Item now",
        "order_info": "{} ORDERED ON {} ✅\n\n\nOrder 🆔: {}\nOrder Date 🗓: {}\nProduct Name 📦: {}\nProduct 🆔:{}\nProduct Price 💰: {} {}\nPayment Method 💳: {}\nProduct Keys 🔑: {}\nDownload ⤵️: {}",
        "your_new_order": "YOUR NEW ORDER ✅\n\n\nOrder 🆔: {}\nOrder Date 🗓: {}\nProduct Name 📦: {}\nProduct 🆔:{}\nProduct Price 💰: {} {}\nPayment Method 💳: {}\nProduct Keys 🔑: {}\nDownload ⤵️: {}",
        "thank_order": "Thank for your order 🤝",
        "write_note": "Would you like to write a note to the Seller ?",
        "reply_note": "Reply with your note or reply with NIL to proceed",
        "order_list": "Your Orders List: ✅",
        "order_id_product_buyer": "👇 OrderID - ProductName - BuyerUserName👇",
        "click_order_delete": "Click on an Order ID of the order you want to delete: ✅",
        "no_order_store": "No Order available in your store, /start",
        
        # Messages - Payment
        "select_payment": "💡 Select a Payment method to pay for this product 👇",
        "item_soldout": "This Item is soldout !!!",
        "send_btc": "Please send exact {} BTC (approximately {} {}) to the following Bitcoin",
        "address": "Address: `{}`",
        "stay_check_payment": "Please stay on this page and click on Check Payment Status ⌛ button until payment is confirmed",
        "error_payment_address": "Error creating payment address. Please try again later.\n\nOR Amount value is too small",
        "error_btc_convert": "Error converting amount to BTC. Please try again later.",
        "invalid_command": "Invalid command.",
        "payment_received": "Payment received and confirmed!",
        "payment_successful": "Payment successful ✅",
        "payment_status": "Your payment is {} for Order ID: {}",
        "no_pending_payment": "No order found with pending payment confirmation !",
        
        # Messages - Support
        "contact_us": "Contact us @{}",
        
        # Messages - Broadcast
        "broadcast_message": "This Bot is about to Broadcast message to all Shop Users\n\n\nReply with the message you want to Broadcast: ✅",
        "no_user_store": "No user available in your store, /start",
        "broadcasting": "Now Broadcasting Message To All Users: ✅",
        "message_sent": "Message successfully sent ✅ To: @`{}`",
        "user_blocked": "User @{} has blocked the bot - {}",
        "broadcast_completed": "Broadcast Completed ✅",
        
        # Messages - Bitcoin Setup
        "bitcoin_added": "Bitcoin Added successfully ✅",
        "bitcoin_already_added": "{} Payment method is already added ✅",
        "reply_api_key": "Reply With Your {} API Key for your NowPayments Account (https://account.nowpayments.io/create-account?link_id=3539852335): ✅",
        "added_successfully": "Added successfully ✅",
        
        # Language
        "select_language": "🌐 Select your language / Chọn ngôn ngữ:",
        "language_changed": "Language changed to English 🇬🇧",
    },
    
    "vi": {
        "name": "Tiếng Việt 🇻🇳",
        # Buttons - User
        "shop_items": "Cửa hàng 🛒",
        "my_orders": "Đơn hàng của tôi 🛍",
        "support": "Hỗ trợ 📞",
        "home": "Trang chủ 🏘",
        "check_payment": "Kiểm tra thanh toán ⌛",
        "bitcoin": "Bitcoin ฿",
        
        # Buttons - Admin
        "manage_products": "Quản lý sản phẩm 💼",
        "manage_categories": "Quản lý danh mục 💼",
        "manage_orders": "Quản lý đơn hàng 🛍",
        "payment_methods": "Phương thức thanh toán 💳",
        "news_to_users": "Thông báo người dùng 📣",
        "switch_to_user": "Chuyển sang người dùng 🙍‍♂️",
        "add_product": "Thêm sản phẩm mới ➕",
        "list_product": "Danh sách sản phẩm 🏷",
        "delete_product": "Xóa sản phẩm 🗑️",
        "add_category": "Thêm danh mục mới ➕",
        "list_categories": "Danh sách danh mục 🏷",
        "edit_category": "Sửa tên danh mục ✏️",
        "delete_category": "Xóa danh mục 🗑️",
        "list_orders": "Danh sách đơn hàng 🛍",
        "delete_order": "Xóa đơn hàng 🗑️",
        "add_bitcoin": "Thêm Bitcoin ➕",
        "add_bitcoin_secret": "Thêm Bitcoin Secret ➕",
        
        # Messages - Welcome
        "welcome_admin": "Xin chào Quản trị viên,\n\nChào mừng bạn! 🤝",
        "welcome_customer": "Xin chào Khách hàng,\n\nChào mừng bạn! 🤝\n\nDuyệt sản phẩm, mua hàng và tận hưởng giao hàng nhanh chóng! \nGõ /browse để bắt đầu mua sắm. \n\n💬 Cần hỗ trợ? \nLiên hệ đội ngũ hỗ trợ bất cứ lúc nào.",
        "wallet_balance": "Số dư ví: $",
        
        # Statistics
        "store_statistics": "➖➖➖Thống kê cửa hàng 📊➖➖➖",
        "total_users": "Tổng người dùng 🙍‍♂️",
        "total_admins": "Tổng quản trị viên 🤴",
        "total_products": "Tổng sản phẩm 🏷",
        "total_orders": "Tổng đơn hàng 🛍",
        
        # Messages - General
        "choose_action": "Chọn hành động để thực hiện ✅",
        "admin_only": "⚠️ Chỉ Quản trị viên mới có thể sử dụng lệnh này !!!",
        "error_404": "Lỗi 404 🚫, vui lòng thử lại với dữ liệu đúng.",
        "success": "Thành công ✅",
        "deleted": "Đã xóa thành công 🗑️",
        "list_completed": "Danh sách hoàn tất ✅",
        "done": "Hoàn tất ✅",
        "no_order_found": "Không tìm thấy đơn hàng !",
        "what_next": "Bạn muốn làm gì tiếp theo ?",
        "select_button": "Chọn một trong các nút 👇",
        
        # Messages - User Mode
        "user_mode": "Bạn đang ở Chế độ Người dùng ✅\nGửi lệnh /start hoặc nhấn nút Trang chủ 🏘 để chuyển về Chế độ Quản trị",
        
        # Messages - Products
        "reply_product_name": "Trả lời với Tên sản phẩm: ✅",
        "reply_product_desc": "Trả lời với Mô tả sản phẩm: ✅",
        "reply_product_price": "Trả lời với Giá sản phẩm: ✅",
        "attach_product_photo": "Đính kèm Ảnh sản phẩm: ✅",
        "reply_category_name": "Vui lòng trả lời với tên danh mục mới",
        "categories": "DANH MỤC 👇",
        "select_category": "Nhấn vào ID Danh mục để chọn Danh mục cho Sản phẩm này: ✅\n\n⚠️Hoặc Viết Danh mục Mới",
        "attach_keys_file": "Đính kèm Keys sản phẩm trong File Text: ✅\n\n⚠️ Vui lòng sắp xếp Keys sản phẩm trong File Text, Mỗi Key một dòng\n\n\n⚠️ Trả lời Skip để bỏ qua bước này nếu Sản phẩm không có Keys",
        "reply_download_link": "Trả lời với Link tải xuống cho Sản phẩm này\n\nĐây sẽ là Link khách hàng có thể truy cập sau khi thanh toán: ✅\n\n\n⚠️ Trả lời Skip để bỏ qua bước này nếu Sản phẩm không có Link tải",
        "download_skipped": "Đã bỏ qua Link tải xuống ✅",
        "product_added": "Sản phẩm đã được thêm thành công ✅\n\nBạn muốn làm gì tiếp theo ?",
        "no_product": "Không có sản phẩm, vui lòng gửi lệnh /start để bắt đầu tạo sản phẩm",
        "product_id_name": "👇Mã SP --- Tên sản phẩm👇",
        "click_product_delete": "Nhấn vào Mã sản phẩm bạn muốn xóa: ✅",
        "no_product_store": "Không có sản phẩm trong cửa hàng",
        "category_products": "Sản phẩm trong danh mục",
        "buy_now": "MUA NGAY 💰",
        "product_info": "Mã SP 🪪: /{}\n\nTên SP 📦: {}\n\nGiá 💰: {} {}\n\nCòn hàng 🛍: {}\n\nMô tả 💬: {}",
        "product_title": "Tên sản phẩm",
        "product_number": "Mã sản phẩm",
        "product_price": "Giá sản phẩm",
        "quantity_available": "Số lượng còn",
        "product_description": "Mô tả sản phẩm",
        "new_category_created": "Danh mục mới đã tạo thành công - {}",
        "file_saved": "File đã lưu thành công.",
        
        # Messages - Categories
        "no_category": "Không có Danh mục trong Cửa hàng !!!",
        "reply_new_category": "Vui lòng trả lời với tên danh mục mới để tạo Danh mục",
        "select_category_manage": "Chọn Danh mục bạn muốn quản lý: ✅\n\nHoặc Tạo danh mục mới",
        "category_not_found": "Không tìm thấy Danh mục !!!",
        "category_deleted": "{} đã xóa thành công 🗑️",
        "current_category_name": "Tên Danh mục hiện tại: {} \n\n\nTrả lời với tên Danh mục mới",
        "category_to_edit_not_found": "Không tìm thấy Danh mục để sửa !!!",
        "category_updated": "Tên danh mục đã cập nhật thành công: ✅",
        "new_category_what_next": "Danh mục mới {} đã tạo thành công\n\n\nBạn muốn làm gì tiếp theo ?",
        
        # Messages - Orders
        "no_order_completed": "Bạn chưa hoàn thành đơn hàng nào, vui lòng mua sản phẩm ngay",
        "order_info": "{} ĐẶT HÀNG NGÀY {} ✅\n\n\nMã ĐH 🆔: {}\nNgày đặt 🗓: {}\nTên SP 📦: {}\nMã SP 🆔:{}\nGiá 💰: {} {}\nThanh toán 💳: {}\nKeys 🔑: {}\nTải xuống ⤵️: {}",
        "your_new_order": "ĐƠN HÀNG MỚI ✅\n\n\nMã ĐH 🆔: {}\nNgày đặt 🗓: {}\nTên SP 📦: {}\nMã SP 🆔:{}\nGiá 💰: {} {}\nThanh toán 💳: {}\nKeys 🔑: {}\nTải xuống ⤵️: {}",
        "thank_order": "Cảm ơn đơn hàng của bạn 🤝",
        "write_note": "Bạn có muốn viết ghi chú cho Người bán không ?",
        "reply_note": "Trả lời với ghi chú hoặc trả lời NIL để tiếp tục",
        "order_list": "Danh sách đơn hàng: ✅",
        "order_id_product_buyer": "👇 Mã ĐH - Tên SP - Người mua👇",
        "click_order_delete": "Nhấn vào Mã đơn hàng bạn muốn xóa: ✅",
        "no_order_store": "Không có đơn hàng trong cửa hàng, /start",
        
        # Messages - Payment
        "select_payment": "💡 Chọn phương thức thanh toán cho sản phẩm này 👇",
        "item_soldout": "Sản phẩm này đã hết hàng !!!",
        "send_btc": "Vui lòng gửi chính xác {} BTC (khoảng {} {}) đến địa chỉ Bitcoin sau",
        "address": "Địa chỉ: `{}`",
        "stay_check_payment": "Vui lòng ở lại trang này và nhấn nút Kiểm tra thanh toán ⌛ cho đến khi thanh toán được xác nhận",
        "error_payment_address": "Lỗi tạo địa chỉ thanh toán. Vui lòng thử lại sau.\n\nHOẶC Số tiền quá nhỏ",
        "error_btc_convert": "Lỗi chuyển đổi sang BTC. Vui lòng thử lại sau.",
        "invalid_command": "Lệnh không hợp lệ.",
        "payment_received": "Thanh toán đã nhận và xác nhận!",
        "payment_successful": "Thanh toán thành công ✅",
        "payment_status": "Thanh toán của bạn đang {} cho Mã ĐH: {}",
        "no_pending_payment": "Không tìm thấy đơn hàng đang chờ xác nhận thanh toán !",
        
        # Messages - Support
        "contact_us": "Liên hệ @{}",
        
        # Messages - Broadcast
        "broadcast_message": "Bot sẽ gửi thông báo đến tất cả Người dùng\n\n\nTrả lời với nội dung bạn muốn gửi: ✅",
        "no_user_store": "Không có người dùng trong cửa hàng, /start",
        "broadcasting": "Đang gửi thông báo đến tất cả Người dùng: ✅",
        "message_sent": "Tin nhắn đã gửi thành công ✅ Đến: @`{}`",
        "user_blocked": "Người dùng @{} đã chặn bot - {}",
        "broadcast_completed": "Gửi thông báo hoàn tất ✅",
        
        # Messages - Bitcoin Setup
        "bitcoin_added": "Bitcoin đã thêm thành công ✅",
        "bitcoin_already_added": "Phương thức thanh toán {} đã được thêm ✅",
        "reply_api_key": "Trả lời với API Key {} cho tài khoản NowPayments (https://account.nowpayments.io/create-account?link_id=3539852335): ✅",
        "added_successfully": "Đã thêm thành công ✅",
        
        # Language
        "select_language": "🌐 Select your language / Chọn ngôn ngữ:",
        "language_changed": "Đã chuyển sang Tiếng Việt 🇻🇳",
    }
}

# Default language
DEFAULT_LANG = "vi"

# User language preferences (stored in memory, can be moved to database)
user_languages = {}

def get_text(key, lang=None, *args):
    """Get translated text for a key"""
    if lang is None:
        lang = DEFAULT_LANG
    
    text = LANGUAGES.get(lang, LANGUAGES[DEFAULT_LANG]).get(key, key)
    
    if args:
        try:
            return text.format(*args)
        except:
            return text
    return text

def get_user_lang(user_id):
    """Get user's preferred language"""
    return user_languages.get(user_id, DEFAULT_LANG)

def set_user_lang(user_id, lang):
    """Set user's preferred language"""
    if lang in LANGUAGES:
        user_languages[user_id] = lang
        return True
    return False

def get_button_text(key, lang=None):
    """Get button text for a key"""
    return get_text(key, lang)
