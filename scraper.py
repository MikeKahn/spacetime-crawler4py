import re
from lxml import html
from lxml.html.clean import Cleaner
from urllib.parse import urlparse
from urllib.parse import urldefrag
from urllib.parse import urljoin
from urllib.parse import parse_qs
import datetime
import os
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import operator
from operator import itemgetter

# you may need to download nltk data in order to make use of the nltk functionality
nltk.download('stopwords')

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
# used to get list of tokens in a page, commented out for now
#tokenFile = None
# dict mapping all tokens to total frequency 
wordFreq = None
# dict mapping all pages to page length (# of filtered tokens)
pageLen = None


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
        # tokenize the text on the page
        tk = tokenize_words(url, text)
        # calculate length of the page (# of filtered tokens)
        tk_page_len = page_length(url, tk)
        # update the total frequencies of all words from all crawled pages
        word_frequencies(tk)
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

# uses nltk word_tokenizer to tokenize the text from a url, returns a list of tokens
def tokenize_words(url, text):
    # preprocessing step, converts all characters to lowercase
    words = text.replace("  ", " ").replace("\n", " ").lower().strip()
    # the tokenizing step
    tokens = word_tokenize(words)
    # this is the list of valid tokens
    ftokens = []
    # iterates through full token list to filter out invalid tokens
    for t in tokens:
        # do not include the token if it is a stopword
        if t in stopwords.words():
            continue
        # do not include the token if there are no alphanumeric characters
        if not re.match('[A-Za-z0-9]+', t):
            continue
        ftokens.append(t)
    # the commented code below is for recording the tokens and text from each page; not necessary for the assignment, but kept for reference
    #global tokenFile
    #if not tokenFile:
    #    tokenFile = open("tokenFile.txt", "w")
    #tokenFile.write(str(url) + ": " + str(ftokens) + "\n")
    #tokenFile.write(str(url) + ": " + words + "\n")
    #tokenFile.flush()
    # write sorted file mapping URL's to page length (# of valid tokens)
    return ftokens

# evaluates the page length of a url (# of valid tokens), updates to a dictionary that tracks page lengths for all urls
# also returns the page lenth    
def page_length(url, ftokens):
    # call pageLen dict
    global pageLen
    # creates dict if it does not exist yet, creates folder for word_data if it does not exist yet
    if not pageLen:
        if not os.path.isdir('word_data'):
            os.mkdir('word_data')
        pageLen = {}
        pageLen[url] = len(ftokens)
    else:
        # only updates dict if current page length is greater than or equal to the longest page length found so far
        longPage = max(pageLen, key=pageLen.get)
        if len(ftokens) > pageLen[longPage]:
            pageLen = {}
            pageLen[url] = len(ftokens)
        elif len(ftokens) == pageLen[longPage]:
                pageLen[url] = len(ftokens)
        else:
            return len(ftokens)
    # update pageLen dict
    pageLenFile = open("word_data/pageLengths.csv", 'w')
    for i in pageLen:
        toWrite = i + "," + str(pageLen[i]) + "\n"
        pageLenFile.write(toWrite)
    pageLenFile.close()
    # return page length
    return len(ftokens)

# updates word frequency dict with words from current page    
def word_frequencies(ftokens):
    # call wordFreq dict
    global wordFreq
    # creates dict if it does not exist yet, creates folder for word_data if it does not exist yet
    if not wordFreq:
        if not os.path.isdir('word_data'):
            os.mkdir('word_data')
        wordFreq = {}
    # update wordFreq dict, iterates through each token in token list
    for t in ftokens:
        if t not in wordFreq:
            wordFreq[t] = 0
        wordFreq[t] += 1
    # sort pageLen dict (highest frequencies first)
    wordFreqR = dict(sorted(wordFreq.items(), key=operator.itemgetter(1), reverse=True))
    # write dict to file
    wordFreqFile = open("word_data/wordFreqs.csv", 'w')
    for i in wordFreqR:
        toWrite = i + "," + str(wordFreqR[i]) + "\n"
        wordFreqFile.write(toWrite)
    wordFreqFile.close()
    # update dict to sorted dict
    wordFreq = wordFreqR
    