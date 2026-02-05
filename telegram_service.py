import os
import asyncio
import threading
import queue
import sys
import time
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import Config

class TelegramService:
    def __init__(self):
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH
        self.phone = Config.PHONE_NUMBER
        self.session_string = Config.SESSION_STRING
        
        self.loop = None
        self.client = None
        self.thread = None
        self.ready_event = threading.Event()
        self.app = None # To be set by app.py
        
        # Communication queues
        self.request_queue = queue.Queue()
        self.result_queues = {}
        
        # Progress tracking: { task_id: percentage }
        self.progress_data = {}

    def _progress_callback(self, current, total, task_id):
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_data[task_id] = percent

    def get_progress(self, task_id):
        if task_id not in self.progress_data:
            # self._log(f"Warning: task_id {task_id} not found")
            return 0
        return self.progress_data.get(task_id, 0)

    def _log(self, msg):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [TelegramService] {msg}"
        print(log_msg)
        sys.stdout.flush()
        # Also log to a file for persistence on PythonAnywhere
        try:
            with open("telegram_service.log", "a") as f:
                f.write(log_msg + "\n")
        except:
            pass

    def start(self, flask_app=None):
        """Starts the background thread with its own asyncio loop."""
        self.app = flask_app
        if self.thread and self.thread.is_alive():
            return

        if not self.api_id or not self.api_hash:
            self._log("CRITICAL ERROR: API_ID or API_HASH missing from environment variables!")
            self.ready_event.set() # Set it so the app doesn't show "sleeping" but can show specific errors
            return

        def run_loop():
            try:
                self._log("Starting background thread...")
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
                # Use a specific session folder on PythonAnywhere
                basedir = os.path.dirname(os.path.abspath(__file__))
                session_dir = os.path.join(basedir, "sessions")
                if not os.path.exists(session_dir):
                    os.makedirs(session_dir)
                
                session_path = os.path.join(session_dir, Config.SESSION_NAME)
                session = StringSession(self.session_string) if self.session_string else session_path
                
                # Proxy configuration with remote DNS enabled
                proxy = None
                if Config.IS_PYTHONANYWHERE:
                    try:
                        import socks
                        # The 4th argument 'True' enables remote DNS (rdns)
                        proxy = (socks.HTTP, Config.PROXY_HOST, Config.PROXY_PORT, True)
                        self._log(f"Using PA Proxy: {Config.PROXY_HOST}:{Config.PROXY_PORT} with RDNS")
                    except ImportError:
                        self._log("PySocks NOT INSTALLED! Proxy will not work.")
                
                from telethon import connection
                self.client = TelegramClient(
                    session, 
                    self.api_id, 
                    self.api_hash, 
                    loop=self.loop, 
                    proxy=proxy,
                    connection=connection.ConnectionTcpAbridged
                )
                
                async def worker():
                    try:
                        self._log("Connecting to Telegram (Abridged)...")
                        # Try to connect with a longer timeout
                        await asyncio.wait_for(self.client.connect(), timeout=30)
                        
                        authorized = await self.client.is_user_authorized()
                        if not authorized:
                            self._log("!!! AUTH ERROR: Session String might be invalid or expired.")
                            self._log("Please generate a NEW ONE using run_auth.py locally.")
                        else:
                            self._log("Client connected and authorized successfully.")
                        
                        self.ready_event.set()
                        if not authorized: return
                        
                        session_str = self.client.session.save()
                        with open(os.path.join(basedir, "SESSION_STRING_FOR_RENDER.txt"), "w") as f:
                            f.write(session_str)
                        
                        self._log("Session string saved.")
                        self.ready_event.set()
                        
                        while True:
                            try:
                                try:
                                    req = self.request_queue.get_nowait()
                                except queue.Empty:
                                    await asyncio.sleep(0.1)
                                    continue
                                    
                                thread_id, cmd, args = req
                                self._log(f"Processing command: {cmd}")
                                
                                try:
                                    if cmd == 'upload':
                                        task_id = args.get('task_id', thread_id)
                                        db_file_id = args.get('db_file_id')
                                        self.progress_data[task_id] = 0
                                        
                                        msg = await self.client.send_file(
                                            'me', 
                                            args['path'],
                                            progress_callback=lambda c, t: self._progress_callback(c, t, task_id)
                                        )
                                        
                                        self.progress_data[task_id] = 100
                                        self._log(f"Upload done for task {task_id}. Msg ID: {msg.id}")
        
                                        # Update Database
                                        if self.app and db_file_id:
                                            from database import db, File
                                            with self.app.app_context():
                                                file_record = File.query.get(db_file_id)
                                                if file_record:
                                                    file_record.telegram_id = msg.id
                                                    file_record.chat_id = msg.chat_id
                                                    db.session.commit()
                                                    self._log(f"Database updated for file {db_file_id}")
        
                                        if os.path.exists(args['path']):
                                            os.remove(args['path'])
                                        
                                        if thread_id in self.result_queues:
                                            self.result_queues[thread_id].put(('ok', {'id': msg.id}))
        
                                    elif cmd == 'download':
                                        message = await self.client.get_messages('me', ids=args['msg_id'])
                                        if message:
                                            await self.client.download_media(message, args['output'])
                                            self.result_queues[thread_id].put(('ok', None))
                                        else:
                                            self.result_queues[thread_id].put(('error', "Message not found"))
        
                                    elif cmd == 'delete':
                                        await self.client.delete_messages('me', args['msg_ids'])
                                        self.result_queues[thread_id].put(('ok', None))
                                        
                                except Exception as e:
                                    self._log(f"Error in command {cmd}: {e}")
                                    if thread_id in self.result_queues:
                                        self.result_queues[thread_id].put(('error', str(e)))
                                    if cmd == 'upload':
                                        self.progress_data[args.get('task_id', thread_id)] = -1
                                    
                            except Exception as e:
                                self._log(f"Worker loop error: {e}")
                                await asyncio.sleep(1)
                    except Exception as e:
                        self._log(f"Worker startup error: {e}")
                        self.ready_event.set() 

                self.loop.run_until_complete(worker())
            except Exception as e:
                self._log(f"Background thread crash: {e}")
                self.ready_event.set()

        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
        # Do NOT wait here; let the web server finish starting up.
        # We will wait inside _send_request only when a real request comes in.

    def _send_request(self, cmd, args):
        # If the service isn't ready, wait up to 45 seconds (important for slow proxy connections)
        if not self.ready_event.is_set():
            self._log("Service not ready yet, waiting...")
            if not self.ready_event.wait(timeout=45):
                raise Exception("Telegram service is sleeping or not initialized. Check your credentials and connection.")
        
        thread_id = threading.get_ident()
        res_q = queue.Queue()
        self.result_queues[thread_id] = res_q
        try:
            self.request_queue.put((thread_id, cmd, args))
            status, val = res_q.get(timeout=300)
            if status == 'error': raise Exception(val)
            return val
        finally:
            self.result_queues.pop(thread_id, None)

    def upload_file(self, path, task_id=None): # Sync version
        return self._send_request('upload', {'path': path, 'task_id': task_id})

    def submit_upload(self, path, db_file_id, task_id=None): # Async version
        self.request_queue.put((f"async_{task_id}", 'upload', {
            'path': path, 
            'task_id': task_id, 
            'db_file_id': db_file_id
        }))
        return True

    def download_file_to_stream(self, msg_id, output):
        return self._send_request('download', {'msg_id': int(msg_id), 'output': output})

    def delete_messages(self, msg_ids):
        # Ensure IDs are integers
        clean_ids = [int(mid) for mid in msg_ids if mid]
        if clean_ids:
            return self._send_request('delete', {'msg_ids': clean_ids})
        return True

telegram_service = TelegramService()
