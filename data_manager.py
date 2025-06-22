import csv
import os
from datetime import datetime
from typing import List, Dict, Optional

class DataManager:
    """Handles all data operations for the vehicle tracker application"""

    def __init__(self):
        self.vehicles_file = 'vehicles.csv'
        self.expenses_file = 'expenses.csv'
        self.sales_file = 'sales.csv'

        # Initialize files if they don't exist
        self._initialize_files()

    def _initialize_files(self):
        """Create CSV files with headers if they don't exist"""
        # Vehicle headers
        if not os.path.exists(self.vehicles_file):
            with open(self.vehicles_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'make', 'model', 'year', 'vin', 'price', 'date', 'notes', 'status', 'bill_of_sale_filename'])

        # Expenses headers
        if not os.path.exists(self.expenses_file):
            with open(self.expenses_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'vehicle_id', 'type', 'amount', 'date', 'description'])

        # Sales headers
        if not os.path.exists(self.sales_file):
            with open(self.sales_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'vehicle_id', 'sale_price', 'sale_date', 'buyer_info', 'sale_notes'])

    def get_vehicles(self) -> List[Dict]:
        """Get all vehicles from CSV"""
        vehicles = []
        try:
            with open(self.vehicles_file, 'r') as f:
                reader = csv.DictReader(f)
                vehicles = list(reader)
                # Convert id to int for consistency
                for vehicle in vehicles:
                    vehicle['id'] = int(vehicle['id'])
        except FileNotFoundError:
            pass
        return vehicles

    def get_vehicle_by_id(self, vehicle_id: int) -> Optional[Dict]:
        """Get a specific vehicle by ID"""
        vehicles = self.get_vehicles()
        return next((v for v in vehicles if v['id'] == vehicle_id), None)

    def add_vehicle(self, vehicle_data: Dict) -> int:
        """Add a new vehicle and return its ID"""
        vehicles = self.get_vehicles()

        # Generate new ID
        vehicle_id = max([v['id'] for v in vehicles], default=0) + 1
        vehicle_data['id'] = vehicle_id

        # Write to CSV
        with open(self.vehicles_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'make', 'model', 'year', 'vin', 'price', 'date', 'notes', 'status', 'bill_of_sale_filename'])
            writer.writerow(vehicle_data)

        return vehicle_id

    def delete_vehicle(self, vehicle_id: int) -> bool:
        """Delete a vehicle by ID"""
        vehicles = self.get_vehicles()
        updated_vehicles = [v for v in vehicles if v['id'] != vehicle_id]

        if len(updated_vehicles) == len(vehicles):
            return False  # Vehicle not found

        # Rewrite the file
        with open(self.vehicles_file, 'w', newline='') as f:
            if updated_vehicles:
                writer = csv.DictWriter(f, fieldnames=['id', 'make', 'model', 'year', 'vin', 'price', 'date', 'notes', 'status', 'bill_of_sale_filename'])
                writer.writeheader()
                writer.writerows(updated_vehicles)
            else:
                # Write just headers if no vehicles left
                writer = csv.writer(f)
                writer.writerow(['id', 'make', 'model', 'year', 'vin', 'price', 'date', 'notes', 'status', 'bill_of_sale_filename'])

        return True

    def update_vehicle_status(self, vehicle_id: int, status: str) -> bool:
        """Update vehicle status"""
        vehicles = self.get_vehicles()
        updated = False

        for vehicle in vehicles:
            if vehicle['id'] == vehicle_id:
                vehicle['status'] = status
                updated = True
                break

        if updated:
            with open(self.vehicles_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['id', 'make', 'model', 'year', 'vin', 'price', 'date', 'notes', 'status', 'bill_of_sale_filename'])
                writer.writeheader()
                writer.writerows(vehicles)

        return updated

    def update_vehicle(self, vehicle_id: int, updated_data: Dict) -> bool:
        """Update a vehicle's information"""
        vehicles = self.get_vehicles()
        updated = False

        for vehicle in vehicles:
            if vehicle['id'] == vehicle_id:
                # Update all fields
                vehicle.update(updated_data)
                updated = True
                break

        if updated:
            with open(self.vehicles_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['id', 'make', 'model', 'year', 'vin', 'price', 'date', 'notes', 'status', 'bill_of_sale_filename'])
                writer.writeheader()
                writer.writerows(vehicles)

        return updated

    def vin_exists(self, vin: str) -> bool:
        """Check if a VIN already exists"""
        vehicles = self.get_vehicles()
        return any(v['vin'].upper() == vin.upper() for v in vehicles)

    def vehicle_exists(self, vehicle_id: int) -> bool:
        """Check if a vehicle exists"""
        return self.get_vehicle_by_id(vehicle_id) is not None

    def get_available_vehicles(self) -> List[Dict]:
        """Get vehicles that are available for sale (In Stock)"""
        vehicles = self.get_vehicles()
        return [v for v in vehicles if v['status'] == 'In Stock']

    def get_expenses(self) -> List[Dict]:
        """Get all expenses from CSV"""
        expenses = []
        try:
            with open(self.expenses_file, 'r') as f:
                reader = csv.DictReader(f)
                expenses = list(reader)
                # Convert IDs to int for consistency
                for expense in expenses:
                    expense['id'] = int(expense['id'])
                    expense['vehicle_id'] = int(expense['vehicle_id'])
        except FileNotFoundError:
            pass
        return expenses

    def add_expense(self, expense_data: Dict) -> int:
        """Add a new expense and return its ID"""
        expenses = self.get_expenses()

        # Generate new ID
        expense_id = max([e['id'] for e in expenses], default=0) + 1
        expense_data['id'] = expense_id

        # Write to CSV
        with open(self.expenses_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'vehicle_id', 'type', 'amount', 'date', 'description'])
            writer.writerow(expense_data)

        return expense_id

    def delete_expense(self, expense_id: int) -> bool:
        """Delete an expense by ID"""
        expenses = self.get_expenses()
        updated_expenses = [e for e in expenses if e['id'] != expense_id]

        if len(updated_expenses) == len(expenses):
            return False  # Expense not found

        # Rewrite the file
        with open(self.expenses_file, 'w', newline='') as f:
            if updated_expenses:
                writer = csv.DictWriter(f, fieldnames=['id', 'vehicle_id', 'type', 'amount', 'date', 'description'])
                writer.writeheader()
                writer.writerows(updated_expenses)
            else:
                # Write just headers if no expenses left
                writer = csv.writer(f)
                writer.writerow(['id', 'vehicle_id', 'type', 'amount', 'date', 'description'])

        return True

    def get_sales(self) -> List[Dict]:
        """Get all sales from CSV"""
        sales = []
        try:
            with open(self.sales_file, 'r') as f:
                reader = csv.DictReader(f)
                sales = list(reader)
                # Convert IDs to int for consistency
                for sale in sales:
                    sale['id'] = int(sale['id'])
                    sale['vehicle_id'] = int(sale['vehicle_id'])
        except FileNotFoundError:
            pass
        return sales

    def add_sale(self, sale_data: Dict) -> int:
        """Add a new sale and update vehicle status"""
        sales = self.get_sales()

        # Generate new ID
        sale_id = max([s['id'] for s in sales], default=0) + 1
        sale_data['id'] = sale_id

        # Write to CSV
        with open(self.sales_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'vehicle_id', 'sale_price', 'sale_date', 'buyer_info', 'sale_notes'])
            writer.writerow(sale_data)

        # Update vehicle status to Sold
        self.update_vehicle_status(int(sale_data['vehicle_id']), 'Sold')

        return sale_id

    def delete_sale(self, sale_id: int) -> bool:
        """Delete a sale and restore vehicle to inventory"""
        sales = self.get_sales()
        deleted_sale = None
        updated_sales = []

        for sale in sales:
            if sale['id'] == sale_id:
                deleted_sale = sale
            else:
                updated_sales.append(sale)

        if not deleted_sale:
            return False  # Sale not found

        # Rewrite the file
        with open(self.sales_file, 'w', newline='') as f:
            if updated_sales:
                writer = csv.DictWriter(f, fieldnames=['id', 'vehicle_id', 'sale_price', 'sale_date', 'buyer_info', 'sale_notes'])
                writer.writeheader()
                writer.writerows(updated_sales)
            else:
                # Write just headers if no sales left
                writer = csv.writer(f)
                writer.writerow(['id', 'vehicle_id', 'sale_price', 'sale_date', 'buyer_info', 'sale_notes'])

        # Restore vehicle to In Stock status
        self.update_vehicle_status(deleted_sale['vehicle_id'], 'In Stock')

        return True

    def get_dashboard_stats(self) -> Dict:
        """Generate dashboard statistics"""
        vehicles = self.get_vehicles()
        expenses = self.get_expenses()
        sales = self.get_sales()

        # Calculate statistics
        total_vehicles = len(vehicles)
        in_stock_vehicles = len([v for v in vehicles if v['status'] == 'In Stock'])
        sold_vehicles = len([v for v in vehicles if v['status'] == 'Sold'])

        total_inventory_value = sum(float(v['price']) for v in vehicles if v['status'] == 'In Stock')
        total_expenses = sum(float(e['amount']) for e in expenses)
        total_sales_revenue = sum(float(s['sale_price']) for s in sales)

        # Calculate profit (sales revenue - purchase cost of sold vehicles - expenses)
        sold_vehicle_costs = 0
        for sale in sales:
            vehicle = self.get_vehicle_by_id(sale['vehicle_id'])
            if vehicle:
                sold_vehicle_costs += float(vehicle['price'])

        gross_profit = total_sales_revenue - sold_vehicle_costs
        net_profit = gross_profit - total_expenses

        return {
            'total_vehicles': total_vehicles,
            'in_stock_vehicles': in_stock_vehicles,
            'sold_vehicles': sold_vehicles,
            'total_inventory_value': total_inventory_value,
            'total_expenses': total_expenses,
            'total_sales_revenue': total_sales_revenue,
            'gross_profit': gross_profit,
            'net_profit': net_profit
        }

    def generate_reports(self) -> Dict:
        """Generate comprehensive reports"""
        vehicles = self.get_vehicles()
        expenses = self.get_expenses()
        sales = self.get_sales()

        # Vehicle summary by make
        make_summary = {}
        for vehicle in vehicles:
            make = vehicle['make']
            if make not in make_summary:
                make_summary[make] = {'total': 0, 'in_stock': 0, 'sold': 0}
            make_summary[make]['total'] += 1
            if vehicle['status'] == 'In Stock':
                make_summary[make]['in_stock'] += 1
            elif vehicle['status'] == 'Sold':
                make_summary[make]['sold'] += 1

        # Expense summary by type
        expense_summary = {}
        for expense in expenses:
            exp_type = expense['type']
            if exp_type not in expense_summary:
                expense_summary[exp_type] = {'count': 0, 'total_amount': 0}
            expense_summary[exp_type]['count'] += 1
            expense_summary[exp_type]['total_amount'] += float(expense['amount'])

        # Sales summary by month
        sales_by_month = {}
        for sale in sales:
            try:
                # Parse date and get year-month
                sale_date = datetime.strptime(sale['sale_date'], '%Y-%m-%d')
                month_key = sale_date.strftime('%Y-%m')
                if month_key not in sales_by_month:
                    sales_by_month[month_key] = {'count': 0, 'revenue': 0}
                sales_by_month[month_key]['count'] += 1
                sales_by_month[month_key]['revenue'] += float(sale['sale_price'])
            except ValueError:
                continue  # Skip invalid dates

        # Most profitable vehicles (vehicles with expenses and sales)
        vehicle_profits = []
        for sale in sales:
            vehicle = self.get_vehicle_by_id(sale['vehicle_id'])
            if vehicle:
                vehicle_expenses = [e for e in expenses if e['vehicle_id'] == sale['vehicle_id']]
                total_expenses = sum(float(e['amount']) for e in vehicle_expenses)
                profit = float(sale['sale_price']) - float(vehicle['price']) - total_expenses

                vehicle_profits.append({
                    'vehicle': f"{vehicle['make']} {vehicle['model']} {vehicle['year']}",
                    'purchase_price': float(vehicle['price']),
                    'sale_price': float(sale['sale_price']),
                    'expenses': total_expenses,
                    'profit': profit,
                    'sale_date': sale['sale_date']
                })

        # Sort by profit descending
        vehicle_profits.sort(key=lambda x: x['profit'], reverse=True)

        return {
            'make_summary': make_summary,
            'expense_summary': expense_summary,
            'sales_by_month': sales_by_month,
            'vehicle_profits': vehicle_profits[:10]  # Top 10 most profitable
        }