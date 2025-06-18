import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone

def scrape_oddsportal():
    url = "https://www.oddsportal.com/virtual-soccer/results/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except:
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    matches = []
    
    for row in soup.select('.table-main tbody tr:not(.center)'):
        try:
            # Ignorar linhas de cabeçalho
            if 'dark' in row.get('class', []):
                continue
                
            league = row.select_one('td:nth-child(1) a').text.strip()
            teams = row.select_one('td:nth-child(2) a').text.strip()
            score = row.select_one('td:nth-child(3)').text.strip()
            
            if ':' not in score:
                continue
                
            home_team, away_team = teams.split(' - ')
            home_goals, away_goals = map(int, score.split(':'))
            
            matches.append({
                'id': f'oddsportal_{datetime.now().timestamp()}',
                'league': league,
                'home_team': home_team,
                'away_team': away_team,
                'home_goals': home_goals,
                'away_goals': away_goals,
                'minute': 90,
                'status': 'Finalizado',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'odds': {
                    'home': round(1.5 + (abs(home_goals - away_goals) * 0.2), 2),
                    'draw': round(3.0 + (abs(home_goals - away_goals) * 0.1), 2),
                    'away': round(4.0 - (abs(home_goals - away_goals) * 0.1), 2)
                }
            })
        except Exception as e:
            print(f"Erro ao processar linha: {e}")
    
    return matches

if __name__ == "__main__":
    matches = scrape_oddsportal()
    data = {
        "matches": matches,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    
    with open('live-matches.json', 'w') as f:
        json.dump(data, f, indent=2)
