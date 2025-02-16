import time
import random
import re
from urllib.parse import urljoin
from requests_html import HTMLSession
from trafilatura import extract

def fetch_article_content(url):
    """Extrai título, conteúdo e imagem principal de forma estruturada"""
    
    # Configuração anti-ban melhorada
    headers = {
        'User-Agent': random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) AppleWebKit/605.1.15'
        ]),
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    time.sleep(random.uniform(1, 3))  # Delay aleatório

    try:
        with HTMLSession() as session:
            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Extração estruturada
            result = {
                'title': _extract_title(response),
                'content': _extract_content(response),
                'images': [_extract_main_image(response)],  # Lista de imagens para manter compatibilidade
                'url': url,
                'keywords': []  # Lista vazia de keywords para manter compatibilidade
            }
            
            # Pós-processamento
            result['content'] = _clean_content(result['content'])
            
            # Validações
            if not result['content']:
                raise ValueError("Não foi possível extrair o conteúdo do artigo")
                
            if not result['title']:
                raise ValueError("Não foi possível extrair o título do artigo")
                
            if not result['images'][0]:
                raise ValueError("Não foi possível extrair a imagem principal do artigo")
            
            return result

    except Exception as e:
        print(f"❌ Erro ao extrair conteúdo: {str(e)}")
        return None

def fetch_main_article_image(url):
    """Função auxiliar para extrair apenas a imagem principal do artigo"""
    try:
        with HTMLSession() as session:
            response = session.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            return _extract_main_image(response)
    except Exception as e:
        print(f"❌ Erro ao extrair imagem principal: {str(e)}")
        return None

def _extract_title(response):
    """Extrai título com prioridade para Open Graph"""
    og_title = response.html.xpath('//meta[contains(@property, "og:title")]/@content', first=True)
    twitter_title = response.html.xpath('//meta[contains(@name, "twitter:title")]/@content', first=True)
    return og_title or twitter_title or response.html.find('title', first=True).text

def _extract_content(response):
    """Extrai conteúdo principal com fallback hierárquico"""
    if 'wp-content' in response.text:
        return extract(response.text, favor_precision=True)
    elif 'medium.com' in response.url:
        article = response.html.find('article', first=True)
        return article.text if article else None
    return extract(response.text)  # Fallback genérico

def _extract_main_image(response):
    """Extrai imagem principal com múltiplas estratégias"""
    og_image = response.html.xpath('//meta[contains(@property, "og:image")]/@content', first=True)
    twitter_image = response.html.xpath('//meta[contains(@name, "twitter:image")]/@content', first=True)
    
    if not og_image and not twitter_image:
        # Fallback: Primeira imagem do artigo com tamanho relevante
        images = response.html.find('article img')
        if images:
            return urljoin(response.url, images[0].attrs.get('src'))
    
    return urljoin(response.url, og_image or twitter_image)

def _clean_content(text):
    """Limpeza avançada do conteúdo"""
    if not text:
        return None
    # Remove múltiplas quebras de linha
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove espaços em excesso
    return re.sub(r'[^\S\n]{2,}', ' ', text).strip()

if __name__ == "__main__":
    url = input("Digite a URL do artigo: ").strip()
    
    print("\nProcessando... (Técnicas anti-ban ativas)\n")
    result = fetch_article_content(url)
    
    if not result:
        print("❌ Erro ao extrair conteúdo do artigo")
    else:
        print(f"\n{'='*50}")
        print(f"Título: {result['title']}")
        print(f"\nImagem Principal: {result['images'][0]}")
        print(f"\nConteúdo:\n{'-'*40}\n{result['content']}")
        print(f"\n{'='*50}\nExtração concluída!")