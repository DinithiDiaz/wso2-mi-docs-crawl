import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import csv
import logging

# Setup logging
logging.basicConfig(filename='crawling.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

visited_urls = set()
checked_correct_urls = set()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

VALID_DOMAINS = [
    "https://apim.docs.wso2.com/en/latest",
    "https://apim.docs.wso2.com/en/4.3.0"
]

def remove_fragment(url):
    # Parse the URL
    parsed_url = urlparse(url)
    # Rebuild the URL without the fragment
    url_without_fragment = urlunparse(parsed_url._replace(fragment=''))
    return url_without_fragment

def join_url(base, link):
    parsed_url = urlparse(base)
    
    # Ensure the path ends with a slash if there's no fragment or query
    if not parsed_url.path.endswith('/') and not parsed_url.path.split('/')[-1].count('.'):
        base = urlunparse(parsed_url._replace(path=parsed_url.path + '/'))
    
    return urljoin(base, link)

def is_file_path(url):
    parsed_url = urlparse(url)
    return bool(parsed_url.path.split('/')[-1].count('.'))

def is_same_domain(url1, url2):
    return urlparse(url1).netloc == urlparse(url2).netloc

def is_valid_domain(url):
    return any(url.startswith(domain) for domain in VALID_DOMAINS)

def check_url(url, target_redirect, csv_writer, parent_url=None):

    if url in checked_correct_urls:
        return

    logging.info(f"Checking: {url}")

    try:
        link_response = requests.get(url, headers=headers, allow_redirects=True)
        if link_response.status_code in (301, 302) and link_response.headers.get('Location') == target_redirect:
            visited_urls.add(url)
            logging.error(f"{url} redirects to {link_response.headers.get('Location')} and is found on {parent_url}")
            csv_writer.writerow([url, link_response.headers.get('Location'), parent_url, '301/302 redirect to target URL'])
            return False  # Error found
        elif link_response.url == target_redirect:
            visited_urls.add(url)
            logging.error(f"{url} redirects to {link_response.url} and is found on {parent_url}")
            csv_writer.writerow([url, link_response.url, parent_url, 'Redirect to target URL'])
            return False  # Error found
        elif link_response.status_code == 404:
            visited_urls.add(url)
            logging.error(f"{url} returns 404 error and is found on {parent_url}")
            csv_writer.writerow([url, None, parent_url, '404 Not Found'])
            return False  # Error found
    except requests.RequestException as e:
        logging.error(f"Failed to fetch {url} and is found in {parent_url}: {e}")
        csv_writer.writerow([url, None, parent_url, f"Failed to fetch {url} and is found in {parent_url}: {e}"])
        return False  # Error found

    checked_correct_urls.add(url)
    return True  # No error found

def find_redirects(url, target_redirect, base_url, csv_writer, max_depth=300, depth=0):
    if depth > max_depth or url in visited_urls:
        return
    
    visited_urls.add(url)
    
    if is_file_path(url):
        logging.info(f"Skipped Crawling: {url} is a file path")
        return

    logging.info(f"Crawling: {url}")
    print(f"Crawling: {url}")

    try:
        response = requests.get(url, headers=headers)
    except requests.RequestException as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all <nav> elements with aria-label="Navigation"
    nav_elements = soup.find_all('nav', {'aria-label': 'Navigation'})

    # Collect links to exclude
    exclude_links = []
    for nav in nav_elements:
        # Find the ul directly inside nav
        ul = nav.find('ul', recursive=False)
        if ul:
            # Find li elements directly inside this ul
            for li in ul.find_all('li', recursive=False):
                if 'md-nav__item--active' not in li.get('class', []):
                    exclude_links.extend(li.find_all('a', href=True))

    for link in soup.find_all('a', href=True):
        # Exclude <a> tags that are in the exclude_links list
        if link in exclude_links:
            continue

        full_url = join_url(url, link['href'])
        full_url = remove_fragment(full_url) #url with fragments are identical to url without it 

        if is_same_domain(full_url, base_url):
            if not is_valid_domain(full_url):
                logging.info(f"{full_url} is a version mismatch and is found on {url} and href is {link['href']}")
                csv_writer.writerow([full_url, None, url, 'Version mismatch'])
            else:
                if check_url(full_url, target_redirect, csv_writer, parent_url=url):
                    find_redirects(full_url, target_redirect, base_url, csv_writer, max_depth, depth+1)
        else:
            check_url(full_url, target_redirect, csv_writer, parent_url=url)

def crawl_website(base_url, target_redirect, csv_writer):
    find_redirects(base_url, target_redirect, base_url, csv_writer)

if __name__ == "__main__":
    base_url = "https://apim.docs.wso2.com/en/latest/"  # Replace with the base URL of the website you want to crawl
    target_redirect = "https://apim.docs.wso2.com/en/latest/page-not-found/"  # Replace with the URL to check for redirects

    with open('redirects.csv', mode='w', newline='', encoding='utf-8') as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow(['Source URL', 'Redirected URL', 'Containing Page', 'Description'])
        crawl_website(base_url, target_redirect, csv_writer)

    print("Crawling completed!!!")
    logging.info("Crawling compleeted!!!")