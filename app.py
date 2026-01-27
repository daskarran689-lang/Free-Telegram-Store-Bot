"""
Render Entry Point - Flask starts FIRST, then bot initializes
This ensures port opens within Render's 60 second requirement
"""

import os
import time
import logging
import threading
from flask import Flask, request
import requests as http_requests

# Configure logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv('config.env')

# Create Flask app IMMEDIATELY - this is the key to fast port binding
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

# State tracking
_bot_module = None
_bot_ready = False

# Health check endpoints - MUST be available immediately for Render
@app.route("/", methods=["GET", "HEAD"])
def health():
    return "ok", 200

@app.route("/health")
def health_check():
    return "OK", 200

# Webhook endpoint - forwards to bot after initialization
@app.route("/", methods=["POST"])
@app.route("/webhook", methods=["POST"])
def webhook():
    global _bot_module, _bot_ready
    
    try:
        if _bot_ready and _bot_module:
            # Bot is ready, process update
            ctype = (request.headers.get("content-type") or "").lower()
            if ctype.startswith("application/json"):
                json_string = request.get_data(as_text=True)
                
                # Process in background thread
                def process():
                    try:
                        import telebot
                        update = telebot.types.Update.de_json(json_string)
                        _bot_module.bot.process_new_updates([update])
                    except Exception as e:
                        logger.error(f"Update processing error: {e}")
                
                threading.Thread(target=process, daemon=True).start()
                return "ok", 200
        else:
            # Bot not ready yet, just acknowledge
            logger.debug("Webhook received but bot not ready yet")
            return "ok", 200
            
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "ok", 200

# PayOS webhook endpoint
@app.route("/payos-webhook", methods=["POST", "GET"])
def payos_webhook():
    global _bot_module, _bot_ready
    
    if request.method == "GET":
        return "ok", 200
    
    try:
        if _bot_ready and _bot_module and hasattr(_bot_module, 'handle_payos_webhook'):
            return _bot_module.handle_payos_webhook(request)
        else:
            logger.warning("PayOS webhook received but bot not ready")
            return "ok", 200
    except Exception as e:
        logger.error(f"PayOS webhook error: {e}")
        return "ok", 200

def initialize_bot():
    """Initialize bot after Flask is running"""
    global _bot_module, _bot_ready
    
    logger.info("Waiting 3 seconds for Flask to fully start...")
    time.sleep(3)  # Give Flask time to bind port and respond to Render health check
    
    logger.info("Starting bot initialization...")
    
    try:
        # Import the main bot module - this triggers all the DB connections
        logger.info("Importing store_main module...")
        import store_main
        _bot_module = store_main
        
        _bot_ready = True
        logger.info("Bot initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Bot initialization failed: {e}")
        import traceback
        traceback.print_exc()

def keep_alive():
    """Keep-alive ping to prevent Render from sleeping"""
    render_url = os.getenv('RENDER_EXTERNAL_URL', '')
    if not render_url:
        logger.info("RENDER_EXTERNAL_URL not set, skipping keep-alive")
        return
    
    while True:
        try:
            time.sleep(600)  # 10 minutes
            response = http_requests.get(f"{render_url}/health", timeout=30)
            logger.info(f"Keep-alive ping: {response.status_code}")
        except Exception as e:
            logger.warning(f"Keep-alive failed: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    
    logger.info("=" * 50)
    logger.info(f"Starting Flask on port {port}...")
    logger.info("Bot will initialize after Flask is ready")
    logger.info("=" * 50)
    
    # Start bot initialization in background AFTER Flask starts
    init_thread = threading.Thread(target=initialize_bot, daemon=True)
    init_thread.start()
    
    # Start keep-alive
    if os.getenv('RENDER_EXTERNAL_URL'):
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
    
    # Run Flask - opens port immediately
    # This MUST be called quickly to satisfy Render's port requirement
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
