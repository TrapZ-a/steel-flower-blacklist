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
        if not os.path.exists('data/blacklist.xlsx'):
            print("Error: File not found at data/blacklist.xlsx")
            return []

        print("Loading Excel file...")
        df = pd.read_excel(
            'data/blacklist.xlsx',
            sheet_name='Sheet1',
            engine='openpyxl',
            dtype={'Discord ID': str, 'Player ID': str},
            na_filter=False
        )

        def clean_discord_id(x):
            try:
                if x.strip() in ['', 'N/A', 'nan']:
                    return ''
                return f"{int(float(x))}"
            except Exception as e:
                print(f"Error cleaning ID {x}: {str(e)}")
                return ''
            
        if 'Discord ID' in df.columns:
            df['Discord ID'] = df['Discord ID'].apply(clean_discord_id)
        else:
            print("Warning: Discord ID column missing")

        if 'Date Added' in df.columns:
            df['Date Added'] = pd.to_datetime(
                df['Date Added'],
                errors='coerce',
                format='mixed'
            )
            df['Date Added'] = df['Date Added'].apply(
                lambda x: x.isoformat() if not pd.isna(x) else None
            )
        else:
            print("Warning: Date Added column missing")

        column_map = {
            'In-Game Name': 'ign',
            'Player ID': 'game_id',
            'Discord Username': 'discord_username',
            'Discord ID': 'discord_id',
            'Reason': 'reason',
            'Status': 'status',
            'Date Added': 'date_added'
        }
        
        df = df.rename(columns=column_map)

        required_columns = ['ign', 'game_id', 'reason', 'status']
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            print(f"Critical error: Missing columns {missing_cols}")
            return []
            
        return df.to_dict('records')
        
    except Exception as e:
        print(f"Error processing blacklist: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

@app.route('/')
@app.route('/blacklist')
def index():
    return render_template('index.html')

@app.route('/api/blacklist')
def get_blacklist():
    data = process_blacklist()
    return jsonify({'data': data})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')