"""
Simple test to verify telegram_service queue system works
"""
import sys
import time
sys.path.insert(0, 'c:/Users/shani/Desktop/cloude-project')

from telegram_service import telegram_service

print("Starting Telegram service...")
telegram_service.start()

print("Waiting for service to be ready...")
time.sleep(3)

print("Testing upload with a dummy file...")
try:
    # Create a test file
    with open('test_upload.txt', 'w') as f:
        f.write('This is a test file for upload')
    
    result = telegram_service.upload_file('test_upload.txt')
    print(f"SUCCESS! Upload result: {result}")
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
