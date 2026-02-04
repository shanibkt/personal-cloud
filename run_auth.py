import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import Config

async def main():
    print("Authenticating to generate a StringSession...")
    
    # We start with an empty StringSession
    session = StringSession()
    
    client = TelegramClient(session, Config.API_ID, Config.API_HASH)
    
    # This will ask for code interactively in the terminal
    await client.start(phone=Config.PHONE_NUMBER)
    
    # After successful login, generate the string
    session_string = client.session.save()
    
    me = await client.get_me()
    print("\n" + "="*50)
    print(f"SUCCESS! Logged in as: {me.first_name}")
    print("\nYOUR SESSION STRING IS BELOW (Copy everything correctly):")
    print(session_string)
    print("="*50)
    print("\n1. Copy this string.")
    print("2. Paste it in your .env file as: TELEGRAM_SESSION_STRING=your_string_here")
    print("3. Then run 'python app.py'.")
    
    await client.disconnect()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
