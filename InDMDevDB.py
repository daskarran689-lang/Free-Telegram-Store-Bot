import sqlite3
from datetime import datetime
import threading
import logging
import os
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', '')

db_lock = threading.Lock()

if DATABASE_URL and DATABASE_URL.startswith('postgres'):
    # Use PostgreSQL with psycopg3
    import psycopg
    from psycopg import OperationalError
    from psycopg_pool import ConnectionPool
    
    USE_POSTGRES = True
    logger.info("Using PostgreSQL database")
    
    # Connection pool for better performance
    try:
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            timeout=10,
            kwargs={"autocommit": True, "options": "-c statement_timeout=10000"}
        )
        logger.info("Connection pool created")
    except Exception as e:
        logger.warning(f"Pool creation failed, using single connections: {e}")
        _pool = None
    
    @contextmanager
    def get_db_connection():
        """Context manager for PostgreSQL - uses pool or creates new connection"""
        conn = None
        try:
            if _pool:
                conn = _pool.getconn()
                yield conn
                _pool.putconn(conn)
                conn = None  # Don't close pooled connection
            else:
                conn = psycopg.connect(
                    DATABASE_URL, 
                    connect_timeout=5,
                    options="-c statement_timeout=10000",
                    autocommit=True
                )
                yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn and not conn.closed:
                conn.close()
    
    # For backward compatibility - create initial connection
    def get_connection():
        if _pool:
            return _pool.getconn()
        return psycopg.connect(
            DATABASE_URL, 
            connect_timeout=5,
            options="-c statement_timeout=10000",
            autocommit=True
        )
    
    db_connection = get_connection()
    cursor = db_connection.cursor()
else:
    # Use SQLite (local development)
    USE_POSTGRES = False
    DB_FILE = os.getenv('DATABASE_PATH', 'InDMDevDBShop.db')
    logger.info(f"Using SQLite database: {DB_FILE}")
    
    db_connection = sqlite3.connect(DB_FILE, check_same_thread=False)
    db_connection.row_factory = sqlite3.Row
    cursor = db_connection.cursor()
    
    @contextmanager
    def get_db_connection():
        """Context manager for SQLite - uses global connection"""
        yield db_connection

# Backward compatibility aliases
DBConnection = db_connection
connected = cursor

# Helper class to auto-convert SQLite ? to PostgreSQL %s
class DBCursor:
    def __init__(self, cursor):
        self._cursor = cursor
    
    def execute(self, query, params=None):
        if USE_POSTGRES:
            # Convert ? to %s for PostgreSQL
            query = query.replace("?", "%s")
        if params:
            self._cursor.execute(query, params)
        else:
            self._cursor.execute(query)
        return self._cursor
    
    def fetchone(self):
        return self._cursor.fetchone()
    
    def fetchall(self):
        return self._cursor.fetchall()

# Replace connected with wrapper
connected = DBCursor(cursor)

def execute_with_new_connection(query, params=None, fetch='none'):
    """Execute query with a fresh connection (prevents connection stuck)"""
    if USE_POSTGRES:
        query = query.replace("?", "%s")
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        
        if fetch == 'one':
            return cur.fetchone()
        elif fetch == 'all':
            return cur.fetchall()
        return None

class CreateTables:
    """Database table creation and management"""
    
    @staticmethod
    def create_all_tables():
        """Create all necessary database tables"""
        global db_connection, cursor
        
        # Reconnect for PostgreSQL
        if USE_POSTGRES:
            db_connection = get_connection()
            cursor = db_connection.cursor()
        
        # Use SERIAL for PostgreSQL, INTEGER PRIMARY KEY AUTOINCREMENT for SQLite
        auto_increment = "SERIAL" if USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
        
        try:
            with db_lock:
                # Create ShopUserTable
                if USE_POSTGRES:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS ShopUserTable(
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT UNIQUE NOT NULL,
                        username TEXT,
                        wallet INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                else:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS ShopUserTable(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE NOT NULL,
                        username TEXT,
                        wallet INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                
                # Create ShopAdminTable
                if USE_POSTGRES:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS ShopAdminTable(
                        id SERIAL PRIMARY KEY,
                        admin_id BIGINT UNIQUE NOT NULL,
                        username TEXT,
                        wallet INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                else:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS ShopAdminTable(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        admin_id INTEGER UNIQUE NOT NULL,
                        username TEXT,
                        wallet INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")

                # Create ShopProductTable
                if USE_POSTGRES:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS ShopProductTable(
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
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                else:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS ShopProductTable(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        productnumber INTEGER UNIQUE NOT NULL,
                        admin_id INTEGER NOT NULL,
                        username TEXT,
                        productname TEXT NOT NULL,
                        productdescription TEXT,
                        productprice INTEGER DEFAULT 0,
                        productimagelink TEXT,
                        productdownloadlink TEXT,
                        productkeysfile TEXT,
                        productquantity INTEGER DEFAULT 0,
                        productcategory TEXT DEFAULT 'Default Category',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (admin_id) REFERENCES ShopAdminTable(admin_id)
                    )""")

                # Create ShopOrderTable
                if USE_POSTGRES:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS ShopOrderTable(
                        id SERIAL PRIMARY KEY,
                        buyerid BIGINT NOT NULL,
                        buyerusername TEXT,
                        productname TEXT NOT NULL,
                        productprice TEXT NOT NULL,
                        orderdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        paidmethod TEXT DEFAULT 'NO',
                        productdownloadlink TEXT,
                        productkeys TEXT,
                        buyercomment TEXT,
                        ordernumber BIGINT UNIQUE NOT NULL,
                        productnumber BIGINT NOT NULL,
                        payment_id TEXT
                    )""")
                else:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS ShopOrderTable(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        buyerid INTEGER NOT NULL,
                        buyerusername TEXT,
                        productname TEXT NOT NULL,
                        productprice TEXT NOT NULL,
                        orderdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        paidmethod TEXT DEFAULT 'NO',
                        productdownloadlink TEXT,
                        productkeys TEXT,
                        buyercomment TEXT,
                        ordernumber INTEGER UNIQUE NOT NULL,
                        productnumber INTEGER NOT NULL,
                        payment_id TEXT,
                        FOREIGN KEY (buyerid) REFERENCES ShopUserTable(user_id),
                        FOREIGN KEY (productnumber) REFERENCES ShopProductTable(productnumber)
                    )""")
                
                # Create ShopCategoryTable
                if USE_POSTGRES:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS ShopCategoryTable(
                        id SERIAL PRIMARY KEY,
                        categorynumber BIGINT UNIQUE NOT NULL,
                        categoryname TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                else:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS ShopCategoryTable(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        categorynumber INTEGER UNIQUE NOT NULL,
                        categoryname TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                
                # Create PaymentMethodTable
                if USE_POSTGRES:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS PaymentMethodTable(
                        id SERIAL PRIMARY KEY,
                        admin_id BIGINT,
                        username TEXT,
                        method_name TEXT UNIQUE NOT NULL,
                        token_keys_clientid TEXT,
                        secret_keys TEXT,
                        activated TEXT DEFAULT 'NO',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                else:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS PaymentMethodTable(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        admin_id INTEGER,
                        username TEXT,
                        method_name TEXT UNIQUE NOT NULL,
                        token_keys_clientid TEXT,
                        secret_keys TEXT,
                        activated TEXT DEFAULT 'NO',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                
                # Create CanvaAccountTable for storing Canva accounts with authkey
                if USE_POSTGRES:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS CanvaAccountTable(
                        id SERIAL PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        authkey TEXT NOT NULL,
                        buyer_id BIGINT DEFAULT NULL,
                        order_number BIGINT DEFAULT NULL,
                        status TEXT DEFAULT 'available',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                else:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS CanvaAccountTable(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE NOT NULL,
                        authkey TEXT NOT NULL,
                        buyer_id INTEGER DEFAULT NULL,
                        order_number INTEGER DEFAULT NULL,
                        status TEXT DEFAULT 'available',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                
                # Create PromotionTable for Buy 1 Get 1 promotion
                if USE_POSTGRES:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS PromotionTable(
                        id SERIAL PRIMARY KEY,
                        promo_name TEXT UNIQUE NOT NULL,
                        is_active INTEGER DEFAULT 0,
                        sold_count INTEGER DEFAULT 0,
                        max_count INTEGER DEFAULT 10,
                        started_at TIMESTAMP DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                else:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS PromotionTable(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        promo_name TEXT UNIQUE NOT NULL,
                        is_active INTEGER DEFAULT 0,
                        sold_count INTEGER DEFAULT 0,
                        max_count INTEGER DEFAULT 10,
                        started_at TIMESTAMP DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                
                if not USE_POSTGRES:
                    db_connection.commit()
                logger.info("All database tables created successfully")
                
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            if not USE_POSTGRES:
                db_connection.rollback()
            raise
        
# Initialize tables
CreateTables.create_all_tables()

# Helper function to get placeholder for SQL queries
def get_placeholder():
    return "%s" if USE_POSTGRES else "?"

def execute_query(query, params=None):
    """Execute query with proper placeholder conversion"""
    global db_connection, cursor
    if USE_POSTGRES:
        # Reconnect if needed
        try:
            cursor.execute("SELECT 1")
        except:
            db_connection = get_connection()
            cursor = db_connection.cursor()
        # Convert ? to %s for PostgreSQL
        query = query.replace("?", "%s")
        # Convert INSERT OR IGNORE to INSERT ... ON CONFLICT DO NOTHING
        query = query.replace("INSERT OR IGNORE", "INSERT")
        if "INSERT" in query and "ON CONFLICT" not in query:
            # Add ON CONFLICT DO NOTHING for INSERT statements
            if "VALUES" in query:
                query = query.rstrip(")") + ") ON CONFLICT DO NOTHING"
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    return cursor

class CreateDatas:
    """Database data creation and insertion operations"""
    
    @staticmethod
    def add_user(user_id, username):
        """Add a new user to the database"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                if USE_POSTGRES:
                    cur.execute(
                        "INSERT INTO ShopUserTable (user_id, username, wallet) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING",
                        (user_id, username, 0)
                    )
                else:
                    cur.execute(
                        "INSERT OR IGNORE INTO ShopUserTable (user_id, username, wallet) VALUES (?, ?, ?)",
                        (user_id, username, 0)
                    )
                    conn.commit()
                logger.info(f"User added: {username} (ID: {user_id})")
                return True
        except Exception as e:
            logger.error(f"Error adding user {username}: {e}")
            return False
            
    @staticmethod
    def add_admin(admin_id, username):
        """Add a new admin to the database"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                if USE_POSTGRES:
                    cur.execute(
                        "INSERT INTO ShopAdminTable (admin_id, username, wallet) VALUES (%s, %s, %s) ON CONFLICT (admin_id) DO NOTHING",
                        (admin_id, username, 0)
                    )
                else:
                    cur.execute(
                        "INSERT OR IGNORE INTO ShopAdminTable (admin_id, username, wallet) VALUES (?, ?, ?)",
                        (admin_id, username, 0)
                    )
                    conn.commit()
                logger.info(f"Admin added: {username} (ID: {admin_id})")
                return True
        except Exception as e:
            logger.error(f"Error adding admin {username}: {e}")
            return False

    @staticmethod
    def add_product(productnumber, admin_id, username):
        """Add a new product to the database"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                if USE_POSTGRES:
                    cur.execute("""
                        INSERT INTO ShopProductTable 
                        (productnumber, admin_id, username, productname, productdescription, 
                         productprice, productimagelink, productdownloadlink, productkeysfile, 
                         productquantity, productcategory) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (productnumber, admin_id, username, 'NIL', 'NIL', 0, 'NIL', 
                          'https://nil.nil', 'NIL', 0, 'Default Category'))
                else:
                    cur.execute("""
                        INSERT INTO ShopProductTable 
                        (productnumber, admin_id, username, productname, productdescription, 
                         productprice, productimagelink, productdownloadlink, productkeysfile, 
                         productquantity, productcategory) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (productnumber, admin_id, username, 'NIL', 'NIL', 0, 'NIL', 
                          'https://nil.nil', 'NIL', 0, 'Default Category'))
                    conn.commit()
                logger.info(f"Product {productnumber} added by admin {username}")
                return True
        except Exception as e:
            logger.error(f"Error adding product {productnumber}: {e}")
            return False
    
    # Backward compatibility methods
    @staticmethod
    def AddAuser(user_id, username):
        """Backward compatibility wrapper for add_user"""
        return CreateDatas.add_user(user_id, username)
    
    @staticmethod
    def AddAdmin(admin_id, username):
        """Backward compatibility wrapper for add_admin"""
        return CreateDatas.add_admin(admin_id, username)
    
    @staticmethod
    def AddProduct(productnumber, admin_id, username):
        """Backward compatibility wrapper for add_product"""
        return CreateDatas.add_product(productnumber, admin_id, username)

    @staticmethod
    def AddOrder(buyer_id, username, productname, productprice, orderdate, paidmethod, 
                 productdownloadlink, productkeys, ordernumber, productnumber, payment_id):
        """Add a new order to the database"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                if USE_POSTGRES:
                    cur.execute("""
                        INSERT INTO ShopOrderTable 
                        (buyerid, buyerusername, productname, productprice, orderdate, 
                         paidmethod, productdownloadlink, productkeys, buyercomment, 
                         ordernumber, productnumber, payment_id) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (buyer_id, username, productname, productprice, orderdate, 
                          paidmethod, productdownloadlink, productkeys, 'NIL', 
                          ordernumber, productnumber, payment_id))
                else:
                    cur.execute("""
                        INSERT INTO ShopOrderTable 
                        (buyerid, buyerusername, productname, productprice, orderdate, 
                         paidmethod, productdownloadlink, productkeys, buyercomment, 
                         ordernumber, productnumber, payment_id) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (buyer_id, username, productname, productprice, orderdate, 
                          paidmethod, productdownloadlink, productkeys, 'NIL', 
                          ordernumber, productnumber, payment_id))
                    conn.commit()
                logger.info(f"Order {ordernumber} added for user {username}")
                return True
        except Exception as e:
            logger.error(f"Error adding order {ordernumber}: {e}")
            return False

    def AddCategory(categorynumber, categoryname):
        try:
            query = "INSERT INTO ShopCategoryTable (categorynumber, categoryname) VALUES (?, ?)"
            execute_with_new_connection(query, (categorynumber, categoryname))
        except Exception as e:
            logger.error(f"Error adding category: {e}")

    def AddEmptyRow():
        query = "INSERT INTO PaymentMethodTable (admin_id, username, method_name, activated) VALUES ('None', 'None', 'None', 'None')"
        execute_with_new_connection(query)
    
    def AddCryptoPaymentMethod(id, username, token_keys_clientid, secret_keys, method_name):
        try:
            query = f"UPDATE PaymentMethodTable SET admin_id = ?, username = ?, token_keys_clientid = ?, secret_keys = ?, activated = 'NO' WHERE method_name = '{method_name}'"
            execute_with_new_connection(query, (id, username, token_keys_clientid, secret_keys))
        except Exception as e:
            logger.error(f"Error adding crypto payment: {e}")

    def UpdateOrderConfirmed(paidmethod, ordernumber):
        try:
            query = "UPDATE ShopOrderTable SET paidmethod = ? WHERE ordernumber = ?"
            execute_with_new_connection(query, (paidmethod, ordernumber))
        except Exception as e:
            logger.error(f"Error updating order confirmed: {e}")

    def UpdatePaymentMethodToken(id, username, token_keys_clientid, method_name):
        try:
            query = f"UPDATE PaymentMethodTable SET admin_id = '{id}', username = '{username}', token_keys_clientid = '{token_keys_clientid}' WHERE method_name = '{method_name}'"
            execute_with_new_connection(query)
        except Exception as e:
            logger.error(f"Error updating payment token: {e}")

    def UpdatePaymentMethodSecret(id, username, secret_keys, method_name):
        try:
            query = f"UPDATE PaymentMethodTable SET admin_id = '{id}', username = '{username}', secret_keys = '{secret_keys}' WHERE method_name = '{method_name}'"
            execute_with_new_connection(query)
        except Exception as e:
            logger.error(f"Error updating payment secret: {e}")

    def Update_A_Category(categoryname, categorynumber):
        try:
            query = "UPDATE ShopCategoryTable SET categoryname = ? WHERE categorynumber = ?"
            execute_with_new_connection(query, (categoryname, categorynumber))
        except Exception as e:
            logger.error(f"Error updating category: {e}")

    def UpdateOrderComment(buyercomment, ordernumber):
        try:
            query = "UPDATE ShopOrderTable SET buyercomment = ? WHERE ordernumber = ?"
            execute_with_new_connection(query, (buyercomment, ordernumber))
        except Exception as e:
            logger.error(f"Error updating order comment: {e}")

    def UpdateOrderPaymentMethod(paidmethod, ordernumber):
        try:
            query = "UPDATE ShopOrderTable SET paidmethod = ? WHERE ordernumber = ?"
            execute_with_new_connection(query, (paidmethod, ordernumber))
        except Exception as e:
            logger.error(f"Error updating order payment method: {e}")

    def UpdateOrderPurchasedKeys(productkeys, ordernumber):
        try:
            query = "UPDATE ShopOrderTable SET productkeys = ? WHERE ordernumber = ?"
            execute_with_new_connection(query, (productkeys, ordernumber))
        except Exception as e:
            logger.error(f"Error updating order keys: {e}")

    def AddPaymentMethod(id, username, method_name):
        query = "INSERT INTO PaymentMethodTable (admin_id, username, method_name, activated) VALUES (?, ?, ?, 'YES')"
        execute_with_new_connection(query, (id, username, method_name))

    def UpdateProductName(productname, productnumber):
        try:
            query = "UPDATE ShopProductTable SET productname = ? WHERE productnumber = ?"
            execute_with_new_connection(query, (productname, productnumber))
        except Exception as e:
            logger.error(f"Error updating product name: {e}")

    def UpdateProductDescription(productdescription, productnumber):
        try:
            query = "UPDATE ShopProductTable SET productdescription = ? WHERE productnumber = ?"
            execute_with_new_connection(query, (productdescription, productnumber))
        except Exception as e:
            logger.error(f"Error updating product description: {e}")
    
    def UpdateProductPrice(productprice, productnumber):
        try:
            query = "UPDATE ShopProductTable SET productprice = ? WHERE productnumber = ?"
            execute_with_new_connection(query, (productprice, productnumber))
        except Exception as e:
            logger.error(f"Error updating product price: {e}")
    
    def UpdateProductproductimagelink(productimagelink, productnumber):
        try:
            query = "UPDATE ShopProductTable SET productimagelink = ? WHERE productnumber = ?"
            execute_with_new_connection(query, (productimagelink, productnumber))
        except Exception as e:
            logger.error(f"Error updating product image: {e}")

    def UpdateProductproductdownloadlink(productdownloadlink, productnumber):
        try:
            query = "UPDATE ShopProductTable SET productdownloadlink = ? WHERE productnumber = ?"
            execute_with_new_connection(query, (productdownloadlink, productnumber))
        except Exception as e:
            logger.error(f"Error updating product download link: {e}")
    
    def UpdateProductKeysFile(productkeysfile, productnumber):
        try:
            query = "UPDATE ShopProductTable SET productkeysfile = ? WHERE productnumber = ?"
            execute_with_new_connection(query, (productkeysfile, productnumber))
        except Exception as e:
            logger.error(f"Error updating product keys file: {e}")
    
    def UpdateProductQuantity(productquantity, productnumber):
        try:
            query = "UPDATE ShopProductTable SET productquantity = ? WHERE productnumber = ?"
            execute_with_new_connection(query, (productquantity, productnumber))
        except Exception as e:
            logger.error(f"Error updating product quantity: {e}")
    
    def UpdateProductCategory(productcategory, productnumber):
        try:
            query = "UPDATE ShopProductTable SET productcategory = ? WHERE productnumber = ?"
            execute_with_new_connection(query, (productcategory, productnumber))
        except Exception as e:
            logger.error(f"Error updating product category: {e}")

    def Update_All_ProductCategory(new_category, productcategory):
        try:
            query = "UPDATE ShopProductTable SET productcategory = ? WHERE productcategory = ?"
            execute_with_new_connection(query, (new_category, productcategory))
        except Exception as e:
            logger.error(f"Error updating all product categories: {e}")

class GetDataFromDB:
    """Database query operations"""
    
    @staticmethod
    def GetUserWalletInDB(userid):
        """Get user wallet balance from database"""
        try:
            result = execute_with_new_connection(
                "SELECT wallet FROM ShopUserTable WHERE user_id = ?", 
                (userid,), 
                fetch='one'
            )
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting user wallet for {userid}: {e}")
            return 0
        
    def GetUserNameInDB(userid):
        try:
            result = execute_with_new_connection(
                f"SELECT username FROM ShopUserTable WHERE user_id = '{userid}'",
                fetch='one'
            )
            return result[0] if result else ""
        except Exception as e:
            logger.error(f"Error getting username: {e}")
            return ""
        
    def GetAdminNameInDB(userid):
        try:
            result = execute_with_new_connection(
                f"SELECT username FROM ShopAdminTable WHERE admin_id = '{userid}'",
                fetch='one'
            )
            return result[0] if result else ""
        except Exception as e:
            logger.error(f"Error getting admin name: {e}")
            return ""
        
    def GetUserIDsInDB():
        try:
            return execute_with_new_connection(
                "SELECT user_id FROM ShopUserTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting user IDs: {e}")
            return None

    def GetProductName(productnumber):
        try:
            result = execute_with_new_connection(
                f"SELECT productname FROM ShopProductTable WHERE productnumber = '{productnumber}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting product name: {e}")
            return None

    def GetProductDescription(productnumber):
        try:
            result = execute_with_new_connection(
                f"SELECT productdescription FROM ShopProductTable WHERE productnumber = '{productnumber}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting product description: {e}")
            return None

    def GetProductPrice(productnumber):
        try:
            result = execute_with_new_connection(
                f"SELECT productprice FROM ShopProductTable WHERE productnumber = '{productnumber}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting product price: {e}")
            return None
        
    def GetProductImageLink(productnumber):
        try:
            result = execute_with_new_connection(
                f"SELECT productimagelink FROM ShopProductTable WHERE productnumber = '{productnumber}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting product image: {e}")
            return None
    
    def GetProductDownloadLink(productnumber):
        try:
            result = execute_with_new_connection(
                f"SELECT productdownloadlink FROM ShopProductTable WHERE productnumber = '{productnumber}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting product download link: {e}")
            return None

    def GetProductNumber(productnumber):
        try:
            result = execute_with_new_connection(
                f"SELECT productnumber FROM ShopProductTable WHERE productnumber = '{productnumber}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting product number: {e}")
            return None

    def GetProductQuantity(productnumber):
        try:
            result = execute_with_new_connection(
                f"SELECT productquantity FROM ShopProductTable WHERE productnumber = '{productnumber}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting product quantity: {e}")
            return None

    def GetProduct_A_Category(productnumber):
        try:
            result = execute_with_new_connection(
                f"SELECT productcategory FROM ShopProductTable WHERE productnumber = '{productnumber}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting product category: {e}")
            return None

    def Get_A_CategoryName(categorynumber):
        try:
            result = execute_with_new_connection(
                f"SELECT DISTINCT categoryname FROM ShopCategoryTable WHERE categorynumber = '{categorynumber}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting category name: {e}")
            return None

    def GetCategoryIDsInDB():
        try:
            return execute_with_new_connection(
                "SELECT categorynumber, categoryname FROM ShopCategoryTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting category IDs: {e}")
            return None

    def GetCategoryNumProduct(productcategory):
        try:
            return execute_with_new_connection(
                f"SELECT COUNT(*) FROM ShopProductTable WHERE productcategory = '{productcategory}'",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting category product count: {e}")
            return None
        
    def GetProduct_A_AdminID(productnumber):
        try:
            result = execute_with_new_connection(
                f"SELECT admin_id FROM ShopProductTable WHERE productnumber = '{productnumber}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting product admin ID: {e}")
            return None

    def GetAdminIDsInDB():
        try:
            return execute_with_new_connection(
                "SELECT admin_id FROM ShopAdminTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting admin IDs: {e}")
            return None

    def GetAdminUsernamesInDB():
        try:
            return execute_with_new_connection(
                "SELECT username FROM ShopAdminTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting admin usernames: {e}")
            return None

    def GetProductNumberName():
        try:
            return execute_with_new_connection(
                "SELECT DISTINCT productnumber, productname FROM ShopProductTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting product number/name: {e}")
            return None

    def GetProductInfos():
        try:
            return execute_with_new_connection(
                "SELECT DISTINCT productnumber, productname, productprice FROM ShopProductTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting product infos: {e}")
            return None

    def GetProductInfo():
        try:
            return execute_with_new_connection(
                "SELECT DISTINCT productnumber, productname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory FROM ShopProductTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting product info: {e}")
            return None

    def GetProductInfoByCTGName(productcategory):
        try:
            return execute_with_new_connection(
                f"SELECT DISTINCT productnumber, productname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory FROM ShopProductTable WHERE productcategory = '{productcategory}'",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting product info by category: {e}")
            return None
        
    def GetProductInfoByPName(productnumber):
        try:
            return execute_with_new_connection(
                f"SELECT DISTINCT productnumber, productname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory FROM ShopProductTable WHERE productnumber = '{productnumber}'",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting product info by number: {e}")
            return None
        
    def GetUsersInfo():
        try:
            return execute_with_new_connection(
                "SELECT DISTINCT user_id, username, wallet FROM ShopUserTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting users info: {e}")
            return None
        
    def AllUsers():
        try:
            return execute_with_new_connection(
                "SELECT COUNT(user_id) FROM ShopUserTable",
                fetch='all'
            ) or 0
        except Exception as e:
            logger.error(f"Error counting users: {e}")
            return 0
    
    def AllAdmins():
        try:
            return execute_with_new_connection(
                "SELECT COUNT(admin_id) FROM ShopAdminTable",
                fetch='all'
            ) or 0
        except Exception as e:
            logger.error(f"Error counting admins: {e}")
            return 0

    def AllProducts():
        try:
            return execute_with_new_connection(
                "SELECT COUNT(productnumber) FROM ShopProductTable",
                fetch='all'
            ) or 0
        except Exception as e:
            logger.error(f"Error counting products: {e}")
            return 0

    def AllOrders():
        try:
            return execute_with_new_connection(
                "SELECT COUNT(buyerid) FROM ShopOrderTable",
                fetch='all'
            ) or 0
        except Exception as e:
            logger.error(f"Error counting orders: {e}")
            return 0
             
    def GetAdminsInfo():
        try:
            return execute_with_new_connection(
                "SELECT DISTINCT admin_id, username, wallet FROM ShopAdminTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting admins info: {e}")
            return None
        
    def GetOrderInfo():
        try:
            return execute_with_new_connection(
                "SELECT DISTINCT ordernumber, productname, buyerusername, orderdate FROM ShopOrderTable ORDER BY orderdate DESC",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting order info: {e}")
            return None

    def GetPaymentMethods():
        try:
            return execute_with_new_connection(
                "SELECT DISTINCT method_name, activated, username FROM PaymentMethodTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting payment methods: {e}")
            return None

    def GetPaymentMethodsAll(method_name):
        try:
            return execute_with_new_connection(
                f"SELECT DISTINCT method_name, token_keys_clientid, secret_keys FROM PaymentMethodTable WHERE method_name = '{method_name}'",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting payment method details: {e}")
            return None
 
    def GetPaymentMethodTokenKeysCleintID(method_name):
        try:
            result = execute_with_new_connection(
                f"SELECT DISTINCT token_keys_clientid FROM PaymentMethodTable WHERE method_name = '{method_name}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting payment token: {e}")
            return None

    def GetPaymentMethodSecretKeys(method_name):
        try:
            result = execute_with_new_connection(
                f"SELECT DISTINCT secret_keys FROM PaymentMethodTable WHERE method_name = '{method_name}'",
                fetch='one'
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting payment secret: {e}")
            return None

    def GetAllPaymentMethodsInDB():
        try:
            return execute_with_new_connection(
                "SELECT DISTINCT method_name FROM PaymentMethodTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting all payment methods: {e}")
            return None
        
    def GetProductCategories():
        try:
            return execute_with_new_connection(
                "SELECT DISTINCT productcategory FROM ShopProductTable",
                fetch='all'
            ) or "Default Category"
        except Exception as e:
            logger.error(f"Error getting product categories: {e}")
            return "Default Category"
        
    def GetProductIDs():
        try:
            return execute_with_new_connection(
                "SELECT productnumber FROM ShopProductTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting product IDs: {e}")
            return None
    
    def GetOrderDetails(ordernumber):
        try:
            return execute_with_new_connection(
                f"SELECT DISTINCT buyerid, buyerusername, productname, productprice, orderdate, paidmethod, productdownloadlink, productkeys, buyercomment, ordernumber, productnumber FROM ShopOrderTable WHERE ordernumber = '{ordernumber}' AND paidmethod != 'NO'",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting order details: {e}")
            return None
        
    def GetOrderIDs_Buyer(buyerid):
        try:
            return execute_with_new_connection(
                f"SELECT ordernumber FROM ShopOrderTable WHERE buyerid = '{buyerid}' AND paidmethod != 'NO'",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting buyer order IDs: {e}")
            return None

    def GetOrderIDs():
        try:
            return execute_with_new_connection(
                "SELECT ordernumber FROM ShopOrderTable",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting order IDs: {e}")
            return None

    def GetAllUnfirmedOrdersUser(buyerid):
        try:
            return execute_with_new_connection(
                f"SELECT DISTINCT ordernumber, productname, buyerusername, payment_id, productnumber FROM ShopOrderTable WHERE paidmethod = 'NO' AND buyerid = '{buyerid}' AND payment_id != ordernumber",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Error getting unconfirmed orders: {e}")
            return None


class CleanData:
    def __init__(self) -> None:
        pass

    def CleanShopUserTable():
        try:
            execute_with_new_connection("DELETE FROM ShopUserTable")
        except Exception as e:
            logger.error(f"Error cleaning user table: {e}")

    def CleanShopProductTable():
        try:
            execute_with_new_connection("DELETE FROM ShopProductTable")
        except Exception as e:
            logger.error(f"Error cleaning product table: {e}")
    
    def delete_an_order(ordernumber):
        try:
            execute_with_new_connection(
                "DELETE FROM ShopOrderTable WHERE ordernumber = ?",
                (ordernumber,)
            )
        except Exception as e:
            logger.error(f"Error deleting order: {e}")
    
    def delete_all_orders():
        """Delete all orders from database"""
        try:
            execute_with_new_connection("DELETE FROM ShopOrderTable")
            logger.info("All orders deleted")
            return True
        except Exception as e:
            logger.error(f"Error deleting all orders: {e}")
            return False

    def delete_a_product(productnumber):
        try:
            execute_with_new_connection(
                "DELETE FROM ShopProductTable WHERE productnumber = ?",
                (productnumber,)
            )
        except Exception as e:
            logger.error(f"Error deleting product: {e}")

    def delete_a_payment_method(method_name):
        try:
            execute_with_new_connection(
                "DELETE FROM PaymentMethodTable WHERE method_name = ?",
                (method_name,)
            )
        except Exception as e:
            logger.error(f"Error deleting payment method: {e}")

    def delete_a_category(categorynumber):
        try:
            execute_with_new_connection(
                "DELETE FROM ShopCategoryTable WHERE categorynumber = ?",
                (categorynumber,)
            )
        except Exception as e:
            logger.error(f"Error deleting category: {e}")


# ============== PROMOTION MANAGEMENT ==============

class PromotionDB:
    """Database operations for Buy 1 Get 1 promotion"""
    
    PROMO_NAME = "buy1get1"
    
    @staticmethod
    def init_promotion():
        """Initialize promotion record if not exists"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                if USE_POSTGRES:
                    cur.execute(
                        "INSERT INTO PromotionTable (promo_name, is_active, sold_count, max_count) VALUES (%s, 0, 0, 10) ON CONFLICT (promo_name) DO NOTHING",
                        (PromotionDB.PROMO_NAME,)
                    )
                else:
                    cur.execute(
                        "INSERT OR IGNORE INTO PromotionTable (promo_name, is_active, sold_count, max_count) VALUES (?, 0, 0, 10)",
                        (PromotionDB.PROMO_NAME,)
                    )
                    conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error initializing promotion: {e}")
            return False
    
    @staticmethod
    def is_active():
        """Check if promotion is active"""
        try:
            query = "SELECT is_active FROM PromotionTable WHERE promo_name = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (PromotionDB.PROMO_NAME,))
                result = cur.fetchone()
                return result[0] == 1 if result else False
        except Exception as e:
            logger.error(f"Error checking promotion status: {e}")
            return False
    
    @staticmethod
    def get_sold_count():
        """Get number of accounts sold during this promotion"""
        try:
            query = "SELECT sold_count FROM PromotionTable WHERE promo_name = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (PromotionDB.PROMO_NAME,))
                result = cur.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting promotion sold count: {e}")
            return 0
    
    @staticmethod
    def increment_sold_count(count=1):
        """Increment sold count when account is sold"""
        try:
            query = "UPDATE PromotionTable SET sold_count = sold_count + ? WHERE promo_name = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (count, PromotionDB.PROMO_NAME))
                if not USE_POSTGRES:
                    conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error incrementing sold count: {e}")
            return False
    
    @staticmethod
    def enable_promotion():
        """Enable promotion and reset sold count to 0"""
        try:
            query = "UPDATE PromotionTable SET is_active = 1, sold_count = 0, started_at = CURRENT_TIMESTAMP WHERE promo_name = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (PromotionDB.PROMO_NAME,))
                if not USE_POSTGRES:
                    conn.commit()
                logger.info("Promotion enabled and counter reset")
                return True
        except Exception as e:
            logger.error(f"Error enabling promotion: {e}")
            return False
    
    @staticmethod
    def disable_promotion():
        """Disable promotion"""
        try:
            query = "UPDATE PromotionTable SET is_active = 0 WHERE promo_name = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (PromotionDB.PROMO_NAME,))
                if not USE_POSTGRES:
                    conn.commit()
                logger.info("Promotion disabled")
                return True
        except Exception as e:
            logger.error(f"Error disabling promotion: {e}")
            return False
    
    @staticmethod
    def get_promotion_info():
        """Get full promotion info"""
        try:
            query = "SELECT is_active, sold_count, max_count, started_at FROM PromotionTable WHERE promo_name = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (PromotionDB.PROMO_NAME,))
                result = cur.fetchone()
                if result:
                    return {
                        "is_active": result[0] == 1,
                        "sold_count": result[1],
                        "max_count": result[2],
                        "started_at": result[3]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting promotion info: {e}")
            return None
    
    @staticmethod
    def set_max_count(max_count):
        """Set maximum promotion slots"""
        try:
            query = "UPDATE PromotionTable SET max_count = ? WHERE promo_name = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (max_count, PromotionDB.PROMO_NAME))
                if not USE_POSTGRES:
                    conn.commit()
                logger.info(f"Promotion max count set to {max_count}")
                return True
        except Exception as e:
            logger.error(f"Error setting max count: {e}")
            return False

# Initialize promotion record
PromotionDB.init_promotion()


# ============== CANVA ACCOUNT MANAGEMENT ==============

class CanvaAccountDB:
    """Database operations for Canva accounts with TempMail authkey"""
    
    @staticmethod
    def add_account(email, authkey):
        """Add a new Canva account to database"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                if USE_POSTGRES:
                    cur.execute(
                        "INSERT INTO CanvaAccountTable (email, authkey, status) VALUES (%s, %s, 'available') ON CONFLICT (email) DO NOTHING",
                        (email, authkey)
                    )
                else:
                    cur.execute(
                        "INSERT OR IGNORE INTO CanvaAccountTable (email, authkey, status) VALUES (?, ?, 'available')",
                        (email, authkey)
                    )
                    conn.commit()
                logger.info(f"Canva account added: {email}")
                return True
        except Exception as e:
            logger.error(f"Error adding Canva account {email}: {e}")
            return False
    
    @staticmethod
    def get_available_accounts(count=1):
        """Get available Canva accounts"""
        try:
            query = "SELECT id, email, authkey FROM CanvaAccountTable WHERE status = 'available' LIMIT ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (count,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Error getting available accounts: {e}")
            return []
    
    @staticmethod
    def assign_account_to_buyer(account_id, buyer_id, order_number):
        """Assign account to a buyer after purchase"""
        try:
            query = "UPDATE CanvaAccountTable SET buyer_id = ?, order_number = ?, status = 'sold' WHERE id = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (buyer_id, order_number, account_id))
                if not USE_POSTGRES:
                    conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error assigning account: {e}")
            return False
    
    @staticmethod
    def get_authkey_by_email(email):
        """Get authkey for an email (for OTP retrieval)"""
        try:
            query = "SELECT authkey FROM CanvaAccountTable WHERE email = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (email,))
                result = cur.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting authkey for {email}: {e}")
            return None
    
    @staticmethod
    def get_buyer_accounts(buyer_id):
        """Get all accounts owned by a buyer"""
        try:
            query = "SELECT email, order_number, created_at FROM CanvaAccountTable WHERE buyer_id = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (buyer_id,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Error getting buyer accounts: {e}")
            return []
    
    @staticmethod
    def remove_buyer_from_account(email, buyer_id):
        """Remove buyer from account (user deletes from their list)"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                # Verify the account belongs to this buyer
                query1 = "SELECT id FROM CanvaAccountTable WHERE email = ? AND buyer_id = ?"
                query2 = "UPDATE CanvaAccountTable SET buyer_id = NULL, status = 'deleted_by_user' WHERE email = ? AND buyer_id = ?"
                if USE_POSTGRES:
                    query1 = query1.replace("?", "%s")
                    query2 = query2.replace("?", "%s")
                
                cur.execute(query1, (email, buyer_id))
                result = cur.fetchone()
                if not result:
                    return False
                
                cur.execute(query2, (email, buyer_id))
                if not USE_POSTGRES:
                    conn.commit()
                logger.info(f"User {buyer_id} removed account {email} from their list")
                return True
        except Exception as e:
            logger.error(f"Error removing buyer from account: {e}")
            return False
    
    @staticmethod
    def get_account_count():
        """Get count of available accounts"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM CanvaAccountTable WHERE status = 'available'")
                result = cur.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error counting accounts: {e}")
            return 0
    
    @staticmethod
    def get_sold_count():
        """Get count of sold accounts (for promotion tracking)"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM CanvaAccountTable WHERE status = 'sold'")
                result = cur.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error counting sold accounts: {e}")
            return 0
    
    @staticmethod
    def get_all_accounts():
        """Get all accounts (for admin)"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, email, authkey, buyer_id, order_number, status, created_at FROM CanvaAccountTable"
                )
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Error getting all accounts: {e}")
            return []
    
    @staticmethod
    def delete_account(account_id):
        """Delete an account"""
        try:
            query = "DELETE FROM CanvaAccountTable WHERE id = ?"
            if USE_POSTGRES:
                query = query.replace("?", "%s")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, (account_id,))
                if not USE_POSTGRES:
                    conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting account: {e}")
            return False
    
    @staticmethod
    def import_emails_only(file_content):
        """Import emails only (for Premium - no authkey needed)
        
        Format: one email per line
        """
        count = 0
        try:
            lines = file_content.strip().split('\n')
            for line in lines:
                email = line.strip()
                if email and '@' in email:
                    # Add with empty authkey (Premium doesn't need it)
                    if CanvaAccountDB.add_account(email, "PREMIUM"):
                        count += 1
            return count
        except Exception as e:
            logger.error(f"Error importing emails: {e}")
            return count
    
    @staticmethod
    def import_accounts_from_file(file_content):
        """Import accounts from file content (legacy - with authkey)
        
        Supported formats:
        1. email|authkey (one per line)
        2. Block format:
           email1
           email2
           
           authkey1
           authkey2
        """
        count = 0
        try:
            content = file_content.strip()
            
            # Check if it's pipe-separated format
            if '|' in content:
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 2:
                            email = parts[0].strip()
                            authkey = parts[1].strip()
                            if email and authkey:
                                if CanvaAccountDB.add_account(email, authkey):
                                    count += 1
            else:
                # Block format: emails first, then blank line, then authkeys
                # Split by double newline or find the blank line
                parts = content.split('\n\n')
                if len(parts) >= 2:
                    emails_block = parts[0].strip()
                    authkeys_block = parts[1].strip()
                    
                    emails = [e.strip() for e in emails_block.split('\n') if e.strip()]
                    authkeys = [a.strip() for a in authkeys_block.split('\n') if a.strip()]
                    
                    # Pair emails with authkeys
                    for i in range(min(len(emails), len(authkeys))):
                        email = emails[i]
                        authkey = authkeys[i]
                        if email and authkey and '@' in email:
                            if CanvaAccountDB.add_account(email, authkey):
                                count += 1
                else:
                    # Try single blank line split
                    lines = content.split('\n')
                    # Find the blank line index
                    blank_idx = -1
                    for i, line in enumerate(lines):
                        if not line.strip():
                            blank_idx = i
                            break
                    
                    if blank_idx > 0:
                        emails = [l.strip() for l in lines[:blank_idx] if l.strip()]
                        authkeys = [l.strip() for l in lines[blank_idx+1:] if l.strip()]
                        
                        for i in range(min(len(emails), len(authkeys))):
                            email = emails[i]
                            authkey = authkeys[i]
                            if email and authkey and '@' in email:
                                if CanvaAccountDB.add_account(email, authkey):
                                    count += 1
            
            return count
        except Exception as e:
            logger.error(f"Error importing accounts: {e}")
            return count
