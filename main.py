from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from datetime import datetime
from data_manager import DataManager
import os
import logging
from werkzeug.utils import secure_filename
import mimetypes
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "vehicle-tracker-secret-key")

# File upload configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    """Check if uploaded file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_content(file_data, filename):
    """Validate file content matches its extension"""
    try:
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            if filename.lower().endswith(('.jpg', '.jpeg')) and not mime_type.startswith('image/'):
                return False
            elif filename.lower().endswith('.png') and mime_type != 'image/png':
                return False
            elif filename.lower().endswith('.pdf') and mime_type != 'application/pdf':
                return False
        return True
    except:
        return False

# Initialize data manager
data_manager = DataManager()

@app.route('/')
def index():
    """Dashboard/home page with summary statistics"""
    stats = data_manager.get_dashboard_stats()
    return render_template('index.html', stats=stats)

@app.route('/inventory')
def inventory():
    """Vehicle inventory page"""
    vehicles = data_manager.get_vehicles()
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')

    # Apply filters
    if search:
        vehicles = [v for v in vehicles if search.lower() in f"{v['make']} {v['model']} {v['year']} {v['vin']}".lower()]

    if status_filter:
        vehicles = [v for v in vehicles if v['status'] == status_filter]

    return render_template('inventory.html', vehicles=vehicles, search=search, status_filter=status_filter)

@app.route('/inventory/add', methods=['POST'])
def add_vehicle():
    """Add a new vehicle to inventory"""
    try:
        vehicle_data = {
            'make': request.form.get('make', '').strip(),
            'model': request.form.get('model', '').strip(),
            'year': request.form.get('year', '').strip(),
            'vin': request.form.get('vin', '').strip(),
            'price': request.form.get('price', '').strip(),
            'date': request.form.get('date', '').strip(),
            'notes': request.form.get('notes', '').strip(),
            'status': 'In Stock'
        }

        # Validate required fields
        required_fields = ['make', 'model', 'year', 'vin', 'price']
        if not all(vehicle_data[field] for field in required_fields):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('inventory'))

        # Validate price is numeric
        try:
            float(vehicle_data['price'])
        except ValueError:
            flash('Please enter a valid price', 'error')
            return redirect(url_for('inventory'))

        # Validate year is numeric and reasonable
        try:
            year = int(vehicle_data['year'])
            if year < 1900 or year > datetime.now().year + 1:
                flash('Please enter a valid year', 'error')
                return redirect(url_for('inventory'))
        except ValueError:
            flash('Please enter a valid year', 'error')
            return redirect(url_for('inventory'))

        # Check if VIN already exists
        if data_manager.vin_exists(vehicle_data['vin']):
            flash('A vehicle with this VIN already exists', 'error')
            return redirect(url_for('inventory'))

        # Add vehicle
        vehicle_id = data_manager.add_vehicle(vehicle_data)

        # Handle bill of sale upload if provided
        if 'bill_of_sale' in request.files:
            file = request.files['bill_of_sale']
            if file and file.filename and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    file_data = file.read()

                    # Validate file size (additional check)
                    if len(file_data) > 16 * 1024 * 1024:  # 16MB
                        flash('File too large. Maximum size is 16MB.', 'warning')
                    elif validate_file_content(file_data, filename):
                        if data_manager.upload_bill_of_sale(vehicle_id, file_data, filename):
                            flash(f'Vehicle added successfully with ID {vehicle_id} and bill of sale uploaded', 'success')
                        else:
                            flash(f'Vehicle added with ID {vehicle_id}, but bill of sale upload failed', 'warning')
                    else:
                        flash(f'Vehicle added with ID {vehicle_id}, but bill of sale file type validation failed', 'warning')
                except Exception as e:
                    logging.error(f"Error uploading bill of sale: {e}")
                    flash(f'Vehicle added with ID {vehicle_id}, but bill of sale upload failed', 'warning')
            elif file and file.filename:
                flash(f'Vehicle added with ID {vehicle_id}, but bill of sale file type not allowed', 'warning')

        if 'bill_of_sale' not in request.files or not request.files['bill_of_sale'].filename:
            flash(f'Vehicle added successfully with ID {vehicle_id}', 'success')

    except Exception as e:
        logging.error(f"Error adding vehicle: {e}")
        flash('An error occurred while adding the vehicle', 'error')

    return redirect(url_for('inventory'))

@app.route('/inventory/edit/<int:vehicle_id>', methods=['GET', 'POST'])
def edit_vehicle(vehicle_id):
    """Edit a vehicle in inventory"""
    vehicle = data_manager.get_vehicle_by_id(vehicle_id)
    if not vehicle:
        flash('Vehicle not found', 'error')
        return redirect(url_for('inventory'))

    if request.method == 'POST':
        try:
            updated_data = {
                'id': vehicle_id,
                'make': request.form.get('make', '').strip(),
                'model': request.form.get('model', '').strip(),
                'year': request.form.get('year', '').strip(),
                'vin': request.form.get('vin', '').strip(),
                'price': request.form.get('price', '').strip(),
                'date': request.form.get('date', '').strip(),
                'notes': request.form.get('notes', '').strip(),
                'status': request.form.get('status', vehicle['status'])
            }

            # Validate required fields
            required_fields = ['make', 'model', 'year', 'vin', 'price']
            if not all(updated_data[field] for field in required_fields):
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('edit_vehicle', vehicle_id=vehicle_id))

            # Validate price is numeric
            try:
                float(updated_data['price'])
            except ValueError:
                flash('Please enter a valid price', 'error')
                return redirect(url_for('edit_vehicle', vehicle_id=vehicle_id))

            # Validate year is numeric and reasonable
            try:
                year = int(updated_data['year'])
                if year < 1900 or year > datetime.now().year + 1:
                    flash('Please enter a valid year', 'error')
                    return redirect(url_for('edit_vehicle', vehicle_id=vehicle_id))
            except ValueError:
                flash('Please enter a valid year', 'error')
                return redirect(url_for('edit_vehicle', vehicle_id=vehicle_id))

            # Check if VIN already exists (excluding current vehicle)
            if updated_data['vin'] != vehicle['vin'] and data_manager.vin_exists(updated_data['vin']):
                flash('A vehicle with this VIN already exists', 'error')
                return redirect(url_for('edit_vehicle', vehicle_id=vehicle_id))

            # Update vehicle
            if data_manager.update_vehicle(vehicle_id, updated_data):

                # Handle bill of sale upload if provided
                if 'bill_of_sale' in request.files:
                    file = request.files['bill_of_sale']
                    if file and file.filename and allowed_file(file.filename):
                        try:
                            filename = secure_filename(file.filename)
                            file_data = file.read()

                            # Validate file size
                            if len(file_data) > 16 * 1024 * 1024:  # 16MB
                                flash('Vehicle updated, but bill of sale file too large (max 16MB)', 'warning')
                            elif validate_file_content(file_data, filename):
                                # Delete old bill of sale if exists
                                data_manager.delete_bill_of_sale(vehicle_id)

                                if data_manager.upload_bill_of_sale(vehicle_id, file_data, filename):
                                    flash('Vehicle and bill of sale updated successfully', 'success')
                                else:
                                    flash('Vehicle updated, but bill of sale upload failed', 'warning')
                            else:
                                flash('Vehicle updated, but bill of sale file type validation failed', 'warning')
                        except Exception as e:
                            logging.error(f"Error uploading bill of sale: {e}")
                            flash('Vehicle updated, but bill of sale upload failed', 'warning')
                    elif file and file.filename:
                        flash('Vehicle updated, but bill of sale file type not allowed', 'warning')
                    else:
                        flash('Vehicle updated successfully', 'success')
                else:
                    flash('Vehicle updated successfully', 'success')

                return redirect(url_for('inventory'))
            else:
                flash('Failed to update vehicle', 'error')

        except Exception as e:
            logging.error(f"Error updating vehicle: {e}")
            flash('An error occurred while updating the vehicle', 'error')

    return render_template('edit_vehicle.html', vehicle=vehicle)

@app.route('/inventory/delete/<int:vehicle_id>')
def delete_vehicle(vehicle_id):
    """Delete a vehicle from inventory with cascade deletion"""
    try:
        # First, delete all associated expenses and sales
        expenses = data_manager.get_expenses()
        sales = data_manager.get_sales()

        vehicle_expenses = [e for e in expenses if e['vehicle_id'] == vehicle_id]
        vehicle_sales = [s for s in sales if s['vehicle_id'] == vehicle_id]

        deleted_items = []

        # Delete associated expenses
        for expense in vehicle_expenses:
            if data_manager.delete_expense(expense['id']):
                deleted_items.append(f"expense #{expense['id']}")

        # Delete associated sales
        for sale in vehicle_sales:
            if data_manager.delete_sale(sale['id']):
                deleted_items.append(f"sale #{sale['id']}")

        # Now delete the vehicle
        if data_manager.delete_vehicle(vehicle_id):
            message = 'Vehicle deleted successfully'
            if deleted_items:
                message += f' (also deleted: {", ".join(deleted_items)})'
            flash(message, 'success')
        else:
            flash('Vehicle not found', 'error')
    except Exception as e:
        logging.error(f"Error deleting vehicle: {e}")
        flash('An error occurred while deleting the vehicle', 'error')

    return redirect(url_for('inventory'))

@app.route('/expenses')
def expenses():
    """Vehicle expenses page"""
    expenses = data_manager.get_expenses()
    vehicles = data_manager.get_vehicles()

    # Filter options
    vehicle_filter = request.args.get('vehicle', '')
    type_filter = request.args.get('type', '')

    # Apply filters
    if vehicle_filter:
        expenses = [e for e in expenses if str(e['vehicle_id']) == vehicle_filter]

    if type_filter:
        expenses = [e for e in expenses if type_filter.lower() in e['type'].lower()]

    return render_template('expenses.html', expenses=expenses, vehicles=vehicles, 
                         vehicle_filter=vehicle_filter, type_filter=type_filter)

@app.route('/expenses/add', methods=['POST'])
def add_expense():
    """Add a new expense"""
    try:
        expense_data = {
            'vehicle_id': request.form.get('vehicle_id', '').strip(),
            'type': request.form.get('type', '').strip(),
            'amount': request.form.get('amount', '').strip(),
            'date': request.form.get('date', '').strip(),
            'description': request.form.get('description', '').strip()
        }

        # Validate required fields
        if not all([expense_data['vehicle_id'], expense_data['type'], expense_data['amount']]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('expenses'))

        # Validate amount is numeric
        try:
            float(expense_data['amount'])
        except ValueError:
            flash('Please enter a valid amount', 'error')
            return redirect(url_for('expenses'))

        # Validate vehicle exists
        if not data_manager.vehicle_exists(int(expense_data['vehicle_id'])):
            flash('Selected vehicle does not exist', 'error')
            return redirect(url_for('expenses'))

        expense_id = data_manager.add_expense(expense_data)
        flash(f'Expense added successfully with ID {expense_id}', 'success')

    except Exception as e:
        logging.error(f"Error adding expense: {e}")
        flash('An error occurred while adding the expense', 'error')

    return redirect(url_for('expenses'))

@app.route('/expenses/delete/<int:expense_id>')
def delete_expense(expense_id):
    """Delete an expense"""
    try:
        if data_manager.delete_expense(expense_id):
            flash('Expense deleted successfully', 'success')
        else:
            flash('Expense not found', 'error')
    except Exception as e:
        logging.error(f"Error deleting expense: {e}")
        flash('An error occurred while deleting the expense', 'error')

    return redirect(url_for('expenses'))

@app.route('/sales')
def sales():
    """Vehicle sales page"""
    sales = data_manager.get_sales()
    available_vehicles = data_manager.get_available_vehicles()  # Only in-stock vehicles for the form
    all_vehicles = data_manager.get_vehicles()  # All vehicles for displaying sale history

    return render_template('sales.html', sales=sales, vehicles=available_vehicles, all_vehicles=all_vehicles)

@app.route('/sales/add', methods=['POST'])
def add_sale():
    """Record a new sale"""
    try:
        sale_data = {
            'vehicle_id': request.form.get('vehicle_id', '').strip(),
            'sale_price': request.form.get('sale_price', '').strip(),
            'sale_date': request.form.get('sale_date', '').strip(),
            'buyer_info': request.form.get('buyer_info', '').strip(),
            'sale_notes': request.form.get('sale_notes', '').strip()
        }

        # Validate required fields
        if not all([sale_data['vehicle_id'], sale_data['sale_price'], sale_data['sale_date']]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('sales'))

        # Validate sale price is numeric
        try:
            float(sale_data['sale_price'])
        except ValueError:
            flash('Please enter a valid sale price', 'error')
            return redirect(url_for('sales'))

        # Validate vehicle exists and is available
        vehicle_id = int(sale_data['vehicle_id'])
        vehicle = data_manager.get_vehicle_by_id(vehicle_id)
        if not vehicle:
            flash('Selected vehicle does not exist', 'error')
            return redirect(url_for('sales'))

        if vehicle['status'] != 'In Stock':
            flash('Selected vehicle is not available for sale', 'error')
            return redirect(url_for('sales'))

        sale_id = data_manager.add_sale(sale_data)
        flash(f'Sale recorded successfully with ID {sale_id}', 'success')

    except Exception as e:
        logging.error(f"Error recording sale: {e}")
        flash('An error occurred while recording the sale', 'error')

    return redirect(url_for('sales'))

@app.route('/sales/delete/<int:sale_id>')
def delete_sale(sale_id):
    """Delete a sale and restore vehicle to inventory"""
    try:
        if data_manager.delete_sale(sale_id):
            flash('Sale deleted successfully and vehicle restored to inventory', 'success')
        else:
            flash('Sale not found', 'error')
    except Exception as e:
        logging.error(f"Error deleting sale: {e}")
        flash('An error occurred while deleting the sale', 'error')

    return redirect(url_for('sales'))

@app.route('/reports')
def reports():
    """Reports and analytics page"""
    reports_data = data_manager.generate_reports()
    return render_template('reports.html', reports=reports_data)

@app.route('/downloads')
def downloads():
    """Downloads page for vehicle reports"""
    try:
        sold_vehicles_data = []
        sales = data_manager.get_sales()
        vehicles = data_manager.get_vehicles()
        expenses = data_manager.get_expenses()

        for sale in sales:
            vehicle = data_manager.get_vehicle_by_id(sale['vehicle_id'])
            if vehicle:
                # Get expenses for this vehicle
                vehicle_expenses = [e for e in expenses if e['vehicle_id'] == sale['vehicle_id']]
                total_expenses = sum(float(e['amount']) for e in vehicle_expenses)

                # Calculate profit
                purchase_price = float(vehicle['price'])
                sale_price = float(sale['sale_price'])
                net_profit = sale_price - purchase_price - total_expenses

                sold_vehicles_data.append({
                    'sale_id': sale['id'],
                    'vehicle': vehicle,
                    'purchase_price': purchase_price,
                    'sale_price': sale_price,
                    'sale_date': sale['sale_date'],
                    'buyer_info': sale['buyer_info'],
                    'total_expenses': total_expenses,
                    'net_profit': net_profit,
                    'expense_count': len(vehicle_expenses)
                })

        # Sort by sale date (newest first)
        sold_vehicles_data.sort(key=lambda x: x['sale_date'], reverse=True)

        return render_template('downloads.html', sold_vehicles=sold_vehicles_data)

    except Exception as e:
        logging.error(f"Error loading downloads page: {e}")
        flash('An error occurred while loading the downloads page', 'error')
        return redirect(url_for('index'))

@app.route('/download/vehicle/<int:sale_id>')
def download_vehicle_report(sale_id):
    """Download detailed PDF report for a specific vehicle sale"""
    return generate_bill_of_sale(sale_id)  # Reuse existing function

@app.route('/download/vehicle_csv/<int:sale_id>')
def download_vehicle_csv(sale_id):
    """Download CSV data for a specific vehicle sale"""
    try:
        import csv

        # Get sale details
        sales = data_manager.get_sales()
        sale = next((s for s in sales if s['id'] == sale_id), None)

        if not sale:
            flash('Sale not found', 'error')
            return redirect(url_for('downloads'))

        # Get vehicle details
        vehicle = data_manager.get_vehicle_by_id(sale['vehicle_id'])
        if not vehicle:
            flash('Vehicle not found', 'error')
            return redirect(url_for('downloads'))

        # Get expenses for this vehicle
        expenses = data_manager.get_expenses()
        vehicle_expenses = [e for e in expenses if e['vehicle_id'] == sale['vehicle_id']]

        # Create CSV in memory
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Vehicle Information
        writer.writerow(['VEHICLE INFORMATION'])
        writer.writerow(['Field', 'Value'])
        writer.writerow(['Vehicle ID', vehicle['id']])
        writer.writerow(['Make', vehicle['make']])
        writer.writerow(['Model', vehicle['model']])
        writer.writerow(['Year', vehicle['year']])
        writer.writerow(['VIN', vehicle['vin']])
        writer.writerow(['Purchase Price', f"${float(vehicle['price']):,.2f}"])
        writer.writerow(['Purchase Date', vehicle['date']])
        writer.writerow(['Notes', vehicle['notes']])
        writer.writerow([])

        # Sale Information
        writer.writerow(['SALE INFORMATION'])
        writer.writerow(['Field', 'Value'])
        writer.writerow(['Sale ID', sale['id']])
        writer.writerow(['Sale Price', f"${float(sale['sale_price']):,.2f}"])
        writer.writerow(['Sale Date', sale['sale_date']])
        writer.writerow(['Buyer Info', sale['buyer_info']])
        writer.writerow(['Sale Notes', sale['sale_notes']])
        writer.writerow([])

        # Expenses
        if vehicle_expenses:
            writer.writerow(['VEHICLE EXPENSES'])
            writer.writerow(['Expense ID', 'Date', 'Type', 'Amount', 'Description'])
            total_expenses = 0
            for expense in vehicle_expenses:
                writer.writerow([
                    expense['id'],
                    expense['date'],
                    expense['type'],
                    f"${float(expense['amount']):,.2f}",
                    expense['description']
                ])
                total_expenses += float(expense['amount'])
            writer.writerow(['', '', 'TOTAL EXPENSES', f"${total_expenses:,.2f}", ''])
            writer.writerow([])

        # Financial Summary
        writer.writerow(['FINANCIAL SUMMARY'])
        writer.writerow(['Item', 'Amount'])
        purchase_price = float(vehicle['price'])
        sale_price = float(sale['sale_price'])
        total_expenses = sum(float(e['amount']) for e in vehicle_expenses)
        gross_profit = sale_price - purchase_price
        net_profit = gross_profit - total_expenses

        writer.writerow(['Purchase Price', f"${purchase_price:,.2f}"])
        writer.writerow(['Sale Price', f"${sale_price:,.2f}"])
        writer.writerow(['Gross Profit', f"${gross_profit:,.2f}"])
        writer.writerow(['Total Expenses', f"${total_expenses:,.2f}"])
        writer.writerow(['Net Profit', f"${net_profit:,.2f}"])

        # Return CSV
        output = buffer.getvalue()
        buffer.close()

        filename = f"vehicle_report_{vehicle['make']}_{vehicle['model']}_{vehicle['year']}_sale_{sale_id}.csv"

        return send_file(
            io.BytesIO(output.encode('utf-8')),
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )

    except Exception as e:
        logging.error(f"Error generating vehicle CSV: {e}")
        flash('An error occurred while generating the CSV file', 'error')
        return redirect(url_for('downloads'))

@app.route('/download/all_sales_pdf')
def download_all_sales_pdf():
    """Download PDF report for all sales"""
    try:
        sales = data_manager.get_sales()
        if not sales:
            flash('No sales data available for download', 'error')
            return redirect(url_for('downloads'))

        # Create PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)

        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=30,
            alignment=1  # Center alignment
        )

        # Build PDF content
        story = []

        # Title
        story.append(Paragraph("ALL VEHICLE SALES REPORT", title_style))
        story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        story.append(Spacer(1, 30))

        # Sales Summary Table
        sales_data = [['Vehicle', 'Purchase Price', 'Sale Price', 'Sale Date', 'Profit/Loss']]

        total_purchase = 0
        total_sale = 0
        total_expenses = 0

        expenses = data_manager.get_expenses()

        for sale in sales:
            vehicle = data_manager.get_vehicle_by_id(sale['vehicle_id'])
            if vehicle:
                vehicle_expenses = [e for e in expenses if e['vehicle_id'] == sale['vehicle_id']]
                expense_total = sum(float(e['amount']) for e in vehicle_expenses)

                purchase_price = float(vehicle['price'])
                sale_price = float(sale['sale_price'])
                profit = sale_price - purchase_price - expense_total

                total_purchase += purchase_price
                total_sale += sale_price
                total_expenses += expense_total

                sales_data.append([
                    f"{vehicle['make']} {vehicle['model']} {vehicle['year']}",
                    f"${purchase_price:,.2f}",
                    f"${sale_price:,.2f}",
                    sale['sale_date'],
                    f"${profit:,.2f}"
                ])

        # Add totals row
        total_profit = total_sale - total_purchase - total_expenses
        sales_data.append(['TOTALS', f"${total_purchase:,.2f}", f"${total_sale:,.2f}", '', f"${total_profit:,.2f}"])

        sales_table = Table(sales_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1*inch, 1*inch])
        sales_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -2), 'LEFT'),  # Vehicle names left aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))

        story.append(sales_table)

        # Build PDF
        doc.build(story)

        # Return PDF
        buffer.seek(0)
        filename = f"all_sales_report_{datetime.now().strftime('%Y%m%d')}.pdf"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        logging.error(f"Error generating all sales PDF: {e}")
        flash('An error occurred while generating the PDF report', 'error')
        return redirect(url_for('downloads'))

@app.route('/download/all_sales_csv')
def download_all_sales_csv():
    """Download CSV of all sales data"""
    try:
        import csv

        sales = data_manager.get_sales()
        vehicles = data_manager.get_vehicles()
        expenses = data_manager.get_expenses()

        if not sales:
            flash('No sales data available for download', 'error')
            return redirect(url_for('downloads'))

        # Create CSV in memory
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Headers
        writer.writerow([
            'Sale ID', 'Vehicle ID', 'Make', 'Model', 'Year', 'VIN',
            'Purchase Price', 'Sale Price', 'Sale Date', 'Buyer Info',
            'Total Expenses', 'Net Profit', 'Sale Notes'
        ])

        for sale in sales:
            vehicle = data_manager.get_vehicle_by_id(sale['vehicle_id'])
            if vehicle:
                vehicle_expenses = [e for e in expenses if e['vehicle_id'] == vehicle['id']]
                total_expenses = sum(float(e['amount']) for e in vehicle_expenses)

                purchase_price = float(vehicle['price'])
                sale_price = float(sale['sale_price'])
                net_profit = sale_price - purchase_price - total_expenses

                writer.writerow([
                    sale['id'],
                    vehicle['id'],
                    vehicle['make'],
                    vehicle['model'],
                    vehicle['year'],
                    vehicle['vin'],
                    f"{purchase_price:.2f}",
                    f"{sale_price:.2f}",
                    sale['sale_date'],
                    sale['buyer_info'],
                    f"{total_expenses:.2f}",
                    f"{net_profit:.2f}",
                    sale['sale_notes']
                ])

        # Return CSV
        output = buffer.getvalue()
        buffer.close()

        filename = f"all_sales_data_{datetime.now().strftime('%Y%m%d')}.csv"

        return send_file(
            io.BytesIO(output.encode('utf-8')),
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )

    except Exception as e:
        logging.error(f"Error generating all sales CSV: {e}")
        flash('An error occurred while generating the CSV file', 'error')
        return redirect(url_for('downloads'))

@app.route('/download/inventory_summary')
def download_inventory_summary():
    """Download inventory summary CSV"""
    try:
        import csv

        vehicles = data_manager.get_vehicles()
        expenses = data_manager.get_expenses()
        sales = data_manager.get_sales()

        # Create CSV in memory
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Headers
        writer.writerow([
            'Vehicle ID', 'Make', 'Model', 'Year', 'VIN', 'Status',
            'Purchase Price', 'Purchase Date', 'Total Expenses',
            'Sale Price', 'Sale Date', 'Net Profit'
        ])

        for vehicle in vehicles:
            vehicle_expenses = [e for e in expenses if e['vehicle_id'] == vehicle['id']]
            total_expenses = sum(float(e['amount']) for e in vehicle_expenses)

            # Find sale if exists
            vehicle_sale = next((s for s in sales if s['vehicle_id'] == vehicle['id']), None)

            sale_price = float(vehicle_sale['sale_price']) if vehicle_sale else 0
            sale_date = vehicle_sale['sale_date'] if vehicle_sale else ''
            net_profit = sale_price - float(vehicle['price']) - total_expenses if vehicle_sale else 0

            writer.writerow([
                vehicle['id'],
                vehicle['make'],
                vehicle['model'],
                vehicle['year'],
                vehicle['vin'],
                vehicle['status'],
                f"{float(vehicle['price']):.2f}",
                vehicle['date'],
                f"{total_expenses:.2f}",
                f"{sale_price:.2f}" if vehicle_sale else '',
                sale_date,
                f"{net_profit:.2f}" if vehicle_sale else ''
            ])

        # Return CSV
        output = buffer.getvalue()
        buffer.close()

        filename = f"inventory_summary_{datetime.now().strftime('%Y%m%d')}.csv"

        return send_file(
            io.BytesIO(output.encode('utf-8')),
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )

    except Exception as e:
        logging.error(f"Error generating inventory summary: {e}")
        flash('An error occurred while generating the inventory summary', 'error')
        return redirect(url_for('downloads'))

@app.route('/bill_of_sale/<int:sale_id>')
def generate_bill_of_sale(sale_id):
    """Generate and download bill of sale PDF for a sold vehicle"""
    try:
        # Get sale details
        sales = data_manager.get_sales()
        sale = next((s for s in sales if s['id'] == sale_id), None)

        if not sale:
            flash('Sale not found', 'error')
            return redirect(url_for('sales'))

        # Get vehicle details
        vehicle = data_manager.get_vehicle_by_id(sale['vehicle_id'])
        if not vehicle:
            flash('Vehicle not found', 'error')
            return redirect(url_for('sales'))

        # Get expenses for this vehicle
        expenses = data_manager.get_expenses()
        vehicle_expenses = [e for e in expenses if e['vehicle_id'] == sale['vehicle_id']]

        # Create PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)

        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center alignment
        )

        # Build PDF content
        story = []

        # Title
        story.append(Paragraph("BILL OF SALE", title_style))
        story.append(Spacer(1, 20))

        # Vehicle Information
        story.append(Paragraph("<b>VEHICLE INFORMATION</b>", styles['Heading2']))
        vehicle_data = [
            ['Make:', vehicle['make']],
            ['Model:', vehicle['model']],
            ['Year:', vehicle['year']],
            ['VIN:', vehicle['vin']],
            ['Purchase Price:', f"${float(vehicle['price']):,.2f}"],
            ['Status:', vehicle['status']]
        ]

        vehicle_table = Table(vehicle_data, colWidths=[1.5*inch, 4*inch])
        vehicle_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(vehicle_table)
        story.append(Spacer(1, 20))

        # Sale Information
        story.append(Paragraph("<b>SALE INFORMATION</b>", styles['Heading2']))
        sale_data = [
            ['Sale ID:', str(sale['id'])],
            ['Sale Price:', f"${float(sale['sale_price']):,.2f}"],
            ['Sale Date:', sale['sale_date']],
            ['Buyer Info:', sale['buyer_info'] or 'Not provided'],
        ]

        sale_table = Table(sale_data, colWidths=[1.5*inch, 4*inch])
        sale_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(sale_table)
        story.append(Spacer(1, 20))

        # Sale Notes if available
        if sale.get('sale_notes'):
            story.append(Paragraph("<b>SALE NOTES</b>", styles['Heading2']))
            story.append(Paragraph(sale['sale_notes'], styles['Normal']))
            story.append(Spacer(1, 20))

        # Vehicle Expenses
        if vehicle_expenses:
            story.append(Paragraph("<b>VEHICLE EXPENSES</b>", styles['Heading2']))

            expense_data = [['Date', 'Type', 'Description', 'Amount']]
            total_expenses = 0

            for expense in vehicle_expenses:
                expense_data.append([
                    expense['date'],
                    expense['type'],
                    expense['description'] or 'N/A',
                    f"${float(expense['amount']):,.2f}"
                ])
                total_expenses += float(expense['amount'])

            # Add total row
            expense_data.append(['', '', 'TOTAL EXPENSES:', f"${total_expenses:,.2f}"])

            expense_table = Table(expense_data, colWidths=[1*inch, 1.5*inch, 2.5*inch, 1*inch])
            expense_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (2, 1), (2, -2), 'LEFT'),  # Description column left aligned
                ('ALIGN', (3, 0), (3, -1), 'RIGHT'), # Amount column right aligned
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (-2, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
            ]))
            story.append(expense_table)
            story.append(Spacer(1, 20))

        # Financial Summary
        story.append(Paragraph("<b>FINANCIAL SUMMARY</b>", styles['Heading2']))
        purchase_price = float(vehicle['price'])
        sale_price = float(sale['sale_price'])
        total_expenses = sum(float(e['amount']) for e in vehicle_expenses)
        gross_profit = sale_price - purchase_price
        net_profit = gross_profit - total_expenses

        financial_data = [
            ['Purchase Price:', f"${purchase_price:,.2f}"],
            ['Sale Price:', f"${sale_price:,.2f}"],
            ['Gross Profit:', f"${gross_profit:,.2f}"],
            ['Total Expenses:', f"${total_expenses:,.2f}"],
            ['Net Profit:', f"${net_profit:,.2f}"]
        ]

        financial_table = Table(financial_data, colWidths=[2*inch, 1.5*inch])
        financial_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (-2, -1), (-1, -1), 2, colors.black),
            ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        story.append(financial_table)
        story.append(Spacer(1, 30))

        # Footer
        story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))

        # Build PDF
        doc.build(story)

        # Return PDF
        buffer.seek(0)
        filename = f"bill_of_sale_{vehicle['make']}_{vehicle['model']}_{vehicle['year']}_sale_{sale_id}.pdf"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        logging.error(f"Error generating bill of sale: {e}")
        flash('An error occurred while generating the bill of sale', 'error')
        return redirect(url_for('sales'))

@app.route('/api/vehicle/<int:vehicle_id>')
def get_vehicle_api(vehicle_id):
    """API endpoint to get vehicle details"""
    vehicle = data_manager.get_vehicle_by_id(vehicle_id)
    if vehicle:
        return jsonify(vehicle)
    return jsonify({'error': 'Vehicle not found'}), 404

@app.route('/vehicle/<int:vehicle_id>/bill_of_sale/download')
def download_bill_of_sale(vehicle_id):
    """Download bill of sale for a vehicle"""
    try:
        vehicle = data_manager.get_vehicle_by_id(vehicle_id)
        if not vehicle:
            flash('Vehicle not found', 'error')
            return redirect(url_for('inventory'))

        if not data_manager.has_bill_of_sale(vehicle_id):
            flash('No bill of sale found for this vehicle', 'error')
            return redirect(url_for('inventory'))

        file_data = data_manager.get_bill_of_sale(vehicle_id)
        if not file_data:
            flash('Error retrieving bill of sale', 'error')
            return redirect(url_for('inventory'))

        # Get original filename from vehicle record
        original_filename = vehicle.get('bill_of_sale_filename', '').split('/')[-1]
        if not original_filename:
            original_filename = f"bill_of_sale_vehicle_{vehicle_id}.pdf"

        # Determine content type
        content_type = 'application/pdf'
        if original_filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif original_filename.lower().endswith('.png'):
            content_type = 'image/png'

        return send_file(
            io.BytesIO(file_data),
            as_attachment=True,
            download_name=original_filename,
            mimetype=content_type
        )

    except Exception as e:
        logging.error(f"Error downloading bill of sale: {e}")
        flash('Error downloading bill of sale', 'error')
        return redirect(url_for('inventory'))

@app.route('/vehicle/<int:vehicle_id>/bill_of_sale/delete')
def delete_vehicle_bill_of_sale(vehicle_id):
    """Delete bill of sale for a vehicle"""
    try:
        if data_manager.delete_bill_of_sale(vehicle_id):
            flash('Bill of sale deleted successfully', 'success')
        else:
            flash('Error deleting bill of sale', 'error')
    except Exception as e:
        logging.error(f"Error deleting bill of sale: {e}")
        flash('Error deleting bill of sale', 'error')

    return redirect(url_for('edit_vehicle', vehicle_id=vehicle_id))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)