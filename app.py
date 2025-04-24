from flask import Flask, render_template, jsonify
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)

# Configuration
DATA_DIR = 'data'
BLACKLIST_FILE = os.path.join(DATA_DIR, 'blacklist.xlsx')

def process_blacklist():
    try:
        df = pd.read_excel('data/blacklist.xlsx', sheet_name='Sheet1', engine='openpyxl')
        return df.rename(columns={
            'In-Game Name': 'ign',
            'Player ID': 'game_id',
            'Discord ID': 'discord_id',
            'Reason': 'reason',
            'Status': 'status',
            'Date Added': 'date_added'
        }).to_dict('records')
    except Exception as e:
        print(f"Error processing blacklist: {e}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/blacklist')
def get_blacklist():
    data = process_blacklist()
    return jsonify({'data': data})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')