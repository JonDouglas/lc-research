from Bio import Entrez
import requests
import json
import textwrap
from datetime import datetime, timedelta
from IPython.display import HTML, display
import time
from urllib.error import HTTPError
from urllib.parse import urlencode

# HTML color codes
GREEN = "#92C353"
YELLOW = "#F2C94C"
RED = "#E57373"

# Global variables to store API links
pubmed_api_link = ""
preprint_api_link = ""
researchsquare_api_link = ""

def search_pubmed(query, page, results_per_page, max_retries=3, initial_delay=1):
    global pubmed_api_link
    start = (page - 1) * results_per_page
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": results_per_page,
        "sort": "date",
        "retstart": start,
        "retmode": "json"
    }
    pubmed_api_link = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{urlencode(params)}"
    
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            handle = Entrez.esearch(db="pubmed", term=query, retmax=results_per_page, sort="date", retstart=start, retmode="json")
            results = json.load(handle)
            handle.close()
            return results
        except HTTPError as e:
            if e.code == 500 and attempt < max_retries - 1:
                print(f"Encountered HTTP 500 error. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise  # Re-raise the exception if it's not a 500 error or we've run out of retries
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            raise

    raise Exception("Max retries reached. Unable to complete the request.")

def fetch_pubmed_details(id_list, max_retries=3, initial_delay=1):
    ids = ",".join(id_list)
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            handle = Entrez.efetch(db="pubmed", id=ids, retmode="xml")
            results = Entrez.read(handle)
            handle.close()
            return results
        except HTTPError as e:
            if e.code == 500 and attempt < max_retries - 1:
                print(f"Encountered HTTP 500 error. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise  # Re-raise the exception if it's not a 500 error or we've run out of retries
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            raise

    raise Exception("Max retries reached. Unable to complete the request.")

def search_preprints(query, page, results_per_page):
    global preprint_api_link
    start = (page - 1) * results_per_page
    preprint_api_link = f"https://api.biorxiv.org/covid19/{start}/{results_per_page}?text={query}"
    
    base_url = "https://api.biorxiv.org/covid19"
    url = f"{base_url}/{start}/{results_per_page}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    params = {'text': query}
    response = requests.get(url, headers=headers, params=params)
    return response.json()

def format_author_list(authors):
    def format_author(author):
        last_name = author.get('LastName', '')
        initials = author.get('Initials', '')
        if last_name and initials:
            return f"{last_name} {initials}"
        elif last_name:
            return last_name
        elif initials:
            return initials
        else:
            return "Unknown Author"

    if len(authors) > 5:
        return ", ".join(format_author(author) for author in authors[:5]) + ", et al."
    return ", ".join(format_author(author) for author in authors)

def parse_date(date_obj):
    if isinstance(date_obj, dict):
        year = date_obj.get('Year')
        month = date_obj.get('Month', '01')
        day = date_obj.get('Day', '01')
        date_str = f"{year}-{month}-{day}"
    else:
        date_str = date_obj
    
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed_date
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m")
        except ValueError:
            try:
                return datetime.strptime(date_str, "%Y")
            except ValueError:
                return None

def get_color_by_date(date):
    if date is None:
        return RED
    days_ago = (datetime.now() - date).days
    if days_ago <= 3:
        return GREEN
    elif days_ago <= 7:
        return YELLOW
    else:
        return RED

def get_matching_queries(text, queries):
    return [q for q in queries if q.lower() in text.lower()]

def filter_articles_by_timeframe(articles, timeframe):
    today = datetime.now().date()
    if timeframe == "today":
        start_date = today
    elif timeframe == "week":
        start_date = today - timedelta(days=7)
    elif timeframe == "month":
        start_date = today - timedelta(days=30)
    else:
        return articles  # Return all articles if timeframe is not recognized

    return [article for article in articles if article['date'].date() >= start_date]

def search_researchsquare(query, page, results_per_page, timeframe=None):
    global researchsquare_api_link
    base_url = "https://www.researchsquare.com/api/search"
    
    end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    params = {
        "unified": query,
        "limit": results_per_page,
        "offset": (page - 1) * results_per_page,
        "postedAfter": start_date,
        "postedBefore": end_date
    }
    researchsquare_api_link = f"{base_url}?{urlencode(params)}"
    
    response = requests.get(base_url, params=params)
    return response.json()

def get_researchsquare_color(date):
    days_ago = (datetime.now() - date).days
    if days_ago <= 7:
        return '#8FBC8F'  # Dark Sea Green (less bright)
    elif days_ago <= 30:
        return '#DEB887'  # Burlywood (less bright)
    else:
        return '#CD5C5C'  # Indian Red (less bright)

def search_articles(query, page=1, results_per_page=100, timeframe=None, max_future_months=6):
    pubmed_results = search_pubmed(query, page, results_per_page)
    pubmed_papers = fetch_pubmed_details(pubmed_results['esearchresult']['idlist'])
    preprint_results = search_preprints(query, page, results_per_page)
    researchsquare_results = search_researchsquare(query, page, results_per_page, timeframe)

    all_articles = []
    current_date = datetime.now()
    max_future_date = current_date + timedelta(days=30 * max_future_months)

    def is_valid_date(date):
        return current_date - timedelta(days=365*5) <= date <= max_future_date

    def get_pubmed_color(date):
        days_ago = (current_date - date).days
        if days_ago <= 7:
            return '#2E8B57'  # Sea Green (darker)
        elif days_ago <= 30:
            return '#DAA520'  # Goldenrod
        else:
            return '#B22222'  # Firebrick (darker red)

    def get_preprint_color(date):
        days_ago = (current_date - date).days
        if days_ago <= 7:
            return '#98FB98'  # Pale Green (lighter)
        elif days_ago <= 30:
            return '#FAFAD2'  # Light Goldenrod Yellow
        else:
            return '#FFA07A'  # Light Salmon

    # Process PubMed results
    for paper in pubmed_papers['PubmedArticle']:
        try:
            # Extract date
            if 'PubmedData' in paper and 'History' in paper['PubmedData']:
                dates = paper['PubmedData']['History']
                online_date = None
                for date in dates:
                    if isinstance(date, dict) and 'PubStatus' in date and date['PubStatus'] == 'pubmed':
                        online_date = datetime(int(date['Year']), int(date['Month']), int(date['Day']))
                        break
                if not online_date:
                    online_date = max(datetime(int(date['Year']), int(date['Month']), int(date['Day'])) for date in dates if isinstance(date, dict))
            else:
                continue

            if not is_valid_date(online_date):
                continue

            color = get_pubmed_color(online_date)

            # Extract other information
            article = paper.get('MedlineCitation', {}).get('Article', {})
            title = article.get('ArticleTitle', 'No Title Available')
            authors = ', '.join([f"{author.get('LastName', '')} {author.get('Initials', '')}" 
                                 for author in article.get('AuthorList', [])[:3]])
            if len(article.get('AuthorList', [])) > 3:
                authors += ' et al.'
            journal = article.get('Journal', {}).get('Title', 'Unknown Journal')
            pmid = paper.get('MedlineCitation', {}).get('PMID', 'Unknown PMID')
            
            # Extract DOI
            article_id_list = paper.get('PubmedData', {}).get('ArticleIdList', [])
            doi = next((id_obj for id_obj in article_id_list if id_obj.attributes.get('IdType') == 'doi'), None)
            doi_link = f'<a href="https://doi.org/{doi}" target="_blank">{doi}</a>' if doi else 'Not available'

            date_str = online_date.strftime("%Y-%m-%d")

            all_articles.append({
                'date': online_date,
                'color': color,
                'html': f"""
                <div style="margin-bottom: 20px; padding: 10px; background-color: {color};">
                    <h3>{title}</h3>
                    <p><strong>Authors:</strong> {authors}</p>
                    <p><strong>Journal:</strong> {journal}</p>
                    <p><strong>Date:</strong> {date_str}</p>
                    <p><strong>PMID:</strong> {pmid}</p>
                    <p><strong>DOI:</strong> {doi_link}</p>
                </div>
                """,
                'query': query
            })
        except Exception as e:
            continue

    # Process Preprint results
    for paper in preprint_results['collection']:
        try:
            date_posted = datetime.strptime(paper['date'], '%Y-%m-%d')
            if not is_valid_date(date_posted):
                continue
            color = get_preprint_color(date_posted)

            title = paper.get('title', 'No Title Available')
            authors = ', '.join([author.get('name', 'Unknown Author') for author in paper.get('authors', [])[:3]])
            if len(paper.get('authors', [])) > 3:
                authors += ' et al.'
            server = paper.get('server', 'Unknown Server')
            doi = paper.get('doi', '')
            doi_link = f'<a href="https://doi.org/{doi}" target="_blank">{doi}</a>' if doi else 'Not available'

            date_str = date_posted.strftime("%Y-%m-%d")

            all_articles.append({
                'date': date_posted,
                'color': color,
                'html': f"""
                <div style="margin-bottom: 20px; padding: 10px; background-color: {color};">
                    <h3>{title}</h3>
                    <p><strong>Authors:</strong> {authors}</p>
                    <p><strong>Server:</strong> {server}</p>
                    <p><strong>Date:</strong> {date_str}</p>
                    <p><strong>DOI:</strong> {doi_link}</p>
                </div>
                """,
                'query': query
            })
        except Exception as e:
            continue

    # Process ResearchSquare results
    for paper in researchsquare_results['result']['data']:
        try:
            date_posted = datetime.strptime(paper['posted_at'], '%Y-%m-%d %H:%M:%S')
            if not is_valid_date(date_posted):
                continue
            color = get_researchsquare_color(date_posted)

            title = paper.get('title', 'No Title Available')
            authors = ', '.join([author.strip() for author in paper.get('authors', '').split(',')[:3]])
            if len(paper.get('authors', '').split(',')) > 3:
                authors += ' et al.'
            article_identity = paper.get('article_identity', '')
            doi_version = paper.get('doi_version', '1')
            rs_link = f'<a href="https://www.researchsquare.com/article/{article_identity}/v{doi_version}" target="_blank">ResearchSquare Link</a>'

            date_str = date_posted.strftime("%Y-%m-%d")

            all_articles.append({
                'date': date_posted,
                'color': color,
                'html': f"""
                <div style="margin-bottom: 20px; padding: 10px; background-color: {color};">
                    <h3>{title}</h3>
                    <p><strong>Authors:</strong> {authors}</p>
                    <p><strong>Server:</strong> ResearchSquare</p>
                    <p><strong>Date:</strong> {date_str}</p>
                    <p><strong>Link:</strong> {rs_link}</p>
                </div>
                """,
                'query': query
            })
        except Exception as e:
            print(f"Error processing ResearchSquare paper: {str(e)}")
            continue

    # Filter articles based on timeframe
    if timeframe:
        all_articles = filter_articles_by_timeframe(all_articles, timeframe)

    return all_articles

def combine_and_display_results(queries, page=1, results_per_page=200, timeframe=None, max_future_months=6):
    all_results = []
    seen_titles = {}  # Dictionary to track unique titles and their queries
    
    for query in queries:
        results = search_articles(query, page, results_per_page, timeframe, max_future_months)
        for result in results:
            # Extract title from the HTML content
            title_start = result['html'].find('<h3>') + 4
            title_end = result['html'].find('</h3>')
            title = result['html'][title_start:title_end].strip()
            
            if title in seen_titles:
                # If we've seen this title before, append the new query
                seen_titles[title]['queries'].append(query)
            else:
                # If this is a new title, add it to our tracking
                result['queries'] = [query]
                seen_titles[title] = result
    
    # Convert the dictionary values back to a list
    all_results = list(seen_titles.values())

    # Sort all articles by date, most recent first
    all_results.sort(key=lambda x: x['date'], reverse=True)

    # Generate HTML output
    html_output = f"""
    <h3>Search terms: {', '.join(queries)}</h3>
    <p>{len(all_results)} total results</p>
    <p>Page {page}</p>
    <p>Timeframe: {timeframe if timeframe else 'All time'}</p>
    """

    for article in all_results:
        html_output += f"""
        <div style="margin-bottom: 20px; padding: 10px; background-color: {article['color']};">
            {article['html']}
            <p><strong>Matching Queries:</strong> {', '.join(article['queries'])}</p>
        </div>
        """

    display(HTML(html_output))

# Example usage:
# search_and_display_articles("long covid", page=1, results_per_page=200)
