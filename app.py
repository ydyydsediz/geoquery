import sys
import os
import time
import webbrowser
import uuid
import threading
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file, render_template


def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_template_folder():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'templates')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')


for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
    os.environ[k] = ""

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_PATH = get_base_path()
UPLOAD_FOLDER = os.path.join(BASE_PATH, 'uploads')
RESULT_FOLDER = os.path.join(BASE_PATH, 'results')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app = Flask(__name__, template_folder=get_template_folder())
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

tasks = {}


def query_amap(address, api_key):
    try:
        url = "https://restapi.amap.com/v3/place/text"
        params = {"key": api_key, "keywords": address, "output": "JSON"}
        r = requests.get(url, params=params, timeout=10, proxies={"http": "", "https": ""})
        data = r.json()
        if data["status"] == "1" and int(data.get("count", 0)) > 0:
            loc = data["pois"][0]["location"]
            lng, lat = loc.split(",")
            return float(lng), float(lat)
    except Exception:
        pass
    return None, None


def process_task(task_id, file_path, api_key, ext, original_name):
    task = tasks[task_id]
    task["status"] = "processing"

    try:
        if ext == ".csv":
            df = pd.read_csv(file_path, header=None)
        else:
            df = pd.read_excel(file_path, header=None)

        places = df.iloc[:, 0].dropna().tolist()
        task["total"] = len(places)
        results = []

        for i, place in enumerate(places):
            task["current"] = i + 1
            task["current_place"] = str(place)

            lng, lat = query_amap(str(place), api_key)

            if lng is not None:
                results.append({"地名": str(place), "经度": lng, "纬度": lat})
                task["result_index"] = i
                task["last_result"] = {"place": str(place), "lng": lng, "lat": lat, "found": True}
            else:
                results.append({"地名": str(place), "经度": None, "纬度": None})
                task["result_index"] = i
                task["last_result"] = {"place": str(place), "lng": None, "lat": None, "found": False}

            time.sleep(0.3)

        result_df = pd.DataFrame(results)
        output_name = f"{original_name}_result{ext}"
        output_path = os.path.join(RESULT_FOLDER, output_name)

        if ext == ".csv":
            result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        else:
            result_df.to_excel(output_path, index=False)

        task["status"] = "done"
        task["result_file"] = output_path
        task["result_name"] = output_name
        task["found_count"] = sum(1 for r in results if r["经度"] is not None)
        task["not_found_count"] = sum(1 for r in results if r["经度"] is None)

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    api_key = request.form.get("api_key", "").strip()
    if not api_key:
        return jsonify({"error": "请输入高德 API Key"}), 400

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "请上传文件"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        return jsonify({"error": "仅支持 .xlsx / .xls / .csv 文件"}), 400

    task_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_FOLDER, f"{task_id}{ext}")
    file.save(file_path)

    original_name = os.path.splitext(file.filename)[0]

    tasks[task_id] = {
        "status": "starting",
        "total": 0,
        "current": 0,
        "current_place": "",
        "result_index": -1,
        "last_result": None,
        "result_file": None,
        "result_name": None,
        "found_count": 0,
        "not_found_count": 0,
        "error": None,
    }

    thread = threading.Thread(target=process_task, args=(task_id, file_path, api_key, ext, original_name), daemon=True)
    thread.start()

    return jsonify({"task_id": task_id})


@app.route("/progress/<task_id>")
def progress(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    data = dict(task)
    if task["status"] == "done" and task.get("result_file"):
        data["download_url"] = f"/download/{task_id}"
    return jsonify(data)


@app.route("/download/<task_id>")
def download(task_id):
    task = tasks.get(task_id)
    if not task or not task.get("result_file"):
        return jsonify({"error": "文件不存在"}), 404
    return send_file(task["result_file"], as_attachment=True, download_name=task["result_name"])


if __name__ == "__main__":
    port = 5000
    url = f"http://127.0.0.1:{port}"
    print(f"服务已启动，正在打开浏览器: {url}")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)
