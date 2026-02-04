import asyncio
from telegram_service import telegram_service

async def main():
    print("Starting Telegram authentication...")
    await telegram_service.start()
    me = await telegram_service.client.get_me()
    print(f"Successfully logged in as: {me.first_name} (@{me.username})")

if __name__ == "__main__":
    # Windows SelectorEventLoopPolicy fix if needed (Python 3.8+)
    # import sys
    # if sys.platform == 'win32':
    #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
