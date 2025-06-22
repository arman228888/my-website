import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from data_manager import DataManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "vehicle-tracker-secret-key")

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
    """Delete a vehicle from inventory"""
    try:
        # Check if vehicle has associated sales or expenses
        expenses = data_manager.get_expenses()
        sales = data_manager.get_sales()
        
        vehicle_expenses = [e for e in expenses if e['vehicle_id'] == vehicle_id]
        vehicle_sales = [s for s in sales if s['vehicle_id'] == vehicle_id]
        
        if vehicle_expenses or vehicle_sales:
            flash('Cannot delete vehicle with associated expenses or sales. Please delete related records first.', 'error')
            return redirect(url_for('inventory'))
        
        if data_manager.delete_vehicle(vehicle_id):
            flash('Vehicle deleted successfully', 'success')
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

@app.route('/api/vehicle/<int:vehicle_id>')
def get_vehicle_api(vehicle_id):
    """API endpoint to get vehicle details"""
    vehicle = data_manager.get_vehicle_by_id(vehicle_id)
    if vehicle:
        return jsonify(vehicle)
    return jsonify({'error': 'Vehicle not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
