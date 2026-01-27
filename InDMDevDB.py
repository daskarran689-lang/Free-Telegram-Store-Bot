"""
Database module using Supabase REST API
- No connection timeouts
- Instant responses via HTTP
- Works perfectly with Render free tier
- Uses EXISTING table names to preserve data
"""

import os
import logging
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv('config.env')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# Check if Supabase is configured
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)


class SupabaseResponse:
    def __init__(self, data=None, count=None, error=None, status_code=None):
        self.data = data if data is not None else []
        self.count = count
        self.error = error
        self.status_code = status_code


class SupabaseRESTTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.method = "GET"
        self.params = {}
        self.headers = {}
        self.payload = None
        self._count = None

    def select(self, columns="*", count=None):
        self.method = "GET"
        self.params["select"] = columns
        self._count = count
        return self

    def insert(self, data):
        self.method = "POST"
        self.payload = data
        self.headers["Prefer"] = "return=representation"
        return self

    def upsert(self, data, on_conflict=None):
        self.method = "POST"
        self.payload = data
        self.headers["Prefer"] = "return=representation,resolution=merge-duplicates"
        if on_conflict:
            self.params["on_conflict"] = on_conflict
        return self

    def update(self, data):
        self.method = "PATCH"
        self.payload = data
        self.headers["Prefer"] = "return=representation"
        return self

    def delete(self):
        self.method = "DELETE"
        self.headers["Prefer"] = "return=representation"
        return self

    def eq(self, column, value):
        self.params[column] = f"eq.{value}"
        return self

    def limit(self, count):
        self.params["limit"] = str(count)
        return self

    def execute(self):
        url = f"{self.client.base_url}/rest/v1/{self.table_name}"
        headers = dict(self.client.headers)
        headers.update(self.headers)

        if self._count:
            prefer = headers.get("Prefer", "")
            if "count=exact" not in prefer:
                prefer = f"{prefer},count=exact".strip(",")
            headers["Prefer"] = prefer

        response = requests.request(
            self.method,
            url,
            headers=headers,
            params=self.params if self.params else None,
            json=self.payload,
            timeout=self.client.timeout
        )

        count = None
        if self._count:
            content_range = response.headers.get("Content-Range")
            if content_range and "/" in content_range:
                try:
                    count = int(content_range.split("/")[-1])
                except Exception:
                    count = None

        if response.status_code >= 400:
            try:
                error = response.json()
            except Exception:
                error = response.text
            logger.error(f"Supabase REST error: {response.status_code} {error}")
            return SupabaseResponse(data=[], count=count, error=error, status_code=response.status_code)

        try:
            data = response.json()
        except Exception:
            data = []

        if isinstance(data, dict):
            data = [data]
        if data is None:
            data = []

        return SupabaseResponse(data=data, count=count, error=None, status_code=response.status_code)


class SupabaseRESTClient:
    def __init__(self, base_url, api_key, timeout=15):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def table(self, table_name):
        return SupabaseRESTTable(self, table_name)


if USE_SUPABASE:
    supabase = SupabaseRESTClient(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Using Supabase REST API (requests-based, no dependency backtracking)")
else:
    supabase = None
    logger.warning("Supabase not configured! Set SUPABASE_URL and SUPABASE_KEY")

# Flag for backward compatibility
USE_POSTGRES = USE_SUPABASE
IS_SUPABASE = USE_SUPABASE

# Dummy for backward compatibility
def start_background_db_init():
    """No longer needed with Supabase REST API"""
    logger.info("Supabase REST API - no background init needed")
    pass


# ============== TABLE NAMES (using existing tables) ==============
# These match your existing Supabase tables (lowercase)

TABLE_USERS = "shopusertable"
TABLE_ADMINS = "shopadmintable"
TABLE_PRODUCTS = "shopproducttable"
TABLE_ORDERS = "shopordertable"
TABLE_CATEGORIES = "shopcategorytable"
TABLE_PAYMENT = "paymentmethodtable"
TABLE_CANVA = "canvaaccounttable"
TABLE_PROMO = "promotiontable"


# ============== USER OPERATIONS ==============

class CreateDatas:
    """Data creation operations"""
    
    @staticmethod
    def AddAuser(user_id, username):
        """Add a new user"""
        try:
            supabase.table(TABLE_USERS).upsert({
                'user_id': user_id,
                'username': username,
                'wallet': 0
            }, on_conflict='user_id').execute()
            logger.info(f"User added/updated: {username} (ID: {user_id})")
            return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    @staticmethod
    def AddAdmin(admin_id, username):
        """Add a new admin"""
        try:
            supabase.table(TABLE_ADMINS).upsert({
                'admin_id': admin_id,
                'username': username,
                'wallet': 0
            }, on_conflict='admin_id').execute()
            logger.info(f"Admin added/updated: {username} (ID: {admin_id})")
            return True
        except Exception as e:
            logger.error(f"Error adding admin: {e}")
            return False
    
    @staticmethod
    def AddProduct(productnumber, admin_id, username):
        """Add a new product"""
        try:
            supabase.table(TABLE_PRODUCTS).upsert({
                'productnumber': productnumber,
                'admin_id': admin_id,
                'username': username,
                'productname': 'New Product',
                'productprice': 0,
                'productquantity': 0
            }, on_conflict='productnumber').execute()
            return True
        except Exception as e:
            logger.error(f"Error adding product: {e}")
            return False
    
    @staticmethod
    def AddOrder(ordernumber, buyerid, buyerusername, productname, productprice, productnumber, payment_id=None):
        """Add a new order"""
        try:
            supabase.table(TABLE_ORDERS).insert({
                'ordernumber': ordernumber,
                'buyerid': buyerid,
                'buyerusername': buyerusername,
                'productname': productname,
                'productprice': str(productprice),
                'productnumber': productnumber,
                'payment_id': payment_id,
                'paidmethod': 'PENDING'
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Error adding order: {e}")
            return False
    
    @staticmethod
    def AddCategory(categorynumber, categoryname):
        """Add a new category"""
        try:
            supabase.table(TABLE_CATEGORIES).upsert({
                'categorynumber': categorynumber,
                'categoryname': categoryname
            }, on_conflict='categorynumber').execute()
            return True
        except Exception as e:
            logger.error(f"Error adding category: {e}")
            return False
    
    @staticmethod
    def UpdateProductName(name, productnumber):
        try:
            supabase.table(TABLE_PRODUCTS).update({'productname': name}).eq('productnumber', productnumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating product name: {e}")
            return False
    
    @staticmethod
    def UpdateProductDescription(description, productnumber):
        try:
            supabase.table(TABLE_PRODUCTS).update({'productdescription': description}).eq('productnumber', productnumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating product description: {e}")
            return False
    
    @staticmethod
    def UpdateProductPrice(price, productnumber):
        try:
            supabase.table(TABLE_PRODUCTS).update({'productprice': int(price)}).eq('productnumber', productnumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating product price: {e}")
            return False
    
    @staticmethod
    def UpdateProductQuantity(quantity, productnumber):
        try:
            supabase.table(TABLE_PRODUCTS).update({'productquantity': int(quantity)}).eq('productnumber', productnumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating product quantity: {e}")
            return False
    
    @staticmethod
    def UpdateProductproductimagelink(imagelink, productnumber):
        try:
            supabase.table(TABLE_PRODUCTS).update({'productimagelink': imagelink}).eq('productnumber', productnumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating product image: {e}")
            return False
    
    @staticmethod
    def UpdateProductproductdownloadlink(downloadlink, productnumber):
        try:
            supabase.table(TABLE_PRODUCTS).update({'productdownloadlink': downloadlink}).eq('productnumber', productnumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating product download link: {e}")
            return False
    
    @staticmethod
    def UpdateProductKeysFile(keysfile, productnumber):
        try:
            supabase.table(TABLE_PRODUCTS).update({'productkeysfile': keysfile}).eq('productnumber', productnumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating product keys file: {e}")
            return False
    
    @staticmethod
    def UpdateProductCategory(category, productnumber):
        try:
            supabase.table(TABLE_PRODUCTS).update({'productcategory': category}).eq('productnumber', productnumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating product category: {e}")
            return False
    
    @staticmethod
    def UpdateOrderPurchasedKeys(keys, ordernumber):
        try:
            supabase.table(TABLE_ORDERS).update({'productkeys': keys}).eq('ordernumber', ordernumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating order keys: {e}")
            return False
    
    @staticmethod
    def UpdateOrderPaymentMethod(method, ordernumber):
        try:
            supabase.table(TABLE_ORDERS).update({'paidmethod': method}).eq('ordernumber', ordernumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating order payment method: {e}")
            return False
    
    @staticmethod
    def UpdateOrderComment(comment, ordernumber):
        try:
            supabase.table(TABLE_ORDERS).update({'buyercomment': comment}).eq('ordernumber', ordernumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating order comment: {e}")
            return False
    
    @staticmethod
    def DeleteProduct(productnumber):
        try:
            supabase.table(TABLE_PRODUCTS).delete().eq('productnumber', productnumber).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting product: {e}")
            return False


# ============== GET DATA OPERATIONS ==============

class GetDataFromDB:
    """Data retrieval operations"""
    
    @staticmethod
    def GetAdminIDsInDB():
        """Get all admin IDs"""
        try:
            result = supabase.table(TABLE_ADMINS).select('admin_id, username').execute()
            return [(r['admin_id'], r['username']) for r in result.data] if result.data else []
        except Exception as e:
            logger.error(f"Error getting admins: {e}")
            return []
    
    @staticmethod
    def GetUserIDsInDB():
        """Get all user IDs"""
        try:
            result = supabase.table(TABLE_USERS).select('user_id').execute()
            return [(r['user_id'],) for r in result.data] if result.data else []
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []
    
    @staticmethod
    def GetUsersInfo():
        """Get all users info"""
        try:
            result = supabase.table(TABLE_USERS).select('user_id, username, wallet').execute()
            return [(r['user_id'], r['username'], r['wallet']) for r in result.data] if result.data else []
        except Exception as e:
            logger.error(f"Error getting users info: {e}")
            return []
    
    @staticmethod
    def GetUsersInfoWithDate():
        """Get all users info with date"""
        try:
            result = supabase.table(TABLE_USERS).select('user_id, username, wallet, created_at').execute()
            return [(r['user_id'], r['username'], r['wallet'], r['created_at']) for r in result.data] if result.data else []
        except Exception as e:
            logger.error(f"Error getting users info with date: {e}")
            return []
    
    @staticmethod
    def GetProductInfo():
        """Get all products"""
        try:
            result = supabase.table(TABLE_PRODUCTS).select('productnumber, productname, productprice, productdescription, productimagelink, productdownloadlink, productquantity, productcategory').execute()
            return [(r['productnumber'], r['productname'], r['productprice'], r['productdescription'], 
                    r['productimagelink'], r['productdownloadlink'], r['productquantity'], r['productcategory']) 
                    for r in result.data] if result.data else []
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            return []
    
    @staticmethod
    def GetProductInfoByPName(productnumber):
        """Get product by product number"""
        try:
            result = supabase.table(TABLE_PRODUCTS).select('*').eq('productnumber', productnumber).execute()
            if result.data:
                r = result.data[0]
                return [(r['productnumber'], r['productname'], r['productprice'], r['productdescription'],
                        r['productimagelink'], r['productdownloadlink'], r['productquantity'], r['productcategory'])]
            return []
        except Exception as e:
            logger.error(f"Error getting product by number: {e}")
            return []
    
    @staticmethod
    def GetProductName(productnumber):
        try:
            result = supabase.table(TABLE_PRODUCTS).select('productname').eq('productnumber', productnumber).execute()
            return result.data[0]['productname'] if result.data else None
        except:
            return None
    
    @staticmethod
    def GetProductPrice(productnumber):
        try:
            result = supabase.table(TABLE_PRODUCTS).select('productprice').eq('productnumber', productnumber).execute()
            return result.data[0]['productprice'] if result.data else 0
        except:
            return 0
    
    @staticmethod
    def GetProductDescription(productnumber):
        try:
            result = supabase.table(TABLE_PRODUCTS).select('productdescription').eq('productnumber', productnumber).execute()
            return result.data[0]['productdescription'] if result.data else None
        except:
            return None
    
    @staticmethod
    def GetProductQuantity(productnumber):
        try:
            result = supabase.table(TABLE_PRODUCTS).select('productquantity').eq('productnumber', productnumber).execute()
            return result.data[0]['productquantity'] if result.data else 0
        except:
            return 0
    
    @staticmethod
    def GetProductImageLink(productnumber):
        try:
            result = supabase.table(TABLE_PRODUCTS).select('productimagelink').eq('productnumber', productnumber).execute()
            return result.data[0]['productimagelink'] if result.data else None
        except:
            return None
    
    @staticmethod
    def GetProductDownloadLink(productnumber):
        try:
            result = supabase.table(TABLE_PRODUCTS).select('productdownloadlink').eq('productnumber', productnumber).execute()
            return result.data[0]['productdownloadlink'] if result.data else None
        except:
            return None
    
    @staticmethod
    def GetProductNumber(productnumber):
        try:
            result = supabase.table(TABLE_PRODUCTS).select('productnumber').eq('productnumber', productnumber).execute()
            return result.data[0]['productnumber'] if result.data else None
        except:
            return None
    
    @staticmethod
    def GetProductNumberName():
        """Get product numbers and names"""
        try:
            result = supabase.table(TABLE_PRODUCTS).select('productnumber, productname').execute()
            return [(r['productnumber'], r['productname']) for r in result.data] if result.data else []
        except:
            return []
    
    @staticmethod
    def GetProductIDs():
        """Get all product IDs"""
        try:
            result = supabase.table(TABLE_PRODUCTS).select('productnumber').execute()
            return [(r['productnumber'],) for r in result.data] if result.data else []
        except:
            return []
    
    @staticmethod
    def GetCategoryIDsInDB():
        """Get all categories"""
        try:
            result = supabase.table(TABLE_CATEGORIES).select('categorynumber, categoryname').execute()
            return [(r['categorynumber'], r['categoryname']) for r in result.data] if result.data else []
        except:
            return []
    
    @staticmethod
    def Get_A_CategoryName(categorynumber):
        """Get category name by number"""
        try:
            result = supabase.table(TABLE_CATEGORIES).select('categoryname').eq('categorynumber', categorynumber).execute()
            return result.data[0]['categoryname'] if result.data else None
        except:
            return None
    
    @staticmethod
    def GetOrderDetails(ordernumber):
        """Get order details"""
        try:
            result = supabase.table(TABLE_ORDERS).select('*').eq('ordernumber', ordernumber).execute()
            if result.data:
                r = result.data[0]
                return (r['ordernumber'], r['buyerid'], r['buyerusername'], r['productname'],
                       r['productprice'], r['paidmethod'], r['productdownloadlink'], r['productkeys'],
                       r['buyercomment'], r['productnumber'])
            return None
        except:
            return None
    
    @staticmethod
    def GetAllUnfirmedOrdersUser(user_id):
        """Get pending orders"""
        try:
            result = supabase.table(TABLE_ORDERS).select('*').eq('paidmethod', 'PENDING').execute()
            return result.data if result.data else []
        except:
            return []
    
    @staticmethod
    def GetPaymentMethodTokenKeysCleintID(method_name):
        """Get payment method token"""
        try:
            result = supabase.table(TABLE_PAYMENT).select('token_keys_clientid').eq('method_name', method_name).execute()
            return result.data[0]['token_keys_clientid'] if result.data else None
        except:
            return None
    
    @staticmethod
    def GetPaymentMethodsAll(method_name):
        """Get all payment method data"""
        try:
            result = supabase.table(TABLE_PAYMENT).select('*').eq('method_name', method_name).execute()
            return result.data[0] if result.data else None
        except:
            return None
    
    @staticmethod
    def AllUsers():
        return GetDataFromDB.GetUsersInfo()
    
    @staticmethod
    def AllAdmins():
        return GetDataFromDB.GetAdminIDsInDB()
    
    @staticmethod
    def AllProducts():
        return GetDataFromDB.GetProductInfo()
    
    @staticmethod
    def AllOrders():
        try:
            result = supabase.table(TABLE_ORDERS).select('*').execute()
            return result.data if result.data else []
        except:
            return []


# ============== CANVA ACCOUNT OPERATIONS ==============

class CanvaAccountDB:
    """Canva account management"""
    
    @staticmethod
    def add_account(email, authkey):
        """Add a Canva account"""
        try:
            supabase.table(TABLE_CANVA).upsert({
                'email': email,
                'authkey': authkey,
                'status': 'available'
            }, on_conflict='email').execute()
            return True
        except Exception as e:
            logger.error(f"Error adding Canva account: {e}")
            return False
    
    @staticmethod
    def get_available_accounts(count=1):
        """Get available accounts"""
        try:
            result = supabase.table(TABLE_CANVA).select('*').eq('status', 'available').limit(count).execute()
            return [(r['id'], r['email'], r['authkey']) for r in result.data] if result.data else []
        except:
            return []
    
    @staticmethod
    def get_account_count():
        """Get count of available accounts"""
        try:
            result = supabase.table(TABLE_CANVA).select('id', count='exact').eq('status', 'available').execute()
            return result.count if result.count else 0
        except:
            return 0
    
    @staticmethod
    def assign_account_to_buyer(account_id, buyer_id, order_number):
        """Assign account to buyer"""
        try:
            supabase.table(TABLE_CANVA).update({
                'buyer_id': buyer_id,
                'order_number': order_number,
                'status': 'sold'
            }).eq('id', account_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error assigning account: {e}")
            return False
    
    @staticmethod
    def get_buyer_accounts(buyer_id):
        """Get accounts owned by buyer"""
        try:
            result = supabase.table(TABLE_CANVA).select('*').eq('buyer_id', buyer_id).execute()
            return [(r['id'], r['email'], r['authkey'], r['status']) for r in result.data] if result.data else []
        except:
            return []
    
    @staticmethod
    def get_authkey_by_email(email):
        """Get authkey for email"""
        try:
            result = supabase.table(TABLE_CANVA).select('authkey').eq('email', email).execute()
            return result.data[0]['authkey'] if result.data else None
        except:
            return None
    
    @staticmethod
    def get_all_accounts():
        """Get all accounts"""
        try:
            result = supabase.table(TABLE_CANVA).select('*').execute()
            return [(r['id'], r['email'], r['authkey'], r.get('buyer_id'), r.get('order_number'), r['status']) 
                    for r in result.data] if result.data else []
        except:
            return []
    
    @staticmethod
    def delete_account(account_id):
        """Delete account"""
        try:
            supabase.table(TABLE_CANVA).delete().eq('id', account_id).execute()
            return True
        except:
            return False
    
    @staticmethod
    def remove_buyer_from_account(email, buyer_id):
        """Remove buyer from account (make available again)"""
        try:
            supabase.table(TABLE_CANVA).update({
                'buyer_id': None,
                'order_number': None,
                'status': 'available'
            }).eq('email', email).eq('buyer_id', buyer_id).execute()
            return True
        except:
            return False
    
    @staticmethod
    def import_emails_only(content):
        """Import emails from content (one per line: email|authkey)"""
        count = 0
        lines = content.strip().split('\n')
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
            elif '@' in line:
                # Just email, no authkey
                email = line.strip()
                if email:
                    if CanvaAccountDB.add_account(email, 'no_authkey'):
                        count += 1
        return count


# ============== PROMOTION OPERATIONS ==============

class PromotionDB:
    """Promotion management"""
    
    @staticmethod
    def get_promotion_info():
        """Get buy1get1 promotion info"""
        try:
            result = supabase.table(TABLE_PROMO).select('*').eq('promo_name', 'buy1get1').execute()
            if result.data:
                r = result.data[0]
                return {
                    'is_active': r['is_active'],
                    'sold_count': r['sold_count'],
                    'max_count': r['max_count'],
                    'started_at': r['started_at']
                }
            return None
        except:
            return None
    
    @staticmethod
    def activate_promotion(max_count=10):
        """Activate promotion"""
        try:
            supabase.table(TABLE_PROMO).upsert({
                'promo_name': 'buy1get1',
                'is_active': 1,
                'sold_count': 0,
                'max_count': max_count,
                'started_at': datetime.now().isoformat()
            }, on_conflict='promo_name').execute()
            return True
        except:
            return False
    
    @staticmethod
    def deactivate_promotion():
        """Deactivate promotion"""
        try:
            supabase.table(TABLE_PROMO).update({
                'is_active': 0
            }).eq('promo_name', 'buy1get1').execute()
            return True
        except:
            return False
    
    @staticmethod
    def increment_sold_count():
        """Increment sold count"""
        try:
            result = supabase.table(TABLE_PROMO).select('sold_count').eq('promo_name', 'buy1get1').execute()
            if result.data:
                current = result.data[0]['sold_count']
                supabase.table(TABLE_PROMO).update({
                    'sold_count': current + 1
                }).eq('promo_name', 'buy1get1').execute()
            return True
        except:
            return False
    
    @staticmethod
    def is_promotion_active():
        """Check if promotion is active and not exceeded"""
        try:
            info = PromotionDB.get_promotion_info()
            if info and info['is_active'] == 1:
                return info['sold_count'] < info['max_count']
            return False
        except:
            return False


# ============== BACKWARD COMPATIBILITY ==============

class CreateTables:
    @staticmethod
    def create_all_tables():
        logger.info("Using existing Supabase tables - no creation needed")
        return True

def get_db_connection():
    """Not needed with Supabase REST API"""
    return None

def execute_with_new_connection(query, params=None, fetch='none'):
    """Not supported - use Supabase classes instead"""
    logger.warning("execute_with_new_connection not supported with Supabase REST API")
    return None

def get_placeholder():
    return "%s"
