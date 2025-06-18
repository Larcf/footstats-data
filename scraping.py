import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
import random
import time
import os
from urllib.parse import urljoin
import cloudscraper  # Biblioteca para contornar Cloudflare

def get_random_user_agent():
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
    ]
    return random.choice(agents)

def scrape_oddsportal():
    base_url = "https://www.oddsportal.com"
    url = urljoin(base_url, "/virtual-soccer/results/")
    
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'Referer': base_url
    }

    try:
        # Usar cloudscraper para bypass no Cloudflare
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"Status code error: {response.status_code}")
        
        if "Access denied" in response.text:
            raise Exception("Cloudflare bloqueou o acesso")

        soup = BeautifulSoup(response.text, 'html.parser')
        matches = []
        
        # Verificar se a tabela existe
        table = soup.select_one('.table-main')
        if not table:
            raise Exception("Tabela de resultados não encontrada")
        
        for row in table.select('tr:not(.center):not(.dark)'):
            try:
                # Extrair dados com seletores mais resilientes
                league_elem = row.select_one('a[href*="/virtual-soccer/"]')
                teams_elem = row.select_one('a[href*="/match/"]')
                score_elem = row.select_one('.score')
                
                if not all([league_elem, teams_elem, score_elem]):
                    continue
                    
                league = league_elem.text.strip()
                teams = teams_elem.text.strip()
                score = score_elem.text.strip()
                
                if ':' not in score:
                    continue
                    
                home_team, away_team = teams.split(' - ')
                home_goals, away_goals = map(int, score.split(':'))
                
                # Extrair odds reais se disponíveis
                odds_home = row.select_one('.odds-cell:nth-child(4)')
                odds_draw = row.select_one('.odds-cell:nth-child(5)')
                odds_away = row.select_one('.odds-cell:nth-child(6)')
                
                odds = {}
                if odds_home: odds['home'] = float(odds_home.text.strip())
                if odds_draw: odds['draw'] = float(odds_draw.text.strip())
                if odds_away: odds['away'] = float(odds_away.text.strip())
                
                # Gerar ID único
                match_id = f"{league}-{home_team}-{away_team}-{score}".replace(' ', '_')
                
                matches.append({
                    'id': match_id,
                    'league': league,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_goals': home_goals,
                    'away_goals': away_goals,
                    'minute': 90,
                    'status': 'Finalizado',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'odds': odds if odds else None
                })
                
                # Delay aleatório entre requisições
                time.sleep(random.uniform(0.5, 2.5))
                
            except Exception as e:
                print(f"Erro ao processar linha: {e}")
                continue
        
        return matches
    
    except Exception as e:
        print(f"Erro no scraping: {e}")
        return []

if __name__ == "__main__":
    # Configurar proxy via variáveis de ambiente
    proxies = {
        'http': os.getenv('HTTP_PROXY'),
        'https': os.getenv('HTTPS_PROXY')
    } if os.getenv('USE_PROXY') else None
        
    matches = scrape_oddsportal()
    
    data = {
        "matches": matches,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "status": "success" if matches else "empty" if matches is not None else "error"
    }
    
    with open('live-matches.json', 'w') as f:
        json.dump(data, f, indent=2)
