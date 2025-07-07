import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from datetime import datetime
import requests
from fpdf import FPDF
import time
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'project'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RATE_LIMIT'] = 45

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.mkdir(app.config['UPLOAD_FOLDER'])


def allowed_file(filename):
    if filename.endswith(".txt"):
        return True

def validate_ip(ip):
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    
    else:
        for part in parts:
            ip_address = int(part)
            if ip_address < 0 or ip_address > 255: 
                return False
        return True

def get_ip_info(ip_address):
    try:
        url = f"http://ip-api.com/json/{ip_address}"
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        
        if data.get('status') == 'fail':
            return None
        
        return {
            'ip': ip_address,
            'hostname': data.get('reverse', 'N/A'),
            'city': data.get('city', 'N/A'),
            'region': data.get('regionName', 'N/A'),
            'country': data.get('country', 'N/A'),
            'location': f"{data.get('lat', 'N/A')},{data.get('lon', 'N/A')}",
            'org': data.get('isp', 'N/A'),
            'postal': data.get('zip', 'N/A'),
            'timezone': data.get('timezone', 'N/A'),
            'asn': data.get('as', 'N/A')
        }
    except requests.RequestException as e:
        print(f"Error fetching data for IP {ip_address}: {e}")
        return None

def generate_pdf_report(ip_data_list, filename):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Advance IP Scanner Report", 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1)
    pdf.ln(5)

    pdf.set_font("Arial", '', 12)
    for idx, ip_data in enumerate(ip_data_list, 1):
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(0, 10, f"IP {idx}: {ip_data.get('ip', 'N/A')}", 0, 1, 'L', 1)
        pdf.ln(3)
        
        for key, value in ip_data.items():
            if key not in ['report_generation_time']:
                pdf.cell(40, 8, f"{key.capitalize().replace('_', ' ')}:", 0, 0)
                pdf.cell(0, 8, str(value), 0, 1)
        
        pdf.ln(5)
    
    pdf.output(filename)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        ip_input = request.form.get('ip_input')
        file = request.files.get('ip_file')
        ip_list = []
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        ip_list.extend([ip.strip() for ip in line.split(',') if ip.strip()])
            
            os.remove(filepath)
        
        if ip_input:
            ip_list.extend([ip.strip() for ip in ip_input.split(',') if ip.strip()])
        
        if not ip_list:
            flash('No IP addresses provided', 'error')
            return redirect(url_for('index'))
        
        valid_ips = [ip for ip in ip_list if validate_ip(ip)]
        invalid_ips = set(ip_list) - set(valid_ips)
        
        if invalid_ips:
            flash(f'Invalid IP addresses ignored: {", ".join(invalid_ips)}', 'warning')
        
        if not valid_ips:
            flash('No valid IP addresses provided', 'error')
            return redirect(url_for('index'))
        
        results = []
        start_time = time.time()
        
        for i, ip in enumerate(valid_ips):
            if i > 0 and i % app.config['RATE_LIMIT'] == 0:
                time.sleep(60)
            
            ip_data = get_ip_info(ip)
            if ip_data:
                results.append(ip_data)
        
        processing_time = time.time() - start_time
        
        if not results:
            flash('No valid IP information could be retrieved', 'error')
            return redirect(url_for('index'))
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"ip_report_{timestamp}.pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
        
        generate_pdf_report(results, pdf_path)
        
        return render_template('report.html', 
                             results=results, 
                             processing_time=round(processing_time, 2),
                             pdf_filename=pdf_filename)
    
    return render_template('index.html')

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)