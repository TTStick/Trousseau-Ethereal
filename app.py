import os
import uuid
import io
import json
from flask import Flask, render_template, request, redirect, url_for
from rembg import remove
from PIL import Image

app = Flask(__name__)

# --- 配置路径 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'static/clothes')
DB_FILE = os.path.join(BASE_DIR, 'wardrobe_db.json') # 数据存储文件

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# --- 视觉配置 ---
PARCHMENT_COLOR = (244, 236, 216)

# --- 数据库辅助函数 (JSON持久化) ---
def load_db():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def process_image(input_path, output_path):
    """ 处理图片：抠图 -> 裁剪 -> 居中 -> 填色 """
    with open(input_path, 'rb') as i:
        input_data = i.read()
    
    subject_data = remove(input_data)
    img = Image.open(io.BytesIO(subject_data)).convert("RGBA")
    
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    
    canvas_size = 800
    canvas = Image.new("RGB", (canvas_size, canvas_size), PARCHMENT_COLOR)
    target_size = int(canvas_size * 0.85)
    img.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
    
    x = (canvas_size - img.width) // 2
    y = (canvas_size - img.height) // 2
    
    canvas.paste(img, (x, y), img)
    canvas.save(output_path, quality=95)

# --- 路由定义 ---

@app.route('/')
def index():
    clothes = load_db()
    # 倒序排列，最新添加的显示在前面
    return render_template('index.html', clothes=reversed(clothes))

@app.route('/add', methods=['GET', 'POST'])
def add_item():
    if request.method == 'GET':
        return render_template('add.html')
    
    if 'file' not in request.files: return redirect(request.url)
    file = request.files['file']
    note = request.form.get('note', '')
    
    if file.filename == '': return redirect(request.url)

    if file:
        try:
            filename = str(uuid.uuid4())
            raw_filename = filename + '_raw.jpg'
            processed_filename = filename + '.jpg'
            
            raw_path = os.path.join(UPLOAD_FOLDER, raw_filename)
            processed_path = os.path.join(PROCESSED_FOLDER, processed_filename)
            
            file.save(raw_path)
            process_image(raw_path, processed_path)
            
            # 读取旧数据 -> 添加新数据 -> 保存
            db = load_db()
            db.append({
                'id': filename,
                'image': f'clothes/{processed_filename}',
                'raw_image': f'uploads/{raw_filename}', # 记录原图路径方便删除
                'note': note
            })
            save_db(db)
            
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Error: {e}")
            return f"Error: {e}", 500

@app.route('/item/<id>')
def detail(id):
    db = load_db()
    item = next((i for i in db if i['id'] == id), None)
    if item:
        return render_template('detail.html', item=item)
    return "Item not found", 404

@app.route('/delete/<id>')
def delete_item(id):
    """删除功能"""
    db = load_db()
    # 找到要删除的项目
    item = next((i for i in db if i['id'] == id), None)
    
    if item:
        # 1. 尝试删除物理文件
        try:
            processed_path = os.path.join(BASE_DIR, 'static', item['image'])
            raw_path_rel = item.get('raw_image')
            
            if os.path.exists(processed_path):
                os.remove(processed_path)
            
            if raw_path_rel:
                raw_path = os.path.join(BASE_DIR, 'static', raw_path_rel)
                if os.path.exists(raw_path):
                    os.remove(raw_path)
        except Exception as e:
            print(f"Error deleting files: {e}")

        # 2. 从列表中移除并保存
        db = [i for i in db if i['id'] != id]
        save_db(db)
        
    return redirect(url_for('index'))

@app.route('/readme')
def readme():
    return render_template('readme.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)