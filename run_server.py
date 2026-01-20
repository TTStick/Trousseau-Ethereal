import os
import uuid
import io
import json
import random
import datetime
import socket  # 新增：用于获取本机IP
from flask import Flask, render_template, request, redirect, url_for, jsonify
from rembg import remove
from PIL import Image
import colorgram
from waitress import serve # 新增：引入生产级服务器

app = Flask(__name__)

# --- 基础配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'static/clothes')
DB_FILE = os.path.join(BASE_DIR, 'wardrobe_db.json')
PARCHMENT_COLOR = (244, 236, 216)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# --- 辅助函数 ---
def load_db():
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 兼容性处理：确保每个项目都有新字段
            for item in data:
                if 'tags' not in item: item['tags'] = []
                if 'colors' not in item: item['colors'] = [] 
                if 'logs' not in item: item['logs'] = [] 
            return data
    except:
        return []

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_palette(image_path, count=4):
    """提取颜色，返回 Hex 列表"""
    try:
        colors = colorgram.extract(image_path, count)
        hex_colors = []
        for color in colors:
            r, g, b = color.rgb
            if r > 230 and g > 220 and b > 200: continue 
            hex_colors.append(f"#{r:02x}{g:02x}{b:02x}")
        return hex_colors[:3] 
    except:
        return []

def process_image(input_path, output_path):
    with open(input_path, 'rb') as i: input_data = i.read()
    subject_data = remove(input_data)
    img = Image.open(io.BytesIO(subject_data)).convert("RGBA")
    
    bbox = img.getbbox()
    if bbox: img = img.crop(bbox)
    
    canvas_size = 800
    canvas = Image.new("RGB", (canvas_size, canvas_size), PARCHMENT_COLOR)
    target_size = int(canvas_size * 0.85)
    img.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
    x = (canvas_size - img.width) // 2
    y = (canvas_size - img.height) // 2
    canvas.paste(img, (x, y), img)
    canvas.save(output_path, quality=95)

# --- 路由 ---

@app.route('/')
def index():
    clothes = load_db()
    return render_template('index.html', clothes=reversed(clothes))

@app.route('/add', methods=['GET', 'POST'])
def add_item():
    if request.method == 'GET': return render_template('add.html')
    
    file = request.files.get('file')
    note = request.form.get('note', '')
    
    if file and file.filename != '':
        try:
            filename = str(uuid.uuid4())
            raw_path = os.path.join(UPLOAD_FOLDER, filename + '_raw.jpg')
            processed_path = os.path.join(PROCESSED_FOLDER, filename + '.jpg')
            
            file.save(raw_path)
            process_image(raw_path, processed_path)
            
            colors = get_palette(processed_path)
            
            db = load_db()
            db.append({
                'id': filename,
                'image': f'clothes/{filename}.jpg',
                'raw_image': f'uploads/{filename}_raw.jpg',
                'note': note,
                'tags': [],
                'colors': colors,
                'logs': [datetime.date.today().strftime("%Y-%m-%d")]
            })
            save_db(db)
            return redirect(url_for('index'))
        except Exception as e:
            print(e)
            return "Error", 500
    return redirect(url_for('index'))

@app.route('/item/<id>')
def detail(id):
    db = load_db()
    item = next((i for i in db if i['id'] == id), None)
    if item: return render_template('detail.html', item=item)
    return "Not Found", 404

@app.route('/update_item/<id>', methods=['POST'])
def update_item(id):
    db = load_db()
    for item in db:
        if item['id'] == id:
            if 'tags_input' in request.form:
                tags_str = request.form.get('tags_input', '')
                item['tags'] = [t.strip() for t in tags_str.split(',') if t.strip()]
            
            if 'new_log_date' in request.form:
                new_date = request.form.get('new_log_date')
                if new_date and new_date not in item['logs']:
                    item['logs'].append(new_date)
                    item['logs'].sort(reverse=True)
            break
    save_db(db)
    return redirect(url_for('detail', id=id))

@app.route('/delete/<id>')
def delete_item(id):
    db = load_db()
    item = next((i for i in db if i['id'] == id), None)
    if item:
        try:
            os.remove(os.path.join(BASE_DIR, 'static', item['image']))
            os.remove(os.path.join(BASE_DIR, 'static', item['raw_image']))
        except: pass
        db = [i for i in db if i['id'] != id]
        save_db(db)
    return redirect(url_for('index'))

@app.route('/stats')
def stats():
    db = load_db()
    count = len(db)
    all_tags = []
    for i in db: all_tags.extend(i.get('tags', []))
    from collections import Counter
    tag_counts = Counter(all_tags).most_common(5)
    return render_template('stats.html', count=count, tag_counts=tag_counts)

@app.route('/oracle')
def oracle():
    db = load_db()
    if not db: return redirect(url_for('index'))
    chosen = random.choice(db)
    return redirect(url_for('detail', id=chosen['id']))

@app.route('/collage')
def collage():
    db = load_db()
    return render_template('collage.html', clothes=db)

@app.route('/readme')
def readme():
    return render_template('readme.html')

# --- 这里是核心修改：获取IP并使用 Waitress 启动 ---
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == '__main__':
    host_ip = get_ip()
    port = 5000  # 使用 5000 端口
    
    print(f"=======================================================")
    print(f" The Ethereal Trousseau is Online (V2.0)")
    print(f"-------------------------------------------------------")
    print(f" [PC访问]    http://localhost:{port}")
    print(f" [手机访问]  http://{host_ip}:{port}")
    print(f"=======================================================")
    
    # 关键修改：host='0.0.0.0' 表示允许局域网连接
    serve(app, host='0.0.0.0', port=port, threads=6)