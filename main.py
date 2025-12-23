from flask import Flask, request, jsonify, render_template
import json
from datetime import datetime
import math
import os

# Get the directory where this script is located
basedir = os.path.abspath(os.path.dirname(__file__))

# Create Flask app with proper template folder configuration
app = Flask(__name__, template_folder=os.path.join(basedir, 'templates'), static_folder=os.path.join(basedir, 'static'))

# U.S. State Labor Rates (USD/hour) - Based on 2025 market data
STATE_LABOR_RATES = {
    'AL': 28, 'AK': 35, 'AZ': 32, 'AR': 26, 'CA': 38, 'CO': 34, 'CT': 40, 'DE': 33, 
    'FL': 30, 'GA': 29, 'HI': 42, 'ID': 28, 'IL': 36, 'IN': 29, 'IA': 27, 'KS': 26,
    'KY': 27, 'LA': 27, 'ME': 31, 'MD': 34, 'MA': 41, 'MI': 32, 'MN': 33, 'MS': 25,
    'MO': 28, 'MT': 29, 'NE': 27, 'NV': 34, 'NH': 32, 'NJ': 38, 'NM': 27, 'NY': 39,
    'NC': 28, 'ND': 26, 'OH': 30, 'OK': 26, 'OR': 33, 'PA': 35, 'RI': 36, 'SC': 27,
    'SD': 25, 'TN': 28, 'TX': 29, 'UT': 30, 'VT': 32, 'VA': 31, 'WA': 36, 'WV': 27,
    'WI': 31, 'WY': 27
}

# Job type multipliers for labor complexity
JOB_TYPE_MULTIPLIERS = {
    'plumbing': 1.2,
    'electrical': 1.3,
    'hvac': 1.25,
    'roofing': 1.4,
    'carpentry': 1.15,
    'painting': 1.0,
    'flooring': 1.1,
    'drywall': 1.05,
    'general_repair': 1.0,
    'landscaping': 0.9,
    'window_replacement': 1.15,
    'insulation': 1.0,
    'siding': 1.2,
    'bathroom_remodel': 1.3,
    'kitchen_remodel': 1.4
}

# Urgency multipliers
URGENCY_MULTIPLIERS = {
    'normal': 1.0,
    'same_day': 1.25,
    'emergency': 1.5
}

# Logistics cost per km in USD
LOGISTICS_RATE_PER_KM = 0.50

def calculate_logistics_cost(distance_km):
    """Calculate logistics cost based on distance"""
    base_cost = 50  # Base service call fee
    distance_cost = distance_km * LOGISTICS_RATE_PER_KM
    return round(base_cost + distance_cost, 2)

def select_supplier(material_prices):
    """Select the most cost-effective supplier"""
    if not material_prices:
        return None, 0
    
    sorted_suppliers = sorted(material_prices.items(), key=lambda x: x[1])
    return sorted_suppliers[0][0], sorted_suppliers[0][1]

def calculate_pricing(job_data):
    """
    Core pricing engine - generates fair and realistic U.S. home services quotes
    """
    try:
        # Extract input data
        job_type = job_data.get('job_type', '').lower()
        job_description = job_data.get('job_description', '')
        urgency = job_data.get('urgency', 'normal').lower()
        labor_hours = float(job_data.get('labor_hours', 2))
        
        state = job_data.get('state', 'CA').upper()
        distance_km = float(job_data.get('distance_km', 10))
        
        material_prices = job_data.get('material_prices', {})
        
        # Validation
        if state not in STATE_LABOR_RATES:
            return None, "Invalid state code"
        
        if urgency not in URGENCY_MULTIPLIERS:
            urgency = 'normal'
        
        if labor_hours < 0.5 or labor_hours > 100:
            return None, "Labor hours must be between 0.5 and 100"
        
        # Get base labor rate for state
        state_labor_rate = STATE_LABOR_RATES.get(state, 30)
        
        # Apply job type multiplier
        job_multiplier = JOB_TYPE_MULTIPLIERS.get(job_type, 1.0)
        
        # Apply urgency multiplier
        urgency_multiplier = URGENCY_MULTIPLIERS.get(urgency, 1.0)
        
        # Calculate labor cost
        base_hourly_rate = state_labor_rate * job_multiplier
        labor_cost = base_hourly_rate * labor_hours * urgency_multiplier
        labor_cost = round(labor_cost, 2)
        
        # Select material supplier and cost
        material_source, material_cost = select_supplier(material_prices)
        if material_source is None:
            material_source = "Standard Materials"
            material_cost = 0
        else:
            material_cost = round(material_cost, 2)
        
        # Calculate logistics cost
        logistics_cost = calculate_logistics_cost(distance_km)
        
        # Calculate subtotal before margin
        subtotal = labor_cost + material_cost + logistics_cost
        
        # Calculate technician payout (68% of labor revenue - middle of 65-75% range)
        technician_payout = round(labor_cost * 0.68, 2)
        
        # Calculate platform margin (target 25-28% of total client price)
        # We'll work backwards: client_price = subtotal + platform_margin
        # If margin is 25% of client_price, then: client_price = subtotal / 0.75
        # This gives platform margin of 25%
        
        # Target platform margin percentage
        target_margin_percent = 0.27  # 27% - within 20-35% range
        
        # Client price calculation: subtotal / (1 - target_margin_percent)
        client_price = round(subtotal / (1 - target_margin_percent), 2)
        
        # Calculate actual platform margin
        platform_margin = round(client_price - subtotal, 2)
        
        # Recalculate to ensure margin is within 20-35%
        actual_margin_percent = platform_margin / client_price if client_price > 0 else 0
        
        # Adjust if needed
        if actual_margin_percent < 0.20:
            # Too low, increase price
            client_price = round(subtotal / 0.80, 2)
            platform_margin = round(client_price - subtotal, 2)
        elif actual_margin_percent > 0.35:
            # Too high, decrease price
            client_price = round(subtotal / 0.65, 2)
            platform_margin = round(client_price - subtotal, 2)
        
        # Determine pricing confidence
        pricing_confidence = "high"
        if not material_prices:
            pricing_confidence = "medium"
        if labor_hours > 50 or client_price > 2000:
            pricing_confidence = "medium"
        
        # Determine if approval is required
        approval_required = False
        if urgency == 'emergency':
            approval_required = True
        if client_price > 3000:
            approval_required = True
        if pricing_confidence == "low":
            approval_required = True
        
        # Build response
        response = {
            "client_price": round(client_price),
            "technician_payout": round(technician_payout),
            "material_source": material_source,
            "material_cost": round(material_cost),
            "labor_cost": round(labor_cost),
            "logistics_cost": round(logistics_cost),
            "platform_margin": round(platform_margin),
            "pricing_confidence": pricing_confidence,
            "approval_required": approval_required
        }
        
        return response, None
        
    except Exception as e:
        return None, str(e)

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/quote-form')
def quote_form():
    """Quote form page"""
    return render_template('quote_form.html')

@app.route('/quote-result')
def quote_result():
    """Quote result page"""
    return render_template('quote_result.html')

@app.route('/api/calculate-quote', methods=['POST'])
def calculate_quote():
    """
    API endpoint for quote calculation
    Expects JSON with job details and returns pricing JSON
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Calculate pricing
        result, error = calculate_pricing(data)
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/states', methods=['GET'])
def get_states():
    """Get list of available states and their labor rates"""
    return jsonify({
        "states": sorted(STATE_LABOR_RATES.keys()),
        "rates": STATE_LABOR_RATES
    }), 200

@app.route('/api/job-types', methods=['GET'])
def get_job_types():
    """Get list of available job types"""
    return jsonify({
        "job_types": sorted(JOB_TYPE_MULTIPLIERS.keys())
    }), 200

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)