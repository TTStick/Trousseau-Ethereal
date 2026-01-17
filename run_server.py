# run_server.py
from waitress import serve
from app import app
import socket

# 获取本机局域网 IP 地址，方便你查看
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 并不真的连接，只是为了获取IP
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == '__main__':
    host_ip = get_ip()
    port = 8080
    
    print(f"-------------------------------------------------------")
    print(f" The Ethereal Trousseau is Online.")
    print(f" Access via PC:   http://localhost:{port}")
    print(f" Access via Phone: http://{host_ip}:{port}")
    print(f"-------------------------------------------------------")
    
    # 启动生产级服务器

    serve(app, host='0.0.0.0', port=port)
