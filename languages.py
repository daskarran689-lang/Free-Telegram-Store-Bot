# Multi-language support for Telegram Store Bot
# Hỗ trợ đa ngôn ngữ cho Bot Cửa hàng Telegram

LANGUAGES = {
    "en": {
        "name": "English 🇬🇧",
        # Buttons - User
        "shop_items": "Mua Canva 🎨",
        "my_orders": "Đơn hàng 🛍",
        "support": "Hỗ trợ 📞",
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
        "restock_product": "Restock/Add Keys 📦",
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
        "welcome_admin": "👋 *Welcome Admin!*\n━━━━━━━━━━━━━━\nReady to manage your store",
        "welcome_customer": "👋 *Hello* {username}!\nWelcome to\n━━━━━━━━━━━━━━\n🏪 *DLNDAI SHOP*\n━━━━━━━━━━━━━━\n\n💳 Buy automatically 24/7\n📦 View order history easily\n💬 Support: @dlndai\n\n📖 Type /help to see commands\n👇 Or press button below to start",
        "wallet_balance": "Your Wallet Balance: $",
        
        # Statistics
        "store_statistics": "📊 *STORE STATISTICS*\n━━━━━━━━━━━━━━━━━━━━",
        "total_users": "Total Users 🙍‍♂️",
        "total_admins": "Total Admins 🤴",
        "total_products": "Total Products 🏷",
        "total_orders": "Total Orders 🛍",
        
        # Messages - General
        "choose_action": "Choose an action to perform ✅",
        "admin_only": "⚠️ *Admin Only*\nThis command is restricted to administrators",
        "error_404": "❌ *Error 404*\nPlease try again with correct input",
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
        "attach_keys_file": "Đính kèm file chứa tài khoản Canva (.txt): ✅\n\n⚠️ Mỗi tài khoản 1 dòng (email:password)\n\n⚠️ Trả lời Skip nếu không có",
        "reply_download_link": "Nhập link hướng dẫn sử dụng Canva (nếu có):\n\n⚠️ Trả lời Skip để bỏ qua",
        "download_skipped": "Download Link Skipped ✅",
        "product_added": "✅ *Product Added!*\n━━━━━━━━━━━━━━\nWhat would you like to do next?",
        "no_product": "No product available, please send /start command to start creating products",
        "product_id_name": "👇Product ID --- Product Name👇",
        "click_product_delete": "Click on a Product ID of the product you want to delete: ✅",
        "click_product_restock": "Click on a Product ID to restock: ✅",
        "restock_method": "Choose restock method:\n\n1️⃣ Add quantity manually\n2️⃣ Upload keys file",
        "add_quantity": "Add Quantity ➕",
        "upload_keys": "Upload Keys File 📄",
        "reply_quantity": "Reply with quantity to add:",
        "quantity_added": "✅ *Added* `{}`!\n📦 Stock: `{}`",
        "keys_added": "✅ *Added* `{}` accounts!\n📦 Stock: `{}`",
        "no_product_store": "No Product in the store",
        "category_products": "Category's Products",
        "buy_now": "BUY NOW 💰",
        "product_info": "🎨 <b>{}</b>\n\n💰 Giá: <b>{} {}</b>\n📦 Còn: <code>{}</code> tài khoản\n\n📝 <i>{}</i>",
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
        "category_deleted": "🗑️ *Deleted:* `{}`",
        "current_category_name": "Current Category's Name: {} \n\n\nReply with your new Category's name",
        "category_to_edit_not_found": "Category to edit not found !!!",
        "category_updated": "Category's name successfully updated: ✅",
        "new_category_what_next": "✅ *Category Created!*\n━━━━━━━━━━━━━━━━━━━━\n📁 Name: *{}*\n\n_What would you like to do next?_",
        
        # Messages - Orders
        "no_order_completed": "📭 *No Orders Yet*\n_You haven't made any purchase. Start shopping now!_",
        "order_info": "━━━━━━━━━━━━━━━━━━━━\n📦 *{}*\n━━━━━━━━━━━━━━━━━━━━\n🆔 Mã đơn hàng: `{}`\n📅 Ngày mua: _{}_\n💰 Giá: *{:,} {}*\n{}\n🔑 Tài khoản: `{}`\n━━━━━━━━━━━━━━━━━━━━",
        "your_new_order": "✅ *PAYMENT SUCCESSFUL!*{}\n━━━━━━━━━━━━━━━━━━━━\n🆔 Mã đơn hàng: `{}`\n📅 Ngày mua: _{}_\n📦 Gói: *{}*\n💰 Giá: *{:,} {}*\n━━━━━━━━━━━━━━━━━━━━\n🔑 *Tài khoản Canva:*\n`{}`\n━━━━━━━━━━━━━━━━━━━━\n📌 _Click button below to get login code_",
        "thank_order": "🙏 *Thank you for your order!*",
        "write_note": "Would you like to write a note to the Seller ?",
        "reply_note": "Reply with your note or reply with NIL to proceed",
        "order_list": "📋 *Your Orders*\n━━━━━━━━━━━━━━━━━━━━",
        "order_id_product_buyer": "👇 OrderID - ProductName - BuyerUserName👇",
        "click_order_delete": "Click on an Order ID of the order you want to delete: ✅",
        "no_order_store": "No Order available in your store, /start",
        
        # Messages - Payment
        "select_payment": "💡 *Select Payment Method*\n━━━━━━━━━━━━━━━━━━━━\n👇 _Choose one below_",
        "item_soldout": "❌ *Hết hàng!*\n_Sản phẩm này đã hết, vui lòng quay lại sau_",
        "send_btc": "Please send exact {} BTC (approximately {} {}) to the following Bitcoin",
        "address": "Address: `{}`",
        "stay_check_payment": "Please stay on this page and click on Check Payment Status ⌛ button until payment is confirmed",
        "error_payment_address": "Error creating payment address. Please try again later.\n\nOR Amount value is too small",
        "error_btc_convert": "Error converting amount to BTC. Please try again later.",
        "invalid_command": "Invalid command.",
        "payment_received": "✅ *Payment Received!*\n_Your payment has been confirmed_",
        "payment_successful": "✅ *Payment Successful!*",
        "payment_status": "Your payment is {} for Order ID: {}",
        "no_pending_payment": "No order found with pending payment confirmation !",
        
        # Messages - Support
        "contact_us": "💬 *Need Help?*\n━━━━━━━━━━━━━━━━━━━━\n📞 Contact: @{}\n_We're here to help you!_",
        
        # Messages - Broadcast
        "broadcast_message": "This Bot is about to Broadcast message to all Shop Users\n\n\nReply with the message you want to Broadcast: ✅",
        "no_user_store": "No user available in your store, /start",
        "broadcasting": "Now Broadcasting Message To All Users: ✅",
        "message_sent": "Message successfully sent ✅ To: @`{}`",
        "user_blocked": "User @{} has blocked the bot - {}",
        "broadcast_completed": "✅ *Broadcast Complete!*\n_Message sent to all users_",
        
        # Messages - Bitcoin Setup
        "bitcoin_added": "Bitcoin Added successfully ✅",
        "bitcoin_already_added": "{} Payment method is already added ✅",
        "reply_api_key": "Reply With Your {} API Key for your NowPayments Account (https://account.nowpayments.io/create-account?link_id=3539852335): ✅",
        "added_successfully": "Added successfully ✅",
        
        # Messages - VietQR Bank Transfer
        "bank_transfer": "Bank Transfer 🏦",
        "setup_bank": "Setup Bank Account 🏦",
        "reply_bank_code": "Reply with your bank code (e.g. VCB, TCB, MB, ACB...):\n\nCommon banks:\n• VCB - Vietcombank\n• TCB - Techcombank\n• MB - MB Bank\n• ACB - ACB\n• VPB - VPBank\n• TPB - TPBank\n• BIDV - BIDV\n• VTB - Vietinbank",
        "reply_account_number": "Reply with your bank account number:",
        "reply_account_name": "Reply with account holder name:",
        "bank_setup_success": "✅ *Bank Setup Complete!*\n━━━━━━━━━━━━━━━━━━━━\n🏦 Bank: *{}*\n💳 Account: `{}`\n👤 Name: *{}*",
        "bank_not_setup": "Bank account not configured. Please setup first.",
        "scan_qr_transfer": "📱 <b>QUÉT MÃ QR ĐỂ CHUYỂN KHOẢN</b>\n\n🏦 Ngân hàng: <b>{}</b>\n💳 Số TK: <code>{}</code>\n👤 Chủ TK: <b>{}</b>\n💰 Số tiền: <b>{:,} VND</b>\n📝 Nội dung: <code>{}</code>\n\n<i>⚠️ Vui lòng nhập đúng nội dung để hệ thống xử lý tự động</i>\n\n⏳ Mã đơn hàng: <code>{}</code>\n<i>Sau khi chuyển, hệ thống sẽ tự xác nhận trong giây lát</i>",
        "transfer_pending": "⏳ *Order Pending*\n━━━━━━━━━━━━━━━━━━━━\n🆔 Order ID: `{}`\n━━━━━━━━━━━━━━━━━━━━\n_After transferring, system will auto-confirm_",
        "cancel_order": "❌ Cancel Order",
        "order_cancelled": "❌ *Đã hủy đơn hàng* `{}`",
        "confirm_payment": "Confirm Payment ✅",
        "pending_orders": "Pending Orders 📋",
        "order_confirmed": "✅ *Order Confirmed!*\nOrder ID: `{}`",
        "no_pending_orders": "No pending orders.",
        "admin_confirm_order": "🔔 *NEW ORDER PENDING!*\n━━━━━━━━━━━━━━━━━━━━\n🆔 Order ID: `{}`\n👤 Buyer: @{}\n📦 Product: *{}*\n💰 Amount: *{:,} VND*\n📝 Content: `{}`\n━━━━━━━━━━━━━━━━━━━━\n_Click button below to confirm_",
        
        # Language
        "select_language": "🌐 Select your language / Chọn ngôn ngữ:",
        "language_changed": "✅ *Language changed to English* 🇬🇧",
    },
    
    "vi": {
        "name": "Tiếng Việt 🇻🇳",
        # Buttons - User
        "shop_items": "Mua Canva 🎨",
        "my_orders": "Đơn hàng 🛍",
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
        "switch_to_user": "Quản lý người dùng 👥",
        "add_product": "Thêm sản phẩm mới ➕",
        "restock_product": "Thêm hàng/keys 📦",
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
        "welcome_admin": "👋 *Xin chào Admin!*\n━━━━━━━━━━━━━━\nSẵn sàng quản lý cửa hàng",
        "welcome_customer": "👋 *Xin chào* {username}!\nChào mừng đến với\n━━━━━━━━━━━━━━\n🏪 *DLNDAI SHOP*\n━━━━━━━━━━━━━━\n\n💳 Mua hàng tự động 24/7\n📦 Xem lịch sử đơn dễ dàng\n💬 Hỗ trợ: @dlndai\n\n📖 Gõ /help để xem các lệnh của bot\n👇 Hoặc bấm nút bên dưới để bắt đầu",
        "wallet_balance": "Số dư ví: $",
        
        # Statistics
        "store_statistics": "📊 *THỐNG KÊ CỬA HÀNG*\n━━━━━━━━━━━━━━━━━━━━",
        "total_users": "Tổng người dùng 🙍‍♂️",
        "total_admins": "Tổng quản trị viên 🤴",
        "total_products": "Tổng sản phẩm 🏷",
        "total_orders": "Tổng đơn hàng 🛍",
        
        # Messages - General
        "choose_action": "Chọn hành động để thực hiện ✅",
        "admin_only": "⚠️ *Chỉ Admin*\nLệnh này chỉ dành cho quản trị viên",
        "error_404": "❌ *Lỗi 404*\nVui lòng thử lại với dữ liệu đúng",
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
        "attach_keys_file": "Đính kèm file chứa tài khoản Canva (.txt): ✅\n\n⚠️ Mỗi tài khoản 1 dòng (email:password)\n\n⚠️ Trả lời Skip nếu không có",
        "reply_download_link": "Nhập link hướng dẫn sử dụng Canva (nếu có):\n\n⚠️ Trả lời Skip để bỏ qua",
        "download_skipped": "Đã bỏ qua Link tải xuống ✅",
        "product_added": "✅ *Đã thêm sản phẩm!*\n━━━━━━━━━━━━━━\nBạn muốn làm gì tiếp theo?",
        "no_product": "Không có sản phẩm, vui lòng gửi lệnh /start để bắt đầu tạo sản phẩm",
        "product_id_name": "👇Mã SP --- Tên sản phẩm👇",
        "click_product_delete": "Nhấn vào Mã sản phẩm bạn muốn xóa: ✅",
        "click_product_restock": "Nhấn vào Mã sản phẩm để thêm hàng: ✅",
        "restock_method": "Chọn cách thêm hàng:\n\n1️⃣ Thêm số lượng thủ công\n2️⃣ Upload file keys",
        "add_quantity": "Thêm số lượng ➕",
        "upload_keys": "Upload file keys 📄",
        "reply_quantity": "Nhập số lượng muốn thêm:",
        "quantity_added": "✅ *Đã thêm* `{}`!\n📦 Tồn kho: `{}`",
        "keys_added": "✅ *Đã thêm* `{}` tài khoản!\n📦 Tồn kho: `{}`",
        "no_product_store": "Không có sản phẩm trong cửa hàng",
        "category_products": "Sản phẩm trong danh mục",
        "buy_now": "MUA NGAY 💰",
        "product_info": "🎨 <b>{}</b>\n\n💰 Giá: <b>{} {}</b>\n📦 Còn: <code>{}</code> tài khoản\n\n📝 <i>{}</i>",
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
        "category_deleted": "🗑️ *Đã xóa:* `{}`",
        "current_category_name": "Tên Danh mục hiện tại: {} \n\n\nTrả lời với tên Danh mục mới",
        "category_to_edit_not_found": "Không tìm thấy Danh mục để sửa !!!",
        "category_updated": "Tên danh mục đã cập nhật thành công: ✅",
        "new_category_what_next": "✅ *Đã tạo danh mục!*\n━━━━━━━━━━━━━━━━━━━━\n📁 Tên: *{}*\n\n_Bạn muốn làm gì tiếp theo?_",
        
        # Messages - Orders
        "no_order_completed": "📭 *Chưa có đơn hàng*\n_Bạn chưa mua sản phẩm nào. Bắt đầu mua sắm ngay!_",
        "order_info": "━━━━━━━━━━━━━━━━━━━━\n📦 *{}*\n━━━━━━━━━━━━━━━━━━━━\n🆔 Mã đơn hàng: `{}`\n📅 Ngày mua: _{}_\n💰 Giá: *{:,} {}*\n{}\n🔑 Tài khoản: `{}`\n━━━━━━━━━━━━━━━━━━━━",
        "your_new_order": "✅ *THANH TOÁN THÀNH CÔNG!*{}\n━━━━━━━━━━━━━━━━━━━━\n🆔 Mã đơn hàng: `{}`\n📅 Ngày mua: _{}_\n📦 Gói: *{}*\n💰 Giá: *{:,} {}*\n━━━━━━━━━━━━━━━━━━━━\n🔑 *Tài khoản Canva:*\n`{}`\n🔐 *Mật khẩu:* `dlndaicanvaedu`\n━━━━━━━━━━━━━━━━━━━━\n👇 _Bấm nút bên dưới để lấy mã xác thực cho email (dùng cho việc đăng nhập, đổi mail, v.v...)_",
        "thank_order": "🙏 *Cảm ơn bạn đã mua hàng!*",
        "write_note": "Bạn có muốn viết ghi chú cho Người bán không ?",
        "reply_note": "Trả lời với ghi chú hoặc trả lời NIL để tiếp tục",
        "order_list": "📋 *Đơn hàng của bạn*\n━━━━━━━━━━━━━━━━━━━━",
        "order_id_product_buyer": "👇 Mã ĐH - Tên SP - Người mua👇",
        "click_order_delete": "Nhấn vào Mã đơn hàng bạn muốn xóa: ✅",
        "no_order_store": "Không có đơn hàng trong cửa hàng, /start",
        
        # Messages - Payment
        "select_payment": "💡 *Chọn phương thức thanh toán*\n━━━━━━━━━━━━━━━━━━━━\n👇 _Chọn một trong các nút bên dưới_",
        "item_soldout": "❌ *Hết hàng!*\n_Sản phẩm này đã hết, vui lòng quay lại sau_",
        "send_btc": "Vui lòng gửi chính xác {} BTC (khoảng {} {}) đến địa chỉ Bitcoin sau",
        "address": "Địa chỉ: `{}`",
        "stay_check_payment": "Vui lòng ở lại trang này và nhấn nút Kiểm tra thanh toán ⌛ cho đến khi thanh toán được xác nhận",
        "error_payment_address": "Lỗi tạo địa chỉ thanh toán. Vui lòng thử lại sau.\n\nHOẶC Số tiền quá nhỏ",
        "error_btc_convert": "Lỗi chuyển đổi sang BTC. Vui lòng thử lại sau.",
        "invalid_command": "Lệnh không hợp lệ.",
        "payment_received": "✅ *Đã nhận thanh toán!*\n_Thanh toán của bạn đã được xác nhận_",
        "payment_successful": "✅ *Thanh toán thành công!*",
        "payment_status": "Thanh toán của bạn đang {} cho Mã ĐH: {}",
        "no_pending_payment": "Không tìm thấy đơn hàng đang chờ xác nhận thanh toán !",
        
        # Messages - Support
        "contact_us": "💬 *Cần hỗ trợ?*\n━━━━━━━━━━━━━━━━━━━━\n📞 Liên hệ: @{}",
        
        # Messages - Broadcast
        "broadcast_message": "Bot sẽ gửi thông báo đến tất cả Người dùng\n\n\nTrả lời với nội dung bạn muốn gửi: ✅",
        "no_user_store": "Không có người dùng trong cửa hàng, /start",
        "broadcasting": "Đang gửi thông báo đến tất cả Người dùng: ✅",
        "message_sent": "Tin nhắn đã gửi thành công ✅ Đến: @`{}`",
        "user_blocked": "Người dùng @{} đã chặn bot - {}",
        "broadcast_completed": "✅ *Gửi thông báo hoàn tất!*\n_Đã gửi tin nhắn đến tất cả người dùng_",
        
        # Messages - Bitcoin Setup
        "bitcoin_added": "Bitcoin đã thêm thành công ✅",
        "bitcoin_already_added": "Phương thức thanh toán {} đã được thêm ✅",
        "reply_api_key": "Trả lời với API Key {} cho tài khoản NowPayments (https://account.nowpayments.io/create-account?link_id=3539852335): ✅",
        "added_successfully": "Đã thêm thành công ✅",
        
        # Messages - VietQR Bank Transfer
        "bank_transfer": "Chuyển khoản 🏦",
        "setup_bank": "Cài đặt tài khoản 🏦",
        "reply_bank_code": "Nhập mã ngân hàng (VD: VCB, TCB, MB, ACB...):\n\nCác ngân hàng phổ biến:\n• VCB - Vietcombank\n• TCB - Techcombank\n• MB - MB Bank\n• ACB - ACB\n• VPB - VPBank\n• TPB - TPBank\n• BIDV - BIDV\n• VTB - Vietinbank",
        "reply_account_number": "Nhập số tài khoản ngân hàng:",
        "reply_account_name": "Nhập tên chủ tài khoản:",
        "bank_setup_success": "✅ *Cài đặt thành công!*\n━━━━━━━━━━━━━━━━━━━━\n🏦 Ngân hàng: *{}*\n💳 Số TK: `{}`\n👤 Chủ TK: *{}*",
        "bank_not_setup": "Chưa cài đặt tài khoản ngân hàng. Vui lòng cài đặt trước.",
        "scan_qr_transfer": "📱 <b>QUÉT MÃ QR ĐỂ CHUYỂN KHOẢN</b>\n\n🏦 Ngân hàng: <b>{}</b>\n💳 Số TK: <code>{}</code>\n👤 Chủ TK: <b>{}</b>\n💰 Số tiền: <b>{:,} VND</b>\n📝 Nội dung: <code>{}</code>\n\n<i>⚠️ Vui lòng nhập đúng nội dung để hệ thống xử lý tự động</i>\n\n⏳ Mã đơn hàng: <code>{}</code>\n<i>Sau khi chuyển, hệ thống sẽ tự xác nhận trong giây lát</i>",
        "transfer_pending": "⏳ *Đơn hàng đang chờ*\n━━━━━━━━━━━━━━━━━━━━\n🆔 Mã đơn hàng: `{}`\n━━━━━━━━━━━━━━━━━━━━\n_Sau khi chuyển khoản, hệ thống sẽ tự xác nhận_",
        "cancel_order": "❌ Hủy đơn",
        "order_cancelled": "❌ *Đã hủy đơn hàng* `{}`",
        "confirm_payment": "Xác nhận thanh toán ✅",
        "pending_orders": "Đơn chờ xác nhận 📋",
        "order_confirmed": "✅ *Đã xác nhận đơn hàng!*\nMã đơn hàng: `{}`",
        "no_pending_orders": "Không có đơn hàng chờ xác nhận.",
        "admin_confirm_order": "🔔 *ĐƠN HÀNG MỚI!*\n━━━━━━━━━━━━━━━━━━━━\n🆔 Mã đơn hàng: `{}`\n👤 Người mua: @{}\n📦 Sản phẩm: *{}*\n💰 Số tiền: *{:,} VND*\n📝 Nội dung CK: `{}`\n━━━━━━━━━━━━━━━━━━━━\n_Nhấn nút bên dưới để xác nhận_",
        
        # Language
        "select_language": "🌐 Select your language / Chọn ngôn ngữ:",
        "language_changed": "✅ *Đã chuyển sang Tiếng Việt* 🇻🇳",
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
