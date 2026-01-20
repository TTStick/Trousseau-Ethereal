import os
import uuid
import io
import json
import random
import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
from rembg import remove
from PIL import Image
import colorgram

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
                if 'colors' not in item: item['colors'] = [] # 存储格式: ['#Hex', '#Hex']
                if 'logs' not in item: item['logs'] = [] # 存储格式: ['2023-10-01', ...]
            return data
    except:
        return []

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_palette(image_path, count=4):
    """提取颜色，返回 Hex 列表"""
    try:
        # colorgram 需要读取文件
        colors = colorgram.extract(image_path, count)
        hex_colors = []
        for color in colors:
            # 过滤掉近似背景色的颜色 (羊皮纸色)
            r, g, b = color.rgb
            if r > 230 and g > 220 and b > 200: continue 
            hex_colors.append(f"#{r:02x}{g:02x}{b:02x}")
        return hex_colors[:3] # 只取前3个
    except:
        return []

def process_image(input_path, output_path):
    # 1. 抠图
    with open(input_path, 'rb') as i: input_data = i.read()
    subject_data = remove(input_data)
    img = Image.open(io.BytesIO(subject_data)).convert("RGBA")
    
    # 2. 裁剪
    bbox = img.getbbox()
    if bbox: img = img.crop(bbox)
    
    # 3. 填色
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
            
            # 自动提取颜色
            colors = get_palette(processed_path)
            
            db = load_db()
            db.append({
                'id': filename,
                'image': f'clothes/{filename}.jpg',
                'raw_image': f'uploads/{filename}_raw.jpg',
                'note': note,
                'tags': [],
                'colors': colors,
                'logs': [datetime.date.today().strftime("%Y-%m-%d")] # 默认记录添加日期
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
    """更新标签或日志"""
    db = load_db()
    for item in db:
        if item['id'] == id:
            # 处理标签 (逗号分隔)
            if 'tags_input' in request.form:
                tags_str = request.form.get('tags_input', '')
                # 清洗标签
                item['tags'] = [t.strip() for t in tags_str.split(',') if t.strip()]
            
            # 处理新增日志
            if 'new_log_date' in request.form:
                new_date = request.form.get('new_log_date')
                if new_date and new_date not in item['logs']:
                    item['logs'].append(new_date)
                    item['logs'].sort(reverse=True) # 最近日期在前
            
            # 处理颜色修正 (可选)
            # item['colors'] = ...
            
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

# --- 新功能路由 ---

@app.route('/stats')
def stats():
    """统计与预言页"""
    db = load_db()
    count = len(db)
    
    # 标签统计
    all_tags = []
    for i in db: all_tags.extend(i.get('tags', []))
    from collections import Counter
    tag_counts = Counter(all_tags).most_common(5)
    
    return render_template('stats.html', count=count, tag_counts=tag_counts)

@app.route('/oracle')
def oracle():
    """随机返回一件衣服"""
    db = load_db()
    if not db: return redirect(url_for('index'))
    chosen = random.choice(db)
    return redirect(url_for('detail', id=chosen['id']))

@app.route('/collage')
def collage():
    """穿搭拼贴板"""
    db = load_db()
    return render_template('collage.html', clothes=db)

@app.route('/readme')
def readme():
    return render_template('readme.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)