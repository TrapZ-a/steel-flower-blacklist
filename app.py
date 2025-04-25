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
        # 1. Verify file existence
        if not os.path.exists('data/blacklist.xlsx'):
            print("Error: File not found at data/blacklist.xlsx")
            return []

        # 2. Read with debug logging
        print("Loading Excel file...")
        df = pd.read_excel(
            'data/blacklist.xlsx',
            sheet_name='Sheet1',
            engine='openpyxl',
            dtype={'Discord ID': str, 'Player ID': str},
            na_filter=False
        )
        print(f"Raw data loaded ({len(df)} rows):\n{df.head()}")

        # 3. Clean Discord IDs
        def clean_discord_id(x):
            try:
                if x.strip() in ['', 'N/A', 'nan']:
                    return ''
                return f"{int(float(x))}"
            except Exception as e:
                print(f"Error cleaning ID {x}: {str(e)}")
                return ''
            
        if 'Discord ID' in df.columns:
            print("Cleaning Discord IDs...")
            df['Discord ID'] = df['Discord ID'].apply(clean_discord_id)
        else:
            print("Warning: Discord ID column missing")

        # 4. Date handling with validation
        if 'Date Added' in df.columns:
            print("Processing dates...")
            df['Date Added'] = pd.to_datetime(
                df['Date Added'],
                errors='coerce',
                format='mixed'
            )
            # Convert to ISO format and handle NaT
            df['Date Added'] = df['Date Added'].apply(
                lambda x: x.isoformat() if not pd.isna(x) else None
            )
            print("Date conversion counts:")
            print(df['Date Added'].value_counts(dropna=False))
        else:
            print("Warning: Date Added column missing")

        # 5. Column renaming verification
        column_map = {
            'In-Game Name': 'ign',
            'Player ID': 'game_id',
            'Discord Username': 'discord_username',
            'Discord ID': 'discord_id',
            'Reason': 'reason',
            'Status': 'status',
            'Date Added': 'date_added'
        }
        
        print("Original columns:", df.columns.tolist())
        df = df.rename(columns=column_map)
        print("Renamed columns:", df.columns.tolist())

        # 6. Final data validation
        required_columns = ['ign', 'game_id', 'reason', 'status']
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            print(f"Critical error: Missing columns {missing_cols}")
            return []
            
        print("Processed data sample:\n", df.head().to_dict())
        return df.to_dict('records')
        
    except Exception as e:
        print(f"Error processing blacklist: {str(e)}")
        import traceback
        traceback.print_exc()
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