import requests
from bs4 import BeautifulSoup
import json
import os
import random
import time
import hashlib
import pickle
from datetime import datetime
import pytz
from pydantic import BaseModel, validator
from tenacity import retry, stop_after_attempt, wait_exponential

# Modelo de validação de dados
class Match(BaseModel):
    id: str
    league: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    minute: int = 90
    status: str = "Finalizado"
    timestamp: str
    odds: dict | None = None
    
    @validator('home_goals', 'away_goals')
    def goals_valid(cls, v):
        if v < 0 or v > 30:
            raise ValueError(f"Gols inválidos: {v}")
        return v

def get_random_user_agent():
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
    ]
    return random.choice(agents)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def fetch_url(scraper, url, headers, timeout=30):
    return scraper.get(url, headers=headers, timeout=timeout)

def scrape_oddsportal():
    base_url = "https://www.oddsportal.com"
    url = urljoin(base_url, "/virtual-soccer/results/")
    tz = pytz.timezone('America/Sao_Paulo')
    
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
        'Referer': base_url,
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Dnt': '1'
    }

    # Configuração avançada do cloudscraper
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True,
            'mobile': False
        },
        delay=10,
        debug=False
    )
    
    # Tentar carregar sessão persistente
    session_file = 'session.cache'
    if os.path.exists(session_file):
        try:
            with open(session_file, 'rb') as f:
                session_state = pickle.load(f)
            scraper = cloudscraper.create_scraper(sess=session_state)
        except Exception as e:
            print(f"Erro ao carregar sessão: {e}")

    try:
        response = fetch_url(scraper, url, headers)
        
        # Verificação robusta de bloqueio
        block_phrases = ["Access Denied", "cloudflare", "security check", "captcha"]
        if any(phrase in response.text for phrase in block_phrases):
            raise Exception("Bloqueio detectado: Reinicie a sessão")
        
        if response.status_code != 200:
            raise Exception(f"Status code error: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        matches = []
        
        table = soup.select_one('.table-main')
        if not table:
            raise Exception("Tabela de resultados não encontrada")
        
        for row in table.select('tr:not(.center):not(.dark)'):
            try:
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
                
                # Extrair odds
                odds_home = row.select_one('.odds-cell:nth-child(4)')
                odds_draw = row.select_one('.odds-cell:nth-child(5)')
                odds_away = row.select_one('.odds-cell:nth-child(6)')
                
                odds = {}
                if odds_home: 
                    odds['home'] = float(odds_home.text.strip())
                if odds_draw: 
                    odds['draw'] = float(odds_draw.text.strip())
                if odds_away: 
                    odds['away'] = float(odds_away.text.strip())
                
                # Gerar ID único com hash
                match_str = f"{league}{home_team}{away_team}{datetime.now(tz)}"
                match_id = hashlib.sha256(match_str.encode()).hexdigest()[:12]
                
                match_data = {
                    'id': match_id,
                    'league': league,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_goals': home_goals,
                    'away_goals': away_goals,
                    'minute': 90,
                    'status': 'Finalizado',
                    'timestamp': datetime.now(tz).isoformat(),
                    'odds': odds if odds else None
                }
                
                # Validação com Pydantic
                validated_match = Match(**match_data)
                matches.append(validated_match.dict())
                
                time.sleep(random.uniform(0.5, 2.5))
                
            except Exception as e:
                print(f"Erro ao processar linha: {e}")
                continue
        
        # Salvar sessão para reutilização
        with open(session_file, 'wb') as f:
            pickle.dump(scraper.session, f)
        
        return matches
    
    except Exception as e:
        print(f"Erro no scraping: {e}")
        # Remover sessão inválida
        if os.path.exists(session_file):
            os.remove(session_file)
        return []

if __name__ == "__main__":
    proxies = {
        'http': os.getenv('HTTP_PROXY'),
        'https': os.getenv('HTTPS_PROXY')
    } if os.getenv('USE_PROXY') else None
        
    matches = scrape_oddsportal()
    
    data = {
        "metadata": {
            "source": "oddsportal",
            "schema_version": "1.1",
            "generated_at": datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat(),
            "timezone": "America/Sao_Paulo"
        },
        "status": {
            "success": bool(matches),
            "matches_processed": len(matches) if matches else 0,
            "error_count": 0 if matches else 1
        },
        "matches": matches if matches else []
    }
    
    # Escrita atômica para evitar corrupção
    temp_file = 'live-matches.tmp'
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    os.replace(temp_file, 'live-matches.json')
