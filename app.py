from flask import Flask, render_template, jsonify, request, abort
import pandas as pd
from datetime import datetime
import os
import sqlite3

app = Flask(__name__)

# Configuration
DATA_DIR = 'data'
BLACKLIST_FILE = os.path.join(DATA_DIR, 'blacklist.xlsx')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'tournaments1.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

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
def index():
    return render_template('index.html')

@app.route('/blacklist')
def blacklist():
    return render_template('blacklist.html')

@app.route('/tournaments/<tournament_name>')
def tournament_details(tournament_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch tournament details
        cursor.execute('''
            SELECT 
                t.*,
                COUNT(DISTINCT team.team_id) as registered_teams,
                t.tournament_brackets as brackets,
                CASE 
                    WHEN t.start_date > datetime('now') THEN 'upcoming'
                    WHEN t.end_date < datetime('now') THEN 'completed'
                    ELSE 'active'
                END as status
            FROM tournaments t
            LEFT JOIN teams team ON t.challonge_id = team.tournament_id
            WHERE t.name = ?
            GROUP BY t.tournament_id
        ''', (tournament_name,))
        
        tournament = cursor.fetchone()
        
        if not tournament:
            print(f"Tournament with name '{tournament_name}' not found")
            conn.close()
            abort(404)
        
        # Fetch teams in the tournament
        cursor.execute('''
            SELECT 
                team.*, 
                GROUP_CONCAT(p.name) as player_names,
                GROUP_CONCAT(p.game_id) as player_ids,
                GROUP_CONCAT(p.region) as player_regions,
                GROUP_CONCAT(p.clan_name) as player_clans
            FROM teams team
            LEFT JOIN json_each(team.players) as player_list
            LEFT JOIN players p ON json_extract(player_list.value, '$.id') = p.player_id
            WHERE team.tournament_id = ?
            GROUP BY team.team_id
        ''', (tournament['challonge_id'],))
        
        teams = []
        for row in cursor.fetchall():
            team_dict = dict(row)
            # Process player data
            player_names = team_dict['player_names'].split(',') if team_dict['player_names'] else []
            player_ids = team_dict['player_ids'].split(',') if team_dict['player_ids'] else []
            player_regions = team_dict['player_regions'].split(',') if team_dict['player_regions'] else []
            player_clans = team_dict['player_clans'].split(',') if team_dict['player_clans'] else []
            
            # Combine player details
            team_dict['players'] = [
                {
                    'name': name,
                    'id': pid,
                    'region': region,
                    'clan': clan
                }
                for name, pid, region, clan in zip(player_names, player_ids, player_regions, player_clans)
            ]
            teams.append(team_dict)
        
        # Fetch matches in the tournament
        cursor.execute('''
            SELECT 
                m.match_id,
                m.round,
                m.match_date,
                m.format_type,
                m.recording_type,
                m.server_type,
                CASE
                   WHEN m.match_date > datetime('now') THEN 'upcoming'
                   WHEN m.status = 'underway' THEN 'live'
                   ELSE 'completed'
                END as status,
                t1.logo_url as team1_logo,
                t2.logo_url as team2_logo
            FROM matches m
            LEFT JOIN teams t1 ON m.team1_id = t1.team_id
            LEFT JOIN teams t2 ON m.team2_id = t2.team_id
            WHERE m.tournament_id = ?
        ''', (tournament['tournament_id'],))
        
        matches = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return render_template('tournament.html',
                               tournament=dict(tournament),
                               teams=teams,
                               matches=matches)
                             
    except Exception as e:
        print(f"Error fetching tournament details: {str(e)}")
        abort(404)

@app.route('/api/tournaments')
def get_tournaments():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch tournaments with team count and status
        cursor.execute('''
            SELECT 
                t.tournament_id,
                t.name,
                t.max_teams,
                t.region,
                t.format,
                t.logo_url,
                t.start_date,
                t.end_date,
                COUNT(DISTINCT team.team_id) AS registered_teams,
                CASE 
                    WHEN t.start_date > datetime('now') THEN 'upcoming'
                    WHEN t.end_date < datetime('now') THEN 'completed'
                    ELSE 'active'
                END AS status
            FROM tournaments t
            LEFT JOIN teams team ON t.challonge_id = team.tournament_id
            GROUP BY t.tournament_id
            ORDER BY t.start_date DESC
        ''')

        tournaments = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({'success': True, 'data': tournaments})

    except Exception as e:
        print(f"Error fetching tournaments: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tournament/<int:tournament_id>')
def get_tournament_details(tournament_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch tournament details
        cursor.execute('''
            SELECT 
                t.tournament_id,
                t.challonge_id,
                t.name,
                t.max_teams,
                t.region,
                t.format,
                t.logo_url,
                t.start_date,
                t.end_date,
                t.tournament_brackets,
                COUNT(DISTINCT team.team_id) AS registered_teams
            FROM tournaments t
            LEFT JOIN teams team ON t.challonge_id = team.tournament_id
            WHERE t.tournament_id = ?
            GROUP BY t.tournament_id
        ''', (tournament_id,))
        tournament = cursor.fetchone()

        if not tournament:
            return jsonify({'success': False, 'error': 'Tournament not found'}), 404

        # Fetch teams in the tournament
        cursor.execute('''
            SELECT 
                team.team_id,
                team.name,
                team.tag,
                team.region,
                team.logo_url,
                team.checked_in
            FROM teams team
            WHERE team.tournament_id = ?
        ''', (tournament['challonge_id'],))
        teams = [dict(row) for row in cursor.fetchall()]

        # Fetch matches in the tournament
        cursor.execute('''
            SELECT 
                m.match_id,
                m.round,
                m.match_date,
                m.format_type,
                m.recording_type,
                m.server_type,
                m.status,
                t1.name AS team1_name,
                t2.name AS team2_name
            FROM matches m
            LEFT JOIN teams t1 ON m.team1_id = t1.team_id
            LEFT JOIN teams t2 ON m.team2_id = t2.team_id
            WHERE m.tournament_id = ?
        ''', (tournament_id,))
        matches = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'tournament': dict(tournament),
                'teams': teams,
                'matches': matches
            }
        })

    except Exception as e:
        print(f"Error fetching tournament details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/players/search')
def search_players():
    try:
        query = request.args.get('q', '').strip()
        if len(query) < 3:
            return jsonify({'success': False, 'error': 'Query too short'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Updated query to correctly join teams through the players JSON array
        cursor.execute('''
            SELECT DISTINCT 
                p.*,
                t.name as team_name,
                t.tag as team_tag
            FROM players p
            LEFT JOIN teams t ON EXISTS (
                SELECT 1 
                FROM json_each(t.players) as player_list 
                WHERE json_extract(player_list.value, '$.id') = p.player_id
            )
            WHERE 
                p.name LIKE ? OR
                p.game_id LIKE ? OR
                p.clan_name LIKE ?
            GROUP BY p.player_id
            LIMIT 10
        ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
        
        players = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({'success': True, 'data': players})
        
    except Exception as e:
        print(f"Error searching players: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/blacklist')
def get_blacklist():
    data = process_blacklist()
    return jsonify({'data': data})

@app.route('/tournaments')
def tournaments():
    return render_template('index.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')