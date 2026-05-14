import os
import datetime
import re # Added for Regex matching
from flask import Flask, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from flask_cors import CORS
import certifi

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# INSERT YOUR ATLAS CONNECTION STRING HERE
MONGO_URI = "mongodb+srv://admin:dangel143@cluster0.qb2arpu.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['findit_db']
items_collection = db['items']

# ... (Keep all your imports and MongoDB connection setup exactly the same) ...

# --- PAGE ROUTES ---
@app.route('/')
def student_portal():
    # Serves the public student page
    return send_file('student.html')

@app.route('/admin')
def admin_portal():
    # Serves the private admin dashboard
    return send_file('admin.html')

# ... (Keep all your /api/items routes exactly the same as before) ...

@app.route('/uploads/<filename>')
def get_uploaded_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/items', methods=['GET'])
def get_items():
    items = list(items_collection.find({}, {'_id': 0}))
    return jsonify(items), 200

@app.route('/api/items', methods=['POST'])
def add_item():
    try:
        data = request.form.to_dict()
        file = request.files.get('image')
        if file and file.filename != '':
            filename = f"{int(datetime.datetime.now().timestamp())}_{secure_filename(file.filename)}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            data['image'] = filename
        else:
            data['image'] = None

        count = items_collection.count_documents({})
        data['id'] = f"ITM-{str(count + 1).zfill(3)}"
        data['date'] = datetime.datetime.now().strftime("%Y-%m-%d")
        data['status'] = data.get('status', 'found')
        
        items_collection.insert_one(data.copy())
        return jsonify({"message": "Item added successfully", "id": data['id']}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/items/<item_id>', methods=['PUT'])
def update_item(item_id):
    data = request.json
    update_data = {'name': data['name'], 'status': data['status'], 'desc': data['desc']}
    if data['status'] == 'claimed':
        update_data['claimer_name'] = data.get('claimer_name', '')
        update_data['claimer_id'] = data.get('claimer_id', '')
        update_data['claim_date'] = datetime.datetime.now().strftime("%Y-%m-%d")

    items_collection.update_one({'id': item_id}, {'$set': update_data})
    return jsonify({"message": "Item updated"}), 200

@app.route('/api/items/<item_id>', methods=['DELETE'])
def delete_item(item_id):
    items_collection.delete_one({'id': item_id})
    return jsonify({"message": "Item deleted"}), 200

# --- NEW: SMART MATCHING ALGORITHM ---
@app.route('/api/items/<item_id>/matches', methods=['GET'])
def find_matches(item_id):
    # 1. Get the lost item
    lost_item = items_collection.find_one({'id': item_id}, {'_id': 0})
    if not lost_item:
        return jsonify({"error": "Item not found"}), 404

    # 2. Extract keywords from the lost item's name (ignoring small words)
    words = [word for word in lost_item['name'].split() if len(word) > 2]
    if not words:
        words = [lost_item['name']] # Fallback if name is short
    
    # Create a regex pattern (e.g. "Blue|Backpack")
    regex_pattern = "|".join([re.escape(w) for w in words])

    # 3. Query MongoDB for items that are 'found', in the same category, and match the keywords
    query = {
        'status': 'found',
        'cat': lost_item['cat'],
        '$or': [
            {'name': {'$regex': regex_pattern, '$options': 'i'}},
            {'desc': {'$regex': regex_pattern, '$options': 'i'}}
        ]
    }
    
    matches = list(items_collection.find(query, {'_id': 0}))
    return jsonify({"lost_item": lost_item, "matches": matches}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)