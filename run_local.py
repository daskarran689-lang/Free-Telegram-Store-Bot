"""
Local development runner for Telegram Store Bot
Automatically starts ngrok and updates webhook URL
"""
import subprocess
import time
import requests
import os
import sys

def get_ngrok_url():
    """Get the public URL from ngrok"""
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        tunnels = response.json().get("tunnels", [])
        for tunnel in tunnels:
            if tunnel.get("proto") == "https":
                return tunnel.get("public_url")
    except:
        pass
    return None

def start_ngrok(port=5000):
    """Start ngrok in background"""
    print(f"[INFO] Starting ngrok on port {port}...")
    subprocess.Popen(
        ["ngrok", "http", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    )
    
    # Wait for ngrok to start
    for i in range(10):
        time.sleep(1)
        url = get_ngrok_url()
        if url:
            return url
        print(f"[INFO] Waiting for ngrok... ({i+1}/10)")
    
    return None

def update_env_file(ngrok_url):
    """Update config.env with ngrok URL"""
    env_file = "config.env"
    
    if not os.path.exists(env_file):
        print(f"[ERROR] {env_file} not found!")
        return False
    
    with open(env_file, "r") as f:
        lines = f.readlines()
    
    with open(env_file, "w") as f:
        for line in lines:
            if line.startswith("NGROK_HTTPS_URL="):
                f.write(f"NGROK_HTTPS_URL={ngrok_url}\n")
            else:
                f.write(line)
    
    print(f"[OK] Updated {env_file} with NGROK_HTTPS_URL={ngrok_url}")
    return True

def main():
    print("=" * 50)
    print("  Telegram Store Bot - Local Development")
    print("=" * 50)
    print()
    
    # Check if ngrok is already running
    ngrok_url = get_ngrok_url()
    
    if not ngrok_url:
        ngrok_url = start_ngrok(5000)
    
    if not ngrok_url:
        print("[ERROR] Could not get ngrok URL!")
        print("[INFO] Please start ngrok manually: ngrok http 5000")
        print("[INFO] Then update config.env with the HTTPS URL")
        return
    
    print(f"\n[OK] Ngrok URL: {ngrok_url}")
    print()
    
    # Update config.env
    update_env_file(ngrok_url)
    
    print()
    print("=" * 50)
    print("  Starting bot...")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    print()
    
    # Run the bot
    os.system("python store_main.py")

if __name__ == "__main__":
    main()
