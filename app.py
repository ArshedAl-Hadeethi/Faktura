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

@app.route('/add', methods=['POST'])
def add():
    import dropbox  # säkerställ att importen finns i början av din fil eller här

    name = request.form.get('name', '').strip().capitalize()
    phone = request.form.get('phone', '').strip()
    car_model = request.form.get('car_model', '').strip().capitalize()
    license_plate = request.form.get('license_plate', '').strip().upper()
    service = request.form.get('service', '').strip().capitalize()
    price = request.form.get('price', '').strip()

    # Validera endast namn, regnr och tjänst
    if not name or not license_plate or not service:
        flash("Namn, registreringsnummer och tjänst är obligatoriska.")
        return redirect('/')

    data = (
        name,
        phone if phone else None,
        car_model if car_model else None,
        license_plate,
        service,
        float(price) if price else None,
        datetime.now().strftime('%Y-%m-%d %H:%M'),
        'Ej fakturerad'
    )

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

    # === Dropbox-backup ===
    DROPBOX_TOKEN = "sl.u.AF2QvZTgGtW65AMGsjOIeMUczNvVoL4JTQGrEFqDAKuJmRv_hp2sKzMVsOCSfACmz_Ib0pwTOj2x7j-7wgBtkpxf_2RN-Gs7Pa5QaUL7MW8Bnd19WnKbPqeH1O3tgCIObQKHfEAKrdwE2hX7lnINO35fMhUGIfiP3wHG3EFBcHkt7XfK7CUF8b29-TTzd2_G2ZRInX5HS8kht8a5nUa1uohq2FR6kvFRAvfjeqDm-GxpsIw3DTiJjD90pk1fz2cONKaU7YG2TobDz4EPM19Gkgd932ZYZxpVgIJk4izXxWQvrHesH9RDzRPHTS18EqoG3Hn8yIc_fC6YcccSQ3fPIQHRIgH3aqDiOICFOjEFwn8M2H9njFk6HFRhg6yN7cAhYALA-iDbuKBrc-Ios7kFL7sfAEECEz5ifs_FPSDw0z2_2NWv5YmZzsCpYJ9tZlzq8J2_ncQH6kTrIvm0J4joJby0nhjMYieKclo5Qwr3t5UMgMKKRHfMPlTDjfVL_LQkuYx6Qq-UH5LffsMNN4qsy1OJ6v0YDim3M-ZqcPO0sZDGqoqdwPA7LIHhLX5OCyCxQUCJBUcJ0dCeKxeIz2R6sTEZsmiqP1zZfwjc5vBVw-CeFTzLVzAcLt7uiIkAYlT3Kzz1agC21DcdBn1tnJEPvPBPqgabuEo7H-VhMe14yaxmmGUBy2A-FIh6NK_avfuvxByE8Uq4MkVDtrdeN8Nt8bSIUk3Zd-NGYXqh5xt6WPQnAKY6PBrS7Zd7Qjj6SXRDQgN_MQxC3ESxkx-m_9dPLvs3UlKIdBCZwVXWgw_1q0lNFkwnax-dR4wIiJqrP0HU-L7FnpnjwRJ4_iUcjma3m5h1CLt0XzTvajrV1Op6_lo4U64W26H7wB9cg97OCMIQ80UYh03RmrwvtrPv-E9a0cWx2vxlo-nFnndGGYvt4OLrNtmnU_Ks3Vxzv8NeiaIryQYShBporfcVllwGuQgHDTeYbjcMK55ERt52x5qZMH7QEWVa1dSo-tNBEWt59aT6sCULhTfZ8ldPsKj5Kts7KTjZaWIkcyb5ohUz0X9sTfP5_8HUrnxLhUfdTD-NGzCmGgwrvF_Na1_C3TNm4M2miTAmu0DZ5KoWgcU1dpyWJnsv-NO8pHqo7dQPPd4nHeQMJSrQvKyCMl2u3tIZ7BNpie4k4ZvOwc6eak8ZR2UitrDmth_XBHT3zqcsZqrIpT4L0c2BH4wyaPXIMfMUNZbmVZcKNhWlL9gFO9HIBMVtv43j9QXC7RoJIMKS3O1WUm0XtK8"  # byt ut mot din token
    dbx = dropbox.Dropbox(DROPBOX_TOKEN)

    # Hämta alla icke-arkiverade jobb
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE archived = 0")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Skapa CSV-data
    csv_data = "id,namn,telefon,bil,regnr,tjänst,pris,datum,status\n"
    for row in rows:
        row = [str(field) if field is not None else "" for field in row]
        csv_data += ",".join(row) + "\n"

    # Ladda upp till Dropbox
    dbx.files_upload(csv_data.encode('utf-8'), '/backup_registrerade_job.csv', mode=dropbox.files.WriteMode.overwrite)

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
        flash("Fel kod")
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
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE jobs SET customer_name = %s, phone = %s, car_model = %s,
        license_plate = %s, service = %s, price = %s WHERE id = %s
    """, (
        request.form['customer_name'],
        request.form['phone'],
        request.form['car_model'],
        request.form['license_plate'],
        request.form['service'],
        request.form['price'],
        job_id
    ))
    conn.commit()
    cur.close()
    conn.close()
    flash("Jobbet har uppdaterats!")
    return redirect('/jobs')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    