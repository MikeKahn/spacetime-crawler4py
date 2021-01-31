import re
from lxml import html
from lxml.html.clean import Cleaner
from urllib.parse import urlparse
from urllib.parse import urldefrag
from urllib.parse import urljoin
from urllib.parse import parse_qs
import datetime
import os

# domains that are valid to crawl
valid_domains = "ics.uci.edu|cs.uci.edu|informatics.uci.edu|stat.uci.edu|today.uci.edu/department" \
                "/information_computer_sciences "
# enable logging
logging = True
# output file
output = None
# min text size of a page to analyze
min_size = 0
# max size of a page to analyze
max_size = 1e9
# min portion of a page that should be text
min_part = 0.1


def scraper(url, resp):
    links = extract_next_links(url, resp)
    urls = []
    for link in links:
        # parse the url
        parsed = urlparse(link)
        # separate the queries
        queries = parse_qs(parsed.query, keep_blank_values=False)
        # check if the link is a redirect to another url
        if "url" in queries:
            link = queries["url"][0]
        else:
            # remove queries
            link = urljoin(link, parsed.path)
        if is_valid(link):
            # append the url with fragment removed
            urls.append(urldefrag(link)[0])
    return urls


def extract_next_links(url, resp):
    if resp.status == 200:
        # log(f"{resp.status} - {url}\n")
        # get total size of page
        page_size = len(resp.raw_response.content)
        # initialize text size
        text_size = 0
        # convert content into html data
        parser = html.HTMLParser(remove_blank_text=True)
        data = html.document_fromstring(resp.raw_response.content, parser)
        # clean the document
        cleaner = Cleaner(style=True)
        cleaned = cleaner.clean_html(data)
        text = cleaned.text_content()
        text_size = len(text)
        log(f"{resp.status} - {url} - {text_size}/{page_size}\n")
        # return all the links in the page
        return [link for element, attribute, link, pos in data.iterlinks()]
    else:
        log(f"{resp.status} - {url} - {resp.error}\n")
    return list()


def is_valid(url):
    try:
        parsed = urlparse(url)
        # Check if valid http/https link
        if parsed.scheme not in set(["http", "https"]):
            return False
        # Check if not a web page
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1|php"
            + r"|thmx|mso|arff|rtf|jar|csv|xml"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False
        # Check if a valid domain
        return re.search(rf"({valid_domains})", url)
    except TypeError:
        print("TypeError for ", parsed)
        raise


# outputs message to a log file
def log(message):
    # if logging disabled, do not output anything
    if not logging:
        return
    global output
    # open log file if not already open
    if not output:
        # ensure data folder exists
        if not os.path.isdir('data'):
            os.mkdir('data')
            # open log file
        output = open(f"data/{datetime.datetime.now()}.txt", "w")
    # write message to file
    output.write(message)
    # flush file to save output
    output.flush()
