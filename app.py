from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, jsonify
import os
import pandas as pd
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from mashov_api import MashovClient, DEFAULT_SUBJECT, DEFAULT_TEMPLATE, normalize_id
import json
import datetime

def get_academic_years():
    current_date = datetime.date.today()
    current_year = current_date.year
    current_month = current_date.month

    years = []
    # If current month is July or later, the current academic year is current_year + 1
    # Otherwise, it's current_year
    if current_month >= 7:
        academic_year_end = current_year + 1
    else:
        academic_year_end = current_year

    # Generate last 3 academic years
    for i in range(3):
        years.append(str(academic_year_end - i))
    return years

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'

@app.route('/', methods=['GET', 'POST'])
def index():
    step = session.get('step', 1)

    if request.method == 'POST':
        if step == 1:
            return handle_login()
        elif step == 2:
            if 'csv_file' in request.files:
                return handle_csv_upload()
            else:
                return handle_column_mapping()
        elif step == 3:
            return handle_send_messages()

    return render_step(step)

def render_step(step):
    if step == 1:
        years = get_academic_years()
        current_academic_year = years[0] # The most recent academic year
        return render_template('index_rtl.html', step=1, years=years, current_academic_year=current_academic_year)
    elif step == 2:
        return render_template('index_rtl.html', step=2, columns=session.get('columns'), file_path=session.get('file_path'))
    elif step == 3:
        file_path = session.get('file_path')
        df = pd.read_csv(file_path) if file_path else pd.DataFrame()
        return render_template('index_rtl.html', step=3, subject=session.get('subject', DEFAULT_SUBJECT), body=session.get('body', DEFAULT_TEMPLATE), df=df)
    return redirect(url_for('index'))

def handle_login():
    user = request.form['username']
    pwd = request.form['password']
    year = request.form['year']
    semel = os.getenv('MASHOV_SEMEL','')

    client = MashovClient(user, pwd, year, semel)
    try:
        login_data = client.login()
        session['mashov_credentials'] = {
            'user': user,
            'pwd': pwd,
            'year': year,
            'semel': semel
        }
        session['step'] = 2
        flash(f"מחובר כ{login_data.get('accessToken',{}).get('displayName')}", 'success')
    except Exception as e:
        flash(f'Login failed: {e}', 'danger')
        return redirect(url_for('index'))
    return redirect(url_for('index'))

def handle_csv_upload():
    file = request.files['csv_file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename and file.filename.endswith('.csv'):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        df = pd.read_csv(file_path)
        session['columns'] = list(df.columns)
        session['file_path'] = file_path
        session['step'] = 2 # Stay on step 2 to map columns

        return jsonify({'columns': list(df.columns), 'rows': len(df)})
    else:
        return jsonify({'error': 'Invalid file type. Please upload a CSV file.'}), 400

def handle_column_mapping():
    if 'id_col' in request.form:
        session['id_col'] = request.form['id_col']
        session['step'] = 3
        flash('כל העמודות מופו בהצלחה.', 'success')
    return redirect(url_for('index'))

def handle_send_messages():
    subject = request.form['subject']
    body = request.form['body']
    dry_run = 'dry_run' in request.form
    send_email = 'send_email' in request.form

    session['subject'] = subject
    session['body'] = body

    creds = session['mashov_credentials']
    file_path = session['file_path']
    id_col = session['id_col']

    return Response(generate_logs(creds, file_path, id_col, subject, body, dry_run, send_email), mimetype='text/event-stream')

def generate_logs(creds, file_path, id_col, subject, body, dry_run, send_email):
    client = MashovClient(creds['user'], creds['pwd'], creds['year'], creds['semel'])
    try:
        client.login()
    except Exception as e:
        yield f"data: [ERROR] Login failed: {e}\n\n"
        return

    df = pd.read_csv(file_path)
    success_count = 0
    failure_count = 0
    failed_rows = []

    for index, row in df.iterrows():
        yield f"data: {json.dumps({'type': 'highlight', 'row_index': index, 'status': 'processing'})}\n\n"
        student_id = normalize_id(row[id_col])
        
        try:
            student_details = client.locate_by_id(student_id)
            if not student_details:
                yield f"data: [SKIP] No match for {row[id_col]}\n\n"
                yield f"data: {json.dumps({'type': 'highlight', 'row_index': index, 'status': 'failed'})}\n\n"
                failure_count += 1
                failed_rows.append(row.to_dict())
                continue

            recipient_id = student_details.get('studentGuid')
            if not recipient_id:
                yield f"data: [SKIP] Could not extract studentGuid for {row[id_col]}\n\n"
                yield f"data: {json.dumps({'type': 'highlight', 'row_index': index, 'status': 'failed'})}\n\n"
                failure_count += 1
                failed_rows.append(row.to_dict())
                continue

            # Compose message
            message_body = body.format(**row.to_dict())
            message_subject = subject.format(**row.to_dict())

            if not dry_run:
                client.send_message(message_subject, message_body, [recipient_id], sendViaEmail=send_email)
                yield f"data: [OK] Sent to {row[id_col]}\n\n"
                yield f"data: {json.dumps({'type': 'highlight', 'row_index': index, 'status': 'success'})}\n\n"
                success_count += 1
            else:
                yield f"data: [DRY RUN] Would send to {row[id_col]}\n\n"
                yield f"data: {json.dumps({'type': 'highlight', 'row_index': index, 'status': 'success'})}\n\n"
                success_count += 1

        except Exception as e:
            yield f"data: [FAIL] {row[id_col]}: {e}\n\n"
            yield f"data: {json.dumps({'type': 'highlight', 'row_index': index, 'status': 'failed'})}\n\n"
            failure_count += 1
            failed_rows.append(row.to_dict())
    
    if failed_rows:
        failed_df = pd.DataFrame(failed_rows)
        errors_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'errors.csv')
        failed_df.to_csv(errors_file_path, index=False)
        yield f"data: [INFO] Failed rows written to {errors_file_path}\n\n"

    yield "data: --- SUMMARY ---\n\n"
    yield f"data: Success: {success_count}\n\n"
    yield f"data: Failed: {failure_count}\n\n"



@app.route('/reset')
def reset():
    session.clear()
    flash('Session reset.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
