-- ============================================
-- SUPABASE TABLES SETUP
-- Run this in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/bjukgqfynvzhyfkjbayo/sql
-- ============================================

-- Users table
CREATE TABLE IF NOT EXISTS shop_users (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    wallet INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Admins table
CREATE TABLE IF NOT EXISTS shop_admins (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    wallet INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Products table
CREATE TABLE IF NOT EXISTS shop_products (
    id SERIAL PRIMARY KEY,
    productnumber BIGINT UNIQUE NOT NULL,
    admin_id BIGINT NOT NULL,
    username TEXT,
    productname TEXT NOT NULL,
    productdescription TEXT,
    productprice INTEGER DEFAULT 0,
    productimagelink TEXT,
    productdownloadlink TEXT,
    productkeysfile TEXT,
    productquantity INTEGER DEFAULT 0,
    productcategory TEXT DEFAULT 'Default Category',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Orders table
CREATE TABLE IF NOT EXISTS shop_orders (
    id SERIAL PRIMARY KEY,
    buyerid BIGINT NOT NULL,
    buyerusername TEXT,
    productname TEXT NOT NULL,
    productprice TEXT NOT NULL,
    orderdate TIMESTAMP DEFAULT NOW(),
    paidmethod TEXT DEFAULT 'NO',
    productdownloadlink TEXT,
    productkeys TEXT,
    buyercomment TEXT,
    ordernumber BIGINT UNIQUE NOT NULL,
    productnumber BIGINT NOT NULL,
    payment_id TEXT
);

-- Categories table
CREATE TABLE IF NOT EXISTS shop_categories (
    id SERIAL PRIMARY KEY,
    categorynumber BIGINT UNIQUE NOT NULL,
    categoryname TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Payment methods table
CREATE TABLE IF NOT EXISTS payment_methods (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT,
    username TEXT,
    method_name TEXT UNIQUE NOT NULL,
    token_keys_clientid TEXT,
    secret_keys TEXT,
    activated TEXT DEFAULT 'NO',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Canva accounts table
CREATE TABLE IF NOT EXISTS canva_accounts (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    authkey TEXT NOT NULL,
    buyer_id BIGINT DEFAULT NULL,
    order_number BIGINT DEFAULT NULL,
    status TEXT DEFAULT 'available',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Promotions table
CREATE TABLE IF NOT EXISTS promotions (
    id SERIAL PRIMARY KEY,
    promo_name TEXT UNIQUE NOT NULL,
    is_active INTEGER DEFAULT 0,
    sold_count INTEGER DEFAULT 0,
    max_count INTEGER DEFAULT 10,
    started_at TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert default promotion
INSERT INTO promotions (promo_name, is_active, sold_count, max_count)
VALUES ('buy1get1', 0, 0, 10)
ON CONFLICT (promo_name) DO NOTHING;

-- ============================================
-- ROW LEVEL SECURITY POLICIES
-- These allow the anon key to access all data
-- ============================================

-- Enable RLS
ALTER TABLE shop_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE shop_admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE shop_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE shop_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE shop_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_methods ENABLE ROW LEVEL SECURITY;
ALTER TABLE canva_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE promotions ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (to avoid conflicts)
DROP POLICY IF EXISTS "Allow all" ON shop_users;
DROP POLICY IF EXISTS "Allow all" ON shop_admins;
DROP POLICY IF EXISTS "Allow all" ON shop_products;
DROP POLICY IF EXISTS "Allow all" ON shop_orders;
DROP POLICY IF EXISTS "Allow all" ON shop_categories;
DROP POLICY IF EXISTS "Allow all" ON payment_methods;
DROP POLICY IF EXISTS "Allow all" ON canva_accounts;
DROP POLICY IF EXISTS "Allow all" ON promotions;

-- Create policies to allow all operations
CREATE POLICY "Allow all" ON shop_users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON shop_admins FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON shop_products FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON shop_orders FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON shop_categories FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON payment_methods FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON canva_accounts FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON promotions FOR ALL USING (true) WITH CHECK (true);

-- ============================================
-- SAMPLE DATA (Optional - uncomment if needed)
-- ============================================

-- Insert sample product
-- INSERT INTO shop_products (productnumber, admin_id, productname, productprice, productquantity, productcategory)
-- VALUES (1, 5996278430, 'Canva Edu Admin', 30000, 100, 'Canva');

-- INSERT INTO shop_products (productnumber, admin_id, productname, productprice, productquantity, productcategory)
-- VALUES (2, 5996278430, 'Up lại Canva Edu', 20000, 100, 'Canva');
