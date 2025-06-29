from flask import Flask, render_template, request, redirect, send_file, flash
import psycopg2
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from io import BytesIO
import os
DB_URL = os.environ.get("DB_URL")

import dropbox
import csv



app = Flask(__name__)
app.secret_key = 'valfri-hemlig-nyckel'

# PostgreSQL connection string
# DB_URL = "postgresql://postgres:Carcenter2025@db.jzozwtsrwntarctybqym.supabase.co:6543/postgres"

# Connect helper

def get_db():
    return psycopg2.connect(DB_URL)

@app.route('/')
def index():
    return render_template('index.html')

from flask import Flask, request, redirect, flash
from datetime import datetime
import os
import dropbox  # glöm inte importen

from flask import request, redirect, flash
from datetime import datetime
import dropbox
import os

@app.route('/add', methods=['POST'])
def add():
    name = request.form.get('name', '').strip().capitalize()
    phone = request.form.get('phone', '').strip()
    car_model = request.form.get('car_model', '').strip().capitalize()
    license_plate = request.form.get('license_plate', '').strip().upper()
    service = request.form.get('service', '').strip().capitalize()
    price = request.form.get('price', '').strip().upper()


    # Validera endast namn, regnr, och tjänst
    if not name or not license_plate or not service:
        flash("Namn, registreringsnummer och tjänst är obligatoriska.")
        

        return redirect('/')

    data = (
        name,
        phone if phone else None,
        car_model if car_model else None,
        license_plate,
        service,
        price if price else None,
        datetime.now().strftime('%Y-%m-%d %H:%M'),
        'Ej fakturerad'
    )

    # Spara till databas
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO jobs (customer_name, phone, car_model, license_plate, service, price, date, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, data)
    conn.commit()
    cur.close()
    conn.close()

    flash("Registreringen lyckades!")
    print("Försöker köra Dropbox-backup...")

    # === Dropbox-backup ===
    try:
        DROPBOX_TOKEN = os.environ.get('DROPBOX_TOKEN')  # sätts i Render > Environment
        if not DROPBOX_TOKEN:
            raise Exception("Dropbox-token saknas!")

        dbx = dropbox.Dropbox(DROPBOX_TOKEN)

        # Hämta alla aktiva jobb
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE archived = 0")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Skapa CSV-data
        csv_data = "id,namn,telefon,bil,regnr,tjänst,pris,datum,status\n"
        for row in rows:
            csv_data += ",".join([str(f) if f is not None else "" for f in row]) + "\n"

        # Ladda upp till Dropbox
        dbx.files_upload(
            csv_data.encode('utf-8'),
            '/backup_registrerade_job.csv',
            mode=dropbox.files.WriteMode.overwrite
        )

        print("✅ Backup till Dropbox klar.")
        flash("Backup till Dropbox lyckades.")

    except Exception as e:
        print("Fel vid Dropbox-backup:", str(e))  # Visas i Render-loggar

    return redirect('/jobs')



@app.route('/jobs')
def jobs():
    search = request.args.get('search', '')
    sort_field = request.args.get('sort_field', 'date')
    sort_order = request.args.get('sort', 'desc')

    allowed = {'date': 'date', 'name': 'customer_name'}
    order_by = allowed.get(sort_field, 'date')

    conn = get_db()
    cur = conn.cursor()
    if search:
        cur.execute(f"""
            SELECT * FROM jobs
            WHERE archived = 0 AND (license_plate ILIKE %s OR customer_name ILIKE %s)
            ORDER BY {order_by} {sort_order}
        """, (f"%{search}%", f"%{search}%"))
    else:
        cur.execute(f"SELECT * FROM jobs WHERE archived = 0 ORDER BY {order_by} {sort_order}")
    jobs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('jobs.html', jobs=jobs, search=search, sort=sort_order, sort_field=sort_field)

@app.route('/delete/<int:job_id>', methods=['POST'])
def delete(job_id):
    pin = request.form.get('pin')
    if pin != "1234":
        flash("Fel PIN-kod.")
        return redirect('/jobs')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET archived = 1 WHERE id = %s", (job_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Raden arkiverades")
    return redirect('/jobs')

@app.route('/archived')
def archived():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE archived = 1 ORDER BY date DESC")
    jobs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('archived.html', jobs=jobs)

@app.route('/toggle_status/<int:job_id>', methods=['POST'])
def toggle_status(job_id):
    pin = request.form.get('pin')
    if pin != "1234":
        flash("Fel PIN-kod.")
        return redirect('/jobs')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT status FROM jobs WHERE id = %s", (job_id,))
    status = cur.fetchone()[0]
    new_status = 'Ej fakturerad' if status == 'Fakturerad' else 'Fakturerad'
    cur.execute("UPDATE jobs SET status = %s WHERE id = %s", (new_status, job_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/jobs')

@app.route('/generate_pdf')
def generate_job_list_pdf():
    sort_field = request.args.get('sort_field', 'date')
    sort_order = request.args.get('sort', 'desc')
    order_by = {'date': 'date', 'name': 'customer_name'}.get(sort_field, 'date')

    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM jobs WHERE archived = 0 ORDER BY {order_by} {sort_order}")
    jobs = cur.fetchall()
    cur.close()
    conn.close()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    data = [["Datum", "Kund", "Reg.nr", "Tjänst", "Pris"]] + [
        [job[7], job[1], job[4], job[5], f"{job[6]}" if job[6] else ""] for job in jobs
    ]

    table = Table(data, colWidths=[100]*5)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    table.wrapOn(pdf, width, height)
    table.drawOn(pdf, 50, height - 100 - len(jobs) * 20)
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="jobb_lista.pdf", mimetype='application/pdf')

@app.route('/edit/<int:job_id>', methods=['POST'])
def edit(job_id):
    try:
        # Hämta fält från formuläret
        name = request.form['customer_name'].strip()
        phone = request.form['phone'].strip()
        car_model = request.form['car_model'].strip()
        license_plate = request.form['license_plate'].strip()
        service = request.form['service'].strip()
        price = request.form['price'].strip()

        # Kontrollera att obligatoriska fält inte är tomma
        if not name or not license_plate or not service:
            flash("Namn, registreringsnummer och tjänst får inte vara tomma.")
            return redirect('/jobs')

        # Förbered värden för databasen
        data = (
            name.capitalize(),
            phone if phone else None,
            car_model.capitalize() if car_model else None,
            license_plate.upper(),
            service.capitalize(),
            float(price) if price else None,
            job_id
        )

        # Uppdatera i databasen
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE jobs SET customer_name = %s, phone = %s, car_model = %s,
            license_plate = %s, service = %s, price = %s WHERE id = %s
        """, data)
        conn.commit()
        cur.close()
        conn.close()

        flash("Jobbet har uppdaterats!")
    except Exception as e:
        print("Fel vid uppdatering:", str(e))
        flash("Ett fel inträffade vid uppdatering.")
    return redirect('/jobs')


@app.route('/delete_selected', methods=['POST'])
def delete_selected():
    try:
        ids = request.form.getlist('delete_ids')

        if not ids:
            flash("Inga jobb markerades för radering.")
            return redirect('/archived')

        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM jobs WHERE id IN %s", (tuple(ids),))  # använd tuple här!
        conn.commit()
        cur.close()
        conn.close()

        flash(f"{len(ids)} jobb raderades permanent.")
        return redirect('/archived')
    
    except Exception as e:
        print("Fel vid radering:", str(e))  # Visas i Render-loggen
        flash("Ett fel inträffade vid radering.")
        return redirect('/archived')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    