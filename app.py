from flask import Flask, render_template, request, redirect, send_file, make_response
import sqlite3
from datetime import datetime
from reportlab.lib.utils import ImageReader
import os
from flask import flash, session
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from flask import send_file
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

ADMIN_PIN = "1234"


app = Flask(__name__)
app.secret_key = 'valfri-hemlig-nyckel'  # måste finnas för att flash ska funka

# Skapa databasen om den inte finns
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Skapa tabellen om den inte finns
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT,
        phone TEXT,
        car_model TEXT,
        license_plate TEXT,
        service TEXT,
        price REAL,
        date TEXT,
        status TEXT
    )''')

    # Försök lägga till kolumnen "archived" om den inte redan finns
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN archived INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Kolumnen finns redan

    conn.commit()
    conn.close()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add', methods=['POST'])
def add():
    name = request.form['name']
    phone = request.form['phone']
    car_model = request.form['car_model']
    license_plate = request.form['license_plate']
    service = request.form['service']
    price = request.form['price']
    date = datetime.now().strftime('%Y-%m-%d %H:%M')
    status = 'Ej fakturerad'

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO jobs (customer_name, phone, car_model, license_plate, service, price, date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (name, phone, car_model, license_plate, service, price, date, status))
    conn.commit()
    conn.close()

    flash("Registreringen lyckades!")  # ← LÄGG TILL DENNA RAD HÄR
    return redirect('/jobs')


@app.route('/jobs')
def jobs():
    search = request.args.get('search', '')
    sort_field = request.args.get('sort_field', 'date')
    sort_order = request.args.get('sort', 'desc')

    allowed_fields = {
        'date': 'date',
        'name': 'customer_name'
    }
    order_by = allowed_fields.get(sort_field, 'date')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if search:
        c.execute(f"""
            SELECT * FROM jobs
            WHERE archived = 0 AND (license_plate LIKE ? OR customer_name LIKE ?)
            ORDER BY {order_by} {sort_order}
        """, ('%' + search + '%', '%' + search + '%'))
    else:
        c.execute(f"SELECT * FROM jobs WHERE archived = 0 ORDER BY {order_by} {sort_order}")

    jobs = c.fetchall()
    conn.close()
    return render_template('jobs.html', jobs=jobs, search=search, sort=sort_order, sort_field=sort_field)



@app.route('/confirm_status/<int:job_id>', methods=['GET', 'POST'])
def confirm_status(job_id):
    if request.method == 'POST':
        entered_pin = request.form.get('pin')
        if entered_pin == ADMIN_PIN:
            # Växla status
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
            result = c.fetchone()
            if result:
                current_status = result[0]
                new_status = "Ej fakturerad" if current_status == "Fakturerad" else "Fakturerad"
                c.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
                conn.commit()
            conn.close()
            return redirect('/jobs')
        else:
            return render_template('pin.html', job_id=job_id, error="Fel kod!")

    return render_template('pin.html', job_id=job_id)

@app.route('/delete/<int:job_id>', methods=['POST'])
def delete(job_id):
    entered_pin = request.form.get('pin')
    if entered_pin != ADMIN_PIN:
        flash("Fel kod – raden flyttades inte.")
        return redirect('/jobs')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE jobs SET archived = 1 WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()

    flash("Raden har arkiverats.")
    return redirect('/jobs')

@app.route('/archived')
def archived():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE archived = 1 ORDER BY date DESC")
    jobs = c.fetchall()
    conn.close()
    return render_template('archived.html', jobs=jobs)

@app.route('/toggle_status/<int:job_id>', methods=['POST'])
def toggle_status(job_id):
    pin = request.form.get('pin')
    if pin != "1234":  # byt till din kod
        flash("Fel PIN-kod.")
        return redirect('/jobs')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
    result = c.fetchone()
    if result:
        current_status = result[0]
        new_status = 'Ej fakturerad' if current_status == 'Fakturerad' else 'Fakturerad'
        c.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
    conn.commit()
    conn.close()
    return redirect('/jobs')

@app.route('/generate_pdf')
def generate_job_list_pdf():
    sort_field = request.args.get('sort_field', 'date')
    sort_order = request.args.get('sort', 'desc')

    allowed_fields = {
        'date': 'date',
        'name': 'customer_name'
    }
    order_by = allowed_fields.get(sort_field, 'date')

    # Hämta data
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute(f"SELECT * FROM jobs WHERE archived = 0 ORDER BY {order_by} {sort_order}")
    jobs = c.fetchall()
    conn.close()

    # Skapa PDF
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Tabellrubrik + data
    data = [["Datum", "Kund", "Reg.nr", "Tjänst", "Pris"]]
    for job in jobs:
        datum = job[7]
        kund = job[1]
        reg = job[4]
        tjänst = job[5]
        pris = f"{job[6]} kr" if job[6] else ""
        data.append([datum, kund, reg, tjänst, pris])

    # Rita tabell
    table = Table(data, colWidths=[100, 100, 100, 120, 80])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ])
    table.setStyle(style)
    table.wrapOn(pdf, width, height)
    table.drawOn(pdf, 50, height - 100 - len(jobs) * 20)

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="jobb_lista.pdf", mimetype='application/pdf')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
