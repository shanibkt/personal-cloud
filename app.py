import os
import threading
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from werkzeug.utils import secure_filename
from config import Config
from database import db, File, Folder
from telegram_service import telegram_service
import traceback
import sys
import time

# Create the application
app = Flask(__name__)
app.config.from_object(Config)

# Initialize Database
db.init_app(app)
with app.app_context():
    db.create_all()

def log_debug(msg):
    print(f"[Web] {msg}")
    sys.stdout.flush()

@app.route('/debug_status')
def debug_status():
    status = {
        "API_ID_LOADED": bool(Config.API_ID),
        "API_HASH_LOADED": bool(Config.API_HASH),
        "PHONE_NUMBER_LOADED": bool(Config.PHONE_NUMBER),
        "ENV_FILE_EXISTS": getattr(Config, 'DOTENV_EXISTS', 'unknown'),
        "ENV_FILE_LOADED": getattr(Config, 'DOTENV_LOADED', 'unknown'),
        "SESSION_STRING_LOADED": bool(Config.SESSION_STRING),
        "IS_PYTHONANYWHERE": Config.IS_PYTHONANYWHERE,
        "ENV_KEYS": list(os.environ.keys()),
        "TELEGRAM_READY": telegram_service.ready_event.is_set(),
        "THREAD_ALIVE": telegram_service.thread.is_alive() if telegram_service.thread else False,
        "LOG_TAIL": [],
        "UPLOAD_FOLDER": Config.UPLOAD_FOLDER,
        "CWD": os.getcwd(),
        "NETWORK_CHECK": {}
    }
    
    # Test outbound connectivity
    import requests
    try:
        # Test Bot API (should be whitelisted)
        bot_api_check = requests.get("https://api.telegram.org", timeout=5)
        status["NETWORK_CHECK"]["BOT_API_DIRECT"] = bot_api_check.status_code
    except Exception as e:
        status["NETWORK_CHECK"]["BOT_API_DIRECT_ERROR"] = str(e)

    try:
        # Test through proxy
        proxies = {
            "http": f"http://{Config.PROXY_HOST}:{Config.PROXY_PORT}",
            "https": f"http://{Config.PROXY_HOST}:{Config.PROXY_PORT}"
        }
        bot_api_proxy_check = requests.get("https://api.telegram.org", proxies=proxies, timeout=5)
        status["NETWORK_CHECK"]["BOT_API_PROXY"] = bot_api_proxy_check.status_code
    except Exception as e:
        status["NETWORK_CHECK"]["BOT_API_PROXY_ERROR"] = str(e)
    
    try:
        if os.path.exists("telegram_service.log"):
            with open("telegram_service.log", "r") as f:
                status["LOG_TAIL"] = f.readlines()[-20:]
    except Exception as e:
        status["LOG_ERROR"] = str(e)
        
    return jsonify(status)

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/delete_file/<int:file_id>', methods=['POST'])
def do_delete_file(file_id):
    file_record = File.query.get_or_404(file_id)
    try:
        if file_record.telegram_id != 0:
            telegram_service.delete_messages([file_record.telegram_id])
        db.session.delete(file_record)
        db.session.commit()
        flash(f'File "{file_record.name}" deleted.')
    except Exception as e:
        flash(f'Delete failed: {str(e)}')
    return redirect(request.referrer)

@app.route('/bulk_delete_files', methods=['POST'])
def do_bulk_delete():
    file_ids = request.form.getlist('file_ids')
    if not file_ids:
        flash('No files selected.')
        return redirect(request.referrer)
    
    try:
        files = File.query.filter(File.id.in_(file_ids)).all()
        tg_ids = [f.telegram_id for f in files if f.telegram_id != 0]
        
        if tg_ids:
            telegram_service.delete_messages(tg_ids)
            
        for f in files:
            db.session.delete(f)
        db.session.commit()
        flash(f'Deleted {len(files)} items.')
    except Exception as e:
        flash(f'Bulk delete failed: {str(e)}')
        
    return redirect(request.referrer)

@app.route('/dashboard')
@app.route('/dashboard/<int:folder_id>')
def dashboard(folder_id=None):
    current_folder = None
    if folder_id:
        current_folder = Folder.query.get_or_404(folder_id)
        folders = Folder.query.filter_by(parent_id=folder_id).all()
        files = File.query.filter_by(folder_id=folder_id).all()
    else:
        folders = Folder.query.filter_by(parent_id=None).all()
        files = File.query.filter_by(folder_id=None).all()
    
    breadcrumbs = []
    temp = current_folder
    while temp:
        breadcrumbs.insert(0, temp)
        temp = temp.parent if temp.parent_id else None

    return render_template('dashboard.html', 
                           folders=folders, 
                           files=files, 
                           current_folder=current_folder, 
                           breadcrumbs=breadcrumbs)

@app.route('/upload_progress/<task_id>')
def upload_progress(task_id):
    percent = telegram_service.get_progress(task_id)
    return jsonify({"progress": percent})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
    
    folder_id = request.form.get('folder_id')
    folder_id = int(folder_id) if folder_id and folder_id != 'None' else None
    task_id = request.form.get('task_id')

    filename = secure_filename(file.filename)
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    file.save(upload_path)
    
    # Create DB entry (placeholder)
    new_file = File(
        name=filename,
        size=os.path.getsize(upload_path),
        mime_type=file.content_type,
        telegram_id=0,
        chat_id=0,
        folder_id=folder_id
    )
    db.session.add(new_file)
    db.session.commit()
    
    # Submit for background upload
    telegram_service.submit_upload(upload_path, db_file_id=new_file.id, task_id=task_id)
    
    return jsonify({"status": "uploading", "task_id": task_id}), 202

@app.route('/create_folder', methods=['POST'])
def create_folder():
    name = request.form.get('name')
    parent_id = request.form.get('parent_id')
    parent_id = int(parent_id) if parent_id and parent_id != 'None' else None
    
    if name:
        new_folder = Folder(name=name, parent_id=parent_id)
        db.session.add(new_folder)
        db.session.commit()
        flash(f'Folder "{name}" created!')
        
    return redirect(url_for('dashboard', folder_id=parent_id))

@app.route('/download/<int:file_id>')
def download_file(file_id):
    file_record = File.query.get_or_404(file_id)
    if file_record.telegram_id == 0:
        flash('File is still uploading to Telegram. Please wait.')
        return redirect(request.referrer)

    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"dl_{file_record.name}")
    try:
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        with open(temp_path, 'wb') as f:
            telegram_service.download_file_to_stream(file_record.telegram_id, f)
            
        return send_file(temp_path, as_attachment=True, download_name=file_record.name)
    except Exception as e:
        log_debug(f"Download failed: {str(e)}")
        flash(f'Download failed: {str(e)}')
        return redirect(request.referrer)

# Initialize Telegram Service
telegram_service.start(app)

if __name__ == '__main__':
    log_debug("Starting application...")
    # host='0.0.0.0' allows access from other devices on your Wi-Fi (like your phone)
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5002, threaded=True)
