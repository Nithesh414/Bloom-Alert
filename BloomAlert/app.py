# --- full app.py (updated) ---
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import pandas as pd
import os
import time
import requests

# --- Flask setup ---
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', 'change-me-in-production')

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# OpenWeather API key (env override recommended)
app.config['OPENWEATHER_API_KEY'] = os.getenv('OPENWEATHER_API_KEY', '8521546e5718899860daefbce97bea4e')

# Uploads should be placed under static/uploads so they are served
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Simple in-memory caches
_weather_cache = {}
_forecast_cache = {}
_aqi_cache = {}
CACHE_TTL = 10 * 60  # 10 minutes

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    reports = db.relationship('Report', backref='user', lazy=True)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_filename = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255))
    date_time = db.Column(db.String(255))
    flower_name = db.Column(db.String(255))       # New field for flower name
    intensity = db.Column(db.String(50))          # New field for bloom intensity

with app.app_context():
    db.create_all()

# --- Helpers ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            flash('Please login to continue.', 'error')
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated

def load_ndvi_records():
    csv_path = os.path.join('data', 'ndvi_sample.csv')
    try:
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            if 'month' in df.columns and 'ndvi' in df.columns:
                return df[['month','ndvi']].to_dict(orient='records')
            if 'date' in df.columns and 'ndvi' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df['month'] = df['date'].dt.strftime('%b')
                months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
                monthly = df.groupby('month', sort=False)['ndvi'].mean().reset_index()
                monthly = monthly.set_index('month').reindex(months).dropna().reset_index()
                return monthly.to_dict(orient='records')
    except Exception:
        pass
    return [
        {"month":"Jan","ndvi":0.65},
        {"month":"Feb","ndvi":0.70},
        {"month":"Mar","ndvi":0.75},
        {"month":"Apr","ndvi":0.72},
        {"month":"May","ndvi":0.68},
        {"month":"Jun","ndvi":0.74},
    ]

# --- Routes: Pages ---
@app.route('/')
@login_required
def home():
    return render_template('home.html')

@app.route('/auth', methods=['GET','POST'])
def auth():
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        if action == 'register':
            if User.query.filter_by(username=username).first():
                flash('Username exists', 'error')
                return redirect(url_for('auth'))
            user = User(username=username, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash('Registered. Please login.', 'success')
            return redirect(url_for('auth'))
        elif action == 'login':
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                session['username'] = username
                flash('Logged in', 'success')
                return redirect(url_for('home'))
            flash('Invalid credentials', 'error')
            return redirect(url_for('auth'))
    return render_template('auth.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('username', None)
    flash('Logged out', 'success')
    return redirect(url_for('auth'))

@app.route('/report')
@login_required
def report_detect():
    # Synthetic/real NASA bloom NDVI sample data
    reports = [
        {'location': 'Valley 1', 'date': '2025-03-10', 'ndvi': 0.73, 'blooming': True},
        {'location': 'Valley 1', 'date': '2025-05-15', 'ndvi': 0.61, 'blooming': True},
        {'location': 'Field A',  'date': '2025-02-11', 'ndvi': 0.48, 'blooming': False},
        {'location': 'Park North','date': '2025-04-13','ndvi':0.68, 'blooming':True},
        {'location': 'Village Z', 'date': '2025-03-20', 'ndvi': 0.43, 'blooming': False},
        {'location': 'Field B',  'date': '2025-06-22', 'ndvi': 0.77, 'blooming': True},
        {'location': 'Foothills', 'date': '2025-05-02', 'ndvi': 0.39, 'blooming': False},
        {'location': 'Ridge S', 'date': '2025-05-12', 'ndvi': 0.82, 'blooming': True}
    ]
    return render_template('report_detect.html', reports=reports)


@app.route('/camera')
@login_required
def camera():
    return render_template('camera.html')

@app.route('/calendar')
@login_required
def calendar_learn():
    return render_template('calendar_learn.html')

@app.route('/about')
@login_required
def about_admin():
    return render_template('about_admin.html')

@app.route('/report')
@login_required
def report_detect_with_data():
    user = User.query.filter_by(username=session['username']).first()
    reports = Report.query.filter_by(user_id=user.id).order_by(Report.date_time.desc()).all()
    return render_template('report_detect.html', reports=reports)


# --- Upload / Detect ---
@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('flowerImage')
    if not file or file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('report_detect'))

    location = request.form.get('location')
    date_time = request.form.get('dateTime')
    flower_name = request.form.get('flower_name')    # get flower name
    intensity = request.form.get('intensity')        # get bloom intensity

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        user = User.query.filter_by(username=session['username']).first()
        new_report = Report(
            user_id=user.id,
            image_filename=filename,
            location=location,
            date_time=date_time,
            flower_name=flower_name,
            intensity=intensity
        )
        db.session.add(new_report)
        db.session.commit()
        flash('Uploaded successfully', 'success')
        return redirect(url_for('report_detect'))

    flash('Invalid file type', 'error')
    return redirect(url_for('report_detect'))

@app.route('/api/reports')
@login_required
def api_reports():
    """Return all bloom reports for calendar page."""
    reports = Report.query.all()
    return jsonify([
        {
            'date_time': r.date_time,
            'flower_name': r.flower_name,
            'location': r.location,
            'intensity': r.intensity,
            'image': url_for('static', filename='uploads/' + r.image_filename)
        } for r in reports
    ])

# --- Existing detect, NDVI, bloom summary, weather, forecast, AQI APIs ---  
# (All existing functionality below remains unchanged)
@app.route('/detect', methods=['POST'])
@login_required
def detect():
    if 'detectImage' not in request.files:
        return jsonify({'error':'no image provided'}), 400
    file = request.files['detectImage']
    if file.filename == '':
        return jsonify({'error':'no filename'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        predicted = "Unknown"
        name = filename.lower()
        if 'full' in name:
            predicted = "Full Bloom"
        elif 'partial' in name:
            predicted = "Partial Bloom"
        else:
            size = os.path.getsize(save_path)
            if size > 200000:
                predicted = "Full Bloom"
            elif size > 80000:
                predicted = "Partial Bloom"
            else:
                predicted = "No Bloom"
        return jsonify({'prediction':predicted})
    return jsonify({'error':'invalid file type'}), 400

# NDVI and bloom summary
@app.route('/api/ndvi_monthly')
@login_required
def api_ndvi_monthly():
    try:
        records = load_ndvi_records()
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bloom_summary')
@login_required
def api_bloom_summary():
    try:
        records = load_ndvi_records()
        vals = [float(r.get('ndvi', 0)) for r in records if r.get('ndvi') is not None]
        if not vals:
            return jsonify({'status':'No data','recent_mean':None})
        recent = vals[-3:] if len(vals) >= 3 else vals
        mean = sum(recent)/len(recent)
        if mean >= 0.70:
            status = "High Bloom Activity"
        elif mean >= 0.60:
            status = "Moderate Bloom"
        else:
            status = "Low Bloom Phase"
        return jsonify({'status':status, 'recent_mean': round(mean,3)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Weather / Forecast / AQI APIs (unchanged)
def _cache_get(cache, key):
    item = cache.get(key)
    if not item: return None
    if time.time() - item['ts'] > CACHE_TTL: return None
    return item['data']

def _cache_set(cache, key, data):
    cache[key] = {'ts': time.time(), 'data': data}

@app.route('/api/weather')
@login_required
def api_weather():
    lat = request.args.get('lat', type=float) or 13.0827
    lon = request.args.get('lon', type=float) or 80.2707
    key = app.config.get('OPENWEATHER_API_KEY')
    cache_key = (round(lat,3), round(lon,3))
    cached = _cache_get(_weather_cache, cache_key)
    if cached:
        return jsonify({'source':'cache','data':cached})
    if not key:
        return jsonify({'error':'OpenWeather key not configured'}), 500
    url = 'https://api.openweathermap.org/data/2.5/weather'
    params = {'lat':lat,'lon':lon,'units':'metric','appid':key}
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        d = resp.json()
        data = {
            'name': d.get('name'),
            'main': d.get('weather',[{}])[0].get('main'),
            'description': d.get('weather',[{}])[0].get('description'),
            'temp': d.get('main',{}).get('temp'),
            'humidity': d.get('main',{}).get('humidity'),
            'wind_speed': d.get('wind',{}).get('speed'),
        }
        _cache_set(_weather_cache, cache_key, data)
        return jsonify({'source':'api','data':data})
    except requests.RequestException as e:
        if _weather_cache.get(cache_key):
            return jsonify({'source':'cache_stale','data':_weather_cache[cache_key]['data'],'warning':str(e)})
        return jsonify({'error':'Failed to fetch weather','details':str(e)}), 502

@app.route('/api/forecast')
@login_required
def api_forecast():
    lat = request.args.get('lat', type=float) or 13.0827
    lon = request.args.get('lon', type=float) or 80.2707
    key = app.config.get('OPENWEATHER_API_KEY')
    cache_key = (round(lat,3), round(lon,3))
    cached = _cache_get(_forecast_cache, cache_key)
    if cached:
        return jsonify({'source':'cache','data':cached})
    if not key:
        return jsonify({'error':'OpenWeather key not configured'}), 500
    url = 'https://api.openweathermap.org/data/2.5/forecast'
    params = {'lat':lat,'lon':lon,'units':'metric','appid':key}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        d = resp.json()
        forecasts = []
        flist = d.get('list',[])
        for i in range(0, len(flist), 8):
            entry = flist[i]
            forecasts.append({
                'date': entry.get('dt_txt','').split(' ')[0],
                'temp': entry.get('main',{}).get('temp'),
                'desc': entry.get('weather',[{}])[0].get('description'),
                'icon': entry.get('weather',[{}])[0].get('icon'),
            })
            if len(forecasts) >= 3: break
        _cache_set(_forecast_cache, cache_key, forecasts)
        return jsonify({'source':'api','data':forecasts})
    except requests.RequestException as e:
        if _forecast_cache.get(cache_key):
            return jsonify({'source':'cache_stale','data':_forecast_cache[cache_key]['data'],'warning':str(e)})
        return jsonify({'error':'Failed to fetch forecast','details':str(e)}), 502

@app.route('/api/air_quality')
@login_required
def api_air_quality():
    lat = request.args.get('lat', type=float) or 13.0827
    lon = request.args.get('lon', type=float) or 80.2707
    key = app.config.get('OPENWEATHER_API_KEY')
    cache_key = (round(lat,3), round(lon,3))
    cached = _cache_get(_aqi_cache, cache_key)
    if cached:
        return jsonify({'source':'cache','data':cached})
    if not key:
        return jsonify({'error':'OpenWeather key not configured'}), 500
    url = 'https://api.openweathermap.org/data/2.5/air_pollution'
    params = {'lat':lat,'lon':lon,'appid':key}
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        d = resp.json()
        aqi_val = d.get('list',[{}])[0].get('main',{}).get('aqi')
        levels = {1:'Good 🌿',2:'Fair 🌤️',3:'Moderate 🌼',4:'Poor 🌫️',5:'Very Poor 🌋'}
        result = {'aqi': aqi_val, 'status': levels.get(aqi_val,'Unknown')}
        _cache_set(_aqi_cache, cache_key, result)
        return jsonify({'source':'api','data':result})
    except requests.RequestException as e:
        if _aqi_cache.get(cache_key):
            return jsonify({'source':'cache_stale','data':_aqi_cache[cache_key]['data'],'warning':str(e)})
        return jsonify({'error':'Failed to fetch air quality','details':str(e)}), 502
# --- API to get all user reports for calendar ---
@app.route('/api/user_reports')
@login_required
def api_user_reports():
    """Return all reports of the logged-in user as JSON."""
    user = User.query.filter_by(username=session['username']).first()
    reports = Report.query.filter_by(user_id=user.id).all()
    report_list = []
    for r in reports:
        report_list.append({
            "flower_name": getattr(r, 'flower_name', None),  
            "location": r.location,
            "intensity": getattr(r, 'intensity', ''),      
            "date_time": r.date_time,
            "image": url_for('static', filename='uploads/' + r.image_filename)
        })
    return jsonify(report_list)

@app.route('/user_reports_page')
@login_required
def user_reports_page():
    user = User.query.filter_by(username=session['username']).first()
    reports = Report.query.filter_by(user_id=user.id).order_by(Report.date_time.desc()).all()
    return render_template('user_reports_page.html', reports=reports)

@app.route('/update_report/<int:idx>', methods=['GET', 'POST'])
@login_required
def update_report(idx):
    # Make sure this matches how you pass 'reports'
    reports = [...]  # Rebuild or load your exact list, same as in /report!
    if idx < 0 or idx >= len(reports):
        return "Report not found", 404
    if request.method == 'POST':
        reports[idx]['location'] = request.form['location']
        reports[idx]['date'] = request.form['date']
        reports[idx]['ndvi'] = float(request.form['ndvi'])
        reports[idx]['blooming'] = True if request.form.get('blooming')=='on' else False
        # TODO: save updated reports data!
        return redirect(url_for('report_detect'))
    return render_template('update_report.html', report=reports[idx], idx=idx)

if __name__ == '__main__':
    app.run(debug=True)