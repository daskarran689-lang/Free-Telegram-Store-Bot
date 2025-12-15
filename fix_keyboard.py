import re

with open('store_main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix cases where user_id is used instead of id
replacements = [
    ('create_main_keyboard(lang, id))', 'user_id, "❌ Bạn chưa có', 'create_main_keyboard(lang, user_id))'),
    ('create_main_keyboard(lang, id))', 'user_id, "❌ Bạn không có', 'create_main_keyboard(lang, user_id))'),
    ('create_main_keyboard(lang, id))', 'user_id, f"✅ Đã xóa', 'create_main_keyboard(lang, user_id))'),
    ('create_main_keyboard(lang, id))', 'user_id, f"❌ Không thể xóa', 'create_main_keyboard(lang, user_id))'),
    ('create_main_keyboard(lang, id))', 'user_id, f"❌ Không tìm thấy thông tin', 'create_main_keyboard(lang, user_id))'),
    ('create_main_keyboard(lang, id))', 'user_id, "❌ Không tìm thấy tài khoản', 'create_main_keyboard(lang, user_id))'),
    ('create_main_keyboard(lang, id))', 'user_id, get_text("item_soldout"', 'create_main_keyboard(lang, user_id))'),
    ('create_main_keyboard(lang, id))', 'user_id, get_text("bank_not_setup"', 'create_main_keyboard(lang, user_id))'),
]

# Simple approach: find lines with user_id and create_main_keyboard(lang, id) and fix them
lines = content.split('\n')
new_lines = []
for line in lines:
    if 'user_id' in line and 'create_main_keyboard(lang, id)' in line:
        line = line.replace('create_main_keyboard(lang, id)', 'create_main_keyboard(lang, user_id)')
    new_lines.append(line)

content = '\n'.join(new_lines)

with open('store_main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
