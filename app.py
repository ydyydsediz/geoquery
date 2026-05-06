import sys
import os
import time
import webbrowser
import uuid
import threading
import json
import re
import datetime
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
CONFIG_FILE = os.path.join(BASE_PATH, 'config.json')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app = Flask(__name__, template_folder=get_template_folder())
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

tasks = {}

# ---------- 配置持久化 ----------

DEFAULT_CONFIG = {
    "api_keys": [],
    "mode": "forward",
    "coord_system": "gcj02"
}


def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update(cfg)
            return merged
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------- API Key 管理 ----------

class ApiKeyManager:
    def __init__(self, keys=None):
        self.keys = keys or []
        self.current_index = 0
        self.quotas = {}  # key -> {"date": "YYYY-MM-DD", "count": int}
        self.daily_limit = 5000  # 高德免费版每日限额

    def set_keys(self, keys):
        self.keys = [k.strip() for k in keys if k.strip()]
        self.current_index = 0

    def get_key(self):
        if not self.keys:
            return None
        key = self.keys[self.current_index % len(self.keys)]
        self.current_index += 1
        return key

    def mark_quota_exceeded(self, key):
        today = datetime.date.today().isoformat()
        if key not in self.quotas:
            self.quotas[key] = {"date": today, "count": self.daily_limit}
        else:
            self.quotas[key] = {"date": today, "count": self.daily_limit}
        self._save_quotas()

    def record_usage(self, key):
        today = datetime.date.today().isoformat()
        if key not in self.quotas:
            self.quotas[key] = {"date": today, "count": 0}
        q = self.quotas[key]
        if q["date"] != today:
            q["date"] = today
            q["count"] = 0
        q["count"] += 1
        self._save_quotas()
        if q["count"] >= self.daily_limit:
            self.mark_quota_exceeded(key)

    def get_quotas(self):
        today = datetime.date.today().isoformat()
        result = []
        for key in self.keys:
            q = self.quotas.get(key, {"date": today, "count": 0})
            if q["date"] != today:
                q = {"date": today, "count": 0}
            remaining = max(0, self.daily_limit - q["count"])
            result.append({
                "key": key,
                "used": q["count"],
                "limit": self.daily_limit,
                "remaining": remaining,
                "exhausted": remaining <= 0
            })
        return result

    def get_available_keys(self):
        today = datetime.date.today().isoformat()
        available = []
        for key in self.keys:
            q = self.quotas.get(key, {"date": today, "count": 0})
            if q["date"] != today:
                q = {"date": today, "count": 0}
            if q["count"] < self.daily_limit:
                available.append(key)
        return available

    def _save_quotas(self):
        try:
            data = {"quotas": self.quotas, "daily_limit": self.daily_limit}
            quota_file = os.path.join(BASE_PATH, 'quotas.json')
            with open(quota_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_quotas(self):
        try:
            quota_file = os.path.join(BASE_PATH, 'quotas.json')
            if os.path.exists(quota_file):
                with open(quota_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.quotas = data.get("quotas", {})
                self.daily_limit = data.get("daily_limit", 5000)
        except Exception:
            pass


key_manager = ApiKeyManager()

# 启动时加载配置
_config = load_config()
key_manager.set_keys(_config.get("api_keys", []))
key_manager._load_quotas()


import math

PI = math.pi
X_PI = PI * 3000.0 / 180.0
A = 6378245.0
EE = 0.00669342162296594323


def _out_of_china(lng, lat):
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(lng, lat):
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * PI) + 40.0 * math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * PI) + 320 * math.sin(lat * PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng, lat):
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * PI) + 40.0 * math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * PI) + 300.0 * math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lng, lat):
    if _out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return lng * 2 - (lng + dlng), lat * 2 - (lat + dlat)


def gcj02_to_bd09(lng, lat):
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * X_PI)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * X_PI)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def convert_coords(lng, lat, target):
    if target == "wgs84" or target == "cgcs2000":
        return gcj02_to_wgs84(lng, lat)
    elif target == "bd09":
        return gcj02_to_bd09(lng, lat)
    return lng, lat


_DMS_PATTERN = re.compile(
    r"(?P<deg>[\d.]+)\s*[°ºd]\s*"
    r"(?P<min>[\d.]+)\s*['\u2032m]\s*"
    r'(?P<sec>[\d.]+)\s*["\u2033s]?\s*'
    r"(?P<dir>[NSEWnsew]?)"
)


def parse_dms(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None

    sign = 1
    if s.startswith('-') or re.match(r'^[SWsw]', s):
        sign = -1

    m = _DMS_PATTERN.search(s)
    if m:
        deg = float(m.group('deg'))
        minute = float(m.group('min'))
        second = float(m.group('sec'))
        direction = m.group('dir').upper()
        dd = deg + minute / 60.0 + second / 3600.0
        if direction in ('S', 'W'):
            dd = -abs(dd)
        elif sign == -1:
            dd = -abs(dd)
        return dd

    s_clean = s.lstrip('NSEWnsew+-').strip()
    try:
        return float(s_clean) * sign
    except (ValueError, TypeError):
        return None


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


def reverse_geocode(lng, lat, api_key):
    try:
        url = "https://restapi.amap.com/v3/geocode/regeo"
        params = {"key": api_key, "location": f"{lng},{lat}", "output": "JSON"}
        r = requests.get(url, params=params, timeout=10, proxies={"http": "", "https": ""})
        data = r.json()
        if data["status"] == "1" and data.get("regeocode"):
            addr = data["regeocode"]
            formatted = addr.get("formatted_address", "")
            province = addr["addressComponent"].get("province", "")
            city = addr["addressComponent"].get("city", "")
            district = addr["addressComponent"].get("district", "")
            return formatted, province, city, district
    except Exception:
        pass
    return None, None, None, None


def process_task(task_id, file_path, ext, original_name, coord_system="gcj02"):
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

            api_key = key_manager.get_key()
            if not api_key:
                task["status"] = "error"
                task["error"] = "没有可用的 API Key"
                return

            lng, lat = query_amap(str(place), api_key)
            key_manager.record_usage(api_key)

            if lng is not None:
                out_lng, out_lat = convert_coords(lng, lat, coord_system)
                results.append({"地名": str(place), "经度": out_lng, "纬度": out_lat})
                task["result_index"] = i
                task["last_result"] = {"place": str(place), "lng": out_lng, "lat": out_lat, "found": True}
            else:
                results.append({"地名": str(place), "经度": None, "纬度": None})
                task["result_index"] = i
                task["last_result"] = {"place": str(place), "lng": None, "lat": None, "found": False}

            time.sleep(0.3)

        coord_label = {"gcj02": "", "wgs84": "_WGS84", "cgcs2000": "_CGCS2000", "bd09": "_BD09"}.get(coord_system, "")
        result_df = pd.DataFrame(results)
        output_name = f"{original_name}_result{coord_label}{ext}"
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


def process_reverse_task(task_id, file_path, ext, original_name, coord_system="gcj02"):
    task = tasks[task_id]
    task["status"] = "processing"

    try:
        if ext == ".csv":
            df = pd.read_csv(file_path, header=None)
        else:
            df = pd.read_excel(file_path, header=None)

        rows = df.dropna(subset=[0, 1]).values.tolist()
        task["total"] = len(rows)
        results = []

        for i, row in enumerate(rows):
            task["current"] = i + 1
            lng = parse_dms(row[0])
            lat = parse_dms(row[1])
            if lng is None or lat is None:
                results.append({"经度": None, "纬度": None, "详细地址": None, "省份": None, "城市": None, "区县": None})
                task["result_index"] = i
                task["last_result"] = {"lng": None, "lat": None, "address": None, "found": False}
                continue
            task["current_place"] = f"{lng},{lat}"

            api_key = key_manager.get_key()
            if not api_key:
                task["status"] = "error"
                task["error"] = "没有可用的 API Key"
                return

            formatted, province, city, district = reverse_geocode(lng, lat, api_key)
            key_manager.record_usage(api_key)

            if formatted:
                out_lng, out_lat = convert_coords(lng, lat, coord_system)
                results.append({"经度": out_lng, "纬度": out_lat, "详细地址": formatted, "省份": province, "城市": city, "区县": district})
                task["last_result"] = {"lng": out_lng, "lat": out_lat, "address": formatted, "found": True}
            else:
                out_lng, out_lat = convert_coords(lng, lat, coord_system)
                results.append({"经度": out_lng, "纬度": out_lat, "详细地址": None, "省份": None, "城市": None, "区县": None})
                task["last_result"] = {"lng": out_lng, "lat": out_lat, "address": None, "found": False}

            task["result_index"] = i
            time.sleep(0.3)

        coord_label = {"gcj02": "", "wgs84": "_WGS84", "cgcs2000": "_CGCS2000", "bd09": "_BD09"}.get(coord_system, "")
        result_df = pd.DataFrame(results)
        output_name = f"{original_name}_reverse{coord_label}{ext}"
        output_path = os.path.join(RESULT_FOLDER, output_name)

        if ext == ".csv":
            result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        else:
            result_df.to_excel(output_path, index=False)

        task["status"] = "done"
        task["result_file"] = output_path
        task["result_name"] = output_name
        task["found_count"] = sum(1 for r in results if r["详细地址"] is not None)
        task["not_found_count"] = sum(1 for r in results if r["详细地址"] is None)

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify({
            "api_keys": key_manager.keys,
            "mode": load_config().get("mode", "forward"),
            "coord_system": load_config().get("coord_system", "gcj02"),
            "quotas": key_manager.get_quotas()
        })

    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "无效的请求数据"}), 400

    cfg = load_config()

    if "api_keys" in data:
        keys = data["api_keys"]
        cfg["api_keys"] = keys
        key_manager.set_keys(keys)

    if "mode" in data:
        cfg["mode"] = data["mode"]

    if "coord_system" in data:
        cfg["coord_system"] = data["coord_system"]

    save_config(cfg)
    return jsonify({"ok": True, "quotas": key_manager.get_quotas()})


@app.route("/api/quotas")
def api_quotas():
    return jsonify({"quotas": key_manager.get_quotas()})


@app.route("/upload", methods=["POST"])
def upload():
    api_keys_raw = request.form.get("api_keys", "").strip()
    if api_keys_raw:
        keys = [k.strip() for k in api_keys_raw.split(",") if k.strip()]
        if keys:
            key_manager.set_keys(keys)

    if not key_manager.keys:
        return jsonify({"error": "请至少配置一个高德 API Key"}), 400

    coord_system = request.form.get("coord_system", "gcj02")

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

    thread = threading.Thread(target=process_task, args=(task_id, file_path, ext, original_name, coord_system), daemon=True)
    thread.start()

    return jsonify({"task_id": task_id})


@app.route("/reverse-upload", methods=["POST"])
def reverse_upload():
    api_keys_raw = request.form.get("api_keys", "").strip()
    if api_keys_raw:
        keys = [k.strip() for k in api_keys_raw.split(",") if k.strip()]
        if keys:
            key_manager.set_keys(keys)

    if not key_manager.keys:
        return jsonify({"error": "请至少配置一个高德 API Key"}), 400

    coord_system = request.form.get("coord_system", "gcj02")

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

    thread = threading.Thread(target=process_reverse_task, args=(task_id, file_path, ext, original_name, coord_system), daemon=True)
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
