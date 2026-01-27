"""
Performance optimization module for Telegram Bot
- Smart caching system
- Background task processing
- Rate limiting
- Non-blocking operations
"""

import threading
import time
import logging
from functools import wraps
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import queue

logger = logging.getLogger(__name__)

# ============== SMART CACHE SYSTEM ==============

class TTLCache:
    """Thread-safe cache with TTL (Time To Live)"""
    
    def __init__(self, maxsize=1000, ttl=300):
        self.maxsize = maxsize
        self.ttl = ttl  # seconds
        self._cache = OrderedDict()
        self._timestamps = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key, default=None):
        """Get value from cache"""
        with self._lock:
            if key in self._cache:
                # Check if expired
                if time.time() - self._timestamps[key] < self.ttl:
                    # Move to end (LRU)
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return self._cache[key]
                else:
                    # Expired, remove
                    del self._cache[key]
                    del self._timestamps[key]
            self._misses += 1
            return default
    
    def set(self, key, value, ttl=None):
        """Set value in cache"""
        with self._lock:
            # Remove oldest if at capacity
            while len(self._cache) >= self.maxsize:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                del self._timestamps[oldest_key]
            
            self._cache[key] = value
            self._timestamps[key] = time.time()
            if ttl:
                self._timestamps[key] = time.time() - self.ttl + ttl
    
    def delete(self, key):
        """Remove key from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]
    
    def clear(self):
        """Clear all cache"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
    
    def stats(self):
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'size': len(self._cache)
        }


# ============== GLOBAL CACHES ==============

# Admin cache - long TTL since admins rarely change
admin_cache = TTLCache(maxsize=100, ttl=600)  # 10 minutes

# User cache - medium TTL
user_cache = TTLCache(maxsize=5000, ttl=300)  # 5 minutes

# Product cache - medium TTL
product_cache = TTLCache(maxsize=500, ttl=180)  # 3 minutes

# Promotion cache - short TTL since it changes often
promo_cache = TTLCache(maxsize=10, ttl=60)  # 1 minute

# Rate limit cache - very short TTL
rate_limit_cache = TTLCache(maxsize=10000, ttl=60)  # 1 minute


# ============== CACHED DECORATORS ==============

def cached(cache, key_func=None, ttl=None):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Call function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, ttl)
            return result
        
        # Add cache control methods
        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_delete = lambda key: cache.delete(key)
        return wrapper
    return decorator


# ============== BACKGROUND TASK PROCESSOR ==============

class BackgroundProcessor:
    """Process heavy tasks in background without blocking"""
    
    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.task_queue = queue.Queue()
        self._running = True
        
        # Start background worker thread
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
    
    def _worker(self):
        """Background worker that processes queued tasks"""
        while self._running:
            try:
                task, args, kwargs = self.task_queue.get(timeout=1)
                try:
                    task(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Background task error: {e}")
                finally:
                    self.task_queue.task_done()
            except queue.Empty:
                continue
    
    def submit(self, task, *args, **kwargs):
        """Submit task to thread pool (immediate execution)"""
        return self.executor.submit(task, *args, **kwargs)
    
    def queue_task(self, task, *args, **kwargs):
        """Queue task for sequential processing"""
        self.task_queue.put((task, args, kwargs))
    
    def shutdown(self):
        """Shutdown the processor"""
        self._running = False
        self.executor.shutdown(wait=False)


# Global background processor
background = BackgroundProcessor(max_workers=4)


# ============== RATE LIMITING ==============

def check_rate_limit(user_id, max_requests=30, window=60):
    """
    Check if user is rate limited.
    Returns True if allowed, False if rate limited.
    """
    cache_key = f"rate:{user_id}"
    
    # Get current request count
    data = rate_limit_cache.get(cache_key)
    
    if data is None:
        # First request
        rate_limit_cache.set(cache_key, {'count': 1, 'start': time.time()}, ttl=window)
        return True
    
    count = data['count']
    start = data['start']
    
    # Check if window expired
    if time.time() - start > window:
        # Reset counter
        rate_limit_cache.set(cache_key, {'count': 1, 'start': time.time()}, ttl=window)
        return True
    
    # Check if over limit
    if count >= max_requests:
        return False
    
    # Increment counter
    data['count'] += 1
    rate_limit_cache.set(cache_key, data, ttl=window)
    return True


# ============== ADMIN CHECK WITH CACHE ==============

_admin_ids_cache = None
_admin_cache_time = 0
_ADMIN_CACHE_TTL = 300  # 5 minutes

def get_cached_admin_ids():
    """Get admin IDs with caching"""
    global _admin_ids_cache, _admin_cache_time
    
    current_time = time.time()
    
    # Return cached if still valid
    if _admin_ids_cache is not None and (current_time - _admin_cache_time) < _ADMIN_CACHE_TTL:
        return _admin_ids_cache
    
    # Refresh cache in background if expired but have old data
    if _admin_ids_cache is not None:
        # Return stale data immediately, refresh in background
        background.submit(_refresh_admin_cache)
        return _admin_ids_cache
    
    # No cache, must fetch synchronously
    _refresh_admin_cache()
    return _admin_ids_cache or []

def _refresh_admin_cache():
    """Refresh admin cache from database"""
    global _admin_ids_cache, _admin_cache_time
    try:
        from InDMDevDB import GetDataFromDB
        admins = GetDataFromDB.GetAdminIDsInDB() or []
        _admin_ids_cache = set(str(admin[0]) for admin in admins)
        _admin_cache_time = time.time()
    except Exception as e:
        logger.error(f"Error refreshing admin cache: {e}")

def is_admin_cached(user_id, env_admin_id=None):
    """Check if user is admin with caching"""
    # Check env admin first (instant)
    if env_admin_id and str(user_id) == str(env_admin_id):
        return True
    
    # Check cached admin list
    admin_ids = get_cached_admin_ids()
    return str(user_id) in admin_ids


# ============== USER PURCHASE CHECK WITH CACHE ==============

def has_purchased_cached(user_id):
    """Check if user has purchased with caching"""
    cache_key = f"purchased:{user_id}"
    
    # Check cache first
    cached = user_cache.get(cache_key)
    if cached is not None:
        return cached
    
    # Query database
    try:
        from InDMDevDB import CanvaAccountDB
        accounts = CanvaAccountDB.get_buyer_accounts(user_id)
        has_purchased = accounts and len(accounts) > 0
        user_cache.set(cache_key, has_purchased)
        return has_purchased
    except:
        return False

def invalidate_user_purchase_cache(user_id):
    """Invalidate purchase cache when user buys something"""
    user_cache.delete(f"purchased:{user_id}")


# ============== PRODUCT CACHE ==============

def get_products_cached():
    """Get products with caching"""
    cache_key = "all_products"
    
    cached = product_cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        from InDMDevDB import GetDataFromDB
        products = GetDataFromDB.GetProductInfo() or []
        product_cache.set(cache_key, products)
        return products
    except:
        return []

def invalidate_product_cache():
    """Invalidate product cache when products change"""
    product_cache.clear()


# ============== PROMOTION CACHE ==============

def get_promotion_cached():
    """Get promotion info with caching"""
    cache_key = "promotion"
    
    cached = promo_cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        from InDMDevDB import PromotionDB
        promo = PromotionDB.get_promotion_info()
        promo_cache.set(cache_key, promo)
        return promo
    except:
        return None

def invalidate_promotion_cache():
    """Invalidate promotion cache when it changes"""
    promo_cache.delete("promotion")


# ============== ASYNC-LIKE HELPERS ==============

def run_async(func):
    """Decorator to run function in background thread"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return background.submit(func, *args, **kwargs)
    return wrapper

def defer(func, *args, delay=0, **kwargs):
    """Run function after delay in background"""
    def delayed_task():
        if delay > 0:
            time.sleep(delay)
        func(*args, **kwargs)
    background.submit(delayed_task)


# ============== NON-BLOCKING NOTIFICATIONS ==============

def notify_admin_async(bot, admin_id, message):
    """Send admin notification without blocking"""
    def send():
        try:
            bot.send_message(int(admin_id), message)
        except Exception as e:
            logger.error(f"Error sending admin notification: {e}")
    background.submit(send)

def add_user_async(user_id, username):
    """Add user to database without blocking"""
    def add():
        try:
            from InDMDevDB import CreateDatas
            CreateDatas.AddAuser(user_id, username)
        except Exception as e:
            logger.error(f"Error adding user async: {e}")
    background.submit(add)


# ============== CACHE WARMING ==============

def warm_caches():
    """Pre-load frequently accessed data into caches"""
    def warm():
        logger.info("Warming caches...")
        try:
            # Warm admin cache
            _refresh_admin_cache()
            
            # Warm product cache
            get_products_cached()
            
            # Warm promotion cache
            get_promotion_cached()
            
            logger.info("Cache warming completed")
        except Exception as e:
            logger.error(f"Cache warming error: {e}")
    
    background.submit(warm)


# ============== CACHE STATS ==============

def get_all_cache_stats():
    """Get statistics for all caches"""
    return {
        'admin': admin_cache.stats(),
        'user': user_cache.stats(),
        'product': product_cache.stats(),
        'promo': promo_cache.stats(),
        'rate_limit': rate_limit_cache.stats()
    }
